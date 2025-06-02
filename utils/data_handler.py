import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
import json
import os
from urllib.parse import quote_plus

def load_db_config():
    """Load database configuration from config file"""
    try:
        with open('config/database.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading database configuration: {str(e)}")
        return None

def get_db_connection():
    """Create database connection"""
    config = load_db_config()
    if config is None:
        return None
    
    try:
        password = quote_plus(config['password'])
        connection_string = f"postgresql://{config['user']}:{password}@{config['host']}:{config['port']}/{config['database']}"
        engine = create_engine(connection_string)
        return engine
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return None

def save_vehicle_entry(plate_number, in_time=None, out_time=None, is_unauthorized=False):
    """
    Save vehicle entry to both CSV and database
    
    Args:
        plate_number (str): Vehicle plate number
        in_time (datetime, optional): Entry time. Defaults to current time if None
        out_time (datetime, optional): Exit time. Defaults to None
        is_unauthorized (bool, optional): Whether this is an unauthorized exit. Defaults to False
    """
    try:
        # Set default in_time to current time if not provided
        if in_time is None:
            in_time = datetime.now()
        
        # Save to CSV
        # if is_unauthorized:
        #     csv_path = "database/unauthorized_exits.csv"
        #     data = {
        #         'Plate Number': [plate_number],
        #         'Timestamp': [in_time]
        #     }
        # else:
        #     csv_path = "database/plates_log.csv"
        #     data = {
        #         'Plate Number': [plate_number],
        #         'In time': [in_time],
        #         'Out time': [out_time]
        #     }
        
        # # Create directory if it doesn't exist
        # os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # # Append to CSV
        # df = pd.DataFrame(data)
        # if os.path.exists(csv_path):
        #     df.to_csv(csv_path, mode='a', header=False, index=False)
        # else:
        #     df.to_csv(csv_path, index=False)
        
        # Save to database
        engine = get_db_connection()
        if engine is not None:
            if is_unauthorized:
                query = text("""
                    INSERT INTO unauthorized_exits (plate_number, timestamp)
                    VALUES (:plate_number, :timestamp)
                """)
                with engine.connect() as conn:
                    conn.execute(query, {
                        "plate_number": plate_number,
                        "timestamp": in_time
                    })
                    conn.commit()
            else:
                query = text("""
                    INSERT INTO vehicle_logs (plate_number, in_time, out_time)
                    VALUES (:plate_number, :in_time, :out_time)
                """)
                with engine.connect() as conn:
                    conn.execute(query, {
                        "plate_number": plate_number,
                        "in_time": in_time,
                        "out_time": out_time
                    })
                    conn.commit()
        
        return True
    except Exception as e:
        print(f"Error saving vehicle entry: {str(e)}")
        return False

def update_vehicle_exit(plate_number, out_time=None):
    """
    Update vehicle exit time in both CSV and database
    
    Args:
        plate_number (str): Vehicle plate number
        out_time (datetime, optional): Exit time. Defaults to current time if None
    """
    try:
        if out_time is None:
            out_time = datetime.now()
        
        # # Update CSV
        # csv_path = "database/plates_log.csv"
        # if os.path.exists(csv_path):
        #     df = pd.read_csv(csv_path)
        #     mask = (df['Plate Number'] == plate_number) & (pd.isna(df['Out time']) | (df['Out time'] == ''))
        #     if mask.any():
        #         df.loc[mask, 'Out time'] = out_time
        #         df.to_csv(csv_path, index=False)
        
        # Update database
        engine = get_db_connection()
        if engine is not None:
            query = text("""
                UPDATE vehicle_logs 
                SET out_time = :out_time
                WHERE plate_number = :plate_number 
                AND out_time IS NULL
            """)
            with engine.connect() as conn:
                conn.execute(query, {
                    "plate_number": plate_number,
                    "out_time": out_time
                })
                conn.commit()
        
        return True
    except Exception as e:
        print(f"Error updating vehicle exit: {str(e)}")
        return False 