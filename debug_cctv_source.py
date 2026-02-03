import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_utic():
    url = "https://www.utic.go.kr/map/mapcctv.do"
    key = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
    headers = {
        "Referer": "https://www.utic.go.kr/guide/cctvOpenData.do?key=" + key,
        "User-Agent": "Mozilla/5.0"
    }
    
    print("Fetching UTIC data...")
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=30)
        data = resp.json()
        print(f"UTIC Response Type: {type(data)}")
        
        items = []
        if isinstance(data, dict):
            if "result" in data: items = data["result"]
            elif "data" in data: items = data["data"]
        elif isinstance(data, list):
            items = data
            
        print(f"UTIC Items Found: {len(items)}")
        
        # Search for Guri or Achasan
        found = []
        for item in items:
            name = item.get("CCTVNAME", "")
            if "구리" in name or "아차산" in name:
                found.append(item)
                
        print(f"\nFound {len(found)} items matching '구리' or '아차산' in UTIC:")
        for res in found:
            print(f" - {res.get('CCTVNAME')} (ID: {res.get('CCTVID')})")
            
    except Exception as e:
        print(f"UTIC Error: {e}")

def check_its():
    url = "https://openapi.its.go.kr:9443/cctvInfo"
    key = "8c86cb02ef2647d9a6484c47386549ae"
    params = {
        "apiKey": key,
        "type": "all",
        "cctvType": "1",
        "minX": "124.0",
        "maxX": "132.0",
        "minY": "33.0",
        "maxY": "43.0",
        "getType": "json"
    }
    
    print("\nFetching ITS data...")
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        items = data.get("response", {}).get("data", [])
        if not items and "data" in data:
            items = data["data"]
            
        print(f"ITS Items Found: {len(items)}")
        
        found = []
        for item in items:
            name = item.get("cctvname", "")
            if "구리" in name or "아차산" in name:
                found.append(item)
                
        print(f"\nFound {len(found)} items matching '구리' or '아차산' in ITS:")
        for res in found:
            print(f" - {res.get('cctvname')} (URL: {res.get('cctvurl')})")

    except Exception as e:
        print(f"ITS Error: {e}")

if __name__ == "__main__":
    check_utic()
    check_its()
