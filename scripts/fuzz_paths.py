import requests
import warnings
import concurrent.futures
import time
import random

warnings.filterwarnings('ignore')

targets = [
    # IP, cctv_id, id_param
    ('115.92.162.198', 'L33002', '02'),
    ('211.236.106.5', 'L45020', 'cctv20'),
    ('211.34.147.236', 'L190001', '61') # Representative for 211.34.147.x subnet
]

# Common CCTV path patterns
base_paths = [
    "/hls/{cctv_id}.m3u8",
    "/{cctv_id}/index.m3u8",
    "/{cctv_id}.m3u8",
    "/live/{cctv_id}/index.m3u8",
    "/media/{id_param}/chunklist.m3u8",  
    "/hls/{id_param}/index.m3u8",
    "/{id_param}.m3u8",
    "/media/{cctv_id}/chunklist.m3u8",
    "/k/{cctv_id}.m3u8", 
    "/media/k/{cctv_id}.m3u8",
    "/LiveApp/streams/{cctv_id}.m3u8",
    "/LiveApp/streams/{id_param}.m3u8",
    "/vod/{cctv_id}.m3u8"
]

def check_url(args):
    ip, cctv_id, id_param, path_template = args
    path = path_template.format(cctv_id=cctv_id, id_param=id_param)
    url = f"http://{ip}{path}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.utic.go.kr/'
    }
    
    try:
        # Stealth delay
        time.sleep(random.uniform(0.5, 1.5))
        resp = requests.head(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return f"[FOUND] {url}"
        else:
            return f"[Status {resp.status_code}] {url}"
    except Exception as e:
        return f"[ERR] {url}: {e}"
    return None

print(f"Fuzzing {len(targets)} targets with {len(base_paths)} patterns...")
tasks = []
for ip, cctv_id, id_param in targets:
    for path in base_paths:
        tasks.append((ip, cctv_id, id_param, path))

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # Low concurrency
    for result in executor.map(check_url, tasks):
        # Print everything
        if result:
            print(result)

print("Fuzzing complete.")
