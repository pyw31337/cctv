# CCTV Quality Operations Playbook

## 운영 원칙

- 카메라 목록은 보존한다. 일시 장애, 토큰 만료, 공급처 장애가 있어도 `cctv_data.json`에서 삭제하지 않는다.
- 헬스체크, 카나리, 실사용 텔레메트리는 삭제가 아니라 추천 순위와 상태 표시를 조정하는 신호로만 사용한다.
- 녹색 상태는 카메라 단위 실사용 성공 또는 핵심 카나리 성공처럼 직접 재생 근거가 있을 때만 강하게 표시한다.
- Z3 캐시가 8시간을 넘으면 단순 경고가 아니라 운영 장애로 보고 Z3 후보를 강하게 후순위 처리한다.

## 핵심 카나리 지역

다음 지역은 서비스 신뢰도 체감에 직접 영향을 주는 핵심 카나리다.

- 진도
- 제주
- 대전
- 구리
- 남양주
- 독도

Oracle/local `server_quality_cron.sh`는 15분 기본 주기로 카나리를 실행하며 `/canary-status`, `/ops-status`에서 즉시 제공한다.
`Core Canary Playback Probe` GitHub Actions 워크플로우는 3시간마다 실행되어 GitHub Pages 정적 백업용 `data/canary_status.json`과 `data/ops_status.json`을 갱신한다.
각 핵심 지역은 단일 카메라가 아니라 넓은 후보군을 점검한다. 진도/제주는 더 많은 후보를 확인해 특정 공급처 장애가 전체 지역 장애처럼 보이지 않도록 한다.

## GitHub Actions 실패 분류

Actions 실패 메일은 두 종류로 나누어 본다.

- 워크플로우/프로세스 실패: 스크립트 오류, 의존성 설치 실패, 커밋/푸시 충돌, 데이터 보존 검증 실패. GitHub 메일의 `Run failed`는 이 경우에만 발생해야 한다.
- 서비스 영향 데이터: 외부 CCTV 공급처 장애, 토큰 만료, 카나리 실패. 이 경우 워크플로우는 성공으로 끝내고 `ops_status.json`에 `SERVICE_IMPACT`로 기록한다.
- 보존형 수집 실패: GITS ingest, UTIC audit/resurrect, URL renew가 실패했지만 기존 목록을 복원할 수 있는 경우다. 이 경우 워크플로우는 `data/workflow_status.json`에 경고 이벤트를 남기고 기존 데이터를 유지한다.

## 관리자 대시보드 확인 항목

운영 대시보드는 `https://pyw31337.github.io/cctv/quality.html` 이다. 로컬에서는 `quality.html`을 직접 열어도 같은 정적 fallback을 확인할 수 있다.

`quality.html`에서 다음을 우선 확인한다.

- 운영 영향 상태
- Z3 캐시 최신성
- 토큰/URL 갱신 상태
- 핵심 카나리 지역별 성공률
- 최근 자동 복구 수
- 실사용 텔레메트리 기준 실패율과 로딩 속도
- 데이터 최신성: `time.schema = cctv-quality-time-v1` 기준으로 모든 품질 JSON의 원본 갱신 시각과 표준화 시각을 비교한다.
- GitHub 워크플로우 알림: 실패 메일 대신 기록된 보존형 경고를 확인한다.

## 대응 기준

- `Z3 age > 8h`: Z3 캐시 갱신 워크플로우와 Oracle 리졸버를 먼저 확인한다.
- 카나리 `SERVICE_IMPACT`: 해당 지역의 실패 원인을 `auth_or_token`, `timeout`, `not_found`, `html_or_frame`로 나누어 본다.
- `auth_or_token`: 토큰/서명 URL 재발급 루틴을 우선 확인한다.
- `timeout`: 공급처 또는 Oracle 프록시 응답 지연이다. 대체 소스를 우선 노출하고 재시도한다.
- `not_found`: URL 구조 또는 카메라 ID 변경 가능성이 높다. 수집/복구 스크립트가 새 후보를 찾아야 한다.
- 실사용 성공이 새로 쌓이면 서버 점검 실패보다 실제 재생 성공을 우선 반영한다.

## 2026-05-22 카나리 운영 보강

- Oracle 서버가 운영 1차 경로입니다. `/canary-status`, `/ops-status`, `/canary-history`가 90초 캐시로 공개됩니다.
- GitHub Actions 카나리는 정적 fallback 갱신용으로 3시간마다만 실행합니다. 분 단위 품질 유지 책임은 Oracle/local cron이 맡습니다.
- 대전/독도처럼 공급처 timeout, 404, 토큰 만료가 섞이는 지역은 카메라를 삭제하지 않고 `recovery_plan`에 원인을 기록한 뒤 추천 순위만 낮춥니다.
- `data/canary_history.json`은 최근 288회 카나리 요약을 보존해서 관리자 대시보드의 지역별 추세 막대로 표시합니다.
- 실제 브라우저 재생 카나리는 비용 보호를 위해 수동 워크플로우 `Manual Browser Playback Canary`로 운영합니다. 반복 민원이나 공급처 변경 의심 시 실행합니다.

## 원본 사이트 전용 영상 정책

- 원본 사이트에서만 안정적으로 볼 수 있는 글로벌/관광 CCTV는 삭제하지 않는다.
- 앱은 원본 사이트 전용 영상을 필터링할 수 있게 유지하고, 기본 추천에서는 직접 재생 가능한 영상보다 낮게 둔다.
- 원본 전용 여부는 품질 신호이지 삭제 사유가 아니다.
