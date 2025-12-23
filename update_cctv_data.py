
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
            # E60: Han River, E61: Nakdong River, E62: Geum River, E63: Yeongsan River
            cctv_id_str = item.get("CCTVID", "")
            
            # Extract common logic
            obscd = item.get('ID')
            cctv_passwd = item.get("PASSWD")
            
            if "E60" in cctv_id_str:
                url = f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={obscd}"
            elif "E61" in cctv_id_str:
                url = f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={obscd}"
            elif "E62" in cctv_id_str:
                # E62 (Geum River) logic from collect_cctv_data.py
                # https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={cctv_passwd}&cctvcd={details.get('ID', '')}
                url = f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={cctv_passwd}&cctvcd={obscd}"
            elif "E63" in cctv_id_str:
                # E63 (Yeongsan River) logic from collect_cctv_data.py
                # https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={cctv_passwd}
                url = f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={cctv_passwd}"
            
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
    
    # 2. Load Existing Data
    existing_data_map = load_existing_data(OUTPUT_FILE)
    
    final_data_list = []
    
    # Process ITS (NTIC)
    if its_data:
        print(f"Using {len(its_data)} new entries from ITS.")
        final_data_list.extend(its_data)
    else:
        # Fetch failed, try to recover from existing
        print("ITS fetch failed/empty. Attempting to recover existing ITS data...")
        existing_its = [item for item in existing_data_map.values() if item.get('source') == 'NTIC']
        if existing_its:
            print(f"Preserving {len(existing_its)} existing ITS entries.")
            final_data_list.extend(existing_its)
        else:
            print("No existing ITS data to preserve.")

    # Process UTIC
    if utic_data:
        print(f"Using {len(utic_data)} new entries from UTIC.")
        final_data_list.extend(utic_data)
    else:
        # Fetch failed, recover
        print("UTIC fetch failed/empty. Attempting to recover existing UTIC data...")
        existing_utic = [item for item in existing_data_map.values() if item.get('source') == 'UTIC']
        if existing_utic:
            print(f"Preserving {len(existing_utic)} existing UTIC entries.")
            final_data_list.extend(existing_utic)
        else:
            print("No existing UTIC data to preserve.")

    # 3. Stats & Verification
    print(f"Total entries combined: {len(final_data_list)}")

    # SAFETY GUARDRAIL: Check if data drop is too significant (> 20%)
    # Now we compare the FINAL list against the OLD list.
    if len(existing_data_map) > 0:
        existing_count = len(existing_data_map)
        new_count = len(final_data_list)
        
        drop_rate = (existing_count - new_count) / existing_count
        if drop_rate > 0.2:
            print(f"\n[CRITICAL WARNING] Data drop detected!")
            print(f"Existing: {existing_count} -> New: {new_count} (Drop rate: {drop_rate*100:.1f}%)")
            print("The drop rate still exceeds the 20% safety threshold even after preservation.")
            print("This indicates a massive loss of data from a successful fetch or total missing data.")
            print("Update ABORTED.")
            exit(1)
            
    # Calculate simple stats for change log (approximate)
    # Since we are rebuilding the list, 'updated' is hard to track perfectly without detailed diffing,
    # but strictly speaking, we just want to know how many are new/removed from the perspective of the FILE.
    
    added = 0
    removed = 0
    updated = 0 # Placeholder, hard to calculate cheaply with full rebuild strategy, but that's fine.
    
    # Simple count of ID presence
    new_ids = set(item['id'] for item in final_data_list)
    old_ids = set(existing_data_map.keys())
    
    added = len(new_ids - old_ids)
    removed = len(old_ids - new_ids)
    
    print(f"Summary:")
    print(f"  Total Result: {len(final_data_list)}")
    print(f"  New IDs: {added}")
    print(f"  Removed IDs: {removed}")
    
    # 4. Save
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_data_list, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
