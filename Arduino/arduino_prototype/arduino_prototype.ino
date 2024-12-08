#include <SPI.h>
#include "Arduino.h"

// Pin
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

void setup() {
    Serial.begin(9600);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROSSO, OUTPUT);
    pinMode(LED_BLU, OUTPUT);
    pinMode(BUZZER, OUTPUT);

    // Serratura chiusa e porta chiusa
    digitalWrite(LED_BLU, LOW);
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_ROSSO, HIGH);
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
        Serial.println("Errore nella lettura del sensore.");
        return -1;
    }

    float distanza = (durata * 0.0343) / 2;
    Serial.print("Distanza misurata: ");
    Serial.println(distanza);

    if (distanza > DISTANCE_THRESHOLD) {
        return 1; // porta aperta
    } else {
        return 0; // porta chiusa
    }
}

void buzz(int duration) {
    digitalWrite(BUZZER, HIGH);
    delay(duration);
    digitalWrite(BUZZER, LOW);
}

void send_packet(const char* message) {
    Serial.write(0xFB);  // Inizio pacchetto
    Serial.print(message);  // Messaggio
    Serial.write(0xFA);  // Fine pacchetto
}

void unlock_procedure() {
    buzz(200);
    lock = false; // Serratura sbloccata
    digitalWrite(LED_VERDE, HIGH);
    digitalWrite(LED_ROSSO, LOW);

    Serial.println("Serratura sbloccata.");

    int consecutive_closed = 0;
    while (true) {
        delay(3000); // Controllo ogni 3 secondi
        int door_status = check_proximity();

        if (door_status == 1) {
            // Porta aperta
            if (!door_open) {
                door_open = true;
                digitalWrite(LED_BLU, HIGH);
                send_packet("001"); // Notifica porta aperta
                Serial.println("Porta aperta.");
            }
            consecutive_closed = 0; // Reset contatore
        } else if (door_status == 0) {
            // Porta chiusa
            if (door_open) {
                consecutive_closed++;
                Serial.print("Porta chiusa, ciclo: ");
                Serial.println(consecutive_closed);
                if (consecutive_closed >= 3) {
                    door_open = false;
                    lock = true; // Serratura torna chiusa
                    digitalWrite(LED_BLU, LOW);
                    digitalWrite(LED_VERDE, LOW);
                    digitalWrite(LED_ROSSO, HIGH);
                    send_packet("000"); // Notifica porta chiusa e serratura bloccata
                    Serial.println("Porta chiusa e serratura bloccata.");
                    break; // Esci dalla procedura di unlock
                }
            }
        } else {
            Serial.println("Errore nella lettura del sensore.");
        }
    }
}

void lock_procedure() {
    buzz(100);
    lock = true; // Serratura bloccata
    digitalWrite(LED_ROSSO, HIGH);
    digitalWrite(LED_VERDE, LOW);
    if (!door_open) {
        digitalWrite(LED_BLU, LOW); // Spegni LED blu solo se porta chiusa
    }

    Serial.println("Serratura bloccata.");
    send_packet("000"); // Notifica porta chiusa
}

void check_for_remote_input() {
    if (Serial.available() > 0) {
        String command = Serial.readString();
        command.trim();
        Serial.print("Valore ricevuto: ");
        Serial.println(command);

        if (command == "1") {
            // Sblocco serratura
            unlock_procedure();
        } else if (command == "0") {
            // Blocco serratura
            lock_procedure();
        }
    }
}

void loop() {
    check_for_remote_input();
}