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
      getCameraPlaybackConfidence
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
assert(harness.inferRegionKey(byId.get('GITS_6739')) === 'GITS', 'GITS cameras should remain in GITS bucket');

const guri = {
  label: '제이헤어 / 경기 구리시 수택동 437-48',
  center: { lat: 37.5959910402814, lng: 127.138034918802 },
  expectedNearby: ['세무서4', '중앙예식장사거리', '돌다리사거리', '삼육고등학교앞', '교문사거리'],
};

for (const sortMode of ['recommended', 'nearest', 'urban']) {
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
assert(isolatedHealth.status === 'CAMERA_CRITICAL', 'camera failure registry should override aggregate health');
assert(isolatedConfidence.tone === 'danger', 'critical camera failure should render a red selector dot');
assert(!isolatedTopNames.includes('세무서4'), `critical camera should be isolated from top 8, got ${JSON.stringify(isolatedTopNames)}`);
console.log(`[OK] critical camera isolation: ${isolatedTopNames.join(', ')}`);

console.log('[OK] ranking regressions passed');
