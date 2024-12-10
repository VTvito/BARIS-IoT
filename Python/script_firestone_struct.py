import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Percorso al file di credenziali del tuo service account Firebase
SERVICE_ACCOUNT_FILE = 'Python/baris-iot-vito-firebase-adminsdk-baww0-f6eece4154.json'

# Inizializza l'app Firebase Admin con le credenziali
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)

# Ottieni una reference al database Firestore
db = firestore.client()

# --------------------------------------------------------------------------------
# Creazione di un utente di esempio
# --------------------------------------------------------------------------------
user_id = "user_123"  # Questo idealmente corrisponde all'UID dell'utente autenticato con Firebase Auth
user_data = {
    "email": "admin@example.com",
    "role": "admin",        # Può essere 'admin' o 'user'
    "devices": []           # Array dei device_id a cui l'utente ha accesso. Lo aggiorneremo dopo.
}

users_ref = db.collection("users")
users_ref.document(user_id).set(user_data)
print("Utente creato o aggiornato con successo:", user_id)

# --------------------------------------------------------------------------------
# Creazione di un dispositivo (serratura) di esempio
# --------------------------------------------------------------------------------
device_id = "device_1"
device_data = {
    "name": "Appartamento Demo",
    "lock": True,
    "porta_aperta": False,
    "allarme": False,
    "latitude": 45.4642,
    "longitude": 9.1900,
    "maintenance_mode": False,
    "last_access": datetime.utcnow().isoformat()  # Puoi usare un timestamp ISO8601
}

devices_ref = db.collection("devices")
devices_ref.document(device_id).set(device_data)
print("Dispositivo creato o aggiornato con successo:", device_id)

# Aggiorna l'utente per dargli accesso a device_1
users_ref.document(user_id).update({
    "devices": firestore.ArrayUnion([device_id])
})

# --------------------------------------------------------------------------------
# Creazione di una prenotazione di esempio per device_1
# --------------------------------------------------------------------------------
booking_id = "booking_abc"
start_time = datetime.utcnow()
end_time = start_time + timedelta(hours=2)  # Prenotazione valida per le prossime 2 ore

booking_data = {
    "user_id": user_id,
    "start_time": start_time.isoformat(),
    "end_time": end_time.isoformat()
}

prenotazioni_ref = devices_ref.document(device_id).collection("prenotazioni")
prenotazioni_ref.document(booking_id).set(booking_data)
print("Prenotazione creata con successo:", booking_id)

# --------------------------------------------------------------------------------
# Creazione di un log di accesso di esempio
# --------------------------------------------------------------------------------
log_id = "log_001"
log_data = {
    "timestamp": datetime.utcnow().isoformat(),
    "stato": "aperta",
    "user_id": user_id
}

access_logs_ref = devices_ref.document(device_id).collection("access_logs")
access_logs_ref.document(log_id).set(log_data)
print("Log di accesso creato con successo:", log_id)

print("Struttura creata o aggiornata con successo su Firestore!")
