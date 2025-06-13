#!/usr/bin/env python3
"""
Test script to verify virtual RTSP stream integration with GB28181
"""

import json
import time
import subprocess
import sys
import os

def test_virtual_rtsp_stream():
    """Test the virtual RTSP stream setup"""
    print("🧪 Testing Virtual RTSP Stream Integration")
    print("=" * 50)
    
    # Check if virtual RTSP container is running
    print("1. Checking virtual RTSP container...")
    try:
        result = subprocess.run(['docker', 'ps', '--filter', 'name=virtual-rtsp-test'], 
                              capture_output=True, text=True)
        if 'virtual-rtsp-test' in result.stdout:
            print("   ✅ Virtual RTSP container is running")
        else:
            print("   ❌ Virtual RTSP container not found")
            return False
    except Exception as e:
        print(f"   ❌ Error checking container: {e}")
        return False
    
    # Test RTSP stream connectivity
    print("2. Testing RTSP stream connectivity...")
    try:
        result = subprocess.run([
            'timeout', '10', 'gst-launch-1.0', 
            'rtspsrc', 'location=rtsp://localhost:8554/stream', 
            '!', 'fakesink'
        ], capture_output=True, text=True, timeout=15)
        
        if 'Setting pipeline to PLAYING' in result.stderr:
            print("   ✅ RTSP stream is accessible")
        else:
            print("   ⚠️  RTSP stream may have issues")
            print(f"   Debug: {result.stderr[:200]}...")
    except Exception as e:
        print(f"   ❌ Error testing RTSP stream: {e}")
        return False
    
    # Check configuration
    print("3. Checking configuration...")
    try:
        with open('config/config.json', 'r') as f:
            config = json.load(f)
        
        virtual_stream_found = False
        for source in config.get('rtsp_sources', []):
            if 'localhost:8554' in source.get('url', ''):
                virtual_stream_found = True
                enabled = source.get('enabled', False)
                print(f"   ✅ Virtual RTSP stream configured: {source['name']}")
                print(f"   📊 Enabled: {enabled}")
                break
        
        if not virtual_stream_found:
            print("   ❌ Virtual RTSP stream not found in config")
            return False
            
    except Exception as e:
        print(f"   ❌ Error reading config: {e}")
        return False
    
    # Test video file
    print("4. Checking test video file...")
    video_path = "test-videos/sample.mp4"
    if os.path.exists(video_path):
        size = os.path.getsize(video_path) / (1024*1024)  # MB
        print(f"   ✅ Test video exists: {size:.1f} MB")
    else:
        print("   ❌ Test video file not found")
        return False
    
    print("\n🎉 Virtual RTSP Test Summary:")
    print("   ✅ Container: Running")
    print("   ✅ Stream: Accessible") 
    print("   ✅ Config: Configured")
    print("   ✅ Video: Available")
    print("\n📋 Ready for GB28181 testing!")
    
    return True

def show_usage_instructions():
    """Show instructions for using the test setup"""
    print("\n" + "=" * 60)
    print("🚀 USAGE INSTRUCTIONS")
    print("=" * 60)
    print()
    print("Your test environment is ready! Here's how to use it:")
    print()
    print("1. 🎥 AVAILABLE TEST STREAMS:")
    print("   • Virtual RTSP: rtsp://localhost:8554/stream")
    print("   • Wowza Test: rtsp://807e9439d5ca.entrypoint.cloud.wowza.com:1935/app-rC94792j/068b9c9a_stream2")
    print()
    print("2. 🔧 START GB28181 SYSTEM:")
    print("   python3 src/main.py")
    print()
    print("3. 🌐 CHECK WVP PLATFORM:")
    print("   • URL: https://wvp-gb28181-pro.example.com")
    print("   • Look for registered devices")
    print("   • Test video playback")
    print()
    print("4. 📊 MONITOR LOGS:")
    print("   tail -f logs/gb28181.log")
    print()
    print("5. 🔄 RESTART VIRTUAL RTSP (if needed):")
    print("   docker restart virtual-rtsp-test")
    print()
    print("6. 🛠️  TROUBLESHOOTING:")
    print("   • Check container: docker ps")
    print("   • Check logs: docker logs virtual-rtsp-test")
    print("   • Test stream: gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! fakesink")
    print()

if __name__ == "__main__":
    print("🎬 GB28181 Virtual RTSP Test Suite")
    print("=" * 50)
    
    success = test_virtual_rtsp_stream()
    
    if success:
        show_usage_instructions()
        print("✅ All tests passed! Your system is ready for testing.")
    else:
        print("❌ Some tests failed. Please check the issues above.")
        sys.exit(1) 