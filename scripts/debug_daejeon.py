import requests
from datetime import datetime, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_daejeon():
    # KST is UTC+9
    now = datetime.utcnow() + timedelta(hours=9)
    print(f"Current KST: {now.strftime('%H:%M:%S')}")
    
    # Check last 30 minutes
    for i in range(1, 31):
        test_time = now - timedelta(minutes=i)
        ts = test_time.strftime('%Y%m%d.%H%M00')
        # CTV0071 is 도안네거리
        url = f"https://tportal.daejeon.go.kr:37084/01/media/CTV0071/CTV0071_{ts}.000.mp4"
        try:
            r = requests.head(url, timeout=5, verify=False)
            print(f"{ts}: {r.status_code}")
        except Exception as e:
            print(f"{ts}: Error {e}")

if __name__ == "__main__":
    check_daejeon()
