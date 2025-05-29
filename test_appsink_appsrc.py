#!/usr/bin/env python3
"""
Test for Appsink/Appsrc Mode
This test demonstrates the frame processing capabilities using appsink/appsrc elements.
"""

import os
import sys
import time
import json
import logging
import numpy as np
import cv2
import argparse
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# Import our code
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from media_streamer import MediaStreamer

class StreamProcessingDemo:
    def __init__(self):
        # Load configuration
        self.config = self._load_config()
        self.media_streamer = MediaStreamer(self.config)
        self.active_streams = []
        
    def _load_config(self):
        """Load configuration from config.json"""
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                log.info(f"Configuration loaded from {config_path}")
                return config
        except Exception as e:
            log.error(f"Failed to load config: {e}")
            return {"srtp": {"key": "313233343536373839303132333435363132333435363738393031323334"}}
    
    def start_test_stream(self, video_path, dest_ip="127.0.0.1", dest_port=9000, 
                         processing_type=None, ssrc=None):
        """Start a test stream with optional frame processing"""
        if not os.path.exists(video_path):
            log.error(f"Video file not found: {video_path}")
            return False
            
        # Define a frame processor callback based on the processing type
        processor = None
        if processing_type:
            if processing_type == "grayscale":
                processor = self.process_grayscale
            elif processing_type == "edge":
                processor = self.process_edge_detection
            elif processing_type == "blur":
                processor = self.process_blur
            elif processing_type == "text":
                processor = self.process_add_text
                
        # Set encoder parameters
        encoder_params = {
            "width": 640,
            "height": 480,
            "framerate": 15,
            "bitrate": 1024,
            "keyframe_interval": 30
        }
        
        log.info(f"Starting stream with video: {video_path}")
        log.info(f"Processing type: {processing_type if processing_type else 'None'}")
        
        # Generate a stream ID
        stream_id = f"{dest_ip}:{dest_port}"
        if ssrc:
            stream_id = f"{stream_id}:{ssrc}"
            
        # Start the stream with frame processing
        success = self.media_streamer.start_stream_with_processing(
            video_path=video_path,
            dest_ip=dest_ip,
            dest_port=dest_port,
            frame_processor_callback=processor,
            ssrc=ssrc,
            encoder_params=encoder_params
        )
        
        if success:
            log.info(f"Stream {stream_id} started successfully")
            self.active_streams.append(stream_id)
            return stream_id
        else:
            log.error(f"Failed to start stream {stream_id}")
            return None
            
    # Frame processor examples
    
    def process_grayscale(self, frame, timestamp, stream_info):
        """Convert frame to grayscale and back to RGB"""
        # Convert RGB to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        # Convert grayscale back to RGB
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), timestamp
    
    def process_edge_detection(self, frame, timestamp, stream_info):
        """Apply edge detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        # Apply Canny edge detection
        edges = cv2.Canny(gray, 100, 200)
        # Convert back to RGB
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB), timestamp
    
    def process_blur(self, frame, timestamp, stream_info):
        """Apply gaussian blur"""
        # Process in RGB color space directly
        return cv2.GaussianBlur(frame, (15, 15), 0), timestamp
        
    def process_add_text(self, frame, timestamp, stream_info):
        """Add timestamp text to frame"""
        # Work with copy to avoid modifying the original
        frame_copy = frame.copy()
        
        # Get current timestamp
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        
        # Since OpenCV uses BGR but we get RGB, convert colors manually for text
        # Green in RGB is (0, 255, 0) and Orange in RGB is (255, 165, 0)
        green_rgb = (0, 255, 0)
        orange_rgb = (255, 165, 0)
        
        # Add text to the frame
        cv2.putText(
            frame_copy, 
            f"Time: {timestamp_str}", 
            (20, 40), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            1,
            green_rgb,  # Green color in RGB
            2
        )
        
        # Add project name
        cv2.putText(
            frame_copy, 
            "GB28181 Restreamer", 
            (20, frame_copy.shape[0] - 20), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.8,
            orange_rgb,  # Orange color in RGB
            2
        )
        
        return frame_copy, timestamp
        
    def toggle_processing(self, stream_id, enabled=True):
        """Toggle frame processing on/off"""
        return self.media_streamer.toggle_frame_processing(stream_id, enabled)
        
    def change_processor(self, stream_id, processing_type):
        """Change the processor type for an active stream"""
        processor = None
        if processing_type == "grayscale":
            processor = self.process_grayscale
        elif processing_type == "edge":
            processor = self.process_edge_detection
        elif processing_type == "blur":
            processor = self.process_blur
        elif processing_type == "text":
            processor = self.process_add_text
            
        return self.media_streamer.set_frame_processor(stream_id, processor)
        
    def stop_streams(self):
        """Stop all active streams"""
        if not self.active_streams:
            log.info("No active streams to stop")
            return
            
        for stream_id in self.active_streams[:]:
            self.media_streamer.stop_stream(stream_id)
            log.info(f"Stopped stream {stream_id}")
            self.active_streams.remove(stream_id)
            
    def cleanup(self):
        """Clean up resources"""
        self.stop_streams()
        self.media_streamer.shutdown()

def load_test_config():
    """Load test configuration"""
    return {
        "sip": {
            "device_id": "81000000465002100000",
            "username": "81000000465002100000",
            "password": "admin123",
            "server": "localhost",
            "port": 5060
        },
        "stream_directory": "./recordings"
    }

def frame_processor(frame, timestamp, stream_info):
    """Example frame processor that adds a timestamp overlay"""
    # Convert frame to numpy array if it isn't already
    if not isinstance(frame, np.ndarray):
        frame = np.frombuffer(frame, dtype=np.uint8).reshape(-1, 3)
    
    # Add timestamp text (simplified example)
    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    
    # Add text to the frame
    frame_copy = frame.copy()
    cv2.putText(
        frame_copy, 
        timestamp_str, 
        (20, 40), 
        cv2.FONT_HERSHEY_SIMPLEX, 
        1,
        (0, 255, 0),  # Green color in RGB
        2
    )
    
    # Return processed frame and timestamp
    return frame_copy, timestamp

def test_appsink_appsrc():
    """Test the appsink/appsrc functionality"""
    print("🧪 Starting Appsink/Appsrc Test")
    
    # Initialize GStreamer
    Gst.init(None)
    
    # Load test configuration
    config = load_test_config()
    
    # Create media streamer instance with specific pipeline configuration
    config.update({
        "pipeline": {
            "format": "RGB",
            "width": 640,
            "height": 480,
            "framerate": 30,
            "buffer_size": 33554432,  # 32MB buffer
            "queue_size": 3000,
            "sync": False,
            "async": False
        }
    })
    
    streamer = MediaStreamer(config)
    
    # Find a test video file
    test_video = None
    for root, dirs, files in os.walk(config["stream_directory"]):
        for file in files:
            if file.endswith(('.mp4', '.avi', '.mkv')):
                test_video = os.path.join(root, file)
                break
        if test_video:
            break
    
    if not test_video:
        print("❌ No test video found")
        return False
    
    print(f"📹 Using test video: {test_video}")
    
    # Create a wrapper function that provides default values for timestamp and stream_info
    def frame_processor_wrapper(frame, timestamp=None, stream_info=None):
        if timestamp is None:
            timestamp = time.time()
        if stream_info is None:
            stream_info = {"stream_id": "127.0.0.1:9000"}
        # Call the original processor and extract just the frame from the tuple
        processed_frame, _ = frame_processor(frame, timestamp, stream_info)
        # Ensure frame is in correct format
        if not isinstance(processed_frame, np.ndarray):
            processed_frame = np.frombuffer(processed_frame, dtype=np.uint8).reshape(-1, 3)
        return processed_frame
    
    # Start stream with processing
    success = streamer.start_stream_with_processing(
        video_path=test_video,
        dest_ip="127.0.0.1",
        dest_port=9000,
        frame_processor_callback=frame_processor_wrapper
    )
    
    if not success:
        print("❌ Failed to start stream with processing")
        return False
    
    print("✅ Stream started with processing")
    
    # Let it run for a few seconds
    time.sleep(5)
    
    # Stop the stream
    streamer.stop_stream("127.0.0.1:9000")
    print("✅ Test completed")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Test GStreamer appsink/appsrc functionality")
    parser.add_argument("--video", default="sample_videos/video.mp4", help="Path to video file")
    parser.add_argument("--ip", default="127.0.0.1", help="Destination IP address")
    parser.add_argument("--port", type=int, default=9000, help="Destination port")
    parser.add_argument("--processor", choices=["grayscale", "edge", "blur", "text"], 
                        default="text", help="Frame processor type")
    parser.add_argument("--duration", type=int, default=60, help="Stream duration in seconds")
    parser.add_argument("--toggle", action="store_true", help="Toggle processing on/off during test")
    args = parser.parse_args()
    
    demo = StreamProcessingDemo()
    
    try:
        # Start stream with the specified processor
        stream_id = demo.start_test_stream(args.video, args.ip, args.port, args.processor)
        
        if not stream_id:
            log.error("Failed to start stream. Exiting.")
            return
            
        log.info(f"Streaming started with {args.processor} processing. Stream will run for {args.duration} seconds.")
        log.info(f"You can view the stream using VLC: vlc rtp://{args.ip}:{args.port}")
        
        # If toggle flag is set, toggle processing every 5 seconds
        start_time = time.time()
        processing_enabled = True
        
        while time.time() - start_time < args.duration:
            if args.toggle and time.time() - start_time > 5:
                if (int((time.time() - start_time) / 5) % 2) == 0:
                    if not processing_enabled:
                        log.info("Enabling frame processing")
                        demo.toggle_processing(stream_id, True)
                        processing_enabled = True
                else:
                    if processing_enabled:
                        log.info("Disabling frame processing")
                        demo.toggle_processing(stream_id, False)
                        processing_enabled = False
                        
            # Change processor type every 15 seconds if stream is running longer than 30 seconds
            if args.duration > 30 and time.time() - start_time > 15:
                processor_index = int((time.time() - start_time) / 15) % 4
                processors = ["grayscale", "edge", "blur", "text"]
                new_processor = processors[processor_index]
                if time.time() - start_time > 15 and int((time.time() - start_time - 15) / 15) != int((time.time() - start_time - 14) / 15):
                    log.info(f"Changing processor to: {new_processor}")
                    demo.change_processor(stream_id, new_processor)
            
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        log.info("Test interrupted by user")
    finally:
        # Clean up resources
        demo.cleanup()
        log.info("Test completed")
        
if __name__ == "__main__":
    success = test_appsink_appsrc()
    sys.exit(0 if success else 1) 