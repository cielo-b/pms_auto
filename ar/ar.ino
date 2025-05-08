#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9 // Reset pin for MFRC522
#define SS_PIN 10 // Slave Select pin for MFRC522
#define DETECTION_RETRIES 15 // Retries for card detection in read
#define DETECTION_DELAY 400 // Delay between retries (ms)
#define WRITE_RETRIES 5 // Retries for card detection in write

MFRC522 rfid(SS_PIN, RST_PIN); // Create MFRC522 instance
MFRC522::MIFARE_Key key; // Default key for authentication

void setup() {
  Serial.begin(9600); // Initialize serial communication at 9600 baud
  while (!Serial); // Wait for serial port to connect
  SPI.begin(); // Initialize SPI bus
  rfid.PCD_Init(); // Initialize MFRC522
  // Set default key (0xFF for all 6 bytes)
  for (byte i = 0; i < 6; i++) {
    key.keyByte[i] = 0xFF;
  }
  // Verify RFID module
  if (rfid.PCD_PerformSelfTest()) {
    Serial.println("RFID Module Initialized<END>");
  } else {
    Serial.println("RFID Module Failed - Resetting<END>");
    rfid.PCD_Init(); // Retry initialization
  }
  Serial.flush();
}

void loop() {
  // Check for incoming serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove whitespace
    processCommand(command);
  }
}

void processCommand(String command) {
  // Clear serial buffer to avoid stale data
  while (Serial.available()) {
    Serial.read();
  }
  
  if (command == "READ") {
    readCard();
  } else if (command.startsWith("WRITE")) {
    // Expected format: WRITE,card_id,plate_number,balance
    int firstComma = command.indexOf(',');
    int secondComma = command.indexOf(',', firstComma + 1);
    int thirdComma = command.indexOf(',', secondComma + 1);
    
    if (firstComma != -1 && secondComma != -1 && thirdComma != -1) {
      String card_id = command.substring(firstComma + 1, secondComma);
      String plate_number = command.substring(secondComma + 1, thirdComma);
      String balance = command.substring(thirdComma + 1);
      if (card_id.length() >= 8 && plate_number.length() > 0 && balance.length() > 0) {
        writeCard(card_id, plate_number, balance);
      } else {
        Serial.println("INVALID_WRITE_DATA<END>");
      }
    } else {
      Serial.println("INVALID_WRITE_FORMAT<END>");
    }
  } else {
    Serial.println("UNKNOWN_COMMAND<END>");
  }
  Serial.flush();
}

void readCard() {
  // Retry card detection multiple times
  for (int i = 0; i < DETECTION_RETRIES; i++) {
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      // Get card UID
      String card_id = "";
      for (byte i = 0; i < rfid.uid.size; i++) {
        if (rfid.uid.uidByte[i] < 0x10) card_id += "0";
        card_id += String(rfid.uid.uidByte[i], HEX);
      }
      card_id.toUpperCase();
      Serial.println(card_id + "<END>");
      Serial.flush();
      // Do not halt the card to allow immediate write
      rfid.PCD_StopCrypto1();
      return;
    }
    delay(DETECTION_DELAY); // Wait before retrying
  }
  Serial.println("NO_CARD<END>");
  Serial.flush();
}

void writeCard(String card_id, String plate_number, String balance) {
  // Reset reader state
  rfid.PCD_Init();
  delay(500); // Reduced delay to stabilize reader
  
  // Retry card detection multiple times
  for (int i = 0; i < WRITE_RETRIES; i++) {
    if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
      // Verify card ID matches
      String current_id = "";
      for (byte i = 0; i < rfid.uid.size; i++) {
        if (rfid.uid.uidByte[i] < 0x10) current_id += "0";
        current_id += String(rfid.uid.uidByte[i], HEX);
      }
      current_id.toUpperCase();
      
      if (current_id != card_id) {
        Serial.println("CARD_MISMATCH<END>");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        Serial.flush();
        return;
      }

      // Authenticate for writing (using sector 1, block 4)
      MFRC522::StatusCode status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, 4, &key, &(rfid.uid));
      if (status != MFRC522::STATUS_OK) {
        Serial.println("AUTH_FAIL<END>");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        Serial.flush();
        return;
      }

      // Prepare data: plate_number (max 16 bytes) and balance (max 16 bytes)
      byte buffer[16];
      // Write plate_number to block 4
      memset(buffer, 0, 16); // Clear buffer
      plate_number.getBytes(buffer, 16);
      status = rfid.MIFARE_Write(4, buffer, 16);
      if (status != MFRC522::STATUS_OK) {
        Serial.println("WRITE_FAIL_PLATE<END>");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        Serial.flush();
        return;
      }

      // Authenticate for next block (block 5)
      status = rfid.PCD_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, 5, &key, &(rfid.uid));
      if (status != MFRC522::STATUS_OK) {
        Serial.println("AUTH_FAIL<END>");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        Serial.flush();
        return;
      }

      // Write balance to block 5
      memset(buffer, 0, 16); // Clear buffer
      balance.getBytes(buffer, 16);
      status = rfid.MIFARE_Write(5, buffer, 16);
      if (status != MFRC522::STATUS_OK) {
        Serial.println("WRITE_FAIL_BALANCE<END>");
        rfid.PICC_HaltA();
        rfid.PCD_StopCrypto1();
        Serial.flush();
        return;
      }

      Serial.println("WRITE_SUCCESS<END>");
      Serial.flush();
      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      return;
    }
    delay(DETECTION_DELAY); // Wait before retrying
  }
  
  Serial.println("NO_CARD<END>");
  Serial.flush();
}
