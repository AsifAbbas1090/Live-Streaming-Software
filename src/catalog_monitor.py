"""
Catalog Query Monitor for GB28181 Communication
This tool specifically monitors catalog query/response cycles to identify timing issues.
"""

import subprocess
import time
import threading
import re
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from logger import log

class CatalogMonitor:
    def __init__(self, config):
        self.config = config
        self.server = config["sip"]["server"]
        self.port = config["sip"]["port"]
        self.device_id = config["sip"]["device_id"]
        self.username = config["sip"]["username"]
        
        self.monitoring = False
        self.catalog_queries = []  # Track incoming queries
        self.catalog_responses = []  # Track outgoing responses
        self.query_response_pairs = []  # Track complete query-response cycles
        
        # Enhanced SIP monitoring with netstat integration
        self.sip_monitor = None
        
    def start_monitoring(self):
        """Start catalog-specific monitoring"""
        log.info("[CATALOG-MON] Starting catalog query monitoring...")
        self.monitoring = True
        
        # Start SIP message monitoring specifically for catalog queries
        monitor_thread = threading.Thread(target=self._monitor_catalog_messages, daemon=True)
        monitor_thread.start()
        
        # Start network monitoring
        network_thread = threading.Thread(target=self._monitor_network_activity, daemon=True)
        network_thread.start()
        
    def stop_monitoring(self):
        """Stop catalog monitoring"""
        log.info("[CATALOG-MON] Stopping catalog query monitoring...")
        self.monitoring = False
        
    def _monitor_catalog_messages(self):
        """Monitor for catalog-specific SIP messages"""
        log.info("[CATALOG-MON] Catalog message monitoring started")
        
        # Use netstat to monitor SIP connections
        while self.monitoring:
            try:
                self._check_sip_connections()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                log.error(f"[CATALOG-MON] Error in message monitoring: {e}")
                time.sleep(1)
                
    def _monitor_network_activity(self):
        """Monitor network activity on SIP port"""
        while self.monitoring:
            try:
                # Check for active connections to the SIP server
                cmd = ["netstat", "-an"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if f":{self.port}" in line and self.server in line:
                            log.debug(f"[CATALOG-MON] SIP connection: {line.strip()}")
                            
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                log.debug(f"[CATALOG-MON] Network monitoring error: {e}")
                time.sleep(5)
                
    def _check_sip_connections(self):
        """Check current SIP connections"""
        try:
            cmd = ["ss", "-tuln"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{self.port}" in line:
                        log.debug(f"[CATALOG-MON] SIP port status: {line.strip()}")
                        
        except FileNotFoundError:
            # Try netstat as fallback
            try:
                cmd = ["netstat", "-tuln"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if f":{self.port}" in line:
                            log.debug(f"[CATALOG-MON] SIP port status: {line.strip()}")
            except:
                pass
        except Exception as e:
            log.debug(f"[CATALOG-MON] Connection check error: {e}")
            
    def simulate_catalog_query(self):
        """Simulate receiving a catalog query to test response generation"""
        log.info("[CATALOG-MON] Simulating catalog query...")
        
        # Create a realistic catalog query like WVP would send
        sn = int(time.time()) % 1000000  # Use timestamp for unique SN
        test_query = f"""MESSAGE sip:{self.device_id}@{self.server}:{self.port} SIP/2.0
Via: SIP/2.0/UDP {self.server}:{self.port};branch=z9hG4bK-test123
From: <sip:{self.server}:{self.port}>;tag=test123
To: <sip:{self.device_id}@{self.server}:{self.port}>
Call-ID: test-catalog-{sn}@{self.server}
CSeq: 1 MESSAGE
Content-Type: Application/MANSCDP+xml
Content-Length: 150

<?xml version="1.0" encoding="GB2312"?>
<Query>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
</Query>"""
        
        log.info(f"[CATALOG-MON] Simulated query with SN: {sn}")
        
        # Track this as a query
        query_info = {
            "timestamp": datetime.now().isoformat(),
            "sn": str(sn),
            "device_id": self.device_id,
            "source": "simulation"
        }
        self.catalog_queries.append(query_info)
        
        # Test the response generation timing
        start_time = time.time()
        
        try:
            # Import and test the SIP handler
            from sip_handler_pjsip import SIPClient
            test_client = SIPClient(self.config)
            
            # Generate device catalog first
            test_client.generate_device_catalog()
            catalog_gen_time = time.time() - start_time
            
            # Handle the catalog query
            response = test_client.handle_catalog_query(test_query)
            total_time = time.time() - start_time
            
            response_info = {
                "timestamp": datetime.now().isoformat(),
                "sn": str(sn),
                "catalog_gen_time": catalog_gen_time,
                "total_time": total_time,
                "response_length": len(response) if response else 0,
                "success": response is not None
            }
            self.catalog_responses.append(response_info)
            
            log.info(f"[CATALOG-MON] Response generation: {catalog_gen_time:.3f}s catalog, {total_time:.3f}s total")
            
            if response:
                # Parse the response to verify structure
                self._analyze_catalog_response(response, sn)
            else:
                log.error("[CATALOG-MON] No response generated!")
                
        except Exception as e:
            log.error(f"[CATALOG-MON] Error in simulation: {e}")
            import traceback
            log.error(f"[CATALOG-MON] Traceback: {traceback.format_exc()}")
            
    def _analyze_catalog_response(self, xml_response, sn):
        """Analyze the structure and content of a catalog response"""
        try:
            # Parse XML
            root = ET.fromstring(xml_response)
            
            # Extract key information
            cmd_type = root.find('CmdType').text if root.find('CmdType') is not None else "Unknown"
            response_sn = root.find('SN').text if root.find('SN') is not None else "Unknown"
            device_id = root.find('DeviceID').text if root.find('DeviceID') is not None else "Unknown"
            result = root.find('Result').text if root.find('Result') is not None else "Unknown"
            sum_num = root.find('SumNum').text if root.find('SumNum') is not None else "0"
            
            device_list = root.find('DeviceList')
            actual_devices = len(device_list.findall('Item')) if device_list is not None else 0
            
            log.info(f"[CATALOG-MON] Response Analysis:")
            log.info(f"  CmdType: {cmd_type}")
            log.info(f"  SN: {response_sn} (expected: {sn})")
            log.info(f"  DeviceID: {device_id}")
            log.info(f"  Result: {result}")
            log.info(f"  SumNum: {sum_num}")
            log.info(f"  Actual Items: {actual_devices}")
            
            # Check for potential issues
            if str(response_sn) != str(sn):
                log.warning(f"[CATALOG-MON] ⚠️ SN mismatch! Expected {sn}, got {response_sn}")
                
            if result != "OK":
                log.warning(f"[CATALOG-MON] ⚠️ Non-OK result: {result}")
                
            if int(sum_num) != actual_devices:
                log.warning(f"[CATALOG-MON] ⚠️ Device count mismatch! SumNum={sum_num}, actual={actual_devices}")
                
            if actual_devices == 0:
                log.error(f"[CATALOG-MON] ❌ No devices in catalog response!")
                
            # Save response for inspection
            filename = f"catalog_response_{sn}.xml"
            with open(filename, 'w') as f:
                f.write(xml_response)
            log.info(f"[CATALOG-MON] Saved response to {filename}")
            
        except ET.ParseError as e:
            log.error(f"[CATALOG-MON] ❌ Invalid XML in response: {e}")
        except Exception as e:
            log.error(f"[CATALOG-MON] Error analyzing response: {e}")
            
    def test_direct_pjsua_response(self):
        """Test sending a catalog response directly via pjsua"""
        log.info("[CATALOG-MON] Testing direct pjsua catalog response...")
        
        sn = int(time.time()) % 1000000
        
        # Create a proper catalog response XML
        xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>1</SumNum>
  <DeviceList Num="1">
    <Item>
      <DeviceID>{self.device_id[:10]}1320000001</DeviceID>
      <Name>Direct Test Camera</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Direct Test</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{self.device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
  </DeviceList>
</Response>"""
        
        # Test using the SIP sender
        try:
            from gb28181_sip_sender import GB28181SIPSender
            sender = GB28181SIPSender(self.config)
            sender.start()
            
            target_uri = f"sip:{self.server}:{self.port}"
            
            start_time = time.time()
            success = sender.send_catalog(xml_content, target_uri)
            send_time = time.time() - start_time
            
            log.info(f"[CATALOG-MON] Direct send result: {success}, took {send_time:.3f}s")
            
            # Give some time for the message to be sent
            time.sleep(2)
            sender.stop()
            
        except Exception as e:
            log.error(f"[CATALOG-MON] Error in direct send test: {e}")
            
    def test_response_timing_variations(self):
        """Test catalog response with different configurations to identify timing issues"""
        log.info("[CATALOG-MON] Testing response timing variations...")
        
        # Test 1: Empty catalog
        self._test_empty_catalog()
        
        # Test 2: Small catalog (1 device)
        self._test_small_catalog()
        
        # Test 3: Medium catalog (10 devices)
        self._test_medium_catalog()
        
        # Test 4: Large catalog (100 devices) 
        self._test_large_catalog()
        
    def _test_empty_catalog(self):
        """Test with empty catalog"""
        log.info("[CATALOG-MON] Testing empty catalog response...")
        
        sn = int(time.time()) % 1000000
        xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>0</SumNum>
  <DeviceList Num="0">
  </DeviceList>
</Response>"""
        
        self._time_response_send(xml_content, "empty")
        
    def _test_small_catalog(self):
        """Test with small catalog (1 device)"""
        log.info("[CATALOG-MON] Testing small catalog response...")
        
        sn = int(time.time()) % 1000000
        xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>1</SumNum>
  <DeviceList Num="1">
    <Item>
      <DeviceID>{self.device_id[:10]}1320000001</DeviceID>
      <Name>Small Test Camera</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Small Test</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{self.device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>
  </DeviceList>
</Response>"""
        
        self._time_response_send(xml_content, "small")
        
    def _test_medium_catalog(self):
        """Test with medium catalog (10 devices)"""
        log.info("[CATALOG-MON] Testing medium catalog response...")
        
        sn = int(time.time()) % 1000000
        devices = []
        
        for i in range(1, 11):
            device_xml = f"""    <Item>
      <DeviceID>{self.device_id[:10]}132{i:07d}</DeviceID>
      <Name>Medium Test Camera {i}</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Medium Test</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{self.device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>"""
            devices.append(device_xml)
            
        xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>10</SumNum>
  <DeviceList Num="10">
{chr(10).join(devices)}
  </DeviceList>
</Response>"""
        
        self._time_response_send(xml_content, "medium")
        
    def _test_large_catalog(self):
        """Test with large catalog (100 devices)"""
        log.info("[CATALOG-MON] Testing large catalog response...")
        
        sn = int(time.time()) % 1000000
        devices = []
        
        for i in range(1, 101):
            device_xml = f"""    <Item>
      <DeviceID>{self.device_id[:10]}132{i:07d}</DeviceID>
      <Name>Large Test Camera {i}</Name>
      <Manufacturer>GB28181-Restreamer</Manufacturer>
      <Model>Large Test</Model>
      <Owner>gb28181-restreamer</Owner>
      <CivilCode>340200</CivilCode>
      <Block>34020000</Block>
      <Address>Local Stream</Address>
      <Parental>0</Parental>
      <ParentID>{self.device_id}</ParentID>
      <SafetyWay>0</SafetyWay>
      <RegisterWay>1</RegisterWay>
      <Secrecy>0</Secrecy>
      <Status>ON</Status>
      <Longitude>116.307629</Longitude>
      <Latitude>39.984094</Latitude>
    </Item>"""
            devices.append(device_xml)
            
        xml_content = f"""<?xml version="1.0" encoding="GB2312"?>
<Response>
  <CmdType>Catalog</CmdType>
  <SN>{sn}</SN>
  <DeviceID>{self.device_id}</DeviceID>
  <Result>OK</Result>
  <SumNum>100</SumNum>
  <DeviceList Num="100">
{chr(10).join(devices)}
  </DeviceList>
</Response>"""
        
        self._time_response_send(xml_content, "large")
        
    def _time_response_send(self, xml_content, test_type):
        """Time the sending of a catalog response"""
        try:
            from gb28181_sip_sender import GB28181SIPSender
            sender = GB28181SIPSender(self.config)
            sender.start()
            
            target_uri = f"sip:{self.server}:{self.port}"
            
            start_time = time.time()
            success = sender.send_catalog(xml_content, target_uri)
            send_time = time.time() - start_time
            
            log.info(f"[CATALOG-MON] {test_type} catalog send: {success}, {send_time:.3f}s, {len(xml_content)} bytes")
            
            time.sleep(1)  # Brief pause between tests
            sender.stop()
            
        except Exception as e:
            log.error(f"[CATALOG-MON] Error in {test_type} catalog test: {e}")
            
    def run_comprehensive_catalog_tests(self):
        """Run all catalog-related tests"""
        log.info("[CATALOG-MON] 🧪 Starting comprehensive catalog testing...")
        
        # Test 1: Simulate catalog query
        self.simulate_catalog_query()
        time.sleep(2)
        
        # Test 2: Direct pjsua response
        self.test_direct_pjsua_response()
        time.sleep(2)
        
        # Test 3: Response timing variations
        self.test_response_timing_variations()
        
        # Generate summary report
        self.generate_catalog_report()
        
    def generate_catalog_report(self):
        """Generate a catalog-specific diagnostic report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "server": self.server,
                "port": self.port,
                "device_id": self.device_id,
                "username": self.username
            },
            "catalog_queries": self.catalog_queries,
            "catalog_responses": self.catalog_responses,
            "query_response_pairs": self.query_response_pairs
        }
        
        with open("catalog_diagnostics_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        log.info("[CATALOG-MON] Catalog diagnostics report saved to catalog_diagnostics_report.json")


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
        
        monitor = CatalogMonitor(config)
        monitor.start_monitoring()
        
        # Run tests after a brief startup delay
        time.sleep(1)
        monitor.run_comprehensive_catalog_tests()
        
        # Keep monitoring for a bit
        time.sleep(10)
        monitor.stop_monitoring()
        
    except Exception as e:
        print(f"Error running catalog monitor: {e}")
        import traceback
        print(traceback.format_exc()) 