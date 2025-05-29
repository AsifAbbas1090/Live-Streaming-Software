#!/usr/bin/env python3
"""
GB28181 Test Suite

This script provides a comprehensive test environment for GB28181 restreamer,
setting up a local testing environment and verifying functionality.
"""

import os
import sys
import argparse
import signal
import time
import subprocess
import json
import socket
import threading
import re  # For detect_sip_port

# Test modes
MODE_SEND_INVITE = "invite"
MODE_START_SERVER = "server"
MODE_FULL_TEST = "full"

# Global variables for process management
server_process = None
server_log_file = "./server_logs.txt"

def setup_environment():
    """Setup the testing environment"""
    print("\n🔧 Setting up test environment...")
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
        print("✅ Created logs directory")
    
    # Check for config file
    if not os.path.exists('config/config.json'):
        print("❌ config.json not found! Please create one first.")
        return False
    
    # Check for sample videos
    if not os.path.exists('sample_videos') or not os.listdir('sample_videos'):
        print("❌ No sample videos found in sample_videos/ directory")
        return False
        
    print("✅ Environment looks good!")
    return True

def detect_sip_port():
    """Detect which port the SIP server is running on by parsing logs"""
    try:
        # First check if we have a server log file
        if os.path.exists(server_log_file):
            with open(server_log_file, 'r') as f:
                log_content = f.read()
                port_match = re.search(r"Server started successfully on port (\d+)", log_content)
                if port_match:
                    return int(port_match.group(1))
        
        # Default to 5060
        return 5060
    except Exception as e:
        print(f"⚠️ Warning: Could not detect SIP port: {e}")
        return 5060

def send_invite(dest_ip="127.0.0.1", dest_port=9000, sip_server="127.0.0.1", sip_port=None, device_id=None, use_tcp=True):
    """Send an INVITE request to the SIP server"""
    if sip_port is None:
        sip_port = detect_sip_port()
    
    print(f"\n📨 Sending INVITE request to {sip_server}:{sip_port}")
    
    # Try to load device ID from config if not provided
    if not device_id:
        try:
            with open('config/config.json', 'r') as f:
                config = json.load(f)
                device_id = config['sip']['device_id']
                print(f"ℹ️ Using device ID from config: {device_id}")
        except Exception as e:
            print(f"❌ Failed to load device ID from config: {e}")
            device_id = "34020000001320000001"
            print(f"ℹ️ Using default device ID: {device_id}")
    
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

    # Determine transport protocol
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
        if use_tcp:
            # Send via TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                print(f"🔄 Connecting to {sip_server}:{sip_port} via TCP...")
                sock.connect((sip_server, int(sip_port)))
                sock.sendall(invite_msg.encode())
                print("✅ TCP connection established and INVITE sent")
                
                # Wait for response
                print("🔄 Waiting for response...")
                response = sock.recv(4096)
                if response:
                    print(f"📩 Received response: {response.decode()[:100]}...")
        else:
            # Send via UDP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(invite_msg.encode(), (sip_server, int(sip_port)))
                print("✅ UDP packet sent")
        
        print("\n▶️ To view the stream, run in another terminal:")
        print(f"  cvlc rtp://{dest_ip}:{dest_port}")
        
        # Also create/update the SDP file for proper VLC playback
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
        print("✅ Created SDP file. You can also use: vlc invite.sdp")
        
        return True
    except Exception as e:
        print(f"❌ Failed to send INVITE: {e}")
        return False

def start_server():
    """Start the GB28181 restreamer server"""
    print("\n🚀 Starting GB28181 Restreamer server...")
    
    # Ensure any previous server is stopped
    global server_process
    if server_process and server_process.poll() is None:
        server_process.terminate()
        time.sleep(1)
    
    # Try to kill any existing processes
    try:
        subprocess.run(["pkill", "-f", "python3 src/main.py"], stderr=subprocess.DEVNULL)
        time.sleep(1)
    except:
        pass
    
    # Start the server process
    try:
        # Clear previous log file
        with open(server_log_file, 'w') as f:
            f.write("")
        
        server_process = subprocess.Popen(
            ["python3", "src/main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"✅ Server started with PID {server_process.pid}")
        
        # Monitor the output
        print("\n📋 Server output:")
        print("=" * 80)
        
        # Read output for a few seconds and capture to log file
        start_time = time.time()
        with open(server_log_file, 'a') as log_file:
            while time.time() - start_time < 5:  # Read for 5 seconds
                line = server_process.stdout.readline()
                if line:
                    print(line.strip())
                    log_file.write(line)
                if server_process.poll() is not None:
                    break
                
        print("=" * 80)
        
        # Check if still running
        if server_process.poll() is None:
            print("✅ Server is running")
            return server_process
        else:
            print(f"❌ Server exited with code: {server_process.returncode}")
            return None
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return None

def run_vlc(dest_ip="127.0.0.1", dest_port=9000):
    """Start VLC to receive the stream"""
    print(f"\n📺 Starting VLC to receive stream from rtp://{dest_ip}:{dest_port}")
    
    try:
        # First try using the SDP file for better compatibility
        if os.path.exists('invite.sdp'):
            vlc_process = subprocess.Popen(
                ["vlc", "invite.sdp"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        else:
            vlc_process = subprocess.Popen(
                ["cvlc", f"rtp://{dest_ip}:{dest_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        
        print(f"✅ VLC started with PID {vlc_process.pid}")
        return vlc_process
    except Exception as e:
        print(f"❌ Failed to start VLC: {e}")
        return None

def full_test(dest_ip="127.0.0.1", dest_port=9000, sip_port=None):
    """Run a full test of the GB28181 restreamer"""
    global server_process
    vlc_process = None
    
    # Set up signal handler
    def signal_handler(sig, frame):
        print("\n🛑 Shutting down test...")
        if server_process:
            server_process.terminate()
        if vlc_process:
            vlc_process.terminate()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check environment
    if not setup_environment():
        return False
    
    # Start server
    server_process = start_server()
    if not server_process:
        return False
    
    # Give the server time to initialize
    print("\n⏳ Waiting for server to initialize...")
    time.sleep(3)
    
    # Send INVITE
    if not send_invite(dest_ip=dest_ip, dest_port=dest_port, sip_port=sip_port):
        server_process.terminate()
        return False
    
    # Start VLC
    vlc_process = run_vlc(dest_ip=dest_ip, dest_port=dest_port)
    
    print("\n✅ Test setup complete!")
    print("🔍 Check if video appears in VLC window")
    print("📝 Press Ctrl+C to stop the test\n")
    
    try:
        while True:
            # Check if server is still running
            if server_process.poll() is not None:
                print(f"❌ Server exited with code: {server_process.returncode}")
                break
                
            # Check if VLC is still running
            if vlc_process and vlc_process.poll() is not None:
                print(f"❌ VLC exited with code: {vlc_process.returncode}")
                break
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    finally:
        # Clean up
        if server_process:
            server_process.terminate()
        if vlc_process:
            vlc_process.terminate()
    
    return True

def main():
    """Main entry point for the test suite"""
    parser = argparse.ArgumentParser(description="GB28181 Restreamer Test Suite")
    parser.add_argument("--mode", choices=[MODE_SEND_INVITE, MODE_START_SERVER, MODE_FULL_TEST], 
                      default=MODE_FULL_TEST, help="Test mode")
    parser.add_argument("--sip-server", default="127.0.0.1", help="SIP server address")
    parser.add_argument("--sip-port", type=int, help="SIP server port")
    parser.add_argument("--dest-ip", default="127.0.0.1", help="Destination IP address")
    parser.add_argument("--dest-port", type=int, default=9000, help="Destination port")
    parser.add_argument("--device-id", help="Device ID for INVITE request")
    parser.add_argument("--udp", action="store_true", help="Use UDP instead of TCP")
    parser.add_argument("--streams", type=int, help="Number of concurrent streams to test")
    
    args = parser.parse_args()

    # Execute test based on mode and args
    if args.streams:
        # Multiple streams test using test_multiple_streams.py
        print(f"\n================================================================================")
        print(f"📡 GB28181 Restreamer Multiple Streams Test ({args.streams} streams)")
        print(f"================================================================================")
        
        # First ensure environment is ready
        if not setup_environment():
            sys.exit(1)

        # Run the multiple streams test
        try:
            subprocess.run([sys.executable, "test_multiple_streams.py", "--streams", str(args.streams)], check=True)
            print("\n✅ Multiple streams test completed")
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Multiple streams test failed: {e}")
            sys.exit(1)
    elif args.mode == MODE_SEND_INVITE:
        # Send INVITE request
        send_invite(args.dest_ip, args.dest_port, args.sip_server, args.sip_port, args.device_id, not args.udp)
    elif args.mode == MODE_START_SERVER:
        # Start the server
        server = start_server()
        if not server:
            sys.exit(1)
        
        print("\n🔄 Server is running. Press Ctrl+C to stop.")
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
    else:
        # Full test
        full_test(args.dest_ip, args.dest_port, args.sip_port)

    print("\n✅ Test completed")

if __name__ == "__main__":
    main() 