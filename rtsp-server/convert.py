#!/usr/bin/env python3
"""
RTSP to HLS Converter
Converts RTSP streams to HLS format using FFmpeg
"""
import json
import subprocess
import os
import time
import signal
import sys
from pathlib import Path

STREAMS_FILE = "/app/streams.json"
HLS_DIR = "/hls"
SEGMENT_TIME = 2  # seconds per HLS segment
LIST_SIZE = 5     # number of segments in playlist

# Track running processes
processes = {}

def load_streams():
    """Load stream configurations from JSON file"""
    try:
        with open(STREAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading streams: {e}")
        return []

def start_ffmpeg(stream_id, rtsp_url):
    """Start FFmpeg process for a single stream"""
    output_dir = Path(HLS_DIR) / stream_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    playlist_path = output_dir / "playlist.m3u8"
    segment_path = output_dir / "segment%03d.ts"
    
    # FFmpeg command for RTSP to HLS conversion
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",          # Use TCP for stability
        "-i", rtsp_url,                     # Input RTSP stream
        "-c:v", "copy",                     # Copy video codec (no re-encoding)
        "-c:a", "aac",                      # Convert audio to AAC
        "-b:a", "128k",                     # Audio bitrate
        "-f", "hls",                        # Output format: HLS
        "-hls_time", str(SEGMENT_TIME),     # Segment duration
        "-hls_list_size", str(LIST_SIZE),   # Playlist size
        "-hls_flags", "delete_segments+append_list",  # Clean up old segments
        "-hls_segment_filename", str(segment_path),
        str(playlist_path)
    ]
    
    print(f"[{stream_id}] Starting: {rtsp_url[:50]}...")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        processes[stream_id] = process
        return True
    except Exception as e:
        print(f"[{stream_id}] Error starting FFmpeg: {e}")
        return False

def stop_all():
    """Stop all FFmpeg processes"""
    print("Stopping all streams...")
    for stream_id, process in processes.items():
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            process.kill()
    print("All streams stopped.")

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    stop_all()
    sys.exit(0)

def monitor_processes():
    """Monitor and restart failed processes"""
    streams = load_streams()
    stream_map = {s['id']: s['rtsp_url'] for s in streams}
    
    for stream_id, process in list(processes.items()):
        if process.poll() is not None:  # Process has exited
            print(f"[{stream_id}] Stream died, restarting...")
            if stream_id in stream_map:
                start_ffmpeg(stream_id, stream_map[stream_id])

def main():
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 50)
    print("RTSP to HLS Converter")
    print("=" * 50)
    
    # Load and start all streams
    streams = load_streams()
    print(f"Loaded {len(streams)} stream configurations")
    
    for stream in streams:
        stream_id = stream.get('id')
        rtsp_url = stream.get('rtsp_url')
        
        if stream_id and rtsp_url:
            start_ffmpeg(stream_id, rtsp_url)
            time.sleep(1)  # Stagger starts
    
    print(f"\nStarted {len(processes)} streams")
    print(f"HLS streams available at: http://localhost:8080/streams/")
    
    # Main loop - monitor processes
    while True:
        time.sleep(30)
        monitor_processes()

if __name__ == "__main__":
    main()
