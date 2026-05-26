#!/usr/bin/env node
/**
 * Manual browser playback canary.
 *
 * This is intentionally not scheduled by default because headless Chromium runs
 * are expensive in GitHub Actions minutes. Use it when we need proof that the
 * public app can start playback in a real browser, not just that stream URLs
 * respond from the server.
 */
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const APP_BASE = process.env.CCTV_APP_BASE || 'https://pyw31337.github.io/cctv/';
const OUT = process.env.BROWSER_CANARY_OUT || 'data/browser_canary_report.json';
const TIMEOUT_MS = Number(process.env.BROWSER_CANARY_TIMEOUT_MS || 30000);

const REGIONS = [
  { key: 'jindo', name: '진도', lat: 34.456845, lng: 126.242558 },
  { key: 'jeju', name: '올레길 7코스(서귀포-월평 올레)', lat: 33.2406, lng: 126.5628 },
  { key: 'daejeon', name: '한밭수목원', lat: 36.3672, lng: 127.3880 },
  { key: 'guri', name: '제이헤어', lat: 37.5943, lng: 127.1296 },
  { key: 'namyangju', name: '크라운모텔', lat: 37.6525, lng: 127.3072 },
  { key: 'dokdo', name: '독도', lat: 37.23936, lng: 131.8686 },
];

function targetUrl(region) {
  const url = new URL(APP_BASE);
  url.searchParams.set('lat', String(region.lat));
  url.searchParams.set('lng', String(region.lng));
  url.searchParams.set('name', region.name);
  url.searchParams.set('mode', 'video');
  url.searchParams.set('sort', 'stability');
  url.searchParams.set('_canary', region.key);
  return url.toString();
}

async function main() {
  let chromium;
  try {
    ({ chromium } = await import('playwright'));
  } catch (error) {
    console.error('playwright is not installed. Run `npm exec playwright install chromium` in CI or install playwright locally.');
    process.exitCode = 2;
    return;
  }

  const browser = await chromium.launch({ headless: true });
  const results = [];
  try {
    for (const region of REGIONS) {
      const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
      const started = Date.now();
      const result = {
        key: region.key,
        label: region.name,
        url: targetUrl(region),
        ok: false,
        first_frame_ms: null,
        playing_count: 0,
        video_count: 0,
        error_text: null,
      };
      try {
        await page.goto(result.url, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
        await page.waitForFunction(() => {
          const videos = Array.from(document.querySelectorAll('video'));
          const iframes = Array.from(document.querySelectorAll('iframe'));
          return videos.some(video => video.readyState >= 2 && video.videoWidth > 0)
            || iframes.some(frame => frame.clientWidth > 100 && frame.clientHeight > 100);
        }, { timeout: TIMEOUT_MS });
        const metrics = await page.evaluate(() => {
          const videos = Array.from(document.querySelectorAll('video'));
          return {
            video_count: videos.length,
            playing_count: videos.filter(video => video.readyState >= 2 && video.videoWidth > 0).length,
          };
        });
        result.ok = metrics.playing_count > 0 || metrics.video_count === 0;
        result.first_frame_ms = Date.now() - started;
        result.video_count = metrics.video_count;
        result.playing_count = metrics.playing_count;
      } catch (error) {
        result.error_text = String(error?.message || error).slice(0, 300);
      } finally {
        await page.close().catch(() => {});
      }
      console.log(`[browser-canary] ${region.key} ok=${result.ok} first=${result.first_frame_ms ?? '-'}ms videos=${result.playing_count}/${result.video_count}`);
      results.push(result);
    }
  } finally {
    await browser.close();
  }

  const payload = {
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    app_base: APP_BASE,
    timeout_ms: TIMEOUT_MS,
    mode: 'manual_real_browser_playback',
    results,
    summary: {
      checked: results.length,
      passed: results.filter(item => item.ok).length,
      failed: results.filter(item => !item.ok).length,
    },
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, `${JSON.stringify(payload, null, 2)}\n`);
  if (payload.summary.failed > 0) process.exitCode = 1;
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
