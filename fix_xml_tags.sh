#!/bin/bash

# Fix sip_handler_pjsip.py
echo "Fixing XML tags in sip_handler_pjsip.py..."
sed -i 's/<n>{name}<\/n>/<Name>{name}<\/Name>/g' src/sip_handler_pjsip.py
sed -i 's/<r>OK<\/r>/<Result>OK<\/Result>/g' src/sip_handler_pjsip.py

# Fix catalog_response.xml if it exists
if [ -f catalog_response.xml ]; then
    echo "Fixing XML tags in catalog_response.xml..."
    sed -i 's/<n>/<Name>/g' catalog_response.xml
    sed -i 's/<\/n>/<\/Name>/g' catalog_response.xml
    sed -i 's/<r>OK<\/r>/<Result>OK<\/Result>/g' catalog_response.xml
fi

echo "Fixed XML tags in files." 