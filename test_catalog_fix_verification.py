#!/usr/bin/env python3
"""
Catalog Fix Verification Test
Verifies that the catalog XML fixes are working properly for WVP compatibility.
"""

import sys
import os
import json
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_catalog_xml_format():
    """Test the fixed catalog XML format"""
    print("🔧 Testing Fixed Catalog XML Format...")
    print("=" * 50)
    
    try:
        from sip_handler_pjsip import SIPClient
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        # Create SIP client
        sip_client = SIPClient(config)
        
        # Generate catalog
        print("📂 Generating device catalog...")
        catalog = sip_client.generate_device_catalog()
        
        if not catalog:
            print("❌ No catalog generated!")
            return False
            
        print(f"✅ Generated catalog with {len(catalog)} channels")
        
        # Test XML response generation
        print("\n📝 Testing XML response generation...")
        test_sn = "999888"
        xml_response = sip_client._generate_catalog_response(test_sn)
        
        if not xml_response:
            print("❌ Failed to generate XML response!")
            return False
            
        print(f"✅ Generated XML response ({len(xml_response)} bytes)")
        
        # Save the response for inspection
        with open("test_catalog_fix_verification.xml", "w", encoding="utf-8") as f:
            f.write(xml_response)
        print("💾 Saved test response to: test_catalog_fix_verification.xml")
        
        # Validate XML structure
        print("\n🔍 Validating XML structure...")
        
        # Check for required elements
        required_elements = [
            '<CmdType>Catalog</CmdType>',
            f'<SN>{test_sn}</SN>',
            f'<DeviceID>{sip_client.device_id}</DeviceID>',
            '<Result>OK</Result>',  # This was missing before!
            '<SumNum>',
            '<DeviceList Num=',
            '<Item>',
            '</Item>',
            '</DeviceList>',
            '</Response>'
        ]
        
        missing_elements = []
        for element in required_elements:
            if element not in xml_response:
                missing_elements.append(element)
        
        if missing_elements:
            print("❌ Missing required XML elements:")
            for element in missing_elements:
                print(f"   • {element}")
            return False
        else:
            print("✅ All required XML elements present")
        
        # Check XML parsing
        print("\n🔍 Testing XML parsing...")
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_response)
            
            # Extract counts
            sumnum = int(root.find('SumNum').text)
            device_list = root.find('DeviceList')
            device_list_num = int(device_list.get('Num'))
            actual_items = len(device_list.findall('Item'))
            
            print(f"📊 XML Structure Analysis:")
            print(f"   • SumNum: {sumnum}")
            print(f"   • DeviceList Num: {device_list_num}")
            print(f"   • Actual Items: {actual_items}")
            
            if sumnum == device_list_num == actual_items:
                print("✅ XML counts are consistent!")
            else:
                print("❌ XML count mismatch - this could cause frontend issues!")
                return False
                
            # Check item structure
            first_item = device_list.find('Item')
            if first_item is not None:
                device_id = first_item.find('DeviceID').text
                name = first_item.find('Name').text
                parental = first_item.find('Parental').text
                
                print(f"📋 First Item (should be parent device):")
                print(f"   • DeviceID: {device_id}")
                print(f"   • Name: {name}")
                print(f"   • Parental: {parental}")
                
                # Check if this is the parent device (Parental=0, no ParentID)
                if parental == "0":
                    print("✅ First item is parent device (Parental=0)")
                    if device_id == sip_client.device_id:
                        print("✅ Parent device ID matches configuration")
                    else:
                        print("❌ Parent device ID mismatch")
                        return False
                else:
                    # This is a child channel - should have ParentID
                    parent_id_elem = first_item.find('ParentID')
                    if parent_id_elem is not None:
                        parent_id = parent_id_elem.text
                        print(f"   • ParentID: {parent_id}")
                        if parent_id == sip_client.device_id:
                            print("✅ Child channel parent-child relationship correct")
                        else:
                            print("❌ Child channel parent-child relationship incorrect")
                            return False
                    else:
                        print("❌ Child channel missing ParentID")
                        return False
            
            print("✅ XML parsing successful - structure is valid")
            
        except ET.ParseError as e:
            print(f"❌ XML parsing failed: {e}")
            return False
        
        # Size analysis
        print(f"\n📏 Size Analysis:")
        print(f"   • Total response size: {len(xml_response)} bytes")
        print(f"   • UTF-8 encoded size: {len(xml_response.encode('utf-8'))} bytes")
        
        if len(xml_response.encode('utf-8')) > 1400:
            print("⚠️  Large response - may cause UDP issues")
        else:
            print("✅ Response size is UDP-safe")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🎯 GB28181 Catalog Fix Verification")
    print("=" * 50)
    print("This test verifies that the catalog XML fixes resolve")
    print("the WVP frontend display issues.")
    print()
    
    success = test_catalog_xml_format()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("🎉 The catalog fixes should resolve the frontend issue.")
        print("💡 Key fixes applied:")
        print("   • Added missing <Result>OK</Result> field")
        print("   • Fixed newline characters in XML generation")
        print("   • Improved UDP size management")
        print("   • Consistent format between responses and notifications")
    else:
        print("❌ TESTS FAILED!")
        print("🚨 There are still issues with the catalog format.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 