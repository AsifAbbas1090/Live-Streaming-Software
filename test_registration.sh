#!/bin/bash
# GB28181 Device Registration Test Script

echo "====================================="
echo "GB28181 Device Registration Test"
echo "====================================="

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

# Check pjsua is installed
if ! command -v pjsua &> /dev/null; then
    echo "❌ pjsua is not installed."
    echo "Installing pjsip-tools..."
    sudo apt update
    sudo apt install -y pjsip-tools
    
    if ! command -v pjsua &> /dev/null; then
        echo "❌ Failed to install pjsip-tools. Please install it manually."
        exit 1
    fi
    echo "✅ pjsip-tools installed successfully."
fi

# Check if requests module is installed
if ! python3 -c "import requests" &> /dev/null; then
    echo "❌ Python requests module is not installed."
    echo "Installing requests module..."
    pip3 install requests
    echo "✅ Requests module installed successfully."
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate a unique device ID using timestamp
DEVICE_ID="810000004650010000$(date +%H%M)"

echo "🔍 Using device ID: $DEVICE_ID"
echo "🔌 Connecting to SIP server: ai-sip.x-stage.bull-b.com:5060"
echo "🌐 Will verify device in WVP-pro after registration"
echo ""
echo "Starting test in 3 seconds..."
sleep 3

# Run the test
python3 "$SCRIPT_DIR/test_device_registration.py" --device-id $DEVICE_ID

# Check exit code
if [ $? -eq 0 ]; then
    echo "✅ Registration test completed successfully!"
else
    echo "❌ Registration test failed."
fi

echo ""
echo "To view log details, check: logs/device_registration_test.log"
echo "=====================================" 