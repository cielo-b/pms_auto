#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN 9
#define SS_PIN 10

MFRC522 mfrc522(SS_PIN, RST_PIN);
String currentCard = "";
String storedData = "";

void setup()
{
    Serial.begin(9600);
    SPI.begin();
    mfrc522.PCD_Init();
    delay(4);
    mfrc522.PCD_DumpVersionToSerial();
    Serial.println("RFID Ready");
}

void loop()
{
    // Check for incoming commands
    if (Serial.available() > 0)
    {
        String command = Serial.readStringUntil('\n');
        command.trim();

        if (command == "READ")
        {
            readRFID();
        }
        else if (command.startsWith("WRITE"))
        {
            processWrite(command);
        }
    }
}

void readRFID()
{
    if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial())
    {
        Serial.println("NO_CARD");
        return;
    }

    String content = "";
    for (byte i = 0; i < mfrc522.uid.size; i++)
    {
        content.concat(String(mfrc522.uid.uidByte[i] < 0x10 ? "0" : ""));
        content.concat(String(mfrc522.uid.uidByte[i], HEX));
    }

    content.toUpperCase();
    Serial.println(content);
    delay(1000);
}

void processWrite(String command)
{
    // Format: WRITE,card_id,plate,balance
    int firstComma = command.indexOf(',');
    int secondComma = command.indexOf(',', firstComma + 1);
    int thirdComma = command.indexOf(',', secondComma + 1);

    String cardId = command.substring(firstComma + 1, secondComma);
    String plate = command.substring(secondComma + 1, thirdComma);
    String balance = command.substring(thirdComma + 1);
    
    storedData = cardId + "," + plate + "," + balance;
    Serial.println("WRITE_SUCCESS");
}