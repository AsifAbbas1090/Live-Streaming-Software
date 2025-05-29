# src/media_streamer.py

import gi
import os
import time
import threading
import subprocess
import numpy as np
from datetime import datetime
import binascii
import cv2

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GLib, GObject
from gi.repository import GstApp

from logger import log

Gst.init(None)

class MediaStreamer:
    def __init__(self, config):
        self.pipelines = {}  # Dictionary to store multiple pipelines
        self.config = config
        self.streams_info = {}  # Dictionary to store info for multiple streams
        self.main_loop = None
        self.main_loop_thread = None
        self.health_check_thread = None
        self.running = False
        self.stream_health = {}  # Dictionary to store health info for multiple streams
        
        # For appsink/appsrc handling
        self.frame_processors = {}  # Dictionary to store frame processor callbacks
        self.appsink_callbacks = {}  # Store appsink callbacks
        self.appsrc_elements = {}   # Store appsrc elements
        self.processing_enabled = {}  # Track if processing is enabled for a stream
        
        # Dictionary of named processor functions
        self.named_processors = {}

    def start_glib_loop(self):
        """Start GLib main loop in a separate thread for event handling"""
        if self.main_loop is not None:
            return
            
        self.main_loop = GLib.MainLoop()
        self.main_loop_thread = threading.Thread(target=self._run_glib_loop, daemon=True)
        self.main_loop_thread.start()
        log.info("[STREAM] GLib main loop started")
    
    def _run_glib_loop(self):
        """Run the GLib main loop"""
        self.running = True
        try:
            self.main_loop.run()
        except Exception as e:
            log.error(f"[STREAM] Error in GLib main loop: {e}")
        finally:
            self.running = False
    
    def start_health_monitoring(self):
        """Start a thread to monitor stream health"""
        if self.health_check_thread is not None and self.health_check_thread.is_alive():
            return
            
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        log.info("[STREAM] Stream health monitoring started")
    
    def _health_check_loop(self):
        """Periodically check stream health and attempt recovery if needed"""
        check_interval = 5  # seconds
        
        while self.running:
            try:
                # Check health for each active stream
                for stream_id in list(self.pipelines.keys()):
                    self._check_stream_health(stream_id)
                time.sleep(check_interval)
            except Exception as e:
                log.error(f"[STREAM] Error in health check loop: {e}")
    
    def _check_stream_health(self, stream_id):
        """Check if the specified stream is healthy"""
        if stream_id not in self.pipelines or stream_id not in self.stream_health:
            return
            
        pipeline = self.pipelines[stream_id]
        health = self.stream_health[stream_id]
            
        # Update watchdog time
        health["watchdog_time"] = time.time()
        
        # Check pipeline state
        state_return = pipeline.get_state(0)
        if state_return[0] != Gst.StateChangeReturn.SUCCESS:
            log.warning(f"[STREAM] Pipeline state change issues detected for stream {stream_id}")
            health["errors"] += 1
            
        # If there are errors and we haven't recovered recently, attempt recovery
        if health["errors"] > 3:
            now = time.time()
            # Only attempt recovery if we haven't tried in the last 30 seconds
            if not health["last_recovery"] or (now - health["last_recovery"]) > 30:
                log.warning(f"[STREAM] Attempting to recover pipeline {stream_id} after {health['errors']} errors")
                self._recover_stream(stream_id)
                health["errors"] = 0  # Reset error counter
    
    def _recover_stream(self, stream_id):
        """Attempt to recover a stream by recreating the pipeline"""
        if stream_id not in self.streams_info:
            log.error(f"[STREAM] Cannot recover - no info available for stream {stream_id}")
            return False
            
        # Record recovery attempt
        if stream_id in self.stream_health:
            self.stream_health[stream_id]["last_recovery"] = time.time()
            self.stream_health[stream_id]["recoveries"] += 1
        
        # Stop the current pipeline
        if stream_id in self.pipelines:
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
        
        # Attempt to restart with same parameters
        info = self.streams_info[stream_id]
        log.info(f"[STREAM] 🔄 Recovery attempt for stream {stream_id}")
        
        # Start the stream again
        result = self._create_pipeline(
            stream_id,
            info["video_path"], 
            info["dest_ip"], 
            info["dest_port"], 
            info["ssrc"],
            info.get("encoder_params", {})
        )
        
        if result:
            log.info(f"[STREAM] ✅ Stream {stream_id} recovered successfully")
        else:
            log.error(f"[STREAM] ❌ Stream {stream_id} recovery failed")
        
        return result

    def start_stream(self, video_path, dest_ip, dest_port, ssrc=None, encoder_params=None):
        """
        Start streaming a video file to the specified destination
        
        Args:
            video_path (str): Path to the video file
            dest_ip (str): Destination IP address
            dest_port (int): Destination port
            ssrc (str, optional): SSRC value for RTP
            encoder_params (dict, optional): Encoding parameters
        
        Returns:
            bool: True if stream started successfully, False otherwise
        """
        if not video_path or not dest_ip or not dest_port:
            log.error("[STREAM] Invalid stream parameters.")
            return False

        # Ensure file exists
        if not os.path.isfile(video_path):
            log.error(f"[STREAM] File not found: {video_path}")
            return False

        # Generate a unique stream ID
        stream_id = f"{dest_ip}:{dest_port}"
        if ssrc:
            stream_id = f"{stream_id}:{ssrc}"
            
        # Start GLib main loop if not running already
        self.start_glib_loop()
        
        # If this stream is already running, stop it first
        if stream_id in self.pipelines:
            log.info(f"[STREAM] Stopping previous stream with ID {stream_id}...")
            self.stop_stream(stream_id)

        # Store current stream info with safe defaults
        self.streams_info[stream_id] = {
            "video_path": video_path,
            "dest_ip": dest_ip,
            "dest_port": dest_port,
            "ssrc": ssrc or "0000000001",  # Provide default SSRC if None
            "start_time": time.time(),
            "encoder_params": encoder_params or {}
        }
        
        # Create the pipeline
        success = self._create_pipeline(stream_id, video_path, dest_ip, dest_port, ssrc, encoder_params)
        
        # Start health monitoring
        self.start_health_monitoring()
        
        return success
        
    def _create_pipeline(self, stream_id, video_path, dest_ip, dest_port, ssrc=None, encoder_params=None):
        """Create a GStreamer pipeline for streaming"""
        # Prepare encoder parameters
        encoder_params = encoder_params or {}
        
        # Default encoder settings - can be overridden by encoder_params
        width = encoder_params.get("width", 704)
        height = encoder_params.get("height", 576)
        framerate = encoder_params.get("framerate", 25)
        bitrate = encoder_params.get("bitrate", 1024)  # kbps
        keyframe_interval = encoder_params.get("keyframe_interval", 50)  # frames
        speed_preset = encoder_params.get("speed_preset", "medium")  # quality/speed tradeoff
        codec = encoder_params.get("codec", "h264")

        # Get SRTP key from config
        srtp_key = self.config.get("srtp", {}).get(
            "key", "313233343536373839303132333435363132333435363738393031323334"
        )

        log.info(f"[STREAM] Starting GB28181 RTP stream to {dest_ip}:{dest_port}")
        log.info(f"[STREAM] File: {video_path}, Stream ID: {stream_id}")
        log.info(f"[STREAM] Video settings: {width}x{height}@{framerate}fps, {bitrate}kbps")
        
        try:
            # Build pipeline based on file type
            file_ext = os.path.splitext(video_path)[1].lower()
            
            # Start building the pipeline
            pipeline_str = f'filesrc location="{video_path}" ! '
            
            # Handle different file types
            if file_ext == ".mp4":
                # Fix for MP4 handling - add a decoder between h264parse and videoconvert
                pipeline_str += 'qtdemux ! queue ! h264parse ! avdec_h264 ! '
            elif file_ext == ".avi":
                pipeline_str += 'avidemux ! queue ! avdec_h264 ! '
            else:
                # Generic decoder for other formats
                pipeline_str += 'decodebin ! '
            
            # Video conversion and scaling
            pipeline_str += (
                f'videoconvert ! videorate ! videoscale ! '
                f'video/x-raw,format=I420,framerate={framerate}/1,width={width},height={height} ! '
            )
            
            # Video encoder - different settings based on codec
            if codec == "h264":
                pipeline_str += (
                    f'x264enc tune=zerolatency bitrate={bitrate} key-int-max={keyframe_interval} '
                    f'byte-stream=true speed-preset={speed_preset} ! '
                    f'video/x-h264,profile=baseline ! '
                )
            elif codec == "mpeg4":
                pipeline_str += (
                    f'avenc_mpeg4 bitrate={bitrate*1000} ! '
                    f'video/mpeg,mpegversion=4 ! '
                )
            else:
                # Default to H.264 with high compatibility
                pipeline_str += (
                    f'x264enc tune=zerolatency bitrate={bitrate} key-int-max={keyframe_interval} '
                    f'byte-stream=true speed-preset=superfast ! '
                    f'video/x-h264,profile=baseline ! '
                )
            
            # RTP packetization
            if codec == "h264":
                pipeline_str += 'rtph264pay config-interval=1 pt=96 '
            elif codec == "mpeg4":
                pipeline_str += 'rtpmp4vpay config-interval=1 pt=96 '
            else:
                pipeline_str += 'rtph264pay config-interval=1 pt=96 '
            
            # Add SSRC if provided
            ssrc_value = ssrc or "0000000001"
            if ssrc_value:
                pipeline_str += f'ssrc={ssrc_value} ! '
            else:
                pipeline_str += '! '
                
            # Add SRTP and UDP sink
            pipeline_str += (
                f'srtpenc key={srtp_key} ! '
                f'udpsink host={dest_ip} port={dest_port} sync=false async=false'
            )
            
            log.debug(f"[STREAM] Pipeline for stream {stream_id}: {pipeline_str}")
            
            # Create and store the pipeline
            pipeline = Gst.parse_launch(pipeline_str)
            self.pipelines[stream_id] = pipeline
            
            # Set to PLAYING state
            pipeline.set_state(Gst.State.PLAYING)

            # Setup bus to watch for EOS and errors
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            # Pass stream_id to the callback
            bus.connect("message", lambda b, m, sid=stream_id: self._on_bus_message(b, m, sid))
            
            # Initialize stream health monitoring
            self.stream_health[stream_id] = {
                "active": True,
                "start_time": time.time(),
                "errors": 0,
                "last_error": None,
                "recoveries": 0,
                "last_recovery": None,
                "watchdog_time": time.time()
            }
            
            log.info(f"[STREAM] ✅ Pipeline for stream {stream_id} started successfully.")
            return True
        except Exception as e:
            log.exception(f"[STREAM] Failed to launch GStreamer pipeline for stream {stream_id}: {e}")
            self.stream_health[stream_id] = self.stream_health.get(stream_id, {})
            self.stream_health[stream_id]["last_error"] = str(e)
            self.stream_health[stream_id]["errors"] = self.stream_health[stream_id].get("errors", 0) + 1
            
            # Cleanup if failed
            if stream_id in self.pipelines:
                self.pipelines[stream_id].set_state(Gst.State.NULL)
                del self.pipelines[stream_id]
                
            return False
    
    def _on_bus_message(self, bus, message, stream_id):
        """Handle GStreamer bus messages"""
        if stream_id not in self.pipelines:
            return
            
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.error(f"[STREAM] ❌ GStreamer error for stream {stream_id}: {err.message}")
            log.debug(f"[STREAM] Debug info: {debug}")
            
            # Record error for health monitoring
            if stream_id in self.stream_health:
                self.stream_health[stream_id]["errors"] += 1
                self.stream_health[stream_id]["last_error"] = f"{err.message}"
            
            # Stop on fatal errors
            if "No such file or directory" in err.message or "Could not open" in err.message:
                log.error(f"[STREAM] Fatal file error for stream {stream_id}, stopping pipeline")
                self.stop_stream(stream_id)
            else:
                # For non-fatal errors, let health monitoring handle recovery
                log.warning(f"[STREAM] Non-fatal error for stream {stream_id}, health monitoring will attempt recovery if needed")
                
        elif t == Gst.MessageType.EOS:
            log.info(f"[STREAM] ✅ End of stream reached for stream {stream_id}.")
            
            # For file sources, loop the video by restarting the pipeline
            if stream_id in self.streams_info and os.path.isfile(self.streams_info[stream_id]["video_path"]):
                log.info(f"[STREAM] Restarting video file for continuous playback of stream {stream_id}")
                self._restart_stream_for_looping(stream_id)
            else:
                self.stop_stream(stream_id)
                
        elif t == Gst.MessageType.STATE_CHANGED:
            if stream_id in self.pipelines and message.src == self.pipelines[stream_id]:
                old_state, new_state, pending_state = message.parse_state_changed()
                log.debug(f"[STREAM] Pipeline state changed for stream {stream_id} from {old_state.value_nick} to {new_state.value_nick}")
                
                # Reset error counter when pipeline reaches PLAYING state
                if new_state == Gst.State.PLAYING:
                    if stream_id in self.stream_health:
                        self.stream_health[stream_id]["errors"] = 0
    
    def _restart_stream_for_looping(self, stream_id):
        """Restart the stream to create a looping effect for video files"""
        if stream_id not in self.streams_info:
            return
            
        # Get current stream info
        info = self.streams_info[stream_id]
        
        # Stop the current pipeline
        if stream_id in self.pipelines:
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
            
        # Start the stream again with the same parameters
        self._create_pipeline(
            stream_id,
            info["video_path"],
            info["dest_ip"], 
            info["dest_port"],
            info["ssrc"],
            info.get("encoder_params", {})
        )
        
        log.info(f"[STREAM] Video restarted for continuous looping of stream {stream_id}")

    def stop_stream(self, stream_id=None):
        """
        Stop a specific stream or all streams if no stream_id provided
        
        Args:
            stream_id (str, optional): ID of the stream to stop. If None, stops all streams.
        """
        if stream_id is None:
            # Stop all streams
            for sid in list(self.pipelines.keys()):
                self.stop_stream(sid)
            return
                
        # Stop the specific stream
        if stream_id in self.pipelines:
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
            
            # Clean up appsink/appsrc resources
            if stream_id in self.appsrc_elements:
                del self.appsrc_elements[stream_id]
            if stream_id in self.appsink_callbacks:
                del self.appsink_callbacks[stream_id]
            if stream_id in self.frame_processors:
                del self.frame_processors[stream_id]
            if stream_id in self.processing_enabled:
                del self.processing_enabled[stream_id]
            
            if stream_id in self.stream_health:
                self.stream_health[stream_id]["active"] = False
                
            log.info(f"[STREAM] Pipeline for stream {stream_id} stopped.")
            
            # Remove stream info
            if stream_id in self.streams_info:
                del self.streams_info[stream_id]
    
    def shutdown(self):
        """Completely shut down the streamer and all threads"""
        self.running = False
        self.stop_stream()  # Stop all streams
        
        if self.main_loop and self.main_loop.is_running():
            self.main_loop.quit()
            
        # Wait for threads to complete
        if self.main_loop_thread and self.main_loop_thread.is_alive():
            self.main_loop_thread.join(1)
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(1)
            
        log.info("[STREAM] Media streamer shut down")
    
    def get_stream_status(self, stream_id=None):
        """
        Get status information for a specific stream or all streams
        
        Args:
            stream_id (str, optional): ID of the stream to get status for. If None, returns status for all streams.
            
        Returns:
            dict: Status information for the requested stream(s)
        """
        if stream_id is None:
            # Return status for all streams
            result = {}
            for sid in self.streams_info:
                result[sid] = self.get_stream_status(sid)
            return result
        
        # Get status for a specific stream
        if stream_id not in self.pipelines or stream_id not in self.streams_info:
            return {"status": "stopped", "stream_id": stream_id}
        
        # Get pipeline state
        state_return = self.pipelines[stream_id].get_state(0)  # Non-blocking
        state = state_return[1].value_nick if state_return[0] == Gst.StateChangeReturn.SUCCESS else "unknown"
        
        # Get stream duration
        duration = 0
        if self.streams_info[stream_id].get("start_time"):
            duration = int(time.time() - self.streams_info[stream_id]["start_time"])
        
        # Calculate health status
        health_status = "good"
        if stream_id in self.stream_health and self.stream_health[stream_id]["errors"] > 0:
            error_count = self.stream_health[stream_id]["errors"]
            if error_count > 5:
                health_status = "critical"
            else:
                health_status = "warning"
                
        result = {
            "stream_id": stream_id,
            "status": state,
            "health": health_status,
            "video_path": self.streams_info[stream_id]["video_path"],
            "dest_ip": self.streams_info[stream_id]["dest_ip"],
            "dest_port": self.streams_info[stream_id]["dest_port"],
            "ssrc": self.streams_info[stream_id].get("ssrc"),
            "duration": duration,
            "start_time": self.streams_info[stream_id].get("start_time", 0)
        }
        
        # Add health information if available
        if stream_id in self.stream_health:
            result.update({
                "errors": self.stream_health[stream_id]["errors"],
                "recoveries": self.stream_health[stream_id].get("recoveries", 0),
                "last_error": self.stream_health[stream_id].get("last_error")
            })
            
        return result
        
    def get_active_streams_count(self):
        """Get the count of currently active streams"""
        return len(self.pipelines)

    def start_stream_with_processing(self, video_path, dest_ip, dest_port, 
                                    frame_processor_callback=None, ssrc=None, encoder_params=None):
        """
        Start a stream with frame processing capabilities
        
        This differs from start_stream() in that it uses appsink/appsrc elements to
        intercept frames for processing before sending them to the network.
        
        Args:
            video_path (str): Path to the video file
            dest_ip (str): Destination IP address
            dest_port (int): Destination port
            frame_processor_callback (function): Callback function to process frames
            ssrc (str, optional): SSRC value for RTP
            encoder_params (dict, optional): Encoding parameters
        
        Returns:
            bool: True if stream started successfully, False otherwise
        """
        if not video_path or not dest_ip or not dest_port:
            log.error("[STREAM] Invalid stream parameters.")
            return False

        # Ensure file exists
        if not os.path.isfile(video_path):
            log.error(f"[STREAM] File not found: {video_path}")
            return False

        # Generate a unique stream ID
        stream_id = f"{dest_ip}:{dest_port}"
        if ssrc:
            stream_id = f"{stream_id}:{ssrc}"
            
        # Start GLib main loop if not running already
        self.start_glib_loop()
        
        # If this stream is already running, stop it first
        if stream_id in self.pipelines:
            log.info(f"[STREAM] Stopping previous stream with ID {stream_id}...")
            self.stop_stream(stream_id)

        # Store current stream info with safe defaults
        self.streams_info[stream_id] = {
            "video_path": video_path,
            "dest_ip": dest_ip,
            "dest_port": dest_port,
            "ssrc": ssrc or "0000000001",  # Provide default SSRC if None
            "start_time": time.time(),
            "encoder_params": encoder_params or {},
            "is_processing": True
        }
        
        # Store the frame processor callback if provided
        if frame_processor_callback:
            self.frame_processors[stream_id] = frame_processor_callback
            self.processing_enabled[stream_id] = True
        
        # Create the processing pipeline
        success = self._create_processing_pipeline(stream_id, video_path, dest_ip, dest_port, ssrc, encoder_params)
        
        # Start health monitoring
        self.start_health_monitoring()
        
        return success
    
    def start_recording_playback(self, recording_info, dest_ip, dest_port, 
                               start_timestamp=None, end_timestamp=None,
                               ssrc=None, encoder_params=None):
        """
        Start streaming a recording with time-based parameters
        
        This method allows playback of a recording with specific start and end times
        according to GB28181 requirements for historical playback.
        
        Args:
            recording_info (dict): Recording metadata
            dest_ip (str): Destination IP address
            dest_port (int): Destination port
            start_timestamp (str, optional): Start time in GB28181 format (YYYYMMDDThhmmssZ)
            end_timestamp (str, optional): End time in GB28181 format
            ssrc (str, optional): SSRC value for RTP
            encoder_params (dict, optional): Encoding parameters
            
        Returns:
            bool: True if stream started successfully, False otherwise
        """
        log.info(f"[STREAM] Starting historical playback to {dest_ip}:{dest_port}")
        
        video_path = recording_info.get("path")
        if not video_path or not os.path.isfile(video_path):
            log.error(f"[STREAM] Recording file not found: {video_path}")
            return False
            
        # Generate a unique stream ID for this playback
        stream_id = f"{dest_ip}:{dest_port}:playback"
        if ssrc:
            stream_id = f"{stream_id}:{ssrc}"
            
        # Validate timestamps if provided
        playback_settings = {}
        
        # Convert timestamps to Unix timestamps if provided
        start_time_unix = None
        end_time_unix = None
        
        if start_timestamp:
            try:
                from datetime import datetime
                # Parse GB28181 format timestamp (YYYYMMDDThhmmssZ)
                dt_format = "%Y%m%dT%H%M%SZ"
                start_dt = datetime.strptime(start_timestamp, dt_format)
                start_time_unix = start_dt.timestamp()
                log.info(f"[STREAM] Playback start time: {start_dt}")
            except Exception as e:
                log.error(f"[STREAM] Failed to parse start timestamp {start_timestamp}: {e}")
                
        if end_timestamp:
            try:
                from datetime import datetime
                # Parse GB28181 format timestamp (YYYYMMDDThhmmssZ)
                dt_format = "%Y%m%dT%H%M%SZ"
                end_dt = datetime.strptime(end_timestamp, dt_format)
                end_time_unix = end_dt.timestamp()
                log.info(f"[STREAM] Playback end time: {end_dt}")
            except Exception as e:
                log.error(f"[STREAM] Failed to parse end timestamp {end_timestamp}: {e}")
        
        # Prepare time parameters for playback
        if start_time_unix or end_time_unix:
            try:
                # Get recording start timestamp from metadata
                recording_start_time = recording_info.get("timestamp")
                
                # Create a frame processor to handle time-based playback
                def time_based_frame_processor(frame, timestamp, stream_info):
                    # If we don't have stream info or start time info, just pass through
                    if not stream_info or "start_time" not in stream_info:
                        return frame, timestamp
                    
                    # Calculate relative time in the video
                    stream_start_time = stream_info["start_time"]
                    video_time = recording_start_time + (timestamp - stream_start_time)
                    
                    # Check if this frame is within our requested time window
                    is_in_range = True
                    
                    if start_time_unix and video_time < start_time_unix:
                        is_in_range = False
                    
                    if end_time_unix and video_time > end_time_unix:
                        is_in_range = False
                    
                    if not is_in_range:
                        # Return a black frame for frames outside the time range
                        # or we could return None to skip the frame entirely
                        black_frame = np.zeros_like(frame)
                        return black_frame, timestamp
                    
                    # Add timestamp overlay to the frame
                    # Create a copy of the frame
                    processed_frame = frame.copy()
                    
                    # Format the timestamp for display
                    dt = datetime.fromtimestamp(video_time)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Add text to the frame
                    cv2.putText(
                        processed_frame,
                        f"Time: {time_str}",
                        (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),  # Green
                        2
                    )
                    
                    return processed_frame, timestamp
                    
                # Use the processing-enabled pipeline for time-based playback
                return self.start_stream_with_processing(
                    video_path=video_path,
                    dest_ip=dest_ip,
                    dest_port=dest_port,
                    frame_processor_callback=time_based_frame_processor,
                    ssrc=ssrc,
                    encoder_params=encoder_params
                )
                
            except Exception as e:
                log.error(f"[STREAM] Error setting up time-based playback: {e}")
                return False
        else:
            # If no time constraints, use regular streaming
            return self.start_stream(
                video_path=video_path,
                dest_ip=dest_ip,
                dest_port=dest_port,
                ssrc=ssrc,
                encoder_params=encoder_params
            )
    
    def _create_processing_pipeline(self, stream_id, video_path, dest_ip, dest_port, ssrc=None, encoder_params=None):
        """Create a GStreamer pipeline with appsink/appsrc for frame processing"""
        try:
            # Get the absolute path to the video file
            video_path = os.path.abspath(video_path)
            
            # Get file extension
            file_ext = os.path.splitext(video_path)[1].lower()
            
            # Default encoder parameters
            bitrate = 1024
            width = 640
            height = 480
            framerate = 15
            
            # Override with custom encoder parameters if provided
            if encoder_params:
                bitrate = encoder_params.get("bitrate", bitrate)
                width = encoder_params.get("width", width)
                height = encoder_params.get("height", height)
                framerate = encoder_params.get("framerate", framerate)
            
            # Create a new pipeline
            pipeline = Gst.Pipeline.new(f"pipeline-{stream_id}")
            
            # Create elements common to all file types
            src = Gst.ElementFactory.make("filesrc", f"source-{stream_id}")
            src.set_property("location", video_path)
            
            # Elements for specific file types
            if file_ext == ".mp4":
                demux = Gst.ElementFactory.make("qtdemux", f"demux-{stream_id}")
                parser = Gst.ElementFactory.make("h264parse", f"parser-{stream_id}")
                decoder = Gst.ElementFactory.make("avdec_h264", f"decoder-{stream_id}")
            elif file_ext == ".avi":
                demux = Gst.ElementFactory.make("avidemux", f"demux-{stream_id}")
                decoder = Gst.ElementFactory.make("avdec_h264", f"decoder-{stream_id}")
            else:
                # Assume raw video file or other format
                decoder = Gst.ElementFactory.make("decodebin", f"decoder-{stream_id}")
            
            # Video processing elements
            convert = Gst.ElementFactory.make("videoconvert", f"convert-{stream_id}")
            rate = Gst.ElementFactory.make("videorate", f"rate-{stream_id}")
            scale = Gst.ElementFactory.make("videoscale", f"scale-{stream_id}")
            
            # appsink for capturing frames
            appsink = Gst.ElementFactory.make("appsink", f"appsink-{stream_id}")
            appsink.set_property("emit-signals", True)
            appsink.set_property("max-buffers", 1)
            appsink.set_property("drop", True)
            appsink.set_property("sync", False)
            
            # Set caps for appsink
            appsink_caps = Gst.Caps.from_string(f"video/x-raw,format=RGB,width={width},height={height},framerate={framerate}/1")
            appsink.set_property("caps", appsink_caps)
            
            # appsrc for reintroducing processed frames
            appsrc = Gst.ElementFactory.make("appsrc", f"appsrc-{stream_id}")
            appsrc.set_property("emit-signals", False)
            appsrc.set_property("is-live", True)
            appsrc.set_property("do-timestamp", False)
            appsrc.set_property("format", Gst.Format.TIME)
            appsrc.set_property("max-bytes", 0)
            appsrc.set_property("stream-type", 0)  # 0 = GST_APP_STREAM_TYPE_STREAM
            
            # Store the appsrc element for later use
            self.appsrc_elements[stream_id] = appsrc
            
            # Set caps for appsrc - match the incoming video format
            appsrc_caps = Gst.Caps.from_string(f"video/x-raw,format=RGB,width={width},height={height},framerate={framerate}/1")
            appsrc.set_property("caps", appsrc_caps)
            
            # Add videoconvert after appsrc to handle format conversion
            appsrc_convert = Gst.ElementFactory.make("videoconvert", f"appsrc-convert-{stream_id}")
            
            # Add capsfilter to ensure proper format for x264enc
            appsrc_capsfilter = Gst.ElementFactory.make("capsfilter", f"appsrc-capsfilter-{stream_id}")
            i420_caps = Gst.Caps.from_string("video/x-raw,format=I420")
            appsrc_capsfilter.set_property("caps", i420_caps)
            
            # Encoder elements
            encoder = Gst.ElementFactory.make("x264enc", f"encoder-{stream_id}")
            encoder.set_property("tune", "zerolatency")
            encoder.set_property("speed-preset", "ultrafast")
            encoder.set_property("bitrate", bitrate)
            encoder.set_property("key-int-max", 30)
            # Additional performance settings
            encoder.set_property("pass", 0)  # 0 = single pass
            encoder.set_property("quantizer", 21)  # Lower = better quality, higher = smaller size
            
            # RTP payloader
            payloader = Gst.ElementFactory.make("rtph264pay", f"rtp-{stream_id}")
            
            # Enable video frame consistency
            payloader.set_property("config-interval", 1)
            payloader.set_property("pt", 96)
            
            # Add SSRC if provided
            ssrc_value = ssrc or "0000000001"
            payloader.set_property("ssrc", int(ssrc_value))
            
            # Create SRTP encoder
            srtp_enc = Gst.ElementFactory.make("srtpenc", f"srtp-{stream_id}")
            
            # Get SRTP key from config and convert it to GstBuffer
            srtp_key = self.config.get("srtp", {}).get("key", "313233343536373839303132333435363132333435363738393031323334")
            try:
                # Convert hex string to bytes and create GstBuffer
                key_bytes = binascii.unhexlify(srtp_key)
                key_buffer = Gst.Buffer.new_wrapped(key_bytes)
                srtp_enc.set_property("key", key_buffer)
            except Exception as e:
                log.error(f"[STREAM] Error converting SRTP key to GstBuffer: {e}")
                raise
            
            # Create UDP sink
            udpsink = Gst.ElementFactory.make("udpsink", f"udp-{stream_id}")
            udpsink.set_property("host", dest_ip)
            udpsink.set_property("port", dest_port)
            udpsink.set_property("sync", False)
            udpsink.set_property("async", False)
            
            # Add all elements to the pipeline
            pipeline.add(src)
            
            if file_ext == ".mp4":
                pipeline.add(demux)
                pipeline.add(parser)
                pipeline.add(decoder)
            elif file_ext == ".avi":
                pipeline.add(demux)
                pipeline.add(decoder)
            else:
                pipeline.add(decoder)
                
            pipeline.add(convert)
            pipeline.add(rate)
            pipeline.add(scale)
            pipeline.add(appsink)
            pipeline.add(appsrc)
            pipeline.add(appsrc_convert)
            pipeline.add(appsrc_capsfilter)
            pipeline.add(encoder)
            pipeline.add(payloader)
            pipeline.add(srtp_enc)
            pipeline.add(udpsink)
            
            # Link elements
            src.link(demux if file_ext in [".mp4", ".avi"] else decoder)
            
            # Handle dynamic pad creation for demuxers
            if file_ext == ".mp4":
                demux.connect("pad-added", self._on_pad_added, parser)
                parser.link(decoder)
                decoder.link(convert)
            elif file_ext == ".avi":
                demux.connect("pad-added", self._on_pad_added, decoder)
                decoder.link(convert)
            else:
                decoder.connect("pad-added", self._on_pad_added, convert)
                
            # Link the rest of the pipeline
            convert.link(rate)
            rate.link(scale)
            scale.link(appsink)
            appsrc.link(appsrc_convert)
            appsrc_convert.link(appsrc_capsfilter)
            appsrc_capsfilter.link(encoder)
            encoder.link(payloader)
            payloader.link(srtp_enc)
            srtp_enc.link(udpsink)
            
            # Set up appsink callbacks
            self._setup_appsink_callbacks(stream_id, appsink)
            
            # Store and start the pipeline
            self.pipelines[stream_id] = pipeline
            pipeline.set_state(Gst.State.PLAYING)
            
            # Setup bus to watch for EOS and errors
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", lambda b, m, sid=stream_id: self._on_bus_message(b, m, sid))
            
            # Initialize stream health monitoring
            self.stream_health[stream_id] = {
                "active": True,
                "start_time": time.time(),
                "errors": 0,
                "last_error": None,
                "recoveries": 0,
                "last_recovery": None,
                "watchdog_time": time.time()
            }
            
            log.info(f"[STREAM] ✅ Processing pipeline for stream {stream_id} started successfully.")
            return True
            
        except Exception as e:
            log.exception(f"[STREAM] Failed to create processing pipeline for stream {stream_id}: {e}")
            if stream_id in self.stream_health:
                self.stream_health[stream_id]["last_error"] = str(e)
                self.stream_health[stream_id]["errors"] += 1
            
            # Cleanup
            if stream_id in self.pipelines:
                self.pipelines[stream_id].set_state(Gst.State.NULL)
                del self.pipelines[stream_id]
            
            return False
    
    def _on_pad_added(self, element, pad, connect_to):
        """Handle dynamic pad creation"""
        sink_pad = connect_to.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)
    
    def _setup_appsink_callbacks(self, stream_id, appsink):
        """Set up callbacks for appsink"""
        
        def on_new_sample(appsink):
            if stream_id not in self.processing_enabled or not self.processing_enabled[stream_id]:
                return Gst.FlowReturn.OK
            
            # Get the sample from appsink
            sample = appsink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.ERROR
            
            # Get buffer and create numpy array from it
            buffer = sample.get_buffer()
            caps = sample.get_caps()
            structure = caps.get_structure(0)
            width = structure.get_value("width")
            height = structure.get_value("height")
            
            # Map buffer to numpy array
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                buffer.unmap(map_info)
                return Gst.FlowReturn.ERROR
            
            try:
                # Create a proper numpy array from buffer data by first converting to bytes and then to numpy array
                data_bytes = bytes(map_info.data)
                # Create a numpy array from a copy of the data, not a view
                np_data = np.frombuffer(data_bytes, dtype=np.uint8).copy()
                # Reshape to image dimensions
                frame = np_data.reshape((height, width, 3))
                
                # Get stream info with timestamps
                current_timestamp = time.time()
                stream_info = self.streams_info.get(stream_id, {
                    "stream_id": stream_id,
                    "start_time": current_timestamp
                })
                
                # Process the frame using the callback
                processed_frame = None
                if stream_id in self.frame_processors and self.frame_processors[stream_id]:
                    processor_func = self.frame_processors[stream_id]
                    
                    # Check if this is a named processor string
                    if isinstance(processor_func, str) and processor_func in self.named_processors:
                        processor_func = self.named_processors[processor_func]
                    
                    # Call the processor function with appropriate arguments
                    if callable(processor_func):
                        result = processor_func(frame, current_timestamp, stream_info)
                        # If the processor returns a tuple (processed_frame, timestamp), use it
                        if isinstance(result, tuple) and len(result) == 2:
                            processed_frame, _ = result
                        else:
                            # Otherwise assume it just returned the processed frame
                            processed_frame = result
                    else:
                        processed_frame = frame
                else:
                    processed_frame = frame
                
                # Push processed frame to appsrc
                if stream_id in self.appsrc_elements and processed_frame is not None:
                    self._push_frame_to_appsrc(stream_id, processed_frame, buffer.pts, buffer.dts, buffer.duration)
            except Exception as e:
                log.error(f"[STREAM] Error in frame processing for stream {stream_id}: {e}")
            finally:
                # Clean up
                buffer.unmap(map_info)
                
            return Gst.FlowReturn.OK
            
        # Connect the callbacks
        appsink.connect("new-sample", on_new_sample)
        self.appsink_callbacks[stream_id] = on_new_sample
    
    def _push_frame_to_appsrc(self, stream_id, frame, pts, dts, duration):
        """Push a processed frame back into the pipeline via appsrc"""
        if stream_id not in self.appsrc_elements:
            return False
        
        appsrc = self.appsrc_elements[stream_id]
        
        # Convert numpy array to bytes and wrap in a new buffer
        data = frame.tobytes()
        
        # Create a new buffer by wrapping the data instead of copying
        buffer = Gst.Buffer.new_wrapped(data)
        
        # Set buffer timing
        buffer.pts = pts
        buffer.dts = dts
        buffer.duration = duration
        
        # Push buffer to appsrc
        result = appsrc.emit("push-buffer", buffer)
        return result == Gst.FlowReturn.OK
    
    def set_frame_processor(self, stream_id, processor_callback):
        """Set or update the frame processor for a stream"""
        if stream_id not in self.pipelines:
            log.error(f"[STREAM] Cannot set frame processor: Stream {stream_id} does not exist")
            return False
            
        self.frame_processors[stream_id] = processor_callback
        self.processing_enabled[stream_id] = processor_callback is not None
        log.info(f"[STREAM] Frame processor {'enabled' if processor_callback else 'disabled'} for stream {stream_id}")
        return True
        
    def toggle_frame_processing(self, stream_id, enabled=True):
        """Enable or disable frame processing for a stream"""
        if stream_id not in self.pipelines:
            log.error(f"[STREAM] Cannot toggle processing: Stream {stream_id} does not exist")
            return False
            
        self.processing_enabled[stream_id] = enabled
        log.info(f"[STREAM] Frame processing {'enabled' if enabled else 'disabled'} for stream {stream_id}")
        return True
        
    def register_frame_processor(self, name, processor_function):
        """Register a named frame processor function
        
        Args:
            name (str): Name to identify this processor
            processor_function (callable): Function that takes (frame, timestamp, stream_info) and returns (processed_frame, timestamp)
            
        Returns:
            bool: True if registered successfully
        """
        if not callable(processor_function):
            log.error(f"[STREAM] Cannot register processor '{name}': Not a callable function")
            return False
            
        self.named_processors[name] = processor_function
        log.info(f"[STREAM] Registered frame processor: {name}")
        return True
        
    def get_frame_processor(self, name):
        """Get a registered frame processor by name
        
        Args:
            name (str): Name of the processor to retrieve
            
        Returns:
            callable: The processor function or None if not found
        """
        if name not in self.named_processors:
            log.warning(f"[STREAM] Frame processor '{name}' not found")
            return None
            
        return self.named_processors[name]
