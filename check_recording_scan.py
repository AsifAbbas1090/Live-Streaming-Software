#!/usr/bin/env python3
"""
Recording Scan Progress Checker
This script helps monitor the recording scan progress when dealing with large files.
"""

import sys
import os
import time
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def main():
    try:
        from recording_manager import RecordingManager
        
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
        with open(config_path) as f:
            config = json.load(f)
        
        print("🎬 GB28181 Recording Scan Checker")
        print("=" * 50)
        print(f"📁 Recordings directory: {config['stream_directory']}")
        print()
        
        # Create recording manager
        print("⏳ Initializing recording manager (non-blocking)...")
        rm = RecordingManager(config)
        print("✅ Recording manager created successfully!")
        print()
        
        # Monitor scan progress
        print("📊 Monitoring scan progress...")
        print("Press Ctrl+C to stop monitoring")
        print()
        
        last_count = 0
        start_time = time.time()
        
        while True:
            status = rm.get_scan_status()
            
            # Calculate elapsed time
            elapsed = int(time.time() - start_time)
            
            # Show progress
            if status['scanning']:
                files_found = status['files_cached']
                new_files = files_found - last_count
                rate = f"+{new_files}" if new_files > 0 else ""
                
                print(f"⚡ [T+{elapsed:03d}s] Scanning... {files_found} files found {rate}")
                last_count = files_found
                
            elif status['scan_complete']:
                total_files = status['files_cached']
                print(f"🎉 [T+{elapsed:03d}s] Scan COMPLETE! Found {total_files} video files")
                break
            else:
                print(f"⌛ [T+{elapsed:03d}s] Scan starting...")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped by user")
        if 'rm' in locals():
            status = rm.get_scan_status()
            print(f"📊 Final status: {status['files_cached']} files cached")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 