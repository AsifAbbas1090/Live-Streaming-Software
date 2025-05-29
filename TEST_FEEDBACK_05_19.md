# Testing Feedback

19-05-2025

## Config
config used during testing
```
{
  "sip": {
    "device_id": "81000000465002100000",
    "username": "81000000465002100000",
    "password": "admin123",
    "server": "ai-sip.x-stage.bull-b.com",
    "port": 5060,
    "local_port": 5060
  },
  "local_sip": {
    "enabled": true,
    "port": 5060,
    "transport": "tcp"
  },
  "stream_directory": "./recordings",
  "rtsp_sources": [
    "rtsp://192.168.3.101:554/12"
  ],
  "srtp": {
    "key": "313233343536373839303132333435363132333435363738393031323334"
  },
  "logging": {
    "level": "INFO",
    "file": "./logs/gb28181-restreamer.log",
    "console": true
  }
}
```

## src/main.py
We have an IPCAM running with rtsp at rtsp://192.168.3.101:554/12

- SIP not working. Cannot install pjsip-tools / pjsua
- Cannot read rtsp stream, Gstreamer error: Internal data stream error.


LOGS:
```
python3 src/main.py
[2025-05-19 16:09:07] [INFO] [BOOT] Starting GB28181 Restreamer...
[2025-05-19 16:09:07] [INFO] [CONFIG] Loaded configuration successfully.
[2025-05-19 16:09:07] [INFO] [SCAN] Found 8 video files.
[2025-05-19 16:09:07] [INFO] [CATALOG] 8 video files found.
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-15/14-32-14.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-15/00-10-10.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-15/12-30-00.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-15/01-20-30.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-16/14-32-14.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-16/00-10-10.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-16/12-30-00.mp4
[2025-05-19 16:09:07] [INFO]   • ./recordings/2025-05-16/01-20-30.mp4
[2025-05-19 16:09:07] [INFO] [RTSP] Launching stream: rtsp://192.168.3.101:554/12
[2025-05-19 16:09:07] [INFO] [RTSP] Started RTSP stream handler for rtsp://192.168.3.101:554/12
[2025-05-19 16:09:07] [DEBUG] [RTSP] Pipeline: rtspsrc location="rtsp://192.168.3.101:554/12" latency=0 buffer-mode=auto tcp-timeout=5000000 retry=3 connection-speed=1000000 ! rtph264depay ! h264parse ! queue max-size-buffers=3000 ! fakesink sync=false
[2025-05-19 16:09:07] [INFO] [LOCAL-SIP] Local SIP server is enabled
[2025-05-19 16:09:07] [INFO] [LOCAL-SIP] Starting local SIP server on port 5060 using TCP
[2025-05-19 16:09:07] [INFO] [LOCAL-SIP] TCP listener started
[2025-05-19 16:09:07] [INFO] [LOCAL-SIP] Server started successfully on port 5060
[2025-05-19 16:09:07] [INFO] [STATUS] Starting periodic status monitoring
[2025-05-19 16:09:07] [INFO] [SIP] Starting SIP client...
[2025-05-19 16:09:07] [INFO] [SIP] 🚀 Launching GB28181 SIP client...
[2025-05-19 16:09:07] [INFO] [SIP] Generated catalog with 8 channels
[2025-05-19 16:09:07] [INFO] [STATUS] Active streams: 0
[2025-05-19 16:09:07] [INFO] [SIP-SENDER] Started GB28181 SIP message sender thread
[2025-05-19 16:09:07] [INFO] [SIP] Using transport: udp
Exception in thread Thread-5 (listen_loop):
Traceback (most recent call last):
  File "/usr/lib/python3.10/threading.py", line 1016, in _bootstrap_inner
    self.run()
  File "/usr/lib/python3.10/threading.py", line 953, in run
    self._target(*self._args, **self._kwargs)
  File "/home/bullb/safe-vision/gb28181-restreamer/src/sip_handler_pjsip.py", line 439, in listen_loop
    self.process = subprocess.Popen(
  File "/usr/lib/python3.10/subprocess.py", line 971, in __init__
    self._execute_child(args, executable, preexec_fn, close_fds,
  File "/usr/lib/python3.10/subprocess.py", line 1863, in _execute_child
    raise child_exception_type(errno_num, err_msg, err_filename)
FileNotFoundError: [Errno 2] No such file or directory: 'pjsua'
[2025-05-19 16:09:07] [INFO] [RTSP] GStreamer RTSP pipeline started.
[2025-05-19 16:09:07] [INFO] [RTSP] Starting stream health monitoring for rtsp://192.168.3.101:554/12
[2025-05-19 16:09:07] [INFO] [RTSP] Stream registered: rtsp://192.168.3.101:554/12
[2025-05-19 16:09:07] [DEBUG] [RTSP] Pipeline state changed from null to ready
[2025-05-19 16:09:07] [DEBUG] [RTSP] Pipeline state changed from ready to paused
[2025-05-19 16:09:09] [WARNING] [RTSP] Failed to get pipeline state: failure
[2025-05-19 16:09:09] [ERROR] [RTSP] GStreamer error: Internal data stream error.
[2025-05-19 16:09:09] [DEBUG] [RTSP] Debug info: ../libs/gst/base/gstbasesrc.c(3127): gst_base_src_loop (): /GstPipeline:pipeline0/GstRTSPSrc:rtspsrc0/GstUDPSrc:udpsrc1:
streaming stopped, reason not-linked (-1)
[2025-05-19 16:09:09] [INFO] [RTSP] Will retry rtsp://192.168.3.101:554/12 in 3.3s (attempt 1/10)...
[2025-05-19 16:09:12] [INFO] [RTSP] Attempting to reconnect to rtsp://192.168.3.101:554/12
[2025-05-19 16:09:12] [INFO] [RTSP] Launching stream: rtsp://192.168.3.101:554/12
[2025-05-19 16:09:12] [DEBUG] [RTSP] Pipeline: rtspsrc location="rtsp://192.168.3.101:554/12" latency=0 buffer-mode=auto tcp-timeout=5000000 retry=3 connection-speed=1000000 ! rtph264depay ! h264parse ! queue max-size-buffers=3000 ! fakesink sync=false
[2025-05-19 16:09:12] [DEBUG] [RTSP] Pipeline state changed from null to ready
[2025-05-19 16:09:12] [INFO] [RTSP] GStreamer RTSP pipeline started.
[2025-05-19 16:09:12] [DEBUG] [RTSP] Pipeline state changed from ready to paused
[2025-05-19 16:09:13] [ERROR] [RTSP] GStreamer error: Internal data stream error.
[2025-05-19 16:09:13] [DEBUG] [RTSP] Debug info: ../libs/gst/base/gstbasesrc.c(3127): gst_base_src_loop (): /GstPipeline:pipeline1/GstRTSPSrc:rtspsrc1/GstUDPSrc:udpsrc7:
streaming stopped, reason not-linked (-1)
[2025-05-19 16:09:13] [INFO] [RTSP] Will retry rtsp://192.168.3.101:554/12 in 5.2s (attempt 2/10)...
^C[2025-05-19 16:09:14] [WARNING] [SHUTDOWN] Caught signal 2. Initiating graceful shutdown...
[2025-05-19 16:09:14] [WARNING] [SHUTDOWN] Cleaning up resources...
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping SIP client...
[2025-05-19 16:09:14] [INFO] [SIP] Stopping all streams and SIP client...
[2025-05-19 16:09:14] [INFO] [SIP-SENDER] Stopped GB28181 SIP message sender thread
[2025-05-19 16:09:14] [INFO] [STREAM] Media streamer shut down
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping local SIP server...
[2025-05-19 16:09:14] [INFO] [LOCAL-SIP] Server stopped
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping all RTSP streams...
[2025-05-19 16:09:14] [INFO] [RTSP] Stopping all 1 streams
[2025-05-19 16:09:14] [INFO] [RTSP] Stopping stream: rtsp://192.168.3.101:554/12
[2025-05-19 16:09:14] [INFO] [RTSP] Stream stopped: rtsp://192.168.3.101:554/12
[2025-05-19 16:09:14] [INFO] [RTSP] All streams stopped
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping media streamer...
[2025-05-19 16:09:14] [INFO] [STREAM] Media streamer shut down
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Cleanup complete
[2025-05-19 16:09:14] [WARNING] [SHUTDOWN] Cleaning up resources...
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping SIP client...
[2025-05-19 16:09:14] [INFO] [SIP] Stopping all streams and SIP client...
[2025-05-19 16:09:14] [INFO] [SIP-SENDER] Stopped GB28181 SIP message sender thread
[2025-05-19 16:09:14] [INFO] [STREAM] Media streamer shut down
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping local SIP server...
[2025-05-19 16:09:14] [INFO] [LOCAL-SIP] Server stopped
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping all RTSP streams...
[2025-05-19 16:09:14] [INFO] [RTSP] Stopping all 0 streams
[2025-05-19 16:09:14] [INFO] [RTSP] All streams stopped
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Stopping media streamer...
[2025-05-19 16:09:14] [INFO] [STREAM] Media streamer shut down
[2025-05-19 16:09:14] [INFO] [SHUTDOWN] Cleanup complete
```

## test_integrated_app.py
Most seem to be success, except the RTSP server (exited with code:1)

LOGS:
```
python3 test_integrated_app.py 

[15:47:16] 🧪 Starting GB28181 integrated application test
[15:47:16] Setting up test environment...
[15:47:16] ✅ Environment setup complete
[15:47:16] 🎬 Starting RTSP server...
[15:47:16] ✅ RTSP server started with PID 483253
[15:47:16] ✅ RTSP URL: rtsp://localhost:8554/test
[15:47:18] ❌ RTSP server exited with code: 1
[15:47:18] ⚠️ RTSP server failed to start, proceeding with test anyway
[15:47:18] 🚀 Starting GB28181 restreamer server...
[15:47:18] ✅ Created test configuration at ./config/test_config.json
[15:47:18] ✅ Server started with PID 483278
[15:47:21] ✅ Server startup confirmed
[15:47:21] ⏳ Waiting for server to initialize...
[15:47:26] 📂 Sending catalog query to 127.0.0.1:5060
[15:47:26] ✅ Catalog query sent
[15:47:26] 📩 Received response, length 280 bytes
[15:47:26] ✅ Catalog query test succeeded
[15:47:26] 📨 Sending INVITE request to 127.0.0.1:5060
[15:47:26] ℹ️ Using device ID from config: 81000000465002100000
[15:47:26] 🔄 Connecting to 127.0.0.1:5060 via TCP...
[15:47:26] ✅ TCP connection established and INVITE sent
[15:47:26] 📩 Received response: SIP/2.0 200 OK
Via: SIP/2.0/TCP 127.0.0.1:5060;branch=z9hG4bK-1747640846
From: <sip:10000000000000...
[15:47:26] ✅ Received positive response
[15:47:26] ✅ Created SDP file for VLC (invite.sdp)
[15:47:26] 
▶️ To view the stream, run in another terminal:
[15:47:26]   vlc invite.sdp
[15:47:26]   or: cvlc rtp://127.0.0.1:9000
[15:47:26] ✅ INVITE test succeeded
[15:47:26] ⏳ Test complete. Exiting in 5 seconds... (Ctrl+C to keep running)
[15:47:27] ⏳ Test complete. Exiting in 4 seconds... (Ctrl+C to keep running)
[15:47:28] ⏳ Test complete. Exiting in 3 seconds... (Ctrl+C to keep running)
[15:47:29] ⏳ Test complete. Exiting in 2 seconds... (Ctrl+C to keep running)
[15:47:30] ⏳ Test complete. Exiting in 1 seconds... (Ctrl+C to keep running)
[15:47:31] 🧹 Cleaning up resources...
[15:47:31] 🛑 Stopping server process...
[15:47:34] ✅ Cleanup complete
```

## run_viewer.sh
rtsp simple server doesn't work. probably because your rtsp-simple-server is amd64 but my architecture is arm

LOGS:
```
====================================
GB28181 Restreamer Complete Setup
====================================

Cleaning up any running processes...

Step 1: Starting RTSP server...
✗ Failed to start RTSP server
```

# Other Feedback

## appsink/appsrc input mode
- How to switch to this mode?
- test_appsink_appsrc.py doesn't seem like it tests this feature?

## WVP-pro device registration
In the documents, you mentioned that I should manually add the device to the device list in WVP. This isn't correct because it should automatically add the device to the device list when registering to the SIP. Please make sure this works.

## Video catalog / Time series query
In the documents, you mentioned that the videos will be listed in the device's channels. We actually want it to be listed in the device's recording list. 

The page can be found in WVP. 国标设备(Device List) -> 通道(Channels) -> 更多(More) -> 设备录像(Device Recordings)

This utilises the Time Series Query feature.

# Other depedencies that are not listed (for our record)

rtspclientsink
```bash
sudo apt install gstreamer1.0-rtsp
```

ffmpeg
```bash
sudo apt install ffmpeg
```

screen
```bash
sudo apt install screen
```