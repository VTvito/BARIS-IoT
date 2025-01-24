import serial
import time
import logging
from datetime import datetime
import threading
from firebase_admin import messaging

class Bridge:
    def __init__(self, port, device_id, db, name, latitude, longitude):
        self.port = port
        self.device_id = device_id
        self.db = db
        self.ser = None
        self.inbuffer = b''

        # Local variables to track lock/door/alarm status
        self.lock_state = True
        self.porta_aperta_state = False
        self.allarme_state = False

        self.name = name
        self.latitude = latitude
        self.longitude = longitude

        # General control flag
        self.running = True

        # Variables for Arduino heartbeat
        self.last_arduino_packet_time = time.time()
        self.arduino_offline_notified = False

    def setup_serial(self):
        """
        Initialize the serial connection with Arduino.
        If successful, synchronize the state with Firestore.
        """
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            time.sleep(2)  # small delay to ensure serial port is ready
            logging.info(f"Connected to serial port {self.port}")
            self.sync_with_arduino()
        except serial.SerialException as e:
            logging.error(f"Serial connection error: {e}")
            exit()

    def reopen_serial(self):
        """
        If the serial connection drops, this method closes the current
        port (if open) and attempts to reconnect again.
        """
        if self.ser and self.ser.is_open:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            time.sleep(2)
            logging.info(f"Reconnected to serial port {self.port}")
            self.sync_with_arduino()
        except serial.SerialException as e:
            logging.error(f"Reconnection error: {e}")

    def sync_with_arduino(self):
        """
        Synchronize Firestore state with Arduino state when the system starts.
        It reads the doc from Firestore:
          - If the doc does not exist, create it with default fields.
          - If it exists, update lat/long and check if lock or alarm states
            differ from Arduino's default to send commands (e.g. '1' or 'A').

        By default, Arduino starts with lock=true, alarm=false, door closed.
        """
        doc_ref = self.db.collection("devices").document(self.device_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()

            # (1) Update lat/long in Firestore, in case they've changed
            # from the main.py config
            doc_ref.update({
                "latitude": float(self.latitude),
                "longitude": float(self.longitude)
            })

            desired_lock = data.get("lock", True)
            desired_allarme = data.get("allarme", False)
            
            # If Firestore says lock=false, we send '1' to unlock Arduino
            if not desired_lock:
                logging.info("Sync: Firestore says lock=false, sending '1' to unlock on Arduino.")
                self.ser.write("1".encode())
                self.lock_state = False
            
            # If Firestore says allarme=true, we send 'A' to activate alarm on Arduino
            if desired_allarme:
                logging.info("Sync: Firestore says allarme=true, sending 'A' to Arduino.")
                self.ser.write("A".encode())
                self.allarme_state = True

            logging.info("Sync completed. Firestore doc existed; lat/long updated, lock/alarm checked.")
        else:
            # If the Firestore document doesn't exist, create it
            logging.warning("Sync: No document found for this device. Creating it with default fields.")
            doc_ref.set({
                "name": self.name,
                "lock": True,
                "porta_aperta": False,
                "allarme": False,
                "latitude": float(self.latitude),
                "longitude": float(self.longitude),
                "last_access": "Never"
            })
            logging.info(f"Device {self.name} initialized in Firestore.")
            # Arduino is already in the default state (lock=true, alarm=false).
            self.lock_state = True
            self.allarme_state = False
            self.porta_aperta_state = False

    def check_door_remote_thread(self):
        """
        This thread constantly reads from the serial port for incoming data/packets from Arduino.
        The packets start with 0xFB and end with 0xFA, with the content in between.
        """
        while self.running:
            try:
                byte = self.ser.read(1)
                if not byte:
                    continue
                if byte != b'\xfb':
                    # If it's not the start delimiter, ignore it
                    continue
                
                # Start reading payload
                self.inbuffer = b''

                while True:
                    byte = self.ser.read(1)
                    if not byte:
                        continue
                    if byte == b'\xfa':
                        # End delimiter reached
                        break
                    self.inbuffer += byte

                # Decode the message
                try:
                    data_str = self.inbuffer.decode('utf-8').strip()
                    logging.info(f"Packet received: {data_str}")
                    
                    # Update heartbeat
                    self.last_arduino_packet_time = time.time()
                    if self.arduino_offline_notified:
                        # If we had notified that Arduino was offline, it's now back
                        self.send_notification_to_admins("Arduino Online", 
                            f"Arduino for device {self.name} is back online!")
                    self.arduino_offline_notified = False

                    # Interpret the payload
                    if data_str == "001":
                        # Door opened
                        self.update_device_state(porta_aperta=True, lock=False)
                    elif data_str == "000":
                        # Door closed & lock engaged
                        self.update_device_state(porta_aperta=False, lock=True)
                    elif data_str == "EFF":
                        # Intrusion -> alarm triggered
                        self.update_alarm(True)
                        self.send_notification_to_admins("Intrusion Alarm!", 
                            f"Intrusion detected on {self.name}!")
                    elif data_str == "D":
                        # Disable alarm
                        self.update_alarm(False)
                    elif data_str == "NOLOCK":
                        # Your custom message: "Lock not re-engaged in time"
                        self.send_notification_to_admins("Lock remains open too long!", 
                            f"The lock on {self.name} remained unlocked too long!")
                    elif data_str == "HB":
                        # Heartbeat: do nothing except note we got a packet
                        continue
                    else:
                        logging.error(f"Unknown message from Arduino: {data_str}")

                except UnicodeDecodeError as e:
                    logging.error(f"Decoding error: {e}")
            
            except serial.SerialException as e:
                logging.error(f"Serial read error: {e}")
                # Attempt to reopen serial if disconnected
                self.reopen_serial()
                time.sleep(5)
            except Exception as e:
                logging.error(f"Error reading packet: {e}")
                time.sleep(1)

    def check_arduino_offline(self):
        """
        Monitors whether Arduino stops sending packets for more than 5 minutes.
        Sends a notification if it remains silent beyond this threshold.
        """
        while self.running:
            time.sleep(60)  # check every 60 seconds
            now = time.time()
            diff = now - self.last_arduino_packet_time
            # If we haven't heard from Arduino for more than 5 minutes (300 sec)
            if diff > 300 and not self.arduino_offline_notified:
                logging.warning("No packets from Arduino for more than 5 minutes. Possibly offline.")
                self.send_notification_to_admins("Arduino Offline", 
                    f"No packets from the lock device for over 5 minutes: {self.name}.")
                self.arduino_offline_notified = True

    def update_device_state(self, porta_aperta: bool, lock: bool):
        """
        Updates the device state (door open/closed, lock status) in Firestore,
        and logs the change in the access_logs sub-collection.
        """
        timestamp = datetime.utcnow().isoformat()
        doc = self.db.collection("devices").document(self.device_id)
        doc.update({
            "porta_aperta": porta_aperta,
            "lock": lock,
            "last_access": timestamp
        })

        state_str = "porta aperta" if porta_aperta else "porta chiusa"
        doc.collection("access_logs").add({
            "timestamp": timestamp,
            "action": state_str,
            "user_id": None
        })

        self.lock_state = lock
        self.porta_aperta_state = porta_aperta
        logging.info("Firestore updated with the current device state.")

    def update_alarm(self, stato_allarme):
        """
        Sets the alarm state in Firestore and logs the change in access_logs.
        """
        timestamp = datetime.utcnow().isoformat()
        doc = self.db.collection("devices").document(self.device_id)
        doc.update({"allarme": stato_allarme})
        
        self.allarme_state = stato_allarme
        action = "allarme_on" if stato_allarme else "allarme_off"
        doc.collection('access_logs').add({
            "timestamp": timestamp,
            "user_id": None,
            "action": action
        })

        if stato_allarme:
            logging.warning("Alarm activated in Firestore.")
        else:
            logging.info("Alarm deactivated in Firestore.")

    def read_from_firebase(self):
        """
        Periodically called in the main loop to check if the user changed the
        lock/alarm state in Firestore, and sends commands to Arduino accordingly.
        """
        try:
            doc_ref = self.db.collection("devices").document(self.device_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                logging.info(f'Document data: {data}')
                
                new_lock_state = data.get("lock", True)
                new_porta_aperta_state = data.get("porta_aperta", False)
                new_allarme_state = data.get("allarme", False)

                # If the lock state changed from what we currently have
                if self.lock_state != new_lock_state:
                    self.lock_state = new_lock_state
                    if new_lock_state:
                        # Firestore wants lock=true -> send "0" to Arduino
                        logging.info("Sending lock command '0' to Arduino.")
                        self.ser.write("0".encode())
                    else:
                        # Firestore wants lock=false -> send "1" to Arduino
                        logging.info("Sending unlock command '1' to Arduino.")
                        self.ser.write("1".encode())
                        self.send_notification_to_admins(
                            "Lock Unlocked",
                            f"The lock {self.name} was unlocked by a user."
                        )

                # If the alarm state changed
                if self.allarme_state and not new_allarme_state:
                    # We have alarm active, but Firestore says alarm=false
                    logging.info("Alarm deactivation from Firestore - sending 'D' to Arduino.")
                    self.ser.write("D".encode())
                    self.allarme_state = new_allarme_state
                elif not self.allarme_state and new_allarme_state:
                    # We have alarm off, but Firestore says alarm=true
                    self.allarme_state = new_allarme_state
                    # If you want to also send a command "A" to Arduino here, you can.
                    # It's done in sync_with_arduino or you can do it here as well if needed.

            else:
                logging.warning("No Firestore document found for this device!")
        except Exception as e:
            logging.error(f"Error reading from Firestore: {e}")

    def send_notification_to_admins(self, title, body):
        """
        Sends push notifications to all admins (users with role='admin') using FCM tokens
        stored in 'fcm_tokens' field.
        """
        admins = self.db.collection('users').where('role', '==', 'admin').stream()
        tokens = []
        for admin_doc in admins:
            data = admin_doc.to_dict()
            user_tokens = data.get('fcm_tokens', [])
            tokens.extend(user_tokens)
        
        logging.info(f"Admin FCM Tokens: {tokens}")

        if not tokens:
            logging.warning("No FCM tokens found for admins.")
            return

        # Send notifications to each token
        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=token
            )
            try:
                response = messaging.send(message)
                logging.info(f"Notification sent to {token}, response: {response}")
            except Exception as e:
                logging.error(f"Error sending notification to {token}: {e}")

    def start_offline_check_thread(self):
        """
        Launches a thread that periodically checks if Arduino is offline
        (no packets received for > 5 minutes).
        """
        offline_thread = threading.Thread(target=self.check_arduino_offline, daemon=True)
        offline_thread.start()

    def start_remote_thread(self):
        """
        Launches a thread that constantly reads and interprets packets
        from Arduino (handle door open/close, alarm triggers, etc.).
        """
        remote_thread = threading.Thread(target=self.check_door_remote_thread, daemon=True)
        remote_thread.start()

    def stop(self):
        """
        Stops the main loop, closes the serial connection,
        and sends a notification that the Bridge is stopping.
        """
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.send_notification_to_admins("Bridge Stopped", f"Bridge stopped on {self.name}")
        logging.info("Bridge stopped.")