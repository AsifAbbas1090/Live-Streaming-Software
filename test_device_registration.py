#!/usr/bin/env python3
"""
GB28181 Device Registration Test for WVP-pro

This script tests device registration with a WVP-pro platform using the client's credentials.
It focuses solely on SIP registration functionality.

Usage:
  python test_device_registration.py [--device-id DEVICE_ID] [--password PASSWORD]
"""

import os
import sys
import time
import signal
import argparse
import subprocess
import threading
import random
import tempfile
import logging
import json
from datetime import datetime
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger('gb28181-reg-test')

# Default WVP server credentials from the client
DEFAULT_DEVICE_ID = "81000000465001000101"
DEFAULT_PASSWORD = "admin123"
DEFAULT_SIP_SERVER = "ai-sip.x-stage.bull-b.com"
DEFAULT_SIP_PORT = 5060

# Try to load config from config.json
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.json")
if os.path.exists(config_path):
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        sip_config = config.get('sip', {})
        DEFAULT_DEVICE_ID = sip_config.get('device_id', DEFAULT_DEVICE_ID)
        DEFAULT_PASSWORD = sip_config.get('password', DEFAULT_PASSWORD)
        DEFAULT_SIP_SERVER = sip_config.get('server', DEFAULT_SIP_SERVER)
        DEFAULT_SIP_PORT = sip_config.get('port', DEFAULT_SIP_PORT)
        log.info(f"Loaded configuration from {config_path}")
    except Exception as e:
        log.error(f"Failed to load config from {config_path}: {e}")

def kill_existing_pjsua_processes():
    """Kill any existing pjsua processes that might be holding ports"""
    try:
        # Find all pjsua processes
        ps_process = subprocess.run(["ps", "-ef"], capture_output=True, text=True)
        lines = ps_process.stdout.split('\n')
        
        # Get the current process ID to avoid killing parent processes
        current_pid = os.getpid()
        
        for line in lines:
            if 'pjsua' in line and str(current_pid) not in line:
                try:
                    # Extract PID
                    parts = line.split()
                    if len(parts) > 1:
                        pid = int(parts[1])
                        # Kill the process
                        log.info(f"Killing existing pjsua process with PID {pid}")
                        os.kill(pid, signal.SIGKILL)
                except Exception as e:
                    log.error(f"Error killing pjsua process: {e}")
    except Exception as e:
        log.error(f"Error checking for existing pjsua processes: {e}")

def find_available_port(start_port=5080, max_tries=20):
    """Find an available port starting from the given port"""
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
    
    # If we couldn't find an available port, generate a random one
    # This is less reliable but better than failing
    return random.randint(5080, 6000)

def create_pjsua_config(device_id, password, server, port, local_port):
    """Create a PJSUA configuration file for registration testing"""
    # Use a temporary file for the config
    fd, config_path = tempfile.mkstemp(prefix="pjsua_", suffix=".cfg")
    os.close(fd)
    
    with open(config_path, "w") as f:
        f.write(f"""--id sip:{device_id}@{server}
--registrar sip:{server}:{port}
--realm *
--username {device_id}
--password {password}
--local-port {local_port}
--auto-answer 200
--null-audio
--log-level 5
--auto-update-nat=1
--max-calls=4
""")
    
    log.info(f"Created PJSUA config file at {config_path}")
    return config_path

def test_device_registration(device_id, password, server, port, timeout=60):
    """Test GB28181 device registration with the given credentials"""
    # Kill any existing pjsua processes
    kill_existing_pjsua_processes()
    
    # Find an available local port
    local_port = find_available_port(5080)
    log.info(f"Using local port: {local_port}")
    
    # Create the PJSUA config file
    config_path = create_pjsua_config(device_id, password, server, port, local_port)
    
    try:
        # Launch PJSUA to test registration
        log.info(f"Starting PJSUA with configuration...")
        log.info(f"  Device ID: {device_id}")
        log.info(f"  SIP Server: {server}:{port}")
        log.info(f"  Transport: UDP")
        
        # Launch the process
        process = subprocess.Popen(
            ["pjsua", "--config-file", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        log.info(f"PJSUA process started with PID: {process.pid}")
        
        # Monitor the output for registration status
        registration_complete = False
        registration_failed = False
        start_time = time.time()
        
        while time.time() - start_time < timeout and not registration_complete and not registration_failed:
            line = process.stdout.readline().strip()
            if not line:
                if process.poll() is not None:
                    log.error(f"PJSUA process exited unexpectedly with code {process.returncode}")
                    break
                continue
            
            # Log important lines
            if any(x in line for x in ["Registration", "AUTH", "Success", "Error", "Failed"]):
                log.info(f"PJSUA: {line}")
            
            # Check for registration success/failure
            if "Registration complete" in line or "status=200" in line:
                log.info(f"✅ Registration successfully completed!")
                registration_complete = True
            elif "Registration failed" in line or "status=40" in line or "status=50" in line:
                log.error(f"❌ Registration failed!")
                registration_failed = True
        
        # If we timed out without a clear success/failure
        if not registration_complete and not registration_failed:
            log.warning(f"⏱️ Registration timed out after {timeout} seconds")
        
        # Keep the process running for a bit if registration was successful
        if registration_complete:
            log.info("Registration successful. Keeping connection open for 10 seconds...")
            time.sleep(10)
        
        # Return the result
        return registration_complete
    
    except Exception as e:
        log.error(f"Error in registration test: {e}")
        return False
    
    finally:
        # Clean up the config file
        try:
            os.unlink(config_path)
        except Exception:
            pass
        
        # Terminate the PJSUA process if still running
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

def main():
    parser = argparse.ArgumentParser(description='Test GB28181 device registration with WVP-pro')
    parser.add_argument('--device-id', default=DEFAULT_DEVICE_ID,
                        help=f'Device ID to register (default: {DEFAULT_DEVICE_ID})')
    parser.add_argument('--password', default=DEFAULT_PASSWORD,
                        help=f'SIP password (default: {DEFAULT_PASSWORD})')
    parser.add_argument('--server', default=DEFAULT_SIP_SERVER,
                        help=f'SIP server address (default: {DEFAULT_SIP_SERVER})')
    parser.add_argument('--port', type=int, default=DEFAULT_SIP_PORT,
                        help=f'SIP server port (default: {DEFAULT_SIP_PORT})')
    parser.add_argument('--timeout', type=int, default=60,
                        help='Timeout in seconds for registration (default: 60)')
    
    args = parser.parse_args()
    
    # Check if PJSUA is installed
    try:
        subprocess.run(["which", "pjsua"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log.error("PJSUA not found. Please install it with: sudo apt install pjsip-tools")
        return 1
    
    # Print test header
    print("\n" + "=" * 50)
    print(f"GB28181 Device Registration Test")
    print("=" * 50)
    
    # Run the test
    success = test_device_registration(
        args.device_id,
        args.password,
        args.server,
        args.port,
        args.timeout
    )
    
    if success:
        print("\n✅ Device registration test PASSED!")
        return 0
    else:
        print("\n❌ Device registration test FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 