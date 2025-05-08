from rfid_manager import RFIDManager
import time
from datetime import datetime
import csv
import os


class PaymentProcessor:
    def __init__(self):
        self.rfid = RFIDManager()
        self.cards_csv = "./database/cards.csv"
        self.plates_csv = "plates_log.csv"  # From car_entry.py
        self.parking_rate = 200  # 200 per hour
        self.initialize_cards_csv()

    def initialize_cards_csv(self):
        """Initialize cards.csv if it doesn't exist"""
        if not os.path.exists(self.cards_csv):
            with open(self.cards_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Card ID", "Plate Number", "Balance"])

    def register_card(self):
        """Register a new card"""
        print("\nWaiting for card...")
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
        print("\nWaiting for card...")
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
        print("\nWaiting for card...")
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
        """Process parking exit and payment"""
        print("\nWaiting for card...")
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

        # Find the latest entry in plates_log.csv with no Out time
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
            print("No active parking session for this plate")
            return

        # Calculate fee
        current_time = datetime.now()
        entry_time = datetime.strptime(entry["In time"], "%Y-%m-%d %H:%M:%S")
        fee = ((current_time - entry_time).total_seconds() / 3600) * self.parking_rate
        fee = round(fee, 2)

        if balance >= fee:
            new_balance = round(balance - fee, 2)
            if self.rfid.write_rfid(card_id, plate_number, new_balance):
                # Update cards.csv with new balance
                self.log_transaction(card_id, plate_number, new_balance)

                # Update plates_log.csv with Payment Status=1 and Out time
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
                            row["Out time"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
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
                print(
                    f"Duration: {(current_time - entry_time).total_seconds() / 60:.1f} min"
                )
                print(f"Fee: {fee:.2f}")
                print(f"New Balance: {new_balance:.2f}")
            else:
                print("Failed to update card balance")
        else:
            print(f"Insufficient balance (Need: {fee:.2f}, Has: {balance:.2f})")

    def get_card_data(self, card_id):
        """Retrieve card data from cards.csv"""
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
        print("\n=== Parking Management System ===")
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
