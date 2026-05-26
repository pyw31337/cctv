#!/usr/bin/env node
import fs from 'node:fs';
import vm from 'node:vm';

const ROOT = new URL('..', import.meta.url);
const readText = (path) => fs.readFileSync(new URL(path, ROOT), 'utf8');
const noop = () => {};

function fakeElement() {
  return {
    style: { cssText: '', setProperty: noop },
    classList: { add: noop, remove: noop, contains: () => false, toggle: noop },
    dataset: {},
    appendChild: noop,
    append: noop,
    setAttribute: noop,
    addEventListener: noop,
    removeEventListener: noop,
    querySelector: () => null,
    querySelectorAll: () => [],
    closest: () => null,
  };
}

function loadAppHarness() {
  const appCode = readText('js/app.js') + `
    ;globalThis.__cctvTest = {
      state,
      buildGeoIndex,
      updateNearestCctvs,
      inferRegionKey,
      getCameraHealthMeta,
      getCameraPlaybackConfidence,
      getCameraDisplayHealthMeta,
      findManualRetryFallback,
      getCctvReservationKeys
    };
  `;
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    performance: { now: () => Date.now() },
    URL,
    URLSearchParams,
    window: {
      CCTV_QUALITY_CONFIG: {},
      location: { search: '', origin: 'http://test.local', pathname: '/' },
      history: { replaceState: noop },
      addEventListener: noop,
      removeEventListener: noop,
      localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
      crypto: { getRandomValues: (arr) => arr.fill(255) },
    },
    document: {
      readyState: 'loading',
      addEventListener: noop,
      removeEventListener: noop,
      querySelector: () => null,
      querySelectorAll: () => [],
      createElement: fakeElement,
      getElementById: () => null,
    },
    navigator: { sendBeacon: () => false, clipboard: null, share: null, serviceWorker: null },
    localStorage: { getItem: () => null, setItem: noop, removeItem: noop },
    fetch: async () => ({ ok: false, json: async () => ({}), text: async () => '' }),
    Hls: function Hls() {},
  };
  sandbox.globalThis = sandbox;
  sandbox.window.document = sandbox.document;
  vm.createContext(sandbox);
  vm.runInContext(appCode, sandbox, { filename: 'js/app.js' });
  return sandbox.__cctvTest;
}

function makeSyntheticHealth() {
  const ok = { status: 'OK', checked: 4, passed: 4, failed: 0, checked_at: '2026-05-15T00:00:00Z' };
  const down = { status: 'DOWN', checked: 6, passed: 0, failed: 6, active_source: 'main', checked_at: '2026-05-15T00:00:00Z' };
  return {
    last_updated: '2026-05-15T00:00:00Z',
    regions: {
      DAEJEON: ok,
      GITS: down,
      JEJU: ok,
      KBS: ok,
      NOWJEJU: ok,
      NTIC: down,
      SPATIC: ok,
      TOPIS: ok,
      TRENDWORLD: ok,
      ULLEUNG: down,
      UTIC_DIRECT: down,
      UTIC_LEGACY: down,
      UTIC_Z3: down,
    },
  };
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function names(list, limit = 8) {
  return list.slice(0, limit).map((item) => item.name);
}

const harness = loadAppHarness();
const cctvData = JSON.parse(readText('cctv_data.json'));
harness.state.cctvData = cctvData;
harness.state.cctvById = new Map(cctvData.map((item) => [item.id, item]));
harness.state.regionHealth = makeSyntheticHealth().regions;
harness.state.healthSnapshot = makeSyntheticHealth();
harness.state.cameraFailures = new Map();
harness.state.healthSnapshotStale = false;
harness.state.qualitySummary = null;
harness.buildGeoIndex(cctvData);

const byId = new Map(cctvData.map((item) => [item.id, item]));
assert(harness.inferRegionKey(byId.get('L901466')) === 'UTIC_DIRECT', 'L901466 should use UTIC_DIRECT health bucket');
assert(harness.inferRegionKey(byId.get('E902483')) === 'UTIC_Z3', 'E902483 should use UTIC_Z3 health bucket');
assert(harness.inferRegionKey(byId.get('L380002')) === 'JEJU', 'Jeju UTIC K streams should remain in JEJU bucket');

const z3Sample = byId.get('E902483');
const z3Health = harness.getCameraHealthMeta(z3Sample);
const z3Confidence = harness.getCameraPlaybackConfidence(z3Sample, z3Health);
const z3DisplayHealth = harness.getCameraDisplayHealthMeta(z3Sample, z3Health);
assert(z3Health.status === 'DOWN', 'synthetic UTIC_Z3 aggregate health should remain DOWN');
assert(z3Confidence.tone === 'unknown', 'aggregate-only UTIC_Z3 DOWN should not promise a per-camera failure');
assert(z3DisplayHealth.tone === 'unknown', 'map marker display should not turn aggregate-only UTIC_Z3 DOWN red');

const gitsSample = cctvData.find((item) => item.source === 'GITS' || String(item.id || '').startsWith('GITS_'));
if (gitsSample) {
  assert(harness.inferRegionKey(gitsSample) === 'GITS', 'GITS cameras should remain in GITS bucket');
} else {
  console.log('[SKIP] no GITS sample in current generated dataset');
}

const guri = {
  label: '제이헤어 / 경기 구리시 수택동 437-48',
  center: { lat: 37.5959910402814, lng: 127.138034918802 },
  expectedNearby: ['세무서4', '중앙예식장사거리', '돌다리사거리', '삼육고등학교앞', '교문사거리'],
};

for (const sortMode of ['nearest', 'urban']) {
  harness.state.center = guri.center;
  harness.state.sortMode = sortMode;
  harness.updateNearestCctvs();
  const topNames = names(harness.state.nearestCctvs, 8);
  const matched = guri.expectedNearby.filter((name) => topNames.includes(name));
  assert(
    matched.length >= 4,
    `${guri.label} ${sortMode} regression: expected at least 4 known nearby urban cameras in top 8, got ${JSON.stringify(topNames)}`
  );
  console.log(`[OK] ${guri.label} ${sortMode}: ${topNames.join(', ')}`);
}

const failingGuriCamera = byId.get('L901466');
harness.state.cameraFailures = new Map([[
  'L901466',
  {
    id: 'L901466',
    name: '세무서4',
    region: 'UTIC_DIRECT',
    source: 'UTIC',
    emergency_level: 'critical',
    failed_for_minutes: 130,
    failure_count: 4,
    last_failed_at: new Date().toISOString(),
    diagnosis: {
      likely_cause: '테스트용 반복 장애',
      recommended_action: '추천 하위 격리',
    },
  },
]]);
harness.state.center = guri.center;
harness.state.sortMode = 'nearest';
harness.updateNearestCctvs();
const isolatedTopNames = names(harness.state.nearestCctvs, 8);
const isolatedHealth = harness.getCameraHealthMeta(failingGuriCamera);
const isolatedConfidence = harness.getCameraPlaybackConfidence(failingGuriCamera, isolatedHealth);
const retryFallback = harness.findManualRetryFallback(failingGuriCamera);
const retryFallbackReserved = new Set(harness.getCctvReservationKeys(retryFallback));
const nextRetryFallback = harness.findManualRetryFallback(failingGuriCamera, retryFallbackReserved);
assert(isolatedHealth.status === 'CAMERA_CRITICAL', 'camera failure registry should override aggregate health');
assert(isolatedConfidence.tone === 'danger', 'critical camera failure should render a red selector dot');
assert(harness.getCameraDisplayHealthMeta(failingGuriCamera, isolatedHealth).tone === 'danger', 'camera-specific critical failures should still render red markers');
assert(!isolatedTopNames.includes('세무서4'), `critical camera should be isolated from top 8, got ${JSON.stringify(isolatedTopNames)}`);
assert(retryFallback && retryFallback.id !== failingGuriCamera.id, 'manual retry fallback should choose a different playable nearby camera');
assert(!['세무서4'].includes(retryFallback.name), `manual retry fallback should avoid failed camera, got ${retryFallback.name}`);
assert(nextRetryFallback && nextRetryFallback.id !== retryFallback.id, 'reserved manual retry fallback should choose a non-overlapping camera');
console.log(`[OK] critical camera isolation: ${isolatedTopNames.join(', ')}`);
console.log(`[OK] manual retry fallback: ${failingGuriCamera.name} -> ${retryFallback.name} / ${nextRetryFallback.name}`);

const crownMotel = {
  label: '크라운모텔 / 남양주 화도읍',
  center: { lat: 37.6525, lng: 127.3072 },
  expectedUrbanNearby: ['마석사거리(웹)', '창현A앞4', '송라초교사거리(웹)', '화도읍사무소'],
  outskirtPattern: /수도권제2순환선|서울양양선|IC|JC|터널|영업소/,
};
harness.state.cameraFailures = new Map();
harness.state.center = crownMotel.center;
harness.state.sortMode = 'nearest';
harness.updateNearestCctvs();
const crownTopNames = names(harness.state.nearestCctvs, 8);
const crownMatched = crownMotel.expectedUrbanNearby.filter((name) => crownTopNames.includes(name));
assert(
  crownMatched.length >= 3,
  `${crownMotel.label} nearest regression: expected nearby city cameras, got ${JSON.stringify(crownTopNames)}`
);
assert(
  harness.state.nearestCctvs.slice(0, 4).filter((item) => crownMotel.outskirtPattern.test(item.name)).length <= 1,
  `${crownMotel.label} nearest regression: too many outskirt road cameras in top 4, got ${JSON.stringify(crownTopNames)}`
);
console.log(`[OK] ${crownMotel.label} nearest: ${crownTopNames.join(', ')}`);

const cheonwang = {
  label: '천왕역모아엘가트레뷰아파트 / 안정우선',
  center: { lat: 37.4867, lng: 126.8394 },
  failingIds: ['GITS_6211', 'GITS_6098', 'GITS_6143', 'L902392', 'GITS_9252', 'SPATIC_93'],
};
harness.state.cameraFailures = new Map(
  cheonwang.failingIds
    .map((id) => byId.get(id))
    .filter(Boolean)
    .map((item) => [item.id, {
      id: item.id,
      name: item.name,
      region: harness.inferRegionKey(item),
      source: item.source,
      emergency_level: 'critical',
      failed_for_minutes: 90,
      failure_count: 3,
      last_failed_at: new Date().toISOString(),
      diagnosis: {
        likely_cause: '테스트용 안정우선 실패 후보',
        recommended_action: '안정우선 상위 후보에서 제외',
      },
    }])
);
harness.state.center = cheonwang.center;
harness.state.sortMode = 'stability';
harness.updateNearestCctvs();
const cheonwangTop = harness.state.nearestCctvs.slice(0, 4);
const cheonwangTopNames = names(harness.state.nearestCctvs, 8);
assert(
  cheonwangTop.every((item) => !cheonwang.failingIds.includes(item.id)),
  `${cheonwang.label} regression: failed cameras must not remain in first 4, got ${JSON.stringify(cheonwangTopNames)}`
);
assert(
  cheonwangTop.every((item) => harness.getCameraDisplayHealthMeta(item).tone !== 'danger'),
  `${cheonwang.label} regression: first 4 should avoid red candidates, got ${JSON.stringify(cheonwangTopNames)}`
);
assert(
  cheonwangTop.filter((item) => {
    const url = item.directUrl || item.url || '';
    return url.includes('.m3u8') || url.includes('.mp4') || url.includes('/kb?cctvip=') || url.includes('/jeju?id=');
  }).length >= 2,
  `${cheonwang.label} regression: stability mode should prefer direct playable URLs, got ${JSON.stringify(cheonwangTopNames)}`
);
console.log(`[OK] ${cheonwang.label}: ${cheonwangTopNames.join(', ')}`);

console.log('[OK] ranking regressions passed');
