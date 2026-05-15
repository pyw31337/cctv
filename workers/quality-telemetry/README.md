# CCTV Quality Telemetry Worker

익명 실사용 재생 품질 이벤트를 D1에 시간 단위로 집계하는 Cloudflare Worker입니다.

## 수집 원칙

- 저장함: CCTV ID, 공개 CCTV 이름, 소스, 지역, 성공/실패, 첫 화면 로딩 시간, 해상도, 대체 소스 사용 여부
- 저장하지 않음: IP 원문, 정확한 사용자 위치, 검색어, User-Agent 원문, CCTV 토큰 URL, 개인 식별자

## 배포 순서

```bash
cd workers/quality-telemetry
npm install
npx wrangler d1 create cctv_quality
```

`wrangler.jsonc`의 `database_id`를 생성된 값으로 교체합니다.

```bash
npm run migrate:remote
npm run deploy
```

배포 후 앱의 `index.html`에 설정된 `https://cctv-quality.pyw31337.workers.dev` 주소가 실제 Worker 주소와 다르면 수정하세요.

## 엔드포인트

- `POST /v1/events`: 브라우저 재생 품질 이벤트 수신
- `GET /v1/summary`: 최근 24시간 CCTV/소스/지역별 품질 요약 반환

