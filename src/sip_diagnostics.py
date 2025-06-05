# src/sip_diagnostics.py
"""
SIP Diagnostics Tool for GB28181 Communication
This tool monitors and diagnoses SIP message exchanges with the WVP platform
to identify why catalog queries are timing out.
"""

import subprocess
import time
import threading
import re
import os
import json
from datetime import datetime
from logger import log

class SIPDiagnostics:
    def __init__(self, config):
        self.config = config
        self.server = config["sip"]["server"]
        self.port = config["sip"]["port"]
        self.device_id = config["sip"]["device_id"]
        self.username = config["sip"]["username"]
        self.local_port = config["sip"].get("local_port", 5080)
        
        self.monitoring = False
        self.message_log = []
        self.packet_capture = None
        
    def start_monitoring(self):
        """Start comprehensive SIP monitoring"""
        log.info("[DIAG] Starting SIP diagnostics monitoring...")
        self.monitoring = True
        
        # Start packet capture if tcpdump is available
        self._start_packet_capture()
        
        # Start PJSUA logging for our device
        self._start_pjsua_logging()
        
        # Monitor for incoming messages
        monitor_thread = threading.Thread(target=self._monitor_sip_traffic, daemon=True)
        monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop SIP monitoring"""
        log.info("[DIAG] Stopping SIP diagnostics monitoring...")
        self.monitoring = False
        
        if self.packet_capture:
            self.packet_capture.terminate()
            
    def _start_packet_capture(self):
        """Start packet capture using tcpdump"""
        try:
            cmd = [
                "tcpdump", 
                "-i", "any",
                "-n",
                f"host {self.server} and port {self.port}",
                "-A"  # Print packet contents in ASCII
            ]
            
            self.packet_capture = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            log.info(f"[DIAG] Started packet capture for {self.server}:{self.port}")
            
        except FileNotFoundError:
            log.warning("[DIAG] tcpdump not available, skipping packet capture")
        except Exception as e:
            log.error(f"[DIAG] Error starting packet capture: {e}")
            
    def _start_pjsua_logging(self):
        """Start detailed PJSUA logging"""
        log.info("[DIAG] Starting detailed PJSUA logging...")
        
    def _monitor_sip_traffic(self):
        """Monitor SIP traffic and analyze patterns"""
        log.info("[DIAG] SIP traffic monitoring started")
        
        while self.monitoring:
            if self.packet_capture and self.packet_capture.poll() is None:
                try:
                    line = self.packet_capture.stdout.readline()
                    if line:
                        self._analyze_packet(line.strip())
                except Exception as e:
                    log.error(f"[DIAG] Error reading packet data: {e}")
            
            time.sleep(0.1)
            
    def _analyze_packet(self, packet_line):
        """Analyze captured packet for SIP messages"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        # Look for SIP messages
        if "MESSAGE" in packet_line:
            log.info(f"[DIAG] {timestamp} SIP MESSAGE detected: {packet_line}")
            self._extract_message_details(packet_line)
            
        elif "200 OK" in packet_line:
            log.info(f"[DIAG] {timestamp} SIP 200 OK detected: {packet_line}")
            
        elif "REGISTER" in packet_line:
            log.info(f"[DIAG] {timestamp} SIP REGISTER detected: {packet_line}")
            
        elif "INVITE" in packet_line:
            log.info(f"[DIAG] {timestamp} SIP INVITE detected: {packet_line}")
            
        elif "Catalog" in packet_line:
            log.info(f"[DIAG] {timestamp} Catalog query detected: {packet_line}")
            
    def _extract_message_details(self, message_line):
        """Extract details from SIP MESSAGE"""
        # This will be enhanced to parse XML content from messages
        message_info = {
            "timestamp": datetime.now().isoformat(),
            "content": message_line,
            "direction": "unknown"
        }
        
        self.message_log.append(message_info)
        
    def test_catalog_response(self):
        """Test catalog response generation and timing"""
        log.info("[DIAG] Testing catalog response generation...")
        
        # Simulate a catalog query
        test_query = """<?xml version="1.0" encoding="GB2312"?>
<Query>
  <CmdType>Catalog</CmdType>
  <SN>123456</SN>
  <DeviceID>{}</DeviceID>
</Query>""".format(self.device_id)
        
        start_time = time.time()
        
        # Test the catalog generation (assuming we have access to SIP client)
        try:
            from sip_handler_pjsip import SIPClient
            test_client = SIPClient(self.config)
            test_client.generate_device_catalog()
            
            response = test_client.handle_catalog_query(test_query)
            generation_time = time.time() - start_time
            
            log.info(f"[DIAG] Catalog generation took {generation_time:.3f} seconds")
            
            if response:
                log.info(f"[DIAG] Generated catalog response length: {len(response)} bytes")
                # Save to file for inspection
                with open("diagnostic_catalog.xml", "w") as f:
                    f.write(response)
                log.info("[DIAG] Saved catalog response to diagnostic_catalog.xml")
            else:
                log.error("[DIAG] Failed to generate catalog response")
                
        except Exception as e:
            log.error(f"[DIAG] Error testing catalog response: {e}")
            
    def test_sip_connectivity(self):
        """Test basic SIP connectivity to the platform"""
        log.info(f"[DIAG] Testing SIP connectivity to {self.server}:{self.port}")
        
        # Test 1: Network connectivity
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            result = s.connect_ex((self.server, self.port))
            s.close()
            
            if result == 0:
                log.info("[DIAG] ✅ TCP connectivity to SIP server is OK")
            else:
                log.error(f"[DIAG] ❌ TCP connectivity failed: {result}")
        except Exception as e:
            log.error(f"[DIAG] ❌ Network connectivity test failed: {e}")
            
        # Test 2: UDP connectivity (more important for SIP)
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(5)
            s.sendto(b"test", (self.server, self.port))
            s.close()
            log.info("[DIAG] ✅ UDP connectivity to SIP server is OK")
        except Exception as e:
            log.error(f"[DIAG] ❌ UDP connectivity test failed: {e}")
            
    def test_pjsua_message_sending(self):
        """Test direct message sending using pjsua"""
        log.info("[DIAG] Testing direct SIP MESSAGE sending via pjsua")
        
        test_xml = """<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>123456</SN>
  <DeviceID>{}</DeviceID>
  <Result>OK</Result>
  <SumNum>1</SumNum>
  <DeviceList Num="1">
    <Item>
      <DeviceID>{}1320000001</DeviceID>
      <Name>Test Camera</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Test Model</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
  </DeviceList>
</Response>""".format(self.device_id, self.device_id[:10], self.device_id)
        
        # Save test XML to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(test_xml)
            temp_file = f.name
            
        try:
            target_uri = f"sip:{self.server}:{self.port}"
            
            cmd = [
                "pjsua",
                "--id", f"sip:{self.username}@{self.server}",
                "--realm", "*",
                "--username", self.username,
                "--password", self.config["sip"]["password"],
                "--local-port", "0",  # Random port
                "--null-audio",
                "--duration", "10",
                "--auto-quit",
                "--send-message", target_uri,
                "--message-content-type", "Application/MANSCDP+xml",
                "--message-content", f"@{temp_file}"
            ]
            
            log.info(f"[DIAG] Sending test message to {target_uri}")
            start_time = time.time()
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=15
            )
            
            send_time = time.time() - start_time
            log.info(f"[DIAG] Message send attempt took {send_time:.3f} seconds")
            
            if result.returncode == 0:
                log.info("[DIAG] ✅ Test message sent successfully")
                log.debug(f"[DIAG] PJSUA output: {result.stdout}")
            else:
                log.error(f"[DIAG] ❌ Test message failed: {result.stdout}")
                
        except subprocess.TimeoutExpired:
            log.error("[DIAG] ❌ Test message sending timed out")
        except Exception as e:
            log.error(f"[DIAG] ❌ Error sending test message: {e}")
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
                
    def analyze_timing_issues(self):
        """Analyze potential timing issues in the SIP communication"""
        log.info("[DIAG] Analyzing timing issues...")
        
        # Test catalog generation speed
        start_time = time.time()
        try:
            from file_scanner import get_video_catalog
            videos = get_video_catalog()
            catalog_time = time.time() - start_time
            log.info(f"[DIAG] Video catalog scan took {catalog_time:.3f} seconds ({len(videos)} videos)")
        except Exception as e:
            log.error(f"[DIAG] Error scanning video catalog: {e}")
            
        # Test XML generation speed
        start_time = time.time()
        try:
            from gb28181_xml import format_catalog_response
            test_channels = {
                f"{self.device_id[:10]}1320000001": {
                    'name': 'Test Camera',
                    'manufacturer': 'GB28181-Restreamer',
                    'model': 'Test Model',
                    'status': 'ON',
                    'parent_id': self.device_id
                }
            }
            xml_response = format_catalog_response(self.device_id, test_channels)
            xml_time = time.time() - start_time
            log.info(f"[DIAG] XML generation took {xml_time:.3f} seconds ({len(xml_response)} bytes)")
        except Exception as e:
            log.error(f"[DIAG] Error generating XML: {e}")
            
    def run_comprehensive_diagnostics(self):
        """Run all diagnostic tests"""
        log.info("[DIAG] 🔍 Starting comprehensive SIP diagnostics...")
        
        # Basic connectivity tests
        self.test_sip_connectivity()
        
        # Timing analysis
        self.analyze_timing_issues()
        
        # Catalog response test
        self.test_catalog_response()
        
        # Direct message sending test
        self.test_pjsua_message_sending()
        
        log.info("[DIAG] 📊 Diagnostics complete. Check logs for results.")
        
    def generate_report(self):
        """Generate a diagnostic report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "server": self.server,
                "port": self.port,
                "device_id": self.device_id,
                "username": self.username,
                "local_port": self.local_port
            },
            "messages": self.message_log
        }
        
        with open("sip_diagnostics_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        log.info("[DIAG] Diagnostic report saved to sip_diagnostics_report.json")


if __name__ == "__main__":
    # For standalone testing
    import sys
    import os
    
    # Add src directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Load config
    import json
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        diagnostics = SIPDiagnostics(config)
        diagnostics.run_comprehensive_diagnostics()
        diagnostics.generate_report()
        
    except Exception as e:
        print(f"Error running diagnostics: {e}") 