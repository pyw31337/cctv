
import requests
import json

TARGET_IDS = ["L230308", "L230309", "L230310"]  # East Busan IC, IKEA, Lotte Mall
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
HEADERS = {
    "Referer": "https://www.utic.go.kr/",
    "User-Agent": "Mozilla/5.0"
}

def fetch_fresh_metadata():
    print("Fetching fresh metadata from UTIC API...")
    
    for cctv_id in TARGET_IDS:
        print(f"\n=== {cctv_id} ===")
        try:
            resp = requests.get(API_URL, params={"cctvId": cctv_id}, headers=HEADERS, verify=False, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                print(f"Name: {data.get('CCTVNAME')}")
                print(f"KIND: {data.get('KIND')}")
                print(f"CCTVIP: {data.get('CCTVIP')}")
                print(f"CH: {data.get('CH')}")
                print(f"ID: {data.get('ID')}")
                print(f"PASSWD: {data.get('PASSWD')}")
                print(f"PORT: {data.get('PORT')}")
            else:
                print(f"API Error: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    fetch_fresh_metadata()
