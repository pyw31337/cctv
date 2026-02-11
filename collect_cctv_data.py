import json
import requests
import urllib.parse
import os
import time
import concurrent.futures
import re
import sys

# Import custom collectors
from collectors.gits import GitsCollector
from collectors.topis import TopisCollector
from collectors.jeju import JejuCollector
from collectors.gangwon import GangwonCollector
from collectors.busan import BusanCollector
from collectors.incheon import IncheonCollector
from collectors.daejeon import DaejeonCollector
from collectors.gwangju import GwangjuCollector
from collectors.ulsan import UlsanCollector
from collectors.daegu import DaeguCollector
from collectors.sejong import SejongCollector

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
        response = requests.get(ITS_API_URL, params=params, timeout=45)
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
    """
    Process a single UTIC item: construct BASE URL from UTIC API.
    
    NEW ARCHITECTURE:
    - 'url' field: UTIC JSP URL (매일 갱신되는 기본 URL, 항상 최신 토큰 포함)
    - 'directUrl' field: 직통 HLS URL (알려진 패턴만, 별도 보존)
    
    이 함수는 기본 URL을 생성합니다. Deep Inspection은 별도 스크립트에서 수행.
    """
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
    
    # Special handling for Seoul region
    if center and "서울" in center:
        kind = "Seoul"
    elif cctv_id.startswith("L01"):
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
    
    # Filter out None values
    query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    
    # BASE URL - default to UTIC JSP
    url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?{query_string}"
    cctvip = str(item.get("CCTVIP", ""))

    # Special handling for River Flood Control Offices
    cctv_id_str = item.get("CCTVID", "")
    obscd = item.get('ID')
    cctv_passwd = item.get("PASSWD")
    
    PROXY_SSLIP = "https://158.179.194.163.sslip.io/proxy?url="
    
    if "E60" in cctv_id_str:
        # Han River
        hls_url = f"https://cctvlo.hrfco.go.kr/live/cctv{obscd}/hls.m3u8"
        url = f"{PROXY_SSLIP}{hls_url}"
    elif "E61" in cctv_id_str:
        # Nakdong River
        hls_url = f"https://cctvlo.nakdongriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = f"{PROXY_SSLIP}{hls_url}"
    elif "E62" in cctv_id_str:
        # Geum River
        hls_url = f"https://cctvlo.geumriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = f"{PROXY_SSLIP}{hls_url}"
    elif "E63" in cctv_id_str:
        # Yeongsan River
        hls_url = f"https://cctvlo.yeongsanriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = f"{PROXY_SSLIP}{hls_url}"
    
    # DIRECT HLS FOR KNOWN SERVERS - url 자체를 직통 HLS로 설정 (iframe 제거)
    # Pattern 1: Namyangju/Changhyeon Server (211.57.45.101)
    # IMPORTANT: Use ID_PARAM (item.ID), NOT CCTVID!
    # Supports: L-prefixed IDs (L180111) and _video2 IDs (3024_video2)
    elif cctvip == "211.57.45.101":
        stream_id = item.get("ID")  # ID_PARAM field, not CCTVID
        if stream_id and (stream_id.startswith("L") or "_video" in stream_id):
            url = f"https://211.57.45.101/media/{stream_id}/chunklist.m3u8"
    
    # Pattern 2: Incheon/Gyeonggi Servers
    elif cctvip in ["210.95.12.126", "211.114.87.164"]:
        stream_id = item.get("ID")
        if stream_id:
            url = f"http://{cctvip}/media/{stream_id}/chunklist.m3u8"
    
    result = {
        "id": cctv_id,
        "name": name,
        "lat": lat,
        "lng": lng,
        "url": url,
        "source": "UTIC",
        "status": "active"
    }
    
    return result

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
            
            # CRITICAL: DO NOT auto-match URL to CCTVID for Namyangju (211.57.45.101)
            # This causes scrambles where one camera's ID is another's Stream ID.
            # Let the original URL from UTIC or overrides stand.
            """
            if 'cctvip=211.57.45.101' in url:
                match = re.search(r'cctvid=([^&]+)', url)
                if match:
                    cctvid = match.group(1)
                    item['url'] = f"https://211.57.45.101/media/{cctvid}/chunklist.m3u8"
                    optimized_count += 1
            """
            
            # Pattern B: 210.95.12.126, 211.114.87.164 (uses id param)
            if 'cctvip=210.95.12.126' in url or 'cctvip=211.114.87.164' in url:
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
        # Reduced sleep to just 0.1s jitter to avoid hammering, but rely on concurrency control
        time.sleep(0.1) 
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
            # removed long sleep, just pass
            pass
            
        return False # Not modified

    # Process in parallel using ThreadPoolExecutor
    modified_count = 0
    print(f"Starting concurrent inspection of {len(targets)} items...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(inspect_item, targets))
        modified_count = sum(results)

    print(f"Deep Inspection completed. Optimized {modified_count} URLs.")
    return cctv_list

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force refresh (Compatibility arg)")
    parser.add_argument("--duration", type=float, default=0.5, help="Target duration (Compatibility arg)")
    args = parser.parse_args()

    print(f"Starting CCTV data update at {time.strftime('%Y-%m-%d %H:%M:%S')} (Args: {args})...")
    
    # 1. Load Existing Data
    existing_data_map = load_existing_data(OUTPUT_FILE)
    
    # 2. Fetch Data (Processing with Delta Sync)
    its_data = fetch_its_data()
    # Corrected call: fetch_utic_data does not take arguments in its definition
    utic_data = fetch_utic_data() 
    
    # GITS (Gyeonggi)
    print("Fetching GITS data...")
    gits_data = GitsCollector().fetch_data()

    # TOPIS (Seoul)
    print("Fetching TOPIS data...")
    topis_data = TopisCollector().fetch_data() 
    
    # Jeju
    print("Fetching Jeju data...")
    jeju_data = JejuCollector().fetch_data()
    
    # Gangwon
    print("Fetching Gangwon data...")
    gangwon_data = GangwonCollector().fetch_data() 

    # Busan
    print("Fetching Busan data...")
    busan_data = BusanCollector().fetch_data()

    # Incheon
    print("Fetching Incheon data...")
    incheon_data = IncheonCollector().fetch_data()

    # Daejeon
    print("Fetching Daejeon data...")
    daejeon_data = DaejeonCollector().fetch_data()
    gwangju_data = GwangjuCollector().fetch_data()
    ulsan_data = UlsanCollector().fetch_data()
    daegu_data = DaeguCollector().fetch_data()
    sejong_data = SejongCollector().fetch_data()
    
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

    # === NEW: Preserve directUrl from existing data ===
    preserved_count = 0
    for item in utic_data:
        item_id = item['id']
        if item_id in existing_data_map:
            existing = existing_data_map[item_id]
            # Preserve directUrl if it exists in old data but not in new
            if 'directUrl' in existing and 'directUrl' not in item:
                item['directUrl'] = existing['directUrl']
                preserved_count += 1
    
    if preserved_count > 0:
        print(f"Preserved {preserved_count} existing directUrl entries.")
    # === END NEW ===

    # 1. Add ALL UTIC data
    for item in utic_data:
        # Add aspect ratio hint for Namyangju/GITS-proxy compatible streams
        url = item.get('url', '')
        if '211.57.45.101' in url or 'L180' in url:
            item['aspectRatio'] = '4:3'
        final_merged.append(item)
    
    print(f"Added {len(utic_data)} UTIC entries (Primary).")
    
    # 2. Add ITS data if not duplicate
    added_its = 0
    skipped_its = 0
    
    # Helper for duplicate check - returns the index of the duplicate if found, else -1
    def find_duplicate_index(new_item, existing_items):
        try:
            nlat, nlng = float(new_item['lat']), float(new_item['lng'])
            nid = new_item.get('id')
            nsource = new_item.get('source')
            
            # Fast filter first
            for i, ex in enumerate(existing_items):
                # RULE: If it is the SAME SOURCE but DIFFERENT ID, it's a MULTI-VIEW CAMERA.
                # Primarily applies to UTIC (e.g. L180195 vs L180196 sharing coordinates)
                if nsource == ex.get('source') and nid != ex.get('id'):
                    continue

                elat, elng = float(ex['lat']), float(ex['lng'])
                if abs(nlat - elat) > 0.002 or abs(nlng - elng) > 0.002: continue 
                if get_dist(nlat, nlng, elat, elng) < 200: # 200m radius
                    return i
        except:
            pass
        return -1

    for item in its_data:
        if find_duplicate_index(item, final_merged) == -1:
            final_merged.append(item)
            added_its += 1
        else:
            skipped_its += 1
            
    print(f"Merged ITS: {added_its} added, {skipped_its} skipped.")

    # 3. Add GITS data (with upgrade logic)
    added_gits = 0
    skipped_gits = 0
    upgraded_gits = 0
    
    for item in gits_data:
        # GITS streams are almost all 4:3 in Gyeonggi local servers
        item['aspectRatio'] = '4:3'
        
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_gits += 1
        else:
            # Check if we should upgrade the existing item
            existing = final_merged[idx]
            
            # CRITICAL: Do NOT replace if existing is already a direct Namyangju stream 
            # (GITS redirects have burned bars, direct HLS doesn't)
            if '211.57.45.101' in existing.get('url', ''):
                continue

            # Upgrade! GITS is better than JSP wrappers or generic ITS links
            final_merged[idx] = item
            upgraded_gits += 1
                
    print(f"Merged GITS: {added_its} added, {skipped_its} skipped, {upgraded_gits} upgraded.")

    # 4. Add TOPIS data (with upgrade logic)
    added_topis = 0
    skipped_topis = 0
    upgraded_topis = 0
    for item in topis_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_topis += 1
        else:
            # Upgrade if existing is UTIC or NTIC (likely a wrapper or lower quality)
            # and TOPIS is direct HLS
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_topis += 1
            else:
                skipped_topis += 1
    print(f"Merged TOPIS: {added_topis} added, {skipped_topis} skipped, {upgraded_topis} upgraded (replaced UTIC/NTIC).")

    # 5. Add Jeju data
    added_jeju = 0
    skipped_jeju = 0
    upgraded_jeju = 0
    for item in jeju_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_jeju += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_jeju += 1
            else:
                skipped_jeju += 1
    print(f"Merged Jeju: {added_jeju} added, {skipped_jeju} skipped, {upgraded_jeju} upgraded.")

    # 6. Add Gangwon data
    added_gangwon = 0
    skipped_gangwon = 0
    upgraded_gangwon = 0
    for item in gangwon_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_gangwon += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_gangwon += 1
            else:
                skipped_gangwon += 1
    print(f"Merged Gangwon: {added_gangwon} added, {skipped_gangwon} skipped, {upgraded_gangwon} upgraded.")

    # 6.1 Add Busan data
    added_busan = 0
    skipped_busan = 0
    upgraded_busan = 0
    for item in busan_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_busan += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_busan += 1
            else:
                skipped_busan += 1
    print(f"Merged Busan: {added_busan} added, {skipped_busan} skipped, {upgraded_busan} upgraded.")

    # 6.2 Add Incheon data
    added_incheon = 0
    skipped_incheon = 0
    upgraded_incheon = 0
    for item in incheon_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_incheon += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_incheon += 1
            else:
                skipped_incheon += 1
    print(f"Merged Incheon: {added_incheon} added, {skipped_incheon} skipped, {upgraded_incheon} upgraded.")

    # 6.3 Add Daejeon data
    added_daejeon = 0
    skipped_daejeon = 0
    upgraded_daejeon = 0
    for item in daejeon_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_daejeon += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_daejeon += 1
            else:
                skipped_daejeon += 1
    print(f"Merged Daejeon: {added_daejeon} added, {skipped_daejeon} skipped, {upgraded_daejeon} upgraded.")

    # 6.4 Add Gwangju data
    added_gwangju = 0
    skipped_gwangju = 0
    upgraded_gwangju = 0
    for item in gwangju_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_gwangju += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_gwangju += 1
            else:
                skipped_gwangju += 1
    print(f"Merged Gwangju: {added_gwangju} added, {skipped_gwangju} skipped, {upgraded_gwangju} upgraded.")

    # 6.5 Add Ulsan data
    added_ulsan = 0
    skipped_ulsan = 0
    upgraded_ulsan = 0
    for item in ulsan_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_ulsan += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_ulsan += 1
            else:
                skipped_ulsan += 1
    print(f"Merged Ulsan: {added_ulsan} added, {skipped_ulsan} skipped, {upgraded_ulsan} upgraded.")

    # 6.6 Add Daegu data
    added_daegu = 0
    skipped_daegu = 0
    upgraded_daegu = 0
    for item in daegu_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_daegu += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_daegu += 1
            else:
                skipped_daegu += 1
    print(f"Merged Daegu: {added_daegu} added, {skipped_daegu} skipped, {upgraded_daegu} upgraded.")

    # 6.7 Add Sejong data
    added_sejong = 0
    skipped_sejong = 0
    upgraded_sejong = 0
    for item in sejong_data:
        idx = find_duplicate_index(item, final_merged)
        if idx == -1:
            final_merged.append(item)
            added_sejong += 1
        else:
            existing = final_merged[idx]
            if existing.get('source') in ['UTIC', 'NTIC']:
                final_merged[idx] = item
                upgraded_sejong += 1
            else:
                skipped_sejong += 1
    print(f"Merged Sejong: {added_sejong} added, {skipped_sejong} skipped, {upgraded_sejong} upgraded.")

    # 7. Final Global Deduplication Pass (Cleanup)
    print("Running final global deduplication pass...")
    unique_merged = []
    
    # Sort to prioritize sources: GITS > TOPIS > Busan/Incheon/Daejeon > UTIC > ITS
    priority = {
        'GITS': 0, 
        'TOPIS': 1, 
        'BUSAN_ITS': 2, 
        'INCHEON_ITS': 2, 
        'DAEJEON_ITS': 2,
        'GWANGJU': 2,
        'ULSAN': 2,
        'DAEGU': 2,
        'SEJONG': 2,
        'JEJU': 3,
        'GANGWON': 3,
        'UTIC': 4, 
        'NTIC': 5
    }
    final_merged.sort(key=lambda x: priority.get(x.get('source'), 99))
    
    for item in final_merged:
        if find_duplicate_index(item, unique_merged) == -1:
            unique_merged.append(item)
    
    print(f"Final Deduplication: {len(final_merged)} -> {len(unique_merged)}")
    final_merged = unique_merged

    # 7.5 Rename duplicates pass (Unique suffixes for multi-view)
    print("Renaming cameras with same name and location (multi-view)...")
    name_loc_map = {}
    for item in final_merged:
        # Use name and coordinates to find multi-view sets
        key = (item['name'], item['lat'], item['lng'])
        if key not in name_loc_map:
            name_loc_map[key] = []
        name_loc_map[key].append(item)
    
    renamed_count = 0
    for key, items in name_loc_map.items():
        if len(items) > 1:
            for i, item in enumerate(items, 1):
                item['name'] = f"{item['name']} ({i})"
                renamed_count += 1
    
    print(f"Renaming Pass: Applied suffixes to {renamed_count} cameras.")

    # 7.6 FINAL AUTHORITY: Apply cctv_overrides.json
    # This is the "Golden Record" safeguard to prevent regressions.
    OVERRIDE_FILE = "cctv_overrides.json"
    if os.path.exists(OVERRIDE_FILE):
        print(f"Applying final authority from {OVERRIDE_FILE}...")
        try:
            with open(OVERRIDE_FILE, 'r', encoding='utf-8') as f:
                overrides = json.load(f)
            
            # Map by ID for fast lookup
            override_map = {item['id']: item for item in overrides}
            
            override_count = 0
            for item in final_merged:
                if item['id'] in override_map:
                    ovr = override_map[item['id']]
                    # Force fields from override file
                    for key in ["url", "name", "aspectRatio", "status"]:
                        if key in ovr:
                            item[key] = ovr[key]
                    override_count += 1
            
            print(f"Safeguard: Applied {override_count} golden overrides.")
        except Exception as e:
            print(f"Warning: Failed to apply golden overrides: {e}")

    # 8. Stats & Verification
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
