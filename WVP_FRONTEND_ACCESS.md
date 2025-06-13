# 🌐 WVP Frontend Access Guide

Your GB28181 system is running and attempting to register with the WVP server. Here's how to access the WVP frontend to see your live streams.

## 🎯 **WVP Server Details**

Based on your configuration:
- **WVP Server**: `ai-sip.x-stage.bull-b.com:5060`
- **Your Device ID**: `81000000465001000001`
- **Registration Status**: Check logs for confirmation

## 🌐 **Accessing WVP Frontend**

### **Option 1: Direct WVP Web Interface**

The WVP-GB28181-pro platform typically runs a web interface. Try these URLs:

1. **Primary Web Interface**:
   ```
   http://ai-sip.x-stage.bull-b.com:18080
   https://ai-sip.x-stage.bull-b.com:18443
   ```

2. **Alternative Ports**:
   ```
   http://ai-sip.x-stage.bull-b.com:8080
   http://ai-sip.x-stage.bull-b.com:9090
   http://ai-sip.x-stage.bull-b.com:3000
   ```

3. **Check if WVP has a custom domain**:
   ```
   http://wvp.x-stage.bull-b.com
   https://wvp.x-stage.bull-b.com
   ```

### **Option 2: Contact Client for WVP Access**

Since this is a client's WVP server, you should ask them for:
- **WVP Web Interface URL**
- **Login credentials** (username/password)
- **Access instructions**

## 🔍 **Verification Steps**

### **1. Check Registration Status**

```bash
# Check if registration was successful
grep -i "register\|200 OK\|401\|403" logs/gb28181.log | tail -10

# Monitor live registration attempts
tail -f logs/gb28181.log | grep -i "register\|sip"
```

### **2. Test SIP Server Connectivity**

```bash
# Test if WVP server is reachable
nmap -p 5060 ai-sip.x-stage.bull-b.com

# Test UDP connectivity
nc -u ai-sip.x-stage.bull-b.com 5060
```

### **3. Check Device Registration**

Your devices should appear in WVP with these IDs:
- **Virtual RTSP Stream**: `34020000001320000004`
- **Wowza Test Stream**: `34020000001320000001`
- **Highway Camera**: `34020000001320000002`

## 🎬 **Expected WVP Interface**

Based on the [WVP-GB28181-pro repository](https://github.com/648540858/wvp-GB28181-pro), you should see:

### **Login Page**
- Username/Password authentication
- Modern web interface

### **Device Management**
- List of registered GB28181 devices
- Device status (online/offline)
- Device information

### **Live Video**
- Click on device to start live stream
- Multiple viewing modes
- PTZ controls (if supported)

### **Features Available**
- 🎥 Live video preview
- 📹 Recording playback
- 🎛️ PTZ control
- 📊 Device monitoring
- 🔄 Multi-screen display

## 🚨 **Troubleshooting**

### **If Registration Fails**

1. **Check Credentials**:
   ```json
   {
     "device_id": "81000000465001000001",
     "username": "81000000465001000001", 
     "password": "admin123"
   }
   ```

2. **Verify Server Details**:
   ```bash
   # Test server connectivity
   ping ai-sip.x-stage.bull-b.com
   telnet ai-sip.x-stage.bull-b.com 5060
   ```

3. **Check Firewall**:
   ```bash
   # Ensure ports are open
   sudo ufw status
   sudo iptables -L
   ```

### **If Streams Don't Appear**

1. **Verify RTSP Sources**:
   ```bash
   # Test virtual stream
   gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! fakesink
   
   # Check container status
   docker ps | grep virtual-rtsp
   ```

2. **Check Device IDs**:
   - Ensure device IDs are unique
   - Follow GB28181 ID format
   - No conflicts with existing devices

3. **Monitor SIP Messages**:
   ```bash
   # Watch SIP traffic
   sudo tcpdump -i any port 5060 -A
   ```

## 📞 **Contact Client**

Since you're working with a client's WVP server, ask them:

1. **WVP Web Interface URL**
2. **Login credentials for the web interface**
3. **Expected device registration process**
4. **Any specific configuration requirements**

## 🎯 **Quick Test Commands**

```bash
# Check if GB28181 is running
ps aux | grep main.py

# Check registration status
grep -i "register" logs/gb28181.log | tail -5

# Test virtual RTSP stream
timeout 5 gst-launch-1.0 rtspsrc location=rtsp://localhost:8554/stream ! fakesink

# Check WVP server connectivity
nmap -p 5060,8080,18080 ai-sip.x-stage.bull-b.com
```

## 🎉 **Success Indicators**

You'll know everything is working when:
- ✅ GB28181 shows "Registration successful" in logs
- ✅ WVP web interface shows your devices online
- ✅ You can click on a device and see live video
- ✅ Stream plays smoothly in the web browser

## 📋 **Next Steps**

1. **Ask client for WVP web interface URL**
2. **Test the provided URLs above**
3. **Check registration logs**
4. **Verify device appears in WVP interface**
5. **Test live video playback**

---

**🎬 The key is accessing the WVP web interface where your GB28181 devices will appear as clickable video sources!** 