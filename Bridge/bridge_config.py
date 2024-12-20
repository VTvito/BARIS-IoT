import firebase_admin
from firebase_admin import credentials, firestore

def init_firebase(cred_path):
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db