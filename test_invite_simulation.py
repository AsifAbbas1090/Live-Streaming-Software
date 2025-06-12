#!/usr/bin/env python3
"""
INVITE Message Simulation Test
Simulates WVP platform sending SIP INVITE to test streaming functionality
"""

import socket
import time
import argparse
from datetime import datetime

def send_invite_test(target_ip, target_port, channel_id, dest_ip, dest_port):
    """
    Send a SIP INVITE message to test if the device responds
    This simulates what WVP platform should be doing
    """
    
    # Generate SIP message components
    timestamp = int(time.time())
    call_id = f"test-invite-{timestamp}@test-server"
    branch = f"z9hG4bK-test-{timestamp}"
    tag = f"testtag-{timestamp}"
    cseq = 1
    
    # FIXED: Use exact GB28181 SDP format that works
    sdp_content = f"""v=0
o=- {timestamp} 1 IN IP4 {dest_ip}
s=GB28181 Test Session
c=IN IP4 {dest_ip}
t=0 0
m=video {dest_port} RTP/AVP 96
a=rtpmap:96 H264/90000
a=recvonly
y=0000000001
f=v/2/25
"""

    # Build SIP INVITE message (what WVP platform should send)
    sip_invite = f"""INVITE sip:{channel_id}@{target_ip}:{target_port} SIP/2.0
Via: SIP/2.0/UDP {dest_ip}:5060;branch={branch}
Max-Forwards: 70
From: <sip:WVP-Platform@{dest_ip}:5060>;tag={tag}
To: <sip:{channel_id}@{target_ip}:{target_port}>
Call-ID: {call_id}
CSeq: {cseq} INVITE
Contact: <sip:{dest_ip}:5060>
Content-Type: application/sdp
User-Agent: WVP-Test-Client/1.0
Content-Length: {len(sdp_content)}

{sdp_content}"""

    print(f"\n🔔 INVITE Simulation Test")
    print(f"📍 Target: {target_ip}:{target_port}")
    print(f"📺 Channel: {channel_id}")
    print(f"📡 Stream destination: {dest_ip}:{dest_port}")
    print(f"⏰ Time: {datetime.now()}")
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10.0)  # 10 second timeout
        
        # Send INVITE
        message_bytes = sip_invite.encode('utf-8')
        print(f"\n📤 Sending INVITE message ({len(message_bytes)} bytes)...")
        
        bytes_sent = sock.sendto(message_bytes, (target_ip, target_port))
        print(f"✅ INVITE sent successfully: {bytes_sent} bytes")
        
        # Try to receive response
        print(f"⏳ Waiting for SIP response...")
        
        try:
            response, addr = sock.recvfrom(4096)
            response_text = response.decode('utf-8', errors='ignore')
            
            print(f"\n📨 Response received from {addr}:")
            print("=" * 50)
            print(response_text)
            print("=" * 50)
            
            # Analyze response
            if "200 OK" in response_text:
                print("🎉 SUCCESS: Device accepted INVITE and should start streaming!")
                return True
            elif "100 Trying" in response_text:
                print("⏳ Device is processing INVITE (100 Trying)")
                return True
            elif "180 Ringing" in response_text:
                print("📞 Device is ringing (180 Ringing)")
                return True
            elif "400" in response_text:
                print("❌ FAIL: Bad Request (400) - SDP format issue")
                if "Bad SDP" in response_text:
                    print("   🔧 SDP format is incompatible with PJSUA")
                return False
            elif "404" in response_text:
                print("❌ FAIL: Device/Channel not found (404)")
                return False
            elif "486 Busy" in response_text:
                print("📞 Device is busy (486)")
                return False
            else:
                print(f"⚠️ Unexpected response")
                return False
                
        except socket.timeout:
            print("⏰ TIMEOUT: No response received from device")
            print("   This suggests:")
            print("   1. Device may not be listening on specified port")
            print("   2. Firewall may be blocking the connection")
            print("   3. Device may not handle INVITE messages properly")
            return False
            
    except Exception as e:
        print(f"❌ ERROR sending INVITE: {e}")
        return False
        
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser(description="Test SIP INVITE to GB28181 device")
    parser.add_argument("--device-ip", default="127.0.0.1", 
                       help="Device IP address (default: 127.0.0.1)")
    parser.add_argument("--device-port", type=int, default=5080,
                       help="Device SIP port (default: 5080)")
    parser.add_argument("--channel", default="810000004650131000001",
                       help="Channel ID to test (default: 810000004650131000001)")
    parser.add_argument("--dest-ip", default="127.0.0.1",
                       help="Stream destination IP (default: 127.0.0.1)")
    parser.add_argument("--dest-port", type=int, default=5004,
                       help="Stream destination port (default: 5004)")
    
    args = parser.parse_args()
    
    print("🧪 GB28181 Device INVITE Test")
    print("=" * 40)
    
    # Run the test
    success = send_invite_test(
        args.device_ip, 
        args.device_port, 
        args.channel,
        args.dest_ip,
        args.dest_port
    )
    
    print("\n" + "=" * 40)
    if success:
        print("✅ RESULT: Device appears to handle INVITE messages correctly")
        print("   This suggests the WVP platform issue is likely:")
        print("   1. WVP not sending INVITE messages")
        print("   2. Network configuration blocking INVITE")
        print("   3. WVP platform misconfiguration")
    else:
        print("❌ RESULT: Device did not respond properly to INVITE")
        print("   This suggests:")
        print("   1. Device may need debugging")
        print("   2. INVITE handling may have issues")
        print("   3. Network connectivity problems")
        print("   4. SDP format incompatibility")
    
    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Check your device logs during this test")
    print(f"   2. Verify if INVITE was received and processed")
    print(f"   3. If device works, focus on WVP platform configuration")

if __name__ == "__main__":
    main() 