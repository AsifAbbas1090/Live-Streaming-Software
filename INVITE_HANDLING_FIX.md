# INVITE Message Handling Fix

## Problem Diagnosis

Your GB28181 device has **two issues**:

### 1. **Device-Side Issue**: INVITE Detection Not Working
- ✅ Device receives INVITE messages (confirmed in PJSUA logs)
- ❌ Python application layer doesn't detect INVITE messages
- ❌ PJSUA responds with "488 Not Acceptable Here" due to media handling issues

### 2. **WVP Platform Issue**: Missing INVITE Messages  
- ❌ WVP platform is not sending INVITE messages when users click "play"
- ✅ Registration, heartbeat, and catalog queries work fine

## Fix for Device-Side INVITE Handling

### Problem
PJSUA configuration has `--auto-answer 200` which makes PJSUA handle INVITE messages directly instead of passing them to the Python application. The Python application's INVITE detection logic in `_process_sip_message` is looking for log patterns that don't match the actual PJSUA output format.

### Solution

#### Step 1: Fix PJSUA Configuration
Remove auto-answer and improve INVITE handling:

```python
# In _start_pjsua_process method, REMOVE this line:
# "--auto-answer", "200",  # Remove auto-answer

# REPLACE with these settings:
"--auto-answer", "0",      # Disable auto-answer 
"--null-audio",            # Keep null audio
"--max-calls", "10",       # Allow more calls
```

#### Step 2: Improve INVITE Detection Logic
The current INVITE detection pattern `"INVITE sip:"` doesn't match PJSUA log format. 

Fix the pattern in `_process_sip_message`:

```python
# CURRENT (doesn't work):
if "INVITE sip:" in line and "SDP" not in line:

# REPLACE WITH (works):
if "Request msg INVITE" in line or "RX" in line and "INVITE" in line:
    log.info("[SIP] INVITE detected in log line, processing buffer for full message.")
```

#### Step 3: Add Proper SIP Response for INVITE
Add code to respond to INVITE messages properly:

```python
def handle_invite_message(self, call_id, sdp_content):
    """Handle incoming INVITE message and start streaming"""
    try:
        # Process SDP and start streaming
        success = self.parse_sdp_and_stream(sdp_content, call_id)
        
        if success:
            # Send 200 OK response
            self._send_invite_ok_response(call_id)
            log.info(f"[SIP] ✅ INVITE accepted, streaming started for {call_id}")
        else:
            # Send 488 Not Acceptable Here
            self._send_invite_error_response(call_id, 488)
            log.error(f"[SIP] ❌ INVITE rejected for {call_id}")
            
    except Exception as e:
        log.error(f"[SIP] Error handling INVITE: {e}")
        self._send_invite_error_response(call_id, 500)

def _send_invite_ok_response(self, call_id):
    """Send 200 OK response to INVITE"""
    # Implementation needed
    pass

def _send_invite_error_response(self, call_id, error_code):
    """Send error response to INVITE"""
    # Implementation needed  
    pass
```

## Fix for WVP Platform Configuration

Since your device is properly registered and catalog works, the issue is likely:

### 1. Check WVP Stream Configuration
```
WVP Admin → 设备管理 → 国标设备 → [Your Device: 81000000465001000001]
- Verify device shows as "在线" (Online)
- Check if channels are properly listed
- Try clicking "实时视频" (Live Video) directly from device management
```

### 2. Check WVP Media Server Settings
```
WVP Admin → 系统设置 → 流媒体设置
- Verify "流媒体服务器IP" is correctly configured
- Check "RTP端口范围" (typically 30000-30500)
- Ensure "流媒体代理" settings are correct
```

### 3. Test WVP API Directly
```bash
# Test stream start API
curl -X POST "http://WVP_SERVER:18080/api/play/start/81000000465001000001/810000004650131000001" \
  -H "Content-Type: application/json"

# Check WVP logs for errors
tail -f /opt/wvp/logs/wvp.log
```

### 4. Network Configuration
Ensure these ports are open on WVP platform:
```bash
# SIP signaling
iptables -A INPUT -p udp --dport 5060 -j ACCEPT

# RTP media streams  
iptables -A INPUT -p udp --dport 30000:30500 -j ACCEPT

# Check if SIP ALG is disabled on router
```

## Verification Steps

### 1. Test Device INVITE Handling
```bash
cd /home/ubuntu/rstp/gb28181-restreamer
python3 test_invite_simulation.py --device-ip 172.31.7.94 --device-port 5080
```

After fix, you should see:
- ✅ Device responds with 200 OK (not 488 error)
- ✅ Streaming starts successfully
- ✅ Python application logs show "INVITE detected"

### 2. Test WVP Platform
After WVP configuration:
- ✅ Frontend clicking "play" sends INVITE to device
- ✅ Device logs show incoming INVITE messages  
- ✅ Streaming starts without timeout

## Emergency Workaround

If WVP platform configuration is complex, you can test streaming by:

1. **Direct INVITE simulation**:
```bash
python3 test_invite_simulation.py --device-ip YOUR_DEVICE_IP --device-port 5080
```

2. **Manual stream trigger**:
Modify the device to periodically start test streams to verify the streaming pipeline works.

## Expected Result

After both fixes:
1. ✅ Device properly handles INVITE messages
2. ✅ WVP platform sends INVITE when users click "play"  
3. ✅ Frontend shows video stream instead of "收流超时" error
4. ✅ End-to-end streaming works correctly

## Implementation Priority

1. **HIGH**: Fix device INVITE handling (your code)
2. **HIGH**: Configure WVP platform properly (platform admin)
3. **MEDIUM**: Network/firewall configuration 
4. **LOW**: Frontend optimizations

The device-side fix is critical and can be implemented immediately. The WVP platform configuration may require administrator access to the WVP server. 