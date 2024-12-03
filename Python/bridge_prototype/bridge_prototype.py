import serial
import subprocess
import firebase_admin
from firebase_admin import credentials, firestore
import time
import logging
from datetime import datetime

## Configuration
PORTNAME = 'COM3'

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Bridge:  # inizializzo la classe bridge

    def __init__(self):
        self.ser = None
        self.db = None
        self.lock_state = None  # Initialize as None to set based on Firestore
        self.count = 0

    def setup_serial(self):    # funzione per inizializzare la porta serial e il buffer per la raccolta dati e pacchetti proveniente da arduino
        try:
            self.ser = serial.Serial(PORTNAME, 9600, timeout=1)
            logging.info(f"Connesso alla porta seriale {PORTNAME}")
        except serial.SerialException as e:
            logging.error(f"Errore nella connessione seriale: {e}")
            exit()

    def get_ssid(self): # funzione per ricavare il nome dell' ssid a cui il bridge è connesso
        try:
            results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"])
            results = results.decode("latin1")  # needed in python 3
            results = results.replace("\r", "")
            ls = results.split("\n")
            ssid_line = next((line for line in ls if "SSID" in line and "BSSID" not in line), None)
            if ssid_line:
                SSID = ssid_line.split(":")[1].strip()
                logging.info(f"SSID rilevato: {SSID}")
                return SSID
            else:
                logging.error("SSID non trovato.")
                return "Unknown_SSID"
        except Exception as e:
            logging.error(f"Errore nel recupero SSID: {e}")
            return "Unknown_SSID"

    def check_door_remote(self, ssid): # funzione che riceve da arduino lo status della porta DA REMOTO
        # Attendi l'inizio del pacchetto
        while True:
            byte = self.ser.read(1)
            if byte == b'\xfb':
                logging.info("Inizio pacchetto rilevato.")
                break

        # Leggi il tipo di messaggio
        message_type = self.ser.read(1)
        if not message_type:
            logging.error("Tipo di messaggio non ricevuto.")
            return

        # Leggi i dati fino alla fine del pacchetto
        data = b''
        while True:
            byte = self.ser.read(1)
            if byte == b'\xfa':
                logging.info("Fine pacchetto rilevato.")
                break
            elif byte:
                data += byte
            else:
                continue

        try:
            data_str = data.decode('utf-8')
            status = data_str  # "001" o "000"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Timestamp leggibile
            logging.info(f"Stato Porta: {status}, Timestamp: {timestamp}")
        except Exception as e:
            logging.error(f"Errore nel parsing dei dati: {e}")
            return

        doc = self.db.collection("dispositivi").document(ssid)
        if status == "001": # porta aperta
            doc.update({"porta": True, "lock": False, "last_access": timestamp})
            # Aggiungi log di accesso
            doc.collection("access_logs").add({"timestamp": timestamp, "stato": "aperta"})
            logging.info("Aggiornato Firestore: Porta Aperta e Log Aggiunto")
        elif status == "000": # porta chiusa
            doc.update({"porta": False, "lock": True, "last_access": timestamp})
            # Aggiungi log di accesso
            doc.collection("access_logs").add({"timestamp": timestamp, "stato": "chiusa"})
            logging.info("Aggiornato Firestore: Porta Chiusa e Log Aggiunto")

    def write_to_firebase(self, ssid): # funzione eseguita la prima volta per inizializzare la collection relativa al nuovo arduino collegato
        doc = self.db.collection("dispositivi").document(ssid)
        doc.set({"SSID": ssid, "lock": True, "porta": False, "last_access": "Never"})
        logging.info(f"Document {ssid} inizializzato in Firestore.")
        self.lock_state = True  # Update local lock_state
        logging.info(f"lock_state set to {self.lock_state}")

    def read_from_firebase(self, ssid): # funzione che controlla l'eventuale cambiamento di variabile della serratura
        try:
            doc_ref = self.db.collection(u'dispositivi').document(ssid)
            doc = doc_ref.get()
            if doc.exists:
                logging.info(f'Document data: {doc.to_dict()}')
            else:
                logging.warning(u'No such document!')
                return

            output = doc.to_dict()
            new_lock_state = output.get('lock')
            new_porta_state = output.get('porta')
            last_access = output.get('last_access')
            logging.info(f"Lock state corrente: {self.lock_state}, Nuovo lock state: {new_lock_state}")
            logging.info(f"Porta state corrente: {new_porta_state}, Last Access: {last_access}")

            if self.lock_state == new_lock_state:
                self.count +=1
                if self.count >= 3:
                    logging.info("No changes detected for 3 consecutive checks. Continuing...")
                    self.count =0
                else:
                    logging.info("ATTESA PER CAMBIAMENTI...")
                time.sleep(5)
                return

            self.lock_state = new_lock_state  # Update local lock_state
            self.count =0

            # Controllo delle inconsistenze tra lock e porta
            if new_lock_state and new_porta_state:
                logging.warning("Inconsistenza rilevata: Serratura bloccata ma porta aperta!")
                self.activate_alarm()

            # Aggiorna lo stato della serratura se necessario
            if new_lock_state: # Blocco serratura
                logging.info("Blocco serratura")
                self.ser.write("0".encode())
            else: # Sblocco serratura
                logging.info("Sblocco serratura")
                self.ser.write("1".encode())
                self.check_door_remote(ssid) # Controlla lo stato della porta dopo lo sblocco

        except Exception as e:
            logging.error(f"Errore nella lettura da Firestore: {e}")

    def activate_alarm(self):
        logging.critical("Allarme attivato! Inconsistenza tra lock e porta.")
        # Implementa notifiche o altre azioni di allarme qui
        # Per semplicità, possiamo attivare un allarme sonoro sul bridge o inviare una notifica
        # Esempio: stampare un messaggio di allarme
        print("ALLARME! Potenziale effrazione rilevata!")
        # Puoi anche inviare una notifica via email o altro

if __name__ == '__main__':
    br = Bridge()
    br.setup_serial()
    try:
        # Percorso relativo
        cred = credentials.Certificate("Python/bridge_prototype/baris-iot-vito-firebase-adminsdk-baww0-f6eece4154.json")
        firebase_admin.initialize_app(cred)   # inizializzazione database
        br.db = firestore.client()  # richiamo alle api di firebase
        logging.info("Connesso a Firebase Firestore.")
    except Exception as e:
        logging.error(f"Errore nell'inizializzazione di Firebase: {e}")
        exit()

    ssid = br.get_ssid()
    br.write_to_firebase(ssid)
    while True:
        try:
            time.sleep(2)
            br.read_from_firebase(ssid)
        except KeyboardInterrupt:
            logging.info("Interrotto dall'utente.")
            break
        except Exception as e:
            logging.error(f"Errore nel loop principale: {e}")