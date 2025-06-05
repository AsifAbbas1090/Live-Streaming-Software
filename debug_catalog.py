#!/usr/bin/env python3
"""
Debug script to test catalog generation and identify XML issues
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sip_handler_pjsip import SIPClient
from logger import log

def main():
    """Run catalog debug tests"""
    try:
        log.info("🔍 Starting catalog debug tests...")
        
        # Load configuration
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        if not os.path.exists(config_path):
            log.error(f"Config file not found: {config_path}")
            return
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        log.info("✅ Configuration loaded")
        
        # Create SIP client instance (but don't start it)
        sip_client = SIPClient(config)
        
        # Generate device catalog
        log.info("🔧 Generating device catalog...")
        sip_client.generate_device_catalog()
        
        # Run comprehensive debug
        log.info("🔍 Running catalog debug...")
        sip_client.debug_catalog_generation()
        
        log.info("✅ Debug tests completed - check logs above for results")
        
    except Exception as e:
        log.error(f"❌ Debug test failed: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main() 