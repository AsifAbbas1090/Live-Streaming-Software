# src/main.py

import json
import os
import threading
import time
import signal
import sys
import atexit
import logging

# Set GStreamer environment variables BEFORE importing any GStreamer modules
# This suppresses internal GStreamer debug messages and critical warnings
os.environ.setdefault('GST_DEBUG', '0')
os.environ.setdefault('GST_DEBUG_NO_COLOR', '1') 
os.environ.setdefault('GST_DEBUG_DUMP_DOT_DIR', '/tmp')
os.environ.setdefault('GST_REGISTRY_FORK', 'no')
os.environ.setdefault('GST_DEBUG_FILE', '/dev/null')
os.environ.setdefault('G_MESSAGES_DEBUG', '')

# Suppress specific GStreamer critical assertion warnings at the C library level
import ctypes
import ctypes.util
import warnings

# Suppress Python warnings related to GStreamer
warnings.filterwarnings("ignore", category=RuntimeWarning, module="gi")
warnings.filterwarnings("ignore", message=".*gst_segment_to_running_time.*")

# Try to suppress GLib critical warnings at the C library level
try:
    glib = ctypes.CDLL(ctypes.util.find_library('glib-2.0'))
    glib.g_log_set_always_fatal(0)
    # Try to set a null log handler to suppress critical messages
    try:
        glib.g_log_set_default_handler(None, None)
    except:
        pass
except:
    pass  # If we can't load glib, just continue

# Add a logging filter to suppress GStreamer critical warnings
class GStreamerCriticalFilter(logging.Filter):
    """Filter to suppress non-critical GStreamer warnings"""
    
    def filter(self, record):
        # Suppress specific GStreamer critical warnings that don't affect functionality
        critical_patterns = [
            "gst_segment_to_running_time: assertion",
            "segment->format == format",
            "segment format",
            "Critical",
            "GStreamer-CRITICAL",
            "assertion 'segment->format == format' failed",
            "gst_segment_to_running_time",
            "format == format"
        ]
        
        # Check if the log message contains any of the patterns to suppress
        msg = str(record.getMessage()).lower()
        return not any(pattern.lower() in msg for pattern in critical_patterns)

# Add the filter to suppress GStreamer critical warnings
gst_filter = GStreamerCriticalFilter()
logging.getLogger().addFilter(gst_filter)

# Now import the rest of the modules
from logger import log
from file_scanner import scan_video_files, get_video_catalog
from rtsp_handler import start_rtsp_stream, cleanup_all_streams, get_rtsp_status
from live_stream_handler import LiveStreamHandler
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
live_stream_handler = None
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


def run_rtsp_sources(rtsp_sources, config):
    """Launch all configured RTSP sources using the enhanced LiveStreamHandler."""
    global live_stream_handler
    
    if not rtsp_sources:
        log.info("[RTSP] No RTSP sources configured")
        return
    
    # Initialize the live stream handler
    live_stream_handler = LiveStreamHandler(config)
    live_stream_handler.start()
    
    log.info(f"[RTSP] Setting up {len(rtsp_sources)} RTSP sources for live streaming")
    
    # Process RTSP sources from configuration  
    for i, rtsp_config in enumerate(rtsp_sources):
        try:
            # Handle both string URLs and config objects
            if isinstance(rtsp_config, str):
                rtsp_url = rtsp_config
                device_name = f"RTSP Camera {i+1}"
            else:
                rtsp_url = rtsp_config.get("url")
                device_name = rtsp_config.get("name", f"RTSP Camera {i+1}")
                enabled = rtsp_config.get("enabled", True)
                
                if not enabled:
                    log.info(f"[RTSP] Skipping disabled RTSP source: {device_name}")
                    continue
            
            if not rtsp_url:
                log.warning(f"[RTSP] Invalid RTSP config: {rtsp_config}")
                continue
            
            # Simple check to see if the RTSP server responds
            import socket
            from urllib.parse import urlparse
            
            parsed_url = urlparse(rtsp_url)
            host = parsed_url.hostname or "127.0.0.1"
            port = parsed_url.port or 554
            
            # Test connection to RTSP server
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)  # 2 second timeout
            result = s.connect_ex((host, port))
            s.close()
            
            if result != 0:
                log.warning(f"[RTSP] RTSP server at {host}:{port} is not available, will attempt to start handler anyway")
                # Continue anyway as the server might be temporarily unavailable
            
            # RTSP sources are now handled as channels under the main device by the SIP handler
            # No separate device registration needed - they will appear as channels in the catalog
            log.info(f"[RTSP] Preparing RTSP source: {device_name} ({rtsp_url})")
            
            # The actual streaming will be initiated when WVP requests an INVITE
            # The SIP handler will route RTSP requests to the LiveStreamHandler
            
        except Exception as e:
            log.warning(f"[RTSP] Error setting up RTSP source {rtsp_url}: {e}")
            log.warning(f"[RTSP] Continuing with other sources...")
    
    log.info(f"[RTSP] ✅ Live stream handler ready for {len(rtsp_sources)} RTSP sources")


def periodic_status_check():
    """Periodically check and log the status of all components"""
    global running, sip_client
    
    log.info("[STATUS] Starting periodic status monitoring")
    
    # Get recording manager reference
    try:
        recording_manager = get_recording_manager(None)  # Get existing instance
    except:
        recording_manager = None
    
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
            
            # Check recording manager status
            if recording_manager:
                try:
                    scan_status = recording_manager.get_scan_status()
                    if scan_status['scanning']:
                        log.info(f"[STATUS] Recording scan in progress: {scan_status['files_cached']} files found")
                    elif scan_status['scan_complete']:
                        log.info(f"[STATUS] Recording scan complete: {scan_status['files_cached']} files cached")
                except Exception as e:
                    log.debug(f"[STATUS] Could not get recording status: {e}")
            
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
            
    # Cleanup all RTSP streams and live stream handler
    try:
        log.info("[SHUTDOWN] Stopping all RTSP streams...")
        cleanup_all_streams()
    except Exception as e:
        log.error(f"[SHUTDOWN] Error stopping RTSP streams: {e}")
    
    # Stop live stream handler
    global live_stream_handler
    if live_stream_handler:
        try:
            log.info("[SHUTDOWN] Stopping live stream handler...")
            live_stream_handler.stop()
        except Exception as e:
            log.error(f"[SHUTDOWN] Error stopping live stream handler: {e}")
    
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

        # QUICK SCAN: Just get a small sample of video files for immediate catalog generation
        log.info("[CATALOG] Performing quick video scan (full scan will happen in background)...")
        try:
            sample_videos = []
            # Get just the first few video files from each directory for immediate use
            for root, dirs, files in os.walk(config["stream_directory"]):
                dirs[:] = [d for d in dirs if not d.startswith('.')]  # Skip hidden dirs
                video_count = 0
                for file in files:
                    if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.ts', '.m4v')):
                        sample_videos.append(os.path.join(root, file))
                        video_count += 1
                        if video_count >= 5:  # Only take first 5 videos per directory
                            break
                if len(sample_videos) >= 20:  # Limit total sample to 20 videos
                    break
            
            log.info(f"[CATALOG] Quick scan found {len(sample_videos)} sample video files")
            for video in sample_videos[:5]:  # Log first 5
                log.info(f"  • {os.path.basename(video)}")
            if len(sample_videos) > 5:
                log.info(f"  ... and {len(sample_videos) - 5} more videos")
                
            # Set this as temporary catalog for immediate use
            config["sample_videos"] = sample_videos
            
        except Exception as e:
            log.error(f"[CATALOG] Quick scan failed: {e}")
            config["sample_videos"] = []

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
        
        # Start RTSP sources with live stream handler
        run_rtsp_sources(config.get("rtsp_sources", []), config)

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

        # PRIORITY: Start SIP client first to get online quickly
        log.info("[SIP] Starting SIP client with priority (recording scan will happen in background)...")
        config["streamer"] = streamer  # Pass streamer instance to SIP client
        sip_client = SIPClient(config)
        
        # Start local SIP server if enabled
        if config.get("local_sip", {}).get("enabled", False):
            log.info("[LOCAL-SIP] Local SIP server is enabled")
            local_sip_server = LocalSIPServer(config, sip_client)
            local_sip_server.start()
        
        # Start SIP client in a separate thread to avoid blocking
        sip_thread = threading.Thread(target=sip_client.start, daemon=True)
        sip_thread.start()
        log.info("[SIP] SIP client started in background thread")
        
        # Give SIP client a moment to start registering
        time.sleep(2)
        
        # NOW start recording manager after SIP is initializing (this is the expensive operation)
        log.info("[RECORD] Starting recording manager (this will scan files in background)...")
        recording_manager = get_recording_manager(config)
        if recording_manager:
            # The recording manager will scan asynchronously in its own thread
            log.info("[RECORD] Recording manager initialized with async scanning")
            # Log initial scan status
            status = recording_manager.get_scan_status()
            log.info(f"[RECORD] Initial scan status: {status['files_cached']} files cached, scanning={status['scanning']}")
        else:
            log.warning("[RECORD] Recording manager not available")
        
        # Start status monitoring thread
        status_thread = threading.Thread(target=periodic_status_check, daemon=True)
        status_thread.start()
        
        try:
            # Wait for SIP client thread and monitor its health
            log.info("[MAIN] Monitoring SIP client health...")
            
            # Keep main thread alive with healthchecks
            while running:
                time.sleep(60)  # Check every minute instead of 30 seconds
                
                # Check if SIP thread is still alive
                if not sip_thread.is_alive():
                    log.warning("[MAIN] SIP client thread has ended")
                    break
                
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
