# GB28181 Restreamer - Testing Environment & Procedures

## Environment Setup

### System Requirements

The GB28181 Restreamer has been developed and tested in the following environment:

- **Operating System**: Ubuntu 20.04 LTS (also tested on Ubuntu 18.04)
- **Architecture**: x86_64 and ARM64 (NVIDIA Jetson Orin NX)
- **Python**: Version 3.8 or later
- **GStreamer**: Version 1.16 or later with all required plugins
- **Network**: Both local testing and over-network testing configurations

### Dependency Installation

Before running the application, install all required dependencies:

```bash
# Update package lists
sudo apt update

# Install system dependencies
sudo apt install -y python3 python3-pip python3-dev \
    gstreamer1.0-tools gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly python3-gi vlc \
    build-essential pjsip-tools

# Install Python dependencies
pip3 install -r requirements.txt
```

### Directory Structure Setup

Create the necessary directories for the application:

```bash
mkdir -p logs
mkdir -p sample_videos
```

For testing, we've placed sample video files in the `sample_videos` directory. You should add some MP4 or AVI files to this directory for testing purposes.

## Testing Procedures

We've developed several test scripts to verify different functionalities of the GB28181 Restreamer:

### 1. Basic Integration Test

The `test_integrated_app.py` script verifies the core functionality of the application:

```bash
./test_integrated_app.py
```

**What this tests**:
- Configuration loading
- Video file scanning
- SIP client initialization
- Basic component integration

**Expected output**:
- Application starts successfully
- Logs show video files found
- SIP client initializes

**Example**:
```
[INFO] [BOOT] Starting GB28181 Restreamer...
[INFO] [CONFIG] Loaded configuration successfully.
[INFO] [SCAN] Found 2 video files.
[INFO] [CATALOG] 2 video files found.
[INFO]   • ./sample_videos/Entryyy.mp4
[INFO]   • ./sample_videos/Entryyy copy.mp4
...
```

### 2. Full GB28181 Protocol Test

The `test_gb28181.py` script provides comprehensive testing of the GB28181 protocol implementation:

```bash
./test_gb28181.py
```

**What this tests**:
- SIP registration process
- INVITE message handling
- SDP processing
- Video streaming via RTP
- Full protocol flow

**Options**:
- `--mode server`: Start only the server component
- `--mode invite`: Send INVITE message to test streaming
- `--streams N`: Test multiple concurrent streams (where N is the number of streams)

**Example**:
```bash
# Test with 3 concurrent streams
./test_gb28181.py --streams 3

# Test server mode only
./test_gb28181.py --mode server

# Test sending INVITE message only
./test_gb28181.py --mode invite
```

### 3. RTSP Source Testing

To test RTSP source integration, we provide a simple RTSP server setup script:

```bash
./setup_rtsp_server.py --video ./sample_videos/Entryyy.mp4
```

Then update `config.json` to include the RTSP source:
```json
"rtsp_sources": [
  "rtsp://127.0.0.1:8554/test"
]
```

Run the main application to verify RTSP source handling:
```bash
python3 src/main.py
```

**What this tests**:
- RTSP connection establishment
- Stream health monitoring
- Automatic retry mechanism
- RTSP to GB28181 conversion

## Manual Testing with WVP-GB28181-Pro

For testing with WVP-GB28181-Pro:

1. Ensure WVP is installed and running on your test server
2. Configure the GB28181 Restreamer to connect to WVP:
   ```json
   "sip": {
     "device_id": "34020000001320000001",
     "username": "34020000001320000001",
     "password": "12345678",
     "server": "your-wvp-server-ip",
     "port": 5060
   }
   ```
3. Start the GB28181 Restreamer:
   ```bash
   python3 src/main.py
   ```
4. In the WVP web interface:
   - Verify the device shows as "Online"
   - View the device channels (each video file should appear as a channel)
   - Click on a channel to start streaming

## Troubleshooting Testing Issues

### Common Testing Problems

1. **Python Module Not Found**:
   - Ensure all dependencies are installed: `pip3 install -r requirements.txt`
   - Check Python path issues in test scripts, may need to set `PYTHONPATH`

2. **SIP Port Conflicts**:
   - The application will try to use alternative ports automatically
   - Look for messages like "Using alternative port: 5062"
   - If needed, manually set a different port in config.json

3. **RTSP Connection Failures**:
   - Verify the RTSP server is running
   - Check network connectivity to the RTSP source
   - Inspect logs for "RTSP server not available" messages

4. **Test Script Path Issues**:
   - Run scripts from the project root directory
   - If importing modules fails, the script might automatically add the src directory to the Python path
   - If needed, manually set the Python path: `export PYTHONPATH=$PYTHONPATH:/path/to/gb28181-restreamer`

### Checking Test Results

1. **Log Analysis**:
   - Check the application logs for detailed information
   - Look for ERROR or WARNING level messages
   - Verify successful connection and registration messages

2. **XML Response Validation**:
   - Examine the XML files generated during testing
   - Verify they follow the GB28181 protocol structure

3. **Stream Verification**:
   - Use VLC to verify streams are working
   - Create an SDP file as described in the documentation
   - Check that RTP packets are being received

4. **Performance Testing**:
   - Monitor CPU and memory usage during multi-stream tests
   - Check for any degradation with multiple concurrent connections
   - Verify stream health monitoring is working correctly

## Test Environment Variables

The test scripts and application support several environment variables for configuration:

- `GB28181_CONFIG_PATH`: Override the default configuration file path
- `GB28181_LOG_LEVEL`: Set the logging level (DEBUG, INFO, WARNING, ERROR)
- `GB28181_RTSP_RETRY_COUNT`: Set the number of RTSP connection retry attempts
- `GB28181_STREAM_PRESET`: Set the default streaming preset (low, medium, high)

Example:
```bash
GB28181_LOG_LEVEL=DEBUG GB28181_STREAM_PRESET=high python3 src/main.py
```

## Continuous Testing

For ongoing testing and monitoring:

1. **Run the application in a terminal**:
   ```bash
   python3 src/main.py
   ```

2. **Monitor logs for issues**:
   ```bash
   tail -f logs/gb28181.log
   ```

3. **Test streaming with VLC**:
   ```bash
   vlc invite.sdp
   ```

By following these testing procedures, you can verify all aspects of the GB28181 Restreamer functionality and ensure it works correctly with your surveillance system. 