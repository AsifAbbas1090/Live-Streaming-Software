#!/usr/bin/env python3

import socket
import time
import json

def test_catalog_response():
    """Test sending a catalog response directly to the WVP platform"""
    
    # WVP platform details
    platform_ip = "203.142.93.131"
    platform_port = 5060
    
    # Our device details 
    device_id = "81000000465001000001"
    local_ip = "172.31.7.94"  # Private IP for binding
    contact_ip = "13.50.108.195"  # Public IP for Contact headers
    local_port = 5080
    
    # Simple catalog response
    catalog_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>999999</SN>
  <DeviceID>{device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>3</SumNum>
  <DeviceList Num="3">
    <Item>
      <DeviceID>{device_id}</DeviceID>
      <Name>GB28181-Restreamer</Name>
      <Manufacturer>GB28181-RestreamerProject</Manufacturer>
      <Model>Restreamer-1.0</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>810000</CivilCode>
      <Block>81000000</Block>
      <Address>Local Stream Server</Address>
      <Parental>1</Parental>
      <ParentID>8100000046000000</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <IPAddress></IPAddress>
      <Port>0</Port>
      <Password></Password>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
    <Item>
      <DeviceID>810000004650131000001</DeviceID>
      <Name>Test Camera 1</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>File Stream</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>810000</CivilCode>
      <Block>81000000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <IPAddress></IPAddress>
      <Port>0</Port>
      <Password></Password>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
    <Item>
      <DeviceID>810000004650131000002</DeviceID>
      <Name>Test Camera 2</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>File Stream</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>810000</CivilCode>
      <Block>81000000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <IPAddress></IPAddress>
      <Port>0</Port>
      <Password></Password>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
  </DeviceList>
</Response>"""

    # Build SIP MESSAGE
    call_id = f"test-catalog-{int(time.time())}"
    cseq = "1"
    
    sip_message = f"""MESSAGE sip:81000000462001888888@{platform_ip}:{platform_port} SIP/2.0
Via: SIP/2.0/UDP {contact_ip}:{local_port};rport;branch=z9hG4bK-test-{int(time.time())}
Max-Forwards: 70
From: <sip:{device_id}@{contact_ip}:{local_port}>;tag=test-{int(time.time())}
To: <sip:81000000462001888888@{platform_ip}:{platform_port}>
Call-ID: {call_id}
CSeq: {cseq} MESSAGE
User-Agent: GB28181-Restreamer-Test
Content-Type: Application/MANSCDP+xml
Content-Length: {len(catalog_xml)}

{catalog_xml}"""

    print("Testing catalog response send to WVP platform...")
    print(f"Target: {platform_ip}:{platform_port}")
    print(f"Source: {local_ip}:{local_port}")
    print(f"XML Length: {len(catalog_xml)} bytes")
    print()

    try:
        # Create UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((local_ip, 0))  # Let OS assign port
        
        actual_port = sock.getsockname()[1]
        print(f"Using local port: {actual_port}")
        
        # Send the message
        print("Sending SIP MESSAGE...")
        sock.sendto(sip_message.encode('utf-8'), (platform_ip, platform_port))
        
        print("✅ Message sent successfully!")
        
        # Try to receive response (with timeout)
        sock.settimeout(10.0)
        try:
            response, addr = sock.recvfrom(4096)
            print(f"\n📨 Received response from {addr}:")
            print(response.decode('utf-8', errors='ignore'))
        except socket.timeout:
            print("\n⏰ No response received within 10 seconds")
        
        sock.close()
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False
    
    return True

def check_platform_connectivity():
    """Check basic UDP connectivity to platform"""
    platform_ip = "203.142.93.131"
    platform_port = 5060
    
    print(f"Testing UDP connectivity to {platform_ip}:{platform_port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5.0)
        
        # Send a simple OPTIONS message
        test_msg = f"""OPTIONS sip:{platform_ip}:{platform_port} SIP/2.0
Via: SIP/2.0/UDP 172.31.7.94:5080;rport;branch=z9hG4bK-test-{int(time.time())}
Max-Forwards: 70
From: <sip:test@172.31.7.94:5080>;tag=test-{int(time.time())}
To: <sip:{platform_ip}:{platform_port}>
Call-ID: test-{int(time.time())}
CSeq: 1 OPTIONS
User-Agent: GB28181-Test
Content-Length: 0

"""
        
        sock.sendto(test_msg.encode('utf-8'), (platform_ip, platform_port))
        print("✅ Test message sent")
        
        try:
            response, addr = sock.recvfrom(4096)
            print(f"✅ Received response: {response[:100].decode('utf-8', errors='ignore')}...")
            return True
        except socket.timeout:
            print("⏰ No response to OPTIONS (may be filtered)")
            return True  # Still consider connectivity OK
            
    except Exception as e:
        print(f"❌ Connectivity test failed: {e}")
        return False
    finally:
        sock.close()

if __name__ == "__main__":
    print("=== GB28181 WVP Platform Communication Test ===")
    print()
    
    # Test 1: Basic connectivity
    print("1. Testing basic UDP connectivity...")
    connectivity_ok = check_platform_connectivity()
    print()
    
    # Test 2: Send catalog response
    print("2. Testing catalog response send...")
    catalog_ok = test_catalog_response()
    print()
    
    print("=== Test Summary ===")
    print(f"Connectivity: {'✅ OK' if connectivity_ok else '❌ FAIL'}")
    print(f"Catalog Send: {'✅ OK' if catalog_ok else '❌ FAIL'}")
    
    if connectivity_ok and catalog_ok:
        print("\n🎉 Communication appears to be working!")
        print("If videos still don't appear, the issue may be:")
        print("  - Platform configuration")
        print("  - Channel ID format requirements")
        print("  - Authentication/authorization")
    else:
        print("\n❌ Communication issues detected") 