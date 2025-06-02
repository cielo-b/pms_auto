import time
from datetime import datetime
import csv
import os
import random

class RFIDSimulator:
    """Simulates RFID card operations without physical hardware"""
    def __init__(self):
        self.simulated_cards = {}  # Stores card data in memory
        
    def wait_for_card(self, timeout):
        """Simulates waiting for a card to be presented"""
        print("\n[Simulation] Present a card:")
        print("1. Use existing test card")
        print("2. Create new test card")
        print("3. Cancel (timeout)")
        
        choice = input("Select option (1-3): ").strip()
        if choice == "1":
            if not self.simulated_cards:
                print("No cards registered yet")
                return None
            print("\nAvailable cards:")
            for i, card_id in enumerate(self.simulated_cards.keys(), 1):
                print(f"{i}. {card_id}")
            card_choice = input("Select card (1-{}): ".format(len(self.simulated_cards))).strip()
            try:
                card_index = int(card_choice) - 1
                return list(self.simulated_cards.keys())[card_index]
            except (ValueError, IndexError):
                print("Invalid selection")
                return None
        elif choice == "2":
            card_id = "CARD-" + str(random.randint(1000, 9999))
            plate = "ABC-" + str(random.randint(100, 999))
            balance = round(random.uniform(50, 500), 2)
            self.simulated_cards[card_id] = {
                "Plate Number": plate,
                "Balance": balance
            }
            print(f"Created new test card: {card_id}")
            print(f"Plate: {plate}, Balance: {balance}")
            return card_id
        else:
            print("No card detected (simulated timeout)")
            return None
    
    def write_rfid(self, card_id, plate_number, balance):
        """Simulates writing data to an RFID card"""
        if card_id in self.simulated_cards:
            self.simulated_cards[card_id] = {
                "Plate Number": plate_number,
                "Balance": balance
            }
            return True
        return False
    
    def read_rfid(self, card_id):
        """Simulates reading data from an RFID card"""
        return self.simulated_cards.get(card_id, None)


class PaymentProcessor:
    def __init__(self):
        self.rfid = RFIDSimulator()  # Using the simulator instead of real RFIDManager
        self.cards_csv = "./database/cards.csv"
        self.plates_csv = "./database/plates_log.csv"
        self.parking_rate = 200  # 200 per hour
        self.initialize_files()
        
    def initialize_files(self):
        """Initialize required files if they don't exist"""
        os.makedirs("./database", exist_ok=True)
        
        # Initialize cards.csv
        if not os.path.exists(self.cards_csv):
            with open(self.cards_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Card ID", "Plate Number", "Balance"])
        
        # Initialize plates_log.csv
        if not os.path.exists(self.plates_csv):
            with open(self.plates_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Plate Number", "Payment Status", "In time", "Out time"])

    def register_card(self):
        """Register a new card"""
        print("\n[Register Card] Waiting for card...")
        card_id = self.rfid.wait_for_card(10)
        if not card_id:
            print("No card detected within time limit")
            return

        # Check if card is already registered
        if self.get_card_data(card_id):
            print("This card is already registered!")
            return

        print("\nNew card detected! Card ID:", card_id)
        plate_number = input("Enter vehicle plate number: ").strip().upper()
        while True:
            try:
                balance = float(input("Enter initial balance: "))
                break
            except ValueError:
                print("Please enter a valid number")

        if self.rfid.write_rfid(card_id, plate_number, balance):
            self.log_transaction(card_id, plate_number, balance)
            print("\nCard registered successfully!")
            print(f"Card ID: {card_id}")
            print(f"Plate: {plate_number}")
            print(f"Initial Balance: {balance}")
        else:
            print("Failed to register card")

    def topup_balance(self):
        """Top up card balance"""
        print("\n[Top Up] Waiting for card...")
        card_id = self.rfid.wait_for_card(10)
        if not card_id:
            print("No card detected within time limit")
            return

        card_data = self.get_card_data(card_id)
        if not card_data:
            print("Card not registered. Please register first.")
            return

        print(f"\nCard ID: {card_id}")
        print(f"Current Balance: {card_data['Balance']}")
        try:
            amount = float(input("Enter top-up amount: "))
            new_balance = float(card_data["Balance"]) + amount

            if self.rfid.write_rfid(card_id, card_data["Plate Number"], new_balance):
                self.log_transaction(card_id, card_data["Plate Number"], new_balance)
                print(f"Top-up successful! New balance: {new_balance}")
            else:
                print("Failed to update card")
        except ValueError:
            print("Invalid amount entered")

    def check_card(self):
        """Check card details"""
        print("\n[Check Card] Waiting for card...")
        card_id = self.rfid.wait_for_card(10)
        if not card_id:
            print("No card detected within time limit")
            return

        card_data = self.get_card_data(card_id)
        if card_data:
            print("\nCard Details:")
            print(f"Card ID: {card_id}")
            print(f"Plate: {card_data['Plate Number']}")
            print(f"Balance: {card_data['Balance']}")
        else:
            print("Card not registered")

    def process_exit(self):
        """Process parking exit and payment (without updating Out time)"""
        print("\n[Process Exit] Waiting for card...")
        card_id = self.rfid.wait_for_card(10)
        if not card_id:
            print("No card detected within time limit")
            return

        card_data = self.get_card_data(card_id)
        if not card_data:
            print("Card not registered")
            return

        plate_number = card_data["Plate Number"]
        balance = float(card_data["Balance"])

        # Simulate finding an active parking session
        print(f"\nLooking for active parking session for plate: {plate_number}")
        
        # Create a simulated entry if none exists
        entry = None
        try:
            with open(self.plates_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reversed(list(reader)):
                    if row["Plate Number"] == plate_number and not row["Out time"]:
                        entry = row
                        break
        except Exception as e:
            print(f"[CSV READ ERROR] {str(e)}")
            return

        if not entry:
            print("No active parking session found. Creating a simulated one...")
            entry_time = datetime.now() - timedelta(minutes=random.randint(30, 180))
            entry = {
                "Plate Number": plate_number,
                "Payment Status": "0",
                "In time": entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                "Out time": ""
            }
            # Add to log
            with open(self.plates_csv, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=entry.keys())
                writer.writerow(entry)
            print(f"Created simulated entry at {entry['In time']}")

        # Calculate fee
        current_time = datetime.now()
        entry_time = datetime.strptime(entry["In time"], "%Y-%m-%d %H:%M:%S")
        duration_hours = (current_time - entry_time).total_seconds() / 3600
        fee = duration_hours * self.parking_rate
        fee = round(fee, 2)

        print(f"\nParking Duration: {duration_hours*60:.1f} minutes")
        print(f"Parking Fee: {fee:.2f}")
        print(f"Current Balance: {balance:.2f}")

        if balance >= fee:
            new_balance = round(balance - fee, 2)
            if self.rfid.write_rfid(card_id, plate_number, new_balance):
                # Update cards.csv with new balance
                self.log_transaction(card_id, plate_number, new_balance)

                # Update plates_log.csv with Payment Status=1 (do NOT update Out time)
                try:
                    rows = []
                    with open(self.plates_csv, "r") as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                    for row in rows:
                        if (
                            row["Plate Number"] == plate_number
                            and row["In time"] == entry["In time"]
                        ):
                            row["Payment Status"] = "1"
                    with open(self.plates_csv, "w", newline="") as f:
                        writer = csv.DictWriter(
                            f,
                            fieldnames=[
                                "Plate Number",
                                "Payment Status",
                                "In time",
                                "Out time",
                            ],
                        )
                        writer.writeheader()
                        writer.writerows(rows)
                except Exception as e:
                    print(f"[CSV WRITE ERROR] {str(e)}")
                    return

                print("\nPayment successful!")
                print(f"New Balance: {new_balance:.2f}")
            else:
                print("Failed to update card balance")
        else:
            print(f"Insufficient balance (Need: {fee:.2f}, Has: {balance:.2f})")

    def get_card_data(self, card_id):
        """Retrieve card data from cards.csv and simulated cards"""
        # First check the simulated cards
        sim_data = self.rfid.read_rfid(card_id)
        if sim_data:
            return sim_data
        
        # Then check the CSV file
        try:
            with open(self.cards_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["Card ID"] == card_id:
                        return row
        except Exception as e:
            print(f"[CSV READ ERROR] {str(e)}")
        return None

    def log_transaction(self, card_id, plate_number, balance):
        """Update or add card data in cards.csv"""
        try:
            rows = []
            updated = False
            if os.path.exists(self.cards_csv):
                with open(self.cards_csv, "r") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    for row in rows:
                        if row["Card ID"] == card_id:
                            row["Plate Number"] = plate_number
                            row["Balance"] = str(balance)
                            updated = True
                            break
            if not updated:
                rows.append(
                    {
                        "Card ID": card_id,
                        "Plate Number": plate_number,
                        "Balance": str(balance),
                    }
                )
            with open(self.cards_csv, "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["Card ID", "Plate Number", "Balance"]
                )
                writer.writeheader()
                writer.writerows(rows)
            return True
        except Exception as e:
            print(f"[CSV WRITE ERROR] {str(e)}")
            return False

    def show_menu(self):
        """Display main menu"""
        print("\n=== Parking Management System (Simulation) ===")
        print("1. Register New Card")
        print("2. Top Up Balance")
        print("3. Check Card Details")
        print("4. Process Exit")
        print("5. Exit System")

    def run(self):
        """Main system loop"""
        while True:
            self.show_menu()
            try:
                choice = input("Select option: ").strip()
                if choice == "1":
                    self.register_card()
                elif choice == "2":
                    self.topup_balance()
                elif choice == "3":
                    self.check_card()
                elif choice == "4":
                    self.process_exit()
                elif choice == "5":
                    print("Goodbye!")
                    break
                else:
                    print("Invalid option")
                time.sleep(1)
            except KeyboardInterrupt:
                print("\nSystem shutting down...")
                break


if __name__ == "__main__":
    processor = PaymentProcessor()
    processor.run()