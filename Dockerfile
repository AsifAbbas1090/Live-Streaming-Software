# Use NVIDIA Jetson-compatible Ubuntu base (for Orin NX)
FROM nvcr.io/nvidia/l4t-base:r35.3.1

# System dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    && apt-get clean

# Set work directory
WORKDIR /app

# Copy source code
COPY ./src ./src
COPY ./config ./config

# Install Python dependencies (if any)
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Expose standard SIP port (5060 or 5061 for TLS)
EXPOSE 5060 5061

# Set entry point
CMD ["python3", "src/main.py"]
