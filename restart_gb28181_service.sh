#!/bin/bash

# Enhanced GB28181 Restreamer Service Restart Script
# This script safely restarts the GB28181 service with comprehensive monitoring

set -e  # Exit on error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="gb28181-restreamer"
PYTHON_SCRIPT="$SCRIPT_DIR/src/main.py"
CONFIG_FILE="$SCRIPT_DIR/config/config.json"
LOG_DIR="$SCRIPT_DIR/logs"
MONITOR_SCRIPT="$SCRIPT_DIR/src/live_sip_monitor.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} ${timestamp} - $message" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} ${timestamp} - $message" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} ${timestamp} - $message" ;;
    esac
    
    # Also log to file
    echo "[$level] $timestamp - $message" >> "$LOG_DIR/restart.log"
}

# Create logs directory if it doesn't exist
create_log_directory() {
    if [[ ! -d "$LOG_DIR" ]]; then
        mkdir -p "$LOG_DIR"
        log INFO "Created logs directory: $LOG_DIR"
    fi
}

# Check prerequisites
check_prerequisites() {
    log INFO "🔍 Checking prerequisites..."
    
    # Check if Python script exists
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        log ERROR "Python script not found: $PYTHON_SCRIPT"
        exit 1
    fi
    
    # Check if config file exists
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log ERROR "Config file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        log ERROR "Python3 is not installed or not in PATH"
        exit 1
    fi
    
    # Check if required Python modules are available
    python3 -c "import json, threading, subprocess, time" 2>/dev/null || {
        log ERROR "Required Python modules are not available"
        exit 1
    }
    
    # Check if pjsua is available
    if ! command -v pjsua &> /dev/null; then
        log WARN "pjsua is not installed. SIP functionality may not work."
        log INFO "Install pjsua with: sudo apt-get install pjsua-lib-bin"
    fi
    
    # Check if tcpdump is available for monitoring
    if ! command -v tcpdump &> /dev/null; then
        log WARN "tcpdump is not installed. Live monitoring may be limited."
        log INFO "Install tcpdump with: sudo apt-get install tcpdump"
    fi
    
    log INFO "✅ Prerequisites check completed"
}

# Find and stop existing processes
stop_existing_processes() {
    log INFO "🔍 Searching for existing GB28181 processes..."
    
    # Find Python processes running our script
    local pids=$(pgrep -f "$PYTHON_SCRIPT" || true)
    
    if [[ -n "$pids" ]]; then
        log INFO "Found existing GB28181 processes: $pids"
        
        # Try graceful shutdown first
        log INFO "🛑 Attempting graceful shutdown..."
        for pid in $pids; do
            if kill -TERM "$pid" 2>/dev/null; then
                log INFO "Sent SIGTERM to process $pid"
            fi
        done
        
        # Wait for graceful shutdown
        local wait_time=0
        local max_wait=10
        
        while [[ $wait_time -lt $max_wait ]]; do
            remaining_pids=$(pgrep -f "$PYTHON_SCRIPT" || true)
            if [[ -z "$remaining_pids" ]]; then
                log INFO "✅ All processes shut down gracefully"
                break
            fi
            sleep 1
            ((wait_time++))
        done
        
        # Force kill if still running
        remaining_pids=$(pgrep -f "$PYTHON_SCRIPT" || true)
        if [[ -n "$remaining_pids" ]]; then
            log WARN "⚠️ Forcing process termination..."
            for pid in $remaining_pids; do
                if kill -KILL "$pid" 2>/dev/null; then
                    log WARN "Force killed process $pid"
                fi
            done
        fi
    else
        log INFO "No existing GB28181 processes found"
    fi
    
    # Also stop any lingering pjsua processes
    local pjsua_pids=$(pgrep pjsua || true)
    if [[ -n "$pjsua_pids" ]]; then
        log INFO "Found lingering pjsua processes: $pjsua_pids"
        for pid in $pjsua_pids; do
            kill -KILL "$pid" 2>/dev/null || true
            log INFO "Killed pjsua process $pid"
        done
    fi
}

# Clean up temporary files
cleanup_temp_files() {
    log INFO "🧹 Cleaning up temporary files..."
    
    # Remove old debug files
    find "$SCRIPT_DIR" -name "catalog_response*.xml" -mtime +1 -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -name "catalog_debug*.xml" -mtime +1 -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -name "pjsua*.log" -mtime +1 -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -name "debug_catalog_response*.xml" -mtime +1 -delete 2>/dev/null || true
    
    # Clean up old monitor reports
    find "$SCRIPT_DIR" -name "live_sip_monitor_report*.json" -mtime +7 -delete 2>/dev/null || true
    find "$SCRIPT_DIR" -name "*_diagnostics_report.json" -mtime +7 -delete 2>/dev/null || true
    
    log INFO "✅ Cleanup completed"
}

# Validate configuration
validate_config() {
    log INFO "🔧 Validating configuration..."
    
    # Check if config is valid JSON
    if ! python3 -c "import json; json.load(open('$CONFIG_FILE'))" 2>/dev/null; then
        log ERROR "Invalid JSON in config file: $CONFIG_FILE"
        exit 1
    fi
    
    # Extract and validate key configuration values
    local device_id=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['sip']['device_id'])" 2>/dev/null || echo "")
    local server=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['sip']['server'])" 2>/dev/null || echo "")
    local stream_dir=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['stream_directory'])" 2>/dev/null || echo "")
    
    if [[ -z "$device_id" ]]; then
        log ERROR "Device ID not found in configuration"
        exit 1
    fi
    
    if [[ -z "$server" ]]; then
        log ERROR "SIP server not found in configuration"
        exit 1
    fi
    
    if [[ -z "$stream_dir" ]]; then
        log ERROR "Stream directory not found in configuration"
        exit 1
    fi
    
    if [[ ! -d "$stream_dir" ]]; then
        log ERROR "Stream directory does not exist: $stream_dir"
        exit 1
    fi
    
    log INFO "✅ Configuration validation completed"
    log INFO "   Device ID: $device_id"
    log INFO "   SIP Server: $server"
    log INFO "   Stream Directory: $stream_dir"
}

# Test basic functionality before starting
test_functionality() {
    log INFO "🧪 Testing basic functionality..."
    
    # Test video file scanning
    local video_count=$(find "$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['stream_directory'])")" -name "*.mp4" -o -name "*.avi" -o -name "*.mkv" | wc -l)
    log INFO "Found $video_count video files in stream directory"
    
    if [[ $video_count -eq 0 ]]; then
        log WARN "⚠️ No video files found. Catalog will be empty."
    fi
    
    # Test network connectivity to SIP server
    local server=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['sip']['server'])")
    local port=$(python3 -c "import json; config=json.load(open('$CONFIG_FILE')); print(config['sip']['port'])")
    
    if command -v nc &> /dev/null; then
        if nc -z -w3 "$server" "$port" 2>/dev/null; then
            log INFO "✅ Network connectivity to $server:$port OK"
        else
            log WARN "⚠️ Cannot connect to $server:$port"
        fi
    fi
    
    log INFO "✅ Functionality test completed"
}

# Start the service with enhanced monitoring
start_service() {
    log INFO "🚀 Starting GB28181 Restreamer service..."
    
    # Change to script directory
    cd "$SCRIPT_DIR"
    
    # Start the main service in the background
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local main_log="$LOG_DIR/gb28181_main_$timestamp.log"
    
    nohup python3 "$PYTHON_SCRIPT" > "$main_log" 2>&1 &
    local main_pid=$!
    
    log INFO "Started main service with PID: $main_pid"
    log INFO "Main service log: $main_log"
    
    # Wait a moment for the service to initialize
    sleep 3
    
    # Check if the service is still running
    if ! kill -0 "$main_pid" 2>/dev/null; then
        log ERROR "❌ Service failed to start or crashed immediately"
        log ERROR "Check the log file: $main_log"
        return 1
    fi
    
    log INFO "✅ Service appears to be running successfully"
    
    # Start live monitoring if available
    if [[ -f "$MONITOR_SCRIPT" ]]; then
        log INFO "🔍 Starting live SIP monitoring..."
        local monitor_log="$LOG_DIR/sip_monitor_$timestamp.log"
        
        nohup python3 "$MONITOR_SCRIPT" > "$monitor_log" 2>&1 &
        local monitor_pid=$!
        
        log INFO "Started SIP monitor with PID: $monitor_pid"
        log INFO "Monitor log: $monitor_log"
        
        # Give monitoring a moment to start
        sleep 2
        
        if ! kill -0 "$monitor_pid" 2>/dev/null; then
            log WARN "⚠️ SIP monitoring failed to start"
        else
            log INFO "✅ SIP monitoring active"
        fi
    fi
    
    return 0
}

# Monitor service health
monitor_service_health() {
    log INFO "🏥 Monitoring service health for 30 seconds..."
    
    local start_time=$(date +%s)
    local end_time=$((start_time + 30))
    local check_count=0
    
    while [[ $(date +%s) -lt $end_time ]]; do
        ((check_count++))
        
        # Check if main process is still running
        local main_pids=$(pgrep -f "$PYTHON_SCRIPT" || true)
        
        if [[ -z "$main_pids" ]]; then
            log ERROR "❌ Main service process has died!"
            return 1
        fi
        
        # Check for SIP registration status in logs
        if [[ $check_count -eq 10 ]]; then  # Check at 10 seconds
            local recent_logs=$(find "$LOG_DIR" -name "gb28181_main_*.log" -mmin -1 -exec tail -50 {} \; | grep -i "registration\|registered\|catalog" | tail -5)
            if [[ -n "$recent_logs" ]]; then
                log INFO "📊 Recent activity:"
                echo "$recent_logs" | while read -r line; do
                    log DEBUG "   $line"
                done
            fi
        fi
        
        sleep 3
    done
    
    log INFO "✅ Service health monitoring completed - service appears stable"
    return 0
}

# Display service status
show_service_status() {
    log INFO "📊 Service Status Summary"
    log INFO "========================="
    
    # Show running processes
    local main_pids=$(pgrep -f "$PYTHON_SCRIPT" || true)
    if [[ -n "$main_pids" ]]; then
        log INFO "✅ GB28181 main service running (PIDs: $main_pids)"
    else
        log ERROR "❌ GB28181 main service not running"
    fi
    
    local monitor_pids=$(pgrep -f "$MONITOR_SCRIPT" || true)
    if [[ -n "$monitor_pids" ]]; then
        log INFO "✅ SIP monitor running (PIDs: $monitor_pids)"
    else
        log INFO "ℹ️ SIP monitor not running"
    fi
    
    # Show latest log files
    local latest_main_log=$(find "$LOG_DIR" -name "gb28181_main_*.log" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    if [[ -n "$latest_main_log" ]]; then
        log INFO "📄 Latest main log: $latest_main_log"
    fi
    
    local latest_monitor_log=$(find "$LOG_DIR" -name "sip_monitor_*.log" -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    if [[ -n "$latest_monitor_log" ]]; then
        log INFO "📄 Latest monitor log: $latest_monitor_log"
    fi
    
    # Show recent errors
    if [[ -n "$latest_main_log" ]]; then
        local recent_errors=$(tail -100 "$latest_main_log" | grep -i "error\|failed\|exception" | tail -3)
        if [[ -n "$recent_errors" ]]; then
            log WARN "⚠️ Recent errors found:"
            echo "$recent_errors" | while read -r line; do
                log WARN "   $line"
            done
        fi
    fi
}

# Run diagnostic test
run_diagnostic_test() {
    log INFO "🔬 Running diagnostic test..."
    
    local diagnostic_script="$SCRIPT_DIR/debug_catalog_sync.py"
    if [[ -f "$diagnostic_script" ]]; then
        local diagnostic_log="$LOG_DIR/diagnostic_$(date +%Y%m%d_%H%M%S).log"
        
        if python3 "$diagnostic_script" > "$diagnostic_log" 2>&1; then
            log INFO "✅ Diagnostic test passed"
        else
            log WARN "⚠️ Diagnostic test found issues - check $diagnostic_log"
        fi
    else
        log INFO "ℹ️ Diagnostic script not found, skipping test"
    fi
}

# Main function
main() {
    log INFO "🎬 Starting GB28181 Restreamer restart process..."
    
    create_log_directory
    check_prerequisites
    stop_existing_processes
    cleanup_temp_files
    validate_config
    test_functionality
    
    if start_service; then
        if monitor_service_health; then
            run_diagnostic_test
            show_service_status
            log INFO "🎉 GB28181 Restreamer restart completed successfully!"
            log INFO "💡 To monitor live SIP traffic, check the monitor logs in $LOG_DIR"
            log INFO "💡 To view real-time logs: tail -f $LOG_DIR/gb28181_main_*.log"
        else
            log ERROR "❌ Service health check failed"
            exit 1
        fi
    else
        log ERROR "❌ Failed to start service"
        exit 1
    fi
}

# Handle script interruption
trap 'log WARN "Script interrupted by user"; exit 130' INT TERM

# Parse command line arguments
case "${1:-}" in
    --help|-h)
        echo "GB28181 Restreamer Service Restart Script"
        echo "Usage: $0 [--help]"
        echo ""
        echo "This script safely restarts the GB28181 Restreamer service with"
        echo "comprehensive monitoring and diagnostics."
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac 