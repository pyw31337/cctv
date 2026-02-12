import json
import random
import requests
import os
from datetime import datetime, timedelta
import time

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")
CONFIG_FILE = os.path.join(BASE_DIR, "configs", "region_config.json")
STATUS_FILE = os.path.join(BASE_DIR, "data", "status.json")
LOG_FILE = os.path.join(BASE_DIR, "sentinel.log")

# Ensure data dir exists
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def get_daejeon_url(stream_id, offset_minutes=2):
    # Calculate KST time
    now_utc = datetime.utcnow()
    kst_time = now_utc + timedelta(hours=9) - timedelta(minutes=offset_minutes)
    
    timestamp = kst_time.strftime("%Y%m%d.%H%M00")
    
    # Process ID
    if 'DAEJEON_' in stream_id:
        clean_id = stream_id.replace('DAEJEON_', '')
        if clean_id.startswith('CCTV'):
             # CCTV08 -> CTV0008
             num = clean_id[4:]
             clean_id = f"CTV{num.zfill(4)}"
        stream_id_formatted = clean_id
    else:
        stream_id_formatted = stream_id

    return f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id_formatted}/{stream_id_formatted}_{timestamp}.000.mp4"

def check_daejeon_stream(cctv):
    stream_id = cctv.get('id', '')
    
    # Try 1 to 3 minutes ago
    for offset in range(1, 4):
        url = get_daejeon_url(stream_id, offset)
        try:
            # We use verify=False because of internal server cert issues sometimes, or to be safe
            # But tportal usually requires valid certs. Let's try with verify=False for robustness checking if server is UP.
            # Timeout increased to 15s and added User-Agent to mimic browser
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.head(url, timeout=15, verify=False, headers=headers)
            if resp.status_code == 200:
                log(f"[OK] Daejeon {stream_id} is UP (Offset {offset}m)")
                return True
            else:
                log(f"[FAIL] Daejeon {stream_id} (Offset {offset}m) returned {resp.status_code}")
        except Exception as e:
            log(f"[ERR] Daejeon {stream_id} check failed: {e}")
    
    return False

def check_jeju_stream(cctv):
    # Jeju verification is trickier without full handshake emulation (UUID resolution etc).
    # However, we can check if the Jeju ITS main site is responding, or check a known static point.
    # For now, let's assume if we can reach the main ITS site, it's "OK" enough for a sentinel check
    # OR we can try to resolve the ID using the same logic as app.py if we port it here.
    # Capturing the real full logic here might be overkill for V1.
    # Let's check the generic Jeju ITS endpoint connectivity.
    
    # Better: Check our own proxy? No, Sentinel runs on server.
    # Check Jeju ITS API endpoint.
    try:
        url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
        resp = requests.head(url, timeout=10, verify=False)
        if resp.status_code < 500: # 200 or 405 (Method Not Allowed) usually means server is up
            return True
    except:
        pass
    return False

def test_region(region_name, cameras):
    if not cameras:
        return True # No cameras, assume OK
        
    # sample 1
    sample = random.choice(cameras)
    log(f"Testing {region_name} with sample: {sample.get('id')}")
    
    success = False
    if region_name == "DAEJEON":
        success = check_daejeon_stream(sample)
    elif region_name == "JEJU":
        success = check_jeju_stream(sample)
    else:
        success = True # Unknown region, skip
        
    if success:
        return True
        
    # Retry with 2 others
    log(f"{region_name} sample failed. Retrying with 2 backups...")
    backups = random.sample(cameras, min(len(cameras), 2))
    
    monitor_results = []
    for cam in backups:
        if region_name == "DAEJEON":
            res = check_daejeon_stream(cam)
        elif region_name == "JEJU":
            res = check_jeju_stream(cam)
        else:
            res = True
        monitor_results.append(res)
        
    if any(monitor_results):
        log(f"{region_name} backup succeeded. Region is OK.")
        return True
    else:
        log(f"{region_name} ALL checks failed. Region is DOWN.")
        return False

def run_sentinel():
    log("--- Sentinel Started ---")
    
    cctv_data = load_json(DATA_FILE)
    config = load_json(CONFIG_FILE)
    current_status = load_json(STATUS_FILE)
    
    if "regions" not in current_status:
        current_status["regions"] = {}

    # Group cameras
    region_map = {}
    for cam in cctv_data:
        rid = cam.get('id', '')
        if '_' in rid:
            r = rid.split('_')[0]
            if r not in region_map:
                region_map[r] = []
            region_map[r].append(cam)

    # Check
    for region_name, conf in config.items():
        if region_name in region_map:
            is_healthy = test_region(region_name, region_map[region_name])
            
            # Update Status
            if region_name not in current_status["regions"]:
                current_status["regions"][region_name] = {}
            
            status_entry = current_status["regions"][region_name]
            
            if is_healthy:
                status_entry["status"] = "OK"
                status_entry["active_source"] = "main"
            else:
                status_entry["status"] = "DOWN"
                # If we have a sub, switch to it. Config defines "sub".
                if conf.get("sub", {}).get("type") != "none":
                    status_entry["active_source"] = "sub"
                else:
                    status_entry["active_source"] = "main" # No backup, stay main (or show error)

    current_status["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json(STATUS_FILE, current_status)
    log("--- Sentinel Finished ---")

if __name__ == "__main__":
    run_sentinel()
