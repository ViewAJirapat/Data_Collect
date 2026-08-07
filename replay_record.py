import pyrealsense2 as rs
import numpy as np
import cv2
import os

import glob

def main():
    # Define the directory where the bag file is located
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Find all recorded bag files
    bag_files = glob.glob(os.path.join(output_dir + "/data", 'outdoor_dataset_*.bag'))
    
    if not bag_files:
        print("Error: No bag files found in the directory.")
        print("Please ensure you have recorded data first using record_outdoor_data.py")
        return

    # Sort files by creation time and pick the most recent one
    bag_files.sort(key=os.path.getctime, reverse=True)
    bag_path = bag_files[0]

    # Setup the pipeline
    pipeline = rs.pipeline()
    config = rs.config()

    # Instruct the config to load the device from the recorded bag file
    # Setting repeat_playback=True will loop the recording indefinitely
    rs.config.enable_device_from_file(config, bag_path, repeat_playback=True)

    print(f"Starting playback from: {bag_path}")
    print("Press 'q' or 'ESC' on the video window to stop playback.")

    # Start streaming from the file
    pipeline.start(config)

    # Create an alignment object to align the depth frames to color frames
    align_to = rs.stream.color
    align = rs.align(align_to)

    try:
        while True:
            # Wait for a coherent set of frames
            frames = pipeline.wait_for_frames()

            # Align the depth frame to the color frame
            aligned_frames = align.process(frames)

            # Get aligned frames
            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()

            if not depth_frame or not color_frame:
                continue

            # Convert images to numpy arrays for OpenCV
            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
            # Scaling alpha to 0.03 is a standard visualization trick for 16-bit depth
            depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

            # Resize images to 480p (848x480) for display
            color_image = cv2.resize(color_image, (848, 480))
            depth_colormap = cv2.resize(depth_colormap, (848, 480))

            # Stack both images horizontally for visualization
            images = np.hstack((color_image, depth_colormap))

            # Display the visualization
            cv2.namedWindow('RealSense Playback (Color & Depth)', cv2.WINDOW_AUTOSIZE)
            cv2.imshow('RealSense Playback (Color & Depth)', images)

            # Wait for a key press (1ms delay allows the frame to render)
            key = cv2.waitKey(1)
            
            # Press 'q' or 'ESC' to close the image window
            if key & 0xFF == ord('q') or key == 27:
                cv2.destroyAllWindows()
                break

    finally:
        # Clean up and stop the pipeline
        pipeline.stop()
        print("Playback finished.")

if __name__ == "__main__":
    main()
