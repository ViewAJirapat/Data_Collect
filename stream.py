import pyrealsense2 as rs
import numpy as np
import cv2

def main():
    # Configure depth and color streams
    pipeline = rs.pipeline()
    config = rs.config()

    # RealSense D415 stream configuration (640x480 at 30 fps)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    print("Starting the Intel RealSense D415 camera stream...")
    print("Press 'q' or 'ESC' to stop the stream.")

    try:
        # Start streaming
        pipeline.start(config)
    except RuntimeError as e:
        print(f"Error starting pipeline: {e}")
        print("Please make sure the Intel RealSense camera is connected.")
        return
    
    # Create an align object to align depth frames to color frames
    align_to = rs.stream.color
    align = rs.align(align_to)

    try:
        while True:
            # Wait for a coherent pair of frames: depth and color
            frames = pipeline.wait_for_frames()
            
            # Align the depth frame to color frame
            aligned_frames = align.process(frames)
            
            # Get aligned frames
            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()
            
            if not depth_frame or not color_frame:
                continue

            # Convert images to numpy arrays
            depth_image = np.asanyarray(depth_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            # Apply colormap on depth image (image must be converted to 8-bit per pixel first)
            depth_colormap = cv2.applyColorMap(cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET)

            # Stack both images horizontally for 2-column visualization
            images = np.hstack((color_image, depth_colormap))

            # Show images
            cv2.namedWindow('RealSense Stream (Color & Depth)', cv2.WINDOW_AUTOSIZE)
            cv2.imshow('RealSense Stream (Color & Depth)', images)
            
            # Press 'q' or 'ESC' to close the image window
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q') or key == 27:
                cv2.destroyAllWindows()
                break

    finally:
        # Stop streaming
        pipeline.stop()
        print("Camera stream stopped.")

if __name__ == "__main__":
    main()
