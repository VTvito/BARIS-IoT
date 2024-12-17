import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:geolocator/geolocator.dart';

class UserDashboard extends StatefulWidget {
  @override
  _UserDashboardState createState() => _UserDashboardState();
}

class _UserDashboardState extends State<UserDashboard> {
  User? user = FirebaseAuth.instance.currentUser;
  List<String> userDevices = [];
  Map<String, String> deviceIdToName = {};
  String? selectedUserDeviceId; // Device selezionato dall'utente

  @override
  void initState() {
    super.initState();
    loadUserDevices();
  }

  Future<void> loadUserDevices() async {
  if (user == null) return;
  DocumentSnapshot doc = await FirebaseFirestore.instance.collection('users').doc(user!.uid).get();
  if (doc.exists) {
    var data = doc.data() as Map<String, dynamic>;
    List devices = data['devices'] ?? [];
    userDevices = devices.cast<String>();

    await loadDevicesNames();

    // Filtra i devices su cui l'utente ha prenotazioni
    List<String> filteredDevices = [];
    for (var devId in userDevices) {
      var bookingsSnap = await FirebaseFirestore.instance
          .collection('devices')
          .doc(devId)
          .collection('prenotazioni')
          .where('user_id', isEqualTo: user!.uid)
          .get();

      if (bookingsSnap.docs.isNotEmpty) {
        filteredDevices.add(devId);
      }
    }
    userDevices = filteredDevices;

    setState(() {
      if (userDevices.isNotEmpty) {
        if (userDevices.length == 1) {
          selectedUserDeviceId = userDevices.first;
        } else {
          selectedUserDeviceId = null;
        }
      }
    });
  } else {
    setState(() {
      userDevices = [];
      selectedUserDeviceId = null;
    });
  }
}

  Future<void> loadDevicesNames() async {
    deviceIdToName.clear();
    for (var devId in userDevices) {
      DocumentSnapshot devDoc = await FirebaseFirestore.instance.collection('devices').doc(devId).get();
      if (devDoc.exists) {
        var devData = devDoc.data() as Map<String, dynamic>;
        String name = devData['name'] ?? devId;
        deviceIdToName[devId] = name;
      } else {
        deviceIdToName[devId] = devId; // fallback
      }
    }
  }

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
      body: buildUserInterface(),
      floatingActionButton: FloatingActionButton(
        onPressed: checkAndUnlock,
        child: Icon(Icons.lock_open),
      ),
    );
  }

  Widget buildUserInterface() {
    if (userDevices.isEmpty) {
      return Center(child: Text('Nessun dispositivo associato. Contatta l\'admin per una prenotazione.'));
    }

    if (userDevices.length > 1) {
      // Se più device, mostra dropdown con i nomi dei device
      List<DropdownMenuItem<String>> items = userDevices.map((d) {
        String deviceName = deviceIdToName[d] ?? d;
        return DropdownMenuItem(value: d, child: Text(deviceName));
      }).toList();

      return Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Text('Seleziona dispositivo: '),
                SizedBox(width: 10),
                DropdownButton<String>(
                  value: selectedUserDeviceId,
                  hint: Text('Scegli un device'),
                  items: items,
                  onChanged: (val) {
                    setState(() {
                      selectedUserDeviceId = val;
                    });
                  },
                )
              ],
            ),
          ),
          Expanded(
            child: selectedUserDeviceId == null
                ? Center(child: Text('Seleziona un dispositivo per vedere le prenotazioni'))
                : buildPrenotazioniList(selectedUserDeviceId!),
          )
        ],
      );
    } else {
      // Un solo device
      String singleDeviceId = userDevices.first;
      String deviceName = deviceIdToName[singleDeviceId] ?? singleDeviceId;
      return Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Text('Dispositivo: $deviceName'),
          ),
          Expanded(child: buildPrenotazioniList(singleDeviceId)),
        ],
      );
    }
  }

  Widget buildPrenotazioniList(String deviceId) {
    return StreamBuilder<QuerySnapshot>(
      stream: FirebaseFirestore.instance
          .collection('devices')
          .doc(deviceId)
          .collection('prenotazioni')
          .where('user_id', isEqualTo: user!.uid)
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
    );
  }

  Future<void> checkAndUnlock() async {
    if (user == null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Non sei loggato.')));
      return;
    }

    String? deviceId;
    if (userDevices.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Nessun dispositivo associato.')));
      return;
    } else if (userDevices.length == 1) {
      deviceId = userDevices.first;
    } else {
      if (selectedUserDeviceId == null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Seleziona un dispositivo.')));
        return;
      }
      deviceId = selectedUserDeviceId;
    }

    // Prima di procedere con il controllo prenotazioni e posizione:
    DocumentSnapshot deviceDoc = await FirebaseFirestore.instance.collection('devices').doc(deviceId).get();
    if (deviceDoc.exists) {
      var deviceData = deviceDoc.data() as Map<String, dynamic>;
      bool currentLock = deviceData['lock'] ?? true;
      if (!currentLock) {
        // Serratura già sbloccata
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('La serratura è già sbloccata.')));
        return;
      }
    }
      // Ottieni posizione utente
    Position? userPosition = await getCurrentUserPosition();
    if (userPosition == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Impossibile ottenere la posizione utente. Verifica i permessi.')),
      );
      return;
    }

    // Ottieni posizione dispositivo
    var devicePos = await getDevicePosition(deviceId!);
    if (devicePos == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Impossibile ottenere la posizione del dispositivo.')),
      );
      return;
    }

    double distance = calculateDistance(
      userPosition.latitude, userPosition.longitude,
      devicePos['lat']!, devicePos['lng']!
    );

    double maxDistance = 100.0; // Raggio in metri
    if (distance > maxDistance) {
      // Utente troppo lontano
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Sei troppo lontano dal dispositivo per sbloccarlo.')),
      );
      return;
    }

  // Se l'utente è nel raggio, continua

    final now = DateTime.now();

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

      // Aggiungiamo il log
      await FirebaseFirestore.instance
          .collection('devices')
          .doc(deviceId)
          .collection('access_logs')
          .add({
            "timestamp": DateTime.now().toUtc().toIso8601String(),
            "user_id": user!.uid,
            "action": "unlock"
          });

      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Serratura sbloccata!')));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Nessuna prenotazione attiva al momento.')),
      );
    }
  }

  Future<Position?> getCurrentUserPosition() async {
    bool serviceEnabled;
    LocationPermission permission;

    // Verifica se i servizi di geolocalizzazione sono abilitati
    serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      // Servizi GPS non abilitati
      return null;
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        // Permessi negati
        return null;
      }
    }
    
    if (permission == LocationPermission.deniedForever) {
      // Permessi permanentemente negati
      return null;
    }

    // Recupera la posizione corrente
    Position position = await Geolocator.getCurrentPosition(desiredAccuracy: LocationAccuracy.high);
    return position;
  }

  Future<Map<String, double>?> getDevicePosition(String deviceId) async {
    DocumentSnapshot doc = await FirebaseFirestore.instance.collection('devices').doc(deviceId).get();
    if (doc.exists) {
      var data = doc.data() as Map<String, dynamic>?;
      if (data != null) {
        double lat = (data['latitude'] as num).toDouble();
        double lng = (data['longitude'] as num).toDouble();
        return {"lat": lat, "lng": lng};
      }
    }
    return null;
  }

  double calculateDistance(double userLat, double userLng, double deviceLat, double deviceLng) {
    double distanceInMeters = Geolocator.distanceBetween(userLat, userLng, deviceLat, deviceLng);
    return distanceInMeters;
  }
}