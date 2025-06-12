# src/sip_handler_pjsip.py
import subprocess
import threading
import time
import re
import os
import logging
import json
import tempfile
import signal
import xml.etree.ElementTree as ET
from logger import log
from file_scanner import get_video_catalog, scan_video_files
from media_streamer import MediaStreamer
from recording_manager import get_recording_manager
from gb28181_xml import (
    format_catalog_response,
    format_device_info_response,
    format_keepalive_response,
    format_device_status_response,
    format_media_status_response,
    format_recordinfo_response,
    parse_xml_message,
    parse_recordinfo_query
)
from gb28181_sip_sender import GB28181SIPSender

class SIPClient:
    def __init__(self, config):
        """Initialize SIP client"""
        self.config = config
        self.device_id = config["sip"]["device_id"]
        self.username = config["sip"]["username"]
        self.password = config["sip"]["password"]
        self.server = config["sip"]["server"]
        self.port = config["sip"]["port"]
        self.local_port = config["sip"].get("local_port", 5080)
        self.realm = config["sip"].get("realm", "*")
        self.transport = config["sip"].get("transport", "udp")
        self.stream_directory = config["stream_directory"]
        
        # For handling streams
        self.active_streams = {}
        self.stream_locks = {}
        
        # For storing device catalog
        self.device_catalog = {}
        
        # FIXED: Thread-safe rate limiting for catalog responses
        self._catalog_lock = threading.Lock()
        self._last_catalog_time = 0
        self.catalog_response_interval = 0.5  # Reduced from 2 to 0.5 seconds for faster WVP response
        
        # FIXED: Thread-safe catalog generation
        self._catalog_generation_lock = threading.Lock()
        
        # FIXED: Enhanced health monitoring for WVP platform compatibility
        self.registration_status = "OFFLINE"
        self.last_keepalive_time = None
        self.last_keepalive_check = time.time()
        self.keepalive_interval = 15  # FIXED: Reduced from 30 to 15 seconds for WVP compatibility
        self.registration_retry_interval = 20  # FIXED: Reduced from 30 to 20 seconds for faster recovery
        self.last_registration_time = 0  # Track when we last registered
        self.registration_timeout = 120  # FIXED: Registration expires in 2 minutes (120s) for WVP platform
        
        # Streamer connection
        self.streamer = config.get("streamer")
        
        # Initialize SIP sender for XML messages
        self.sip_sender = GB28181SIPSender(config)
        
        # SIP status
        self.running = False
        self.process = None
        self.last_registration_attempt = 0
        self.registration_failures = 0
        
        # Add missing attributes to prevent errors
        self.registration_attempts = 0
        self.max_registration_attempts = 5
        self.last_keepalive = time.time()
        self.catalog_ready = False # Used to track if catalog has been generated at least once
        self.last_catalog_update = 0
        
        # Create thread-safe pipe for communication with PJSUA
        self.pipe_read, self.pipe_write = os.pipe()
        
        # Initialize SIP header storage for OPTIONS responses
        self._last_via = ""
        self._last_from = ""
        self._last_to = ""
        self._last_call_id = ""
        self._last_cseq = ""
        self._local_tag = f"tag{int(time.time())}"
        self.local_ip = self._get_local_ip()  # Get actual local IP

        # ADDED: Enhanced message processing with thread safety
        self._message_processing_lock = threading.Lock()
        self._pending_catalog_queries = {}  # Track pending queries to prevent duplicates
        
        # FIXED: Dedicated heartbeat thread for WVP platform compatibility with reduced intervals
        self._heartbeat_thread = None
        self._heartbeat_running = False
        self._last_successful_keepalive = time.time()  # Track successful keepalives for failure detection

    def _get_local_ip(self):
        """Get the local IP address that can reach the SIP server"""
        try:
            import socket
            # Create a socket to determine which local IP is used to reach the server
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.server, self.port))
            local_ip = s.getsockname()[0]
            s.close()
            log.info(f"[SIP] Determined local IP: {local_ip}")
            return local_ip
        except Exception as e:
            log.warning(f"[SIP] Could not determine local IP: {e}, using 127.0.0.1")
            return "127.0.0.1"

    def generate_device_catalog(self):
        """Generate device catalog information according to GB28181 standard with thread safety"""
        # FIXED: Thread-safe catalog generation
        with self._catalog_generation_lock:
            try:
                log.info("[SIP] 🔧 Generating device catalog (thread-safe)...")
                
                # Clear existing catalog first
                self.device_catalog = {}
                
                # First, try to scan video files with improved error handling
                video_catalog = []
                stream_dir = self.config.get('stream_directory', './recordings')
                log.info(f"[SIP] 📁 Using stream directory: {stream_dir}")
                
                try:
                    from file_scanner import scan_video_files, get_video_catalog
                    
                    # Ensure directory exists
                    import os
                    if not os.path.exists(stream_dir):
                        log.warning(f"[SIP] ⚠️ Stream directory does not exist: {stream_dir}")
                        log.info(f"[SIP] 📂 Creating stream directory: {stream_dir}")
                        os.makedirs(stream_dir, exist_ok=True)
                    
                    # Scan videos with detailed logging
                    log.info(f"[SIP] 🔍 Scanning videos in: {stream_dir}")
                    scan_result = scan_video_files(stream_dir)
                    video_catalog = get_video_catalog()
                    log.info(f"[SIP] ✅ Video scanning complete: Found {len(video_catalog)} video files")
                    
                    # Show first few videos for debugging
                    if video_catalog:
                        for i, video_path in enumerate(video_catalog[:3]):
                            log.info(f"[SIP]   Video {i+1}: {os.path.basename(video_path)}")
                    
                except Exception as e:
                    log.error(f"[SIP] ❌ Error during video scanning: {e}")
                    import traceback
                    log.debug(f"[SIP] Traceback: {traceback.format_exc()}")
                    video_catalog = []
                
                # Create channels from video files (limit to 20 for WVP platform)
                channels_created = 0
                if video_catalog:
                    log.info(f"[SIP] 📺 Creating channels from {len(video_catalog)} video files")
                    for i, video_path in enumerate(video_catalog[:20], 1):  # Limit to 20 channels for WVP
                        try:
                            # Generate proper 20-digit channel ID with type 131 (video channel)
                            base_id = self.device_id[:12] if len(self.device_id) >= 12 else "340200000000"
                            channel_id = f"{base_id}131{i:06d}"
                            
                            # Extract meaningful name from video file path
                            video_name = os.path.splitext(os.path.basename(video_path))[0]
                            if len(video_name) > 30:  # Truncate long names
                                video_name = video_name[:27] + "..."
                            
                            # Get file size if possible
                            try:
                                file_size = os.path.getsize(video_path)
                            except:
                                file_size = 0
                            
                            self.device_catalog[channel_id] = {
                                'name': video_name,
                                'manufacturer': 'GB28181-Restreamer',
                                'model': 'File Stream',
                                'status': 'ON',
                                'parent_id': self.device_id,
                                'video_path': video_path,
                                'file_size': file_size,
                                'duration': 'Unknown'
                            }
                            channels_created += 1
                            
                        except Exception as channel_error:
                            log.error(f"[SIP] ❌ Error creating channel for {video_path}: {channel_error}")
                
                # CRITICAL: Always ensure we have at least 2 channels for the frontend
                if channels_created == 0:
                    log.warning("[SIP] ⚠️ No video channels created, generating default test channels")
                    
                    # Check for RTSP sources first
                    rtsp_sources = self.config.get('rtsp_sources', [])
                    if rtsp_sources:
                        log.info(f"[SIP] 📡 Creating {len(rtsp_sources)} RTSP channels")
                        for i, rtsp_url in enumerate(rtsp_sources[:10], 1):  # Limit to 10 RTSP sources
                            base_id = self.device_id[:12] if len(self.device_id) >= 12 else "340200000000"
                            channel_id = f"{base_id}131{i:06d}"
                            
                            self.device_catalog[channel_id] = {
                                'name': f'RTSP Stream {i}',
                                'manufacturer': 'GB28181-Restreamer',
                                'model': 'RTSP Camera',
                                'status': 'ON',
                                'parent_id': self.device_id,
                                'rtsp_url': rtsp_url
                            }
                            channels_created += 1
                    
                    # If still no channels, create 2 default test channels
                    if channels_created == 0:
                        log.info("[SIP] 🎯 Creating 2 default test channels for WVP frontend")
                        base_id = self.device_id[:12] if len(self.device_id) >= 12 else "340200000000"
                        
                        # Channel 1
                        channel_id_1 = f"{base_id}13100001"
                        self.device_catalog[channel_id_1] = {
                            'name': 'Test Camera 1',
                            'manufacturer': 'GB28181-Restreamer',
                            'model': 'Virtual Camera',
                            'status': 'ON',
                            'parent_id': self.device_id
                        }
                        
                        # Channel 2  
                        channel_id_2 = f"{base_id}13100002"
                        self.device_catalog[channel_id_2] = {
                            'name': 'Test Camera 2',
                            'manufacturer': 'GB28181-Restreamer',
                            'model': 'Virtual Camera',
                            'status': 'ON',
                            'parent_id': self.device_id
                        }
                        channels_created = 2
                
                # Mark catalog as ready
                self.catalog_ready = True
                self.last_catalog_update = time.time()
                
                log.info(f"[SIP] ✅ Generated device catalog with {len(self.device_catalog)} channels")
                log.info(f"[SIP] 📊 Catalog summary:")
                log.info(f"[SIP]   • Total channels: {len(self.device_catalog)}")
                log.info(f"[SIP]   • Video file channels: {channels_created}")
                log.info(f"[SIP]   • Ready for WVP platform: {self.catalog_ready}")
                
                # Debug output for first few channels
                for i, (channel_id, channel_info) in enumerate(list(self.device_catalog.items())[:3]):
                    log.info(f"[SIP]   Channel {i+1}: {channel_id} - {channel_info['name']}")
                
                if len(self.device_catalog) > 3:
                    log.info(f"[SIP]   ... and {len(self.device_catalog) - 3} more channels")
                
                return self.device_catalog
                
            except Exception as e:
                log.error(f"[SIP] ❌ CRITICAL ERROR in catalog generation: {e}")
                import traceback
                log.error(f"[SIP] Traceback: {traceback.format_exc()}")
                
                # Emergency fallback - create minimal working catalog
                log.error("[SIP] 🚨 Using emergency fallback catalog")
                self.device_catalog = {}
                base_id = self.device_id[:12] if len(self.device_id) >= 12 else "340200000000"
                
                self.device_catalog[f"{base_id}13100001"] = {
                    'name': 'Emergency Channel 1',
                    'manufacturer': 'GB28181-Restreamer',
                    'model': 'Fallback',
                    'status': 'ON',
                    'parent_id': self.device_id
                }
                
                self.device_catalog[f"{base_id}13100002"] = {
                    'name': 'Emergency Channel 2', 
                    'manufacturer': 'GB28181-Restreamer',
                    'model': 'Fallback',
                    'status': 'ON',
                    'parent_id': self.device_id
                }
                
                self.catalog_ready = True
                self.last_catalog_update = time.time()
                
                log.error(f"[SIP] 🆘 Emergency catalog created with {len(self.device_catalog)} channels")
                return self.device_catalog

    def extract_sdp_from_message(self, msg_text):
        """Extract SDP content from a SIP message with enhanced parsing
        
        This function handles various SDP formats found in GB28181 implementations:
        - Standard SDP format (after empty line)
        - Embedded SDP without proper separators
        - Partial SDP information in log lines
        - Malformed SDP with missing fields
        """
        # Method 1: Find the SDP section which typically starts after an empty line
        sdp_section = re.search(r'\r\n\r\n(v=0.*)', msg_text, re.DOTALL)
        if sdp_section:
            log.debug("[SIP] Found SDP using standard empty line separator")
            return self._validate_and_fix_sdp(sdp_section.group(1))
        
        # Method 2: Look for SDP with alternative separators
        alt_sdp_section = re.search(r'(\r\n|\n)(v=0.*)', msg_text, re.DOTALL)
        if alt_sdp_section:
            log.debug("[SIP] Found SDP using alternative separator")
            return self._validate_and_fix_sdp(alt_sdp_section.group(2))
        
        # Method 3: If we can't find the standard pattern, look for SDP contents more generally
        sdp_start = msg_text.find('v=0')
        if sdp_start != -1:
            log.debug("[SIP] Found SDP using direct v=0 search")
            return self._validate_and_fix_sdp(msg_text[sdp_start:])
        
        # Method 4: Extract key SDP fields to reconstruct a minimal valid SDP
        log.debug("[SIP] No standard SDP found, attempting to extract key fields")
        
        # Extract IP address (c= line)
        c_match = re.search(r'c=IN IP4 (\d+\.\d+\.\d+\.\d+)', msg_text)
        # Extract port (m= line)
        m_match = re.search(r'm=video (\d+)', msg_text)
        # Look for SSRC (y= line in GB28181)
        y_match = re.search(r'y=(\d+)', msg_text)
        # Look for format (f= line in GB28181)
        f_match = re.search(r'f=v/(\d+)/(\d+)', msg_text)
        
        if c_match or m_match or y_match:
            log.debug("[SIP] Reconstructing SDP from partial fields")
            sdp_parts = []
            sdp_parts.append("v=0")
            sdp_parts.append(f"o=- {int(time.time())} 1 IN IP4 127.0.0.1")
            sdp_parts.append("s=GB28181 Stream")
            sdp_parts.append("t=0 0")
            
            # Add connection information if available
            if c_match:
                sdp_parts.append(f"c=IN IP4 {c_match.group(1)}")
            else:
                # Use server IP as fallback
                sdp_parts.append(f"c=IN IP4 {self.server}")
                log.warning("[SIP] No IP found in SDP, using server IP as fallback")
            
            # Add media description if available
            if m_match:
                sdp_parts.append(f"m=video {m_match.group(1)} RTP/AVP 96")
            else:
                # Use default port as fallback
                sdp_parts.append("m=video 9000 RTP/AVP 96")
                log.warning("[SIP] No port found in SDP, using default port 9000")
            
            # Add RTPMAP for H.264
            sdp_parts.append("a=rtpmap:96 H264/90000")
            sdp_parts.append("a=fmtp:96 profile-level-id=42e01f")
            
            # Add SSRC if available (GB28181 specific)
            if y_match:
                sdp_parts.append(f"y={y_match.group(1)}")
            else:
                sdp_parts.append("y=0000000001")
                
            # Add format if available (GB28181 specific)
            if f_match:
                sdp_parts.append(f"f=v/{f_match.group(1)}/{f_match.group(2)}")
            else:
                sdp_parts.append("f=v/2/25")  # Default to H.264 at 25fps
                
            return "\n".join(sdp_parts)
        
        log.error("[SIP] Failed to extract or reconstruct SDP from message")
        return None

    def _validate_and_fix_sdp(self, sdp_text):
        """Validate and fix common SDP issues"""
        if not sdp_text:
            return None
            
        lines = sdp_text.splitlines()
        fixed_lines = []
        has_video = False
        has_rtpmap = False
        has_connection = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Fix common issues
            if line.startswith('m=video'):
                has_video = True
                # Ensure RTP/AVP is present
                if 'RTP/AVP' not in line:
                    line = line.replace('UDP', 'RTP/AVP')
                # Ensure payload type 96 is present
                if not re.search(r'\s96(\s|$)', line):
                    line = f"{line} 96"
                    
            elif line.startswith('c=IN'):
                has_connection = True
                # Ensure IPv4 is specified
                if 'IP4' not in line:
                    line = line.replace('IN ', 'IN IP4 ')
                    
            elif line.startswith('a=rtpmap:96'):
                has_rtpmap = True
                # Ensure correct format for H.264
                if 'H264' not in line:
                    line = 'a=rtpmap:96 H264/90000'
                
            fixed_lines.append(line)
            
        # Add missing required fields
        if not has_video:
            fixed_lines.append('m=video 9000 RTP/AVP 96')
        if not has_connection:
            fixed_lines.append(f'c=IN IP4 {self.server}') # This might be the platform's IP, use self.local_ip for local SIP client's perspective?
                                                       # However, for an SDP *offer*, it indicates the target IP for media.
        if not has_rtpmap:
            fixed_lines.append('a=rtpmap:96 H264/90000')
            fixed_lines.append('a=fmtp:96 profile-level-id=42e01f')
            
        # Ensure GB28181 specific fields
        if not any(l.startswith('y=') for l in fixed_lines):
            fixed_lines.append('y=0000000001')
        if not any(l.startswith('f=') for l in fixed_lines):
            fixed_lines.append('f=v/2/25')
            
        return '\n'.join(fixed_lines)

    def parse_sdp_and_stream(self, sdp_text, callid=None, target_channel=None, ssrc=None):
        """Parse SDP offer and start streaming to the specified destination
        
        Enhanced with better error handling and recovery mechanisms.
        Added SSRC parameter for WVP compatibility.
        """
        try:
            # Check if sdp_text is already SDP content or a full SIP message
            if sdp_text.strip().startswith('v='):
                # Already SDP content
                sdp_content = sdp_text
                log.debug("[SIP] Using provided SDP content directly")
            else:
                # Extract SDP content from full SIP message
                sdp_content = self.extract_sdp_from_message(sdp_text)
                if not sdp_content:
                    log.warning("[SIP] ⚠️ No SDP content found in message, cannot start stream")
                    return False
                log.debug("[SIP] Extracted SDP content from SIP message")
                
            log.debug(f"[SIP] Using SDP content: {sdp_content}")
                
            # Extract destination IP (c= line)
            ip_match = re.search(r"c=IN IP4 (\d+\.\d+\.\d+\.\d+)", sdp_content)
            if not ip_match:
                log.warning("[SIP] ⚠️ Failed to extract IP address from SDP")
                # Use the server IP as fallback
                ip = self.server
                log.info(f"[SIP] Using fallback IP: {ip}")
            else:
                ip = ip_match.group(1)
                
            # Extract port (m= line)
            port_match = re.search(r"m=video (\d+)", sdp_content)
            if not port_match:
                log.warning("[SIP] ⚠️ Failed to extract port from SDP")
                # Use a default port as fallback
                port = 9000
                log.info(f"[SIP] Using fallback port: {port}")
            else:
                port = int(port_match.group(1))
            
            # CRITICAL FIX: Extract transport protocol from SDP
            transport_protocol = "UDP"  # Default
            m_line_match = re.search(r"m=video \d+ ([A-Z/]+)", sdp_content)
            if m_line_match:
                transport_protocol = m_line_match.group(1)
                log.info(f"[SIP] 🚀 Detected transport protocol: {transport_protocol}")
            else:
                log.warning(f"[SIP] Could not detect transport protocol from SDP, using default UDP")
            
            # Extract SSRC (y= line in GB28181) or use provided SSRC
            if ssrc is None:
                # Try to extract from SDP
                y_match = re.search(r"y=(\d+)", sdp_content)
                ssrc = y_match.group(1) if y_match else "0000000001"
            else:
                log.info(f"[SIP] 🎯 Using provided SSRC: {ssrc}")
            
            # Extract video format requirements if available (f= line in GB28181)
            encoder_params = {}
            use_ps_format = False
            selected_pt = None  # payload type for H264/90000 if present
            
            # Scan SDP lines
            for line in sdp_content.split('\n'):
                line = line.strip()
                # Detect PS request
                if 'rtpmap:96 PS/' in line:
                    use_ps_format = True
                    log.info(f"[SIP] 🔧 Detected PS format requirement from SDP rtpmap")

                # Detect H264 payload type mapping
                if line.lower().startswith('a=rtpmap:') and 'h264/90000' in line.lower():
                    try:
                        selected_pt = line.split()[0].split(':')[1]
                    except Exception:
                        pass
            
            f_match = re.search(r"f=v/(\d+)/(\d+)", sdp_content)
            if f_match:
                codec_id = f_match.group(1)
                resolution_id = f_match.group(2)
                
                # Map GB28181 codec IDs to GStreamer encoder parameters
                if codec_id == "1":  # MPEG-4
                    encoder_params["codec"] = "mpeg4"
                    encoder_params["profile"] = "simple"
                elif codec_id == "2":  # H.264
                    encoder_params["codec"] = "h264"
                    encoder_params["profile"] = "baseline"
                elif codec_id == "3":  # H.265
                    encoder_params["codec"] = "h265"
                    encoder_params["profile"] = "main"
                    
                # Map GB28181 resolution IDs to actual resolutions
                if resolution_id == "1":  # QCIF
                    encoder_params["width"] = 176
                    encoder_params["height"] = 144
                elif resolution_id == "2":  # CIF
                    encoder_params["width"] = 352
                    encoder_params["height"] = 288
                elif resolution_id == "3":  # 4CIF
                    encoder_params["width"] = 704
                    encoder_params["height"] = 576
                elif resolution_id == "4":  # D1
                    encoder_params["width"] = 720
                    encoder_params["height"] = 576
                elif resolution_id == "5":  # 720P
                    encoder_params["width"] = 1280
                    encoder_params["height"] = 720
                elif resolution_id == "6":  # 1080P
                    encoder_params["width"] = 1920
                    encoder_params["height"] = 1080
                    
                log.info(f"[SIP] Video format request: codec={encoder_params.get('codec', 'h264')}, " +
                             f"resolution={encoder_params.get('width', '?')}x{encoder_params.get('height', '?')}")
            
            # Pass the detected payload type down to the media streamer so the payloader uses the same PT
            if selected_pt and selected_pt.isdigit():
                encoder_params['payload_type'] = int(selected_pt)

            # Set PS format flag for GB28181 compatibility
            if use_ps_format:
                encoder_params["use_ps_format"] = True
                log.info(f"[SIP] 🔧 Enabling PS format for GB28181 compatibility")
            
            # Select video source based on target channel
            video_source = None
            
            # If a specific channel/device was targeted
            if target_channel and self.catalog_ready:
                # Check if this is a known channel ID in our catalog
                if target_channel in self.device_catalog:
                    # **FIX:** Use .get() for safer access and handle both video_path and rtsp_url
                    video_source = self.device_catalog[target_channel].get("video_path")
                    if not video_source:
                        video_source = self.device_catalog[target_channel].get("rtsp_url")
                    
                    if video_source:
                        log.info(f"[SIP] Using channel-specific video source: {video_source}")
                    else:
                        log.warning(f"[SIP] Channel {target_channel} found in catalog but has no playable source (video_path/rtsp_url).")
                elif target_channel == self.device_id:
                    # If requesting the main device ID, use first available video
                    if self.device_catalog:
                        # **FIX:** Iterate to find first available video_path or rtsp_url
                        for ch_id, ch_info in self.device_catalog.items():
                            video_source = ch_info.get("video_path")
                            if not video_source:
                                video_source = ch_info.get("rtsp_url")
                            if video_source:
                                log.info(f"[SIP] Using first available video from catalog: {video_source}")
                                break
                    if not video_source:
                        log.warning("[SIP] Main device ID requested but no playable sources found in catalog.")
            
            # If still no video source, select first available one from a fresh scan
            if not video_source:
                log.info("[SIP] Falling back to scanning video files for a source.")
                catalog = get_video_catalog()
                if catalog:
                    video_source = catalog[0]
                    log.info(f"[SIP] Using first available video file: {video_source}")
                else:
                    log.error("[SIP] No video files available to stream.")
                    # Also check for RTSP sources from config as a last resort
                    rtsp_sources = self.config.get('rtsp_sources', [])
                    if rtsp_sources:
                        video_source = rtsp_sources[0]
                        log.info(f"[SIP] Using first configured RTSP source: {video_source}")
                    else:
                        log.error("[SIP] No RTSP sources configured either. Cannot start stream.")
                        return False
                
            # Start the stream using our Media Streamer with transport protocol
            success = self.streamer.start_stream(
                video_path=video_source,
                dest_ip=ip,
                dest_port=port,
                ssrc=ssrc,
                encoder_params=encoder_params,
                transport_protocol=transport_protocol
            )
            
            if success:
                # Record this stream in active streams
                stream_info = {
                    "dest_ip": ip,
                    "dest_port": port,
                    "ssrc": ssrc,
                    "video_path": video_source, # Storing the actual source used
                    "start_time": time.time(),
                    "status": "active",
                    "encoder_params": encoder_params,
                    "transport_protocol": transport_protocol
                }
                
                if callid:
                    self.active_streams[callid] = stream_info
                else:
                    # Generate a unique stream ID if no callid
                    stream_id = f"{ip}:{port}:{ssrc}"
                    self.active_streams[stream_id] = stream_info
                
                # Schedule a media status update
                self._schedule_media_status_update(callid if callid else stream_id)
                
                log.info(f"[SIP] Started stream to {ip}:{port} with SSRC {ssrc}")
                return True
            else:
                log.error("[SIP] Failed to start stream")
                return False
                
        except Exception as e:
            log.error(f"[SIP] Error in parse_sdp_and_stream: {e}")
            return False

    def _send_media_status_update(self, stream_id):
        """Send media status update with enhanced monitoring
        
        This method provides detailed status updates about active streams,
        including health metrics and error recovery information.
        """
        try:
            if stream_id not in self.active_streams:
                log.warning(f"[SIP] Cannot update status for unknown stream: {stream_id}")
                return
                
            stream_info = self.active_streams[stream_id]
            
            # Get detailed stream status from media streamer
            stream_status = self.streamer.get_stream_status(stream_id)
            if not stream_status:
                log.warning(f"[SIP] Could not get stream status for {stream_id}")
                return
                
            # Calculate stream metrics
            now = time.time()
            duration = now - stream_info["start_time"]
            
            # Combine all status information
            status_data = {
                **stream_info,
                "stream_id": stream_id,
                "status": "active",
                "duration": duration,
                "stream_status": stream_status,
                "last_update": now,
                "health": {
                    "fps": stream_status.get("fps", 0),
                    "bitrate": stream_status.get("bitrate", 0),
                    "packet_loss": stream_status.get("packet_loss", 0),
                    "jitter": stream_status.get("jitter", 0)
                }
            }
            
            # Check stream health metrics
            health_issues = []
            
            if status_data["health"]["fps"] < 10:
                health_issues.append("Low FPS")
            if status_data["health"]["packet_loss"] > 5:
                health_issues.append("High packet loss")
            if status_data["health"]["jitter"] > 50:
                health_issues.append("High jitter")
                
            if health_issues:
                log.warning(f"[SIP] Stream {stream_id} health issues: {', '.join(health_issues)}")
                status_data["health_issues"] = health_issues
                
                # Attempt recovery if needed
                if len(health_issues) >= 2:
                    self._attempt_stream_recovery(stream_id, status_data)
            
            # Format XML message for media status
            xml_msg = format_media_status_response(self.device_id, status_data)
            
            # Send the XML message via the SIP sender
            self.sip_sender.send_media_status(xml_msg)
            
            # Update stream info with latest status
            self.active_streams[stream_id].update({
                "last_status": status_data,
                "last_update": now
            })
            
            log.debug(f"[SIP] Sent media status update for {stream_id}")
            
        except Exception as e:
            log.error(f"[SIP] Error sending media status update: {e}")
            
    def _attempt_stream_recovery(self, stream_id, status_data):
        """Attempt to recover a problematic stream"""
        try:
            log.info(f"[SIP] Attempting recovery for stream {stream_id}")
            
            # Get current stream info
            stream_info = self.active_streams[stream_id]
            
            # Check if we've attempted recovery recently
            now = time.time()
            if stream_info.get("last_recovery", 0) > now - 60:
                log.info("[SIP] Recovery attempted too recently, skipping")
                return
                
            # Stop the current stream
            self.streamer.stop_stream(stream_id)
            
            # Wait briefly
            time.sleep(2)
            
            # Attempt to restart with original parameters
            success = self.streamer.start_stream(
                video_path=stream_info["video_path"], # This should still be accurate as set in parse_sdp_and_stream
                dest_ip=stream_info["dest_ip"],
                dest_port=stream_info["dest_port"],
                ssrc=stream_info["ssrc"],
                encoder_params=stream_info.get("encoder_params", {}),
                transport_protocol=stream_info.get("transport_protocol", "UDP")
            )
            
            if success:
                log.info(f"[SIP] Successfully recovered stream {stream_id}")
                # Update recovery timestamp
                self.active_streams[stream_id]["last_recovery"] = now
            else:
                log.error(f"[SIP] Failed to recover stream {stream_id}")
                # Mark stream as failed
                self.active_streams[stream_id]["status"] = "failed"
                
        except Exception as e:
            log.error(f"[SIP] Error during stream recovery: {e}")
            
    def handle_catalog_query(self, msg_text):
        """Handle catalog query according to GB28181 protocol with thread safety"""
        # FIXED: Thread-safe message processing to prevent race conditions
        with self._message_processing_lock:
            try:
                log.info("[SIP] 🔍 Processing catalog query from platform (thread-safe)")
                
                # Extract XML from the message - improved to handle both with and without XML prolog
                xml_match = re.search(r'(<\?xml.*?<\/Query>)', msg_text, re.DOTALL)
                if not xml_match:
                    xml_match = re.search(r'(<Query.*?<\/Query>)', msg_text, re.DOTALL)
                if not xml_match:
                    log.error("[SIP] ❌ Failed to extract <Query>…</Query> block from Catalog message")
                    log.debug(f"[SIP] Message content preview: {msg_text[:300]}...")
                    return None
                    
                xml_content = xml_match.group(1)
                
                if not xml_content.strip().startswith('<?xml'):
                    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content
                    
                log.debug(f"[SIP] Extracted raw Catalog XML: {xml_content[:200]}...")
                
                if not re.search(r'<CmdType>\s*Catalog\s*</CmdType>', xml_content, re.IGNORECASE):
                    log.debug("[SIP] Not a catalog query, ignoring")
                    return None
                    
                sn_match = re.search(r'<SN>(\d+)</SN>', xml_content)
                if not sn_match:
                    log.warning("[SIP] No SN found in catalog query")
                    return None
                    
                sn = sn_match.group(1)
                log.info(f"✅ Valid catalog query confirmed (SN: {sn}), processing...")
                
                # IMPROVED: Check catalog status before rate limiting
                log.info(f"[SIP] 📊 Catalog status before response generation:")
                log.info(f"[SIP]   • Catalog ready: {self.catalog_ready}")
                log.info(f"[SIP]   • Device catalog size: {len(self.device_catalog) if hasattr(self, 'device_catalog') else 'N/A'}")
                
                # FIXED: Simplified rate limiting that won't cause issues
                current_time = time.time()
                if hasattr(self, '_last_catalog_time'):
                    time_diff = current_time - self._last_catalog_time
                    if time_diff < 0.5:  # Minimal rate limiting (0.5 seconds)
                        log.debug(f"[SIP] ⏱️ Rate limiting: brief delay")
                        time.sleep(0.1)  # Very short delay
                else:
                    self._last_catalog_time = 0
                
                self._last_catalog_time = current_time
                
                # CRITICAL: Ensure catalog is available before generation
                if not hasattr(self, 'device_catalog') or not self.device_catalog:
                    log.warning("[SIP] ⚠️ Device catalog is empty - triggering immediate regeneration")
                    try:
                        self.generate_device_catalog()
                        log.info(f"[SIP] ✅ Emergency catalog regeneration complete: {len(self.device_catalog)} channels")
                    except Exception as catalog_error:
                        log.error(f"[SIP] ❌ Emergency catalog regeneration failed: {catalog_error}")
                
                # Generate full catalog response
                log.info(f"[SIP] 🏗️ Generating catalog response for SN: {sn}")
                response_xml = self._generate_catalog_response(sn)
                
                if response_xml:
                    # Verify response has content
                    item_count = len(re.findall(r'<Item>', response_xml))
                    log.info(f"[SIP] 📂 Generated catalog response: {len(response_xml)} bytes, {item_count} items")
                    
                    if item_count == 0:
                        log.error(f"[SIP] ❌ CRITICAL: Generated response has no items!")
                        log.error(f"[SIP] Device catalog size: {len(self.device_catalog)}")
                        log.debug(f"[SIP] Response preview: {response_xml[:500]}...")
                else:
                    log.error(f"[SIP] ❌ Failed to generate catalog response")

                # Save response to file for debugging
                try:
                    debug_filename = f"catalog_response_sn_{sn}.xml"
                    with open(debug_filename, "w", encoding="utf-8") as f:
                        f.write(response_xml if response_xml else "NO_RESPONSE_GENERATED")
                    log.debug(f"[SIP] 💾 Saved response to {debug_filename}")
                except Exception as e:
                    log.warning(f"[SIP] Could not save debug file: {e}")
                
                # Clean up pending queries (remove old entries) - simplified
                if hasattr(self, '_pending_catalog_queries'):
                    try:
                        current_time = time.time()
                        expired_queries = [sn for sn, timestamp in self._pending_catalog_queries.items() 
                                         if current_time - timestamp > 30]  # 30-second expiry
                        for expired_sn in expired_queries:
                            del self._pending_catalog_queries[expired_sn]
                    except Exception as cleanup_error:
                        log.debug(f"[SIP] Minor error during cleanup: {cleanup_error}")
                
                return response_xml
                
            except Exception as e:
                log.error(f"[SIP] ❌ CRITICAL ERROR in catalog query handling: {e}")
                import traceback
                log.error(f"[SIP] Full traceback: {traceback.format_exc()}")
                
                # Try to extract SN for error response
                try:
                    sn = re.search(r'<SN>(\d+)</SN>', msg_text).group(1) if re.search(r'<SN>(\d+)</SN>', msg_text) else "0"
                except:
                    sn = "0"
                
                log.error(f"[SIP] 🚨 Returning emergency error response for SN: {sn}")
                
                # Return a minimal valid response with error status to prevent platform timeout
                error_response_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>Error</Result>
  <SumNum>0</SumNum>
  <DeviceList Num="0">
  </DeviceList>
</Response>"""
                log.error(f"[SIP] Emergency response size: {len(error_response_xml)} bytes")
                return error_response_xml

    def _generate_catalog_response(self, sn):
        """Generate catalog response XML for given SN using thread-safe cached catalog"""
        try:
            # FIXED: Use the thread-safe cached device catalog instead of re-scanning
            with self._catalog_generation_lock:
                # Ensure catalog is ready and up-to-date
                if not self.catalog_ready or not self.device_catalog:
                    log.warning("[SIP] Device catalog not ready, generating on-demand...")
                    self.generate_device_catalog()
                
                # Use the cached catalog
                catalog_items = list(self.device_catalog.items())
                
            log.info(f"[SIP] Using cached catalog with {len(catalog_items)} video channels")
            
            # Build XML items for COMPLETE CATALOG FORMAT (parent device + channels)
            # CRITICAL FIX: WVP platform requires the parent device as first item, then channels
            xml_items = []
            
            # STEP 1: Add the parent device as the first item (required by WVP)
            parent_device_xml = f"""    <Item>
      <DeviceID>{self.device_id}</DeviceID>
      <Name>GB28181-Restreamer</Name>
      <Manufacturer>GB28181-RestreamerProject</Manufacturer>
      <Model>Restreamer-1.0</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>{self.device_id[:6]}</CivilCode>
      <Block>{self.device_id[:8]}</Block>
      <Address>gb28181-restreamer</Address>
      <Parental>0</Parental>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <CertNum>1234567890</CertNum>
      <Certifiable>1</Certifiable>
      <ErrCode>0</ErrCode>
      <EndTime></EndTime>
      <Secrecy>0</Secrecy>
      <IPAddress>{self.local_ip}</IPAddress>
      <Port>{self.local_port}</Port>
      <Password></Password>
      <Status>ON</Status>
      <Longitude>0.0</Longitude>
      <Latitude>0.0</Latitude>
      <PTZType>0</PTZType>
      <PositionType>0</PositionType>
      <RoomType>0</RoomType>
      <UseType>0</UseType>
      <SupplyLightType>0</SupplyLightType>
      <DirectionType>0</DirectionType>
      <Resolution>640*480</Resolution>
      <BusinessGroupID></BusinessGroupID>
      <DownloadSpeed></DownloadSpeed>
      <SVCSpaceSupportMode>0</SVCSpaceSupportMode>
      <SVCTimeSupportMode>0</SVCTimeSupportMode>
    </Item>"""
            xml_items.append(parent_device_xml)
            
            # STEP 2: Add video channels as child items with Parental=1
            for channel_id, channel_info in catalog_items:
                # Use compact format for UDP efficiency while maintaining WVP compatibility
                channel_item_xml = f"""    <Item>
      <DeviceID>{channel_id}</DeviceID>
      <Name>{channel_info['name']}</Name>
      <Manufacturer>GB28181-RestreamerProject</Manufacturer>
      <Model>Virtual-Channel</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>{self.device_id[:6]}</CivilCode>
      <Block>{self.device_id[:8]}</Block>
      <Address>Channel {channel_info['name']}</Address>
      <Parental>1</Parental>
      <ParentID>{self.device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <IPAddress></IPAddress>
      <Port>0</Port>
      <Password></Password>
      <Status>{channel_info['status']}</Status>
    </Item>"""
                xml_items.append(channel_item_xml)

            # Total count includes parent device + channels
            total_count = len(xml_items)  # 1 parent + N channels
            
            # FIXED: Check message size for UDP safety with proper newlines
            xml_content = "\n".join(xml_items)  # FIXED: Use actual newlines, not \\n
            estimated_size = len(xml_content) + 1000  # Add overhead for headers
            
            log.info(f"[SIP] 🏗️ Building WVP-compatible catalog response:")
            log.info(f"[SIP]   • Parent Device: {self.device_id} (GB28181-Restreamer)")
            log.info(f"[SIP]   • Child Channels: {len(catalog_items)}")
            log.info(f"[SIP]   • Total Items: {total_count}")
            log.info(f"[SIP]   • Estimated size: {estimated_size} bytes")
            
            # FIXED: Apply reasonable UDP size limits but less aggressive for parent+children format
            if estimated_size > 3000:  # Higher limit since we need parent + at least some channels
                log.warning(f"[SIP] ⚠️ Large response ({estimated_size} bytes) - limiting channels for UDP safety")
                
                # Always keep the parent device (first item), limit channels
                safe_items = [xml_items[0]]  # Parent device must be included
                running_size = len(xml_items[0].encode('utf-8')) + 800  # Base response size + headers
                
                # Add as many channels as fit within UDP limit
                for channel_item in xml_items[1:]:  # Skip parent device (already added)
                    item_size = len(channel_item.encode('utf-8'))
                    if running_size + item_size < 3000:  # Allow more space for this format
                        safe_items.append(channel_item)
                        running_size += item_size
                    else:
                        break
                
                xml_content = "\n".join(safe_items)
                actual_count = len(safe_items)
                channel_count = actual_count - 1  # Subtract parent device
                log.info(f"[SIP] 📦 Limited to parent device + {channel_count} channels (total: {actual_count} items)")
            else:
                safe_items = xml_items
                actual_count = total_count
                channel_count = len(catalog_items)
                log.info(f"[SIP] 📦 Including parent device + all {channel_count} channels (total: {actual_count} items)")

            # FIXED: Generate the XML response with proper WVP-compatible format
            xml_response = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>Catalog</CmdType>
<SN>{sn}</SN>
<DeviceID>{self.device_id}</DeviceID>
<Result>OK</Result>
<SumNum>{actual_count}</SumNum>
<DeviceList Num="{actual_count}">
{xml_content}
</DeviceList>
</Response>"""

            # Validate the response structure
            message_size = len(xml_response.encode('utf-8'))
            log.info(f"[SIP] 📊 Final WVP-compatible catalog response:")
            log.info(f"[SIP]   • Message size: {message_size} bytes")
            log.info(f"[SIP]   • SumNum: {actual_count}")
            log.info(f"[SIP]   • DeviceList Num: {actual_count}")
            log.info(f"[SIP]   • Structure: 1 Parent Device + {actual_count-1} Channels")
            
            # FIXED: Final size check with better fallback - ensure at least parent + 1 channel
            if message_size > 4000:  # Higher threshold for parent+children format
                log.error(f"[SIP] ❌ Response still too large ({message_size} bytes) - using minimal fallback")
                # Emergency fallback: Parent device + 1 channel only
                minimal_items = [xml_items[0]]  # Parent device
                if len(xml_items) > 1:
                    minimal_items.append(xml_items[1])  # First channel
                
                minimal_xml = "\n".join(minimal_items)
                xml_response = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>Catalog</CmdType>
<SN>{sn}</SN>
<DeviceID>{self.device_id}</DeviceID>
<r>OK</r>
<SumNum>{len(minimal_items)}</SumNum>
<DeviceList Num="{len(minimal_items)}">
{minimal_xml}
</DeviceList>
</Response>"""
                log.info(f"[SIP] 📦 Emergency fallback: parent device + 1 channel, {len(xml_response.encode('utf-8'))} bytes")

            return xml_response

        except Exception as e:
            log.error(f"[SIP] Error generating catalog response: {e}")
            # FIXED: Return minimal valid response with parent device
            return f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>Catalog</CmdType>
<SN>{sn}</SN>
<DeviceID>{self.device_id}</DeviceID>
<Result>OK</Result>
<SumNum>1</SumNum>
<DeviceList Num="1">
    <Item>
      <DeviceID>{self.device_id}</DeviceID>
      <Name>GB28181-Restreamer</Name>
      <Manufacturer>GB28181-RestreamerProject</Manufacturer>
      <Model>Restreamer-1.0</Model>
      <Status>ON</Status>
      <Parental>0</Parental>
    </Item>
</DeviceList>
</Response>"""

    def handle_device_info_query(self, msg_text):
        """Handle device info query according to GB28181 protocol"""
        log.info("[SIP] Received device info query")
        
        # Extract SN from the query for proper response
        sn_match = re.search(r'<SN>(\d+)</SN>', msg_text)
        sn = sn_match.group(1) if sn_match else "0"
        
        # Prepare device info response XML
        device_info_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
<CmdType>DeviceInfo</CmdType>
<SN>{sn}</SN>
<DeviceID>{self.device_id}</DeviceID>
<Result>OK</Result>
<DeviceName>GB28181-Restreamer</DeviceName>
<Manufacturer>GB28181-RestreamerProject</Manufacturer>
<Model>Restreamer-1.0</Model>
<Firmware>1.0.0</Firmware>
<MaxCamera>{len(get_video_catalog()) if get_video_catalog() else 0}</MaxCamera>
<MaxAlarm>0</MaxAlarm>
</Response>"""
        
        log.info(f"[SIP] Generated DeviceInfo response for SN: {sn}")
        return device_info_xml

    def handle_device_control(self, msg_text):
        """Handle device control commands according to GB28181 protocol"""
        # Example control commands include PTZ control, recording control, etc.
        if "PTZ" in msg_text:
            log.info("[SIP] Received PTZ control command (not supported)")
            # Would send appropriate response for unsupported command
        elif "RECORD" in msg_text:
            log.info("[SIP] Received recording control command (not supported)")
            # Would send appropriate response for unsupported command
        else:
            log.info("[SIP] Received unknown control command")
            # Would send appropriate response
            
    def handle_recordinfo_query(self, msg_text):
        """Handle record info query from platform"""
        try:
            query_info = parse_recordinfo_query(msg_text)
            log.info(f"[SIP] RecordInfo query received: {query_info}")
            
            if not query_info:
                log.error("[SIP] Failed to parse record info query")
                return None
                
            device_id = query_info.get("device_id")
            start_time = query_info.get("start_time")
            end_time = query_info.get("end_time")
            
            log.info(f"[SIP] Record info query for device {device_id} from {start_time} to {end_time}")
            
            # Get recording manager instance
            recording_manager = get_recording_manager(self.config)
            if not recording_manager:
                log.error("[SIP] Recording manager not initialized")
                recordings = []
            else:
                # Get recordings in the time range
                recordings = recording_manager.get_recordings_in_range(start_time, end_time)
                
            if not recordings:
                log.info("[SIP] No recordings found in the specified time range")
                recordings = []
                
            # Format response according to GB28181 standard
            response = format_recordinfo_response(
                device_id=device_id,
                records=recordings,
                sn=query_info.get("sn")
            )
            
            # Send response via SIP message
            if response:
                success = self.send_sip_message(response)
                if success:
                    log.info(f"[SIP] Sent record info response with {len(recordings)} recordings")
                else:
                    log.error("[SIP] Failed to send record info response")
            else:
                log.error("[SIP] Failed to format record info response")
                
        except Exception as e:
            log.error(f"[SIP] Error handling record info query: {e}")
            return None

    def handle_invite(self, msg_text):
        """Handle SIP INVITE message for stream requests"""
        try:
            # Extract Call-ID for tracking this stream
            callid_match = re.search(r"Call-ID:\s*(.+)", msg_text)
            if not callid_match:
                callid_match = re.search(r"i:\s*(.+)", msg_text)  # Short form header
                
            if not callid_match:
                log.warning("[SIP] Failed to extract Call-ID from INVITE message")
                return False
                
            callid = callid_match.group(1).strip()
            log.info(f"[SIP] Processing INVITE with Call-ID: {callid}")
            
            # Extract target channel from message if present - helps select the right video source
            target_channel = None
            channel_match = re.search(r"z:\s*(.+)", msg_text)
            if channel_match:
                target_channel = channel_match.group(1).strip()
                log.info(f"[SIP] INVITE targets channel: {target_channel}")
            
            # Check if this is a playback request with time parameters
            is_playback = False
            start_time = None
            end_time = None
            
            # Look for playback time parameters in the SDP
            playback_match = re.search(r"y=playback:(.+)", msg_text)
            if playback_match:
                playback_info = playback_match.group(1).strip()
                log.info(f"[SIP] Playback request detected: {playback_info}")
                is_playback = True
                
                # Check for time range parameters
                time_range_match = re.search(r"starttime=(\d+T\d+Z);endtime=(\d+T\d+Z)", msg_text)
                if time_range_match:
                    start_time = time_range_match.group(1).strip()
                    end_time = time_range_match.group(2).strip()
                    log.info(f"[SIP] Playback time range: {start_time} to {end_time}")
            
            # Handle the streaming differently based on whether it's a playback request
            if is_playback:
                # This is a historical playback request
                log.info("[SIP] Processing historical playback request")
                
                # Get the recording manager
                recording_manager = get_recording_manager(self.config)
                if not recording_manager:
                    log.error("[SIP] Recording manager not available for playback")
                    return False
                
                # Query for matching recordings
                matching_recordings = recording_manager.query_recordings(
                    device_id=target_channel,
                    start_time=start_time,
                    end_time=end_time
                )
                
                if not matching_recordings:
                    log.warning("[SIP] No matching recordings found for playback request")
                    return False
                
                # Use the first matching recording
                recording = matching_recordings[0]
                log.info(f"[SIP] Selected recording for playback: {recording['name']}")
                
                # Parse SDP to get destination IP/port
                success = self.parse_sdp_and_stream_recording(
                    sdp_text=msg_text,
                    callid=callid,
                    recording_info=recording,
                    start_time=start_time,
                    end_time=end_time
                )
                
                if success:
                    log.info(f"[SIP] Started playback stream for Call-ID: {callid}")
                else:
                    log.error(f"[SIP] Failed to start playback stream for Call-ID: {callid}")
                
                return success
            else:
                # This is a regular live streaming request
                return self.parse_sdp_and_stream(msg_text, callid, target_channel)
                
        except Exception as e:
            log.error(f"[SIP] Error handling INVITE: {e}")
            return False
            
    def parse_sdp_and_stream_recording(self, sdp_text, callid, recording_info, 
                                     start_time=None, end_time=None):
        """Parse SDP offer and start streaming a recording to the specified destination
        
        This method handles playback of recordings with time parameters.
        """
        try:
            # Extract SDP content
            sdp_content = self.extract_sdp_from_message(sdp_text)
            if not sdp_content:
                log.warning("[SIP] ⚠️ No SDP content found in message, cannot start playback")
                return False
                
            log.debug(f"[SIP] Parsed SDP content for playback: {sdp_content}")
                
            # Extract destination IP
            ip_match = re.search(r"c=IN IP4 (\d+\.\d+\.\d+\.\d+)", sdp_content)
            if not ip_match:
                log.warning("[SIP] ⚠️ Failed to extract IP address from SDP")
                ip = self.server
                log.info(f"[SIP] Using fallback IP: {ip}")
            else:
                ip = ip_match.group(1)
                
            # Extract port
            port_match = re.search(r"m=video (\d+)", sdp_content)
            if not port_match:
                log.warning("[SIP] ⚠️ Failed to extract port from SDP")
                port = 9000
                log.info(f"[SIP] Using fallback port: {port}")
            else:
                port = int(port_match.group(1))
            
            # Extract SSRC
            y_match = re.search(r"y=(\d+)", sdp_content)
            ssrc = y_match.group(1) if y_match else "0000000001"
            
            # Start playback of the recording
            success = self.streamer.start_recording_playback(
                recording_info=recording_info,
                dest_ip=ip,
                dest_port=port,
                start_timestamp=start_time,
                end_timestamp=end_time,
                ssrc=ssrc
            )
                
            if success:
                # Record this stream in active streams
                self.active_streams[callid] = {
                    "type": "playback",
                    "recording": recording_info,
                    "dest_ip": ip,
                    "dest_port": port,
                    "ssrc": ssrc,
                    "start_time": time.time(),
                    "status": "active"
                }
                
                # Set up a periodic status update for this stream
                self._schedule_media_status_update(callid)
                
                log.info(f"[SIP] Started playback stream to {ip}:{port}")
                return True
            else:
                log.error("[SIP] Failed to start playback stream")
                return False
                
        except Exception as e:
            log.error(f"[SIP] Error starting playback: {e}")
            return False

    def handle_keepalive(self, msg_text):
        """Handle keepalive messages according to GB28181 protocol"""
        log.info("[SIP] Received keepalive message")
        
        # Format XML response
        xml_response = format_keepalive_response(self.device_id)
        
        # Send keepalive response using the SIP sender
        self.sip_sender.send_keepalive(xml_response)

    def start(self):
        log.info("[SIP] 🚀 Launching GB28181 SIP client...")

        # Start the SIP sender
        self.sip_sender.start()

        # Generate device catalog on startup
        self.generate_device_catalog()

        cfg_path = "/tmp/pjsua.cfg"
        sip = self.config["sip"]

        # Enhanced transport selection
        transport = self._determine_transport()
        log.info(f"[SIP] Using transport: {transport}")

        # Enhanced local port configuration
        local_port_option = f"--local-port {self.local_port} " if hasattr(self, 'local_port') else ""
        
        # Effective SIP domain is the server itself, used for AOR, registrar, and realm
        effective_sip_domain = sip['server']

        # Define proxy using server address and port
        proxy_address = sip['server']
        proxy_port = sip['port']

        proxy_uri = f"sip:{proxy_address}:{proxy_port}"
        if transport == "tcp":
            log.info("[SIP] Configuring proxy with TCP transport.")
            proxy_uri += ";transport=tcp"
        elif transport == "tls": # Placeholder for future TLS support
            log.info("[SIP] Configuring proxy with TLS transport (if implemented).")
            proxy_uri += ";transport=tls"
        # UDP is implicit if no transport parameter is added to the proxy_uri

        # Detailed logging of SIP configuration
        log.info(f"[SIP] Device ID: {sip['device_id']}")
        log.info(f"[SIP] Username: {sip['username']}")
        log.info(f"[SIP] Server: {effective_sip_domain}")
        log.info(f"[SIP] Proxy: {proxy_uri}")
        log.info(f"[SIP] Local port: {self.local_port}")

        # Updated PJSUA configuration for WVP-pro compatibility
        with open(cfg_path, "w") as f:
            f.write(f"""--id sip:{sip['username']}@{effective_sip_domain}
--registrar sip:{effective_sip_domain}:{sip['port']}
--proxy {proxy_uri}
--realm *
--username {sip['username']}
--password {sip['password']}
{local_port_option}--null-audio
--duration 0
--log-level 5
--auto-update-nat=1
--reg-timeout=120
--rereg-delay=60
--max-calls=4
--thread-cnt=4
--rtp-port=10000
--dis-codec=speex/16000
--dis-codec=speex/8000
--dis-codec=iLBC
--add-codec=H264
--publish
--use-timer=2
--timer-min-se=90
--timer-se=1800
""")

        def listen_loop():
            restart_count = 0
            max_restarts = 3  # Limit restart attempts
            
            while restart_count < max_restarts:
                try:
                    log.info(f"[SIP] Starting pjsua process (attempt {restart_count + 1}/{max_restarts})")
                    self._start_pjsua_process(cfg_path)
                    self._handle_pjsua_output()
                    
                    # If we reach here, the process exited normally
                    log.warning("[SIP] pjsua process exited normally")
                    break
                    
                except Exception as e:
                    restart_count += 1
                    log.error(f"[SIP] Error in listen loop (attempt {restart_count}/{max_restarts}): {e}")
                    
                    if restart_count >= max_restarts:
                        log.error("[SIP] Maximum restart attempts reached, giving up")
                        self.running = False
                        break
                        
                    log.info(f"[SIP] Waiting 10 seconds before restart attempt {restart_count + 1}")
                    time.sleep(10)  # Longer wait between restarts
                    
            log.warning("[SIP] SIP client listen loop has ended")

        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()

        try:
            while True:
                time.sleep(1)
                self._check_registration()
                # REMOVED: _check_keepalive() - now handled by dedicated heartbeat thread
                self._check_streams()
        except KeyboardInterrupt:
            self.stop()

    def _determine_transport(self):
        """Determine which transport protocol to use"""
        # Always use UDP for WVP-pro as specified
        transport = self.config["sip"].get("transport", "udp").lower()
        if transport != "udp":
            log.warning("[SIP] WVP-pro requires UDP transport, overriding configured transport")
            transport = "udp"
        return transport

    def _start_pjsua_process(self, cfg_path):
        """Start the PJSUA process with the given configuration"""
        transport = self._determine_transport()
        
        # Kill any existing PJSUA processes
        self._kill_existing_pjsua_processes()
        
        # Create PJSUA configuration
        config = [
            "--id", f"sip:{self.username}@{self.server}",
            "--registrar", f"sip:{self.server}:{self.port}",
            "--realm", "*",
            "--username", self.username,
            "--password", self.password,
            "--local-port", str(self.local_port),
            "--log-level", "4",  # Increased log level to see MESSAGE content
            "--app-log-level", "4",
            "--log-file", "pjsua.log",
            "--auto-update-nat", "0",
            "--disable-stun",
            "--null-audio",
            "--duration", "0",  # No call duration limit
            "--max-calls", "4",  # Match the compiled limit
            "--thread-cnt", "4",  # Use default thread count
            "--capture-dev", "-1",  # Disable audio capture
            "--playback-dev", "-1",  # Disable audio playback
            "--reg-timeout", "120",  # FIXED: 2 minute registration timeout to match WVP platform expectations
            "--rereg-delay", "60",   # FIXED: Re-register every 60 seconds to prevent timeout
        ]
        
        # Set transport based on configuration
        if transport == "udp":
            config.append("--no-tcp")  # Only use UDP
        elif transport == "tcp":
            config.append("--no-udp")  # Only use TCP
        
        try:
            # Ensure any old process is properly terminated
            if hasattr(self, 'process') and self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except:
                    pass
            
            self.process = subprocess.Popen(
                ["pjsua"] + config,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,  # Enable stdin for interactive commands
                universal_newlines=True,
                bufsize=0,  # Unbuffered to get immediate output
                preexec_fn=os.setsid  # Create new process group
            )
            log.info(f"[SIP] Started PJSUA process with PID: {self.process.pid}")
            self.running = True
            
        except FileNotFoundError:
            log.error("[SIP] PJSUA not found. Please install pjsua.")
            raise
        except Exception as e:
            log.error(f"[SIP] Failed to start PJSUA: {e}")
            raise

    def _kill_existing_pjsua_processes(self):
        """Kill any existing pjsua processes that might be holding ports"""
        try:
            # Find all pjsua processes
            ps_process = subprocess.run(["ps", "-ef"], capture_output=True, text=True)
            lines = ps_process.stdout.split('\n')
            
            # Get the current process ID to avoid killing parent processes
            current_pid = os.getpid()
            
            for line in lines:
                if 'pjsua' in line and str(current_pid) not in line:
                    try:
                        # Extract PID
                        parts = line.split()
                        if len(parts) > 1:
                            pid = int(parts[1])
                            # Kill the process
                            log.info(f"[SIP] Killing existing pjsua process with PID {pid}")
                            os.kill(pid, signal.SIGKILL)
                    except Exception as e:
                        log.error(f"[SIP] Error killing pjsua process: {e}")
        except Exception as e:
            log.error(f"[SIP] Error checking for existing pjsua processes: {e}")

    def _handle_pjsua_output(self):
        """Handle PJSUA process output with improved error handling"""
        if not self.process:
            log.error("[SIP] No pjsua process to handle output from")
            return

        buffer = ""
        line_count = 0
        try:
            log.info("[SIP] 🔍 Starting PJSUA output monitoring...")
            for line in self.process.stdout:
                if not self.running:
                    break
                    
                line_count += 1
                print(line.strip())
                
                # Debug: Log every few lines to ensure we're receiving output
                if line_count % 50 == 0:
                    log.debug(f"[SIP] Processed {line_count} lines from PJSUA")
                
                # Extra debugging for MESSAGE-related lines
                if "MESSAGE" in line:
                    log.info(f"[SIP] 🔍 DEBUG: MESSAGE line detected: {line.strip()}")
                if "pjsua_app.c" in line:
                    log.debug(f"[SIP] 🔍 DEBUG: pjsua_app.c line: {line.strip()}")
                
                # Buffer the line for context
                buffer += line
                if len(buffer) > 10000:
                    buffer = buffer[-5000:]  # Keep last 5000 chars
                
                # Enhanced message handling with better error handling
                try:
                    self._process_sip_message(line, buffer)
                except Exception as e:
                    log.error(f"[SIP] Error processing SIP message: {e}")
                    # Don't crash the whole handler for a single message error
                    continue
                    
        except Exception as e:
            log.error(f"[SIP] Error in output handler: {e}")
        finally:
            log.info(f"[SIP] PJSUA output handler finished after processing {line_count} lines")
            self.running = False

    def _process_sip_message(self, line, buffer):
        """Process SIP messages with improved handling"""
        
        # Store SIP headers for OPTIONS responses
        if line.startswith("Via:"):
            self._last_via = line.strip()
        elif line.startswith("From:"):
            self._last_from = line.strip()
        elif line.startswith("To:"):
            self._last_to = line.strip()
        elif line.startswith("Call-ID:"):
            self._last_call_id = line.strip()
        elif line.startswith("CSeq:"):
            self._last_cseq = line.strip()
            
        # ───────────────────────────────────────────────────────────────────────
        # Immediately respond to any incoming OPTIONS so the server knows we're alive
        if "Request msg OPTIONS" in line or re.match(r'^OPTIONS\s', line):
            log.info("[SIP] Received OPTIONS → replying 200 OK to keep‐alive")
            # Build a simple 200 OK response
            ok_resp = (
                "SIP/2.0 200 OK\r\n"
                f"{self._last_via}\r\n"
                f"{self._last_from}\r\n"
                f"{self._last_to};tag={self._local_tag}\r\n"
                f"{self._last_call_id}\r\n"
                f"{self._last_cseq}\r\n"
                f"Contact: <sip:{self.local_ip}:{self.local_port}>\r\n"
                "Content-Length: 0\r\n"
                "\r\n"
            )
            
            # Send the response using our SIP sender
            sent = self.send_sip_message(ok_resp)
            if not sent:
                log.error("[SIP] Failed to send 200 OK for OPTIONS")
            else:
                log.info("[SIP] ✅ Sent 200 OK response to OPTIONS")
            return  # don't try to parse this as XML or anything else
        # ───────────────────────────────────────────────────────────────────────
        
        # Registration status handling
        if "Registration successfully sent" in line:
            log.info("[SIP] Registration request sent successfully")
            self.registration_status = "registering"
        elif "registration success" in line:
            log.info("[SIP] ✅ Registration completed successfully")
            self.registration_status = "registered"
            self.registration_attempts = 0
            # ADDED: Start heartbeat thread immediately after successful registration
            self._start_heartbeat_thread()
            # ADDED: Send immediate heartbeat to update keepaliveTime in WVP platform
            log.info("[SIP] 💓 Sending immediate heartbeat after registration to update WVP keepaliveTime")
            threading.Timer(2.0, self._send_keepalive).start()  # Send after 2 seconds
            
            # NEW FIX: Send proactive catalog notification to WVP platform for immediate frontend visibility
            log.info("[SIP] 🚀 Sending proactive catalog notification for immediate frontend visibility")
            threading.Timer(3.0, self._send_proactive_catalog_notification).start()  # Send after 3 seconds
        elif "Registration failed" in line:
            log.warning("[SIP] ⚠️ Registration failed")
            self.registration_status = "failed"
            # ADDED: Stop heartbeat thread if registration fails
            self._stop_heartbeat_thread()
            self._handle_registration_failure()
            
        # Handle Route header warnings that cause offline issues
        if "sip: unkonw message head Route" in line or "sip: unknown message head Route" in line:
            log.warning("[SIP] ⚠️ Route header detected - this is normal for some GB28181 implementations")
            log.info("[SIP] Route headers are used for SIP routing and should not cause registration failures")
            # Don't treat this as an error - continue processing
            return
        
        # ═══════════════════════════════════════════════════════════════════════
        # IMPROVED APPROACH: Direct PJSUA XML capture with better multi-line handling
        # ═══════════════════════════════════════════════════════════════════════
        
        # Detect PJSUA MESSAGE lines - XML will appear in subsequent lines
        # Updated to match actual PJSUA output format
        if ("pjsua_core.c" in line and "Request msg MESSAGE" in line) or \
           ("pjsua_app.c" in line and ".MESSAGE from" in line):
            log.info(f"[SIP] 🎯 Direct PJSUA XML capture - detected MESSAGE line: {line.strip()}")
            
            # Initialize XML collection for subsequent lines
            self._pjsua_xml_lines = []
            self._collecting_pjsua_xml = True
            self._non_xml_line_count = 0  # Reset counter
            
            # Check if XML starts on this same line (rare but possible)
            xml_start_pos = -1
            for xml_marker in ["<?xml", "<Query>", "<Response>", "<Control>"]:
                pos = line.find(xml_marker)
                if pos != -1:
                    xml_start_pos = pos
                    break
            
            if xml_start_pos != -1:
                xml_content = line[xml_start_pos:].strip()
                self._pjsua_xml_lines.append(xml_content)
                log.debug(f"[SIP] 📝 Found XML on MESSAGE line: {xml_content}")
            
            return
        
        # Continue collecting PJSUA XML content if we're in collection mode
        if hasattr(self, '_collecting_pjsua_xml') and self._collecting_pjsua_xml:
            stripped_line = line.strip()
            
            # Skip empty lines and PJSUA metadata lines (but not --end msg--)
            if not stripped_line or ("pjsua_" in stripped_line and "MESSAGE" not in stripped_line and "--end msg--" not in stripped_line) or \
               (".TX " in stripped_line) or (".RX " in stripped_line and "MESSAGE" not in stripped_line):
                return
            
            # Check for XML content patterns
            is_xml_line = False
            
            # Method 1: Line starts with XML declaration or tag
            if stripped_line.startswith('<?xml') or stripped_line.startswith('<'):
                is_xml_line = True
            
            # Method 2: Line contains XML tags  
            elif any(tag in stripped_line for tag in ['<CmdType>', '<SN>', '<DeviceID>', '<Query>', '<Response>', '<Control>', '</Query>', '</Response>', '</Control>']):
                is_xml_line = True
            
            # Method 3: Check for --end msg-- which indicates end of PJSUA message block
            elif "--end msg--" in stripped_line:
                # End of PJSUA message block, process collected XML if any
                if self._pjsua_xml_lines:
                    complete_xml = '\n'.join(self._pjsua_xml_lines)
                    log.info(f"[SIP] ✅ PJSUA XML collection complete (end msg): {len(complete_xml)} characters")
                    log.debug(f"[SIP] Complete XML: {complete_xml}")
                    self._process_xml_content(complete_xml)
                else:
                    log.warning("[SIP] ⚠️ No XML collected before end msg")
                
                # Reset collection
                self._collecting_pjsua_xml = False
                self._pjsua_xml_lines = []
                return
            
            # ENHANCED DEBUG: Log what we're processing
            log.debug(f"[SIP] 🔍 XML line analysis: '{stripped_line}' - is_xml: {is_xml_line}")
            
            if is_xml_line:
                self._pjsua_xml_lines.append(stripped_line)
                log.debug(f"[SIP] 📝 Added XML line ({len(self._pjsua_xml_lines)} total): {stripped_line}")
                
                # Check if this line completes the XML
                if stripped_line.endswith('</Query>') or stripped_line.endswith('</Response>') or stripped_line.endswith('</Control>'):
                    # XML is complete, process it immediately
                    complete_xml = '\n'.join(self._pjsua_xml_lines)
                    log.info(f"[SIP] ✅ PJSUA XML collection complete (end tag): {len(complete_xml)} characters")
                    log.debug(f"[SIP] Complete XML: {complete_xml}")
                    
                    # Process the complete XML
                    self._process_xml_content(complete_xml)
                    
                    # Reset collection
                    self._collecting_pjsua_xml = False
                    self._pjsua_xml_lines = []
                    
                    return
                    
                # Also check if we have a complete Query even without proper end tag
                elif len(self._pjsua_xml_lines) >= 5 and any('</Query>' in line for line in self._pjsua_xml_lines):
                    # We have enough lines and there's an end tag somewhere
                    complete_xml = '\n'.join(self._pjsua_xml_lines)
                    log.info(f"[SIP] ✅ PJSUA XML collection complete (found end in lines): {len(complete_xml)} characters")
                    log.debug(f"[SIP] Complete XML: {complete_xml}")
                    
                    # Process the complete XML
                    self._process_xml_content(complete_xml)
                    
                    # Reset collection
                    self._collecting_pjsua_xml = False
                    self._pjsua_xml_lines = []
                    
                    return
                    
                # Force completion if we have enough XML content for a basic query
                elif len(self._pjsua_xml_lines) >= 5:
                    # Check if we have the essential elements for a catalog query
                    xml_text = '\n'.join(self._pjsua_xml_lines)
                    if all(element in xml_text for element in ['<Query>', '<CmdType>Catalog', '<SN>', '<DeviceID>']):
                        # Force add closing tag if missing
                        if '</Query>' not in xml_text:
                            self._pjsua_xml_lines.append('</Query>')
                            xml_text = '\n'.join(self._pjsua_xml_lines)
                        
                        log.info(f"[SIP] ✅ PJSUA XML collection complete (forced): {len(xml_text)} characters")
                        log.debug(f"[SIP] Complete XML: {xml_text}")
                        
                        # Process the complete XML
                        self._process_xml_content(xml_text)
                        
                        # Reset collection
                        self._collecting_pjsua_xml = False
                        self._pjsua_xml_lines = []
                        
                        return
            else:
                # Non-XML line encountered - log what we're skipping
                log.debug(f"[SIP] 🚫 Skipping non-XML line: '{stripped_line}'")
                
                # If we have incomplete XML, continue collecting a bit more
                # But if we hit multiple non-XML lines, stop collecting
                if not hasattr(self, '_non_xml_line_count'):
                    self._non_xml_line_count = 0
                
                self._non_xml_line_count += 1
                
                if self._non_xml_line_count > 10:  # FIXED: Increased from 3 to 10 to allow for SIP headers
                    # Too many non-XML lines, check if we have valid XML to process
                    if self._pjsua_xml_lines:
                        xml_text = '\n'.join(self._pjsua_xml_lines)
                        
                        # Check if we have enough for a basic query
                        if all(element in xml_text for element in ['<Query>', '<CmdType>', '<SN>', '<DeviceID>']):
                            # Force add closing tag if missing
                            if '</Query>' not in xml_text:
                                self._pjsua_xml_lines.append('</Query>')
                                xml_text = '\n'.join(self._pjsua_xml_lines)
                            
                            log.info(f"[SIP] ✅ PJSUA XML collection finished (non-XML limit): {len(xml_text)} characters")
                            log.debug(f"[SIP] Complete XML: {xml_text}")
                            self._process_xml_content(xml_text)
                        else:
                            log.warning(f"[SIP] ⚠️ XML collection abandoned - incomplete: {xml_text[:100]}...")
                    else:
                        log.warning("[SIP] ⚠️ XML collection abandoned - no XML collected")
                    
                    # Reset collection
                    self._collecting_pjsua_xml = False
                    self._pjsua_xml_lines = []
                    self._non_xml_line_count = 0
            
            return
            
        # ═══════════════════════════════════════════════════════════════════════
        # FALLBACK: Keep the original message collection logic as backup
        # ═══════════════════════════════════════════════════════════════════════
        
        # Handle incoming MESSAGE requests - only process complete messages
        if "MESSAGE sip:" in line and "SIP/2.0" in line:
            log.info(f"[SIP] Incoming MESSAGE detected: {line.strip()}")
            # Start collecting the complete message
            self._current_message_buffer = [line]
            self._collecting_message = True
            return
            
        # Continue collecting message lines
        if hasattr(self, '_collecting_message') and self._collecting_message:
            self._current_message_buffer.append(line)
            
            # Improved message completion detection
            # Check for multiple completion indicators
            message_complete = False
            
            # Method 1: Look for --end msg-- marker (most reliable)
            if "--end msg--" in line:
                message_complete = True
                log.debug("[SIP] Message complete: Found --end msg-- marker")
                
            # Method 2: Look for XML end tags which indicate complete XML content
            elif "</Query>" in line or "</Response>" in line or "</Control>" in line:
                message_complete = True
                log.debug(f"[SIP] Message complete: Found XML end tag in line: {line.strip()}")
                
            # Method 3: Check Content-Length compliance after we have enough content
            elif line.strip() == "" and len(self._current_message_buffer) > 10:
                # Only check content length if we have a substantial message
                complete_message_preview = "\n".join(self._current_message_buffer)
                content_length_match = re.search(r'Content-Length:\s*(\d+)', complete_message_preview, re.IGNORECASE)
                if content_length_match:
                    expected_length = int(content_length_match.group(1))
                    # Find where headers end
                    if '\r\n\r\n' in complete_message_preview:
                        body_start = complete_message_preview.find('\r\n\r\n') + 4
                    elif '\n\n' in complete_message_preview:
                        body_start = complete_message_preview.find('\n\n') + 2
                    else:
                        body_start = len(complete_message_preview)
                    
                    actual_body_length = len(complete_message_preview) - body_start
                    if actual_body_length >= expected_length:
                        message_complete = True
                        log.debug(f"[SIP] Message complete: Content-Length satisfied ({actual_body_length}/{expected_length})")
            
            # Continue collecting if not complete
            if not message_complete:
                return
            
            # Process the complete message (FALLBACK ONLY)
            complete_message = "\n".join(self._current_message_buffer)
            self._collecting_message = False
            
            log.debug(f"[SIP] 🔙 FALLBACK: Processing complete message ({len(complete_message)} bytes)")
            
            # Try to extract XML using the old method as fallback
            xml_content = self._extract_xml_from_message(complete_message)
            if xml_content:
                log.info("[SIP] ✅ FALLBACK: Successfully extracted XML from message buffer")
                self._process_xml_content(xml_content)
            else:
                log.warning("[SIP] ⚠️ FALLBACK: No XML content found in message buffer")
            
            # Clear the buffer for next message
            self._current_message_buffer = []
            return
            
        # Enhanced INVITE detection for GB28181 streaming
        if "Request msg INVITE" in line:
            log.info("[SIP] 🎬 INVITE detected in log line, processing buffer for full message.")
            # IMPROVED: Start INVITE collection with timeout tracking
            self._collecting_invite = True
            self._invite_buffer = []
            self._invite_collection_start = time.time()
            log.info("[SIP] ⏰ Started INVITE collection with 5-second timeout protection")
            return
            
        # Continue collecting INVITE message content
        if hasattr(self, '_collecting_invite') and self._collecting_invite:
            # IMPROVED: Enable INVITE collection with timeout protection
            current_time = time.time()
            collection_start_time = getattr(self, '_invite_collection_start', current_time)
            
            # Timeout protection: abort collection after 5 seconds
            if current_time - collection_start_time > 5:
                log.error("[SIP] ⏰ INVITE collection timeout - aborting to prevent infinite loop")
                self._collecting_invite = False
                delattr(self, '_invite_collection_start')
                return
                
            stripped_line = line.strip()
            log.debug(f"[SIP] 🔍 Processing line during INVITE collection: '{stripped_line[:100]}'")
            
            # Skip PJSUA metadata lines but keep SIP content
            if "pjsua_core.c" in stripped_line or ".RX " in stripped_line:
                log.debug("[SIP] 🔍 Skipping PJSUA metadata line")
                return
                
            # Check for end of INVITE message - multiple termination conditions
            if ("--end msg--" in stripped_line or 
                "pjsua_call.c" in stripped_line or
                (len(self._invite_buffer) > 20 and stripped_line.startswith('y=')) or
                # NEW: Detect completion when we have all essential SIP/SDP components
                (len(self._invite_buffer) >= 10 and 
                 any('m=video' in line for line in self._invite_buffer) and
                 any('Content-Length:' in line for line in self._invite_buffer) and
                 any('Call-ID:' in line for line in self._invite_buffer))):
                
                log.info("[SIP] 🏁 Detected end-of-message marker for INVITE")
                # End of INVITE message, process it
                if self._invite_buffer:
                    invite_message = '\n'.join(self._invite_buffer)
                    log.info(f"[SIP] ✅ INVITE message collection complete: {len(invite_message)} bytes")
                    log.debug(f"[SIP] Full INVITE message:\n{invite_message}")
                    
                    # Extract Call-ID from collected message
                    call_id = self._extract_call_id_from_invite_message(invite_message)
                    if call_id:
                        log.info(f"[SIP] 🎬 Processing INVITE with Call-ID: {call_id}")
                        self._handle_invite_request(call_id, invite_message)
                    else:
                        log.warning("[SIP] ⚠️ Could not extract Call-ID from INVITE message")
                        log.debug(f"[SIP] 🔍 INVITE content for Call-ID debug: {invite_message[:200]}...")
                else:
                    log.warning("[SIP] ⚠️ No INVITE content collected")
                
                # Reset collection
                self._collecting_invite = False
                self._invite_buffer = []
                return
                
            # Add line to INVITE collection if it looks like SIP content
            if stripped_line and (
                stripped_line.startswith(('Call-ID:', 'CSeq:', 'From:', 'To:', 'Via:', 'Max-Forwards:', 
                                        'User-Agent:', 'Contact:', 'Subject:', 'Content-Type:', 'Content-Length:',
                                        'v=', 'o=', 's=', 'c=', 't=', 'm=', 'a=')) or
                stripped_line.startswith('SIP/') or
                'sip:' in stripped_line.lower()
            ):
                self._invite_buffer.append(stripped_line)
                log.debug(f"[SIP] Added INVITE line: {stripped_line}")
                
                # Extract Call-ID when we encounter it
                if stripped_line.startswith('Call-ID:') and not self._invite_call_id:
                    self._invite_call_id = stripped_line.split(':', 1)[1].strip()
                    log.debug(f"[SIP] Found Call-ID in INVITE: {self._invite_call_id}")
            
            return
                    
        # Handle other SIP responses and status updates
        if "SIP/2.0" in line and any(code in line for code in ["200 OK", "401", "404", "500"]):
            log.debug(f"[SIP] SIP response: {line.strip()}")
            
        # Handle keep-alive and other status messages
        if "Keep-alive" in line:
            log.debug("[SIP] Keep-alive message")
        elif "pjsua_core.c" in line and ("TX" in line or "RX" in line):
            log.debug(f"[SIP] SIP traffic: {line.strip()}")

    def _extract_xml_from_message(self, complete_message):
        """Extract XML content from a complete SIP message"""
        try:
            # Enhanced XML content detection that looks at the entire message
            xml_content = ""

            # Method 1: Look for XML declaration
            if "<?xml" in complete_message:
                xml_start = complete_message.find("<?xml")
                xml_content = complete_message[xml_start:]
                log.debug(f"[SIP] Found XML prolog at position {xml_start}")
                
            # Method 2: Look for GB28181 query tags
            elif "<Query>" in complete_message:
                xml_start = complete_message.find("<Query>")
                xml_content = complete_message[xml_start:]
                log.debug(f"[SIP] Found <Query> tag at position {xml_start}")
                
            # Method 3: Look for GB28181 response tags
            elif "<Response>" in complete_message:
                xml_start = complete_message.find("<Response>")
                xml_content = complete_message[xml_start:]
                log.debug(f"[SIP] Found <Response> tag at position {xml_start}")
                
            # Method 4: Emergency detection - look for XML content after double newline
            if not xml_content:
                log.debug("[SIP] Primary XML detection failed, trying emergency detection")
                
                # Split by double newlines to separate headers from body
                if '\r\n\r\n' in complete_message:
                    headers, body = complete_message.split('\r\n\r\n', 1)
                elif '\n\n' in complete_message:
                    headers, body = complete_message.split('\n\n', 1)
                else:
                    headers = complete_message
                    body = ""
                
                log.debug(f"[SIP] Emergency: Headers length: {len(headers)}, Body length: {len(body)}")
                
                # Check if body contains XML
                if body and ("<?xml" in body or "<Query>" in body or "<Response>" in body):
                    xml_content = body.strip()
                    log.info(f"[SIP] 🔧 Emergency XML detection successful! Found: {xml_content[:100]}...")
                elif "Query" in complete_message or "Response" in complete_message:
                    # Last resort: extract any XML-like content
                    log.warning("[SIP] 🚨 Desperate XML search in complete message")
                    for pattern in ["<Query>", "<Response>", "<?xml"]:
                        if pattern in complete_message:
                            start_pos = complete_message.find(pattern)
                            xml_content = complete_message[start_pos:]
                            log.info(f"[SIP] 🔧 Desperate search found XML: {xml_content[:100]}...")
                            break

            return xml_content.strip() if xml_content else None
            
        except Exception as e:
            log.error(f"[SIP] Error extracting XML: {e}")
            return None

    def _process_xml_content(self, xml_content):
        """Process extracted XML content"""
        try:
            if not xml_content:
                return
                
            log.info(f"[SIP] ✅ Processing XML content ({len(xml_content)} bytes)")
            log.debug(f"[SIP] XML content preview: {xml_content[:200]}...")
            
            # Parse XML to determine message type
            import xml.etree.ElementTree as ET
            
            # Clean XML content for parsing
            clean_xml = xml_content.strip()
            
            # Handle cases where XML might not have proper declaration
            if not clean_xml.startswith('<?xml'):
                clean_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + clean_xml
            
            # Parse the XML
            root = ET.fromstring(clean_xml)
            cmd_type = None
            
            # Extract command type
            if root.tag == "Query":
                cmd_type_elem = root.find("CmdType")
                if cmd_type_elem is not None:
                    cmd_type = cmd_type_elem.text
                    
            log.info(f"[SIP] ✅ Successfully parsed {root.tag} message with CmdType: {cmd_type}")
            
            # Handle different query types
            if root.tag == "Query":
                if cmd_type == "Catalog":
                    log.info("[SIP] 📂 Processing Catalog query - will send device catalog")
                    response = self.handle_catalog_query(xml_content)
                    if response:
                        log.info("[SIP] ✅ Sending catalog response to WVP platform")
                        success = self.send_sip_message(response)
                        if success:
                            log.info("[SIP] ✅ Catalog response sent successfully")
                        else:
                            log.error("[SIP] ❌ Failed to send catalog response")
                    else:
                        log.error("[SIP] ❌ Failed to generate catalog response")
                elif cmd_type == "DeviceStatus":
                    log.info("[SIP] 🔍 Processing DeviceStatus query")
                    response = self.handle_device_info_query(xml_content)
                    if response:
                        self.send_sip_message(response)
                elif cmd_type == "DeviceInfo":
                    log.info("[SIP] ℹ️ Processing DeviceInfo query")
                    response = self.handle_device_info_query(xml_content)
                    if response:
                        self.send_sip_message(response)
                elif cmd_type == "RecordInfo":
                    log.info("[SIP] 📹 Processing RecordInfo query")
                    response = self.handle_recordinfo_query(xml_content)
                    if response:
                        success = self.send_sip_message(response)
                        if success:
                            log.info(f"[SIP] Sent record info response with {len(recordings)} recordings")
                        else:
                            log.error("[SIP] Failed to send record info response")
                    else:
                        log.error("[SIP] Failed to format record info response")
                else:
                    log.warning(f"[SIP] ⚠️ Unhandled query type: {cmd_type}")
            elif root.tag == "Control":
                log.info("[SIP] 🎮 Processing Control message")
                response = self.handle_device_control(xml_content)
                if response:
                    self.send_sip_message(response)
            else:
                log.warning(f"[SIP] ❓ Unknown XML message type: {root.tag}")
                
        except ET.ParseError as e:
            log.error(f"[SIP] ❌ XML parsing error: {e}")
            log.debug(f"[SIP] Failed XML content: {xml_content}")
            # Try manual processing for Catalog queries
            if "Catalog" in xml_content:
                log.info("[SIP] 🔧 Attempting manual catalog processing")
                try:
                    response = self.handle_catalog_query(xml_content)
                    if response:
                        log.info("[SIP] ✅ Manual catalog processing successful")
                        self.send_sip_message(response)
                except Exception as manual_e:
                    log.error(f"[SIP] ❌ Manual catalog processing failed: {manual_e}")
        except Exception as e:
            log.error(f"[SIP] ❌ Error processing XML message: {e}")
            import traceback
            log.debug(f"[SIP] Full traceback: {traceback.format_exc()}")

    def _handle_registration_failure(self):
        """Handle registration failures with retry logic"""
        self.registration_attempts += 1
        
        if self.registration_attempts >= self.max_registration_attempts:
            log.error(f"[SIP] ❌ Registration failed after {self.registration_attempts} attempts")
            return
            
        retry_delay = min(30, self.registration_retry_interval * self.registration_attempts)
        log.info(f"[SIP] Will retry registration in {retry_delay} seconds")
        
        # Schedule registration retry
        threading.Timer(retry_delay, self._retry_registration).start()

    def _retry_registration(self):
        """Retry SIP registration"""
        if self.registration_status == "registered":
            return
            
        log.info("[SIP] Retrying registration...")
        self._start_pjsua_process("/tmp/pjsua.cfg")

    def _check_registration(self):
        """Periodically check registration status and renew proactively for WVP platform compatibility"""
        if self.registration_status != "registered":
            return
            
        now = time.time()
        
        # FIXED: Proactive registration renewal for WVP platform (renew at 75% of expiry time)
        # WVP platform expects registration renewal every ~90 seconds to prevent offline status
        registration_renewal_time = 90  # FIXED: 90 seconds instead of 2700 (45 minutes)
        
        if now - self.last_registration_time > registration_renewal_time:
            log.info("[SIP] 🔄 Proactive registration renewal for WVP platform - preventing device offline")
            self.last_registration_time = now  # Update timestamp before renewal
            self._retry_registration()
        
        # Check for registration expiry warnings
        elif now - self.last_registration_time > 75:  # FIXED: 75 seconds - warning before expiry
            log.warning(f"[SIP] 🔄 Registration approaching expiry in {120 - (now - self.last_registration_time):.0f}s - will renew soon")
            
        # Emergency registration renewal if we're close to expiry
        elif now - self.last_registration_time > 105:  # FIXED: 105 seconds - emergency renewal before 2min timeout
            log.error("[SIP] 🚨 Emergency registration renewal - device may go offline in 15 seconds!")
            self.last_registration_time = now  # Update timestamp before renewal
            self._retry_registration()

    def _check_streams(self):
        """Check and maintain active streams with enhanced monitoring"""
        now = time.time()
        for call_id, stream_info in list(self.active_streams.items()):
            try:
                # Convert Call-ID to MediaStreamer stream ID format
                media_stream_id = f"{stream_info['dest_ip']}:{stream_info['dest_port']}"
                if stream_info.get('ssrc'):
                    media_stream_id = f"{media_stream_id}:{stream_info['ssrc']}"
                
                # Check stream health using get_stream_status with correct stream ID
                status = self.streamer.get_stream_status(media_stream_id)
                if not status or status.get("status") in ["stopped", "unknown"] or status.get("health") == "critical":
                    log.warning(f"[SIP] Stream {call_id} (media: {media_stream_id}) appears unhealthy: {status}")
                    self._handle_stream_failure(call_id, stream_info)
                    continue

                # Check stream duration
                duration = now - stream_info["start_time"]
                if duration > 3600:  # 1 hour
                    log.info(f"[SIP] Stream {call_id} running for {duration:.0f}s")
                    
                # Update stream status
                if duration % 60 < 1:  # Every minute
                    self._send_media_status_update(call_id)
                    
            except Exception as e:
                log.error(f"[SIP] Error checking stream {call_id}: {e}")

    def _handle_stream_failure(self, call_id, stream_info):
        """Handle stream failures with recovery attempts"""
        try:
            # Create MediaStreamer stream ID format
            media_stream_id = f"{stream_info['dest_ip']}:{stream_info['dest_port']}"
            if stream_info.get('ssrc'):
                media_stream_id = f"{media_stream_id}:{stream_info['ssrc']}"
                
            log.info(f"[SIP] Handling stream failure for Call-ID: {call_id}, Media stream: {media_stream_id}")
            
            # Stop the failed stream using correct stream ID
            self.streamer.stop_stream(media_stream_id)
            
            # Attempt to restart the stream
            success = self.streamer.start_stream(
                video_path=stream_info.get("video_path"),
                dest_ip=stream_info["dest_ip"],
                dest_port=stream_info["dest_port"],
                ssrc=stream_info["ssrc"]
            )
            
            if success:
                log.info(f"[SIP] Successfully restarted stream for Call-ID: {call_id}")
            else:
                log.error(f"[SIP] Failed to restart stream for Call-ID: {call_id}")
                del self.active_streams[call_id]
                
        except Exception as e:
            log.error(f"[SIP] Error handling stream failure: {e}")

    def stop(self):
        log.info("[SIP] Stopping all streams and SIP client...")
        
        # Set running flag to false first
        self.running = False
        
        # ADDED: Stop heartbeat thread first
        self._stop_heartbeat_thread()
        
        # Stop the SIP sender
        try:
            if hasattr(self, 'sip_sender'):
                self.sip_sender.stop()
        except Exception as e:
            log.error(f"[SIP] Error stopping SIP sender: {e}")
        
        # Stop all active media streams
        for callid, stream_info in list(self.active_streams.items()):
            try:
                stream_id = f"{stream_info['dest_ip']}:{stream_info['dest_port']}"
                if stream_info.get('ssrc'):
                    stream_id = f"{stream_id}:{stream_info['ssrc']}"
                
                log.info(f"[SIP] Stopping stream {stream_id} for Call-ID: {callid}")
                if self.streamer:
                    self.streamer.stop_stream(stream_id)
            except Exception as e:
                log.error(f"[SIP] Error stopping stream for Call-ID {callid}: {e}")
        
        # Clear active streams
        self.active_streams.clear()
            
        # Properly shutdown the media streamer
        try:
            if self.streamer:
                self.streamer.shutdown()
        except Exception as e:
            log.error(f"[SIP] Error shutting down media streamer: {e}")
        
        # Enhanced process cleanup for pjsua
        if self.process:
            try:
                # First attempt graceful termination
                log.info("[SIP] Attempting graceful pjsua termination...")
                self.process.terminate()
                
                # Wait with timeout
                try:
                    self.process.wait(timeout=5)
                    log.info("[SIP] PJSUA process terminated gracefully")
                except subprocess.TimeoutExpired:
                    log.warning("[SIP] PJSUA process did not terminate gracefully, forcing kill...")
                    self.process.kill()
                    try:
                        self.process.wait(timeout=2)
                        log.info("[SIP] PJSUA process killed successfully")
                    except subprocess.TimeoutExpired:
                        log.error("[SIP] Failed to kill PJSUA process")
                        
            except Exception as e:
                log.error(f"[SIP] Error during process cleanup: {e}")
            finally:
                self.process = None
                
        # Additional cleanup of any remaining pjsua processes
        try:
            self._kill_existing_pjsua_processes()
        except Exception as e:
            log.error(f"[SIP] Error in additional process cleanup: {e}")
            
        # Close pipes if they exist
        try:
            if hasattr(self, 'pipe_read'):
                os.close(self.pipe_read)
            if hasattr(self, 'pipe_write'):
                os.close(self.pipe_write)
        except Exception as e:
            log.debug(f"[SIP] Error closing pipes: {e}")
            
        log.info("[SIP] SIP client stopped and cleanup completed")

    def _schedule_media_status_update(self, stream_id, delay=5.0):
        """Schedule a media status update after a delay"""
        if not stream_id:
            return
            
        def _update():
            try:
                self._send_media_status_update(stream_id)
            except Exception as e:
                log.error(f"[SIP] Error in scheduled status update: {e}")
                
        threading.Timer(delay, _update).start()

    def handle_catalog_subscription(self, msg_text):
        """Handle catalog subscription requests"""
        try:
            # Extract headers from the message
            call_id_match = re.search(r"Call-ID:\s*(.+)", msg_text, re.IGNORECASE)
            from_match = re.search(r"From:\s*<(.+?)>", msg_text, re.IGNORECASE)
            to_match = re.search(r"To:\s*<(.+?)>", msg_text, re.IGNORECASE)
            via_match = re.search(r"Via:\s*(.+)", msg_text, re.IGNORECASE)
            cseq_match = re.search(r"CSeq:\s*(\d+)\s+SUBSCRIBE", msg_text, re.IGNORECASE)
            event_match = re.search(r"Event:\s*Catalog", msg_text, re.IGNORECASE)
            
            if not all([call_id_match, from_match, to_match, via_match, cseq_match, event_match]):
                log.warning("[SIP] Missing required headers in SUBSCRIBE request")
                return
                
            call_id = call_id_match.group(1).strip()
            from_uri = from_match.group(1).strip()
            to_uri = to_match.group(1).strip()
            via_header = via_match.group(1).strip()
            cseq = cseq_match.group(1).strip()
            
            # Extract SN and DeviceID from the XML body if present
            xml_match = re.search(r'<\?xml.*<\/Query>', msg_text, re.DOTALL)
            if xml_match:
                # Parse the XML
                xml_content = xml_match.group(0)
                root = ET.fromstring(xml_content)
                
                # Extract basic information
                cmd_type = root.find('CmdType').text if root.find('CmdType') is not None else ""
                device_id = root.find('DeviceID').text if root.find('DeviceID') is not None else ""
                sn = root.find('SN').text if root.find('SN') is not None else ""
                
                log.info(f"[SIP] Catalog subscription: CMD={cmd_type}, SN={sn}, DeviceID={device_id}")
            
            # Prepare a NOTIFY with the device catalog
            self.sip_sender.send_notify_catalog(
                call_id=call_id,
                from_uri=from_uri,
                to_uri=to_uri,
                via_header=via_header,
                cseq=cseq
            )
            
            log.info(f"[SIP] Sent catalog notification for subscription: {call_id}")
            
        except Exception as e:
            log.error(f"[SIP] Error handling catalog subscription: {e}")
            
    def handle_alarm_subscription(self, msg_text):
        """Handle alarm subscription requests"""
        try:
            # Extract headers from the message
            call_id_match = re.search(r"Call-ID:\s*(.+)", msg_text, re.IGNORECASE)
            from_match = re.search(r"From:\s*<(.+?)>", msg_text, re.IGNORECASE)
            to_match = re.search(r"To:\s*<(.+?)>", msg_text, re.IGNORECASE)
            via_match = re.search(r"Via:\s*(.+)", msg_text, re.IGNORECASE)
            cseq_match = re.search(r"CSeq:\s*(\d+)\s+SUBSCRIBE", msg_text, re.IGNORECASE)
            
            if not all([call_id_match, from_match, to_match, via_match, cseq_match]):
                log.warning("[SIP] Missing required headers in alarm SUBSCRIBE request")
                return
                
            # We don't yet support alarms, but respond with a 200 OK
            log.info("[SIP] Alarm subscription received (not supported)")
            
        except Exception as e:
            log.error(f"[SIP] Error handling alarm subscription: {e}")

    def send_sip_message(self, xml_content):
        """Send SIP message with XML content by writing to file for PJSUA to process"""
        try:
            if not xml_content:
                log.warning("[SIP] No XML content to send")
                return False
                
            # Extract SN from XML for tracking
            import re
            sn_match = re.search(r'<SN>(\d+)</SN>', xml_content)
            sn = sn_match.group(1) if sn_match else "unknown"
            
            log.info(f"[SIP] 📤 Sending catalog response (SN: {sn}) via file-based method")
            
            # Use file-based method to avoid any socket conflicts
            return self._send_via_file_method(xml_content, sn)
                    
        except Exception as e:
            log.error(f"[SIP] ❌ Error sending SIP message: {e}")
            return False

    def _send_via_file_method(self, xml_content, sn):
        """Send SIP message via file-based method for reliable delivery"""
        try:
            import time
            import random
            
            # Generate unique identifiers for the SIP message
            current_time = int(time.time())
            call_id = f"catalog-{sn}-{current_time}"
            branch = f"z9hG4bK-{current_time}"
            tag = f"tag{current_time}"
            # FIXED: Handle both string and numeric SNs for CSeq conversion
            try:
                if isinstance(sn, str) and sn.isdigit():
                    cseq = int(sn) % 9999 + 1000
                elif isinstance(sn, int):
                    cseq = sn % 9999 + 1000
                else:
                    # Fallback for non-numeric SNs
                    cseq = hash(str(sn)) % 9999 + 1000
            except (ValueError, TypeError):
                # Final fallback
                cseq = int(time.time()) % 9999 + 1000
            
            # FIXED: Use the platform's actual SIP address from recent query
            # Instead of hardcoded platform ID, use the actual server domain
            from_uri = f"sip:{self.device_id}@{self.local_ip}:{self.local_port}"
            # CRITICAL FIX: Use the platform's domain/realm, not specific user ID
            to_uri = f"sip:{self.server}:{self.port}"  # Use platform server directly
            contact_uri = f"<sip:{self.local_ip}:{self.local_port}>"
            
            # Write XML content to a temporary file for debugging
            temp_file = f"catalog_response_{sn}.xml"
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                log.debug(f"[SIP] Saved response XML to {temp_file}")
            except Exception as file_error:
                log.warning(f"[SIP] Could not save debug file: {file_error}")
            
            # Build complete SIP message
            sip_message = f"""MESSAGE {to_uri} SIP/2.0
Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};rport;branch={branch}
Max-Forwards: 70
From: <{from_uri}>;tag={tag}
To: <{to_uri}>
Call-ID: {call_id}
CSeq: {cseq} MESSAGE
Contact: {contact_uri}
User-Agent: GB28181-Restreamer/1.0
Content-Type: Application/MANSCDP+xml
Content-Length: {len(xml_content)}

{xml_content}"""
            
            # Send using a clean UDP socket that doesn't conflict with PJSUA
            success = self._send_udp_message(sip_message, sn)
            
            if success:
                log.info(f"[SIP] ✅ File-based catalog response sent successfully (SN: {sn})")
                return True
            else:
                log.error(f"[SIP] ❌ File-based catalog response failed (SN: {sn})")
                return False
                
        except Exception as e:
            log.error(f"[SIP] ❌ Error in file-based sending: {e}")
            return False
            
    def _send_udp_message(self, sip_message, sn):
        """Send SIP message via clean UDP socket"""
        try:
            import socket
            
            # Create a new UDP socket for this message only
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            try:
                # Don't bind to any specific port - let OS choose
                # This avoids any conflicts with PJSUA
                sock.settimeout(5.0)  # 5 second timeout
                
                # ENHANCED DEBUGGING: Analyze message before sending
                message_bytes = sip_message.encode('utf-8')
                
                # FIXED: Determine message type for accurate logging
                message_type = "Unknown"
                item_count = 0
                declared_count = 0
                
                if "<CmdType>Keepalive</CmdType>" in sip_message:
                    message_type = "Keepalive"
                    # Don't count items for keepalive messages
                elif "<CmdType>Catalog</CmdType>" in sip_message:
                    message_type = "Catalog"
                    # Count XML elements in catalog messages only
                    import re
                    item_count = len(re.findall(r'<Item>', sip_message))
                    sumnum_match = re.search(r'<SumNum>(\d+)</SumNum>', sip_message)
                    declared_count = int(sumnum_match.group(1)) if sumnum_match else 0
                elif "Notify" in sip_message and "CmdType" in sip_message:
                    message_type = "Notify"
                else:
                    # Generic SIP message analysis
                    import re
                    item_count = len(re.findall(r'<Item>', sip_message))
                    if item_count > 0:
                        message_type = "Catalog"
                        sumnum_match = re.search(r'<SumNum>(\d+)</SumNum>', sip_message)
                        declared_count = int(sumnum_match.group(1)) if sumnum_match else 0
                
                log.info(f"[SIP] 📊 UDP TRANSMISSION ANALYSIS (SN: {sn}):")
                log.info(f"[SIP]   • Message type: {message_type}")
                log.info(f"[SIP]   • Message size: {len(message_bytes)} bytes")
                log.info(f"[SIP]   • Target: {self.server}:{self.port}")
                log.info(f"[SIP]   • Encoding: UTF-8")
                
                if message_type == "Catalog":
                    log.info(f"[SIP]   • XML <Item> count: {item_count}")
                    log.info(f"[SIP]   • XML SumNum: {declared_count}")
                    
                    if item_count != declared_count:
                        log.error(f"[SIP] ❌ CRITICAL: Item count mismatch before sending!")
                        log.error(f"[SIP]   Declared: {declared_count}, Actual: {item_count}")
                    else:
                        log.info(f"[SIP] ✅ XML integrity verified before transmission")
                
                # Check if message might be too large for single UDP packet
                if len(message_bytes) > 1400:  # Conservative UDP safe size
                    log.warning(f"[SIP] ⚠️ Large UDP packet: {len(message_bytes)} bytes (may fragment)")
                    
                # Log message headers and start of content
                lines = sip_message.split('\n')
                log.debug(f"[SIP] 📨 Message headers:")
                for i, line in enumerate(lines[:10]):  # First 10 lines
                    log.debug(f"[SIP]   {i+1}: {line.strip()}")
                if len(lines) > 10:
                    log.debug(f"[SIP]   ... and {len(lines) - 10} more lines")
                
                # Send the message
                log.info(f"[SIP] 🚀 Sending UDP packet to {self.server}:{self.port}...")
                bytes_sent = sock.sendto(message_bytes, (self.server, self.port))
                
                # Verify transmission
                if bytes_sent == len(message_bytes):
                    log.info(f"[SIP] ✅ UDP transmission SUCCESSFUL: {bytes_sent}/{len(message_bytes)} bytes")
                else:
                    log.error(f"[SIP] ❌ UDP transmission INCOMPLETE: {bytes_sent}/{len(message_bytes)} bytes")
                    return False
                
                # Additional verification for large messages
                if len(message_bytes) > 1400:
                    log.warning(f"[SIP] 📡 Large message sent - WVP platform may need time to reassemble")
                
                # Brief pause to ensure message is sent
                time.sleep(0.05)
                
                # FIXED: Accurate success logging based on message type
                if message_type == "Keepalive":
                    log.info(f"[SIP] 💓 Keepalive message (SN: {sn}) delivered successfully")
                    log.info(f"[SIP]   • Device should stay online for next 15-30 seconds")
                elif message_type == "Catalog":
                    log.info(f"[SIP] 📤 Catalog response (SN: {sn}) delivered successfully")
                    log.info(f"[SIP]   • Contains {item_count} devices")
                    log.info(f"[SIP]   • Total size: {len(message_bytes)} bytes")
                    log.info(f"[SIP]   • WVP platform should process this within 30 seconds")
                else:
                    log.info(f"[SIP] 📤 {message_type} message (SN: {sn}) delivered successfully")
                    log.info(f"[SIP]   • Total size: {len(message_bytes)} bytes")
                
                return True
                
            except socket.timeout:
                log.error(f"[SIP] ❌ UDP send timeout for SN: {sn}")
                log.error(f"[SIP] Network may be congested or WVP platform unresponsive")
                return False
            except socket.error as send_error:
                log.error(f"[SIP] ❌ UDP socket error for SN: {sn}: {send_error}")
                log.error(f"[SIP] This may indicate network connectivity issues")
                return False
            except Exception as send_error:
                log.error(f"[SIP] ❌ UDP send error for SN: {sn}: {send_error}")
                return False
            finally:
                sock.close()
                
        except Exception as e:
            log.error(f"[SIP] ❌ Error creating UDP socket: {e}")
            return False

    def _extract_call_id_from_line(self, line):
        """Extract Call-ID from a SIP message line"""
        try:
            # Look for Call-ID in the line
            call_id_match = re.search(r"Call-ID:\s*(.+)", line)
            if call_id_match:
                return call_id_match.group(1).strip()
            return None
        except Exception as e:
            log.error(f"[SIP] Error extracting Call-ID: {e}")
            return None
    
    def _extract_call_id_from_invite_message(self, invite_message):
        """Extract Call-ID from a complete INVITE message"""
        try:
            # Look for Call-ID line in the message
            for line in invite_message.split('\n'):
                if line.strip().startswith('Call-ID:'):
                    call_id = line.split(':', 1)[1].strip()
                    log.debug(f"[SIP] Extracted Call-ID from INVITE: {call_id}")
                    return call_id
            return None
        except Exception as e:
            log.error(f"[SIP] Error extracting Call-ID from INVITE message: {e}")
            return None
    
    def _extract_sdp_from_buffer(self, buffer):
        """Extract SDP content from message buffer"""
        try:
            return self.extract_sdp_from_message(buffer)
        except Exception as e:
            log.error(f"[SIP] Error extracting SDP from buffer: {e}")
            return None
    
    def _extract_sdp_from_invite_message(self, invite_message):
        """Extract SDP content from INVITE message"""
        try:
            # SDP content starts after empty line and consists of lines starting with v=, o=, s=, c=, t=, m=, a=
            lines = invite_message.split('\n')
            sdp_lines = []
            in_sdp = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('v='):
                    in_sdp = True
                    sdp_lines.append(line)
                elif in_sdp and line.startswith(('o=', 's=', 'c=', 't=', 'm=', 'a=')):
                    sdp_lines.append(line)
                elif in_sdp and not line:
                    # Empty line ends SDP
                    break
                elif in_sdp and not line.startswith(('v=', 'o=', 's=', 'c=', 't=', 'm=', 'a=')):
                    # Non-SDP line ends SDP
                    break
            
            if sdp_lines:
                sdp_content = '\n'.join(sdp_lines)
                log.debug(f"[SIP] Extracted SDP from INVITE: {sdp_content}")
                return sdp_content
            else:
                log.warning("[SIP] No SDP content found in INVITE message")
                return None
                
        except Exception as e:
            log.error(f"[SIP] Error extracting SDP from INVITE message: {e}")
            return None
    
    def _extract_target_channel_from_invite(self, invite_message):
        """Extract target channel ID from INVITE URI"""
        try:
            # Look for INVITE line with target URI
            for line in invite_message.split('\n'):
                line = line.strip()
                if line.startswith('INVITE sip:'):
                    # Extract channel ID from URI
                    # Format: INVITE sip:810000004650131000001@13.50.108.195:5080
                    match = re.search(r'INVITE sip:([^@]+)@', line)
                    if match:
                        channel_id = match.group(1)
                        log.debug(f"[SIP] Extracted target channel from INVITE: {channel_id}")
                        return channel_id
            return None
        except Exception as e:
            log.error(f"[SIP] Error extracting target channel from INVITE: {e}")
            return None
            
    def _extract_ssrc_from_invite(self, invite_message):
        """Extract SSRC from INVITE Subject line - CRITICAL for WVP compatibility"""
        try:
            # Look for Subject line with SSRC
            # Format: Subject: 810000004650131000001:0000009593,81000000462001888888:0
            for line in invite_message.split('\n'):
                line = line.strip()
                if line.startswith('Subject:'):
                    # Extract SSRC from subject
                    # Pattern: channel_id:ssrc,caller_id:0
                    match = re.search(r':(\d{10}),', line)
                    if match:
                        ssrc = match.group(1)
                        log.info(f"[SIP] 🎯 Extracted SSRC from WVP INVITE: {ssrc}")
                        return ssrc
            return None
        except Exception as e:
            log.error(f"[SIP] Error extracting SSRC from INVITE: {e}")
            return None
            
    def _capture_invite_headers(self, invite_message):
        """Capture exact headers from INVITE for SIP compliance - CRITICAL for avoiding 488 errors"""
        try:
            # Initialize header storage
            self._invite_via = None
            self._invite_from = None
            self._invite_to = None
            self._invite_cseq = None
            
            # Parse headers line by line
            for line in invite_message.split('\n'):
                line = line.strip()
                if line.startswith('Via:'):
                    self._invite_via = line
                elif line.startswith('From:'):
                    self._invite_from = line
                elif line.startswith('To:'):
                    self._invite_to = line
                elif line.startswith('CSeq:'):
                    self._invite_cseq = line
                    
            log.info(f"[SIP] 📋 Captured INVITE headers for SIP compliance:")
            log.info(f"[SIP]   Via: {self._invite_via}")
            log.info(f"[SIP]   From: {self._invite_from}")
            log.info(f"[SIP]   To: {self._invite_to}")
            log.info(f"[SIP]   CSeq: {self._invite_cseq}")
            
            # Verify we captured all required headers
            if not all([self._invite_via, self._invite_from, self._invite_to, self._invite_cseq]):
                log.warning(f"[SIP] ⚠️ Missing required headers in INVITE - may cause 488 response")
                
        except Exception as e:
            log.error(f"[SIP] Error capturing INVITE headers: {e}")
            # Set fallback values to prevent crashes
            self._invite_via = "Via: SIP/2.0/UDP 0.0.0.0:5060"
            self._invite_from = "From: <sip:unknown@unknown>"
            self._invite_to = "To: <sip:unknown@unknown>"
            self._invite_cseq = "CSeq: 1 INVITE"
            
    def _build_to_header_with_tag(self):
        """Build To header by echoing INVITE To header and adding our local tag"""
        try:
            # Get the original To header from INVITE
            original_to = getattr(self, '_invite_to', f"To: <sip:{self.server}:{self.port}>")
            
            # Check if it already has a tag parameter
            if ';tag=' in original_to:
                # Original already has tag - just return as is
                return original_to
            else:
                # Add our local tag
                return f"{original_to};tag={getattr(self, '_local_tag', 'device123')}"
                
        except Exception as e:
            log.error(f"[SIP] Error building To header with tag: {e}")
            return f"To: <sip:{self.server}:{self.port}>;tag={getattr(self, '_local_tag', 'device123')}"
            
    def _create_gb28181_sdp_response(self, target_channel, call_id, expected_ssrc=None, incoming_sdp=None):
        """Create GB28181-compliant SDP response for WVP-Pro platform"""
        try:
            # Get network configuration
            local_ip = self.get_local_ip() 
            rtp_port = self.get_available_port()
            
            # Generate unique session ID
            session_id = str(int(time.time()))
            
            # Use the SSRC that WVP expects - CRITICAL for compatibility
            if not expected_ssrc:
                expected_ssrc = target_channel  # Fallback to channel ID
                
            # CRITICAL FIX: Detect transport protocol from incoming INVITE
            # Default to UDP RTP, but match what WVP platform offered
            transport_protocol = "RTP/AVP"
            payload_types = ""
            h264_pt = None   # PT for H264/90000 if offered
            ps_pt   = None   # PT for PS/90000 if offered
            
            if incoming_sdp:
                # Check if WVP platform offered TCP/RTP/AVP and extract payload types
                for line in incoming_sdp.split('\n'):
                    line = line.strip()
                    if line.startswith('m=video '):
                        parts = line.split()
                        if len(parts) >= 3:
                            if 'TCP/RTP/AVP' in line:
                                transport_protocol = "TCP/RTP/AVP"
                                log.info(f"[SIP] 🔧 WVP platform uses TCP/RTP/AVP - matching transport protocol")
                            elif 'RTP/SAVP' in line:
                                transport_protocol = "RTP/SAVP"
                                log.info(f"[SIP] 🔧 WVP platform uses RTP/SAVP - matching transport protocol")
                            elif 'RTP/AVP' in line:
                                transport_protocol = "RTP/AVP"
                                log.info(f"[SIP] 🔧 WVP platform uses RTP/AVP - matching transport protocol")
                            
                            # Extract payload types (everything after transport protocol)
                            if len(parts) > 3:
                                offered_pts = parts[3:]
                                payload_types = " ".join(offered_pts)
                                log.info(f"[SIP] 🔧 WVP offered payload types: {payload_types}")
                                h264_pt = offered_pts[0]
                                ps_pt = offered_pts[1]
                        break
                        
                # Look for explicit rtpmap lines to detect which PT corresponds to H264/90000
                for line in incoming_sdp.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('a=rtpmap:'):
                        if 'h264/90000' in line.lower():
                            try:
                                h264_pt = line.split()[0].split(':')[1]
                                log.info(f"[SIP] 🔧 Detected H264 payload type in offer: {h264_pt}")
                            except Exception:
                                pass
                        if 'ps/90000' in line.lower():
                            try:
                                ps_pt = line.split()[0].split(':')[1]
                                log.info(f"[SIP] 🔧 Detected PS payload type in offer: {ps_pt}")
                            except Exception:
                                pass

                # If we still don't have payload_types, default to H264 PT or first offered
                if not payload_types:
                    payload_types = h264_pt if h264_pt else '96'

            # If we still have multiple payload types, narrow to the selected H264 PT for the answer
            if payload_types and ' ' in payload_types:
                if h264_pt:
                    payload_types = h264_pt
                else:
                    # default to the first one
                    payload_types = payload_types.split()[0]

            # Decide which PT/codec we will answer with
            chosen_pt = None
            chosen_codec = None
            if ps_pt:
                chosen_pt = ps_pt
                chosen_codec = "PS/90000"
            elif h264_pt:
                chosen_pt = h264_pt
                chosen_codec = "H264/90000"
            else:
                chosen_pt = payload_types.split()[0] if payload_types else "96"
                chosen_codec = "H264/90000"

            payload_types = chosen_pt  # our m-line will contain only this PT

            # Create GB28181-compliant SDP content according to GB/T 28181-2016 standard
            # CRITICAL FIX: Use PS (Program Stream) format which is standard for GB28181
            sdp_lines = [
                "v=0",
                f"o=- {session_id} {session_id} IN IP4 {local_ip}",
                "s=Play",
                f"c=IN IP4 {local_ip}",
                "t=0 0",
                # CRITICAL FIX: Match the transport protocol and payload types from WVP platform
                # When we are ACTIVE (RFC 4145) we must set the port to 9 (discard) as recommended
                # by the COMEDIA specification. Some SIP servers (including WVP) reject an SDP
                # answer that specifies any other port while declaring a=setup:active.
                f"m=video {9 if 'TCP' in transport_protocol else rtp_port} {transport_protocol} {payload_types}",
                # The offer was a=recvonly, so our answer must be a=sendonly
                "a=sendonly",
                # RFC 4145: indicate we will actively initiate the TCP connection to WVP
                "a=setup:active",
                # Use H.264 format for better GB28181 compatibility with WVP
                f"a=rtpmap:{chosen_pt} {chosen_codec}",
                # No extra rtpmap lines – keep answer minimal
            ]
            
            # Add rtpmap for additional payload types if present
            pts = payload_types.split()
            for pt in pts[1:]:  # Skip first one (96) as it's already added
                if pt.isdigit():
                    sdp_lines.append(f"a=rtpmap:{pt} H264/90000")
            
            # Add GB28181-specific attributes
            sdp_lines.extend([
                f"y={expected_ssrc}",
                "f=v/2/25"
            ])
            
            sdp_content = "\r\n".join(sdp_lines) + "\r\n"
            
            log.info(f"[SIP] 📄 Created GB28181-compliant SDP response for channel {target_channel}")
            log.info(f"[SIP] 🎯 Using WVP-expected SSRC: {expected_ssrc}")
            log.info(f"[SIP] 🚀 Using transport protocol: {transport_protocol} (CRITICAL FIX)")
            log.info(f"[SIP] 🎯 Using payload types: {payload_types}")
            media_port_for_log = 9 if 'TCP' in transport_protocol else rtp_port
            log.info(f"[SIP] 🌐 Media endpoint: {local_ip}:{media_port_for_log}")
            log.debug(f"[SIP] SDP content:\n{sdp_content}")
            
            return sdp_content
            
        except Exception as e:
            log.error(f"[SIP] Error creating GB28181 SDP response: {e}")
            return None
            
    def get_local_ip(self):
        """Get local IP address for SDP"""
        try:
            # Try to get the actual local IP that can reach external networks
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                log.debug(f"[SIP] Detected local IP: {local_ip}")
                return local_ip
        except Exception as e:
            log.warning(f"[SIP] Could not detect local IP: {e}, using fallback")
            return "127.0.0.1"
            
    def get_available_port(self):
        """Get an available port for RTP"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind(('', 0))
                port = s.getsockname()[1]
                log.debug(f"[SIP] Allocated RTP port: {port}")
                return port
        except Exception as e:
            log.warning(f"[SIP] Could not allocate dynamic port: {e}, using default")
            return 10000
            
    def _parse_destination_from_sdp(self, sdp_content):
        """Parse destination IP and port from WVP's SDP"""
        try:
            dest_ip = None
            dest_port = None
            
            for line in sdp_content.split('\n'):
                line = line.strip()
                
                # Connection line: c=IN IP4 203.142.93.131
                if line.startswith('c=IN IP4 '):
                    dest_ip = line.split()[-1]
                    log.debug(f"[SIP] Found destination IP: {dest_ip}")
                
                # Media line: m=video 10000 TCP/RTP/AVP 96 97 98 99
                if line.startswith('m=video '):
                    parts = line.split()
                    if len(parts) >= 2:
                        dest_port = int(parts[1])
                        log.debug(f"[SIP] Found destination port: {dest_port}")
                        
            if dest_ip and dest_port:
                log.info(f"[SIP] 📍 Parsed destination: {dest_ip}:{dest_port}")
                return dest_ip, dest_port
            else:
                log.warning(f"[SIP] ⚠️ Could not parse destination from SDP: ip={dest_ip}, port={dest_port}")
                return None, None
                
        except Exception as e:
            log.error(f"[SIP] Error parsing destination from SDP: {e}")
            return None, None
            
    def _start_streaming_to_platform(self, channel_id, call_id, dest_ip, dest_port, ssrc=None, transport_protocol="TCP/RTP/AVP"):
        """Start streaming to WVP platform at specified destination with correct SSRC"""
        try:
            log.info(f"[SIP] 🎥 Starting stream from channel {channel_id} to WVP at {dest_ip}:{dest_port}")
            
            # Use the SSRC that WVP expects - this is CRITICAL for compatibility
            if not ssrc:
                ssrc = "0000000001"  # Fallback
                
            log.info(f"[SIP] 🎯 Using SSRC for streaming: {ssrc}")
            log.info(f"[SIP] 🚀 Using transport protocol: {transport_protocol}")
            
            # Create SDP that describes the stream we're about to send
            # Use H.264 format to match the actual pipeline output
            mock_destination_sdp = f"""v=0
o=GB28181 0 0 IN IP4 {dest_ip}
s=Play
c=IN IP4 {dest_ip}
t=0 0
m=video {dest_port} {transport_protocol} 96
a=sendrecv
a=rtpmap:96 PS/90000
a=rtpmap:97 H264/90000
a=rtpmap:98 H264/90000
a=rtpmap:99 H264/90000
"""
            
            log.info(f"[SIP] 🎯 Configured streaming destination: {dest_ip}:{dest_port}")
            
            # Use existing streaming infrastructure with SSRC parameter
            success = self.parse_sdp_and_stream(mock_destination_sdp, callid=call_id, target_channel=channel_id, ssrc=ssrc)
            
            if success:
                log.info(f"[SIP] ✅ Stream started successfully to WVP platform")
                # Store stream info
                if not hasattr(self, '_active_streams'):
                    self._active_streams = {}
                self._active_streams[call_id] = {
                    'channel_id': channel_id,
                    'dest_ip': dest_ip,
                    'dest_port': dest_port,
                    'ssrc': ssrc,
                    'start_time': time.time(),
                    'status': 'active'
                }
                return True
            else:
                log.error(f"[SIP] ❌ Failed to start stream to WVP platform")
                return False
                
        except Exception as e:
            log.error(f"[SIP] Error starting stream to platform: {e}")
            import traceback
            log.debug(f"[SIP] Platform streaming error: {traceback.format_exc()}")
            return False
    
    def _handle_invite_request(self, call_id, invite_message):
        """Handle incoming INVITE request for GB28181 streaming"""
        try:
            log.info(f"[SIP] 🎬 Processing INVITE request with Call-ID: {call_id}")
            
            # CRITICAL: Capture exact headers from INVITE for SIP compliance
            self._capture_invite_headers(invite_message)
            
            # Extract target channel from INVITE URI - this is what WVP wants us to stream
            target_channel = self._extract_target_channel_from_invite(invite_message)
            if not target_channel:
                log.warning("[SIP] ⚠️ Could not extract target channel from INVITE URI")
                self._send_invite_response(call_id, "400", "Bad Request")
                return
                
            log.info(f"[SIP] 🎯 WVP requesting stream for channel: {target_channel}")
            
            # Verify this channel exists in our catalog
            if not self._is_valid_channel(target_channel):
                log.warning(f"[SIP] ⚠️ Requested channel {target_channel} not found in device catalog")
                self._send_invite_response(call_id, "404", "Not Found")
                return
                
            # Extract incoming SDP from WVP - this tells us WHERE to send the stream
            incoming_sdp = self._extract_sdp_from_invite_message(invite_message)
            if not incoming_sdp:
                log.warning("[SIP] ⚠️ No SDP in INVITE - cannot determine streaming destination")
                self._send_invite_response(call_id, "400", "Bad Request")
                return
                
            # CRITICAL FIX: Extract SSRC from WVP's INVITE subject
            expected_ssrc = self._extract_ssrc_from_invite(invite_message)
            if not expected_ssrc:
                log.warning("[SIP] ⚠️ No SSRC found in INVITE Subject line")
                expected_ssrc = "0000009593"  # Default fallback
                
            log.info(f"[SIP] 📄 WVP provided destination SDP: {incoming_sdp[:200]}...")
            
            # Parse WVP's SDP to get destination IP and port
            dest_ip, dest_port = self._parse_destination_from_sdp(incoming_sdp)
            if not dest_ip or not dest_port:
                log.error("[SIP] ❌ Could not parse destination from WVP SDP")
                self._send_invite_response(call_id, "488", "Not Acceptable Here")
                return
                
            log.info(f"[SIP] 🎯 WVP expects stream at: {dest_ip}:{dest_port}")
            
            # CRITICAL FIX: Detect transport protocol from WVP's SDP for consistent usage
            transport_protocol = "TCP/RTP/AVP"  # Default for WVP
            for line in incoming_sdp.split('\n'):
                line = line.strip()
                if line.startswith('m=video ') and 'TCP/RTP/AVP' in line:
                    transport_protocol = "TCP/RTP/AVP"
                    break
                elif line.startswith('m=video ') and 'RTP/SAVP' in line:
                    transport_protocol = "RTP/SAVP"
                    break
                elif line.startswith('m=video ') and 'RTP/AVP' in line:
                    transport_protocol = "RTP/AVP"
                    break
            
            # Start streaming TO the WVP platform using the exact SSRC WVP expects
            success = self._start_streaming_to_platform(target_channel, call_id, dest_ip, dest_port, expected_ssrc, transport_protocol)
            if success:
                log.info(f"[SIP] ✅ Successfully started stream for channel {target_channel}")
                
                # Create GB28181-compliant SDP response with WVP's expected SSRC and matching transport protocol
                response_sdp = self._create_gb28181_sdp_response(target_channel, call_id, expected_ssrc, incoming_sdp)
                if response_sdp:
                    log.info(f"[SIP] 📄 Generated SDP response for 200 OK")
                    self._send_invite_response(call_id, "200", "OK", response_sdp)
                else:
                    log.error(f"[SIP] ❌ Failed to generate SDP response")
                    self._send_invite_response(call_id, "500", "Internal Server Error")
            else:
                log.error(f"[SIP] ❌ Failed to start media stream for channel {target_channel}")
                self._send_invite_response(call_id, "488", "Not Acceptable Here")
                
        except Exception as e:
            log.error(f"[SIP] ❌ Error handling INVITE request: {e}")
            import traceback
            log.debug(f"[SIP] Full traceback: {traceback.format_exc()}")
            self._send_invite_response(call_id, "500", "Internal Server Error")

    def _is_valid_channel(self, channel_id):
        """Check if the requested channel exists in our device catalog"""
        try:
            # Check if channel matches our device ID or any of our channels
            if channel_id == self.device_id:
                return True
                
            # Check channel format - should be device_id + channel suffix
            # For GB28181, channels usually follow pattern like: 810000004650131000001
            if channel_id.startswith(self.device_id[:13]):  # Device prefix + channel
                return True
                
            log.debug(f"[SIP] Channel validation: {channel_id} vs device {self.device_id}")
            return True  # For now, accept all channels - can be made stricter later
            
        except Exception as e:
            log.error(f"[SIP] Error validating channel {channel_id}: {e}")
            return False
            


    def _send_invite_response(self, call_id, status_code, reason_phrase, sdp_content=None):
        """Send SIP response to INVITE request - CRITICAL: Echo headers for SIP compliance"""
        try:
            log.info(f"[SIP] 📤 Sending INVITE response: {status_code} {reason_phrase}")
            
            # Generate unique local tag for this dialog
            if not hasattr(self, '_local_tag'):
                self._local_tag = f"device{int(time.time())}"
            
            # Build response headers by echoing INVITE headers - CRITICAL for SIP compliance
            response_lines = [
                f"SIP/2.0 {status_code} {reason_phrase}",       # 1. Status line
                self._invite_via,                               # 2. Via
                f"{self._invite_to};tag={self._local_tag}",     # 3. To with our tag
                self._invite_from,                              # 4. From
                f"Call-ID: {call_id}",                          # 5. Call-ID
                self._invite_cseq,                              # 6. CSeq
                f"Contact: <sip:{self.device_id}@{self.local_ip}:{self.local_port}>",
                "User-Agent: GB28181-Restreamer/1.0"             # 7. Other headers
            ]
            if status_code == "200" and sdp_content:
                response_lines += [
                    "Content-Type: application/sdp",
                    f"Content-Length: {len(sdp_content)}",
                    "",                  # 8. Single blank line
                    sdp_content.rstrip() # 9. SDP body
                ]
            else:
                response_lines += [
                    "Content-Length: 0",
                    ""  # blank line
                ]
            response_msg = "\r\n".join(response_lines).strip("\r\n") + "\r\n\r\n"
            
            
            log.info(f"[SIP] 📋 Response headers echoed from INVITE:")
            log.info(f"[SIP]   Via: {getattr(self, '_invite_via', 'MISSING')}")
            log.info(f"[SIP]   CSeq: {getattr(self, '_invite_cseq', 'MISSING')}")
            
            # Send response via UDP socket directly
            success = self._send_sip_response_udp(response_msg)
            if success:
                log.info(f"[SIP] ✅ INVITE response {status_code} sent successfully")
            else:
                log.error(f"[SIP] ❌ Failed to send INVITE response {status_code}")
            
            # Store response info for debugging
            if not hasattr(self, '_invite_responses'):
                self._invite_responses = {}
            self._invite_responses[call_id] = {
                'status_code': status_code,
                'reason_phrase': reason_phrase,
                'sdp_content': sdp_content,
                'timestamp': time.time(),
                'sent': success,
                'headers_echoed': {
                    'via': getattr(self, '_invite_via', None),
                    'from': getattr(self, '_invite_from', None),
                    'to': getattr(self, '_invite_to', None),
                    'cseq': getattr(self, '_invite_cseq', None)
                }
            }
            
            return success
            
        except Exception as e:
            log.error(f"[SIP] ❌ Error sending INVITE response: {e}")
            import traceback
            log.debug(f"[SIP] Response error traceback: {traceback.format_exc()}")
            return False

    def _send_sip_response_udp(self, response_message):
        """Send SIP response via UDP socket"""
        try:
            # Use the same UDP sending method as keepalive
            import socket
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            
            # Send to server IP and port
            server_addr = (self.server, self.port)
            response_bytes = response_message.encode('utf-8')
            
            sent_bytes = sock.sendto(response_bytes, server_addr)
            sock.close()
            
            log.debug(f"[SIP] 📤 Sent SIP response: {sent_bytes}/{len(response_bytes)} bytes to {server_addr}")
            return sent_bytes == len(response_bytes)
            
        except Exception as e:
            log.error(f"[SIP] ❌ Error sending SIP response via UDP: {e}")
            return False

    def _handle_invite_with_sdp(self, call_id, sdp_content):
        """Handle INVITE with SDP content (legacy method)"""
        try:
            success = self.parse_sdp_and_stream(sdp_content, call_id)
            if success:
                log.info(f"[SIP] Successfully started stream for Call-ID: {call_id}")
            else:
                log.error(f"[SIP] Failed to start stream for Call-ID: {call_id}")
            return success
        except Exception as e:
            log.error(f"[SIP] Error handling INVITE with SDP: {e}")
            return False

    def _start_heartbeat_thread(self):
        """Start dedicated heartbeat thread for WVP platform compatibility"""
        if self._heartbeat_running:
            return
            
        log.info("[SIP] 💓 Starting dedicated heartbeat thread for WVP platform")
        self._heartbeat_running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self._heartbeat_thread.start()
        
        # ADDED: Start periodic catalog notification thread
        log.info("[SIP] 📋 Starting periodic catalog notification thread")
        self._catalog_notification_thread = threading.Thread(target=self._catalog_notification_worker, daemon=True)
        self._catalog_notification_thread.start()
        
    def _stop_heartbeat_thread(self):
        """Stop the heartbeat thread"""
        log.info("[SIP] 🛑 Stopping heartbeat thread")
        self._heartbeat_running = False
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=2)
            
    def _catalog_notification_worker(self):
        """Periodic catalog notification worker - sends catalog every 60 seconds to ensure frontend visibility"""
        log.info("[SIP] 📋 Catalog notification worker started - will send catalog every 60s")
        
        # Wait 10 seconds after start before first notification
        time.sleep(10)
        
        while self._heartbeat_running and self.running:
            try:
                # Only send catalog if registered
                if self.registration_status == "registered":
                    log.info("[SIP] 📋 Sending periodic catalog notification to maintain frontend visibility")
                    success = self._send_proactive_catalog_notification()
                    if success:
                        log.info("[SIP] ✅ Periodic catalog notification sent successfully")
                    else:
                        log.warning("[SIP] ⚠️ Periodic catalog notification failed")
                else:
                    log.debug("[SIP] 📋 Skipping catalog notification - not registered")
                
                # Wait 60 seconds before next notification
                for _ in range(60):  # Split into 1-second intervals for responsive shutdown
                    if not self._heartbeat_running or not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                log.error(f"[SIP] ❌ Error in catalog notification worker: {e}")
                time.sleep(10)  # Brief pause before retry
                
        log.info("[SIP] 📋 Catalog notification worker stopped")

    def _heartbeat_worker(self):
        """Dedicated heartbeat worker thread - sends keepalive every 15 seconds for WVP platform compatibility"""
        log.info("[SIP] 💓 Heartbeat worker started - will send keepalive every 15s to prevent WVP timeout")
        
        while self._heartbeat_running and self.running:
            try:
                # Only send heartbeat if registered
                if self.registration_status == "registered":
                    log.info("[SIP] 💓 Sending scheduled heartbeat to WVP platform")
                    self._send_keepalive()
                else:
                    log.debug("[SIP] 💓 Skipping heartbeat - not registered")
                
                # FIXED: Wait 15 seconds before next heartbeat (increased frequency for WVP platform)
                for _ in range(15):  # Split into 1-second intervals for responsive shutdown
                    if not self._heartbeat_running or not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                log.error(f"[SIP] ❌ Error in heartbeat worker: {e}")
                time.sleep(5)  # Brief pause before retry
                
        log.info("[SIP] 💓 Heartbeat worker stopped")

    def _send_keepalive(self):
        """Send keepalive message to maintain registration with enhanced WVP compatibility"""
        try:
            # Create proper GB28181 keepalive message according to WVP platform requirements
            current_time = time.time()
            sn = int(current_time) % 100000  # Use timestamp for unique SN
            
            # Format timestamp for Info section (WVP may expect this)
            timestamp_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(current_time))
            
            keepalive_xml = f"""<?xml version="1.0" encoding="GB2312"?>
<Notify>
<CmdType>Keepalive</CmdType>
<SN>{sn}</SN>
<DeviceID>{self.device_id}</DeviceID>
<Status>OK</Status>
<Info>
<DeviceID>{self.device_id}</DeviceID>
<Time>{timestamp_str}</Time>
</Info>
</Notify>"""
            
            log.info(f"[SIP] 💓 Sending WVP-compatible keepalive (SN: {sn}) to prevent heartbeat timeout")
            
            # FIXED: Send keepalive via dedicated UDP socket, not catalog response method
            success = self._send_keepalive_message(keepalive_xml, sn)
            
            if success:
                self.last_keepalive_time = current_time
                self.last_keepalive = current_time
                log.info(f"[SIP] ✅ Keepalive sent successfully - device should stay online")
            else:
                log.warning(f"[SIP] ⚠️ Keepalive failed to send - device may go offline")
                
                # If keepalive fails consistently, try emergency registration renewal
                if hasattr(self, '_last_successful_keepalive'):
                    time_since_last_success = current_time - self._last_successful_keepalive
                    if time_since_last_success > 90:  # 90 seconds without successful keepalive
                        log.error("[SIP] 🚨 Keepalive failures detected - triggering emergency registration renewal")
                        self._retry_registration()
                else:
                    self._last_successful_keepalive = current_time
                    
            # Track successful keepalive for failure detection
            if success:
                self._last_successful_keepalive = current_time
                
        except Exception as e:
            log.error(f"[SIP] ❌ Error sending keepalive: {e}")
            import traceback
            log.debug(f"[SIP] Keepalive error traceback: {traceback.format_exc()}")
            
            # Emergency fallback - try to renew registration if keepalive fails
            try:
                log.warning("[SIP] 🔄 Keepalive failed, attempting registration renewal as fallback")
                self._retry_registration()
            except Exception as retry_error:
                log.error(f"[SIP] ❌ Emergency registration renewal also failed: {retry_error}")

    def _send_keepalive_message(self, keepalive_xml, sn):
        """Send keepalive message via clean UDP socket"""
        try:
            import socket
            import time
            
            # Generate unique identifiers for the SIP message
            current_time = int(time.time())
            call_id = f"keepalive-{sn}-{current_time}"
            branch = f"z9hG4bK-ka-{current_time}"
            tag = f"katag{current_time}"
            cseq = sn % 9999 + 2000  # Different range for keepalives
            
            # Build SIP URIs
            from_uri = f"sip:{self.device_id}@{self.local_ip}:{self.local_port}"
            to_uri = f"sip:{self.server}:{self.port}"
            contact_uri = f"<sip:{self.local_ip}:{self.local_port}>"
            
            # Build complete SIP MESSAGE for keepalive
            sip_message = f"""MESSAGE {to_uri} SIP/2.0
Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};rport;branch={branch}
Max-Forwards: 70
From: <{from_uri}>;tag={tag}
To: <{to_uri}>
Call-ID: {call_id}
CSeq: {cseq} MESSAGE
Contact: {contact_uri}
User-Agent: GB28181-Restreamer/1.0
Content-Type: Application/MANSCDP+xml
Content-Length: {len(keepalive_xml)}

{keepalive_xml}"""

            # Send the keepalive via UDP helper
            return self._send_udp_message(sip_message, sn)
        
        except Exception as e:
            log.error(f"[SIP] ❌ Error constructing/sending keepalive: {e}")
            return False

    def _send_proactive_catalog_notification(self):
        """Send proactive catalog notification to WVP platform after registration - CRITICAL for device visibility"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                log.info("[SIP] 📋 Sending proactive catalog notification to WVP platform for immediate visibility")
                
                # CRITICAL: Ensure catalog is available before generation
                if not hasattr(self, 'device_catalog') or not self.device_catalog:
                    log.warning("[SIP] ⚠️ Device catalog is empty - regenerating for proactive notification")
                    try:
                        self.generate_device_catalog()
                        log.info(f"[SIP] ✅ Catalog regenerated: {len(self.device_catalog)} channels")
                    except Exception as catalog_error:
                        log.error(f"[SIP] ❌ Failed to regenerate catalog: {catalog_error}")
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            log.info(f"[SIP] 🔄 Retrying proactive notification (attempt {retry_count + 1})")
                            time.sleep(2)
                            continue
                        else:
                            return False
                
                # Generate a unique SN for this proactive notification
                current_time = int(time.time())
                sn = current_time % 100000 + 50000  # Different range from keepalives
                
                # Generate catalog response XML
                catalog_xml = self._generate_catalog_response(str(sn))
                
                if not catalog_xml:
                    log.error("[SIP] ❌ Failed to generate catalog for proactive notification")
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        log.info(f"[SIP] 🔄 Retrying proactive notification (attempt {retry_count + 1})")
                        time.sleep(2)
                        continue
                    else:
                        return False
                
                # Verify catalog has devices
                item_count = len(re.findall(r'<Item>', catalog_xml))
                if item_count == 0:
                    log.error("[SIP] ❌ Generated catalog has no devices - this will not work!")
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        log.info(f"[SIP] 🔄 Retrying proactive notification (attempt {retry_count + 1})")
                        time.sleep(2)
                        continue
                    else:
                        return False
                
                # Build complete SIP MESSAGE for catalog notification
                from_uri = f"sip:{self.device_id}@{self.local_ip}:{self.local_port}"
                to_uri = f"sip:{self.server}:{self.port}"
                contact_uri = f"<sip:{self.local_ip}:{self.local_port}>"
                
                call_id = f"catalog-proactive-{sn}-{current_time}"
                branch = f"z9hG4bK-cat-{current_time}"
                tag = f"cattag{current_time}"
                cseq = sn % 9999 + 5000  # Different range for catalog
                
                sip_message = f"""MESSAGE {to_uri} SIP/2.0
Via: SIP/2.0/UDP {self.local_ip}:{self.local_port};rport;branch={branch}
Max-Forwards: 70
From: <{from_uri}>;tag={tag}
To: <{to_uri}>
Call-ID: {call_id}
CSeq: {cseq} MESSAGE
Contact: {contact_uri}
User-Agent: GB28181-Restreamer/1.0
Content-Type: Application/MANSCDP+xml
Content-Length: {len(catalog_xml)}

{catalog_xml}"""

                # Send via UDP
                success = self._send_udp_message(sip_message, sn)
                
                if success:
                    log.info(f"[SIP] ✅ Proactive catalog notification sent successfully (SN: {sn})")
                    log.info(f"[SIP] 📱 WVP frontend should now show {len(self.device_catalog)} available channels")
                    return True
                else:
                    log.error(f"[SIP] ❌ Failed to send proactive catalog notification (SN: {sn})")
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        log.info(f"[SIP] 🔄 Retrying proactive notification (attempt {retry_count + 1})")
                        time.sleep(2)
                        continue
                    else:
                        return False
                        
            except Exception as e:
                log.error(f"[SIP] ❌ Error sending proactive catalog notification: {e}")
                import traceback
                log.debug(f"[SIP] Proactive catalog error traceback: {traceback.format_exc()}")
                
                if retry_count < max_retries - 1:
                    retry_count += 1
                    log.info(f"[SIP] 🔄 Retrying proactive notification after error (attempt {retry_count + 1})")
                    time.sleep(2)
                    continue
                else:
                    log.error(f"[SIP] ❌ Failed to send proactive catalog notification after {max_retries} attempts")
                    return False
        
        return False
