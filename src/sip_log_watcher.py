import re
import time
from media_streamer import MediaStreamer
import os

LOG_FILE = "logs/sip.log"
VIDEO_FILE = "sample_videos/Entryyy.mp4"

streamer = MediaStreamer()

def extract_sdp_info(sdp_text):
    c_line = re.search(r"c=IN IP4 (\d+\.\d+\.\d+\.\d+)", sdp_text)
    m_line = re.search(r"m=video (\d+)", sdp_text)
    if c_line and m_line:
        ip = c_line.group(1)
        port = int(m_line.group(1))
        return ip, port
    return None, None

print("👀 Watching logs/sip.log for SIP INVITE...")

with open(LOG_FILE, "r") as f:
    f.seek(0, os.SEEK_END)  # Go to end of file

    while True:
        line = f.readline()
        if not line:
            time.sleep(0.5)
            continue

        if "Received INVITE" in line:
            print("📞 SIP INVITE detected. Waiting for SDP...")
            sdp = ""
            while True:
                l = f.readline()
                if not l or l.startswith("----"):
                    break
                sdp += l

            ip, port = extract_sdp_info(sdp)
            if ip and port:
                print(f"🎯 SDP target: {ip}:{port}")
                streamer.start_stream(VIDEO_FILE, ip, port)
            else:
                print("⚠️ Failed to extract SDP info.")
