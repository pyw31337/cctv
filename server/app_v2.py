import flask
from flask import request, Response, abort, send_from_directory
import requests
import os
import subprocess
import time
import shutil
import logging
import threading
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = flask.Flask(__name__)

# Directory for HLS segments (local storage on VM)
HLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hls_cache')

# Store for active streams
# { stream_id: { 'process': subprocess.Popen, 'last_access': timestamp, 'url': original_url } }
streams = {}
lock = threading.Lock()

# Persistent session for Jeju ITS
jeju_session = requests.Session()
jeju_session.verify = False

def get_jeju_headers(referer="https://www.jejuits.go.kr/jido/mainView.do"):
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": referer,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }

@app.route('/')
@app.route('/index.html')
def index():
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..'), 'index.html')

@app.route('/cctv_data.json')
def data():
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..'), 'cctv_data.json')

@app.route('/proxy')
def proxy_stream():
    """Simple pass-through proxy for SSL/CORS issues"""
    target_url = request.args.get('url')
    if not target_url:
        return "Missing URL", 400
        
    try:
        resp = requests.get(target_url, stream=True, timeout=10, verify=False)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]
        
        # Add CORS
        headers.append(('Access-Control-Allow-Origin', '*'))
        
        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return f"Proxy error: {str(e)}", 502

@app.route('/jeju')
def proxy_jeju():
    cctv_id = request.args.get('id')
    if not cctv_id:
        return "Missing ID", 400

    # Clean ID
    short_id = cctv_id.replace("JEJU_", "")
    
    # Check if this is already a UUID (long string)
    target_id = short_id
    
    # 0. Ensure session is initialized
    try:
        if not jeju_session.cookies:
            logger.info("Initializing Jeju session cookies...")
            jeju_session.get("https://www.jejuits.go.kr/jido/mainView.do", headers=get_jeju_headers(), timeout=5)
    except:
        pass

    # 1. Resolve Short ID -> UUID if necessary
    if len(short_id) < 15:
        try:
            info_url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
            payload = {
                "DEVICE_KIND": "CCTV",
                "DEVICE_ID": short_id,
                "maplevel": "11"
            }
            logger.info(f"Resolving UUID for Jeju Short ID: {short_id}")
            resp = jeju_session.post(info_url, data=payload, headers=get_jeju_headers(), timeout=5)
            logger.info(f"Resolution response status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                if 'stremid' in data:
                    target_id = data['stremid']
                    logger.info(f"Resolved {short_id} -> {target_id}")
                else:
                    logger.warning(f"Could not find stream ID for {short_id}. Response: {resp.text}")
            else:
                logger.error(f"Resolution failed with {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Error resolving Jeju UUID: {e}")

    # 1. Fetch dynamic stream URL
    try:
        stream_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
        payload = {"DEVICE_ID": target_id}
        
        # Sometimes one attempt isn't enough or session needs refreshing
        for attempt in range(2):
            resp = jeju_session.post(stream_api, data=payload, headers=get_jeju_headers(), timeout=5)
            if resp.status_code == 200:
                url = resp.text.strip().strip('"')
                if url.startswith("http"):
                    return flask.redirect(url)
                else:
                    logger.warning(f"Jeju API returned non-URL (Attempt {attempt+1}): {url}")
                    # Refresh session if it returned "error"
                    if "error" in url.lower():
                        jeju_session.get("https://www.jejuits.go.kr/jido/mainView.do", headers=get_jeju_headers(), timeout=5)
            
        return f"Jeju Proxy Error: Received invalid response from API for {target_id}", 502

    except Exception as e:
        logger.error(f"Jeju Proxy Exception: {e}")
        return f"Server Error: {str(e)}", 500

if __name__ == '__main__':
    # Cleanup HLS dir if any
    shutil.rmtree(HLS_DIR, ignore_errors=True)
    os.makedirs(HLS_DIR, exist_ok=True)
    
    # Start the app
    logger.info("Starting CCTV Proxy Server on port 8080...")
    app.run(host='0.0.0.0', port=8080)
