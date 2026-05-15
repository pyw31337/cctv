const DEFAULT_ALLOWED_ORIGINS = [
  'https://pyw31337.github.io',
  'http://localhost:8000',
  'http://127.0.0.1:8000'
];

const MAX_EVENTS_PER_REQUEST = 12;
const MAX_BODY_BYTES = 24 * 1024;
const SUMMARY_WINDOW_HOURS = 24;

function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      ...headers
    }
  });
}

function getCorsHeaders(request, env) {
  const requestOrigin = request.headers.get('origin') || '';
  const configuredOrigins = String(env.ALLOWED_ORIGINS || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  const allowedOrigins = configuredOrigins.length > 0 ? configuredOrigins : DEFAULT_ALLOWED_ORIGINS;
  const allowOrigin = allowedOrigins.includes(requestOrigin) ? requestOrigin : allowedOrigins[0];

  return {
    'access-control-allow-origin': allowOrigin,
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    'access-control-allow-headers': 'content-type',
    'access-control-max-age': '86400',
    vary: 'Origin'
  };
}

function sanitizeText(value, maxLength) {
  return String(value || '')
    .replace(/[^\p{L}\p{N}\s._@()[\]-]/gu, '')
    .trim()
    .slice(0, maxLength);
}

function toPositiveInteger(value, maxValue = 120000) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue) || numberValue < 0) return 0;
  return Math.min(maxValue, Math.round(numberValue));
}

function normalizeEvent(input) {
  if (!input || typeof input !== 'object') return null;
  const eventType = sanitizeText(input.event_type || input.eventType, 24);
  if (!['success', 'slow', 'failure', 'fallback'].includes(eventType)) return null;

  const cameraId = sanitizeText(input.camera_id || input.cameraId, 96);
  if (!cameraId) return null;

  return {
    eventType,
    appVersion: sanitizeText(input.app_version || input.appVersion, 40),
    cameraId,
    cameraName: sanitizeText(input.camera_name || input.cameraName, 80),
    source: sanitizeText(input.source, 32) || 'UNKNOWN',
    region: sanitizeText(input.region, 32) || 'UNKNOWN',
    sourceIndex: toPositiveInteger(input.source_index || input.sourceIndex, 20),
    usedFallback: Boolean(input.used_fallback || input.usedFallback),
    firstFrameMs: toPositiveInteger(input.first_frame_ms || input.firstFrameMs),
    failMs: toPositiveInteger(input.fail_ms || input.failMs),
    stallCount: toPositiveInteger(input.stall_count || input.stallCount, 100),
    videoWidth: toPositiveInteger(input.video_width || input.videoWidth, 10000),
    videoHeight: toPositiveInteger(input.video_height || input.videoHeight, 10000),
    reason: sanitizeText(input.reason, 48)
  };
}

async function readEvents(request) {
  const contentLength = Number(request.headers.get('content-length') || 0);
  if (contentLength > MAX_BODY_BYTES) throw new Error('body-too-large');

  const body = await request.json();
  const rawEvents = Array.isArray(body) ? body : (Array.isArray(body.events) ? body.events : [body]);
  return rawEvents.slice(0, MAX_EVENTS_PER_REQUEST).map(normalizeEvent).filter(Boolean);
}

function getCurrentHourBucket() {
  const now = new Date();
  now.setUTCMinutes(0, 0, 0);
  return now.toISOString();
}

function getCutoffBucket() {
  const cutoff = new Date(Date.now() - SUMMARY_WINDOW_HOURS * 60 * 60 * 1000);
  cutoff.setUTCMinutes(0, 0, 0);
  return cutoff.toISOString();
}

function buildRollupStatement(env, event, bucket) {
  const isSuccess = event.eventType === 'success' || event.eventType === 'slow';
  const isFailure = event.eventType === 'failure';
  const isFallback = event.eventType === 'fallback' || event.usedFallback || event.sourceIndex > 0;
  const isSlow = event.eventType === 'slow';
  const isPlaybackSample = isSuccess || isFailure;
  const firstFrameMs = isSuccess ? event.firstFrameMs : 0;
  const failMs = isFailure ? event.failMs : 0;
  const width = isSuccess ? event.videoWidth : 0;
  const height = isSuccess ? event.videoHeight : 0;

  return env.DB.prepare(`
    INSERT INTO camera_quality_rollups (
      bucket, camera_id, camera_name, source, region,
      samples, success, failure, fallback, slow,
      first_frame_ms_sum, fail_ms_sum, stall_count_sum, width_sum, height_sum, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(bucket, camera_id) DO UPDATE SET
      camera_name = excluded.camera_name,
      source = excluded.source,
      region = excluded.region,
      samples = samples + excluded.samples,
      success = success + excluded.success,
      failure = failure + excluded.failure,
      fallback = fallback + excluded.fallback,
      slow = slow + excluded.slow,
      first_frame_ms_sum = first_frame_ms_sum + excluded.first_frame_ms_sum,
      fail_ms_sum = fail_ms_sum + excluded.fail_ms_sum,
      stall_count_sum = stall_count_sum + excluded.stall_count_sum,
      width_sum = width_sum + excluded.width_sum,
      height_sum = height_sum + excluded.height_sum,
      updated_at = excluded.updated_at
  `).bind(
    bucket,
    event.cameraId,
    event.cameraName,
    event.source,
    event.region,
    isPlaybackSample ? 1 : 0,
    isSuccess ? 1 : 0,
    isFailure ? 1 : 0,
    isFallback ? 1 : 0,
    isSlow ? 1 : 0,
    firstFrameMs,
    failMs,
    event.stallCount,
    width,
    height,
    new Date().toISOString()
  );
}

async function handleEvents(request, env, corsHeaders) {
  if (!env.DB) return jsonResponse({ ok: false, error: 'missing-db-binding' }, 503, corsHeaders);

  let events;
  try {
    events = await readEvents(request);
  } catch (error) {
    return jsonResponse({ ok: false, error: error.message || 'bad-request' }, 400, corsHeaders);
  }

  if (events.length === 0) return jsonResponse({ ok: true, accepted: 0 }, 202, corsHeaders);

  const bucket = getCurrentHourBucket();
  const statements = events.map((event) => buildRollupStatement(env, event, bucket));
  await env.DB.batch(statements);

  return jsonResponse({ ok: true, accepted: events.length }, 202, corsHeaders);
}

function normalizeRows(rows, keyName) {
  const output = {};
  for (const row of rows || []) {
    const key = row[keyName];
    const samples = Number(row.samples || 0);
    const success = Number(row.success || 0);
    const failure = Number(row.failure || 0);
    const slow = Number(row.slow || 0);
    const fallback = Number(row.fallback || 0);
    output[key] = {
      camera_name: row.camera_name,
      source: row.source,
      region: row.region,
      samples,
      success,
      failure,
      slow,
      fallback,
      success_rate: samples ? success / samples : 0,
      failure_rate: samples ? failure / samples : 0,
      slow_rate: samples ? slow / samples : 0,
      fallback_rate: samples ? fallback / samples : 0,
      avg_first_frame_ms: success ? Number(row.first_frame_ms_sum || 0) / success : 0,
      avg_fail_ms: failure ? Number(row.fail_ms_sum || 0) / failure : 0,
      avg_width: success ? Number(row.width_sum || 0) / success : 0,
      avg_height: success ? Number(row.height_sum || 0) / success : 0,
      updated_at: row.updated_at
    };
  }
  return output;
}

async function handleSummary(env, corsHeaders) {
  if (!env.DB) return jsonResponse({ generated_at: new Date().toISOString(), cameras: {}, sources: {}, regions: {} }, 200, corsHeaders);

  const cutoff = getCutoffBucket();
  const cameraQuery = env.DB.prepare(`
    SELECT
      camera_id,
      camera_name,
      source,
      region,
      SUM(samples) AS samples,
      SUM(success) AS success,
      SUM(failure) AS failure,
      SUM(fallback) AS fallback,
      SUM(slow) AS slow,
      SUM(first_frame_ms_sum) AS first_frame_ms_sum,
      SUM(fail_ms_sum) AS fail_ms_sum,
      SUM(stall_count_sum) AS stall_count_sum,
      SUM(width_sum) AS width_sum,
      SUM(height_sum) AS height_sum,
      MAX(updated_at) AS updated_at
    FROM camera_quality_rollups
    WHERE bucket >= ?
    GROUP BY camera_id
    HAVING samples >= 2
    ORDER BY samples DESC
    LIMIT 2000
  `).bind(cutoff);

  const sourceQuery = env.DB.prepare(`
    SELECT
      source AS source_id,
      source,
      NULL AS camera_name,
      NULL AS region,
      SUM(samples) AS samples,
      SUM(success) AS success,
      SUM(failure) AS failure,
      SUM(fallback) AS fallback,
      SUM(slow) AS slow,
      SUM(first_frame_ms_sum) AS first_frame_ms_sum,
      SUM(fail_ms_sum) AS fail_ms_sum,
      SUM(stall_count_sum) AS stall_count_sum,
      SUM(width_sum) AS width_sum,
      SUM(height_sum) AS height_sum,
      MAX(updated_at) AS updated_at
    FROM camera_quality_rollups
    WHERE bucket >= ?
    GROUP BY source
  `).bind(cutoff);

  const regionQuery = env.DB.prepare(`
    SELECT
      region AS region_id,
      NULL AS camera_name,
      NULL AS source,
      region,
      SUM(samples) AS samples,
      SUM(success) AS success,
      SUM(failure) AS failure,
      SUM(fallback) AS fallback,
      SUM(slow) AS slow,
      SUM(first_frame_ms_sum) AS first_frame_ms_sum,
      SUM(fail_ms_sum) AS fail_ms_sum,
      SUM(stall_count_sum) AS stall_count_sum,
      SUM(width_sum) AS width_sum,
      SUM(height_sum) AS height_sum,
      MAX(updated_at) AS updated_at
    FROM camera_quality_rollups
    WHERE bucket >= ?
    GROUP BY region
  `).bind(cutoff);

  const [cameraResult, sourceResult, regionResult] = await Promise.all([
    cameraQuery.all(),
    sourceQuery.all(),
    regionQuery.all()
  ]);

  return jsonResponse({
    generated_at: new Date().toISOString(),
    window_hours: SUMMARY_WINDOW_HOURS,
    cameras: normalizeRows(cameraResult.results, 'camera_id'),
    sources: normalizeRows(sourceResult.results, 'source_id'),
    regions: normalizeRows(regionResult.results, 'region_id')
  }, 200, {
    ...corsHeaders,
    'cache-control': 'public, max-age=300'
  });
}

async function pruneOldRollups(env) {
  if (!env.DB) return;
  const cutoff = new Date(Date.now() - 14 * 24 * 60 * 60 * 1000);
  cutoff.setUTCMinutes(0, 0, 0);
  await env.DB.prepare('DELETE FROM camera_quality_rollups WHERE bucket < ?').bind(cutoff.toISOString()).run();
}

export default {
  async fetch(request, env) {
    const corsHeaders = getCorsHeaders(request, env);
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: corsHeaders });

    const url = new URL(request.url);
    try {
      if (request.method === 'POST' && url.pathname === '/v1/events') {
        return await handleEvents(request, env, corsHeaders);
      }
      if (request.method === 'GET' && url.pathname === '/v1/summary') {
        return await handleSummary(env, corsHeaders);
      }
      return jsonResponse({ ok: false, error: 'not-found' }, 404, corsHeaders);
    } catch (error) {
      console.error(JSON.stringify({ level: 'error', message: error.message, stack: error.stack }));
      return jsonResponse({ ok: false, error: 'internal-error' }, 500, corsHeaders);
    }
  },

  async scheduled(_event, env, ctx) {
    ctx.waitUntil(pruneOldRollups(env));
  }
};
