#include <SPI.h>
#include "Arduino.h"

// Definisco i pin per i vari sensori e attuatori
#define triggerPort 6  // Sensore di prossimità
#define echoPort 7     // Sensore di prossimità
#define LED_G 5        // Pin LED verde
#define LED_R 4        // Pin LED rosso
#define LED_B 3        // Pin LED blu che simula l'apertura della porta
#define BUZZER 10       // Definisci il pin per il buzzer
#define ACCESS_DELAY 2000

void setup() {
    Serial.begin(9600);   // Inizializzo la porta seriale per debugging e comunicazione con il bridge
    pinMode(triggerPort, OUTPUT);
    pinMode(echoPort, INPUT);
    pinMode(LED_G, OUTPUT);
    pinMode(LED_R, OUTPUT);
    pinMode(LED_B, OUTPUT);
    pinMode(BUZZER, OUTPUT);
    digitalWrite(LED_B, LOW); // Inizialmente la porta è chiusa (LED blu spento)
    digitalWrite(BUZZER, LOW);
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

void check_for_remote_input() { // Funzione che riceve l'input di apertura da remoto tramite USB seriale
    if (Serial.available() > 0) {
        String a = Serial.readString(); // Ricevo il pacchetto dal bridge
        Serial.print("Valore ricevuto: " + a);
        int b = a.toInt();
        if (b == 1) { // Apri serratura (simulata con LED blu)
            buzz(200); // Buzzer suona per 200ms
            digitalWrite(LED_B, HIGH); // Simula apertura porta
            digitalWrite(LED_G, HIGH);
            digitalWrite(LED_R, LOW);
            delay(10); // Aspetto per vedere se la porta viene chiusa
            if (check_proximity()) {  // Se la porta è aperta
                send_packet(0x01, "001"); // Porta aperta
                // Devo comunicare al bridge che la porta è aperta
                while (check_proximity()) { // Finché la porta resta aperta
                    delay(10000); // Controllo ogni 10 secondi
                }
            }
            // Richiudo la porta (simulata con LED blu)..
            delay(ACCESS_DELAY);
            digitalWrite(LED_B, LOW);  // Chiudo la porta simulata
            digitalWrite(LED_G, LOW);
            delay(ACCESS_DELAY);
            send_packet(0x01, "000"); // Porta chiusa
            // Comunico di nuovo al bridge che la porta è chiusa
        } else if (b == 0) {
            buzz(100); // Buzzer suona per 100ms
            digitalWrite(LED_B, LOW); // Chiudo la porta simulata
            digitalWrite(LED_G, LOW);
        }
    }
}

void loop() {
    check_for_remote_input();
}