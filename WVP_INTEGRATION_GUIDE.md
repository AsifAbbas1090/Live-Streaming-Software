# WVP Integration Guide - RTSP Live Streaming

## Quick Start

### 1. Configure RTSP Sources

Edit `config/config.json` to add your actual RTSP camera URLs:

```json
{
  "rtsp_sources": [
    {
      "url": "rtsp://admin:password@192.168.1.100:554/stream1",
      "name": "Front Door Camera",
      "device_id": "34020000001320000001"
    },
    {
      "url": "rtsp://admin:password@192.168.1.101:554/stream1",
      "name": "Parking Lot Camera", 
      "device_id": "34020000001320000002"
    }
  ]
}
```

### 2. Start the GB28181 Restreamer

```bash
cd gb28181-restreamer
python3 src/main.py
```

### 3. Verify Registration with WVP

1. **Check Logs**: Look for successful SIP registration messages
2. **WVP Platform**: Login to WVP web interface
3. **Device List**: Navigate to device management section
4. **Verify Devices**: Your RTSP cameras should appear as GB28181 devices

### 4. Test Video Playback

1. **Select Device**: Click on one of your RTSP camera devices in WVP
2. **Start Playback**: Click the play button
3. **Verify Stream**: Video should start playing in real-time

## Expected Behavior

### Device Registration
- RTSP cameras appear as GB28181 devices in WVP
- Device names match your configuration
- Status shows as "Online"

### Video Streaming
- Low latency (< 2 seconds)
- Smooth playback without buffering issues
- Automatic reconnection if RTSP source disconnects

### Logs to Monitor
```
[SIP] ✅ Generated device catalog with X channels
[LIVE] ✅ Pipeline started successfully for stream_xxx
[SIP] Using live stream handler for RTSP: rtsp://...
```

## Troubleshooting

### RTSP Connection Issues
```bash
# Test RTSP connectivity
ffplay rtsp://admin:password@192.168.1.100:554/stream1
```

### WVP Registration Issues
- Check SIP server configuration
- Verify network connectivity
- Check firewall settings

### Streaming Issues
- Monitor GStreamer pipeline logs
- Check RTSP source stability
- Verify network bandwidth

## Configuration Options

### Low Latency Settings
```json
{
  "stream_defaults": {
    "latency": 50,
    "buffer_size": 1,
    "speed_preset": "ultrafast"
  }
}
```

### High Quality Settings
```json
{
  "stream_defaults": {
    "width": 1920,
    "height": 1080,
    "bitrate": 4096,
    "speed_preset": "medium"
  }
}
```

## Testing Commands

### Run Integration Test
```bash
python3 test_live_stream_integration.py
```

### Check Pipeline Status
```bash
# Monitor logs for pipeline status
tail -f logs/gb28181-restreamer.log | grep LIVE
```

### Test RTSP Source
```bash
# Test individual RTSP source
gst-launch-1.0 rtspsrc location="rtsp://admin:password@192.168.1.100:554/stream1" ! autovideosink
```

## Success Indicators

✅ **Registration Success**
- SIP registration completes without errors
- Device catalog generated with RTSP sources
- WVP shows devices as online

✅ **Streaming Success**  
- Video plays smoothly in WVP interface
- Low latency (< 2 seconds)
- No buffering or connection drops

✅ **Performance Success**
- CPU usage remains reasonable
- Memory usage stable
- Network bandwidth efficient

## Next Steps

Once basic functionality is confirmed:

1. **Scale Testing**: Add more RTSP sources
2. **Performance Tuning**: Optimize for your specific cameras
3. **Monitoring**: Set up logging and alerting
4. **Production Deployment**: Configure for production environment

## Support

For issues or questions:
1. Check the logs in `logs/gb28181-restreamer.log`
2. Run the integration test for diagnostics
3. Verify RTSP source connectivity independently
4. Check WVP platform logs for additional details 