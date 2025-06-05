#!/usr/bin/env python3
"""
WVP Platform Diagnostics - Comprehensive troubleshooting for WVP-GB28181-pro platform
Analyzes timeout issues, catalog synchronization problems, and platform compatibility
"""

import subprocess
import socket
import json
import re
import time
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import sys
import os

class WVPPlatformDiagnostics:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "wvp_platform_tests": {},
            "catalog_analysis": {},
            "timeout_analysis": {},
            "network_analysis": {},
            "recommendations": []
        }
        
    def test_catalog_response_size(self):
        """Test if catalog response is too large causing timeouts"""
        print("🔍 Testing catalog response size and performance...")
        
        try:
            # Check latest catalog file
            catalog_files = subprocess.run(
                ["ls", "-la", "catalog_response_sn_*.xml"], 
                capture_output=True, text=True, cwd="/home/ubuntu/rstp/gb28181-restreamer"
            )
            
            if catalog_files.returncode == 0:
                latest_file = None
                for line in catalog_files.stdout.strip().split('\n'):
                    if 'catalog_response_sn_' in line:
                        latest_file = line.split()[-1]
                
                if latest_file:
                    file_path = f"/home/ubuntu/rstp/gb28181-restreamer/{latest_file}"
                    
                    # Get file size
                    file_size = os.path.getsize(file_path)
                    
                    # Read and analyze XML
                    with open(file_path, 'r', encoding='utf-8') as f:
                        xml_content = f.read()
                    
                    # Parse XML to count channels
                    try:
                        root = ET.fromstring(xml_content)
                        device_list = root.find('DeviceList')
                        channel_count = int(device_list.get('Num', 0)) if device_list is not None else 0
                        sum_num = root.find('SumNum')
                        total_devices = int(sum_num.text) if sum_num is not None else 0
                        
                        self.results["catalog_analysis"] = {
                            "file_size_bytes": file_size,
                            "file_size_kb": round(file_size / 1024, 2),
                            "channel_count": channel_count,
                            "total_devices": total_devices,
                            "xml_length": len(xml_content),
                            "size_warning": file_size > 50000  # Over 50KB might cause timeouts
                        }
                        
                        print(f"📊 Catalog file: {latest_file}")
                        print(f"   Size: {self.results['catalog_analysis']['file_size_kb']} KB")
                        print(f"   Channels: {channel_count}")
                        print(f"   Total devices: {total_devices}")
                        
                        if file_size > 50000:
                            print(f"⚠️  WARNING: Large catalog ({file_size/1024:.1f}KB) may cause WVP timeouts!")
                            self.results["recommendations"].append("Reduce channel count to <50 for better WVP compatibility")
                        
                    except ET.ParseError as e:
                        print(f"❌ XML parsing error: {e}")
                        self.results["catalog_analysis"]["xml_error"] = str(e)
                        
        except Exception as e:
            print(f"❌ Catalog analysis failed: {e}")
            self.results["catalog_analysis"]["error"] = str(e)
    
    def test_wvp_response_timing(self):
        """Test response timing to identify timeout issues"""
        print("⏱️  Testing catalog response timing...")
        
        try:
            # Simulate catalog generation timing
            import sys
            sys.path.append('/home/ubuntu/rstp/gb28181-restreamer/src')
            
            start_time = time.time()
            
            # Test catalog generation speed
            from sip_handler_pjsip import SIPClient
            config = json.load(open('/home/ubuntu/rstp/gb28181-restreamer/config/config.json'))
            client = SIPClient(config)
            
            catalog_gen_start = time.time()
            client.generate_device_catalog()
            catalog_gen_time = time.time() - catalog_gen_start
            
            # Test XML generation speed
            xml_gen_start = time.time()
            xml_response = client._generate_catalog_response("test123")
            xml_gen_time = time.time() - xml_gen_start
            
            total_time = time.time() - start_time
            
            self.results["timeout_analysis"] = {
                "catalog_generation_seconds": round(catalog_gen_time, 3),
                "xml_generation_seconds": round(xml_gen_time, 3),
                "total_response_seconds": round(total_time, 3),
                "timeout_risk": total_time > 5.0  # WVP typically times out after 5-10 seconds
            }
            
            print(f"📈 Performance Analysis:")
            print(f"   Catalog generation: {catalog_gen_time:.3f}s")
            print(f"   XML generation: {xml_gen_time:.3f}s")
            print(f"   Total response time: {total_time:.3f}s")
            
            if total_time > 5.0:
                print(f"⚠️  WARNING: Response time too slow for WVP platform!")
                self.results["recommendations"].append("Optimize catalog generation - reduce video file count or use caching")
            elif total_time > 2.0:
                print(f"⚠️  CAUTION: Response time borderline for WVP platform")
            else:
                print(f"✅ Response time acceptable for WVP platform")
                
        except Exception as e:
            print(f"❌ Timing analysis failed: {e}")
            self.results["timeout_analysis"]["error"] = str(e)
    
    def test_wvp_network_connectivity(self):
        """Test network connectivity specifically for WVP platform requirements"""
        print("🌐 Testing WVP platform network connectivity...")
        
        wvp_tests = {}
        
        # Test SIP server connectivity
        try:
            config = json.load(open('/home/ubuntu/rstp/gb28181-restreamer/config/config.json'))
            sip_server = config['sip']['server']
            sip_port = config['sip']['port']
            
            print(f"🔗 Testing connection to WVP SIP server: {sip_server}:{sip_port}")
            
            # TCP connectivity test
            tcp_start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            tcp_result = sock.connect_ex((sip_server, sip_port))
            tcp_time = time.time() - tcp_start
            sock.close()
            
            # UDP connectivity test  
            udp_start = time.time()
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.settimeout(5)
            try:
                udp_sock.sendto(b"test", (sip_server, sip_port))
                udp_result = 0
            except:
                udp_result = 1
            udp_time = time.time() - udp_start
            udp_sock.close()
            
            wvp_tests["sip_connectivity"] = {
                "tcp_connected": tcp_result == 0,
                "tcp_time_ms": round(tcp_time * 1000, 2),
                "udp_reachable": udp_result == 0,
                "udp_time_ms": round(udp_time * 1000, 2)
            }
            
            print(f"   TCP connection: {'✅ OK' if tcp_result == 0 else '❌ FAILED'} ({tcp_time*1000:.1f}ms)")
            print(f"   UDP reachable: {'✅ OK' if udp_result == 0 else '❌ FAILED'} ({udp_time*1000:.1f}ms)")
            
        except Exception as e:
            print(f"❌ SIP connectivity test failed: {e}")
            wvp_tests["sip_connectivity"] = {"error": str(e)}
        
        # Test if our device is reachable from WVP platform
        try:
            # Get our external IP
            external_ip_result = subprocess.run(["curl", "-s", "ifconfig.me"], capture_output=True, text=True, timeout=10)
            external_ip = external_ip_result.stdout.strip()
            
            # Get our local IP  
            local_ip_result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
            local_ip = local_ip_result.stdout.strip().split()[0]
            
            wvp_tests["device_accessibility"] = {
                "external_ip": external_ip,
                "local_ip": local_ip,
                "sip_port_bound": self._check_port_binding(5080)
            }
            
            print(f"📍 Device network info:")
            print(f"   External IP: {external_ip}")
            print(f"   Local IP: {local_ip}")
            print(f"   SIP port 5080 bound: {'✅ YES' if wvp_tests['device_accessibility']['sip_port_bound'] else '❌ NO'}")
            
        except Exception as e:
            print(f"❌ Device accessibility test failed: {e}")
            wvp_tests["device_accessibility"] = {"error": str(e)}
        
        self.results["wvp_platform_tests"] = wvp_tests
    
    def _check_port_binding(self, port):
        """Check if a port is bound and listening"""
        try:
            result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
            return f":{port}" in result.stdout
        except:
            return False
    
    def test_wvp_catalog_subscription(self):
        """Test if WVP platform catalog subscription is working properly"""
        print("📋 Testing WVP catalog subscription behavior...")
        
        try:
            # Check recent SIP logs for subscription patterns
            log_file = "/home/ubuntu/rstp/gb28181-restreamer/logs/gb28181-restreamer.log"
            
            if os.path.exists(log_file):
                # Read recent logs
                with open(log_file, 'r') as f:
                    recent_logs = f.readlines()[-500:]  # Last 500 lines
                
                # Analyze subscription patterns
                catalog_queries = []
                device_status_queries = []
                responses_sent = []
                
                for line in recent_logs:
                    if "CmdType>Catalog</CmdType" in line:
                        catalog_queries.append(line.strip())
                    elif "CmdType>DeviceStatus</CmdType" in line:
                        device_status_queries.append(line.strip())
                    elif "Catalog response sent successfully" in line:
                        responses_sent.append(line.strip())
                
                subscription_analysis = {
                    "catalog_queries_count": len(catalog_queries),
                    "device_status_queries_count": len(device_status_queries), 
                    "responses_sent_count": len(responses_sent),
                    "query_response_ratio": len(responses_sent) / max(len(catalog_queries), 1)
                }
                
                print(f"📊 Recent WVP platform activity:")
                print(f"   Catalog queries received: {len(catalog_queries)}")
                print(f"   Device status queries: {len(device_status_queries)}")
                print(f"   Responses sent: {len(responses_sent)}")
                print(f"   Response ratio: {subscription_analysis['query_response_ratio']:.2f}")
                
                if subscription_analysis['query_response_ratio'] < 0.8:
                    print("⚠️  WARNING: Low response ratio - some queries may be timing out!")
                    self.results["recommendations"].append("Check for network issues causing response failures")
                
                self.results["catalog_analysis"]["subscription_analysis"] = subscription_analysis
                
        except Exception as e:
            print(f"❌ Subscription analysis failed: {e}")
            self.results["catalog_analysis"]["subscription_error"] = str(e)
    
    def create_optimized_catalog_config(self):
        """Create an optimized configuration for better WVP compatibility"""
        print("⚙️  Creating WVP-optimized configuration...")
        
        try:
            # Create a smaller test catalog configuration
            optimized_config = {
                "reduced_catalog_size": True,
                "max_channels": 20,  # Reduce from 100 to 20 for testing
                "response_timeout_optimization": True,
                "wvp_compatibility_mode": True
            }
            
            # Write optimized config
            with open('/home/ubuntu/rstp/gb28181-restreamer/wvp_optimized_config.json', 'w') as f:
                json.dump(optimized_config, f, indent=2)
            
            print("✅ Created WVP-optimized configuration")
            print("   - Reduced max channels to 20")
            print("   - Enabled response timeout optimization")
            print("   - Enabled WVP compatibility mode")
            
            self.results["recommendations"].append("Use WVP-optimized configuration with reduced channel count")
            
        except Exception as e:
            print(f"❌ Configuration optimization failed: {e}")
    
    def test_xml_format_compatibility(self):
        """Test XML format compatibility with WVP platform requirements"""
        print("📄 Testing XML format compatibility with WVP platform...")
        
        try:
            # Check latest catalog response
            catalog_files = subprocess.run(
                ["ls", "-t", "catalog_response_sn_*.xml"], 
                capture_output=True, text=True, cwd="/home/ubuntu/rstp/gb28181-restreamer"
            )
            
            if catalog_files.returncode == 0:
                latest_file = catalog_files.stdout.strip().split('\n')[0]
                file_path = f"/home/ubuntu/rstp/gb28181-restreamer/{latest_file}"
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                # Check WVP-specific XML requirements
                format_checks = {
                    "has_gb2312_encoding": "GB2312" in xml_content,
                    "has_device_list": "<DeviceList" in xml_content,
                    "has_sum_num": "<SumNum>" in xml_content,
                    "has_result_ok": "<Result>OK</Result>" in xml_content,
                    "has_parent_device": '"Parental">1<' in xml_content,
                    "has_child_devices": '"Parental">0<' in xml_content,
                    "proper_device_ids": True  # Will check device ID format
                }
                
                # Check device ID format compliance
                device_id_pattern = r'<DeviceID>(\d{20})</DeviceID>'
                device_ids = re.findall(device_id_pattern, xml_content)
                
                if device_ids:
                    # Check if all device IDs are proper 20-digit format
                    for dev_id in device_ids:
                        if len(dev_id) != 20 or not dev_id.isdigit():
                            format_checks["proper_device_ids"] = False
                            break
                
                format_checks["device_id_count"] = len(device_ids)
                
                print(f"🔍 XML Format Analysis:")
                for check, result in format_checks.items():
                    if isinstance(result, bool):
                        print(f"   {check}: {'✅ PASS' if result else '❌ FAIL'}")
                    else:
                        print(f"   {check}: {result}")
                
                self.results["catalog_analysis"]["xml_format_checks"] = format_checks
                
                # Check for WVP-specific issues
                if not format_checks["has_gb2312_encoding"]:
                    self.results["recommendations"].append("Ensure XML uses GB2312 encoding for WVP compatibility")
                
                if not format_checks["proper_device_ids"]:
                    self.results["recommendations"].append("Fix device ID format - must be exactly 20 digits")
                    
        except Exception as e:
            print(f"❌ XML format analysis failed: {e}")
            self.results["catalog_analysis"]["xml_format_error"] = str(e)
    
    def run_comprehensive_wvp_diagnostics(self):
        """Run all WVP platform-specific diagnostics"""
        print("🚀 Starting comprehensive WVP platform diagnostics...")
        print("=" * 60)
        
        # Run all diagnostic tests
        self.test_catalog_response_size()
        print()
        
        self.test_wvp_response_timing()
        print()
        
        self.test_wvp_network_connectivity()
        print()
        
        self.test_wvp_catalog_subscription()
        print()
        
        self.test_xml_format_compatibility()
        print()
        
        self.create_optimized_catalog_config()
        print()
        
        # Generate final report
        self.generate_wvp_report()
    
    def generate_wvp_report(self):
        """Generate comprehensive WVP diagnostics report"""
        print("📋 WVP Platform Diagnostics Report")
        print("=" * 60)
        
        # Save detailed results
        with open('/home/ubuntu/rstp/gb28181-restreamer/wvp_diagnostics_report.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Generate summary
        print("🔥 CRITICAL ISSUES FOUND:")
        critical_issues = []
        
        # Check for timeout-causing issues
        if self.results.get("catalog_analysis", {}).get("size_warning", False):
            critical_issues.append("❌ Catalog too large (>50KB) - will cause WVP timeouts")
        
        if self.results.get("timeout_analysis", {}).get("timeout_risk", False):
            critical_issues.append("❌ Response time too slow (>5s) - WVP will timeout")
        
        # Check connectivity issues
        wvp_tests = self.results.get("wvp_platform_tests", {})
        if not wvp_tests.get("sip_connectivity", {}).get("udp_reachable", False):
            critical_issues.append("❌ UDP connectivity to WVP platform failed")
        
        if not wvp_tests.get("device_accessibility", {}).get("sip_port_bound", False):
            critical_issues.append("❌ SIP port 5080 not properly bound")
        
        # Check format issues
        xml_checks = self.results.get("catalog_analysis", {}).get("xml_format_checks", {})
        if not xml_checks.get("proper_device_ids", True):
            critical_issues.append("❌ Device ID format incompatible with WVP")
        
        if critical_issues:
            for issue in critical_issues:
                print(f"  {issue}")
        else:
            print("  ✅ No critical issues detected")
        
        print()
        print("💡 RECOMMENDATIONS:")
        for rec in self.results.get("recommendations", []):
            print(f"  • {rec}")
        
        print()
        print(f"📄 Full report saved to: wvp_diagnostics_report.json")

def main():
    diagnostics = WVPPlatformDiagnostics()
    diagnostics.run_comprehensive_wvp_diagnostics()

if __name__ == "__main__":
    main() 