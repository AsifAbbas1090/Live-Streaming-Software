#!/usr/bin/env python3
"""
Test script for the GB28181 recording query functionality.
This script tests the time-based query function of the recording manager.
"""

import os
import sys
import json
import datetime

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from logger import log
from recording_manager import get_recording_manager
from gb28181_xml import format_recordinfo_response, parse_recordinfo_query

# Create a basic config
test_config = {
    "sip": {
        "device_id": "34020000001320000001",
        "username": "34020000001320000001",
        "password": "12345678",
        "server": "127.0.0.1",
        "port": 5060
    },
    "stream_directory": "./sample_videos",
}

def test_load_recordings():
    """Test loading recordings from the database"""
    recording_manager = get_recording_manager(test_config)
    recording_manager.scan_recordings(force=True)
    
    # Print summary of recordings found
    recordings = recording_manager.recording_db
    print(f"\n===== Found {len(recordings)} recordings =====")
    
    # Group by date
    recordings_by_date = {}
    for recording in recordings:
        # Extract date from start time (YYYYMMDDThhmmssZ)
        date_part = recording['start_time'][:8]  # Extract YYYYMMDD
        if date_part not in recordings_by_date:
            recordings_by_date[date_part] = []
        recordings_by_date[date_part].append(recording)
    
    # Print recordings by date
    for date, date_recordings in recordings_by_date.items():
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}-{month}-{day}"
        print(f"\n-- Recordings for {formatted_date} ({len(date_recordings)}) --")
        
        for rec in date_recordings:
            # Format times for better readability
            start_time = rec['start_time'][8:10] + ":" + rec['start_time'][10:12] + ":" + rec['start_time'][12:14]
            end_time = rec['end_time'][8:10] + ":" + rec['end_time'][10:12] + ":" + rec['end_time'][12:14]
            
            # Print recording details
            print(f"  • {rec['name']} ({start_time} to {end_time})")

def test_time_query():
    """Test querying recordings by time range"""
    recording_manager = get_recording_manager(test_config)
    
    # Define test cases with different time ranges
    test_cases = [
        {
            "name": "All recordings (no time filter)",
            "device_id": test_config["sip"]["device_id"],
            "start_time": None,
            "end_time": None
        },
        {
            "name": "Recordings for 2025-05-15 morning",
            "device_id": test_config["sip"]["device_id"],
            "start_time": "20250515T000000Z",
            "end_time": "20250515T120000Z"
        },
        {
            "name": "Recordings for 2025-05-15 afternoon",
            "device_id": test_config["sip"]["device_id"],
            "start_time": "20250515T120000Z",
            "end_time": "20250515T235959Z"
        },
        {
            "name": "Recordings for 2025-05-16 only",
            "device_id": test_config["sip"]["device_id"],
            "start_time": "20250516T000000Z",
            "end_time": "20250516T235959Z"
        },
        {
            "name": "Recordings across all days",
            "device_id": test_config["sip"]["device_id"],
            "start_time": "20250515T000000Z",
            "end_time": "20250516T235959Z"
        }
    ]
    
    # Run test cases
    for i, test_case in enumerate(test_cases):
        print(f"\n===== Test Case {i+1}: {test_case['name']} =====")
        
        # Query recordings
        results = recording_manager.query_recordings(
            device_id=test_case["device_id"],
            start_time=test_case["start_time"],
            end_time=test_case["end_time"]
        )
        
        # Display results
        print(f"Found {len(results)} matching recordings")
        for rec in results:
            # Format times for better readability
            start_time = rec['start_time'][8:10] + ":" + rec['start_time'][10:12] + ":" + rec['start_time'][12:14]
            end_time = rec['end_time'][8:10] + ":" + rec['end_time'][10:12] + ":" + rec['end_time'][12:14]
            date = rec['start_time'][:8]
            year = date[:4]
            month = date[4:6]
            day = date[6:8]
            formatted_date = f"{year}-{month}-{day}"
            
            # Print recording details
            print(f"  • [{formatted_date}] {rec['name']} ({start_time} to {end_time})")
        
        # Also generate the XML response that would be sent to the platform
        xml_response = format_recordinfo_response(
            device_id=test_case["device_id"],
            records=results,
            query_info=test_case
        )
        
        # Save XML to a file for inspection
        xml_file = f"test_recording_query_{i+1}.xml"
        with open(xml_file, "w") as f:
            f.write(xml_response)
        print(f"Saved XML response to {xml_file}")

def main():
    """Main test function"""
    print("===== GB28181 Recording Query Test =====")
    
    # Test loading recordings
    test_load_recordings()
    
    # Test time-based queries
    test_time_query()
    
    print("\n===== Tests complete =====")

if __name__ == "__main__":
    main() 