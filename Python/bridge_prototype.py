import serial
import subprocess
import firebase_admin
from firebase_admin import credentials, firestore
import time
import logging
from datetime import datetime
import threading

## Configurazione
PORTNAME = 'COM3'
DEVICE_ID = 'iliadbox-77F2A2' 
FIREBASE_CREDENTIALS = "Python/baris-iot-vito-firebase-adminsdk-baww0-f6eece4154.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Bridge:
    def __init__(self, port, device_id):
        self.port = port
        self.device_id = device_id
        self.ser = None
        self.db = None
        self.inbuffer = b''
        self.lock_state = True  
        self.porta_aperta_state = False
        self.allarme_state = False
        self.running = True

    def setup_serial(self):
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            logging.info(f"Connesso alla porta seriale {self.port}")
        except serial.SerialException as e:
            logging.error(f"Errore nella connessione seriale: {e}")
            exit()

    def get_ssid(self):
        try:
            results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"])
            results = results.decode("latin1")
            results = results.replace("\r", "")
            lines = results.split("\n")
            ssid_line = next((line for line in lines if "SSID" in line and "BSSID" not in line), None)
            if ssid_line:
                ssid = ssid_line.split(":")[1].strip()
                logging.info(f"SSID rilevato: {ssid}")
                self.device_id = ssid  
                return ssid
            else:
                logging.error("SSID non trovato.")
                return "Unknown_SSID"
        except Exception as e:
            logging.error(f"Errore nel recupero SSID: {e}")
            return "Unknown_SSID"

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
                        self.update_firestore(True, False)
                    elif data_str == "000":
                        self.update_firestore(False, True)
                    elif data_str == "EFF":
                        self.update_alarm(True)
                    elif data_str == "D":
                        self.update_alarm(False)
                    else:
                        logging.error(f"Messaggio sconosciuto: {data_str}")

                except UnicodeDecodeError as e:
                    logging.error(f"Errore decodifica: {e}")
            except Exception as e:
                logging.error(f"Errore lettura pacchetto: {e}")
                time.sleep(1)

    def update_firestore(self, porta_aperta, lock):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc = self.db.collection("dispositivi").document(self.device_id)
        doc.update({
            "porta_aperta": porta_aperta,
            "lock": lock,
            "last_access": timestamp
        })
        stato_str = "aperta" if porta_aperta else "chiusa"
        doc.collection("access_logs").add({"timestamp": timestamp, "stato": stato_str})
        self.lock_state = lock
        self.porta_aperta_state = porta_aperta
        logging.info("Aggiornato Firestore con stato corrente.")

    def update_alarm(self, stato_allarme):
        doc = self.db.collection("dispositivi").document(self.device_id)
        doc.update({"allarme": stato_allarme})
        self.allarme_state = stato_allarme
        if stato_allarme:
            logging.warning("Allarme attivato su Firestore.")
        else:
            logging.info("Allarme disattivato su Firestore.")

    def write_to_firebase(self, ssid):
        try:
            doc = self.db.collection("dispositivi").document(ssid)
            doc.set({
                "SSID": ssid,
                "lock": True,
                "porta_aperta": False,
                "last_access": "Never",
                "latitude": "",
                "longitude": "",
                "allarme": False
            })
            logging.info(f"Document {ssid} inizializzato in Firestore.")
            self.lock_state = True
            self.porta_aperta_state = False
            self.allarme_state = False
            logging.info("Stati iniziali impostati: lock=True, porta_aperta=False, allarme=False")
        except Exception as e:
            logging.error(f"Errore nell'inizializzazione Firestore: {e}")

    def read_from_firebase(self):
        try:
            doc_ref = self.db.collection("dispositivi").document(self.device_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                logging.info(f'Document data: {data}')
                new_lock_state = data.get("lock")
                new_porta_aperta_state = data.get("porta_aperta")
                new_allarme_state = data.get("allarme")

                # Controlla se lo stato della serratura è cambiato
                if self.lock_state != new_lock_state:
                    self.lock_state = new_lock_state
                    if new_lock_state:
                        logging.info("Invio comando blocco serratura.")
                        self.ser.write("0".encode())
                    else:
                        logging.info("Invio comando sblocco serratura.")
                        self.ser.write("1".encode())

                # Se allarme su Firestore è false ma allarme_state è true, disattiva allarme
                if self.allarme_state and not new_allarme_state:
                    logging.info("Disattivazione allarme da Firestore.")
                    self.ser.write("D".encode())
                    self.allarme_state = new_allarme_state
                elif not self.allarme_state and new_allarme_state:
                    # In questo scenario l'allarme viene attivato solo da Arduino (EFF)
                    self.allarme_state = new_allarme_state
            else:
                logging.warning("Nessun documento trovato!")
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


if __name__ == '__main__':
    bridge = Bridge(port=PORTNAME, device_id=DEVICE_ID)
    bridge.setup_serial()

    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
        bridge.db = firestore.client()
        logging.info("Connesso a Firebase Firestore.")
    except Exception as e:
        logging.error(f"Errore nell'inizializzazione di Firebase: {e}")
        exit()

    ssid = bridge.get_ssid()
    bridge.write_to_firebase(ssid)

    bridge.start_remote_thread()

    try:
        while bridge.running:
            bridge.read_from_firebase()
            time.sleep(2)
    except KeyboardInterrupt:
        logging.info("Interrotto dall'utente.")
    except Exception as e:
        logging.error(f"Errore nel loop principale: {e}")
    finally:
        bridge.stop()