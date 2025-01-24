#include <SPI.h>
#include "Arduino.h"

#define ECHO_PIN 13
#define TRIGGER_PIN 12
#define BUZZER 10
#define LED_VERDE 5
#define LED_ROSSO 4
#define LED_BLU 3
#define DISTANCE_THRESHOLD 10

// System state variables -- initialization
bool lock = true;        // Lock is engaged
bool door_open = false;  // Door is closed
bool allarme_attivo = false; // Alarm is deactivated

// Variables for alarm management
int effrazione_count = 0;  // Counter for confirming intrusions (avoids false positives)
unsigned long lastCheckTime = 0; // Stores the last time the alarm was checked
const unsigned long CHECK_INTERVAL = 3000;

// Variables for heartbeat
unsigned long lastHeartbeatTime = 0;  // Stores the last time a heartbeat was sent
const unsigned long HEARTBEAT_INTERVAL = 60000;

void setup() {
    Serial.begin(9600);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROSSO, OUTPUT);
    pinMode(LED_BLU, OUTPUT);
    pinMode(BUZZER, OUTPUT);

    // Initial state
    digitalWrite(LED_BLU, LOW); // Door closed
    digitalWrite(LED_VERDE, LOW);
    digitalWrite(LED_ROSSO, HIGH); // Lock is engaged
    digitalWrite(BUZZER, LOW);

    Serial.println("System ready...");
    lastHeartbeatTime = millis(); // Initialize heartbeat timer
}

// Monitors door status using an ultrasonic sensor by measuring the detected distance
int check_proximity() {
    digitalWrite(TRIGGER_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIGGER_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIGGER_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH);
    if (duration == 0) {
        // Unreliable reading
        return -1;
    }

    float distance = (duration * 0.0343) / 2;
    Serial.print("Measured distance: ");
    Serial.print(distance);
    Serial.println(" cm");
    if (distance > DISTANCE_THRESHOLD) {
        return 1; // Door is open
    } else {
        return 0; // Door is closed
    }
}

// Controls the buzzer
void buzz(int duration) {
    digitalWrite(BUZZER, HIGH);
    delay(duration);
    digitalWrite(BUZZER, LOW);
}

// Sends state information about the lock, door, and alarm to the bridge
void send_packet(const char* message) {
    Serial.write(0xFB);
    Serial.print(message);
    Serial.write(0xFA);
}

// Activates the alarm in case of unauthorized door openings, turns on the buzzer, and sends a status packet to the bridge
void activate_alarm() {
    if (!allarme_attivo) {
        Serial.println("Alarm activated!");
        allarme_attivo = true;
        send_packet("EFF");
    }
}

// Deactivates the alarm, restores the system, and sends a status packet to the bridge
void deactivate_alarm() {
    if (allarme_attivo) {
        Serial.println("Alarm deactivated (D).");
        allarme_attivo = false;
        send_packet("D");
        digitalWrite(LED_ROSSO, HIGH);
        digitalWrite(BUZZER, LOW);
        effrazione_count = 0;
    }
}

// Unlocks the lock in response to commands received from the bridge, turns on the corresponding LEDs,
// and persists in a routine (while loop) until the door is closed. If not re-locked within 60 seconds, it sends an alert.
void unlock_procedure() {
    buzz(200); // Unlock confirmation beep
    lock = false; 
    digitalWrite(LED_VERDE, HIGH);
    digitalWrite(LED_ROSSO, LOW);
    Serial.println("Lock unlocked.");

    // Save the time the lock was unlocked
    unsigned long unlockStartTime = millis();
    bool notRelockedAlarm = false;  // Flag to send an alert once and activate a fixed beep

    int consecutive_closed = 0;

    while (true) {
        delay(1000); 
        int door_status = check_proximity();

        // Check if 60 seconds have passed since the lock was unlocked
        if (!notRelockedAlarm && (millis() - unlockStartTime >= 60000)) {
            digitalWrite(BUZZER, HIGH);
            send_packet("NRLOCK");
            Serial.println("Alert: The lock has not been re-locked within 60s!");
            notRelockedAlarm = true;
        }

        if (door_status == 1) { 
            // Door is open
            if (!door_open) {
                door_open = true;
                digitalWrite(LED_BLU, HIGH);
                send_packet("001"); 
                Serial.println("Door opened.");
            }
            consecutive_closed = 0;
        } 
        else if (door_status == 0) { 
            // Door is closed
            if (door_open) {
                consecutive_closed++;
                Serial.print("Door closed, cycle: ");
                Serial.println(consecutive_closed);

                // If the door is closed for 3 consecutive readings (3 seconds in this case)
                if (consecutive_closed >= 3) {
                    door_open = false;
                    lock = true; 
                    digitalWrite(LED_BLU, LOW);
                    digitalWrite(LED_VERDE, LOW);
                    digitalWrite(LED_ROSSO, HIGH);

                    // If the buzzer was sounding, turn it off
                    digitalWrite(BUZZER, LOW);

                    send_packet("000");
                    Serial.println("Door closed and lock re-engaged.");
                    break;
                }
            }
        } 
    }
}

// Locks the lock and visually updates the state -- aligns Arduino's logical state with Firestore --
void lock_procedure() {
    buzz(100);
    lock = true;
    digitalWrite(LED_ROSSO, HIGH);
    digitalWrite(LED_VERDE, LOW);
    if (!door_open) {
        digitalWrite(LED_BLU, LOW);
    }
    Serial.println("Lock engaged.");
    send_packet("000");
}

// Listens for commands received from the bridge regarding lock, door, and alarm state
void check_for_remote_input() {
    if (Serial.available() > 0) {
        String command = Serial.readString();
        command.trim();
        Serial.print("Received value: ");
        Serial.println(command);

        if (command == "1") {
            unlock_procedure();
        } else if (command == "0") {
            lock_procedure();
        } else if (command == "D") {
            // Deactivate alarm remotely
            deactivate_alarm();
        } else if (command == "A"){
            // Activate alarm (sync with Firestore)
            activate_alarm();
        }
    }
}

// Checks the conditions of the door and lock: activates the alarm if it detects abnormal openings
void check_alarm_condition() {
    // If the lock is engaged
    if (lock && !allarme_attivo) {
        int door_status = check_proximity();
        if (door_status == 1) {
            // Door opened with the lock engaged: increment intrusion counter
            effrazione_count++;
            if (effrazione_count >= 3) {
                activate_alarm();
            }
        } else if (door_status == 0) {
            // Door closed, reset counter
            effrazione_count = 0;
        }
    }
    // If the alarm is active, blink the red LED and the buzzer
    if (allarme_attivo) {
        digitalWrite(LED_ROSSO, !digitalRead(LED_ROSSO));
        digitalWrite(BUZZER, !digitalRead(BUZZER));
        delay(500); 
    }
}

void loop() {
    check_for_remote_input();

    // Every 3 seconds, check the alarm
    if (!allarme_attivo && (millis() - lastCheckTime >= CHECK_INTERVAL)) {
        lastCheckTime = millis();
        check_alarm_condition();
    } else if (allarme_attivo) {
        // Keep the delay(500) inside check_alarm_condition
        check_alarm_condition();
    }

    // Heartbeat: if more than HEARTBEAT_INTERVAL (60s) has passed, send "HB" to the bridge
    if (millis() - lastHeartbeatTime >= HEARTBEAT_INTERVAL) {
        send_packet("HB");
        Serial.println("Heartbeat sent (HB).");
        lastHeartbeatTime = millis();
    }
}