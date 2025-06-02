-- Create database
CREATE DATABASE parking_system;

-- Connect to the database
\c parking_system;

-- Create vehicle_logs table
CREATE TABLE vehicle_logs (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    in_time TIMESTAMP NOT NULL,
    out_time TIMESTAMP,
    status INTEGER DEFAULT 0, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unauthorized_exits table
CREATE TABLE unauthorized_exits (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_vehicle_logs_plate_number ON vehicle_logs(plate_number);
CREATE INDEX idx_vehicle_logs_in_time ON vehicle_logs(in_time);
CREATE INDEX idx_vehicle_logs_out_time ON vehicle_logs(out_time);
CREATE INDEX idx_unauthorized_exits_timestamp ON unauthorized_exits(timestamp);
CREATE INDEX idx_unauthorized_exits_plate_number ON unauthorized_exits(plate_number); 