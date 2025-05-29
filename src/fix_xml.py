#!/usr/bin/env python3
import re

filename = 'src/gb28181_xml.py'
with open(filename, 'r') as f:
    content = f.read()
    
# Replace <r>OK</r> with <Result>OK</Result>
content = content.replace('<r>OK</r>', '<Result>OK</Result>')

# Replace <n>{name}</n> with <Name>{name}</Name>
content = content.replace('<n>{name}</n>', '<Name>{name}</Name>')

# Replace other <n> tags with <Name> tags
content = re.sub(r'<n>(.*?)</n>', r'<Name>\1</Name>', content)

with open(filename, 'w') as f:
    f.write(content)

print("XML tags fixed!") 