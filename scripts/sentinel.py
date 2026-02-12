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
    try:
        url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
        resp = requests.head(url, timeout=10, verify=False)
        if resp.status_code < 500:
            return True
    except:
        pass
    return False

def check_paju_stream(cctv):
    # Check both directUrl and url
    url = cctv.get('directUrl') or cctv.get('url')
    if not url: return False
    
    try:
        resp = requests.head(url, timeout=10, verify=False)
        # 200 OK or 302 Redirect is good for Paju
        if resp.status_code in [200, 302]:
            log(f"[OK] Paju {cctv.get('id')} is UP")
            return True
        else:
            log(f"[FAIL] Paju {cctv.get('id')} returned {resp.status_code}")
    except Exception as e:
        log(f"[ERR] Paju {cctv.get('id')} check failed: {e}")
    return False

def check_generic_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url')
    if not url: return False
    
    try:
        # Standard HEAD check for any other region
        resp = requests.head(url, timeout=10, verify=False)
        if resp.status_code < 400: # Any success or redirect
            log(f"[OK] {cctv.get('id')} is UP")
            return True
        else:
            log(f"[FAIL] {cctv.get('id')} returned {resp.status_code}")
    except Exception as e:
        log(f"[ERR] {cctv.get('id')} check failed: {e}")
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
    elif region_name == "PAJU":
        success = check_paju_stream(sample)
    else:
        success = check_generic_stream(sample)
        
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
        elif region_name == "PAJU":
            res = check_paju_stream(cam)
        else:
            res = check_generic_stream(cam)
        monitor_results.append(res)
        
    if any(monitor_results):
        log(f"{region_name} backup succeeded. Region is OK.")
        return True
    else:
        log(f"{region_name} ALL checks failed. Region is DOWN.")
        return False

def run_sentinel():
    try:
        log("--- Sentinel Started ---")
        
        cctv_data = load_json(DATA_FILE)
        if not cctv_data:
            log("No CCTV data loaded. Exiting.")
            return

        config = load_json(CONFIG_FILE)
        current_status = load_json(STATUS_FILE)
        
        if not isinstance(current_status, dict):
            log("Status file is not a dict. Initializing.")
            current_status = {}

        if "regions" not in current_status:
            current_status["regions"] = {}

        # Group cameras
        region_map = {}
        # Ensure cctv_data is a list
        items = cctv_data if isinstance(cctv_data, list) else []
        for cam in items:
            rid = cam.get('id', '')
            if not rid: continue
            
            if '_' in rid:
                r = rid.split('_')[0]
                if r not in region_map:
                    region_map[r] = []
                region_map[r].append(cam)
            elif rid.startswith('L12'):
                if 'PAJU' not in region_map:
                    region_map['PAJU'] = []
                region_map['PAJU'].append(cam)

        # Pass 2: Check ALL discovered regions
        all_regions = set(region_map.keys()) | set(config.keys())
        
        log(f"Discovered {len(all_regions)} regions: {sorted(all_regions)}")

        for region_name in sorted(all_regions):
            cameras = region_map.get(region_name, [])
            if not cameras: 
                continue
            
            conf = config.get(region_name, {})
            is_healthy = test_region(region_name, cameras)
            
            # Update Status
            if region_name not in current_status["regions"]:
                current_status["regions"][region_name] = {}
            
            status_entry = current_status["regions"][region_name]
            
            if is_healthy:
                status_entry["status"] = "OK"
                status_entry["active_source"] = "main"
            else:
                status_entry["status"] = "DOWN"
                # If we have a sub, switch to it. 
                if conf.get("sub", {}).get("type") and conf.get("sub", {}).get("type") != "none":
                    status_entry["active_source"] = "sub"
                else:
                    status_entry["active_source"] = "main"

        current_status["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(STATUS_FILE, current_status)
        log("--- Sentinel Finished ---")
    except Exception as e:
        log(f"FATAL ERROR in run_sentinel: {e}")
        log(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    run_sentinel()
