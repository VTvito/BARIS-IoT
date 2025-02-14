# BARIS-IoT - A Cloud-Based Smart Lock

Bnb Access Remote IoT System is a project that integrates a smart lock system controllable via a Flutter app, with a Python bridge to communicate with Arduino and interact with Firestore/Firebase. The project includes:
- A Flutter mobile app for end-users and admins (managing bookings, lock status, alarm, and logs).
- A Python bridge that communicates with Arduino via serial connection and with Firestore via the Admin SDK.
- A data analysis script (Jupyter notebook) with forecasting and Machine Learning techniques.

## Features
- **User and admin authentication** with Firebase Auth.
- **Booking and device management**: Admins can create bookings, and users can unlock the lock if they have an active booking.
- **User addition and log visualization**: Admins can add new users and view logs related to unlocks, alarms, etc.
- **Push notifications** to admins in case of intrusion alarms, Arduino device going "offline," or lock unlock events.
- **Arduino-Firestore state alignment**: The bridge ensures the lock's state remains synchronized.
- **Heartbeat and offline detection**: The bridge detects if Arduino goes offline and notifies admins.
- **GMaps APIs in App**: For geofencing in app of user during unlock; they must be within 100m from the lock.
- **Data analysis**: Python scripts and notebooks to extract data from Firestore and generate statistics, forecasts, clustering, and other advanced analyses.

## Project Structure
- `App/baris_app` - Flutter mobile app source code.
- `App/baris_app/assets/` - Icons, images, and Flutter graphic resources.
- `Arduino/` - Arduino source code for the smart lock.
- `Bridge/` - Python scripts, including the bridge (`bridge.py`).
- `Data Analysis/` - Analysis notebooks (Jupyter).

## Requirements
- **Flutter & Dart SDK** to build the app.
- **Python 3.9+** with libraries:  
  - `firebase_admin`
  - `pandas`, `matplotlib`, `seaborn`, `scikit-learn` (for analysis and ML)
- **Arduino IDE** to program the lock.
- **Firebase Project** configured with Firestore, Auth, and Cloud Messaging.

## How to..
To run the project you need to satisfy all the above requirements and create your own project on Firebase, and include the .json files in /app and release the .apk.
Load the code on Arduino, connect it to the bridge (pc) and launch the python script.


![architecture](https://github.com/user-attachments/assets/5115c665-c0db-4a50-81e9-e8f2f0b23514)


