# src/gb28181_sip_sender.py
"""
GB28181 SIP Message Sender
This module provides functionality to send SIP messages according to the GB28181 protocol.
"""

import os
import subprocess
import tempfile
import time
import threading
import atexit
import re
import uuid
from logger import log
import logging

class GB28181SIPSender:
    """
    Class to handle sending SIP messages according to the GB28181 protocol.
    Uses pjsua command line tool to send SIP messages with XML content.
    """
    
    def __init__(self, config):
        """Initialize with SIP configuration"""
        self.config = config
        self.device_id = config["sip"]["device_id"]
        self.username = config["sip"]["username"]
        self.password = config["sip"]["password"]
        self.server = config["sip"]["server"]
        self.port = config["sip"]["port"]
        self.pjsua_proc = None
        self.message_queue = []
        self.sender_thread = None
        self.running = False
        self.lock = threading.Lock()
        
        # Create a directory for temporary files
        self.temp_dir = tempfile.mkdtemp(prefix="gb28181_")
        atexit.register(self._cleanup)
    
    def _cleanup(self):
        """Clean up temporary files on exit"""
        if os.path.exists(self.temp_dir):
            try:
                for filename in os.listdir(self.temp_dir):
                    os.remove(os.path.join(self.temp_dir, filename))
                os.rmdir(self.temp_dir)
            except Exception as e:
                log.error(f"[SIP-SENDER] Error cleaning up temp files: {e}")
    
    def _ensure_temp_dir(self):
        """Ensure the temporary directory exists"""
        if not os.path.exists(self.temp_dir):
            try:
                os.makedirs(self.temp_dir, exist_ok=True)
                log.info(f"[SIP-SENDER] Created temporary directory: {self.temp_dir}")
            except Exception as e:
                log.error(f"[SIP-SENDER] Error creating temp directory: {e}")
                # Fall back to a different location if the original doesn't work
                self.temp_dir = tempfile.mkdtemp(prefix="gb28181_")
                log.info(f"[SIP-SENDER] Using alternative temp directory: {self.temp_dir}")
    
    def start(self):
        """Start the SIP sender thread"""
        if self.running:
            return
            
        self.running = True
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.sender_thread.start()
        log.info("[SIP-SENDER] Started GB28181 SIP message sender thread")
    
    def stop(self):
        """Stop the SIP sender thread"""
        self.running = False
        if self.sender_thread:
            self.sender_thread.join(timeout=2)
        log.info("[SIP-SENDER] Stopped GB28181 SIP message sender thread")
    
    def _sender_loop(self):
        """Worker thread to process and send SIP messages"""
        while self.running:
            try:
                if self.message_queue:
                    with self.lock:
                        if self.message_queue:
                            message_data = self.message_queue.pop(0)
                            self._send_message(message_data)
                time.sleep(0.1)  # Small delay to prevent CPU hogging
            except Exception as e:
                log.error(f"[SIP-SENDER] Error in sender loop: {e}")
    
    def _send_message(self, message_data):
        """Send a SIP message using pjsua without registration"""
        # Handle None value for target_uri with default server URI
        target_uri = message_data.get("target_uri")
        if target_uri is None:
            target_uri = f"sip:{self.server}:{self.port}"
        
        content_type = message_data.get("content_type", "Application/MANSCDP+xml")
        content = message_data.get("content", "")
        
        # Ensure temp directory exists
        self._ensure_temp_dir()
        
        # Create temporary file for the message content
        fd, temp_path = tempfile.mkstemp(prefix="msg_", suffix=".xml", dir=self.temp_dir)
        os.close(fd)
        
        try:
            with open(temp_path, 'w') as f:
                f.write(content)
            
            log.info(f"[SIP-SENDER] Preparing to send {content_type} message to {target_uri}")
            log.debug(f"[SIP-SENDER] Message content length: {len(content)} bytes")
            log.debug(f"[SIP-SENDER] Message preview: {content[:200]}...")
            
            # Get transport preference from config
            prefer_tcp = self.config["sip"].get("prefer_tcp", False)
            transport = "tcp" if prefer_tcp else "udp"
            
            # Build pjsua command to send the message WITHOUT REGISTRATION
            # This prevents creating new connections that trigger VS Code popups
            cmd = [
                "pjsua",
                "--id", f"sip:{self.device_id}@{self.server}",
                "--realm", "*",
                "--username", self.username,
                "--password", self.password,
                "--local-port", "0",  # Use random port to avoid conflicts
                "--no-tcp" if transport == "udp" else "--use-tcp",
                "--null-audio",
                "--duration", "5",  # Limit session duration to 5 seconds
                "--auto-quit",  # Quit automatically after sending
                "--send-message", target_uri,
                "--message-content-type", content_type,
                "--message-content", f"@{temp_path}"
            ]
            
            log.info(f"[SIP-SENDER] Sending message to {target_uri} using {transport} transport (no registration)")
            log.debug(f"[SIP-SENDER] Command: {' '.join(cmd)}")
            
            # Execute the command with shorter timeout
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=8  # Reduced timeout since no registration needed
            )
            
            if result.returncode == 0:
                log.info(f"[SIP-SENDER] ✅ Successfully sent message to {target_uri}")
            else:
                log.error(f"[SIP-SENDER] ❌ Failed to send message: {result.stdout}")
                log.debug(f"[SIP-SENDER] Command returned code: {result.returncode}")
                
        except subprocess.TimeoutExpired:
            log.error(f"[SIP-SENDER] ⌛ Timeout sending message to {target_uri}")
        except Exception as e:
            log.error(f"[SIP-SENDER] Error sending message: {e}")
            import traceback
            log.error(f"[SIP-SENDER] {traceback.format_exc()}")
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def queue_message(self, content, target_uri=None, content_type="Application/MANSCDP+xml"):
        """Queue a message to be sent"""
        logging.info(f"[SIP-SENDER] Queuing SIP MESSAGE to {target_uri} with content type {content_type} (length {len(content)})")
        message_data = {
            "target_uri": target_uri,
            "content_type": content_type,
            "content": content,
            "timestamp": time.time()
        }
        
        with self.lock:
            self.message_queue.append(message_data)
        
        # Start the sender thread if not already running
        if not self.running:
            self.start()
            
        return True
    
    def send_catalog(self, xml_content, target_uri=None):
        """Send device catalog information"""
        logging.info(f"[SIP-SENDER] Sending catalog SIP MESSAGE to {target_uri} (length {len(xml_content)})")
        return self.queue_message(xml_content, target_uri)
    
    def send_device_info(self, xml_content, target_uri=None):
        """Send device information"""
        return self.queue_message(xml_content, target_uri)
    
    def send_keepalive(self, xml_content, target_uri=None):
        """Send keepalive message"""
        return self.queue_message(xml_content, target_uri)
    
    def send_media_status(self, xml_content, target_uri=None):
        """Send media status update"""
        return self.queue_message(xml_content, target_uri)
    
    def send_recordinfo(self, xml_content, target_uri=None):
        """Send a RecordInfo response message to the SIP platform
        
        Args:
            xml_content (str): XML content to send
            target_uri (str): Target URI to send the message to (optional)
        
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        log.info("[SIP-SENDER] Preparing to send RecordInfo response")
        
        # Use the default target URI if not provided
        if not target_uri:
            target_uri = f"sip:{self.server}:{self.port}"
            
        # Create a temporary file for the message content
        self._ensure_temp_dir()
        message_file = self._create_temp_file(xml_content)
        
        if not message_file:
            log.error("[SIP-SENDER] Failed to create temporary file for RecordInfo response")
            return False
            
        # Send the message using pjsua
        result = self._send_sip_message(
            target_uri=target_uri,
            content_type="Application/MANSCDP+xml",
            message_file=message_file
        )
        
        # Cleanup the temporary file
        if os.path.exists(message_file):
            os.remove(message_file)
            
        return result
    
    def send_alarm(self, xml_content, target_uri=None):
        """Send alarm notification"""
        return self.queue_message(xml_content, target_uri)
    
    def send_response(self, request, code, reason, sdp_content=None):
        """
        Send a SIP response message to an INVITE or other request
        
        Args:
            request (str): The original SIP request message
            code (str): The response code (200, 404, etc)
            reason (str): The reason phrase ("OK", "Not Found", etc)
            sdp_content (str, optional): SDP content for responses that require it
        """
        try:
            # Extract necessary headers from the request
            lines = request.split('\n')
            request_line = lines[0] if lines else ""
            
            # Extract essential headers
            call_id = None
            from_header = None
            to_header = None
            via_header = None
            cseq = None
            
            for line in lines:
                if line.lower().startswith("call-id:"):
                    call_id = line
                elif line.lower().startswith("from:"):
                    from_header = line
                elif line.lower().startswith("to:"):
                    to_header = line
                elif line.lower().startswith("via:"):
                    via_header = line
                elif line.lower().startswith("cseq:"):
                    cseq = line
                    
            # Identify the request method (INVITE, OPTIONS, etc.)
            method = request_line.split(' ')[0] if ' ' in request_line else "UNKNOWN"
            
            # Create response
            response = f"SIP/2.0 {code} {reason}\r\n"
            if via_header:
                response += via_header + "\r\n"
            if from_header:
                response += from_header + "\r\n"
            if to_header:
                # Add tag if not present
                if ";tag=" not in to_header:
                    to_header += f";tag=as{int(time.time())}"
                response += to_header + "\r\n"
            if call_id:
                response += call_id + "\r\n"
            if cseq:
                response += cseq + "\r\n"
                
            # Add server identity
            response += f"Server: GB28181-Restreamer\r\n"
            
            # If method was INVITE and code is 200, include SDP content
            if method == "INVITE" and code == "200" and sdp_content:
                response += f"Content-Type: application/sdp\r\n"
                response += f"Content-Length: {len(sdp_content)}\r\n\r\n"
                response += sdp_content
            else:
                response += "Content-Length: 0\r\n\r\n"
                
            # Extract target URI from request
            to_match = re.search(r"To:\s*<([^>]+)>", request)
            target_uri = to_match.group(1) if to_match else None
            
            # Create a temporary file for the response
            fd, temp_path = tempfile.mkstemp(prefix="response_", suffix=".sip", dir=self.temp_dir)
            os.close(fd)
            
            with open(temp_path, 'w') as f:
                f.write(response)
            
            # TODO: Need to implement actual response sending via socket
            # For now we log the response and consider it as handled
            log.info(f"[SIP-SENDER] Prepared {code} {reason} response for {method} request")
            log.debug(f"[SIP-SENDER] Response: {response}")
            
            # In future, implement actual sending
            # This would require socket handling similar to LocalSIPServer
            
            # Clean up
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
                    
            return True
        except Exception as e:
            log.error(f"[SIP-SENDER] Error preparing response: {e}")
            return False 

    def send_message(self, xml_content, target_uri=None):
        """Send a generic SIP MESSAGE with XML content"""
        return self.queue_message(xml_content, target_uri)
        
    def send_notify_catalog(self, call_id, from_uri, to_uri, via_header, cseq, target_uri=None):
        """Send a NOTIFY message for catalog subscription"""
        from file_scanner import get_video_catalog
        from gb28181_xml import format_catalog_response
        
        # Get the device catalog
        catalog = {}
        video_files = get_video_catalog()
        
        for i, video_path in enumerate(video_files):
            video_name = os.path.basename(video_path)
            # Generate unique channel ID for each video file
            channel_id = f"{self.device_id}_{i+1:03d}"
            
            catalog[channel_id] = {
                "name": video_name,
                "path": video_path,
                "status": "ON",
                "manufacturer": "GB28181-Restreamer",
                "model": "Video-File",
                "owner": "gb28181-restreamer",
                "civil_code": "123456",
                "address": f"Video-{i+1}",
                "parental": "0",
                "parent_id": self.device_id,
                "register_way": "1",
                "secrecy": "0",
            }
        
        # Format XML catalog response
        xml_content = format_catalog_response(self.device_id, catalog)
        
        # Create direct NOTIFY message
        if not target_uri:
            # Extract target URI from SUBSCRIBE
            if to_uri:
                # Find IP part of to_uri
                ip_match = re.search(r'@([^:;>]+)', to_uri)
                if ip_match:
                    ip = ip_match.group(1)
                    target_uri = f"sip:{to_uri}"
                else:
                    log.warning(f"[SIP-SENDER] Could not extract IP from {to_uri}")
                    target_uri = f"sip:{self.server}:{self.port}"
            else:
                target_uri = f"sip:{self.server}:{self.port}"
                
        log.info(f"[SIP-SENDER] Sending catalog NOTIFY to {target_uri}")
        
        # Ensure temp directory exists
        self._ensure_temp_dir()
        
        # Create temporary file for NOTIFY content
        try:
            fd, temp_path = tempfile.mkstemp(prefix="notify_", suffix=".xml", dir=self.temp_dir)
            os.close(fd)
            
            with open(temp_path, 'w') as f:
                f.write(xml_content)
                
            # Get transport preference from config
            prefer_tcp = self.config["sip"].get("prefer_tcp", False)
            transport = "tcp" if prefer_tcp else "udp"
            
            # Try to extract contact information for the direct NOTIFY
            contact_match = re.search(r'Contact:\s*<([^>]+)>', from_uri) if from_uri else None
            contact_uri = contact_match.group(1) if contact_match else None
            
            # Build a custom NOTIFY message
            if contact_uri:
                log.info(f"[SIP-SENDER] Sending direct NOTIFY to {contact_uri}")
                # Sending direct NOTIFY message
                direct_notify_cmd = self._create_direct_notify_command(
                    xml_content, 
                    contact_uri, 
                    call_id,
                    transport
                )
                
                if direct_notify_cmd:
                    result = subprocess.run(
                        direct_notify_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        log.info("[SIP-SENDER] Successfully sent direct catalog NOTIFY")
                    else:
                        log.error(f"[SIP-SENDER] Failed to send direct catalog NOTIFY: {result.stdout}")
                        
                        # Fallback to regular pjsua NOTIFY
                        self._send_pjsua_notify(xml_content, target_uri, transport, temp_path)
                else:
                    # If direct command creation failed, use standard method
                    self._send_pjsua_notify(xml_content, target_uri, transport, temp_path)
            else:
                # Use standard pjsua notify
                self._send_pjsua_notify(xml_content, target_uri, transport, temp_path)
                
        except Exception as e:
            log.error(f"[SIP-SENDER] Error sending catalog NOTIFY: {e}")
        finally:
            # Clean up
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    log.error(f"[SIP-SENDER] Error removing temp file: {e}")
                    
        return True
        
    def _create_direct_notify_command(self, xml_content, contact_uri, call_id, transport):
        """Create a direct NOTIFY command using netcat or similar tools"""
        
        # First, try to extract IP and port from contact URI
        ip_port_match = re.search(r'@([^:;>]+):?(\d+)?', contact_uri)
        
        if not ip_port_match:
            log.warning(f"[SIP-SENDER] Could not extract IP/port from {contact_uri}")
            return None
            
        ip = ip_port_match.group(1)
        port = ip_port_match.group(2) if ip_port_match.group(2) else "5060"
        
        notify_body = f"""NOTIFY sip:{contact_uri} SIP/2.0
Via: SIP/2.0/{transport.upper()} {self.server}:{self.port};branch=z9hG4bK-{uuid.uuid4().hex[:12]}
From: <sip:{self.device_id}@{self.server}>;tag={uuid.uuid4().hex[:12]}
To: <sip:{contact_uri}>
Call-ID: {call_id}
CSeq: 1 NOTIFY
Contact: <sip:{self.device_id}@{self.server}:{self.port}>
Event: Catalog
Subscription-State: active;expires=60
Content-Type: Application/MANSCDP+xml
Content-Length: {len(xml_content)}

{xml_content}"""

        # Ensure temp directory exists
        self._ensure_temp_dir()

        try:
            # Create temporary file for the direct NOTIFY message
            fd, direct_notify_path = tempfile.mkstemp(prefix="direct_notify_", suffix=".sip", dir=self.temp_dir)
            with os.fdopen(fd, 'w') as f:
                f.write(notify_body)
            
            # Instead of using shell redirection, we'll use cat to pipe into netcat
            if transport.lower() == "tcp":
                cmd = ["sh", "-c", f"cat {direct_notify_path} | nc -w 5 {ip} {port}"]
            else:
                cmd = ["sh", "-c", f"cat {direct_notify_path} | nc -u -w 5 {ip} {port}"]
                
            return cmd
        except Exception as e:
            log.error(f"[SIP-SENDER] Error creating direct NOTIFY command: {e}")
            return None
        
    def _send_pjsua_notify(self, xml_content, target_uri, transport, temp_path):
        """Send a NOTIFY message using pjsua"""
        try:
            # Build pjsua command to send the message with proper transport
            cmd = [
                "pjsua",
                "--id", f"sip:{self.device_id}@{self.server}",
                "--registrar", f"sip:{self.server}:{self.port}",
                "--realm", "*",
                "--username", self.username,
                "--password", self.password,
                "--local-port", "0",
            ]
            
            # Add transport parameter
            if transport == "tcp":
                cmd.extend(["--use-tcp"])
            
            # Complete the command
            cmd.extend([
                "--null-audio",
                "--send-message", target_uri,
                "--message-content-type", "Application/MANSCDP+xml",
                "--message-content", f"@{temp_path}"
            ])
            
            log.info(f"[SIP-SENDER] Sending NOTIFY message to {target_uri} using {transport} transport")
            log.debug(f"[SIP-SENDER] Command: {' '.join(cmd)}")
            
            # Execute the command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=10
            )
            
            if result.returncode == 0:
                log.info(f"[SIP-SENDER] ✅ Successfully sent NOTIFY message to {target_uri}")
                return True
            else:
                log.error(f"[SIP-SENDER] ❌ Failed to send NOTIFY message: {result.stdout}")
                log.debug(f"[SIP-SENDER] Command returned code: {result.returncode}")
                return False
                
        except Exception as e:
            log.error(f"[SIP-SENDER] Error sending NOTIFY message: {e}")
            return False 