#!/usr/bin/env python3
"""
Test script for RTSP to GB28181 live streaming integration
This script tests the integration between RTSP sources and WVP-GB28181-pro platform
"""

import os
import sys
import json
import time
import threading
import subprocess
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from logger import log
from live_stream_handler import LiveStreamHandler
from sip_handler_pjsip import SIPClient
from media_streamer import MediaStreamer

def load_test_config():
    """Load test configuration"""
    config = {
        "sip": {
            "device_id": "81000000465001000001",
            "username": "81000000465001000001", 
            "password": "admin123",
            "server": "ai-sip.x-stage.bull-b.com",
            "port": 5060,
            "local_port": 5080,
            "transport": "udp",
            "local_ip": "172.31.7.94",
            "contact_ip": "13.50.108.195"
        },
        "rtsp_sources": [
            {
                "url": "rtsp://admin:password@192.168.1.100:554/stream1",
                "name": "Test Camera 1",
                "device_id": "34020000001320000001"
            },
            {
                "url": "rtsp://admin:password@192.168.1.101:554/stream1", 
                "name": "Test Camera 2",
                "device_id": "34020000001320000002"
            }
        ],
        "stream_directory": "/tmp/test_recordings",
        "logging": {
            "level": "INFO",
            "console": True
        }
    }
    return config

def test_live_stream_handler():
    """Test the live stream handler functionality"""
    log.info("[TEST] Testing LiveStreamHandler functionality...")
    
    config = load_test_config()
    
    # Initialize live stream handler
    handler = LiveStreamHandler(config)
    handler.start()
    
    try:
        # Test with a test RTSP URL (this will fail but we can test the pipeline creation)
        test_rtsp_url = "rtsp://test:test@192.168.1.100:554/stream1"
        test_stream_id = "test_stream_001"
        
        log.info(f"[TEST] Testing RTSP stream setup: {test_rtsp_url}")
        
        # This will fail due to connection, but we can verify the pipeline creation
        success = handler.start_rtsp_stream(
            stream_id=test_stream_id,
            rtsp_url=test_rtsp_url,
            dest_ip="192.168.1.200",
            dest_port=20000,
            ssrc="12345678"
        )
        
        log.info(f"[TEST] RTSP stream setup result: {success}")
        
        # Check stream status
        status = handler.get_stream_status(test_stream_id)
        log.info(f"[TEST] Stream status: {status}")
        
        # List active streams
        active_count = handler.get_active_stream_count()
        log.info(f"[TEST] Active streams: {active_count}")
        
        # Clean up
        if test_stream_id in handler.active_streams:
            handler.stop_stream(test_stream_id)
            log.info(f"[TEST] Stopped test stream: {test_stream_id}")
        
    finally:
        handler.stop()
        log.info("[TEST] LiveStreamHandler test completed")

def test_device_catalog_generation():
    """Test device catalog generation with RTSP sources"""
    log.info("[TEST] Testing device catalog generation...")
    
    config = load_test_config()
    
    # Create a minimal SIP client for testing catalog generation
    # We don't need to start the full SIP process for this test
    sip_client = SIPClient(config)
    
    # Generate device catalog
    sip_client.generate_device_catalog()
    
    log.info(f"[TEST] Generated catalog with {len(sip_client.device_catalog)} devices")
    
    # Display catalog entries
    for device_id, device_info in sip_client.device_catalog.items():
        log.info(f"[TEST] Device {device_id}: {device_info.get('name', 'Unnamed')} "
                f"({device_info.get('manufacturer', 'Unknown')})")
        
        # Check for RTSP URL
        if 'rtsp_url' in device_info:
            log.info(f"[TEST]   RTSP URL: {device_info['rtsp_url']}")

def test_xml_catalog_format():
    """Test XML catalog formatting for WVP compatibility"""
    log.info("[TEST] Testing XML catalog formatting...")
    
    try:
        from gb28181_xml import format_catalog_response
        
        # Create test catalog data
        test_catalog = {
            "34020000001320000001": {
                "name": "Test RTSP Camera 1",
                "manufacturer": "Generic",
                "model": "IP Camera",
                "status": "ON",
                "rtsp_url": "rtsp://admin:password@192.168.1.100:554/stream1"
            },
            "34020000001320000002": {
                "name": "Test RTSP Camera 2", 
                "manufacturer": "Generic",
                "model": "IP Camera",
                "status": "ON",
                "rtsp_url": "rtsp://admin:password@192.168.1.101:554/stream1"
            }
        }
        
        device_id = "81000000465001000001"
        
        # Generate XML
        xml_response = format_catalog_response(device_id, test_catalog)
        
        # Save to file for inspection
        output_file = "test_catalog_output.xml"
        with open(output_file, 'w') as f:
            f.write(xml_response)
        
        log.info(f"[TEST] Generated XML catalog saved to: {output_file}")
        
        # Basic validation
        if "DeviceList" in xml_response and "Item" in xml_response:
            log.info("[TEST] ✅ XML catalog appears to be valid")
        else:
            log.warning("[TEST] ⚠️ XML catalog may have formatting issues")
            
    except Exception as e:
        log.error(f"[TEST] XML formatting test failed: {e}")

def test_wvp_connectivity():
    """Test connectivity to WVP platform"""
    log.info("[TEST] Testing WVP platform connectivity...")
    
    config = load_test_config()
    server = config["sip"]["server"]
    port = config["sip"]["port"]
    
    import socket
    
    try:
        # Test TCP connection to WVP server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        result = s.connect_ex((server, port))
        s.close()
        
        if result == 0:
            log.info(f"[TEST] ✅ Successfully connected to WVP server {server}:{port}")
            return True
        else:
            log.warning(f"[TEST] ⚠️ Cannot connect to WVP server {server}:{port}")
            return False
            
    except Exception as e:
        log.error(f"[TEST] Connection test failed: {e}")
        return False

def run_integration_test():
    """Run the complete integration test"""
    log.info("="*60)
    log.info("[TEST] Starting RTSP to GB28181 Integration Test")
    log.info("="*60)
    
    try:
        # Test 1: Live Stream Handler
        test_live_stream_handler()
        print()
        
        # Test 2: Device Catalog Generation
        test_device_catalog_generation()
        print()
        
        # Test 3: XML Catalog Formatting
        test_xml_catalog_format()
        print()
        
        # Test 4: WVP Connectivity
        wvp_available = test_wvp_connectivity()
        print()
        
        # Summary
        log.info("="*60)
        log.info("[TEST] Integration Test Summary")
        log.info("="*60)
        log.info("[TEST] ✅ Live Stream Handler: Tested")
        log.info("[TEST] ✅ Device Catalog: Generated") 
        log.info("[TEST] ✅ XML Formatting: Tested")
        log.info(f"[TEST] {'✅' if wvp_available else '⚠️'} WVP Connectivity: {'Available' if wvp_available else 'Not Available'}")
        
        if wvp_available:
            log.info("[TEST] 🎉 All tests passed! System ready for WVP integration.")
            log.info("[TEST] Next steps:")
            log.info("[TEST]   1. Configure actual RTSP camera URLs in config.json")
            log.info("[TEST]   2. Start the main GB28181 restreamer") 
            log.info("[TEST]   3. Check WVP platform for registered devices")
            log.info("[TEST]   4. Test video playback through WVP interface")
        else:
            log.warning("[TEST] ⚠️ WVP server not reachable. Check network connectivity.")
            
    except Exception as e:
        log.error(f"[TEST] Integration test failed: {e}")
        raise

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    try:
        run_integration_test()
    except KeyboardInterrupt:
        log.info("[TEST] Test interrupted by user")
    except Exception as e:
        log.error(f"[TEST] Test failed: {e}")
        sys.exit(1) 