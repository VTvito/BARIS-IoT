import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class AdminDashboard extends StatefulWidget {
  @override
  _AdminDashboardState createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  String? selectedDeviceId;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);


    // listener per aggiornare la UI quando cambia tab
    _tabController.addListener(() {
      setState(() {}); // Ricostruisce lo scaffold e dunque il FAB
    });
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
            Tab(text: 'Log'),
          ],
        ),
      ),
      body: Column(
        children: [
          // Dropdown dinamico per i device
          StreamBuilder<QuerySnapshot>(
            stream: FirebaseFirestore.instance.collection('devices').snapshots(),
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              if (snapshot.hasError) {
                return Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Text('Errore nel caricamento dispositivi: ${snapshot.error}'),
                );
              }
              if (!snapshot.hasData || snapshot.data!.docs.isEmpty) {
                return Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: Text('Nessun dispositivo disponibile.'),
                );
              }

              var devicesDocs = snapshot.data!.docs;
              List<DropdownMenuItem<String>> items = devicesDocs.map((doc) {
                var devData = doc.data() as Map<String, dynamic>;
                String devId = doc.id;
                String name = devData['name'] ?? devId;
                return DropdownMenuItem(
                  value: devId,
                  child: Text(name),
                );
              }).toList();

              if (selectedDeviceId == null && items.isNotEmpty) {
                selectedDeviceId = items.first.value;
              }

              return Padding(
                padding: const EdgeInsets.all(8.0),
                child: Row(
                  children: [
                    Text('Dispositivo: '),
                    SizedBox(width: 10),
                    DropdownButton<String>(
                      value: selectedDeviceId,
                      items: items,
                      onChanged: (val) {
                        setState(() {
                          selectedDeviceId = val;
                        });
                      },
                    )
                  ],
                ),
              );
            },
          ),
              // Mostra l'indicatore allarme se è stato selezionato un device
          if (selectedDeviceId != null)
            buildAlarmIndicator(selectedDeviceId!),
          
              // Mostra l'indicatore dello stato delle porte e della serratura
          if (selectedDeviceId != null)
            buildLockIndicator(selectedDeviceId!),

          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                buildPrenotazioniTab(),
                buildUtentiTab(),
                buildLogTab(),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: _buildFab(),
    );
  }

  Widget _buildFab() {
    if (_tabController.index == 0 && selectedDeviceId != null) {
      // Tab Prenotazioni: FAB per creare nuove prenotazioni
      return FloatingActionButton(
        onPressed: showCreateBookingDialog,
        child: Icon(Icons.add),
      );
    } else if (_tabController.index == 1) {
      // Tab Utenti: FAB per creare un nuovo utente
      return FloatingActionButton(
        onPressed: showCreateUserDialog,
        child: Icon(Icons.person_add),
      );
    } else {
      // Tab Log o nessun'altra tab: nessun FAB
      return SizedBox.shrink(); // widget invisibile invece di null
    }
  }


  Widget buildPrenotazioniTab() {
    if (selectedDeviceId == null) {
      return Center(child: Text("Seleziona un dispositivo"));
    }
    return StreamBuilder<QuerySnapshot>(
      stream: FirebaseFirestore.instance
          .collection('devices')
          .doc(selectedDeviceId)
          .collection('prenotazioni')
          .orderBy('start_time', descending: false)
          .snapshots(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('Errore: ${snapshot.error}'));
        }
        if (!snapshot.hasData) {
          return Center(child: Text('Nessun dato'));
        }

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

            return FutureBuilder<DocumentSnapshot>(
              future: FirebaseFirestore.instance.collection('users').doc(userId).get(),
              builder: (context, userSnapshot) {
                if (userSnapshot.connectionState == ConnectionState.waiting) {
                  return ListTile(title: Text('Caricamento...'));
                }
                var userData = userSnapshot.data?.data() as Map<String, dynamic>?;
                String email = userData?['email'] ?? 'no-email';

                return ListTile(
                  title: Text('Utente: $email'),
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
      },
    );
  }

  Widget buildUtentiTab() {
    return 
          StreamBuilder<QuerySnapshot>(
          stream: FirebaseFirestore.instance.collection('users').snapshots(),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return Center(child: Text('Errore: ${snapshot.error}'));
            }
            if (!snapshot.hasData) {
              return Center(child: Text('Nessun dato'));
            }

            var users = snapshot.data!.docs;
            if (users.isEmpty) return Center(child: Text("Nessun utente registrato"));

            return ListView.builder(
              itemCount: users.length,
              itemBuilder: (context, index) {
                var userData = users[index].data() as Map<String, dynamic>;
                String email = userData['email'] ?? 'no-email';
                String role = userData['role'] ?? 'user';
                String uid = users[index].id;

                return ListTile(
                  title: Text(email),
                  subtitle: Text('Ruolo: $role'),
                  trailing: IconButton(
                    icon: Icon(Icons.delete, color: Colors.red),
                    onPressed: () => removeUser(uid),
                  ),
                );
              },
            );
          },
        );
  }

  Widget buildLogTab() {
    if (selectedDeviceId == null) {
      return Center(child: Text("Seleziona un dispositivo"));
    }

    return StreamBuilder<QuerySnapshot>(
      stream: FirebaseFirestore.instance
        .collection('devices')
        .doc(selectedDeviceId)
        .collection('access_logs')
        .orderBy('timestamp', descending: true)
        .snapshots(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('Errore: ${snapshot.error}'));
        }
        if (!snapshot.hasData || snapshot.data!.docs.isEmpty) {
          return Center(child: Text("Nessun log disponibile"));
        }


        var logs = snapshot.data!.docs;
        return ListView.builder(
          itemCount: logs.length,
          itemBuilder: (context, index) {
            var logData = logs[index].data() as Map<String, dynamic>;
            String action = logData['action'] ?? 'unknown';
            String userId = logData['user_id'] ?? 'unknown';
            String timestampStr = logData['timestamp'] ?? '';
            DateTime? timestamp = DateTime.tryParse(timestampStr);
            String timeStr = timestamp != null ? timestamp.toLocal().toString() : timestampStr;
            if (userId == 'unknown' || userId == 'None') {
              return ListTile(
                title: Text('Azione: $action'),
                subtitle: Text('Utente: N/A - $timeStr'),
              );
            }
            return FutureBuilder<DocumentSnapshot>(
              future: (userId == 'unknown' || userId == 'None')
                ? Future.value(null)
                : FirebaseFirestore.instance.collection('users').doc(userId).get(),
              builder: (context, userSnapshot) {
                String email = 'N/A';
                if (userSnapshot.connectionState == ConnectionState.done && userSnapshot.data != null) {
                  var userData = userSnapshot.data!.data() as Map<String, dynamic>?;
                  email = userData?['email'] ?? 'no-email';
                }

                return ListTile(
                  title: Text('Azione: $action'),
                  subtitle: Text('Utente: $email - $timeStr'),
                );
              },
            );
          },
        );
      },
    );
  }

  Widget buildAlarmIndicator(String deviceId) {
    return StreamBuilder<DocumentSnapshot>(
      stream: FirebaseFirestore.instance.collection('devices').doc(deviceId).snapshots(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
        var data = snapshot.data!.data() as Map<String, dynamic>?;
        if (data == null) return Text('Nessun dato sul dispositivo');
        
        bool allarme = data['allarme'] ?? false;

        return Padding(
          padding: const EdgeInsets.all(8.0),
          child: Row(
            children: [
              Text('Allarme: ${allarme ? "Attivo" : "Disattivo"}'),
              SizedBox(width: 20),
              if (allarme)
                ElevatedButton(
                  onPressed: () async {
                    // Disattiva allarme
                    await FirebaseFirestore.instance
                      .collection('devices')
                      .doc(deviceId)
                      .update({"allarme": false});
                  },
                  child: Text('Disattiva Allarme'),
                )
            ],
          ),
        );
      },
    );
  }

  Widget buildLockIndicator(String deviceId) {
  return StreamBuilder<DocumentSnapshot>(
    stream: FirebaseFirestore.instance.collection('devices').doc(deviceId).snapshots(),
    builder: (context, snapshot) {
      if (!snapshot.hasData) return Center(child: CircularProgressIndicator());
      var data = snapshot.data!.data() as Map<String, dynamic>?;
      if (data == null) return Text('Nessun dato sul dispositivo');

      bool lock = data['lock'] ?? true;
      bool portaAperta = data['porta_aperta'] ?? false;

      return Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Prima riga: stato della porta
            Row(
              children: [
                Text('Porta: ${portaAperta ? "Aperta" : "Chiusa"}'),
              ],
            ),
            SizedBox(height: 10),

            // Seconda riga: stato serratura e pulsante
            Row(
              children: [
                Text('Serratura: ${lock ? "Bloccata" : "Sbloccata"}'),
                SizedBox(width: 20),
                if (lock)
                  ElevatedButton(
                    onPressed: () async {
                      // L’admin forza lo sblocco della serratura
                      await FirebaseFirestore.instance.collection('devices').doc(deviceId).update({"lock": false});
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Serratura sbloccata da admin.')));
                    },
                    child: Text('Sblocca Serratura'),
                  )
              ],
            ),
          ],
        ),
      );
    },
  );
  }



  Future<void> deleteBooking(String bookingId) async {
    if (selectedDeviceId == null) return;
    await FirebaseFirestore.instance
        .collection('devices')
        .doc(selectedDeviceId)
        .collection('prenotazioni')
        .doc(bookingId)
        .delete();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Prenotazione eliminata.')));
  }

  Future<void> removeUser(String uid) async {
    await FirebaseFirestore.instance.collection('users').doc(uid).delete();
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Utente rimosso.')));
  }

  void showCreateBookingDialog() {
    String? selectedUserId;
    DateTime? startTime;
    DateTime? endTime;

    if (selectedDeviceId == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Seleziona un dispositivo prima.')));
      return;
    }

    showDialog(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (dialogContext, setStateDialog) {
            return AlertDialog(
              title: Text('Crea Prenotazione'),
              content: SingleChildScrollView(
                child: Column(
                  children: [
                    StreamBuilder<QuerySnapshot>(
                      stream: FirebaseFirestore.instance.collection('users').snapshots(),
                      builder: (context, snapshot) {
                        if (snapshot.connectionState == ConnectionState.waiting) {
                          return Center(child: CircularProgressIndicator());
                        }
                        if (snapshot.hasError) {
                          return Text('Errore: ${snapshot.error}');
                        }
                        if (!snapshot.hasData || snapshot.data!.docs.isEmpty) {
                          return Text('Nessun utente registrato');
                        }

                        var usersDocs = snapshot.data!.docs;
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
                              isExpanded: true,
                              items: items,
                              onChanged: (val) {
                                setStateDialog(() {
                                  selectedUserId = val;
                                });
                              },
                            ),
                            SizedBox(height: 20),
                            ElevatedButton(
                              onPressed: () async {
                                var date = await pickDateTime(dialogContext, 'Seleziona inizio');
                                setStateDialog(() {
                                  startTime = date;
                                });
                              },
                              child: Text(startTime == null ? 'Seleziona inizio' : startTime.toString()),
                            ),
                            SizedBox(height: 10),
                            ElevatedButton(
                              onPressed: () async {
                                var date = await pickDateTime(dialogContext, 'Seleziona fine');
                                setStateDialog(() {
                                  endTime = date;
                                });
                              },
                              child: Text(endTime == null ? 'Seleziona fine' : endTime.toString()),
                            ),
                          ],
                        );
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: Text('Annulla'),
                ),
                TextButton(
                  onPressed: () async {
                    if (selectedUserId == null || startTime == null || endTime == null) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Compila tutti i campi!')));
                      return;
                    }
                    await createBooking(selectedUserId!, startTime!, endTime!);
                    Navigator.pop(dialogContext);
                  },
                  child: Text('Crea'),
                ),
              ],
            );
          },
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
    if (selectedDeviceId == null) return;
    if (end.isBefore(start)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('End time deve essere dopo start time.')));
      return;
    }

    // Creazione prenotazione
    await FirebaseFirestore.instance
        .collection('devices')
        .doc(selectedDeviceId)
        .collection('prenotazioni')
        .add({
          "user_id": userId,
          "start_time": start.toIso8601String(),
          "end_time": end.toIso8601String(),
        });

    // Aggiorna l'utente aggiungendo il device_id se non presente
    DocumentReference userRef = FirebaseFirestore.instance.collection('users').doc(userId);
    DocumentSnapshot userDoc = await userRef.get();
    if (userDoc.exists) {
      var userData = userDoc.data() as Map<String, dynamic>;
      List devices = userData['devices'] ?? [];
      if (!devices.contains(selectedDeviceId)) {
        devices.add(selectedDeviceId);
        await userRef.update({"devices": devices});
      }
    } else {
      await userRef.set({
        "email": "no-email",
        "role": "user",
        "devices": [selectedDeviceId]
      });
    }

    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Prenotazione creata con successo.')));
  }

  // Funzione per creare un nuovo utente
  void showCreateUserDialog() {
    String email = '';
    String password = '';
    String selectedRole = 'user'; // default user

    showDialog(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (dialogContext, setStateDialog) {
            return AlertDialog(
              title: Text('Crea Utente'),
              content: SingleChildScrollView(
                child: Column(
                  children: [
                    TextField(
                      decoration: InputDecoration(labelText: 'Email'),
                      onChanged: (val) => email = val,
                    ),
                    TextField(
                      decoration: InputDecoration(labelText: 'Password'),
                      obscureText: true,
                      onChanged: (val) => password = val,
                    ),
                    SizedBox(height: 20),
                    Row(
                      children: [
                        Text('Ruolo: '),
                        SizedBox(width: 10),
                        DropdownButton<String>(
                          value: selectedRole,
                          items: [
                            DropdownMenuItem(value: 'user', child: Text('User')),
                            DropdownMenuItem(value: 'admin', child: Text('Admin')),
                          ],
                          onChanged: (val) {
                            setStateDialog(() {
                              selectedRole = val!;
                            });
                          },
                        )
                      ],
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: Text('Annulla'),
                ),
                TextButton(
                  onPressed: () async {
                    if (email.isEmpty || password.isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Compila tutti i campi!')));
                      return;
                    }

                    await createUser(email, password, selectedRole);
                    Navigator.pop(dialogContext);
                  },
                  child: Text('Crea'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> createUser(String email, String password, String role) async {
    try {
      UserCredential cred = await FirebaseAuth.instance.createUserWithEmailAndPassword(email: email, password: password);
      String uid = cred.user!.uid;
      await FirebaseFirestore.instance.collection('users').doc(uid).set({
        "email": email,
        "role": role,
        "devices": []
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Utente creato con successo!')));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Errore: $e')));
    }
  }
}