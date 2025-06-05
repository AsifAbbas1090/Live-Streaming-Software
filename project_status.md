# GB28181 Restreamer Project Status

## Project Architecture Overview
The project implements a GB28181-compliant system that can:
1. Restream RTSP sources using the GB28181 protocol
2. Scan directories for video files and make them available via GB28181
3. Handle SIP registration and INVITE requests
4. Provide a web-based viewer for testing streams

## Current Functional Components

### Core Components
- **Configuration System**: JSON-based configuration for SIP settings, video directories, and RTSP sources
- **Logging System**: Comprehensive logging for debugging and monitoring
- **SIP Client**: Handles registration and SIP message exchange with GB28181 platforms
- **Media Streaming**: GStreamer-based pipeline for RTP streaming with SRTP encryption
- **File Scanner**: Scans directories for compatible video files (.mp4, .avi)
- **Stream Configuration**: Comprehensive presets and quality profiles for different streaming scenarios

### Supporting Tools
- **Web Viewer**: HLS-based web interface for testing streams (stream_server.py)
- **Local SIP Server**: Test server for development (local_sip_server.py) 
- **Testing Framework**: Test scripts to verify functionality (test_gb28181.py)

## Implementation Status

### Completed Features
1. **Configuration Management**
   - Complete JSON configuration system with validation
   - Support for SIP, RTSP, and local SIP server configuration
   - Logging configuration with file and console options
   - Stream configuration presets for different quality levels and GB28181 format profiles

2. **Video File Management**
   - Directory scanner for .mp4 and .avi files
   - Video catalog in GB28181-compliant format
   - Automatic catalog updates

3. **GB28181 Protocol Implementation**
   - SIP registration with TCP/UDP transport
   - XML message generation for catalog, device info, keepalive
   - Enhanced SDP parsing for INVITE requests with robust error handling
   - SSRC handling for RTP streams

4. **Media Streaming**
   - GStreamer-based RTP streaming pipelines
   - SRTP encryption support
   - H.264 video encoding with configurable parameters
   - Stream status monitoring
   - Support for multiple concurrent streams
   - Comprehensive health monitoring for streams with automatic recovery
   - Improved video quality with detailed encoding parameter control

5. **Error Handling**
   - Robust error recovery strategies with exponential backoff
   - Proper resource management and stream cleanup
   - Complete shutdown procedures for all components

6. **Testing Tools**
   - Local SIP server for development testing
   - INVITE request simulator
   - Web viewer with HLS for visual verification
   - Support for testing multiple concurrent streams

### Partially Implemented Features
1. **Advanced GB28181 Features**
   - Basic features implemented, PTZ control and recording pending
   - Time-based video query support to be implemented

2. **RTSP Integration**
   - Basic RTSP source handling with retries and recovery 
   - Additional reliability improvements may be needed for specific sources

### Known Issues
1. **Web Viewer Limitations**
   - HLS playlists may not update correctly for web viewer (requires manual refresh)
   - Web viewer showing short playback for RTP streams (approx. 6 seconds)

2. **Performance**
   - Not yet tested on target hardware (Nvidia Jetson Orin NX)
   - May need optimization for ARM architecture

## Testing Status
- Local testing with test_gb28181.py is functional
- Web viewer (stream_server.py) works but has limitations
- Multiple concurrent stream testing has been successfully completed
- Full GB28181 platform integration testing pending

## Next Development Steps

### Critical Items
1. Test on ARM platform (Nvidia Jetson Orin NX)
2. Full integration testing with an actual GB28181 platform

### Feature Enhancements
1. Advanced GB28181 features (PTZ control, recording, etc.)
2. Time-based video query support
3. Additional performance optimizations

### Documentation & Testing
1. Complete API documentation
2. Installation guide for ARM platform
3. Performance benchmarking
4. Security review

## Deployment Notes
- Requires Python 3.8+ and GStreamer 1.0 with plugins
- ARM compatibility to be verified
- SRTP key management needs security review for production use

## Client Questions and Responses

### GStreamer appsink/appsrc Support
The system now includes support for GStreamer appsink/appsrc, allowing for frame-by-frame video processing. The implementation provides:
1. Ability to extract frames from video sources into Python using appsink
2. Frame processing capabilities (grayscale conversion, edge detection, blur, text overlay, etc.)
3. Re-injection of processed frames back into the pipeline using appsrc
4. Dynamic toggling of processing and switching between different processing methods
5. A test script (test_appsink_appsrc.py) demonstrating the functionality

This feature enables advanced use cases such as computer vision integration, video analytics, and custom overlays on GB28181 streams.

### GB28181 Protocol Testing
Testing is done through a built-in local SIP server and test scripts that generate compliant SIP messages. Integration testing with an actual GB28181 platform is recommended for full validation.

### wvp-gb28181-pro and zlmediakit Integration
The current implementation is a standalone solution that doesn't require these tools as dependencies. They were referenced as potential integration points rather than requirements.

### Time-based Video Query Support
The system currently makes video files available through the GB28181 catalog, but doesn't yet implement time-based querying. This functionality is defined in the GB28181 protocol and can be added in the next development phase.

## Client Demonstration Guide

### Setup Required
1. Ensure all dependencies are installed:
   ```bash
   sudo apt install python3 python3-pip gstreamer1.0-tools gstreamer1.0-plugins-base \
     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
     python3-gi vlc
   pip3 install -r requirements.txt
   ```

2. Place sample video files in the `sample_videos/` directory (MP4 or AVI format)

3. Configure the system in `config/config.json`:
   - Ensure `"local_sip"` section is enabled for local testing
   - Set the proper `"sip"` parameters for production testing
   - Optionally configure streaming presets in `config/streaming_presets.json`

### Running the Full Demonstration

The simplest way to demonstrate the complete system is using our test suite:

```bash
./test_gb28181.py
```

This will:
1. Start the GB28181 restreamer server
2. Send a test INVITE request to initiate streaming
3. Open VLC to view the stream

For testing multiple concurrent streams:

```bash
./test_gb28181.py --streams 3  # Specify the number of concurrent streams to test
```

### Manual Step-by-Step Demonstration

For a more controlled demonstration, you can run each component separately:

#### 1. Start the GB28181 Restreamer Server

```bash
./test_gb28181.py --mode server
```

This will:
- Launch the main application
- Start the local SIP server (on port 5060)
- Scan for video files
- Generate a video catalog
- Begin listening for INVITE requests

#### 2. Send a GB28181 INVITE Request

In a new terminal:

```bash
./test_gb28181.py --mode invite
```

This will:
- Connect to the local SIP server
- Send a properly formatted GB28181 INVITE request
- Include SDP information for streaming setup

The server logs should show:
- Successful receipt of the INVITE message
- SDP parsing (extracting IP, port, SSRC)
- Video stream selection
- GStreamer pipeline initialization

#### 3. View the Stream

For viewing the stream, there are two options:

**Option 1 - VLC with SDP file** (recommended for client demo):

Create an `invite.sdp` file with:
```
v=0
o=- 0 0 IN IP4 127.0.0.1
s=GB28181 Test
c=IN IP4 127.0.0.1
t=0 0
m=video 9000 RTP/AVP 96
a=rtpmap:96 H264/90000
```

Then run:
```bash
vlc invite.sdp
```

For multiple streams, create separate SDP files with different port numbers.

**Option 2 - Direct RTP reception** (may not work on all VLC versions):
```bash
cvlc rtp://127.0.0.1:9000
```

### RTSP Streaming Demonstration

To demonstrate RTSP capabilities:

1. Start an RTSP server with one of the sample videos:
   ```bash
   ./setup_rtsp_server.py --video ./sample_videos/Entryyy.mp4
   ```

2. Update `config.json` to include the RTSP source:
   ```json
   "rtsp_sources": [
     "rtsp://127.0.0.1:8554/test"
   ]
   ```

3. Start the restreamer server and send INVITE requests as above

## Validation Testing

To verify the application is working correctly, check for:

1. **Video File Scanning**:
   - Logs should show all MP4/AVI files in the sample_videos directory

2. **SIP Protocol**:
   - INVITE requests should receive 200 OK responses
   - Messages should be properly formatted according to GB28181 standard

3. **Video Streaming**:
   - GStreamer pipeline should start successfully (logs show "Pipeline started successfully")
   - Multiple concurrent streams should function correctly
   - Stream quality should match the configured preset
   - VLC should display the video when properly configured

4. **Error Recovery**:
   - Temporarily disconnect an RTSP source and verify automatic recovery
   - Check logs for health monitoring status

## Known Limitations

1. **SDP Handling**:
   - VLC requires an SDP file for playback (use the approach described above)
   - Some GB28181 platforms may send SDP in non-standard formats requiring special handling

2. **RTSP Reliability**:
   - RTSP connections may time out with certain sources
   - Use reliable RTSP sources or local test sources for demonstrations

3. **SIP Registration**:
   - For full production use, add proper error handling for SIP registration failures

## Next Steps

1. Test with an actual GB28181 platform
2. Implement remaining advanced GB28181 features (PTZ, recording)
3. Test on ARM platform (Nvidia Jetson Orin NX)
4. Complete documentation and security review 