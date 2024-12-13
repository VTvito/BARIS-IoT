import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:provider/provider.dart';

import 'auth_service.dart';
import 'admin_dashboard.dart';
import 'user_dashboard.dart';
import 'main.dart';

class HomePage extends StatefulWidget {
  @override
  _HomePageState createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  String role = 'user'; // di default supponiamo user

  @override
  void initState() {
    super.initState();
    fetchUserRole();
    requestNotificationPermission();
    saveFcmToken();

    // Setup del listener per le notifiche
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      print('Received a message in foreground: ${message.messageId}');
      if (message.notification != null) {
        showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: Text(message.notification!.title ?? 'No Title'),
            content: Text(message.notification!.body ?? 'No Body'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text('OK'),
              ),
            ],
          ),
        );
      }
    });

    // Listener per notifiche aperte dall'app chiusa o in background
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      print('A new onMessageOpenedApp event was published!');
      // Puoi navigare verso una pagina specifica o aggiornare l’interfaccia
    });
  }

  Future<void> fetchUserRole() async {
    final authService = Provider.of<AuthService>(context, listen: false);
    String? userRole = await authService.getUserRole();
    if (userRole != null) {
      setState(() {
        role = userRole;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final authService = Provider.of<AuthService>(context);

    return Scaffold(
      appBar: AppBar(
        title: Text('Baris App'),
        actions: [
          IconButton(
            icon: Icon(Icons.logout),
            onPressed: () async {
              await authService.signOut();
            },
          ),
        ],
      ),
      body: role == 'admin' ? AdminDashboard() : UserDashboard(),
    );
  }
}