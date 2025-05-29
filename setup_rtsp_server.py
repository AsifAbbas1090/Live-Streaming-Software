#!/usr/bin/env python3
"""
Local RTSP Server Setup
This script sets up a local RTSP server using GStreamer to stream a video file.
"""

import argparse
import os
import signal
import subprocess
import sys
import time

def setup_rtsp_server(video_path, port=8554, path="/test"):
    """
    Set up an RTSP server using GStreamer with the specified video file.
    
    Args:
        video_path: Path to the video file
        port: RTSP server port
        path: RTSP stream path
    
    Returns:
        subprocess.Popen: The process object for the RTSP server
    """
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}")
        return None
    
    # Build the GStreamer pipeline
    pipeline = (
        f'gst-launch-1.0 -v rtspclientsink location=rtsp://127.0.0.1:{port}{path} '
        f'name=sink filesrc location="{video_path}" ! decodebin name=dec '
        f'dec. ! queue ! videoconvert ! x264enc tune=zerolatency ! rtph264pay name=pay pt=96 ! sink.sink_0'
    )
    
    print(f"[RTSP] Starting RTSP server on port {port} with path {path}")
    print(f"[RTSP] Streaming video: {video_path}")
    print(f"[RTSP] RTSP URL: rtsp://127.0.0.1:{port}{path}")
    
    # Start the RTSP server
    try:
        process = subprocess.Popen(
            pipeline, 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        print(f"[RTSP] Server started with PID {process.pid}")
        return process
    except Exception as e:
        print(f"[ERROR] Failed to start RTSP server: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Local RTSP Server Setup')
    parser.add_argument('--video', default='./sample_videos/Entryyy.mp4', help='Path to video file')
    parser.add_argument('--port', type=int, default=8554, help='RTSP server port')
    parser.add_argument('--path', default='/test', help='RTSP stream path')
    
    args = parser.parse_args()
    
    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n[RTSP] Shutting down RTSP server...")
        if rtsp_process:
            rtsp_process.terminate()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the RTSP server
    rtsp_process = setup_rtsp_server(args.video, args.port, args.path)
    
    if rtsp_process:
        print("\n[INFO] To update your config.json, add this RTSP source:")
        print(f'  "rtsp://127.0.0.1:{args.port}{args.path}"')
        print("\n[INFO] Press Ctrl+C to stop the RTSP server\n")
        
        # Monitor the process
        while rtsp_process.poll() is None:
            line = rtsp_process.stdout.readline()
            if line:
                print(line.strip())
            time.sleep(0.1)
    
    print("[RTSP] Server stopped")

if __name__ == "__main__":
    main() 