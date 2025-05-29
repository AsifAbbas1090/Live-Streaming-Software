#!/usr/bin/env python3

# Read the sip_handler_pjsip.py file
with open("src/sip_handler_pjsip.py", "r") as f:
    content = f.read()

# Fix the XML tags in the sip handler
content = content.replace("<n>{name}</n>", "<Name>{name}</Name>")
content = content.replace("<r>OK</r>", "<Result>OK</Result>")

# Save the changes
with open("src/sip_handler_pjsip.py", "w") as f:
    f.write(content)

print("Fixed XML tags in sip_handler_pjsip.py")

# Fix the catalog_response.xml file if it exists
try:
    with open("catalog_response.xml", "r") as f:
        xml_content = f.read()
    
    # Replace tags in the XML file
    xml_content = xml_content.replace("<n>", "<Name>")
    xml_content = xml_content.replace("</n>", "</Name>")
    xml_content = xml_content.replace("<r>OK</r>", "<Result>OK</Result>")
    
    with open("catalog_response.xml", "w") as f:
        f.write(xml_content)
    
    print("Fixed XML tags in catalog_response.xml")
except FileNotFoundError:
    print("catalog_response.xml not found, skipping")

print("All XML tags fixed. Please restart the server.")