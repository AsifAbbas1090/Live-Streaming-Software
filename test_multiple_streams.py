#!/usr/bin/env python3
# test_multiple_streams.py

import os
import sys
import time
import json
import threading
import argparse

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from media_streamer import MediaStreamer
from file_scanner import scan_video_files
from logger import log


def load_config():
    """Load configuration from JSON file"""
    config_path = os.path.join("config", "config.json")
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)
        
    with open(config_path, 'r') as f:
        return json.load(f)


def display_status(streamer, streams):
    """Display the status of all streams every few seconds"""
    while True:
        print("\n" + "="*60)
        print(f"ACTIVE STREAMS: {streamer.get_active_streams_count()}")
        print("="*60)
        
        # Get status for all streams
        status_all = streamer.get_stream_status()
        
        for stream_id, status in status_all.items():
            health_emoji = "✅" if status.get("health") == "good" else "⚠️" if status.get("health") == "warning" else "❌"
            state = status.get("status", "unknown")
            duration = status.get("duration", 0)
            errors = status.get("errors", 0)
            recoveries = status.get("recoveries", 0)
            video = os.path.basename(status.get("video_path", "unknown"))
            
            print(f"{health_emoji} Stream: {stream_id}")
            print(f"   State: {state}, Duration: {duration}s, Errors: {errors}, Recoveries: {recoveries}")
            print(f"   Video: {video}")
        
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Test multiple concurrent GB28181 streams")
    parser.add_argument("--streams", type=int, default=3, help="Number of concurrent streams to test")
    args = parser.parse_args()

    # Load configuration
    config = load_config()
    
    # Initialize media streamer
    streamer = MediaStreamer(config)
    
    # Get available video files
    video_dir = config.get("stream_directory", "./sample_videos/")
    videos = scan_video_files(video_dir)
    
    if not videos:
        print("Error: No video files found in the specified directory")
        sys.exit(1)
    
    print(f"Found {len(videos)} videos")
    
    # Create specified number of streams
    streams = []
    base_port = 9000
    
    print(f"Starting {args.streams} concurrent streams...")
    
    for i in range(args.streams):
        # Use videos in rotation
        video_index = i % len(videos)
        video_path = videos[video_index]
        
        # Use different port for each stream
        port = base_port + i
        
        # Create unique SSRC for each stream
        ssrc = f"{1000000 + i:010d}"
        
        print(f"Starting stream #{i+1}: {os.path.basename(video_path)} -> 127.0.0.1:{port} (SSRC: {ssrc})")
        
        # Start the stream
        result = streamer.start_stream(
            video_path=video_path,
            dest_ip="127.0.0.1",
            dest_port=port,
            ssrc=ssrc,
            encoder_params={
                "width": 640,
                "height": 480,
                "framerate": 25,
                "bitrate": 1024,
                "speed_preset": "ultrafast"
            }
        )
        
        if result:
            print(f"Stream #{i+1} started successfully")
            streams.append({
                "index": i+1, 
                "video": video_path,
                "port": port,
                "ssrc": ssrc
            })
        else:
            print(f"Failed to start stream #{i+1}")
    
    # Start status monitoring thread
    status_thread = threading.Thread(target=display_status, args=(streamer, streams), daemon=True)
    status_thread.start()
    
    try:
        print("\nStreams are running. Press Ctrl+C to stop...\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping streams...")
        streamer.shutdown()
        print("All streams stopped.")


if __name__ == "__main__":
    main() 