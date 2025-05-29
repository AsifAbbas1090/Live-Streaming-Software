#!/usr/bin/env python3
# test_media_streamer.py

import os
import sys
import time
import json
import logging

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger()

# Import GStreamer
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

class MediaStreamer:
    """Simplified version for testing the streamer enhancements"""
    def __init__(self):
        self.pipelines = {}  # Dictionary to store multiple pipelines
        self.streams_info = {}  # Dictionary to store info for multiple streams
        self.main_loop = None
        self.main_loop_thread = None
        self.running = False
        
    def start_stream(self, video_path, dest_ip, dest_port, ssrc=None):
        """Start streaming a video file"""
        if not os.path.isfile(video_path):
            log.error(f"[TEST] File not found: {video_path}")
            return False
            
        # Create a stream ID
        stream_id = f"{dest_ip}:{dest_port}"
        if ssrc:
            stream_id = f"{stream_id}:{ssrc}"
            
        # Start GLib main loop if needed
        self._start_glib_loop()
        
        # Stop previous stream if exists
        if stream_id in self.pipelines:
            self.stop_stream(stream_id)
            
        # Store stream info
        self.streams_info[stream_id] = {
            "video_path": video_path,
            "dest_ip": dest_ip,
            "dest_port": dest_port,
            "ssrc": ssrc,
            "start_time": time.time()
        }
        
        # Create pipeline
        try:
            # Simple testing pipeline - no SRTP
            pipeline_str = (
                f'filesrc location="{video_path}" ! '
                f'decodebin ! videoconvert ! videorate ! videoscale ! '
                f'video/x-raw,format=I420,framerate=25/1,width=640,height=480 ! '
                f'x264enc tune=zerolatency bitrate=1024 key-int-max=50 ! '
                f'rtph264pay config-interval=1 pt=96 '
            )
            
            # Add SSRC if provided
            if ssrc:
                pipeline_str += f'ssrc={ssrc} ! '
            else:
                pipeline_str += '! '
                
            # Add UDP sink
            pipeline_str += (
                f'udpsink host={dest_ip} port={dest_port} sync=false async=false'
            )
            
            log.info(f"[TEST] Creating pipeline for stream {stream_id}")
            log.debug(f"[TEST] Pipeline: {pipeline_str}")
            
            # Create and start pipeline
            pipeline = Gst.parse_launch(pipeline_str)
            self.pipelines[stream_id] = pipeline
            
            # Start the pipeline
            pipeline.set_state(Gst.State.PLAYING)
            
            # Setup bus
            bus = pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message", lambda b, m, sid=stream_id: self._on_bus_message(b, m, sid))
            
            log.info(f"[TEST] Stream {stream_id} started successfully")
            return True
            
        except Exception as e:
            log.error(f"[TEST] Failed to start stream: {e}")
            return False
    
    def _start_glib_loop(self):
        """Start the GLib mainloop in a separate thread"""
        if self.main_loop is not None:
            return
            
        self.main_loop = GLib.MainLoop()
        import threading
        self.main_loop_thread = threading.Thread(target=self._run_glib_loop, daemon=True)
        self.main_loop_thread.start()
        self.running = True
        log.info("[TEST] GLib main loop started")
    
    def _run_glib_loop(self):
        """Run the GLib mainloop"""
        try:
            self.main_loop.run()
        except Exception as e:
            log.error(f"[TEST] Error in GLib mainloop: {e}")
        finally:
            self.running = False
    
    def _on_bus_message(self, bus, message, stream_id):
        """Handle bus messages"""
        if stream_id not in self.pipelines:
            return
            
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.error(f"[TEST] Error on stream {stream_id}: {err.message}")
            log.debug(f"[TEST] Debug info: {debug}")
        elif t == Gst.MessageType.EOS:
            log.info(f"[TEST] End of stream for {stream_id}")
            # Restart the stream for looping
            self._restart_stream(stream_id)
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipelines[stream_id]:
                old, new, pending = message.parse_state_changed()
                if new == Gst.State.PLAYING:
                    log.info(f"[TEST] Stream {stream_id} is now playing")
    
    def _restart_stream(self, stream_id):
        """Restart a stream to loop the video"""
        if stream_id not in self.streams_info:
            return
            
        info = self.streams_info[stream_id]
        log.info(f"[TEST] Restarting stream {stream_id} for looping")
        
        # Stop the pipeline
        if stream_id in self.pipelines:
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
        
        # Start it again
        self.start_stream(
            info["video_path"],
            info["dest_ip"],
            info["dest_port"],
            info["ssrc"]
        )
    
    def stop_stream(self, stream_id=None):
        """Stop a stream or all streams"""
        if stream_id is None:
            # Stop all streams
            for sid in list(self.pipelines.keys()):
                self.stop_stream(sid)
            return
            
        # Stop specific stream
        if stream_id in self.pipelines:
            log.info(f"[TEST] Stopping stream {stream_id}")
            self.pipelines[stream_id].set_state(Gst.State.NULL)
            del self.pipelines[stream_id]
            
            if stream_id in self.streams_info:
                del self.streams_info[stream_id]
    
    def shutdown(self):
        """Shut down everything"""
        log.info("[TEST] Shutting down media streamer")
        
        # Stop all streams
        self.stop_stream()
        
        # Stop the mainloop
        if self.main_loop and self.main_loop.is_running():
            self.main_loop.quit()
            
        # Wait for threads
        import threading
        if self.main_loop_thread and self.main_loop_thread.is_alive():
            self.main_loop_thread.join(1)
            
        self.running = False
        log.info("[TEST] Media streamer shut down")
    
    def get_stream_status(self):
        """Get status of all streams"""
        result = {}
        
        for stream_id in self.pipelines.keys():
            if stream_id not in self.streams_info:
                continue
                
            info = self.streams_info[stream_id]
            
            # Get pipeline state
            pipeline = self.pipelines[stream_id]
            state_return = pipeline.get_state(0)
            state = state_return[1].value_nick if state_return[0] == Gst.StateChangeReturn.SUCCESS else "unknown"
            
            # Get duration
            duration = int(time.time() - info["start_time"])
            
            result[stream_id] = {
                "stream_id": stream_id,
                "status": state,
                "video_path": os.path.basename(info["video_path"]),
                "dest_ip": info["dest_ip"],
                "dest_port": info["dest_port"],
                "duration": duration
            }
            
        return result
    
    def get_active_streams_count(self):
        """Get count of active streams"""
        return len(self.pipelines)


def test_multiple_streams(num_streams):
    """Test multiple concurrent streams"""
    # Find some video files to test with
    video_files = []
    for root, _, files in os.walk("sample_videos"):
        for file in files:
            if file.endswith((".mp4", ".avi", ".mkv")):
                video_files.append(os.path.join(root, file))
    
    if not video_files:
        log.error("[TEST] No video files found in sample_videos directory")
        return
    
    # Create media streamer
    streamer = MediaStreamer()
    
    # Start streams
    streams = []
    base_port = 9000
    
    log.info(f"[TEST] Starting {num_streams} streams...")
    
    for i in range(num_streams):
        video_path = video_files[i % len(video_files)]
        port = base_port + i
        ssrc = f"{1000000 + i}"
        
        log.info(f"[TEST] Starting stream #{i+1}: {os.path.basename(video_path)} -> 127.0.0.1:{port}")
        
        success = streamer.start_stream(
            video_path=video_path,
            dest_ip="127.0.0.1", 
            dest_port=port,
            ssrc=ssrc
        )
        
        if success:
            streams.append({
                "id": i+1,
                "port": port,
                "video": video_path
            })
    
    # Monitor streams
    try:
        log.info("[TEST] Press Ctrl+C to stop...")
        while True:
            print("\n" + "="*60)
            print(f"ACTIVE STREAMS: {streamer.get_active_streams_count()}")
            print("="*60)
            
            status = streamer.get_stream_status()
            for stream_id, info in status.items():
                print(f"Stream {stream_id}:")
                print(f"  Status: {info['status']}")
                print(f"  Video: {info['video_path']}")
                print(f"  Duration: {info['duration']}s")
                print()
                
            time.sleep(5)
    except KeyboardInterrupt:
        log.info("[TEST] Stopping all streams...")
        streamer.shutdown()
        log.info("[TEST] Test completed")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            num_streams = int(sys.argv[1])
        except ValueError:
            num_streams = 2
    else:
        num_streams = 2
        
    test_multiple_streams(num_streams) 