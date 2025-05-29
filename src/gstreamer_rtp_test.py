import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

DEST_IP = "127.0.0.1"  # You can change this to your SIP peer IP later
DEST_PORT = 5004       # Choose any test port (later matched via SIP/SDP)

pipeline_str = f"""
filesrc location=sample_videos/Entryyy.mp4 !
decodebin name=dec

dec. ! queue ! x264enc tune=zerolatency bitrate=512 speed-preset=ultrafast !
rtph264pay config-interval=1 pt=96 !
udpsink host={DEST_IP} port={DEST_PORT} sync=false async=false
"""

pipeline = Gst.parse_launch(pipeline_str)
bus = pipeline.get_bus()

pipeline.set_state(Gst.State.PLAYING)
print(f"🚀 Sending RTP stream to {DEST_IP}:{DEST_PORT}...")

while True:
    msg = bus.timed_pop_filtered(
        Gst.CLOCK_TIME_NONE,
        Gst.MessageType.ERROR | Gst.MessageType.EOS
    )
    if msg:
        if msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            print(f"❌ Error: {err.message}")
        elif msg.type == Gst.MessageType.EOS:
            print("✅ End of stream.")
        break

pipeline.set_state(Gst.State.NULL)
