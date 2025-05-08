import serial
import serial.tools.list_ports
from datetime import datetime
import csv
import time
import os
import random


class RFIDManager:
    def __init__(self):
        self.arduino = self.connect_arduino()
        self.parking_rate = 200  # 200 per hour
        self.parking_log = "./database/parking_transactions.csv"
        self.initialize_log()

    def initialize_log(self):
        """Initialize the CSV log file if it doesn't exist"""
        if not os.path.exists(self.parking_log):
            with open(self.parking_log, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "Card ID",
                        "Plate Number",
                        "Balance",
                        "Last Top-up",
                        "Last Entry",
                        "Last Exit",
                    ]
                )

    def connect_arduino(self):
        """Connect to Arduino via serial port"""
        try:
            ports = list(serial.tools.list_ports.comports())
            for port in ports:
                if "ttyUSB" in port.device or "ttyACM" in port.device:
                    try:
                        arduino = serial.Serial(
                            port.device, 9600, timeout=10
                        )  # Increased timeout
                        time.sleep(2)  # Wait for connection
                        print(f"[CONNECTED] Arduino on {port.device}")
                        return arduino
                    except serial.SerialException as e:
                        print(f"[ERROR] Failed to connect to {port.device}: {str(e)}")
                        continue
        except Exception as e:
            print(f"[PORT SCAN ERROR] {str(e)}")
        print("[WARNING] Running in simulation mode")
        return None

    def wait_for_card(self, timeout=15):
        """Wait for card to be detected with timeout"""
        print(f"\nPlease place your card on the reader (waiting {timeout} seconds)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            card_id = self.read_rfid()
            if card_id and card_id != "NO_CARD" and len(card_id) >= 8:
                return card_id
            time.sleep(0.5)  # Polling interval
        return None

    def read_rfid(self):
        """Read RFID card data"""
        if not self.arduino:
            return "SIM_" + str(random.randint(1000, 9999))

        try:
            self.arduino.reset_input_buffer()  # Reset buffer once
            self.arduino.write(b"READ\n")
            start_time = time.time()
            response = ""
            while time.time() - start_time < 10:  # Wait up to 10 seconds
                if self.arduino.in_waiting > 0:
                    print(f"[DEBUG] Raw Response: '{response}'")
                    response += self.arduino.readline().decode().strip()
                    if response.endswith("<END>"):
                        response = response.replace("<END>", "")
                        if response and response != "NO_CARD" and len(response) >= 8:
                            print(f"[DEBUG] Valid Card ID: '{response}'")
                            return response
                        elif response == "NO_CARD":
                            return response
                    elif response and response != "NO_CARD" and len(response) >= 8:
                        print(f"[DEBUG] Partial Valid Card ID: '{response}'")
                        return response  # Accept partial valid ID
                time.sleep(0.1)  # Small delay to avoid CPU overload
            print(f"[READ ERROR] No valid card ID after 10 seconds")
            return None
        except Exception as e:
            print(f"[READ ERROR] {str(e)}")
            return None

    def write_rfid(self, card_id, plate_number, balance):
        """Write data to RFID card"""
        if not self.arduino:
            print("[SIMULATION] Write operation simulated")
            return True

        try:
            self.arduino.reset_input_buffer()  # Reset buffer once
            data_str = f"WRITE,{card_id},{plate_number},{balance}\n"
            print(f"[DEBUG] Sending write command: '{data_str.strip()}'")
            self.arduino.write(data_str.encode())
            start_time = time.time()
            response = ""
            while time.time() - start_time < 12:  # Wait up to 12 seconds
                if self.arduino.in_waiting > 0:
                    response += self.arduino.readline().decode().strip()
                    print(f"[DEBUG] Raw Write Response: '{response}'")
                    if response.endswith("<END>"):
                        response = response.replace("<END>", "")
                        if response == "WRITE_SUCCESS":
                            print(f"[DEBUG] Write successful")
                            return True
                        elif response in [
                            "NO_CARD",
                            "CARD_MISMATCH",
                            "AUTH_FAIL",
                            "WRITE_FAIL_PLATE",
                            "WRITE_FAIL_BALANCE",
                        ]:
                            print(f"[WRITE ERROR] Arduino reported: {response}")
                            return False
                time.sleep(0.1)  # Small delay
            print("[WRITE ERROR] No valid response after 12 seconds")
            return False
        except Exception as e:
            print(f"[WRITE ERROR] {str(e)}")
            return False

    def get_card_data(self, card_id):
        """Retrieve card data from log file"""
        try:
            with open(self.parking_log, "r") as f:
                reader = csv.DictReader(f)
                for row in reversed(list(reader)):
                    if row["Card ID"] == card_id:
                        return row
        except Exception as e:
            print(f"[LOG READ ERROR] {str(e)}")
        return None

    def log_transaction(self, card_id, plate_number, balance, action):
        """Log transaction to CSV file"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.parking_log, "a", newline="") as f:
                writer = csv.writer(f)
                if action == "entry":
                    writer.writerow([card_id, plate_number, balance, "", timestamp, ""])
                elif action == "exit":
                    writer.writerow([card_id, plate_number, balance, "", "", timestamp])
                elif action == "topup":
                    writer.writerow([card_id, plate_number, balance, timestamp, "", ""])
            return True
        except Exception as e:
            print(f"[LOG WRITE ERROR] {str(e)}")
            return False

    def calculate_fee(self, entry_time, exit_time):
        """Calculate parking fee based on duration"""
        duration_hours = (exit_time - entry_time).total_seconds() / 3600
        return round(duration_hours * self.parking_rate, 2)
