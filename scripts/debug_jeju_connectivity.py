
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TEST_URLS = [
    # Jeju Proxy
    "https://158.179.194.163.sslip.io/jeju?id=516",
    # NOWJEJU HLS (HTTP)
    "http://123.140.197.51/stream/35/play.m3u8",
    # NOWJEJU HLS (HTTPS Test)
    "https://123.140.197.51/stream/35/play.m3u8",
    # Vurix (HTTP)
    "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100003/0/1",
    # Vurix (HTTPS Test)
    "https://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100003/0/1",
    # Hallasan HLS
    "https://hallacctv.kr/live/cctv01.stream_360p/playlist.m3u8"
]

def test_connectivity():
    for url in TEST_URLS:
        print(f"Testing {url}...")
        try:
            resp = requests.get(url, timeout=10, verify=False, stream=True)
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                print("  Success!")
            else:
                print(f"  Failed: {resp.text[:100]}")
        except Exception as e:
            print(f"  Error: {e}")
        print("-" * 20)

if __name__ == "__main__":
    test_connectivity()
