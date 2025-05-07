import cv2
from ultralytics import YOLO
import pytesseract
import os
import time
import serial
import serial.tools.list_ports
import csv
from collections import Counter
import numpy as np
import random

# ===== Configuration =====
CONFIG = {
    "model_path": "./best.pt",
    "save_dir": "plates",
    "csv_file": "plates_log.csv",
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
            writer.writerow(["Plate Number", "Payment Status", "Timestamp"])

    return model


# ===== Serial Communication =====
def connect_arduino():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "ttyUSB" in port.device or "ttyACM" in port.device:
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
    # Convert to grayscale
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)

    # Apply CLAHE for better contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Denoising
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Optional: Morphological operations to clean up image
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

        # Additional processing to improve accuracy
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

    # Check for required prefix
    if CONFIG["plate_format"]["required_prefix"] not in plate_text:
        return None

    start_idx = plate_text.find(CONFIG["plate_format"]["required_prefix"])
    plate_candidate = plate_text[start_idx:]

    # Check minimum length
    min_length = (
        CONFIG["plate_format"]["prefix_len"]
        + CONFIG["plate_format"]["digits_len"]
        + CONFIG["plate_format"]["suffix_len"]
    )

    if len(plate_candidate) < min_length:
        return None

    # Extract parts
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

    # Validate format
    if (
        prefix.isalpha()
        and prefix.isupper()
        and digits.isdigit()
        and suffix.isalpha()
        and suffix.isupper()
    ):
        return f"{prefix}{digits}{suffix}"

    return None


# ===== Main Loop =====
def main():
    model = initialize_system()
    arduino = connect_arduino()

    if not arduino:
        print("[WARNING] Running in simulation mode without Arduino")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open video capture")
        return

    # Set camera resolution for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    plate_buffer = []
    last_saved_plate = None
    last_entry_time = 0

    print("[SYSTEM] Ready. Press 'q' to exit.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Frame capture failed")
                break

            # Simulate ultrasonic sensor
            distance = random.choice([random.randint(10, 40), random.randint(60, 150)])
            print(f"[SENSOR] Distance: {distance} cm")

            if distance <= CONFIG["ultrasonic_threshold"]:
                # Start timer for performance measurement
                start_time = time.time()

                # Run YOLO detection
                results = model(
                    frame, verbose=False
                )  # Disable verbose output for cleaner logs
                detection_time = time.time() - start_time
                print(f"[PERF] Detection time: {detection_time:.2f}s")

                if len(results[0].boxes) > 0:
                    for box in results[0].boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        plate_img = frame[y1:y2, x1:x2]

                        # Process plate image
                        processed_img = preprocess_plate_image(plate_img)

                        # Extract plate text
                        plate_text = extract_plate_text(processed_img)
                        print(f"[OCR] Raw text: {plate_text}")

                        # Validate plate
                        valid_plate = validate_plate(plate_text)
                        if valid_plate:
                            print(f"[VALID] Plate detected: {valid_plate}")
                            plate_buffer.append(valid_plate)

                            # Show processed images
                            cv2.imshow("Plate", plate_img)
                            cv2.imshow("Processed", processed_img)

                            # Check if we have enough detections
                            if len(plate_buffer) >= CONFIG["plate_buffer_size"]:
                                most_common = Counter(plate_buffer).most_common(1)[0][0]
                                current_time = time.time()

                                # Check cooldown
                                if (
                                    most_common != last_saved_plate
                                    or (current_time - last_entry_time)
                                    > CONFIG["entry_cooldown"]
                                ):

                                    # Log to CSV
                                    with open(CONFIG["csv_file"], "a", newline="") as f:
                                        writer = csv.writer(f)
                                        writer.writerow(
                                            [
                                                most_common,
                                                0,  # Payment status
                                                time.strftime("%Y-%m-%d %H:%M:%S"),
                                            ]
                                        )
                                    print(f"[SAVED] {most_common} logged to CSV")

                                    # Control gate
                                    if arduino:
                                        arduino.write(b"1")
                                        print("[GATE] Opening gate")
                                        time.sleep(CONFIG["gate_open_duration"])
                                        arduino.write(b"0")
                                        print("[GATE] Closing gate")

                                    last_saved_plate = most_common
                                    last_entry_time = current_time
                                else:
                                    print(
                                        "[SKIPPED] Duplicate plate within cooldown period"
                                    )

                                plate_buffer.clear()

                # Display annotated frame
                annotated_frame = results[0].plot()
                cv2.putText(
                    annotated_frame,
                    f"Detection: {detection_time:.2f}s",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
            else:
                annotated_frame = frame

            cv2.imshow("Webcam Feed", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[SYSTEM] Shutting down...")
    finally:
        cap.release()
        if arduino:
            arduino.close()
        cv2.destroyAllWindows()
        print("[SYSTEM] Cleanup complete")


if __name__ == "__main__":
    main()
