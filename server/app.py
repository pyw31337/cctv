import os
import time
import signal
import subprocess
import shutil
import logging
import threading
import hashlib
from urllib.parse import quote
import flask
from flask import Flask, request, Response, send_from_directory, abort
import requests

# Configuration
HLS_DIR = os.environ.get('HLS_DIR', '/tmp/hls')
IDLE_TIMEOUT = 30  # Seconds to keep stream alive without viewers
MAX_STREAMS = 2    # Hard limit on concurrent FFmpeg processes (CPU safety)

# App initialized below with static folder config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
streams = {}  # { stream_id: { 'process': Popen, 'last_access': time, 'url': url } }
lock = threading.Lock()

def get_stream_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def kill_stream(stream_id):
    with lock:
        if stream_id in streams:
            logger.info(f"Killing idle stream: {stream_id}")
            proc = streams[stream_id]['process']
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=5)
            except:
                proc.kill()
            
            # Cleanup files
            stream_dir = os.path.join(HLS_DIR, stream_id)
            if os.path.exists(stream_dir):
                shutil.rmtree(stream_dir, ignore_errors=True)
            
            del streams[stream_id]

def cleanup_loop():
    while True:
        time.sleep(5)
        now = time.time()
        to_kill = []
        with lock:
            for sid, data in streams.items():
                if now - data['last_access'] > IDLE_TIMEOUT:
                    to_kill.append(sid)
        
        for sid in to_kill:
            kill_stream(sid)

# Start background cleanup
threading.Thread(target=cleanup_loop, daemon=True).start()

app = Flask(__name__, static_folder='../', static_url_path='')

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

@app.route('/stream')
def stream_video():
    url = request.args.get('url')
    if not url:
        return "Missing URL", 400
    
    stream_id = get_stream_id(url)
    stream_dir = os.path.join(HLS_DIR, stream_id)
    playlist_path = os.path.join(stream_dir, 'index.m3u8')
    
    with lock:
        # Update keepalive
        if stream_id in streams:
            streams[stream_id]['last_access'] = time.time()
        else:
            # Check limits
            if len(streams) >= MAX_STREAMS:
                return "Server busy (max streams reached)", 503
                
            # Start new stream
            os.makedirs(stream_dir, exist_ok=True)
            
            # FFmpeg: Low CPU preset, low FPS, scaled down
            cmd = [
                'ffmpeg',
                '-rtsp_transport', 'tcp',
                '-i', url,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-r', '15',             # 15 FPS
                '-vf', 'scale=-2:360',  # 360p height
                '-g', '30',             # Keyframe every 2s
                '-sc_threshold', '0',
                '-hls_time', '2',
                '-hls_list_size', '3',
                '-hls_flags', 'delete_segments',
                '-f', 'hls',
                os.path.join(stream_dir, 'index.m3u8')
            ]
            
            logger.info(f"Starting FFmpeg for {stream_id}")
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            streams[stream_id] = {
                'process': proc,
                'last_access': time.time(),
                'url': url
            }
            
            # Wait a bit for the first segment
            time.sleep(3)

    # Redirect to the HLS endpoint so relative TS segments work
    return flask.redirect(f"/hls/{stream_id}/index.m3u8")

@app.route('/hls/<stream_id>/<filename>')
def serve_hls(stream_id, filename):
    # Security check
    if '..' in stream_id or '..' in filename:
        abort(400)
        
    with lock:
        if stream_id in streams:
            streams[stream_id]['last_access'] = time.time()
            
    return send_from_directory(os.path.join(HLS_DIR, stream_id), filename)

@app.route('/proxy')
def proxy_stream():
    """Simple pass-through proxy for SSL/CORS issues"""
    target_url = request.args.get('url')
    if not target_url:
        return "Missing URL", 400
        
    try:
        # Some servers (UTIC) need Headers
        headers = {}
        if 'utic.go.kr' in target_url:
             headers["Referer"] = "https://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
             headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        elif 'jejuits.go.kr' in target_url:
             headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
             headers["Referer"] = "https://www.jejuits.go.kr/jido/mainView.do"

        # Fetch the target URL
        resp = requests.get(target_url, stream=True, timeout=15, verify=False, headers=headers, allow_redirects=True)
        
        # Use stream=False for manifest rewriting if it's a small text file
        # But for video segments (TS), we want streaming.
        is_manifest = target_url.endswith('.m3u8') or 'application/vnd.apple.mpegurl' in resp.headers.get('Content-Type', '').lower()
        
        if is_manifest:
            content = resp.text
            # Rewrite relative paths to absolute proxied paths
            # Jeju uses /hls/....ts
            base_parts = target_url.split('/')
            base_url = "/".join(base_parts[:3]) # https://host:port
            
            # Replace lines starting with / or not starting with http
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    if line.startswith('/'):
                        # Absolute path within source: /hls/abc.ts -> /proxy?url=base_url/hls/abc.ts
                        full_segment_url = f"{base_url}{line}"
                        new_lines.append(f"/proxy?url={quote(full_segment_url)}")
                    elif not line.startswith('http'):
                        # Relative path: abc.ts -> /proxy?url=current_dir/abc.ts
                        current_dir = "/".join(base_parts[:-1])
                        full_segment_url = f"{current_dir}/{line}"
                        new_lines.append(f"/proxy?url={quote(full_segment_url)}")
                    else:
                        # Already absolute http: -> /proxy?url=...
                        new_lines.append(f"/proxy?url={quote(line)}")
                else:
                    new_lines.append(line)
            
            rewritten_content = "\n".join(new_lines).encode('utf-8')
            
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'access-control-allow-origin', 'content-type']
            resp_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                       if name.lower() not in excluded_headers]
            resp_headers.append(('Access-Control-Allow-Origin', '*'))
            resp_headers.append(('Content-Type', 'application/vnd.apple.mpegurl'))
            
            return Response(rewritten_content, resp.status_code, resp_headers)
        
        # Binary/Streaming for TS segments
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                yield chunk

        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'access-control-allow-origin']
        resp_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        # Add CORS (Force single *)
        resp_headers.append(('Access-Control-Allow-Origin', '*'))
        
        return Response(generate(), resp.status_code, resp_headers)
    except Exception as e:
        logger.error(f"Proxy error for {target_url}: {e}")
        return f"Proxy error: {str(e)}", 502

# === Daejeon Proxy Logic ===
@app.route('/daejeon')
def proxy_daejeon():
    cctv_id = request.args.get('id')
    if not cctv_id:
        return "Missing ID", 400

    # Clean ID: DAEJEON_CCTV08 -> CTV0008
    clean_id = cctv_id.replace("DAEJEON_", "")
    stream_id = clean_id
    if clean_id.startswith("CCTV"):
        num = clean_id[4:] # "08"
        stream_id = f"CTV{num.zfill(4)}"

    # Generate Timestamp (current - 2 mins to be safe)
    from datetime import datetime, timedelta
    now = datetime.now()
    target_time = now - timedelta(minutes=2)
    timestamp = target_time.strftime("%Y%m%d.%H%M00")

    # Construct URL
    # https://tportal.daejeon.go.kr:37084/01/media/CTV0008/CTV0008_20260211.140500.000.mp4
    real_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_{timestamp}.000.mp4"
    
    logger.info(f"Proxying Daejeon {cctv_id} -> {real_url}")
    return flask.redirect(real_url)

# === Jeju Proxy Logic ===
@app.route('/jeju')
def proxy_jeju():
    cctv_id = request.args.get('id')
    if not cctv_id:
        return "Missing ID", 400

    # Clean ID
    short_id = cctv_id.replace("JEJU_", "")
    
    # 0. Check if we need to resolve Short ID -> UUID
    target_id = short_id
    if len(short_id) < 20: # Likely a short ID like 'C62'
        try:
            info_url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest"
            }
            # Need maplevel param or it might fail? Script used "maplevel": "14"
            payload = {
                "DEVICE_KIND": "CCTV",
                "DEVICE_ID": short_id,
                "maplevel": "14"
            }
            
            logger.info(f"Resolving UUID for {short_id}...")
            resp = requests.post(info_url, data=payload, headers=headers, timeout=5, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if 'stremid' in data:
                    target_id = data['stremid']
                    logger.info(f"Resolved {short_id} -> {target_id}")
                else:
                    logger.warning(f"No stremid in info for {short_id}: {data}")
        except Exception as e:
            logger.error(f"Failed to resolve UUID: {e}")
            # Continue with short_id just in case, or fail?
            # likely fail, but let's try.

    # 1. Fetch fresh Auth Key using UUID (target_id)
    try:
        target_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.jejuits.go.kr/jido/mainView.do?DEVICE_KIND=CCTV",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        payload = {"DEVICE_ID": target_id}
        
        resp = requests.post(target_api, data=payload, headers=headers, timeout=5, verify=False)
        if resp.status_code != 200:
            return f"Jeju API Error: {resp.status_code}", 502
            
        real_url = resp.text.strip().strip('"')
        
        if not real_url.startswith("http"):
             return f"Invalid URL from Jeju API for {target_id}: {real_url}", 502

        # 2. Redirect to the local CORS-safe proxy instead of raw URL
        logger.info(f"Jeju {cctv_id} -> Redirecting to CORS proxy for {real_url}")
        return flask.redirect(f"/proxy?url={quote(real_url)}")

    except Exception as e:
        logger.error(f"Jeju Proxy Failed: {e}")
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    # Ensure HLS dir exists
    shutil.rmtree(HLS_DIR, ignore_errors=True)
    os.makedirs(HLS_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=8080)
