#!/usr/bin/env python3
"""
WVP-pro Integration Test

This script tests integration with a WVP-pro platform, including:
1. Device registration
2. Time-series recording query (RecordInfo)
3. Basic streaming functionality

Usage:
  python test_wvp_integration.py

Configuration is loaded from config/config.json by default
"""

import os
import sys
import time
import json
import argparse
import logging
import datetime
import subprocess
import signal
import random
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('wvp-test')

# Default test configuration
DEFAULT_CONFIG = {
    "sip": {
        "device_id": "81000000462001888888",
        "username": "81000000462001888888",
        "password": "admin123",
        "server": "ai-sip.x-stage.bull-b.com",
        "port": 5060,
        "local_port": 5080,
        "prefer_tcp": True
    },
    "local_sip": {
        "enabled": False
    },
    "stream_directory": "./recordings",
    "logging": {
        "level": "DEBUG",
        "console": True
    }
}

def create_test_recordings(directory, count=5):
    """Create test recording files with proper timestamps"""
    log.info(f"Creating {count} test recording files in {directory}")
    
    # Create base directory
    Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for dates
    today = datetime.datetime.now()
    yesterday = today - datetime.timedelta(days=1)
    
    today_dir = os.path.join(directory, today.strftime("%Y-%m-%d"))
    yesterday_dir = os.path.join(directory, yesterday.strftime("%Y-%m-%d"))
    
    Path(today_dir).mkdir(parents=True, exist_ok=True)
    Path(yesterday_dir).mkdir(parents=True, exist_ok=True)
    
    # Create recording files with metadata
    recordings = []
    
    # Create some recordings for yesterday
    for i in range(count // 2):
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        filename = f"{hour:02d}-{minute:02d}-{second:02d}.mp4"
        filepath = os.path.join(yesterday_dir, filename)
        
        # Create a small video file using ffmpeg (if available)
        try:
            duration = random.randint(10, 60)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=640x480:rate=30",
                "-c:v", "libx264", "-t", str(duration), filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            log.info(f"Created test recording: {filepath}")
            
            # Store recording metadata
            recordings.append({
                "path": filepath,
                "time": yesterday.replace(hour=hour, minute=minute, second=second),
                "duration": duration
            })
        except (subprocess.SubprocessError, FileNotFoundError):
            # If ffmpeg fails, create an empty file
            with open(filepath, 'wb') as f:
                f.write(b'\0' * 1024)
            log.info(f"Created empty test file: {filepath}")
            
            # Store recording metadata
            recordings.append({
                "path": filepath,
                "time": yesterday.replace(hour=hour, minute=minute, second=second),
                "duration": 10
            })
    
    # Create some recordings for today
    for i in range(count - (count // 2)):
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        
        filename = f"{hour:02d}-{minute:02d}-{second:02d}.mp4"
        filepath = os.path.join(today_dir, filename)
        
        # Create a small video file using ffmpeg (if available)
        try:
            duration = random.randint(10, 60)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=10:size=640x480:rate=30",
                "-c:v", "libx264", "-t", str(duration), filepath
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            log.info(f"Created test recording: {filepath}")
            
            # Store recording metadata
            recordings.append({
                "path": filepath,
                "time": today.replace(hour=hour, minute=minute, second=second),
                "duration": duration
            })
        except (subprocess.SubprocessError, FileNotFoundError):
            # If ffmpeg fails, create an empty file
            with open(filepath, 'wb') as f:
                f.write(b'\0' * 1024)
            log.info(f"Created empty test file: {filepath}")
            
            # Store recording metadata
            recordings.append({
                "path": filepath,
                "time": today.replace(hour=hour, minute=minute, second=second),
                "duration": 10
            })
    
    # Save recording metadata to JSON file
    metadata_file = os.path.join(directory, "recordings.json")
    with open(metadata_file, 'w') as f:
        serialized_recordings = []
        for rec in recordings:
            serialized_recordings.append({
                "path": rec["path"],
                "time": rec["time"].isoformat(),
                "duration": rec["duration"]
            })
        json.dump(serialized_recordings, f, indent=2)
    
    log.info(f"Created {len(recordings)} test recordings with metadata saved to {metadata_file}")
    return recordings

def create_test_config(output_path, custom_config=None):
    """Create a test configuration file"""
    config = DEFAULT_CONFIG.copy()
    
    if custom_config:
        # Deep merge the custom config into the default config
        for key, value in custom_config.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                config[key].update(value)
            else:
                config[key] = value
    
    # Generate a unique device ID if not specified to avoid conflicts
    if "custom_device_id" not in locals():
        timestamp = datetime.datetime.now().strftime("%H%M")
        random_suffix = random.randint(10, 99)
        config["sip"]["device_id"] = f"{config['sip']['device_id']}{timestamp}{random_suffix}"
        config["sip"]["username"] = config["sip"]["device_id"]
    
    # Write the config file
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    log.info(f"Created test configuration at {output_path}")
    log.info(f"Using device ID: {config['sip']['device_id']}")
    
    return config

def run_restreamer(config_path, timeout=300):
    """Run the GB28181 restreamer with the specified config"""
    log.info("Starting GB28181 restreamer...")
    
    # Start the restreamer process
    process = subprocess.Popen(
        ["python3", "src/main.py", "--config", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    log.info(f"Restreamer started with PID {process.pid}")
    
    # Wait for startup indicators in the output
    startup_complete = False
    registration_complete = False
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        line = process.stdout.readline().strip()
        if not line:
            if process.poll() is not None:
                log.error(f"Restreamer process exited unexpectedly with code {process.returncode}")
                break
            continue
        
        print(f"[RESTREAMER] {line}")
        
        if "Starting GB28181 Restreamer" in line:
            log.info("Restreamer startup initiated")
            
        if "Generated catalog with" in line:
            log.info("Catalog generation complete")
            startup_complete = True
            
        if "Registration complete" in line or "Registration completed successfully" in line:
            log.info("SIP registration completed successfully")
            registration_complete = True
            break
    
    if not startup_complete:
        log.warning("Timed out waiting for restreamer startup")
    
    if not registration_complete:
        log.warning("Timed out waiting for SIP registration")
    
    return process

def test_wvp_integration():
    """Run the WVP integration test"""
    log.info("=" * 50)
    log.info("WVP-pro Integration Test")
    log.info("=" * 50)
    
    try:
        # Create test recordings
        recordings_dir = "./test_recordings"
        recordings = create_test_recordings(recordings_dir, count=10)
        
        # Create test configuration
        config_path = "./config/wvp_test_config.json"
        config = create_test_config(config_path, {
            "stream_directory": recordings_dir
        })
        
        # Run the restreamer
        restreamer_process = run_restreamer(config_path)
        
        try:
            # Wait for user to verify in WVP interface
            log.info("\nPlease verify the following in the WVP interface:")
            log.info(f"1. Device {config['sip']['device_id']} should appear in the device list")
            log.info("2. Check that the device's channels are listed")
            log.info("3. Navigate to device recordings to verify time-series query works")
            log.info("\nPress Enter to continue or Ctrl+C to stop...")
            
            input()
            
            log.info("Test complete")
            
        finally:
            # Clean up restreamer process
            if restreamer_process and restreamer_process.poll() is None:
                log.info("Stopping restreamer process...")
                restreamer_process.send_signal(signal.SIGINT)
                try:
                    restreamer_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    log.warning("Restreamer process didn't exit gracefully, force killing")
                    restreamer_process.kill()
    
    except KeyboardInterrupt:
        log.info("Test interrupted by user")
    except Exception as e:
        log.error(f"Test failed: {e}")
    finally:
        log.info("Test cleanup complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WVP-pro Integration Test")
    parser.add_argument("--keep-recordings", action="store_true", help="Keep test recordings after test")
    
    args = parser.parse_args()
    
    test_wvp_integration()
    
    if not args.keep_recordings and os.path.exists("./test_recordings"):
        import shutil
        log.info("Removing test recordings...")
        shutil.rmtree("./test_recordings") 