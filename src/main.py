# src/main.py

import json
import os
from file_scanner import scan_video_files
from rtsp_handler import start_rtsp_stream, play_video_file
from sip_handler import register_to_sip_server, handle_invite_request

def load_config(config_path):
    """Load configuration from a JSON file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r') as file:
        config = json.load(file)
    return config

def main():
    # Correct path to configuration
    current_dir = os.path.dirname(os.path.abspath(__file__))  # Gets this script's folder
    config_path = os.path.join(current_dir, '..', 'config', 'config.json')  # Navigate to config/

    # Normalize path
    config_path = os.path.normpath(config_path)

    config = load_config(config_path)
    print("[INFO] Configuration loaded successfully.")

    # Scan video files
    video_files = scan_video_files(config["stream_directory"])
    print(f"[INFO] Found {len(video_files)} video files:")
    for video in video_files:
        print(f" - {video}")

    # Start RTSP streams
    rtsp_sources = config.get("rtsp_sources", [])
    for rtsp_url in rtsp_sources:
        start_rtsp_stream(rtsp_url)

    # Play a sample video file
    if video_files:
        play_video_file(video_files[0])  # Play the first video file found

    # Simulate SIP Registration
    register_to_sip_server(config)

    # Simulate handling an INVITE request
    if video_files:
        handle_invite_request(video_files[0])

if __name__ == "__main__":
    main()
