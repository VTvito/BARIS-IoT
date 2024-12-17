# BARIS-IoT - Serratura Intelligente con Analisi Firebase

BARIS-IoT è un progetto che integra un sistema di serratura intelligente controllabile via app Flutter, con un bridge Python per la comunicazione con Arduino e l'interfaccia verso Firestore/Firebase. Il progetto include:
- Un'app mobile Flutter per l'utente finale e per l'admin (gestione prenotazioni, stato serratura, allarme, logs).
- Un bridge Python che comunica con Arduino via seriale e con Firestore via Admin SDK.
- Uno script per l'analisi dati (Jupyter notebook) con possibilità di integrare Prophet per previsioni e tecniche di Machine Learning.

## Funzionalità
- **Autenticazione utenti e admin** con Firebase Auth.
- **Prenotazioni e gestione dispositivi**: l'admin può creare prenotazioni, l'utente può sbloccare la serratura se ha una prenotazione attiva.
- **Aggiunta utenti e visualizzazione log**: l'admin può creare nuovi utenti e visualizzare i log relativi ad aperture, allarmi ecc..
- **Notifiche push** agli admin in caso di allarme per effrazione rilevata, dispositivo Arduino "offline", unlock serratura.
- **Allineamento stato Arduino-Firestore**: il bridge mantiene sincronizzato lo stato della serratura.
- **Heartbeat e offline detection**: il bridge rileva se Arduino è offline e notifica gli admin.
- **Analisi dati**: script Python e notebook per estrarre dati da Firestore e generare statistiche, previsioni (via Prophet), clustering, e altre analisi avanzate.

## Struttura del Progetto
- `app/` - Codice Flutter dell'app mobile.
- `Python/` - Script Python, bridge (bridge.py), notebook di analisi (Jupyter).
- `firebase_credentials/` - File di credenziali del service account Firebase.
- `arduino/` - Codice sorgente Arduino per la serratura intelligente.
- `assets/` - Icone, immagini, e risorse grafiche Flutter.

## Requisiti
- **Flutter & Dart SDK** per compilare l'app.
- **Python 3.9+** con librerie:  
  - `firebase_admin`
  - `pandas`, `matplotlib`, `seaborn`, `scikit-learn`, `prophet` (per analisi e ML)
- **Arduino IDE** per programmare la serratura.
- **Firebase Project** con Firestore, Auth e Cloud Messaging configurati.