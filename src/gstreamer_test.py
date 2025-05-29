import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

pipeline = Gst.parse_launch(
    "filesrc location=sample_videos/Entryyy.mp4 ! decodebin ! fakesink"
)

bus = pipeline.get_bus()
pipeline.set_state(Gst.State.PLAYING)

print("🔄 Playing MP4 file (headless)...")

# Wait until error or EOS
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
