# Frame Processing Feature Documentation

## Overview

The **Frame Processing Feature** in GB28181 Restreamer allows real-time manipulation and filtering of video frames during streaming. This feature enables you to apply various visual effects, overlays, and transformations to video content before it's sent to GB28181 platforms.

## What It Does

The frame processing system intercepts video frames in the GStreamer pipeline using **appsink/appsrc** elements, allowing Python code to:

1. **Extract frames** from the video stream
2. **Process frames** using OpenCV or other image processing libraries
3. **Re-inject processed frames** back into the stream
4. **Apply real-time effects** without stopping the stream

## Architecture

```
Video Input → GStreamer Pipeline → appsink → Frame Processor → appsrc → Output Stream
```

### Why Appsink/Appsrc?

**Appsink/Appsrc** is the standard GStreamer mechanism for:
- **appsink**: Extracting frames from a GStreamer pipeline into application code
- **appsrc**: Feeding processed frames back into a GStreamer pipeline

This is **not** unusual - it's the recommended approach for real-time frame processing in GStreamer applications.

## Built-in Frame Processors

The system includes several pre-built processors:

### 1. Grayscale Converter (`process_grayscale`)
```python
streamer.register_frame_processor("grayscale", process_grayscale)
```
- Converts color video to grayscale
- Useful for bandwidth reduction
- Maintains full resolution

### 2. Edge Detection (`process_edge_detection`)
```python
streamer.register_frame_processor("edge", process_edge_detection)
```
- Applies Canny edge detection
- Highlights object boundaries
- Useful for security/surveillance applications

### 3. Blur Filter (`process_blur`)
```python
streamer.register_frame_processor("blur", process_blur)
```
- Applies Gaussian blur
- Can be used for privacy protection
- Configurable blur intensity

### 4. Text Overlay (`process_add_text`)
```python
streamer.register_frame_processor("text", process_add_text)
```
- Adds timestamp overlays
- Displays system information
- Customizable text positioning and styling

## Use Cases

### 1. **Surveillance Systems**
- Add timestamps and camera information
- Apply privacy filters to sensitive areas
- Enhance image quality for better recognition

### 2. **Broadcasting**
- Add logo overlays
- Apply visual effects
- Real-time color correction

### 3. **Security Applications**
- Blur faces for privacy compliance
- Highlight motion detection areas
- Add security watermarks

### 4. **Analytics Integration**
- Draw bounding boxes around detected objects
- Overlay statistical information
- Highlight areas of interest

## How to Use

### Basic Usage
```python
# Register a frame processor
streamer.register_frame_processor("my_filter", my_custom_function)

# Enable processing for a stream
streamer.start_stream_with_processing(
    video_path="/path/to/video.mp4",
    dest_ip="192.168.1.100",
    dest_port=9000,
    frame_processor_callback=my_custom_function
)
```

### Custom Processor Function
```python
def my_custom_processor(frame, timestamp=None, stream_info=None):
    """
    Custom frame processor function
    
    Args:
        frame: NumPy array (RGB format)
        timestamp: Frame timestamp
        stream_info: Stream metadata
        
    Returns:
        tuple: (processed_frame, timestamp)
    """
    # Your processing logic here
    processed_frame = apply_custom_filter(frame)
    return processed_frame, timestamp
```

### Enable/Disable Processing
```python
# Enable processing for a specific stream
streamer.toggle_frame_processing(stream_id, enabled=True)

# Disable processing
streamer.toggle_frame_processing(stream_id, enabled=False)
```

## Performance Considerations

### CPU Usage
- Frame processing is **CPU intensive**
- Each processor adds computational overhead
- Consider frame rate vs. processing complexity

### Memory Usage
- Frames are temporarily stored in memory
- Buffer sizes are configurable
- Monitor memory usage with large resolutions

### Latency
- Processing adds **minimal latency** (typically <50ms per frame)
- Optimized for real-time applications
- Asynchronous processing prevents blocking

## Configuration

### Pipeline Settings
```json
{
  "pipeline": {
    "format": "RGB",
    "width": 640,
    "height": 480,
    "framerate": 30,
    "buffer_size": 33554432,
    "queue_size": 3000,
    "sync": false,
    "async": false
  }
}
```

### Buffer Configuration
- **buffer_size**: Memory allocated for frame buffers (32MB default)
- **queue_size**: Number of frames that can be queued (3000 default)
- **sync**: Synchronization mode (false for low latency)

## Technical Details

### Frame Format
- Frames are provided as **NumPy arrays** in **RGB format**
- Shape: `(height, width, 3)`
- Data type: `uint8`
- Color order: Red, Green, Blue

### Thread Safety
- Frame processing runs in **separate threads**
- Thread-safe queue management
- No blocking of main application

### Error Handling
- Graceful degradation on processing errors
- Automatic fallback to original frames
- Comprehensive logging

## Best Practices

1. **Keep processors lightweight** - avoid heavy computations
2. **Use appropriate resolutions** - balance quality vs. performance
3. **Monitor system resources** - watch CPU and memory usage
4. **Test thoroughly** - verify processing doesn't break streams
5. **Consider frame rate** - higher FPS = more processing load

## Troubleshooting

### High CPU Usage
- Reduce frame rate or resolution
- Optimize processor algorithms
- Use hardware acceleration when available

### Memory Issues
- Reduce buffer sizes
- Lower queue sizes
- Monitor for memory leaks in custom processors

### Processing Errors
- Check processor function signatures
- Verify frame format assumptions
- Add error handling in custom processors

## Integration with GB28181

The frame processing feature is **fully compatible** with GB28181 protocol:
- Processed frames maintain proper timing
- RTP packaging remains intact
- Stream metadata is preserved
- Compatible with all GB28181 platforms

This feature enhances the basic GB28181 streaming capability by allowing real-time video enhancement and analysis without breaking protocol compatibility. 