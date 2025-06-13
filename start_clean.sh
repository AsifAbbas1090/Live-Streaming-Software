#!/bin/bash

# Clean startup script for GB28181 Restreamer
# Suppresses GStreamer critical warnings while preserving important logs

echo "🚀 Starting GB28181 Restreamer with clean output..."

# Set environment variables to suppress GStreamer warnings
export GST_DEBUG=0
export GST_DEBUG_NO_COLOR=1
export GST_DEBUG_FILE=/dev/null
export GST_REGISTRY_FORK=no
export G_MESSAGES_DEBUG=""

# Kill any existing instances
pkill -f "python3.*main.py" 2>/dev/null || true
sleep 2

# Start the application with filtered output
# Filter out GStreamer critical warnings but keep important messages
python3 src/main.py 2>&1 | grep -v -E "(GStreamer-CRITICAL|gst_segment_to_running_time|assertion.*segment.*format.*failed)" | \
while IFS= read -r line; do
    # Only show lines that contain important information
    if [[ "$line" =~ (ERROR|WARNING|INFO|✅|❌|🎯|🚀|📊|💓) ]] || [[ "$line" =~ ^[[:space:]]*$ ]]; then
        echo "$line"
    fi
done 