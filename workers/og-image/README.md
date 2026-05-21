# cctv-og-image

Dynamic Open Graph image worker for "밖에 눈오나?" share cards.

## Why a worker

`shareCurrentView()` previously emitted a generic OG image (`title.png`) for every share. Now each shared link gets a 1200×630 PNG composed at the edge with:
- the current cctv's name (and direction parenthesis)
- the city / region
- the live snapshot blurred behind a vertical gradient
- the "밖에 눈오나?" brand chip

KakaoTalk / Slack / Twitter / Discord all render the link card with this dynamic image.

## Deploy

```bash
cd workers/og-image
npm install
npx wrangler login         # one-time
npx wrangler deploy
```

The worker URL ends up as `https://cctv-og.<account>.workers.dev`. Update the constant `CCTV_OG_WORKER_URL` in `js/app.js` if you use a custom subdomain.

## URL

```
GET https://cctv-og.<account>.workers.dev/og
  ?id=<cctv_id>
  &title=<urlencoded title incl. direction>
  &city=<urlencoded city>
  &snap=<urlencoded snapshot URL — used as the background>
```

## Cache

- Edge cache: 6 hours (`public, max-age=21600, stale-while-revalidate=86400`).
- Snapshot fetches inside the worker use a 30-minute Cloudflare cache.
- Override by adding `_=<timestamp>` if you need a forced refresh.

## Cost

Free tier covers 100k req/day. Each render uses satori (CPU-bound) ~80-150ms — well within Worker free-tier limits even at moderate share volume.
