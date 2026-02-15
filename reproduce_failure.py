
import json
import requests
from datetime import datetime, timedelta
import urllib3
import random

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CCTV_DATA_FILE = "cctv_data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.utic.go.kr/"
}

def generate_daejeon_url(item):
    cctv_id = item.get("original_id")
    if not cctv_id: return None
    
    stream_id = cctv_id
    if cctv_id.startswith("CCTV"):
        num = cctv_id[4:] 
        stream_id = f"CTV{num.zfill(4)}"
        
    base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_"
    now = datetime.now()
    
    candidates = []
    for m in range(1, 6): # Try 1 to 5 mins ago
        t = now - timedelta(minutes=m)
        ts = t.strftime("%Y%m%d.%H%M00")
        candidates.append(f"{base_url}{ts}.000.mp4")
    return candidates

def check_one(item):
    url_type = item.get("urlType", "")
    urls = [item.get("url")]
    if url_type == "daejeon_mp4_dynamic" or "daejeon" in item.get("url", "").lower():
        candidates = generate_daejeon_url(item)
        if candidates: urls = candidates

    for url in urls:
        try:
            resp = requests.head(url, headers=HEADERS, timeout=5, verify=False)
            if resp.status_code == 200:
                return True, url, 200
        except:
            pass
    return False, urls[0], "FAIL"

with open(CCTV_DATA_FILE, 'r') as f:
    data = json.load(f)

daejeon_streams = [s for s in data if "daejeon" in s.get("source", "").lower() or "daejeon" in s.get("url", "").lower()]
print(f"Total Daejeon streams found: {len(daejeon_streams)}")

sample = random.sample(daejeon_streams, 10)
for s in sample:
    ok, url, code = check_one(s)
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {s['name']} ({s['id']}) - {url} ({code})")
