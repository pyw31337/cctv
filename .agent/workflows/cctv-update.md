---
description: CCTV 데이터 업데이트 시 반드시 따라야 할 규칙과 체크리스트
---

# CCTV 데이터 업데이트 워크플로우

## 우선순위

### 0순위: 직통 영상 설정 (최우선)
- 직통 HLS가 확보된 서버(211.57.45.101, 210.95.12.126, 211.114.87.164)는 **url 필드 자체를 직통 m3u8로 설정**
- iframe(utic.go.kr) 사용 금지
- `update_cctv_data.py`의 `process_utic_item()` 함수에서 처리

### 1순위: UTIC 리스트대로 영상 출력 확인
- UTIC API에서 데이터 수집 후 스트림이 실제로 재생되는지 테스트
- ID 매핑 확인: `CCTVID`와 `ID_PARAM`이 다를 수 있음
  - 예: L180075(마석사거리) → 스트림 ID는 L180111

### 2순위: 직통 영상 확보 가능성 테스트
- 새로운 CCTV IP 패턴 발견 시 직통 HLS 패턴 테스트
- 작동하면 `update_cctv_data.py`에 패턴 추가

## 검증 체크리스트

업데이트 완료 후 반드시 `validate_cctv_data.py` 실행:

```bash
// turbo
python validate_cctv_data.py
```

검증 항목:
1. 직통 HLS 서버가 url에 m3u8으로 설정되어 있는지
2. 주요 CCTV 샘플(마석사거리, 마석윗3)의 스트림 접근 가능 여부
3. iframe 방지 (utic.go.kr URL 사용 금지)

## 알려진 직통 서버 패턴

| 서버 IP | ID 패턴 | URL 패턴 |
|---------|---------|----------|
| 211.57.45.101 | L*, *_video* | `https://211.57.45.101/media/{ID}/chunklist.m3u8` |
| 210.95.12.126 | * | `http://210.95.12.126/media/{ID}/chunklist.m3u8` |
| 211.114.87.164 | * | `http://211.114.87.164/media/{ID}/chunklist.m3u8` |

## 중요 주의사항

1. **CCTVID ≠ 스트림 ID**: UTIC의 `CCTVID`는 표시용, `ID_PARAM`(item.ID)이 실제 스트림 ID
2. **데일리 업데이트 후 검증 필수**: GitHub Actions에서 자동 검증, 실패 시 커밋 차단
3. **수동 수정 금지**: 모든 수정은 `update_cctv_data.py`에 반영하여 데일리 업데이트에서도 유지
