# GB28181 Restreamer

A lightweight software solution that can restream local RTSP streams and video files using the GB28181 protocol.

## Overview

This project implements a GB28181 protocol compliant video restreamer that can:

1. Scan directories for video files (.mp4, .avi)
2. Register with a GB28181 SIP server
3. Handle GB28181 protocol messages (catalog query, device info, etc.)
4. Stream video files using GStreamer over RTP with SRTP encryption
5. Restream RTSP sources

## Requirements

- Python 3.6+
- GStreamer 1.0 with required plugins
- PJSIP/PJSUA command line tools

### Installation

1. Install dependencies:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip gstreamer1.0-tools gstreamer1.0-plugins-base \
     gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
     libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev pjsip-tools
     
# Install Python dependencies
pip3 install -r requirements.txt
```

2. Configure the application by editing `config/config.json`:

```json
{
  "sip": {
    "device_id": "34020000001320000001",
    "username": "34020000001320000001",
    "password": "12345678",
    "server": "your-sip-server-ip",
    "port": 5061
  },
  "stream_directory": "./sample_videos/",
  "rtsp_sources": [
    "rtsp://example.com/stream1"
  ],
  "srtp": {
    "key": "313233343536373839303132333435363132333435363738393031323334"
  }
}
```

## Usage

Run the application:

```bash
python3 src/main.py
```

### Configuration Options

- `sip.device_id`: The GB28181 device ID for registration
- `sip.username`: SIP username (usually same as device_id)
- `sip.password`: SIP password for authentication
- `sip.server`: SIP server IP address
- `sip.port`: SIP server port (usually 5060 for UDP/TCP or 5061 for TLS)
- `stream_directory`: Directory to scan for video files
- `rtsp_sources`: List of RTSP URLs to restream
- `srtp.key`: SRTP encryption key (hex format)

## GB28181 Protocol Support

The application implements the following GB28181 protocol features:

- SIP registration with TLS transport
- Device catalog query handling
- Device info query handling
- Keepalive message handling
- Media streaming with proper RTP parameters
- SSRC synchronization
- GB28181-compliant XML message formatting

## Architecture

The application consists of several components:

1. **Main Application** (`src/main.py`): Initializes and coordinates the components
2. **SIP Handler** (`src/sip_handler_pjsip.py`): Handles SIP messages and GB28181 protocol
3. **Media Streamer** (`src/media_streamer.py`): Manages GStreamer pipelines for video streaming
4. **File Scanner** (`src/file_scanner.py`): Scans directories for video files
5. **RTSP Handler** (`src/rtsp_handler.py`): Handles RTSP source connections
6. **GB28181 XML** (`src/gb28181_xml.py`): Generates XML messages according to GB28181 standard
7. **SIP Message Sender** (`src/gb28181_sip_sender.py`): Sends SIP messages with XML content

## Development Status

See the [tasks.md](tasks.md) file for current development status and planned features.

## Testing

To test with a GB28181 platform:

1. Configure the application with your GB28181 platform's SIP server details
2. Run the application
3. Use the GB28181 platform to query device info and catalog
4. Initiate a video stream from the GB28181 platform

## License

This project is open source software.

---

## 🐳 Docker Quickstart

### 1. Build the image

```bash
docker build -t gb28181-restreamer .

## Device Registration

The GB28181 Restreamer automatically registers with the SIP server using the configured device credentials. No manual device addition is required in WVP-pro. The device will appear in the device list once registration is successful.

### Registration Process
1. The application starts and loads the configuration
2. The SIP client automatically attempts to register with the server
3. Upon successful registration, the device appears in WVP-pro's device list
4. The device maintains its registration through periodic keepalive messages

### Troubleshooting Registration
If the device does not appear in WVP-pro:
1. Check the SIP server configuration in config.json
2. Verify network connectivity to the SIP server
3. Check the application logs for registration errors
4. Ensure the device ID and credentials match the expected format

