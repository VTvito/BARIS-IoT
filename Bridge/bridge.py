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
        self.lock_state = True
        self.porta_aperta_state = False
        self.allarme_state = False
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.running = True
        # varibili per heartbeat arduino
        self.last_arduino_packet_time = time.time()
        self.arduino_offline_notified = False


# Configura la connessione seriale con Arduino
    def setup_serial(self):
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            # attesa per assicurare che la connessione sia avvenuta
            time.sleep(2)
            logging.info(f"Connesso alla porta seriale {self.port}")
            self.sync_with_arduino()
        except serial.SerialException as e:
            logging.error(f"Errore nella connessione seriale: {e}")
            exit()

# Riattiva la connessione seriale in caso di disconnessione -- gestisce "riconnessioni a caldo" senza riavviare il bridge.
    def reopen_serial(self):
        # chiudi connessione attuale
        if self.ser and self.ser.is_open:
            self.ser.close()
        # tentativo di connessione
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            time.sleep(2)
            logging.info(f"Riconnesso alla porta seriale {self.port}")
            self.sync_with_arduino()
        except serial.SerialException as e:
            logging.error(f"Errore nella riconnessione seriale: {e}")


# Allinea lo stato di Firestore con Arduino durante l'avvio del sistema.
# Aggiorna lo stato di blocco, allarme e inizializza Firestore se non esiste il documento associato al dispositivo.
    def sync_with_arduino(self):
        # Legge stato da Firestore
        doc_ref = self.db.collection("devices").document(self.device_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            desired_lock = data.get("lock", True)
            desired_allarme = data.get("allarme", False)
            
            # Arduino appena acceso: lock=true, allarme=false di default.
            if not desired_lock:
                logging.info("Sync: Firestore dice lock=false, invio '1' per sbloccare Arduino.")
                self.ser.write("1".encode())
                self.lock_state = False
            
            # Se Firestore dice allarme=true, invia "A".
            if desired_allarme:
                logging.info("Sync: Firestore dice allarme=true, invio 'A' per attivare allarme su Arduino.")
                self.ser.write("A".encode())
                self.allarme_state = True
                logging.info("Sync completata. Stato allineato secondo Firestore.")

            # Porta aperta: Arduino determina lo stato dalla distanza. Firestore ne tiene solo traccia.
            # In caso di discrepanza, ci fidiamo di Arduino, il bridge aspetta i pacchetti da Arduino per aggiornarla.
                        
        else:
            logging.warning("Sync: Nessun documento trovato per il dispositivo. Uso stato base.")
            # Se non esiste il documento del device, lo inizializzo
            doc_ref.set({
                "name": self.name,
                "lock": True,
                "porta_aperta": False,
                "allarme": False,
                "latitude": float(self.latitude),
                "longitude": float(self.longitude),
                "last_access": "Never"
            })
            logging.info(f"Dispositivo {self.name} inizializzato in Firestore.")  
            # Arduino è già allo stato base, niente da fare.
            self.lock_state = True
            self.allarme_state = False
            self.porta_aperta_state = False


# Gestisce la ricezione e il parsing dei pacchetti inviati da Arduino -- gestisto in modo async con thread separato
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
                    
                    # Ricevuto un pacchetto da Arduino - Aggiornamento heartbeat
                    self.last_arduino_packet_time = time.time()  # Aggiorna ultimo pacchetto ricevuto
                    if self.arduino_offline_notified:
                        self.send_notification_to_admins("Arduino Online", f"Arduino per il device {self.name} è di nuovo online!")
                    self.arduino_offline_notified = False  # Arduino è vivo, resetta notifica offline

                    if data_str == "001":
                        # Porta aperta
                        self.update_device_state(porta_aperta=True, lock=False)
                    elif data_str == "000":
                        # Porta chiusa e serratura bloccata
                        self.update_device_state(porta_aperta=False, lock=True)
                    elif data_str == "EFF":
                        # Effrazione -> allarme attivato
                        self.update_alarm(True)
                        self.send_notification_to_admins("Allarme Effrazione!", f"Effrazione rilevata su {self.name}!")
                    elif data_str == "D":
                        # Disattiva allarme
                        self.update_alarm(False)
                    elif data_str == "NOLOCK":
                        # Serrattura da più di 60s
                        self.send_notification_to_admins("Serratura aperta troppo a lungo!", f"Serratura aperta a lungo Su {self.name}!")
                    elif data_str == "HB":
                        # heartbeat
                        continue
                    else:
                        logging.error(f"Messaggio sconosciuto: {data_str}")

                except UnicodeDecodeError as e:
                    logging.error(f"Errore decodifica: {e}")
            except serial.SerialException as e:
                logging.error(f"Errore lettura seriale: {e}")
                self.reopen_serial()
                time.sleep(5) # attesa prima di riprovare
            except Exception as e:
                logging.error(f"Errore lettura pacchetto: {e}")
                time.sleep(1)


# Monitora l'attività di Arduino tramite heartbeat e invia notifiche se non riceve pacchetti per più di 5 minuti.
    def check_arduino_offline(self):
        while self.running:
            # Controlla ogni 60 secondi (1 minuto)
            time.sleep(60)
            now = time.time()
            diff = now - self.last_arduino_packet_time
            # Soglia: 5 minuti (300 secondi)
            if diff > 300 and not self.arduino_offline_notified:
                logging.warning("Nessun pacchetto da Arduino da più di 5 minuti. Arduino offline?")
                self.send_notification_to_admins("Arduino Offline", f"La connettività con la serratura è interrotta da + di 5 minuti per il device {self.name}.")
                self.arduino_offline_notified = True


# Aggiorna lo stato della porta e della serratura su Firestore
    def update_device_state(self, porta_aperta: bool, lock: bool):
        timestamp = datetime.utcnow().isoformat()
        doc = self.db.collection("devices").document(self.device_id)
        doc.update({
            "porta_aperta": porta_aperta,
            "lock": lock,
            "last_access": timestamp
        })
        # Aggiunge un log nella sottocollezione access_logs
        stato_str = "porta aperta" if porta_aperta else "porta chiusa"
        doc.collection("access_logs").add({
            "timestamp": timestamp,
            "action": stato_str,
            "user_id": None
        })
        self.lock_state = lock
        self.porta_aperta_state = porta_aperta
        logging.info("Aggiornato Firestore con stato corrente del dispositivo.")


# Gestisce l'attivazione e la disattivazione dell'allarme, registrando gli eventi su Firestore.
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


# Sincronizza lo stato del dispositivo leggendo modifiche su Firestore (utenti controllano il dispositivo da remoto tramite l’app)
# Reagisce a cambiamenti dello stato della serratura o dell’allarme.
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
                        self.send_notification_to_admins("Serratura sbloccata", f"La serratura {self.name} è stata sbloccata da un utente")


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


#  Invia notifiche in app agli admin in caso di eventi critici (es.: allarme attivato, serratura aperta troppo a lungo).
    def send_notification_to_admins(self, title, body):
        admins = self.db.collection('users').where('role', '==', 'admin').stream()
        tokens = []
        for admin_doc in admins:
            data = admin_doc.to_dict()
            user_tokens = data.get('fcm_tokens', [])
            tokens.extend(user_tokens)
        
        logging.info(f"Admin FCM Tokens: {tokens}")

        if not tokens:
            logging.warning("Nessun token FCM trovato per gli admin.")
            return

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
                logging.info(f"Notifica inviata a {token}, risposta: {response}")
            except Exception as e:
                logging.error(f"Errore nell'invio della notifica a {token}: {e}")


# Thread per monitoraggio stato di connettività di Arduino
    def start_offline_check_thread(self):
        offline_thread = threading.Thread(target=self.check_arduino_offline, daemon=True)
        offline_thread.start()

# Thread per monitorare gli eventi remoti
    def start_remote_thread(self):
        remote_thread = threading.Thread(target=self.check_door_remote_thread, daemon=True)
        remote_thread.start()

# Termina il funzionamento del bridge, chiudendo la connessione seriale.
    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.send_notification_to_admins("Bridge stoppato", f"Bridge stoppato su {self.name}")
        logging.info("Bridge fermato.")