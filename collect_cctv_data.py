import concurrent.futures
import importlib.util
import os
import threading
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
from cctv_runtime import atomic_write_json, build_proxy_url, camera_identity, camera_source_id, first_env, public_proxy_base, sanitize_utic_payload
from highway_traffic import (
    ITS_DEMO_KEY,
    KeyProblemError,
    UpstreamError,
    parse_its_cctv_response,
    resolve_api_key,
)
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

# Upstream key/availability problems seen during this run. Reported to
# data/workflow_status.json at the end of main() so a silently failing
# collector (e.g. missing GitHub secret) shows up on quality.html.
SOURCE_ISSUES = []
_SOURCE_ISSUES_LOCK = threading.Lock()


def record_source_issue(source, message, *, category="upstream", status="warning"):
    with _SOURCE_ISSUES_LOCK:
        SOURCE_ISSUES.append({
            "source": source,
            "message": message,
            "category": category,
            "status": status,
        })


def report_source_issues(issues=None, output=None):
    """Write collected source issues as workflow status events.

    Never raises: status reporting must not break a data refresh.
    """
    issues = list(SOURCE_ISSUES if issues is None else issues)
    if not issues:
        return 0
    try:
        module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "write_workflow_status.py")
        spec = importlib.util.spec_from_file_location("_write_workflow_status", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        kwargs = {"output": output} if output is not None else {}
        for issue in issues:
            prefix = "인증키 문제(key_problem): " if issue["category"] == "key_problem" else ""
            module.append_workflow_event(
                "Update CCTV Data",
                job=issue["source"],
                status=issue["status"],
                impact="possible",
                message=f"{prefix}{issue['message']}",
                category=issue["category"],
                **kwargs,
            )
        return len(issues)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[WARNING] Could not record source issues: {exc}")
        return 0


def normalize_its_items(cctv_list):
    normalized_data = []
    for item in cctv_list:
        # ITS data keys: cctvname, cctvurl, coordx, coordy
        if not item.get("cctvurl") or not item.get("coordx") or not item.get("coordy"):
            continue
        try:
            lng = float(item.get("coordx"))
            lat = float(item.get("coordy"))
        except (TypeError, ValueError):
            continue

        # Generate ID consistent with previous data: NTIC_[name]_[lng]
        cctv_name = item.get("cctvname", "Unknown")
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

        normalized_data.append({
            "id": cctv_id,
            "name": cctv_name,
            "lat": lat,
            "lng": lng,
            "url": url,
            "source": "NTIC",
            "status": "active",
            "canonical_id": canonical_id,
        })
    return normalized_data


def fetch_its_data():
    """Fetches CCTV data from the ITS API."""
    print("Fetching ITS data...")
    its_api_key, is_demo = resolve_api_key(
        "ITS_API_KEY", demo_key=ITS_DEMO_KEY, label="ITS cctvInfo", log=print
    )
    if is_demo:
        record_source_issue(
            "ITS",
            "ITS_API_KEY secret is not set; using the public demo key 'test' (may be revoked or rate limited).",
            category="key_problem",
            status="warning",
        )

    # Using a large bounding box to cover South Korea
    params = build_its_params(its_api_key)

    try:
        response = requests.get(ITS_API_URL, params=params, timeout=45)
        # ITS answers success as XML even with getType=json, and key errors
        # as HTTP 401 + JSON {"header": {"resultCode": 4005}}.
        cctv_list = parse_its_cctv_response(response.text, response.status_code)
        normalized_data = normalize_its_items(cctv_list)
        print(f"Fetched {len(normalized_data)} entries from ITS.")
        return normalized_data

    except KeyProblemError as e:
        key_label = "demo key 'test'" if is_demo else "ITS_API_KEY"
        print(f"Error fetching ITS data (key problem, {key_label}): {e}")
        record_source_issue("ITS", f"{key_label} rejected: {e}", category="key_problem", status="error")
        return []
    except UpstreamError as e:
        print(f"Error fetching ITS data: {e}")
        record_source_issue("ITS", str(e), category="upstream")
        return []
    except Exception as e:
        # requests exceptions embed the full URL, including apiKey.
        print(f"Error fetching ITS data: {type(e).__name__}")
        record_source_issue("ITS", f"request failed: {type(e).__name__}", category="upstream")
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
    utic_api_key = first_env("UTIC_API_KEY", "UTIC_KEY")
    if not utic_api_key:
        print("Error fetching UTIC data: UTIC_API_KEY / UTIC_KEY is not set")
        record_source_issue(
            "UTIC",
            "UTIC_API_KEY secret is not set; UTIC refresh skipped and existing UTIC records reused.",
            category="key_problem",
            status="error",
        )
        return []
    try:
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

    reported = report_source_issues()
    if reported:
        print(f"Recorded {reported} source issue(s) in data/workflow_status.json")


if __name__ == "__main__":
    main()
