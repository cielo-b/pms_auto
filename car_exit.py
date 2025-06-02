import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import csv
from collections import Counter, deque
from datetime import datetime, timedelta
from utils.data_handler import get_db_connection, update_vehicle_exit, save_vehicle_entry
from sqlalchemy import create_engine, text

# ===== Message Queue System =====
class MessageQueue:
    def __init__(self, max_messages=3, message_duration=5):
        self.messages = deque(maxlen=max_messages)
        self.message_duration = message_duration
    
    def add_message(self, message, color):
        self.messages.append({
            'message': message,
            'color': color,
            'timestamp': datetime.now()
        })
    
    def get_active_messages(self):
        current_time = datetime.now()
        active_messages = []
        for msg in self.messages:
            if (current_time - msg['timestamp']).total_seconds() < self.message_duration:
                active_messages.append(msg)
        return active_messages

# ===== Display Message on Frame =====
def display_messages(frame, message_queue):
    """Display multiple messages on the frame with background for better visibility"""
    # Create a copy of the frame
    display_frame = frame.copy()
    
    # Get frame dimensions
    height, width = frame.shape[:2]
    
    # Get active messages
    active_messages = message_queue.get_active_messages()
    
    # Display each message
    for i, msg in enumerate(active_messages):
        message = msg['message']
        color = msg['color']
        
        # Calculate position for this message
        text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
        text_x = (width - text_size[0]) // 2
        text_y = height - 50 - (i * 60)  # Stack messages vertically
        
        # Draw background rectangle
        cv2.rectangle(display_frame, 
                     (text_x - 10, text_y - text_size[1] - 10),
                     (text_x + text_size[0] + 10, text_y + 10),
                     (0, 0, 0),
                     -1)
        
        # Draw text
        cv2.putText(display_frame,
                    message,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    color,
                    2)
    
    return display_frame

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
def process_exit(plate_number, message_queue):
    if not os.path.exists(authorized_csv):
        print("[ERROR] Log file does not exist.")
        message_queue.add_message("ERROR: Log file does not exist", (0, 0, 255))
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
            current_time = datetime.now()
            current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
            row['Out time'] = current_time_str
            
            # Write back all rows
            with open(authorized_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['Plate Number', 'Payment Status', 'In time', 'Out time'])
                writer.writeheader()
                writer.writerows(rows)
            
            # Update database with out_time only
            engine = get_db_connection()
            if engine is not None:
                query = text("""
                    UPDATE vehicle_logs 
                    SET out_time = :out_time
                    WHERE plate_number = :plate_number 
                    AND status = 1
                    AND out_time IS NULL
                    RETURNING id
                """)
                try:
                    with engine.connect() as conn:
                        result = conn.execute(query, {
                            "plate_number": plate_number,
                            "out_time": current_time
                        })
                        conn.commit()
                        if result.rowcount > 0:
                            print(f"[DATABASE] Exit time updated in database for {plate_number}")
                            message_queue.add_message(f"EXIT GRANTED: {plate_number}", (0, 255, 0))
                        else:
                            print(f"[DATABASE] No matching record found for {plate_number}")
                            message_queue.add_message(f"ERROR: No record found for {plate_number}", (0, 0, 255))
                except Exception as e:
                    print(f"[DATABASE ERROR] Failed to update exit time: {str(e)}")
                    message_queue.add_message("ERROR: Database update failed", (0, 0, 255))
            else:
                print(f"[ERROR] Failed to connect to database for exit time update")
                message_queue.add_message("ERROR: Database connection failed", (0, 0, 255))
            
            print(f"[SUCCESS] Exit time updated for {plate_number}")
            return True

    print(f"[ERROR] No valid entry found for {plate_number}")
    message_queue.add_message(f"DENIED: No valid entry for {plate_number}", (0, 0, 255))
    return False

# ===== Log unauthorized exit =====
def log_unauthorized_exit(plate_number, message_queue):
    # Create file if it doesn't exist
    if not os.path.exists(unauthorized_csv):
        with open(unauthorized_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Plate Number', 'Timestamp'])
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Append new entry to CSV
    with open(unauthorized_csv, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([plate_number, current_time])
    
    # Log to database
    engine = get_db_connection()
    if engine is not None:
        query = text("""
            INSERT INTO unauthorized_exits (plate_number, timestamp)
            VALUES (:plate_number, :timestamp)
        """)
        try:
            with engine.connect() as conn:
                conn.execute(query, {
                    "plate_number": plate_number,
                    "timestamp": current_time
                })
                conn.commit()
                print(f"[DATABASE] Unauthorized exit logged in database for {plate_number}")
                message_queue.add_message(f"SECURITY ALERT: Unauthorized exit logged for {plate_number}", (0, 0, 255))
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to log unauthorized exit: {str(e)}")
            message_queue.add_message("ERROR: Failed to log unauthorized exit", (0, 0, 255))
    else:
        print(f"[ERROR] Failed to connect to database for unauthorized exit logging")
        message_queue.add_message("ERROR: Database connection failed", (0, 0, 255))
    
    print(f"[SECURITY ALERT] Unauthorized exit logged for {plate_number}")

# ===== Webcam and Main Loop =====
cap = cv2.VideoCapture(0)
plate_buffer = []
message_queue = MessageQueue(max_messages=3, message_duration=5)

print("[EXIT SYSTEM] Ready. Press 'q' to quit.")
message_queue.add_message("Exit System Ready", (0, 255, 0))

while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARNING] Frame capture failed")
        message_queue.add_message("WARNING: Frame capture failed", (255, 165, 0))
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
                        message_queue.add_message(f"Plate Detected: {plate_candidate}", (0, 255, 255))
                        plate_buffer.append(plate_candidate)

                        if len(plate_buffer) >= 3:
                            most_common = Counter(plate_buffer).most_common(1)[0][0]
                            plate_buffer.clear()

                            # Process exit and update CSV
                            if process_exit(most_common, message_queue):
                                print(f"[ACCESS GRANTED] Processing exit for {most_common}")
                                if arduino:
                                    arduino.write(b'1')  # Open gate
                                    print("[GATE] Opening gate (sent '1')")
                                    message_queue.add_message("GATE: Opening", (0, 255, 0))
                                    time.sleep(15)
                                    arduino.write(b'0')  # Close gate
                                    print("[GATE] Closing gate (sent '0')")
                                    message_queue.add_message("GATE: Closing", (0, 255, 0))
                            else:
                                print(f"[ACCESS DENIED] Cannot process exit for {most_common}")
                                log_unauthorized_exit(most_common, message_queue)
                                if arduino:
                                    arduino.write(b'2')  # Trigger warning buzzer
                                    print("[ALERT] Buzzer triggered (sent '2')")
                                    message_queue.add_message("ALERT: Unauthorized exit", (0, 0, 255))
                                    time.sleep(3)  # Buzzer duration
                                    arduino.write(b'0')  # Stop buzzer

            cv2.imshow("Plate", plate_img)
            cv2.imshow("Processed", thresh)

    annotated_frame = results[0].plot()
    # Display all active messages
    annotated_frame = display_messages(annotated_frame, message_queue)
    
    # Add system status
    cv2.putText(
        annotated_frame,
        "System: ACTIVE",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
    )
    cv2.imshow("Exit Webcam Feed", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        message_queue.add_message("System Shutting Down", (255, 165, 0))
        break

cap.release()
if arduino:
    arduino.close()
cv2.destroyAllWindows()