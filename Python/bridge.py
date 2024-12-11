import serial
import time
import logging
from datetime import datetime
import threading

class Bridge:
    def __init__(self, port, device_id, db, name, latitude, longitude):
        self.port = port
        self.device_id = device_id
        self.db = db
        self.ser = None
        self.inbuffer = b''
        self.lock_state = True
        self.porta_aperta_state = False
        self.allarme_state = False
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.running = True

        # Inizializzazione del device se non esiste
        doc_ref = self.db.collection("devices").document(self.device_id)
        doc = doc_ref.get()
        if not doc.exists:
            doc_ref.set({
                "name": self.name,
                "lock": True,
                "porta_aperta": False,
                "allarme": False,
                "latitude": float(self.latitude),
                "longitude": float(self.longitude),
                "maintenance_mode": False,
                "last_access": "Never"
            })
            logging.info(f"Dispositivo {self.device_id} inizializzato in Firestore.")

    def setup_serial(self):
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            logging.info(f"Connesso alla porta seriale {self.port}")
        except serial.SerialException as e:
            logging.error(f"Errore nella connessione seriale: {e}")
            exit()

    def check_door_remote_thread(self):
        while self.running:
            try:
                byte = self.ser.read(1)
                if not byte:
                    continue
                if byte != b'\xfb':
                    continue
                self.inbuffer = b''

                while True:
                    byte = self.ser.read(1)
                    if not byte:
                        continue
                    if byte == b'\xfa':
                        break
                    self.inbuffer += byte

                try:
                    data_str = self.inbuffer.decode('utf-8').strip()
                    logging.info(f"Pacchetto ricevuto: {data_str}")

                    if data_str == "001":
                        # Porta aperta
                        self.update_device_state(porta_aperta=True, lock=False)
                    elif data_str == "000":
                        # Porta chiusa e serratura bloccata
                        self.update_device_state(porta_aperta=False, lock=True)
                    elif data_str == "EFF":
                        # Effrazione -> allarme attivato
                        self.update_alarm(True)
                    elif data_str == "D":
                        # Disattiva allarme
                        self.update_alarm(False)
                    else:
                        logging.error(f"Messaggio sconosciuto: {data_str}")

                except UnicodeDecodeError as e:
                    logging.error(f"Errore decodifica: {e}")
            except Exception as e:
                logging.error(f"Errore lettura pacchetto: {e}")
                time.sleep(1)

    def update_device_state(self, porta_aperta: bool, lock: bool):
        timestamp = datetime.utcnow().isoformat()
        doc = self.db.collection("devices").document(self.device_id)
        doc.update({
            "porta_aperta": porta_aperta,
            "lock": lock,
            "last_access": timestamp
        })
        stato_str = "aperta" if porta_aperta else "chiusa"
        doc.collection("access_logs").add({
            "timestamp": timestamp,
            "action": stato_str,
            "user_id": None
        })
        self.lock_state = lock
        self.porta_aperta_state = porta_aperta
        logging.info("Aggiornato Firestore con stato corrente del dispositivo.")

    def update_alarm(self, stato_allarme):
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
            logging.warning("Allarme attivato su Firestore.")
        else:
            logging.info("Allarme disattivato su Firestore.")

    def read_from_firebase(self):
        try:
            doc_ref = self.db.collection("devices").document(self.device_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                logging.info(f'Document data: {data}')
                new_lock_state = data.get("lock", True)
                new_porta_aperta_state = data.get("porta_aperta", False)
                new_allarme_state = data.get("allarme", False)

                if self.lock_state != new_lock_state:
                    self.lock_state = new_lock_state
                    if new_lock_state:
                        logging.info("Invio comando blocco serratura ad Arduino.")
                        self.ser.write("0".encode())
                    else:
                        logging.info("Invio comando sblocco serratura ad Arduino.")
                        self.ser.write("1".encode())

                if self.allarme_state and not new_allarme_state:
                    logging.info("Disattivazione allarme da Firestore - invio comando 'D' ad Arduino.")
                    self.ser.write("D".encode())
                    self.allarme_state = new_allarme_state
                elif not self.allarme_state and new_allarme_state:
                    self.allarme_state = new_allarme_state
            else:
                logging.warning("Nessun documento trovato per il dispositivo!")
        except Exception as e:
            logging.error(f"Errore nella lettura da Firestore: {e}")

    def start_remote_thread(self):
        remote_thread = threading.Thread(target=self.check_door_remote_thread, daemon=True)
        remote_thread.start()

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        logging.info("Bridge fermato.")