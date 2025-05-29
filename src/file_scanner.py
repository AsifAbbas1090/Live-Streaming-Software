# src/file_scanner.py

import os
from logger import log

# Internal catalog storage
_video_catalog = []

def scan_video_files(directory):
    """
    Scans a given directory (and its subdirectories) for .mp4 and .avi files.
    Updates and returns the internal catalog.
    """
    global _video_catalog
    _video_catalog = []  # Reset on every scan

    supported_formats = ('.mp4', '.avi')
    
    # Convert to absolute path
    abs_directory = os.path.abspath(directory)
    log.info(f"[SCAN] Scanning directory: {abs_directory}")
    
    if not os.path.isdir(abs_directory):
        log.warning(f"[SCAN] Invalid directory: {abs_directory}")
        return []

    for root, dirs, files in os.walk(abs_directory):
        log.debug(f"[SCAN] Scanning subdirectory: {root}")
        log.debug(f"[SCAN] Found subdirectories: {dirs}")
        log.debug(f"[SCAN] Found files: {files}")
        
        for file in files:
            if file.lower().endswith(supported_formats):
                full_path = os.path.join(root, file)
                _video_catalog.append(full_path)
                log.debug(f"[SCAN] Added video file: {full_path}")

    log.info(f"[SCAN] Found {len(_video_catalog)} video files.")
    return _video_catalog

def get_video_catalog():
    """
    Returns the cached catalog of video files.
    """
    return _video_catalog
