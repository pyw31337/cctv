
import json
import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_stream(item):
    url = item.get("url", "")
    if not url:
        return None
        
    # Skip if already inactive
    if item.get("status") in ["inactive", "broken"]:
        return None

    # Focus on HLS/MP4
    is_video = False
    if ".m3u8" in url or ".mp4" in url:
        is_video = True
    
    # Also check "Other" (failed consistently in report)
    # But checking everything is costly. 16k streams.
    # Let's check HLS and MP4 first as they are most critical for playback.
    if not is_video:
        return None

    try:
        # Use HEAD for speed, but some servers reject. try GET with stream=True
        # Timeoutshort 
        r = requests.head(url, timeout=3, verify=False)
        if r.status_code == 404:
            return {"id": item["id"], "name": item["name"], "status": 404}
        elif r.status_code == 405: # Method Not Allowed, try GET
            r = requests.get(url, timeout=3, stream=True, verify=False)
            if r.status_code == 404:
                return {"id": item["id"], "name": item["name"], "status": 404}
    except:
        pass
        
    return None

def main():
    print("Scanning ALL HLS/MP4 streams for 404s...")
    data = load_json(CCTV_DATA_FILE)
    
    # Filter for HLS/MP4
    targets = [item for item in data if (".m3u8" in item.get("url", "") or ".mp4" in item.get("url", "")) and item.get("status") not in ["inactive", "broken"]]
    
    print(f"Found {len(targets)} active HLS/MP4 streams to check.")
    
    broken_ids = []
    
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_stream, item): item for item in targets}
        
        completed = 0
        for future in as_completed(futures):
            res = future.result()
            if res:
                print(f"[BROKEN] {res['name']} ({res['id']}): 404")
                broken_ids.append(res['id'])
            
            completed += 1
            if completed % 100 == 0:
                print(f"Progress: {completed}/{len(targets)}")

    print(f"Scan complete. Found {len(broken_ids)} broken streams.")
    
    if broken_ids:
        print("Disabling broken streams...")
        disabled_count = 0
        for item in data:
            if item.get("id") in broken_ids:
                item["status"] = "inactive"
                item["status_note"] = "Auto-disabled: 404 during full scan"
                disabled_count += 1
        
        save_json(CCTV_DATA_FILE, data)
        print(f"Saved {disabled_count} updates to {CCTV_DATA_FILE}")

if __name__ == "__main__":
    main()
