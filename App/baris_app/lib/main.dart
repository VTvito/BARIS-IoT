import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'firebase_options.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Baris App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  final String deviceId = 'iliadbox-77F2A2'; // Il tuo device_id

  @override
  Widget build(BuildContext context) {
    final docRef = FirebaseFirestore.instance.collection('dispositivi').doc(deviceId);

    return Scaffold(
      appBar: AppBar(
        title: Text('Test Sblocco Serratura'),
      ),
      body: StreamBuilder<DocumentSnapshot>(
        stream: docRef.snapshots(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return Center(child: CircularProgressIndicator());
          }

          var data = snapshot.data!.data() as Map<String, dynamic>?;
          if (data == null) {
            return Center(child: Text('Nessun dato trovato'));
          }

          bool lock = data['lock'] ?? true;
          bool portaAperta = data['porta_aperta'] ?? false;

          return Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              children: [
                Text(
                  'Stato Serratura: ${lock ? 'Chiusa' : 'Aperta'}',
                  style: TextStyle(fontSize: 20),
                ),
                SizedBox(height: 10),
                Text(
                  'Stato Porta: ${portaAperta ? 'Aperta' : 'Chiusa'}',
                  style: TextStyle(fontSize: 20),
                ),
                SizedBox(height: 20),
                ElevatedButton(
                  onPressed: () async {
                    // Imposta lock = false per sbloccare la serratura
                    await docRef.update({'lock': false});
                  },
                  child: Text('Sblocca Serratura'),
                ),
                SizedBox(height: 10),
                ElevatedButton(
                  onPressed: () async {
                    // Imposta lock = true per bloccare la serratura
                    await docRef.update({'lock': true});
                  },
                  child: Text('Blocca Serratura'),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
