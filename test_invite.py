#!/usr/bin/env python3
"""
GB28181 INVITE Request Simulator
This script simulates a simple GB28181 SIP INVITE request to test the restreamer's
ability to parse SDP and stream video to the specified destination.
"""

import socket
import time
import argparse
import os

def send_invite_request(sip_server, sip_port, dest_ip, dest_port, device_id="34020000001320000001", use_tcp=True):
    """
    Send a GB28181 INVITE request to the SIP server.
    
    Args:
        sip_server: SIP server IP address
        sip_port: SIP server port
        dest_ip: Destination IP for video streaming
        dest_port: Destination port for video streaming
        device_id: GB28181 device ID (from config)
        use_tcp: Whether to use TCP (True) or UDP (False)
    """
    # Format the SDP content with the streaming destination
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

    print(f"[TEST] Sending INVITE via {transport} to {sip_server}:{sip_port}")
    print(f"[TEST] Video will be streamed to {dest_ip}:{dest_port}")
    
    try:
        if use_tcp:
            # Send via TCP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((sip_server, int(sip_port)))
                sock.sendall(invite_msg.encode())
                print("[TEST] TCP connection established and INVITE sent")
        else:
            # Send via UDP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(invite_msg.encode(), (sip_server, int(sip_port)))
                print("[TEST] UDP packet sent")
        
        print("[TEST] INVITE sent. Run VLC to receive the stream:")
        print(f"[TEST] cvlc rtp://{dest_ip}:{dest_port}")
    except Exception as e:
        print(f"[ERROR] Failed to send INVITE: {e}")

def main():
    parser = argparse.ArgumentParser(description='GB28181 INVITE Request Simulator')
    parser.add_argument('--sip-server', default='127.0.0.1', help='SIP server IP')
    parser.add_argument('--sip-port', default=5060, type=int, help='SIP server port')
    parser.add_argument('--dest-ip', default='127.0.0.1', help='Destination IP for streaming')
    parser.add_argument('--dest-port', default=9000, type=int, help='Destination port for streaming')
    parser.add_argument('--device-id', help='GB28181 device ID')
    parser.add_argument('--udp', action='store_true', help='Use UDP instead of TCP')
    
    args = parser.parse_args()
    
    # Use device ID from config if not provided
    device_id = args.device_id
    if not device_id:
        try:
            import json
            with open('config/config.json', 'r') as f:
                config = json.load(f)
                device_id = config['sip']['device_id']
        except Exception as e:
            print(f"[ERROR] Failed to load device ID from config: {e}")
            device_id = "34020000001320000001"
    
    send_invite_request(args.sip_server, args.sip_port, args.dest_ip, args.dest_port, device_id, not args.udp)

if __name__ == "__main__":
    main() 