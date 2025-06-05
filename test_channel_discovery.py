#!/usr/bin/env python3
"""
Channel Discovery Test Script
Tests catalog generation and channel discovery for WVP platform compatibility.
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_video_scanning():
    """Test video file scanning functionality"""
    print("🔍 Testing Video File Scanning...")
    print("-" * 40)
    
    try:
        from file_scanner import scan_video_files, get_video_catalog, get_catalog_summary
        
        # Load config to get directory
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        stream_dir = config.get('stream_directory', './recordings')
        print(f"📁 Scanning directory: {stream_dir}")
        
        # Scan for videos
        videos = scan_video_files(stream_dir)
        catalog = get_video_catalog()
        summary = get_catalog_summary()
        
        print(f"📊 Results:")
        print(f"  Videos found: {len(videos)}")
        print(f"  Catalog size: {len(catalog)}")
        print(f"  Summary: {summary}")
        
        # Show first few videos
        if videos:
            print(f"\n📄 Sample videos:")
            for i, video in enumerate(videos[:5]):
                print(f"  {i+1}. {os.path.basename(video)}")
            if len(videos) > 5:
                print(f"  ... and {len(videos) - 5} more")
        
        return len(videos) > 0
        
    except Exception as e:
        print(f"❌ Error testing video scanning: {e}")
        return False

def test_catalog_generation():
    """Test device catalog generation"""
    print("\n🏗️  Testing Catalog Generation...")
    print("-" * 40)
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        print(f"📱 Device ID: {config.get('device_id', 'N/A')}")
        print(f"🔗 RTSP Sources: {config.get('rtsp_sources', [])}")
        
        # Create SIP client (without starting it)
        client = SIPClient(config)
        
        # Generate catalog
        print("\n🔄 Generating device catalog...")
        client.generate_device_catalog()
        
        catalog = client.device_catalog
        print(f"✅ Generated {len(catalog)} channels")
        
        # Display channels
        if catalog:
            print("\n📋 Generated Channels:")
            for channel_id, channel_info in catalog.items():
                print(f"  🎥 {channel_id}: {channel_info['name']}")
                print(f"      Status: {channel_info['status']}")
                print(f"      Model: {channel_info['model']}")
                print(f"      Path: {channel_info['path']}")
                print()
        else:
            print("❌ No channels generated!")
            
        return len(catalog) > 0
        
    except Exception as e:
        print(f"❌ Error testing catalog generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_catalog_xml_response():
    """Test XML catalog response generation"""
    print("\n📝 Testing XML Catalog Response...")
    print("-" * 40)
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        # Create SIP client
        client = SIPClient(config)
        client.generate_device_catalog()
        
        # Generate XML response
        test_sn = "123456"
        xml_response = client._generate_catalog_response(test_sn)
        
        if xml_response:
            print("✅ Generated XML catalog response")
            print(f"📏 Response length: {len(xml_response)} characters")
            
            # Save to file for inspection
            with open("test_catalog_response.xml", "w", encoding="utf-8") as f:
                f.write(xml_response)
            print("💾 Saved response to: test_catalog_response.xml")
            
            # Show snippet
            print("\n📄 Response snippet:")
            lines = xml_response.split('\n')
            for line in lines[:10]:
                print(f"  {line}")
            if len(lines) > 10:
                print(f"  ... ({len(lines) - 10} more lines)")
                
            return True
        else:
            print("❌ Failed to generate XML response")
            return False
            
    except Exception as e:
        print(f"❌ Error testing XML response: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_catalog_query_handling():
    """Test handling of catalog queries like WVP sends"""
    print("\n💬 Testing Catalog Query Handling...")
    print("-" * 40)
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        # Create SIP client
        client = SIPClient(config)
        client.generate_device_catalog()
        
        # Test Catalog query (like WVP sends)
        catalog_query = """MESSAGE sip:81000000465001800001@192.168.96.1:13199 SIP/2.0
Call-ID: test-call-id-123
CSeq: 272 MESSAGE
From: <sip:81000000462001888888@81000000>;tag=test-tag
To: <sip:81000000465001800001@192.168.96.1:13199>
Via: SIP/2.0/UDP 0.0.0.0:5060;rport;branch=test-branch
Max-Forwards: 70
User-Agent: WVP-Pro
Content-Type: Application/MANSCDP+xml
Content-Length: 153

<?xml version="1.0" encoding="GB2312"?>
<Query>
<CmdType>Catalog</CmdType>
<SN>275474</SN>
<DeviceID>81000000465001800001</DeviceID>
</Query>"""
        
        print("📥 Testing Catalog query...")
        response = client.handle_catalog_query(catalog_query)
        
        if response:
            print("✅ Catalog query handled successfully")
            print(f"📏 Response length: {len(response)} characters")
            return True
        else:
            print("❌ Catalog query handling failed")
            return False
            
        # Test DeviceStatus query (from client's logs)
        device_status_query = """MESSAGE sip:81000000465001800001@192.168.96.1:13199 SIP/2.0
Call-ID: test-call-id-456
CSeq: 272 MESSAGE
From: <sip:81000000462001888888@81000000>;tag=test-tag
To: <sip:81000000465001800001@192.168.96.1:13199>
Via: SIP/2.0/UDP 0.0.0.0:5060;rport;branch=test-branch
Max-Forwards: 70
User-Agent: WVP-Pro
Content-Type: Application/MANSCDP+xml
Content-Length: 153

<?xml version="1.0" encoding="GB2312"?>
<Query>
<CmdType>DeviceStatus</CmdType>
<SN>275474</SN>
<DeviceID>81000000465001800001</DeviceID>
</Query>"""
        
        print("\n📥 Testing DeviceStatus query...")
        # For now, DeviceStatus should be handled by handle_device_info_query
        # This is the type the client was seeing in their logs
        print("ℹ️  DeviceStatus queries should be handled separately from Catalog queries")
        
    except Exception as e:
        print(f"❌ Error testing query handling: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all channel discovery tests"""
    print("🧪 GB28181 Channel Discovery Test Suite")
    print("=" * 60)
    
    tests = [
        ("Video File Scanning", test_video_scanning),
        ("Catalog Generation", test_catalog_generation),
        ("XML Response Generation", test_catalog_xml_response),
        ("Query Handling", test_catalog_query_handling)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\n🎯 Summary: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All channel discovery tests passed!")
        print("📋 Your device should now show channels in WVP platform!")
    else:
        print("⚠️  Some tests failed - channels may not appear in WVP platform")
        print("💡 Check the logs above for specific issues")
    
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    sys.exit(main()) 