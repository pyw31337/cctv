# CCTV Quality Operations

이 서비스의 품질 관리는 두 층으로 나눕니다.

1. 브라우저 실사용 품질
   - 사용자의 실제 재생 성공, 실패, 첫 화면 로딩 시간, 대체 소스 사용 여부를 익명 집계합니다.
   - 앱은 이 집계가 있으면 카메라, 소스, 지역 순서로 마커 색상과 추천 순위를 보정합니다.
   - `data/quality_policy.json`은 성공률, 실패율, 첫 화면 시간, 해상도, 표본 수, 최신성을 점수화합니다. 낮은 점수는 삭제하지 않고 `data/quality_repair_queue.json`으로 보내 재검증 우선순위를 높입니다.
   - 잠긴 카메라 ID/stream ID 매핑은 이 점수나 AI가 변경할 수 없습니다. 독립 검증을 통과한 후보만 승격합니다.
  - `data/catalog_playability_report.json`과 `data/catalog_playability_history.json`은 국내·세계 카탈로그의 전체 수, 엄격한 인앱 재생 가능 수, 이전 수집 대비 증감을 기록합니다.
  - 국내의 낮은 점수 항목은 삭제하지 않고 `quality_repair_queue.json`에서 재생 재검증, URL 갱신, 근거 갱신 순으로 복구합니다. 품질 대시보드의 `반복 복구 대상`에서 현재 우선순위를 확인할 수 있습니다.

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
- `category: "key_problem"` 이벤트는 API 키 문제(시크릿 미설정, 데모 키 사용, ITS HTTP 401/resultCode 4005, data.ex.co.kr `code: "ERROR"`)입니다. 대시보드에 `인증키 문제`로 표시되며, 수집기는 기존 데이터를 보존한 채 계속 동작합니다. GitHub 시크릿(`ITS_API_KEY`, `UTIC_API_KEY`)을 확인하세요.

## 상태 정의

- `점검 실패`: 자동 샘플 점검에서 실패했습니다. 실제 재생 성공 시 화면 상태가 우선입니다.
- `실사용 불안정`: 사용자 재생 데이터에서 실패율이 높습니다.
- `로딩 느림`: 재생은 되지만 첫 화면 로딩 시간이 느립니다.
- `실사용 정상`: 최근 사용자 재생 데이터가 안정적입니다.
- `상태 미확인`: 충분한 점검 또는 실사용 샘플이 없습니다.

## 로컬 AI 보조

- `python3 scripts/quality_ai_advisor.py`는 로컬 Ollama가 설치된 운영 환경에서만 실행할 수 있습니다. 모델은 집계된 품질 수치와 복구 대기열을 요약할 뿐, URL·ID·잠긴 매핑을 자동 변경하지 않습니다.
- GitHub Actions에는 로컬 모델을 실행하지 않습니다. AI 부재가 재생·수집·배포 실패로 이어지지 않게 결정적 검증 로직을 기본으로 유지합니다.

## 카탈로그 수량 기준

- 국내 `최근 인앱 재생 검증`은 최근 품질 표본 3건 이상, 성공률 80% 이상, 실패율 20% 이하인 카메라입니다. URL 모양만 직접 스트림처럼 보여도 이 기준을 통과했다고 간주하지 않습니다.
- 세계 `엄격 인앱 재생`은 현재 검증된 공개 `playUrl`, `embedUrl`, 또는 재생 가능한 YouTube ID가 있는 항목입니다. `world_tour_playability_history.json`은 카메라별 최근 96시간의 직접재생 결과를 보존합니다. 같은 항목이 5회 연속 실패하고 그 사이 성공이 한 번도 없을 때만 목록에서 제거합니다. 첫 실행부터 즉시 삭제하지 않고, 실패 항목을 다음 6시간 점검에서 우선 재검증합니다.

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
