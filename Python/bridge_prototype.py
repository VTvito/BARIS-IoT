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
DEVICE_ID = 'iliadbox-77F2A2'  # Assicurati che corrisponda all'SSID

FIREBASE_CREDENTIALS = "BARIS-IoT/Python/baris-iot-vito-firebase-adminsdk-baww0-f6eece4154.json"

# Configura il logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class Bridge:
    def __init__(self, port, device_id):
        self.port = port
        self.device_id = device_id
        self.ser = None
        self.db = None
        self.inbuffer = b''  # Buffer interno per la comunicazione seriale
        self.lock_state = None  # Serratura (True = chiusa, False = aperta)
        self.porta_aperta_state = None  # Porta (True = aperta, False = chiusa)
        self.running = True  # Flag per il thread

    def setup_serial(self):
        """Inizializza la connessione seriale."""
        try:
            self.ser = serial.Serial(self.port, 9600, timeout=1)
            logging.info(f"Connesso alla porta seriale {self.port}")
        except serial.SerialException as e:
            logging.error(f"Errore nella connessione seriale: {e}")
            exit()

    def get_ssid(self):
        """Recupera l'SSID del Wi-Fi a cui è connesso il bridge."""
        try:
            results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"])
            results = results.decode("latin1")
            results = results.replace("\r", "")
            lines = results.split("\n")
            ssid_line = next((line for line in lines if "SSID" in line and "BSSID" not in line), None)
            if ssid_line:
                ssid = ssid_line.split(":")[1].strip()
                logging.info(f"SSID rilevato: {ssid}")
                self.device_id = ssid  # Imposta l'ID del dispositivo come l'SSID
                return ssid
            else:
                logging.error("SSID non trovato.")
                return "Unknown_SSID"
        except Exception as e:
            logging.error(f"Errore nel recupero SSID: {e}")
            return "Unknown_SSID"

    def check_door_remote_thread(self):
        """Thread che riceve lo stato della porta dall'Arduino e aggiorna Firestore."""
        while self.running:
            try:
                # Aspetta l'inizio del pacchetto
                byte = self.ser.read(1)
                if not byte:
                    continue  # Nessun dato, continua
                if byte != b'\xfb':
                    continue  # Ignora fino a trovare \xfb

                logging.info("Inizio pacchetto rilevato.")
                self.inbuffer = b''  # Reset buffer

                # Leggi fino alla fine del pacchetto
                while True:
                    byte = self.ser.read(1)
                    if not byte:
                        continue  # Nessun dato, continua
                    if byte == b'\xfa':
                        logging.info("Fine pacchetto rilevato.")
                        break
                    self.inbuffer += byte

                # Decodifica il buffer
                try:
                    # Rimuovi eventuali caratteri non validi
                    data_str = self.inbuffer.decode('utf-8').strip()
                    logging.info(f"Pacchetto ricevuto: {data_str}")

                    if data_str == "001":  # Porta aperta
                        porta_aperta = True
                        lock = False
                    elif data_str == "000":  # Porta chiusa
                        porta_aperta = False
                        lock = True
                    else:
                        logging.error(f"Messaggio sconosciuto: {data_str}")
                        continue  # Ignora messaggi sconosciuti

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    logging.info(f"Stato Porta: {porta_aperta}, Serratura: {lock}, Timestamp: {timestamp}")

                    # Aggiorna Firestore
                    doc = self.db.collection("dispositivi").document(self.device_id)
                    doc.update({
                        "porta_aperta": porta_aperta,
                        "lock": lock,
                        "last_access": timestamp
                    })

                    # Aggiungi log dell'accesso
                    stato = "aperta" if porta_aperta else "chiusa"
                    doc.collection("access_logs").add({"timestamp": timestamp, "stato": stato})
                    logging.info("Aggiornato Firestore con lo stato corrente.")

                except UnicodeDecodeError as e:
                    logging.error(f"Errore nella decodifica del pacchetto: {e}")
                except Exception as e:
                    logging.error(f"Errore nell'interpretazione del pacchetto: {e}")

            except Exception as e:
                logging.error(f"Errore nella lettura del pacchetto: {e}")
                time.sleep(1)  # Evita di bloccare il thread in caso di errore



    def write_to_firebase(self, ssid):
        """Inizializza Firestore con i valori di default."""
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
            logging.info("Stati iniziali impostati: lock=True, porta_aperta=False")
        except Exception as e:
            logging.error(f"Errore nell'inizializzazione Firestore: {e}")


    def read_from_firebase(self):
        """Legge Firestore e invia comandi all'Arduino."""
        try:
            doc_ref = self.db.collection("dispositivi").document(self.device_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                logging.info(f'Document data: {data}')
                new_lock_state = data.get("lock")
                new_porta_aperta_state = data.get("porta_aperta")

                # Controlla se lo stato della serratura è cambiato
                if self.lock_state != new_lock_state:
                    self.lock_state = new_lock_state
                    if new_lock_state:  # Serratura bloccata
                        logging.info("Invio comando blocco serratura.")
                        self.ser.write("0".encode())
                    else:  # Serratura sbloccata
                        logging.info("Invio comando sblocco serratura.")
                        self.ser.write("1".encode())
            else:
                logging.warning("Nessun documento trovato!")
        except Exception as e:
            logging.error(f"Errore nella lettura da Firestore: {e}")


    def check_alarm(self):
        """Implementa la logica di controllo dell'allarme."""
        # Implementare la logica specifica per il controllo dell'allarme
        # Ad esempio, controllare Firestore e inviare notifiche
        pass

    def check_card_local(self):
        """Implementa la logica per controllare la carta locale."""
        # Implementare la logica specifica per il controllo della carta
        pass

    def get_lock_value(self):
        """Recupera lo stato della serratura."""
        return self.lock_state

    def check_lock(self):
        """Implementa la logica per controllare lo stato della serratura."""
        # Implementare la logica specifica per il controllo della serratura
        pass

    def start_remote_thread(self):
        """Avvia il thread per ricevere dati dall'Arduino."""
        remote_thread = threading.Thread(target=self.check_door_remote_thread, daemon=True)
        remote_thread.start()

    def stop(self):
        """Ferma il bridge."""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        logging.info("Bridge fermato.")


if __name__ == '__main__':
    bridge = Bridge(port=PORTNAME, device_id=DEVICE_ID)
    bridge.setup_serial()

    try:
        # Inizializza Firestore
        cred = credentials.Certificate(FIREBASE_CREDENTIALS)
        firebase_admin.initialize_app(cred)
        bridge.db = firestore.client()
        logging.info("Connesso a Firebase Firestore.")
    except Exception as e:
        logging.error(f"Errore nell'inizializzazione di Firebase: {e}")
        exit()

    ssid = bridge.get_ssid()
    bridge.write_to_firebase(ssid)

    # Avvia il thread per ricevere dati dall'Arduino
    bridge.start_remote_thread()

    # Loop principale per leggere Firestore e inviare comandi
    try:
        while bridge.running:
            bridge.read_from_firebase()
            time.sleep(2)  # Attendi prima di leggere di nuovo
    except KeyboardInterrupt:
        logging.info("Interrotto dall'utente.")
    except Exception as e:
        logging.error(f"Errore nel loop principale: {e}")
    finally:
        bridge.stop()