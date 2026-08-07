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
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'time', 'numSatellites', 'fix', 'latitude', 'longitude', 'altitude'])
        except Exception as e:
            print(f"Warning: Failed to open GNSS serial port {self.port}: {e}")
            
    def run(self):
        if not self.serial_conn:
            return
        
        while self.running:
            try:
                line = self.serial_conn.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    data = json.loads(line)
                    date_time = data.get("time", "")
                    date_str = date_time.split(" ")[0] if " " in date_time else ""
                    time_str = date_time.split(" ")[1] if " " in date_time else date_time
                    
                    row = [
                        date_str,
                        time_str,
                        data.get("numSatellites", 0),
                        data.get("fix", False),
                        data.get("latitude", 0.0),
                        data.get("longitude", 0.0),
                        data.get("altitude", 0.0)
                    ]
                    
                    with open(self.csv_path, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
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

    # Set the appropriate serial port for your OS
    import platform
    if platform.system() == "Windows":
        serial_port = "COM3"  # <-- CHANGE THIS TO YOUR SPRESENSE COM PORT ON WINDOWS
    else:
        serial_port = "/dev/ttyUSB0"

    # Start GNSS recording
    gnss_recorder = GNSSRecorder(serial_port, 115200, csv_path)
    gnss_recorder.start()

    try:
        # Start the pipeline
        pipeline_profile = pipeline.start(config)

        # Get the device and the depth sensor to configure hardware settings
        device = pipeline_profile.get_device()
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

        print("Recording started. Press 'q' or 'ESC' on the window to stop.")

        # Continuously record streams
        while True:

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
        pipeline.stop()
        cv2.destroyAllWindows()
        print(f"=========================================")
        print(f"Recording finished! Data successfully saved to {bag_path} and {csv_path}")
        print(f"=========================================")

if __name__ == "__main__":
    main()
