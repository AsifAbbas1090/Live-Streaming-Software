#!/usr/bin/env python3
"""
Startup script that launches a dummy RTSP server and then runs the main application.
This provides a complete testing environment with both an RTSP source and the GB28181 restreamer.
"""

import os
import sys
import time
import signal
import subprocess
import atexit
import glob
import json
import shutil
from pathlib import Path

# Add src to Python path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'src')
sys.path.insert(0, src_dir)

from logger import log

# Global variables
rtsp_server_process = None
main_app_process = None

def find_sample_video():
    """Find a sample video file to use for the RTSP server."""
    sample_dir = os.path.join(script_dir, 'sample_videos')
    
    # Look for mp4 files first, then avi
    videos = glob.glob(os.path.join(sample_dir, '*.mp4'))
    if not videos:
        videos = glob.glob(os.path.join(sample_dir, '*.avi'))
    
    if not videos:
        # If no videos found, check if the directory exists
        if not os.path.exists(sample_dir):
            os.makedirs(sample_dir)
            log.warning(f"Created {sample_dir} directory, but no video files found.")
        else:
            log.warning(f"No video files found in {sample_dir}.")
        return None
    
    return videos[0]

def update_config_with_rtsp():
    """Update config.json to include the RTSP source."""
    config_path = os.path.join(script_dir, 'config', 'config.json')
    
    if not os.path.exists(config_path):
        log.error(f"Config file not found at {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Add or update the RTSP sources
        config['rtsp_sources'] = ["rtsp://127.0.0.1:8554/test"]
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        log.info("Updated config.json with RTSP source")
        return True
    except Exception as e:
        log.error(f"Failed to update config: {e}")
        return False

def command_exists(cmd):
    """Check if a command exists and is executable in PATH."""
    return shutil.which(cmd) is not None

def start_rtsp_server(video_path):
    """Start an RTSP server with the given video file."""
    global rtsp_server_process
    
    if not video_path:
        log.error("No video file available for RTSP server")
        return False
    
    try:
        # Check for available RTSP server options
        if command_exists("rtsp-simple-server"):
            # Use rtsp-simple-server (best option)
            log.info("Using rtsp-simple-server for RTSP streaming")
            
            # Create a simple config file
            rtsp_config_path = os.path.join(script_dir, 'rtsp-simple-server.yml')
            with open(rtsp_config_path, 'w') as f:
                f.write(f"""
paths:
  test:
    runOnDemand: ffmpeg -re -stream_loop -1 -i {video_path} -c copy -f rtsp rtsp://localhost:$RTSP_PORT/$RTSP_PATH
                """)
            
            # Start rtsp-simple-server
            rtsp_server_process = subprocess.Popen(
                ['rtsp-simple-server', rtsp_config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        elif command_exists("test-launch") and command_exists("test-mp4"):
            # GStreamer RTSP server tools
            log.info("Using GStreamer's test-launch for RTSP streaming")
            rtsp_server_process = subprocess.Popen(
                ['test-launch', f'filesrc location={video_path} ! decodebin ! x264enc ! rtph264pay name=pay0 pt=96'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        elif command_exists("ffmpeg"):
            # Use FFmpeg (wide compatibility)
            log.info("Using FFmpeg for RTSP streaming")
            rtsp_server_process = subprocess.Popen(
                ['ffmpeg', '-re', '-i', video_path, '-c', 'copy', '-f', 'rtsp', 'rtsp://127.0.0.1:8554/test'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        elif command_exists("vlc"):
            # VLC as another fallback
            log.info("Using VLC for RTSP streaming")
            rtsp_server_process = subprocess.Popen(
                ['vlc', video_path, '--sout', '#rtp{sdp=rtsp://127.0.0.1:8554/test}', '--loop'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        elif command_exists("gst-launch-1.0"):
            # Last resort: Use a simple GStreamer pipeline
            log.info("Using GStreamer pipeline for RTSP simulation")
            
            # Create a UDP server that mimics an RTSP stream
            pipeline = f'filesrc location={video_path} ! decodebin ! videoconvert ! x264enc tune=zerolatency ! rtph264pay ! udpsink host=127.0.0.1 port=8554'
            rtsp_server_process = subprocess.Popen(
                ['gst-launch-1.0', '-v'] + pipeline.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        else:
            log.error("No suitable RTSP server or streaming tool found")
            print("Please install one of: rtsp-simple-server, gstreamer, ffmpeg, or vlc")
            return False
        
        # Give the server a moment to start
        time.sleep(3)
        
        if rtsp_server_process.poll() is not None:
            log.error("RTSP server failed to start")
            return False
        
        log.info(f"RTSP server started with {video_path}")
        return True
    except Exception as e:
        log.error(f"Failed to start RTSP server: {e}")
        return False

def create_dummy_rtsp_stream():
    """Create a simulated RTSP stream by writing a test file when nothing else works."""
    try:
        log.info("Falling back to creating a dummy RTSP simulation file")
        # Create a simple text file that explains there's no real RTSP server
        fallback_path = os.path.join(script_dir, 'dummy_rtsp.txt')
        with open(fallback_path, 'w') as f:
            f.write("This is a dummy RTSP simulation file. No actual RTSP server could be started.\n")
            f.write("The application will still run, but RTSP functionality will be limited.\n")
        
        log.info("Created dummy RTSP simulation file")
        print("WARNING: Running in limited mode without actual RTSP server")
        print("The application will continue but RTSP streaming will not work correctly.")
        return True
    except Exception as e:
        log.error(f"Failed to create dummy RTSP simulation: {e}")
        return False

def start_main_app():
    """Start the main GB28181 restreamer application."""
    global main_app_process
    
    try:
        main_path = os.path.join(src_dir, 'main.py')
        
        # Start the main application
        main_app_process = subprocess.Popen(
            ['python3', main_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        
        # Monitor main app output
        for line in main_app_process.stdout:
            print(line, end='')
            
        return True
    except Exception as e:
        log.error(f"Failed to start main application: {e}")
        return False

def cleanup():
    """Clean up subprocesses when the script exits."""
    log.info("Cleaning up processes...")
    
    if main_app_process:
        log.info("Terminating main application")
        main_app_process.terminate()
        try:
            main_app_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            main_app_process.kill()
    
    if rtsp_server_process:
        log.info("Terminating RTSP server")
        rtsp_server_process.terminate()
        try:
            rtsp_server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            rtsp_server_process.kill()
    
    log.info("Cleanup complete")

def signal_handler(sig, frame):
    """Handle termination signals."""
    log.info(f"Received signal {sig}, shutting down...")
    cleanup()
    sys.exit(0)

def main():
    """Main function."""
    print("===== GB28181 Restreamer with RTSP Server =====")
    
    # Register cleanup handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Find a sample video
    video_path = find_sample_video()
    if not video_path:
        print("Please place an MP4 or AVI video file in the 'sample_videos' directory")
        return
    
    # Update config to include RTSP source
    if not update_config_with_rtsp():
        return
    
    # Start RTSP server
    print(f"Starting RTSP server with video: {video_path}")
    rtsp_started = start_rtsp_server(video_path)
    
    # If RTSP server failed to start, try to create a dummy simulation
    if not rtsp_started:
        if not create_dummy_rtsp_stream():
            print("Could not set up any RTSP environment. Exiting.")
            return
    
    # Start main application
    print("Starting GB28181 Restreamer application...")
    start_main_app()

if __name__ == "__main__":
    main() 