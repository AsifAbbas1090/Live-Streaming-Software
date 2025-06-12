# WVP Platform Configuration Fix for Missing INVITE Messages

## Problem Description
- Device registers successfully with WVP platform
- Catalog queries work fine
- Frontend shows "收流超时" (stream timeout) when clicking play
- **NO INVITE messages are being sent to the device**

## Root Cause Analysis
Based on logs analysis, the WVP platform is not sending SIP INVITE messages to start media streaming, likely due to NAT/network configuration issues.

## WVP Platform Settings to Check

### 1. Device Management Settings
```
WVP Admin → 设备管理 → 国标设备 → [Your Device]
- Check "流媒体模式" (Streaming Mode)
- Verify "传输协议" (Transport Protocol) is set to UDP
- Ensure "设备状态" shows as "在线" (Online)
```

### 2. Stream Proxy Settings
```
WVP Admin → 系统设置 → 流媒体设置
- 确认 "流媒体服务器IP" (Media Server IP) is correct
- 检查 "RTP端口范围" (RTP Port Range): typically 30000-30500
- 验证 "流媒体代理" (Media Proxy) settings
```

### 3. SIP Settings
```
WVP Admin → 系统设置 → SIP设置
- SIP端口: 5060 (should match your device config)
- SIP域: Should match device configuration
- 传输协议: UDP
- 注册有效期: 3600 (or match device setting)
```

### 4. Network Configuration
```
WVP Admin → 系统设置 → 网络设置
- 服务器IP: Must be the public IP where WVP is accessible
- 检查防火墙规则 (Firewall Rules)
- NAT穿透设置 (NAT Traversal Settings)
```

## Network Infrastructure Fixes

### 1. Firewall Rules (WVP Platform Server)
```bash
# Allow SIP signaling
iptables -A INPUT -p udp --dport 5060 -j ACCEPT
iptables -A OUTPUT -p udp --sport 5060 -j ACCEPT

# Allow RTP media streams
iptables -A INPUT -p udp --dport 30000:30500 -j ACCEPT
iptables -A OUTPUT -p udp --sport 30000:30500 -j ACCEPT

# Allow GB28181 default ports
iptables -A INPUT -p udp --dport 15060 -j ACCEPT
iptables -A OUTPUT -p udp --sport 15060 -j ACCEPT
```

### 2. Router/NAT Configuration (if WVP is behind NAT)
```
Port Forwarding Rules:
- UDP 5060 → WVP_INTERNAL_IP:5060 (SIP)
- UDP 30000-30500 → WVP_INTERNAL_IP:30000-30500 (RTP)
- Disable SIP ALG (Application Layer Gateway)
```

## Device Configuration Verification

### 1. Check Your Device Registration Info
```bash
# Your device should show these details in WVP
Device ID: 81000000465001000001
Status: 在线 (Online)
IP Address: 13.50.108.195 (Your device's public IP)
Port: 5080
Transport: UDP
```

### 2. Verify Catalog Response Format
Your device is sending catalog correctly, but ensure channels have:
```xml
<Item>
    <DeviceID>810000004650131000001</DeviceID>
    <Name>Channel 1</Name>
    <Status>ON</Status>
    <Parental>0</Parental>  <!-- Required for streaming -->
    <ParentID>81000000465001000001</ParentID>
</Item>
```

## Diagnostic Commands

### 1. Test INVITE from WVP Platform
```bash
# On WVP platform server, test if it can send to your device
curl -X POST http://localhost:8080/api/v1/device/81000000465001000001/stream/start
```

### 2. Monitor SIP Traffic on WVP Platform
```bash
# Install tcpdump on WVP platform server
sudo tcpdump -i any port 5060 -n -A

# Look for INVITE messages going OUT to your device IP
# Should see: INVITE sip:810000004650131000001@13.50.108.195:5080
```

### 3. Check WVP Platform Logs
```bash
# Common WVP log locations
tail -f /opt/wvp/logs/wvp.log
tail -f /var/log/wvp/streaming.log

# Look for errors related to:
# - "stream timeout"
# - "device not responding"
# - "INVITE failed"
```

## Testing Stream Start

### 1. Manual Stream Test
Try starting a stream directly from WVP admin interface:
```
1. Go to: 设备管理 → 国标设备 → [Your Device]
2. Click on channel: 810000004650131000001
3. Click "实时视频" (Live Video)
4. Check if INVITE is sent
```

### 2. API Test
```bash
# Test WVP API directly
curl -X POST "http://WVP_SERVER:18080/api/play/start/81000000465001000001/810000004650131000001" \
  -H "Content-Type: application/json"
```

## Expected Fix Results

After proper configuration, you should see:
1. ✅ INVITE messages in your device logs
2. ✅ Successful stream establishment  
3. ✅ Frontend shows video stream instead of timeout

## Emergency Workaround

If WVP configuration is complex, consider using a SIP testing tool to verify your device receives INVITE:

```bash
# Install SIPp testing tool
apt-get install sipp

# Send test INVITE to your device
sipp -sf invite_test.xml 13.50.108.195:5080
```

Create `invite_test.xml`:
```xml
<?xml version="1.0" encoding="ISO-8859-1" ?>
<scenario name="Basic INVITE">
  <send retrans="500">
    <![CDATA[
      INVITE sip:810000004650131000001@[remote_ip]:[remote_port] SIP/2.0
      Via: SIP/2.0/UDP [local_ip]:[local_port];branch=[branch]
      From: <sip:test@test.com>;tag=[pid]SIPpTag00[call_number]
      To: <sip:810000004650131000001@[remote_ip]:[remote_port]>
      Call-ID: [call_id]
      CSeq: 1 INVITE
      Contact: <sip:test@[local_ip]:[local_port]>
      Content-Type: application/sdp
      Content-Length: [len]

      v=0
      o=test 0 0 IN IP4 [local_ip]
      s=Test
      c=IN IP4 [local_ip]
      t=0 0
      m=video 5004 RTP/AVP 96
      a=rtpmap:96 H264/90000
    ]]>
  </send>
  <recv response="200" optional="false"></recv>
</scenario>
```

This will help verify your device properly handles INVITE messages. 