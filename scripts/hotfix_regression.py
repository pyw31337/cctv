
import json
import requests
import urllib.parse
import time

TARGETS = ["L010227", "L010224", "E600016"] # Onsu, Oryu IC, Neobudaegyo
CCTV_DATA_FILE = "cctv_data.json"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"

def fetch_details(cctv_id):
    try:
        # Hack to look like browser
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.utic.go.kr/"}
        resp = requests.get(API_URL, params={"cctvId": cctv_id}, headers=headers, verify=False, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def construct_url(cctv_id, details):
    if not details: return None
    
    # E60 (Han River)
    if "E60" in cctv_id: 
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={details.get('ID', '')}"
        
    # L-codes (Seoul) -> Force kind=1
    cctv_name = details.get("CCTVNAME", "")
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))
    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
    
    # FORCE kind=1
    kind = "1"
    
    params = {
        "key": "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI",
        "cctvid": cctv_id,
        "cctvName": encoded_name,
        "kind": kind,
        "cctvip": details.get("CCTVIP", ""),
        "cctvch": details.get("CH") or "null",
        "id": details.get("ID") or "null",
        "cctvpasswd": details.get("PASSWD") or "null",
        "cctvport": details.get("PORT") or "null"
    }
    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{qs}"

def main():
    print("Running Hotfix...")
    with open(CCTV_DATA_FILE, "r") as f:
        data = json.load(f)
        
    updated = 0
    for item in data:
        if item["id"] in TARGETS:
            print(f"Fixing {item['name']} ({item['id']})...")
            details = fetch_details(item["id"])
            if details:
                new_url = construct_url(item["id"], details)
                if new_url:
                    print(f" -> New URL: {new_url}")
                    item["url"] = new_url
                    item["lastVerified"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    updated += 1
    
    if updated > 0:
        with open(CCTV_DATA_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Saved.")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
