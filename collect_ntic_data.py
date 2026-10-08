import json
import time
import urllib.error
import urllib.request
import urllib.parse
import ssl
import sys
from highway_traffic import ITS_DEMO_KEY, KeyProblemError, parse_its_cctv_response, resolve_api_key

# Configuration
ITS_API_URL = "https://openapi.its.go.kr:9443/cctvInfo"
OUTPUT_FILE = "ntic_data.json"

def collect_ntic_data_nationwide():
    """
    Collect NTIC data for entire Korea (mainland focus)
    More precise bounds to avoid sea areas
    """
    results = []
    seen_ids = set()
    its_api_key, _is_demo = resolve_api_key("ITS_API_KEY", demo_key=ITS_DEMO_KEY, label="ITS cctvInfo", log=print)
    
    # Define regions for better coverage (avoid sea)
    regions = [
        # Seoul/Gyeonggi/Incheon
        {"name": "수도권", "lat_min": 37.0, "lat_max": 38.0, "lng_min": 126.5, "lng_max": 127.5},
        # Gangwon
        {"name": "강원도", "lat_min": 37.0, "lat_max": 38.5, "lng_min": 127.5, "lng_max": 129.5},
        # Chungcheong
        {"name": "충청도", "lat_min": 36.0, "lat_max": 37.0, "lng_min": 126.5, "lng_max": 128.0},
        # Gyeongsang
        {"name": "경상도", "lat_min": 35.0, "lat_max": 37.0, "lng_min": 128.0, "lng_max": 130.0},
        # Jeolla
        {"name": "전라도", "lat_min": 34.5, "lat_max": 36.0, "lng_min": 126.0, "lng_max": 128.0},
        # Jeju
        {"name": "제주도", "lat_min": 33.0, "lat_max": 34.0, "lng_min": 126.0, "lng_max": 127.0},
    ]
    
    step = 0.1  # 0.1 degree grid
    
    # Calculate total cells
    total_cells = 0
    for r in regions:
        lat_steps = int((r["lat_max"] - r["lat_min"]) / step)
        lng_steps = int((r["lng_max"] - r["lng_min"]) / step)
        total_cells += lat_steps * lng_steps
    
    print(f"전국 NTIC 데이터 수집 시작")
    print(f"총 {total_cells}개 그리드 셀 스캔 예정 ({len(regions)}개 지역)")
    print("=" * 60)
    
    # Create SSL context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    cell_count = 0
    error_count = 0
    last_save_count = 0
    
    for region in regions:
        print(f"\n[{region['name']}] 수집 중...")
        
        lat = region["lat_min"]
        while lat < region["lat_max"]:
            lng = region["lng_min"]
            while lng < region["lng_max"]:
                cell_count += 1
                progress = (cell_count / total_cells) * 100
                
                # Progress bar
                bar_len = 40
                filled = int(bar_len * cell_count / total_cells)
                bar = '█' * filled + '░' * (bar_len - filled)
                
                sys.stdout.write(f"\r[{bar}] {progress:5.1f}% | CCTV: {len(results):,}개 | 오류: {error_count}")
                sys.stdout.flush()
                
                params = {
                    'apiKey': its_api_key,
                    'type': 'all',
                    'cctvType': '1',
                    'minX': f"{lng:.6f}",
                    'maxX': f"{lng + step:.6f}",
                    'minY': f"{lat:.6f}",
                    'maxY': f"{lat + step:.6f}",
                    'getType': 'json'
                }
                
                query_string = urllib.parse.urlencode(params)
                url = f"{ITS_API_URL}?{query_string}"
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        req = urllib.request.Request(url)
                        req.add_header('User-Agent', 'Mozilla/5.0')
                        
                        try:
                            with urllib.request.urlopen(req, context=ctx, timeout=20) as response:
                                status_code, body = response.status, response.read().decode('utf-8', 'replace')
                        except urllib.error.HTTPError as http_error:
                            status_code = http_error.code
                            body = http_error.read().decode('utf-8', 'replace')

                        # Success bodies are XML even with getType=json.
                        cctv_list = parse_its_cctv_response(body, status_code)
                        for item in cctv_list:
                            cctv_id = item.get('cctvid') or item.get('id')
                            if not cctv_id and 'cctvname' in item:
                                cctv_id = f"NTIC_{item['cctvname']}_{item.get('coordx')}"

                            if cctv_id and cctv_id not in seen_ids:
                                try:
                                    lat_val = float(item.get('coordy', 0))
                                    lng_val = float(item.get('coordx', 0))

                                    if lat_val > 0 and lng_val > 0:
                                        results.append({
                                            'id': cctv_id,
                                            'name': item.get('cctvname', 'Unknown'),
                                            'lat': lat_val,
                                            'lng': lng_val,
                                            'url': item.get('cctvurl', ''),
                                            'source': 'NTIC',
                                            'status': 'active'
                                        })
                                        seen_ids.add(cctv_id)
                                except ValueError:
                                    pass
                        break  # Success
                        
                    except KeyProblemError as e:
                        # Retrying every grid cell with a rejected key is pointless.
                        print(f"\n[ERROR] ITS 인증키 문제: {e}")
                        print("ITS_API_KEY를 확인하세요. 지금까지 수집한 결과만 저장합니다.")
                        return results
                    except Exception as e:  # includes UpstreamError (blocked, HTTP 5xx, bad body)
                        if attempt < max_retries - 1:
                            time.sleep(0.5)
                        else:
                            error_count += 1
                
                # Auto-save every 1000 new CCTVs
                if len(results) - last_save_count >= 1000:
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(results, f, ensure_ascii=False, indent=2)
                    last_save_count = len(results)
                
                time.sleep(0.08)  # Rate limiting
                lng += step
            lat += step
    
    print(f"\n\n{'='*60}")
    print(f"✅ 수집 완료!")
    print(f"   총 CCTV: {len(results):,}개")
    print(f"   오류: {error_count}건")
    print(f"{'='*60}")
    
    return results

def main():
    results = collect_ntic_data_nationwide()

    if not results:
        # Do not clobber the previous snapshot with an empty list when the key
        # was rejected or the API was unreachable.
        print(f"\n수집 결과가 없어 기존 {OUTPUT_FILE}을(를) 유지합니다.")
        return 1

    print(f"\n{OUTPUT_FILE}에 저장 중...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("✅ 저장 완료!")
    return 0

if __name__ == '__main__':
    sys.exit(main())
