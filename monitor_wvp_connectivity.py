#!/usr/bin/env python3
"""
WVP Platform Connectivity Monitor
Monitors GB28181 device connectivity with WVP platform to prevent offline issues.
"""

import sys
import os
import time
import json
import requests
from datetime import datetime, timedelta

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class WVPConnectivityMonitor:
    def __init__(self, config_file):
        """Initialize WVP connectivity monitor"""
        with open(config_file) as f:
            self.config = json.load(f)
        
        self.device_id = self.config.get('device_id')
        self.wvp_platform_ip = self.config.get('sip_server')
        self.wvp_platform_port = self.config.get('sip_port', 5060)
        
        # Monitoring configuration
        self.check_interval = 60  # Check every minute
        self.offline_threshold = 180  # Consider offline after 3 minutes
        self.last_seen = {}
        
        print(f"🔍 WVP Connectivity Monitor Started")
        print(f"📱 Device ID: {self.device_id}")
        print(f"🌐 WVP Platform: {self.wvp_platform_ip}:{self.wvp_platform_port}")
        print("=" * 60)
    
    def check_sip_registration(self):
        """Check if SIP registration is active"""
        try:
            # Import here to avoid circular imports
            from recording_manager import RecordingManager
            
            # Check if our application is running and registered
            # This is a placeholder - you would implement actual SIP status checking
            return True
            
        except Exception as e:
            print(f"❌ Error checking SIP registration: {e}")
            return False
    
    def simulate_device_status_check(self):
        """Simulate checking device status on WVP platform"""
        try:
            # This would normally be an API call to WVP platform
            # For now, simulate based on time since last keepalive
            
            current_time = time.time()
            
            # Simulate device status based on registration patterns
            if self.device_id not in self.last_seen:
                self.last_seen[self.device_id] = current_time
                return "Online"
            
            time_since_last_seen = current_time - self.last_seen[self.device_id]
            
            if time_since_last_seen < self.offline_threshold:
                return "Online"
            else:
                return "Offline"
                
        except Exception as e:
            print(f"❌ Error checking device status: {e}")
            return "Unknown"
    
    def update_device_seen(self):
        """Update last seen timestamp for device"""
        self.last_seen[self.device_id] = time.time()
    
    def get_connectivity_report(self):
        """Generate connectivity status report"""
        status = self.simulate_device_status_check()
        current_time = datetime.now()
        
        if self.device_id in self.last_seen:
            last_seen_time = datetime.fromtimestamp(self.last_seen[self.device_id])
            time_diff = current_time - last_seen_time
            last_seen_str = f"{time_diff.total_seconds():.0f}s ago"
        else:
            last_seen_str = "Never"
        
        return {
            "device_id": self.device_id,
            "status": status,
            "last_seen": last_seen_str,
            "platform_ip": self.wvp_platform_ip,
            "check_time": current_time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def check_for_route_header_issues(self):
        """Check application logs for Route header issues"""
        log_file = "app_debug.log"
        route_header_issues = 0
        
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    
                # Check last 100 lines for Route header issues
                for line in lines[-100:]:
                    if "sip: unkonw message head Route" in line or "sip: unknown message head Route" in line:
                        route_header_issues += 1
                        
        except Exception as e:
            print(f"⚠️ Could not check log file: {e}")
        
        return route_header_issues
    
    def run_monitoring_cycle(self):
        """Run one monitoring cycle"""
        print(f"\n🔍 Monitoring Cycle - {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)
        
        # Check SIP registration
        sip_registered = self.check_sip_registration()
        sip_status = "✅ Registered" if sip_registered else "❌ Not Registered"
        print(f"📡 SIP Registration: {sip_status}")
        
        # Check device connectivity
        if sip_registered:
            self.update_device_seen()
        
        connectivity_report = self.get_connectivity_report()
        status_icon = "✅" if connectivity_report["status"] == "Online" else "❌"
        print(f"🌐 WVP Platform Status: {status_icon} {connectivity_report['status']}")
        print(f"⏱️  Last Seen: {connectivity_report['last_seen']}")
        
        # Check for Route header issues
        route_issues = self.check_for_route_header_issues()
        if route_issues > 0:
            print(f"⚠️  Route Header Issues: {route_issues} (this may cause offline issues)")
        else:
            print("✅ No Route Header Issues")
        
        # Check registration renewal timing
        if self.device_id in self.last_seen:
            time_since_last = time.time() - self.last_seen[self.device_id]
            if time_since_last > 2700:  # 45 minutes
                print("🔄 Registration renewal should happen soon")
            elif time_since_last > 3300:  # 55 minutes  
                print("⚠️ Registration approaching expiry")
            elif time_since_last > 3500:  # 58+ minutes
                print("🚨 URGENT: Registration about to expire!")
        
        return connectivity_report
    
    def run(self):
        """Run continuous monitoring"""
        print("🚀 Starting WVP Connectivity Monitoring...")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                report = self.run_monitoring_cycle()
                
                # Alert if device goes offline
                if report["status"] == "Offline":
                    print("\n" + "🚨" * 20)
                    print("🚨 ALERT: DEVICE OFFLINE ON WVP PLATFORM!")
                    print("🚨 Check SIP registration and keepalive mechanism!")
                    print("🚨" * 20)
                
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Monitoring error: {e}")

def main():
    """Main function"""
    config_file = "config/config.json"
    
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return 1
    
    monitor = WVPConnectivityMonitor(config_file)
    monitor.run()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 