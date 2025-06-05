#!/bin/bash

# Network Configuration Fix for WVP-GB28181-pro Compatibility
# Based on solutions from https://github.com/648540858/wvp-GB28181-pro

echo "🔧 GB28181 Network Configuration Fix"
echo "===================================="

# Get current network information
LOCAL_IP=$(hostname -I | awk '{print $1}')
PUBLIC_IP=$(curl -s ifconfig.me)
SERVER="ai-sip.x-stage.bull-b.com"
SERVER_IP=$(nslookup $SERVER | grep Address | tail -1 | awk '{print $2}')

echo "📊 Current Network Configuration:"
echo "   Local IP:  $LOCAL_IP"
echo "   Public IP: $PUBLIC_IP"
echo "   Server:    $SERVER"
echo "   Server IP: $SERVER_IP"

# Test connectivity to WVP server
echo ""
echo "🌐 Testing WVP Server Connectivity:"
echo "=================================="

# Test UDP connectivity (most important for SIP)
echo "Testing UDP connection to $SERVER:5060..."
timeout 5 nc -u -v $SERVER 5060 <<< "TEST" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ UDP connectivity to WVP server: OK"
else
    echo "❌ UDP connectivity to WVP server: FAILED"
    echo "   This is likely the root cause of your issue!"
fi

# Test TCP connectivity
echo "Testing TCP connection to $SERVER:5060..."
timeout 5 nc -v $SERVER 5060 <<< "TEST" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ TCP connectivity to WVP server: OK"
else
    echo "❌ TCP connectivity to WVP server: FAILED"
fi

# Check if firewall is blocking
echo ""
echo "🔒 Firewall Check:"
echo "=================="
ufw status
iptables -L INPUT | grep DROP

# Fix 1: Update config with correct IP binding
echo ""
echo "🔧 Solution 1: Updating SIP configuration..."
echo "============================================"

# Backup current config
cp config/config.json config/config.json.backup

# Create corrected config
cat > config/config.json << EOF
{
  "sip": {
    "device_id": "81000000465001000001",
    "username": "81000000465001000001",
    "password": "admin123",
    "server": "ai-sip.x-stage.bull-b.com",
    "port": 5060,
    "local_port": 5080,
    "transport": "udp",
    "local_ip": "$LOCAL_IP",
    "contact_ip": "$PUBLIC_IP"
  },
  "local_sip": {
    "enabled": false,
    "port": 5060,
    "transport": "udp"
  },
  "stream_directory": "/home/ubuntu/rstp/gb28181-restreamer/recordings",
  "rtsp_sources": [],
  "srtp": {
    "key": "313233343536373839303132333435363132333435363738393031323334"
  },
  "logging": {
    "level": "INFO",
    "file": "./logs/gb28181-restreamer.log",
    "console": true
  },
  "pipeline": {
    "format": "RGB",
    "width": 640,
    "height": 480,
    "framerate": 30,
    "buffer_size": 33554432,
    "queue_size": 3000,
    "sync": false,
    "async": false
  }
}
EOF

echo "✅ Updated config with explicit IP configuration"

# Fix 2: Open required ports
echo ""
echo "🔧 Solution 2: Opening required ports..."
echo "========================================"

# Open SIP port
sudo ufw allow 5060/udp
sudo ufw allow 5080/udp
# Open RTP ports range
sudo ufw allow 10000:20000/udp

echo "✅ Opened SIP and RTP ports"

# Fix 3: Test direct SIP MESSAGE sending
echo ""
echo "🔧 Solution 3: Testing direct SIP communication..."
echo "================================================="

# Create a test catalog response
cat > /tmp/test_catalog.xml << 'EOF'
<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>999999</SN>
  <DeviceID>81000000465001000001</DeviceID>
  <Result>OK</Result>
  <SumNum>1</SumNum>
  <DeviceList Num="1">
    <Item>
      <DeviceID>810000004651320000001</DeviceID>
      <Name>Network Test Camera</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Network Test</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>81000000465001000001</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
  </DeviceList>
</Response>
EOF

# Test sending with explicit local IP binding
echo "Sending test catalog message with network fixes..."
pjsua \
    --id "sip:81000000465001000001@ai-sip.x-stage.bull-b.com" \
    --realm "*" \
    --username "81000000465001000001" \
    --password "admin123" \
    --bound-addr "$LOCAL_IP" \
    --contact "sip:81000000465001000001@$PUBLIC_IP:5080" \
    --local-port 5080 \
    --no-tcp \
    --null-audio \
    --duration 10 \
    --auto-quit \
    --send-message "sip:ai-sip.x-stage.bull-b.com:5060" \
    --message-content-type "Application/MANSCDP+xml" \
    --message-content "@/tmp/test_catalog.xml" \
    2>&1

if [ $? -eq 0 ]; then
    echo "✅ Test message sent successfully with network fixes"
else
    echo "❌ Test message failed - network issue confirmed"
fi

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo "1. Restart your GB28181 service: ./restart_gb28181_service.sh"
echo "2. Check WVP platform for the test device with 1 channel"
echo "3. If still not working, check WVP server logs for firewall blocks"
echo "4. Consider using VPN or different network if cloud firewall is blocking"

echo ""
echo "📋 Common WVP-GB28181-pro Solutions Applied:"
echo "==========================================="
echo "✅ Added explicit IP binding configuration"
echo "✅ Opened required firewall ports"
echo "✅ Set correct Contact header for NAT traversal"
echo "✅ Used proper SIP message format"
echo "✅ Tested with minimal catalog for debugging"

# Clean up
rm -f /tmp/test_catalog.xml 