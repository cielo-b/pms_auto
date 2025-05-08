#include <Servo.h>
#include <SPI.h>
#include <MFRC522.h>

// RFID Setup
#define RST_PIN 9
#define SS_PIN 10
MFRC522 mfrc522(SS_PIN, RST_PIN);

// Ultrasonic Sensor Setup
#define TRIG_PIN 2
#define ECHO_PIN 3
#define MAX_DISTANCE 50 // cm

// LED Setup
#define RED_LED 6
#define BLUE_LED 7

// Servo Setup
#define SERVO_PIN 5
Servo gateServo;

// System Variables
bool gateOpen = false;
unsigned long vehicleDetectionTime = 0;
const unsigned long GATE_TIMEOUT = 10000; // 10 seconds

void setup() {
  Serial.begin(9600);
  
  // Initialize RFID
  SPI.begin();
  mfrc522.PCD_Init();
  
  // Initialize Ultrasonic
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  // Initialize LEDs
  pinMode(RED_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);
  
  // Initialize Servo
  gateServo.attach(SERVO_PIN);
  closeGate(); // Start with gate closed
  
  Serial.println("SYSTEM_READY");
}

void loop() {
  // Handle serial commands from Python
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "READ") {
      handleRFIDRead();
    } 
    else if (command.startsWith("WRITE,")) {
      handleRFIDWrite(command);
    }
    else if (command == "OPEN_GATE") {
      openGate();
    }
    else if (command == "CLOSE_GATE") {
      closeGate();
    }
  }

  // Vehicle presence detection
  if (gateOpen && checkVehiclePresence()) {
    vehicleDetectionTime = millis();
  } 
  else if (gateOpen && (millis() - vehicleDetectionTime > GATE_TIMEOUT)) {
    closeGate();
    Serial.println("GATE_AUTO_CLOSE");
  }
}

// RFID Functions
void handleRFIDRead() {
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    Serial.println("NO_CARD");
    return;
  }
  
  String cardID = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    cardID += String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
    cardID += String(mfrc522.uid.uidByte[i], HEX);
  }
  cardID.toUpperCase();
  mfrc522.PICC_HaltA();
  
  Serial.println(cardID);
}

void handleRFIDWrite(String command) {
  // Parse: WRITE,cardID,plate,balance
  int params[3];
  int lastIndex = 0;
  for (int i = 0; i < 3; i++) {
    lastIndex = command.indexOf(',', lastIndex + 1);
    params[i] = lastIndex;
  }
  
  String cardID = command.substring(params[0] + 1, params[1]);
  String plate = command.substring(params[1] + 1, params[2]);
  float balance = command.substring(params[2] + 1).toFloat();

  // Wait for correct card
  if (!waitForCard(cardID)) {
    Serial.println("WRITE_ERROR_CARD_NOT_FOUND");
    return;
  }

  // Write data to block 8
  String dataToWrite = plate + "," + String(balance, 2);
  if (writeToBlock(8, dataToWrite)) {
    Serial.println("WRITE_SUCCESS");
  } else {
    Serial.println("WRITE_ERROR");
  }
  mfrc522.PICC_HaltA();
}

// Gate Control Functions
void openGate() {
  gateServo.write(90); // Open position
  digitalWrite(BLUE_LED, HIGH);
  digitalWrite(RED_LED, LOW);
  gateOpen = true;
  vehicleDetectionTime = millis();
  Serial.println("GATE_OPEN");
}

void closeGate() {
  gateServo.write(0); // Closed position
  digitalWrite(RED_LED, HIGH);
  digitalWrite(BLUE_LED, LOW);
  gateOpen = false;
  Serial.println("GATE_CLOSED");
}

// Vehicle Detection
bool checkVehiclePresence() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH);
  int distance = duration * 0.034 / 2;
  
  return (distance > 0 && distance < MAX_DISTANCE);
}

// Helper Functions
bool waitForCard(String targetID) {
  unsigned long startTime = millis();
  while (millis() - startTime < 10000) {
    if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
      String currentID = "";
      for (byte i = 0; i < mfrc522.uid.size; i++) {
        currentID += String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : "");
        currentID += String(mfrc522.uid.uidByte[i], HEX);
      }
      currentID.toUpperCase();
      
      if (currentID == targetID) return true;
      mfrc522.PICC_HaltA();
    }
    delay(200);
  }
  return false;
}

bool writeToBlock(int block, String data) {
  MFRC522::MIFARE_Key key;
  for (byte i = 0; i < 6; i++) key.keyByte[i] = 0xFF;
  
  if (mfrc522.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, block, &key, &(mfrc522.uid)) != MFRC522::STATUS_OK) {
    return false;
  }

  byte buffer[16];
  for (byte i = 0; i < 16; i++) buffer[i] = ' ';
  data.getBytes(buffer, data.length() + 1);

  return (mfrc522.MIFARE_Write(block, buffer, 16) == MFRC522::STATUS_OK);
}
