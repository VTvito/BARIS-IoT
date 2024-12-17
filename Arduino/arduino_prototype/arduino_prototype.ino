#include <SPI.h>
#include "Arduino.h"

#define ECHO_PIN 13
#define TRIGGER_PIN 12
#define BUZZER 10
#define LED_VERDE 5
#define LED_ROSSO 4
#define LED_BLU 3
#define DISTANCE_THRESHOLD 10

// Stato del sistema
bool lock = true;        // Serratura inizialmente bloccata
bool door_open = false;  // Porta inizialmente chiusa
bool allarme_attivo = false; // Allarme inizialmente disattivato

int effrazione_count = 0;  // Contatore per rilevare effrazione
unsigned long lastCheckTime = 0; // Per controllo periodico porta
const unsigned long CHECK_INTERVAL = 3000; // Controllo ogni 3 secondi

void setup() {
    Serial.begin(9600);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROSSO, OUTPUT);
    pinMode(LED_BLU, OUTPUT);
    pinMode(BUZZER, OUTPUT);

    // Stato iniziale
    digitalWrite(LED_BLU, LOW);
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_ROSSO, HIGH); // Serratura chiusa
    digitalWrite(BUZZER, LOW);

    Serial.println("Sistema pronto...");
}

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

void buzz(int duration) {
    digitalWrite(BUZZER, HIGH);
    delay(duration);
    digitalWrite(BUZZER, LOW);
}

void send_packet(const char* message) {
    Serial.write(0xFB);
    Serial.print(message);
    Serial.write(0xFA);
}

void activate_alarm() {
    if (!allarme_attivo) {
        Serial.println("Allarme attivato!");
        allarme_attivo = true;
        send_packet("EFF");
    }
}

void deactivate_alarm() {
    if (allarme_attivo) {
        Serial.println("Allarme disattivato (D).");
        allarme_attivo = false;
        send_packet("D");
        // Ripristino LED e buzzer
        digitalWrite(LED_ROSSO, HIGH);
        digitalWrite(BUZZER, LOW);
        effrazione_count = 0;
    }
}

void unlock_procedure() {
    buzz(200);
    lock = false; 
    digitalWrite(LED_VERDE, HIGH);
    digitalWrite(LED_ROSSO, LOW);
    Serial.println("Serratura sbloccata.");

    int consecutive_closed = 0;
    while (true) {
        delay(3000); 
        int door_status = check_proximity();

        if (door_status == 1) { // Porta aperta
            if (!door_open) {
                door_open = true;
                digitalWrite(LED_BLU, HIGH);
                send_packet("001");
                Serial.println("Porta aperta.");
            }
            consecutive_closed = 0;
        } else if (door_status == 0) { // Porta chiusa
            if (door_open) {
                consecutive_closed++;
                Serial.print("Porta chiusa, ciclo: ");
                Serial.println(consecutive_closed);
                if (consecutive_closed >= 3) {
                    door_open = false;
                    lock = true; 
                    digitalWrite(LED_BLU, LOW);
                    digitalWrite(LED_VERDE, LOW);
                    digitalWrite(LED_ROSSO, HIGH);
                    send_packet("000");
                    Serial.println("Porta chiusa e serratura bloccata.");
                    break;
                }
            }
        } 
    }
}

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

void check_alarm_condition() {
    // Se serratura bloccata
    if (lock && !allarme_attivo) {
        int door_status = check_proximity();
        if (door_status == 1) {
            // Porta aperta con serratura bloccata: incrementa contatore
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
        // Se allarme attivo, lampeggia più frequentemente LED e BUZZER
        // Le pause avvengono nella funzione stessa
        // Per semplicità, manteniamo il delay(500) interno a check_alarm_condition
        check_alarm_condition();
    }
}
