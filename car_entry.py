import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import csv
from collections import Counter, deque
import numpy as np
import random
from utils.data_handler import save_vehicle_entry, update_vehicle_exit, get_db_connection
from sqlalchemy import text
from datetime import datetime, timedelta

# ===== Configuration =====
CONFIG = {
    "model_path": "./best.pt",
    "save_dir": "plates",
    "csv_file": "./database/plates_log.csv",
    "arduino_baudrate": 9600,
    "ultrasonic_threshold": 50,  # cm
    "plate_buffer_size": 3,
    "entry_cooldown": 300,  # 5 minutes in seconds
    "gate_open_duration": 15,  # seconds
    "ocr_config": "--psm 8 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "plate_format": {
        "prefix_len": 3,
        "digits_len": 3,
        "suffix_len": 1,
        "required_prefix": "RA",
    },
}


# ===== Initialize Components =====
def initialize_system():
    # Load YOLOv8 model
    model = YOLO(CONFIG["model_path"])

    # Create directories if they don't exist
    os.makedirs(CONFIG["save_dir"], exist_ok=True)

    # Initialize CSV log file
    if not os.path.exists(CONFIG["csv_file"]):
        with open(CONFIG["csv_file"], "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Plate Number", "Payment Status", "In time", "Out time"])

    return model


# ===== Serial Communication =====
def connect_arduino():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        print(port.device)
        if "ttyUSB" in port.device or "ttyACM0" in port.device:
            try:
                arduino = serial.Serial(
                    port.device, CONFIG["arduino_baudrate"], timeout=1
                )
                time.sleep(2)  # Allow time for connection
                print(f"[CONNECTED] Arduino on {port.device}")
                return arduino
            except serial.SerialException:
                continue
    print("[ERROR] Arduino not detected or connection failed.")
    return None


# ===== Image Processing =====
def preprocess_plate_image(plate_img):
    """Optimized plate image preprocessing"""
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    kernel = np.ones((1, 1), np.uint8)
    processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    return processed


# ===== OCR Processing =====
def extract_plate_text(processed_img):
    """Optimized plate text extraction"""
    try:
        plate_text = (
            pytesseract.image_to_string(processed_img, config=CONFIG["ocr_config"])
            .strip()
            .replace(" ", "")
        )
        plate_text = "".join(c for c in plate_text if c.isalnum())
        return plate_text.upper()
    except Exception as e:
        print(f"[OCR ERROR] {str(e)}")
        return ""


# ===== Plate Validation =====
def validate_plate(plate_text):
    """Validate plate format"""
    if not plate_text:
        return None
    if CONFIG["plate_format"]["required_prefix"] not in plate_text:
        return None
    start_idx = plate_text.find(CONFIG["plate_format"]["required_prefix"])
    plate_candidate = plate_text[start_idx:]
    min_length = (
        CONFIG["plate_format"]["prefix_len"]
        + CONFIG["plate_format"]["digits_len"]
        + CONFIG["plate_format"]["suffix_len"]
    )
    if len(plate_candidate) < min_length:
        return None
    prefix = plate_candidate[: CONFIG["plate_format"]["prefix_len"]]
    digits = plate_candidate[
        CONFIG["plate_format"]["prefix_len"] : CONFIG["plate_format"]["prefix_len"]
        + CONFIG["plate_format"]["digits_len"]
    ]
    suffix = plate_candidate[
        CONFIG["plate_format"]["prefix_len"]
        + CONFIG["plate_format"]["digits_len"] : CONFIG["plate_format"]["prefix_len"]
        + CONFIG["plate_format"]["digits_len"]
        + CONFIG["plate_format"]["suffix_len"]
    ]
    if (
        prefix.isalpha()
        and prefix.isupper()
        and digits.isdigit()
        and suffix.isalpha()
        and suffix.isupper()
    ):
        return f"{prefix}{digits}{suffix}"
    return None


# ===== Check for Unpaid Duplicate Plates =====
def check_unpaid_duplicate(plate_number):
    """Check if there's an unpaid entry for this plate number"""
    try:
        # Check CSV file
        if os.path.exists(CONFIG["csv_file"]):
            with open(CONFIG["csv_file"], "r") as f:
                reader = csv.DictReader(f)
                for row in reversed(list(reader)):
                    if (row["Plate Number"] == plate_number and 
                        row["Payment Status"] == "0" and 
                        not row["Out time"]):
                        return True

        # Check database
        engine = get_db_connection()
        if engine is not None:
            query = text("""
                SELECT COUNT(*) 
                FROM vehicle_logs 
                WHERE plate_number = :plate_number 
                AND status = 0 
                AND out_time IS NULL
            """)
            with engine.connect() as conn:
                result = conn.execute(query, {"plate_number": plate_number})
                count = result.scalar()
                return count > 0

        return False
    except Exception as e:
        print(f"[ERROR] Failed to check for unpaid duplicates: {str(e)}")
        return False


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


# ===== Main Loop =====
def main():
    model = initialize_system()
    arduino = connect_arduino()
    message_queue = MessageQueue(max_messages=3, message_duration=5)

    if not arduino:
        print("[WARNING] Running in simulation mode without Arduino")
        message_queue.add_message("WARNING: Running in simulation mode", (255, 165, 0))

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open video capture")
        message_queue.add_message("ERROR: Could not open video capture", (0, 0, 255))
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    plate_buffer = []
    last_saved_plate = None
    last_entry_time = 0

    print("[SYSTEM] Ready. Press 'q' to exit.")
    message_queue.add_message("System Ready", (0, 255, 0))

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Frame capture failed")
                message_queue.add_message("WARNING: Frame capture failed", (255, 165, 0))
                break

            # Simulate ultrasonic sensor
            distance = random.choice([random.randint(10, 40), random.randint(60, 150)])

            if distance <= CONFIG["ultrasonic_threshold"]:
                # Run YOLO detection
                start_time = time.time()
                results = model(frame, verbose=False)
                detection_time = time.time() - start_time

                if len(results[0].boxes) > 0:
                    for box in results[0].boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        plate_img = frame[y1:y2, x1:x2]
                        processed_img = preprocess_plate_image(plate_img)
                        plate_text = extract_plate_text(processed_img)
                        print(f"[OCR] Raw text: {plate_text}")

                        valid_plate = validate_plate(plate_text)
                        if valid_plate:
                            print(f"[VALID] Plate detected: {valid_plate}")
                            plate_buffer.append(valid_plate)
                            message_queue.add_message(f"Plate Detected: {valid_plate}", (0, 255, 255))

                            cv2.imshow("Plate", plate_img)
                            cv2.imshow("Processed", processed_img)

                            if len(plate_buffer) >= CONFIG["plate_buffer_size"]:
                                most_common = Counter(plate_buffer).most_common(1)[0][0]
                                current_time = time.time()

                                # Check for unpaid duplicates
                                if check_unpaid_duplicate(most_common):
                                    print(f"[DENIED] Unpaid entry exists for plate: {most_common}")
                                    message_queue.add_message(
                                        f"DENIED: Unpaid entry exists for {most_common}",
                                        (0, 0, 255)
                                    )
                                    if arduino:
                                        arduino.write(b"2")
                                        print("[ALERT] Buzzer triggered")
                                        time.sleep(3)
                                        arduino.write(b"0")
                                    plate_buffer.clear()
                                    continue

                                # Check cooldown
                                if (
                                    most_common != last_saved_plate
                                    or (current_time - last_entry_time)
                                    > CONFIG["entry_cooldown"]
                                ):
                                    # Log to CSV and Database
                                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                                    with open(CONFIG["csv_file"], "a", newline="") as f:
                                        writer = csv.writer(f)
                                        writer.writerow(
                                            [
                                                most_common,
                                                "0",
                                                current_time,
                                                "",
                                            ]
                                        )
                                    print(f"[SAVED] Plate: {most_common} logged to CSV")
                                    message_queue.add_message(
                                        f"SAVED: {most_common} logged to CSV",
                                        (0, 255, 0)
                                    )

                                    # Log to database
                                    if save_vehicle_entry(most_common):
                                        print(f"[SAVED] Plate: {most_common} logged to database")
                                        message_queue.add_message(
                                            f"ACCESS GRANTED: {most_common}",
                                            (0, 255, 0)
                                        )
                                    else:
                                        print(f"[ERROR] Failed to log plate: {most_common} to database")
                                        message_queue.add_message(
                                            f"ERROR: Failed to log {most_common}",
                                            (0, 0, 255)
                                        )

                                    # Control gate
                                    if arduino:
                                        arduino.write(b"1")
                                        print("[GATE] Opening gate")
                                        message_queue.add_message("GATE: Opening", (0, 255, 0))
                                        time.sleep(CONFIG["gate_open_duration"])
                                        arduino.write(b"0")
                                        print("[GATE] Closing gate")
                                        message_queue.add_message("GATE: Closing", (0, 255, 0))

                                    last_saved_plate = most_common
                                    last_entry_time = current_time
                                else:
                                    print("[SKIPPED] Duplicate plate within cooldown period")
                                    message_queue.add_message(
                                        f"SKIPPED: {most_common} within cooldown",
                                        (255, 165, 0)
                                    )

                                plate_buffer.clear()

                annotated_frame = results[0].plot()
                # Display all active messages
                annotated_frame = display_messages(annotated_frame, message_queue)
                
                # Add detection time and system status
                cv2.putText(
                    annotated_frame,
                    f"Detection: {detection_time:.2f}s",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.putText(
                    annotated_frame,
                    "System: ACTIVE",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
            else:
                annotated_frame = frame
                # Display all active messages
                annotated_frame = display_messages(annotated_frame, message_queue)
                # Add system status
                cv2.putText(
                    annotated_frame,
                    "System: WAITING",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 165, 0),
                    2,
                )

            cv2.imshow("Webcam Feed", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down...")
        message_queue.add_message("System Shutting Down", (255, 165, 0))
    finally:
        cap.release()
        if arduino:
            arduino.close()
        cv2.destroyAllWindows()
        print("[SYSTEM] Cleanup complete")


if __name__ == "__main__":
    main()
