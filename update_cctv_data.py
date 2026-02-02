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
            
            cctv_entry = {
                "id": cctv_id,
                "name": cctv_name,
                "lat": lat,
                "lng": lng,
                "url": item.get("cctvurl"),
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
    
    # [Optimization] Deep Inspection for HLS
    # Many UTIC streams are actually HLS wrapped in JSP.
    try:
        if "openDataCctvStream.jsp" in url:
            # Set a short timeout (e.g., 3s)
            jsp_res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=3)
            if jsp_res.status_code == 200:
                 match = re.search(r'(http[s]?://[^\s"\']+\.m3u8[^\s"\']*)', jsp_res.text)
                 if match:
                     direct_hls = match.group(1)
                     # print(f"  [Optimization] Found direct HLS for {name}") # Too noisy for threads
                     url = direct_hls
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
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
            print("Update ABORTED to allow manual inspection.")
            # print("Proceeding with caution... (User requested fix)") # Commented out for now
            return

    # 5. Save
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_merged, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
