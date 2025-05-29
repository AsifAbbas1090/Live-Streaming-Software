#!/bin/bash

# Exit on error
set -e

echo "Installing GB28181 Restreamer dependencies..."

# Use Python to detect architecture
ARCH=$(python3 -c "
import platform
import sys
machine = platform.machine().lower()
if machine in ['x86_64', 'amd64']:
    print('amd64')
elif machine in ['aarch64', 'arm64', 'armv8l']:
    print('arm64')
elif machine in ['armv7l', 'armv6l']:
    print('arm')
else:
    print(machine)
")

echo "Detected architecture: $ARCH"

# Update package lists
sudo apt-get update

# Install basic dependencies
echo "Installing basic dependencies..."
sudo apt-get install -y \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-rtsp \
    ffmpeg \
    screen \
    build-essential \
    git \
    wget \
    libssl-dev \
    libsrtp2-dev \
    libspeex-dev \
    libspeexdsp-dev \
    libopus-dev \
    libopusfile-dev \
    libopusfile0 \
    libopus0

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Build PJSIP from source
echo "Building PJSIP from source..."
if [ ! -d "pjproject" ]; then
    git clone https://github.com/pjsip/pjproject.git
fi
cd pjproject
./configure --enable-shared --disable-sound --disable-video --disable-opencore-amr
make dep && make
sudo make install
sudo ldconfig
cd ..

# Check for Go installation
if ! command -v go &> /dev/null; then
    echo "Installing Go..."
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "arm" ]; then
        wget https://go.dev/dl/go1.21.0.linux-arm64.tar.gz
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf go1.21.0.linux-arm64.tar.gz
        rm go1.21.0.linux-arm64.tar.gz
    else
        wget https://go.dev/dl/go1.21.0.linux-amd64.tar.gz
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf go1.21.0.linux-amd64.tar.gz
        rm go1.21.0.linux-amd64.tar.gz
    fi
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
    source ~/.bashrc
fi

# Build rtsp-simple-server
echo "Building rtsp-simple-server for $ARCH..."
git clone https://github.com/aler9/rtsp-simple-server.git
cd rtsp-simple-server

# Set GOARCH based on detected architecture
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "arm" ]; then
    export GOARCH=arm64
else
    export GOARCH=amd64
fi

# Build with specific GOOS and GOARCH
export GOOS=linux
go build -v
if [ $? -ne 0 ]; then
    echo "Error: Failed to build rtsp-simple-server"
    exit 1
fi

# Verify the binary
file rtsp-simple-server
sudo mv rtsp-simple-server /usr/local/bin/
cd ..
rm -rf rtsp-simple-server

echo "Dependencies installed successfully!" 