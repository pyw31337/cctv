# CCTV Project - Agent Handoff & Architecture Guide
> **필독 (MUST READ)**: 이 프로젝트에서 작업을 수행하는 모든 AI 에이전트(Claude, Codex, Antigravity, Cursor 등)는 작업 시작 전 반드시 이 문서를 숙지해야 합니다. 본 저장소의 모든 코드는 서비스 연속성과 데이터 보존을 최우선으로 설계되어 있습니다.

---

## 1. 프로젝트 개요 및 아키텍처

- **목적**: 전국 공공 교통 CCTV(경찰청 UTIC, 경기도 GITS, 한국도로공사, 지자체, KBS 등)를 지도/검색 기반 4분할 격자 및 단일 뷰어로 실시간 스트리밍 제공
- **프론트엔드**: Vanilla JS ([js/app.js](file:///Users/pyw31337/Developer/cctv/js/app.js)), HLS.js, Kakao Maps API, PWA Service Worker ([sw.js](file:///Users/pyw31337/Developer/cctv/sw.js))
- **데이터 파이프라인**:
  - [cctv_data.json](file:///Users/pyw31337/Developer/cctv/cctv_data.json): 전체 18,000+ CCTV 메타데이터
  - [data/cctv_core.json](file:///Users/pyw31337/Developer/cctv/data/cctv_core.json): 브라우저 초기 로딩 최적화용 경량 데이터셋
  - [data/cctv_extended.json](file:///Users/pyw31337/Developer/cctv/data/cctv_extended.json): 부가 상세 데이터
- **스트림 프록시 아키텍처**:
  - 경기도 GITS: `https://cctv-proxy-hoon-001.fly.dev/gits?cctvip=<originalId>`
    - GITS 스트림은 2시간 만료 토큰(`validminutes=120`)을 사용하므로, 클라이언트가 시청 시 동적 프록시를 통해 즉시 발급받아 스트리밍합니다.
  - 경찰청 UTIC / 기타: `https://cctv-proxy.pyw213.workers.dev`

---

## 2. 핵심 불변 원칙 (Core Rules & Invariants)

어느 에이전트가 어떤 작업을 하더라도 **다음 원칙을 절대로 위반해서는 안 됩니다**:

### ① 깃 충돌 및 에러 방지 규칙
- 로컬 깃 설정은 항상 `pull.rebase true` 및 `rebase.autoStash true`를 유지합니다.
- 동적 JSON 데이터 파일([cctv_data.json](file:///Users/pyw31337/Developer/cctv/cctv_data.json), `status.json` 등)의 노이즈 diff 방지를 위해 [.gitattributes](file:///Users/pyw31337/Developer/cctv/.gitattributes) 병합 정책을 존중합니다.
- 파이프라인 데이터 변경 시 반드시 [scripts/guard_data_preservation.py](file:///Users/pyw31337/Developer/cctv/scripts/guard_data_preservation.py)를 실행하여 골든 카메라, 별칭(alias), split 동기화를 검증합니다.

### ② 데이터 보존 및 골든 카메라 규칙
- 어떠한 상황에서도 기존 정상 카메라를 무차별 삭제하거나 `manual_check`/`disabled`로 대량 강등시키지 않습니다.
- 골든 카메라(`L180075`, `L180206`, `E600016` 등)는 테스트 및 서비스의 기준점이므로 임의 변경을 금지합니다.
- 점검 중(`manual_check`)인 카메라도 지도 마커에서는 유지되어야 합니다.

### ③ 재생 안정성 및 장애 대체(Auto-Failover) 규칙
- **제자리 재연결 우선 (In-place Retry)**:
  - 영상 재생 에러 또는 버퍼링 발생 시, 즉시 다른 카메라로 갈아타지 않고 **현재 카메라에서 최소 2회 재연결**을 먼저 시도해야 합니다 (`handleStreamFailover`).
- **버퍼링 타이머 민감도 (Stall Timeout)**:
  - 라이브 HLS 스트림의 정상 청크 수신 지연을 장애로 오판하지 않도록 감시 타이머는 최소 **8.0초 이상** 대기해야 합니다 (`armVideoPlaybackWatchdog`).
- **검색 장소 중심 반경 제한 (Geofence Anchor)**:
  - 카메라 자동 대체(`findFailoverCandidate`) 시, 직전 카메라가 아닌 **사용자가 보고 있는 장소(`state.center`)**를 기준으로 거리를 계산하며, 최대 허용 반경(`MAX_GEODISTANCE_KM = 4.5km`)을 벗어나 타 시/도로 넘어가지 않도록 제한합니다.
- **슬롯 중복 금지**:
  - 4분할 화면 내에 동일한 카메라나 동일한 씬이 중복 표시되지 않도록 배타적 점유(`ReservationKeys`)를 유지합니다.

### ④ 경기도 GITS 수집 규칙
- [collectors/gits.py](file:///Users/pyw31337/Developer/cctv/collectors/gits.py)에서 GITS 공식 목록(`webLoadCCTVData.do`)에 존재하는 카메라는 일시적 팝업 스크래핑 실패 여부와 무관하게 카탈로그에 보존되어야 합니다.
- 임시 응답 지연으로 인해 수천 대의 정상 GITS 카메라가 `manual_check`(`stream_missing_latest_gits_ingest`)로 강등되는 일이 없어야 합니다.

---

## 3. 최근 완료된 개선 작업 내역 (2026-11)

1. **GitHub Actions CI/CD 안정화**:
   - 골든 카메라 매핑 누락(`L180075`, `L180206`) 및 오버라이드 충돌 해결.
   - [scripts/guard_data_preservation.py](file:///Users/pyw31337/Developer/cctv/scripts/guard_data_preservation.py)에 별칭 자동 치유, 골든 레코드 오버라이드 자동 복구 기능 내장.
   - Quality Gate 및 Deploy Pages 워크플로우 100% 정상 통과 체계 확립.
2. **Git 충돌 고질병 해결**:
   - `pull.rebase true` 및 `rebase.autoStash true` 적용으로 원격 동기화 자동화.
   - [.gitattributes](file:///Users/pyw31337/Developer/cctv/.gitattributes)를 통한 대용량 동적 JSON 파일 병합 충돌 방지.
3. **오프라인 캐싱 및 듀얼 폴백(Dual-Layer Fallback)**:
   - [js/app.js](file:///Users/pyw31337/Developer/cctv/js/app.js) 초기 로딩 시 `cctv_core.json` 실패 시 `cctv_data.json`으로 자동 폴백.
   - [sw.js](file:///Users/pyw31337/Developer/cctv/sw.js) Service Worker 정적 캐시 대상에 코어 데이터 추가.
4. **구리 수택동('제이헤어') 및 주변 카메라 복구**:
   - 제이헤어 20m 거리 최인접 카메라인 **'수택동4'(`GITS_6739`)**를 1순위로 지정.
   - 인근 핵심 카메라 4대('수택동4', '돌다리사거리', '세무서4', '왕숙교입구')가 4분할에 안정적으로 뜨도록 `applyLocalPlacePriority` 개편.
5. **영상 재생 중 화면 널뛰기/바뀜 방지 (전체 카메라 적용)**:
   - 버퍼링 시 즉시 카메라가 바뀌던 문제를 2회 제자리 재연결 후 전환으로 안정화.
   - 감시 타이머 3.5초 조기 판정을 8.0초로 완화.
   - 검색 중심점 기준 4.5km 지오펜스 엄격 적용으로 타 시/도로 튕겨 나가는 현상 원천 차단.
6. **부당하게 점검 중으로 분류된 경기도 GITS 카메라 889대 전량 복구**:
   - `stream_missing_latest_gits_ingest` 사유로 묶여 있던 889대를 `active`로 일괄 복구 완료.
   - [collectors/gits.py](file:///Users/pyw31337/Developer/cctv/collectors/gits.py) 수집 로직 보강.

---

## 4. 향후 진행할 권장 작업 로드맵 (Roadmap)

다음 에이전트는 사용자의 요청이나 서비스 고도화 시 아래 작업을 우선적으로 검토하여 진행합니다:

1. **[UX] 즐겨찾기 장소 카메라 고정 핀(Pin) 기능**:
   - 즐겨찾기 장소를 열었을 때 자동 계산된 4개 화면 중, 사용자가 원하는 카메라를 고정(Lock)하여 새로고침이나 재방문 시에도 항상 동일한 카메라가 나오도록 하는 기능.
2. **[성능] 모바일 공간 인덱스(GeoCell) 검색 최적화**:
   - 모바일 저사양 기기에서 18,000개 데이터 검색 시 프레임 드랍이 없도록 `state.geoIndex` 조회 알고리즘 메모리 튜닝.
3. **[모니터링] GITS 프록시 헬스체크 고도화**:
   - Sentinel 모니터링 배치([scripts/sentinel.py](file:///Users/pyw31337/Developer/cctv/scripts/sentinel.py))에서 GITS 카메라 검사 시 정적 URL 검사 대신 Fly.dev 프록시 경유 유효성 검증을 지원하도록 보강.
4. **[스트림] 구형 UTIC 플래시/ActiveX 잔재 제거 및 HLS 전환**:
   - 각 지자체 교통정보센터(ITS) 중 자체 HLS를 새로 오픈한 지역(예: 인천, 대구 등)에 대한 다이렉트 스트림 매핑 점진적 확대.

---

## 5. 작업 완료 시 필수 검증 체크리스트 (Verification Checklist)

코드나 데이터를 수정한 에이전트는 커밋 전 아래 명령어를 순서대로 실행하여 무결성을 확인해야 합니다:

```bash
# 1. 자바스크립트 문법 검사
node --check js/app.js
node --check js/world-tour.js
node --check sw.js

# 2. 정적 데이터 및 워크플로우 무결성 검증
python scripts/validate_static_data.py
python scripts/validate_workflows.py

# 3. 시스템 무결성 5대 테스트 (지오펜스, 제이헤어/크라운모텔 핀포인트 등)
python scripts/verify_system_integrity.py

# 4. 데이터셋 보존 및 코어/확장 동기화 검증
python scripts/guard_data_preservation.py

# 5. 전체 단위 테스트 스위트 (144개 테스트 통과 필수)
python -m unittest discover -p 'test_*.py'
```

---

## 6. 배포 및 Handoff 준수 사항

- 워크플로우나 스케줄러 변경 시 [WORKFLOW_HANDOFF.md](file:///Users/pyw31337/Developer/cctv/WORKFLOW_HANDOFF.md)와 캐노니컬 저장소(`https://github.com/pyw31337/macmini-workflow-handoff`)의 규칙을 반드시 준수합니다.
- 토큰, 시크릿 키, `.env` 파일은 절대로 커밋하지 않습니다.
- 작업 완료 후 명확한 커밋 메시지를 작성하고 `main` 브랜치에 안전하게 동기화합니다.
