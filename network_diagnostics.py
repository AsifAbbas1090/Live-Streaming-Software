#!/usr/bin/env python3
"""
Comprehensive Network Diagnostics for GB28181 Service
This script analyzes network configuration and identifies IP-related issues
"""

import subprocess
import socket
import json
import re
import time
from datetime import datetime

class NetworkDiagnostics:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "network_interfaces": {},
            "connectivity_tests": {},
            "sip_configuration": {},
            "issues_found": [],
            "recommendations": []
        }
        
    def get_network_interfaces(self):
        """Get all network interfaces and their IP addresses"""
        print("🔍 Analyzing network interfaces...")
        
        try:
            # Get interface information
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                interfaces = {}
                current_interface = None
                
                for line in result.stdout.split('\n'):
                    # Interface line
                    if re.match(r'^\d+:', line):
                        match = re.search(r'^\d+:\s+(\w+):', line)
                        if match:
                            current_interface = match.group(1)
                            interfaces[current_interface] = {
                                "status": "UP" if "UP" in line else "DOWN",
                                "addresses": []
                            }
                    
                    # IP address line
                    elif "inet " in line and current_interface:
                        match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+/\d+)', line)
                        if match:
                            interfaces[current_interface]["addresses"].append(match.group(1))
                            
                self.results["network_interfaces"] = interfaces
                
                # Find primary interface
                primary_ip = None
                primary_interface = None
                for iface, info in interfaces.items():
                    if iface != "lo" and info["status"] == "UP" and info["addresses"]:
                        for addr in info["addresses"]:
                            if not addr.startswith("127."):
                                primary_ip = addr.split('/')[0]
                                primary_interface = iface
                                break
                        if primary_ip:
                            break
                            
                print(f"✅ Primary interface: {primary_interface} ({primary_ip})")
                return primary_ip, primary_interface
                
        except Exception as e:
            print(f"❌ Error getting network interfaces: {e}")
            self.results["issues_found"].append(f"Failed to get network interfaces: {e}")
            
        return None, None
    
    def get_public_ip(self):
        """Get the public IP address"""
        print("🌍 Getting public IP address...")
        
        try:
            result = subprocess.run(['curl', '-s', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                public_ip = result.stdout.strip()
                print(f"✅ Public IP: {public_ip}")
                return public_ip
            else:
                print("❌ Failed to get public IP")
                self.results["issues_found"].append("Failed to get public IP address")
                return None
        except Exception as e:
            print(f"❌ Error getting public IP: {e}")
            self.results["issues_found"].append(f"Error getting public IP: {e}")
            return None
    
    def test_sip_server_connectivity(self, server, port):
        """Test connectivity to SIP server"""
        print(f"🔗 Testing connectivity to SIP server {server}:{port}...")
        
        connectivity = {
            "dns_resolution": False,
            "tcp_connectivity": False,
            "udp_connectivity": False,
            "resolved_ip": None
        }
        
        # DNS resolution test
        try:
            resolved_ip = socket.gethostbyname(server)
            connectivity["dns_resolution"] = True
            connectivity["resolved_ip"] = resolved_ip
            print(f"✅ DNS resolution: {server} → {resolved_ip}")
        except Exception as e:
            print(f"❌ DNS resolution failed: {e}")
            self.results["issues_found"].append(f"DNS resolution failed for {server}: {e}")
            
        # TCP connectivity test
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((server, port))
            sock.close()
            
            if result == 0:
                connectivity["tcp_connectivity"] = True
                print(f"✅ TCP connectivity: {server}:{port}")
            else:
                print(f"❌ TCP connectivity failed: {server}:{port}")
                self.results["issues_found"].append(f"TCP connectivity failed to {server}:{port}")
        except Exception as e:
            print(f"❌ TCP test error: {e}")
            self.results["issues_found"].append(f"TCP test error for {server}:{port}: {e}")
            
        # UDP connectivity test (basic)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(b"test", (server, port))
            sock.close()
            connectivity["udp_connectivity"] = True
            print(f"✅ UDP connectivity: {server}:{port}")
        except Exception as e:
            print(f"❌ UDP test error: {e}")
            self.results["issues_found"].append(f"UDP test error for {server}:{port}: {e}")
            
        self.results["connectivity_tests"][f"{server}:{port}"] = connectivity
        return connectivity
    
    def check_port_binding(self, ports):
        """Check if specific ports are bound"""
        print("🔍 Checking port binding...")
        
        bound_ports = {}
        
        try:
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                for port in ports:
                    bound = False
                    for line in result.stdout.split('\n'):
                        if f":{port}" in line:
                            bound = True
                            print(f"✅ Port {port} is bound: {line.strip()}")
                            break
                    
                    if not bound:
                        print(f"❌ Port {port} is NOT bound")
                        self.results["issues_found"].append(f"Port {port} is not bound")
                    
                    bound_ports[port] = bound
            else:
                print("❌ Failed to check port binding")
                self.results["issues_found"].append("Failed to check port binding")
                
        except Exception as e:
            print(f"❌ Error checking port binding: {e}")
            self.results["issues_found"].append(f"Error checking port binding: {e}")
            
        return bound_ports
    
    def analyze_sip_config(self, config_path="config/config.json"):
        """Analyze SIP configuration for potential issues"""
        print("📋 Analyzing SIP configuration...")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            sip_config = config.get("sip", {})
            self.results["sip_configuration"] = sip_config
            
            # Check for configuration issues
            issues = []
            
            # Check if local_ip matches actual IP
            configured_local_ip = sip_config.get("local_ip")
            configured_contact_ip = sip_config.get("contact_ip")
            
            if configured_local_ip:
                print(f"📍 Configured local IP: {configured_local_ip}")
            if configured_contact_ip:
                print(f"📍 Configured contact IP: {configured_contact_ip}")
                
            # Check server configuration
            server = sip_config.get("server")
            port = sip_config.get("port", 5060)
            local_port = sip_config.get("local_port", 5080)
            
            print(f"📍 SIP server: {server}:{port}")
            print(f"📍 Local SIP port: {local_port}")
            
            return sip_config
            
        except Exception as e:
            print(f"❌ Error analyzing SIP configuration: {e}")
            self.results["issues_found"].append(f"Error analyzing SIP configuration: {e}")
            return {}
    
    def check_firewall_rules(self):
        """Check firewall rules that might affect SIP"""
        print("🔥 Checking firewall rules...")
        
        try:
            # Check iptables
            result = subprocess.run(['iptables', '-L', '-n'], capture_output=True, text=True)
            if result.returncode == 0:
                output = result.stdout
                if "DROP" in output or "REJECT" in output:
                    print("⚠️  Firewall rules detected that might block traffic")
                    self.results["issues_found"].append("Firewall rules detected that might block SIP traffic")
                else:
                    print("✅ No obvious firewall blocking rules found")
            else:
                print("❌ Could not check iptables rules")
                
        except Exception as e:
            print(f"ℹ️  Could not check firewall: {e}")
            
        try:
            # Check ufw status
            result = subprocess.run(['ufw', 'status'], capture_output=True, text=True)
            if result.returncode == 0:
                if "Status: active" in result.stdout:
                    print("⚠️  UFW firewall is active")
                    print("UFW Status:")
                    print(result.stdout)
                    self.results["issues_found"].append("UFW firewall is active - may block SIP traffic")
                else:
                    print("✅ UFW firewall is inactive")
            else:
                print("ℹ️  UFW not available")
                
        except Exception as e:
            print(f"ℹ️  Could not check UFW: {e}")
    
    def test_routing(self, target_ip):
        """Test routing to target IP"""
        print(f"🛣️  Testing routing to {target_ip}...")
        
        try:
            result = subprocess.run(['traceroute', '-n', target_ip], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print("✅ Traceroute completed:")
                for line in result.stdout.split('\n')[:5]:  # Show first 5 hops
                    if line.strip():
                        print(f"  {line}")
            else:
                print("❌ Traceroute failed")
                
        except Exception as e:
            print(f"ℹ️  Traceroute not available: {e}")
    
    def generate_recommendations(self, primary_ip, public_ip, sip_config):
        """Generate recommendations based on findings"""
        print("\n📝 Generating recommendations...")
        
        recommendations = []
        
        # IP configuration recommendations
        configured_local_ip = sip_config.get("local_ip")
        configured_contact_ip = sip_config.get("contact_ip")
        
        if configured_local_ip and configured_local_ip != primary_ip:
            recommendations.append({
                "issue": "Local IP mismatch",
                "description": f"Configured local_ip ({configured_local_ip}) differs from actual primary IP ({primary_ip})",
                "recommendation": f"Update config.json: local_ip should be '{primary_ip}'",
                "priority": "HIGH"
            })
            
        if configured_contact_ip and configured_contact_ip != public_ip:
            recommendations.append({
                "issue": "Contact IP mismatch", 
                "description": f"Configured contact_ip ({configured_contact_ip}) differs from actual public IP ({public_ip})",
                "recommendation": f"Update config.json: contact_ip should be '{public_ip}'",
                "priority": "HIGH"
            })
            
        # Check for common misconfigurations
        if not sip_config.get("local_port"):
            recommendations.append({
                "issue": "Missing local port",
                "description": "No local_port specified in SIP configuration",
                "recommendation": "Add local_port configuration (e.g., 5080)",
                "priority": "MEDIUM"
            })
            
        # Network connectivity recommendations
        server = sip_config.get("server")
        if server:
            connectivity = self.results["connectivity_tests"].get(f"{server}:5060", {})
            if not connectivity.get("udp_connectivity"):
                recommendations.append({
                    "issue": "UDP connectivity",
                    "description": f"UDP connectivity to {server}:5060 may be blocked",
                    "recommendation": "Check firewall rules and network connectivity",
                    "priority": "HIGH"
                })
                
        self.results["recommendations"] = recommendations
        
        # Print recommendations
        for rec in recommendations:
            priority_emoji = "🔴" if rec["priority"] == "HIGH" else "🟡" if rec["priority"] == "MEDIUM" else "🟢"
            print(f"{priority_emoji} {rec['issue']}: {rec['description']}")
            print(f"   → {rec['recommendation']}")
            
        return recommendations
    
    def run_comprehensive_diagnostics(self):
        """Run all network diagnostics"""
        print("🚀 Starting comprehensive network diagnostics...\n")
        
        # Get network configuration
        primary_ip, primary_interface = self.get_network_interfaces()
        public_ip = self.get_public_ip()
        
        # Analyze SIP configuration
        sip_config = self.analyze_sip_config()
        
        # Test SIP server connectivity
        server = sip_config.get("server")
        port = sip_config.get("port", 5060)
        if server:
            self.test_sip_server_connectivity(server, port)
            
            # Test routing
            connectivity = self.results["connectivity_tests"].get(f"{server}:{port}", {})
            if connectivity.get("resolved_ip"):
                self.test_routing(connectivity["resolved_ip"])
        
        # Check port binding
        ports_to_check = [5060, 5080]
        local_port = sip_config.get("local_port")
        if local_port:
            ports_to_check.append(local_port)
            
        self.check_port_binding(ports_to_check)
        
        # Check firewall
        self.check_firewall_rules()
        
        # Generate recommendations
        self.generate_recommendations(primary_ip, public_ip, sip_config)
        
        # Save results
        with open("network_diagnostics_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n📊 Diagnostics complete. Report saved to network_diagnostics_report.json")
        print(f"📈 Found {len(self.results['issues_found'])} issues")
        print(f"💡 Generated {len(self.results['recommendations'])} recommendations")
        
        return self.results

if __name__ == "__main__":
    diagnostics = NetworkDiagnostics()
    results = diagnostics.run_comprehensive_diagnostics() 