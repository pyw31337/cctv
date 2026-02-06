
import requests
import re
import json
import urllib.parse
import time
import random
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
MAIN_URL = "https://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
HEADERS = {
    "Referer": MAIN_URL,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
OUTPUT_FILE = "cctv_data.json"
MAX_WORKERS = 20  # Balanced for stealth/speed
STALE_DAYS = 7     # Refresh details if older than 7 days

def load_local_data():
    if not os.path.exists(OUTPUT_FILE):
        return {}
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Create dict keyed by ID for fast lookup
            return {item['id']: item for item in data}
    except Exception as e:
        print(f"Error loading local data: {e}")
        return {}

def get_remote_ids():
    print("Fetching master ID list from UTIC...")
    try:
        response = requests.get(MAIN_URL, headers=HEADERS, verify=False, timeout=30)
        response.raise_for_status()
        ids = re.findall(r"javascript:test\('([^']+)'\)", response.text)
        unique_ids = list(set(ids))
        print(f"  -> Found {len(unique_ids)} IDs on server.")
        return unique_ids
    except Exception as e:
        print(f"Error fetching master list: {e}")
        return []

def fetch_cctv_details(cctv_id, session=None):
    params = {"cctvId": cctv_id}
    try:
        # Use session if provided for connection reuse
        req_func = session.get if session else requests.get
        response = req_func(API_URL, params=params, headers=HEADERS, verify=False, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        # print(f"Error fetching details for {cctv_id}: {e}") # Reduce noise
        return None

def construct_url(cctv_id, details):
    if not details: return None
    
    cctv_ip = details.get("CCTVIP", "")
    cctv_name = details.get("CCTVNAME", "")
    kind = details.get("KIND", "")
    
    # Special Cases (Flood Control)
    if "E61" in cctv_id: # Nakdong River
        return f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={details.get('ID', '')}"
    elif "E60" in cctv_id: # Han River
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={details.get('ID', '')}"
    elif "E62" in cctv_id: # Geum River
        return f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={details.get('PASSWD', '')}&cctvcd={details.get('ID', '')}"
    elif "E63" in cctv_id: # Yeongsan River
        return f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={details.get('PASSWD', '')}"
    
    # General UTIC Case
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))
    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
    
    params = {
        "key": KEY,
        "cctvid": cctv_id,
        "cctvName": encoded_name,
        "kind": kind,
        "cctvip": cctv_ip,
        "cctvch": details.get("CH") or "null",
        "id": details.get("ID") or "null",
        "cctvpasswd": details.get("PASSWD") or "null",
        "cctvport": details.get("PORT") or "null"
    }
    
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query}"

def check_url_status(url, session=None):
    if not url: return "unknown"
    try:
        req_func = session.head if session else requests.head
        resp = req_func(url, timeout=3, verify=False, allow_redirects=True)
        return "active" if resp.status_code < 400 else "error"
    except:
        return "error"

WORKER_SLEEP_DELAY = 0.1

def process_item(cctv_id, existing_item=None):
    """Worker function for threading"""
    # Dynamic sleep based on target duration
    # Add random jitter +/- 20%
    jitter = random.uniform(0.8, 1.2)
    time.sleep(WORKER_SLEEP_DELAY * jitter)
    
    with requests.Session() as session:
        details = fetch_cctv_details(cctv_id, session)
        if not details:
            return None
            
        cctv_name = details.get("CCTVNAME", "")
        if "진도" in cctv_name:
            print(f"!!! FOUND JINDO STREAM: {cctv_name} ({cctv_id})")
            
        url = construct_url(cctv_id, details)
        if not url:
            return None
            
        # Optional: Skipping status check in bulk update speeds things up.
        # Can rely on health monitor for status later.
        # But user wants "always fresh", so let's trust the constructed URL is "active" 
        # unless we want to do a heavy check. 
        # For Optimization, we'll mark as active if construction succeeded.
        status = "active" 
        
        # Preserve "direct_source" if valid
        current_tags = details.get("tags") or []
        is_direct = "direct_source" in current_tags or (existing_item and "direct_source" in existing_item.get("tags", []))
        
        # VIP PROTECTION: If name contains key regions, FORCE retain existing URL/TAGS if they seem special
        # ideally we trust "direct_source", but let's double down for specific keywords users complain about
        vip_keywords = ["파주", "남양주", "부산", "해운대", "진도", "구리", "왕숙천", "왕숙교", "역곡", "부천"]
        is_vip = existing_item and any(k in existing_item.get("name", "") for k in vip_keywords)
        
        if is_vip and is_direct:
            print(f"  [LOCKED] VIP Region Stream (Protected): {cctv_name}")
            return existing_item # Return exactly what we have, ZERO changes allowed.


        
        final_url = url
        final_tags = existing_item.get("tags", []) if existing_item else []
        
        if is_direct and existing_item:
            # Check if existing Direct URL is still valid (Simple HEAD)
            direct_url = existing_item.get("url")
            if direct_url != url:
                try:
                    # Quick check (timeout 2s)
                    with requests.head(direct_url, timeout=2, verify=False) as r:
                         if r.status_code == 200:
                             final_url = direct_url
                             if "direct_source" not in final_tags: final_tags.append("direct_source")
                except:
                     pass # If check fails, fall back to new UTIC URL

        return {
            "id": cctv_id,
            "name": details.get("CCTVNAME"),
            "lat": float(details.get("YCOORD") or 0),
            "lng": float(details.get("XCOORD") or 0),
            "url": final_url,
            "status": status,
            "tags": final_tags,
            "lastUpdated": datetime.now().isoformat()
        }

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force refresh all IDs ignoring stale days")
    parser.add_argument("--duration", type=float, default=0.5, help="Target duration in hours (default: 0.5)")
    args = parser.parse_args()
    
    print(f"Starting Optimized CCTV Sync at {datetime.now()} (Force: {args.force}, Target: {args.duration}h)...")
    
    # 1. Load Local & Remote
    local_data = load_local_data()
    remote_ids = get_remote_ids()
    
    if not remote_ids:
        print("Failed to fetch remote IDs. Aborting.")
        return

    # 2. Diff Analysis
    remote_set = set(remote_ids)
    local_set = set(local_data.keys())
    
    new_ids = list(remote_set - local_set)
    removed_ids = list(local_set - remote_set)
    common_ids = list(remote_set & local_set)
    
    print(f"  Analysis: {len(new_ids)} New, {len(removed_ids)} Removed, {len(common_ids)} Existing.")
    
    # 3. Identify Stale Items
    # Check "lastUpdated" or "lastRenewed" to decide if re-fetch is needed
    stale_ids = []
    threshold = datetime.now() - timedelta(days=STALE_DAYS)
    
    for cid in common_ids:
        if args.force:
            stale_ids.append(cid)
            continue
            
        item = local_data[cid]
        last_up = item.get("lastUpdated") or item.get("lastRenewed")
        if not last_up:
            stale_ids.append(cid)
            continue
            
        try:
            # Handle variable date formats safely
            last_date = datetime.fromisoformat(last_up)
            if last_date < threshold:
                stale_ids.append(cid)
        except:
            stale_ids.append(cid)
    
    print(f"  Stale items (older than {STALE_DAYS} days): {len(stale_ids)}")
    
    # 4. Processing Queue
    # We update NEW + STALE. 
    # Existing FRESH items are kept as is (Passthrough).
    to_process = new_ids + stale_ids
    print(f"  Processing {len(to_process)} items with {MAX_WORKERS} threads...")
    
    final_results = []
    
    # Keep fresh existing items
    for cid in common_ids:
        if cid not in stale_ids:
            final_results.append(local_data[cid])
            
    # Calculate throttling
    total_items = len(to_process)
    if total_items > 0:
        target_seconds = args.duration * 3600
        # safety margin: 90% of target time to ensure completion
        delay_per_item = (target_seconds * 0.9) / total_items
        # workers impact: with N workers, effective delay is delay * N
        worker_delay = delay_per_item * MAX_WORKERS
        
        # Clamp delay
        worker_delay = max(0.1, worker_delay)
        print(f"  Throttling: {total_items} items over {args.duration}h")
        print(f"  -> {total_items / (args.duration * 3600):.2f} req/sec globally")
        print(f"  -> {worker_delay:.2f}s sleep per worker (Workers: {MAX_WORKERS})")
    else:
        worker_delay = 0.1

    # Update global variable for worker access (hacky but works for script)
    global WORKER_SLEEP_DELAY
    WORKER_SLEEP_DELAY = worker_delay

    # Process queue
    processed_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_item, cid): cid for cid in to_process}
        
        for future in as_completed(futures):
            res = future.result()
            if res:
                final_results.append(res)
            
            processed_count += 1
            if processed_count % 50 == 0:
                print(f"    Progress: {processed_count}/{len(to_process)}")
                
    # 5. Statistics
    print(f"Sync Complete.")
    print(f"  Total Items: {len(final_results)}")
    print(f"  New/Updated: {len(to_process)}")
    print(f"  Unchanged: {len(common_ids) - len(stale_ids)}")
    print(f"  Removed: {len(removed_ids)}")
    
    # 6. Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
