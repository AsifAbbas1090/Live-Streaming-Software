# src/file_scanner.py

import os
import threading
from logger import log

# Internal catalog storage with thread safety
_video_catalog = []
_catalog_lock = threading.Lock()

def scan_video_files(directory):
    """
    Scans a given directory (and its subdirectories) for video files.
    Updates and returns the internal catalog with thread safety.
    """
    global _video_catalog
    
    # Thread-safe catalog update
    with _catalog_lock:
        _video_catalog = []  # Reset on every scan

        # Expanded list of supported video formats
        supported_formats = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts', '.mts')
        
        # Convert to absolute path
        abs_directory = os.path.abspath(directory)
        log.info(f"[SCAN] 📁 Scanning directory: {abs_directory}")
        
        if not os.path.isdir(abs_directory):
            log.warning(f"[SCAN] ❌ Invalid directory: {abs_directory}")
            return []

        total_files_scanned = 0
        video_files_found = 0
        
        try:
            for root, dirs, files in os.walk(abs_directory):
                log.debug(f"[SCAN] 📂 Scanning subdirectory: {root}")
                log.debug(f"[SCAN] 📁 Found {len(dirs)} subdirectories: {dirs[:5]}{'...' if len(dirs) > 5 else ''}")
                log.debug(f"[SCAN] 📄 Found {len(files)} files")
                
                for file in files:
                    total_files_scanned += 1
                    if file.lower().endswith(supported_formats):
                        full_path = os.path.join(root, file)
                        _video_catalog.append(full_path)
                        video_files_found += 1
                        log.debug(f"[SCAN] ✅ Added video file: {full_path}")
                        
                        # Limit logging for large directories
                        if video_files_found <= 10:
                            log.info(f"[SCAN] Found video: {os.path.basename(file)}")
                        elif video_files_found == 11:
                            log.info(f"[SCAN] ... (limiting log output, found many more videos)")
                            
        except Exception as e:
            log.error(f"[SCAN] ❌ Error during directory scan: {e}")
            
        log.info(f"[SCAN] 📊 Scan complete: Found {video_files_found} video files out of {total_files_scanned} total files")
        
        if video_files_found == 0:
            log.warning(f"[SCAN] ⚠️ No video files found in {abs_directory}")
            log.info(f"[SCAN] 📋 Supported formats: {', '.join(supported_formats)}")
            
            # List some files for debugging
            try:
                sample_files = []
                for root, dirs, files in os.walk(abs_directory):
                    sample_files.extend(files[:10])  # Get first 10 files
                    if len(sample_files) >= 10:
                        break
                if sample_files:
                    log.info(f"[SCAN] 📄 Sample files found: {sample_files[:5]}")
            except:
                pass
        
        # WVP optimization: limit catalog size to prevent timeouts
        if len(_video_catalog) > 20:
            log.warning(f"[SCAN] WVP Optimization: Limiting catalog from {len(_video_catalog)} to 20 files")
            _video_catalog = _video_catalog[:20]
        
        # Return a copy to ensure thread safety
        return _video_catalog.copy()

def get_video_catalog():
    """
    Returns a thread-safe copy of the cached catalog of video files.
    """
    with _catalog_lock:
        # Return a copy for thread safety
        return _video_catalog.copy()

def get_catalog_summary():
    """
    Returns a summary of the current catalog for debugging with thread safety.
    """
    catalog = get_video_catalog()  # This already returns a thread-safe copy
    if not catalog:
        return "No videos in catalog"
    
    summary = f"{len(catalog)} videos found"
    if catalog:
        # Group by directory
        dirs = {}
        for video in catalog:
            dirname = os.path.dirname(video)
            if dirname not in dirs:
                dirs[dirname] = 0
            dirs[dirname] += 1
        
        if len(dirs) <= 3:
            for dirname, count in dirs.items():
                summary += f"\n  {dirname}: {count} videos"
        else:
            summary += f"\n  Spread across {len(dirs)} directories"
            
    return summary
