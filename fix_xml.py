#!/usr/bin/env python3

# Fix the XML tags in the SIP handler
with open("src/sip_handler_pjsip.py", "r") as f:
    content = f.read()

# Replace <n>{name}</n> with <Name>{name}</Name>
content = content.replace("<n>{name}</n>", "<Name>{name}</Name>")

# Replace <r>OK</r> with <Result>OK</Result>
content = content.replace("<r>OK</r>", "<Result>OK</Result>")

# Write the fixed content back
with open("src/sip_handler_pjsip.py", "w") as f:
    f.write(content)

print("Fixed XML tags in sip_handler_pjsip.py")
