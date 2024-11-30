#include <SPI.h>
#include "Arduino.h"
#include <SoftwareSerial.h>

// Definisco i pin per i vari sensori e attuatori
#define triggerPort 6  // Sensore di prossimità
#define echoPort 7     // Sensore di prossimità
#define LED_G 5        // Pin LED verde
#define LED_R 4        // Pin LED rosso
#define RELAY 3        // Relay pin
#define ACCESS_DELAY 2000

SoftwareSerial BTSerial(10, 11); // RX, TX per il modulo Bluetooth

void setup() {
    Serial.begin(9600);   // Inizializzo la porta seriale per debugging
    BTSerial.begin(9600); // Inizializzo la porta seriale per Bluetooth
    pinMode(triggerPort, OUTPUT);
    pinMode(echoPort, INPUT);
    pinMode(LED_G, OUTPUT);
    pinMode(LED_R, OUTPUT);
    pinMode(RELAY, OUTPUT);
    digitalWrite(RELAY, HIGH);
    Serial.println("Sistema pronto...");
}

int check_proximity() { // Funzione per controllare lo status della porta, se aperta o chiusa
    digitalWrite(triggerPort, LOW); // Porta bassa l'uscita Trig = reset porta
    delay(2);
    digitalWrite(triggerPort, HIGH); // Invia un impulso di 10 microsec su Trig
    delayMicroseconds(10);
    digitalWrite(triggerPort, LOW);

    long durata = pulseIn(echoPort, HIGH); // Misura la durata dell'impulso ALTO su Echo

    if (durata > 38000) { // Dopo 38ms è fuori dalla portata del sensore
        return 1;  // PORTA APERTA
    } 
    else {
        long distanza = 0.0343 * durata / 2; // Calcolo distanza
        if (distanza > 5) {
        return 1;   // PORTA APERTA
        } else {
        return 0;    // PORTA CHIUSA
        }
    }
}

void check_for_remote_input() { // Funzione che riceve l'input di apertura da remoto tramite Bluetooth
    if (BTSerial.available() > 0) {
        String a = BTSerial.readString(); // Ricevo il pacchetto dal bridge
        Serial.print("Valore ricevuto: " + a);
        int b = a.toInt();
        if (b == 1) { // Apri serratura
        digitalWrite(RELAY, LOW);
        digitalWrite(LED_G, HIGH);
        digitalWrite(LED_R, LOW);
        delay(10); // Aspetto per vedere se la porta viene chiusa
        if (check_proximity()) {  // Se la porta è aperta
            BTSerial.write(0xfb); // Inizio pacchetto
            BTSerial.print("001"); // Porta aperta
            BTSerial.write(0xfa); // Fine pacchetto
            // Devo comunicare al bridge che la porta è aperta
            while (check_proximity()) { // Finché la porta resta aperta
            delay(10); // Controllo ogni 10 secondi
            }
        }
        // Richiudo la porta..
        delay(ACCESS_DELAY);
        digitalWrite(RELAY, HIGH);  // Chiudo la serratura perché la porta è chiusa
        digitalWrite(LED_G, LOW);
        delay(ACCESS_DELAY);
        BTSerial.write(0xfb); // Inizio pacchetto
        BTSerial.print("000"); // Porta chiusa
        BTSerial.write(0xfa); // Fine pacchetto
        // Comunico di nuovo al bridge che la porta è chiusa
        } else if (b == 0) {
        digitalWrite(RELAY, HIGH);
        digitalWrite(LED_G, LOW);
        }
    }
}

void loop() {
    check_for_remote_input();
}

