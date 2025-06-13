# 🎥 How to View Your Live Streams

Your GB28181 system is now running! Here's exactly where and how to view your live streams.

## 🔍 **Current Status Check**

Your GB28181 application is running (PID: check with `ps aux | grep main.py`)

## 📺 **Where to View Live Streams**

### **Option 1: Direct RTSP Access (Immediate Testing)**

You can view the streams directly using any RTSP-compatible player:

#### **🎬 VLC Media Player**
1. Open VLC
2. Go to `Media` → `Open Network Stream`
3. Enter one of these URLs:
   - **Virtual Test Stream**: `rtsp://localhost:8554/stream`
   - **Wowza Test Stream**: `rtsp://807e9439d5ca.entrypoint.cloud.wowza.com:1935/app-rC94792j/068b9c9a_stream2`

#### **🖥️ Command Line (GStreamer)**
```bash
# Test virtual RTSP stream
gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! autovideosink

# Test with FFplay
ffplay rtsp://localhost:8554/stream
```

### **Option 2: WVP-GB28181-Pro Platform (Production)**

This is where your streams will appear as GB28181 devices:

#### **🌐 WVP Platform Access**
- **Platform**: WVP-GB28181-Pro
- **Your configured server**: `ai-sip.x-stage.bull-b.com:5060`
- **Protocol**: GB28181/SIP

#### **📋 What You Should See**
1. **Device Registration**: Your RTSP cameras appear as GB28181 devices
2. **Device IDs**: 
   - Virtual Stream: `34020000001320000004`
   - Wowza Stream: `34020000001320000001`
   - Highway Camera: `34020000001320000002`

#### **🔧 WVP Platform Features**
- Device management interface
- Live video playback
- Recording capabilities
- PTZ control (if supported)
- Device status monitoring

## 🚀 **Quick Test Commands**

### **Check if GB28181 is Running**
```bash
ps aux | grep main.py
```

### **Check Virtual RTSP Stream**
```bash
docker ps | grep virtual-rtsp
```

### **Test Stream Connectivity**
```bash
# Test virtual stream
timeout 10 gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! fakesink

# Check application logs
tail -f logs/gb28181.log
```

### **Monitor SIP Registration**
```bash
# Check if SIP server is responding
nmap -p 5060 ai-sip.x-stage.bull-b.com

# Monitor network traffic (optional)
sudo tcpdump -i any port 5060
```

## 🎯 **Expected Workflow**

1. **✅ RTSP Sources Active**: Your virtual stream is running on `localhost:8554`
2. **✅ GB28181 Processing**: Application converts RTSP to GB28181 protocol
3. **✅ SIP Registration**: Devices register with WVP server
4. **✅ WVP Interface**: View streams through WVP web interface
5. **✅ Live Playback**: Watch your camera feeds in the browser

## 🔧 **Troubleshooting**

### **If You Don't See Streams in WVP:**

1. **Check GB28181 Application Logs**:
   ```bash
   tail -f logs/gb28181.log
   ```

2. **Verify RTSP Source**:
   ```bash
   gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! fakesink
   ```

3. **Check SIP Registration**:
   ```bash
   grep -i "register" logs/gb28181.log
   ```

4. **Restart Virtual RTSP if Needed**:
   ```bash
   docker restart virtual-rtsp-test
   ```

### **If Direct RTSP Doesn't Work:**

1. **Check Container Status**:
   ```bash
   docker ps | grep virtual-rtsp
   docker logs virtual-rtsp-test
   ```

2. **Restart Container**:
   ```bash
   docker restart virtual-rtsp-test
   ```

3. **Test with Different Player**:
   ```bash
   ffplay rtsp://localhost:8554/stream
   ```

## 📱 **Mobile/Remote Access**

To access from other devices on your network:
- Replace `localhost` with your server IP: `13.50.108.195`
- Example: `rtsp://13.50.108.195:8554/stream`

## 🎉 **Success Indicators**

You'll know everything is working when:
- ✅ Virtual RTSP stream plays in VLC
- ✅ GB28181 application shows "registered" in logs
- ✅ WVP platform shows your devices online
- ✅ You can play video through WVP interface

## 📞 **Next Steps**

1. **Test Direct RTSP**: Use VLC to confirm streams work
2. **Check WVP Platform**: Look for registered GB28181 devices
3. **Monitor Logs**: Watch for successful registrations
4. **Add Real Cameras**: Replace test streams with actual IP cameras

---

**🎬 Your test environment is ready! Start with VLC to verify the streams, then check the WVP platform for GB28181 device registration.** 