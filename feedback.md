# Testing Feedback 29-05-2025

Test results from src/main.py.

## PJSUA installation

OK

## RTSP gstreamer pipeline error

```
[2025-05-29 17:03:40] [INFO] [RTSP] Launching stream: rtsp://192.168.3.101:554/12
[2025-05-29 17:03:40] [INFO] [RTSP] Started RTSP stream handler for rtsp://192.168.3.101:554/12
[2025-05-29 17:03:40] [DEBUG] Pipeline: rtspsrc location="rtsp://192.168.3.101:554/12" latency=0 buffer-mode=auto tcp-timeout=5000000 retry=3 connection-speed=1000000 ! rtph264depay ! h264parse config-interval=1 ! queue max-size-buffers=3000 max-size-bytes=0 max-size-time=0 ! videoconvert ! video/x-raw,format=RGB ! queue max-size-buffers=3000 max-size-bytes=0 max-size-time=0 ! fakesink sync=false

...

[2025-05-29 17:03:40] [ERROR] [RTSP] Error starting RTSP stream: gst_parse_error: could not link queue0 to videoconvert0 (3)
Traceback (most recent call last):
  File "/home/bullb/safe-vision/Live-Streaming-Software/src/rtsp_handler.py", line 116, in start
    self.pipeline = self._create_pipeline(self.rtsp_url)
  File "/home/bullb/safe-vision/Live-Streaming-Software/src/rtsp_handler.py", line 348, in _create_pipeline
    return Gst.parse_launch(pipeline_str)
gi.repository.GLib.GError: gst_parse_error: could not link queue0 to videoconvert0 (3)
```

## WVP / SIP Connection

Registration: OK

Keep Alive: ?

It looks like the device will become offline in wvp, 3 minutes after registration. It only becomes only again after registration again.

The protocol should have a keep alive mechanism?

## Catalog Query

It looks like there is a bug in the code where the complete message is not being parsed correctly when receiving a catalog query.

sip_handler_pjsip.py (__process_sip_message)

The catalog query is actually not being handled at all.

```
[2025-05-29 17:11:37] [INFO] [SIP] Incoming MESSAGE detected: MESSAGE sip:81000000465001800001@192.168.96.1:13199 SIP/2.0
Call-ID: b90b889462b5482a110cccc98351b1b5@0.0.0.0
CSeq: 272 MESSAGE
From: <sip:81000000462001888888@81000000>;tag=4bda50123acc43adb771e413be196123
To: <sip:81000000465001800001@192.168.96.1:13199>
Via: SIP/2.0/UDP 0.0.0.0:5060;rport;branch=4bda50123acc43adb771e413be196123-b90b889462b5482a110cccc98351b1b5-0.0.0.0-272-message-0.0.0.0-5060373237
Max-Forwards: 70
User-Agent: WVP-Pro
Content-Type: Application/MANSCDP+xml
Content-Length: 153

[2025-05-29 17:11:37] [DEBUG] [SIP] MESSAGE without XML content
<?xml version="1.0" encoding="GB2312"?>
<Query>
<CmdType>DeviceStatus</CmdType>
<SN>275474</SN>
<DeviceID>81000000465001800001</DeviceID>
</Query>
```

## Recording directory scan

The testing "recording" directory with 8 video files works fine, but when configured to my recording directory, the program gets stuck here.

recording_manager.py (scan_recordings)

```
... 

[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/14-08-28.avi
[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/17-13-26.avi
[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/12-39-07.avi
[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/14-29-28.avi
[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/10-02-20.avi
[2025-05-29 17:15:56] [INFO]   • /home/bullb/safe-vision/recordings/2025-04-07/16-11-28.avi
[2025-05-29 17:15:56] [INFO] [STREAM] Initializing media streamer with frame processing support
[2025-05-29 17:15:56] [INFO] [STREAM] GLib main loop started
[2025-05-29 17:15:56] [INFO] [REC-MANAGER] Scanning recordings directory
```

^ The program hangs here after this log

I suspect it may be because I have too many video files in the directory? According to the logs, I have 4167 video files.

## Frame processor with streamer

What is this?

main.py (main)

```python
# Register frame processors with streamer
streamer.register_frame_processor("grayscale", process_grayscale)
streamer.register_frame_processor("edge", process_edge_detection)
streamer.register_frame_processor("blur", process_blur)
streamer.register_frame_processor("text", process_add_text)
log.info("[STREAM] Registered frame processors for video manipulation")
```

## Appsink/Appsrc integration

This is for combining 2 gstreamer pipelines together using appsink and appsrc, which should not have anything to do with frame processing.

# Environment

- System architecture: Linux bullb-desktop 5.15.148-tegra #1 SMP PREEMPT Tue Jan 7 17:14:38 PST 2025 aarch64 aarch64 aarch64 GNU/Linux
- Python version: Python 3.10.12
- GStreamer version: 
  gst-inspect-1.0 version 1.20.3
  GStreamer 1.20.3
  https://launchpad.net/distros/ubuntu/+source/gstreamer1.0
- PJSUA version: 
  ```
  17:47:44.202               config.c !PJLIB (c)2008-2016 Teluu Inc.
  17:47:44.202               config.c  Dumping configurations:
  17:47:44.202               config.c   PJ_VERSION                : 2.14
  17:47:44.202               config.c   PJ_M_NAME                 : aarch64
  17:47:44.202               config.c   PJ_HAS_PENTIUM            : 0
  17:47:44.202               config.c   PJ_OS_NAME                : aarch64-unknown-linux-gnu
  17:47:44.202               config.c   PJ_CC_NAME/VER_(1,2,3)    : gcc-11.4.0
  17:47:44.202               config.c   PJ_IS_(BIG/LITTLE)_ENDIAN : little-endian
  17:47:44.202               config.c   PJ_HAS_INT64              : 1
  17:47:44.202               config.c   PJ_HAS_FLOATING_POINT     : 1
  17:47:44.202               config.c   PJ_DEBUG                  : 1
  17:47:44.202               config.c   PJ_FUNCTIONS_ARE_INLINED  : 0
  17:47:44.202               config.c   PJ_LOG_MAX_LEVEL          : 5
  17:47:44.202               config.c   PJ_LOG_MAX_SIZE           : 4000
  17:47:44.202               config.c   PJ_LOG_USE_STACK_BUFFER   : 1
  17:47:44.202               config.c   PJ_POOL_DEBUG             : 0
  17:47:44.202               config.c   PJ_HAS_POOL_ALT_API       : 0
  17:47:44.202               config.c   PJ_HAS_TCP                : 1
  17:47:44.202               config.c   PJ_MAX_HOSTNAME           : 254
  17:47:44.202               config.c   ioqueue type              : select
  17:47:44.202               config.c   PJ_IOQUEUE_MAX_HANDLES    : 64
  17:47:44.202               config.c   PJ_IOQUEUE_HAS_SAFE_UNREG : 1
  17:47:44.202               config.c   PJ_HAS_THREADS            : 1
  17:47:44.202               config.c   PJ_LOG_USE_STACK_BUFFER   : 1
  17:47:44.202               config.c   PJ_HAS_SEMAPHORE          : 1
  17:47:44.202               config.c   PJ_HAS_EVENT_OBJ          : 1
  17:47:44.202               config.c   PJ_HAS_EXCEPTION_NAMES    : 1
  17:47:44.202               config.c   PJ_MAX_EXCEPTION_ID       : 16
  17:47:44.202               config.c   PJ_EXCEPTION_USE_WIN32_SEH: 0
  17:47:44.202               config.c   PJ_TIMESTAMP_USE_RDTSC:   : 0
  17:47:44.202               config.c   PJ_OS_HAS_CHECK_STACK     : 0
  17:47:44.202               config.c   PJ_HAS_HIGH_RES_TIMER     : 1
  17:47:44.202               config.c   PJ_HAS_IPV6               : 0
  17:47:44.202               config.c   PJ_HAS_SSL_SOCK           : 1
  17:47:44.202               config.c   PJ_SSL_SOCK_IMP           : 1
  17:47:45.208                timer.c  .Dumping timer heap:
  17:47:45.208                timer.c  .  Cur size: 0 entries, max: 3070
  ```
- Config:
  ```json
  {
    "sip": {
      "device_id": "81000000465001800001",
      "username": "81000000465001800001",
      "password": "admin123",
      "server": "ai-sip.x-stage.bull-b.com",
      "port": 5060,
      "local_port": 5080,
      "transport": "udp"
    },
    "local_sip": {
      "enabled": false,
      "port": 5060,
      "transport": "udp"
    },
    "stream_directory": "/home/bullb/safe-vision/recordings",
    "rtsp_sources": ["rtsp://192.168.3.101:554/12"],
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
      "height": 352,
      "framerate": 12,
      "buffer_size": 33554432,
      "queue_size": 3000,
      "sync": false,
      "async": false
    }
  }
  ```