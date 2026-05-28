# CCTV Quality Operations

이 서비스의 품질 관리는 두 층으로 나눕니다.

1. 브라우저 실사용 품질
   - 사용자의 실제 재생 성공, 실패, 첫 화면 로딩 시간, 대체 소스 사용 여부를 익명 집계합니다.
   - 앱은 이 집계가 있으면 카메라, 소스, 지역 순서로 마커 색상과 추천 순위를 보정합니다.

2. 서버 샘플 점검
   - Oracle 무료 서버가 `scripts/sentinel.py`를 주기적으로 실행합니다.
   - 결과는 서버의 `data/status.json`에 저장되고 `/health-status`에서 즉시 제공합니다.
   - GitHub Pages 정적 `data/status.json`은 백업 용도입니다.

3. 핵심 카나리 점검
   - Oracle 무료 서버가 `scripts/canary_probe.py`를 주기적으로 실행합니다.
   - 진도, 제주, 대전, 구리, 남양주, 독도를 핵심 카나리로 별도 확인합니다.
   - 결과는 `/canary-status`, `/ops-status`에서 즉시 제공하고, GitHub Pages 정적 JSON은 백업 용도입니다.
   - GitHub Actions 카나리는 Actions minutes 절감을 위해 3시간마다 정적 백업 스냅샷만 갱신합니다.
   - 핵심 지역은 후보 수를 넓혀 점검합니다. 일부 카메라가 죽어도 인접한 재생 가능 후보를 찾는 것이 목표입니다.

4. 장기 장애 비상 진단
   - 샘플 점검에서 실패한 카메라는 `camera_failures`에 누적합니다.
   - 같은 카메라가 1시간 이상 또는 2회 이상 실패하면 `investigate`로 분류합니다.
   - 2시간 이상 또는 4회 이상 실패하면 `critical`로 분류합니다.
   - 원인 후보는 HTTP 상태, 콘텐츠 타입, 타임아웃, 토큰/권한 오류, 최근 MP4 세그먼트 부재, iframe 전용 소스 여부를 기준으로 남깁니다.

## Oracle Cron

서버에서 다음 cron을 등록합니다.

```cron
*/15 * * * * CCTV_ROOT=/home/ubuntu/cctv /home/ubuntu/cctv/scripts/server_quality_cron.sh
```

이 방식은 GitHub Actions의 시간 사용량을 줄이면서도 앱이 더 최신 점검 정보를 읽게 해줍니다.

## 관리자 대시보드

- URL: `https://pyw31337.github.io/cctv/quality.html`
- `data/status.json`, `data/quality_summary.json`, `data/z3_cache.json`, `data/cache_status.json`, `data/canary_status.json`, `data/ops_status.json`은 공통 `time.schema = cctv-quality-time-v1` 블록을 유지합니다.
- 대시보드의 `데이터 최신성`은 원본 점검 시각과 표준화 시각을 분리해 보여줍니다.
- 대시보드의 `GitHub 워크플로우 알림`은 기존 데이터가 보존된 보존형 실패를 `data/workflow_status.json`에서 보여줍니다.

## 상태 정의

- `점검 실패`: 자동 샘플 점검에서 실패했습니다. 실제 재생 성공 시 화면 상태가 우선입니다.
- `실사용 불안정`: 사용자 재생 데이터에서 실패율이 높습니다.
- `로딩 느림`: 재생은 되지만 첫 화면 로딩 시간이 느립니다.
- `실사용 정상`: 최근 사용자 재생 데이터가 안정적입니다.
- `상태 미확인`: 충분한 점검 또는 실사용 샘플이 없습니다.

## 정렬 기준

- `추천순`: 거리, 안정성, 화질, 실사용 품질을 종합합니다.
- `가까운순`: 가까운 CCTV를 우선합니다.
- `시내우선`: 시청, 역, 사거리, 시장, 학교 등 생활권/시내 맥락을 우선합니다.
- `교통우선`: UTIC, NTIC, 국도, IC, 고속도로, 자동차전용도로, 터널, 램프를 우선합니다.
- `안정우선`: 실패율과 느린 로딩을 가장 강하게 피합니다.
- `화질우선`: 영상 품질과 실사용 로딩 성능을 더 크게 반영합니다.

## 재생 원칙

- 최우선은 iframe이 아닌 `<video>` 기반 직접 HLS/MP4 재생입니다.
- UTIC 계열은 원본 페이지 iframe으로 되돌아가기 전에 프레임 없는 대체 소스를 먼저 시도합니다.
- 팝업/iframe 전용 소스는 점검에서 `frame_only`로 기록하고 추천 순위를 낮춥니다.
- 원본 사이트에서만 안정적으로 재생되는 글로벌/관광 영상은 유지합니다. 다만 필터로 구분하고 직접 재생 영상보다 낮은 우선순위로 둡니다.
