import subprocess
import sys
import os
import pathlib

GSTREAMER_PATH = r"C:\Program Files\gstreamer\1.0\msvc_x86_64\bin\gst-launch-1.0.exe"

def start_rtsp_stream(rtsp_url):
    print(f"[INFO] Launching RTSP stream: {rtsp_url}")

    gst_command = [
        GSTREAMER_PATH,
        "rtspsrc", f"location={rtsp_url}", "latency=0", "!",
        "rtph264depay", "!",
        "h264parse", "!",
        "avdec_h264", "!",
        "videoconvert", "!",
        "autovideosink"
    ]

    try:
        subprocess.Popen(gst_command, stdout=sys.stdout, stderr=sys.stderr)
        print("[INFO] GStreamer pipeline started successfully for RTSP stream.")
    except Exception as e:
        print(f"[ERROR] Failed to start RTSP stream: {e}")

def play_video_file(file_path):
    import pathlib
    print(f"[INFO] Playing video file: {file_path}")

    # Convert Windows path to a GStreamer file URI
    file_uri = pathlib.Path(file_path).as_uri()
    print(f"[DEBUG] Converted file URI: {file_uri}")

    gst_command = [
        GSTREAMER_PATH,
        "urisourcebin", f"uri={file_uri}", "!",
        "decodebin", "!",
        "videoconvert", "!",
        "autovideosink"
    ]

    try:
        subprocess.Popen(gst_command, stdout=sys.stdout, stderr=sys.stderr)
        print("[INFO] GStreamer pipeline started successfully for video file.")
    except Exception as e:
        print(f"[ERROR] Failed to play video file: {e}")
