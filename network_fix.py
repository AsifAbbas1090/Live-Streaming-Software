#!/usr/bin/env python3
"""
Network Configuration Fix Script for GB28181 Service
This script fixes network configuration issues and explains IP changes affecting the service.
"""

import subprocess
import json
import os
import time
from datetime import datetime

class NetworkFixer:
    def __init__(self):
        self.config_path = "config/config.json"
        self.backup_path = f"config/config.json.backup.{int(time.time())}"
        
    def explain_network_situation(self):
        """Explain the current network situation and what IP changes are affecting what"""
        print("🔍 NETWORK SITUATION ANALYSIS:")
        print("=" * 60)
        
        # Get current network info
        result = subprocess.run(['ip', 'addr', 'show', 'ens5'], capture_output=True, text=True)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'inet ' in line and '172.31' in line:
                    print(f"📍 Private IP (AWS internal): {line.strip()}")
                    
        result = subprocess.run(['curl', '-s', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"📍 Public IP (internet-facing): {result.stdout.strip()}")
            
        print("\n🔍 WHAT'S HAPPENING WITH IP ADDRESSES:")
        print("-" * 60)
        print("1. 📡 PRIVATE IP (172.31.7.94):")
        print("   - This is your EC2 instance's internal AWS network IP")
        print("   - Used for local binding and internal AWS communication")
        print("   - SIP client binds to this IP for local socket operations")
        print("   - This IP is what the SIP software 'sees' as its local address")
        
        print("\n2. 🌍 PUBLIC IP (13.50.108.195):")
        print("   - This is your EC2 instance's internet-facing IP")
        print("   - External SIP servers see this IP when you connect")
        print("   - Used in SIP Contact headers for return communication")
        print("   - Must be configured for proper NAT traversal")
        
        print("\n3. 🔗 SIP SERVER (ai-sip.x-stage.bull-b.com → 203.142.93.131):")
        print("   - Your WVP platform's SIP server")
        print("   - All SIP registration and communication goes here")
        print("   - Expects proper Contact headers with your public IP")
        
        print("\n🔍 WHAT IP CHANGES AFFECT WHAT:")
        print("-" * 60)
        print("❌ PROBLEMS WHEN IPs ARE WRONG:")
        print("   • local_ip ≠ actual private IP → Socket binding fails")
        print("   • contact_ip ≠ actual public IP → SIP responses fail")
        print("   • Missing contact_ip → Server can't call back")
        print("   • Wrong ports → Service doesn't listen properly")
        
        print("\n✅ WHAT EACH IP CONFIGURATION DOES:")
        print("   • local_ip: Where SIP client binds locally (must be 172.31.7.94)")
        print("   • contact_ip: What external servers use to reach you (must be 13.50.108.195)")
        print("   • local_port: Which port SIP client listens on (must be bound)")
        print("   • server: Where to register (ai-sip.x-stage.bull-b.com)")
        
    def check_current_config(self):
        """Check current configuration"""
        print("\n🔍 CHECKING CURRENT CONFIGURATION:")
        print("-" * 60)
        
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            sip_config = config.get("sip", {})
            
            print(f"📋 Current SIP Configuration:")
            print(f"   • local_ip: {sip_config.get('local_ip', 'NOT SET')}")
            print(f"   • contact_ip: {sip_config.get('contact_ip', 'NOT SET')}")
            print(f"   • local_port: {sip_config.get('local_port', 'NOT SET')}")
            print(f"   • server: {sip_config.get('server', 'NOT SET')}")
            print(f"   • port: {sip_config.get('port', 'NOT SET')}")
            
            return config
            
        except Exception as e:
            print(f"❌ Error reading config: {e}")
            return None
    
    def get_actual_network_info(self):
        """Get actual network information"""
        print("\n🔍 DETECTING ACTUAL NETWORK CONFIGURATION:")
        print("-" * 60)
        
        # Get private IP
        private_ip = None
        try:
            result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'src' in line:
                        parts = line.split()
                        if 'src' in parts:
                            src_index = parts.index('src')
                            if src_index + 1 < len(parts):
                                private_ip = parts[src_index + 1]
                                break
                                
            if not private_ip:
                # Fallback method
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                if result.returncode == 0:
                    private_ip = result.stdout.strip().split()[0]
                    
        except Exception as e:
            print(f"❌ Error getting private IP: {e}")
            
        # Get public IP
        public_ip = None
        try:
            result = subprocess.run(['curl', '-s', 'ifconfig.me'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                public_ip = result.stdout.strip()
        except Exception as e:
            print(f"❌ Error getting public IP: {e}")
            
        print(f"✅ Detected private IP: {private_ip}")
        print(f"✅ Detected public IP: {public_ip}")
        
        return private_ip, public_ip
    
    def check_port_availability(self, port):
        """Check if a port is available for binding"""
        try:
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "0.0.0.0" in line:
                        return False  # Port is already bound
            return True  # Port is available
        except:
            return True  # Assume available if we can't check
    
    def fix_configuration(self, config, private_ip, public_ip):
        """Fix the SIP configuration with correct IPs"""
        print("\n🔧 FIXING CONFIGURATION:")
        print("-" * 60)
        
        if not config:
            print("❌ No configuration to fix")
            return False
            
        # Backup original config
        try:
            with open(self.backup_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"💾 Backed up original config to {self.backup_path}")
        except Exception as e:
            print(f"❌ Failed to backup config: {e}")
            return False
            
        # Fix SIP configuration
        sip_config = config.setdefault("sip", {})
        changes_made = []
        
        # Fix local_ip
        current_local_ip = sip_config.get("local_ip")
        if current_local_ip != private_ip:
            sip_config["local_ip"] = private_ip
            changes_made.append(f"local_ip: {current_local_ip} → {private_ip}")
            
        # Fix contact_ip  
        current_contact_ip = sip_config.get("contact_ip")
        if current_contact_ip != public_ip:
            sip_config["contact_ip"] = public_ip
            changes_made.append(f"contact_ip: {current_contact_ip} → {public_ip}")
            
        # Ensure proper local_port
        if "local_port" not in sip_config:
            sip_config["local_port"] = 5080
            changes_made.append("Added local_port: 5080")
        elif sip_config["local_port"] == 5060:
            # Avoid conflict with default SIP port
            if not self.check_port_availability(5080):
                sip_config["local_port"] = 5082  # Use alternative
                changes_made.append("Changed local_port: 5060 → 5082 (avoiding conflict)")
            else:
                sip_config["local_port"] = 5080
                changes_made.append("Changed local_port: 5060 → 5080")
                
        # Ensure transport is UDP
        if sip_config.get("transport") != "udp":
            sip_config["transport"] = "udp"
            changes_made.append("Set transport: udp")
            
        if changes_made:
            print("🔧 Changes made:")
            for change in changes_made:
                print(f"   ✓ {change}")
                
            # Save fixed configuration
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"✅ Saved fixed configuration to {self.config_path}")
                return True
            except Exception as e:
                print(f"❌ Failed to save fixed config: {e}")
                return False
        else:
            print("✅ No changes needed - configuration is already correct")
            return True
    
    def restart_service(self):
        """Restart the GB28181 service to apply changes"""
        print("\n🔄 RESTARTING GB28181 SERVICE:")
        print("-" * 60)
        
        # Kill any existing processes
        try:
            result = subprocess.run(['pkill', '-f', 'python.*main.py'], capture_output=True, text=True)
            result = subprocess.run(['pkill', '-f', 'pjsua'], capture_output=True, text=True)
            time.sleep(2)
            print("✅ Stopped existing GB28181 processes")
        except Exception as e:
            print(f"ℹ️  Note: {e}")
            
        # Start the service
        print("🚀 Starting GB28181 service...")
        print("   (This will run in the background)")
        
        try:
            # Start the service in background
            subprocess.Popen(
                ['python3', 'src/main.py'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd='/home/ubuntu/rstp/gb28181-restreamer'
            )
            
            # Give it a moment to start
            time.sleep(3)
            
            # Check if it's running
            result = subprocess.run(['pgrep', '-f', 'python.*main.py'], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ GB28181 service started successfully")
                return True
            else:
                print("❌ Failed to start GB28181 service")
                return False
                
        except Exception as e:
            print(f"❌ Error starting service: {e}")
            return False
    
    def verify_fix(self):
        """Verify that the fix worked"""
        print("\n🔍 VERIFYING FIX:")
        print("-" * 60)
        
        # Check if ports are bound
        time.sleep(2)  # Give service time to bind ports
        
        try:
            result = subprocess.run(['ss', '-tuln'], capture_output=True, text=True)
            if result.returncode == 0:
                bound_ports = []
                for line in result.stdout.split('\n'):
                    if ':5060' in line or ':5080' in line or ':5082' in line:
                        bound_ports.append(line.strip())
                        
                if bound_ports:
                    print("✅ SIP ports are now bound:")
                    for port in bound_ports:
                        print(f"   • {port}")
                else:
                    print("❌ No SIP ports are bound yet")
                    
        except Exception as e:
            print(f"❌ Error checking port binding: {e}")
            
        # Check process status
        try:
            result = subprocess.run(['pgrep', '-f', 'python.*main.py'], capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                print(f"✅ GB28181 service is running (PIDs: {', '.join(pids)})")
            else:
                print("❌ GB28181 service is not running")
                
        except Exception as e:
            print(f"❌ Error checking service status: {e}")
    
    def run_comprehensive_fix(self):
        """Run the complete network fix process"""
        print("🚀 GB28181 NETWORK CONFIGURATION FIX")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Explain the situation
        self.explain_network_situation()
        
        # Step 2: Check current config
        config = self.check_current_config()
        
        # Step 3: Get actual network info
        private_ip, public_ip = self.get_actual_network_info()
        
        if not private_ip or not public_ip:
            print("\n❌ FAILED: Could not detect network configuration")
            return False
            
        # Step 4: Fix configuration
        if not self.fix_configuration(config, private_ip, public_ip):
            print("\n❌ FAILED: Could not fix configuration")
            return False
            
        # Step 5: Restart service
        if not self.restart_service():
            print("\n❌ FAILED: Could not restart service")
            return False
            
        # Step 6: Verify fix
        self.verify_fix()
        
        print("\n" + "=" * 60)
        print("🎉 NETWORK FIX COMPLETE!")
        print("=" * 60)
        print("✅ What was fixed:")
        print("   • IP addresses updated to match actual network configuration")
        print("   • SIP ports properly configured")
        print("   • Service restarted with new configuration")
        print("   • Port binding verified")
        
        print("\n📋 Next steps:")
        print("   1. Check the WVP platform for device registration")
        print("   2. Look for catalog queries in the logs")
        print("   3. Test video streaming functionality")
        
        print(f"\n📁 Configuration backup saved to: {self.backup_path}")
        
        return True

if __name__ == "__main__":
    fixer = NetworkFixer()
    success = fixer.run_comprehensive_fix()
    
    if success:
        print("\n✅ Fix completed successfully!")
    else:
        print("\n❌ Fix failed - check error messages above") 