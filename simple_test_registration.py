#!/usr/bin/env python3
"""
Simple GB28181 Device Registration Test Script

This script tests the device registration with the WVP-pro platform using
direct pjsua calls rather than the full implementation.
"""

import os
import subprocess
import time
import json
import signal
import sys
import random
from datetime import datetime

# Constants for testing
TEST_DEVICE_ID = "810000004650010000XX"  # Replace XX with a unique number
TEST_DEVICE_PASSWORD = "admin123"
WVP_SIP_SERVER = "ai-sip.x-stage.bull-b.com"
WVP_SIP_PORT = 5060

def find_available_port(start_port, max_tries=100):
    """Find an available port starting from the given port."""
    import socket
    
    for i in range(max_tries):
        port = start_port + i
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    
    return None

def generate_device_id():
    """Generate a unique device ID based on timestamp and random number"""
    timestamp = datetime.now().strftime("%H%M")
    random_suffix = random.randint(10, 99)
    return TEST_DEVICE_ID.replace("XX", f"{timestamp}{random_suffix}")

def create_pjsua_config(device_id, local_port):
    """Create a PJSUA configuration file"""
    cfg_path = "/tmp/test_pjsua.cfg"
    
    with open(cfg_path, "w") as f:
        f.write(f"""--id sip:{device_id}@{WVP_SIP_SERVER}
--registrar sip:{WVP_SIP_SERVER}:{WVP_SIP_PORT}
--proxy sip:{WVP_SIP_SERVER}:{WVP_SIP_PORT};transport=tcp
--realm *
--username {device_id}
--password {TEST_DEVICE_PASSWORD}
--local-port {local_port}
--auto-answer 200
--null-audio
--duration 0
--log-level 5
--auto-update-nat=1
--reg-timeout=3600
--rereg-delay=5
--max-calls=4
--thread-cnt=4
--rtp-port=10000
--dis-codec=speex/16000
--dis-codec=speex/8000
--dis-codec=iLBC
--add-codec=H264
--publish
--use-timer=2
--timer-min-se=90
--timer-se=1800
""")
    return cfg_path

def test_registration(duration=300):
    """Run a simple registration test using PJSUA directly"""
    try:
        # Check if PJSUA is installed
        subprocess.run(["which", "pjsua"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ PJSUA not found. Please install with: sudo apt install pjsip-tools")
        return False
    
    # Generate a unique device ID
    device_id = generate_device_id()
    print(f"🔍 Using device ID: {device_id}")
    
    # Find an available port
    local_port = find_available_port(7000)
    if not local_port:
        print("❌ Could not find an available port")
        return False
    
    print(f"🔌 Using local port: {local_port}")
    
    # Create the configuration file
    cfg_path = create_pjsua_config(device_id, local_port)
    print(f"📝 Created configuration at {cfg_path}")
    
    # Run PJSUA with the configuration
    print(f"🚀 Starting PJSUA...")
    
    # Create a pipe for output
    process = subprocess.Popen(
        ["pjsua", "--config-file", cfg_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    # Function to handle process termination
    def signal_handler(sig, frame):
        print("\n⛔ Terminating test...")
        process.terminate()
        sys.exit(0)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Monitor the output for registration status
    start_time = time.time()
    registration_complete = False
    
    try:
        print("⏱️ Waiting for registration (this may take a few minutes)...")
        while time.time() - start_time < duration:
            line = process.stdout.readline()
            if not line:
                break
                
            # Only print important lines to avoid terminal spam
            if ("Registration" in line or 
                "Account" in line or 
                "Error" in line or 
                "Failed" in line or
                "Success" in line):
                print(line.strip())
            
            # Check for registration status
            if "Registration complete" in line or "status=200" in line:
                print("✅ Registration successful!")
                registration_complete = True
                
                # Keep running for a bit to maintain registration
                print(f"⏱️ Maintaining registration for 60 seconds...")
                time.sleep(60)
                break
                
            elif "Registration failed" in line:
                print("❌ Registration failed!")
                break
                
            # Add a small delay to prevent CPU hogging
            time.sleep(0.1)
            
        # If we get here and registration isn't complete, we timed out
        if not registration_complete:
            print(f"⏱️ Registration timed out after {duration} seconds")
            
    finally:
        # Clean up
        print("🧹 Cleaning up...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            
    return registration_complete

if __name__ == "__main__":
    print("==================================")
    print("Simple GB28181 Registration Test")
    print("==================================")
    
    success = test_registration()
    
    if success:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed.")
        sys.exit(1) 