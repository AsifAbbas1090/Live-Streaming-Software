#!/usr/bin/env python3
"""
Simple Test Script for GB28181 Restreamer
Tests core functionality without running the full application
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_file_scanner():
    """Test file scanner functionality"""
    print("🔍 Testing File Scanner...")
    
    try:
        from file_scanner import scan_video_files, get_video_catalog
        
        # Load config
        with open('config/config.json') as f:
            config = json.load(f)
        
        # Scan files
        scan_video_files(config['stream_directory'])
        catalog = get_video_catalog()
        
        print(f"✅ Found {len(catalog)} video files")
        if len(catalog) > 0:
            print(f"   Sample: {os.path.basename(catalog[0])}")
            return True
        else:
            print("❌ No video files found")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_catalog_generation():
    """Test catalog generation"""
    print("\n📂 Testing Catalog Generation...")
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Load config
        with open('config/config.json') as f:
            config = json.load(f)
        
        # Create SIP client
        sip_client = SIPClient(config)
        
        # Generate catalog
        catalog = sip_client.generate_device_catalog()
        
        print(f"✅ Generated catalog with {len(catalog)} channels")
        
        # Test XML response
        xml_response = sip_client._generate_catalog_response("12345")
        if xml_response and "Catalog" in xml_response:
            print("✅ XML response generation working")
            return True
        else:
            print("❌ XML response generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_import_modules():
    """Test that all required modules can be imported"""
    print("\n📦 Testing Module Imports...")
    
    modules = [
        'file_scanner',
        'sip_handler_pjsip',
        'media_streamer',
        'gb28181_xml',
        'gb28181_sip_sender',
        'logger'
    ]
    
    for module in modules:
        try:
            __import__(module)
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            return False
    
    return True

def main():
    """Run simple tests"""
    print("🧪 GB28181 Restreamer - Simple Test")
    print("=" * 40)
    
    tests = [
        ("Module Imports", test_import_modules),
        ("File Scanner", test_file_scanner),
        ("Catalog Generation", test_catalog_generation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    print("\n📊 Test Results:")
    print("-" * 20)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All core components working!")
    else:
        print("\n⚠️  Some issues detected")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 