import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AdminDashboard extends StatefulWidget {
  @override
  _AdminDashboardState createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final String deviceId = 'device_1'; // hardcodato ma rendibile dinamico

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Dashboard Admin'),
        bottom: TabBar(
          controller: _tabController,
          tabs: [
            Tab(text: 'Prenotazioni'),
            Tab(text: 'Utenti'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          buildPrenotazioniTab(),
          buildUtentiTab(),
        ],
      ),
      floatingActionButton: _tabController.index == 0
          ? FloatingActionButton(
              onPressed: showCreateBookingDialog,
              child: Icon(Icons.add),
            )
          : null,
    );
  }

  Widget buildPrenotazioniTab() {
    return StreamBuilder<QuerySnapshot>(
      stream: FirebaseFirestore.instance
          .collection('devices')
          .doc('device_1')
          .collection('prenotazioni')
          .orderBy('start_time', descending: false)
          .snapshots(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
        var bookings = snapshot.data!.docs;
        if (bookings.isEmpty) {
          return Center(child: Text("Nessuna prenotazione"));
        }

        return ListView.builder(
          itemCount: bookings.length,
          itemBuilder: (context, index) {
            var bookingData = bookings[index].data() as Map<String, dynamic>;
            var bookingId = bookings[index].id;
            DateTime start = DateTime.parse(bookingData['start_time'] as String);
            DateTime end = DateTime.parse(bookingData['end_time'] as String);
            String userId = bookingData['user_id'] ?? 'unknown';

            return ListTile(
              title: Text('Utente: $userId'),
              subtitle: Text('Dal ${start.toLocal()} al ${end.toLocal()}'),
              trailing: IconButton(
                icon: Icon(Icons.delete, color: Colors.red),
                onPressed: () => deleteBooking(bookingId),
              ),
            );
          },
        );
      },
    );
  }

  Widget buildUtentiTab() {
    return StreamBuilder<QuerySnapshot>(
      stream: FirebaseFirestore.instance.collection('users').snapshots(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
        var users = snapshot.data!.docs;
        if (users.isEmpty) return Center(child: Text("Nessun utente registrato"));

        return ListView.builder(
          itemCount: users.length,
          itemBuilder: (context, index) {
            var userData = users[index].data() as Map<String, dynamic>;
            String email = userData['email'] ?? 'no-email';
            String role = userData['role'] ?? 'user';
            return ListTile(
              title: Text(email),
              subtitle: Text('Ruolo: $role'),
              // Qui potresti aggiungere funzionalità per cambiare ruolo,
              // o mostrare l'UID
            );
          },
        );
      },
    );
  }

  Future<void> deleteBooking(String bookingId) async {
    await FirebaseFirestore.instance
        .collection('devices')
        .doc('device_1')
        .collection('prenotazioni')
        .doc(bookingId)
        .delete();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Prenotazione eliminata.')));
  }

void showCreateBookingDialog() {
  String? selectedUserId;
  DateTime? startTime;
  DateTime? endTime;

  showDialog(
    context: context,
    builder: (context) {
      return AlertDialog(
        title: Text('Crea Prenotazione'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            StreamBuilder<QuerySnapshot>(
              stream: FirebaseFirestore.instance.collection('users').snapshots(),
              builder: (context, snapshot) {
                if (!snapshot.hasData) {
                  return Center(child: CircularProgressIndicator());
                }
                var usersDocs = snapshot.data!.docs;
                if (usersDocs.isEmpty) {
                  return Text('Nessun utente registrato');
                }

                // Convert usersDocs to a list of DropdownMenuItem
                List<DropdownMenuItem<String>> items = usersDocs.map((doc) {
                  var userData = doc.data() as Map<String, dynamic>;
                  String uid = doc.id;
                  String email = userData['email'] ?? 'no-email';
                  return DropdownMenuItem(
                    value: uid,
                    child: Text(email),
                  );
                }).toList();

                return Column(
                  children: [
                    DropdownButton<String>(
                      value: selectedUserId,
                      hint: Text('Seleziona utente'),
                      items: items,
                      onChanged: (val) {
                        setState(() {
                          selectedUserId = val;
                        });
                      },
                    ),
                    SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: () async {
                        startTime = await pickDateTime(context, 'Seleziona inizio');
                        setState(() {});
                      },
                      child: Text(startTime == null ? 'Seleziona inizio' : startTime.toString()),
                    ),
                    SizedBox(height: 10),
                    ElevatedButton(
                      onPressed: () async {
                        endTime = await pickDateTime(context, 'Seleziona fine');
                        setState(() {});
                      },
                      child: Text(endTime == null ? 'Seleziona fine' : endTime.toString()),
                    ),
                  ],
                );
              },
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Annulla'),
          ),
          TextButton(
            onPressed: () async {
              if (selectedUserId == null || startTime == null || endTime == null) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Compila tutti i campi!')));
                return;
              }
              await createBooking(selectedUserId!, startTime!, endTime!);
              Navigator.pop(context);
            },
            child: Text('Crea'),
          ),
        ],
      );
    },
  );
}

  Future<DateTime?> pickDateTime(BuildContext context, String title) async {
    DateTime? date = await showDatePicker(
      context: context,
      initialDate: DateTime.now(),
      firstDate: DateTime.now().subtract(Duration(days: 1)),
      lastDate: DateTime(2100),
    );
    if (date == null) return null;

    TimeOfDay? time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time == null) return null;

    return DateTime(date.year, date.month, date.day, time.hour, time.minute);
  }

  Future<void> createBooking(String userId, DateTime start, DateTime end) async {
    if (end.isBefore(start)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('End time deve essere dopo start time.')));
      return;
    }

    await FirebaseFirestore.instance
        .collection('devices')
        .doc(deviceId)
        .collection('prenotazioni')
        .add({
          "user_id": userId,
          "start_time": start.toIso8601String(),
          "end_time": end.toIso8601String(),
        });
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Prenotazione creata con successo.')));
  }

}