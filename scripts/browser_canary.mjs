#!/usr/bin/env node
/**
 * Scheduled browser playback canary.
 *
 * Scheduled checks prove that four visible panels use four distinct streams.
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
  { key: 'highway_gyeongbu', name: '경부선', lat: 37.4630, lng: 127.0390, highwayRoute: '경부선' },
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
        ready_panel_count: 0,
        panel_count: 0,
        unique_stream_count: 0,
        duplicate_stream_keys: [],
        duplicate_actual_stream_keys: [],
        duplicate_camera_ids: [],
        panel_details: [],
        mapping_errors: [],
        error_text: null,
      };
      try {
        await page.goto(result.url, { waitUntil: 'domcontentloaded', timeout: TIMEOUT_MS });
        if (region.highwayRoute) {
          // Exercise the real route selector rather than treating the nearby
          // map result as proof that the highway product path is playable.
          await page.locator('#highway-btn').click({ timeout: TIMEOUT_MS });
          const route = page.locator(`.highway-route-item[data-route="${region.highwayRoute}"]`);
          await route.waitFor({ state: 'visible', timeout: TIMEOUT_MS });
          await route.click({ timeout: TIMEOUT_MS });
          result.selection = `highway:${region.highwayRoute}`;
        }
        await page.waitForFunction(() => {
          const panels = Array.from(document.querySelectorAll('.video-panel'));
          return panels.length >= 4 && panels.every(panel => {
            const video = panel.querySelector('video');
            const iframe = panel.querySelector('iframe');
            return (video && video.readyState >= 2 && video.videoWidth > 0)
              || (iframe && iframe.clientWidth > 100 && iframe.clientHeight > 100);
          });
        }, { timeout: TIMEOUT_MS });
        const metrics = await page.evaluate(async () => {
          const key = (url, depth = 0) => {
            try {
              const parsed = new URL(String(url || ''), location.href);
              // The player may use a proxy wrapper while the catalog has the
              // upstream URL. Unwrap it before comparing camera identities.
              const wrappedUrl = parsed.searchParams.get('url') || parsed.searchParams.get('target');
              if (wrappedUrl && depth < 2) return key(wrappedUrl, depth + 1);
              const media = parsed.pathname.match(/\/media\/(L\d+)/i);
              if (media) return `${parsed.hostname.toLowerCase()}:${media[1].toUpperCase()}`;
              const id = parsed.searchParams.get('cctvid') || parsed.searchParams.get('id');
              if (id) return `${parsed.hostname.toLowerCase()}:${id.toUpperCase()}`;
              return parsed.protocol && parsed.hostname ? `${parsed.protocol}//${parsed.hostname}${parsed.pathname}` : '';
            } catch (_) { return ''; }
          };
          const catalog = await fetch(new URL('cctv_data.json', location.href)).then(r => r.ok ? r.json() : []).catch(() => []);
          const byId = new Map((Array.isArray(catalog) ? catalog : []).map(item => [String(item?.id || ''), item]));
          const videos = Array.from(document.querySelectorAll('video'));
          const panels = Array.from(document.querySelectorAll('.video-panel'));
          const readyPanels = panels.filter(panel => {
            const video = panel.querySelector('video');
            const iframe = panel.querySelector('iframe');
            return (video && video.readyState >= 2 && video.videoWidth > 0)
              || (iframe && iframe.clientWidth > 100 && iframe.clientHeight > 100);
          });
          const panelDetails = panels.map(panel => {
            const item = byId.get(panel.dataset.cctvId || '');
            const video = panel.querySelector('video');
            const iframe = panel.querySelector('iframe');
            const actualUrl = video?.currentSrc || video?.src || iframe?.src || '';
            // hls.js normally exposes a blob: URL through currentSrc. The
            // active camera ID is therefore the reliable record of which
            // catalog stream the player is actually rendering after fallback.
            const activeCameraId = video?.dataset.activeCctvId || panel.dataset.cctvId || '';
            const activeItem = byId.get(activeCameraId);
            return {
              camera_id: panel.dataset.cctvId || '',
              active_camera_id: activeCameraId,
              catalog_stream_key: key(item?.directUrl || item?.url || ''),
              actual_stream_key: key(activeItem?.directUrl || activeItem?.url || actualUrl),
              actual_source_kind: video ? 'video' : (iframe ? 'iframe' : 'none'),
            };
          });
          const duplicates = (values) => {
            const counts = new Map();
            values.filter(Boolean).forEach(value => counts.set(value, (counts.get(value) || 0) + 1));
            return [...counts.entries()].filter(([, count]) => count > 1).map(([value]) => value);
          };
          const streamKeys = panelDetails.map(item => item.catalog_stream_key);
          const actualStreamKeys = panelDetails.map(item => item.actual_stream_key);
          const cameraIds = panelDetails.map(item => item.active_camera_id);
          return {
            video_count: videos.length,
            playing_count: videos.filter(video => video.readyState >= 2 && video.videoWidth > 0).length,
            ready_panel_count: readyPanels.length,
            panel_count: panels.length,
            stream_keys: streamKeys,
            unique_stream_count: new Set(streamKeys.filter(Boolean)).size,
            duplicate_stream_keys: duplicates(streamKeys),
            duplicate_actual_stream_keys: duplicates(actualStreamKeys),
            duplicate_camera_ids: duplicates(cameraIds),
            panel_details: panelDetails,
            mapping_errors: panelDetails
              .map(item => item.camera_id && item.catalog_stream_key ? null : item.camera_id || '<missing>')
              .filter(Boolean),
          };
        });
        result.ok = metrics.panel_count >= 4 && metrics.ready_panel_count >= 4
          && metrics.unique_stream_count >= 4 && metrics.duplicate_stream_keys.length === 0
          && metrics.duplicate_actual_stream_keys.length === 0
          && metrics.duplicate_camera_ids.length === 0
          && metrics.mapping_errors.length === 0;
        result.first_frame_ms = Date.now() - started;
        result.video_count = metrics.video_count;
        result.playing_count = metrics.playing_count;
        result.ready_panel_count = metrics.ready_panel_count;
        result.panel_count = metrics.panel_count;
        result.unique_stream_count = metrics.unique_stream_count;
        result.duplicate_stream_keys = metrics.duplicate_stream_keys;
        result.duplicate_actual_stream_keys = metrics.duplicate_actual_stream_keys;
        result.duplicate_camera_ids = metrics.duplicate_camera_ids;
        result.panel_details = metrics.panel_details;
        result.mapping_errors = metrics.mapping_errors;
      } catch (error) {
        result.error_text = String(error?.message || error).slice(0, 300);
        const metrics = await page.evaluate(() => {
          const panels = Array.from(document.querySelectorAll('.video-panel'));
          const readyPanels = panels.filter(panel => {
            const video = panel.querySelector('video');
            const iframe = panel.querySelector('iframe');
            return (video && video.readyState >= 2 && video.videoWidth > 0)
              || (iframe && iframe.clientWidth > 100 && iframe.clientHeight > 100);
          });
          return {
            panel_count: panels.length,
            ready_panel_count: readyPanels.length,
            video_count: document.querySelectorAll('video').length,
            playing_count: Array.from(document.querySelectorAll('video')).filter(video => video.readyState >= 2 && video.videoWidth > 0).length,
          };
        }).catch(() => null);
        if (metrics) Object.assign(result, metrics);
      } finally {
        await page.close().catch(() => {});
      }
      console.log(`[browser-canary] ${region.key} ok=${result.ok} first=${result.first_frame_ms ?? '-'}ms panels=${result.ready_panel_count}/${result.panel_count} videos=${result.playing_count}/${result.video_count}`);
      results.push(result);
    }
  } finally {
    await browser.close();
  }

  const payload = {
    generated_at: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    app_base: APP_BASE,
    timeout_ms: TIMEOUT_MS,
    mode: 'scheduled_real_browser_playback',
    results,
    summary: {
      checked: results.length,
      passed: results.filter(item => item.ok).length,
      failed: results.filter(item => !item.ok).length,
      service_impact_failed: results.filter(item => !item.ok
        && item.duplicate_stream_keys.length === 0
        && item.duplicate_camera_ids.length === 0
        && item.mapping_errors.length === 0).length,
      service_impact_critical_failed: results.filter(item => item.key === 'namyangju' && !item.ok).length,
      hard_failed: results.filter(item => item.duplicate_stream_keys.length > 0
        || item.duplicate_camera_ids.length > 0
        || item.mapping_errors.length > 0).length,
    },
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, `${JSON.stringify(payload, null, 2)}\n`);
  // Upstream camera outages are service-impact telemetry, not a CI failure.
  // Fail only on structural identity violations; those can regress the catalog.
  if (payload.summary.hard_failed > 0
    || (payload.summary.failed > 0 && payload.summary.passed === 0)) process.exitCode = 1;
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
