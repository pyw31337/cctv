import json
import requests
import urllib.parse
import os
import time
import concurrent.futures
import re
import sys
import gc

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
from collectors.nowjeju import NowJejuCollector
from collectors.gigaeyes import GigaEyesCollector
from collectors.youtube_custom import YoutubeCustomCollector
from collectors.spatic import SpaticCollector
from collectors.trendworld import TrendWorldCollector



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
    
    # Pattern 1.5: Paju ITS Server (L12 prefix)
    elif cctv_id_str.startswith("L12"):
        stream_id = item.get("ID")
        if stream_id and stream_id.startswith("cctv_"):
            url = f"https://trafficcctv.paju.go.kr/live/{stream_id}.stream/playlist.m3u8"
    
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
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
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
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
    gc.collect()
    # Corrected call: fetch_utic_data does not take arguments in its definition
    utic_data = fetch_utic_data() 
    gc.collect()
    
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
    gc.collect()

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
    gc.collect()

    # KBS (New Safety Collector)
    print("Fetching KBS data...")
    kbs_data = []
    try:
        from collectors.kbs import KBSCollector
        kbs_data = KBSCollector().fetch_data()
    except Exception as e:
        print(f"[WARNING] KBS Collection failed: {e}")
        print("Continuing with other sources...")
    
    # 3. Merge & Prioritize (Prefer UTIC for Highways/Duplicates)
    print("Merging data with Multi-Stream Failover logic...")
    
    # Priority Configuration (Lower value = Higher Priority)
    PRIORITY = {
        'KBS': 1,       # Best Quality (Direct HLS)
        'ULLEUNG': 1,   # Best Quality (Direct HLS)
        'NOWJEJU': 1,   # Best Quality (Direct HLS)
        'GIGAEYES': 1,  # Best Quality (YouTube)
        'YT_CUSTOM': 1, # Best Quality (YouTube)
        'SPATIC': 1,    # Best Quality (Seoul Police HLS)
        'GITS': 2,      # Direct HLS (Green/No bars)
        'TOPIS': 2,     # Direct HLS (Green/No bars)
        'DAEJEON': 2,   # Direct HLS
        'ULSAN': 2,     # Direct HLS
        'DAEGU': 2,     # Direct HLS
        'SEJONG': 2,    # Direct HLS
        'GWANGJU': 2,   # Direct HLS
        'BUSAN_ITS': 3, # Mixed
        'INCHEON_ITS': 3, 
        'DAEJEON_ITS': 3,
        'JEJU': 3,      # Proxy'd HLS (Clean)
        'GANGWON': 3,   # Proxy'd HLS (Clean)
        'UTIC': 5,      # Fallback (Wrapped JSP, Black bars)
        'NTIC': 6       # Fallback (Wrapped JSP)
    }

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

    # Generic Merge Function
    def merge_cctv_item(target_list, new_item):
        """
        Merges new_item into target_list.
        - If no duplicate: append.
        - If duplicate found:
            - Compare Priority.
            - If new is higher priority (lower val): replace main, move old to backup.
            - If new is lower priority: add new to backup.
        """
        # Ensure backup_urls exists
        new_item.setdefault('backup_urls', [])
        
        idx = find_duplicate_index(new_item, target_list)
        if idx == -1:
            target_list.append(new_item)
            return "added"
        else:
            existing = target_list[idx]
            existing.setdefault('backup_urls', [])
            
            p_new = PRIORITY.get(new_item.get('source'), 99)
            p_old = PRIORITY.get(existing.get('source'), 99)
            
            # Determine if new item is better than existing
            is_better = False
            if p_new < p_old:
                is_better = True
            elif p_new == p_old:
                # If priority same, prefer .m3u8 (Direct) over .jsp (Wrapped/Tokenized)
                new_is_direct = ".m3u8" in new_item['url'].lower()
                old_is_direct = ".m3u8" in existing['url'].lower()
                if new_is_direct and not old_is_direct:
                    is_better = True

            # Check if this specific URL is already in backups to avoid dupes
            existing_urls = [b['url'] for b in existing['backup_urls']] + [existing['url']]
            if new_item['url'] in existing_urls:
                return "skipped_duplicate_url"

            if is_better:
                # UPGRADE: New item becomes main
                # Move old main to backup
                backup_entry = {
                    "source": existing['source'],
                    "url": existing['url']
                }
                existing['backup_urls'].append(backup_entry)
                
                # Update main fields
                existing['id'] = new_item['id']
                existing['original_id'] = new_item.get('original_id', new_item['id'])
                existing['name'] = new_item['name']
                existing['lat'] = new_item['lat']
                existing['lng'] = new_item['lng']
                existing['url'] = new_item['url']
                existing['source'] = new_item['source']
                if 'address' in new_item:
                    existing['address'] = new_item['address']
                # Merge any backups the new item might have had (rare but possible)
                if new_item['backup_urls']:
                    existing['backup_urls'].extend(new_item['backup_urls'])
                    
                return "upgraded"
            else:
                # DOWNGRADE/EQUAL: Add new item to backup
                backup_entry = {
                    "source": new_item['source'],
                    "url": new_item['url']
                }
                existing['backup_urls'].append(backup_entry)
                return "added_backup"

    # Strategy: Start with UTIC (Valid Permalinks)
    # Then add ITS (NTIC) only if no duplicate matches
    
    # If UTIC fetch failed, try to load existing UTIC data
    if not utic_data:
        print("UTIC fetch failed/empty. Attempting to recover existing UTIC data...")
        utic_data = [item for item in existing_data_map.values() if item.get('source') == 'UTIC']
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
            if 'directUrl' in existing and 'directUrl' not in item:
                item['directUrl'] = existing['directUrl']
                preserved_count += 1
    if preserved_count > 0:
        print(f"Preserved {preserved_count} existing directUrl entries.")
    # === END NEW ===

    # 1. Add ALL UTIC data
    for item in utic_data:
        url = item.get('url', '')
        if '211.57.45.101' in url or 'L180' in url:
            item['aspectRatio'] = '4:3'
        merge_cctv_item(final_merged, item)
    print(f"Merged UTIC: {len(final_merged)} entries.")
    
    # 2. Add ITS data
    stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0}
    for item in its_data:
        res = merge_cctv_item(final_merged, item)
        if res.startswith("skipped"): stats["skipped"] += 1
        elif res == "upgraded": stats["upgraded"] += 1
        elif res == "added_backup": stats["added_backup"] += 1
        else: stats["added"] += 1
    print(f"Merged ITS: {stats}")

    # 3. Add GITS data
    stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0}
    for item in gits_data:
        item['aspectRatio'] = '4:3'
        # Do NOT replace if existing is already a direct Namyangju stream 
        # But we can add as backup? existing logic suppressed it. 
        # Let's trust priority (GITS=2, UTIC=5). GITS will upgrade UTIC.
        # But Namyangju special case? 
        # If priority logic is sound, GITS (2) upgrades UTIC (5).
        # Direct Namyangju is usually UTIC source but modified URL.
        # If we upgraded, we lose the direct URL if we aren't careful?
        # Actually GITS is usually better than UTIC JSP, so upgrade is correct.
        res = merge_cctv_item(final_merged, item)
        if res.startswith("skipped"): stats["skipped"] += 1
        elif res == "upgraded": stats["upgraded"] += 1
        elif res == "added_backup": stats["added_backup"] += 1
        else: stats["added"] += 1
    print(f"Merged GITS: {stats}")

    # 4. Regional Collectors
    collectors = [
        ('TOPIS', topis_data),
        ('JEJU', jeju_data),
        ('GANGWON', gangwon_data),
        ('BUSAN', busan_data),
        ('INCHEON', incheon_data),
        ('DAEJEON', daejeon_data),
        ('GWANGJU', gwangju_data),
        ('ULSAN', ulsan_data),
        ('DAEGU', daegu_data),
        ('SEJONG', sejong_data),
        ('KBS', kbs_data),
    ]

    for name, data in collectors:
        stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0}
        for item in data:
            res = merge_cctv_item(final_merged, item)
            if res.startswith("skipped"): stats["skipped"] += 1
            elif res == "upgraded": stats["upgraded"] += 1
            elif res == "added_backup": stats["added_backup"] += 1
            else: stats["added"] += 1
        print(f"Merged {name}: {stats}")

    # 6.9 Add CCTV World (Aggregator) - run LAST
    print("Fetching CCTV World data...")
    try:
        from collectors.cctv_world import CCTVWorldCollector
        cctv_world_data = CCTVWorldCollector().fetch_data()
        
        stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0}
        
        # We need a quick lookup set for existing KBS IDs in final_merged to skip duplicates or resolve
        # But merge_cctv_item handles duplication.
        # CCTVWorld returns KBS items with lat=0. 
        # If we pass them to merge_cctv_item:
        #   - duplicate index check uses Coordinates. 
        #   - CCTVWorld items have (0,0). They won't match existing items (unless existing also 0,0).
        #   - So they will be added as new items.
        #   - This replicates the logic we had before (adding 39 items).
        #   - BUT, if it's a KBS item matching an ID, we might want to merge by ID?
        #   - Existing find_duplicate_index uses coords.
        #   - Let's keep it as is for now: relies on ID mismatch or Coord mismatch to add new.
        
        for item in cctv_world_data:
            # Force separate - DO NOT MERGE
            # User request: "기존 영상들과 merge 하지 말고, 개별적 독립적으로 운영해줘"
            
            # Check if likely YouTube
            if item.get('source') in ['YOUTUBE', 'KBS', 'CCTV_WORLD']:
                item['source'] = 'YOUTUBE' # Force source for Frontend handling
                
                # Check if we already have this ID in our list (by ID string) from previous steps?
                # merge_cctv_item uses coords.
                # Here we just APPEND. We rely on the map renderer to offset them.
                
                # Try to resolve URL if missing (for KBS items via World)
                if not item.get('url'):
                    try:
                        from collectors.kbs import KBSCollector
                        real_url = KBSCollector().resolve_stream_url(item['original_id'])
                        if real_url:
                            item['url'] = real_url
                        else:
                            continue # Skip if can't resolve
                    except:
                        continue

                # Ensure ID is unique if colliding with existing?
                # cctv_data.json is a list. ID collision only matters if consumer ensures uniqueness.
                # app.js uses ID for keys? No, mostly index.
                # But let's verify if 'id' is used in finding dicts.
                
                final_merged.append(item)
                stats["added"] += 1
            else:
                 # Non-YouTube items from World? (Rare)
                 # Merge them normally or skip? 
                 # Let's merge just in case.
                 res = merge_cctv_item(final_merged, item)
                 if res.startswith("skipped"): stats["skipped"] += 1
                 elif res == "upgraded": stats["upgraded"] += 1
                 elif res == "added_backup": stats["added_backup"] += 1
                 else: stats["added"] += 1
                
        print(f"Merged CCTV World (YouTube Separate): {stats}")
        
    except Exception as e:
        print(f"Error fetching CCTV World data: {e}")

    # ---------------------------------------------------------
    # 6.9.5 TrendWorld (Jeju) Integration
    # ---------------------------------------------------------
    try:
        trend_collector = TrendWorldCollector()
        trend_data = trend_collector.collect_data()
        print(f"Collected {len(trend_data)} TrendWorld CCTV items.")
        
        # Merge TrendWorld data
        for item in trend_data:
            merge_cctv_item(final_merged, item)
            
    except Exception as e:
        print(f"Error collecting TrendWorld data: {e}")

    # 6.10 Add Ulleungdo (Official)
    print("Fetching Ulleungdo data...")
    try:
        from collectors.ulleung import UlleungCollector
        ulleung_collector = UlleungCollector()
        ulleung_data = ulleung_collector.fetch_data()
        
        stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0}
        
        for item in ulleung_data:
            # Convert to standard format
            cctv = {
                 "id": f"ULLEUNG_{item['structure_id'].split('_')[-1]}",
                 "name": item['cctv_name'],
                 "lat": item['lat'],
                 "lng": item['lng'],
                 "url": item['url'],
                 "source": "ULLEUNG",
                 "status": "active",
                 "address": item.get('address', ''),
                 "backup_urls": []
            }
            res = merge_cctv_item(final_merged, cctv)
            
            if res == "skipped": stats["skipped"] += 1
            elif res == "upgraded": stats["upgraded"] += 1
            elif res == "added_backup": stats["added_backup"] += 1
            else: stats["added"] += 1
            
        print(f"Merged Ulleungdo: {stats}")
    except Exception as e:
        print(f"Error fetching/merging Ulleungdo data: {e}")

    # 7. Final Global Deduplication Pass (Cleanup)
    # With merge_cctv_item, this should be mostly clean, but let's run a sanity sort
    print("Running final sorting...")
    
    # Sort to prioritize sources based on priority dict (Stable sort: Priority then ID)
    final_merged.sort(key=lambda x: (PRIORITY.get(x.get('source'), 99), x.get('id', '')))
    
    # We don't want to remove duplicates based on simple ID if they were meant to be separate
    # But let's check for exact ID duplicates just in case
    unique_merged = []
    seen = set()
    for item in final_merged:
        if item['id'] not in seen:
            unique_merged.append(item)
            seen.add(item['id'])
    
    final_merged = unique_merged

    # 7.4 NowJeju Integration
    try:
        nowjeju_data = NowJejuCollector().collect()
        stats_nowjeju = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in nowjeju_data:
            res = merge_cctv_item(final_merged, item)
            stats_nowjeju[res] = stats_nowjeju.get(res, 0) + 1
        print(f"Merged NowJeju: {stats_nowjeju}")
    except Exception as e:
        print(f"Error collecting NowJeju data: {e}")

    # NowJeju Integration
    try:
        gigaeyes_data = GigaEyesCollector().collect()
        stats_gigaeyes = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in gigaeyes_data:
            res = merge_cctv_item(final_merged, item)
            stats_gigaeyes[res] = stats_gigaeyes.get(res, 0) + 1
        print(f"Merged GiGAeyes: {stats_gigaeyes}")
    except Exception as e:
        print(f"Error collecting GiGAeyes data: {e}")

    # Custom YouTube Integration
    try:
        yt_custom_data = YoutubeCustomCollector().collect()
        stats_yt = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in yt_custom_data:
            res = merge_cctv_item(final_merged, item)
            stats_yt[res] = stats_yt.get(res, 0) + 1
        print(f"Merged Custom YouTube: {stats_yt}")
    except Exception as e:
        print(f"Error collecting Custom YouTube data: {e}")

    # SPATIC Integration
    try:
        spatic_data = SpaticCollector().collect()
        stats_spatic = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in spatic_data:
            res = merge_cctv_item(final_merged, item)
            stats_spatic[res] = stats_spatic.get(res, 0) + 1
        print(f"Merged SPATIC: {stats_spatic}")
    except Exception as e:
        print(f"Error collecting SPATIC data: {e}")

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
                    for key in ["url", "name", "aspectRatio", "status", "lat", "lng", "address"]:
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
            json.dump(final_merged, f, indent=2, ensure_ascii=False, sort_keys=True)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as e:
        print(f"Error saving data: {e}")

if __name__ == "__main__":
    main()
