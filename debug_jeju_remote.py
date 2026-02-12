import requests
import sys

cctv_id = "C62" # JEJU_C62 without prefix
if len(sys.argv) > 1:
    cctv_id = sys.argv[1].replace("JEJU_", "")

print(f"Testing Jeju API for ID: {cctv_id}")

url = "https://www.jejuits.go.kr/jido/streamUrl.do"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.jejuits.go.kr/jido/mainView.do?DEVICE_KIND=CCTV",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}
payload = {"DEVICE_ID": cctv_id}

try:
    resp = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Body: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
