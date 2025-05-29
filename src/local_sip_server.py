#!/usr/bin/env python3
"""
Simple Local SIP Server for GB28181 Testing

This module implements a basic SIP server that listens for INVITE messages
and forwards them to the main application for processing.
"""

import socket
import threading
import json
import os
import re
import time
from logger import log
import signal
import sys

class LocalSIPServer:
    def __init__(self, config, sip_client=None):
        self.config = config
        self.sip_client = sip_client  # Reference to the main SIP client
        self.local_config = config.get("local_sip", {})
        self.enabled = self.local_config.get("enabled", False)
        self.port = self.local_config.get("port", 5060)
        self.transport = self.local_config.get("transport", "tcp").lower()
        self.running = False
        self.server_socket = None
        self.thread = None
    
    def start(self):
        """Start the local SIP server"""
        if not self.enabled:
            log.info("[LOCAL-SIP] Local SIP server is disabled")
            return False
        
        if self.running:
            log.warning("[LOCAL-SIP] Server already running")
            return True
        
        log.info(f"[LOCAL-SIP] Starting local SIP server on port {self.port} using {self.transport.upper()}")
        
        # Try a range of ports if the default one is in use
        original_port = self.port
        max_port_attempts = 5
        
        for port_offset in range(max_port_attempts):
            try:
                self.port = original_port + port_offset
                if self.transport == "tcp":
                    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.server_socket.bind(("0.0.0.0", self.port))
                    self.server_socket.listen(5)
                    self.thread = threading.Thread(target=self._tcp_listener, daemon=True)
                else:
                    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.server_socket.bind(("0.0.0.0", self.port))
                    self.thread = threading.Thread(target=self._udp_listener, daemon=True)
                
                self.running = True
                self.thread.start()
                
                if port_offset > 0:
                    log.info(f"[LOCAL-SIP] Using alternate port {self.port} (original port {original_port} was in use)")
                
                log.info(f"[LOCAL-SIP] Server started successfully on port {self.port}")
                return True
                
            except OSError as e:
                if e.errno == 98 and port_offset < max_port_attempts - 1:  # Address already in use
                    log.warning(f"[LOCAL-SIP] Port {self.port} already in use, trying port {self.port + 1}")
                else:
                    log.exception(f"[LOCAL-SIP] Failed to start server: {e}")
                    self.stop()
                    return False
        
        log.error(f"[LOCAL-SIP] Could not find available port after {max_port_attempts} attempts")
        return False
    
    def _tcp_listener(self):
        """TCP connection listener thread"""
        log.info("[LOCAL-SIP] TCP listener started")
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                log.info(f"[LOCAL-SIP] New connection from {address[0]}:{address[1]}")
                
                client_handler = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_handler.start()
            
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    log.exception(f"[LOCAL-SIP] Error accepting connection: {e}")
    
    def _udp_listener(self):
        """UDP packet listener thread"""
        log.info("[LOCAL-SIP] UDP listener started")
        
        while self.running:
            try:
                data, address = self.server_socket.recvfrom(4096)
                log.info(f"[LOCAL-SIP] Received packet from {address[0]}:{address[1]}")
                
                # Handle the received packet
                self._process_sip_message(data.decode('utf-8', errors='ignore'))
                
            except Exception as e:
                if self.running:  # Only log if we're still supposed to be running
                    log.exception(f"[LOCAL-SIP] Error receiving UDP packet: {e}")
    
    def _handle_client(self, client_socket, address):
        """Handle TCP client connection"""
        try:
            # Receive data
            buffer = b""
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                buffer += data
                # Check if we've received a complete SIP message
                if b"\r\n\r\n" in buffer or b"\n\n" in buffer:
                    break
            
            # Process the message
            message = buffer.decode('utf-8', errors='ignore')
            self._process_sip_message(message)
            
            # Send a response
            response = self._generate_ok_response(message)
            client_socket.sendall(response.encode())
            
        except Exception as e:
            log.exception(f"[LOCAL-SIP] Error handling client: {e}")
        finally:
            client_socket.close()
    
    def _process_sip_message(self, message):
        """Process a received SIP message"""
        log.info("[LOCAL-SIP] Processing SIP message")
        
        # Log the first few lines for debugging
        message_preview = "\n".join(message.split("\n")[:10])
        log.debug(f"[LOCAL-SIP] Message preview:\n{message_preview}...")
        
        # Check message type
        first_line = message.split('\n')[0] if '\n' in message else message
        method = first_line.split(' ')[0] if ' ' in first_line else "UNKNOWN"
        
        # Process based on method
        if method == "INVITE":
            log.info("[LOCAL-SIP] Received INVITE message")
            
            # Forward to SIP client if available
            if self.sip_client:
                log.info("[LOCAL-SIP] Forwarding INVITE to main SIP handler")
                self.sip_client.handle_invite(message)
            else:
                log.warning("[LOCAL-SIP] No SIP client available to handle INVITE")
                
        elif method == "SUBSCRIBE":
            log.info("[LOCAL-SIP] Received SUBSCRIBE message")
            
            # Check if it's a catalog subscription
            if "Event: Catalog" in message:
                log.info("[LOCAL-SIP] Catalog subscription request received")
                self._handle_catalog_subscription(message)
            else:
                log.info(f"[LOCAL-SIP] Unhandled event type in SUBSCRIBE")
                
        elif method == "MESSAGE":
            log.info("[LOCAL-SIP] Received MESSAGE")
            
            # Forward to SIP client if available
            if self.sip_client:
                # Check message type based on content
                if "Catalog" in message:
                    log.info("[LOCAL-SIP] Forwarding catalog query to main SIP handler")
                    self.sip_client.handle_catalog_query(message)
                elif "RecordInfo" in message:
                    log.info("[LOCAL-SIP] Forwarding record info query to main SIP handler")
                    self.sip_client.handle_recordinfo_query(message)
                elif "DeviceInfo" in message:
                    log.info("[LOCAL-SIP] Forwarding device info query to main SIP handler")
                    self.sip_client.handle_device_info_query(message)
                else:
                    log.info("[LOCAL-SIP] Forwarding generic message to main SIP handler")
                    # Forward the raw message for further processing
                    self.sip_client._process_sip_message(message, message)
            else:
                log.warning("[LOCAL-SIP] No SIP client available to handle MESSAGE")
        
        else:
            log.info(f"[LOCAL-SIP] Received {method} message (not specifically handled)")
    
    def _handle_catalog_subscription(self, message):
        """Handle catalog subscription requests"""
        try:
            # Extract necessary headers from the message
            call_id_match = re.search(r"Call-ID:\s*(.+)", message, re.IGNORECASE)
            from_match = re.search(r"From:\s*<(.+?)>", message, re.IGNORECASE)
            to_match = re.search(r"To:\s*<(.+?)>", message, re.IGNORECASE)
            via_match = re.search(r"Via:\s*(.+)", message, re.IGNORECASE)
            cseq_match = re.search(r"CSeq:\s*(\d+)\s+SUBSCRIBE", message, re.IGNORECASE)
            contact_match = re.search(r"Contact:\s*<(.+?)>", message, re.IGNORECASE)
            expires_match = re.search(r"Expires:\s*(\d+)", message, re.IGNORECASE)
            
            if not all([call_id_match, from_match, to_match, via_match, cseq_match]):
                log.warning("[LOCAL-SIP] Missing required headers in SUBSCRIBE request")
                return
                
            call_id = call_id_match.group(1).strip()
            from_uri = from_match.group(1).strip()
            to_uri = to_match.group(1).strip()
            via_header = via_match.group(1).strip()
            cseq = cseq_match.group(1).strip()
            contact = contact_match.group(1).strip() if contact_match else None
            expires = expires_match.group(1).strip() if expires_match else "60"
                
            # Extract client address for response
            client_address_match = re.search(r"received=([0-9.]+)", via_header)
            client_address = client_address_match.group(1) if client_address_match else None
            
            if not client_address:
                # Try to extract from Via header directly
                client_address_match = re.search(r"SIP/2.0/UDP ([0-9.]+):", via_header)
                client_address = client_address_match.group(1) if client_address_match else None
            
            # Send 200 OK response
            response = self._generate_subscribe_response(message)
            
            if self.transport == "udp" and client_address:
                try:
                    # Extract port from Via header
                    port_match = re.search(r":(\d+);", via_header)
                    port = int(port_match.group(1)) if port_match else 5060
                    
                    log.info(f"[LOCAL-SIP] Sending 200 OK response to {client_address}:{port}")
                    self.server_socket.sendto(response.encode(), (client_address, port))
                except Exception as e:
                    log.error(f"[LOCAL-SIP] Error sending response: {e}")
            
            # Forward to SIP client to send NOTIFY if available
            if self.sip_client:
                log.info("[LOCAL-SIP] Forwarding subscription to main SIP handler for NOTIFY")
                self.sip_client.handle_catalog_subscription(message)
            else:
                log.warning("[LOCAL-SIP] No SIP client available to handle subscription")
                
        except Exception as e:
            log.error(f"[LOCAL-SIP] Error handling catalog subscription: {e}")
    
    def _generate_subscribe_response(self, request):
        """Generate a 200 OK response to a SUBSCRIBE request"""
        lines = request.split("\n")
        request_line = lines[0] if lines else "SUBSCRIBE sip:unknown SIP/2.0"
        
        # Extract necessary headers from request
        call_id = None
        from_header = None
        to_header = None
        via_header = None
        cseq = None
        expires = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("Call-ID:"):
                call_id = line
            elif line.startswith("From:"):
                from_header = line
            elif line.startswith("To:"):
                to_header = line
            elif line.startswith("Via:"):
                via_header = line
            elif line.startswith("CSeq:"):
                cseq = line
            elif line.startswith("Expires:"):
                expires = line
        
        # Create response
        response = "SIP/2.0 200 OK\r\n"
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
        if expires:
            response += expires + "\r\n"
            
        # Add event type
        response += "Event: Catalog\r\n"
        
        response += "Content-Length: 0\r\n\r\n"
        
        return response
    
    def _generate_ok_response(self, request):
        """Generate a 200 OK response to an INVITE"""
        lines = request.split("\n")
        request_line = lines[0] if lines else "INVITE sip:unknown SIP/2.0"
        
        # Extract necessary headers from request
        call_id = None
        from_header = None
        to_header = None
        via_header = None
        cseq = None
        
        for line in lines:
            if line.startswith("Call-ID:"):
                call_id = line
            elif line.startswith("From:"):
                from_header = line
            elif line.startswith("To:"):
                to_header = line
            elif line.startswith("Via:"):
                via_header = line
            elif line.startswith("CSeq:"):
                cseq = line
        
        # Create response
        response = "SIP/2.0 200 OK\r\n"
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
        
        response += "Content-Length: 0\r\n\r\n"
        
        return response
    
    def stop(self):
        """Stop the local SIP server"""
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            
        self.server_socket = None
        log.info("[LOCAL-SIP] Server stopped")
    
    def get_port(self):
        """Get the current port number"""
        return self.port


def start_local_sip_server(config_path="config/config.json", sip_client=None):
    """Start a standalone local SIP server for testing"""
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None
    
    # Create and start the server
    server = LocalSIPServer(config, sip_client)
    if server.start():
        return server
    return None


if __name__ == "__main__":
    # Run as standalone server
    print("Starting standalone Local SIP Server for testing...")
    
    def signal_handler(sig, frame):
        print("\nShutting down...")
        if server:
            server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    server = start_local_sip_server()
    if server:
        print(f"Server running on port {server.get_port()} ({server.transport.upper()})")
        print("Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.stop()
    else:
        print("Failed to start server") 