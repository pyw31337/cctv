
import requests
import json
import time
import random
import os
import sys
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

# Disable warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
MAIN_URL = "https://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
HEADERS = {
    "Referer": MAIN_URL,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
OUTPUT_FILE = "cctv_data_audit.json"
REPORT_FILE = "integrity_report.json"

# Safety Parameters
MAX_WORKERS = 10 
JITTER_MIN = 0.5
JITTER_MAX = 1.0

def load_local_data():
    if os.path.exists("cctv_data.json"):
        with open("cctv_data.json", "r", encoding="utf-8") as f:
            return {item["id"]: item for item in json.load(f)}
    return {}

def fetch_master_list():
    print("Fetching master ID list...")
    import re
    try:
        resp = requests.get(MAIN_URL, headers=HEADERS, verify=False, timeout=30)
        ids = re.findall(r"javascript:test\('([^']+)'\)", resp.text)
        unique_ids = list(set(ids))
        print(f"  -> Found {len(unique_ids)} IDs.")
        return unique_ids
    except Exception as e:
        print(f"  -> Failed to list IDs: {e}")
        return []

def fetch_details(cctv_id, session):
    # Safety Delay
    time.sleep(random.uniform(JITTER_MIN, JITTER_MAX))
    try:
        resp = session.get(API_URL, params={"cctvId": cctv_id}, headers=HEADERS, verify=False, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        return None
    return None

def construct_url(cctv_id, details):
    import urllib.parse
    # (Same logic as valid script)
    if not details: return None
    cctv_name = details.get("CCTVNAME", "")
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))
    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
    params = {
        "key": "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI",
        "cctvid": cctv_id,
        "cctvName": encoded_name,
        "kind": details.get("KIND", ""),
        "cctvip": details.get("CCTVIP", ""),
        "cctvch": details.get("CH") or "null",
        "id": details.get("ID") or "null",
        "cctvpasswd": details.get("PASSWD") or "null",
        "cctvport": details.get("PORT") or "null"
    }
    qs = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{qs}"

def process_id(cid):
    with requests.Session() as session:
        details = fetch_details(cid, session)
        if not details:
            return None
        
        name = details.get("CCTVNAME")
        lat = float(details.get("YCOORD") or 0)
        lng = float(details.get("XCOORD") or 0)
        url = construct_url(cid, details)
        
        return {
            "id": cid,
            "name": name,
            "lat": lat,
            "lng": lng,
            "url": url,
            "source": "UTIC",
            "status": "active", # Assuming active if details fetched
            "lastVerified": datetime.now().isoformat()
        }

def main():
    print(f"Starting Integrity Audit (Threads={MAX_WORKERS}, Delay={JITTER_MIN}-{JITTER_MAX}s)...")
    
    local_map = load_local_data()
    all_ids = fetch_master_list()
    
    if not all_ids:
        print("Aborting: No IDs found.")
        return

    verified_data = []
    changes = {"renamed": [], "moved": [], "new": [], "removed": []}
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_id, cid): cid for cid in all_ids}
        
        count = 0
        total = len(all_ids)
        
        for future in as_completed(futures):
            cid = futures[future]
            try:
                res = future.result()
                if res:
                    verified_data.append(res)
                    
                    # Compare
                    if cid in local_map:
                        old = local_map[cid]
                        if old["name"] != res["name"]:
                            changes["renamed"].append(f"{old['name']} -> {res['name']}")
                            print(f"[RENAME] {old['name']} -> {res['name']}")
                        if abs(old["lat"] - res["lat"]) > 0.001 or abs(old["lng"] - res["lng"]) > 0.001:
                            changes["moved"].append(f"{cid} moved")
                    else:
                        changes["new"].append(cid)
                
            except Exception as e:
                print(f"Error processing {cid}: {e}")
            
            count += 1
            if count % 100 == 0:
                elapsed = time.time() - start_time
                rate = count / elapsed
                print(f"Progress: {count}/{total} ({rate:.1f} items/sec)")

    # Identify removed
    remote_set = set(all_ids)
    for lid in local_map:
        if lid not in remote_set:
            changes["removed"].append(lid)
    
    # Save Verified Data
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(verified_data, f, ensure_ascii=False, indent=2)
        
    # Save Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": {
            "total_server": len(all_ids),
            "verified": len(verified_data),
            "new": len(changes["new"]),
            "removed": len(changes["removed"]),
            "renamed": len(changes["renamed"]),
            "moved": len(changes["moved"])
        },
        "changes": changes
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nAudit Complete.")
    print(f"  Total Verified: {len(verified_data)}")
    print(f"  Renamed: {len(changes['renamed'])}")
    print(f"  New: {len(changes['new'])}")
    print(f"  Removed: {len(changes['removed'])}")
    print(f"Saved to {OUTPUT_FILE} and {REPORT_FILE}")

if __name__ == "__main__":
    main()
