#!/usr/bin/env python3
"""
CCTV 데이터 자동 검증 스크립트
데일리 업데이트 후 실행하여 올바른 설정 확인

검증 항목:
1. 직통 HLS 서버가 url에 m3u8로 설정되어 있는지
2. 주요 CCTV 샘플의 스트림이 실제로 접근 가능한지
"""

import json
import sys
import requests
import urllib3

urllib3.disable_warnings()

# 직통 HLS를 사용해야 하는 서버 목록
DIRECT_HLS_SERVERS = ["211.57.45.101", "210.95.12.126", "211.114.87.164"]

# 반드시 검증해야 하는 주요 CCTV 샘플
CRITICAL_SAMPLES = [
    {"name": "마석사거리", "expected_pattern": "211.57.45.101/media/L"},
    {"name": "마석윗3", "expected_pattern": "211.57.45.101/media/L"},
    {"name": "창현A앞", "expected_pattern": "211.57.45.101/media/L"},
]


def load_cctv_data():
    with open("cctv_data.json", "r", encoding="utf-8") as f:
        return json.load(f)


def validate_direct_hls_urls(data):
    """직통 HLS 서버가 url에 m3u8로 설정되어 있는지 확인"""
    errors = []
    
    for item in data:
        url = item.get("url", "")
        name = item.get("name", "")
        
        # 직통 HLS 서버인 경우 url이 m3u8이어야 함
        for server in DIRECT_HLS_SERVERS:
            if server in url:
                if not url.endswith(".m3u8"):
                    errors.append(f"[ERROR] {name}: {server} 서버인데 url이 m3u8이 아님: {url[:60]}...")
                break
    
    return errors


def validate_critical_samples(data):
    """주요 CCTV 샘플이 올바르게 설정되어 있는지 확인"""
    errors = []
    
    for sample in CRITICAL_SAMPLES:
        found = False
        for item in data:
            if sample["name"] in item.get("name", ""):
                found = True
                url = item.get("url", "")
                
                # 예상 패턴 확인
                if sample["expected_pattern"] not in url:
                    errors.append(f"[ERROR] {item['name']}: 예상 패턴 '{sample['expected_pattern']}' 없음. 실제 URL: {url[:80]}...")
                
                # 스트림 접근 테스트
                if url.endswith(".m3u8"):
                    try:
                        resp = requests.get(url, timeout=5, verify=False, stream=True)
                        if resp.status_code != 200:
                            errors.append(f"[ERROR] {item['name']}: 스트림 접근 실패 (HTTP {resp.status_code})")
                    except Exception as e:
                        errors.append(f"[ERROR] {item['name']}: 스트림 접근 실패 ({str(e)[:30]})")
                break
        
        if not found:
            errors.append(f"[ERROR] '{sample['name']}' CCTV를 찾을 수 없음")
    
    return errors


def validate_no_iframe_for_direct_servers(data):
    """직통 서버 CCTV가 utic.go.kr URL을 사용하지 않는지 확인 (iframe 방지)"""
    errors = []
    warnings = []
    
    # 직통 서버 IP를 사용하는 CCTV 찾기 (UTIC 원본 데이터 기준)
    direct_server_count = 0
    utic_fallback_count = 0
    
    for item in data:
        url = item.get("url", "")
        name = item.get("name", "")
        
        # 직통 HLS 서버 패턴이 있어야 하는데 utic.go.kr을 사용하는 경우
        for server in DIRECT_HLS_SERVERS:
            if server in url:
                direct_server_count += 1
                if "utic.go.kr" in url:
                    utic_fallback_count += 1
                    errors.append(f"[ERROR] {name}: 직통 서버 IP가 URL에 있지만 utic.go.kr 사용 (iframe으로 재생됨)")
    
    print(f"[INFO] 직통 HLS 서버 CCTV: {direct_server_count}개")
    if utic_fallback_count > 0:
        print(f"[WARN] utic.go.kr 폴백 사용 중: {utic_fallback_count}개")
    
    return errors


def main():
    print("=" * 60)
    print("CCTV 데이터 자동 검증 시작")
    print("=" * 60)
    
    data = load_cctv_data()
    print(f"[INFO] 총 CCTV: {len(data)}개")
    
    all_errors = []
    
    # 1. 직통 HLS URL 검증
    print("\n[1] 직통 HLS URL 검증...")
    errors = validate_direct_hls_urls(data)
    all_errors.extend(errors)
    if not errors:
        print("    ✅ 통과")
    else:
        for e in errors[:5]:
            print(f"    {e}")
        if len(errors) > 5:
            print(f"    ... 외 {len(errors) - 5}개")
    
    # 2. 주요 CCTV 샘플 검증
    print("\n[2] 주요 CCTV 샘플 검증...")
    errors = validate_critical_samples(data)
    all_errors.extend(errors)
    if not errors:
        print("    ✅ 통과")
    else:
        for e in errors:
            print(f"    {e}")
    
    # 3. iframe 방지 검증
    print("\n[3] iframe 방지 검증...")
    errors = validate_no_iframe_for_direct_servers(data)
    all_errors.extend(errors)
    if not errors:
        print("    ✅ 통과")
    else:
        for e in errors[:5]:
            print(f"    {e}")
    
    print("\n" + "=" * 60)
    if all_errors:
        print(f"❌ 검증 실패: {len(all_errors)}개 오류 발견")
        sys.exit(1)
    else:
        print("✅ 모든 검증 통과")
        sys.exit(0)


if __name__ == "__main__":
    main()
