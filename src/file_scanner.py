# src/file_scanner.py

import os

def scan_video_files(directory):
    """
    Scans a given directory (and its subdirectories) for .mp4 and .avi files.
    Returns a list of full file paths.
    """
    supported_formats = ('.mp4', '.avi')
    video_files = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(supported_formats):
                video_files.append(os.path.join(root, file))
    
    return video_files
