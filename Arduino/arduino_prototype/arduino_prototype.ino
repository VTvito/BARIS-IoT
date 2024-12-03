#include <SPI.h>
#include "Arduino.h"

// Definisco i pin per i vari sensori e attuatori
#define ECHO_PIN 13     // Sensore di prossimità (Echo)
#define TRIGGER_PIN 12  // Sensore di prossimità (Trigger)
#define BUZZER 10      // Pin per il buzzer
#define LED_VERDE 5    // Pin LED verde
#define LED_ROSSO 4    // Pin LED rosso
#define LED_BLU 3      // Pin LED blu che simula l'apertura della porta
#define ACCESS_DELAY 2000

// Soglia di distanza in cm per determinare se la porta è aperta
#define DISTANCE_THRESHOLD 10

void setup() {
    Serial.begin(9600);   // Inizializzo la porta seriale per debugging e comunicazione con il bridge
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROSSO, OUTPUT);
    pinMode(LED_BLU, OUTPUT);
    pinMode(BUZZER, OUTPUT);

    // Inizialmente la serratura è bloccata e la porta è chiusa
    digitalWrite(LED_BLU, LOW);   // Porta chiusa
    digitalWrite(LED_VERDE, LOW); // Serratura sbloccata (spento)
    digitalWrite(LED_ROSSO, HIGH); // Serratura bloccata
    digitalWrite(BUZZER, LOW);    // Buzzer spento

    Serial.println("Sistema pronto...");
}

int check_proximity() { // Funzione per controllare lo stato della porta, se aperta o chiusa
    digitalWrite(TRIGGER_PIN, LOW); // Reset trigger
    delayMicroseconds(2);
    digitalWrite(TRIGGER_PIN, HIGH); // Invia impulso di 10 microsec su Trig
    delayMicroseconds(10);
    digitalWrite(TRIGGER_PIN, LOW);

    long durata = pulseIn(ECHO_PIN, HIGH); // Misura la durata dell'impulso ALTO su Echo

    if (durata == 0) { // Nessun eco ricevuto
        Serial.println("Errore nella lettura del sensore.");
        return -1; // Errore nella lettura
    }

    long distanza = (durata * 0.0343) / 2; // Calcolo distanza in cm
    Serial.print("Distanza misurata: ");
    Serial.println(distanza);

    if (distanza > DISTANCE_THRESHOLD) {
        return 1; // PORTA APERTA
    } else {
        return 0; // PORTA CHIUSA
    }
}

void buzz(int duration) {
    digitalWrite(BUZZER, HIGH);
    delay(duration);
    digitalWrite(BUZZER, LOW);
}

void send_packet(uint8_t message_type, String data) { // Funzione per inviare pacchetti strutturati
    Serial.write(0xFB); // Inizio pacchetto
    Serial.write(message_type); // Tipo di messaggio
    Serial.print(data); // Dati
    Serial.write(0xFA); // Fine pacchetto
}

void alert_alarm() { // Funzione per attivare l'allarme
    while (1) { // Ciclo infinito per mantenere l'allarme attivo
        digitalWrite(BUZZER, HIGH);
        delay(500);
        digitalWrite(BUZZER, LOW);
        delay(500);
    }
}

void check_for_remote_input() { // Funzione che riceve l'input di apertura da remoto tramite USB seriale
    if (Serial.available() > 0) {
        String a = Serial.readString(); // Ricevo il pacchetto dal bridge
        Serial.print("Valore ricevuto: " + a);
        int b = a.toInt();
        if (b == 1) { // Apri serratura (sbloccata)
            buzz(200); // Buzzer suona per 200ms
            digitalWrite(LED_ROSSO, LOW); // Serratura sbloccata
            digitalWrite(LED_VERDE, HIGH); // Serratura sbloccata
            digitalWrite(LED_BLU, HIGH); // Simula apertura porta
            delay(10); // Aspetto per vedere se la porta viene chiusa
            int door_status = check_proximity();  // Verifica lo stato reale della porta

            if (door_status == 1) {  // Se la porta è aperta
                send_packet(0x01, "001"); // Porta aperta
                // Devo comunicare al bridge che la porta è aperta
                while (door_status == 1) { // Finché la porta resta aperta
                    delay(5000); // Controllo ogni 5 secondi
                    door_status = check_proximity();
                }
            } else if (door_status == 0) { // Porta chiusa
                send_packet(0x01, "000"); // Porta chiusa
            } else { // Errore nella lettura del sensore
                Serial.println("Errore nella lettura del sensore di prossimità.");
            }
        } else if (b == 0) { // Blocca serratura
            buzz(100); // Buzzer suona per 100ms
            digitalWrite(LED_ROSSO, HIGH); // Serratura bloccata
            digitalWrite(LED_VERDE, LOW); // Serratura bloccata
            digitalWrite(LED_BLU, LOW); // Porta chiusa
        }
    }
}

void loop() {
    check_for_remote_input();
}