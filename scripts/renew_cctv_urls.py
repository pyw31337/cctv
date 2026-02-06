#!/usr/bin/env python3
"""
Renew CCTV URLs Script
Auto-renews broken or expired CCTV URLs by re-fetching data from UTIC API.
"""
import json
import requests
import urllib.parse
import time
from datetime import datetime
import re
import os

# Configuration
CCTV_DATA_FILE = "cctv_data.json"
FAILED_STREAMS_FILE = "failed_streams.json"
RENEWAL_REPORT_FILE = "renewal_report.json"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.utic.go.kr/"
}

def load_json(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_cctv_details(cctv_id):
    """Fetch fresh details from UTIC API"""
    params = {"cctvId": cctv_id}
    try:
        response = requests.get(API_URL, params=params, headers=HEADERS, verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching details for {cctv_id}: {e}")
        return None

def construct_url(cctv_id, details):
    """Re-construct the URL from fresh details (Logic from collect_cctv_data.py)"""
    if not details:
        return None
        
    cctv_ip = details.get("CCTVIP", "")
    cctv_name = details.get("CCTVNAME", "")
    kind = details.get("KIND", "")
    
    # Special Cases
    if "E61" in cctv_id: # Nakdong River
        return f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={details.get('ID', '')}"
    elif "E60" in cctv_id: # Han River
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={details.get('ID', '')}"
    elif "E62" in cctv_id: # Geum River
        return f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={details.get('PASSWD', '')}&cctvcd={details.get('ID', '')}"
    elif "E63" in cctv_id: # Yeongsan River
        return f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={details.get('PASSWD', '')}"
    
    # General Case
    # Double Encode Name to match UTIC behavior
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))

    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
    
    # Manually construct query string to ensure correct encoding
    params = {
        "key": KEY,
        "cctvid": cctv_id,
        "cctvName": encoded_name,
        "kind": kind,
        "cctvip": cctv_ip,
        "cctvch": details.get("CH") if details.get("CH") else "null",
        "id": details.get("ID", "null"),
        "cctvpasswd": details.get("PASSWD") if details.get("PASSWD") else "null",
        "cctvport": details.get("PORT") if details.get("PORT") else "null"
    }
    
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"

def main():
    print("Starting CCTV URL Renewal Process...")
    
    # Load data
    existing_data = load_json(CCTV_DATA_FILE)
    failed_streams = load_json(FAILED_STREAMS_FILE)
    
    if not existing_data or not failed_streams:
        print("Missing data files. Aborting.")
        return

    # Create a map for fast lookup
    data_map = {item['id']: item for item in existing_data}
    
    # Identify candidates for renewal
    # Focus on utic_null, http_404, and http_other
    candidates = []
    failed_groups = failed_streams.get("failures", {})
    
    for category in ["utic_null", "http_404", "http_other"]:
        if category in failed_groups:
            for item in failed_groups[category]:
                if item.get("id"):
                    candidates.append(item["id"])
    
    # Filter unique IDs
    candidates = list(set(candidates))
    print(f"Found {len(candidates)} candidates for renewal.")
    
    renewed_count = 0
    failed_count = 0
    skips = 0

    for cctv_id in candidates:
        if cctv_id not in data_map:
            print(f"Skipping {cctv_id} (not in current dataset)")
            continue
            
        print(f"Renewing {cctv_id}...", end=" ")
        
        # 1. Fetch fresh details
        details = fetch_cctv_details(cctv_id)
        if not details:
            print("❌ Fetch failed")
            failed_count += 1
            continue
            
        # 2. Construct new URL
        new_url = construct_url(cctv_id, details)
        if not new_url:
            print("❌ URL construction failed")
            failed_count += 1
            continue
            
        # 3. Compare and Update
        old_url = data_map[cctv_id].get("url", "")
        old_name = data_map[cctv_id].get("name", "")
        
        # Check if metadata changed
        new_name = details.get("CCTVNAME", old_name)
        new_lat = float(details.get("YCOORD", data_map[cctv_id].get("lat", 0)))
        new_lng = float(details.get("XCOORD", data_map[cctv_id].get("lng", 0)))
        
        changed = False
        
        if new_url != old_url:
            data_map[cctv_id]["url"] = new_url
            changed = True
            
        if new_name != old_name:
            data_map[cctv_id]["name"] = new_name
            print(f"  -> Name changed: {old_name} -> {new_name}")
            changed = True
            
        # Update coords if they differ significantly
        if abs(new_lat - float(data_map[cctv_id].get("lat", 0))) > 0.0001 or \
           abs(new_lng - float(data_map[cctv_id].get("lng", 0))) > 0.0001:
            data_map[cctv_id]["lat"] = new_lat
            data_map[cctv_id]["lng"] = new_lng
            changed = True
            
        if changed:
            data_map[cctv_id]["lastRenewed"] = datetime.now().isoformat()
            data_map[cctv_id]["status"] = "active"
            print("✅ UPDATED")
            renewed_count += 1
        else:
            print("⏭️ No change")
            skips += 1
            
        time.sleep(0.1) # Rate limiting
        
    print("-" * 40)
    print(f"Renewal Complete: {renewed_count} updated, {skips} skipped, {failed_count} failed.")
    
    # Save back to file
    if renewed_count > 0:
        save_json(CCTV_DATA_FILE, list(data_map.values()))
        print(f"Saved updated data to {CCTV_DATA_FILE}")
    else:
        print("No changes to save.")
        
    # Generate Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "candidates": len(candidates),
        "renewed": renewed_count,
        "skipped": skips,
        "failed": failed_count
    }
    save_json(RENEWAL_REPORT_FILE, report)

if __name__ == "__main__":
    # Disable SSL warnings
    requests.packages.urllib3.disable_warnings()
    main()
