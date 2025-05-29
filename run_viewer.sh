#!/bin/bash

# Run GB28181 Restreamer Viewer
# This script will:
# 1. Start the RTSP server
# 2. Stream a video file to the RTSP server
# 3. Start the GB28181 restreamer
# 4. Launch the web viewer

# Color codes for prettier output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Command line arguments
COMMAND=$1

# Check for valid commands
if [ "$COMMAND" == "logs" ]; then
    echo -e "${YELLOW}Viewing logs...${NC}"
    tail -f stream_viewer.log
    exit 0
elif [ "$COMMAND" == "stop" ]; then
    echo -e "\n${YELLOW}Stopping all services...${NC}"
    pkill -f rtsp-simple-server || true
    pkill -f "ffmpeg.*rtsp://localhost:8554/test" || true
    pkill -f "python3.*main.py" || true
    pkill -f "python3.*stream_server.py" || true
    echo -e "${GREEN}All services stopped${NC}"
    exit 0x
fi

# Create necessary directories
mkdir -p stream
mkdir -p logs

echo -e "${BLUE}====================================${NC}"
echo -e "${GREEN}GB28181 Restreamer Complete Setup${NC}"
echo -e "${BLUE}====================================${NC}"

# Make sure we can run everything
chmod +x ./rtsp-simple-server
chmod +x ./stream_server.py

# Kill any running instances
echo -e "\n${YELLOW}Cleaning up any running processes...${NC}"
pkill -f rtsp-simple-server || true
pkill -f "ffmpeg.*rtsp://localhost:8554/test" || true
pkill -f "python3.*main.py" || true
pkill -f "python3.*stream_server.py" || true
sleep 1

# Step 1: Start RTSP server
echo -e "\n${YELLOW}Step 1: Starting RTSP server...${NC}"
screen -dmS rtsp-server ./rtsp-simple-server
sleep 2
if pgrep -f rtsp-simple-server > /dev/null; then
    echo -e "${GREEN}✓ RTSP server started${NC}"
else
    echo -e "${RED}✗ Failed to start RTSP server${NC}"
    exit 1
fi

# Step 2: Stream video to RTSP server
echo -e "\n${YELLOW}Step 2: Streaming video to RTSP server...${NC}"
if [ ! -f ./sample_videos/Entryyy.mp4 ]; then
    echo -e "${RED}Error: Sample video not found at ./sample_videos/Entryyy.mp4${NC}"
    echo "Please check that the video file exists"
    exit 1
fi

screen -dmS rtsp-stream ffmpeg -re -i sample_videos/Entryyy.mp4 -c:v copy -c:a copy -f rtsp rtsp://localhost:8554/test
sleep 2
if pgrep -f "ffmpeg.*rtsp://localhost:8554/test" > /dev/null; then
    echo -e "${GREEN}✓ Streaming video to RTSP server${NC}"
else
    echo -e "${RED}✗ Failed to start FFMPEG streaming${NC}"
    # Continue anyway as this might not be fatal
fi

# Step 3: Start GB28181 restreamer
echo -e "\n${YELLOW}Step 3: Starting GB28181 restreamer...${NC}"
screen -dmS gb28181-restreamer python3 src/main.py
sleep 2
if pgrep -f "python3.*main.py" > /dev/null; then
    echo -e "${GREEN}✓ GB28181 restreamer started${NC}"
else
    echo -e "${RED}✗ Failed to start GB28181 restreamer${NC}"
    # Continue anyway
fi

# Step 4: Launch web viewer
echo -e "\n${YELLOW}Step 4: Starting web viewer...${NC}"
screen -dmS web-viewer python3 stream_server.py
sleep 2
if pgrep -f "python3.*stream_server.py" > /dev/null; then
    echo -e "${GREEN}✓ Web viewer started${NC}"
else
    echo -e "${RED}✗ Failed to start web viewer${NC}"
    exit 1
fi

# Display server IP for easy access
IP_ADDRESS=$(hostname -I | cut -d' ' -f1)
echo -e "\n${BLUE}====================================${NC}"
echo -e "${GREEN}All services are running!${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "\nOpen your web browser and go to:"
echo -e "${YELLOW}http://${IP_ADDRESS}:8080${NC}"
echo -e "\nYou should see both the input RTSP stream and the output GB28181 stream."
echo -e "If videos are not playing, try refreshing the page or clicking the reload buttons."
echo -e "\nTo view logs: ${BLUE}./run_viewer.sh logs${NC}"
echo -e "\nTo manage the running services:"
echo -e "  ${BLUE}screen -r rtsp-server${NC}       - RTSP server console"
echo -e "  ${BLUE}screen -r rtsp-stream${NC}       - FFMPEG streaming console"
echo -e "  ${BLUE}screen -r gb28181-restreamer${NC} - GB28181 restreamer console"
echo -e "  ${BLUE}screen -r web-viewer${NC}        - Web viewer console"
echo -e "\nTo stop everything: ${BLUE}./run_viewer.sh stop${NC}" 