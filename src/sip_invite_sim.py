from media_streamer import MediaStreamer
import os

streamer = MediaStreamer()

# 🔁 Simulate a SIP INVITE providing these parameters:
video_file = os.path.join("sample_videos", "Entryyy.mp4")
target_ip = "127.0.0.1"      # Pretend this came from SDP
target_port = 5004           # Ditto

streamer.start_stream(video_file, target_ip, target_port)
