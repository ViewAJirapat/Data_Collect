import pyrealsense2 as rs
import numpy as np
import open3d as o3d

def main():
    # 1. Setup the pipeline and configure streams
    pipeline = rs.pipeline()
    config = rs.config()
    
    # Configure depth stream (D415 typical resolution)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

    try:
        # Start the pipeline
        profile = pipeline.start(config)
        
        # 2. Configure for Passive Stereo
        # Get the device and its depth sensor
        device = profile.get_device()
        depth_sensor = device.first_depth_sensor()
        
        # Disable the IR emitter to use passive stereo only
        if depth_sensor.supports(rs.option.emitter_enabled):
            depth_sensor.set_option(rs.option.emitter_enabled, 0)
            print("IR Emitter disabled. Camera is now operating in passive stereo mode.")
            
        # Enable auto-exposure to adjust to ambient lighting since IR is off
        if depth_sensor.supports(rs.option.enable_auto_exposure):
            depth_sensor.set_option(rs.option.enable_auto_exposure, 1)

        # 3. Setup Open3D Visualizer
        vis = o3d.visualization.Visualizer()
        vis.create_window("RealSense D415 Passive Stereo Point Cloud", width=1024, height=768)
        
        pcd_vis = o3d.geometry.PointCloud()
        first_frame = True
        
        # Initialize pointcloud object
        pc = rs.pointcloud()

        print("Streaming live point cloud... Close the Open3D window to stop.")

        while True:
            # Wait for frames from the live camera
            frames = pipeline.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            
            if not depth_frame:
                continue
                
            # Generate the point cloud
            points = pc.calculate(depth_frame)
            
            # Extract vertices and convert to numpy array
            vtx = np.asanyarray(points.get_vertices()).view(np.float32).reshape(-1, 3)
            
            # Open3D coordinate system adjustment (invert Y and Z)
            vtx[:, 1] = -vtx[:, 1]
            vtx[:, 2] = -vtx[:, 2]
            
            pcd_vis.points = o3d.utility.Vector3dVector(vtx)
            


            # 4. Update the visualizer
            if first_frame:
                vis.add_geometry(pcd_vis)
                first_frame = False
            else:
                vis.update_geometry(pcd_vis)
                
            # Break if window is closed
            if not vis.poll_events():
                break
                
            vis.update_renderer()

    except RuntimeError as e:
        print(f"RuntimeError: {e}")
        print("Please ensure your Intel RealSense D415 camera is connected via USB.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Clean up resources
        if 'vis' in locals():
            vis.destroy_window()
        try:
            pipeline.stop()
        except Exception:
            pass
        print("Stream stopped.")

if __name__ == "__main__":
    main()
