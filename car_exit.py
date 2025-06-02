import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import csv
from collections import Counter
from datetime import datetime

# Load YOLOv8 model
model = YOLO('./best.pt')

# CSV log files
authorized_csv = './database/plates_log.csv'
unauthorized_csv = './database/unauthorized_exits.csv'

# ===== Auto-detect Arduino Serial Port =====
def detect_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "ttyUSB" in port.device or "ttyACM0" in port.device:
            return port.device
    return None

arduino_port = detect_arduino_port()
if arduino_port:
    print(f"[CONNECTED] Arduino on {arduino_port}")
    arduino = serial.Serial(arduino_port, 9600, timeout=1)
    time.sleep(2)
else:
    print("[ERROR] Arduino not detected.")
    arduino = None

# ===== Check payment status and update exit time =====
def process_exit(plate_number):
    if not os.path.exists(authorized_csv):
        print("[ERROR] Log file does not exist.")
        return False

    # Read all rows
    rows = []
    with open(authorized_csv, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find the latest entry for this plate that hasn't exited
    for row in reversed(rows):
        if row['Plate Number'] == plate_number and row['Payment Status'] == '1' and not row['Out time']:
            # Update exit time
            row['Out time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Write back all rows
            with open(authorized_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['Plate Number', 'Payment Status', 'In time', 'Out time'])
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"[SUCCESS] Exit time updated for {plate_number}")
            return True

    print(f"[ERROR] No valid entry found for {plate_number}")
    return False

# ===== Log unauthorized exit =====
def log_unauthorized_exit(plate_number):
    # Create file if it doesn't exist
    if not os.path.exists(unauthorized_csv):
        with open(unauthorized_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Plate Number', 'Timestamp'])
    
    # Append new entry
    with open(unauthorized_csv, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([plate_number, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    
    print(f"[SECURITY ALERT] Unauthorized exit logged for {plate_number}")

# ===== Webcam and Main Loop =====
cap = cv2.VideoCapture(0)
plate_buffer = []

print("[EXIT SYSTEM] Ready. Press 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame)

    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            plate_img = frame[y1:y2, x1:x2]

            # Preprocessing
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

            # OCR
            plate_text = pytesseract.image_to_string(
                thresh, config='--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            ).strip().replace(" ", "")

            if "RA" in plate_text:
                start_idx = plate_text.find("RA")
                plate_candidate = plate_text[start_idx:]
                if len(plate_candidate) >= 7:
                    plate_candidate = plate_candidate[:7]
                    prefix, digits, suffix = plate_candidate[:3], plate_candidate[3:6], plate_candidate[6]
                    if (prefix.isalpha() and prefix.isupper() and
                        digits.isdigit() and suffix.isalpha() and suffix.isupper()):
                        print(f"[VALID] Plate Detected: {plate_candidate}")
                        plate_buffer.append(plate_candidate)

                        if len(plate_buffer) >= 3:
                            most_common = Counter(plate_buffer).most_common(1)[0][0]
                            plate_buffer.clear()

                            # Process exit and update CSV
                            if process_exit(most_common):
                                print(f"[ACCESS GRANTED] Processing exit for {most_common}")
                                if arduino:
                                    arduino.write(b'1')  # Open gate
                                    print("[GATE] Opening gate (sent '1')")
                                    time.sleep(15)
                                    arduino.write(b'0')  # Close gate
                                    print("[GATE] Closing gate (sent '0')")
                            else:
                                print(f"[ACCESS DENIED] Cannot process exit for {most_common}")
                                log_unauthorized_exit(most_common)
                                if arduino:
                                    arduino.write(b'2')  # Trigger warning buzzer
                                    print("[ALERT] Buzzer triggered (sent '2')")
                                    time.sleep(3)  # Buzzer duration
                                    arduino.write(b'0')  # Stop buzzer

            cv2.imshow("Plate", plate_img)
            cv2.imshow("Processed", thresh)

    annotated_frame = results[0].plot()
    cv2.imshow("Exit Webcam Feed", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
if arduino:
    arduino.close()
cv2.destroyAllWindows()