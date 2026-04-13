import os
import time
import signal
import subprocess
import shutil
import logging
import threading
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
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

# === Z3 Stream Cache (its.go.kr CCTV appUrl map, stored in GitHub) ===
_z3_cache = {
    'data': None,       # dict: cctvip (str) -> appUrl (str)
    'fetched': None,    # datetime of last successful fetch
    'lock': threading.Lock()
}
Z3_CACHE_TTL_MINUTES = 50
Z3_GITHUB_RAW_URL = 'https://raw.githubusercontent.com/pyw31337/cctv/main/data/z3_cache.json'

def _refresh_z3_cache():
    """Fetch Z3 appUrl map from GitHub raw content. Caller must hold _z3_cache['lock']."""
    try:
        resp = requests.get(Z3_GITHUB_RAW_URL, timeout=30,
                            headers={'User-Agent': 'CCTV-Proxy/1.0',
                                     'Cache-Control': 'no-cache'})
        if resp.status_code != 200:
            logger.error(f"Z3: GitHub raw fetch failed: {resp.status_code}")
            return
        cache_data = resp.json()
        cctvip_map = cache_data.get('data', {})
        fetched_str = cache_data.get('fetched', 'unknown')
        _z3_cache['data'] = cctvip_map
        _z3_cache['fetched'] = datetime.now()
        logger.info(f"Z3 cache loaded: {len(cctvip_map)} entries (data from {fetched_str})")
    except Exception as e:
        logger.error(f"Z3 cache refresh failed: {e}")

def get_z3_app_url(cctvip):
    """Return appUrl for given cctvip, refreshing cache if needed."""
    with _z3_cache['lock']:
        now = datetime.now()
        needs_refresh = (
            _z3_cache['data'] is None or
            _z3_cache['fetched'] is None or
            now - _z3_cache['fetched'] > timedelta(minutes=Z3_CACHE_TTL_MINUTES)
        )
        if needs_refresh:
            _refresh_z3_cache()
    return (_z3_cache['data'] or {}).get(str(cctvip))

# Pre-warm Z3 cache on startup
def _prewarm_z3():
    with _z3_cache['lock']:
        _refresh_z3_cache()
threading.Thread(target=_prewarm_z3, daemon=True).start()


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

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return response

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
        # Some servers need specific Headers
        headers = {}
        if 'utic.go.kr' in target_url:
             headers["Referer"] = "https://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
             headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        elif 'jejuits.go.kr' in target_url:
             headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
             headers["Referer"] = "https://www.jejuits.go.kr/jido/mainView.do"
        elif 'cctvsec.ktict.co.kr' in target_url:
             headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
             headers["Referer"] = "https://its.go.kr/"

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
    now = datetime.now()
    target_time = now - timedelta(minutes=2)
    timestamp = target_time.strftime("%Y%m%d.%H%M00")

    # https://tportal.daejeon.go.kr:37084/01/media/CTV0008/CTV0008_20260211.140500.000.mp4
    real_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_{timestamp}.000.mp4"
    
    logger.info(f"Proxying Daejeon {cctv_id} -> {real_url}")
    return flask.redirect(real_url)

# === Jeju Proxy Logic ===
@app.route('/jeju')
@app.route('/jeju2')
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
        # Research results: Use POST to streamUrl.do with DEVICE_ID
        target_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Ensure we have a payload that matches what the browser sent
        payload = f"DEVICE_ID={target_id}"
        
        logger.info(f"Jeju: Fetching token for {target_id}...")
        resp = requests.post(target_api, data=payload, headers=headers, timeout=10, verify=False)
        
        if resp.status_code != 200:
            return f"Jeju API Error: {resp.status_code}", 502
            
        real_url = resp.text.strip().strip('"')
        
        # The API returns the full m3u8 URL with auth tokens
        if not real_url or not real_url.startswith("http"):
             logger.error(f"Invalid resp from Jeju API: {real_url}")
             return f"Invalid URL from Jeju API for {target_id}", 502

        # 2. Redirect to the local CORS-safe proxy instead of raw URL
        # Manifest rewriting handles relative segments automatically
        logger.info(f"Jeju {cctv_id} Success -> Proxying: {real_url[:60]}...")
        return flask.redirect(f"/proxy?url={quote(real_url)}")

    except Exception as e:
        logger.error(f"Jeju Proxy Final Failed: {e}")
        return f"Server Error: {str(e)}", 500

# === UTIC/NTIC Proxy Logic ===
@app.route('/utic')
def proxy_utic():
    """Resolves a fresh token for UTIC/NTIC (Highway) CCTV on request"""
    cctv_id = request.args.get('cctvid')
    if not cctv_id:
        return "Missing CCTVID", 400

    kind   = request.args.get('kind', '')
    cctvip = request.args.get('cctvip', '')

    # === Z3 kind: 국가교통정보센터(국도) ===
    # UTIC JSP does not support kind=Z3. Stream via its.go.kr + cctvsec.ktict.co.kr.
    if kind == 'Z3' and cctvip:
        try:
            app_url = get_z3_app_url(cctvip)
            if not app_url:
                logger.error(f"Z3: No appUrl found for cctvip={cctvip} ({cctv_id})")
                return f"Z3 stream not found for cctvip {cctvip}", 404

            # cctvsec.ktict.co.kr returns the signed m3u8 URL in the response body
            hls_resp = requests.get(
                app_url + '!hls', timeout=10, verify=False,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                         'Referer': 'https://its.go.kr/'})
            if hls_resp.status_code != 200:
                logger.error(f"Z3 !hls error {hls_resp.status_code} for {cctvip}")
                return f"Z3 HLS fetch failed: {hls_resp.status_code}", 502

            m3u8_url = hls_resp.text.strip()
            if not m3u8_url.startswith('http'):
                logger.error(f"Z3 unexpected body for {cctvip}: {m3u8_url[:80]}")
                return "Invalid Z3 stream URL", 502

            logger.info(f"Z3 {cctv_id} (cctvip={cctvip}) -> {m3u8_url[:70]}...")
            return flask.redirect(f"/proxy?url={quote(m3u8_url)}")

        except Exception as e:
            logger.error(f"Z3 Proxy Failed ({cctv_id}): {e}")
            return f"Server Error: {str(e)}", 500

    # === General UTIC: scrape the JSP page for an m3u8 URL ===
    params = {
        "key": os.environ.get('UTIC_KEY', 'yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI'),
        "cctvid": cctv_id,
        "cctvName": request.args.get('cctvName', ''),
        "kind": kind,
        "cctvip": cctvip,
        "cctvch": request.args.get('cctvch', ''),
        "id": request.args.get('id', ''),
        "cctvpasswd": request.args.get('cctvpasswd', ''),
        "cctvport": request.args.get('cctvport', '')
    }

    query_string = urlencode({k: v for k, v in params.items() if v})
    jsp_url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?{query_string}"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.utic.go.kr/guide/cctvOpenData.do"
        }
        resp = requests.get(jsp_url, headers=headers, timeout=10, verify=False)
        if resp.status_code != 200:
            return f"UTIC JSP Error: {resp.status_code}", 502

        html = resp.text
        patterns = [
            r'src="([^"]+\.m3u8[^"]*)"',
            r'source\s+src="([^"]+)"\s+type="application/x-mpegURL"',
            r'var\s+[lh]url\s*=\s*"([^"]+)"'
        ]

        real_url = None
        for pat in patterns:
            match = re.search(pat, html)
            if match:
                real_url = match.group(1)
                break

        if not real_url:
            return f"Failed to extract stream for {cctv_id}", 404

        if not real_url.startswith("http"):
            if real_url.startswith("/"):
                real_url = f"https://www.utic.go.kr{real_url}"

        logger.info(f"Resolved UTIC {cctv_id} -> {real_url[:60]}...")
        return flask.redirect(f"/proxy?url={quote(real_url)}")

    except Exception as e:
        logger.error(f"UTIC Proxy Failed: {e}")
        return f"Server Error: {str(e)}", 500


# === KB / Loomex (경기도·부산 CCTV via kbsapi.loomex.net) Proxy Logic ===
@app.route('/kb')
def proxy_kb():
    """Fetches a fresh Loomex (kbsapi) stream URL for a given cctvip via utic.go.kr."""
    cctvip = request.args.get('cctvip')
    if not cctvip:
        return "Missing cctvip", 400

    utic_api_url = f"https://www.utic.go.kr/map/getGyeonggiCctvUrl.do?cctvIp={cctvip}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.utic.go.kr/guide/cctvOpenData.do"
    }

    try:
        resp = requests.get(utic_api_url, headers=headers, timeout=10, verify=False)
        if resp.status_code != 200:
            return f"UTIC KB API error: {resp.status_code}", 502

        kbs_url = resp.text.strip()
        if not kbs_url or kbs_url == 'null':
            return f"No stream URL for cctvip {cctvip}", 404

        if kbs_url.startswith("//"):
            kbs_url = "https:" + kbs_url

        if not kbs_url.startswith("http"):
            return f"Unexpected URL format: {kbs_url[:50]}", 502

        logger.info(f"KB {cctvip} -> {kbs_url[:70]}...")
        return flask.redirect(f"/proxy?url={quote(kbs_url)}")

    except Exception as e:
        logger.error(f"KB Proxy Failed ({cctvip}): {e}")
        return f"Server Error: {str(e)}", 500


# === GiTS (경기도 교통정보서비스) Proxy Logic ===
@app.route('/gits')
def proxy_gits():
    """Fetches a fresh GiTS stream URL on-demand for a given cctvip (GiTS cctvId)."""
    cctvip = request.args.get('cctvip')
    if not cctvip:
        return "Missing cctvip", 400

    popup_url = f"https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId={cctvip}"
    gits_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://gits.gg.go.kr/web/map/webMap.do?opt=3"
    }

    try:
        resp = requests.get(popup_url, headers=gits_headers, timeout=10)
        if resp.status_code != 200:
            return f"GiTS popup error: {resp.status_code}", 502

        html = resp.text

        # Extract the !hls token URL (preferred - returns signed m3u8)
        match_hls = re.search(r'\$\.get\("([^"]+!hls)"', html)
        if match_hls:
            hls_token_url = match_hls.group(1)
            if hls_token_url.startswith("//"):
                hls_token_url = "https:" + hls_token_url
            hls_resp = requests.get(hls_token_url, headers=gits_headers, timeout=10)
            if hls_resp.status_code == 200:
                m3u8_url = hls_resp.text.strip()
                if m3u8_url.startswith("http"):
                    logger.info(f"GiTS {cctvip} -> {m3u8_url[:70]}...")
                    return flask.redirect(f"/proxy?url={quote(m3u8_url)}")

        # Fallback: videoUrl (direct stream, no token resolution needed)
        match_video = re.search(r'var videoUrl = "(http[^"]+)"', html)
        if match_video:
            video_url = match_video.group(1).replace("http://", "https://")
            logger.info(f"GiTS {cctvip} (videoUrl fallback) -> {video_url[:70]}...")
            return flask.redirect(f"/proxy?url={quote(video_url)}")

        return f"GiTS: stream not found for cctvip {cctvip}", 404

    except Exception as e:
        logger.error(f"GiTS Proxy Failed ({cctvip}): {e}")
        return f"Server Error: {str(e)}", 500


if __name__ == '__main__':
    # Ensure HLS dir exists
    shutil.rmtree(HLS_DIR, ignore_errors=True)
    os.makedirs(HLS_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=8080)
