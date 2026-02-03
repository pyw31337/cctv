
import json
import requests
import urllib.parse
import sys

# Configuration
UTIC_API_URL = "https://www.utic.go.kr/map/mapcctv.do"
UTIC_API_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
UTIC_HEADERS = {
    "Referer": "https://www.utic.go.kr/guide/cctvOpenData.do?key=" + UTIC_API_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_utic_data():
    print("Fetching UTIC data...")
    try:
        requests.packages.urllib3.disable_warnings()
        response = requests.get(UTIC_API_URL, headers=UTIC_HEADERS, timeout=60, verify=False)
        response.raise_for_status()
        data = response.json()
        
        items = data if isinstance(data, list) else []
        if isinstance(data, dict):
            if "result" in data: items = data["result"]
            elif "data" in data: items = data["data"]

        print(f"Found {len(items)} items in UTIC response.")
        
        found_count = 0
        for item in items:
            name = item.get("CCTVNAME", "")
            if "경부선" in name: # Kyungbu Line
                # Construct URL logic from update_cctv_data.py
                cctv_id = item.get("CCTVID")
                kind = item.get("KIND")
                center = item.get("CENTERNAME")
                
                if center and "서울" in center: kind = "Seoul"
                elif cctv_id.startswith("L01"): kind = "Seoul"

                params = {
                    "key": UTIC_API_KEY,
                    "cctvid": item.get("CCTVID"),
                    "cctvName": name, 
                    "kind": kind,
                    "cctvip": item.get("CCTVIP"),
                    "cctvch": item.get("CH"),
                    "id": item.get("ID"),
                    "cctvpasswd": item.get("PASSWD"),
                    "cctvport": item.get("PORT")
                }
                
                query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
                url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?{query_string}"
                
                print(f"Name: {name}")
                print(f"Source: UTIC")
                print(f"URL: {url}")
                print("-" * 20)
                
                found_count += 1
                if found_count >= 5:
                    break
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_utic_data()
