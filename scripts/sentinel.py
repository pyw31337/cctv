import json
import math
import os
import random
import requests
import sys
import traceback
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, quote

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'cctv_data.json')
CONFIG_FILE = os.path.join(BASE_DIR, 'configs', 'region_config.json')
STATUS_FILE = os.path.join(BASE_DIR, 'data', 'status.json')
LOG_FILE = os.path.join(BASE_DIR, 'sentinel.log')
REQUEST_TIMEOUT = 15
ORACLE_BASE = 'https://158.179.194.163.sslip.io'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

KNOWN_REGION_KEYS = {
    'BUSAN', 'CCTVWORLD', 'CHUNGJU', 'DAEGU', 'DAEJEON', 'FITIC', 'GANGWON',
    'GGEX', 'GIGAEYES', 'GITS', 'GOYANG', 'GWANGJU', 'ICITS', 'INCHEON',
    'JEJU', 'KBS', 'KNPS', 'NOWJEJU', 'NTIC', 'PAJU', 'SEJONG', 'SPATIC',
    'TOPIS', 'TRENDWORLD', 'ULLEUNG', 'ULSAN', 'UTIC', 'YT'
}

SOURCE_REGION_ALIASES = {
    'BUSAN_ITS': 'BUSAN',
    'CCTVWORLD': 'CCTVWORLD',
    'CHUNGJU': 'CHUNGJU',
    'DAEGU': 'DAEGU',
    'DAEJEON_ITS': 'DAEJEON',
    'FITIC': 'FITIC',
    'GANGWON': 'GANGWON',
    'GGEX': 'GGEX',
    'GIGAEYES': 'GIGAEYES',
    'GITS': 'GITS',
    'GOYANG': 'GOYANG',
    'GWANGJU': 'GWANGJU',
    'ICITS': 'ICITS',
    'INCHEON_ITS': 'INCHEON',
    'JEJU': 'JEJU',
    'KBS': 'KBS',
    'KNPS': 'KNPS',
    'NOWJEJU': 'NOWJEJU',
    'NTIC': 'NTIC',
    'SEJONG': 'SEJONG',
    'SPATIC': 'SPATIC',
    'TOPIS': 'TOPIS',
    'TRENDWORLD': 'TRENDWORLD',
    'ULLEUNG': 'ULLEUNG',
    'ULSAN': 'ULSAN',
    'YOUTUBE': 'YT',
    'YT_CUSTOM': 'YT'
}

os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)


def utc_timestamp():
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_msg = f'[{timestamp}] {message}'
    print(log_msg)
    with open(LOG_FILE, 'a', encoding='utf-8') as handle:
        handle.write(log_msg + '\n')


def load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r', encoding='utf-8') as handle:
        return json.load(handle)


def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def get_url_param(url, key):
    if not url:
        return None
    try:
        query = urlparse(url).query
        values = parse_qs(query).get(key)
        return values[0] if values else None
    except Exception:
        return None


def get_z3_cctvip(url):
    cctvip = get_url_param(url, 'cctvip')
    if cctvip:
        return cctvip
    try:
        parsed = urlparse(url or '')
        if 'cctvsec.ktict.co.kr' not in parsed.netloc:
            return None
        first_segment = parsed.path.strip('/').split('/', 1)[0]
        return first_segment if first_segment.isdigit() else None
    except Exception:
        return None


def is_unsupported_browser_stream(cctv):
    if not cctv:
        return False
    url = cctv.get('directUrl') or cctv.get('url') or ''
    source = cctv.get('source', '')
    kind = get_url_param(url, 'kind')
    stream_id = get_url_param(url, 'id')
    if source == 'UTIC' and kind == 'K' and stream_id and infer_region_name(cctv) == 'JEJU':
        return False
    return source == 'UTIC' and kind == 'K'


def infer_region_name(cctv):
    if not cctv:
        return None

    region_key = cctv.get('regionKey')
    if region_key:
        return region_key

    cctv_id = cctv.get('id', '')
    name = cctv.get('name', '')
    source = cctv.get('source', '')
    url = cctv.get('directUrl') or cctv.get('url') or ''
    prefix = cctv_id.split('_')[0] if '_' in cctv_id else None
    daejeon_inline_id = get_url_param(url, 'id')

    if cctv.get('urlType') == 'daejeon_mp4_dynamic' or cctv_id.startswith('DAEJEON_') or source == 'DAEJEON_ITS':
        return 'DAEJEON'
    if source == 'UTIC' and (cctv_id.startswith('E07') or '대전시' in name):
        return 'DAEJEON'
    if source == 'UTIC' and daejeon_inline_id and daejeon_inline_id.startswith('CCTV'):
        return 'DAEJEON'
    if source == 'UTIC' and (cctv_id.startswith('L380') or '제주' in name):
        return 'JEJU'
    if source == 'JEJU':
        return 'JEJU'
    if source == 'UTIC' and cctv_id.startswith('L12'):
        return 'PAJU'
    if prefix and prefix in KNOWN_REGION_KEYS:
        return prefix
    if source in SOURCE_REGION_ALIASES:
        return SOURCE_REGION_ALIASES[source]
    if source in KNOWN_REGION_KEYS:
        return source
    return None


def get_daejeon_url(stream_id, offset_minutes=2):
    now_utc = datetime.utcnow()
    kst_time = now_utc + timedelta(hours=9) - timedelta(minutes=offset_minutes)
    timestamp = kst_time.strftime('%Y%m%d.%H%M00')

    if 'DAEJEON_' in stream_id:
        clean_id = stream_id.replace('DAEJEON_', '')
        if clean_id.startswith('CCTV'):
            clean_id = f"CTV{clean_id[4:].zfill(4)}"
        stream_id_formatted = clean_id
    else:
        stream_id_formatted = stream_id

    return f'https://tportal.daejeon.go.kr:37084/01/media/{stream_id_formatted}/{stream_id_formatted}_{timestamp}.000.mp4'


def check_daejeon_stream(cctv):
    stream_id = cctv.get('id', '')
    for offset in range(1, 4):
        url = get_daejeon_url(stream_id, offset)
        try:
            resp = requests.head(url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS)
            if resp.status_code == 200:
                log(f'[OK] Daejeon {stream_id} is UP (Offset {offset}m)')
                return True
            log(f'[FAIL] Daejeon {stream_id} (Offset {offset}m) returned {resp.status_code}')
        except Exception as error:
            log(f'[ERR] Daejeon {stream_id} check failed: {error}')
    return False


def check_jeju_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url') or ''
    source = cctv.get('source', '')
    kind = get_url_param(url, 'kind')
    parsed_id = parse_qs(urlparse(url).query).get('id', [None])[0]
    stream_id = cctv.get('original_id') or parsed_id or cctv.get('id')

    if not ((source == 'UTIC' and kind == 'K' and parsed_id) or source == 'JEJU' or 'jejuits.go.kr' in url):
        return check_generic_stream(cctv)

    proxy_url = f"https://158.179.194.163.sslip.io/jeju?id={stream_id}"
    try:
        # The Oracle server can resolve Jeju tokens reliably, but its egress to
        # media*.jejuits.go.kr:7001 is often slower than real browsers. Treat a
        # valid redirect as resolver-healthy and let browser telemetry judge
        # actual playback speed.
        resp = requests.get(proxy_url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS, allow_redirects=False, stream=True)
        location = resp.headers.get('Location', '')
        if resp.status_code in (301, 302, 303, 307, 308) and location.startswith('http'):
            log(f"[OK] Jeju {cctv.get('id')} token redirect is UP")
            return True
        content_type = resp.headers.get('Content-Type', '').lower()
        if resp.status_code == 200 and ('mpegurl' in content_type or resp.raw.read(8, decode_content=True).startswith(b'#EXTM3U')):
            log(f"[OK] Jeju {cctv.get('id')} is UP")
            return True
        log(f"[FAIL] Jeju {cctv.get('id')} returned {resp.status_code} {content_type}")
    except Exception as error:
        log(f"[ERR] Jeju {cctv.get('id')} check failed: {error}")
        return False


def check_paju_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url')
    if not url:
        return False

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS, stream=True)
        if resp.status_code in (200, 302):
            log(f"[OK] Paju {cctv.get('id')} is UP")
            return True
        log(f"[FAIL] Paju {cctv.get('id')} returned {resp.status_code}")
    except Exception as error:
        log(f"[ERR] Paju {cctv.get('id')} check failed: {error}")
    return False


def check_generic_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url')
    if not url:
        return False

    if url.startswith('gangneung_player.html') or 'popup' in url:
        return True

    source = cctv.get('source', '')
    kind = get_url_param(url, 'kind')
    cctvip = get_z3_cctvip(url)
    cctvid = get_url_param(url, 'cctvid') or cctv.get('id', '')
    if source == 'KBS':
        cctvip = cctv.get('original_id') or cctvip or str(cctv.get('id', '')).split('_')[-1]
        url = f'{ORACLE_BASE}/kb?cctvip={cctvip}'
    elif (source == 'NTIC' or kind == 'Z3') and cctvip:
        url = f'{ORACLE_BASE}/utic?kind=Z3&cctvid={quote(cctvid)}&cctvip={quote(cctvip)}'
    elif source == 'UTIC' and kind in ['KB', 'EE', 'EEE'] and cctvip:
        url = f'{ORACLE_BASE}/kb?cctvip={cctvip}'

    if source in ['NOWJEJU', 'TRENDWORLD']:
        url = f'{ORACLE_BASE}/proxy?url={requests.utils.quote(url)}'

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS, stream=True)
        content_type = resp.headers.get('Content-Type', '').lower()
        if resp.status_code < 400 or (resp.status_code == 404 and 'mpegurl' in content_type):
            log(f"[OK] {cctv.get('id')} is UP")
            return True
        log(f"[FAIL] {cctv.get('id')} returned {resp.status_code}")
    except Exception as error:
        log(f"[ERR] {cctv.get('id')} check failed: {error}")
    return False


def check_camera(region_name, cctv):
    if region_name == 'DAEJEON':
        return check_daejeon_stream(cctv)
    if region_name == 'JEJU':
        return check_jeju_stream(cctv)
    if region_name == 'PAJU':
        return check_paju_stream(cctv)
    if is_unsupported_browser_stream(cctv):
        log(f"[UNSUPPORTED] {cctv.get('id')} uses a legacy UTIC browser plugin stream")
        return False
    return check_generic_stream(cctv)


def get_target_sample_size(total_cameras):
    if total_cameras <= 3:
        return total_cameras
    if total_cameras <= 10:
        return 3
    if total_cameras <= 50:
        return 4
    if total_cameras <= 200:
        return 5
    if total_cameras <= 1000:
        return 6
    if total_cameras <= 3000:
        return 7
    return 8


def get_sampling_bucket():
    now = datetime.utcnow()
    slot = 0 if now.minute < 30 else 1
    return now.strftime('%Y%m%d%H') + str(slot)


def select_representative_cameras(region_name, cameras, target_size):
    if not cameras:
        return [], 0, 0

    ordered = sorted(cameras, key=lambda cam: (cam.get('id', ''), cam.get('name', '')))
    if len(ordered) <= target_size:
        return ordered, len(ordered), 0

    stable_target = min(len(ordered), max(2, math.ceil(target_size * 0.5)))
    stable = []
    seen_ids = set()

    anchor_indices = [0, len(ordered) // 4, len(ordered) // 2, (len(ordered) * 3) // 4, len(ordered) - 1]
    for index in anchor_indices:
        cam = ordered[index]
        cam_id = cam.get('id')
        if cam_id in seen_ids:
            continue
        stable.append(cam)
        seen_ids.add(cam_id)
        if len(stable) >= stable_target:
            break

    if len(stable) < stable_target:
        remainder = [cam for cam in ordered if cam.get('id') not in seen_ids]
        remainder.sort(key=lambda cam: f"{region_name}:{cam.get('id', '')}:{cam.get('name', '')}")
        for cam in remainder:
            stable.append(cam)
            seen_ids.add(cam.get('id'))
            if len(stable) >= stable_target:
                break

    exploratory_target = max(0, target_size - len(stable))
    exploratory = []
    if exploratory_target > 0:
        remaining = [cam for cam in ordered if cam.get('id') not in seen_ids]
        sampler = random.Random(f'{region_name}:{get_sampling_bucket()}')
        if len(remaining) <= exploratory_target:
            exploratory = remaining
        else:
            exploratory = sampler.sample(remaining, exploratory_target)

    sample = stable + exploratory
    return sample, len(stable), len(exploratory)


def evaluate_region_health(checked, passed):
    failed = checked - passed
    failure_ratio = (failed / checked) if checked else 0.0

    if checked == 0:
        return 'UNKNOWN', failure_ratio
    if failed == 0:
        return 'OK', failure_ratio
    if passed == 0:
        return 'DOWN', failure_ratio
    if failed >= max(3, math.ceil(checked * 0.75)) and passed <= 1:
        return 'DOWN', failure_ratio
    if failed >= max(2, math.ceil(checked * 0.4)):
        return 'DEGRADED', failure_ratio
    return 'OK', failure_ratio


def test_region(region_name, cameras):
    if not cameras:
        return {
            'status': 'UNKNOWN',
            'checked': 0,
            'passed': 0,
            'failed': 0,
            'failure_ratio': 0.0,
            'camera_count': 0,
            'checked_at': utc_timestamp(),
            'sample_ids': [],
            'failed_ids': [],
            'sample_strategy': {
                'stable': 0,
                'exploratory': 0
            }
        }

    target_size = get_target_sample_size(len(cameras))
    sample, stable_count, exploratory_count = select_representative_cameras(region_name, cameras, target_size)
    sample_ids = [cam.get('id') for cam in sample if cam.get('id')]
    failed_ids = []
    passed = 0

    log(
        f'Testing {region_name} with {len(sample)} samples '
        f'(stable={stable_count}, exploratory={exploratory_count}, total_cameras={len(cameras)})'
    )

    for cam in sample:
        success = check_camera(region_name, cam)
        if success:
            passed += 1
        else:
            failed_ids.append(cam.get('id'))

    checked = len(sample)
    status, failure_ratio = evaluate_region_health(checked, passed)
    failed = checked - passed
    log(f'{region_name} result: {status} ({passed}/{checked} ok, failure_ratio={failure_ratio:.2f})')

    return {
        'status': status,
        'checked': checked,
        'passed': passed,
        'failed': failed,
        'failure_ratio': round(failure_ratio, 3),
        'camera_count': len(cameras),
        'checked_at': utc_timestamp(),
        'sample_ids': sample_ids,
        'failed_ids': failed_ids,
        'sample_strategy': {
            'stable': stable_count,
            'exploratory': exploratory_count
        }
    }


def build_region_map(cctv_data):
    region_map = {}
    items = cctv_data if isinstance(cctv_data, list) else []
    for cam in items:
        region_name = infer_region_name(cam)
        if not region_name:
            continue
        region_map.setdefault(region_name, []).append(cam)
    return region_map


def resolve_active_source(region_name, region_status, config):
    conf = config.get(region_name, {}) if isinstance(config, dict) else {}
    sub_type = conf.get('sub', {}).get('type')
    has_sub = sub_type and sub_type != 'none'
    if region_status == 'DOWN' and has_sub:
        return 'sub'
    return 'main'


def run_sentinel():
    try:
        log('--- Sentinel Started ---')

        cctv_data = load_json(DATA_FILE)
        if not cctv_data:
            log('No CCTV data loaded. Exiting.')
            return

        config = load_json(CONFIG_FILE)
        current_status = load_json(STATUS_FILE)
        if not isinstance(current_status, dict):
            log('Status file is not a dict. Initializing.')
            current_status = {}

        current_status.setdefault('regions', {})
        region_map = build_region_map(cctv_data)

        all_regions = set(region_map.keys()) | set(config.keys()) | set(current_status['regions'].keys())
        log(f'Discovered {len(all_regions)} regions: {sorted(all_regions)}')

        for region_name in sorted(all_regions):
            cameras = region_map.get(region_name, [])
            if not cameras:
                log(f'Skipping {region_name}: no cameras discovered in current dataset.')
                continue

            result = test_region(region_name, cameras)
            status_entry = current_status['regions'].setdefault(region_name, {})
            status_entry.update(result)
            status_entry['active_source'] = resolve_active_source(region_name, result['status'], config)

        current_status['last_updated'] = utc_timestamp()
        save_json(STATUS_FILE, current_status)
        log('--- Sentinel Finished ---')
    except Exception as error:
        log(f'FATAL ERROR in run_sentinel: {error}')
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run_sentinel()
