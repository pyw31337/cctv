
import json
import requests
import urllib.parse
import os
import time

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

        for item in items:
            # Keys: CCTVNAME, CCTVID, XCOORD, YCOORD, KIND, CCTVIP, CH, ID, PASSWD, PORT
            cctv_id = item.get("CCTVID")
            if not cctv_id:
                continue
                
            name = item.get("CCTVNAME", "")
            try:
                lng = float(item.get("XCOORD", 0))
                lat = float(item.get("YCOORD", 0))
            except (ValueError, TypeError):
                continue

            # Construct URL
            # Url format: https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=...&cctvid=...
            # Parameters need to be URL encoded
            
            # Using urllib.parse.quote for values
            def q(v): return urllib.parse.quote(str(v or ''))
            
            # Note: The 'key' in the url param is the API key.
            # Other params: cctvid, cctvName, kind, cctvip, cctvch, id, cctvpasswd, cctvport
            
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
            # E60: Han River, E61: Nakdong River
            # These require specific direct URLs using the 'ID' field
            cctv_id_str = item.get("CCTVID", "")
            if "E60" in cctv_id_str:
                url = f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={item.get('ID')}"
            elif "E61" in cctv_id_str:
                url = f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={item.get('ID')}"
            
            cctv_entry = {
                "id": cctv_id,
                "name": name,
                "lat": lat,
                "lng": lng,
                "url": url,
                "source": "UTIC",
                "status": "active"
            }
            normalized_data.append(cctv_entry)
            
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
    
    if not its_data and not utic_data:
        print("Failed to fetch data from both sources. Aborting update.")
        return

    new_data_list = its_data + utic_data
    new_data_map = {item['id']: item for item in new_data_list}
    
    # 2. Load Existing Data
    existing_data_map = load_existing_data(OUTPUT_FILE)
    
    # 3. Compare
    added = 0
    updated = 0
    removed = 0
    
    final_data_list = []
    
    # Check for additions and updates
    for cctv_id, new_item in new_data_map.items():
        if cctv_id not in existing_data_map:
            added += 1
            final_data_list.append(new_item)
        else:
            old_item = existing_data_map[cctv_id]
            # Check for changes in key fields
            # Note: Float comparison for lat/lng might be tricky, use epsilon if strict needed
            # For now, we update if url or name matches.
            # Actually, we should just use the new data as the source of truth for active items.
            # But we want to count stats.
            
            is_changed = (old_item.get('url') != new_item.get('url')) or \
                         (old_item.get('name') != new_item.get('name')) or \
                         (abs(old_item.get('lat', 0) - new_item.get('lat', 0)) > 0.00001) or \
                         (abs(old_item.get('lng', 0) - new_item.get('lng', 0)) > 0.00001)
                         
            if is_changed:
                updated += 1
            
            final_data_list.append(new_item)
            
    # Check for removals (IDs in old but not in new)
    # Only if we successfully fetched data for that source. 
    # If we failed ITS but got UTIC, we shouldn't delete all ITS entries.
    
    its_fetch_success = len(its_data) > 0
    utic_fetch_success = len(utic_data) > 0
    
    for cctv_id, old_item in existing_data_map.items():
        if cctv_id in new_data_map:
            continue
            
        # Item is missing in new data.
        # Check source to decide if we should remove it (i.e. if we successfully fetched that source and it's gone)
        source = old_item.get('source')
        if source == 'NTIC' and its_fetch_success:
            removed += 1
            # Don't add to final list (effectively removing)
        elif source == 'UTIC' and utic_fetch_success:
            removed += 1
        else:
            # Keep it if we didn't successfully fetch that source (preserve existing data on failure)
            final_data_list.append(old_item)

    print(f"Summary:")
    print(f"  Total entries: {len(final_data_list)}")
    print(f"  Added: {added}")
    print(f"  Updated: {updated}")
    print(f"  Removed: {removed}")
    
    # 4. Save
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data_list, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
