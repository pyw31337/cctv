import requests
import json

cctv_id = "C62" # Short ID

url = "https://www.jejuits.go.kr/jido/getCurFeatureInfo.do"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}
payload = {
    "DEVICE_KIND": "CCTV",
    "DEVICE_ID": cctv_id,
    "maplevel": "14"
}

print(f"Looking up info for {cctv_id}...")
try:
    resp = requests.post(url, data=payload, headers=headers, verify=False, timeout=10)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"Error: {e}")
