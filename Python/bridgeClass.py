import serial
import subprocess
import firebase_admin
from firebase_admin import credentials, firestore
import time

## Configuration
PORTNAME = 'COM3'
lock_state = False
count = 0

class Bridge:  # inizializzo la classe bridge

    def __init__(self):
        self.ser = None
        self.inbuffer = []
        self.db = None

    def setup(self):    # funzione per inizializzare la porta serial e il buffer per la raccolta dati e pacchetti proveniente da arduino
        self.ser = serial.Serial(PORTNAME, 9600, timeout=0)
        self.inbuffer = []

    def get_ssid(self): # funzione per ricavare il nome dell' ssid a cui il bridge è connesso
        results = subprocess.check_output(["netsh", "wlan", "show", "interfaces"])
        results = results.decode("latin1")  # needed in python 3
        results = results.replace("\r", "")
        ls = results.split("\n")[4:]
        ssids = [ls[x] for x in range(0, len(ls), 5)]
        string = ssids[3]
        SSID = string[string.find(":")+2:]
        print(SSID)
        return SSID

    def check_door_remote(self, ssid): # funzione che riceve da arduino lo status della porta DA REMOTO
        door = ""
        while(self.ser.read(1) != b'\xfb'):
            continue
        print("Inizio pacchetto")
        while True:
            code = self.ser.read(1)
            if code == b'\xfa':
                print("fine pacchetto\n")
                print(self.inbuffer)
                break
            elif code == b'':
                continue
            else:
                self.inbuffer.append(code)

        door = ''.join([str(self.inbuffer[i], 'UTF-8') for i in range(len(self.inbuffer))])
        print(door)
        self.inbuffer = []
        doc = self.db.collection("dispositivi").document(ssid)
        if door == "001": # porta aperta, non è possibile chiudere la serratura, si attende che l'utente la chiuda
            doc.update({"porta": True, "lock": True})
            self.check_door_remote(ssid)
        else: # porta chiusa, la serratura viene chiusa
            doc.update({"porta": False, "lock": False})

        return door

    def write_to_firebase(self, ssid): # funzione eseguita la prima volta per inizializzare la collection relativa al nuovo arduino collegato
        doc = self.db.collection("dispositivi").document(ssid)
        doc.set({"SSID": ssid, "lock": True, "porta": False})

    def read_from_firebase(self, ssid, lock_state, count): # funzione che controlla l'eventuale cambiamento di variabile della serratura
        doc_ref = self.db.collection(u'dispositivi').document(ssid)
        doc = doc_ref.get()
        if doc.exists:
            print(f'Document data: {doc.to_dict()}')
        else:
            print(u'No such document!')

        output = doc.to_dict()
        lock_state = output.get('lock')
        print(lock_state)
        time.sleep(5)

        doc = doc_ref.get()
        newoutput = doc.to_dict()
        new_lock_state = newoutput.get('lock')

        if lock_state == new_lock_state and count < 3: # se non c'è stata alcuna modifica controllo altre 3 volte e poi esco
            print("WAITING FOR CHANGES....\n")
            count += 1
            self.read_from_firebase(ssid, lock_state, count)
        if lock_state == True and new_lock_state == False: # chiudo serratura
            print("Blocco serratura\n")
            self.ser.write("0".encode())
        if lock_state == False and new_lock_state == True: # sblocco serratura
            print("Sblocco serratura\n")
            self.ser.write("1".encode())
            self.check_door_remote(ssid) # richiamo la funzione per controllare se la porta viene poi chiusa

if __name__ == '__main__':
    br = Bridge()
    br.setup()
    cred = credentials.Certificate("iot-unimore-firebase-adminsdk-g94mz-af797deabe.json")   # credenziali di firestore
    firebase_admin.initialize_app(cred)   # inizializzazione database
    br.db = firestore.client()  # richiamo alle api di firebase
    ssid = br.get_ssid()
    br.write_to_firebase(ssid)
    while True:
        time.sleep(2)
        br.read_from_firebase(ssid, lock_state, count)
        count = 0
