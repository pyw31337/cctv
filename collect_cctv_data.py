import concurrent.futures
import gc
import json
import os
import re
import sys
import time
import urllib.parse
from functools import partial

import requests

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
from cctv_runtime import append_query_parameter, atomic_write_json, build_proxy_url, camera_identity, camera_source_id, first_env, public_proxy_base, require_env, sanitize_utic_payload
from collectors.pipeline import (
    SOURCE_PRIORITY as PIPELINE_PRIORITY,
    collect_in_parallel,
    finalize_cctv_records as pipeline_finalize_cctv_records,
    load_existing_data as pipeline_load_existing_data,
    merge_named_batches,
    preserve_direct_urls,
    refine_cctv_data as pipeline_refine_cctv_data,
)



# Configuration
ITS_API_URL = "https://openapi.its.go.kr:9443/cctvInfo"
UTIC_API_URL = "https://www.utic.go.kr/map/mapcctv.do"
OUTPUT_FILE = first_env("CCTV_OUTPUT_FILE", default="cctv_data.json")


def build_its_params(its_api_key):
    return {
        "apiKey": its_api_key,
        "type": "all",
        "cctvType": "1",  # Live video
        "minX": "124.0",
        "maxX": "132.0",
        "minY": "33.0",
        "maxY": "43.0",
        "getType": "json",
    }


def build_utic_headers(utic_api_key):
    return {
        "Referer": f"https://www.utic.go.kr/guide/cctvOpenData.do?key={utic_api_key}",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

def fetch_its_data():
    """Fetches CCTV data from the ITS API."""
    print("Fetching ITS data...")
    try:
        its_api_key = require_env("ITS_API_KEY")
    except RuntimeError as exc:
        print(f"Error fetching ITS data: {exc}")
        return []

    # Using a large bounding box to cover South Korea
    params = build_its_params(its_api_key)
    
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
            canonical_id = camera_identity({
                "source": "NTIC",
                "original_id": item.get("cctvurl") or item.get("cctvname") or cctv_id,
                "name": cctv_name,
                "lat": lat,
                "lng": lng,
            })

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
                "status": "active",
                "canonical_id": canonical_id,
            }
            normalized_data.append(cctv_entry)
            
        print(f"Fetched {len(normalized_data)} entries from ITS.")
        return normalized_data

    except Exception as e:
        print(f"Error fetching ITS data: {e}")
        return []

def process_utic_item(item, utic_api_key, proxy_base):
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
    cctvip = str(item.get("CCTVIP", "")).strip()

    # Special handling for River Flood Control Offices
    cctv_id_str = item.get("CCTVID", "")
    obscd = item.get('ID')
    cctv_passwd = item.get("PASSWD")
    
    if "E60" in cctv_id_str:
        # Han River
        hls_url = f"https://cctvlo.hrfco.go.kr/live/cctv{obscd}/hls.m3u8"
        url = build_proxy_url(proxy_base, hls_url)
    elif "E61" in cctv_id_str:
        # Nakdong River
        hls_url = f"https://cctvlo.nakdongriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = build_proxy_url(proxy_base, hls_url)
    elif "E62" in cctv_id_str:
        # Geum River
        hls_url = f"https://cctvlo.geumriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = build_proxy_url(proxy_base, hls_url)
    elif "E63" in cctv_id_str:
        # Yeongsan River
        hls_url = f"https://cctvlo.yeongsanriver.go.kr/live/cctv{obscd}/hls.m3u8"
        url = build_proxy_url(proxy_base, hls_url)
    
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
        utic_api_key = require_env("UTIC_API_KEY", "UTIC_KEY")
        # Disable SSL verification due to certificate errors on UTIC side
        requests.packages.urllib3.disable_warnings()
        response = requests.get(UTIC_API_URL, headers=build_utic_headers(utic_api_key), timeout=60, verify=False)
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
        proxy_base = public_proxy_base()
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # Submit all tasks
            results = list(
                executor.map(
                    partial(process_utic_item, utic_api_key=utic_api_key, proxy_base=proxy_base),
                    items,
                )
            )
            
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
            request_url = append_query_parameter(url, 'key', utic_api_key)
            resp = requests.get(request_url, timeout=4, verify=False)
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

def fetch_kbs_data():
    try:
        from collectors.kbs import KBSCollector

        return KBSCollector().fetch_data()
    except Exception as exc:
        print(f"[WARNING] KBS Collection failed: {exc}")
        print("Continuing with other sources...")
        return []


def fetch_cctv_world_data():
    try:
        from collectors.cctv_world import CCTVWorldCollector

        return CCTVWorldCollector().fetch_data()
    except Exception as exc:
        print(f"Error fetching CCTV World data: {exc}")
        return []


def fetch_ulleung_data():
    try:
        from collectors.ulleung import UlleungCollector

        return UlleungCollector().fetch_data()
    except Exception as exc:
        print(f"Error fetching Ulleungdo data: {exc}")
        return []


def split_cctv_world_items(items):
    separate_items = []
    mergeable_items = []
    for item in items or []:
        item = dict(item)
        if item.get("source") in {"YOUTUBE", "KBS", "CCTV_WORLD"}:
            item["source"] = "YOUTUBE"
            if not item.get("url"):
                try:
                    from collectors.kbs import KBSCollector

                    resolved = KBSCollector().resolve_stream_url(item.get("original_id"))
                    if resolved:
                        item["url"] = resolved
                    else:
                        continue
                except Exception:
                    continue
            separate_items.append(item)
        else:
            mergeable_items.append(item)
    return separate_items, mergeable_items


def normalize_ulleung_items(items):
    normalized = []
    for item in items or []:
        structure_id = str(item.get("structure_id", "")).strip()
        if not structure_id or not item.get("url"):
            continue
        tail = structure_id.split("_")[-1]
        normalized.append({
            "id": f"ULLEUNG_{tail}",
            "original_id": structure_id,
            "name": item.get("cctv_name", "Ulleung CCTV"),
            "lat": item.get("lat"),
            "lng": item.get("lng"),
            "url": item.get("url"),
            "source": "ULLEUNG",
            "status": "active",
            "address": item.get("address", ""),
            "backup_urls": [],
        })
    return normalized


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force refresh (Compatibility arg)")
    parser.add_argument("--duration", type=float, default=0.5, help="Target duration (Compatibility arg)")
    args = parser.parse_args()

    print(f"Starting CCTV data update at {time.strftime('%Y-%m-%d %H:%M:%S')} (Args: {args})...")

    existing_data_map = pipeline_load_existing_data(OUTPUT_FILE)

    primary_fetchers = [
        ("ITS", fetch_its_data),
        ("UTIC", fetch_utic_data),
        ("GITS", lambda: GitsCollector().fetch_data()),
        ("TOPIS", lambda: TopisCollector().fetch_data()),
        ("JEJU", lambda: JejuCollector().fetch_data()),
        ("GANGWON", lambda: GangwonCollector().fetch_data()),
        ("BUSAN", lambda: BusanCollector().fetch_data()),
        ("INCHEON", lambda: IncheonCollector().fetch_data()),
        ("DAEJEON", lambda: DaejeonCollector().fetch_data()),
        ("GWANGJU", lambda: GwangjuCollector().fetch_data()),
        ("ULSAN", lambda: UlsanCollector().fetch_data()),
        ("DAEGU", lambda: DaeguCollector().fetch_data()),
        ("SEJONG", lambda: SejongCollector().fetch_data()),
        ("KBS", fetch_kbs_data),
    ]
    auxiliary_fetchers = [
        ("CCTV_WORLD", fetch_cctv_world_data),
        ("TRENDWORLD", lambda: TrendWorldCollector().collect_data()),
        ("ULLEUNG", fetch_ulleung_data),
        ("NOWJEJU", lambda: NowJejuCollector().collect()),
        ("GIGAEYES", lambda: GigaEyesCollector().collect()),
        ("YT_CUSTOM", lambda: YoutubeCustomCollector().collect()),
        ("SPATIC", lambda: SpaticCollector().collect()),
    ]

    print("Fetching primary collectors in parallel...")
    primary_results = collect_in_parallel(primary_fetchers, label="primary collectors", max_workers=6)
    print("Fetching auxiliary collectors in parallel...")
    auxiliary_results = collect_in_parallel(auxiliary_fetchers, label="auxiliary collectors", max_workers=4)

    its_data = primary_results.get("ITS", [])
    utic_data = primary_results.get("UTIC", [])
    gits_data = primary_results.get("GITS", [])
    topis_data = primary_results.get("TOPIS", [])
    jeju_data = primary_results.get("JEJU", [])
    gangwon_data = primary_results.get("GANGWON", [])
    busan_data = primary_results.get("BUSAN", [])
    incheon_data = primary_results.get("INCHEON", [])
    daejeon_data = primary_results.get("DAEJEON", [])
    gwangju_data = primary_results.get("GWANGJU", [])
    ulsan_data = primary_results.get("ULSAN", [])
    daegu_data = primary_results.get("DAEGU", [])
    sejong_data = primary_results.get("SEJONG", [])
    kbs_data = primary_results.get("KBS", [])

    cctv_world_items = auxiliary_results.get("CCTV_WORLD", [])
    trend_data = auxiliary_results.get("TRENDWORLD", [])
    ulleung_data = auxiliary_results.get("ULLEUNG", [])
    nowjeju_data = auxiliary_results.get("NOWJEJU", [])
    gigaeyes_data = auxiliary_results.get("GIGAEYES", [])
    yt_custom_data = auxiliary_results.get("YT_CUSTOM", [])
    spatic_data = auxiliary_results.get("SPATIC", [])

    if not utic_data:
        print("UTIC fetch failed/empty. Attempting to recover existing UTIC data...")
        utic_data = [item for item in existing_data_map.values() if item.get("source") == "UTIC"]
        if utic_data:
            print("Running Deep Inspection on recovered data...")
            utic_data = pipeline_refine_cctv_data(utic_data)

    if not its_data:
        print("ITS fetch failed/empty. Attempting to recover existing ITS data...")
        its_data = [item for item in existing_data_map.values() if item.get("source") == "NTIC"]

    preserved_count = preserve_direct_urls(utic_data, existing_data_map)
    if preserved_count > 0:
        print(f"Preserved {preserved_count} existing directUrl entries.")

    for item in utic_data:
        url = item.get("url", "")
        if "211.57.45.101" in url or "L180" in url:
            item["aspectRatio"] = "4:3"
    for item in gits_data:
        item["aspectRatio"] = "4:3"

    cctv_world_separate, cctv_world_mergeable = split_cctv_world_items(cctv_world_items)
    ulleung_normalized = normalize_ulleung_items(ulleung_data)

    final_merged = []
    merge_named_batches(
        final_merged,
        [
            ("UTIC", utic_data),
            ("ITS", its_data),
            ("GITS", gits_data),
            ("TOPIS", topis_data),
            ("JEJU", jeju_data),
            ("GANGWON", gangwon_data),
            ("BUSAN", busan_data),
            ("INCHEON", incheon_data),
            ("DAEJEON", daejeon_data),
            ("GWANGJU", gwangju_data),
            ("ULSAN", ulsan_data),
            ("DAEGU", daegu_data),
            ("SEJONG", sejong_data),
            ("KBS", kbs_data),
            ("CCTV World", cctv_world_mergeable),
            ("TrendWorld", trend_data),
            ("Ulleungdo", ulleung_normalized),
            ("NowJeju", nowjeju_data),
            ("GiGAeyes", gigaeyes_data),
            ("Custom YouTube", yt_custom_data),
            ("SPATIC", spatic_data),
        ],
        priority_map=PIPELINE_PRIORITY,
    )

    if cctv_world_separate:
        print(f"Appending {len(cctv_world_separate)} independent CCTV World entries.")
        final_merged.extend(cctv_world_separate)

    final_merged = pipeline_finalize_cctv_records(
        final_merged,
        priority_map=PIPELINE_PRIORITY,
        override_file="cctv_overrides.json",
    )
    final_merged = sanitize_utic_payload(final_merged)

    print(f"Total entries combined: {len(final_merged)}")

    if len(existing_data_map) > 0:
        existing_count = len(existing_data_map)
        new_count = len(final_merged)
        drop_rate = (existing_count - new_count) / existing_count
        if drop_rate > 0.2:
            print("\n[CRITICAL WARNING] Data drop detected!")
            print(f"Existing: {existing_count} -> New: {new_count} (Drop rate: {drop_rate*100:.1f}%)")
            print("Warning ignored. Saving data...")

    try:
        atomic_write_json(OUTPUT_FILE, final_merged)
        print(f"Successfully saved updated data to {OUTPUT_FILE}")
    except Exception as exc:
        print(f"Error saving data: {exc}")


if __name__ == "__main__":
    main()
