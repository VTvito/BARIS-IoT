import logging
import time
from bridge import Bridge
from bridge_config import init_firebase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration parameters for the Bridge, related to the lock device
PORTNAME = 'COM3'
DEVICE_ID = 'Home_77F2A2' 
FIREBASE_CREDENTIALS = "/your/path/.json"

# The new name, latitude, and longitude you want to store in Firestore
NAME = "Home"
LATITUDE = "44.1111"
LONGITUDE = "11.1111"

if __name__ == '__main__':
    # Initialize the Firebase DB reference
    db = init_firebase(FIREBASE_CREDENTIALS)

    # Create a Bridge instance
    bridge = Bridge(
        port=PORTNAME, 
        device_id=DEVICE_ID, 
        db=db, 
        name=NAME, 
        latitude=LATITUDE, 
        longitude=LONGITUDE
    )
    
    # Set up the serial connection
    bridge.setup_serial()

    # Start the thread that listens for packets from Arduino
    bridge.start_remote_thread()
    # Start the thread that checks if Arduino is offline (heartbeat monitor)
    bridge.start_offline_check_thread()

    # Main loop to read device state from Firestore (polling every 2s)
    try:
        while bridge.running:
            bridge.read_from_firebase()
            time.sleep(2)
    except KeyboardInterrupt:
        logging.info("Stopped by the user (KeyboardInterrupt).")
    except Exception as e:
        logging.error(f"Error in the main loop: {e}")
    finally:
        bridge.stop()
