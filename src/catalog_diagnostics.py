#!/usr/bin/env python3
# src/catalog_diagnostics.py

import os
import sys
import json
import time
import argparse
import threading
import logging
from logger import log
from file_scanner import scan_video_files, get_video_catalog
from gb28181_sip_sender import GB28181SIPSender
from gb28181_xml import format_catalog_response

def setup_logging():
    """Setup logging configuration for diagnostics"""
    log_format = '[%(asctime)s] [%(levelname)s] [DIAG] %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('catalog_diagnostics')

def load_config(config_path):
    """Load configuration from a JSON file."""
    if not os.path.exists(config_path):
        log.error(f"Config file not found: {config_path}")
        return None
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    return config

def generate_test_catalog(device_id, video_files):
    """Generate a test catalog for testing purposes"""
    device_catalog = {}
    
    # Create device catalog in GB28181 format
    for i, video_path in enumerate(video_files):
        video_name = os.path.basename(video_path)
        # Generate unique channel ID for each video file
        channel_id = f"{device_id}{i+1:03d}"
        
        device_catalog[channel_id] = {
            "device_id": channel_id,
            "name": video_name,
            "path": video_path,
            "channel_id": channel_id,
            "status": "ON",  # ON or OFF
            "manufacturer": "GB28181-Restreamer",
            "model": "Video-File",
            "owner": "gb28181-restreamer",
            "civil_code": "123456",  # Required by GB28181
            "address": f"Video-{i+1}",
            "parental": "0",  # 0 means root device
            "parent_id": device_id,  # Use device_id as parent
            "safety_way": "0",  # 0 means no safety
            "register_way": "1",  # 1 means active registration
            "secrecy": "0",  # 0 means not secret
        }
    
    log.info(f"Generated catalog with {len(device_catalog)} channels")
    return device_catalog

def test_catalog_xml_generation(device_id, catalog):
    """Test catalog XML generation"""
    log.info("Testing catalog XML generation...")
    xml = format_catalog_response(device_id, catalog)
    xml_length = len(xml)
    
    log.info(f"Generated XML of length {xml_length} bytes")
    if xml_length < 100:
        log.error("XML generation failed: output too short")
        return False
    
    # Save XML to file for inspection
    with open('catalog_test.xml', 'w') as f:
        f.write(xml)
    log.info("Saved XML to catalog_test.xml for inspection")
    
    return True

def test_catalog_sending(config, catalog):
    """Test sending catalog to the platform"""
    device_id = config["sip"]["device_id"]
    
    # Generate catalog XML
    xml = format_catalog_response(device_id, catalog)
    
    # Create SIP sender
    sip_sender = GB28181SIPSender(config)
    sip_sender.start()
    
    # Try to send catalog
    log.info("Sending catalog to platform...")
    target_uri = f"sip:{config['sip']['server']}:{config['sip']['port']}"
    
    success = sip_sender.send_catalog(xml, target_uri)
    
    # Wait for message to be sent
    time.sleep(2)
    
    # Stop the sender
    sip_sender.stop()
    
    if success:
        log.info("Catalog sent successfully")
    else:
        log.error("Failed to send catalog")
    
    return success

def dump_catalog_to_file(catalog, filename='catalog_dump.json'):
    """Dump catalog to file for inspection"""
    with open(filename, 'w') as f:
        json.dump(catalog, f, indent=2)
    log.info(f"Dumped catalog to {filename} for inspection")

def main():
    """Main function for catalog diagnostics"""
    diag_log = setup_logging()
    
    parser = argparse.ArgumentParser(description='Catalog generation diagnostics tool')
    parser.add_argument('--config', '-c', default='config.json', help='Path to config file')
    parser.add_argument('--send', '-s', action='store_true', help='Send catalog to platform')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    if not config:
        return 1
    
    # Scan video files
    diag_log.info(f"Scanning directory: {config['stream_directory']}")
    video_files = scan_video_files(config['stream_directory'])
    
    if not video_files:
        diag_log.error("No video files found")
        return 1
    
    diag_log.info(f"Found {len(video_files)} video files")
    for file in video_files:
        diag_log.info(f"  • {file}")
    
    # Generate test catalog
    device_id = config["sip"]["device_id"]
    catalog = generate_test_catalog(device_id, video_files)
    
    # Dump catalog to file
    dump_catalog_to_file(catalog)
    
    # Test catalog XML generation
    if not test_catalog_xml_generation(device_id, catalog):
        return 1
    
    # Test sending catalog if requested
    if args.send:
        if not test_catalog_sending(config, catalog):
            return 1
    
    diag_log.info("Catalog diagnostics completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 