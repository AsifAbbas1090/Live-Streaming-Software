#!/usr/bin/env python3
"""
Live SIP Message Flow Monitor for GB28181 Communication
Real-time monitoring of SIP message exchanges with detailed timing analysis.
"""

import subprocess
import threading
import time
import re
import os
import json
import signal
import select
import queue
from datetime import datetime
from logger import log

class LiveSIPMonitor:
    def __init__(self, config):
        self.config = config
        self.server = config["sip"]["server"]
        self.port = config["sip"]["port"]
        self.device_id = config["sip"]["device_id"]
        self.local_port = config["sip"].get("local_port", 5080)
        
        # Thread-safe monitoring data
        self.monitoring = False
        self.message_queue = queue.Queue()
        self.catalog_queries = []
        self.catalog_responses = []
        self.timing_data = {}
        
        # Monitoring threads
        self.tcpdump_process = None
        self.monitor_threads = []
        
        # Thread locks for data safety
        self.data_lock = threading.Lock()
        
        # Message pattern matching
        self.sip_patterns = {
            'MESSAGE': re.compile(r'MESSAGE\s+sip:', re.IGNORECASE),
            'CATALOG_QUERY': re.compile(r'<CmdType>\s*Catalog\s*</CmdType>', re.IGNORECASE),
            'CATALOG_RESPONSE': re.compile(r'<Response>.*<CmdType>\s*Catalog\s*</CmdType>', re.DOTALL | re.IGNORECASE),
            'SN': re.compile(r'<SN>(\d+)</SN>'),
            'REGISTER': re.compile(r'REGISTER\s+sip:', re.IGNORECASE),
            'OPTIONS': re.compile(r'OPTIONS\s+sip:', re.IGNORECASE),
            'INVITE': re.compile(r'INVITE\s+sip:', re.IGNORECASE),
            'SIP_200': re.compile(r'SIP/2\.0\s+200\s+OK', re.IGNORECASE),
            'SIP_401': re.compile(r'SIP/2\.0\s+401', re.IGNORECASE)
        }

    def start_monitoring(self):
        """Start comprehensive live SIP monitoring"""
        log.info("[LIVE-MON] 🔴 Starting live SIP message flow monitoring...")
        self.monitoring = True
        
        # Start packet capture
        self._start_packet_capture()
        
        # Start message processor
        processor_thread = threading.Thread(target=self._process_messages, daemon=True)
        processor_thread.start()
        self.monitor_threads.append(processor_thread)
        
        # Start timing analyzer
        timing_thread = threading.Thread(target=self._analyze_timing, daemon=True)
        timing_thread.start()
        self.monitor_threads.append(timing_thread)
        
        # Start live reporter
        reporter_thread = threading.Thread(target=self._live_reporter, daemon=True)
        reporter_thread.start()
        self.monitor_threads.append(reporter_thread)
        
        log.info("[LIVE-MON] ✅ Live monitoring started successfully")

    def stop_monitoring(self):
        """Stop live SIP monitoring"""
        log.info("[LIVE-MON] 🔴 Stopping live SIP monitoring...")
        self.monitoring = False
        
        if self.tcpdump_process:
            try:
                self.tcpdump_process.terminate()
                self.tcpdump_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.tcpdump_process.kill()
            except Exception as e:
                log.error(f"[LIVE-MON] Error stopping tcpdump: {e}")
        
        # Wait for threads to finish
        for thread in self.monitor_threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        log.info("[LIVE-MON] ✅ Live monitoring stopped")

    def _start_packet_capture(self):
        """Start packet capture with tcpdump for live SIP monitoring"""
        try:
            # Comprehensive tcpdump command for SIP traffic
            cmd = [
                "tcpdump",
                "-i", "any",
                "-n",
                "-A",  # ASCII output
                "-s", "1500",  # Capture full packets
                "-l",  # Line buffered output
                f"(host {self.server} and port {self.port}) or (port {self.local_port})"
            ]
            
            log.info(f"[LIVE-MON] Starting packet capture: {' '.join(cmd)}")
            
            self.tcpdump_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=0  # Unbuffered for real-time output
            )
            
            # Start reading tcpdump output
            reader_thread = threading.Thread(target=self._read_tcpdump_output, daemon=True)
            reader_thread.start()
            self.monitor_threads.append(reader_thread)
            
            log.info("[LIVE-MON] ✅ Packet capture started successfully")
            
        except FileNotFoundError:
            log.error("[LIVE-MON] ❌ tcpdump not found. Install tcpdump for packet capture.")
        except Exception as e:
            log.error(f"[LIVE-MON] ❌ Failed to start packet capture: {e}")

    def _read_tcpdump_output(self):
        """Read tcpdump output in real-time"""
        if not self.tcpdump_process:
            return
            
        buffer = ""
        
        while self.monitoring and self.tcpdump_process.poll() is None:
            try:
                # Use select for non-blocking read with timeout
                ready, _, _ = select.select([self.tcpdump_process.stdout], [], [], 0.1)
                
                if ready:
                    line = self.tcpdump_process.stdout.readline()
                    if line:
                        buffer += line
                        
                        # Process complete packets (look for SIP message boundaries)
                        if self._is_packet_complete(buffer):
                            self._enqueue_packet(buffer)
                            buffer = ""
                            
            except Exception as e:
                log.error(f"[LIVE-MON] Error reading tcpdump output: {e}")
                break

    def _is_packet_complete(self, buffer):
        """Check if we have a complete SIP packet"""
        # Look for SIP message end patterns
        return any([
            "Content-Length: 0" in buffer and "\r\n\r\n" in buffer,
            "</Query>" in buffer,
            "</Response>" in buffer,
            "SIP/2.0 200 OK" in buffer and "\r\n\r\n" in buffer
        ])

    def _enqueue_packet(self, packet_data):
        """Enqueue captured packet for processing"""
        timestamp = datetime.now()
        packet_info = {
            "timestamp": timestamp,
            "raw_data": packet_data,
            "processed": False
        }
        
        try:
            self.message_queue.put(packet_info, timeout=1)
        except queue.Full:
            log.warning("[LIVE-MON] ⚠️ Message queue full, dropping packet")

    def _process_messages(self):
        """Process captured SIP messages"""
        log.info("[LIVE-MON] 📊 Message processor started")
        
        while self.monitoring:
            try:
                # Get message from queue with timeout
                message = self.message_queue.get(timeout=1)
                self._analyze_sip_message(message)
                
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"[LIVE-MON] Error processing message: {e}")

    def _analyze_sip_message(self, message):
        """Analyze individual SIP message"""
        timestamp = message["timestamp"]
        raw_data = message["raw_data"]
        
        # Determine message type and direction
        message_type = self._classify_message(raw_data)
        direction = self._determine_direction(raw_data)
        
        # Extract key information
        call_id = self._extract_call_id(raw_data)
        sn = self._extract_sn(raw_data)
        
        message_info = {
            "timestamp": timestamp.isoformat(),
            "type": message_type,
            "direction": direction,
            "call_id": call_id,
            "sn": sn,
            "raw_length": len(raw_data)
        }
        
        # Log important messages immediately
        if message_type in ["CATALOG_QUERY", "CATALOG_RESPONSE", "REGISTER"]:
            log.info(f"[LIVE-MON] 📨 {direction} {message_type} (SN: {sn}, Call-ID: {call_id})")
            
        # Store for analysis
        with self.data_lock:
            if message_type == "CATALOG_QUERY":
                self.catalog_queries.append(message_info)
                # Start timing for this query
                if sn:
                    self.timing_data[sn] = {"query_time": timestamp}
                    
            elif message_type == "CATALOG_RESPONSE":
                self.catalog_responses.append(message_info)
                # Complete timing for this response
                if sn and sn in self.timing_data:
                    self.timing_data[sn]["response_time"] = timestamp
                    response_delay = (timestamp - self.timing_data[sn]["query_time"]).total_seconds()
                    self.timing_data[sn]["delay"] = response_delay
                    log.info(f"[LIVE-MON] ⏱️ Catalog query-response cycle: {response_delay:.3f}s (SN: {sn})")

    def _classify_message(self, raw_data):
        """Classify SIP message type"""
        for msg_type, pattern in self.sip_patterns.items():
            if pattern.search(raw_data):
                if msg_type == "MESSAGE":
                    # Check if it's catalog-specific
                    if self.sip_patterns["CATALOG_QUERY"].search(raw_data):
                        return "CATALOG_QUERY"
                    elif self.sip_patterns["CATALOG_RESPONSE"].search(raw_data):
                        return "CATALOG_RESPONSE"
                    else:
                        return "MESSAGE"
                return msg_type
        return "UNKNOWN"

    def _determine_direction(self, raw_data):
        """Determine message direction (incoming/outgoing)"""
        # Look for source/destination indicators in packet
        if f":{self.port} >" in raw_data or f".{self.port} >" in raw_data:
            return "OUTGOING"
        elif f"> {self.server}" in raw_data:
            return "OUTGOING"
        else:
            return "INCOMING"

    def _extract_call_id(self, raw_data):
        """Extract Call-ID from SIP message"""
        call_id_match = re.search(r'Call-ID:\s*([^\r\n]+)', raw_data, re.IGNORECASE)
        return call_id_match.group(1).strip() if call_id_match else None

    def _extract_sn(self, raw_data):
        """Extract SN from XML content"""
        sn_match = self.sip_patterns["SN"].search(raw_data)
        return sn_match.group(1) if sn_match else None

    def _analyze_timing(self):
        """Analyze timing patterns in real-time"""
        log.info("[LIVE-MON] ⏱️ Timing analyzer started")
        
        while self.monitoring:
            time.sleep(5)  # Analyze every 5 seconds
            
            with self.data_lock:
                # Check for timed-out queries
                current_time = datetime.now()
                for sn, timing in self.timing_data.items():
                    if "response_time" not in timing:
                        query_age = (current_time - timing["query_time"]).total_seconds()
                        if query_age > 30:  # 30-second timeout
                            log.warning(f"[LIVE-MON] ⚠️ Catalog query timeout! SN: {sn}, age: {query_age:.1f}s")
                            timing["timeout"] = True

    def _live_reporter(self):
        """Generate live status reports"""
        log.info("[LIVE-MON] 📊 Live reporter started")
        
        report_interval = 30  # Report every 30 seconds
        
        while self.monitoring:
            time.sleep(report_interval)
            
            with self.data_lock:
                queries = len(self.catalog_queries)
                responses = len(self.catalog_responses)
                timeouts = sum(1 for t in self.timing_data.values() if t.get("timeout", False))
                
                if queries > 0 or responses > 0:
                    success_rate = (responses / queries * 100) if queries > 0 else 0
                    avg_delay = sum(t.get("delay", 0) for t in self.timing_data.values() if "delay" in t)
                    avg_delay = avg_delay / len([t for t in self.timing_data.values() if "delay" in t]) if any("delay" in t for t in self.timing_data.values()) else 0
                    
                    log.info(f"[LIVE-MON] 📊 Live Stats: Queries={queries}, Responses={responses}, "
                           f"Success={success_rate:.1f}%, Timeouts={timeouts}, Avg Delay={avg_delay:.3f}s")

    def get_current_stats(self):
        """Get current monitoring statistics"""
        with self.data_lock:
            return {
                "timestamp": datetime.now().isoformat(),
                "queries": len(self.catalog_queries),
                "responses": len(self.catalog_responses),
                "timing_data": dict(self.timing_data),
                "success_rate": len(self.catalog_responses) / len(self.catalog_queries) * 100 if self.catalog_queries else 0
            }

    def generate_live_report(self):
        """Generate comprehensive live monitoring report"""
        stats = self.get_current_stats()
        
        report_file = f"live_sip_monitor_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump({
                "config": {
                    "server": self.server,
                    "port": self.port,
                    "device_id": self.device_id,
                    "local_port": self.local_port
                },
                "stats": stats,
                "catalog_queries": self.catalog_queries,
                "catalog_responses": self.catalog_responses
            }, f, indent=2)
        
        log.info(f"[LIVE-MON] 📊 Live report saved to {report_file}")
        return report_file


if __name__ == "__main__":
    # Standalone test mode
    import sys
    import signal
    
    def signal_handler(sig, frame):
        log.info("[LIVE-MON] Received interrupt signal, stopping...")
        if monitor:
            monitor.stop_monitoring()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    try:
        with open(config_path) as f:
            config = json.load(f)
        
        monitor = LiveSIPMonitor(config)
        monitor.start_monitoring()
        
        log.info("[LIVE-MON] Live monitoring active. Press Ctrl+C to stop...")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        if 'monitor' in locals():
            monitor.stop_monitoring()
    except Exception as e:
        log.error(f"[LIVE-MON] Error: {e}")
        sys.exit(1) 