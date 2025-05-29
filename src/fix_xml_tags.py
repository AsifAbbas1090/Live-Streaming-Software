#!/usr/bin/env python3

"""
Fix XML tags in gb28181_xml.py
This script updates the XML tags in the gb28181_xml.py file to use the correct format
"""

import re

def fix_xml_tags():
    file_path = 'gb28181_xml.py'
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace <r>OK</r> with <Result>OK</Result>
    content = content.replace('<r>OK</r>', '<Result>OK</Result>')
    
    # Replace <n> tags with <Name> tags in format_device_item
    device_item_pattern = r'return f"""    <Item>(.*?)</Item>\n"""'
    device_item_match = re.search(device_item_pattern, content, re.DOTALL)
    
    if device_item_match:
        device_item_content = device_item_match.group(1)
        fixed_content = device_item_content.replace('<n>', '<Name>').replace('</n>', '</Name>')
        content = content.replace(device_item_content, fixed_content)
    
    # Fix record item format
    record_item_pattern = r'return f"""    <Item>(.*?)</Item>\n"""'
    record_matches = list(re.finditer(record_item_pattern, content, re.DOTALL))
    
    # Fix the second match (record item)
    if len(record_matches) > 1:
        record_item_content = record_matches[1].group(1)
        fixed_content = record_item_content.replace('<n>', '<Name>').replace('</n>', '</Name>')
        content = content.replace(record_item_content, fixed_content)
    
    # Write the updated content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("XML tags fixed in", file_path)

if __name__ == "__main__":
    fix_xml_tags() 