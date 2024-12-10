import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _db = FirebaseFirestore.instance;

  Stream<User?> get authStateChanges => _auth.authStateChanges();

  Future<User?> signIn({required String email, required String password}) async {
    UserCredential cred = await _auth.signInWithEmailAndPassword(email: email, password: password);
    return cred.user;
  }

  Future<User?> signUp({required String email, required String password}) async {
    UserCredential cred = await _auth.createUserWithEmailAndPassword(email: email, password: password);
    // Appena l'utente si registra, creiamo il suo documento in Firestore
    await _db.collection('users').doc(cred.user!.uid).set({
      "email": email,
      "role": "user", // Ruolo di default per un nuovo utente
      "devices": []   // Al momento nessun dispositivo assegnato
    });
    return cred.user;
  }

  Future<void> signOut() async {
    await _auth.signOut();
  }

  Future<String?> getUserRole() async {
    User? user = _auth.currentUser;
    if (user == null) return null;
    DocumentSnapshot doc = await _db.collection('users').doc(user.uid).get();
    if (doc.exists) {
      return doc.get('role');
    }
    return null;
  }
}