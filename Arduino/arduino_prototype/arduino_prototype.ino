#include <SPI.h>
#include "Arduino.h"

#define ECHO_PIN 13
#define TRIGGER_PIN 12
#define BUZZER 10
#define LED_VERDE 5
#define LED_ROSSO 4
#define LED_BLU 3
#define DISTANCE_THRESHOLD 10

// Variabili di stato del sistema --inizializzazione
bool lock = true;        // Serratura bloccata
bool door_open = false;  // Porta chiusa
bool allarme_attivo = false; // Allarme disattivato

// Variabili per gestione allarme
int effrazione_count = 0;  // Contatore per conferma effrazione (evita falsi positivi)
unsigned long lastCheckTime = 0; // Contiene millis() dell'ultimo check sull'allarme
const unsigned long CHECK_INTERVAL = 3000;

// Variabili per heartbeat
unsigned long lastHeartbeatTime = 0;  // Contiene l'ultimo momento in cui abbiamo inviato un heartbeat
const unsigned long HEARTBEAT_INTERVAL = 60000;

void setup() {
    Serial.begin(9600);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROSSO, OUTPUT);
    pinMode(LED_BLU, OUTPUT);
    pinMode(BUZZER, OUTPUT);

    // Stato iniziale
    digitalWrite(LED_BLU, LOW); // Porta Chiusa
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_ROSSO, HIGH); // Serratura chiusa
    digitalWrite(BUZZER, LOW);

    Serial.println("Sistema pronto...");
    lastHeartbeatTime = millis(); // Inizializza tempo di heartbeat
}

// Monitora l'apertura o chiusura della porta usando un sensore ad ultrasuoni, misurando la distanza rilevata
int check_proximity() {
    digitalWrite(TRIGGER_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIGGER_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIGGER_PIN, LOW);

    long durata = pulseIn(ECHO_PIN, HIGH);
    if (durata == 0) {
        // Lettura non affidabile
        return -1;
    }

    float distanza = (durata * 0.0343) / 2;
    Serial.print("Distanza misurata: ");
    Serial.print(distanza);
    Serial.println(" cm");
    if (distanza > DISTANCE_THRESHOLD) {
        return 1; // Porta aperta
    } else {
        return 0; // Porta chiusa
    }
}

// Gestione buzzer
void buzz(int duration) {
    digitalWrite(BUZZER, HIGH);
    delay(duration);
    digitalWrite(BUZZER, LOW);
}

// Scambia informazioni sullo stato della serratura, porta, e allarme: invia messaggi di stato al bridge
void send_packet(const char* message) {
    Serial.write(0xFB);
    Serial.print(message);
    Serial.write(0xFA);
}

// Attiva l’allarme in caso di apertura non autorizzata della porta., accende il buzzer e invia un pacchetto di stato al bridge
void activate_alarm() {
    if (!allarme_attivo) {
        Serial.println("Allarme attivato!");
        allarme_attivo = true;
        send_packet("EFF");
    }
}

// Disattiva l’allarme, ripristina il sistema e invia un pacchetto di stato al bridge
void deactivate_alarm() {
    if (allarme_attivo) {
        Serial.println("Allarme disattivato (D).");
        allarme_attivo = false;
        send_packet("D");
        digitalWrite(LED_ROSSO, HIGH);
        digitalWrite(BUZZER, LOW);
        effrazione_count = 0;
    }
}

// Sblocca la serratura in risposta ai comandi ricevuti dal bridge.. e accende i LED corrispondenti.
// Entra in una routine (while) in cui persiste fin quando la porta non è chiusa.. se entro 60s la serratura non si riblocca lo segnala
void unlock_procedure() {
    buzz(200); // Beep di conferma sblocco
    lock = false; 
    digitalWrite(LED_VERDE, HIGH);
    digitalWrite(LED_ROSSO, LOW);
    Serial.println("Serratura sbloccata.");

    // Salvo il tempo in cui c'è stato lo sblocco
    unsigned long unlockStartTime = millis();
    bool notRelockedAlarm = false;  // flag per inviare una sola volta il pacchetto e attivare beep fisso

    int consecutive_closed = 0;

    while (true) {
        delay(1000); 
        int door_status = check_proximity();

        // Controllo se sono trascorsi 60 secondi dal momento dello sblocco
        if (!notRelockedAlarm && (millis() - unlockStartTime >= 60000)) {
            digitalWrite(BUZZER, HIGH);
            send_packet("NRLOCK");
            Serial.println("Allarme: la serratura non è stata rilockata entro 60s!");
            notRelockedAlarm = true;
        }

        if (door_status == 1) { 
            // Porta aperta
            if (!door_open) {
                door_open = true;
                digitalWrite(LED_BLU, HIGH);
                send_packet("001"); 
                Serial.println("Porta aperta.");
            }
            consecutive_closed = 0;
        } 
        else if (door_status == 0) { 
            // Porta chiusa
            if (door_open) {
                consecutive_closed++;
                Serial.print("Porta chiusa, ciclo: ");
                Serial.println(consecutive_closed);

                // Se la porta risulta chiusa per 3 rilevazioni consecutive (3 secondi nel tuo caso)
                if (consecutive_closed >= 3) {
                    door_open = false;
                    lock = true; 
                    digitalWrite(LED_BLU, LOW);
                    digitalWrite(LED_VERDE, LOW);
                    digitalWrite(LED_ROSSO, HIGH);

                    // se stava suonando, spengo il buzzer
                    digitalWrite(BUZZER, LOW);

                    send_packet("000");
                    Serial.println("Porta chiusa e serratura bloccata.");
                    break;
                }
            }
        } 
    }
}

// Blocca la serratura e aggiorna lo stato visivamente --allinea lo stato logico Arduino/Firestone--
void lock_procedure() {
    buzz(100);
    lock = true;
    digitalWrite(LED_ROSSO, HIGH);
    digitalWrite(LED_VERDE, LOW);
    if (!door_open) {
        digitalWrite(LED_BLU, LOW);
    }
    Serial.println("Serratura bloccata.");
    send_packet("000");
}

// Scambia informazioni sullo stato della serratura, porta, e allarme: ascolta comandi ricevuti dal bridge.
void check_for_remote_input() {
    if (Serial.available() > 0) {
        String command = Serial.readString();
        command.trim();
        Serial.print("Valore ricevuto: ");
        Serial.println(command);

        if (command == "1") {
            unlock_procedure();
        } else if (command == "0") {
            lock_procedure();
        } else if (command == "D") {
            // Disattiva allarme da remoto
            deactivate_alarm();
        } else if (command == "A"){
            // Attiva allarme (sync da Firestone) 
            activate_alarm();
        }
    }
}

// Verifica le condizioni della porta e della serratura: attiva l'allarme se rileva aperture anomale
void check_alarm_condition() {
    // Se serratura bloccata
    if (lock && !allarme_attivo) {
        int door_status = check_proximity();
        if (door_status == 1) {
            // Porta aperta con serratura bloccata: incrementa contatore effrazione
            effrazione_count++;
            if (effrazione_count >= 3) {
                activate_alarm();
            }
        } else if (door_status == 0) {
            // Porta chiusa, reset contatore
            effrazione_count = 0;
        }
    }
    // Se allarme attivo, lampeggia LED rosso e buzzer
    if (allarme_attivo) {
        digitalWrite(LED_ROSSO, !digitalRead(LED_ROSSO));
        digitalWrite(BUZZER, !digitalRead(BUZZER));
        delay(500); 
    }
}

void loop() {
    check_for_remote_input();

    // Ogni 3 secondi controlla allarme
    if (!allarme_attivo && (millis() - lastCheckTime >= CHECK_INTERVAL)) {
        lastCheckTime = millis();
        check_alarm_condition();
    } else if (allarme_attivo) {
        // manteniamo il delay(500) interno a check_alarm_condition
        check_alarm_condition();
    }

        // Heartbeat: se è passato più di HEARTBEAT_INTERVAL (60s), invia "HB" al bridge
    if (millis() - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
        send_packet("HB");
        Serial.println("Heartbeat inviato (HB).");
        lastHeartbeatTime = millis();
    }
}