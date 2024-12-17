import firebase_admin
from firebase_admin import credentials, firestore, auth

# Percorso al file di credenziali del service account
SERVICE_ACCOUNT_FILE = "Python/baris-iot-vito-firebase-adminsdk-baww0-19695e55a0.json"

# Inizializzazione Firebase Admin SDK
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)

db = firestore.client()

def create_admin_user(email, password):
    # Crea l'utente su Firebase Auth
    user = auth.create_user(
        email=email,
        password=password
    )
    print(f"Utente admin creato con UID: {user.uid}")

    # Imposta il documento dell'utente con role=admin
    db.collection("users").document(user.uid).set({
        "email": email,
        "role": "admin",
        "devices": [],   # Per ora nessun device, puoi aggiungerli successivamente
        "fcm_tokens": []
    })
    print("Documento utente admin creato con role=admin nel database.")

if __name__ == "__main__":
    # Dati dell'admin da creare
    email = "admin@example.com"
    password = "password123"
    create_admin_user(email, password)
