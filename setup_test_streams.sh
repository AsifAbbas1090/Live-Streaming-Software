#!/bin/bash

# Setup Test Streams for GB28181 Testing
# This script downloads test videos and sets up virtual RTSP streams

echo "Setting up test streams for GB28181 testing..."

# Create test-videos directory
mkdir -p test-videos
cd test-videos

# Download sample MP4 files from virtual-rtsp project
echo "Downloading test video files..."

# Download highway camera footage (10 minutes, 640x480)
if [ ! -f "highway-10min-640x480.mp4" ]; then
    echo "Downloading highway camera test video..."
    wget -O highway-10min-640x480.mp4 \
        "https://github.com/kerberos-io/virtual-rtsp/releases/download/v1.0.0/highway-10min-640x480-1.mp4"
fi

# Download another test video (different resolution)
if [ ! -f "highway-5min-1280x720.mp4" ]; then
    echo "Downloading HD test video..."
    wget -O highway-5min-1280x720.mp4 \
        "https://github.com/kerberos-io/virtual-rtsp/releases/download/v1.0.0/highway-5min-1280x720-1.mp4"
fi

# Create a symbolic link for the default sample.mp4
if [ -f "highway-10min-640x480.mp4" ]; then
    ln -sf highway-10min-640x480.mp4 sample.mp4
    echo "Created sample.mp4 link"
fi

cd ..

echo "Test videos downloaded successfully!"
echo ""
echo "Available test options:"
echo "1. Public RTSP Streams (ready to use):"
echo "   - Wowza Test Stream: rtsp://807e9439d5ca.entrypoint.cloud.wowza.com:1935/app-rC94792j/068b9c9a_stream2"
echo "   - Highway Camera: rtsp://170.93.143.139/rtplive/470011e600ef003a004ee33696235daa"
echo ""
echo "2. Local Video Files (downloaded):"
echo "   - test-videos/highway-10min-640x480.mp4"
echo "   - test-videos/highway-5min-1280x720.mp4"
echo ""
echo "To use local video files:"
echo "1. Enable the 'Local Test Video' source in config/config.json"
echo "2. Or run: docker run -p 8554:8554 -v \$(pwd)/test-videos:/videos -e SOURCE_URL=file:///videos/sample.mp4 kerberos/virtual-rtsp:1.0.6"
echo "3. Then use rtsp://localhost:8554/stream as your RTSP source"
echo ""
echo "To test with public streams:"
echo "1. The Wowza and Highway streams are already configured in config.json"
echo "2. Just run your GB28181 application: python src/main.py"
echo ""
echo "Setup complete! You can now test without physical cameras." 