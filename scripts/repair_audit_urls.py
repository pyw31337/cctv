
import json
import requests
import urllib.parse
import time
import os
import sys

# Configuration
CCTV_DATA_FILE = "cctv_data.json"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.utic.go.kr/"
}

# IDs known to require special handling
SPECIAL_PREFIXES = ["E60", "E61", "E62", "E63"] 
# Seoul City streams (L codes) might need checking too
SEOUL_PREFIXES = ["L"]

def fetch_details(cctv_id):
    try:
        resp = requests.get(API_URL, params={"cctvId": cctv_id}, headers=HEADERS, verify=False, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching {cctv_id}: {e}")
    return None

def construct_robust_url(cctv_id, details):
    if not details: return None
    
    # Special Cases (Flood Control)
    if "E61" in cctv_id: # Nakdong
        return f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={details.get('ID', '')}"
    elif "E60" in cctv_id: # Han River
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={details.get('ID', '')}"
    elif "E62" in cctv_id: # Geum River
        return f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={details.get('PASSWD', '')}&cctvcd={details.get('ID', '')}"
    elif "E63" in cctv_id: # Yeongsan River
        return f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={details.get('PASSWD', '')}"
        
    # Standard UTIC Construction
    cctv_name = details.get("CCTVNAME", "")
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))
    
    # FORCE kind=1 for Seoul (L-codes) as 'MODE' often fails on mobile
    kind = details.get("KIND", "")
    if cctv_id.startswith("L"):
        kind = "1"
    
    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
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
    print("Starting Post-Audit URL Repair...")
    
    with open(CCTV_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    updated_count = 0
    
    for item in data:
        cid = item["id"]
        needs_repair = False
        
        # Check if ID needs repair
        for p in SPECIAL_PREFIXES:
            if cid.startswith(p):
                needs_repair = True
                break
        
        # Also check L codes (Seoul) if they look suspicious or just to force refresh
        # The user reported "L010227" (Onsu) broken.
        if cid.startswith("L"):
             needs_repair = True

        if needs_repair:
            print(f"Repairing {cid} ({item['name']})...", end=" ")
            details = fetch_details(cid)
            if details:
                new_url = construct_robust_url(cid, details)
                if new_url and new_url != item["url"]:
                    print(f" -> FIXED")
                    item["url"] = new_url
                    item["lastVerified"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    updated_count += 1
                else:
                    print(" -> No Change")
            else:
                 print(" -> Fetch Failed")
            time.sleep(0.1)

    if updated_count > 0:
        with open(CCTV_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Repaired {updated_count} URLs.")
    else:
        print("No URLs needed repair.")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
