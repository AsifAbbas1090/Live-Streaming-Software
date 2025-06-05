#!/usr/bin/env python3
"""
Debug Catalog Sync Tool for GB28181 Restreamer
This tool tests the complete catalog generation and response flow to WVP platform.
"""

import sys
import os
import json
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def load_config():
    """Load configuration"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    with open(config_path) as f:
        return json.load(f)

def test_video_scanning(config):
    """Test video file scanning"""
    print("🔍 Testing Video File Scanning...")
    print("=" * 50)
    
    try:
        from file_scanner import scan_video_files, get_video_catalog
        
        stream_dir = config['stream_directory']
        print(f"📁 Scanning directory: {stream_dir}")
        
        # Scan videos
        videos = scan_video_files(stream_dir)
        catalog = get_video_catalog()
        
        print(f"✅ Scanning results:")
        print(f"   Videos returned by scan_video_files(): {len(videos)}")
        print(f"   Videos in get_video_catalog(): {len(catalog)}")
        
        if videos:
            print(f"\n📄 Sample video files:")
            for i, video in enumerate(videos[:5]):
                print(f"   {i+1}. {os.path.basename(video)}")
                print(f"      Path: {video}")
                print(f"      Exists: {os.path.exists(video)}")
                try:
                    size = os.path.getsize(video)
                    print(f"      Size: {size} bytes")
                except:
                    print(f"      Size: Unable to get size")
                print()
            
            if len(videos) > 5:
                print(f"   ... and {len(videos) - 5} more videos")
        else:
            print("❌ No videos found!")
            
        return len(videos) > 0, videos
        
    except Exception as e:
        print(f"❌ Error during video scanning: {e}")
        import traceback
        traceback.print_exc()
        return False, []

def test_catalog_generation(config, videos):
    """Test device catalog generation"""
    print("\n🏭 Testing Device Catalog Generation...")
    print("=" * 50)
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Create SIP client
        sip_client = SIPClient(config)
        
        print(f"📋 Device ID: {sip_client.device_id}")
        print(f"📂 Stream directory: {sip_client.config['stream_directory']}")
        
        # Generate catalog
        print("\n🔧 Generating device catalog...")
        catalog = sip_client.generate_device_catalog()
        
        print(f"✅ Catalog generation results:")
        print(f"   Device catalog entries: {len(catalog)}")
        print(f"   Catalog ready: {sip_client.catalog_ready}")
        
        if catalog:
            print(f"\n📋 Sample catalog entries:")
            for i, (channel_id, channel_info) in enumerate(list(catalog.items())[:5]):
                print(f"   {i+1}. Channel ID: {channel_id}")
                print(f"      Name: {channel_info.get('name', 'N/A')}")
                print(f"      Model: {channel_info.get('model', 'N/A')}")
                print(f"      Status: {channel_info.get('status', 'N/A')}")
                print(f"      Video Path: {channel_info.get('video_path', 'N/A')}")
                print()
            
            if len(catalog) > 5:
                print(f"   ... and {len(catalog) - 5} more channels")
        else:
            print("❌ No catalog entries generated!")
            
        return len(catalog) > 0, sip_client
        
    except Exception as e:
        print(f"❌ Error during catalog generation: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_catalog_xml_generation(sip_client):
    """Test XML response generation"""
    print("\n📄 Testing Catalog XML Generation...")
    print("=" * 50)
    
    try:
        # Simulate catalog query
        test_sn = "123456"
        query_msg = f"""MESSAGE sip:{sip_client.device_id}@{sip_client.server} SIP/2.0
Via: SIP/2.0/UDP {sip_client.server}:5060;branch=z9hG4bK-test123
From: <sip:wvp@{sip_client.server}>;tag=test123
To: <sip:{sip_client.device_id}@{sip_client.server}>
Call-ID: test-catalog-123@{sip_client.server}
CSeq: 1 MESSAGE
Content-Type: Application/MANSCDP+xml
Content-Length: 150

<?xml version="1.0" encoding="GB2312"?>
<Query>
  <CmdType>Catalog</CmdType>
  <SN>{test_sn}</SN>
  <DeviceID>{sip_client.device_id}</DeviceID>
</Query>"""
        
        print(f"🔧 Processing catalog query with SN: {test_sn}")
        
        # Generate response
        response_xml = sip_client.handle_catalog_query(query_msg)
        
        if response_xml:
            print(f"✅ XML response generated successfully!")
            print(f"   Response length: {len(response_xml)} bytes")
            
            # Parse and analyze the response
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(response_xml)
                cmd_type = root.find('CmdType').text if root.find('CmdType') is not None else "Unknown"
                response_sn = root.find('SN').text if root.find('SN') is not None else "Unknown"
                device_id = root.find('DeviceID').text if root.find('DeviceID') is not None else "Unknown"
                result = root.find('Result').text if root.find('Result') is not None else "Unknown"
                sum_num = root.find('SumNum').text if root.find('SumNum') is not None else "0"
                
                device_list = root.find('DeviceList')
                actual_devices = len(device_list.findall('Item')) if device_list is not None else 0
                
                print(f"\n📊 XML Response Analysis:")
                print(f"   CmdType: {cmd_type}")
                print(f"   SN: {response_sn} (expected: {test_sn})")
                print(f"   DeviceID: {device_id}")
                print(f"   Result: {result}")
                print(f"   SumNum: {sum_num}")
                print(f"   Actual Items: {actual_devices}")
                
                # Check for issues
                issues = []
                if str(response_sn) != str(test_sn):
                    issues.append(f"SN mismatch! Expected {test_sn}, got {response_sn}")
                if result != "OK":
                    issues.append(f"Non-OK result: {result}")
                if int(sum_num) != actual_devices:
                    issues.append(f"Device count mismatch! SumNum={sum_num}, actual={actual_devices}")
                if actual_devices == 0:
                    issues.append("No devices in catalog response!")
                
                if issues:
                    print(f"\n⚠️ Issues found:")
                    for issue in issues:
                        print(f"   - {issue}")
                else:
                    print(f"\n✅ XML response looks correct!")
                
                # Save response for inspection
                filename = f"debug_catalog_response_{test_sn}.xml"
                with open(filename, 'w') as f:
                    f.write(response_xml)
                print(f"\n💾 Saved response to {filename}")
                
                return actual_devices > 0, response_xml
                
            except ET.ParseError as e:
                print(f"❌ Invalid XML generated: {e}")
                print(f"Raw XML: {response_xml[:500]}...")
                return False, response_xml
                
        else:
            print("❌ No XML response generated!")
            return False, None
            
    except Exception as e:
        print(f"❌ Error during XML generation: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_sip_message_sending(config, xml_response):
    """Test sending the XML response via SIP"""
    print("\n📡 Testing SIP Message Sending...")
    print("=" * 50)
    
    try:
        from gb28181_sip_sender import GB28181SIPSender
        
        # Create SIP sender
        sender = GB28181SIPSender(config)
        sender.start()
        
        target_uri = f"sip:{config['sip']['server']}:{config['sip']['port']}"
        
        print(f"🎯 Target URI: {target_uri}")
        print(f"📦 Sending XML response ({len(xml_response)} bytes)...")
        
        start_time = time.time()
        success = sender.send_catalog(xml_response, target_uri)
        send_time = time.time() - start_time
        
        print(f"📊 Send result: {success}")
        print(f"⏱️ Send time: {send_time:.3f} seconds")
        
        # Give time for message to be sent
        time.sleep(2)
        sender.stop()
        
        return success
        
    except Exception as e:
        print(f"❌ Error during SIP sending: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_complete_flow():
    """Test the complete catalog flow"""
    print("🚀 Testing Complete Catalog Flow...")
    print("=" * 70)
    
    # Load config
    try:
        config = load_config()
        print(f"✅ Configuration loaded")
        print(f"   Device ID: {config['sip']['device_id']}")
        print(f"   Server: {config['sip']['server']}:{config['sip']['port']}")
        print(f"   Stream Directory: {config['stream_directory']}")
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return False
    
    # Test 1: Video scanning
    videos_found, videos = test_video_scanning(config)
    if not videos_found:
        print("\n❌ CRITICAL: No videos found. Cannot proceed with catalog generation.")
        return False
    
    # Test 2: Catalog generation
    catalog_generated, sip_client = test_catalog_generation(config, videos)
    if not catalog_generated:
        print("\n❌ CRITICAL: Catalog generation failed.")
        return False
    
    # Test 3: XML generation
    xml_generated, xml_response = test_catalog_xml_generation(sip_client)
    if not xml_generated:
        print("\n❌ CRITICAL: XML generation failed or produced empty catalog.")
        return False
    
    # Test 4: SIP sending
    sip_sent = test_sip_message_sending(config, xml_response)
    if not sip_sent:
        print("\n⚠️ WARNING: SIP message sending failed.")
    
    print("\n" + "=" * 70)
    print("📋 SUMMARY:")
    print(f"   ✅ Video scanning: {len(videos)} videos found")
    print(f"   ✅ Catalog generation: {len(sip_client.device_catalog)} channels created")
    print(f"   ✅ XML generation: Valid response created")
    print(f"   {'✅' if sip_sent else '⚠️'} SIP sending: {'Success' if sip_sent else 'Failed'}")
    
    if videos_found and catalog_generated and xml_generated:
        print("\n🎉 SUCCESS: Catalog generation flow is working correctly!")
        print("   The issue may be with SIP message delivery or timing.")
        print("   Try restarting your GB28181 Restreamer and checking WVP logs.")
        return True
    else:
        print("\n❌ FAILURE: Issues found in catalog generation flow.")
        return False

if __name__ == "__main__":
    success = test_complete_flow()
    sys.exit(0 if success else 1) 