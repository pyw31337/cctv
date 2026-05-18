import json
import math
import os
import random
import re
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
EMERGENCY_INVESTIGATE_AFTER_MINUTES = 60
EMERGENCY_CRITICAL_AFTER_MINUTES = 120
CAMERA_FAILURE_REGISTRY_LIMIT = 500
DAEJEON_MP4_OFFSETS = [2, 4, 6, 8, 10, 1]
DAEJEON_REQUEST_TIMEOUT = (1.0, 1.5)
ORACLE_BASE = 'https://158.179.194.163.sslip.io'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

KNOWN_REGION_KEYS = {
    'BUSAN', 'CCTVWORLD', 'CHUNGJU', 'DAEGU', 'DAEJEON', 'FITIC', 'GANGWON',
    'GGEX', 'GIGAEYES', 'GITS', 'GOYANG', 'GWANGJU', 'ICITS', 'INCHEON',
    'JEJU', 'KBS', 'KNPS', 'NOWJEJU', 'NTIC', 'PAJU', 'SEJONG', 'SPATIC',
    'TOPIS', 'TRENDWORLD', 'ULLEUNG', 'ULSAN', 'UTIC', 'UTIC_DIRECT',
    'UTIC_LEGACY', 'UTIC_Z3', 'YT'
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


def parse_utc_timestamp(value):
    if not value:
        return None
    try:
        return datetime.strptime(value.replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
    except Exception:
        return None


def minutes_between(start_iso, end_iso):
    start = parse_utc_timestamp(start_iso)
    end = parse_utc_timestamp(end_iso)
    if not start or not end:
        return 0
    return max(0, int((end - start).total_seconds() // 60))


def set_probe_result(cctv, ok, reason='ok', category=None, status_code=None, url=None, content_type=None, detail=None):
    if cctv is None:
        return
    cctv['_probe_result'] = {
        'ok': bool(ok),
        'reason': reason,
        'category': category or ('ok' if ok else 'unknown'),
        'status_code': status_code,
        'url': url,
        'content_type': content_type,
        'detail': str(detail)[:240] if detail else None,
        'checked_at': utc_timestamp()
    }


def get_probe_result(cctv):
    probe = cctv.get('_probe_result') if isinstance(cctv, dict) else None
    return probe if isinstance(probe, dict) else {}


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


def get_source_specific_failure_category(cctv, fallback_category, status_code=None):
    url = cctv.get('directUrl') or cctv.get('url') or ''
    source = cctv.get('source') or ''
    region = infer_region_name(cctv)
    kind = get_url_param(url, 'kind')

    if source == 'GITS' or region == 'GITS':
        if status_code == 404 or fallback_category == 'not_found':
            return 'gits_source_missing'
        if status_code in (401, 403) or fallback_category in ('auth_or_token', 'token_or_manifest'):
            return 'gits_token_or_auth'
        return fallback_category

    if kind == 'Z3' or region == 'UTIC_Z3':
        if fallback_category == 'timeout':
            return 'z3_resolver_timeout'
        if status_code == 404 or fallback_category == 'not_found':
            return 'z3_stream_missing'
        if status_code in (401, 403) or fallback_category in ('auth_or_token', 'token_or_manifest'):
            return 'z3_token_or_manifest'
        if fallback_category in ('http_error', 'network_error'):
            return 'z3_resolver_error'
        return fallback_category

    if source == 'NTIC' or region == 'NTIC':
        if fallback_category == 'timeout':
            return 'ntic_resolver_timeout'
        if status_code == 404 or fallback_category == 'not_found':
            return 'ntic_stream_missing'
        if fallback_category in ('http_error', 'network_error'):
            return 'ntic_resolver_error'

    return fallback_category


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
    if source == 'UTIC':
        kind = get_url_param(url, 'kind')
        if kind == 'Z3':
            return 'UTIC_Z3'
        if kind in ['KB', 'EE', 'EEE']:
            return 'UTIC_DIRECT'
        return 'UTIC_LEGACY'
    if prefix and prefix in KNOWN_REGION_KEYS:
        return prefix
    if source in SOURCE_REGION_ALIASES:
        return SOURCE_REGION_ALIASES[source]
    if source in KNOWN_REGION_KEYS:
        return source
    return None


def normalize_daejeon_stream_id(raw_id):
    raw = str(raw_id or '').strip()
    if not raw:
        return None

    match = re.match(r'DAEJEON_(CCTV\d+)$', raw, re.I)
    if match:
        raw = match.group(1)

    match = re.match(r'CCTV(\d+)$', raw, re.I)
    if match:
        return f"CTV{match.group(1).zfill(4)}"

    match = re.match(r'CTV(\d+)$', raw, re.I)
    if match:
        return f"CTV{match.group(1).zfill(4)}"

    return None


def get_daejeon_stream_id(cctv):
    url = cctv.get('directUrl') or cctv.get('url') or ''
    candidates = [
        get_url_param(url, 'cctvpasswd'),
        get_url_param(url, 'id'),
        cctv.get('original_id'),
        cctv.get('id')
    ]
    for candidate in candidates:
        stream_id = normalize_daejeon_stream_id(candidate)
        if stream_id:
            return stream_id
    return None


def get_daejeon_media_path(cctv, stream_id):
    url = cctv.get('directUrl') or cctv.get('url') or ''
    cctvip = str(get_url_param(url, 'cctvip') or '')
    if cctvip == '118' or '210.99.67.118' in url or '192.168.12.101' in url:
        return '01'
    if cctvip == '119' or '210.99.67.119' in url or '192.168.12.102' in url:
        return '02'

    match = re.match(r'CTV0*(\d+)$', str(stream_id or ''), re.I)
    if match:
        number = int(match.group(1))
        return '01' if number < 51 else '02'

    return '01'


def get_daejeon_url(cctv, stream_id, offset_minutes=2):
    now_utc = datetime.utcnow()
    kst_time = now_utc + timedelta(hours=9) - timedelta(minutes=offset_minutes)
    timestamp = kst_time.strftime('%Y%m%d.%H%M00')
    media_path = get_daejeon_media_path(cctv, stream_id)
    return f'https://tportal.daejeon.go.kr:37084/{media_path}/media/{stream_id}/{stream_id}_{timestamp}.000.mp4'


def is_daejeon_mp4_candidate(cctv):
    url = cctv.get('directUrl') or cctv.get('url') or ''
    source = cctv.get('source', '')
    kind = get_url_param(url, 'kind')
    cctvip = get_url_param(url, 'cctvip')

    if cctv.get('urlType') == 'daejeon_mp4_dynamic' or source == 'DAEJEON_ITS':
        return True
    if source == 'UTIC' and kind == 'E' and infer_region_name(cctv) == 'DAEJEON':
        return True
    if source == 'UTIC' and cctvip in ('118', '119') and get_daejeon_stream_id(cctv):
        return True
    if 'traffic.daejeon.go.kr' in url or 'tportal.daejeon.go.kr' in url:
        return bool(get_daejeon_stream_id(cctv))

    return False


def check_daejeon_stream(cctv):
    stream_id = get_daejeon_stream_id(cctv)
    if not stream_id:
        # Some Daejeon-adjacent river cameras are ordinary HLS streams
        # (for example cctvlo.geumriver.go.kr) and do not have CTV/CCTV ids.
        # They should be checked as generic HLS instead of counted as broken
        # Daejeon timestamp-MP4 streams.
        return check_generic_stream(cctv)

    last_status = None
    last_url = None
    saw_http_response = False
    for offset in DAEJEON_MP4_OFFSETS:
        url = get_daejeon_url(cctv, stream_id, offset)
        last_url = url
        try:
            resp = requests.get(
                url,
                timeout=DAEJEON_REQUEST_TIMEOUT,
                verify=False,
                headers={**HEADERS, 'Range': 'bytes=0-1'},
                stream=True
            )
            last_status = resp.status_code
            saw_http_response = True
            if resp.status_code in (200, 206):
                set_probe_result(cctv, True, reason='ok', status_code=resp.status_code, url=url, content_type=resp.headers.get('Content-Type'))
                log(f'[OK] Daejeon {stream_id} is UP (Offset {offset}m)')
                return True
            log(f'[FAIL] Daejeon {stream_id} (Offset {offset}m) returned {resp.status_code}')
        except requests.Timeout as error:
            set_probe_result(cctv, False, reason='timeout', category='timeout', url=url, detail=error)
            log(f'[ERR] Daejeon {stream_id} timed out: {error}')
        except Exception as error:
            set_probe_result(cctv, False, reason='request_error', category='network_error', url=url, detail=error)
            log(f'[ERR] Daejeon {stream_id} check failed: {error}')

    if not saw_http_response:
        # Daejeon traffic-center MP4 is fetched directly by the user's browser.
        # Oracle egress to tportal can time out even while browser playback works,
        # so do not mark the whole region down from monitor-path timeouts alone.
        set_probe_result(
            cctv,
            True,
            reason='monitor_path_timeout_browser_direct_priority',
            category='monitor_path_unverified',
            url=last_url
        )
        log(f'[WARN] Daejeon {stream_id} monitor path timed out; assuming browser-direct path is usable')
        return True

    set_probe_result(
        cctv,
        False,
        reason='recent_mp4_not_found',
        category='segment_missing',
        status_code=last_status,
        url=last_url
    )
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
            set_probe_result(cctv, True, reason='token_redirect_ok', status_code=resp.status_code, url=proxy_url, content_type=resp.headers.get('Content-Type'))
            log(f"[OK] Jeju {cctv.get('id')} token redirect is UP")
            return True
        content_type = resp.headers.get('Content-Type', '').lower()
        if resp.status_code == 200 and ('mpegurl' in content_type or resp.raw.read(8, decode_content=True).startswith(b'#EXTM3U')):
            set_probe_result(cctv, True, reason='ok', status_code=resp.status_code, url=proxy_url, content_type=content_type)
            log(f"[OK] Jeju {cctv.get('id')} is UP")
            return True
        set_probe_result(
            cctv,
            False,
            reason='jeju_token_or_manifest_failed',
            category='token_or_manifest',
            status_code=resp.status_code,
            url=proxy_url,
            content_type=content_type
        )
        log(f"[FAIL] Jeju {cctv.get('id')} returned {resp.status_code} {content_type}")
        return False
    except requests.Timeout as error:
        set_probe_result(cctv, False, reason='timeout', category='timeout', url=proxy_url, detail=error)
        log(f"[ERR] Jeju {cctv.get('id')} timed out: {error}")
        return False
    except Exception as error:
        set_probe_result(cctv, False, reason='request_error', category='network_error', url=proxy_url, detail=error)
        log(f"[ERR] Jeju {cctv.get('id')} check failed: {error}")
        return False


def check_paju_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url')
    if not url:
        set_probe_result(cctv, False, reason='missing_url', category='data_error')
        return False

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS, stream=True)
        if resp.status_code in (200, 302):
            set_probe_result(cctv, True, reason='ok', status_code=resp.status_code, url=url, content_type=resp.headers.get('Content-Type'))
            log(f"[OK] Paju {cctv.get('id')} is UP")
            return True
        set_probe_result(cctv, False, reason='http_error', category='http_error', status_code=resp.status_code, url=url, content_type=resp.headers.get('Content-Type'))
        log(f"[FAIL] Paju {cctv.get('id')} returned {resp.status_code}")
    except requests.Timeout as error:
        set_probe_result(cctv, False, reason='timeout', category='timeout', url=url, detail=error)
        log(f"[ERR] Paju {cctv.get('id')} timed out: {error}")
    except Exception as error:
        set_probe_result(cctv, False, reason='request_error', category='network_error', url=url, detail=error)
        log(f"[ERR] Paju {cctv.get('id')} check failed: {error}")
    return False


def check_gits_stream(cctv):
    stream_id = cctv.get('original_id') or str(cctv.get('id', '')).replace('GITS_', '')
    if not stream_id:
        set_probe_result(cctv, False, reason='missing_gits_id', category='data_error')
        return False

    url = f'{ORACLE_BASE}/gits?cctvip={quote(str(stream_id))}'
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            verify=False,
            headers=HEADERS,
            allow_redirects=False,
            stream=True
        )
        location = resp.headers.get('Location', '')
        content_type = resp.headers.get('Content-Type', '').lower()
        if resp.status_code in (301, 302, 303, 307, 308) and location:
            set_probe_result(cctv, True, reason='resolver_redirect_ok', status_code=resp.status_code, url=url, content_type=content_type)
            log(f"[OK] GiTS {cctv.get('id')} resolver is UP")
            return True
        if resp.status_code == 200:
            body = resp.raw.read(128, decode_content=True).decode('utf-8', errors='ignore').strip()
            if body.startswith('http') or body.startswith('#EXTM3U'):
                set_probe_result(cctv, True, reason='resolver_body_ok', status_code=resp.status_code, url=url, content_type=content_type)
                log(f"[OK] GiTS {cctv.get('id')} resolver body is UP")
                return True
        base_category = 'not_found' if resp.status_code == 404 else ('auth_or_token' if resp.status_code in (401, 403) else 'token_or_manifest')
        category = get_source_specific_failure_category(cctv, base_category, resp.status_code)
        set_probe_result(cctv, False, reason='gits_resolver_failed', category=category, status_code=resp.status_code, url=url, content_type=content_type)
        log(f"[FAIL] GiTS {cctv.get('id')} resolver returned {resp.status_code}")
    except requests.Timeout as error:
        set_probe_result(cctv, False, reason='timeout', category=get_source_specific_failure_category(cctv, 'timeout'), url=url, detail=error)
        log(f"[ERR] GiTS {cctv.get('id')} timed out: {error}")
    except Exception as error:
        set_probe_result(cctv, False, reason='request_error', category=get_source_specific_failure_category(cctv, 'network_error'), url=url, detail=error)
        log(f"[ERR] GiTS {cctv.get('id')} check failed: {error}")
    return False


def check_generic_stream(cctv):
    url = cctv.get('directUrl') or cctv.get('url')
    if not url:
        set_probe_result(cctv, False, reason='missing_url', category='data_error')
        return False

    if url.startswith('gangneung_player.html') or 'popup' in url:
        set_probe_result(cctv, False, reason='iframe_only_source', category='frame_only', url=url)
        return False

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
    elif source == 'UTIC' and 'openDataCctvStream.jsp' in url:
        query = urlparse(url).query
        url = f'{ORACLE_BASE}/utic?{query}'

    if source in ['NOWJEJU', 'TRENDWORLD']:
        url = f'{ORACLE_BASE}/proxy?url={requests.utils.quote(url)}'

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, verify=False, headers=HEADERS, stream=True)
        content_type = resp.headers.get('Content-Type', '').lower()
        if resp.status_code < 400 or (resp.status_code == 404 and 'mpegurl' in content_type):
            if 'text/html' in content_type and source not in ['YOUTUBE', 'YT_CUSTOM']:
                set_probe_result(cctv, False, reason='html_not_direct_video', category='frame_or_bad_content', status_code=resp.status_code, url=url, content_type=content_type)
                log(f"[FAIL] {cctv.get('id')} returned HTML instead of a direct stream")
                return False
            set_probe_result(cctv, True, reason='ok', status_code=resp.status_code, url=url, content_type=content_type)
            log(f"[OK] {cctv.get('id')} is UP")
            return True
        base_category = 'not_found' if resp.status_code == 404 else ('auth_or_token' if resp.status_code in (401, 403) else 'http_error')
        category = get_source_specific_failure_category(cctv, base_category, resp.status_code)
        set_probe_result(cctv, False, reason='http_error', category=category, status_code=resp.status_code, url=url, content_type=content_type)
        log(f"[FAIL] {cctv.get('id')} returned {resp.status_code}")
    except requests.Timeout as error:
        set_probe_result(cctv, False, reason='timeout', category=get_source_specific_failure_category(cctv, 'timeout'), url=url, detail=error)
        log(f"[ERR] {cctv.get('id')} timed out: {error}")
    except Exception as error:
        set_probe_result(cctv, False, reason='request_error', category=get_source_specific_failure_category(cctv, 'network_error'), url=url, detail=error)
        log(f"[ERR] {cctv.get('id')} check failed: {error}")
    return False


def check_camera(region_name, cctv):
    if region_name == 'DAEJEON' and is_daejeon_mp4_candidate(cctv):
        return check_daejeon_stream(cctv)
    if region_name == 'JEJU':
        return check_jeju_stream(cctv)
    if region_name == 'PAJU':
        return check_paju_stream(cctv)
    if cctv.get('source') == 'GITS':
        return check_gits_stream(cctv)
    if is_unsupported_browser_stream(cctv):
        log(f"[UNSUPPORTED] {cctv.get('id')} uses a legacy UTIC browser plugin stream")
        set_probe_result(cctv, False, reason='unsupported_legacy_player', category='unsupported_legacy')
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


def build_failed_sample(region_name, cctv):
    probe = get_probe_result(cctv)
    url = probe.get('url') or cctv.get('directUrl') or cctv.get('url')
    return {
        'id': cctv.get('id'),
        'name': cctv.get('name'),
        'region': region_name,
        'source': cctv.get('source'),
        'reason': probe.get('reason') or 'unknown',
        'category': probe.get('category') or 'unknown',
        'status_code': probe.get('status_code'),
        'content_type': probe.get('content_type'),
        'url': url,
        'detail': probe.get('detail'),
        'checked_at': probe.get('checked_at') or utc_timestamp()
    }


def classify_failure(sample):
    category = sample.get('category') or 'unknown'
    status_code = sample.get('status_code')
    source = sample.get('source') or 'UNKNOWN'
    region = sample.get('region') or 'UNKNOWN'

    if category == 'gits_source_missing':
        return {
            'likely_cause': 'GITS 팝업에서 HLS 토큰 또는 videoUrl이 더 이상 노출되지 않음',
            'recommended_action': 'GITS 지도 데이터 수집 경로와 cctvId/routeId/svcLinkId 조합을 재수집하고, 복구 전까지 경기 ITS 카메라를 추천 하위로 격리'
        }
    if category == 'gits_token_or_auth':
        return {
            'likely_cause': 'GITS 토큰 발급 또는 접근 권한 정책 변경',
            'recommended_action': 'Referer/session/cookie가 필요한지 확인하고 토큰 리졸버를 갱신'
        }
    if category == 'z3_resolver_timeout':
        return {
            'likely_cause': 'UTIC 국도(Z3) 토큰 리졸버 또는 cctvsec.ktict.co.kr 응답 지연',
            'recommended_action': 'z3_cache 최신성, its.go.kr 직접 갱신 가능 여부, Oracle 서버에서 cctvsec 연결 지연 여부를 확인'
        }
    if category == 'z3_stream_missing':
        return {
            'likely_cause': 'UTIC 국도(Z3) cctvip가 최신 its.go.kr appUrl 캐시에 없거나 원본 경로가 변경됨',
            'recommended_action': 'data/z3_cache.json을 갱신하고 해당 cctvip가 최신 지도 API에 존재하는지 재확인'
        }
    if category == 'z3_token_or_manifest':
        return {
            'likely_cause': 'UTIC 국도(Z3) 토큰 만료 또는 HLS manifest 발급 실패',
            'recommended_action': 'its.go.kr 세션 기반 appUrl 재발급 후 !hls 응답을 재검증'
        }
    if category == 'z3_resolver_error':
        return {
            'likely_cause': 'UTIC 국도(Z3) Oracle 리졸버 또는 원본 프록시 응답 오류',
            'recommended_action': 'Oracle /utic 로그의 Z3 오류 상태와 원본 HTTP 상태를 함께 확인'
        }
    if category == 'ntic_resolver_timeout':
        return {
            'likely_cause': '고속도로/NTIC 원본 또는 Oracle 프록시 경로 응답 지연',
            'recommended_action': '같은 URL을 서버와 브라우저에서 교차 확인하고, 반복 지연 카메라는 추천 하위로 격리'
        }
    if category == 'ntic_stream_missing':
        return {
            'likely_cause': '고속도로/NTIC 카메라 ID 또는 스트림 경로 변경',
            'recommended_action': 'NTIC 수집기 원본 목록을 갱신하고 해당 카메라 ID를 재매핑'
        }
    if category == 'ntic_resolver_error':
        return {
            'likely_cause': '고속도로/NTIC 리졸버 또는 원본 서버 HTTP 오류',
            'recommended_action': 'Oracle /utic 응답 코드와 원본 manifest 응답을 분리해서 확인'
        }

    if category == 'frame_only':
        return {
            'likely_cause': '원본 제공처가 팝업/iframe 전용 플레이어만 제공',
            'recommended_action': '직접 HLS/MP4 주소 추출기를 추가하거나 프레임 없는 대체 카메라를 우선 추천'
        }
    if category == 'unsupported_legacy':
        return {
            'likely_cause': '구형 UTIC 전용 플레이어 기반 스트림',
            'recommended_action': '브라우저 재생 가능한 대체 소스 매핑 또는 해당 카메라 노출순위 하향'
        }
    if category in ('auth_or_token', 'token_or_manifest') or status_code in (401, 403):
        return {
            'likely_cause': '토큰 만료, 권한 오류 또는 원본 제공처 인증 정책 변경',
            'recommended_action': '토큰 재발급 경로와 리졸버 응답을 확인하고 최신 토큰 캐시를 갱신'
        }
    if category == 'segment_missing' or status_code == 404:
        return {
            'likely_cause': '최근 영상 조각이 아직 발행되지 않았거나 카메라 ID/경로가 변경됨',
            'recommended_action': '최근 10분 범위의 세그먼트 존재 여부와 카메라 ID/서버 경로를 재검증'
        }
    if category == 'timeout':
        return {
            'likely_cause': '원본 서버 응답 지연 또는 네트워크 경로 지연',
            'recommended_action': '타임아웃 재시도 간격, 지역별 대체 소스, 프록시 위치를 점검'
        }
    if category == 'frame_or_bad_content':
        return {
            'likely_cause': '직접 영상 대신 HTML/플레이어 페이지가 반환됨',
            'recommended_action': '실제 video/hls/mp4 URL 추출 로직을 추가하거나 해당 소스를 frame-only로 분류'
        }
    if category == 'data_error':
        return {
            'likely_cause': '수집 데이터의 URL 또는 스트림 ID 누락',
            'recommended_action': '수집기 원본 필드와 정규화 규칙을 확인'
        }
    if category == 'network_error':
        return {
            'likely_cause': '점검 서버에서 원본 제공처까지의 네트워크 오류',
            'recommended_action': '동일 URL을 브라우저/프록시/점검 서버에서 교차 확인'
        }

    return {
        'likely_cause': f'{region}/{source} 원본 스트림 응답 실패',
        'recommended_action': 'HTTP 상태, 콘텐츠 타입, 브라우저 재생 결과를 함께 확인'
    }


def is_retired_daejeon_hls_data_error(entry):
    """Drop old false positives from before Daejeon HLS was checked generically."""
    if not isinstance(entry, dict):
        return False
    last_url = entry.get('last_url') or ''
    return (
        entry.get('region') == 'DAEJEON'
        and entry.get('source') == 'UTIC'
        and entry.get('last_reason') == 'missing_daejeon_stream_id'
        and entry.get('last_category') == 'data_error'
        and 'cctvlo.geumriver.go.kr' in last_url
    )


def update_camera_failure_registry(current_status, region_name, result):
    registry = current_status.get('camera_failures')
    if not isinstance(registry, dict):
        registry = {}
        current_status['camera_failures'] = registry
    now_iso = utc_timestamp()
    passed_ids = set(result.get('passed_ids') or [])
    failed_samples = result.get('failed_samples') or []

    for camera_id, entry in list(registry.items()):
        if is_retired_daejeon_hls_data_error(entry):
            registry.pop(camera_id, None)

    for camera_id in passed_ids:
        registry.pop(camera_id, None)

    for sample in failed_samples:
        camera_id = sample.get('id')
        if not camera_id:
            continue

        previous = registry.get(camera_id, {})
        first_failed_at = previous.get('first_failed_at') or now_iso
        failed_for_minutes = minutes_between(first_failed_at, now_iso)
        failure_count = int(previous.get('failure_count') or 0) + 1
        diagnosis = classify_failure(sample)

        if failed_for_minutes >= EMERGENCY_CRITICAL_AFTER_MINUTES or failure_count >= 4:
            emergency_level = 'critical'
        elif failed_for_minutes >= EMERGENCY_INVESTIGATE_AFTER_MINUTES or failure_count >= 2:
            emergency_level = 'investigate'
        else:
            emergency_level = 'watch'

        registry[camera_id] = {
            'id': camera_id,
            'name': sample.get('name'),
            'region': region_name,
            'source': sample.get('source'),
            'first_failed_at': first_failed_at,
            'last_failed_at': now_iso,
            'failed_for_minutes': failed_for_minutes,
            'failure_count': failure_count,
            'emergency_level': emergency_level,
            'last_reason': sample.get('reason'),
            'last_category': sample.get('category'),
            'last_status_code': sample.get('status_code'),
            'last_content_type': sample.get('content_type'),
            'last_url': sample.get('url'),
            'last_checked_at': sample.get('checked_at') or now_iso,
            'diagnosis': diagnosis
        }

        if emergency_level in ('investigate', 'critical'):
            log(
                f"[EMERGENCY:{emergency_level}] {region_name} {camera_id} "
                f"failed_for={failed_for_minutes}m count={failure_count} cause={diagnosis['likely_cause']}"
            )

    if len(registry) > CAMERA_FAILURE_REGISTRY_LIMIT:
        ordered = sorted(
            registry.items(),
            key=lambda item: item[1].get('last_failed_at') or '',
            reverse=True
        )
        current_status['camera_failures'] = dict(ordered[:CAMERA_FAILURE_REGISTRY_LIMIT])


def summarize_failed_samples(failed_samples):
    breakdown = {}
    for sample in failed_samples:
        category = sample.get('category') or 'unknown'
        entry = breakdown.setdefault(category, {
            'category': category,
            'count': 0,
            'sample_ids': [],
            'likely_cause': None,
            'recommended_action': None
        })
        entry['count'] += 1
        if sample.get('id') and len(entry['sample_ids']) < 5:
            entry['sample_ids'].append(sample.get('id'))
        if not entry['likely_cause']:
            diagnosis = classify_failure(sample)
            entry['likely_cause'] = diagnosis.get('likely_cause')
            entry['recommended_action'] = diagnosis.get('recommended_action')

    ordered = sorted(breakdown.values(), key=lambda item: item['count'], reverse=True)
    return {
        'categories': ordered,
        'dominant': ordered[0] if ordered else None
    }


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
            'passed_ids': [],
            'failed_samples': [],
            'failure_breakdown': {'categories': [], 'dominant': None},
            'sample_strategy': {
                'stable': 0,
                'exploratory': 0
            }
        }

    target_size = get_target_sample_size(len(cameras))
    sample, stable_count, exploratory_count = select_representative_cameras(region_name, cameras, target_size)
    sample_ids = [cam.get('id') for cam in sample if cam.get('id')]
    failed_ids = []
    passed_ids = []
    failed_samples = []
    passed = 0

    log(
        f'Testing {region_name} with {len(sample)} samples '
        f'(stable={stable_count}, exploratory={exploratory_count}, total_cameras={len(cameras)})'
    )

    for cam in sample:
        success = check_camera(region_name, cam)
        if success:
            passed += 1
            if cam.get('id'):
                passed_ids.append(cam.get('id'))
        else:
            failed_ids.append(cam.get('id'))
            failed_samples.append(build_failed_sample(region_name, cam))

    checked = len(sample)
    status, failure_ratio = evaluate_region_health(checked, passed)
    failed = checked - passed
    failure_breakdown = summarize_failed_samples(failed_samples)
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
        'passed_ids': passed_ids,
        'failed_samples': failed_samples,
        'failure_breakdown': failure_breakdown,
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
            update_camera_failure_registry(current_status, region_name, result)

        current_status['last_updated'] = utc_timestamp()
        save_json(STATUS_FILE, current_status)
        log('--- Sentinel Finished ---')
    except Exception as error:
        log(f'FATAL ERROR in run_sentinel: {error}')
        log(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run_sentinel()
