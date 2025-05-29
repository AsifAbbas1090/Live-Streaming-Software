#!/usr/bin/env python3

import re
import sys
import os

def fix_sip_handler_xml():
    """
    Fix XML tag issues in the sip_handler_pjsip.py file
    """
    file_path = "src/sip_handler_pjsip.py"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False
        
    with open(file_path, "r") as f:
        content = f.read()
    
    # Fix the <n> tags to <Name> tags
    content = re.sub(r'<n>({name})</n>', r'<Name>\1</Name>', content)
    
    # Fix the <r>OK</r> tag to <Result>OK</Result>
    content = re.sub(r'<r>OK</r>', r'<Result>OK</Result>', content)
    
    # Write the fixed content back to the file
    with open(file_path, "w") as f:
        f.write(content)
    
    print(f"Fixed XML tags in {file_path}")
    return True

def process_catalog_xml():
    """
    Process the catalog_response.xml file directly
    """
    file_path = "catalog_response.xml"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False
        
    with open(file_path, "r") as f:
        content = f.read()
    
    # Fix the <n> tags to <Name> tags
    content = content.replace("<n>", "<Name>")
    content = content.replace("</n>", "</Name>")
    
    # Fix the <r>OK</r> tag to <Result>OK</Result>
    content = content.replace("<r>OK</r>", "<Result>OK</Result>")
    
    # Write the fixed content back to the file
    with open(file_path, "w") as f:
        f.write(content)
    
    print(f"Fixed XML tags in {file_path}")
    return True

def fix_gb28181_xml_py():
    """
    Check the format_catalog_response function in gb28181_xml.py
    """
    file_path = "src/gb28181_xml.py"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return False
        
    with open(file_path, "r") as f:
        content = f.read()
    
    # Check if the XML template is already using correct tags
    # This is just to diagnose, not to change
    if "<Result>OK</Result>" in content:
        print("GB28181 XML already uses <Result>OK</Result> tag.")
    else:
        print("Warning: <Result>OK</Result> tag not found in gb28181_xml.py")
    
    if "<Name>{name}</Name>" in content:
        print("GB28181 XML already uses <Name> tag.")
    else:
        print("Warning: <Name> tag not found in gb28181_xml.py")
    
    print(f"Checked {file_path}")
    return True

if __name__ == "__main__":
    print("GB28181 XML Tag Fixer")
    print("---------------------")
    
    # Fix all the files
    fix_sip_handler_xml()
    process_catalog_xml()
    fix_gb28181_xml_py()
    
    print("\nDone! Please restart the server for changes to take effect.") 