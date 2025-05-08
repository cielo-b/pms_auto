#include <Servo.h>

#define TRIG_PIN 7
#define ECHO_PIN 6
#define RED_LED 4
#define BLUE_LED 5
#define SERVO_PIN 9

Servo gateServo;
String incomingData = "";
bool carDetected = false;

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);

  gateServo.attach(SERVO_PIN);
  gateServo.write(0);  // gate closed position
}

void loop() {
  checkForSerialCommand();
  detectCar();
}

void checkForSerialCommand() {
  while (Serial.available()) {
    char received = Serial.read();
    if (received == '\n') {
      incomingData.trim();
      if (incomingData == "GRANT") {
        Serial.print(incomingData);
        grantAccess();
      } else if (incomingData == "DENY") {
        denyAccess();
      }
      incomingData = "";
    } else {
      incomingData += received;
    }
  }
}

void detectCar() {
  long duration, distance;
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  duration = pulseIn(ECHO_PIN, HIGH);
  distance = duration * 0.034 / 2;

  if (distance < 10 && !carDetected) {
    carDetected = true;
    Serial.println("CAR_DETECTED");
  } else if (distance >= 10 && carDetected) {
    carDetected = false;
    Serial.println("CAR_LEFT");
  }
}

void grantAccess() {
  digitalWrite(RED_LED, LOW);
  digitalWrite(BLUE_LED, HIGH);

  gateServo.write(90);  // open gate
  delay(3000);          // keep open 3 seconds

  gateServo.write(0);   // close gate
  digitalWrite(BLUE_LED, LOW);
}

void denyAccess() {
  digitalWrite(BLUE_LED, LOW);
  for (int i = 0; i < 3; i++) {
    digitalWrite(RED_LED, HIGH);
    delay(300);
    digitalWrite(RED_LED, LOW);
    delay(300);
  }
}
