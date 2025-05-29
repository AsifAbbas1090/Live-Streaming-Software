import gi
import os
import time

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)

# Set RTP destination
RTP_DEST_IP = "127.0.0.1"  # Send to local RTP listener
RTP_DEST_PORT = 9000       # Port where the stream_server is listening

# Find a sample video file
sample_dir = "./sample_videos/"
video_files = os.listdir(sample_dir)
if not video_files:
    print(f"No video files found in {sample_dir}. Please add a video file.")
    exit(1)

video_path = os.path.join(sample_dir, video_files[0])
print(f"Using video file: {video_path}")

# Create a simple pipeline to send H.264 RTP packets
pipeline_str = (
    f'filesrc location="{video_path}" ! '
    f'decodebin ! videoconvert ! videorate ! videoscale ! '
    f'video/x-raw,format=I420,framerate=25/1,width=704,height=576 ! '
    f'x264enc tune=zerolatency bitrate=1024 key-int-max=50 bframes=0 '
    f'byte-stream=true speed-preset=ultrafast quantizer=22 ! '
    f'rtph264pay config-interval=1 pt=96 ! '
    f'udpsink host={RTP_DEST_IP} port={RTP_DEST_PORT} sync=false async=false'
)

# Create and start the pipeline
print(f"Starting RTP test stream to {RTP_DEST_IP}:{RTP_DEST_PORT}")
print(f"Pipeline: {pipeline_str}")

try:
    pipeline = Gst.parse_launch(pipeline_str)
    pipeline.set_state(Gst.State.PLAYING)
    
    # Handle bus messages
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    
    # Create a GLib MainLoop to handle GStreamer events
    mainloop = GLib.MainLoop()
    
    def on_bus_message(bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End of stream")
            loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err.message}")
            loop.quit()
        return True
    
    bus.connect("message", on_bus_message, mainloop)
    
    print("Test stream started. Press Ctrl+C to stop...")
    mainloop.run()
    
except KeyboardInterrupt:
    print("Stopping test stream...")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'pipeline' in locals():
        pipeline.set_state(Gst.State.NULL)
    print("Test stream stopped.") 