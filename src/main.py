# src/main.py

import json
import os
import threading
import time
import signal
import sys
import atexit
from logger import log
from file_scanner import scan_video_files, get_video_catalog
from rtsp_handler import start_rtsp_stream, cleanup_all_streams, get_rtsp_status
from sip_handler_pjsip import SIPClient
from local_sip_server import LocalSIPServer
from media_streamer import MediaStreamer
from recording_manager import get_recording_manager
import cv2
import numpy as np


# Global variables for cleanup and status
sip_client = None
local_sip_server = None
rtsp_handlers = []
streamer = None
running = True
status_thread = None


def load_config(config_path):
    """Load configuration from a JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r') as file:
        config = json.load(file)

    required_keys = ["sip", "stream_directory"]
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")
            
    # Validate SIP configuration
    required_sip_keys = ["device_id", "username", "password", "server", "port"]
    for key in required_sip_keys:
        if key not in config["sip"]:
            raise ValueError(f"Missing required SIP config key: {key}")
            
    return config


def run_rtsp_sources(rtsp_sources):
    """Launch all configured RTSP sources as subprocesses."""
    global rtsp_handlers
    
    if not rtsp_sources:
        log.info("[RTSP] No RTSP sources configured")
        return
    
    # Check if RTSP server is running before trying to connect
    for rtsp_url in rtsp_sources:
        try:
            # Simple check to see if the RTSP server responds
            import socket
            from urllib.parse import urlparse
            
            parsed_url = urlparse(rtsp_url)
            host = parsed_url.hostname or "127.0.0.1"
            port = parsed_url.port or 554
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)  # 2 second timeout
            result = s.connect_ex((host, port))
            s.close()
            
            if result != 0:
                log.warning(f"[RTSP] RTSP server at {host}:{port} is not available, skipping {rtsp_url}")
                continue
                
            # Start RTSP stream handler
            handler = threading.Thread(target=start_rtsp_stream, args=(rtsp_url,), daemon=True)
            handler.start()
            rtsp_handlers.append(handler)
            log.info(f"[RTSP] Started RTSP stream handler for {rtsp_url}")
                
        except Exception as e:
            log.warning(f"[RTSP] Error checking RTSP source {rtsp_url}: {e}")
            # Don't start RTSP handler if there was an error
            log.warning(f"[RTSP] Skipping RTSP source {rtsp_url} due to error")


def periodic_status_check():
    """Periodically check and log the status of all components"""
    global running, sip_client
    
    log.info("[STATUS] Starting periodic status monitoring")
    
    while running:
        try:
            # Check active streams
            if sip_client:
                active_streams = len(sip_client.active_streams)
                log.info(f"[STATUS] Active streams: {active_streams}")
                
                # Log detailed stream info if there are active streams
                if active_streams > 0:
                    for callid, stream_info in sip_client.active_streams.items():
                        duration = int(time.time() - stream_info["start_time"])
                        log.info(f"[STATUS] Stream {callid}: running for {duration}s to {stream_info['dest_ip']}:{stream_info['dest_port']}")
            
            # Check RTSP status
            rtsp_status = get_rtsp_status()
            if rtsp_status:
                for url, status in rtsp_status.items():
                    health = status.get("health", "unknown")
                    log.info(f"[STATUS] RTSP {url}: {health}")
            
            # Sleep for 60 seconds before next check
            for _ in range(60):
                if not running:
                    break
                time.sleep(1)
                
        except Exception as e:
            log.error(f"[STATUS] Error in status check: {e}")
            time.sleep(60)


def cleanup():
    """Perform cleanup operations before exit"""
    log.warning("[SHUTDOWN] Cleaning up resources...")
    
    global running
    running = False
    
    # Stop SIP client
    global sip_client
    if sip_client:
        try:
            log.info("[SHUTDOWN] Stopping SIP client...")
            sip_client.stop()
        except Exception as e:
            log.error(f"[SHUTDOWN] Error stopping SIP client: {e}")
    
    # Stop local SIP server
    global local_sip_server
    if local_sip_server:
        try:
            log.info("[SHUTDOWN] Stopping local SIP server...")
            local_sip_server.stop()
        except Exception as e:
            log.error(f"[SHUTDOWN] Error stopping local SIP server: {e}")
            
    # Cleanup all RTSP streams
    try:
        log.info("[SHUTDOWN] Stopping all RTSP streams...")
        cleanup_all_streams()
    except Exception as e:
        log.error(f"[SHUTDOWN] Error stopping RTSP streams: {e}")
    
    # Stop media streamer
    global streamer
    if streamer:
        try:
            log.info("[SHUTDOWN] Stopping media streamer...")
            streamer.shutdown()
        except Exception as e:
            log.error(f"[SHUTDOWN] Error stopping media streamer: {e}")
    
    log.info("[SHUTDOWN] Cleanup complete")


def signal_handler(sig, frame):
    """Handle termination signals gracefully"""
    log.warning(f"[SHUTDOWN] Caught signal {sig}. Initiating graceful shutdown...")
    cleanup()
    sys.exit(0)


def find_available_port(start_port, max_tries=10):
    """Find an available port starting from the given port."""
    import socket
    
    for i in range(max_tries):
        port = start_port + (i * 2)  # Try even-numbered ports
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    
    return None


# Frame processor functions for video manipulation
def process_grayscale(frame, timestamp=None, stream_info=None):
    """Convert frame to grayscale and back to RGB"""
    if timestamp is None:
        timestamp = time.time()
    # Convert RGB to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    # Convert grayscale back to RGB
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), timestamp

def process_edge_detection(frame, timestamp=None, stream_info=None):
    """Apply edge detection"""
    if timestamp is None:
        timestamp = time.time()
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    # Apply Canny edge detection
    edges = cv2.Canny(gray, 100, 200)
    # Convert back to RGB
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB), timestamp

def process_blur(frame, timestamp=None, stream_info=None):
    """Apply gaussian blur"""
    if timestamp is None:
        timestamp = time.time()
    # Process in RGB color space directly
    return cv2.GaussianBlur(frame, (15, 15), 0), timestamp
    
def process_add_text(frame, timestamp=None, stream_info=None):
    """Add timestamp text to frame"""
    if timestamp is None:
        timestamp = time.time()
    # Work with copy to avoid modifying the original
    frame_copy = frame.copy()
    
    # Get current timestamp
    timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    
    # Since OpenCV uses BGR but we get RGB, convert colors manually for text
    # Green in RGB is (0, 255, 0) and Orange in RGB is (255, 165, 0)
    green_rgb = (0, 255, 0)
    orange_rgb = (255, 165, 0)
    
    # Add text to the frame
    cv2.putText(
        frame_copy, 
        f"Time: {timestamp_str}", 
        (20, 40), 
        cv2.FONT_HERSHEY_SIMPLEX, 
        1,
        green_rgb,  # Green color in RGB
        2
    )
    
    # Add project name
    cv2.putText(
        frame_copy, 
        "GB28181 Restreamer", 
        (20, frame_copy.shape[0] - 20), 
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.8,
        orange_rgb,  # Orange color in RGB
        2
    )
    
    return frame_copy, timestamp


def main():
    log.info("[BOOT] Starting GB28181 Restreamer...")
    global sip_client, local_sip_server, status_thread, streamer
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register cleanup function to be called on exit
    atexit.register(cleanup)

    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.normpath(os.path.join(current_dir, '..', 'config', 'config.json'))
        config = load_config(config_path)

        log.info("[CONFIG] Loaded configuration successfully.")

        # Scan for video files
        video_files = scan_video_files(config["stream_directory"])
        log.info(f"[CATALOG] {len(video_files)} video files found.")
        for video in video_files:
            log.info(f"  • {video}")

        # Create shared media streamer instance with processing capabilities
        log.info("[STREAM] Initializing media streamer with frame processing support")
        
        # Add pipeline configuration for frame processing if not present
        if "pipeline" not in config:
            config["pipeline"] = {
                "format": "RGB",
                "width": 640,
                "height": 480,
                "framerate": 30,
                "buffer_size": 33554432,  # 32MB buffer
                "queue_size": 3000,
                "sync": False,
                "async": False
            }
            
        streamer = MediaStreamer(config)
        # Start GLib main loop for GStreamer event handling
        streamer.start_glib_loop()
        
        # Initialize recording manager
        recording_manager = get_recording_manager(config)
        if recording_manager:
            # Scan for recordings
            recording_manager.scan_recordings(force=True)
            log.info("[RECORD] Recording manager initialized")
        
        # Start RTSP sources
        run_rtsp_sources(config.get("rtsp_sources", []))

        # Check if the SIP local port is already in use and adjust if needed
        if config.get("local_sip", {}).get("enabled", False):
            local_port = config.get("local_sip", {}).get("port", 5060)
            
            # Find an available port
            available_port = find_available_port(local_port)
            if available_port:
                if available_port != local_port:
                    log.info(f"[LOCAL-SIP] Using alternative port: {available_port}")
                    config["local_sip"]["port"] = available_port
            else:
                log.error("[LOCAL-SIP] Could not find an available port, disabling local SIP server")
                config["local_sip"]["enabled"] = False

        # Also find an available port for SIP client if not specified
        if "local_port" not in config["sip"]:
            # Find a port different from the local SIP server
            base_port = 5070  # Start from a different base port
            sip_client_port = find_available_port(base_port)
            if sip_client_port:
                log.info(f"[SIP] Using port {sip_client_port} for SIP client")
                config["sip"]["local_port"] = sip_client_port
            else:
                log.warning("[SIP] Could not find an available port for SIP client")

        # Register frame processors with streamer
        streamer.register_frame_processor("grayscale", process_grayscale)
        streamer.register_frame_processor("edge", process_edge_detection)
        streamer.register_frame_processor("blur", process_blur)
        streamer.register_frame_processor("text", process_add_text)
        log.info("[STREAM] Registered frame processors for video manipulation")

        # Start SIP client with improved error handling and streamer connection
        config["streamer"] = streamer  # Pass streamer instance to SIP client
        sip_client = SIPClient(config)
        
        # Start local SIP server if enabled
        if config.get("local_sip", {}).get("enabled", False):
            log.info("[LOCAL-SIP] Local SIP server is enabled")
            local_sip_server = LocalSIPServer(config, sip_client)
            local_sip_server.start()
        
        # Start status monitoring thread
        status_thread = threading.Thread(target=periodic_status_check, daemon=True)
        status_thread.start()
        
        try:
            log.info("[SIP] Starting SIP client...")
            sip_client.start()
            
            # Keep main thread alive with healthchecks
            while running:
                time.sleep(60)  # Check every minute instead of 30 seconds
                
                # DISABLED: Automatic restart logic that was causing connection loops
                # Check if SIP client is still running
                if not sip_client or not hasattr(sip_client, 'process') or sip_client.process is None:
                    log.warning("[MAIN] SIP client appears to have stopped")
                    
                    # Log more details about the process state
                    if sip_client and hasattr(sip_client, 'process'):
                        if sip_client.process is not None:
                            return_code = sip_client.process.poll()
                            log.warning(f"[MAIN] SIP process exit code: {return_code}")
                        else:
                            log.warning("[MAIN] SIP process is None - likely crashed")
                    else:
                        log.warning("[MAIN] SIP client object is invalid")
                    
                    # DISABLED: This automatic restart was causing VS Code popups every few seconds
                    # Instead, let the user manually restart if needed
                    log.warning("[MAIN] SIP client stopped. Manual restart required.")
                    log.warning("[MAIN] To restart: stop the application and run it again.")
                    break  # Exit the loop instead of restarting automatically
                
            # Regenerate the device catalog
            if not sip_client:
                log.warning("[MAIN] SIP client not available for catalog regeneration")
            else:
                log.info("[MAIN] Regenerating device catalog")
                sip_client.generate_device_catalog()
                # Test the catalog response format
                from gb28181_xml import format_catalog_response
                test_xml = format_catalog_response(sip_client.device_id, sip_client.device_catalog)
                with open('catalog_debug.xml', 'w') as f:
                    f.write(test_xml)
                log.info(f"[MAIN] Saved catalog debug XML to catalog_debug.xml with {len(sip_client.device_catalog)} channels")
            
        except KeyboardInterrupt:
            # This will trigger the cleanup through atexit
            log.warning("[SHUTDOWN] Caught keyboard interrupt.")
            return
    except FileNotFoundError as e:
        log.error(f"[ERROR] {e}")
        sys.exit(1)
    except ValueError as e:
        log.error(f"[ERROR] Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        log.exception(f"[ERROR] Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
