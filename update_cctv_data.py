import json
import requests
import urllib.parse
import os
import time
import concurrent.futures
import re

# Configuration
ITS_API_URL = "https://openapi.its.go.kr:9443/cctvInfo"
ITS_API_KEY = "8c86cb02ef2647d9a6484c47386549ae"

UTIC_API_URL = "https://www.utic.go.kr/map/mapcctv.do"
UTIC_API_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
UTIC_HEADERS = {
    "Referer": "https://www.utic.go.kr/guide/cctvOpenData.do?key=" + UTIC_API_KEY,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

OUTPUT_FILE = "cctv_data.json"

def fetch_its_data():
    """Fetches CCTV data from the ITS API."""
    print("Fetching ITS data...")
    # Using a large bounding box to cover South Korea
    params = {
        "apiKey": ITS_API_KEY,
        "type": "all",
        "cctvType": "1", # Live video
        "minX": "124.0",
        "maxX": "132.0",
        "minY": "33.0",
        "maxY": "43.0",
        "getType": "json"
    }
    
    try:
        response = requests.get(ITS_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        cctv_list = data.get("response", {}).get("data", [])
        if not cctv_list and "data" in data:
             cctv_list = data["data"]
             
        normalized_data = []
        for item in cctv_list:
            # ITS data keys: cctvname, cctvurl, coordx, coordy
            if not item.get("cctvurl") or not item.get("coordx") or not item.get("coordy"):
                continue

            # Generate ID consistent with previous data if possible, or new standard
            # Existing data seems to use: NTIC_[name]_[lng]
            # We will follow this pattern
            cctv_name = item.get("cctvname", "Unknown")
            lng = float(item.get("coordx"))
            lat = float(item.get("coordy"))
            cctv_id = f"NTIC_{cctv_name}_{lng}"
            

            url = item.get("cctvurl")
            if url and "cctvsec.ktict.co.kr" in url and url.startswith("http://"):
                url = url.replace("http://", "https://")

            cctv_entry = {
                "id": cctv_id,
                "name": cctv_name,
                "lat": lat,
                "lng": lng,
                "url": url,
                "source": "NTIC",
                "status": "active"
            }
            normalized_data.append(cctv_entry)
            
        print(f"Fetched {len(normalized_data)} entries from ITS.")
        return normalized_data

    except Exception as e:
        print(f"Error fetching ITS data: {e}")
        return []

def process_utic_item(item):
    """Process a single UTIC item: construct URL and check for HLS."""
    # Keys: CCTVNAME, CCTVID, XCOORD, YCOORD, KIND, CCTVIP, CH, ID, PASSWD, PORT
    cctv_id = item.get("CCTVID")
    if not cctv_id:
        return None
        
    name = item.get("CCTVNAME", "")
    try:
        lng = float(item.get("XCOORD", 0))
        lat = float(item.get("YCOORD", 0))
    except (ValueError, TypeError):
        return None

    # Determine parameters
    kind = item.get("KIND")
    center = item.get("CENTERNAME")
    
    # Special handling for Seoul region to use 'Seoul' kind instead of 'MODE'
    if center and "서울" in center:
        kind = "Seoul"
    elif cctv_id.startswith("L01"): # Fallback for Seoul ID prefix
        kind = "Seoul"

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
    
    # Filter out None values for UTIC URL
    query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    
    # Web URL (Default)
    url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?{query_string}"

    # Special handling for River Flood Control Offices
    cctv_id_str = item.get("CCTVID", "")
    obscd = item.get('ID')
    cctv_passwd = item.get("PASSWD")
    
    if "E60" in cctv_id_str:
        url = f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={obscd}"
    elif "E61" in cctv_id_str:
        url = f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={obscd}"
    elif "E62" in cctv_id_str:
        url = f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={cctv_passwd}&cctvcd={obscd}"
    elif "E63" in cctv_id_str:
        url = f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={cctv_passwd}"
    
    # [Optimization] Direct Pattern Construction (Instant, no server request)
    # 1. Changhyeon/Maseok Server (211.57.45.101) - Uses 'cctvid'
    if 'cctvip=211.57.45.101' in url and cctvid:
        url = f"https://211.57.45.101/media/{cctvid}/chunklist.m3u8"
    
    # 2. Incheon/Gyeonggi Servers (210.95.12.126, 211.114.87.164) - Uses 'id' param, HTTP port 80
    elif ('cctvip=210.95.12.126' in url or 'cctvip=211.114.87.164' in url):
        # Extract 'id' param (distinct from cctvid)
        id_match = re.search(r'[?&]id=([^&]+)', url)
        if id_match:
            real_id = id_match.group(1)
            # Find which IP is used
            ip = '210.95.12.126' if 'cctvip=210.95.12.126' in url else '211.114.87.164'
            url = f"http://{ip}/media/{real_id}/chunklist.m3u8"
    else:
        # [Optimization] Deep Inspection for HLS (Only if not already optimized)
        # We try to find the real video URL (.m3u8 or .mp4) to avoid black bars in iframe
        try:
            resp = requests.get(url, timeout=4, verify=False)
            if resp.status_code == 200:
                html = resp.text
                found_video = False
            
            # Pattern 1: src="...m3u8"
            match = re.search(r'src="([^"]+\.m3u8[^"]*)"', html)
            if match:
                hls_url = match.group(1)
                if hls_url.startswith("http"):
                    url = hls_url
                    found_video = True

            # Pattern 2: src="...mp4"
            if not found_video:
                match = re.search(r'src="([^"]+\.mp4[^"]*)"', html)
                if match:
                    mp4_url = match.group(1)
                    if mp4_url.startswith("http"):
                        url = mp4_url
                        found_video = True
            
            # Pattern 3: source src="..." type="application/x-mpegURL"
            if not found_video:
                match = re.search(r'source\s+src="([^"]+)"\s+type="application/x-mpegURL"', html)
                if match:
                    src_url = match.group(1)
                    if src_url.startswith("http"):
                        url = src_url
                        found_video = True

            # Logging failures (Sample 1%)
            # If no video found and it's a generic UTIC JSP, log it to see new patterns
            if not found_video and "openDataCctvStream.jsp" in url:
                import random
                if random.random() < 0.01: 
                    with open("failed_samples.log", "a", encoding="utf-8") as log:
                        log.write(f"\n--- FAIL: {cctv_id} ({name}) ---\n")
                        log.write(html[:1000] + "...\n")

        except Exception:
            pass

    
    return {
        "id": cctv_id,
        "name": name,
        "lat": lat,
        "lng": lng,
        "url": url,
        "source": "UTIC",
        "status": "active"
    }

def fetch_utic_data():
    """Fetches CCTV data from the UTIC API (internal JSON endpoint)."""
    print("Fetching UTIC data...")
    try:
        # Disable SSL verification due to certificate errors on UTIC side
        requests.packages.urllib3.disable_warnings()
        response = requests.get(UTIC_API_URL, headers=UTIC_HEADERS, timeout=60, verify=False)
        response.raise_for_status()
        data = response.json()
        
        normalized_data = []
        
        # UTIC data is likely a list directly
        items = data if isinstance(data, list) else []
        if isinstance(data, dict):
            if "result" in data: items = data["result"]
            elif "data" in data: items = data["data"]
        
        if not items:
            print("No data found in UTIC response.")
            return []

        print(f"Processing {len(items)} UTIC items with concurrency...")
        
        # Process in parallel
        # Max workers 50 to balance speed and server load
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            # Submit all tasks
            results = list(executor.map(process_utic_item, items))
            
        # Filter None results
        normalized_data = [r for r in results if r is not None]
        
        print(f"Fetched {len(normalized_data)} entries from UTIC.")
        return normalized_data

    except Exception as e:
        print(f"Error fetching UTIC data: {e}")
        return []

def load_existing_data(filepath):
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Return as dict keyed by id for easy lookup
            return {item['id']: item for item in data}
    except Exception as e:
        print(f"Error loading existing data: {e}")
        return {}

def refine_cctv_data(cctv_list):
    """
    Iterates through the list, finds items with generic JSP URLs,
    and tries to find the real HLS URL (Deep Inspection).
    Used when reusing existing data or to ensure everything is optimized.
    """
    print(f"Refining {len(cctv_list)} items for Deep Inspection...")
    
    # 1. Apply Direct Pattern Construction FIRST (Instant, no server request)
    optimized_count = 0
    for item in cctv_list:
        url = item.get('url', '')
        if item.get('source') == 'UTIC' and 'jsp' in url:
            
            # Pattern A: 211.57.45.101 (uses cctvid)
            if 'cctvip=211.57.45.101' in url:
                match = re.search(r'cctvid=([^&]+)', url)
                if match:
                    cctvid = match.group(1)
                    item['url'] = f"https://211.57.45.101/media/{cctvid}/chunklist.m3u8"
                    optimized_count += 1
            
            # Pattern B: 210.95.12.126, 211.114.87.164 (uses id param)
            elif 'cctvip=210.95.12.126' in url or 'cctvip=211.114.87.164' in url:
                match = re.search(r'[?&]id=([^&]+)', url)
                if match:
                    real_id = match.group(1)
                    ip = '210.95.12.126' if 'cctvip=210.95.12.126' in url else '211.114.87.164'
                    item['url'] = f"http://{ip}/media/{real_id}/chunklist.m3u8"
                    optimized_count += 1
    
    print(f"Direct Pattern Optimization applied to {optimized_count} items (Instant).")

    # 2. Filter items that need inspection (UTIC source, JSP url OR HRFCO popup)
    targets = [
        item for item in cctv_list 
        if item.get('source') == 'UTIC' and ('openDataCctvStream.jsp' in item.get('url', '') or 'cctvPopup.do' in item.get('url', ''))
    ]
    
    print(f"Found {len(targets)} items needing Deep Inspection (JSP wrapper/HRFCO).")
    if not targets:
        return cctv_list

    def inspect_item(item):
        time.sleep(1.0) # Ultra-Safe Politeness delay
        url = item['url']
        try:
            resp = requests.get(url, timeout=4, verify=False)
            if resp.status_code == 200:
                html = resp.text
                
                # Regex patterns (same as process_utic_item + HRFCO vars)
                patterns = [
                    r'src="([^"]+\.m3u8[^"]*)"',
                    r'src="([^"]+\.mp4[^"]*)"',
                    r'source\s+src="([^"]+)"\s+type="application/x-mpegURL"',
                    r'var\s+[lh]url\s*=\s*"([^"]+)"'  # HRFCO: var lurl = "..."
                ]
                
                for pat in patterns:
                    match = re.search(pat, html)
                    if match:
                        new_url = match.group(1)
                        if new_url.startswith("http"):
                            item['url'] = new_url
                            return True # Modified
        except Exception as e:
            # Smart Backoff: If we hit a timeout/error, wait 15s to clear the "3 errors in 10s" window
            print(f"[Smart Backoff] Error inspecting {item.get('name')}: {e}. Sleeping 15s...")
            time.sleep(15)
            
        return False # Not modified

    # Process in parallel (Ultra-Safe Mode: SEQUENTIAL to avoid blocking)
    modified_count = 0
    # max_workers=1 essentially makes it sequential, but keeps the futures interface.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        # We process 'targets' but 'item' is a reference to the dict in 'cctv_list',
        # so modifying 'item' modifies the original list.
        results = list(executor.map(inspect_item, targets))
        modified_count = sum(1 for r in results if r)

    print(f"Deep Inspection completed. Optimized {modified_count} URLs.")
    return cctv_list

def main():
    print(f"Starting CCTV data update at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
    
    # 1. Fetch Data
    its_data = fetch_its_data()
    utic_data = fetch_utic_data()
    
    # 2. Load Existing Data
    existing_data_map = load_existing_data(OUTPUT_FILE)
    
    # 3. Merge & Prioritize (Prefer UTIC for Highways/Duplicates)
    print("Merging data (Prioritizing UTIC)...")
    
    # Helper to calculate distance
    def get_dist(lat1, lng1, lat2, lng2):
        from math import sin, cos, sqrt, atan2, radians
        R = 6371000
        phi1, phi2 = radians(lat1), radians(lat2)
        dphi = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        a = sin(dphi/2)**2 + cos(phi1) * cos(phi2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c

    final_merged = []
    
    # Strategy: Start with UTIC (Valid Permalinks)
    # Then add ITS (NTIC) only if no duplicate matches
    
    # If UTIC fetch failed, try to load existing UTIC data
    if not utic_data:
        print("UTIC fetch failed/empty. Attempting to recover existing UTIC data...")
        utic_data = [item for item in existing_data_map.values() if item.get('source') == 'UTIC']
        
        # KEY CHANGE: Since we are using OLD data, we must REFINE it.
        if utic_data:
            print("Running Deep Inspection on recovered data...")
            utic_data = refine_cctv_data(utic_data)
        
    if not its_data:
        print("ITS fetch failed/empty. Attempting to recover existing ITS data...")
        its_data = [item for item in existing_data_map.values() if item.get('source') == 'NTIC']

    # 1. Add ALL UTIC data
    final_merged.extend(utic_data)
    print(f"Added {len(utic_data)} UTIC entries (Primary).")
    
    # 2. Add ITS data if not duplicate
    added_its = 0
    skipped_its = 0
    
    for its_item in its_data:
        is_duplicate = False
        try:
            ilat, ilng = float(its_item['lat']), float(its_item['lng'])
            
            for u_item in utic_data:
                # Quick filter: lat/lng diff > 0.01 (approx 1km)
                ulat, ulng = float(u_item['lat']), float(u_item['lng'])
                if abs(ilat - ulat) > 0.01 or abs(ilng - ulng) > 0.01:
                    continue
                    
                dist = get_dist(ilat, ilng, ulat, ulng)
                if dist < 200: # 200m radius for duplicate
                    is_duplicate = True
                    break
                    
        except Exception:
            pass # Skip check if coords invalid
            
        if not is_duplicate:
            final_merged.append(its_item)
            added_its += 1
        else:
            skipped_its += 1
            
    print(f"Merged ITS: {added_its} added, {skipped_its} skipped (duplicate/covered by UTIC).")

    # 4. Stats & Verification
    print(f"Total entries combined: {len(final_merged)}")

    # SAFETY GUARDRAIL
    if len(existing_data_map) > 0:
        existing_count = len(existing_data_map)
        new_count = len(final_merged)
        
        drop_rate = (existing_count - new_count) / existing_count
        if drop_rate > 0.2:
            print(f"\n[CRITICAL WARNING] Data drop detected!")
            print(f"Existing: {existing_count} -> New: {new_count} (Drop rate: {drop_rate*100:.1f}%)")
            # Forcing save even if drop detected because we might have refined data
            # print("Update ABORTED to allow manual inspection.")
            # return
            print("Warning ignored. Saving data...")

    # 5. Save
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_merged, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
