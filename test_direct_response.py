#!/usr/bin/env python3

import sys
import os
import subprocess
import tempfile
import time

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from gb28181_sip_sender import GB28181SIPSender
import json

def test_service_catalog_send():
    """Test catalog sending using the same mechanism as the actual service"""
    
    # Load the actual configuration
    config_path = "config/config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print("=== Testing Service Catalog Send ===")
    print(f"Device ID: {config['sip']['device_id']}")
    print(f"Server: {config['sip']['server']}")
    print(f"Local IP: {config['sip'].get('local_ip', 'NOT SET')}")
    print(f"Contact IP: {config['sip'].get('contact_ip', 'NOT SET')}")
    print()
    
    # Create SIP sender instance
    sender = GB28181SIPSender(config)
    
    # Create a test catalog response
    device_id = config['sip']['device_id']
    catalog_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>999888</SN>
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
      <Name>Direct Test Camera 1</Name>
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
      <Name>Direct Test Camera 2</Name>
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
    
    print(f"Catalog XML length: {len(catalog_xml)} bytes")
    print("Sending catalog via service SIP sender...")
    
    # Start sender and send catalog
    sender.start()
    
    # Send to platform
    target_uri = f"sip:{config['sip']['server']}:{config['sip']['port']}"
    success = sender.send_catalog(catalog_xml, target_uri)
    
    if success:
        print("✅ Catalog queued for sending")
        # Give it time to send
        time.sleep(5)
    else:
        print("❌ Failed to queue catalog")
    
    sender.stop()
    
    return success

def test_manual_pjsua_send():
    """Test sending directly with pjsua to mimic what the service should be doing"""
    
    print("\n=== Testing Manual PJSUA Send ===")
    
    # Load config
    config_path = "config/config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    device_id = config['sip']['device_id']
    username = config['sip']['username']
    password = config['sip']['password']
    server = config['sip']['server']
    port = config['sip']['port']
    local_ip = config['sip'].get('local_ip', '172.31.7.94')
    
    # Simple catalog XML
    xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>888777</SN>
  <DeviceID>{device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>2</SumNum>
  <DeviceList Num="2">
    <Item>
      <DeviceID>{device_id}</DeviceID>
      <Name>Manual Test Device</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Restreamer-1.0</Model>
      <Status>ON</Status>
    </Item>
    <Item>
      <DeviceID>810000004650131000001</DeviceID>
      <Name>Manual Test Camera</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>File Stream</Model>
      <Status>ON</Status>
    </Item>
  </DeviceList>
</Response>"""
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_path = f.name
    
    try:
        # Build command for direct message send
        target_uri = f"sip:81000000462001888888@{server}:{port}"
        
        cmd = [
            "pjsua",
            "--id", f"sip:{device_id}@{server}",
            "--registrar", f"sip:{server}:{port}",
            "--realm", "*",
            "--username", username,
            "--password", password,
            "--local-port", "0",  # Random port
            "--null-audio",
            "--duration", "8",
            "--auto-quit",
            "--send-message", target_uri,
            "--message-content-type", "Application/MANSCDP+xml",
            "--message-content", f"@{temp_path}"
        ]
        
        print(f"Target URI: {target_uri}")
        print(f"XML length: {len(xml_content)} bytes")
        print("Executing pjsua command...")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=15
        )
        
        print(f"Return code: {result.returncode}")
        print("Output:")
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Manual pjsua send completed successfully")
            return True
        else:
            print("❌ Manual pjsua send failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass

if __name__ == "__main__":
    print("Testing catalog response mechanisms...")
    
    # Test 1: Service SIP sender
    service_ok = test_service_catalog_send()
    
    # Test 2: Manual pjsua
    manual_ok = test_manual_pjsua_send()
    
    print("\n=== Summary ===")
    print(f"Service SIP Sender: {'✅ OK' if service_ok else '❌ FAIL'}")
    print(f"Manual PJSUA Send: {'✅ OK' if manual_ok else '❌ FAIL'}")
    
    if service_ok and manual_ok:
        print("\n✅ Both methods appear to work!")
        print("The issue may be with:")
        print("  - Timing of responses")
        print("  - Platform expecting different message format")
        print("  - Authentication in SIP headers")
    else:
        print("\n❌ Communication issues detected") 