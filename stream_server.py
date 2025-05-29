#!/usr/bin/env python3
import gi
import os
import sys
import threading
import http.server
import socketserver
import socket
import logging
import time
import glob
from datetime import datetime
from urllib.parse import parse_qs, urlparse
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stream_viewer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("GB28181-Viewer")

# Initialize GStreamer
Gst.init(None)

# Global state
rtsp_pipeline = None
rtp_pipeline = None
mainloop = None
PORT = 8080
STREAM_DIR = os.path.abspath("stream")

# Added function to manually update M3U8 playlists when segments are found
def update_playlist_files():
    """Check for segments and update playlist files if GStreamer hasn't done it"""
    while True:
        try:
            # Check RTP segments
            rtp_segments = sorted(glob.glob(os.path.join(STREAM_DIR, "rtp_segment-*.ts")))
            if rtp_segments:
                rtp_playlist_path = os.path.join(STREAM_DIR, "rtp_stream.m3u8")
                with open(rtp_playlist_path, 'r') as f:
                    content = f.read()
                
                # If playlist doesn't have segments but we have segment files
                if "#EXTINF" not in content and rtp_segments:
                    logger.info(f"Manually updating RTP playlist with {len(rtp_segments)} segments")
                    with open(rtp_playlist_path, 'w') as f:
                        f.write("#EXTM3U\n")
                        f.write("#EXT-X-VERSION:3\n")
                        f.write("#EXT-X-MEDIA-SEQUENCE:0\n")
                        f.write("#EXT-X-TARGETDURATION:5\n\n")
                        
                        for segment in rtp_segments:
                            segment_name = os.path.basename(segment)
                            f.write(f"#EXTINF:5.0,\n")
                            f.write(f"/{segment_name}\n")
            
            # Sleep to avoid high CPU usage
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error updating playlists: {e}")
            time.sleep(5)  # Longer sleep on error

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STREAM_DIR, **kwargs)
    
    def log_message(self, format, *args):
        logger.info(f"HTTP: {format % args}")
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type, Accept')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        logger.info(f"HTTP Request: {self.path}")
        
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Get the server's IP address
            hostname = socket.gethostname()
            try:
                server_ip = socket.gethostbyname(hostname)
            except:
                server_ip = "your-server-ip"
            
            # Check if stream files exist
            rtsp_playlist = os.path.join(STREAM_DIR, "rtsp_stream.m3u8")
            rtp_playlist = os.path.join(STREAM_DIR, "rtp_stream.m3u8")
            
            rtsp_exists = os.path.exists(rtsp_playlist)
            rtp_exists = os.path.exists(rtp_playlist)
            
            logger.info(f"Stream files status - RTSP: {rtsp_exists}, RTP: {rtp_exists}")
            
            # Debug info to show in the page
            debug_info = f"""
            <div class="debug">
                <h3>Debug Information</h3>
                <p>Stream directory: {STREAM_DIR}</p>
                <p>RTSP playlist exists: {rtsp_exists}</p>
                <p>RTP playlist exists: {rtp_exists}</p>
                <p>Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><a href="/dir">Directory listing</a></p>
            </div>
            """
            
            # Simple HTML player page with HLS.js for better browser compatibility
            html = f"""
            <html>
            <head>
                <title>GB28181 Restreamer Viewer</title>
                <meta http-equiv="refresh" content="300">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                    h1 {{ color: #333; text-align: center; }}
                    .container {{ display: flex; flex-direction: column; align-items: center; }}
                    .player {{ margin: 20px; padding: 20px; border: 1px solid #ddd; background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); width: 640px; }}
                    .player h2 {{ color: #555; }}
                    button {{ padding: 10px 15px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }}
                    button:hover {{ background-color: #45a049; }}
                    .debug {{ margin: 20px; padding: 10px; border: 1px dashed #ff8800; background-color: #fff9e6; border-radius: 5px; }}
                    .status {{ padding: 5px 10px; border-radius: 3px; font-size: 12px; font-weight: bold; }}
                    .status.success {{ background-color: #d4edda; color: #155724; }}
                    .status.error {{ background-color: #f8d7da; color: #721c24; }}
                </style>
                <!-- Add HLS.js for better browser compatibility -->
                <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
            </head>
            <body>
                <h1>GB28181 Restreamer Viewer</h1>
                <div class="container">
                    <div class="player">
                        <h2>RTSP Input Stream</h2>
                        <span class="status {{'success' if rtsp_exists else 'error'}}">
                            {{'READY' if rtsp_exists else 'NOT READY'}}
                        </span>
                        <video id="rtspPlayer" width="640" height="480" controls autoplay></video>
                        <p>RTSP source: rtsp://127.0.0.1:8554/test</p>
                        <button onclick="loadHlsStream('rtspPlayer', '/rtsp_stream.m3u8')">Reload RTSP Stream</button>
                    </div>
                    
                    <div class="player">
                        <h2>GB28181 Output Stream (RTP)</h2>
                        <span class="status {{'success' if rtp_exists else 'error'}}">
                            {{'READY' if rtp_exists else 'NOT READY'}}
                        </span>
                        <video id="rtpPlayer" width="640" height="480" controls autoplay></video>
                        <p>RTP output on port 9000</p>
                        <button onclick="loadHlsStream('rtpPlayer', '/rtp_stream.m3u8')">Reload RTP Stream</button>
                    </div>
                    
                    <p>If the videos don't play in the browser, you can also open these links in VLC:</p>
                    <ul>
                        <li><a href="http://{server_ip}:{PORT}/rtsp_stream.m3u8" target="_blank">RTSP Input Stream</a></li>
                        <li><a href="http://{server_ip}:{PORT}/rtp_stream.m3u8" target="_blank">GB28181 Output Stream</a></li>
                    </ul>
                    
                    {debug_info}
                </div>
                
                <script>
                    // Function to load HLS stream with HLS.js if supported, fallback to native
                    function loadHlsStream(videoId, streamUrl) {{
                        const video = document.getElementById(videoId);
                        const fullUrl = window.location.protocol + '//' + window.location.host + streamUrl + '?t=' + new Date().getTime();
                        console.log('Loading stream:', fullUrl);
                        
                        // If Media Source Extensions are supported
                        if (Hls.isSupported()) {{
                            const hls = new Hls({{
                                debug: true,
                                fragLoadingTimeOut: 60000,
                                manifestLoadingTimeOut: 60000
                            }});
                            hls.loadSource(fullUrl);
                            hls.attachMedia(video);
                            hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                                console.log('Manifest loaded, trying to play');
                                video.play().catch(e => console.error('Play error:', e));
                            }});
                            hls.on(Hls.Events.ERROR, function(event, data) {{
                                console.error('HLS error:', data);
                                if (data.fatal) {{
                                    switch(data.type) {{
                                        case Hls.ErrorTypes.NETWORK_ERROR:
                                            console.log('Network error, trying to recover');
                                            hls.startLoad();
                                            break;
                                        case Hls.ErrorTypes.MEDIA_ERROR:
                                            console.log('Media error, trying to recover');
                                            hls.recoverMediaError();
                                            break;
                                        default:
                                            console.error('Fatal error, cannot recover');
                                            break;
                                    }}
                                }}
                            }});
                        }}
                        // Try native browser HLS support as fallback
                        else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                            video.src = fullUrl;
                            video.addEventListener('loadedmetadata', function() {{
                                video.play().catch(e => console.error('Play error:', e));
                            }});
                        }}
                        else {{
                            console.error('HLS not supported in this browser');
                            // Show friendly message to the user
                            document.getElementById(videoId).insertAdjacentHTML('afterend', 
                                '<p style="color:red">Your browser does not support HLS streams. Please try VLC instead.</p>');
                        }}
                    }}
                    
                    // Initialize both players when page loads
                    document.addEventListener('DOMContentLoaded', function() {{
                        loadHlsStream('rtspPlayer', '/rtsp_stream.m3u8');
                        loadHlsStream('rtpPlayer', '/rtp_stream.m3u8');
                    }});
                </script>
            </body>
            </html>
            """
            self.wfile.write(html.encode())
            return
        elif self.path == '/dir':
            # Directory listing for debugging
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = "<html><head><title>Directory Listing</title></head><body>"
            html += f"<h1>Contents of {STREAM_DIR}</h1><ul>"
            
            try:
                for item in os.listdir(STREAM_DIR):
                    fullpath = os.path.join(STREAM_DIR, item)
                    size = os.path.getsize(fullpath)
                    mtime = os.path.getmtime(fullpath)
                    mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    html += f"<li><a href='{item}'>{item}</a> - {size} bytes - {mtime_str}</li>"
            except Exception as e:
                html += f"<li>Error: {e}</li>"
                
            html += "</ul></body></html>"
            self.wfile.write(html.encode())
            return
        
        # Let the parent class handle static files
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

def start_http_server():
    # Create working directory
    logger.info(f"Creating stream directory: {STREAM_DIR}")
    os.makedirs(STREAM_DIR, exist_ok=True)
    
    # Initialize placeholder files to avoid 404s
    for playlist in ["rtsp_stream.m3u8", "rtp_stream.m3u8"]:
        placeholder_path = os.path.join(STREAM_DIR, playlist)
        if not os.path.exists(placeholder_path):
            with open(placeholder_path, 'w') as f:
                f.write("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:5\n#EXT-X-MEDIA-SEQUENCE:0\n")
            logger.info(f"Created placeholder file: {placeholder_path}")
    
    handler = CORSHTTPRequestHandler
    httpd = socketserver.TCPServer(("", PORT), handler)
    logger.info(f"Serving at http://localhost:{PORT}")
    
    # Get the server's IP address
    hostname = socket.gethostname()
    try:
        server_ip = socket.gethostbyname(hostname)
        logger.info(f"Access from other computers: http://{server_ip}:{PORT}")
    except Exception as e:
        logger.error(f"Failed to get server IP: {e}")
        logger.info(f"Access from other computers: http://<server-ip>:{PORT}")
    
    httpd.serve_forever()

def create_rtsp_pipeline(rtsp_url="rtsp://127.0.0.1:8554/test"):
    """Create pipeline for RTSP source"""
    # Create absolute paths for HLS files
    playlist_path = os.path.join(STREAM_DIR, "rtsp_stream.m3u8")
    segment_pattern = os.path.join(STREAM_DIR, "rtsp_segment-%05d.ts")
    
    pipeline_str = (
        f'rtspsrc location="{rtsp_url}" latency=0 ! '
        'rtph264depay ! h264parse ! '
        f'mpegtsmux ! hlssink playlist-root=/ playlist-location="{playlist_path}" '
        f'location="{segment_pattern}" target-duration=5 max-files=10'
    )
    
    logger.info(f"Starting RTSP pipeline: {pipeline_str}")
    logger.info(f"RTSP Playlist path: {playlist_path}")
    
    return Gst.parse_launch(pipeline_str)

def create_rtp_pipeline(rtp_port=9000):
    """Create pipeline for RTP stream"""
    # Create absolute paths for HLS files
    playlist_path = os.path.join(STREAM_DIR, "rtp_stream.m3u8")
    segment_pattern = os.path.join(STREAM_DIR, "rtp_segment-%05d.ts")
    
    pipeline_str = (
        f'udpsrc port={rtp_port} caps="application/x-rtp,media=(string)video,encoding-name=(string)H264" ! '
        'rtpjitterbuffer ! rtph264depay ! h264parse ! '
        f'mpegtsmux ! hlssink playlist-root=/ playlist-location="{playlist_path}" '
        f'location="{segment_pattern}" target-duration=5 max-files=10'
    )
    
    logger.info(f"Starting RTP pipeline: {pipeline_str}")
    logger.info(f"RTP Playlist path: {playlist_path}")
    
    return Gst.parse_launch(pipeline_str)

def on_bus_message(bus, message, pipeline_name):
    t = message.type
    if t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        logger.error(f"[{pipeline_name}] Error: {err.message}")
        logger.error(f"[{pipeline_name}] Debug: {debug}")
    elif t == Gst.MessageType.EOS:
        logger.info(f"[{pipeline_name}] End of stream")
    elif t == Gst.MessageType.STATE_CHANGED:
        old, new, pending = message.parse_state_changed()
        if new == Gst.State.PLAYING:
            logger.info(f"[{pipeline_name}] Now playing")
    return True

def main():
    global rtsp_pipeline, rtp_pipeline
    
    rtsp_url = "rtsp://127.0.0.1:8554/test"
    rtp_port = 9000
    
    # Parse command line args
    if len(sys.argv) > 1:
        rtsp_url = sys.argv[1]
    if len(sys.argv) > 2:
        rtp_port = int(sys.argv[2])
    
    logger.info("GB28181 Restreamer Viewer")
    logger.info("-------------------------")
    logger.info(f"RTSP Source: {rtsp_url}")
    logger.info(f"RTP Port: {rtp_port}")
    logger.info(f"Stream directory: {STREAM_DIR}")
    logger.info("-------------------------")
    
    # Create stream directory
    os.makedirs(STREAM_DIR, exist_ok=True)
    
    # Start HTTP server in a thread
    server_thread = threading.Thread(target=start_http_server, daemon=True)
    server_thread.start()
    logger.info("HTTP server thread started")
    
    # Start playlist updater thread
    updater_thread = threading.Thread(target=update_playlist_files, daemon=True)
    updater_thread.start()
    logger.info("Playlist updater thread started")
    
    # Wait a moment for the HTTP server to be ready
    time.sleep(1)
    
    # Create a mainloop
    mainloop = GLib.MainLoop()
    
    # Start RTSP pipeline
    try:
        rtsp_pipeline = create_rtsp_pipeline(rtsp_url)
        rtsp_bus = rtsp_pipeline.get_bus()
        rtsp_bus.add_signal_watch()
        rtsp_bus.connect("message", on_bus_message, "RTSP")
        rtsp_pipeline.set_state(Gst.State.PLAYING)
        logger.info("RTSP pipeline created and set to PLAYING")
    except Exception as e:
        logger.error(f"Error starting RTSP pipeline: {e}")
        rtsp_pipeline = None
    
    # Start RTP pipeline
    try:
        rtp_pipeline = create_rtp_pipeline(rtp_port)
        rtp_bus = rtp_pipeline.get_bus()
        rtp_bus.add_signal_watch()
        rtp_bus.connect("message", on_bus_message, "RTP")
        rtp_pipeline.set_state(Gst.State.PLAYING)
        logger.info("RTP pipeline created and set to PLAYING")
    except Exception as e:
        logger.error(f"Error starting RTP pipeline: {e}")
        rtp_pipeline = None
    
    logger.info("\nStreaming server started!")
    logger.info("Open your browser and navigate to:")
    
    # Get the server's IP address
    hostname = socket.gethostname()
    try:
        server_ip = socket.gethostbyname(hostname)
        logger.info(f"http://{server_ip}:{PORT}")
    except:
        logger.info(f"http://<server-ip>:{PORT}")
    
    logger.info("\nPress Ctrl+C to stop")
    
    # Run mainloop
    try:
        mainloop.run()
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        if rtsp_pipeline:
            rtsp_pipeline.set_state(Gst.State.NULL)
            logger.info("RTSP pipeline stopped")
        if rtp_pipeline:
            rtp_pipeline.set_state(Gst.State.NULL)
            logger.info("RTP pipeline stopped")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
