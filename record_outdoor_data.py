import pyrealsense2 as rs
import os
import time
import cv2
import numpy as np
import serial
import json
import threading
import csv

class GNSSRecorder(threading.Thread):
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, csv_path='gnss_data.csv'):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.csv_path = csv_path
        self.running = True
        self.serial_conn = None
        self.daemon = True
        self.has_fix = False
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'time', 'numSatellites', 'fix', 'latitude', 'longitude', 'altitude', 'usec', 'speed_ms', 'heading', 'pdop', 'hdop', 'vdop'])
        except Exception as e:
            print(f"Warning: Failed to open GNSS serial port {self.port}: {e}")
            
    def run(self):
        if not self.serial_conn:
            return
        
        while self.running:
            try:
                line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                        
                    # Ignore status messages or update state
                    if "status" in data:
                        continue
                        
                    lat = data.get("latitude")
                    lon = data.get("longitude")
                    alt = data.get("altitude")
                    
                    # Strictly require valid coordinates before considering it a true "fix" for camera recording
                    self.has_fix = data.get("fix", False) and (lat is not None) and (lon is not None) and (alt is not None)
                    
                    date_time = data.get("time", "") or ""
                    date_str = date_time.split(" ")[0] if " " in date_time else ""
                    time_str = date_time.split(" ")[1] if " " in date_time else date_time
                    
                    usec = data.get("usec")
                    speed = data.get("speed_ms")
                    heading = data.get("heading")
                    pdop = data.get("pdop")
                    hdop = data.get("hdop")
                    vdop = data.get("vdop")
                    
                    row = [
                        date_str,
                        time_str,
                        data.get("numSatellites", 0),
                        self.has_fix,
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
                    
                    with open(self.csv_path, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                        
                    # Print the data to terminal so the user can see it live
                    print(f"[GNSS] Time: {time_str} | Fix: {self.has_fix} | Sats: {data.get('numSatellites', 0)} | Lat: {lat} | Lon: {lon} | Alt: {alt}")
            except Exception:
                pass
                
    def stop(self):
        self.running = False
        if self.serial_conn:
            self.serial_conn.close()

def main():
    # Define the directory where the data will be saved (./data)
    data_dir = os.path.join(os.getcwd(), "data")
    
    # Ensure the data directory exists
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Find the next available file number to avoid overwriting
    base_name = "outdoor_dataset"
    counter = 1
    while True:
        bag_name = f"{base_name}_{counter}.bag"
        csv_name = f"{base_name}_{counter}.csv"
        bag_path = os.path.join(data_dir, bag_name)
        csv_path = os.path.join(data_dir, csv_name)
        if not os.path.exists(bag_path) and not os.path.exists(csv_path):
            break
        counter += 1

    # Initialize the pipeline and configuration
    pipeline = rs.pipeline()
    config = rs.config()

    # Enable recording to the bag file
    config.enable_record_to_file(bag_path)

    # Configure streams: Color, Depth, and Infrared (Left/Right)
    # Note: Max resolution usually differs between color and depth sensors.
    # 1920x1080 is typical max for Color. 1280x720 (or 1280x800) is typical max for Depth/IR.
    color_width, color_height = 1920, 1080
    depth_width, depth_height = 1280, 720
    fps = 30

    config.enable_stream(rs.stream.color, color_width, color_height, rs.format.bgr8, fps)
    config.enable_stream(rs.stream.depth, depth_width, depth_height, rs.format.z16, fps)
    config.enable_stream(rs.stream.infrared, 1, depth_width, depth_height, rs.format.y8, fps)
    config.enable_stream(rs.stream.infrared, 2, depth_width, depth_height, rs.format.y8, fps)

    print(f"Initializing stream. Recording will be saved to: {bag_path}")
    print(f"Initializing GNSS. Recording will be saved to: {csv_path}")

    # Set the GNSS serial port
    serial_port = "/dev/ttyUSB0"

    # Start GNSS recording
    gnss_recorder = GNSSRecorder(serial_port, 115200, csv_path)
    gnss_recorder.start()

    try:
        # Start the pipeline
        pipeline_profile = pipeline.start(config)

        # Get the device and the depth sensor to configure hardware settings
        device = pipeline_profile.get_device()
        
        # Pause the recording initially until we get a GPS fix
        recorder = device.as_recorder()
        recorder.pause()
        is_recording = False
        total_record_time = 0.0
        current_session_start = None
        
        depth_sensor = device.first_depth_sensor()

        # 1. Disable the IR emitter for outdoor environments
        if depth_sensor.supports(rs.option.emitter_enabled):
            depth_sensor.set_option(rs.option.emitter_enabled, 0)
            print("IR emitter disabled.")

        # 2. Enable auto-exposure
        if depth_sensor.supports(rs.option.enable_auto_exposure):
            depth_sensor.set_option(rs.option.enable_auto_exposure, 1)
            print("Auto-exposure enabled.")

        # 4. Apply an Align object to align depth frames to color frames
        align_to = rs.stream.color
        align = rs.align(align_to)

        print("Waiting for GNSS Fix... Press 'q' or 'ESC' on the window to stop.")

        # Continuously record streams
        while True:
            # Check GNSS fix status and toggle recording
            if gnss_recorder.has_fix and not is_recording:
                recorder.resume()
                is_recording = True
                current_session_start = time.time()
                print("\nSatellite fix obtained. Recording started!")
            elif not gnss_recorder.has_fix and is_recording:
                recorder.pause()
                is_recording = False
                if current_session_start:
                    total_record_time += time.time() - current_session_start
                    current_session_start = None
                print("\nSatellite fix lost. Recording paused!")

            # Wait for the next set of frames
            frames = pipeline.wait_for_frames()
            
            # Align the depth frames to the color frames
            aligned_frames = align.process(frames)
            
            # Get the color frame for visualization
            color_frame = aligned_frames.get_color_frame()
            if color_frame:
                color_image = np.asanyarray(color_frame.get_data())
                # Resize for display purposes to fit on most screens
                display_image = cv2.resize(color_image, (960, 540))
                
                # Add text overlay indicating status
                if is_recording:
                    elapsed = total_record_time + (time.time() - current_session_start)
                    mins, secs = divmod(int(elapsed), 60)
                    status_text = f"Recording (GNSS Fix) - {mins:02d}:{secs:02d}"
                    color = (0, 255, 0)
                else:
                    status_text = "Waiting for GNSS Fix..."
                    color = (0, 0, 255)
                cv2.putText(display_image, status_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                
                cv2.imshow('Realtime Stream (Color)', display_image)
            
            # Update the cv2 window and allow manual exit with 'q' or 'ESC'
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q') or key == 27:
                print("\nRecording stopped manually by user.")
                break

    except KeyboardInterrupt:
        print("\nRecording interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"\nAn error occurred during recording: {e}")
    finally:
        # Cleanly stop the pipeline and release resources
        gnss_recorder.stop()
        gnss_recorder.join(timeout=2.0)
        try:
            pipeline.stop()
        except RuntimeError:
            pass # pipeline was never started
        cv2.destroyAllWindows()
        print(f"=========================================")
        print(f"Recording finished! Data successfully saved to {bag_path} and {csv_path}")
        print(f"=========================================")

if __name__ == "__main__":
    main()
