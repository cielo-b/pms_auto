-- Create vehicle_logs table
CREATE TABLE IF NOT EXISTS vehicle_logs (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    in_time TIMESTAMP NOT NULL,
    out_time TIMESTAMP,
    status INTEGER DEFAULT 0,  -- 0: unpaid, 1: paid
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create unauthorized_exits table
CREATE TABLE IF NOT EXISTS unauthorized_exits (
    id SERIAL PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
); 