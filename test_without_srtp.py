#!/usr/bin/env python3
# test_without_srtp.py - Test script without SRTP encryption

import os
import sys
import time
import json
import logging
import numpy as np
import cv2
import argparse
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi.repository import Gst, GLib
from gi.repository import GstApp

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# Initialize GStreamer
Gst.init(None)

def create_pipeline(video_path, dest_ip, dest_port, ssrc="1234"):
    """Create a simple RTP pipeline without SRTP encryption"""
    
    pipeline_str = f"""
        filesrc location="{video_path}" ! 
        qtdemux ! queue ! h264parse ! avdec_h264 ! 
        videoconvert ! videorate ! videoscale ! 
        video/x-raw,format=I420,framerate=25/1,width=640,height=480 ! 
        x264enc tune=zerolatency bitrate=1024 key-int-max=30 ! 
        video/x-h264,profile=baseline ! 
        rtph264pay config-interval=1 pt=96 ssrc={ssrc} ! 
        udpsink host={dest_ip} port={dest_port} sync=false async=false
    """
    
    log.info(f"Creating pipeline with video: {video_path}")
    log.info(f"Destination: {dest_ip}:{dest_port}")
    log.info(f"Pipeline: {pipeline_str}")
    
    try:
        pipeline = Gst.parse_launch(pipeline_str)
        return pipeline
    except Exception as e:
        log.error(f"Failed to create pipeline: {e}")
        return None

def run_test(args):
    """Run the test with the specified arguments"""
    
    # Create the pipeline
    pipeline = create_pipeline(
        args.video,
        args.ip,
        args.port,
        args.ssrc
    )
    
    if not pipeline:
        log.error("Failed to create pipeline. Exiting.")
        return False
    
    # Create a GLib main loop
    loop = GLib.MainLoop()
    
    # Set up the bus watcher
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    
    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            log.info("End of stream")
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.error(f"Error: {err.message}")
            loop.quit()
            
    bus.connect("message", on_message)
    
    # Start the pipeline
    pipeline.set_state(Gst.State.PLAYING)
    log.info("Pipeline started. Use VLC to view: vlc rtp://<ip>:<port>")
    log.info(f"Stream will run for {args.duration} seconds")
    
    # Start a timer to stop the stream after the specified duration
    def stop_after_duration():
        time.sleep(args.duration)
        log.info("Duration reached, stopping pipeline")
        pipeline.set_state(Gst.State.NULL)
        loop.quit()
        
    import threading
    timer = threading.Thread(target=stop_after_duration)
    timer.daemon = True
    timer.start()
    
    try:
        loop.run()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    finally:
        pipeline.set_state(Gst.State.NULL)
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Test RTP streaming without SRTP encryption")
    parser.add_argument("--video", default="sample_videos/video.mp4", help="Path to video file")
    parser.add_argument("--ip", default="127.0.0.1", help="Destination IP address")
    parser.add_argument("--port", type=int, default=9000, help="Destination port")
    parser.add_argument("--ssrc", default="1234", help="SSRC value")
    parser.add_argument("--duration", type=int, default=60, help="Stream duration in seconds")
    args = parser.parse_args()
    
    run_test(args)
    
if __name__ == "__main__":
    main() 