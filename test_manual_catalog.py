#!/usr/bin/env python3

import socket
import time
import random

def send_catalog_query():
    """Send a manual catalog query to test the service response"""
    
    # Service details
    device_ip = "172.31.7.94"  # Private IP where service is bound
    device_port = 5080
    
    # Generate unique identifiers
    call_id = f"test-{int(time.time())}-{random.randint(1000, 9999)}"
    branch = f"z9hG4bK-test-{int(time.time())}"
    tag = f"test-{int(time.time())}"
    sn = random.randint(100000, 999999)
    cseq = random.randint(1, 1000)
    
    # Create catalog query XML
    catalog_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Query>
<CmdType>Catalog</CmdType>
<SN>{sn}</SN>
<DeviceID>81000000465001000001</DeviceID>
</Query>"""
    
    # Create SIP MESSAGE
    sip_message = f"""MESSAGE sip:81000000465001000001@{device_ip}:{device_port} SIP/2.0
Via: SIP/2.0/UDP 127.0.0.1:6060;rport;branch={branch}
Max-Forwards: 70
From: <sip:test@127.0.0.1:6060>;tag={tag}
To: <sip:81000000465001000001@{device_ip}:{device_port}>
Call-ID: {call_id}
CSeq: {cseq} MESSAGE
User-Agent: Manual-Test
Content-Type: Application/MANSCDP+xml
Content-Length: {len(catalog_xml)}

{catalog_xml}"""
    
    print(f"=== Manual Catalog Query Test ===")
    print(f"Target: {device_ip}:{device_port}")
    print(f"SN: {sn}")
    print(f"Call-ID: {call_id}")
    print()
    
    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(10)  # 10 second timeout
        
        # Send the query
        print("📤 Sending catalog query...")
        sock.sendto(sip_message.encode('utf-8'), (device_ip, device_port))
        print("✅ Query sent successfully")
        
        # Try to receive response
        print("📥 Waiting for response...")
        try:
            data, addr = sock.recvfrom(4096)
            response = data.decode('utf-8')
            print(f"✅ Received response from {addr}")
            print("Response preview:")
            print(response[:500])
            
            if "200 OK" in response:
                print("\n✅ Got 200 OK response - service acknowledged the query")
            else:
                print(f"\n⚠️ Unexpected response: {response[:100]}")
                
        except socket.timeout:
            print("⏰ No response received (timeout)")
            print("This could mean:")
            print("  - Service not listening on UDP port")
            print("  - Response sent to different address")
            print("  - Service processing but not responding")
            
        sock.close()
        
        # Check if catalog response file was created
        print(f"\n📁 Checking for catalog response file...")
        import os
        response_file = f"catalog_response_sn_{sn}.xml"
        time.sleep(2)  # Give some time for file to be created
        
        if os.path.exists(response_file):
            print(f"✅ Catalog response file created: {response_file}")
            with open(response_file, 'r') as f:
                content = f.read()
                print(f"Response size: {len(content)} bytes")
                if "SumNum" in content:
                    import re
                    sum_match = re.search(r'<SumNum>(\d+)</SumNum>', content)
                    if sum_match:
                        count = sum_match.group(1)
                        print(f"Device count in response: {count}")
        else:
            print(f"❌ No catalog response file found: {response_file}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    send_catalog_query() 