#!/bin/bash

# GB28181 Restreamer Safe Startup Script
# This script provides crash protection and automatic recovery

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MAX_CRASHES=5
CRASH_COUNT=0
RESTART_DELAY=5

echo -e "${BLUE}🚀 GB28181 Restreamer Safe Startup${NC}"
echo -e "${BLUE}=====================================${NC}"

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
    # Kill any remaining processes
    pkill -f "python3 src/main.py" 2>/dev/null || true
    pkill -f "pjsua" 2>/dev/null || true
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Function to check system requirements
check_requirements() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python3 not found${NC}"
        exit 1
    fi
    
    # Check GStreamer
    if ! python3 -c "import gi; gi.require_version('Gst', '1.0')" 2>/dev/null; then
        echo -e "${RED}❌ GStreamer Python bindings not found${NC}"
        exit 1
    fi
    
    # Check pjsua
    if ! command -v pjsua &> /dev/null; then
        echo -e "${RED}❌ pjsua not found${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All requirements satisfied${NC}"
}

# Function to set up crash protection environment
setup_crash_protection() {
    echo -e "${BLUE}🛡️ Setting up crash protection...${NC}"
    
    # Set GStreamer environment variables to prevent crashes
    export GST_DEBUG_NO_COLOR=1
    export GST_DEBUG=1
    export GST_DEBUG_DUMP_DOT_DIR=/tmp/gst-debug
    
    # Disable GStreamer registry forking to prevent crashes
    export GST_REGISTRY_FORK=no
    
    # Set memory limits to prevent runaway processes
    ulimit -v 2097152  # 2GB virtual memory limit
    ulimit -m 1048576  # 1GB resident memory limit
    
    # Create debug directory
    mkdir -p /tmp/gst-debug
    
    echo -e "${GREEN}✅ Crash protection enabled${NC}"
}

# Function to start the application with monitoring
start_application() {
    echo -e "${BLUE}🎬 Starting GB28181 Restreamer...${NC}"
    
    cd "$(dirname "$0")"
    
    # Start with timeout and crash detection
    timeout 3600 python3 src/main.py &
    APP_PID=$!
    
    # Monitor the application
    while kill -0 $APP_PID 2>/dev/null; do
        sleep 1
    done
    
    # Check exit status
    wait $APP_PID
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 139 ]; then
        echo -e "${RED}💥 Segmentation fault detected (exit code 139)${NC}"
        return 139
    elif [ $EXIT_CODE -eq 124 ]; then
        echo -e "${YELLOW}⏰ Application timeout (1 hour limit)${NC}"
        return 124
    elif [ $EXIT_CODE -ne 0 ]; then
        echo -e "${RED}❌ Application crashed with exit code: $EXIT_CODE${NC}"
        return $EXIT_CODE
    else
        echo -e "${GREEN}✅ Application exited normally${NC}"
        return 0
    fi
}

# Main execution loop
main() {
    check_requirements
    setup_crash_protection
    
    while true; do
        echo -e "\n${BLUE}📊 Attempt $((CRASH_COUNT + 1))/${MAX_CRASHES}${NC}"
        
        if start_application; then
            # Normal exit
            echo -e "${GREEN}🎉 Application completed successfully${NC}"
            break
        else
            EXIT_CODE=$?
            CRASH_COUNT=$((CRASH_COUNT + 1))
            
            if [ $CRASH_COUNT -ge $MAX_CRASHES ]; then
                echo -e "${RED}💀 Maximum crash limit reached (${MAX_CRASHES}). Giving up.${NC}"
                exit 1
            fi
            
            if [ $EXIT_CODE -eq 139 ]; then
                echo -e "${YELLOW}🔄 Segfault detected. Restarting in ${RESTART_DELAY} seconds...${NC}"
                echo -e "${YELLOW}💡 This restart should use the H.264 fallback pipeline${NC}"
            else
                echo -e "${YELLOW}🔄 Restarting in ${RESTART_DELAY} seconds...${NC}"
            fi
            
            sleep $RESTART_DELAY
            
            # Increase restart delay for subsequent crashes
            RESTART_DELAY=$((RESTART_DELAY + 2))
        fi
    done
}

# Run main function
main "$@" 