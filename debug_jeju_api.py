import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_jeju(cctv_id):
    target_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.jejuits.go.kr/jido/mainView.do?DEVICE_KIND=CCTV",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    payload = {"DEVICE_ID": cctv_id}
    
    print(f"Requesting {cctv_id}...")
    try:
        resp = requests.post(target_api, data=payload, headers=headers, timeout=10, verify=False)
        print(f"Status: {resp.status_code}")
        print(f"Headers: {resp.headers}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with a few IDs
    test_jeju("246") # Short ID?
    test_jeju("JEJU_246") # With prefix?
    test_jeju("26837ae9-8005-3d07-a3cd-e38856cdc22b") # UUID from browser investigation
