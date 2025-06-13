#!/usr/bin/env python3
# src/live_stream_handler.py
"""
Enhanced Live Stream Handler for RTSP to GB28181 streaming
Optimized for low-latency and high-reliability live streaming
"""

import os
import time
import threading
import logging
from typing import Dict, Optional, Tuple, Any
from logger import log
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject

class LiveStreamHandler:
    """
    Specialized handler for RTSP to GB28181 live streaming
    Optimized for real-time performance and WVP integration
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.active_streams: Dict[str, Dict] = {}
        self.pipelines: Dict[str, Gst.Pipeline] = {}
        self.stream_threads: Dict[str, threading.Thread] = {}
        self.glib_loop = None
        self.glib_thread = None
        self.monitoring_thread = None
        self.running = False
        
        # Initialize GStreamer
        if not Gst.is_initialized():
            Gst.init(None)
        
        # Stream configuration defaults optimized for live streaming
        self.stream_defaults = {
            "width": 1280,
            "height": 720,
            "framerate": 25,
            "bitrate": 2048,
            "keyframe_interval": 25,  # 1 second keyframes at 25fps
            "latency": 100,  # Low latency for live streaming
            "buffer_size": 2,  # Minimal buffering
            "speed_preset": "ultrafast",
            "tune": "zerolatency",
            "profile": "baseline"
        }
        
        log.info("[LIVE] LiveStreamHandler initialized")
    
    def start(self):
        """Start the live stream handler"""
        self.running = True
        
        # Start GLib main loop
        self._start_glib_loop()
        
        # Start monitoring thread
        self._start_monitoring()
        
        log.info("[LIVE] LiveStreamHandler started")
    
    def stop(self):
        """Stop the live stream handler"""
        self.running = False
        
        # Stop all active streams
        for stream_id in list(self.active_streams.keys()):
            self.stop_stream(stream_id)
        
        # Stop monitoring
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        # Stop GLib loop
        if self.glib_loop and self.glib_loop.is_running():
            self.glib_loop.quit()
        
        if self.glib_thread and self.glib_thread.is_alive():
            self.glib_thread.join(timeout=5)
        
        log.info("[LIVE] LiveStreamHandler stopped")
    
    def _start_glib_loop(self):
        """Start GLib main loop in separate thread"""
        if not self.glib_loop:
            self.glib_loop = GLib.MainLoop()
            self.glib_thread = threading.Thread(target=self._run_glib_loop, daemon=True)
            self.glib_thread.start()
            log.info("[LIVE] GLib main loop started")
    
    def _run_glib_loop(self):
        """Run the GLib main loop"""
        try:
            self.glib_loop.run()
        except Exception as e:
            log.error(f"[LIVE] GLib main loop error: {e}")
    
    def _start_monitoring(self):
        """Start stream monitoring thread"""
        if not self.monitoring_thread or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            log.info("[LIVE] Stream monitoring started")
    
    def _monitoring_loop(self):
        """Monitor active streams and handle recovery"""
        while self.running:
            try:
                # Check each active stream
                for stream_id in list(self.active_streams.keys()):
                    self._check_stream_health(stream_id)
                
                # Sleep before next check
                time.sleep(5)
            except Exception as e:
                log.error(f"[LIVE] Monitoring loop error: {e}")
                time.sleep(5)
    
    def _check_stream_health(self, stream_id: str):
        """Check health of a specific stream"""
        if stream_id not in self.active_streams:
            return
        
        stream_info = self.active_streams[stream_id]
        pipeline = self.pipelines.get(stream_id)
        
        if not pipeline:
            log.warning(f"[LIVE] No pipeline found for stream {stream_id}")
            return
        
        # Check pipeline state
        state_ret = pipeline.get_state(Gst.CLOCK_TIME_NONE)
        if state_ret[0] == Gst.StateChangeReturn.SUCCESS:
            current_state = state_ret[1]
            
            if current_state != Gst.State.PLAYING:
                log.warning(f"[LIVE] Stream {stream_id} not in PLAYING state: {current_state.value_nick}")
                # Try to recover
                self._recover_stream(stream_id)
            else:
                # Update last seen time
                stream_info['last_seen'] = time.time()
        else:
            log.warning(f"[LIVE] Failed to get state for stream {stream_id}")
            self._recover_stream(stream_id)
    
    def _recover_stream(self, stream_id: str):
        """Attempt to recover a failed stream"""
        if stream_id not in self.active_streams:
            return
        
        stream_info = self.active_streams[stream_id]
        stream_info['recovery_attempts'] = stream_info.get('recovery_attempts', 0) + 1
        
        if stream_info['recovery_attempts'] > 3:
            log.error(f"[LIVE] Max recovery attempts reached for stream {stream_id}")
            return
        
        log.info(f"[LIVE] Attempting recovery for stream {stream_id} (attempt #{stream_info['recovery_attempts']})")
        
        # Stop current pipeline
        if stream_id in self.pipelines:
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
        
        # Wait before retry
        time.sleep(2)
        
        # Restart stream
        self._start_stream_pipeline(
            stream_id,
            stream_info['rtsp_url'],
            stream_info['dest_ip'],
            stream_info['dest_port'],
            stream_info.get('ssrc'),
            stream_info.get('encoder_params')
        )
    
    def start_rtsp_stream(self, stream_id: str, rtsp_url: str, dest_ip: str, dest_port: int, 
                         ssrc: Optional[str] = None, encoder_params: Optional[Dict] = None) -> bool:
        """
        Start an RTSP stream with optimized pipeline for live streaming
        
        Args:
            stream_id: Unique identifier for the stream
            rtsp_url: RTSP source URL
            dest_ip: Destination IP address
            dest_port: Destination port
            ssrc: SSRC value for RTP
            encoder_params: Encoding parameters
            
        Returns:
            bool: True if stream started successfully
        """
        if stream_id in self.active_streams:
            log.warning(f"[LIVE] Stream {stream_id} already active")
            return True
        
        # Store stream info
        self.active_streams[stream_id] = {
            'rtsp_url': rtsp_url,
            'dest_ip': dest_ip,
            'dest_port': dest_port,
            'ssrc': ssrc,
            'encoder_params': encoder_params or {},
            'start_time': time.time(),
            'last_seen': time.time(),
            'recovery_attempts': 0
        }
        
        # Start the pipeline
        success = self._start_stream_pipeline(stream_id, rtsp_url, dest_ip, dest_port, ssrc, encoder_params)
        
        if not success:
            del self.active_streams[stream_id]
        
        return success
    
    def _start_stream_pipeline(self, stream_id: str, rtsp_url: str, dest_ip: str, dest_port: int,
                              ssrc: Optional[str] = None, encoder_params: Optional[Dict] = None) -> bool:
        """Create and start optimized pipeline for live RTSP streaming"""
        
        # Merge encoder params with defaults
        params = {**self.stream_defaults, **(encoder_params or {})}
        
        # Build optimized pipeline for live streaming
        pipeline_str = self._build_live_pipeline(
            rtsp_url, dest_ip, dest_port, ssrc, params
        )
        
        log.info(f"[LIVE] Starting pipeline for {stream_id}: {rtsp_url} -> {dest_ip}:{dest_port}")
        log.debug(f"[LIVE] Pipeline: {pipeline_str}")
        
        try:
            # Create pipeline
            pipeline = Gst.parse_launch(pipeline_str)
            
            # Set up bus monitoring
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", lambda b, m: self._on_bus_message(b, m, stream_id))
            
            # Store pipeline
            self.pipelines[stream_id] = pipeline
            
            # Set to PLAYING state
            ret = pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                log.error(f"[LIVE] Failed to start pipeline for {stream_id}")
                return False
            
            log.info(f"[LIVE] ✅ Pipeline started successfully for {stream_id}")
            return True
            
        except Exception as e:
            log.error(f"[LIVE] Failed to create pipeline for {stream_id}: {e}")
            return False
    
    def _build_live_pipeline(self, rtsp_url: str, dest_ip: str, dest_port: int,
                            ssrc: Optional[str], params: Dict) -> str:
        """Build optimized GStreamer pipeline for live RTSP streaming"""
        
        # RTSP source with optimized settings for live streaming
        pipeline_parts = [
            f'rtspsrc location="{rtsp_url}"',
            f'latency={params["latency"]}',
            'is-live=true',
            'buffer-mode=slave',
            'ntp-sync=true',
            'protocols=tcp+udp-mcast+udp',
            'connection-speed=1000000',
            'timeout=5000000',
            'retry=3',
            '!'
        ]
        
        # RTP depayloader and parser
        pipeline_parts.extend([
            'rtph264depay',
            '!',
            'h264parse',
            'config-interval=1',
            '!'
        ])
        
        # Decoder (only if we need to re-encode)
        if params.get('reencode', True):
            pipeline_parts.extend([
                'avdec_h264',
                '!',
                'video/x-raw,format=I420',
                '!',
                'queue',
                f'max-size-buffers={params["buffer_size"]}',
                'max-size-time=0',
                'leaky=downstream',
                '!'
            ])
        
        # Video processing (if re-encoding)
        if params.get('reencode', True):
            pipeline_parts.extend([
                'videoconvert',
                '!',
                'videoscale',
                '!',
                f'video/x-raw,format=I420,width={params["width"]},height={params["height"]},framerate={params["framerate"]}/1',
                '!',
                'queue',
                f'max-size-buffers={params["buffer_size"]}',
                'max-size-time=0',
                'leaky=downstream',
                '!'
            ])
            
            # H.264 encoder optimized for live streaming
            pipeline_parts.extend([
                'x264enc',
                f'tune={params["tune"]}',
                f'speed-preset={params["speed_preset"]}',
                f'bitrate={params["bitrate"]}',
                f'key-int-max={params["keyframe_interval"]}',
                'byte-stream=true',
                'threads=1',
                'sync-lookahead=0',
                'intra-refresh=false',
                'sliced-threads=false',
                '!',
                f'video/x-h264,profile={params["profile"]},stream-format=byte-stream,alignment=au',
                '!'
            ])
        
        # Queue before muxing
        pipeline_parts.extend([
            'queue',
            f'max-size-buffers={params["buffer_size"]}',
            'max-size-time=0',
            'leaky=downstream',
            '!'
        ])
        
        # MPEG-PS muxing for GB28181 compliance
        pipeline_parts.extend([
            'mpegpsmux',
            'aggregate-gops=false',
            '!',
            'queue',
            f'max-size-buffers={params["buffer_size"]}',
            'max-size-time=0',
            'leaky=downstream',
            '!'
        ])
        
        # RTP payloader
        payload_type = params.get('payload_type', 96)
        pipeline_parts.extend([
            'rtpgstpay',
            f'pt={payload_type}',
            'perfect-rtptime=false'
        ])
        
        # Add SSRC if provided
        if ssrc:
            try:
                ssrc_value = int(ssrc) if isinstance(ssrc, str) and ssrc.isdigit() else int(ssrc, 16)
                pipeline_parts.append(f'ssrc={ssrc_value}')
            except (ValueError, TypeError):
                log.warning(f"[LIVE] Invalid SSRC value: {ssrc}")
        
        pipeline_parts.extend([
            '!',
            'queue',
            'max-size-buffers=0',
            'max-size-time=0',
            'leaky=downstream',
            '!',
            f'udpsink host={dest_ip} port={dest_port} sync=false async=false'
        ])
        
        return ' '.join(pipeline_parts)
    
    def _on_bus_message(self, bus: Gst.Bus, message: Gst.Message, stream_id: str):
        """Handle GStreamer bus messages"""
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            log.error(f"[LIVE] Pipeline error for {stream_id}: {error}")
            log.debug(f"[LIVE] Debug info: {debug}")
            # Schedule recovery
            threading.Thread(target=self._recover_stream, args=(stream_id,), daemon=True).start()
            
        elif msg_type == Gst.MessageType.WARNING:
            warning, debug = message.parse_warning()
            log.warning(f"[LIVE] Pipeline warning for {stream_id}: {warning}")
            
        elif msg_type == Gst.MessageType.EOS:
            log.info(f"[LIVE] End of stream for {stream_id}")
            # For live streams, EOS might indicate connection loss
            threading.Thread(target=self._recover_stream, args=(stream_id,), daemon=True).start()
            
        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipelines.get(stream_id):
                old_state, new_state, pending_state = message.parse_state_changed()
                log.debug(f"[LIVE] Stream {stream_id} state changed: {old_state.value_nick} -> {new_state.value_nick}")
                
                if new_state == Gst.State.PLAYING:
                    if stream_id in self.active_streams:
                        self.active_streams[stream_id]['last_seen'] = time.time()
                        self.active_streams[stream_id]['recovery_attempts'] = 0
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop a specific stream"""
        if stream_id not in self.active_streams:
            log.warning(f"[LIVE] Stream {stream_id} not found")
            return False
        
        # Stop pipeline
        if stream_id in self.pipelines:
            pipeline = self.pipelines[stream_id]
            pipeline.set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
        
        # Remove from active streams
        del self.active_streams[stream_id]
        
        log.info(f"[LIVE] Stream {stream_id} stopped")
        return True
    
    def get_stream_status(self, stream_id: Optional[str] = None) -> Dict:
        """Get status of streams"""
        if stream_id:
            if stream_id in self.active_streams:
                stream_info = self.active_streams[stream_id].copy()
                # Add pipeline state if available
                if stream_id in self.pipelines:
                    state_ret = self.pipelines[stream_id].get_state(Gst.CLOCK_TIME_NONE)
                    if state_ret[0] == Gst.StateChangeReturn.SUCCESS:
                        stream_info['pipeline_state'] = state_ret[1].value_nick
                return stream_info
            else:
                return {}
        else:
            # Return all streams
            status = {}
            for sid in self.active_streams:
                status[sid] = self.get_stream_status(sid)
            return status
    
    def get_active_stream_count(self) -> int:
        """Get number of active streams"""
        return len(self.active_streams)
    
    def list_rtsp_sources(self) -> list:
        """List configured RTSP sources"""
        return self.config.get('rtsp_sources', []) 