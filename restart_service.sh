#!/bin/bash

echo "🔄 Restarting GB28181 Service..."

# Kill any existing processes
echo "🛑 Stopping existing services..."
pkill -f "python3 src/main.py" || true
sleep 2

# Make sure the port is free
echo "🔍 Checking port availability..."
netstat -tuln | grep :5080 || echo "Port 5080 is free"

# Clean old logs
echo "🧹 Cleaning old logs..."
rm -f service.log pjsua.log

# Start the service with enhanced logging
echo "🚀 Starting service with debug logging..."
cd /home/ubuntu/rstp/gb28181-restreamer
nohup python3 src/main.py > service.log 2>&1 &

# Wait for startup
echo "⏳ Waiting for service to start..."
sleep 5

# Check if service is running
PID=$(pgrep -f "python3 src/main.py")
if [ -n "$PID" ]; then
    echo "✅ Service started successfully (PID: $PID)"
    echo "📊 Service status:"
    ps aux | grep "$PID" | grep -v grep
    echo ""
    echo "📝 Monitoring logs for 10 seconds..."
    timeout 10 tail -f service.log &
    sleep 10
    kill $! 2>/dev/null || true
    echo ""
    echo "🎯 Service is ready for testing!"
else
    echo "❌ Failed to start service"
    echo "📝 Last few lines of log:"
    tail -20 service.log || echo "No log file found"
fi 