import os
import time
import serial
import json
import csv
import signal
import sys

# Global flag to control the recording loop
running = True

def signal_handler(sig, frame):
    global running
    print('\nStopping GNSS recording gracefully...')
    running = False

def main():
    global running
    
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal_handler)
    
    # Define the directory where the data will be saved (./data_gnss_only)
    data_dir = os.path.join(os.getcwd(), "data_gnss_only")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Find the next available file number to avoid overwriting
    base_name = "gnss_only_dataset"
    counter = 1
    while True:
        csv_name = f"{base_name}_{counter}.csv"
        csv_path = os.path.join(data_dir, csv_name)
        if not os.path.exists(csv_path):
            break
        counter += 1

    # Default Linux serial port for Spresense GNSS
    serial_port = "/dev/ttyUSB0"
    baudrate = 115200

    print(f"Initializing GNSS on {serial_port} at {baudrate} baud.")
    print(f"Data will be saved to: {csv_path}")
    print("Press Ctrl+C to stop recording.\n")

    try:
        serial_conn = serial.Serial(serial_port, baudrate, timeout=1)
    except Exception as e:
        print(f"Error: Failed to open GNSS serial port {serial_port}: {e}")
        return

    # Write the CSV header
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'time', 'numSatellites', 'fix', 'latitude', 'longitude', 'altitude', 'usec', 'speed_ms', 'heading', 'pdop', 'hdop', 'vdop'])

    has_fix = False

    # Main continuous recording loop
    while running:
        try:
            # Read line from the serial port
            line = serial_conn.readline().decode('utf-8', errors='ignore').strip()
            if line:
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                    
                # Ignore status or startup messages
                if "status" in data:
                    continue
                    
                lat = data.get("latitude")
                lon = data.get("longitude")
                alt = data.get("altitude")
                
                # Strictly require valid coordinates before considering it a true "fix"
                has_fix = data.get("fix", False) and (lat is not None) and (lon is not None) and (alt is not None)
                
                date_time = data.get("time", "") or ""
                date_str = date_time.split(" ")[0] if " " in date_time else ""
                time_str = date_time.split(" ")[1] if " " in date_time else date_time
                
                usec = data.get("usec")
                speed = data.get("speed_ms")
                heading = data.get("heading")
                pdop = data.get("pdop")
                hdop = data.get("hdop")
                vdop = data.get("vdop")
                
                # Prepare row data, replacing None values with empty strings
                row = [
                    date_str,
                    time_str,
                    data.get("numSatellites", 0),
                    has_fix,
                    lat if lat is not None else "",
                    lon if lon is not None else "",
                    alt if alt is not None else "",
                    usec if usec is not None else "",
                    speed if speed is not None else "",
                    heading if heading is not None else "",
                    pdop if pdop is not None else "",
                    hdop if hdop is not None else "",
                    vdop if vdop is not None else ""
                ]
                
                # Append row to CSV
                with open(csv_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                    
                # Print the data to terminal so the user can see it live
                print(f"[GNSS] Time: {time_str} | Fix: {has_fix} | Sats: {data.get('numSatellites', 0)} | Lat: {lat} | Lon: {lon} | Alt: {alt}")
        
        except Exception:
            pass # Catch transient errors but keep the loop alive

    # Clean up when Ctrl+C is pressed
    serial_conn.close()
    print(f"=========================================")
    print(f"GNSS Recording finished! Data successfully saved to {csv_path}")
    print(f"=========================================")

if __name__ == "__main__":
    main()
