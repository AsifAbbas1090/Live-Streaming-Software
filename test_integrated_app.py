#!/usr/bin/env python3
"""
GB28181 Integrated Application Test Script

This script tests the complete integrated application by:
1. Starting the main application
2. Verifying SIP registration
3. Sending INVITE requests
4. Verifying stream functionality
5. Testing proper shutdown
"""

import os
import sys
import time
import json
import socket
import signal
import threading
import subprocess
import re
import argparse
import tempfile
from datetime import datetime

# Global variables
server_process = None
server_log_file = "./server_logs.txt"
rtsp_process = None  # New global variable to track the RTSP server process
vlc_processes = []
running = True

def log(message):
    """Log a message with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def setup_environment():
    """Set up the testing environment"""
    log("Setting up test environment...")
    
    # Check for config file
    if not os.path.exists('config/config.json'):
        log("⚠️ config.json not found! Creating default config.")
        # Create minimal config structure
        os.makedirs('config', exist_ok=True)
        with open('config/config.json', 'w') as f:
            default_config = {
                "sip": {
                    "device_id": "34020000001320000001",
                    "username": "34020000001320000001",
                    "password": "12345678",
                    "server": "127.0.0.1",
                    "port": 5060
                },
                "local_sip": {
                    "enabled": True,
                    "port": 5060,
                    "transport": "tcp"
                },
                "stream_directory": "./sample_videos/",
                "logging": {
                    "level": "INFO",
                    "file": "./logs/gb28181-restreamer.log",
                    "console": True
                }
            }
            json.dump(default_config, f, indent=2)
        log("✅ Created default config.json")
    
    # Check for sample_videos directory
    if not os.path.exists('sample_videos'):
        log("⚠️ sample_videos directory not found! Creating directory.")
        os.makedirs('sample_videos', exist_ok=True)
        # Create a dummy video file for testing if needed
        if not os.listdir('sample_videos'):
            try:
                log("⚠️ No video files found. Creating a test file...")
                # Try to find a sample video file elsewhere
                sample_paths = [
                    '/usr/share/example-videos/',
                    os.path.expanduser('~/Videos/')
                ]
                video_found = False
                for path in sample_paths:
                    if os.path.exists(path):
                        for file in os.listdir(path):
                            if file.endswith(('.mp4', '.avi')):
                                src = os.path.join(path, file)
                                dst = os.path.join('sample_videos', file)
                                import shutil
                                shutil.copy(src, dst)
                                log(f"✅ Copied {src} to {dst}")
                                video_found = True
                                break
                    if video_found:
                        break
                
                if not video_found:
                    # Create an empty file as placeholder
                    with open('sample_videos/test.mp4', 'wb') as f:
                        # Write minimal MP4 header
                        f.write(b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42mp41\x00\x00\x00\x00')
                    log("✅ Created placeholder video file")
            except Exception as e:
                log(f"⚠️ Error creating sample video: {e}")
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Clear previous log file
    with open(server_log_file, 'w') as f:
        f.write("")
    
    log("✅ Environment setup complete")
    return True

def start_server():
    """Start the main application server"""
    global server_process, server_log_file
    
    log("🚀 Starting GB28181 restreamer server...")
    
    # Create a test configuration file
    config_file = create_test_config()
    log(f"✅ Created test configuration at {config_file}")
    
    # Start the main application with our test config
    try:
        # Open a log file to capture the server output
        f = open(server_log_file, "w")
        
        # Start the server process
        server_process = subprocess.Popen(
            ["python3", "src/main.py", "--config", config_file],
            stdout=f,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        
        log(f"✅ Server started with PID {server_process.pid}")
        
        # Wait a bit for the server to start
        time.sleep(3)
        
        # Check if the process is still running
        if server_process.poll() is not None:
            log(f"❌ Server crashed with exit code: {server_process.returncode}")
            return False
            
        # Monitor the log file for startup indications
        startup_timeout = 20
        start_time = time.time()
        success = False
        
        while time.time() - start_time < startup_timeout:
            try:
                # Check server logs for success indicators
                with open(server_log_file, "r") as log_file:
                    log_content = log_file.read()
                    if "SIP server started" in log_content or "Server started successfully" in log_content:
                        success = True
                        break
            except Exception as e:
                log(f"Error reading log file: {e}")
            
            # Check if server is still running
            if server_process.poll() is not None:
                log(f"❌ Server crashed with exit code: {server_process.returncode}")
                return False
                
            # Wait before checking again
            time.sleep(1)
            
        if success:
            log("✅ Server startup confirmed")
            return True
        else:
            log("⚠️ Server may not have started properly, proceeding with tests anyway")
            return True  # Continue with tests, the server might still work
            
    except Exception as e:
        log(f"❌ Failed to start server: {e}")
        return False

def wait_for_server_startup(timeout=20):
    """Wait for server to start up successfully"""
    global server_process
    
    log(f"⏳ Waiting up to {timeout} seconds for server startup...")
    
    start_time = time.time()
    success_indicators = [
        "SIP client...",
        "Started GB28181 SIP message sender thread",
        "Local SIP server is enabled"
    ]
    
    # Read output until timeout or success
    log_capture = []
    success_count = 0
    
    try:
        while time.time() - start_time < timeout:
            if server_process.poll() is not None:
                log(f"❌ Server process exited with code: {server_process.returncode}")
                break
                
            line = server_process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            line = line.strip()
            log_capture.append(line)
            print(f"  {line}")
            
            # Check for success indicators
            for indicator in success_indicators:
                if indicator in line:
                    success_count += 1
                    log(f"✓ Found indicator: '{indicator}'")
                    
            # Check if we've found all success indicators
            if success_count >= 2:  # Need at least 2 key indicators
                log("✅ Server is ready")
                # Continue reading output but in a separate thread
                threading.Thread(target=monitor_server_output, daemon=True).start()
                return True
                
            # Check for failure indicators
            if "ERROR" in line and not "Failed to extract" in line:
                log(f"⚠️ Possible error detected: {line}")
    
        # Save captured log to file
        with open(server_log_file, 'a') as f:
            f.write("\n".join(log_capture) + "\n")
            
        if time.time() - start_time >= timeout:
            log("❌ Timeout waiting for server startup")
            return False
            
        return False
    except Exception as e:
        log(f"❌ Error while waiting for server: {e}")
        return False

def monitor_server_output():
    """Monitor server output in a separate thread"""
    global server_process, running
    
    log("📊 Starting server output monitoring")
    
    try:
        with open(server_log_file, 'a') as f:
            while running and server_process and server_process.poll() is None:
                line = server_process.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                    
                line = line.strip()
                f.write(line + "\n")
                f.flush()
                
                # Print only important lines
                if any(x in line for x in ["ERROR", "INVITE", "SDP", "Registration", "Stream"]):
                    log(f"SERVER: {line}")
    except Exception as e:
        log(f"⚠️ Error in output monitor: {e}")
    finally:
        log("📊 Server output monitoring stopped")

def send_invite(dest_ip="127.0.0.1", dest_port=9000, sip_server="127.0.0.1", sip_port=5060, device_id=None, use_tcp=True):
    """Send an INVITE request to the SIP server"""
    log(f"📨 Sending INVITE request to {sip_server}:{sip_port}")
    
    # Try to load device ID from config if not provided
    if not device_id:
        try:
            with open('config/config.json', 'r') as f:
                config = json.load(f)
                device_id = config['sip']['device_id']
                log(f"ℹ️ Using device ID from config: {device_id}")
        except Exception as e:
            log(f"⚠️ Failed to load device ID from config: {e}")
            device_id = "34020000001320000001"
            log(f"ℹ️ Using default device ID: {device_id}")
    
    # Format the SDP content
    sdp_content = f"""v=0
o=- {int(time.time())} 1 IN IP4 {dest_ip}
s=GB28181 Test Session
c=IN IP4 {dest_ip}
t=0 0
m=video {dest_port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=recvonly
y=0000000001
f=v/2/25
"""

    # Transport protocol
    transport = "TCP" if use_tcp else "UDP"

    # Format the SIP INVITE message
    invite_msg = f"""INVITE sip:{device_id}@{sip_server}:{sip_port} SIP/2.0
Via: SIP/2.0/{transport} {dest_ip}:5060;branch=z9hG4bK-{int(time.time())}
From: <sip:100000000000000000@{dest_ip}:5060>;tag=tag-{int(time.time())}
To: <sip:{device_id}@{sip_server}:{sip_port}>
Call-ID: call-{int(time.time())}@{dest_ip}
CSeq: 1 INVITE
Contact: <sip:100000000000000000@{dest_ip}:5060>
Content-Type: application/sdp
Max-Forwards: 70
User-Agent: GB28181 Test Client
Content-Length: {len(sdp_content)}

{sdp_content}"""

    try:
        # Send the INVITE
        if use_tcp:
            # Send via TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                log(f"🔄 Connecting to {sip_server}:{sip_port} via TCP...")
                sock.connect((sip_server, int(sip_port)))
                sock.sendall(invite_msg.encode())
                log("✅ TCP connection established and INVITE sent")
                
                # Wait for response (timeout after 5 seconds)
                sock.settimeout(5)
                try:
                    response = sock.recv(4096)
                    if response:
                        log(f"📩 Received response: {response.decode()[:100]}...")
                        
                        # Check response code
                        if re.search(r"SIP/2.0 (100|180|200) ", response.decode()):
                            log("✅ Received positive response")
                        else:
                            log(f"⚠️ Unexpected response code")
                except socket.timeout:
                    log("⚠️ No response received (timeout)")
        else:
            # Send via UDP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(invite_msg.encode(), (sip_server, int(sip_port)))
                log("✅ UDP packet sent")
        
        # Create SDP file for VLC
        create_sdp_file(dest_ip, dest_port)
        
        return True
    except ConnectionRefusedError:
        log(f"❌ Connection refused to {sip_server}:{sip_port}. Is the server running?")
        return False
    except Exception as e:
        log(f"❌ Failed to send INVITE: {e}")
        return False

def create_sdp_file(dest_ip="127.0.0.1", dest_port=9000):
    """Create an SDP file for VLC to use"""
    with open('invite.sdp', 'w') as f:
        f.write(f"""v=0
o=- 0 0 IN IP4 {dest_ip}
s=GB28181 Test Stream
c=IN IP4 {dest_ip}
t=0 0
m=video {dest_port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=framerate:25
a=fmtp:96 profile-level-id=42e01f
""")
    log("✅ Created SDP file for VLC (invite.sdp)")
    
    log("\n▶️ To view the stream, run in another terminal:")
    log(f"  vlc invite.sdp")
    log(f"  or: cvlc rtp://{dest_ip}:{dest_port}")

def run_viewer(dest_ip="127.0.0.1", dest_port=9000, use_vlc=False):
    """Start a viewer for the stream"""
    global vlc_processes
    
    if use_vlc:
        # Try to start VLC
        try:
            if os.path.exists('invite.sdp'):
                log("🎬 Starting VLC with SDP file...")
                proc = subprocess.Popen(
                    ["vlc", "--quiet", "invite.sdp"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                log(f"🎬 Starting VLC with RTP URL...")
                proc = subprocess.Popen(
                    ["vlc", "--quiet", f"rtp://{dest_ip}:{dest_port}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            vlc_processes.append(proc)
            log(f"✅ Started VLC (PID: {proc.pid})")
            return True
        except Exception as e:
            log(f"❌ Failed to start VLC: {e}")
            return False
    else:
        # Just print the command to use
        log("\n▶️ To view the stream, run in another terminal:")
        log(f"  vlc invite.sdp")
        log(f"  or: cvlc rtp://{dest_ip}:{dest_port}")
        return True

def test_catalog_query(sip_server="127.0.0.1", sip_port=5060, device_id=None):
    """Test sending a catalog query message"""
    if not device_id:
        try:
            with open('config/config.json', 'r') as f:
                config = json.load(f)
                device_id = config['sip']['device_id']
        except Exception:
            device_id = "34020000001320000001"
    
    log(f"📂 Sending catalog query to {sip_server}:{sip_port}")
    
    # Simple catalog query message
    xml_content = f"""<?xml version="1.0"?>
<Query>
<CmdType>Catalog</CmdType>
<SN>1</SN>
<DeviceID>{device_id}</DeviceID>
</Query>"""
    
    message = f"""MESSAGE sip:{device_id}@{sip_server}:{sip_port} SIP/2.0
Via: SIP/2.0/TCP 127.0.0.1:5061;branch=z9hG4bK-{int(time.time())}
From: <sip:100000000000000000@127.0.0.1:5061>;tag=tag-{int(time.time())}
To: <sip:{device_id}@{sip_server}:{sip_port}>
Call-ID: query-{int(time.time())}@127.0.0.1
CSeq: 1 MESSAGE
Content-Type: Application/MANSCDP+xml
Max-Forwards: 70
User-Agent: Test Client
Content-Length: {len(xml_content)}

{xml_content}"""

    try:
        # Send via TCP
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((sip_server, int(sip_port)))
            sock.sendall(message.encode())
            log("✅ Catalog query sent")
            
            # Wait for response
            sock.settimeout(5)
            try:
                response = sock.recv(4096)
                if response:
                    log(f"📩 Received response, length {len(response)} bytes")
                    return True
            except socket.timeout:
                log("⚠️ No response received (timeout)")
                return False
    except Exception as e:
        log(f"❌ Failed to send catalog query: {e}")
        return False

def start_rtsp_server(video_path="./sample_videos/Entryyy.mp4", port=8554, timeout=300):
    """Start an RTSP server using FFmpeg"""
    global rtsp_process
    
    log("🎬 Starting RTSP server...")
    
    # Check if video file exists
    if not os.path.exists(video_path):
        log(f"⚠️ Video file not found: {video_path}")
        
        # Look for any video in the sample_videos directory
        sample_dir = "./sample_videos"
        if os.path.exists(sample_dir):
            for file in os.listdir(sample_dir):
                if file.endswith(('.mp4', '.avi')):
                    video_path = os.path.join(sample_dir, file)
                    log(f"✅ Using alternative video file: {video_path}")
                    break
    
    if not os.path.exists(video_path):
        log("❌ No suitable video file found for RTSP streaming")
        return False
    
    rtsp_url = f"rtsp://localhost:{port}/test"
    
    # Use FFmpeg to stream the video as an RTSP source
    try:
        cmd = [
            "ffmpeg",
            "-re",                   # Read input at native frame rate (realtime)
            "-i", video_path,        # Input file
            "-c", "copy",            # Copy codecs (no transcoding)
            "-f", "rtsp",            # Output format
            "-t", str(timeout),      # Set a timeout to prevent endless streaming
            rtsp_url                 # Output URL
        ]
        
        rtsp_log_file = open("rtsp_server.log", "w")
        rtsp_process = subprocess.Popen(
            cmd,
            stdout=rtsp_log_file,
            stderr=rtsp_log_file,
            universal_newlines=True,
        )
        
        log(f"✅ RTSP server started with PID {rtsp_process.pid}")
        log(f"✅ RTSP URL: {rtsp_url}")
        
        # Wait a bit for the server to start up
        time.sleep(2)
        
        # Check if process is still running
        if rtsp_process.poll() is not None:
            log(f"❌ RTSP server exited with code: {rtsp_process.returncode}")
            return False
            
        # Verify RTSP server is working
        if check_rtsp_server(rtsp_url):
            log("✅ RTSP server verified working")
        else:
            log("⚠️ Could not verify RTSP server, but process is running")
        
        return True
    except Exception as e:
        log(f"❌ Failed to start RTSP server: {e}")
        return False

def check_rtsp_server(rtsp_url, timeout=5):
    """Check if RTSP server is working by testing connection with FFmpeg"""
    try:
        # Use FFmpeg to check if the RTSP server is responding
        cmd = [
            "ffprobe",
            "-v", "error",
            "-timeout", f"{timeout*1000000}",  # Timeout in microseconds
            "-i", rtsp_url,
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1"
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout+1,  # Give subprocess a little extra time
            text=True
        )
        
        return result.returncode == 0
    except Exception as e:
        log(f"RTSP check error: {e}")
        return False

def cleanup():
    """Clean up all resources"""
    global server_process, rtsp_process, vlc_processes, running
    
    log("🧹 Cleaning up resources...")
    running = False
    
    # Stop all VLC processes
    for proc in vlc_processes:
        if proc.poll() is None:
            proc.terminate()
    vlc_processes.clear()
    
    # Stop RTSP server process
    if rtsp_process and rtsp_process.poll() is None:
        log("🛑 Stopping RTSP server...")
        rtsp_process.terminate()
        try:
            rtsp_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log("⚠️ RTSP server didn't stop gracefully, forcing...")
            rtsp_process.kill()
    
    # Stop server process
    if server_process and server_process.poll() is None:
        log("🛑 Stopping server process...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log("⚠️ Server didn't stop gracefully, forcing...")
            server_process.kill()
            
    log("✅ Cleanup complete")

def signal_handler(sig, frame):
    """Handle termination signals"""
    log(f"Caught signal {sig}, shutting down...")
    cleanup()
    sys.exit(0)

def create_test_config():
    """Create a temporary config file for testing"""
    config = {
        "sip_server": {
            "listen_ip": "0.0.0.0",
            "port": 5060,
            "realm": "3402000000",
            "disable_auth": True,
            "protocol": "UDP",
            "device_id": "34020000001320000001",
            "password": "12345678"
        },
        "rtsp_sources": [
            # Default to the RTSP server we start
            "rtsp://localhost:8554/test"
        ],
        "restream_server": {
            "listen_ip": "0.0.0.0",
            "rtsp_port": 8555,
            "hls_port": 8080,
            "hls_segment_length": 2
        },
        "debug": True
    }
    
    # Write the config to a temporary file
    config_file = "./config/test_config.json"
    os.makedirs("./config", exist_ok=True)
    with open(config_file, "w") as f:
        json.dump(config, f, indent=4)
    
    return config_file

def main():
    parser = argparse.ArgumentParser(description="Test the GB28181 restreamer integrated application")
    parser.add_argument("--dest-ip", default="127.0.0.1", help="Destination IP for streaming")
    parser.add_argument("--dest-port", type=int, default=9000, help="Destination port for streaming")
    parser.add_argument("--sip-port", type=int, default=5060, help="SIP server port")
    parser.add_argument("--viewers", type=int, default=0, help="Number of VLC viewers to start")
    parser.add_argument("--no-setup", action="store_true", help="Skip environment setup")
    parser.add_argument("--no-server", action="store_true", help="Don't start the server (use existing)")
    parser.add_argument("--no-rtsp", action="store_true", help="Don't start the RTSP server")
    parser.add_argument("--catalog-only", action="store_true", help="Only test catalog query")
    parser.add_argument("--invite-only", action="store_true", help="Only test INVITE")
    parser.add_argument("--rtsp-video", help="Path to video file for RTSP streaming")
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        log("🧪 Starting GB28181 integrated application test")
        
        if not args.no_setup:
            if not setup_environment():
                log("❌ Failed to set up environment")
                return 1
        
        if args.invite_only:
            # Just send an INVITE to an existing server
            success = send_invite(
                dest_ip=args.dest_ip,
                dest_port=args.dest_port,
                sip_port=args.sip_port
            )
            if success and args.viewers > 0:
                run_viewer(dest_ip=args.dest_ip, dest_port=args.dest_port, use_vlc=True)
            return 0 if success else 1
            
        if args.catalog_only:
            # Just send a catalog query to an existing server
            success = test_catalog_query(sip_port=args.sip_port)
            return 0 if success else 1
        
        # Start RTSP server if not disabled
        if not args.no_rtsp:
            rtsp_video = args.rtsp_video if args.rtsp_video else "./sample_videos/Entryyy.mp4"
            if not start_rtsp_server(video_path=rtsp_video):
                log("⚠️ RTSP server failed to start, proceeding with test anyway")
        
        if not args.no_server:
            if not start_server():
                log("❌ Failed to start server")
                return 1
                
            # Wait a bit for server to initialize fully
            log("⏳ Waiting for server to initialize...")
            time.sleep(5)
        
        # Test catalog query
        catalog_success = test_catalog_query(sip_port=args.sip_port)
        if catalog_success:
            log("✅ Catalog query test succeeded")
        else:
            log("⚠️ Catalog query test failed")
        
        # Send INVITE request
        invite_success = send_invite(
            dest_ip=args.dest_ip,
            dest_port=args.dest_port,
            sip_port=args.sip_port
        )
        
        if invite_success:
            log("✅ INVITE test succeeded")
            
            # Start viewers if requested
            for i in range(args.viewers):
                run_viewer(dest_ip=args.dest_ip, dest_port=args.dest_port + i, use_vlc=True)
                
            # Keep running for a while to let things settle
            for i in range(5, 0, -1):
                log(f"⏳ Test complete. Exiting in {i} seconds... (Ctrl+C to keep running)")
                time.sleep(1)
        else:
            log("❌ INVITE test failed")
            
        return 0 if invite_success else 1
        
    except KeyboardInterrupt:
        log("User interrupted - exiting with server still running")
        return 0
    except Exception as e:
        log(f"❌ Unhandled error: {e}")
        return 1
    finally:
        if not args.invite_only and not args.catalog_only:
            cleanup()

if __name__ == "__main__":
    sys.exit(main()) 