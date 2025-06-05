#!/usr/bin/env python3
"""
SIP Binding Fix Script - Focused fix for port binding issues
Fixes the critical SIP port 5080 binding problem causing WVP platform timeouts
"""

import subprocess
import time
import os
import json
from datetime import datetime

class SIPBindingFixer:
    def __init__(self):
        self.config_path = "config/config.json"
        
    def fix_sip_port_binding(self):
        """Fix SIP port 5080 binding issue"""
        print("🔧 FIXING SIP PORT BINDING ISSUE...")
        print("=" * 50)
        
        # Step 1: Kill any processes that might be blocking ports
        print("1. Stopping any existing GB28181 processes...")
        try:
            subprocess.run(["pkill", "-f", "python.*main.py"], capture_output=True)
            subprocess.run(["pkill", "-f", "pjsua"], capture_output=True)
            time.sleep(2)
            print("   ✅ Stopped existing processes")
        except Exception as e:
            print(f"   ⚠️  Process cleanup: {e}")
        
        # Step 2: Check port availability
        print("2. Checking port availability...")
        result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
        
        port_5080_bound = ":5080" in result.stdout
        port_5060_bound = ":5060" in result.stdout
        
        print(f"   Port 5060: {'✅ BOUND' if port_5060_bound else '❌ NOT BOUND'}")
        print(f"   Port 5080: {'✅ BOUND' if port_5080_bound else '❌ NOT BOUND'}")
        
        if not port_5080_bound:
            print("   🎯 Found the issue: Port 5080 not bound!")
        
        # Step 3: Verify configuration
        print("3. Verifying SIP configuration...")
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            local_port = config["sip"].get("local_port", 5080)
            print(f"   Configured local port: {local_port}")
            
            if local_port != 5080:
                print(f"   🔧 Fixing local_port in config: {local_port} → 5080")
                config["sip"]["local_port"] = 5080
                
                # Backup original config
                backup_path = f"{self.config_path}.backup.{int(time.time())}"
                subprocess.run(["cp", self.config_path, backup_path])
                print(f"   💾 Backed up config to: {backup_path}")
                
                # Save updated config
                with open(self.config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print("   ✅ Updated configuration")
            else:
                print("   ✅ Configuration correct")
                
        except Exception as e:
            print(f"   ❌ Configuration error: {e}")
            return False
        
        # Step 4: Start service with proper binding
        print("4. Starting GB28181 service with proper port binding...")
        try:
            # Start the service
            process = subprocess.Popen(
                ["python3", "src/main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            print("   🚀 Service starting...")
            
            # Wait a moment for startup
            time.sleep(5)
            
            # Check if process is still running
            if process.poll() is None:
                print("   ✅ Service started successfully")
                
                # Verify port binding
                time.sleep(2)
                result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
                
                if ":5080" in result.stdout:
                    print("   ✅ Port 5080 now properly bound!")
                    
                    # Check for GB28181 process
                    ps_result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
                    if "python.*main.py" in ps_result.stdout:
                        print("   ✅ GB28181 service running")
                        return True
                    else:
                        print("   ⚠️  Service might not be fully started")
                else:
                    print("   ❌ Port 5080 still not bound")
                    
            else:
                print(f"   ❌ Service failed to start (exit code: {process.poll()})")
                
        except Exception as e:
            print(f"   ❌ Error starting service: {e}")
            return False
        
        return False
    
    def verify_binding_fix(self):
        """Verify that the binding fix worked"""
        print("\n🔍 VERIFYING BINDING FIX...")
        print("=" * 40)
        
        # Check port binding
        result = subprocess.run(["netstat", "-tuln"], capture_output=True, text=True)
        port_5080_bound = ":5080" in result.stdout
        
        # Check service running
        ps_result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        service_running = "python.*main.py" in ps_result.stdout
        
        # Check pjsua process
        pjsua_running = "pjsua" in ps_result.stdout
        
        print(f"Port 5080 bound: {'✅ YES' if port_5080_bound else '❌ NO'}")
        print(f"GB28181 service: {'✅ RUNNING' if service_running else '❌ NOT RUNNING'}")
        print(f"PJSUA process: {'✅ RUNNING' if pjsua_running else '❌ NOT RUNNING'}")
        
        if port_5080_bound and service_running:
            print("\n🎉 SUCCESS: SIP binding fix applied successfully!")
            print("💡 Now test the WVP platform refresh to see if channels appear")
            return True
        else:
            print("\n❌ BINDING FIX FAILED: Will need to run complete fix script")
            print("💡 Please run the complete fix script next")
            return False
    
    def run_sip_binding_fix(self):
        """Run the complete SIP binding fix"""
        print("🚀 STARTING SIP BINDING FIX")
        print("=" * 60)
        print("🎯 GOAL: Fix port 5080 binding to resolve WVP synchronization timeouts")
        print()
        
        # Apply the binding fix
        success = self.fix_sip_port_binding()
        
        if success:
            # Verify the fix
            return self.verify_binding_fix()
        else:
            print("\n❌ BINDING FIX FAILED")
            return False

def main():
    fixer = SIPBindingFixer()
    success = fixer.run_sip_binding_fix()
    
    if not success:
        print("\n🔄 NEXT STEP: Run the complete fix script")
        print("   python3 wvp_timeout_fix.py")

if __name__ == "__main__":
    main() 