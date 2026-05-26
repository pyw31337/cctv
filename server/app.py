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
import base64
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode, urljoin, unquote
import flask
from flask import Flask, request, Response, send_from_directory, abort
import requests

TRANSIENT_UPSTREAM_STATUSES = {502, 503, 504}

# Configuration
HLS_DIR = os.environ.get('HLS_DIR', '/tmp/hls')
IDLE_TIMEOUT = 30  # Seconds to keep stream alive without viewers
MAX_STREAMS = 2    # Hard limit on concurrent FFmpeg processes (CPU safety)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEALTH_STATUS_FILE = os.environ.get('HEALTH_STATUS_FILE', os.path.join(ROOT_DIR, 'data', 'status.json'))
CANARY_STATUS_FILE = os.environ.get('CANARY_STATUS_FILE', os.path.join(ROOT_DIR, 'data', 'canary_status.json'))
OPS_STATUS_FILE = os.environ.get('OPS_STATUS_FILE', os.path.join(ROOT_DIR, 'data', 'ops_status.json'))
CANARY_HISTORY_FILE = os.environ.get('CANARY_HISTORY_FILE', os.path.join(ROOT_DIR, 'data', 'canary_history.json'))

# App initialized below with static folder config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
streams = {}  # { stream_id: { 'process': Popen, 'last_access': time, 'url': url } }
lock = threading.Lock()

# === Z3 Stream Cache (its.go.kr CCTV appUrl map) ===
_z3_cache = {
    'data': None,       # dict: cctvip (str) -> appUrl (str)
    'fetched': None,    # datetime when this process loaded/refreshed the cache
    'data_fetched': None,  # datetime embedded in the cache payload
    'local_mtime': None,   # filesystem mtime for the local JSON that populated memory
    'source': None,     # local, github, its.go.kr, or stale fallback source
    'lock': threading.Lock()
}
Z3_CACHE_TTL_MINUTES = 50
Z3_CACHE_STALE_HOURS = 2   # If GitHub data is older than this, try its.go.kr directly
Z3_GITHUB_RAW_URL = 'https://raw.githubusercontent.com/pyw31337/cctv/main/data/z3_cache.json'
Z3_LOCAL_CACHE_FILE = os.environ.get('Z3_LOCAL_CACHE_FILE', os.path.join(ROOT_DIR, 'data', 'z3_cache.json'))

JEJU_STREAM_CACHE_TTL_SECONDS = 120
jeju_session = requests.Session()
jeju_session.verify = False
jeju_lock = threading.Lock()
jeju_stream_cache = {}


def load_jeju_id_map():
    """Load stable short-id to stream UUID mappings recovered from Jeju data."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.environ.get('JEJU_ID_MAP_PATH'),
        os.path.join(root_dir, 'data', 'jeju_id_map.json'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jeju_id_map.json'),
    ]
    for path in [candidate for candidate in candidates if candidate]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                logger.info("Jeju: loaded %d short-id mappings from %s", len(data), path)
                return data
            logger.warning("Jeju: ID map at %s was not an object", path)
        except FileNotFoundError:
            continue
        except Exception as exc:
            logger.warning("Jeju: failed to load ID map from %s: %s", path, exc)
    logger.warning("Jeju: no local short-id map loaded")
    return {}


JEJU_ID_MAP = load_jeju_id_map()


def utc_now():
    return datetime.utcnow()


def parse_z3_fetched(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return None


def z3_age_hours(fetched):
    if not fetched:
        return None
    return (utc_now() - fetched).total_seconds() / 3600


def get_z3_local_cache_mtime():
    try:
        return os.path.getmtime(Z3_LOCAL_CACHE_FILE)
    except OSError:
        return None


def z3_local_cache_updated():
    current_mtime = get_z3_local_cache_mtime()
    known_mtime = _z3_cache.get('local_mtime')
    return bool(current_mtime and known_mtime and current_mtime > known_mtime + 0.001)


def set_z3_cache_data(cctvip_map, source, data_fetched=None, local_mtime=None):
    _z3_cache['data'] = cctvip_map
    _z3_cache['fetched'] = utc_now()
    _z3_cache['data_fetched'] = data_fetched or utc_now()
    _z3_cache['local_mtime'] = local_mtime
    _z3_cache['source'] = source


def load_z3_cache_payload(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        cctvip_map = payload.get('data', {}) if isinstance(payload, dict) else {}
        data_fetched = parse_z3_fetched(payload.get('fetched')) if isinstance(payload, dict) else None
        if isinstance(cctvip_map, dict) and cctvip_map:
            return cctvip_map, data_fetched
    except FileNotFoundError:
        return None, None
    except Exception as exc:
        logger.warning("Z3: failed to load local cache %s: %s", path, exc)
    return None, None


def save_z3_local_cache(cctvip_map):
    try:
        os.makedirs(os.path.dirname(Z3_LOCAL_CACHE_FILE), exist_ok=True)
        payload = {
            'fetched': utc_now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'entries': len(cctvip_map),
            'data': cctvip_map,
        }
        tmp_path = f"{Z3_LOCAL_CACHE_FILE}.tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))
            f.write('\n')
        os.replace(tmp_path, Z3_LOCAL_CACHE_FILE)
    except Exception as exc:
        logger.warning("Z3: failed to persist local cache %s: %s", Z3_LOCAL_CACHE_FILE, exc)


def get_jeju_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }


def redirect_cached_jeju_stream(target_id):
    with jeju_lock:
        cached = jeju_stream_cache.get(target_id)
    if not cached:
        return None

    age = time.time() - cached.get('created_at', 0)
    if age > JEJU_STREAM_CACHE_TTL_SECONDS:
        with jeju_lock:
            jeju_stream_cache.pop(target_id, None)
        return None

    return flask.redirect(cached['url'])


def _refresh_z3_from_its():
    """Fetch Z3 appUrl map directly from its.go.kr.
    Works when the server is in a region with access to Korean government sites (e.g. Tokyo).
    Caller must hold _z3_cache['lock']. Returns True if successful."""
    try:
        s = requests.Session()
        s.verify = False
        logger.info("Z3: Attempting direct its.go.kr refresh...")

        r = s.get('https://its.go.kr/', timeout=15,
                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        xsrf = s.cookies.get('XSRF-TOKEN', '')
        if not xsrf:
            logger.warning("Z3: No XSRF token from its.go.kr - server IP may be geo-blocked")
            return False

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://its.go.kr/',
            'Content-Type': 'application/json',
            'X-XSRF-TOKEN': xsrf,
            'Accept': 'application/json',
        }
        r2 = s.post('https://its.go.kr/map/getMarkers',
                    data=json.dumps({'body': {'data': {'type': 'CCTV'}}}),
                    headers=headers, timeout=120)

        if r2.status_code != 200:
            logger.error(f"Z3: its.go.kr getMarkers returned {r2.status_code}")
            return False

        features = r2.json().get('features', [])
        cctvip_map = {}
        for f in features:
            props = f.get('properties', {})
            info_str = props.get('INFO', '{}')
            try:
                info = json.loads(info_str) if isinstance(info_str, str) else info_str
            except Exception:
                continue
            app_url = info.get('appUrl', '')
            if app_url and 'cctvsec.ktict.co.kr' in app_url:
                parts = app_url.split('/')
                if len(parts) >= 4:
                    cctvip_map[parts[3]] = app_url

        if not cctvip_map:
            logger.error("Z3: No entries extracted from its.go.kr getMarkers")
            return False

        set_z3_cache_data(cctvip_map, 'its.go.kr', utc_now())
        save_z3_local_cache(cctvip_map)
        logger.info(f"Z3 cache refreshed from its.go.kr: {len(cctvip_map)} entries")
        return True
    except Exception as e:
        logger.error(f"Z3: Direct its.go.kr refresh failed: {e}")
        return False


def _refresh_z3_cache():
    """Fetch Z3 appUrl map. Tries GitHub cached file first; if stale, falls back to
    direct its.go.kr fetch. Caller must hold _z3_cache['lock']."""
    # Step 1: Prefer the local Oracle cache written by cron or previous refresh.
    local_mtime = get_z3_local_cache_mtime()
    local_map, local_fetched = load_z3_cache_payload(Z3_LOCAL_CACHE_FILE)
    local_age_hours = z3_age_hours(local_fetched)
    if local_map and (local_age_hours is None or local_age_hours < Z3_CACHE_STALE_HOURS):
        set_z3_cache_data(local_map, 'local', local_fetched, local_mtime)
        age_str = f"{local_age_hours:.1f}h" if local_age_hours is not None else "unknown age"
        logger.info(f"Z3 cache from local file: {len(local_map)} entries (data age: {age_str})")
        return

    # Step 2: Try GitHub raw URL as a static fallback.
    try:
        resp = requests.get(Z3_GITHUB_RAW_URL, timeout=30,
                            headers={'User-Agent': 'CCTV-Proxy/1.0',
                                     'Cache-Control': 'no-cache'})
        if resp.status_code == 200:
            cache_data = resp.json()
            cctvip_map = cache_data.get('data', {})
            fetched_str = cache_data.get('fetched', '')

            fetched_dt = parse_z3_fetched(fetched_str)
            cache_age_hours = z3_age_hours(fetched_dt)

            if cctvip_map and (cache_age_hours is None or cache_age_hours < Z3_CACHE_STALE_HOURS):
                set_z3_cache_data(cctvip_map, 'github', fetched_dt)
                age_str = f"{cache_age_hours:.1f}h" if cache_age_hours is not None else "unknown age"
                logger.info(f"Z3 cache from GitHub: {len(cctvip_map)} entries (data age: {age_str})")
                return
            else:
                age_str = f"{cache_age_hours:.1f}h" if cache_age_hours is not None else "unknown"
                logger.warning(f"Z3: GitHub cache is stale ({age_str} old) — trying its.go.kr directly")
                # Use stale data as temporary fallback while we try to refresh
                if cctvip_map and _z3_cache['data'] is None:
                    set_z3_cache_data(cctvip_map, 'github-stale', fetched_dt)
        else:
            logger.error(f"Z3: GitHub raw fetch failed: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Z3: GitHub cache fetch failed: {e}")

    # Step 3: Try direct its.go.kr (works if server IP is not geo-blocked)
    if not _refresh_z3_from_its():
        if local_map and _z3_cache['data'] is None:
            set_z3_cache_data(local_map, 'local-stale', local_fetched)
            logger.error("Z3: direct refresh failed — using stale local cache as emergency fallback")
            return
        logger.error("Z3: All refresh sources failed — using existing cached data if available")


def get_z3_app_url(cctvip):
    """Return appUrl for given cctvip, refreshing cache if needed."""
    with _z3_cache['lock']:
        now = utc_now()
        needs_refresh = (
            _z3_cache['data'] is None or
            _z3_cache['fetched'] is None or
            now - _z3_cache['fetched'] > timedelta(minutes=Z3_CACHE_TTL_MINUTES) or
            z3_local_cache_updated()
        )
        if needs_refresh:
            _refresh_z3_cache()
    return (_z3_cache['data'] or {}).get(str(cctvip))


def fetch_z3_hls_url(app_url):
    return requests.get(
        app_url + '!hls',
        timeout=10,
        verify=False,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://its.go.kr/'
        }
    )


def retry_z3_with_fresh_cache(cctvip, cctv_id, reason):
    logger.warning("Z3: refreshing its.go.kr cache for cctvip=%s (%s) after %s", cctvip, cctv_id, reason)
    with _z3_cache['lock']:
        refreshed = _refresh_z3_from_its()
        fresh_url = (_z3_cache['data'] or {}).get(str(cctvip)) if refreshed else None
    if not fresh_url:
        logger.error("Z3: cctvip=%s not found after forced refresh", cctvip)
        return None, refreshed
    return fetch_z3_hls_url(fresh_url), refreshed


def get_z3_cache_payload():
    with _z3_cache['lock']:
        now = utc_now()
        needs_refresh = (
            _z3_cache['data'] is None or
            _z3_cache['fetched'] is None or
            now - _z3_cache['fetched'] > timedelta(minutes=Z3_CACHE_TTL_MINUTES) or
            z3_local_cache_updated()
        )
        if needs_refresh:
            _refresh_z3_cache()

        data = _z3_cache.get('data') or {}
        fetched = _z3_cache.get('data_fetched') or _z3_cache.get('fetched')
        fetched_text = fetched.strftime('%Y-%m-%dT%H:%M:%SZ') if fetched else None
        age_minutes = None
        if fetched:
            age_minutes = round((utc_now() - fetched).total_seconds() / 60, 1)
        return {
            'fetched': fetched_text,
            'entries': len(data),
            'source': _z3_cache.get('source') or 'unknown',
            'age_minutes': age_minutes,
            'data': data,
        }

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

@app.route('/health-status')
def serve_health_status():
    try:
        with open(HEALTH_STATUS_FILE, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        data['_served_by'] = 'oracle-proxy'
        data['_served_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        return Response(
            json.dumps(data, ensure_ascii=False),
            200,
            {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'public, max-age=120'
            }
        )
    except FileNotFoundError:
        return Response(
            json.dumps({'regions': {}, 'last_updated': None, 'error': 'status-not-found'}),
            404,
            {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}
        )
    except Exception as exc:
        logger.error("Health status read failed: %s", exc)
        return Response(
            json.dumps({'regions': {}, 'last_updated': None, 'error': 'status-read-failed'}),
            500,
            {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}
        )


def serve_json_file(path, missing_payload, served_by='oracle-proxy', max_age=120):
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data['_served_by'] = served_by
            data['_served_at'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        return Response(
            json.dumps(data, ensure_ascii=False),
            200,
            {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': f'public, max-age={max_age}'
            }
        )
    except FileNotFoundError:
        return Response(
            json.dumps(missing_payload, ensure_ascii=False),
            404,
            {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}
        )
    except Exception as exc:
        logger.error("JSON endpoint read failed for %s: %s", path, exc)
        return Response(
            json.dumps({'error': 'json-read-failed'}, ensure_ascii=False),
            500,
            {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}
        )


@app.route('/canary-status')
def serve_canary_status():
    return serve_json_file(
        CANARY_STATUS_FILE,
        {'regions': {}, 'cameras': {}, 'generated_at': None, 'error': 'canary-status-not-found'},
        max_age=90
    )


@app.route('/ops-status')
def serve_ops_status():
    return serve_json_file(
        OPS_STATUS_FILE,
        {'service_status': 'UNKNOWN', 'generated_at': None, 'error': 'ops-status-not-found'},
        max_age=90
    )


@app.route('/canary-history')
def serve_canary_history():
    return serve_json_file(
        CANARY_HISTORY_FILE,
        [],
        max_age=90
    )


@app.route('/z3-cache.json')
def serve_z3_cache():
    try:
        payload = get_z3_cache_payload()
        status = 200 if payload.get('data') else 503
        return Response(
            json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
            status,
            {
                'Content-Type': 'application/json; charset=utf-8',
                'Cache-Control': 'public, max-age=300'
            }
        )
    except Exception as exc:
        logger.error("Z3 cache endpoint failed: %s", exc)
        return Response(
            json.dumps({'error': 'z3-cache-unavailable'}),
            503,
            {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'}
        )

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)

def fetch_upstream(url, headers, attempts=3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(
                url,
                timeout=(5, 20),
                verify=False,
                headers=headers,
                allow_redirects=True,
            )
            if resp.status_code in TRANSIENT_UPSTREAM_STATUSES and attempt < attempts:
                time.sleep(0.25 * attempt)
                continue
            return resp
        except requests.RequestException as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(0.25 * attempt)
                continue
            raise
    raise last_error

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
             headers["Accept"] = "*/*"
             headers["Connection"] = "close"
        elif 'cctvsec.ktict.co.kr' in target_url:
             headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
             headers["Referer"] = "https://its.go.kr/"
        elif 'kbsapi.loomex.net' in target_url or 'kbscctv-cache.loomex.net' in target_url:
             headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
             headers["Referer"] = "https://www.utic.go.kr/guide/cctvOpenData.do"
             headers["Accept"] = "*/*"

        # Fetch fully before responding so transient upstream resets can be retried.
        resp = fetch_upstream(target_url, headers)
        
        # Use stream=False for manifest rewriting if it's a small text file
        # But for video segments (TS), we want streaming.
        content_type = resp.headers.get('Content-Type', '').lower()
        is_manifest = (
            target_url.endswith('.m3u8')
            or 'mpegurl' in content_type
            or 'm3u8' in content_type
        )
        
        if is_manifest:
            content = resp.text
            # Rewrite relative paths to absolute proxied paths
            # Jeju uses /hls/....ts
            # Replace lines starting with / or not starting with http
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    base_url = target_url
                    target_path_tail = target_url.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]
                    if (
                        'kbsapi.loomex.net/v1/api/cctvRequest' in target_url
                        and not target_url.endswith('/')
                        and '.' not in target_path_tail
                    ):
                        base_url = target_url + '/'
                    full_segment_url = urljoin(base_url, line.strip())
                    new_lines.append(f"/proxy?url={quote(full_segment_url, safe='')}")
                else:
                    new_lines.append(line)
            
            rewritten_content = "\n".join(new_lines).encode('utf-8')
            
            excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'access-control-allow-origin', 'content-type']
            resp_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                       if name.lower() not in excluded_headers]
            resp_headers.append(('Access-Control-Allow-Origin', '*'))
            resp_headers.append(('Cache-Control', 'no-store, max-age=0'))
            resp_headers.append(('Content-Type', 'application/vnd.apple.mpegurl'))
            
            return Response(rewritten_content, resp.status_code, resp_headers)
        
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'access-control-allow-origin']
        resp_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        # Add CORS (Force single *)
        resp_headers.append(('Access-Control-Allow-Origin', '*'))
        resp_headers.append(('Cache-Control', 'no-store, max-age=0'))
        
        return Response(resp.content, resp.status_code, resp_headers)
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

    def get_media_path(stream):
        cctvip = request.args.get('cctvip', '')
        if cctvip == '118':
            return '01'
        if cctvip == '119':
            return '02'
        match = re.match(r'CTV0*(\d+)$', stream, re.I)
        if match:
            number = int(match.group(1))
            return '01' if number < 51 else '02'
        return '01'

    media_path = get_media_path(stream_id)

    # Daejeon publishes minute MP4 files with a short delay. Probe recent
    # timestamps so playback does not fail just because the newest file is late.
    now = datetime.utcnow() + timedelta(hours=9)
    last_url = None
    probe_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Range": "bytes=0-1",
    }
    for offset in [2, 4, 6, 8, 10, 1]:
        target_time = now - timedelta(minutes=offset)
        timestamp = target_time.strftime("%Y%m%d.%H%M00")
        real_url = f"https://tportal.daejeon.go.kr:37084/{media_path}/media/{stream_id}/{stream_id}_{timestamp}.000.mp4"
        last_url = real_url
        try:
            resp = requests.get(real_url, headers=probe_headers, timeout=(1.0, 1.5), verify=False, stream=True)
            if resp.status_code in (200, 206):
                logger.info(f"Proxying Daejeon {cctv_id} offset={offset}m -> {real_url}")
                return flask.redirect(real_url)
            logger.info(f"Daejeon {cctv_id} offset={offset}m unavailable: {resp.status_code}")
        except requests.RequestException as exc:
            logger.info(f"Daejeon {cctv_id} offset={offset}m probe failed: {exc}")

    logger.warning(f"Daejeon {cctv_id} no recent MP4 found; last tried {last_url}")
    return "Daejeon stream not ready", 502

# === Jeju Proxy Logic ===
@app.route('/jeju')
@app.route('/jeju2')
def proxy_jeju():
    cctv_id = request.args.get('id')
    if not cctv_id:
        return "Missing ID", 400

    short_id = cctv_id.replace("JEJU_", "")
    mapped_id = JEJU_ID_MAP.get(short_id)
    target_id = mapped_id or short_id
    cache_keys = {short_id, target_id}
    if mapped_id:
        logger.info(f"Jeju: Mapped {short_id} -> {target_id}")

    cached_response = redirect_cached_jeju_stream(target_id)
    if not cached_response and mapped_id:
        cached_response = redirect_cached_jeju_stream(short_id)
    if cached_response:
        return cached_response

    headers = get_jeju_headers()

    try:
        if not jeju_session.cookies:
            try:
                jeju_session.get(
                    "https://www.jejuits.go.kr/jido/mainView.do",
                    headers=headers,
                    timeout=(2, 4),
                )
            except requests.RequestException:
                pass

        # Short IDs such as C75/W83 need a UUID lookup. Prefer the local map
        # because Jeju's feature-info endpoint frequently closes short-id calls.
        if len(short_id) < 20 and not mapped_id:
            info_url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
            payload = {
                "DEVICE_KIND": "CCTV",
                "DEVICE_ID": short_id,
                "maplevel": "14",
            }
            logger.info(f"Jeju: Resolving UUID for {short_id}...")
            resp = jeju_session.post(info_url, data=payload, headers=headers, timeout=(2, 4))
            if resp.status_code == 200:
                data = resp.json()
                if 'stremid' in data:
                    target_id = data['stremid']
                    cache_keys.add(target_id)
                    logger.info(f"Jeju: Resolved {short_id} -> {target_id}")

            cached_response = redirect_cached_jeju_stream(target_id)
            if cached_response:
                return cached_response

        target_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
        payload = {"DEVICE_ID": target_id}

        logger.info(f"Jeju: Fetching token for {target_id}...")
        resp = jeju_session.post(target_api, data=payload, headers=headers, timeout=(3, 12))
        if resp.status_code != 200:
            return f"Jeju API Error: {resp.status_code}", 502

        real_url = resp.text.strip().strip('"')
        if real_url.startswith("http"):
            with jeju_lock:
                for cache_key in cache_keys:
                    jeju_stream_cache[cache_key] = {
                        'url': real_url,
                        'created_at': time.time(),
                    }
            logger.info(f"Jeju {cctv_id} Success -> Redirecting direct: {real_url[:60]}...")
            return flask.redirect(real_url)

        logger.error(f"Invalid resp from Jeju API: {real_url}")
        return f"Invalid URL from Jeju API for {target_id}", 502

    except requests.RequestException as e:
        logger.error(f"Jeju Proxy Upstream Failed: {e}")
        return f"Jeju Proxy Error: {str(e)}", 502
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

            # cctvsec.ktict.co.kr returns the signed m3u8 URL in the response body.
            hls_resp = fetch_z3_hls_url(app_url)

            # Expired/stale Z3 tokens can appear as 401/403/404/5xx or a non-URL body.
            # Force a direct its.go.kr refresh once before declaring the camera broken.
            first_body = hls_resp.text.strip() if hls_resp.status_code < 400 else ''
            if hls_resp.status_code >= 400 or not first_body.startswith('http'):
                retry_resp, refreshed = retry_z3_with_fresh_cache(cctvip, cctv_id, f"HTTP {hls_resp.status_code}")
                if retry_resp is not None:
                    hls_resp = retry_resp
                elif refreshed:
                    return f"Z3 stream not found after refresh for cctvip {cctvip}", 404

            if hls_resp.status_code >= 400:
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
def extract_wowza_query_from_kbs_manifest(manifest_text):
    match = re.search(r'chunklist_([^\s/]+?)\.m3u8', manifest_text or '')
    if not match:
        return None

    raw_token = unquote(match.group(1))
    candidates = [raw_token, raw_token[1:], raw_token[2:]]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            padded = candidate + ('=' * ((4 - len(candidate) % 4) % 4))
            decoded = base64.b64decode(padded).decode('utf-8')
        except Exception:
            continue
        if decoded.startswith('wowzatoken'):
            return decoded
    return None


def build_kbs_cache_url(cctvip, kbs_url, headers):
    """KBS scenic cameras return a kbsapi manifest whose child playlist can 500.
    Reuse its fresh Wowza token against the public kbscctv-cache lowStream path.
    """
    if 'kbsapi.loomex.net/v1/api/cctvRequest' not in kbs_url:
        return None

    resp = fetch_upstream(kbs_url, headers, attempts=2)
    if resp.status_code != 200:
        logger.warning("KB %s kbsapi manifest returned %s", cctvip, resp.status_code)
        return None

    wowza_query = extract_wowza_query_from_kbs_manifest(resp.text)
    if not wowza_query:
        logger.warning("KB %s could not extract Wowza token from kbsapi manifest", cctvip)
        return None

    return f"https://kbscctv-cache.loomex.net/lowStream/_definst_/{cctvip}_low.stream/playlist.m3u8?{wowza_query}"


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
        cache_url = build_kbs_cache_url(cctvip, kbs_url, headers)
        if cache_url:
            logger.info(f"KB {cctvip} cache lowStream -> {cache_url[:80]}...")
            return flask.redirect(f"/proxy?url={quote(cache_url, safe='')}")

        return flask.redirect(f"/proxy?url={quote(kbs_url)}")

    except Exception as e:
        logger.error(f"KB Proxy Failed ({cctvip}): {e}")
        return f"Server Error: {str(e)}", 500


# === GiTS (경기도 교통정보서비스) Proxy Logic ===
@app.route('/gits')
def proxy_gits():
    """Fetches a fresh GiTS stream URL on-demand for a given cctvip (GiTS cctvId)."""
    cctvip = request.args.get('cctvip') or request.args.get('id')
    if not cctvip:
        return "Missing cctvip", 400

    cctvip = str(cctvip).replace('GITS_', '').strip()
    route_id = request.args.get('routeId', '')
    svc_link_id = request.args.get('svcLinkId', '')

    query = urlencode({k: v for k, v in {
        'cctvId': cctvip,
        'routeId': route_id,
        'svcLinkId': svc_link_id,
    }.items() if v})
    popup_url = f"https://gits.gg.go.kr/web/popup/webCctvPopup.do?{query}"
    gits_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://gits.gg.go.kr/web/map/webMap.do?opt=3"
    }

    try:
        resp = requests.get(popup_url, headers=gits_headers, timeout=10)
        if resp.status_code != 200:
            return f"GiTS popup error: {resp.status_code}", 502

        html = resp.text

        # Extract the !hls token URL (preferred - returns signed m3u8).
        hls_patterns = [
            r'\$\.get\(["\']([^"\']+!hls)["\']',
            r'["\'](https?:\/\/gitsview\.gg\.go\.kr\/[^"\']+!hls)["\']',
            r'["\'](\/\/gitsview\.gg\.go\.kr\/[^"\']+!hls)["\']',
        ]
        for pattern in hls_patterns:
            match_hls = re.search(pattern, html)
            if not match_hls:
                continue
            hls_token_url = match_hls.group(1)
            if hls_token_url.startswith("//"):
                hls_token_url = "https:" + hls_token_url
            hls_resp = requests.get(hls_token_url, headers=gits_headers, timeout=10, verify=False)
            if hls_resp.status_code == 200:
                m3u8_url = hls_resp.text.strip()
                if m3u8_url.startswith("http"):
                    logger.info(f"GiTS {cctvip} -> {m3u8_url[:70]}...")
                    return flask.redirect(f"/proxy?url={quote(m3u8_url, safe='')}")

        # Fallback: videoUrl (direct stream, no token resolution needed)
        match_video = re.search(r'var\s+videoUrl\s*=\s*["\'](http[^"\']+)["\']', html)
        if match_video:
            video_url = match_video.group(1).replace("http://", "https://")
            logger.info(f"GiTS {cctvip} (videoUrl fallback) -> {video_url[:70]}...")
            return flask.redirect(f"/proxy?url={quote(video_url, safe='')}")

        return f"GiTS: stream not found for cctvip {cctvip}", 404

    except Exception as e:
        logger.error(f"GiTS Proxy Failed ({cctvip}): {e}")
        return f"Server Error: {str(e)}", 500


if __name__ == '__main__':
    # Ensure HLS dir exists
    shutil.rmtree(HLS_DIR, ignore_errors=True)
    os.makedirs(HLS_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=8080)
