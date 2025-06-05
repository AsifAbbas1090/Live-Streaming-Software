#!/usr/bin/env python3
"""
Recording Manager Module for GB28181-Restreamer

This module provides functionality to:
1. Track and catalog video recordings
2. Support RecordInfo time-series queries from GB28181 platforms
3. Serve recordings via streaming protocols
"""

import os
import re
import json
import time
import datetime
import logging
import threading
from pathlib import Path
from logger import log

class RecordingManager:
    """Recording Manager for handling video recording files and metadata"""
    
    def __init__(self, config):
        """Initialize the Recording Manager"""
        self.config = config
        self.recordings_directory = config.get("stream_directory", "./recordings")
        self.metadata_cache = {}
        self.last_scan_time = 0
        self.scan_interval = 60  # Scan every 60 seconds
        self.scanning = False  # Flag to prevent concurrent scans
        self.scan_thread = None  # Thread for async scanning
        
        # Ensure the recordings directory exists
        os.makedirs(self.recordings_directory, exist_ok=True)
        
        # Start initial async scan
        self.start_async_scan()
        
    def start_async_scan(self):
        """Start asynchronous recording scan to avoid blocking startup"""
        if self.scanning or (self.scan_thread and self.scan_thread.is_alive()):
            log.info("[REC-MANAGER] Scan already in progress, skipping")
            return
            
        log.info("[REC-MANAGER] Starting asynchronous recording scan")
        self.scan_thread = threading.Thread(target=self._async_scan_recordings, daemon=True)
        self.scan_thread.start()
    
    def _async_scan_recordings(self):
        """Asynchronous recording scan that doesn't block the main thread"""
        try:
            self.scanning = True
            log.info("[REC-MANAGER] Starting async scan with CPU throttling for better SIP performance")
            self.scan_recordings(force=True)
        finally:
            self.scanning = False
    
    def scan_recordings(self, force=False):
        """Scan the recordings directory and update the metadata cache"""
        current_time = time.time()
        
        # Only scan if enough time has passed since the last scan or if forced
        if not force and current_time - self.last_scan_time < self.scan_interval:
            return
            
        log.info("[REC-MANAGER] Scanning recordings directory with CPU throttling")
        self.last_scan_time = current_time
        
        # Clear the cache if rescanning
        if force:
            self.metadata_cache = {}
        
        file_count = 0
        processed_count = 0
        skipped_count = 0
        batch_size = 5  # Process files in small batches
        batch_count = 0
            
        # Walk through the recordings directory
        for root, dirs, files in os.walk(self.recordings_directory):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                # Only process video files
                if not self._is_video_file(file):
                    continue
                    
                file_count += 1
                file_path = os.path.join(root, file)
                
                # Skip files we've already scanned
                if file_path in self.metadata_cache:
                    skipped_count += 1
                    continue
                    
                # Extract metadata from the file with progress logging
                if file_count % 10 == 0:  # Log progress every 10 files
                    log.info(f"[REC-MANAGER] Processing file {file_count}: {os.path.basename(file)}")
                
                metadata = self._extract_metadata(file_path)
                if metadata:
                    self.metadata_cache[file_path] = metadata
                    processed_count += 1
                
                # CPU throttling: sleep briefly every few files to not overwhelm the system
                batch_count += 1
                if batch_count >= batch_size:
                    batch_count = 0
                    time.sleep(0.01)  # 10ms pause every 5 files to reduce CPU load
                    
                    # Check if we should yield more time for high file counts
                    if file_count % 50 == 0:
                        time.sleep(0.1)  # 100ms pause every 50 files for better system responsiveness
        
        log.info(f"[REC-MANAGER] Scan complete: {len(self.metadata_cache)} total files, {processed_count} processed, {skipped_count} skipped")
    
    def _is_video_file(self, filename):
        """Check if a file is a video file based on extension"""
        video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.ts', '.m4v')
        return filename.lower().endswith(video_extensions)
    
    def _extract_metadata(self, file_path):
        """Extract metadata from a video file with improved error handling"""
        try:
            # Get file stats
            file_stats = os.stat(file_path)
            file_size = file_stats.st_size
            file_mtime = file_stats.st_mtime
            
            # Skip very large files during initial scan to prevent blocking
            max_file_size = 2 * 1024 * 1024 * 1024  # 2GB limit for quick scan
            if file_size > max_file_size:
                log.warning(f"[REC-MANAGER] Skipping large file for quick scan: {os.path.basename(file_path)} ({file_size / (1024*1024*1024):.1f}GB)")
                return {
                    "path": file_path,
                    "filename": os.path.basename(file_path),
                    "size": file_size,
                    "date_time": datetime.datetime.fromtimestamp(file_mtime),
                    "timestamp": file_mtime,
                    "duration": file_size / (1024 * 1024) * 10,  # Rough estimate
                    "secrecy": "0",
                    "type": "all",
                    "device_id": None,
                    "scan_status": "quick_scan"  # Mark as quick scan
                }
            
            # Extract date and time from path or filename
            date_time = self._extract_datetime_from_path(file_path)
            
            # If we couldn't extract date/time from path, use file modification time
            if not date_time:
                date_time = datetime.datetime.fromtimestamp(file_mtime)
            
            # Try to get duration from file with timeout, fallback to estimating based on size
            duration = self._get_video_duration_with_timeout(file_path, timeout=5)
            if not duration:
                # Rough estimate: 1MB ~= 10 seconds for medium quality video
                duration = file_size / (1024 * 1024) * 10
            
            # Create metadata record
            return {
                "path": file_path,
                "filename": os.path.basename(file_path),
                "size": file_size,
                "date_time": date_time,
                "timestamp": date_time.timestamp(),
                "duration": duration,
                "secrecy": "0",  # Default secrecy level (0 = not secret)
                "type": "all",   # Default recording type (all = general recording)
                "device_id": None,  # Will be set by query method
                "scan_status": "complete"
            }
        except Exception as e:
            log.error(f"[REC-MANAGER] Error extracting metadata for {file_path}: {e}")
            return None
    
    def _extract_datetime_from_path(self, file_path):
        """Extract date and time information from file path"""
        try:
            # Get relative path
            rel_path = os.path.relpath(file_path, self.recordings_directory)
            parts = rel_path.split(os.path.sep)
            
            # Check if the directory structure contains a date
            date_match = None
            time_match = None
            
            # Look for date in YYYY-MM-DD format in directory names
            for part in parts:
                if re.match(r'^\d{4}-\d{2}-\d{2}$', part):
                    date_match = part
                    break
                    
            # If no date found in directories, try common date formats
            if not date_match:
                for part in parts:
                    # Try YYYYMMDD format
                    if re.match(r'^\d{8}$', part):
                        date_match = f"{part[0:4]}-{part[4:6]}-{part[6:8]}"
                        break
            
            # Get filename without extension
            filename = os.path.splitext(os.path.basename(file_path))[0]
            
            # Try to extract time from filename in format HH-MM-SS or HH:MM:SS
            time_match = re.search(r'(\d{2})[-:](\d{2})[-:](\d{2})', filename)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                second = int(time_match.group(3))
            else:
                # Default to noon if no time found
                hour, minute, second = 12, 0, 0
            
            # If we found a date, construct a datetime object
            if date_match:
                year, month, day = map(int, date_match.split('-'))
                return datetime.datetime(year, month, day, hour, minute, second)
            
            # If no date found, return None to use file modification time
            return None
            
        except Exception as e:
            log.error(f"[REC-MANAGER] Error extracting datetime from path {file_path}: {e}")
            return None
    
    def _get_video_duration_with_timeout(self, file_path, timeout=5):
        """Get video duration using ffmpeg with timeout to prevent blocking"""
        try:
            import subprocess
            
            # Use a shorter timeout for large files to prevent blocking
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                 "-of", "default=noprint_wrappers=1:nokey=1", file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout  # Add timeout to prevent blocking
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
                
            return None
        except subprocess.TimeoutExpired:
            log.warning(f"[REC-MANAGER] ffprobe timeout for {os.path.basename(file_path)}, using size estimation")
            return None
        except Exception as e:
            log.debug(f"[REC-MANAGER] ffprobe failed for {os.path.basename(file_path)}: {e}")
            return None
    
    def _get_video_duration(self, file_path):
        """Get video duration using ffmpeg if available (legacy method)"""
        return self._get_video_duration_with_timeout(file_path, timeout=10)
    
    def is_scan_complete(self):
        """Check if the initial scan is complete"""
        return not self.scanning and self.scan_thread and not self.scan_thread.is_alive()
    
    def get_scan_status(self):
        """Get current scan status"""
        return {
            "scanning": self.scanning,
            "files_cached": len(self.metadata_cache),
            "last_scan": self.last_scan_time,
            "scan_complete": self.is_scan_complete()
        }
    
    def query_recordings(self, device_id=None, start_time=None, end_time=None, 
                        recording_type=None, secrecy=None, max_results=100):
        """Query recordings based on time range and other filters
        
        Args:
            device_id (str): Device ID to use for the recordings
            start_time (str): Start time in ISO format or GB28181 format (YYYYMMDDTHHMMSSZ)
            end_time (str): End time in ISO format or GB28181 format (YYYYMMDDTHHMMSSZ)
            recording_type (str): Type of recording (all, alarm, manual, etc.)
            secrecy (str): Secrecy level of recordings
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of matching recording metadata
        """
        # Start a fresh scan if we don't have recent data (but don't wait for it)
        if time.time() - self.last_scan_time > self.scan_interval:
            self.start_async_scan()
        
        # Parse start and end times if provided
        start_timestamp = None
        end_timestamp = None
        
        if start_time:
            start_timestamp = self._parse_time_string(start_time)
            
        if end_time:
            end_timestamp = self._parse_time_string(end_time)
        
        # Default device ID if not provided
        if not device_id and 'sip' in self.config:
            device_id = self.config['sip'].get('device_id')
        
        # Filter recordings based on criteria
        results = []
        
        for path, metadata in self.metadata_cache.items():
            # Add the device ID to the metadata
            metadata['device_id'] = device_id
            
            # Apply time filters
            if start_timestamp and metadata['timestamp'] < start_timestamp:
                continue
                
            if end_timestamp and metadata['timestamp'] > end_timestamp:
                continue
                
            # Apply recording type filter
            if recording_type and recording_type != "all" and metadata.get('type') != recording_type:
                continue
                
            # Apply secrecy filter
            if secrecy and metadata.get('secrecy') != secrecy:
                continue
            
            results.append(metadata)
            
            # Limit results
            if len(results) >= max_results:
                break
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return results

    def _parse_time_string(self, time_str):
        """Parse a time string into a timestamp
        
        Supports ISO format (YYYY-MM-DDTHH:MM:SS) and
        GB28181 format (YYYYMMDDTHHMMSSZ)
        """
        try:
            # Try ISO format first
            try:
                dt = datetime.datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                return dt.timestamp()
            except ValueError:
                pass
                
            # Try GB28181 format (YYYYMMDDTHHMMSSZ)
            if 'T' in time_str and time_str.endswith('Z'):
                date_part = time_str.split('T')[0]
                time_part = time_str.split('T')[1].rstrip('Z')
                
                year = int(date_part[0:4])
                month = int(date_part[4:6])
                day = int(date_part[6:8])
                
                hour = int(time_part[0:2])
                minute = int(time_part[2:4])
                second = int(time_part[4:6])
                
                dt = datetime.datetime(year, month, day, hour, minute, second)
                return dt.timestamp()
                
            # If all parsing attempts fail, return None
            log.warning(f"[REC-MANAGER] Could not parse time string: {time_str}")
            return None
            
        except Exception as e:
            log.error(f"[REC-MANAGER] Error parsing time string {time_str}: {e}")
            return None

    def get_recording_path(self, recording_id):
        """Get the path to a recording by its ID (filename)"""
        # Scan recordings to ensure we have the latest
        self.scan_recordings()
        
        # Look for the recording by filename
        for path, metadata in self.metadata_cache.items():
            if metadata['filename'] == recording_id:
                return path
                
        # If not found by filename, try the path directly
        if os.path.exists(recording_id) and self._is_video_file(recording_id):
            return recording_id
            
        return None

    def get_recording_stream_uri(self, recording_id):
        """Get a stream URI for a recording by its ID"""
        # For now, just return the file path
        # This could be extended to support RTSP or other streaming protocols
        return self.get_recording_path(recording_id)

    def get_recordings_in_range(self, start_time, end_time):
        """Get recordings within the specified time range"""
        try:
            log.info(f"[REC-MANAGER] Querying recordings from {start_time} to {end_time}")
            
            # Parse the time strings using our existing parser
            start_timestamp = self._parse_time_string(start_time)
            end_timestamp = self._parse_time_string(end_time)
            
            if not start_timestamp or not end_timestamp:
                log.warning(f"[REC-MANAGER] Could not parse time range: {start_time} - {end_time}")
                return []
                
            # Ensure we have the latest recordings
            self.scan_recordings()
            
            matching_recordings = []
            
            # Find recordings that fall within the time range
            for path, metadata in self.metadata_cache.items():
                rec_timestamp = metadata['timestamp']
                
                if start_timestamp <= rec_timestamp <= end_timestamp:
                    # Create a copy with standardized field names for GB28181 response
                    recording_info = {
                        "device_id": metadata.get("device_id", self.config['sip'].get('device_id')),
                        "name": metadata.get("filename", ""),
                        "filename": metadata.get("filename", ""),
                        "path": path,
                        "address": "Local Recording",
                        "start_time": metadata.get("date_time").strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "timestamp": metadata.get("timestamp"),
                        "duration": metadata.get("duration", 3600),
                        "secrecy": metadata.get("secrecy", "0"),
                        "type": metadata.get("type", "time"),
                        "size": metadata.get("size", 0)
                    }
                    matching_recordings.append(recording_info)
                    
            log.info(f"[REC-MANAGER] Found {len(matching_recordings)} recordings in time range")
            return matching_recordings
            
        except Exception as e:
            log.error(f"[REC-MANAGER] Error getting recordings in range: {e}")
            return []

# Global instance
_recording_manager = None

def get_recording_manager(config):
    """Get the global recording manager instance"""
    global _recording_manager
    
    if _recording_manager is None:
        _recording_manager = RecordingManager(config)
        
    return _recording_manager 