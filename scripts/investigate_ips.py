import requests
import warnings
import concurrent.futures

warnings.filterwarnings('ignore')

targets = [
    ('211.57.45.101', 'L180070'),  # Control (Known Good)
    ('211.184.198.178', 'L380001'),
    ('210.95.12.126', 'L100002'),
    ('115.92.162.198', 'L33002'),
    ('211.114.87.164', 'L460001'),
    ('211.236.106.5', 'L45020')
]

patterns = [
    "http://{ip}/media/{id}/chunklist.m3u8",
    "https://{ip}/media/{id}/chunklist.m3u8",
    "http://{ip}:8080/media/{id}/chunklist.m3u8",
    "http://{ip}:1935/media/{id}/chunklist.m3u8",
    "http://{ip}/hls/{id}/index.m3u8",
    "http://{ip}:1935/live/{id}/playlist.m3u8",
    "http://{ip}/LiveApp/streams/{id}.m3u8"
]

def check_url(args):
    ip, cctv_id, pattern = args
    url = pattern.format(ip=ip, id=cctv_id)
    try:
        # verify=False suppresses SSL errors. stream=True allows header-only check effectively.
        resp = requests.get(url, timeout=5, verify=False, stream=True)
        if resp.status_code == 200:
            return f"[SUCCESS] {ip}: {url}"
        else:
            return f"[FAIL] {ip}: {url} (Status {resp.status_code})"
    except Exception as e:
        return f"[ERR] {ip}: {url} ({str(e)})"
    return None

print("Scanning for working patterns...")
tasks = []
for ip, cctv_id in targets:
    for pat in patterns:
        tasks.append((ip, cctv_id, pat))

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    for result in executor.map(check_url, tasks):
        if result:
            print(result)

print("Scan complete.")
