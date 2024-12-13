import logging
import time
from bridge import Bridge
from bridge_config import init_firebase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# parametri di configurazione passati al bridge relativo alla serratura
PORTNAME = 'COM3'
DEVICE_ID = 'iliadbox-77F2A2' 
FIREBASE_CREDENTIALS = "Python/baris-iot-vito-firebase-adminsdk-baww0-19695e55a0.json"
NAME = "Casa"
LATITUDE = "45.4642"
LONGITUDE = "9.19"

if __name__ == '__main__':
    db = init_firebase(FIREBASE_CREDENTIALS)
    bridge = Bridge(port=PORTNAME, device_id=DEVICE_ID, db=db, name=NAME, latitude=LATITUDE, longitude=LONGITUDE)
    bridge.setup_serial()

    # Avvia il thread per ascoltare i pacchetti da Arduino
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