
import requests
import datetime
from datetime import timedelta

ID = "CTV0029"
base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{ID}/{ID}_"

now = datetime.datetime.now()
print(f"Current time: {now}")

for m in range(0, 10):
    t = now - timedelta(minutes=m)
    ts = t.strftime("%Y%m%d.%H%M00")
    url = f"{base_url}{ts}.000.mp4"
    try:
        resp = requests.head(url, timeout=5, verify=False)
        print(f"Checking {url}: {resp.status_code}")
    except Exception as e:
        print(f"Checking {url}: Error {e}")
