import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.utic.go.kr/"
}

def test_url(url, label):
    print(f"Testing {label}: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10, verify=False, stream=True)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"Content length: {len(response.content) if not response.raw else 'Streamed'}")
            if "jsp" in url or "do" in url:
                print(f"Snippet: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

# UTIC API Sample
utic_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI&cctvid=E970016&cctvName=%EC%84%9C%EC%9A%B8%EA%B4%91%EC%9E%A5&kind=Seoul&cctvch=53&id=274"
test_url(utic_url, "UTIC_API")

# Daejeon Sample
# Need to generate current ones
now = datetime.now()
stream_id = "CTV0029" # 부사오거리 from failed_streams.json
base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_"
for m in range(1, 5):
    t = now - timedelta(minutes=m)
    ts = t.strftime("%Y%m%d.%H%M00")
    daejeon_url = f"{base_url}{ts}.000.mp4"
    test_url(daejeon_url, f"Daejeon (T-{m}m)")
