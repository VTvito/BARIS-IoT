import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class UserDashboard extends StatefulWidget {
  @override
  _UserDashboardState createState() => _UserDashboardState();
}

class _UserDashboardState extends State<UserDashboard> {
  final deviceId = 'device_1'; 
  User? user = FirebaseAuth.instance.currentUser;

  @override
  Widget build(BuildContext context) {
    if (user == null) {
      return Scaffold(
        appBar: AppBar(title: Text('Dashboard Utente')),
        body: Center(child: Text('Nessun utente loggato')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Dashboard Utente'),
      ),
      body: StreamBuilder<QuerySnapshot>(
        stream: FirebaseFirestore.instance
            .collection('devices')
            .doc(deviceId)
            .collection('prenotazioni')
            .where('user_id', isEqualTo: user!.uid)
            .orderBy('start_time', descending: false)
            .snapshots(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return Center(child: CircularProgressIndicator());
          }

          var bookings = snapshot.data!.docs;

          if (bookings.isEmpty) {
            return Center(child: Text('Nessuna prenotazione'));
          }

          return ListView.builder(
            itemCount: bookings.length,
            itemBuilder: (context, index) {
              var data = bookings[index].data() as Map<String, dynamic>;
              DateTime start = DateTime.parse(data['start_time'] as String);
              DateTime end = DateTime.parse(data['end_time'] as String);
              return ListTile(
                title: Text('Prenotazione: ${bookings[index].id}'),
                subtitle: Text('Dal ${start.toLocal()} al ${end.toLocal()}'),
              );
            },
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: checkAndUnlock,
        child: Icon(Icons.lock_open),
      ),
    );
  }

  Future<void> checkAndUnlock() async {
    if (user == null) return;
    final now = DateTime.now();

    // Leggi prenotazioni correnti non dal stream, ma con una query diretta,
    // così hai i dati sincroni al momento del clic.
    var bookingsSnapshot = await FirebaseFirestore.instance
        .collection('devices')
        .doc(deviceId)
        .collection('prenotazioni')
        .where('user_id', isEqualTo: user!.uid)
        .get();

    bool hasActiveBooking = false;

    for (var doc in bookingsSnapshot.docs) {
      var data = doc.data() as Map<String, dynamic>;
      DateTime start = DateTime.parse(data['start_time'] as String);
      DateTime end = DateTime.parse(data['end_time'] as String);

      if (now.isAfter(start) && now.isBefore(end)) {
        hasActiveBooking = true;
        break;
      }
    }

    if (hasActiveBooking) {
      await FirebaseFirestore.instance
          .collection('devices')
          .doc(deviceId)
          .update({'lock': false});
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Serratura sbloccata!')));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Nessuna prenotazione attiva al momento.')),
      );
    }
  }
}