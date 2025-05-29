# src/rtsp_handler.py

import gi
import threading
import time
import subprocess
import os
import random
from datetime import datetime, timedelta

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from logger import log

Gst.init(None)

class RTSPConnectionStatus:
    """Track RTSP connection status and health metrics"""
    def __init__(self):
        self.connected = False
        self.last_connected_time = None
        self.last_error_time = None
        self.connection_attempts = 0
        self.errors = 0
        self.recoveries = 0
        self.last_recovery_time = None
        self.watchdog_time = time.time()
        self.health_status = "unknown"
        self.total_uptime = 0
        self.last_status_update = time.time()
        
    def mark_connected(self):
        """Mark the connection as successful"""
        self.connected = True
        self.last_connected_time = time.time()
        self.health_status = "good"
        self.watchdog_time = time.time()
        
    def mark_disconnected(self):
        """Mark the connection as disconnected"""
        if self.connected:
            self.connected = False
            now = time.time()
            if self.last_connected_time:
                # Track total uptime
                self.total_uptime += (now - self.last_connected_time)
        
    def mark_error(self, error_msg):
        """Record an error occurrence"""
        self.errors += 1
        self.last_error_time = time.time()
        self.connected = False
        
        # Evaluate health status
        if self.errors > 10:
            self.health_status = "critical"
        elif self.errors > 5:
            self.health_status = "poor"
        elif self.errors > 2:
            self.health_status = "warning"
        else:
            self.health_status = "degraded"
        
    def mark_recovery(self):
        """Record a recovery attempt"""
        self.recoveries += 1
        self.last_recovery_time = time.time()
    
    def get_status_report(self):
        """Get a status report dictionary"""
        now = time.time()
        uptime_seconds = self.total_uptime
        if self.connected and self.last_connected_time:
            uptime_seconds += (now - self.last_connected_time)
            
        return {
            "connected": self.connected,
            "health": self.health_status,
            "connection_attempts": self.connection_attempts,
            "errors": self.errors,
            "recoveries": self.recoveries,
            "uptime_seconds": int(uptime_seconds),
            "last_connected": self.last_connected_time,
            "last_error": self.last_error_time,
            "last_recovery": self.last_recovery_time
        }


class RTSPHandler:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.pipeline = None
        self.mainloop = None
        self.mainloop_thread = None
        self.monitor_thread = None
        self.running = False
        self.retry_count = 0
        self.max_retries = 10  # Increased max retries
        self.retry_backoff_time = 3  # Initial backoff time in seconds
        self.status = RTSPConnectionStatus()
        self.last_keepalive = time.time()
        self.keepalive_interval = 30  # seconds
        self.health_check_interval = 5  # seconds
        self.recovery_attempts = 0
        self.max_recovery_attempts = 3

    def start(self):
        """Start the RTSP stream with improved error handling"""
        log.info(f"[RTSP] Launching stream: {self.rtsp_url}")
        self.status.connection_attempts += 1
        
        # Create GStreamer pipeline
        try:
            # Enhanced pipeline with timeout and reliable error handling
            self.pipeline = self._create_pipeline(self.rtsp_url)
            
            # Add bus watch
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", self._on_bus_message)
            
            # Start the pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                log.error("[RTSP] Failed to start pipeline")
                self.status.mark_error("Failed to start pipeline")
                return False
                
            log.info("[RTSP] GStreamer RTSP pipeline started.")
            self.running = True
            
            # Start a GLib mainloop in a separate thread
            if not self.mainloop:
                self.mainloop = GLib.MainLoop()
                self.mainloop_thread = threading.Thread(target=self._run_mainloop, daemon=True)
                self.mainloop_thread.start()
            
            # Start monitoring thread if not running
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self._monitor_stream, daemon=True)
                self.monitor_thread.start()
            
            return True
        except Exception as e:
            log.exception(f"[RTSP] Error starting RTSP stream: {e}")
            self.status.mark_error(str(e))
            return False
    
    def _run_mainloop(self):
        """Run the GLib mainloop with exception handling"""
        try:
            self.mainloop.run()
        except Exception as e:
            log.error(f"[RTSP] Error in GLib mainloop: {e}")
            # Try to recover by creating a new mainloop
            self.mainloop = None
    
    def _monitor_stream(self):
        """Continuously monitor stream health and handle reconnections"""
        log.info(f"[RTSP] Starting stream health monitoring for {self.rtsp_url}")
        
        while self.running:
            try:
                # Update watchdog
                self.status.watchdog_time = time.time()
                
                # Check if RTSP connection is still alive
                self._check_stream_health()
                
                # Send periodic keepalive for RTSP if needed
                if time.time() - self.last_keepalive > self.keepalive_interval:
                    self._send_keepalive()
                
                # Sleep before next check
                time.sleep(self.health_check_interval)
            except Exception as e:
                log.error(f"[RTSP] Error in monitor thread: {e}")
                time.sleep(5)  # Brief pause to avoid tight error loop
    
    def _check_stream_health(self):
        """Check if the stream is healthy and attempt recovery if needed"""
        if not self.pipeline:
            return
            
        # Check pipeline state
        state_return = self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
        
        if state_return[0] == Gst.StateChangeReturn.SUCCESS:
            current_state = state_return[1]
            
            if current_state == Gst.State.PLAYING:
                # Connection is good
                if not self.status.connected:
                    log.info(f"[RTSP] Connection to {self.rtsp_url} established")
                    self.status.mark_connected()
                    self.retry_count = 0  # Reset retry counter on successful connection
                    self.retry_backoff_time = 3  # Reset backoff time
            else:
                log.warning(f"[RTSP] Stream not in PLAYING state, current state: {current_state.value_nick}")
                if self.status.connected:
                    self.status.mark_disconnected()
        else:
            log.warning(f"[RTSP] Failed to get pipeline state: {state_return[0].value_nick}")
            if self.status.connected:
                self.status.mark_disconnected()
    
    def _send_keepalive(self):
        """Send keepalive message to RTSP server if needed"""
        # Some RTSP servers need periodic activity to maintain connection
        if self.pipeline and self.status.connected:
            log.debug(f"[RTSP] Sending keepalive for {self.rtsp_url}")
            # We don't need to do anything specific here as GStreamer's rtspsrc 
            # handles keepalives internally, but we can check for errors
            
            # Update last keepalive time
            self.last_keepalive = time.time()

    def _on_bus_message(self, bus, message):
        """Handle GStreamer bus messages with enhanced error recovery"""
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.error(f"[RTSP] GStreamer error: {err.message}")
            log.debug(f"[RTSP] Debug info: {debug}")
            
            # Mark connection status
            self.status.mark_error(err.message)
            
            # Check for specific error types
            if "not-linked" in debug:
                log.warning("[RTSP] Pipeline elements not linked properly, attempting to fix...")
                self._fix_pipeline_linking()
            elif "timeout" in err.message.lower():
                log.warning("[RTSP] Connection timeout, increasing buffer size...")
                self._increase_buffer_size()
            
            # Clean up and retry with exponential backoff
            self._cleanup_pipeline()
            
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                
                # Calculate backoff time with randomization to avoid thundering herd
                backoff_seconds = min(60, self.retry_backoff_time * (1.5 ** (self.retry_count - 1)))
                jitter = random.uniform(0.5, 1.5)
                wait_time = backoff_seconds * jitter
                
                log.info(f"[RTSP] Will retry {self.rtsp_url} in {wait_time:.1f}s " +
                        f"(attempt {self.retry_count}/{self.max_retries})...")
                
                # Schedule retry
                self.status.mark_recovery()
                threading.Timer(wait_time, self._retry_connect).start()
            else:
                log.error(f"[RTSP] Max retries ({self.max_retries}) reached for {self.rtsp_url}")
                log.info(f"[RTSP] Will attempt again in 5 minutes")
                
                # Reset retry count and try again after a longer pause
                self.status.mark_recovery()
                threading.Timer(300, self._reset_and_retry).start()
            
        elif t == Gst.MessageType.EOS:
            log.info("[RTSP] End of stream")
            self.status.mark_disconnected()
            self._cleanup_pipeline()
            
            # For RTSP streams, an EOS should trigger a reconnect attempt
            log.info("[RTSP] Reconnecting after EOS")
            self.status.mark_recovery()
            threading.Timer(3, self._retry_connect).start()
            
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old, new, pending = message.parse_state_changed()
                log.debug(f"[RTSP] Pipeline state changed from {old.value_nick} to {new.value_nick}")
                
                if new == Gst.State.PLAYING:
                    log.info("[RTSP] Pipeline is now PLAYING")
                    self.status.mark_connected()
                    self.retry_count = 0  # Reset retry count on successful play
                elif new == Gst.State.PAUSED:
                    log.info("[RTSP] Pipeline is PAUSED, checking for issues...")
                    self._check_pipeline_health()

    def _retry_connect(self):
        """Retry connecting to RTSP stream"""
        if not self.running:
            return
            
        log.info(f"[RTSP] Attempting to reconnect to {self.rtsp_url}")
        self.start()
    
    def _reset_and_retry(self):
        """Reset retry counter and attempt to connect again"""
        self.retry_count = 0
        self.retry_backoff_time = 3  # Reset backoff time
        if self.running:
            self._retry_connect()
    
    def _cleanup_pipeline(self):
        """Clean up pipeline resources without stopping the handler"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def stop(self):
        """Stop the RTSP stream and all related threads"""
        log.info(f"[RTSP] Stopping stream: {self.rtsp_url}")
        self.running = False
        
        # Stop the pipeline
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            
        # Stop the mainloop
        if self.mainloop and self.mainloop.is_running():
            self.mainloop.quit()
        
        # Mark disconnected
        self.status.mark_disconnected()
        
        log.info(f"[RTSP] Stream stopped: {self.rtsp_url}")
    
    def get_status(self):
        """Get current status of the RTSP handler"""
        return {
            "url": self.rtsp_url,
            "running": self.running,
            "retry_count": self.retry_count,
            "stream_status": self.status.get_status_report()
        }

    def _create_pipeline(self, rtsp_url):
        """Create GStreamer pipeline for RTSP stream with improved error handling"""
        pipeline_str = (
            f'rtspsrc location="{rtsp_url}" latency=0 buffer-mode=auto '
            'tcp-timeout=5000000 retry=3 connection-speed=1000000 ! '
            'rtph264depay ! h264parse config-interval=1 ! '
            'queue max-size-buffers=3000 max-size-bytes=0 max-size-time=0 ! '
            'videoconvert ! video/x-raw,format=RGB ! '
            'queue max-size-buffers=3000 max-size-bytes=0 max-size-time=0 ! '
            'fakesink sync=false'
        )
        
        log.debug(f"Pipeline: {pipeline_str}")
        return Gst.parse_launch(pipeline_str)

    def _on_pipeline_state_change(self, bus, message):
        """Handle pipeline state changes with detailed monitoring"""
        if message.type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, pending_state = message.parse_state_changed()
            if message.src == self.pipeline:
                log.debug(f"[RTSP] Pipeline state changed from {old_state.value_nick} to {new_state.value_nick}")
                
                # Record state transition time
                now = time.time()
                if not hasattr(self, '_last_state_change'):
                    self._last_state_change = {}
                self._last_state_change[new_state.value_nick] = now
                
                # Check for state transition issues
                if old_state == Gst.State.READY and new_state == Gst.State.PAUSED:
                    # Check if we spent too long in READY state
                    if 'ready' in self._last_state_change:
                        ready_duration = now - self._last_state_change['ready']
                        if ready_duration > 2.0:  # More than 2 seconds in READY state
                            log.warning(f"[RTSP] Spent {ready_duration:.1f}s in READY state")
                            self._check_pipeline_health()
                
                elif old_state == Gst.State.PAUSED and new_state == Gst.State.PLAYING:
                    # Check if we spent too long in PAUSED state
                    if 'paused' in self._last_state_change:
                        paused_duration = now - self._last_state_change['paused']
                        if paused_duration > 1.0:  # More than 1 second in PAUSED state
                            log.warning(f"[RTSP] Spent {paused_duration:.1f}s in PAUSED state")
                            self._check_pipeline_health()
                
                # Handle state transition issues
                if new_state == Gst.State.PLAYING:
                    # Check if pipeline is actually playing
                    ret, state, pending = self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
                    if state != Gst.State.PLAYING:
                        log.warning("[RTSP] Pipeline failed to reach PLAYING state")
                        self._handle_pipeline_error()
                elif new_state == Gst.State.PAUSED:
                    # Check if pipeline is actually paused
                    ret, state, pending = self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
                    if state != Gst.State.PAUSED:
                        log.warning("[RTSP] Pipeline failed to reach PAUSED state")
                        self._handle_pipeline_error()
                    
                # Log state transition timing
                if old_state != Gst.State.NULL:
                    transition_time = now - self._last_state_change.get(old_state.value_nick, now)
                    log.debug(f"[RTSP] State transition {old_state.value_nick}->{new_state.value_nick} took {transition_time:.3f}s")

    def _handle_pipeline_error(self):
        """Handle pipeline errors and attempt recovery"""
        if self.recovery_attempts < self.max_recovery_attempts:
            self.recovery_attempts += 1
            log.info(f"Attempting pipeline recovery (attempt {self.recovery_attempts}/{self.max_recovery_attempts})")
            
            # Stop the pipeline
            self.pipeline.set_state(Gst.State.NULL)
            
            # Recreate pipeline with new configuration
            self.pipeline = self._create_pipeline(self.rtsp_url)
            
            # Add bus watch
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect('message', self._on_pipeline_state_change)
            
            # Start pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                log.error("Failed to restart pipeline")
            else:
                log.info("Pipeline restarted successfully")
        else:
            log.error("Max recovery attempts reached. Pipeline needs manual intervention.")

    def _fix_pipeline_linking(self):
        """Attempt to fix pipeline linking issues"""
        if not self.pipeline:
            return
        
        # Get the pipeline elements
        elements = self.pipeline.iterate_elements()
        
        # Check for unlinked pads
        for element in elements:
            pads = element.iterate_pads()
            for pad in pads:
                if not pad.is_linked():
                    log.warning(f"[RTSP] Found unlinked pad: {element.name}:{pad.name}")
                    
                    # Try to link the pad
                    if pad.is_src():
                        peer = pad.get_peer()
                        if peer:
                            pad.link(peer)
                            log.info(f"[RTSP] Linked pad {element.name}:{pad.name}")

    def _increase_buffer_size(self):
        """Increase buffer sizes in the pipeline"""
        if not self.pipeline:
            return
        
        # Get queue elements
        elements = self.pipeline.iterate_elements()
        for element in elements:
            if element.get_factory().name == 'queue':
                # Increase max-size-buffers
                element.set_property('max-size-buffers', 5000)
                # Increase max-size-bytes
                element.set_property('max-size-bytes', 0)  # Unlimited
                # Increase max-size-time
                element.set_property('max-size-time', 0)  # Unlimited
                log.info(f"[RTSP] Increased buffer size for queue element {element.name}")

    def _check_pipeline_health(self):
        """Check pipeline health and attempt recovery if needed"""
        if not self.pipeline:
            return
        
        # Check if pipeline is actually paused
        ret, state, pending = self.pipeline.get_state(Gst.CLOCK_TIME_NONE)
        if state != Gst.State.PAUSED:
            log.warning("[RTSP] Pipeline failed to reach PAUSED state")
            self._handle_pipeline_error()
            return
        
        # Check for buffer underruns
        elements = self.pipeline.iterate_elements()
        for element in elements:
            if element.get_factory().name == 'queue':
                # Check queue fill level
                fill_level = element.get_property('current-level-buffers')
                max_level = element.get_property('max-size-buffers')
                if fill_level > max_level * 0.9:  # 90% full
                    log.warning(f"[RTSP] Queue {element.name} is almost full ({fill_level}/{max_level})")
                    self._increase_buffer_size()


# Global registry of active RTSP handlers
rtsp_handlers = {}

def start_rtsp_stream(rtsp_url):
    """Start an RTSP stream and register it in the global registry"""
    global rtsp_handlers
    
    # Check if already exists
    if rtsp_url in rtsp_handlers:
        log.warning(f"[RTSP] Stream already exists for {rtsp_url}")
        
        # If the handler exists but is not running, restart it
        if not rtsp_handlers[rtsp_url].running:
            log.info(f"[RTSP] Restarting existing stream for {rtsp_url}")
            rtsp_handlers[rtsp_url].start()
        
        return rtsp_handlers[rtsp_url]
    
    # Create and start a new handler
    handler = RTSPHandler(rtsp_url)
    if handler.start():
        rtsp_handlers[rtsp_url] = handler
        log.info(f"[RTSP] Stream registered: {rtsp_url}")
    else:
        log.error(f"[RTSP] Failed to start stream: {rtsp_url}")
    
    return handler

def stop_rtsp_stream(rtsp_url):
    """Stop an RTSP stream by URL"""
    global rtsp_handlers
    
    if rtsp_url in rtsp_handlers:
        handler = rtsp_handlers[rtsp_url]
        handler.stop()
        del rtsp_handlers[rtsp_url]
        log.info(f"[RTSP] Stream removed: {rtsp_url}")
        return True
    
    log.warning(f"[RTSP] No stream found for {rtsp_url}")
    return False

def get_rtsp_status():
    """Get status of all active RTSP streams"""
    global rtsp_handlers
    
    status = {}
    for url, handler in rtsp_handlers.items():
        status[url] = handler.get_status()
    
    return status

def cleanup_all_streams():
    """Stop all RTSP streams and clean up resources"""
    global rtsp_handlers
    
    log.info(f"[RTSP] Stopping all {len(rtsp_handlers)} streams")
    
    for url, handler in list(rtsp_handlers.items()):
        try:
            handler.stop()
        except Exception as e:
            log.error(f"[RTSP] Error stopping stream {url}: {e}")
    
    rtsp_handlers.clear()
    log.info("[RTSP] All streams stopped")

def play_video_file(file_path):
    """
    Play a local video file with GStreamer subprocess
    """
    from pathlib import Path
    import sys
    
    if not file_path:
        log.error("[VIDEO] No file path provided for playback")
        return
        
    file_uri = Path(file_path).as_uri()
    log.info(f"[VIDEO] Playing file: {file_uri}")

    # Use direct command without GSTREAMER_PATH which wasn't defined
    gst_command = [
        "gst-launch-1.0",
        "urisourcebin", f"uri={file_uri}", "!",
        "decodebin", "!",
        "videoconvert", "!",
        "autovideosink sync=false"  # Use autovideosink for actual viewing
    ]

    try:
        subprocess.Popen(gst_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info("[VIDEO] GStreamer playback started.")
    except Exception as e:
        log.exception(f"[VIDEO] Playback failed: {e}")
