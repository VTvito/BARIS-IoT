import firebase_admin
from firebase_admin import credentials, firestore, auth

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = "path/to/your/.json"

# Initialize Firebase Admin SDK
cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()

def create_admin_user(email, password):
    # Create the user in Firebase Auth
    user = auth.create_user(
        email=email,
        password=password
    )
    print(f"Admin user created with UID: {user.uid}")

    # Set the user document in Firestore with role=admin
    db.collection("users").document(user.uid).set({
        "email": email,
        "role": "admin",
        "devices": [],   # Initially no devices assigned, can be added later
        "fcm_tokens": [] # Empty list for FCM tokens
    })
    print("Admin user document created with role=admin in the database.")

if __name__ == "__main__":
    # Admin credentials to create
    email = "admin@example.com"
    password = "password123"
    create_admin_user(email, password)