/**
 * CCTV Viewer 2.0 - Main Application Logic
 * Clean Rewrite: State-Driven, Event Delegation
 */

// === Z3 Cache (its.go.kr 30min snapshot) ===
let z3CacheData = null;
let z3CachePromise = null;
let z3CacheAgeMs = Infinity; // 캐시가 fetch된 이후 경과 시간 (ms)
const Z3_CACHE_STALE_MS = 90 * 60 * 1000; // 90분 이상이면 토큰 만료 가능성 높음
const CCTV_DATA_BUCKET_MS = 30 * 60 * 1000;
const HEALTH_STATUS_BUCKET_MS = 5 * 60 * 1000;
const HEALTH_STALE_MS = 2 * 60 * 60 * 1000;
const CAMERA_FAILURE_RECENT_MS = 3 * 60 * 60 * 1000;
const APP_BUILD_VERSION = '20260519-world-mobile-toggle1';
const SERVICE_BANNER_VISIBLE_MS = 5000;
const PLAYBACK_HEALTH_STORAGE_KEY = 'cctv_playback_health_v1';
const PLAYBACK_HEALTH_SCHEMA_VERSION = 2;
const PLAYBACK_HEALTH_OK_TTL_MS = 15 * 60 * 1000;
const PLAYBACK_HEALTH_PROBLEM_TTL_MS = 45 * 60 * 1000;
const PLAYBACK_HEALTH_MAX_ENTRIES = 160;
const QUALITY_CONFIG = window.CCTV_QUALITY_CONFIG || {};
const QUALITY_TELEMETRY_ENDPOINT = QUALITY_CONFIG.telemetryEndpoint || 'https://cctv-quality.pyw31337.workers.dev/v1/events';
const QUALITY_SUMMARY_URL = QUALITY_CONFIG.summaryUrl || 'https://cctv-quality.pyw31337.workers.dev/v1/summary';
const QUALITY_SUMMARY_FALLBACK_URL = 'data/quality_summary.json';
const WORLD_TOUR_DATA_URL = `data/world_tour_cams.json?v=${APP_BUILD_VERSION}`;
const QUALITY_SUMMARY_BUCKET_MS = 10 * 60 * 1000;
const QUALITY_SUMMARY_TIMEOUT_MS = 1800;
const QUALITY_TELEMETRY_SAMPLE_RATE = 0.35;
const QUALITY_TELEMETRY_DAILY_LIMIT = 20;
const QUALITY_TELEMETRY_QUEUE_LIMIT = 12;
const QUALITY_SLOW_FIRST_FRAME_MS = 8000;
const QUALITY_SORT_STORAGE_KEY = 'cctv_quality_sort_mode';
const TELEMETRY_SAMPLE_STORAGE_KEY = 'cctv_quality_sample_v1';
const TELEMETRY_DAILY_STORAGE_KEY = 'cctv_quality_daily_v1';
const NEAREST_RESULT_LIMIT = 100;
const MAP_MARKER_LIMIT = 50;
const PANEL_OPTION_LIMIT = 20;
const SEARCH_RESULT_LIMIT = 15;
const GEO_CELL_SIZE = 0.08;
const GEO_SEARCH_RING_LIMIT = 8;
const GEO_CANDIDATE_TARGET = 220;
const PLAYBACK_STARTUP_TIMEOUT_MS = 12000;
const JEJU_PLAYBACK_STARTUP_TIMEOUT_MS = 18000;
const PLAYBACK_STALL_TIMEOUT_MS = 9000;
const DAEJEON_MP4_STALL_RECOVERY_MS = 14000;
const STABLE_HLS_STARTUP_TIMEOUT_MS = 22000;
const STABLE_HLS_STALL_TIMEOUT_MS = 14000;
const MANUAL_RETRY_PRIMARY_ATTEMPTS = 3;
const MANUAL_RETRY_FALLBACK_RADIUS_KM = 12;
const DYNAMIC_BACKUP_RADIUS_KM = 8;
const ORACLE_BASE = 'https://158.179.194.163.sslip.io';
const ORACLE_PROXY_BASE = `${ORACLE_BASE}/proxy`;
const JEJU_PROXY_BASE = 'https://158.179.194.163.sslip.io/jeju';
const KB_PROXY_BASE = `${ORACLE_BASE}/kb`;
const LIVE_HEALTH_STATUS_URL = QUALITY_CONFIG.healthStatusUrl || `${ORACLE_BASE}/health-status`;
const MARKER_DANGER_FILTER = 'hue-rotate(145deg) saturate(1.85) contrast(1.08)';
const MARKER_WARN_FILTER = 'hue-rotate(185deg) saturate(1.55) contrast(1.05)';
const QUALITY_SORT_MODES = ['recommended', 'nearest', 'urban', 'traffic', 'stability', 'quality'];
const WORLD_TOUR_REGIONS = ['All', 'North America', 'Europe', 'Asia', 'Oceania', 'South America', 'Africa'];
const WORLD_TOUR_REGION_LABELS = {
    All: 'All',
    'North America': 'North America',
    Europe: 'Europe',
    Asia: 'Asia',
    Oceania: 'Oceania',
    'South America': 'South America',
    Africa: 'Africa'
};
const WORLD_TOUR_REGION_COLORS = {
    'North America': '#38bdf8',
    Europe: '#a78bfa',
    Asia: '#34d399',
    Oceania: '#22d3ee',
    'South America': '#f59e0b',
    Africa: '#fb7185'
};
const WORLD_TOUR_SOURCE_LABELS = {
    earthcam: 'EarthCam',
    skyline: 'Skyline',
    cctvworld: 'CCTV World',
    tabi: 'TabiCam',
    webcamera24: 'WebCamera24',
    youtube: 'YouTube',
    external: 'External'
};
const URBAN_CONTEXT_PATTERN = /(시청|구청|군청|읍사무소|면사무소|동부출장소|행정복지|주민센터|세무서|법원|경찰서|소방서|보건소|사거리|삼거리|네거리|교차로|로터리|터미널|역|아파트|시장|학교|초교|초등|중학교|고교|병원|마트|상가|대로변|단지내|시내|중앙|읍내)/;
const OUTSKIRT_CONTEXT_PATTERN = /(고속|고속도로|서울양양선|수도권제|국도|IC|JC|TG|영업소|터널|램프|휴게소|졸음쉼터|분기점|진입로|외부|하이패스)/i;
const TRAFFIC_CONTEXT_PATTERN = /(고속|고속도로|도시고속|자동차전용|국도|지방도|IC|JC|TG|영업소|나들목|분기점|램프|터널|휴게소|졸음쉼터|하이패스|외곽|순환|우회|간선|산업도로|대교|교량|지하차도|고가도로)/i;
const SCENIC_CONTEXT_PATTERN = /(해변|해안|항구|포구|전망|공원|오름|산책|관광|해수욕장|방파제|등대|섬|계곡|정자|캠핑|휴양|하천|강변|왕숙천|중랑천|탄천|한강|호수)/;
const BLOCKED_YOUTUBE_VIDEO_IDS = new Set([
    'bKcdTWp6akg' // [YouTube] 대전 엑스포 한빛광장: owner-side private video.
]);

let worldTourMapLibraryPromise = null;
let worldTourLeafletMap = null;
let worldTourLeafletMarkers = [];

const REGION_LABELS = {
    BUSAN: '부산',
    CCTVWORLD: 'CCTV월드',
    CHUNGJU: '충주',
    DAEGU: '대구',
    DAEJEON: '대전',
    FITIC: 'FITIC',
    GANGWON: '강원',
    GGEX: 'GGEX',
    GIGAEYES: '기가아이즈',
    GITS: '경기 ITS',
    GOYANG: '고양',
    GWANGJU: '광주',
    ICITS: '인천도시공사',
    INCHEON: '인천',
    JEJU: '제주',
    KBS: 'KBS',
    KNPS: '국립공원',
    NOWJEJU: '나우제주',
    NTIC: '고속도로',
    PAJU: '파주',
    SEJONG: '세종',
    SPATIC: '서울교통정보',
    TOPIS: 'TOPIS',
    TRENDWORLD: '트렌드월드',
    ULLEUNG: '울릉',
    ULSAN: '울산',
    UTIC: 'UTIC',
    UTIC_DIRECT: 'UTIC 직접영상',
    UTIC_LEGACY: 'UTIC 구형',
    UTIC_Z3: 'UTIC 국도',
    YT: 'YouTube'
};

const REGION_ALIASES = {
    BUSAN_ITS: 'BUSAN',
    DAEGU: 'DAEGU',
    GANGWON: 'GANGWON',
    GIGAEYES: 'GIGAEYES',
    GITS: 'GITS',
    GOYANG: 'GOYANG',
    GWANGJU: 'GWANGJU',
    ICITS: 'ICITS',
    INCHEON_ITS: 'INCHEON',
    JEJU: 'JEJU',
    KBS: 'KBS',
    KNPS: 'KNPS',
    NOWJEJU: 'NOWJEJU',
    NTIC: 'NTIC',
    SEJONG: 'SEJONG',
    SPATIC: 'SPATIC',
    TOPIS: 'TOPIS',
    TRENDWORLD: 'TRENDWORLD',
    ULLEUNG: 'ULLEUNG',
    ULSAN: 'ULSAN',
    YOUTUBE: 'YT',
    YT_CUSTOM: 'YT'
};

const SOURCE_QUALITY_SCORES = {
    TOPIS: 0.92,
    BUSAN_ITS: 0.9,
    DAEGU: 0.89,
    SPATIC: 0.89,
    GITS: 0.87,
    INCHEON_ITS: 0.86,
    GANGWON: 0.83,
    KBS: 0.82,
    NOWJEJU: 0.8,
    JEJU: 0.91,
    NTIC: 0.78,
    UTIC: 0.7,
    YOUTUBE: 0.96,
    YT_CUSTOM: 0.96
};

async function loadZ3Cache() {
    if (z3CacheData) return z3CacheData;
    if (z3CachePromise) return z3CachePromise;
    // 30분마다 cache-bust (워크플로 30분 주기와 동기화)
    z3CachePromise = fetch(`data/z3_cache.json?t=${Math.floor(Date.now() / 1800000)}`)
        .then(r => r.json())
        .then(json => {
            z3CacheData = json.data || json;
            const fetched = json.fetched || null;
            z3CacheAgeMs = fetched ? Date.now() - new Date(fetched).getTime() : Infinity;
            const count = Object.keys(z3CacheData).length;
            const ageMin = Math.round(z3CacheAgeMs / 60000);
            console.log(`[Z3] Cache loaded: ${count} entries (fetched: ${fetched}, age: ${ageMin}min)`);
            if (z3CacheAgeMs > Z3_CACHE_STALE_MS) {
                console.warn(`[Z3] Cache is ${ageMin}min old — tokens likely expired, will skip to strategy3`);
            }
            return z3CacheData;
        })
        .catch(e => {
            console.warn('[Z3] Cache load failed:', e);
            z3CachePromise = null; // allow retry
            return {};
        });
    return z3CachePromise;
}
async function getZ3StreamUrl(cctvip) {
    const cache = await loadZ3Cache();
    // 캐시가 너무 오래됐으면 만료된 토큰 사용 안 함
    if (z3CacheAgeMs > Z3_CACHE_STALE_MS) return null;
    const rawUrl = cache[String(cctvip)];
    if (!rawUrl) return null;
    // 토큰 URL 원형 유지 (http:// 그대로) — /z3가 redirect 체인 해결 후 master m3u8 반환
    let tokenUrl = rawUrl.startsWith('//') ? 'http:' + rawUrl : rawUrl;
    return `https://cctv-proxy.pyw213.workers.dev/z3?url=${encodeURIComponent(tokenUrl)}`;
}

function proxyWithOracle(targetUrl) {
    return `${ORACLE_PROXY_BASE}?url=${encodeURIComponent(targetUrl)}`;
}

function normalizeResolvedZ3StreamUrl(streamUrl) {
    if (!streamUrl) return streamUrl;

    const normalized = streamUrl.trim()
        .replace(/^https:\/\/cctvsec\.ktict\.co\.kr:8081/i, 'http://cctvsec.ktict.co.kr:8081');

    if (/^http:\/\/cctvsec\.ktict\.co\.kr:8081/i.test(normalized)) {
        return proxyWithOracle(normalized);
    }

    return normalized;
}

// === State ===
const state = {
    mode: 'video', // 'video' | 'map'
    center: { lat: 37.5559, lng: 126.9723 }, // Seoul Station
    keyword: '서울역',
    cctvData: [],
    cctvById: new Map(),
    nearestCctvs: [],
    cameraPlaybackHealth: new Map(),
    regionHealth: {},
    cameraFailures: new Map(),
    healthSnapshot: null,
    healthSnapshotStale: false,
    qualitySummary: null,
    qualitySummaryLoaded: false,
    qualityTelemetryQueue: [],
    worldTourCams: null,
    selectedWorldTourId: null,
    worldTourRegion: 'All',
    worldTourViewMode: 'map',
    geoIndex: new Map(),
    markers: [], // Array to store Kakao map markers
    mapInitialized: false,
    searchMarker: null, // Reference to the red marker
    initialSelectionId: null,
    activeCctvId: null,
    serviceBannerTimer: null,
    serviceBannerCountdownTimer: null,
    serviceBannerDismissedKey: null,
    sortMode: 'recommended'
};

let map = null;
const SEARCH_MARKER_SRC = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png';
const YOUTUBE_MARKER_SRC = 'https://img.icons8.com/color/48/youtube-play.png';
const markerImageCache = new Map();
let playbackHealthPersistTimer = null;
let qualityTelemetryFlushTimer = null;


// === DOM References (Cached) ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Initialization ===
document.addEventListener('DOMContentLoaded', async () => {
    console.log('CCTV Viewer 2.0 Initializing...');

    await Promise.all([loadCctvData(), loadHealthStatus()]);
    restoreInitialViewState();
    restoreQualityPreferences();
    hydrateStoredPlaybackHealth();

    // Setup Event Listeners
    setupEventListeners();
    renderQualityControls();

    // Initial State
    updateNearestCctvs();
    renderServiceStatusBanner();
    renderVideoGrid();
    switchMode(state.mode);
    syncUrlState();

    if (state.initialSelectionId) {
        const initialCctv = findCctvById(state.initialSelectionId);
        if (initialCctv) {
            openVideoLayer(initialCctv);
        }
    }

    console.log('Initialization Complete.');

    loadQualitySummary().then((loaded) => {
        if (!loaded) return;
        updateNearestCctvs();
        renderServiceStatusBanner();
        renderVideoGrid();
        renderMapMarkers();
    });
});

// === Data Loading ===
async function loadCctvData() {
    try {
        const cacheBucket = Math.floor(Date.now() / CCTV_DATA_BUCKET_MS);
        const response = await fetch(`cctv_data.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const rawData = await response.json();
        state.cctvData = rawData.filter(cctv => !shouldExcludeCctv(cctv));
        buildGeoIndex(state.cctvData);
        console.log(`Loaded ${state.cctvData.length} CCTV entries.`, rawData.length !== state.cctvData.length ? `(excluded ${rawData.length - state.cctvData.length})` : '');
    } catch (error) {
        console.error('Failed to load CCTV data:', error);
        state.cctvData = [];
        state.cctvById = new Map();
        state.geoIndex = new Map();
    }
}

async function loadHealthStatus() {
    const cacheBucket = Math.floor(Date.now() / HEALTH_STATUS_BUCKET_MS);
    const urls = [
        LIVE_HEALTH_STATUS_URL ? `${LIVE_HEALTH_STATUS_URL}?v=${APP_BUILD_VERSION}&t=${cacheBucket}` : null,
        `data/status.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`
    ].filter(Boolean);

    for (const url of urls) {
        try {
            const snapshot = await fetchJsonWithTimeout(url, 2200);
            state.healthSnapshot = snapshot;
            state.regionHealth = state.healthSnapshot.regions || {};
            state.cameraFailures = buildCameraFailureMap(state.healthSnapshot.camera_failures);
            state.healthSnapshotStale = isStaleHealthTimestamp(snapshot.last_updated);
            if (state.healthSnapshotStale) {
                console.warn('Using stale health status snapshot:', snapshot.last_updated);
            }
            return;
        } catch (error) {
            console.debug('[Health] Status load skipped:', url, error.message || error);
        }
    }

    console.warn('Failed to load all health status sources.');
    state.healthSnapshot = null;
    state.regionHealth = {};
    state.cameraFailures = new Map();
    state.healthSnapshotStale = false;
}

async function fetchJsonWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(url, {
            cache: 'no-store',
            signal: controller.signal
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } finally {
        clearTimeout(timer);
    }
}

async function loadQualitySummary() {
    const cacheBucket = Math.floor(Date.now() / QUALITY_SUMMARY_BUCKET_MS);
    const urls = [
        QUALITY_SUMMARY_URL ? `${QUALITY_SUMMARY_URL}?v=${APP_BUILD_VERSION}&t=${cacheBucket}` : null,
        `${QUALITY_SUMMARY_FALLBACK_URL}?v=${APP_BUILD_VERSION}&t=${cacheBucket}`
    ].filter(Boolean);

    for (const url of urls) {
        try {
            const summary = await fetchJsonWithTimeout(url, QUALITY_SUMMARY_TIMEOUT_MS);
            applyQualitySummary(summary);
            return true;
        } catch (error) {
            console.debug('[Quality] Summary load skipped:', url, error.message || error);
        }
    }

    return false;
}

function applyQualitySummary(summary) {
    if (!summary || typeof summary !== 'object') return;
    state.qualitySummary = {
        generated_at: summary.generated_at || summary.generatedAt || null,
        cameras: summary.cameras || {},
        sources: summary.sources || {},
        regions: summary.regions || {}
    };
    state.qualitySummaryLoaded = true;
}

function restoreInitialViewState() {
    const params = new URLSearchParams(window.location.search);
    const lat = parseFloat(params.get('lat'));
    const lng = parseFloat(params.get('lng'));
    const name = params.get('name');
    const mode = params.get('mode');
    const cctvId = params.get('cctv');

    if (Number.isFinite(lat) && Number.isFinite(lng)) {
        state.center = { lat, lng };
        state.keyword = name || state.keyword;
    } else {
        const history = getSearchHistory();
        if (history.length > 0 && history[0].lat && history[0].lng) {
            state.center = { lat: history[0].lat, lng: history[0].lng };
            state.keyword = history[0].name || state.keyword;
        }
    }

    if (mode === 'map' || mode === 'video') {
        state.mode = mode;
    }

    if (cctvId) {
        state.initialSelectionId = cctvId;
        const selected = findCctvById(cctvId);
        if (selected && (!Number.isFinite(lat) || !Number.isFinite(lng))) {
            state.center = { lat: selected.lat, lng: selected.lng };
            state.keyword = selected.name || state.keyword;
        }
    }

    $('#search-input').value = state.keyword;
}

function restoreQualityPreferences() {
    try {
        const storedSortMode = localStorage.getItem(QUALITY_SORT_STORAGE_KEY);
        if (QUALITY_SORT_MODES.includes(storedSortMode)) {
            state.sortMode = storedSortMode;
        }
        localStorage.removeItem('cctv_low_data_mode');
    } catch {
        state.sortMode = 'recommended';
    }
}

function renderQualityControls() {
    const sortSelect = $('#quality-sort-select');
    if (sortSelect) sortSelect.value = state.sortMode;
}

function setSortMode(mode) {
    if (!QUALITY_SORT_MODES.includes(mode)) return;
    state.sortMode = mode;
    try {
        localStorage.setItem(QUALITY_SORT_STORAGE_KEY, mode);
    } catch {}

    updateNearestCctvs();
    renderServiceStatusBanner();
    renderVideoGrid();
    renderMapMarkers();
    syncUrlState();
}

// === Event Listeners (Delegation) ===
function setupEventListeners() {
    // Segment Control (Video/Map Toggle)
    $('#segment-control').addEventListener('click', (e) => {
        const btn = e.target.closest('.segment-btn');
        if (btn) {
            const mode = btn.dataset.mode;
            if (mode) switchMode(mode);
        }
    });

    // Search Input
    const searchInput = $('#search-input');
    searchInput.addEventListener('focus', showSearchHistory);
    searchInput.addEventListener('input', debounce(handleSearchInput, 300));
    searchInput.addEventListener('keydown', (e) => {
        // Prevent double-submission during IME composition (CJK)
        if (e.isComposing || e.keyCode === 229) return;

        if (e.key === 'Enter') {
            e.preventDefault(); // Prevent default form submission if any
            handleSearchSubmit();
        }
    });

    // Search Clear
    $('#search-clear').addEventListener('click', () => {
        searchInput.value = '';
        searchInput.focus();
        showSearchHistory();
    });

    // Dim Overlay
    $('#dim-overlay').addEventListener('click', closeAllOverlays);

    // Weather
    $('#weather-btn').addEventListener('click', toggleWeather);
    $('#weather-close').addEventListener('click', closeWeather);

    const sortSelect = $('#quality-sort-select');
    if (sortSelect) {
        sortSelect.addEventListener('change', () => {
            setSortMode(sortSelect.value);
        });
    }

    // Video Layer
    $('#video-layer-close').addEventListener('click', closeVideoLayer);
    $('#video-layer').addEventListener('click', (e) => {
        if (e.target.id === 'video-layer') closeVideoLayer();
    });

    // Location Button
    $('#location-btn').addEventListener('click', handleCurrentLocation);

    // Search Results Click (Delegation for items, bookmark, delete)
    $('#search-results').addEventListener('click', (e) => {
        const item = e.target.closest('.search-result-item');
        if (!item) return;

        const actionBtn = e.target.closest('[data-action]');
        if (actionBtn) {
            e.stopPropagation();
            const itemData = {
                lat: parseFloat(item.dataset.lat),
                lng: parseFloat(item.dataset.lng),
                name: item.dataset.name,
                address: item.dataset.address
            };

            if (actionBtn.dataset.action === 'bookmark') {
                toggleBookmark(itemData);
            } else if (actionBtn.dataset.action === 'delete') {
                deleteHistoryItem(itemData.name);
            }
            return;
        }

        selectSearchResult(item);
    });

    // Mobile Keyboard Handling
    setupMobileKeyboardHandling();

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') flushQualityTelemetry();
    });
    window.addEventListener('pagehide', flushQualityTelemetry);
}

// === Mode Switching ===
function switchMode(mode) {
    state.mode = mode;

    // Update Button States
    $$('.segment-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    // Update Views
    $$('.view').forEach(view => view.classList.remove('active'));
    $(`#${mode}-view`).classList.add('active');

    // Move Indicator
    updateSegmentIndicator();
    updateContextActionButton();

    // Map Initialization (Lazy)
    if (mode === 'map' && !state.mapInitialized) {
        initMap();
    } else if (mode === 'map' && map) {
        map.relayout();
        map.setCenter(new kakao.maps.LatLng(state.center.lat, state.center.lng));
    }

    syncUrlState();
}

function updateContextActionButton() {
    const btn = $('#weather-btn');
    if (!btn) return;

    const isWorldTour = state.mode === 'map';
    btn.classList.toggle('world-tour-btn', isWorldTour);
    btn.title = isWorldTour ? '세계 관광 라이브' : '주간 날씨';
    btn.setAttribute('aria-label', isWorldTour ? '세계 관광 라이브' : '주간 날씨');
    btn.innerHTML = isWorldTour ? `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20" />
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            <path d="m10 9 5 3-5 3z" />
        </svg>
    ` : `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
        </svg>
    `;

    if ($('#weather-layer')?.classList.contains('active')) {
        closeWeather({ restoreDomesticMap: false });
    }
}

function updateSegmentIndicator() {
    const activeBtn = $('.segment-btn.active');
    const indicator = $('.segment-indicator');

    if (activeBtn && indicator) {
        const left = activeBtn.offsetLeft;
        const width = activeBtn.offsetWidth;
        const height = activeBtn.offsetHeight;

        indicator.style.transform = `translateX(${left - 4}px)`; // -4 for padding
        indicator.style.width = `${width}px`;
        indicator.style.height = `${height}px`;
    }
}

// === Search ===
function showSearchHistory() {
    // Close weather popup when opening search
    closeWeather();

    const resultsEl = $('#search-results');
    // Filter out undefined or invalid items
    const history = getSearchHistory().filter(item => item && item.name && item.name !== 'undefined');
    const bookmarks = getBookmarks().filter(item => item && item.name && item.name !== 'undefined');

    let html = '';

    // Bookmarks Section (always show)
    html += `<div class="search-section-title">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M5 5c0-1.1.9-2 2-2h10a2 2 0 0 1 2 2v16l-7-3.5L5 21V5z"/></svg>
        북마크
    </div>`;
    if (bookmarks.length > 0) {
        html += bookmarks.map(item => renderSearchItem(item, true)).join('');
    } else {
        html += '<div class="search-section-empty">최근 북마크된 주소가 없습니다</div>';
    }

    // History Section (always show)
    html += `<div class="search-section-title">최근 검색</div>`;
    if (history.length > 0) {
        html += history.map(item => renderSearchItem(item, false)).join('');
    } else {
        html += '<div class="search-section-empty">최근 검색 주소가 없습니다</div>';
    }

    resultsEl.innerHTML = html;
    resultsEl.classList.add('active');
    $('#dim-overlay').classList.add('active');
}

function renderSearchItem(item, isBookmarked) {
    const bookmarkClass = isBookmarked ? 'active' : '';
    return `
        <div class="search-result-item" data-lat="${item.lat}" data-lng="${item.lng}" data-name="${item.name}" data-address="${item.address || ''}">
            <div class="search-result-info">
                <div class="search-result-name">${item.name}</div>
                <div class="search-result-address">${item.address || ''}</div>
            </div>
            <div class="search-result-actions">
                <button class="btn-bookmark ${bookmarkClass}" data-action="bookmark" title="북마크">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
                        <path d="M5 5c0-1.1.9-2 2-2h10a2 2 0 0 1 2 2v16l-7-3.5L5 21V5z"/>
                    </svg>
                </button>
                <button class="btn-delete" data-action="delete" title="삭제">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

async function handleSearchInput(e) {
    const query = e.target.value.trim();
    if (query.length < 1) {
        showSearchHistory();
        return;
    }

    // Debounce is handled by event listener, but ensuring async behavior
    try {
        const results = await performHybridSearch(query);
        renderSearchResults(results);
    } catch (error) {
        console.error("Search failed:", error);
    }
}

async function handleSearchSubmit() {
    const query = $('#search-input').value.trim();
    if (!query) return;

    // Hide mobile keyboard
    $('#search-input').blur();

    try {
        const results = await performHybridSearch(query);
        renderSearchResults(results);

        // If we want to auto-select ONLY if it's a perfect Region match?
        // User disliked auto-select for "Guri City Hall" -> "Meat Shop".
        // But for "Chuncheon", if we get "Chuncheon-si" (Region) as top result, maybe we DO want to move there?
        // For now, let's Stick to "Always Show List" as requested for stability.

    } catch (error) {
        console.error("Search submit failed:", error);
    }
}

// === Hybrid Search Logic ===
function performHybridSearch(query) {
    return new Promise(async (resolve) => {
        const ps = new kakao.maps.services.Places();
        const geocoder = new kakao.maps.services.Geocoder();

        // 1. Places Search
        const placePromise = new Promise((res) => {
            ps.keywordSearch(query, (data, status) => {
                if (status === kakao.maps.services.Status.OK) {
                    res(data);
                } else {
                    res([]);
                }
            });
        });

        // 2. Address/Region Search
        const regionPromise = new Promise((res) => {
            geocoder.addressSearch(query, (data, status) => {
                if (status === kakao.maps.services.Status.OK) {
                    // Normalize to match Place format
                    const normalized = data.map(item => ({
                        place_name: item.address_name, // Use address as name for regions
                        address_name: item.address_name,
                        y: item.y,
                        x: item.x,
                        isRegion: true // Flag to style differently if needed
                    }));
                    res(normalized);
                } else {
                    res([]);
                }
            });
        });

        // Execute Parallel
        const [places, regions] = await Promise.all([placePromise, regionPromise]);

        // Merge: Regions FIRST, then Places
        // Deduplicate?
        // Sometimes Region "Chuncheon" and Place "Chuncheon City Hall" might coexist.
        // We want generic "Chuncheon-si" (Region) at top.

        const combined = [...regions, ...places];
        resolve(combined);
    });
}

function renderSearchResults(data) {
    const resultsEl = $('#search-results');

    if (data.length > 0) {
        resultsEl.innerHTML = data.slice(0, SEARCH_RESULT_LIMIT).map(place => {
            const icon = place.isRegion ? '🏙️' : '📍';
            return `
            <div class="search-result-item" data-lat="${place.y}" data-lng="${place.x}" data-name="${place.place_name}" data-address="${place.address_name || ''}">
                <div class="search-result-icon">${icon}</div>
                <div class="search-result-info">
                    <div class="search-result-name">${place.place_name}</div>
                    <div class="search-result-address">${place.address_name || ''}</div>
                </div>
            </div>
        `}).join('');
        resultsEl.classList.add('active');
        $('#dim-overlay').classList.add('active');
    } else {
        resultsEl.innerHTML = '<div class="search-empty">검색 결과가 없습니다</div>';
        resultsEl.classList.add('active');
    }
}

function selectSearchResult(item) {
    const lat = parseFloat(item.dataset.lat);
    const lng = parseFloat(item.dataset.lng);
    const name = item.dataset.name;
    const address = item.dataset.address || '';

    selectPlace(lat, lng, name, address);
}

function selectPlace(lat, lng, name, address) {
    state.center = { lat, lng };
    state.keyword = name;

    $('#search-input').value = name;
    closeAllOverlays();

    // Save to History
    saveSearchHistory({ lat, lng, name, address });

    // Update CCTVs
    updateNearestCctvs();
    renderServiceStatusBanner();
    renderVideoGrid();
    renderMapMarkers(); // Update markers on map

    // Update Map if Active
    if (map) {
        const moveLatLon = new kakao.maps.LatLng(lat, lng);
        map.setCenter(moveLatLon);
    }

    // Update Search Marker (Red Pin)
    updateSearchMarker(lat, lng);
    syncUrlState();
}

// === Geolocation ===
async function handleCurrentLocation() {
    const btn = $('#location-btn');
    if (!navigator.geolocation) {
        alert('이 브라우저는 위치 정보를 지원하지 않습니다.');
        return;
    }

    btn.classList.add('loading');

    navigator.geolocation.getCurrentPosition(async (position) => {
        const { latitude, longitude } = position.coords;

        // Use Geocoder to get address name
        const geocoder = new kakao.maps.services.Geocoder();
        geocoder.coord2Address(longitude, latitude, (result, status) => {
            btn.classList.remove('loading');
            if (status === kakao.maps.services.Status.OK) {
                const addr = result[0].address;
                const addressName = addr.address_name;
                // Prefer a slightly more descriptive name if possible
                const name = addr.region_3depth_name || addr.region_2depth_name || '현재 위치';

                selectPlace(latitude, longitude, name, addressName);
            } else {
                // Fallback if Geocoder fails
                selectPlace(latitude, longitude, '현재 위치', '');
            }
        });
    }, (error) => {
        btn.classList.remove('loading');
        console.error('Geolocation error:', error);
        const msg = error.code === 1 ? '위치 정보 권한이 거부되었습니다.' : '위치 정보를 가져오는데 실패했습니다.';
        alert(msg);
    }, {
        enableHighAccuracy: true,
        timeout: 5000,
        maximumAge: 0
    });
}

function buildGeoIndex(cctvList) {
    const index = new Map();
    const cctvById = new Map();

    cctvList.forEach(cctv => {
        if (cctv.id) {
            cctvById.set(cctv.id, cctv);
        }
        if (!Number.isFinite(cctv.lat) || !Number.isFinite(cctv.lng)) return;

        const key = getGeoCellKey(cctv.lat, cctv.lng);
        if (!index.has(key)) {
            index.set(key, []);
        }
        index.get(key).push(cctv);
    });

    state.geoIndex = index;
    state.cctvById = cctvById;
}

function getGeoCellKey(lat, lng) {
    const latCell = Math.floor(lat / GEO_CELL_SIZE);
    const lngCell = Math.floor(lng / GEO_CELL_SIZE);
    return `${latCell}:${lngCell}`;
}

function getNearbyCandidates(lat, lng, targetCount) {
    if (!state.geoIndex || state.geoIndex.size === 0) {
        return state.cctvData;
    }

    const latCell = Math.floor(lat / GEO_CELL_SIZE);
    const lngCell = Math.floor(lng / GEO_CELL_SIZE);
    const candidates = [];
    const seenKeys = new Set();

    for (let ring = 0; ring <= GEO_SEARCH_RING_LIMIT && candidates.length < targetCount; ring += 1) {
        for (let latOffset = -ring; latOffset <= ring; latOffset += 1) {
            for (let lngOffset = -ring; lngOffset <= ring; lngOffset += 1) {
                if (ring > 0 && Math.max(Math.abs(latOffset), Math.abs(lngOffset)) !== ring) {
                    continue;
                }

                const key = `${latCell + latOffset}:${lngCell + lngOffset}`;
                if (seenKeys.has(key)) continue;
                seenKeys.add(key);

                const cellItems = state.geoIndex.get(key);
                if (cellItems && cellItems.length > 0) {
                    candidates.push(...cellItems);
                }
            }
        }
    }

    return candidates.length >= targetCount ? candidates : state.cctvData;
}

function getUrlParam(url, key) {
    if (!url) return null;

    try {
        return new URL(url, window.location.origin).searchParams.get(key);
    } catch (error) {
        return null;
    }
}

function getYouTubeVideoId(url) {
    if (!url) return null;

    try {
        const parsed = new URL(url, window.location.origin);
        const host = parsed.hostname.replace(/^www\./, '');
        if (host === 'youtu.be') return parsed.pathname.replace(/^\//, '').split('/')[0] || null;
        if (host.endsWith('youtube.com')) {
            if (parsed.searchParams.get('v')) return parsed.searchParams.get('v');
            const embedMatch = parsed.pathname.match(/\/embed\/([^/?#]+)/);
            if (embedMatch) return embedMatch[1];
            const shortsMatch = parsed.pathname.match(/\/shorts\/([^/?#]+)/);
            if (shortsMatch) return shortsMatch[1];
        }
    } catch {
        const match = String(url).match(/(?:v=|youtu\.be\/|embed\/)([A-Za-z0-9_-]{6,})/);
        if (match) return match[1];
    }

    return null;
}

function shouldExcludeCctv(cctv) {
    if (!cctv) return true;

    const url = cctv.directUrl || cctv.url || '';
    const videoId = getYouTubeVideoId(url);
    if (videoId && BLOCKED_YOUTUBE_VIDEO_IDS.has(videoId)) return true;

    return false;
}

function normalizeDaejeonStreamId(rawId) {
    const raw = String(rawId || '').trim();
    if (!raw) return null;

    const daejeonMatch = raw.match(/DAEJEON_(CCTV\d+)/i);
    const cctvMatch = raw.match(/^CCTV(\d+)$/i) || (daejeonMatch ? daejeonMatch[1].match(/^CCTV(\d+)$/i) : null);
    if (cctvMatch) return `CTV${cctvMatch[1].padStart(4, '0')}`;

    const ctvMatch = raw.match(/^CTV(\d+)$/i);
    if (ctvMatch) return `CTV${ctvMatch[1].padStart(4, '0')}`;

    return null;
}

function getDaejeonStreamId(cctv, url, selectedOriginalId) {
    const candidates = [
        getUrlParam(url, 'cctvpasswd'),
        getUrlParam(url, 'id'),
        selectedOriginalId,
        cctv && cctv.original_id,
        cctv && cctv.id
    ];

    for (const candidate of candidates) {
        const streamId = normalizeDaejeonStreamId(candidate);
        if (streamId) return streamId;
    }

    return null;
}

function getDaejeonMediaPath(url, cctvIp, streamId) {
    const ip = String(cctvIp || getUrlParam(url, 'cctvip') || '');
    if (ip === '118' || url.includes('210.99.67.118') || url.includes('192.168.12.101')) return '01';
    if (ip === '119' || url.includes('210.99.67.119') || url.includes('192.168.12.102')) return '02';

    const numMatch = String(streamId || '').match(/CTV0*(\d+)/i);
    if (numMatch) {
        const num = Number(numMatch[1]);
        if (Number.isFinite(num)) return num < 51 ? '01' : '02';
    }

    return '01';
}

function isDaejeonDirectMp4Candidate(cctv, url, selectedSource, selectedKind, selectedCctvIp, selectedOriginalId) {
    if (!cctv || !url) return false;
    if (sourceLooksLikeDaejeon(selectedSource, selectedKind, cctv, url)) {
        return !!getDaejeonStreamId(cctv, url, selectedOriginalId);
    }
    return false;

    function sourceLooksLikeDaejeon(source, kind, item, itemUrl) {
        if (item.urlType === 'daejeon_mp4_dynamic' || source === 'DAEJEON_ITS') return true;
        if (source === 'UTIC' && kind === 'E' && inferRegionKey(item) === 'DAEJEON') return true;
        if (source === 'UTIC' && selectedCctvIp && ['118', '119'].includes(String(selectedCctvIp))) return true;
        return itemUrl.includes('traffic.daejeon.go.kr') || itemUrl.includes('tportal.daejeon.go.kr');
    }
}

async function resolveJejuPlaybackUrl(url) {
    if (!url || !url.includes('/jeju')) return url;

    const response = await fetch(url, {
        cache: 'no-store',
        method: 'HEAD',
        redirect: 'follow'
    });
    if (!response.ok) {
        throw new Error(`jeju ${response.status}`);
    }
    return response.url || url;
}

function isRawIpStreamUrl(url) {
    return /^https?:\/\/\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?/i.test(url || '');
}

function isJejuUticProxyable(cctv) {
    const url = cctv ? (cctv.directUrl || cctv.url || '') : '';
    const source = cctv ? (cctv.source || '') : '';
    const kind = getUrlParam(url, 'kind');
    const streamId = getUrlParam(url, 'id');
    return source === 'UTIC' && kind === 'K' && !!streamId && inferRegionKey(cctv) === 'JEJU';
}

function isUnsupportedBrowserStream(cctv) {
    const url = cctv ? (cctv.directUrl || cctv.url || '') : '';
    const source = cctv ? (cctv.source || '') : '';
    const kind = getUrlParam(url, 'kind');
    if (isJejuUticProxyable(cctv)) return false;
    return source === 'UTIC' && kind === 'K';
}

function inferRegionKey(cctv) {
    if (!cctv) return 'UNKNOWN';

    const id = cctv.id || '';
    const name = cctv.name || '';
    const source = cctv.source || '';
    const prefix = id.includes('_') ? id.split('_')[0] : null;
    const daejeonInlineId = getUrlParam(cctv.directUrl || cctv.url || '', 'id');

    if (cctv.regionKey) return cctv.regionKey;
    if (cctv.urlType === 'daejeon_mp4_dynamic' || id.startsWith('DAEJEON_') || source === 'DAEJEON_ITS') {
        return 'DAEJEON';
    }
    if (source === 'UTIC' && (id.startsWith('E07') || name.includes('대전시'))) {
        return 'DAEJEON';
    }
    if (source === 'UTIC' && daejeonInlineId && daejeonInlineId.startsWith('CCTV')) {
        return 'DAEJEON';
    }
    if (source === 'UTIC' && (id.startsWith('L380') || name.includes('제주'))) {
        return 'JEJU';
    }
    if (source === 'JEJU') return 'JEJU';
    if (source === 'UTIC' && id.startsWith('L12')) return 'PAJU';
    if (source === 'UTIC') {
        const kind = getUrlParam(cctv.directUrl || cctv.url || '', 'kind');
        if (kind === 'Z3') return 'UTIC_Z3';
        if (['EE', 'EEE', 'KB'].includes(kind)) return 'UTIC_DIRECT';
        return 'UTIC_LEGACY';
    }
    if (prefix && REGION_LABELS[prefix]) return prefix;
    if (REGION_ALIASES[source]) return REGION_ALIASES[source];
    if (id.includes('_')) return id.split('_')[0];
    if (source) return source;
    return 'UNKNOWN';
}

function getRegionLabel(regionKey) {
    return REGION_LABELS[regionKey] || regionKey || '미분류';
}

function buildCameraFailureMap(failures) {
    if (!failures || typeof failures !== 'object') return new Map();
    return new Map(Object.entries(failures).filter(([, value]) => value && typeof value === 'object'));
}

function getCameraFailureRecord(cctv) {
    if (!cctv || !cctv.id || !state.cameraFailures) return null;
    const record = state.cameraFailures.get(cctv.id);
    if (!record) return null;

    const lastFailedAt = Date.parse(record.last_failed_at || record.lastFailedAt || '');
    if (!Number.isFinite(lastFailedAt)) return record;
    if (Date.now() - lastFailedAt > CAMERA_FAILURE_RECENT_MS) return null;
    return record;
}

function getCameraFailureHealthMeta(cctv, regionKey, lastUpdated) {
    const record = getCameraFailureRecord(cctv);
    if (!record) return null;

    const level = record.emergency_level || 'watch';
    const diagnosis = record.diagnosis || {};
    const failedFor = Number(record.failed_for_minutes || 0);
    const failureCount = Number(record.failure_count || 0);
    const cause = diagnosis.likely_cause || record.last_reason || '최근 자동 점검에서 반복 실패가 감지되었습니다';
    const action = diagnosis.recommended_action ? ` 권장 조치: ${diagnosis.recommended_action}` : '';

    if (level === 'critical') {
        return {
            regionKey,
            status: 'CAMERA_CRITICAL',
            shortLabel: '장기 장애',
            longLabel: `${cctv.name || '이 CCTV'}는 ${failedFor}분 동안 ${failureCount}회 실패했습니다. 원인: ${cause}.${action}`,
            tone: 'danger',
            penalty: 14,
            lastUpdated: record.last_failed_at || lastUpdated
        };
    }

    if (level === 'investigate') {
        return {
            regionKey,
            status: 'CAMERA_INVESTIGATE',
            shortLabel: '반복 실패',
            longLabel: `${cctv.name || '이 CCTV'}는 최근 ${failureCount}회 실패했습니다. 원인: ${cause}.${action}`,
            tone: 'danger',
            penalty: 10,
            lastUpdated: record.last_failed_at || lastUpdated
        };
    }

    return {
        regionKey,
        status: 'CAMERA_WATCH',
        shortLabel: '점검 주의',
        longLabel: `${cctv.name || '이 CCTV'}는 최근 점검에서 실패했습니다. 원인: ${cause}.`,
        tone: 'warn',
        penalty: 4,
        lastUpdated: record.last_failed_at || lastUpdated
    };
}

function getCameraQualitySummary(cctv) {
    if (!cctv || !state.qualitySummary || !state.qualitySummary.cameras) return null;
    return state.qualitySummary.cameras[cctv.id] || null;
}

function getSourceQualitySummary(cctv) {
    if (!cctv || !state.qualitySummary || !state.qualitySummary.sources) return null;
    const source = cctv.source || 'UNKNOWN';
    return state.qualitySummary.sources[source] || null;
}

function getRegionQualitySummary(regionKey) {
    if (!regionKey || !state.qualitySummary || !state.qualitySummary.regions) return null;
    return state.qualitySummary.regions[regionKey] || null;
}

function getQualityMetric(summary, snakeName, camelName, fallback = 0) {
    if (!summary) return fallback;
    const value = summary[snakeName] ?? summary[camelName];
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : fallback;
}

function normalizeQualitySummary(summary) {
    if (!summary) return null;

    const samples = getQualityMetric(summary, 'samples', 'samples', getQualityMetric(summary, 'total', 'total', 0));
    const success = getQualityMetric(summary, 'success', 'success', 0);
    const failure = getQualityMetric(summary, 'failure', 'failure', 0);
    const slow = getQualityMetric(summary, 'slow', 'slow', 0);
    const fallback = getQualityMetric(summary, 'fallback', 'fallback', 0);
    const successRate = getQualityMetric(summary, 'success_rate', 'successRate', samples ? success / samples : 0);
    const failureRate = getQualityMetric(summary, 'failure_rate', 'failureRate', samples ? failure / samples : 0);
    const slowRate = getQualityMetric(summary, 'slow_rate', 'slowRate', samples ? slow / samples : 0);
    const fallbackRate = getQualityMetric(summary, 'fallback_rate', 'fallbackRate', samples ? fallback / samples : 0);
    const avgFirstFrameMs = getQualityMetric(summary, 'avg_first_frame_ms', 'avgFirstFrameMs', 0);
    const avgWidth = getQualityMetric(summary, 'avg_width', 'avgWidth', 0);
    const avgHeight = getQualityMetric(summary, 'avg_height', 'avgHeight', 0);

    return {
        samples,
        successRate,
        failureRate,
        slowRate,
        fallbackRate,
        avgFirstFrameMs,
        avgWidth,
        avgHeight,
        updatedAt: summary.updated_at || summary.updatedAt || summary.last_seen_at || summary.lastSeenAt || state.qualitySummary?.generated_at || null
    };
}

function getEffectiveQualitySummary(cctv, regionKey) {
    const cameraSummary = getCameraQualitySummary(cctv);
    const cameraMetrics = normalizeQualitySummary(cameraSummary);
    if (cameraMetrics && cameraMetrics.samples >= 3) {
        return {
            scope: 'camera',
            label: cctv?.name || '현재 CCTV',
            summary: cameraSummary,
            metrics: cameraMetrics,
            weight: 1
        };
    }

    const sourceSummary = getSourceQualitySummary(cctv);
    const sourceMetrics = normalizeQualitySummary(sourceSummary);
    if (sourceMetrics && sourceMetrics.samples >= 10) {
        return {
            scope: 'source',
            label: `${cctv?.source || 'UNKNOWN'} 소스`,
            summary: sourceSummary,
            metrics: sourceMetrics,
            weight: 0.58
        };
    }

    const regionSummary = getRegionQualitySummary(regionKey);
    const regionMetrics = normalizeQualitySummary(regionSummary);
    if (regionMetrics && regionMetrics.samples >= 12) {
        return {
            scope: 'region',
            label: `${getRegionLabel(regionKey)} 지역`,
            summary: regionSummary,
            metrics: regionMetrics,
            weight: 0.45
        };
    }

    return null;
}

function getQualitySummaryAdjustment(cctv) {
    const effective = getEffectiveQualitySummary(cctv, inferRegionKey(cctv));
    if (!effective) return 0;
    const { metrics } = effective;

    let adjustment = 0;
    if (metrics.successRate < 0.5) adjustment += 6;
    else if (metrics.successRate < 0.72) adjustment += 3.2;
    else if (metrics.successRate < 0.85) adjustment += 1.2;

    if (metrics.failureRate >= 0.45) adjustment += 2;
    if (metrics.slowRate >= 0.4) adjustment += 1.4;
    if (metrics.fallbackRate >= 0.5) adjustment += 1;

    if (metrics.avgFirstFrameMs > 12000) adjustment += 2.4;
    else if (metrics.avgFirstFrameMs > QUALITY_SLOW_FIRST_FRAME_MS) adjustment += 1.2;

    if (metrics.samples >= 6 && metrics.successRate >= 0.9 && metrics.avgFirstFrameMs > 0 && metrics.avgFirstFrameMs < 3500) {
        adjustment -= 1;
    }

    return Math.max(-1.2, Math.min(8, adjustment * effective.weight));
}

function getQualitySummaryHealthMeta(cctv, regionKey) {
    const effective = getEffectiveQualitySummary(cctv, regionKey);
    if (!effective) return null;

    const { metrics } = effective;
    const label = effective.label || getRegionLabel(regionKey);
    const timeText = metrics.updatedAt || state.qualitySummary?.generated_at || null;
    const aggregate = effective.scope !== 'camera';
    const downFailureRate = aggregate ? 0.62 : 0.55;
    const downSuccessRate = aggregate ? 0.38 : 0.45;
    const slowRate = aggregate ? 0.5 : 0.4;
    const slowFirstFrameMs = aggregate ? 10000 : QUALITY_SLOW_FIRST_FRAME_MS;

    if (metrics.failureRate >= downFailureRate || metrics.successRate < downSuccessRate) {
        return {
            regionKey,
            status: 'QUALITY_DOWN',
            shortLabel: '실사용 불안정',
            longLabel: `${label} 실사용 재생 실패가 최근 많이 감지되었습니다`,
            tone: 'danger',
            penalty: aggregate ? 4.2 : 7,
            lastUpdated: timeText
        };
    }

    if (metrics.slowRate >= slowRate || metrics.avgFirstFrameMs > slowFirstFrameMs) {
        return {
            regionKey,
            status: 'QUALITY_SLOW',
            shortLabel: '로딩 느림',
            longLabel: `${label} 실사용 기준 첫 화면 로딩이 느린 편입니다`,
            tone: 'warn',
            penalty: aggregate ? 1.8 : 3.2,
            lastUpdated: timeText
        };
    }

    if ((effective.scope === 'camera' && metrics.samples >= 5 && metrics.successRate >= 0.88)
        || (aggregate && metrics.samples >= 20 && metrics.successRate >= 0.9)) {
        return {
            regionKey,
            status: 'QUALITY_OK',
            shortLabel: '실사용 정상',
            longLabel: `${label} 실사용 재생 성공률이 안정적입니다`,
            tone: metrics.avgFirstFrameMs > 6000 ? 'ok-soft' : 'ok',
            penalty: metrics.avgFirstFrameMs > 6000 ? (aggregate ? 0.2 : 0.4) : 0,
            lastUpdated: timeText
        };
    }

    return null;
}

function getStoredPlaybackHealthTimestamp(health) {
    if (!health) return 0;
    const storedAt = Number(health.storedAt);
    if (Number.isFinite(storedAt) && storedAt > 0) return storedAt;

    const parsed = Date.parse(health.lastUpdated || '');
    return Number.isNaN(parsed) ? 0 : parsed;
}

function getStoredPlaybackHealthTtl(health) {
    if (!health) return 0;
    return health.tone === 'danger' || health.status === 'PLAYBACK_ERROR'
        ? PLAYBACK_HEALTH_PROBLEM_TTL_MS
        : PLAYBACK_HEALTH_OK_TTL_MS;
}

function isStoredPlaybackHealthFresh(health, now = Date.now()) {
    const storedAt = getStoredPlaybackHealthTimestamp(health);
    if (!storedAt) return false;
    return now - storedAt <= getStoredPlaybackHealthTtl(health);
}

function sanitizeStoredPlaybackHealth(entry) {
    if (!entry || typeof entry !== 'object') return null;
    const storedAt = getStoredPlaybackHealthTimestamp(entry);
    const penalty = Number(entry.penalty);

    return {
        status: entry.status || 'UNKNOWN',
        shortLabel: entry.shortLabel || '최근 확인',
        longLabel: entry.longLabel || '현재 브라우저에서 확인한 최근 재생 상태',
        tone: entry.tone || 'unknown',
        penalty: Number.isFinite(penalty) ? penalty : 1.5,
        lastUpdated: entry.lastUpdated || (storedAt ? new Date(storedAt).toISOString() : new Date().toISOString()),
        storedAt: storedAt || Date.now()
    };
}

function hydrateStoredPlaybackHealth() {
    try {
        if (!window.localStorage) return;
        const raw = window.localStorage.getItem(PLAYBACK_HEALTH_STORAGE_KEY);
        if (!raw) return;

        const parsed = JSON.parse(raw);
        if (parsed?.version !== PLAYBACK_HEALTH_SCHEMA_VERSION) {
            window.localStorage.removeItem(PLAYBACK_HEALTH_STORAGE_KEY);
            return;
        }

        const entries = Array.isArray(parsed?.entries) ? parsed.entries : [];
        let restoredCount = 0;
        let needsPrune = false;

        entries.forEach(entry => {
            const id = entry?.id;
            if (!id || (state.cctvById.size > 0 && !state.cctvById.has(id))) {
                needsPrune = true;
                return;
            }

            const health = sanitizeStoredPlaybackHealth(entry);
            if (!health || !isStoredPlaybackHealthFresh(health)) {
                needsPrune = true;
                return;
            }

            state.cameraPlaybackHealth.set(id, health);
            restoredCount++;
        });

        if (needsPrune) queueStoredPlaybackHealthPersist();
        if (restoredCount > 0) console.log(`[Playback] Restored ${restoredCount} recent camera health entries`);
    } catch (error) {
        console.warn('[Playback] Stored camera health ignored:', error);
    }
}

function queueStoredPlaybackHealthPersist() {
    if (playbackHealthPersistTimer) {
        clearTimeout(playbackHealthPersistTimer);
    }

    playbackHealthPersistTimer = setTimeout(() => {
        playbackHealthPersistTimer = null;
        persistStoredPlaybackHealth();
    }, 180);
}

function persistStoredPlaybackHealth() {
    try {
        if (!window.localStorage) return;
        const now = Date.now();
        const entries = Array.from(state.cameraPlaybackHealth.entries())
            .map(([id, health]) => ({ id, ...health }))
            .filter(entry => state.cctvById.has(entry.id) && isStoredPlaybackHealthFresh(entry, now))
            .sort((a, b) => getStoredPlaybackHealthTimestamp(b) - getStoredPlaybackHealthTimestamp(a))
            .slice(0, PLAYBACK_HEALTH_MAX_ENTRIES);

        window.localStorage.setItem(PLAYBACK_HEALTH_STORAGE_KEY, JSON.stringify({
            version: PLAYBACK_HEALTH_SCHEMA_VERSION,
            savedAt: now,
            entries
        }));
    } catch (error) {
        console.warn('[Playback] Could not persist camera health:', error);
    }
}

function getCameraHealthMeta(cctv) {
    const playbackHealth = cctv && cctv.id ? state.cameraPlaybackHealth.get(cctv.id) : null;
    if (playbackHealth) {
        if (!isStoredPlaybackHealthFresh(playbackHealth)) {
            state.cameraPlaybackHealth.delete(cctv.id);
            queueStoredPlaybackHealthPersist();
        } else {
            return {
                regionKey: inferRegionKey(cctv),
                status: playbackHealth.status,
                shortLabel: playbackHealth.shortLabel,
                longLabel: playbackHealth.longLabel,
                tone: playbackHealth.tone,
                penalty: playbackHealth.penalty,
                lastUpdated: playbackHealth.lastUpdated
            };
        }
    }

    const regionKey = inferRegionKey(cctv);
    const healthEntry = state.regionHealth[regionKey];
    const lastUpdated = healthEntry && healthEntry.checked_at
        ? healthEntry.checked_at
        : (state.healthSnapshot ? state.healthSnapshot.last_updated : null);
    const staleSuffix = state.healthSnapshotStale ? ' (점검 지연)' : '';

    if (isUnsupportedBrowserStream(cctv)) {
        return {
            regionKey,
            status: 'UNSUPPORTED',
            shortLabel: '웹 미지원',
            longLabel: `${getRegionLabel(regionKey)} 원본은 구형 전용 플레이어 기반이라 현재 웹 앱에서 재생할 수 없습니다`,
            tone: 'danger',
            penalty: 12,
            lastUpdated
        };
    }

    const cameraFailureMeta = getCameraFailureHealthMeta(cctv, regionKey, lastUpdated);
    if (cameraFailureMeta) return cameraFailureMeta;

    const qualityMeta = getQualitySummaryHealthMeta(cctv, regionKey);
    if (qualityMeta) return qualityMeta;

    if (state.healthSnapshotStale) {
        return {
            regionKey,
            status: 'STALE',
            shortLabel: '실시간 확인',
            longLabel: `${getRegionLabel(regionKey)} 점검 정보가 오래되어 실제 재생 상태를 우선 확인합니다`,
            tone: 'unknown',
            penalty: 0.6,
            lastUpdated
        };
    }

    if (!healthEntry) {
        return {
            regionKey,
            status: 'UNKNOWN',
            shortLabel: '상태 미확인',
            longLabel: `${getRegionLabel(regionKey)} 상태 정보 없음`,
            tone: 'unknown',
            penalty: 1.5,
            lastUpdated
        };
    }

    if (healthEntry.status === 'DOWN') {
        const usingFallback = healthEntry.active_source === 'sub';
        return {
            regionKey,
            status: 'DOWN',
            shortLabel: (usingFallback ? '대체 권장' : '점검 실패') + staleSuffix,
            longLabel: usingFallback
                ? `${getRegionLabel(regionKey)} 자동 점검에서 원본 소스 실패가 감지되어 대체 소스를 우선 권장합니다${staleSuffix}`
                : `${getRegionLabel(regionKey)} 자동 점검 샘플이 실패했습니다. 현재 영상이 재생되면 화면의 실제 재생 상태가 우선입니다${staleSuffix}`,
            tone: usingFallback ? 'warn' : 'danger',
            penalty: usingFallback ? 4.2 : 8,
            lastUpdated
        };
    }

    if (healthEntry.status === 'DEGRADED') {
        return {
            regionKey,
            status: 'DEGRADED',
            shortLabel: '불안정' + staleSuffix,
            longLabel: `${getRegionLabel(regionKey)} 일부 카메라 불안정${staleSuffix}`,
            tone: 'warn',
            penalty: 3,
            lastUpdated
        };
    }

    const hasFailures = Number(healthEntry.failed || 0) > 0;
    const okTone = state.healthSnapshotStale ? 'ok-soft' : (hasFailures ? 'ok-soft' : 'ok');
    return {
        regionKey,
        status: 'OK',
        shortLabel: state.healthSnapshotStale ? '최근 점검 정상' : (hasFailures ? '대체 가능' : '안정적'),
        longLabel: hasFailures ? `${getRegionLabel(regionKey)} 일부 샘플은 대체 소스로 회복${staleSuffix}` : `${getRegionLabel(regionKey)} 최근 점검 정상${staleSuffix}`,
        tone: okTone,
        penalty: hasFailures ? 0.8 : 0,
        lastUpdated
    };
}

function getCameraPlaybackConfidence(cctv, health = getCameraHealthMeta(cctv)) {
    const playbackHealth = cctv && cctv.id ? state.cameraPlaybackHealth.get(cctv.id) : null;
    if (playbackHealth && isStoredPlaybackHealthFresh(playbackHealth)) {
        if (playbackHealth.status === 'PLAYING') {
            return {
                tone: 'ok',
                label: '현재 브라우저에서 재생 확인',
                title: '방금 이 브라우저에서 영상 프레임이 확인되었습니다.'
            };
        }
        if (playbackHealth.status === 'PLAYBACK_ERROR' || playbackHealth.tone === 'danger') {
            return {
                tone: 'danger',
                label: '최근 재생 실패',
                title: '최근 이 브라우저에서 영상 재생 실패가 감지되었습니다.'
            };
        }
    }

    const cameraMetrics = normalizeQualitySummary(getCameraQualitySummary(cctv));
    if (cameraMetrics && cameraMetrics.samples >= 5) {
        if (cameraMetrics.failureRate >= 0.25 || cameraMetrics.successRate < 0.72) {
            return {
                tone: 'danger',
                label: '실사용 실패 많음',
                title: `최근 실사용 ${cameraMetrics.samples}건 기준 재생 실패율이 높습니다.`
            };
        }
        if (cameraMetrics.successRate >= 0.92 && cameraMetrics.failureRate <= 0.08 && cameraMetrics.slowRate <= 0.25) {
            return {
                tone: cameraMetrics.avgFirstFrameMs > 6500 ? 'ok-soft' : 'ok',
                label: '실사용 재생 검증',
                title: `최근 실사용 ${cameraMetrics.samples}건 기준 재생 성공률이 높습니다.`
            };
        }
        if (cameraMetrics.slowRate >= 0.35 || cameraMetrics.avgFirstFrameMs > QUALITY_SLOW_FIRST_FRAME_MS) {
            return {
                tone: 'warn',
                label: '재생은 되나 느림',
                title: `최근 실사용 ${cameraMetrics.samples}건 기준 첫 화면 로딩이 느립니다.`
            };
        }
    }

    if (isAggregateOnlyHealthWarning(cctv, health)) {
        return {
            tone: 'unknown',
            label: '직접 확인 전',
            title: '소스 단위 점검은 불안정하지만, 이 카메라는 브라우저 재생 리졸버로 별도 확인합니다.'
        };
    }

    if (['CAMERA_CRITICAL', 'CAMERA_INVESTIGATE'].includes(health.status)) {
        return {
            tone: 'danger',
            label: health.shortLabel,
            title: health.longLabel || '자동 점검에서 반복 장애가 확인되었습니다.'
        };
    }

    if (health.status === 'UNSUPPORTED' || health.status === 'QUALITY_DOWN' || health.status === 'PLAYBACK_ERROR' || health.tone === 'danger') {
        return {
            tone: 'danger',
            label: health.shortLabel || '연결 불안정',
            title: health.longLabel || '현재 재생 실패 가능성이 높습니다.'
        };
    }

    if (health.status === 'DEGRADED' || health.status === 'QUALITY_SLOW' || health.tone === 'warn') {
        return {
            tone: 'warn',
            label: health.shortLabel || '주의',
            title: health.longLabel || '재생이 느리거나 불안정할 수 있습니다.'
        };
    }

    // Region/source-level OK is not strong enough to promise a specific camera will play.
    return {
        tone: 'unknown',
        label: '아직 직접 확인 전',
        title: '이 카메라 단위의 최근 재생 성공 근거가 아직 충분하지 않습니다.'
    };
}

function getCameraDisplayHealthMeta(cctv, health = getCameraHealthMeta(cctv)) {
    const confidence = getCameraPlaybackConfidence(cctv, health);
    const statusByTone = {
        danger: 'DISPLAY_DANGER',
        warn: 'DISPLAY_WARN',
        ok: 'DISPLAY_OK',
        'ok-soft': 'DISPLAY_OK_SOFT',
        unknown: 'DISPLAY_UNKNOWN'
    };

    return {
        ...health,
        status: statusByTone[confidence.tone] || health.status || 'DISPLAY_UNKNOWN',
        shortLabel: confidence.label || health.shortLabel || '상태 미확인',
        longLabel: confidence.title || health.longLabel || '현재 재생 상태를 확인 중입니다.',
        tone: confidence.tone || health.tone || 'unknown'
    };
}

function isKbResolverPlaybackCandidate(cctv) {
    const url = cctv?.directUrl || cctv?.url || '';
    const kind = getUrlParam(url, 'kind');
    const cctvip = getUrlParam(url, 'cctvip');
    return cctv?.source === 'UTIC' && ['EE', 'EEE', 'KB'].includes(kind) && !!cctvip;
}

function hasCameraSpecificPlaybackProblem(cctv) {
    const failureRecord = getCameraFailureRecord(cctv);
    if (failureRecord && ['investigate', 'critical'].includes(failureRecord.emergency_level || '')) {
        return true;
    }

    const playbackHealth = cctv && cctv.id ? state.cameraPlaybackHealth.get(cctv.id) : null;
    if (playbackHealth && isStoredPlaybackHealthFresh(playbackHealth)) {
        return playbackHealth.status === 'PLAYBACK_ERROR' || playbackHealth.tone === 'danger';
    }

    const cameraMetrics = normalizeQualitySummary(getCameraQualitySummary(cctv));
    if (cameraMetrics && cameraMetrics.samples >= 3) {
        return cameraMetrics.failureRate >= 0.25 || cameraMetrics.successRate < 0.72;
    }

    return false;
}

function isProxyResolverBackedCandidate(cctv) {
    const url = cctv?.directUrl || cctv?.url || '';
    const source = cctv?.source || '';
    const kind = getUrlParam(url, 'kind');
    return isKbResolverPlaybackCandidate(cctv)
        || isJejuUticProxyable(cctv)
        || cctv?.urlType === 'daejeon_mp4_dynamic'
        || (source === 'UTIC' && kind === 'E' && inferRegionKey(cctv) === 'DAEJEON')
        || (source === 'UTIC' && kind === 'Z3' && !!getUrlParam(url, 'cctvip'));
}

function isAggregateOnlyHealthWarning(cctv, health) {
    if (!health || !cctv || !isProxyResolverBackedCandidate(cctv)) return false;
    if (hasCameraSpecificPlaybackProblem(cctv)) return false;
    return ['DOWN', 'DEGRADED', 'QUALITY_DOWN', 'QUALITY_SLOW'].includes(health.status);
}

function getRankingHealthPenalty(cctv, health, distanceKm) {
    const basePenalty = Number(health?.penalty || 0);
    if (basePenalty <= 0) return 0;
    if (!cctv) return basePenalty;

    const playbackHealth = cctv.id ? state.cameraPlaybackHealth.get(cctv.id) : null;
    if (playbackHealth && isStoredPlaybackHealthFresh(playbackHealth) && playbackHealth.status === 'PLAYING') {
        return 0;
    }

    if (health?.status === 'UNSUPPORTED' || health?.status === 'PLAYBACK_ERROR' || hasCameraSpecificPlaybackProblem(cctv)) {
        return basePenalty;
    }

    if (!isProxyResolverBackedCandidate(cctv)) return basePenalty;
    if (!Number.isFinite(distanceKm)) return Math.min(basePenalty, 2.8);

    // Source-wide checks can be noisy for mixed UTIC subtypes. Nearby cameras
    // with a fresh resolver should stay discoverable until camera-level evidence
    // proves that this exact camera is broken.
    if (distanceKm <= 1) return Math.min(basePenalty, 0.35);
    if (distanceKm <= 2.5) return Math.min(basePenalty, 0.75);
    if (distanceKm <= 5) return Math.min(basePenalty, 1.4);
    return Math.min(basePenalty, 2.8);
}

function isFrameOnlyPlaybackCandidate(cctv) {
    const url = cctv?.directUrl || cctv?.url || '';
    return url.includes('its.gn.go.kr/popup')
        || url.includes('gangneung_player.html')
        || url.includes('cctvPopup.do')
        || url.includes('hrfco.go.kr');
}

function shouldIsolateProblemCamera(cctv) {
    const health = cctv?._health || getCameraHealthMeta(cctv);
    if (!health) return false;
    if (health.status === 'UNSUPPORTED') return true;
    if (['CAMERA_CRITICAL', 'CAMERA_INVESTIGATE', 'PLAYBACK_ERROR', 'QUALITY_DOWN'].includes(health.status)) {
        return true;
    }
    if (health.status === 'DOWN' && !isAggregateOnlyHealthWarning(cctv, health)) {
        return true;
    }
    return false;
}

function isDirectVideoPlaybackCandidate(cctv) {
    const url = cctv?.directUrl || cctv?.url || '';
    const source = cctv?.source || '';
    const kind = getUrlParam(url, 'kind');
    return cctv?.urlType === 'daejeon_mp4_dynamic'
        || isDaejeonDirectMp4Candidate(cctv, url, source, kind, getUrlParam(url, 'cctvip'), cctv?.original_id)
        || url.includes('.mp4')
        || url.includes('.m3u8')
        || url.includes('/kb?cctvip=')
        || url.includes('/jeju?id=')
        || url.includes('workers.dev')
        || url.includes('sslip.io')
        || ['JEJU', 'NOWJEJU', 'TRENDWORLD', 'KBS', 'GITS'].includes(source)
        || (source === 'UTIC' && ['Z3', 'EE', 'EEE', 'KB'].includes(kind));
}

function getStreamQualityScore(cctv) {
    const url = cctv.directUrl || cctv.url || '';
    const source = cctv.source || '';
    const kind = getUrlParam(url, 'kind');
    const daejeonDirectMp4Candidate = isDaejeonDirectMp4Candidate(
        cctv,
        url,
        source,
        kind,
        getUrlParam(url, 'cctvip'),
        cctv.original_id
    );
    let score = SOURCE_QUALITY_SCORES[source] || 0.72;

    if (isDirectVideoPlaybackCandidate(cctv)) {
        score += 0.08;
    }
    if (isFrameOnlyPlaybackCandidate(cctv)) {
        score -= 0.24;
    }

    if (cctv.backup_urls && cctv.backup_urls.length > 0) {
        score += 0.04;
    }

    if (cctv.urlType === 'daejeon_mp4_dynamic') {
        score += 0.08;
    }
    if (daejeonDirectMp4Candidate) {
        score += 0.12;
    }
    if (url.includes('.m3u8') || url.includes('/kb?cctvip=') || url.includes('workers.dev')) {
        score += 0.06;
    }
    if (source === 'JEJU' || url.includes('158.179.194.163.sslip.io/jeju')) {
        score += 0.08;
    }
    if (source === 'UTIC' && kind === 'E' && inferRegionKey(cctv) === 'DAEJEON' && !daejeonDirectMp4Candidate) {
        score -= 0.04;
    }
    if (url.includes('cctvlo.geumriver.go.kr')) {
        score -= 0.22;
    }
    if ((url.includes('openDataCctvStream.jsp') || url.includes('utic.go.kr/jsp')) && !daejeonDirectMp4Candidate) {
        score -= 0.08;
    }
    if (url.includes('its.gn.go.kr/popup') || url.includes('gangneung_player.html') || url.includes('cctvPopup.do')) {
        score -= 0.1;
    }

    return Math.max(0.4, Math.min(0.98, score));
}

function getRoadContextPriority(cctv, distanceKm) {
    const normalizedName = String(cctv.name || '').replace(/\s+/g, '');
    const source = cctv.source || '';
    const looksUrban = URBAN_CONTEXT_PATTERN.test(normalizedName);
    const looksScenic = SCENIC_CONTEXT_PATTERN.test(normalizedName) || source === 'KBS';
    const looksOutskirt = source === 'NTIC' || OUTSKIRT_CONTEXT_PATTERN.test(normalizedName);

    let score = 0;

    if (looksOutskirt) {
        score += looksUrban ? 2.0 : 4.5;
    }

    if (looksUrban) {
        score -= 1.2;
    } else if (!looksOutskirt && distanceKm < 1.2) {
        score -= 0.5;
    }

    if (looksScenic && !looksUrban) {
        score += Number.isFinite(distanceKm) && distanceKm < 3 ? 1.6 : 0.8;
    }

    return score;
}

function getTrafficContextPriority(cctv, distanceKm) {
    const normalizedName = String(cctv.name || '').replace(/\s+/g, '');
    const source = cctv.source || '';
    const url = cctv.directUrl || cctv.url || '';
    const kind = getUrlParam(url, 'kind');
    const looksTraffic = TRAFFIC_CONTEXT_PATTERN.test(normalizedName);
    const looksUrban = URBAN_CONTEXT_PATTERN.test(normalizedName);
    const looksScenic = SCENIC_CONTEXT_PATTERN.test(normalizedName);
    const isUticRoad = source === 'UTIC';
    const isNationalTraffic = source === 'NTIC' || kind === 'Z3';

    let score = 0;

    if (isNationalTraffic) score -= 7;
    if (isUticRoad) score -= 3;
    if (looksTraffic) score -= 4.5;
    if (OUTSKIRT_CONTEXT_PATTERN.test(normalizedName)) score -= 2.5;

    if (looksUrban) score += 1.8;
    if (looksScenic || ['NOWJEJU', 'TRENDWORLD', 'YOUTUBE'].includes(source)) score += 3;
    if (Number.isFinite(distanceKm) && distanceKm > 12) score += Math.min(4, (distanceKm - 12) * 0.22);

    return score;
}

function getSourceResilienceAdjustment(cctv, health, distanceKm) {
    const source = cctv?.source || '';
    const jejuHealth = state.regionHealth.JEJU;
    const jejuStatus = jejuHealth?.status || '';
    const jejuIsUnstable = ['DEGRADED', 'DOWN'].includes(jejuStatus);

    if (!jejuIsUnstable) return 0;

    if (source === 'JEJU' || isJejuUticProxyable(cctv)) {
        if (Number.isFinite(distanceKm) && distanceKm <= 2) {
            return -Math.max(0, (health?.penalty || 0) - 0.8);
        }
        return 0;
    }

    if (['NOWJEJU', 'TRENDWORLD'].includes(source) && Number.isFinite(distanceKm) && distanceKm <= DYNAMIC_BACKUP_RADIUS_KM) {
        return 0;
    }

    if (health?.status === 'UNSUPPORTED') {
        return 4;
    }

    return 0;
}

function getSortPriorityScore(parts) {
    const {
        distance,
        healthPenalty,
        streamQuality,
        roadContextPriority,
        trafficContextPriority = 0,
        sourceResilience,
        backupBonus,
        qualityAdjustment
    } = parts;

    switch (state.sortMode) {
        case 'nearest':
            return distance + (healthPenalty * 0.65) + qualityAdjustment + sourceResilience - (backupBonus * 0.4);
        case 'urban':
            return distance + healthPenalty + ((1 - streamQuality) * 4) + (roadContextPriority * 1.9) + qualityAdjustment + sourceResilience - backupBonus;
        case 'traffic':
            return (distance * 0.72) + (healthPenalty * 0.85) + ((1 - streamQuality) * 4.5) + trafficContextPriority + (qualityAdjustment * 0.85) + sourceResilience - (backupBonus * 0.7);
        case 'stability':
            return (distance * 0.55) + (healthPenalty * 1.35) + ((1 - streamQuality) * 5.5) + (qualityAdjustment * 1.45) + roadContextPriority + sourceResilience - backupBonus;
        case 'quality':
            return (distance * 0.7) + (healthPenalty * 0.85) + ((1 - streamQuality) * 10) + (qualityAdjustment * 0.9) + roadContextPriority + sourceResilience - (backupBonus * 1.2);
        case 'recommended':
        default:
            return distance + healthPenalty + ((1 - streamQuality) * 6) + roadContextPriority + sourceResilience + qualityAdjustment - backupBonus;
    }
}

function getStableModulo(value, modulo) {
    if (!modulo) return 0;
    const text = String(value || '');
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) {
        hash = ((hash * 31) + text.charCodeAt(i)) >>> 0;
    }
    return hash % modulo;
}

function formatDistance(distanceKm) {
    if (!Number.isFinite(distanceKm)) return '거리 미확인';
    if (distanceKm < 1) return `${Math.round(distanceKm * 1000)}m`;
    return `${distanceKm.toFixed(distanceKm < 10 ? 1 : 0)}km`;
}

function formatRelativeTime(timestamp) {
    if (!timestamp) return '업데이트 시각 없음';

    const parsed = parseHealthTimestamp(timestamp);

    if (Number.isNaN(parsed.getTime())) {
        return timestamp;
    }

    const diffMs = Date.now() - parsed.getTime();
    const diffMinutes = Math.max(0, Math.round(diffMs / 60000));

    if (diffMinutes < 1) return '방금 전 점검';
    if (diffMinutes < 60) return `${diffMinutes}분 전 점검`;

    const diffHours = Math.round(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}시간 전 점검`;

    return parsed.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function parseHealthTimestamp(timestamp) {
    if (!timestamp) return new Date(NaN);
    const normalized = String(timestamp).trim();
    if (!normalized) return new Date(NaN);

    if (/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) {
        return new Date(normalized);
    }

    // GitHub Actions writes bare timestamps in UTC. Without the Z suffix,
    // browsers treat them as local time and make fresh checks look 9 hours old in Korea.
    return new Date(normalized.replace(' ', 'T') + 'Z');
}

function isStaleHealthTimestamp(timestamp) {
    const parsed = parseHealthTimestamp(timestamp);
    if (Number.isNaN(parsed.getTime())) return true;
    return Date.now() - parsed.getTime() > HEALTH_STALE_MS;
}

function renderServiceStatusBanner() {
    const banner = $('#service-status-banner');
    if (!banner) return;

    clearServiceStatusBannerTimers();

    if (!state.healthSnapshot || !state.healthSnapshot.regions) {
        hideServiceStatusBanner(true);
        return;
    }

    const currentRegionKeys = [...new Set(
        state.nearestCctvs.slice(0, 4).map(cctv => inferRegionKey(cctv)).filter(Boolean)
    )];
    if (currentRegionKeys.length === 0) {
        hideServiceStatusBanner(true);
        return;
    }

    const visibleHealth = state.nearestCctvs.slice(0, 4)
        .map(cctv => {
            const health = getCameraHealthMeta(cctv);
            const displayHealth = getCameraDisplayHealthMeta(cctv, health);
            return {
                cctv,
                health,
                displayHealth,
                regionKey: health.regionKey || inferRegionKey(cctv)
            };
        });
    const downRegions = visibleHealth.filter(item => item.displayHealth.tone === 'danger');
    const degradedRegions = visibleHealth.filter(item => item.displayHealth.tone === 'warn');
    const newestAffectedTimestamp = [...downRegions, ...degradedRegions]
        .map(item => item.displayHealth.lastUpdated || item.health.lastUpdated)
        .find(Boolean);
    const lastUpdatedText = formatRelativeTime(newestAffectedTimestamp || state.healthSnapshot.last_updated);

    let tone = null;
    let title = '';
    let body = '';

    if (state.healthSnapshotStale) {
        tone = 'warn';
        title = '점검 정보 지연';
        body = `${currentRegionKeys.map(getRegionLabel).join(', ')} 점검 정보가 지연되어 화면별 실제 재생 상태를 우선 반영합니다.`;
    } else if (downRegions.length > 0) {
        tone = 'danger';
        title = '현재 지역 장애';
        body = `${[...new Set(downRegions.slice(0, 3).map(item => getRegionLabel(item.regionKey)))].join(', ')} 연결이 불안정합니다. 대체 소스를 우선 추천합니다.`;
    } else if (degradedRegions.length > 0) {
        tone = 'warn';
        title = '현재 지역 점검 중';
        body = `${[...new Set(degradedRegions.slice(0, 3).map(item => getRegionLabel(item.regionKey)))].join(', ')} 품질이 일시적으로 흔들릴 수 있습니다.`;
    }

    if (!tone) {
        hideServiceStatusBanner(true);
        return;
    }

    const bannerKey = `${tone}:${title}:${body}:${lastUpdatedText}`;
    if (state.serviceBannerDismissedKey === bannerKey) {
        hideServiceStatusBanner(true);
        return;
    }

    banner.className = `service-status-banner tone-${tone}`;
    banner.innerHTML = `
        <button type="button" class="service-status-close" aria-label="상태 메시지 닫기">×</button>
        <div class="service-status-content">
            <div class="service-status-title">${title}</div>
            <div class="service-status-body">${body}</div>
            <div class="service-status-meta">
                <span class="service-status-time">${lastUpdatedText}</span>
                <span class="service-status-countdown" aria-label="5초 후 자동으로 닫힘">5s</span>
            </div>
        </div>
    `;
    const closeButton = banner.querySelector('.service-status-close');
    if (closeButton) {
        closeButton.addEventListener('click', () => {
            state.serviceBannerDismissedKey = bannerKey;
            hideServiceStatusBanner();
        }, { once: true });
    }

    startServiceStatusBannerCountdown(banner);
    state.serviceBannerTimer = setTimeout(() => {
        hideServiceStatusBanner();
    }, SERVICE_BANNER_VISIBLE_MS);
}

function clearServiceStatusBannerTimers() {
    if (state.serviceBannerTimer) {
        clearTimeout(state.serviceBannerTimer);
        state.serviceBannerTimer = null;
    }

    if (state.serviceBannerCountdownTimer) {
        clearInterval(state.serviceBannerCountdownTimer);
        state.serviceBannerCountdownTimer = null;
    }
}

function startServiceStatusBannerCountdown(banner) {
    const countdown = banner.querySelector('.service-status-countdown');
    if (!countdown) return;

    const startedAt = Date.now();
    const updateCountdown = () => {
        const elapsed = Date.now() - startedAt;
        const remainingSeconds = Math.max(0, Math.ceil((SERVICE_BANNER_VISIBLE_MS - elapsed) / 1000));
        countdown.textContent = `${remainingSeconds}s`;
        countdown.setAttribute('aria-label', `${remainingSeconds}초 후 상태 메시지 자동 닫힘`);
    };

    updateCountdown();
    state.serviceBannerCountdownTimer = setInterval(updateCountdown, 250);
}

function hideServiceStatusBanner(clearContent = false) {
    const banner = $('#service-status-banner');
    if (!banner) return;

    clearServiceStatusBannerTimers();
    banner.classList.add('hidden');
    if (clearContent) banner.innerHTML = '';
}

function showStreamLoadingIndicator(wrapper, title, detail) {
    if (!wrapper) return null;
    const existing = wrapper.querySelector('.video-loading-indicator');
    if (existing) existing.remove();

    const indicator = document.createElement('div');
    indicator.className = 'video-loading-indicator';
    indicator.innerHTML = `
        <span class="video-loading-spinner" aria-hidden="true"></span>
        <span class="video-loading-copy">
            <strong>${title}</strong>
            <span>${detail}</span>
        </span>
    `;
    wrapper.appendChild(indicator);
    return indicator;
}

function bindStreamLoadingIndicator(wrapper, media, indicator) {
    if (!wrapper || !media || !indicator) return;
    if (media.classList && media.classList.contains('video-placeholder')) {
        indicator.remove();
        return;
    }

    let settled = false;
    const cleanupFns = [];
    const clear = () => {
        if (settled) return;
        settled = true;
        cleanupFns.forEach(fn => fn());
        if (indicator.parentElement) indicator.remove();
    };

    if (media.tagName === 'VIDEO') {
        ['loadeddata', 'playing', 'canplay', 'timeupdate'].forEach(eventName => {
            const handler = () => {
                if (media.readyState >= 2 && media.videoWidth > 0) clear();
            };
            media.addEventListener(eventName, handler);
            cleanupFns.push(() => media.removeEventListener(eventName, handler));
        });
    } else if (media.tagName === 'IFRAME') {
        const timer = setTimeout(clear, 1200);
        cleanupFns.push(() => clearTimeout(timer));
    } else {
        clear();
    }
}

function getStreamLoadingCopy(cctv, isFallback = false, fallbackIndex = 0, backupCount = 0) {
    if (isFallback) {
        return {
            title: '대체 영상 연결 중',
            detail: `${cctv?.name || '대체 영상'}으로 전환합니다. (${fallbackIndex}/${backupCount})`
        };
    }

    const isJejuCandidate = inferRegionKey(cctv) === 'JEJU';
    if (isJejuCandidate) {
        return {
            title: '원본 영상 연결 중',
            detail: '최대 18초까지 기다린 뒤 실패하면 대체 영상을 연결합니다.'
        };
    }

    return {
        title: '영상 연결 중',
        detail: '재생 준비가 끝나면 자동으로 표시됩니다.'
    };
}

function renderPanelHealthBadge(panel, cctv) {
    let badge = panel.querySelector('.panel-health-badge');
    if (!badge) {
        badge = document.createElement('div');
        badge.className = 'panel-health-badge';
    }

    const controls = panel.querySelector('.panel-controls');
    const expandButton = panel.querySelector('.panel-expand-btn');
    if (controls && badge.parentElement !== controls) {
        controls.insertBefore(badge, expandButton || null);
    }

    const health = getCameraHealthMeta(cctv);
    badge.className = `panel-health-badge tone-${health.tone}`;
    badge.innerHTML = `
        <span>${formatDistance(cctv.distance)}</span>
    `;
    badge.title = `${health.longLabel} · ${formatRelativeTime(health.lastUpdated)} · ${formatDistance(cctv.distance)}`;
    badge.setAttribute('aria-label', formatDistance(cctv.distance));
}

function renderSelectTrigger(panel, cctv, fallbackLabel) {
    const trigger = panel.querySelector('.cctv-select-trigger');
    if (!trigger) return;

    const health = getCameraHealthMeta(cctv);
    const confidence = getCameraPlaybackConfidence(cctv, health);
    const label = cctv?.name || fallbackLabel || 'CCTV 선택';
    trigger.innerHTML = '';

    const name = document.createElement('span');
    name.className = 'cctv-select-name';
    name.textContent = label;

    const dot = document.createElement('span');
    dot.className = `cctv-status-dot tone-${confidence.tone}`;
    dot.setAttribute('aria-hidden', 'true');

    trigger.append(name, dot);
    trigger.title = `${label} · ${confidence.label} · ${confidence.title} · ${formatRelativeTime(health.lastUpdated)}`;
    trigger.setAttribute('aria-label', `${label}, ${confidence.label}`);
}

function getPanelCctv(panel) {
    const cctvId = panel && panel.dataset ? panel.dataset.cctvId : null;
    if (!cctvId) return null;
    return state.nearestCctvs.find(item => item.id === cctvId) || findCctvById(cctvId);
}

function updatePanelHealthUi(panel, cctv) {
    if (!panel || !cctv) return;
    renderSelectTrigger(panel, cctv);
    renderPanelHealthBadge(panel, cctv);
    populateSelectOptions(panel, Number(panel.dataset.cctvIndex || panel.dataset.slotIndex || 0));
}

function updateVideoLayerHealthUi(cctv) {
    if (!cctv || state.activeCctvId !== cctv.id) return;
    const layer = $('#video-layer');
    if (!layer || !layer.classList.contains('active')) return;

    const subTitle = $('#video-layer-title .video-title-sub');
    if (!subTitle) return;

    const distance = Number.isFinite(cctv.distance)
        ? cctv.distance
        : getDistance(state.center.lat, state.center.lng, cctv.lat, cctv.lng);
    const health = getCameraHealthMeta(cctv);

    subTitle.innerHTML = `
        <span>${formatDistance(distance)}</span>
        <span class="panel-health-sep">·</span>
        <span class="tone-${health.tone}">${health.shortLabel}</span>
        <span class="panel-health-sep">·</span>
        <span>${formatRelativeTime(health.lastUpdated)}</span>
    `;
}

function setPlaybackHealth(cctv, nextHealth) {
    if (!cctv || !cctv.id) return;
    const now = Date.now();
    state.cameraPlaybackHealth.set(cctv.id, {
        status: nextHealth.status,
        shortLabel: nextHealth.shortLabel,
        longLabel: nextHealth.longLabel,
        tone: nextHealth.tone,
        penalty: nextHealth.penalty,
        lastUpdated: new Date(now).toISOString(),
        storedAt: now
    });
    queueStoredPlaybackHealthPersist();
    updateVideoLayerHealthUi(cctv);
}

function getTelemetrySampleDecision() {
    try {
        const existing = localStorage.getItem(TELEMETRY_SAMPLE_STORAGE_KEY);
        if (existing === 'in') return true;
        if (existing === 'out') return false;

        const bytes = new Uint8Array(1);
        if (!window.crypto || typeof window.crypto.getRandomValues !== 'function') return false;
        window.crypto.getRandomValues(bytes);
        const sampledIn = (bytes[0] / 255) < QUALITY_TELEMETRY_SAMPLE_RATE;
        localStorage.setItem(TELEMETRY_SAMPLE_STORAGE_KEY, sampledIn ? 'in' : 'out');
        return sampledIn;
    } catch {
        return false;
    }
}

function canQueueQualityTelemetry() {
    if (!QUALITY_TELEMETRY_ENDPOINT || !getTelemetrySampleDecision()) return false;

    try {
        const today = new Date().toISOString().slice(0, 10);
        const raw = localStorage.getItem(TELEMETRY_DAILY_STORAGE_KEY);
        const stateForDay = raw ? JSON.parse(raw) : {};
        const count = stateForDay.date === today ? Number(stateForDay.count || 0) : 0;
        if (count >= QUALITY_TELEMETRY_DAILY_LIMIT) return false;

        localStorage.setItem(TELEMETRY_DAILY_STORAGE_KEY, JSON.stringify({ date: today, count: count + 1 }));
        return true;
    } catch {
        return false;
    }
}

function sanitizeTelemetryText(value, maxLength = 80) {
    return String(value || '').replace(/[^\p{L}\p{N}\s._@()[\]-]/gu, '').trim().slice(0, maxLength);
}

function recordQualityEvent(cctv, eventType, details = {}) {
    if (!cctv || !cctv.id || !canQueueQualityTelemetry()) return;

    const payload = {
        app_version: APP_BUILD_VERSION,
        event_type: eventType,
        camera_id: sanitizeTelemetryText(cctv.id, 96),
        camera_name: sanitizeTelemetryText(cctv.name, 80),
        source: sanitizeTelemetryText(cctv.source || inferRegionKey(cctv), 32),
        region: sanitizeTelemetryText(inferRegionKey(cctv), 32),
        source_index: Number.isFinite(Number(details.sourceIndex)) ? Number(details.sourceIndex) : 0,
        used_fallback: Boolean(details.usedFallback),
        first_frame_ms: Number.isFinite(Number(details.firstFrameMs)) ? Math.round(Number(details.firstFrameMs)) : null,
        fail_ms: Number.isFinite(Number(details.failMs)) ? Math.round(Number(details.failMs)) : null,
        stall_count: Number.isFinite(Number(details.stallCount)) ? Math.max(0, Math.round(Number(details.stallCount))) : 0,
        video_width: Number.isFinite(Number(details.videoWidth)) ? Math.round(Number(details.videoWidth)) : null,
        video_height: Number.isFinite(Number(details.videoHeight)) ? Math.round(Number(details.videoHeight)) : null,
        reason: sanitizeTelemetryText(details.reason || '', 48),
        ts: new Date().toISOString()
    };

    state.qualityTelemetryQueue.push(payload);
    if (state.qualityTelemetryQueue.length > QUALITY_TELEMETRY_QUEUE_LIMIT) {
        state.qualityTelemetryQueue.splice(0, state.qualityTelemetryQueue.length - QUALITY_TELEMETRY_QUEUE_LIMIT);
    }

    if (state.qualityTelemetryQueue.length >= 3) {
        flushQualityTelemetry();
    } else if (!qualityTelemetryFlushTimer) {
        qualityTelemetryFlushTimer = setTimeout(flushQualityTelemetry, 1200);
    }
}

function flushQualityTelemetry() {
    if (qualityTelemetryFlushTimer) {
        clearTimeout(qualityTelemetryFlushTimer);
        qualityTelemetryFlushTimer = null;
    }

    if (!QUALITY_TELEMETRY_ENDPOINT || state.qualityTelemetryQueue.length === 0) return;
    const events = state.qualityTelemetryQueue.splice(0, state.qualityTelemetryQueue.length);
    const body = JSON.stringify({ events });

    try {
        if (navigator.sendBeacon) {
            const sent = navigator.sendBeacon(QUALITY_TELEMETRY_ENDPOINT, new Blob([body], { type: 'application/json' }));
            if (sent) return;
        }
        fetch(QUALITY_TELEMETRY_ENDPOINT, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body,
            keepalive: true
        }).catch(() => {});
    } catch {
        // Telemetry is optional; playback must never depend on it.
    }
}

function initVideoQualityTelemetry(panel, cctv, video) {
    if (!panel || !cctv || !video || video._qualityTelemetryInitialized) return;
    video._qualityTelemetryInitialized = true;
    video._qualityStartedAt = performance.now();
    video._qualityStallCount = 0;
    video._qualitySourceIndex = Number(video.dataset.sourceIndex || 0);

    const markStall = () => {
        video._qualityStallCount = Number(video._qualityStallCount || 0) + 1;
    };
    video.addEventListener('waiting', markStall);
    video.addEventListener('stalled', markStall);
}

function recordVideoQualitySuccess(video, cctv) {
    if (!video || !cctv || video._qualityReported) return;
    if (video.tagName === 'VIDEO' && (video.readyState < 2 || video.videoWidth <= 0)) return;

    video._qualityReported = true;
    const firstFrameMs = performance.now() - Number(video._qualityStartedAt || performance.now());
    recordQualityEvent(cctv, firstFrameMs > QUALITY_SLOW_FIRST_FRAME_MS ? 'slow' : 'success', {
        firstFrameMs,
        stallCount: Number(video._qualityStallCount || 0),
        videoWidth: video.videoWidth,
        videoHeight: video.videoHeight,
        sourceIndex: Number(video._qualitySourceIndex || 0),
        usedFallback: Number(video._qualitySourceIndex || 0) > 0
    });
}

function recordVideoQualityFailure(video, cctv, reason) {
    if (!video || !cctv || video._qualityReported) return;

    video._qualityReported = true;
    recordQualityEvent(cctv, 'failure', {
        failMs: performance.now() - Number(video._qualityStartedAt || performance.now()),
        stallCount: Number(video._qualityStallCount || 0),
        sourceIndex: Number(video._qualitySourceIndex || 0),
        usedFallback: Number(video._qualitySourceIndex || 0) > 0,
        reason
    });
}

function getPlaybackTimeoutMs(cctv) {
    const source = cctv?.source || '';
    const regionKey = inferRegionKey(cctv);
    if (source === 'JEJU' || regionKey === 'JEJU') return JEJU_PLAYBACK_STARTUP_TIMEOUT_MS;
    return PLAYBACK_STARTUP_TIMEOUT_MS;
}

function armVideoPlaybackWatchdog(video, cctv, onUnhealthy, options = {}) {
    if (!video || video.tagName !== 'VIDEO' || typeof onUnhealthy !== 'function') return;

    const startupTimeoutMs = options.startupTimeoutMs || getPlaybackTimeoutMs(cctv);
    const stallTimeoutMs = options.stallTimeoutMs || PLAYBACK_STALL_TIMEOUT_MS;
    let failed = false;
    let hasStarted = false;
    let lastProgressAt = Date.now();
    let lastCurrentTime = 0;
    let stallStartedAt = null;
    const timers = [];
    let interval = null;

    const cleanup = () => {
        timers.forEach(timer => clearTimeout(timer));
        if (interval) clearInterval(interval);
        video.removeEventListener('loadeddata', markHealthy);
        video.removeEventListener('playing', markHealthy);
        video.removeEventListener('canplay', markHealthy);
        video.removeEventListener('timeupdate', markProgress);
        video.removeEventListener('waiting', markStall);
        video.removeEventListener('stalled', markStall);
        video.removeEventListener('error', failFast);
    };

    const fail = (reason) => {
        if (failed) return;
        failed = true;
        cleanup();
        console.warn(`[Playback] ${cctv?.name || 'CCTV'} unhealthy: ${reason}`);
        recordVideoQualityFailure(video, cctv, reason);
        setPlaybackHealth(cctv, {
            status: 'PLAYBACK_ERROR',
            shortLabel: '재생 불안정',
            longLabel: `${cctv?.name || 'CCTV'} 영상 재생 실패 감지`,
            tone: 'danger',
            penalty: 6
        });
        onUnhealthy(reason);
    };

    const recoverStall = (reason) => {
        if (typeof options.onStallRecovery !== 'function') return false;

        stallStartedAt = null;
        lastProgressAt = Date.now();
        lastCurrentTime = Number(video.currentTime || 0);

        try {
            options.onStallRecovery(reason);
            return true;
        } catch (error) {
            console.warn(`[Playback] ${cctv?.name || 'CCTV'} stall recovery failed:`, error);
            return false;
        }
    };

    function markHealthy() {
        if (video.readyState >= 2 && video.videoWidth > 0) {
            hasStarted = true;
            stallStartedAt = null;
            lastProgressAt = Date.now();
        }
    }

    function markProgress() {
        const currentTime = Number(video.currentTime || 0);
        if (currentTime > lastCurrentTime + 0.05) {
            hasStarted = true;
            stallStartedAt = null;
            lastProgressAt = Date.now();
            lastCurrentTime = currentTime;
        }
    }

    function markStall() {
        if (!stallStartedAt) stallStartedAt = Date.now();
    }

    function failFast() {
        if (options.ignoreTransientErrors && video.dataset.allowTransientErrors === 'true') {
            return;
        }
        fail('video-error');
    }

    video.addEventListener('loadeddata', markHealthy);
    video.addEventListener('playing', markHealthy);
    video.addEventListener('canplay', markHealthy);
    video.addEventListener('timeupdate', markProgress);
    video.addEventListener('waiting', markStall);
    video.addEventListener('stalled', markStall);
    video.addEventListener('error', failFast);

    timers.push(setTimeout(() => {
        if (!hasStarted && (video.readyState < 2 || video.videoWidth === 0)) {
            fail('startup-timeout');
        }
    }, startupTimeoutMs));

    interval = setInterval(() => {
        if (!video.parentElement) {
            cleanup();
            return;
        }
        if (video.readyState >= 2 && video.videoWidth > 0) {
            const currentTime = Number(video.currentTime || 0);
            const progressed = currentTime > lastCurrentTime + 0.05;
            if (progressed) {
                hasStarted = true;
                stallStartedAt = null;
                lastProgressAt = Date.now();
                lastCurrentTime = currentTime;
                return;
            }
            if (!video.paused && Date.now() - lastProgressAt > stallTimeoutMs) {
                if (!recoverStall('playback-stalled')) {
                    fail('playback-stalled');
                }
            }
        } else if (stallStartedAt && Date.now() - stallStartedAt > stallTimeoutMs) {
            if (!hasStarted || !recoverStall('network-stalled')) {
                fail('network-stalled');
            }
        }
    }, 1800);

    video._watchdogCleanup = cleanup;
}

function handlePanelVideoHealthEvent(event) {
    const video = event.target;
    if (!video || video.tagName !== 'VIDEO') return;

    const panel = video.closest('.video-panel');
    const activeCctv = video._activeCctv || (video.dataset.activeCctvId ? findCctvById(video.dataset.activeCctvId) : null);
    const cctv = activeCctv || getPanelCctv(panel);
    if (!panel || !cctv) return;

    if (event.type === 'error') {
        if (video.dataset.allowTransientErrors === 'true') {
            return;
        }
        recordVideoQualityFailure(video, cctv, 'video-error');
        setPlaybackHealth(cctv, {
            status: 'PLAYBACK_ERROR',
            shortLabel: '재생 불안정',
            longLabel: `${cctv.name || 'CCTV'} 영상 재생 오류 감지`,
            tone: 'danger',
            penalty: 6
        });
    } else {
        recordVideoQualitySuccess(video, cctv);
        setPlaybackHealth(cctv, {
            status: 'PLAYING',
            shortLabel: '재생 정상',
            longLabel: `${cctv.name || 'CCTV'} 현재 브라우저에서 재생 확인`,
            tone: 'ok',
            penalty: 0
        });
    }

    updatePanelHealthUi(panel, cctv);
}

function scheduleVideoHealthProbe(panel, cctv, video) {
    if (!panel || !cctv || !video || video.tagName !== 'VIDEO') return;
    initVideoQualityTelemetry(panel, cctv, video);

    [600, 1600, 3200, 5200].forEach(delay => {
        setTimeout(() => {
            if (!video.parentElement || !panel.contains(video)) return;
            if (video.readyState >= 2 && video.videoWidth > 0) {
                recordVideoQualitySuccess(video, cctv);
                setPlaybackHealth(cctv, {
                    status: 'PLAYING',
                    shortLabel: '재생 정상',
                    longLabel: `${cctv.name || 'CCTV'} 현재 브라우저에서 재생 확인`,
                    tone: 'ok',
                    penalty: 0
                });
                updatePanelHealthUi(panel, cctv);
            }
        }, delay);
    });
}

function removePanelHealthBadge(panel) {
    const badge = panel.querySelector('.panel-health-badge');
    if (badge) badge.remove();
}

function findCctvById(cctvId) {
    if (!cctvId) return null;
    return state.cctvById.get(cctvId) || null;
}

function buildShareUrl(cctv) {
    const params = new URLSearchParams();
    params.set('lat', state.center.lat.toFixed(6));
    params.set('lng', state.center.lng.toFixed(6));
    params.set('name', state.keyword);
    params.set('mode', state.mode);
    if (cctv && cctv.id) {
        params.set('cctv', cctv.id);
    }
    return `${window.location.origin}${window.location.pathname}?${params.toString()}`;
}

function syncUrlState() {
    const activeCctv = findCctvById(state.activeCctvId);
    const nextUrl = buildShareUrl(activeCctv);
    window.history.replaceState({}, '', nextUrl);
}

async function shareCurrentView(cctv) {
    const shareUrl = buildShareUrl(cctv);
    const shareTitle = cctv ? `${cctv.name} CCTV` : `${state.keyword} 주변 CCTV`;
    const shareText = cctv ? `${state.keyword} 주변 ${cctv.name} CCTV를 확인해보세요.` : `${state.keyword} 주변 CCTV를 확인해보세요.`;

    try {
        if (navigator.share) {
            await navigator.share({
                title: shareTitle,
                text: shareText,
                url: shareUrl
            });
            return;
        }

        await navigator.clipboard.writeText(shareUrl);
        alert('공유 링크를 복사했습니다.');
    } catch (error) {
        console.warn('Share failed:', error);
    }
}

function openIssueReporter(cctv) {
    if (!cctv) return;

    const health = cctv._health || getCameraHealthMeta(cctv);
    const body = [
        '## 제보 내용',
        '',
        '- 장소: ' + state.keyword,
        '- CCTV 이름: ' + cctv.name,
        '- CCTV ID: ' + cctv.id,
        '- 지역 상태: ' + health.longLabel,
        '- 최근 점검: ' + formatRelativeTime(health.lastUpdated),
        '- 공유 링크: ' + buildShareUrl(cctv),
        '',
        '## 증상',
        '',
        '- [ ] 영상이 재생되지 않음',
        '- [ ] 재생이 매우 느림',
        '- [ ] 다른 영상이 보임',
        '- [ ] CCTV 명칭과 실제 화면이 맞지 않음',
        '- [ ] 지역 상태 안내와 실제 동작이 다름',
        '',
        '## 추가 메모',
        '',
        '여기에 관찰한 내용을 적어주세요.'
    ].join('\n');

    const issueUrl = `https://github.com/pyw31337/cctv/issues/new?title=${encodeURIComponent(`[CCTV] ${cctv.name} 연결 이슈`)}&body=${encodeURIComponent(body)}`;
    window.open(issueUrl, '_blank', 'noopener');
}

// === CCTV Logic ===
function updateNearestCctvs() {
    const { lat, lng } = state.center;
    const candidates = getNearbyCandidates(lat, lng, GEO_CANDIDATE_TARGET);

    const ranked = candidates
        .map(cctv => {
            const distance = getDistance(lat, lng, cctv.lat, cctv.lng);
            const health = getCameraHealthMeta(cctv);
            const streamQuality = getStreamQualityScore(cctv);
            const backupBonus = cctv.backup_urls && cctv.backup_urls.length > 0 ? 0.6 : 0;
            const roadContextPriority = getRoadContextPriority(cctv, distance);
            const trafficContextPriority = getTrafficContextPriority(cctv, distance);
            const sourceResilience = getSourceResilienceAdjustment(cctv, health, distance);
            const qualityAdjustment = getQualitySummaryAdjustment(cctv);
            const rankingHealthPenalty = getRankingHealthPenalty(cctv, health, distance);
            const priorityScore = getSortPriorityScore({
                distance,
                healthPenalty: rankingHealthPenalty,
                streamQuality,
                roadContextPriority,
                trafficContextPriority,
                sourceResilience,
                backupBonus,
                qualityAdjustment
            });

            return {
                ...cctv,
                distance,
                _health: health,
                _streamQuality: streamQuality,
                _roadContextPriority: roadContextPriority,
                _trafficContextPriority: trafficContextPriority,
                _sourceResilience: sourceResilience,
                _qualityAdjustment: qualityAdjustment,
                _rankingHealthPenalty: rankingHealthPenalty,
                _priorityScore: priorityScore
            };
        })
        .sort((a, b) => a._priorityScore - b._priorityScore || a.distance - b.distance);

    const preferred = ranked.filter(cctv => !shouldIsolateProblemCamera(cctv));
    const isolated = ranked.filter(cctv => shouldIsolateProblemCamera(cctv));
    const ordered = preferred.length >= 4
        ? preferred.concat(isolated)
        : ranked;

    state.nearestCctvs = ordered.slice(0, NEAREST_RESULT_LIMIT);
}

function renderVideoGrid() {
    const grid = $('#video-grid');
    const panels = grid.querySelectorAll('.video-panel');
    const visiblePanelCount = panels.length;

    panels.forEach((panel, index) => {
        const cctv = state.nearestCctvs[index];

        // Ensure Wrapper exists
        let wrapper = panel.querySelector('.video-content-wrapper');
        if (!wrapper) {
            wrapper = document.createElement('div');
            wrapper.className = 'video-content-wrapper';
            // Move existing placeholder or video into wrapper if naive structure
            const existingContent = panel.querySelector('.video-placeholder, iframe, video');
            if (existingContent) wrapper.appendChild(existingContent);
            panel.appendChild(wrapper);
            // Ensure controls are still on top (they are absolute)
        }

        // Clear wrapper content
        cleanupVideo(wrapper);
        panel.classList.remove('panel-suspended');
        resetPanelRetryState(panel);

        if (cctv) {
            // Create and insert video element
            const video = createVideoElement(cctv);
            wrapper.appendChild(video);
            if (video.tagName === 'VIDEO') {
                video.dataset.activeCctvId = cctv.id;
                video.dataset.sourceIndex = '0';
                video._activeCctv = cctv;
            }
            const loadingCopy = getStreamLoadingCopy(cctv);
            const loadingIndicator = showStreamLoadingIndicator(wrapper, loadingCopy.title, loadingCopy.detail);
            bindStreamLoadingIndicator(wrapper, video, loadingIndicator);

            panel.dataset.cctvId = cctv.id;
            panel.dataset.slotIndex = index;
            panel.dataset.cctvIndex = index;
            scheduleVideoHealthProbe(panel, cctv, video);

            // Update dropdown trigger with compact status dot instead of status text.
            renderSelectTrigger(panel, cctv, `CCTV ${index + 1}`);

            renderPanelHealthBadge(panel, cctv);

            // Populate dropdown options (up to 20 nearby CCTVs)
            populateSelectOptions(panel, index);
        } else {
            // Show placeholder
            const ph = document.createElement('div');
            ph.className = 'video-placeholder';
            ph.textContent = 'No CCTV';
            wrapper.appendChild(ph);
            removePanelHealthBadge(panel);
        }
    });

    // Attach event listeners (delegated)
    initPanelControls();
}

function getManualRetryCount(panel) {
    if (!panel || !panel.dataset) return 0;
    const count = Number(panel.dataset.manualRetryCount || 0);
    return Number.isFinite(count) ? Math.max(0, count) : 0;
}

function setManualRetryCount(panel, count) {
    if (!panel || !panel.dataset) return;
    panel.dataset.manualRetryCount = String(Math.max(0, Number(count) || 0));
}

function resetPanelRetryState(panel) {
    if (!panel || !panel.dataset) return;
    setManualRetryCount(panel, 0);
    panel._preparedRetryFallback = null;
    delete panel.dataset.preparedRetryFallbackId;
    delete panel.dataset.retrySourceId;
}

function getManualRetryFallbackDistance(sourceCctv, candidate) {
    const sourceLat = Number(sourceCctv?.lat);
    const sourceLng = Number(sourceCctv?.lng);
    const candidateLat = Number(candidate?.lat);
    const candidateLng = Number(candidate?.lng);

    if (Number.isFinite(sourceLat) && Number.isFinite(sourceLng)
        && Number.isFinite(candidateLat) && Number.isFinite(candidateLng)) {
        return getDistance(sourceLat, sourceLng, candidateLat, candidateLng);
    }

    const candidateDistance = Number(candidate?.distance);
    if (Number.isFinite(candidateDistance)) return candidateDistance;

    if (Number.isFinite(candidateLat) && Number.isFinite(candidateLng)
        && Number.isFinite(Number(state.center?.lat)) && Number.isFinite(Number(state.center?.lng))) {
        return getDistance(state.center.lat, state.center.lng, candidateLat, candidateLng);
    }

    return Number.POSITIVE_INFINITY;
}

function isManualRetryFallbackCandidate(candidate, sourceCctv) {
    if (!candidate || !candidate.id || candidate.id === sourceCctv?.id) return false;
    if (isUnsupportedBrowserStream(candidate) || shouldIsolateProblemCamera(candidate)) return false;
    if (!isDirectVideoPlaybackCandidate(candidate) || isFrameOnlyPlaybackCandidate(candidate)) return false;
    return Boolean(candidate.directUrl || candidate.url);
}

function getCctvReservationKeys(cctv) {
    if (!cctv) return [];
    const keys = [];
    const id = cctv.id || '';
    const source = cctv.source || '';
    const originalId = cctv.original_id || '';
    const url = cctv.directUrl || cctv.url || '';

    if (id) keys.push(`id:${id}`);
    if (originalId) keys.push(`origin:${source}:${originalId}`);
    if (url) keys.push(`url:${url}`);

    return keys;
}

function hasReservedCctvKey(cctv, reservedKeys) {
    if (!reservedKeys || reservedKeys.size === 0) return false;
    return getCctvReservationKeys(cctv).some(key => reservedKeys.has(key));
}

function addCctvReservationKeys(reservedKeys, cctv) {
    getCctvReservationKeys(cctv).forEach(key => reservedKeys.add(key));
}

function getManualRetryReservedKeys(currentPanel) {
    const reservedKeys = new Set();
    const panels = document.querySelectorAll ? document.querySelectorAll('.video-panel') : [];

    panels.forEach(panel => {
        if (panel === currentPanel) return;

        const activeCctv = getPanelCctv(panel);
        addCctvReservationKeys(reservedKeys, activeCctv);

        const prepared = panel._preparedRetryFallback?.cctv
            || findCctvById(panel.dataset?.preparedRetryFallbackId);
        addCctvReservationKeys(reservedKeys, prepared);
    });

    return reservedKeys;
}

function scoreManualRetryFallback(candidate, sourceCctv) {
    const health = candidate._health || getCameraHealthMeta(candidate);
    const confidence = getCameraPlaybackConfidence(candidate, health);
    const distance = getManualRetryFallbackDistance(sourceCctv, candidate);
    const streamQuality = candidate._streamQuality || getStreamQualityScore(candidate);
    const qualityAdjustment = candidate._qualityAdjustment || getQualitySummaryAdjustment(candidate);
    const distancePenalty = Number.isFinite(distance)
        ? distance + Math.max(0, distance - MANUAL_RETRY_FALLBACK_RADIUS_KM) * 0.75
        : 80;
    const toneAdjustment = {
        ok: -3.5,
        'ok-soft': -1.8,
        unknown: 0.8,
        warn: 4.5,
        danger: 30
    }[confidence.tone] ?? 1.5;
    const playbackBonus = health.status === 'PLAYING' ? -5 : 0;
    const backupBonus = candidate.backup_urls && candidate.backup_urls.length > 0 ? -0.8 : 0;

    return distancePenalty
        + ((health.penalty || 0) * 1.5)
        + ((1 - streamQuality) * 8)
        + qualityAdjustment
        + toneAdjustment
        + playbackBonus
        + backupBonus;
}

function findManualRetryFallback(sourceCctv, reservedKeys = new Set()) {
    if (!sourceCctv) return null;

    const lat = Number.isFinite(Number(sourceCctv.lat)) ? Number(sourceCctv.lat) : Number(state.center?.lat);
    const lng = Number.isFinite(Number(sourceCctv.lng)) ? Number(sourceCctv.lng) : Number(state.center?.lng);
    const nearby = Number.isFinite(lat) && Number.isFinite(lng)
        ? getNearbyCandidates(lat, lng, GEO_CANDIDATE_TARGET)
        : state.cctvData;
    const merged = [];
    const seen = new Set();

    [...state.nearestCctvs, ...nearby].forEach(candidate => {
        if (!candidate || !candidate.id || seen.has(candidate.id)) return;
        seen.add(candidate.id);
        merged.push(candidate);
    });

    const scored = merged
        .filter(candidate => isManualRetryFallbackCandidate(candidate, sourceCctv))
        .filter(candidate => !hasReservedCctvKey(candidate, reservedKeys))
        .map(candidate => ({
            candidate,
            distance: getManualRetryFallbackDistance(sourceCctv, candidate),
            score: scoreManualRetryFallback(candidate, sourceCctv)
        }))
        .sort((a, b) => a.score - b.score || a.distance - b.distance);

    const local = scored.find(item => Number.isFinite(item.distance) && item.distance <= MANUAL_RETRY_FALLBACK_RADIUS_KM);
    return (local || scored[0])?.candidate || null;
}

function prepareManualRetryFallback(panel, sourceCctv) {
    if (!panel || !sourceCctv) return null;
    const reservedKeys = getManualRetryReservedKeys(panel);
    const cached = panel._preparedRetryFallback;
    if (cached?.sourceId === sourceCctv.id
        && isManualRetryFallbackCandidate(cached.cctv, sourceCctv)
        && !hasReservedCctvKey(cached.cctv, reservedKeys)) {
        return cached.cctv;
    }

    const fallback = findManualRetryFallback(sourceCctv, reservedKeys);
    panel._preparedRetryFallback = fallback
        ? { sourceId: sourceCctv.id, cctv: fallback }
        : null;
    if (fallback) {
        panel.dataset.preparedRetryFallbackId = fallback.id;
        panel.dataset.retrySourceId = sourceCctv.id;
    } else {
        delete panel.dataset.preparedRetryFallbackId;
        delete panel.dataset.retrySourceId;
    }
    return fallback;
}

function switchToPreparedRetryFallback(panel, sourceCctv) {
    if (!panel || !sourceCctv) return false;
    let fallback = prepareManualRetryFallback(panel, sourceCctv);
    if (!fallback) return false;

    let fallbackIndex = state.nearestCctvs.findIndex(item => item.id === fallback.id);
    if (fallbackIndex === -1) {
        const distance = Number.isFinite(Number(fallback.distance))
            ? Number(fallback.distance)
            : getManualRetryFallbackDistance({ lat: state.center.lat, lng: state.center.lng }, fallback);
        state.nearestCctvs = [
            { ...fallback, distance, _health: getCameraHealthMeta(fallback) },
            ...state.nearestCctvs.filter(item => item.id !== fallback.id)
        ].slice(0, NEAREST_RESULT_LIMIT);
        fallbackIndex = 0;
        fallback = state.nearestCctvs[0];
    }

    recordQualityEvent(sourceCctv, 'fallback', {
        sourceIndex: MANUAL_RETRY_PRIMARY_ATTEMPTS + 1,
        usedFallback: true,
        reason: 'manual-retry-fallback'
    });
    attachStreamToPanel(panel, fallback, fallbackIndex);
    return true;
}

function populateSelectOptions(panel, currentIndex) {
    const optionsContainer = panel.querySelector('.cctv-select-options');
    if (!optionsContainer) return;

    // Clear existing options
    optionsContainer.innerHTML = '';

    // Add up to 20 recommended CCTVs as options
    const cctvList = state.nearestCctvs.slice(0, PANEL_OPTION_LIMIT);
    cctvList.forEach((cctv, i) => {
        const option = document.createElement('div');
        const health = getCameraHealthMeta(cctv);
        const confidence = getCameraPlaybackConfidence(cctv, health);
        option.className = `cctv-option confidence-${confidence.tone}` + (i === currentIndex ? ' selected' : '');
        const name = document.createElement('span');
        name.className = 'cctv-option-name';
        name.textContent = cctv.name || `CCTV ${i + 1}`;

        const statusDot = document.createElement('span');
        statusDot.className = `cctv-status-dot tone-${confidence.tone}`;
        statusDot.title = confidence.title;
        statusDot.setAttribute('aria-hidden', 'true');

        option.append(name, statusDot);
        option.dataset.cctvIndex = i;
        option.dataset.confidence = confidence.tone;
        option.title = `${confidence.label} · ${confidence.title} · ${health.longLabel} · ${formatRelativeTime(health.lastUpdated)}`;
        option.setAttribute('aria-label', `${name.textContent}, ${confidence.label}`);
        optionsContainer.appendChild(option);
    });
}

function initPanelControls() {
    // Event delegation for panel controls
    const grid = $('#video-grid');

    // Remove existing listeners by cloning (simple approach)
    // Actually, we'll use a flag to prevent duplicate listeners
    if (grid.dataset.initialized === 'true') return;
    grid.dataset.initialized = 'true';

    ['loadeddata', 'playing', 'canplay', 'error'].forEach(eventName => {
        grid.addEventListener(eventName, handlePanelVideoHealthEvent, true);
    });

    // Dropdown trigger click
    grid.addEventListener('click', (e) => {
        const trigger = e.target.closest('.cctv-select-trigger');
        if (trigger) {
            e.stopPropagation();
            const container = trigger.parentElement;
            const options = container.querySelector('.cctv-select-options');

            // Close other dropdowns first
            document.querySelectorAll('.cctv-select-options.active').forEach(opt => {
                if (opt !== options) {
                    opt.classList.remove('active');
                    // Remove z-active from parent panel
                    opt.closest('.video-panel').classList.remove('z-active');
                }
            });

            const isActive = options.classList.toggle('active');
            const panel = trigger.closest('.video-panel');
            if (isActive) {
                panel.classList.add('z-active');
            } else {
                panel.classList.remove('z-active');
            }
            return;
        }

        // Option click
        const option = e.target.closest('.cctv-option');
        if (option) {
            e.stopPropagation();
            const panel = option.closest('.video-panel');
            const slotIndex = parseInt(panel.dataset.slotIndex);
            const cctvIndex = parseInt(option.dataset.cctvIndex);
            const cctv = state.nearestCctvs[cctvIndex];

            if (cctv) {
                // Switch this panel to selected CCTV
                attachStreamToPanel(panel, cctv, cctvIndex);
            }

            // Close dropdown
            const opts = option.closest('.cctv-select-options');
            opts.classList.remove('active');
            panel.classList.remove('z-active');
            return;
        }

        // Expand button click
        const expandBtn = e.target.closest('.panel-expand-btn');
        if (expandBtn) {
            e.stopPropagation();
            const panel = expandBtn.closest('.video-panel');
            togglePanelExpand(panel, expandBtn);
            return;
        }

        // Refresh button click
        const refreshBtn = e.target.closest('.panel-refresh-btn');
        if (refreshBtn) {
            // This button is removed from HTML but let's keep the handler for backward compatibility 
            // or if we use it in other layers.
            e.stopPropagation();
            const panel = refreshBtn.closest('.video-panel');
            const cctvIndex = parseInt(panel.dataset.cctvIndex);
            const cctv = state.nearestCctvs[cctvIndex];
            if (cctv) {
                attachStreamToPanel(panel, cctv, cctvIndex);
            }
            return;
        }

        // Floating close button click (collapse expanded panel)
        const floatingClose = e.target.closest('.panel-floating-close');
        if (floatingClose) {
            e.stopPropagation();
            const panel = floatingClose.closest('.video-panel');
            if (panel && panel.classList.contains('expanded')) {
                const expandBtn = panel.querySelector('.panel-expand-btn');
                togglePanelExpand(panel, expandBtn);
            }
            return;
        }
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.cctv-select-options.active').forEach(opt => {
            opt.classList.remove('active');
            opt.closest('.video-panel').classList.remove('z-active');
        });
    });
}

function attachStreamToPanel(panel, cctv, cctvIndex) {
    resetPanelRetryState(panel);

    // Use Wrapper
    let wrapper = panel.querySelector('.video-content-wrapper');
    if (!wrapper) {
        wrapper = document.createElement('div');
        wrapper.className = 'video-content-wrapper';
        panel.appendChild(wrapper);
    }

    cleanupVideo(wrapper);

    // Create new video element
    const video = createVideoElement(cctv);
    wrapper.appendChild(video);
    if (video.tagName === 'VIDEO') {
        video.dataset.activeCctvId = cctv.id;
        video.dataset.sourceIndex = '0';
        video._activeCctv = cctv;
    }
    const loadingCopy = getStreamLoadingCopy(cctv);
    const loadingIndicator = showStreamLoadingIndicator(wrapper, loadingCopy.title, loadingCopy.detail);
    bindStreamLoadingIndicator(wrapper, video, loadingIndicator);

    // Update panel data
    panel.dataset.cctvId = cctv.id;
    panel.dataset.cctvIndex = cctvIndex;
    scheduleVideoHealthProbe(panel, cctv, video);

    // Update trigger with compact status dot instead of status text.
    renderSelectTrigger(panel, cctv, `CCTV ${cctvIndex + 1}`);

    // Update selected option
    const options = panel.querySelectorAll('.cctv-option');
    options.forEach((opt, i) => {
        opt.classList.toggle('selected', i === cctvIndex);
    });

    renderPanelHealthBadge(panel, cctv);
}

function togglePanelExpand(panel, btn) {
    const isExpanded = panel.classList.toggle('expanded');

    // Update button icon
    if (isExpanded) {
        // Minimize icon
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M10 14L3 21"/>
        </svg>`;
        btn.title = '축소';
    } else {
        // Expand icon
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/>
        </svg>`;
        btn.title = '확대';
    }

    // Update layout for UTIC scaling
    setTimeout(updateUticLayout, 350); // Small delay for transition
}

function createVideoElement(cctv, sourceIndex = 0) {
    if (sourceIndex === 0 && isUnsupportedBrowserStream(cctv)) {
        return createErrorPlaceholder({
            message: '이 카메라는 원본 제공처가 구형 전용 플레이어만 지원합니다',
            detail: '현재 웹 앱에서는 바로 재생할 수 없어, 제주권 대체 카메라를 우선 추천합니다.',
            cctv
        });
    }

    // Determine URL based on sourceIndex
    // Index 0 = Main URL, Index 1+ = Backup URLs
    let url, type, selectedSource, selectedOriginalId;

    if (sourceIndex === 0) {
        url = cctv.directUrl || cctv.url;
        type = 'main';
        selectedSource = cctv.source || '';
        selectedOriginalId = cctv.original_id || '';

    } else {
        const backup = normalizeBackupEntry(cctv.backup_urls && cctv.backup_urls[sourceIndex - 1], cctv);
        if (backup) {
            url = backup.url;
            type = `backup-${sourceIndex}`;
            selectedSource = backup.source || cctv.source || '';
            selectedOriginalId = backup.original_id || backup.id || '';
        } else {
            console.warn(`No backup source found at index ${sourceIndex}`);
            return createErrorPlaceholder({
                message: '대체 소스를 찾지 못했습니다',
                detail: '대체 스트림 정보를 불러오지 못했습니다.',
                cctv
            });
        }
    }

    const shouldProxy = url && !url.includes('cctv-proxy.pyw213.workers.dev');
    const sourceFallbackId = selectedOriginalId || cctv.original_id || ((cctv.id || '').includes('_') ? cctv.id.split('_').pop() : cctv.id);
    const selectedCctvIp = getUrlParam(url, 'cctvip') || sourceFallbackId;
    const selectedCctvId = getUrlParam(url, 'cctvid') || cctv.id || sourceFallbackId;
    const selectedKind = getUrlParam(url, 'kind');
    const selectedJejuUticStreamId = selectedSource === 'UTIC' && selectedKind === 'K' && inferRegionKey(cctv) === 'JEJU'
        ? getUrlParam(url, 'id')
        : null;
    const genericProxyBase = isRawIpStreamUrl(url)
        ? 'https://158.179.194.163.sslip.io/proxy'
        : 'https://cctv-proxy.pyw213.workers.dev/proxy';

    if (selectedJejuUticStreamId) {
        url = `${JEJU_PROXY_BASE}?id=${encodeURIComponent(selectedJejuUticStreamId)}&_t=${Date.now()}`;
        selectedSource = 'JEJU';
        selectedOriginalId = selectedJejuUticStreamId;
    } else if (selectedSource === 'KBS' && selectedCctvIp) {
        url = `${KB_PROXY_BASE}?cctvip=${encodeURIComponent(selectedCctvIp)}&_t=${Date.now()}`;
    } else if ((selectedSource === 'NTIC' || selectedKind === 'Z3') && selectedCctvIp) {
        url = `${ORACLE_BASE}/utic?kind=Z3&cctvid=${encodeURIComponent(selectedCctvId)}&cctvip=${encodeURIComponent(selectedCctvIp)}&_t=${Date.now()}`;
    } else if (shouldProxy) {
        if (selectedSource === 'TRENDWORLD' || selectedSource === 'NOWJEJU' || selectedSource === 'HRFCO') {
            url = `${genericProxyBase}?url=${encodeURIComponent(url)}&_t=${Date.now()}`;
        } else if (selectedSource === 'JEJU') {
            const jejuStreamId = getUrlParam(url, 'id') || selectedOriginalId || sourceFallbackId;
            url = `${JEJU_PROXY_BASE}?id=${encodeURIComponent(jejuStreamId)}&_t=${Date.now()}`;
        } else if (selectedSource === 'UTIC' && selectedCctvIp && ['EE', 'EEE', 'KB'].includes(selectedKind)) {
            url = `${KB_PROXY_BASE}?cctvip=${encodeURIComponent(selectedCctvIp)}&_t=${Date.now()}`;
        }
    }

    const is43 = cctv.aspectRatio === '4:3';

    // Helper to trigger failover
    const triggerFailover = (wrapper) => {
        console.log(`[Failover] Stream failed for ${cctv.name} (Index ${sourceIndex}). Trying next...`);
        handleStreamFailover(wrapper, cctv, sourceIndex + 1);
    };

    // Handle Daejeon traffic-center MP4 snapshots directly instead of embedding the UTIC legacy frame.
    if (isDaejeonDirectMp4Candidate(cctv, url, selectedSource, selectedKind, selectedCctvIp, selectedOriginalId)) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';

        const streamId = getDaejeonStreamId(cctv, url, selectedOriginalId);
        const mediaPath = getDaejeonMediaPath(url, selectedCctvIp, streamId);
        const getDaejeonUrl = (offsetMins) => {
            const now = new Date();
            const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
            const kst = new Date(utc + (9 * 60 * 60 * 1000));
            kst.setMinutes(kst.getMinutes() - offsetMins);
            const yyyy = kst.getFullYear();
            const mm = String(kst.getMonth() + 1).padStart(2, '0');
            const dd = String(kst.getDate()).padStart(2, '0');
            const hh = String(kst.getHours()).padStart(2, '0');
            const min = String(kst.getMinutes()).padStart(2, '0');
            const sec = '00';
            const timestamp = `${yyyy}${mm}${dd}.${hh}${min}${sec}`;
            return `https://tportal.daejeon.go.kr:37084/${mediaPath}/media/${streamId}/${streamId}_${timestamp}.000.mp4`;
        };

        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        const offsets = [2, 3, 4, 5, 6, 7, 8, 9, 10, 1];
        let attemptIndex = 0;
        let refreshCycle = 0;
        let candidateTimer = null;
        let refreshTimer = null;

        const clearCandidateTimer = () => {
            if (candidateTimer) {
                clearTimeout(candidateTimer);
                candidateTimer = null;
            }
        };

        const clearDaejeonTimers = () => {
            clearCandidateTimer();
            if (refreshTimer) {
                clearTimeout(refreshTimer);
                refreshTimer = null;
            }
        };

        const armCandidateTimer = () => {
            clearCandidateTimer();
            candidateTimer = setTimeout(() => {
                if (video.readyState >= 2) return;
                tryNextDaejeonUrl();
            }, 2800);
        };

        const tryNextDaejeonUrl = () => {
            clearDaejeonTimers();
            if (attemptIndex >= offsets.length) {
                if (!video.parentElement) return;
                if (refreshCycle < 1) {
                    refreshCycle += 1;
                    attemptIndex = 0;
                    refreshTimer = setTimeout(tryNextDaejeonUrl, 1200);
                    return;
                }
                triggerFailover(video.parentElement);
                return;
            }
            const offset = offsets[attemptIndex];
            attemptIndex += 1;
            video.dataset.allowTransientErrors = 'true';
            video.src = getDaejeonUrl(offset);
            video.load();
            armCandidateTimer();
            video.play().catch(() => {});
        };

        const markDaejeonPlayable = () => {
            delete video.dataset.allowTransientErrors;
            clearCandidateTimer();
        };

        video.addEventListener('loadeddata', markDaejeonPlayable);
        video.addEventListener('playing', markDaejeonPlayable);
        video.addEventListener('canplay', markDaejeonPlayable);
        video._daejeonCleanup = clearDaejeonTimers;
        video.onerror = tryNextDaejeonUrl;
        video.onended = () => {
            clearDaejeonTimers();
            attemptIndex = 0;
            refreshCycle = 0;
            refreshTimer = setTimeout(tryNextDaejeonUrl, 700);
        };
        tryNextDaejeonUrl();
        armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement), {
            ignoreTransientErrors: true,
            startupTimeoutMs: STABLE_HLS_STARTUP_TIMEOUT_MS,
            stallTimeoutMs: DAEJEON_MP4_STALL_RECOVERY_MS,
            onStallRecovery: () => {
                clearDaejeonTimers();
                attemptIndex = 0;
                refreshCycle = 0;
                tryNextDaejeonUrl();
            }
        });
        return video;
    }

    // Handle Jeju streams explicitly
    if (cctv.source === 'JEJU' && sourceIndex === 0) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        // URL is already prepared at the beginning of the function
        const jejuUrl = url;

        if (Hls.isSupported()) {
            const hls = new Hls({
                enableWorker: true,
                lowLatencyMode: true,
                capLevelToPlayerSize: true,
                maxBufferLength: 30,
                maxMaxBufferLength: 60,
                fragLoadingTimeOut: 12000,
                manifestLoadingTimeOut: JEJU_PLAYBACK_STARTUP_TIMEOUT_MS,
                manifestLoadingMaxRetry: 2,
                manifestLoadingRetryDelay: 700,
                manifestLoadingMaxRetryTimeout: 5000,
                levelLoadingMaxRetry: 2,
                levelLoadingRetryDelay: 700,
                levelLoadingMaxRetryTimeout: 5000,
                fragLoadingMaxRetry: 2,
                fragLoadingRetryDelay: 700,
                fragLoadingMaxRetryTimeout: 4000,
            });
            hls.on(Hls.Events.MANIFEST_PARSED, function () {
                video.play().catch(() => {});
            });

            let recoveryAttempts = 0;
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (!data.fatal) return;

                const statusCode = Number(data && data.response && (data.response.code || data.response.status));
                if (statusCode >= 400) {
                    triggerFailover(video.parentElement);
                    return;
                }

                const isNetworkError = data.type === Hls.ErrorTypes.NETWORK_ERROR;
                const isMediaError = data.type === Hls.ErrorTypes.MEDIA_ERROR;
                if ((isNetworkError || isMediaError) && recoveryAttempts < 2) {
                    recoveryAttempts += 1;
                    setTimeout(() => {
                        if (!video.parentElement) return;
                        if (isMediaError && typeof hls.recoverMediaError === 'function') {
                            hls.recoverMediaError();
                        }
                        hls.startLoad(-1);
                    }, Math.min(1000 * recoveryAttempts, 6000));
                    return;
                }
                triggerFailover(video.parentElement);
            });

            hls.attachMedia(video);
            resolveJejuPlaybackUrl(jejuUrl)
                .then((resolvedUrl) => {
                    hls.loadSource(resolvedUrl);
                })
                .catch((error) => {
                    console.warn('[JEJU] Manifest resolve failed:', error);
                    triggerFailover(video.parentElement);
                });

            video.hls = hls;
        } else {
            video.src = jejuUrl;
            video.onerror = () => triggerFailover(video.parentElement);
        }
        armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement), {
            startupTimeoutMs: JEJU_PLAYBACK_STARTUP_TIMEOUT_MS,
            stallTimeoutMs: PLAYBACK_STALL_TIMEOUT_MS
        });
        return video;
    }

    // EE kind cameras OR /kb proxy URLs: play full-size MP4 video via Korean server
    // directUrl in cctv_data.json is pre-set to /kb?cctvip=X for EE cameras
    if (url.includes('/kb?cctvip=') || (url.includes('kind=EE') && url.includes('cctvip='))) {
        let kbUrl = url;
        const cctvipMatch = url.match(/[?&]cctvip=(\d+)/);
        if (cctvipMatch) {
            kbUrl = `${KB_PROXY_BASE}?cctvip=${cctvipMatch[1]}`;
        }
        if (!kbUrl.includes('_t=')) kbUrl += `&_t=${Date.now()}`;
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        const shouldUseKbsHls = selectedSource === 'KBS' || selectedKind === 'KB' || cctv.source === 'KBS';
        if (shouldUseKbsHls && window.Hls && Hls.isSupported()) {
            const hls = new Hls({
                enableWorker: true,
                lowLatencyMode: false,
                manifestLoadingMaxRetry: 2,
                levelLoadingMaxRetry: 2,
                fragLoadingMaxRetry: 2,
            });
            hls.on(Hls.Events.MANIFEST_PARSED, function () {
                video.play().catch(() => {});
            });
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data && data.fatal) {
                    triggerFailover(video.parentElement);
                }
            });
            hls.attachMedia(video);
            hls.loadSource(kbUrl);
            video.hls = hls;
        } else {
            video.src = kbUrl;
            video.onerror = () => triggerFailover(video.parentElement);
        }
        armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement));
        return video;
    }

    const isHls = url.includes('.m3u8');
    const isMp4 = url.includes('.mp4');
    const isUtic = url.includes('utic.go.kr') || url.includes('openDataCctvStream');
    const isItsEmbed = url.includes('its.gn.go.kr/popup') || url.includes('gangneung_player.html') || url.includes('hrfco.go.kr');
    const isSecureStream = url.includes('cctvsec.ktict.co.kr');
    const isProxy = url.includes('cctv-proxy-hoon-001.fly.dev')
        || url.includes('cctv-proxy.pyw213.workers.dev')
        || url.includes('158.179.194.163.sslip.io/proxy');
    const isKnownHlsSource = ['NOWJEJU', 'TRENDWORLD', 'JEJU', 'HRFCO'].includes(selectedSource);
    const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
    const isGits = selectedSource === 'GITS';

    // YouTube Handling
    if (isYouTube) {
        let videoId = null;
        if (url.includes('v=')) {
            videoId = url.split('v=')[1].split('&')[0];
        } else if (url.includes('youtu.be/')) {
            videoId = url.split('youtu.be/')[1].split('?')[0];
        }

        if (videoId) {
            const iframe = document.createElement('iframe');
            iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1&playsinline=1&controls=0`;
            iframe.className = 'youtube-iframe';
            iframe.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;border:none;display:block;';
            iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
            iframe.allowFullscreen = true;
            return iframe;
        }
    }

    // GITS: resolve through the same Oracle endpoint used by health checks.
    if (isGits && (selectedOriginalId || cctv.original_id)) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        const gitsId = selectedOriginalId || cctv.original_id;
        const gitsUrl = `${ORACLE_BASE}/gits?cctvip=${encodeURIComponent(gitsId)}&_t=${Date.now()}`;
        const failGits = () => {
            if (video.parentElement) triggerFailover(video.parentElement);
        };

        if (window.Hls && Hls.isSupported()) {
            const hls = new Hls({
                enableWorker: true,
                lowLatencyMode: true,
                capLevelToPlayerSize: true,
                manifestLoadingTimeOut: 12000,
                manifestLoadingMaxRetry: 1,
                levelLoadingMaxRetry: 1,
                fragLoadingMaxRetry: 1,
            });
            hls.on(Hls.Events.MANIFEST_PARSED, function () {
                video.play().catch(() => {});
            });
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data && data.fatal) {
                    hls.destroy();
                    failGits();
                }
            });
            hls.attachMedia(video);
            hls.loadSource(gitsUrl);
            video.hls = hls;
        } else {
            video.src = gitsUrl;
            video.onerror = failGits;
        }
        armVideoPlaybackWatchdog(video, cctv, failGits);

        return video;
    }

    // MP4 / Native (non-GITS)
    if (isMp4) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.src = url;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        video.onerror = () => triggerFailover(video.parentElement);
        armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement));
        return video;
    }

    // UTIC Portal - play natively via worker/oracle resolver.
    // Z3 kind: look up fresh stream URL from z3_cache.json (updated hourly by GitHub Actions)
    // Other kinds: extract real m3u8 URL via /utic endpoint. If that fails, prefer frame-free alternatives.
    if (isUtic) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        const isZ3 = url.includes('kind=Z3');
        const cctvipMatch = url.match(/[?&]cctvip=(\d+)/);
        const z3CctvIp = isZ3 && cctvipMatch ? cctvipMatch[1] : null;

        (async () => {
            let streamUrl = null;

            try {
                if (isZ3 && z3CctvIp) {
                    // Z3 전략 1: z3_cache.json (its.go.kr에서 매시간 갱신되는 신선한 토큰)
                    try {
                        const cacheWorkerUrl = await getZ3StreamUrl(z3CctvIp);
                        if (cacheWorkerUrl) {
                            const cacheResp = await fetch(cacheWorkerUrl, { cache: 'no-store' });
                            if (cacheResp.ok) {
                                const cacheText = (await cacheResp.text()).trim();
                                if (cacheText && cacheText.startsWith('http')) streamUrl = cacheText;
                            }
                        }
                    } catch(e2) { console.warn('[Z3] 전략1 실패:', e2); }

                    // Z3 전략 2: cctv_data.json의 id 파라미터 사용 (fallback)
                    if (!streamUrl) {
                        try {
                            const idParam = new URL(url).searchParams.get('id');
                            if (idParam) {
                                // URLSearchParams는 literal +를 space로 디코딩 → 복원
                                const tokenUrl = `https://cctvsec.ktict.co.kr/${idParam.replace(/ /g, '+')}`;
                                const z3Resp = await fetch(
                                    `https://cctv-proxy.pyw213.workers.dev/z3?url=${encodeURIComponent(tokenUrl)}`,
                                    { cache: 'no-store' }
                                );
                                if (z3Resp.ok) {
                                    const text = (await z3Resp.text()).trim();
                                    if (text && text.startsWith('http')) streamUrl = text;
                                }
                            }
                        } catch(e2) { console.warn('[Z3] 전략2 실패:', e2); }
                    }

                    // Z3 전략 3: Oracle /utic가 GitHub 최신 캐시를 읽고 /proxy로 리다이렉트한다.
                    if (!streamUrl) {
                        try {
                            let uticSearch = '';
                            try { uticSearch = new URL(url).search.substring(1); } catch(e3) {}
                            if (uticSearch) streamUrl = `${ORACLE_BASE}/utic?${uticSearch}&_t=${Date.now()}`;
                        } catch(e2) { console.warn('[Z3] 전략3 실패:', e2); }
                    }

                    if (!streamUrl) throw new Error('z3 all strategies failed');
                    streamUrl = normalizeResolvedZ3StreamUrl(streamUrl);
                } else {
                    // Non-Z3 UTIC: fetch from JSP via CF Worker /utic
                    let uticSearch = '';
                    try { uticSearch = new URL(url).search.substring(1); } catch(e) {}
                    const workerUrl = `https://cctv-proxy.pyw213.workers.dev/utic?${uticSearch}&_t=${Date.now()}`;
                    const resp = await fetch(workerUrl, { redirect: 'follow' });
                    if (!resp.ok) throw new Error('utic ' + resp.status);
                    const body = (await resp.text()).trim();
                    streamUrl = body.startsWith('http') ? body : resp.url;
                    if (!streamUrl || !streamUrl.startsWith('http')) throw new Error('bad url');
                }

                if (!video.parentElement) return;

                if (Hls.isSupported()) {
                    const hls = new Hls({
                        enableWorker: true,
                        lowLatencyMode: true,
                        capLevelToPlayerSize: true,
                        maxBufferLength: 30,
                        maxMaxBufferLength: 60,
                        fragLoadingTimeOut: 30000,
                        manifestLoadingTimeOut: 15000,
                    });
                    hls.loadSource(streamUrl);
                    hls.attachMedia(video);
                    hls.on(Hls.Events.ERROR, function(ev, data) {
                        if (data.fatal) {
                            hls.destroy();
                            if (video.parentElement) fallbackToDirectAlternative(video.parentElement);
                        }
                    });
                    video.hls = hls;
                } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                    video.src = streamUrl;
                    video.onerror = () => { if (video.parentElement) fallbackToDirectAlternative(video.parentElement); };
                } else {
                    if (video.parentElement) fallbackToDirectAlternative(video.parentElement);
                }
            } catch(e) {
                console.error('[UTIC] Stream resolve failed:', e);
                if (video.parentElement) fallbackToDirectAlternative(video.parentElement);
            }

            function fallbackToDirectAlternative(wrapper) {
                triggerFailover(wrapper);
            }
        })();

        return video;
    }

    // ITS Popup embeds (gangneung, hrfco etc.) - keep as iframe
    if (isItsEmbed) {
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.className = 'utic-iframe';
        iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;';
        iframe.allow = 'autoplay; fullscreen';
        iframe.scrolling = 'no';
        iframe.setAttribute('allowfullscreen', '');
        if (is43) iframe.dataset.aspectRatio = '4:3';
        return iframe;
    }

    // HLS streams (Hls.js)
    if ((isHls || isSecureStream || isProxy || isKnownHlsSource) && Hls.isSupported()) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        const isJejuHlsSource = selectedSource === 'JEJU';
        const failFastHlsSource = ['JEJU', 'NOWJEJU'].includes(selectedSource);
        const hlsStartupTimeoutMs = isJejuHlsSource
            ? JEJU_PLAYBACK_STARTUP_TIMEOUT_MS
            : (failFastHlsSource ? PLAYBACK_STARTUP_TIMEOUT_MS : STABLE_HLS_STARTUP_TIMEOUT_MS);
        const hlsStallTimeoutMs = failFastHlsSource ? PLAYBACK_STALL_TIMEOUT_MS : STABLE_HLS_STALL_TIMEOUT_MS;
        const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
            capLevelToPlayerSize: true,
            maxBufferLength: 30,
            maxMaxBufferLength: 60,
            fragLoadingTimeOut: isJejuHlsSource ? JEJU_PLAYBACK_STARTUP_TIMEOUT_MS : (failFastHlsSource ? 12000 : 30000),
            manifestLoadingTimeOut: isJejuHlsSource ? JEJU_PLAYBACK_STARTUP_TIMEOUT_MS : (failFastHlsSource ? 10000 : 15000),
            manifestLoadingMaxRetry: isJejuHlsSource ? 2 : (failFastHlsSource ? 1 : 8),
            manifestLoadingRetryDelay: 700,
            manifestLoadingMaxRetryTimeout: isJejuHlsSource ? 5000 : (failFastHlsSource ? 3000 : 8000),
            levelLoadingMaxRetry: isJejuHlsSource ? 2 : (failFastHlsSource ? 1 : 8),
            levelLoadingRetryDelay: 700,
            levelLoadingMaxRetryTimeout: isJejuHlsSource ? 5000 : (failFastHlsSource ? 3000 : 8000),
            fragLoadingMaxRetry: failFastHlsSource ? 2 : 8,
            fragLoadingRetryDelay: 700,
            fragLoadingMaxRetryTimeout: failFastHlsSource ? 4000 : 8000,
            maxBufferSize: 30 * 1000 * 1000,
        });

        hls.on(Hls.Events.MANIFEST_PARSED, function () {
            video.play().catch(() => {});
        });

        let hlsFailoverTriggered = false;
        let hlsStartupTimer = null;
        let recoveryAttempts = 0;
        const failoverFromHls = () => {
            if (hlsFailoverTriggered) return;
            hlsFailoverTriggered = true;
            const wrapper = video.parentElement;
            if (hlsStartupTimer) {
                clearTimeout(hlsStartupTimer);
                hlsStartupTimer = null;
            }
            hls.destroy();
            triggerFailover(wrapper);
        };

        if (selectedSource === 'NOWJEJU') {
            hlsStartupTimer = setTimeout(() => {
                if (video.readyState < 2) {
                    failoverFromHls();
                }
            }, 7000);
            video.addEventListener('loadeddata', () => {
                if (hlsStartupTimer) {
                    clearTimeout(hlsStartupTimer);
                    hlsStartupTimer = null;
                }
            }, { once: true });
        }

        hls.on(Hls.Events.ERROR, function (event, data) {
            const statusCode = Number(data && data.response && (data.response.code || data.response.status));
            const shouldFailFast = ['JEJU', 'NOWJEJU'].includes(selectedSource) && statusCode >= 400;
            const isJejuHls = selectedSource === 'JEJU';
            const isRecoverable = data.type === Hls.ErrorTypes.NETWORK_ERROR || data.type === Hls.ErrorTypes.MEDIA_ERROR;

            if (shouldFailFast) {
                failoverFromHls();
                return;
            }

            if (data.fatal && isRecoverable && recoveryAttempts < (isJejuHls ? 2 : 3)) {
                recoveryAttempts += 1;
                setTimeout(() => {
                    if (!video.parentElement) return;
                    if (data.type === Hls.ErrorTypes.MEDIA_ERROR && typeof hls.recoverMediaError === 'function') {
                        hls.recoverMediaError();
                    }
                    hls.startLoad(-1);
                }, Math.min(1000 * recoveryAttempts, 6000));
                return;
            }

            if (data.fatal || shouldFailFast) {
                // NOWJEJU sometimes publishes stale variant playlists. Do not make users wait through HLS retries.
                failoverFromHls();
            }
        });

        hls.attachMedia(video);
        const loadHlsSource = (sourceUrl) => {
            if (hlsFailoverTriggered) return;
            hls.loadSource(sourceUrl);
        };
        if (isJejuHlsSource) {
            resolveJejuPlaybackUrl(url)
                .then(loadHlsSource)
                .catch((error) => {
                    console.warn('[JEJU] Manifest resolve failed:', error);
                    failoverFromHls();
                });
        } else {
            loadHlsSource(url);
        }

        video.hls = hls;
        armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement), {
            startupTimeoutMs: hlsStartupTimeoutMs,
            stallTimeoutMs: hlsStallTimeoutMs
        });
        return video;
    }

    // Native HLS (Safari)
    const video = document.createElement('video');
    video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
    if (is43) video.dataset.aspectRatio = '4:3';
    video.src = url;
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;

    video.onerror = () => triggerFailover(video.parentElement);
    armVideoPlaybackWatchdog(video, cctv, () => triggerFailover(video.parentElement));

    return video;
}

function ensureDynamicBackups(cctv) {
    if (!cctv || cctv._dynamicFallbacksAdded) return;
    const backupSource = isJejuUticProxyable(cctv) ? 'JEJU' : cctv.source;
    if (!['JEJU', 'NOWJEJU', 'TRENDWORLD'].includes(backupSource)) return;
    if (!Number.isFinite(Number(cctv.lat)) || !Number.isFinite(Number(cctv.lng))) return;

    const backupUrls = Array.isArray(cctv.backup_urls)
        ? cctv.backup_urls.map(item => normalizeBackupEntry(item, cctv)).filter(Boolean)
        : [];
    const knownUrls = new Set([cctv.directUrl, cctv.url, ...backupUrls.map(item => item && item.url)].filter(Boolean));
    const jejuStatus = state.regionHealth.JEJU?.status || '';
    const jejuIsUnstable = ['DEGRADED', 'DOWN'].includes(jejuStatus);
    const preferredSources = backupSource === 'JEJU' && jejuIsUnstable
        ? ['NOWJEJU', 'TRENDWORLD', 'JEJU', 'GITS']
        : ['JEJU', 'NOWJEJU', 'TRENDWORLD', 'GITS'];

    const nearbyBackupCandidates = state.cctvData
        .filter(item => item && item.id !== cctv.id && preferredSources.includes(item.source))
        .filter(item => !isUnsupportedBrowserStream(item))
        .map(item => ({
            item,
            distance: getDistance(cctv.lat, cctv.lng, item.lat, item.lng)
        }))
        .filter(({ item, distance }) => Number.isFinite(distance) && distance <= DYNAMIC_BACKUP_RADIUS_KM && (item.directUrl || item.url) && !knownUrls.has(item.directUrl || item.url))
        .sort((a, b) => {
            const sourceDelta = preferredSources.indexOf(a.item.source) - preferredSources.indexOf(b.item.source);
            const sameSpotDelta = Number(a.distance > 0.25) - Number(b.distance > 0.25);
            return sameSpotDelta || sourceDelta || a.distance - b.distance;
        });
    const rotation = backupSource === 'JEJU' && nearbyBackupCandidates.length > 1
        ? getStableModulo(cctv.id || cctv.name, Math.min(nearbyBackupCandidates.length, 5))
        : 0;
    const rotatedBackupCandidates = nearbyBackupCandidates
        .slice(rotation)
        .concat(nearbyBackupCandidates.slice(0, rotation));
    const nearbyBackups = rotatedBackupCandidates
        .slice(0, 5)
        .map(({ item }) => ({
            id: item.id,
            source: item.source,
            url: item.directUrl || item.url,
            name: item.name,
            original_id: item.original_id,
            lat: item.lat,
            lng: item.lng,
            distance: getDistance(cctv.lat, cctv.lng, item.lat, item.lng)
        }));

    if (nearbyBackups.length > 0) {
        cctv.backup_urls = backupUrls.concat(nearbyBackups);
    } else {
        cctv.backup_urls = backupUrls;
    }
    cctv._dynamicFallbacksAdded = true;
}

function normalizeBackupEntry(backup, cctv) {
    if (!backup) return null;
    if (typeof backup === 'string') {
        return {
            source: cctv?.source || '',
            url: backup,
            name: cctv?.name || '대체 영상'
        };
    }
    if (!backup.url) return null;
    return backup;
}

function getActiveStreamCctv(cctv, sourceIndex) {
    if (!cctv || sourceIndex === 0) return cctv;

    const backup = normalizeBackupEntry(cctv.backup_urls && cctv.backup_urls[sourceIndex - 1], cctv);
    if (!backup) return cctv;

    const matched = backup.id ? findCctvById(backup.id) : null;
    const display = {
        ...(matched || cctv),
        source: backup.source || matched?.source || cctv.source,
        name: backup.name || matched?.name || cctv.name,
        id: backup.id || matched?.id || cctv.id,
        original_id: backup.original_id || matched?.original_id || cctv.original_id
    };

    if (Number.isFinite(Number(display.lat)) && Number.isFinite(Number(display.lng))) {
        display.distance = getDistance(state.center.lat, state.center.lng, display.lat, display.lng);
    } else if (Number.isFinite(Number(backup.distance))) {
        display.distance = Number(backup.distance);
    } else {
        display.distance = cctv.distance;
    }

    display._health = matched ? getCameraHealthMeta(matched) : getCameraHealthMeta(display);
    return display;
}

function handleStreamFailover(wrapper, cctv, nextIndex) {
    if (!wrapper) return;
    ensureDynamicBackups(cctv);
    const backupCount = Array.isArray(cctv.backup_urls) ? cctv.backup_urls.length : 0;
    const isRetryingPrimary = nextIndex === 0;

    // Cleanup existing content
    cleanupVideo(wrapper);

    if (isRetryingPrimary || nextIndex <= backupCount) {
        setTimeout(() => {
            const activeIndex = isRetryingPrimary ? 0 : nextIndex;
            const activeCctv = getActiveStreamCctv(cctv, activeIndex);
            const newVideo = createVideoElement(cctv, activeIndex);
            wrapper.appendChild(newVideo);
            if (newVideo.tagName === 'VIDEO' && activeCctv?.id) {
                newVideo.dataset.activeCctvId = activeCctv.id;
                newVideo.dataset.sourceIndex = String(activeIndex);
                newVideo._activeCctv = activeCctv;
            }
            if (!isRetryingPrimary && activeCctv) {
                recordQualityEvent(activeCctv, 'fallback', {
                    sourceIndex: activeIndex,
                    usedFallback: true
                });
            }
            const loadingCopy = getStreamLoadingCopy(activeCctv, !isRetryingPrimary, nextIndex, backupCount);
            const loadingIndicator = showStreamLoadingIndicator(wrapper, loadingCopy.title, loadingCopy.detail);
            bindStreamLoadingIndicator(wrapper, newVideo, loadingIndicator);

            const panel = wrapper.closest('.video-panel');
            if (panel && activeCctv) {
                renderSelectTrigger(panel, activeCctv, `CCTV ${nextIndex + 1}`);
                renderPanelHealthBadge(panel, activeCctv);
            }
            scheduleVideoHealthProbe(panel, activeCctv || cctv, newVideo);
        }, isRetryingPrimary ? 160 : 180);
    } else {
        const panel = wrapper.closest('.video-panel');
        const retryCount = getManualRetryCount(panel);
        const preparedFallback = panel ? prepareManualRetryFallback(panel, cctv) : null;
        setPlaybackHealth(cctv, {
            status: 'PLAYBACK_ERROR',
            shortLabel: '재생 불안정',
            longLabel: preparedFallback
                ? `${cctv.name || 'CCTV'} 연결 실패, ${preparedFallback.name || '대체 CCTV'} 대체 후보 준비`
                : `${cctv.name || 'CCTV'} 연결 가능한 대체 영상 없음`,
            tone: 'danger',
            penalty: 6
        });
        if (panel) updatePanelHealthUi(panel, cctv);
        const nextRetryNumber = Math.min(MANUAL_RETRY_PRIMARY_ATTEMPTS, retryCount + 1);
        const retryLabel = retryCount >= MANUAL_RETRY_PRIMARY_ATTEMPTS && preparedFallback
            ? '다른 영상 보기'
            : `다시 시도 (${nextRetryNumber}/${MANUAL_RETRY_PRIMARY_ATTEMPTS})`;
        const retryDetail = preparedFallback
            ? (retryCount >= MANUAL_RETRY_PRIMARY_ATTEMPTS
                ? `${preparedFallback.name || '대체 CCTV'} 영상으로 전환합니다.`
                : `${MANUAL_RETRY_PRIMARY_ATTEMPTS}회 재시도 후에도 안되면 ${preparedFallback.name || '대체 CCTV'} 영상으로 바로 전환합니다.`)
            : '잠시 후 다시 시도하거나, 문제가 계속되면 바로 제보할 수 있습니다.';
        const errPh = createErrorPlaceholder({
            message: '지금은 연결이 불안정합니다',
            detail: retryDetail,
            retryLabel,
            retryFn: () => {
                const activePanel = panel || wrapper.closest('.video-panel');
                const nextRetryCount = getManualRetryCount(activePanel) + 1;
                setManualRetryCount(activePanel, nextRetryCount);
                prepareManualRetryFallback(activePanel, cctv);

                if (nextRetryCount > MANUAL_RETRY_PRIMARY_ATTEMPTS
                    && switchToPreparedRetryFallback(activePanel, cctv)) {
                    return;
                }
                handleStreamFailover(wrapper, cctv, 0);
            },
            cctv
        });
        wrapper.appendChild(errPh);
    }
}

function createErrorPlaceholder(options, legacyRetryFn) {
    const config = typeof options === 'string'
        ? { message: options, retryFn: legacyRetryFn }
        : (options || {});
    const {
        message = '영상을 불러올 수 없습니다',
        detail = '',
        retryFn = null,
        retryLabel = '재시도',
        cctv = null
    } = config;
    const ph = document.createElement('div');
    ph.className = 'video-placeholder error';
    let html = `
        <div class="error-message-block">
            <span class="error-message-title">연결 상태를 확인 중입니다</span>
            <span class="error-message-body">${message}</span>
            ${detail ? `<span class="error-message-meta">${detail}</span>` : ''}
        </div>
    `;
    const actions = [];
    if (retryFn) {
        actions.push(`<button class="retry-btn">${retryLabel}</button>`);
    }
    if (cctv) {
        actions.push('<button class="report-btn">문제 제보</button>');
    }
    if (actions.length > 0) {
        html += `<div class="error-actions">${actions.join('')}</div>`;
    }
    ph.innerHTML = html;

    if (retryFn) {
        const btn = ph.querySelector('.retry-btn');
        btn.onclick = (e) => {
            e.stopPropagation();
            btn.classList.add('pressed');
            setTimeout(() => {
                btn.classList.remove('pressed');
                retryFn();
            }, 100);
        };
    }
    if (cctv) {
        const reportBtn = ph.querySelector('.report-btn');
        reportBtn.onclick = (e) => {
            e.stopPropagation();
            openIssueReporter(cctv);
        };
    }
    return ph;
}

function cleanupVideo(container) {
    if (!container) return;

    const video = container.querySelector('video');
    if (video) {
        if (typeof video._watchdogCleanup === 'function') {
            video._watchdogCleanup();
            video._watchdogCleanup = null;
        }
        if (typeof video._daejeonCleanup === 'function') {
            video._daejeonCleanup();
            video._daejeonCleanup = null;
        }
        if (video.hls) {
            video.hls.destroy();
            video.hls = null;
        }
        video.pause();
        video.removeAttribute('src');
        video.load();
    }

    container.innerHTML = '';
}

// === Map ===
function initMap() {
    if (state.mapInitialized) return;

    const container = $('#kakao-map');
    const options = {
        center: new kakao.maps.LatLng(state.center.lat, state.center.lng),
        level: 5
    };

    map = new kakao.maps.Map(container, options);
    state.mapInitialized = true;

    // Map Move Event handler
    const handleMapMove = () => {
        const center = map.getCenter();
        state.center = { lat: center.getLat(), lng: center.getLng() };
        updateNearestCctvs();
        renderServiceStatusBanner();
        renderMapMarkers();
        // Also update video grid so it stays in sync when switching back
        renderVideoGrid();
        syncUrlState();
    };

    kakao.maps.event.addListener(map, 'dragend', handleMapMove);
    kakao.maps.event.addListener(map, 'zoom_changed', handleMapMove);

    // Add Markers for nearest CCTVs
    renderMapMarkers();

    // Add Search Marker if exists
    if (state.searchMarker) {
        state.searchMarker.setMap(map);
    } else {
        // Create initial marker based on current center if it matches keyword
        updateSearchMarker(state.center.lat, state.center.lng);
    }
}

function renderMapMarkers() {
    if (!map) return;

    // Clear existing markers
    state.markers.forEach(marker => marker.setMap(null));
    state.markers = [];

    const placedPositions = []; // To track overlaps: {lat, lng, count}

    // Render new markers (bounded for mobile map performance)
    state.nearestCctvs.slice(0, MAP_MARKER_LIMIT).forEach(cctv => {
        let lat = cctv.lat;
        let lng = cctv.lng;
        const health = cctv._health || getCameraHealthMeta(cctv);
        const displayHealth = getCameraDisplayHealthMeta(cctv, health);

        // Check for overlap and apply offset
        // User Request: "마커 위치도 ... 살짝 옆으로 비껴서 넣어주고"
        let overlap = placedPositions.find(p =>
            Math.abs(p.lat - lat) < 0.00005 && Math.abs(p.lng - lng) < 0.00005
        );

        if (overlap) {
            overlap.count++;
            // Shift East slightly based on count
            // 0.00015 deg is roughly 10-15 meters
            lng += (0.00015 * overlap.count);
        } else {
            placedPositions.push({ lat, lng, count: 0 });
        }

        const markerTitle = `${cctv.name} · ${displayHealth.shortLabel}`;
        const markerOptions = {
            position: new kakao.maps.LatLng(lat, lng),
            map: map,
            title: markerTitle
        };

        if (cctv.source === 'YOUTUBE') {
            const imageSize = new kakao.maps.Size(32, 32);
            const imageOption = { offset: new kakao.maps.Point(16, 16) }; // Center
            markerOptions.image = new kakao.maps.MarkerImage(YOUTUBE_MARKER_SRC, imageSize, imageOption);
        } else {
            const healthMarkerImage = createHealthMarkerImage(displayHealth);
            if (healthMarkerImage) markerOptions.image = healthMarkerImage;
        }

        const marker = new kakao.maps.Marker(markerOptions);

        kakao.maps.event.addListener(marker, 'click', () => {
            openVideoLayer(cctv);
        });

        state.markers.push(marker);
    });
}

function createHealthMarkerImage(health) {
    if (!window.kakao || !kakao.maps) return null;

    const tone = health?.tone || 'unknown';
    if (markerImageCache.has(tone)) {
        return markerImageCache.get(tone);
    }

    const color = getMarkerHealthColor(health);
    const shadow = tone === 'danger'
        ? 'rgba(127, 29, 29, 0.32)'
        : tone === 'warn'
            ? 'rgba(120, 53, 15, 0.28)'
            : tone === 'unknown'
                ? 'rgba(30, 41, 59, 0.24)'
                : 'rgba(20, 83, 45, 0.24)';
    const svg = `
        <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
            <circle cx="18" cy="20" r="12.5" fill="${shadow}"/>
            <circle cx="18" cy="18" r="13" fill="rgba(255,255,255,.94)" stroke="rgba(15,23,42,.26)" stroke-width="1.25"/>
            <circle cx="18" cy="18" r="9.2" fill="none" stroke="${color}" stroke-width="4.8"/>
            <circle cx="18" cy="18" r="4.2" fill="${color}"/>
            <circle cx="15.1" cy="14.6" r="2" fill="rgba(255,255,255,.58)"/>
        </svg>
    `.trim();
    const image = new kakao.maps.MarkerImage(
        `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`,
        new kakao.maps.Size(36, 36),
        { offset: new kakao.maps.Point(18, 18) }
    );
    markerImageCache.set(tone, image);
    return image;
}

function getMarkerHealthColor(health) {
    if (!health) return '#94a3b8';
    if (health.status === 'UNSUPPORTED' || (health.status === 'DOWN' && health.tone === 'danger') || health.tone === 'danger') {
        return '#ef4444';
    }
    if (health.status === 'DEGRADED' || health.tone === 'warn') {
        return '#f59e0b';
    }
    if (health.tone === 'ok-soft') {
        return '#84cc16';
    }
    if (health.status === 'OK' || health.tone === 'ok') {
        return '#22c55e';
    }
    return '#94a3b8';
}

function getMarkerHealthFilter(health) {
    if (!health) return '';
    if (health.status === 'UNSUPPORTED' || (health.status === 'DOWN' && health.tone === 'danger') || health.tone === 'danger') {
        return MARKER_DANGER_FILTER;
    }
    if (health.status === 'DEGRADED' || health.tone === 'warn') {
        return MARKER_WARN_FILTER;
    }
    return '';
}

function applyMarkerHealthFilter(marker, health, title) {
    const filter = getMarkerHealthFilter(health);
    if (!filter) return;

    marker.setOpacity(1);
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const container = document.getElementById('kakao-map');
            if (!container) return;

            const markerImages = Array.from(container.querySelectorAll('img'));
            const image = markerImages.find(img => img.title === title || img.alt === title);
            if (!image) return;

            image.style.filter = filter;
            image.style.opacity = '1';
        });
    });
}

function updateSearchMarker(lat, lng) {
    if (state.searchMarker) {
        state.searchMarker.setMap(null); // Remove existing
    }

    if (!map) return; // Will be created in initMap

    const imageSize = new kakao.maps.Size(64, 69); // Default size for this red marker
    const imageOption = { offset: new kakao.maps.Point(27, 69) };
    const markerImage = new kakao.maps.MarkerImage(SEARCH_MARKER_SRC, imageSize, imageOption);

    state.searchMarker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(lat, lng),
        image: markerImage,
        map: map
    });
}

// === Weather ===
function toggleWeather() {
    const layer = $('#weather-layer');
    const btn = $('#weather-btn');
    const isOpen = layer.classList.contains('active');

    if (isOpen) {
        closeWeather({ restoreDomesticMap: true });
    } else {
        // Close search first
        $('#search-results').classList.remove('active');

        layer.classList.add('active');
        btn.classList.add('active');

        if (state.mode === 'map') {
            $('#dim-overlay').classList.remove('active');
            openWorldTourPanel();
        } else {
            $('#dim-overlay').classList.add('active');
            openWeatherPanel();
        }
    }
}

function closeWeather(options = {}) {
    const layer = $('#weather-layer');
    const content = layer?.querySelector('.weather-content');
    const wasWorldTour = layer?.classList.contains('world-tour-layer');
    const restoreDomesticMap = options.restoreDomesticMap !== false;

    destroyWorldTourMap();
    layer?.classList.remove('active', 'world-tour-layer');
    content?.classList.remove('world-tour-content');
    document.body.classList.remove('world-tour-active');
    $('#weather-btn')?.classList.remove('active');
    $('#dim-overlay')?.classList.remove('active');
    const list = $('#weather-list');
    if (list) list.innerHTML = '';

    if (wasWorldTour && restoreDomesticMap) {
        switchMode('map');
    }
}

function openWeatherPanel() {
    const layer = $('#weather-layer');
    const content = layer?.querySelector('.weather-content');
    layer?.classList.remove('world-tour-layer');
    content?.classList.remove('world-tour-content');
    document.body.classList.remove('world-tour-active');
    $('#weather-title').innerHTML = `<span style="color: var(--accent)">${state.keyword}</span> 주간 날씨`;
    fetchWeather();
}

async function openWorldTourPanel() {
    const layer = $('#weather-layer');
    const content = layer?.querySelector('.weather-content');
    layer?.classList.add('world-tour-layer');
    content?.classList.add('world-tour-content');
    document.body.classList.add('world-tour-active');
    state.worldTourViewMode = 'map';
    $('#weather-title').textContent = '세계 관광 라이브 지도';
    if (!WORLD_TOUR_REGIONS.includes(state.worldTourRegion)) {
        state.worldTourRegion = 'All';
    }
    await renderWorldTourCams();
}

async function loadWorldTourCams() {
    if (Array.isArray(state.worldTourCams)) return state.worldTourCams;

    const response = await fetch(WORLD_TOUR_DATA_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error(`World tour data failed: ${response.status}`);
    const payload = await response.json();
    state.worldTourCams = (payload.items || [])
        .filter(item => item && (item.videoId || item.embedUrl))
        .sort((a, b) => (Number(b.priority || 0) - Number(a.priority || 0)) || String(a.title).localeCompare(String(b.title)));
    return state.worldTourCams;
}

function getWorldTourEmbedUrl(cam) {
    if (cam.embedUrl) return cam.embedUrl;
    if (!cam.videoId) return null;
    return `https://www.youtube.com/embed/${cam.videoId}?autoplay=1&mute=1&playsinline=1&controls=1&rel=0`;
}

function escapeWorldTourHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[char]));
}

function getWorldTourRegionLabel(region) {
    return WORLD_TOUR_REGION_LABELS[region] || region || 'World';
}

function getWorldTourSourceLabel(cam) {
    const sourceType = String(cam?.sourceType || (cam?.videoId ? 'youtube' : 'external')).toLowerCase();
    return WORLD_TOUR_SOURCE_LABELS[sourceType] || cam?.channel || 'External';
}

function formatWorldTourHashTag(value, compact = false) {
    const text = String(value || '').trim();
    if (!text) return '';
    return `#${compact ? text.replace(/\s+/g, '') : text}`;
}

function renderWorldTourHashTags(cam) {
    const tags = [
        formatWorldTourHashTag(cam?.city, true),
        formatWorldTourHashTag(cam?.country),
        formatWorldTourHashTag(getWorldTourSourceLabel(cam), true)
    ].filter(Boolean);

    return tags.length
        ? `<div class="world-tour-tags">${tags.map(tag => `<span>${escapeWorldTourHtml(tag)}</span>`).join('')}</div>`
        : '';
}

function canPlayWorldTourInApp(cam) {
    return Boolean(cam?.videoId || cam?.embedUrl);
}

function getWorldTourRegionCounts(cams) {
    return cams.reduce((counts, cam) => {
        const region = cam.region || 'Other';
        counts.All = (counts.All || 0) + 1;
        counts[region] = (counts[region] || 0) + 1;
        return counts;
    }, { All: 0 });
}

function getWorldTourVisibleCams(cams) {
    if (state.worldTourRegion === 'All') return cams;
    return cams.filter(cam => cam.region === state.worldTourRegion);
}

function getWorldTourNearbyCams(selected, cams, limit = 6) {
    if (!selected) return [];

    return cams
        .filter(cam => cam.id !== selected.id && Number.isFinite(Number(cam.lat)) && Number.isFinite(Number(cam.lng)))
        .map(cam => ({
            ...cam,
            distance: getDistance(Number(selected.lat), Number(selected.lng), Number(cam.lat), Number(cam.lng))
        }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, limit);
}

function renderWorldTourRegionTabs(cams) {
    const counts = getWorldTourRegionCounts(cams);

    return `
        <div class="world-tour-region-tabs" role="tablist" aria-label="대륙별 관광 라이브 필터">
            ${WORLD_TOUR_REGIONS
                .filter(region => counts[region] > 0)
                .map(region => `
                    <button
                        type="button"
                        class="world-tour-region-tab ${state.worldTourRegion === region ? 'active' : ''}"
                        data-world-region="${escapeWorldTourHtml(region)}"
                    >
                        <span>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</span>
                        <b>${counts[region]}</b>
                    </button>
                `).join('')}
        </div>
    `;
}

function renderWorldTourCard(cam, selectedId) {
    const isActive = cam.id === selectedId;
    const regionColor = WORLD_TOUR_REGION_COLORS[cam.region] || '#86efac';
    const sourceLabel = getWorldTourSourceLabel(cam);

    return `
        <button type="button" class="world-tour-card ${isActive ? 'active' : ''}" data-id="${escapeWorldTourHtml(cam.id)}">
            <span class="world-tour-card-title">${escapeWorldTourHtml(cam.title)}</span>
            <span class="world-tour-card-sub">${escapeWorldTourHtml(cam.city)} · ${escapeWorldTourHtml(cam.country)}</span>
            <span class="world-tour-card-footer">
                <span class="world-tour-card-tag" style="--region-color:${regionColor}">${escapeWorldTourHtml(getWorldTourRegionLabel(cam.region))}</span>
                <span class="world-tour-source-tag ${canPlayWorldTourInApp(cam) ? 'playable' : 'external'}">${escapeWorldTourHtml(sourceLabel)}</span>
            </span>
        </button>
    `;
}

function renderWorldTourModeSwitch() {
    return `
        <div class="world-tour-mode-switch" role="tablist" aria-label="관광 라이브 보기 방식">
            <button
                type="button"
                class="world-tour-mode-option ${state.worldTourViewMode === 'map' ? 'active' : ''}"
                data-world-tour-view="map"
                aria-selected="${state.worldTourViewMode === 'map'}"
            >지도보기</button>
            <button
                type="button"
                class="world-tour-mode-option ${state.worldTourViewMode === 'video' ? 'active' : ''}"
                data-world-tour-view="video"
                aria-selected="${state.worldTourViewMode === 'video'}"
            >영상보기</button>
        </div>
    `;
}

function renderWorldTourSections(cams, selectedId) {
    if (state.worldTourRegion !== 'All') {
        return `
            <section class="world-tour-region-section">
                <div class="world-tour-section-title">
                    <h4>${escapeWorldTourHtml(getWorldTourRegionLabel(state.worldTourRegion))}</h4>
                    <span>${cams.length} live cams</span>
                </div>
                <div class="world-tour-grid">
                    ${cams.map(cam => renderWorldTourCard(cam, selectedId)).join('')}
                </div>
            </section>
        `;
    }

    return WORLD_TOUR_REGIONS
        .filter(region => region !== 'All')
        .map(region => {
            const regionCams = cams.filter(cam => cam.region === region);
            if (!regionCams.length) return '';
            return `
                <section class="world-tour-region-section">
                    <div class="world-tour-section-title">
                        <h4>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</h4>
                        <span>${regionCams.length} live cams</span>
                    </div>
                    <div class="world-tour-grid">
                        ${regionCams.map(cam => renderWorldTourCard(cam, selectedId)).join('')}
                    </div>
                </section>
            `;
        }).join('');
}

function renderWorldTourBottomMenu(cams, visibleCams, selected) {
    const openLink = selected.sourceUrl
        ? `<a class="world-tour-open-btn" href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본 열기</a>`
        : '';

    return `
        <section class="world-tour-bottom-menu" aria-label="세계 관광 라이브 선택 메뉴">
            <div class="world-tour-selected-summary">
                <span class="world-tour-kicker">${escapeWorldTourHtml(getWorldTourRegionLabel(selected.region))} live cam</span>
                <h3>${escapeWorldTourHtml(selected.title)}</h3>
                <p>${escapeWorldTourHtml(selected.subtitle || `${selected.city}, ${selected.country}`)}</p>
                ${renderWorldTourHashTags(selected)}
                <div class="world-tour-actions">
                    ${renderWorldTourModeSwitch()}
                    ${openLink}
                </div>
            </div>
            <div class="world-tour-bottom-main">
                ${renderWorldTourRegionTabs(cams)}
                <div class="world-tour-card-rail" aria-label="선택 가능한 세계 관광 라이브">
                    ${visibleCams.map(cam => renderWorldTourCard(cam, selected.id)).join('')}
                </div>
            </div>
        </section>
    `;
}

function renderWorldTourVideoHero(selected) {
    const embedUrl = getWorldTourEmbedUrl(selected);
    const sourceLabel = getWorldTourSourceLabel(selected);

    return `
        <section class="world-tour-hero">
            ${embedUrl ? `
                <div class="world-tour-video">
                    <iframe
                        src="${escapeWorldTourHtml(embedUrl)}"
                        title="${escapeWorldTourHtml(selected.title)}"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                        allowfullscreen
                    ></iframe>
                </div>
            ` : `
                <div class="world-tour-video world-tour-external-preview">
                    ${selected.thumbnailUrl ? `<img src="${escapeWorldTourHtml(selected.thumbnailUrl)}" alt="${escapeWorldTourHtml(selected.title)} preview" loading="lazy">` : ''}
                    <div class="world-tour-external-copy">
                        <span>${escapeWorldTourHtml(sourceLabel)} 공식 플레이어</span>
                        <strong>이 영상은 원본 사이트에서 안정적으로 재생됩니다.</strong>
                        <a href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본에서 보기</a>
                    </div>
                </div>
            `}
            <div class="world-tour-meta">
                <span class="world-tour-kicker">${escapeWorldTourHtml(getWorldTourRegionLabel(selected.region))} live cam</span>
                <h3>${escapeWorldTourHtml(selected.title)}</h3>
                <p>${escapeWorldTourHtml(selected.subtitle || `${selected.city}, ${selected.country}`)}</p>
                ${renderWorldTourHashTags(selected)}
                <div class="world-tour-actions">
                    ${renderWorldTourModeSwitch()}
                    <a class="world-tour-open-btn" href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본 열기</a>
                </div>
            </div>
        </section>
    `;
}

function renderWorldTourMapHero(selected, visibleCams) {
    const nearby = getWorldTourNearbyCams(selected, visibleCams, 3);

    return `
        <section class="world-tour-map-stage" aria-label="세계 관광 라이브 지도">
            <div class="world-tour-map-wrap">
                <div id="world-tour-map" class="world-tour-map" aria-label="${escapeWorldTourHtml(selected.title)} 주변 관광 라이브 지도">
                    <div class="world-tour-map-loading">OpenStreetMap 지도를 불러오는 중...</div>
                </div>
            </div>
            <div class="world-tour-map-card">
                <span>${escapeWorldTourHtml(getWorldTourRegionLabel(selected.region))}</span>
                <strong>${escapeWorldTourHtml(selected.title)}</strong>
                <p>${escapeWorldTourHtml(selected.city)} · ${escapeWorldTourHtml(selected.country)}</p>
                ${nearby.length ? `
                    <div class="world-tour-nearby">
                        <strong>가까운 영상</strong>
                        <div class="world-tour-nearby-row">
                            ${nearby.map(cam => `
                                <button type="button" class="world-tour-nearby-item" data-id="${escapeWorldTourHtml(cam.id)}">
                                    <span>${escapeWorldTourHtml(cam.title)}</span>
                                    <em>${escapeWorldTourHtml(formatDistance(cam.distance))}</em>
                                </button>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        </section>
    `;
}

async function renderWorldTourCams(selectedId = state.selectedWorldTourId, options = {}) {
    const list = $('#weather-list');
    if (!list) return;
    list.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">세계 관광 라이브를 불러오는 중...</div>';

    try {
        const cams = await loadWorldTourCams();
        if (!cams.length) {
            list.innerHTML = '<div style="padding:20px;">등록된 관광지 영상이 없습니다.</div>';
            return;
        }

        if (options.region && WORLD_TOUR_REGIONS.includes(options.region)) {
            state.worldTourRegion = options.region;
        }
        if (options.viewMode) {
            state.worldTourViewMode = options.viewMode;
        }

        let visibleCams = getWorldTourVisibleCams(cams);
        if (!visibleCams.length) {
            state.worldTourRegion = 'All';
            visibleCams = cams;
        }

        const selectedFromVisible = visibleCams.find(cam => cam.id === selectedId);
        const selectedFromAll = cams.find(cam => cam.id === selectedId);
        const selected = selectedFromVisible || (state.worldTourRegion === 'All' ? selectedFromAll : null) || visibleCams[0] || cams[0];
        state.selectedWorldTourId = selected.id;
        destroyWorldTourMap();

        const isMapView = state.worldTourViewMode === 'map';
        list.innerHTML = `
            <div class="world-tour-shell ${isMapView ? 'world-tour-map-shell' : 'world-tour-video-shell'}">
                ${state.worldTourViewMode === 'map'
                    ? renderWorldTourMapHero(selected, visibleCams)
                    : renderWorldTourVideoHero(selected)}
                ${renderWorldTourBottomMenu(cams, visibleCams, selected)}
            </div>
        `;

        list.querySelectorAll('.world-tour-card').forEach(card => {
            card.addEventListener('click', () => {
                renderWorldTourCams(card.dataset.id, { viewMode: state.worldTourViewMode });
            });
        });
        list.querySelectorAll('.world-tour-region-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const region = tab.dataset.worldRegion || 'All';
                const nextVisibleCams = region === 'All' ? cams : cams.filter(cam => cam.region === region);
                const nextSelected = nextVisibleCams.find(cam => cam.id === state.selectedWorldTourId) || nextVisibleCams[0] || cams[0];
                renderWorldTourCams(nextSelected.id, { region, viewMode: state.worldTourViewMode });
            });
        });
        list.querySelectorAll('.world-tour-mode-option').forEach(button => {
            button.addEventListener('click', () => {
                const viewMode = button.dataset.worldTourView === 'map' ? 'map' : 'video';
                renderWorldTourCams(state.selectedWorldTourId, { viewMode });
            });
        });
        list.querySelectorAll('.world-tour-nearby-item').forEach(item => {
            item.addEventListener('click', () => renderWorldTourCams(item.dataset.id, { viewMode: 'map' }));
        });

        if (state.worldTourViewMode === 'map') {
            requestAnimationFrame(() => initWorldTourMap(selected, visibleCams));
        }
    } catch (error) {
        console.error('[WorldTour] failed to load:', error);
        list.innerHTML = '<div style="padding:20px;">세계 관광 라이브를 불러올 수 없습니다.</div>';
    }
}

function focusWorldTourCamOnMap(cam) {
    if (!cam) return;
    state.worldTourRegion = cam.region || 'All';
    renderWorldTourCams(cam.id, { viewMode: 'map' });
}

function loadWorldTourMapLibrary() {
    if (window.L) return Promise.resolve(window.L);
    if (worldTourMapLibraryPromise) return worldTourMapLibraryPromise;

    worldTourMapLibraryPromise = new Promise((resolve, reject) => {
        if (!document.querySelector('link[data-world-tour-leaflet]')) {
            const style = document.createElement('link');
            style.rel = 'stylesheet';
            style.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            style.dataset.worldTourLeaflet = 'true';
            document.head.appendChild(style);
        }

        const existingScript = document.querySelector('script[data-world-tour-leaflet]');
        if (existingScript) {
            existingScript.addEventListener('load', () => window.L ? resolve(window.L) : reject(new Error('Leaflet did not initialize')));
            existingScript.addEventListener('error', () => reject(new Error('Leaflet script failed to load')));
            return;
        }

        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.async = true;
        script.dataset.worldTourLeaflet = 'true';
        script.onload = () => window.L ? resolve(window.L) : reject(new Error('Leaflet did not initialize'));
        script.onerror = () => reject(new Error('Leaflet script failed to load'));
        document.head.appendChild(script);
    }).catch(error => {
        worldTourMapLibraryPromise = null;
        throw error;
    });

    return worldTourMapLibraryPromise;
}

function destroyWorldTourMap() {
    worldTourLeafletMarkers.forEach(marker => marker?.remove?.());
    worldTourLeafletMarkers = [];

    if (worldTourLeafletMap) {
        worldTourLeafletMap.remove();
        worldTourLeafletMap = null;
    }
}

async function initWorldTourMap(selected, visibleCams) {
    const mapEl = $('#world-tour-map');
    if (!mapEl || !selected) return;

    try {
        const L = await loadWorldTourMapLibrary();
        if (!document.body.contains(mapEl)) return;

        destroyWorldTourMap();
        mapEl.innerHTML = '';

        worldTourLeafletMap = L.map(mapEl, {
            worldCopyJump: true,
            zoomControl: false,
            attributionControl: true
        });

        L.control.zoom({ position: 'topright' }).addTo(worldTourLeafletMap);

        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 18,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(worldTourLeafletMap);

        const mappableCams = visibleCams
            .filter(cam => Number.isFinite(Number(cam.lat)) && Number.isFinite(Number(cam.lng)));
        const bounds = L.latLngBounds(mappableCams.map(cam => [Number(cam.lat), Number(cam.lng)]));
        if (state.worldTourRegion === 'All') {
            const mobileWorldZoom = window.innerWidth <= 600 ? 1 : 2;
            worldTourLeafletMap.setView([18, 8], mobileWorldZoom);
        } else if (bounds.isValid()) {
            worldTourLeafletMap.fitBounds(bounds.pad(0.18), {
                maxZoom: 6
            });
        } else {
            worldTourLeafletMap.setView([Number(selected.lat), Number(selected.lng)], 4);
        }

        visibleCams.forEach(cam => {
            const lat = Number(cam.lat);
            const lng = Number(cam.lng);
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

            const isSelected = cam.id === selected.id;
            const marker = L.circleMarker([lat, lng], {
                radius: isSelected ? 9 : 6,
                color: isSelected ? '#ecfeff' : (WORLD_TOUR_REGION_COLORS[cam.region] || '#38bdf8'),
                weight: isSelected ? 3 : 2,
                fillColor: isSelected ? '#22c55e' : (WORLD_TOUR_REGION_COLORS[cam.region] || '#38bdf8'),
                fillOpacity: isSelected ? 0.98 : 0.74
            }).addTo(worldTourLeafletMap);

            marker
                .bindTooltip(escapeWorldTourHtml(cam.title), {
                    direction: 'top',
                    offset: [0, -8],
                    className: 'world-tour-leaflet-tooltip'
                })
                .on('click', () => renderWorldTourCams(cam.id, { viewMode: 'map' }));

            worldTourLeafletMarkers.push(marker);
        });

        setTimeout(() => worldTourLeafletMap?.invalidateSize(), 80);
        setTimeout(() => worldTourLeafletMap?.invalidateSize(), 320);
    } catch (error) {
        console.error('[WorldTour] map failed:', error);
        if (mapEl) {
            mapEl.innerHTML = '<div class="world-tour-map-loading">지도를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</div>';
        }
    }
}

async function fetchWeather() {
    const list = $('#weather-list');
    list.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">로딩 중...</div>';

    try {
        const response = await fetch(
            `https://api.open-meteo.com/v1/forecast?latitude=${state.center.lat}&longitude=${state.center.lng}&current=temperature_2m,precipitation,cloud_cover,visibility&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto`
        );
        const data = await response.json();

        const days = ['일', '월', '화', '수', '목', '금', '토'];
        const current = data.current || {};
        const visibilityKm = Number.isFinite(current.visibility) ? (current.visibility / 1000).toFixed(1) : null;
        const visibilityLabel = getVisibilityLabel(current.visibility);
        const cloudLabel = getCloudLabel(current.cloud_cover);

        list.innerHTML = `
            <div class="weather-now">
                <div class="weather-now-head">
                    <div class="weather-now-temp">${Math.round(current.temperature_2m || 0)}°</div>
                    <div class="weather-now-meta">
                        <div class="weather-now-label">${visibilityLabel}</div>
                        <div class="weather-now-sub">${cloudLabel}${visibilityKm ? ` · 시야 ${visibilityKm}km` : ''}</div>
                    </div>
                </div>
                <div class="weather-pill-row">
                    <span class="weather-pill">강수 ${Math.round(current.precipitation || 0)}mm</span>
                    <span class="weather-pill">구름 ${Math.round(current.cloud_cover || 0)}%</span>
                </div>
            </div>
        ` + data.daily.time.slice(0, 7).map((time, i) => {
            const date = new Date(time);
            const dayName = i === 0 ? '오늘' : days[date.getDay()];
            const dateStr = `${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
            const icon = getWeatherIcon(data.daily.weathercode[i]);
            const max = Math.round(data.daily.temperature_2m_max[i]);
            const min = Math.round(data.daily.temperature_2m_min[i]);
            const precip = Math.round(data.daily.precipitation_probability_max[i] || 0);

            return `
                <div class="weather-item">
                    <div class="weather-day">${dayName} <span class="weather-date">${dateStr}</span></div>
                    <div class="weather-icon">${icon}</div>
                    <div class="weather-temp">${Math.round((max + min) / 2)}°</div>
                    <div class="weather-range">${min}° / ${max}° · 강수 ${precip}%</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        list.innerHTML = '<div style="padding:20px;">날씨 정보를 불러올 수 없습니다.</div>';
    }
}

function getWeatherIcon(code) {
    const icons = {
        0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️',
        45: '🌫️', 48: '🌫️',
        51: '🌧️', 53: '🌧️', 55: '🌧️',
        61: '🌧️', 63: '🌧️', 65: '🌧️',
        71: '🌨️', 73: '🌨️', 75: '🌨️',
        80: '🌦️', 81: '🌦️', 82: '🌦️',
        95: '⛈️', 96: '⛈️', 99: '⛈️'
    };
    return icons[code] || '☁️';
}

function getVisibilityLabel(visibilityMeters) {
    if (!Number.isFinite(visibilityMeters)) return '시야 정보 없음';
    if (visibilityMeters < 1000) return '시야 낮음';
    if (visibilityMeters < 5000) return '시야 보통';
    return '시야 양호';
}

function getCloudLabel(cloudCover) {
    if (!Number.isFinite(cloudCover)) return '구름 정보 없음';
    if (cloudCover < 25) return '맑음';
    if (cloudCover < 60) return '구름 조금';
    if (cloudCover < 85) return '구름 많음';
    return '흐림';
}

// === Video Layer ===
function openVideoLayer(cctv) {
    const layer = $('#video-layer');
    const frame = $('#video-frame');
    const health = cctv._health || getCameraHealthMeta(cctv);
    const distance = Number.isFinite(cctv.distance)
        ? cctv.distance
        : getDistance(state.center.lat, state.center.lng, cctv.lat, cctv.lng);
    const displayCctv = {
        ...cctv,
        distance,
        _health: health
    };

    // Cleanup previous video
    cleanupVideo(frame);
    state.activeCctvId = cctv.id;

    // Update Title & Controls
    const titleEl = $('#video-layer-title');

    // Find index for Navigation
    const currentIndex = state.nearestCctvs.findIndex(item => item.id === cctv.id);

    // Navigation Buttons HTML
    let navHtml = '';
    if (currentIndex !== -1) {
        navHtml = `
            <span style="display:inline-flex; align-items:center; margin-right:10px; gap:5px;">
                <button class="nav-btn prev" ${currentIndex === 0 ? 'disabled' : ''} title="이전 CCTV">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
                </button>
                <button class="nav-btn next" ${currentIndex === state.nearestCctvs.length - 1 ? 'disabled' : ''} title="다음 CCTV">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </button>
            </span>
        `;
    }

    titleEl.innerHTML = `
        ${navHtml}
        <span class="video-title-block">
            <span class="video-title-main">${cctv.name}</span>
            <span class="video-title-sub">
                <span>${formatDistance(displayCctv.distance)}</span>
                <span class="panel-health-sep">·</span>
                <span class="tone-${health.tone}">${health.shortLabel}</span>
                <span class="panel-health-sep">·</span>
                <span>${formatRelativeTime(health.lastUpdated)}</span>
            </span>
        </span>
    `;

    // Attach Nav Listeners
    if (currentIndex !== -1) {
        const prevBtn = titleEl.querySelector('.nav-btn.prev');
        const nextBtn = titleEl.querySelector('.nav-btn.next');

        if (prevBtn && !prevBtn.disabled) {
            prevBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openVideoLayer(state.nearestCctvs[currentIndex - 1]);
            });
        }
        if (nextBtn && !nextBtn.disabled) {
            nextBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openVideoLayer(state.nearestCctvs[currentIndex + 1]);
            });
        }
    }

    const video = createVideoElement(cctv);
    if (video.tagName === 'VIDEO') {
        video.controls = true;
        video.dataset.activeCctvId = displayCctv.id;
        video.dataset.sourceIndex = '0';
        video._activeCctv = displayCctv;
    }

    frame.appendChild(video);
    if (video.tagName === 'VIDEO') scheduleVideoHealthProbe(frame, displayCctv, video);

    // Add Expand Toggle Button if not exists
    const header = $('.video-layer-header');
    let actionContainer = header.querySelector('.video-header-actions');

    // Create container if it doesn't exist (and move close button into it)
    if (!actionContainer) {
        actionContainer = document.createElement('div');
        actionContainer.className = 'video-header-actions';

        const closeBtn = $('#video-layer-close');
        // temporarily remove close button to append it to container
        if (closeBtn && closeBtn.parentNode === header) {
            header.removeChild(closeBtn);
        }

        header.appendChild(actionContainer);
        if (closeBtn) actionContainer.appendChild(closeBtn);
    }

    let shareBtn = $('#video-layer-share');
    if (!shareBtn) {
        shareBtn = document.createElement('button');
        shareBtn.id = 'video-layer-share';
        shareBtn.className = 'layer-action-btn';
        shareBtn.title = '공유';
        shareBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.59 13.51 15.42 17.49"/><path d="M15.41 6.51 8.59 10.49"/></svg>`;
        actionContainer.insertBefore(shareBtn, $('#video-layer-close'));
    }
    shareBtn.onclick = () => shareCurrentView(displayCctv);

    let reportBtn = $('#video-layer-report');
    if (!reportBtn) {
        reportBtn = document.createElement('button');
        reportBtn.id = 'video-layer-report';
        reportBtn.className = 'layer-action-btn';
        reportBtn.title = '문제 신고';
        reportBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/></svg>`;
        actionContainer.insertBefore(reportBtn, $('#video-layer-close'));
    }
    reportBtn.onclick = () => openIssueReporter(displayCctv);

    let toggleBtn = $('#video-layer-toggle');
    if (!toggleBtn) {
        toggleBtn = document.createElement('button');
        toggleBtn.id = 'video-layer-toggle';
        toggleBtn.className = 'layer-toggle-btn';
        toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>`;

        // Insert before close button in the container
        const closeBtn = $('#video-layer-close');
        actionContainer.insertBefore(toggleBtn, closeBtn);

        toggleBtn.addEventListener('click', () => {
            const content = $('.video-layer-content');
            const isMaximized = content.classList.toggle('maximized');

            if (isMaximized) {
                toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M10 14L3 21"/></svg>`;
            } else {
                toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>`;
            }

            setTimeout(updateUticLayout, 350); // Recalculate layout after transition
        });
    }

    layer.classList.add('active');
    syncUrlState();
    setTimeout(updateUticLayout, 350); // Initial check
}

function closeVideoLayer() {
    const layer = $('#video-layer');
    const frame = $('#video-frame');

    cleanupVideo(frame);
    layer.classList.remove('active');
    state.activeCctvId = null;
    syncUrlState();
}

// === Overlays ===
function closeAllOverlays() {
    $('#search-results').classList.remove('active');
    $('#dim-overlay').classList.remove('active');
    closeWeather();
}

// === Utilities ===
function getDistance(lat1, lng1, lat2, lng2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// === Local Storage (Search History) ===
function getSearchHistory() {
    try {
        return JSON.parse(localStorage.getItem('cctv_search_history') || '[]');
    } catch {
        return [];
    }
}

function saveSearchHistory(item) {
    let history = getSearchHistory();
    history = history.filter(h => h.name !== item.name);
    history.unshift(item);
    history = history.slice(0, 10);
    localStorage.setItem('cctv_search_history', JSON.stringify(history));
}

// === Local Storage (Bookmarks) ===
function getBookmarks() {
    try {
        return JSON.parse(localStorage.getItem('cctv_bookmarks') || '[]');
    } catch {
        return [];
    }
}

function toggleBookmark(item) {
    let bookmarks = getBookmarks();
    const exists = bookmarks.find(b => b.name === item.name);

    if (exists) {
        bookmarks = bookmarks.filter(b => b.name !== item.name);
    } else {
        bookmarks.unshift(item);
    }

    localStorage.setItem('cctv_bookmarks', JSON.stringify(bookmarks));
    showSearchHistory(); // Refresh
}

function deleteHistoryItem(name) {
    let history = getSearchHistory();
    history = history.filter(h => h.name !== name);
    localStorage.setItem('cctv_search_history', JSON.stringify(history));

    // Also remove from bookmarks if exists
    let bookmarks = getBookmarks();
    bookmarks = bookmarks.filter(b => b.name !== name);
    localStorage.setItem('cctv_bookmarks', JSON.stringify(bookmarks));

    showSearchHistory(); // Refresh
}

// === Mobile Keyboard Handling ===
function setupMobileKeyboardHandling() {
    if (!window.visualViewport) return;

    const viewport = window.visualViewport;
    const header = document.getElementById('header');
    const searchResults = document.getElementById('search-results');
    const searchInput = document.getElementById('search-input');

    function updateLayout() {
        // Only active if search input is focused
        if (document.activeElement !== searchInput) {
            resetLayout();
            return;
        }

        // Calculate offset from bottom of layout viewport to bottom of visual viewport
        // This handles iOS keyboard pushing visual viewport up
        // bottom position = layoutHeight - (visualHeight + visualOffsetTop)
        const offset = window.innerHeight - viewport.height - viewport.offsetTop;

        // On Android, viewport.height tracks resize, so offset might be near 0 if innerHeight resizes too.
        // On iOS, innerHeight is constant, height shrinks, offset increases.

        // If the viewport is significantly compressed (keyboard likely open)
        // or if there is a significant offset
        const isKeyboardLike = viewport.height < window.innerHeight * 0.85 || offset > 100;

        if (isKeyboardLike) {
            // Apply lifting
            // Use 0 as floor to prevent negative values
            const liftAmount = Math.max(0, offset);

            header.style.bottom = `${liftAmount}px`;
            if (searchResults) {
                // Keep search results above where the header is
                searchResults.style.bottom = `${liftAmount + 90}px`;
            }
        } else {
            resetLayout();
        }
    }

    function resetLayout() {
        header.style.removeProperty('bottom');
        if (searchResults) searchResults.style.removeProperty('bottom');
    }

    viewport.addEventListener('resize', updateLayout);
    viewport.addEventListener('scroll', updateLayout);

    searchInput.addEventListener('focus', updateLayout);
    searchInput.addEventListener('blur', () => {
        // Delay slightly to handle immediate focus changes or clicks
        setTimeout(resetLayout, 100);
    });
}

// === PWA Install Prompt ===
let deferredPrompt = null;

function setupPwaInstallPrompt() {
    const prompt = document.getElementById('pwa-install-prompt');
    if (!prompt) return;

    // Check if already installed (standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches) {
        prompt.remove();
        return;
    }

    // Listen for beforeinstallprompt
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        showInstallPrompt();
    });

    // Handle click
    prompt.addEventListener('click', async () => {
        if (!deferredPrompt) return;

        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log('PWA Install:', outcome);

        deferredPrompt = null;
        hideInstallPrompt();
    });
}

function showInstallPrompt() {
    const prompt = document.getElementById('pwa-install-prompt');
    if (!prompt) return;

    // Show as expanded banner
    prompt.classList.remove('hidden', 'collapsed');
    prompt.classList.add('visible');

    // Collapse to button after 2.5 seconds
    setTimeout(() => {
        prompt.classList.add('collapsed');
    }, 2500);
}

function hideInstallPrompt() {
    const prompt = document.getElementById('pwa-install-prompt');
    if (!prompt) {
        return;
    }
    prompt.classList.remove('visible');
    prompt.classList.add('hidden');
}

// Initialize on DOM ready (add to existing DOMContentLoaded or call separately)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPwaInstallPrompt);
} else {
    setupPwaInstallPrompt();
}

// === Drag to Pan for Expanded Video Panels ===
function setupVideoPan() {
    const panels = document.querySelectorAll('.video-panel');

    panels.forEach(panel => {
        let isDragging = false;
        let startX, startY;
        let currentX = 50, currentY = 50; // Object position percentages (Video)
        let transX = 0, transY = 0; // Transform pixels (UTIC Iframe)

        const getVideoElement = () => panel.querySelector('video, iframe');

        const onStart = (e) => {
            if (!panel.classList.contains('expanded')) return;

            // Ignore if touching controls (select box, buttons)
            if (e.target.closest('.panel-controls') || e.target.closest('.panel-floating-close')) {
                return;
            }

            isDragging = true;
            panel.classList.add('dragging');
            const touch = e.touches ? e.touches[0] : e;
            startX = touch.clientX;
            startY = touch.clientY;

            // Initialize transformation values from current element style
            const video = getVideoElement();
            if (video && video.classList.contains('utic-iframe')) {
                transX = parseFloat(video.style.getPropertyValue('--tx')) || 0;
                transY = parseFloat(video.style.getPropertyValue('--ty')) || 0;
            }
        };

        const onMove = (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const touch = e.touches ? e.touches[0] : e;

            const video = getVideoElement();
            if (!video) return;

            // UTIC Iframe: Use Transform Translate
            if (video.classList.contains('utic-iframe')) {
                const dx = (touch.clientX - startX);
                const dy = (touch.clientY - startY);

                transX += dx;
                transY += dy;

                video.style.setProperty('--tx', `${transX}px`);
                video.style.setProperty('--ty', `${transY}px`);
            } else {
                // Normal Video: Object Position (Percent)
                const deltaX = (touch.clientX - startX) * 0.15;
                const deltaY = (touch.clientY - startY) * 0.15;

                currentX = Math.max(0, Math.min(100, currentX - deltaX));
                currentY = Math.max(0, Math.min(100, currentY - deltaY));
                video.style.objectPosition = `${currentX}% ${currentY}%`;
            }

            startX = touch.clientX;
            startY = touch.clientY;
        };

        const onEnd = () => {
            isDragging = false;
            panel.classList.remove('dragging');
        };

        // Mouse events
        panel.addEventListener('mousedown', onStart);
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);

        // Touch events
        panel.addEventListener('touchstart', onStart, { passive: true });
        panel.addEventListener('touchmove', onMove, { passive: false });
        panel.addEventListener('touchend', onEnd);
    });
}

// Initialize pan feature
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupVideoPan);
} else {
    setupVideoPan();
}

// === Drag to Pan for Video Layer (Map Popup) ===
function setupVideoLayerPan() {
    const content = document.querySelector('.video-layer-content');
    if (!content) return;

    let isDragging = false;
    let startX, startY;
    let currentX = 50, currentY = 50;
    let transX = 0, transY = 0; // Transform pixels

    const getVideoElement = () => document.querySelector('#video-frame video, #video-frame iframe');

    const onStart = (e) => {
        if (!content.classList.contains('maximized')) return;
        isDragging = true;
        content.classList.add('dragging');
        const touch = e.touches ? e.touches[0] : e;
        startX = touch.clientX;
        startY = touch.clientY;

        // Initialize transformation values from current element style
        // This ensures smoothness if we pause/resume or switch videos
        const video = getVideoElement();
        if (video && video.classList.contains('utic-iframe')) {
            const style = window.getComputedStyle(video);
            // We use CSS variables --tx/--ty, so read them directly from inline style or computed?
            // Inline style is safest for what we set.
            transX = parseFloat(video.style.getPropertyValue('--tx')) || 0;
            transY = parseFloat(video.style.getPropertyValue('--ty')) || 0;
        }
    };

    const onMove = (e) => {
        if (!isDragging) return;
        e.preventDefault();
        const touch = e.touches ? e.touches[0] : e;

        const video = getVideoElement();
        if (!video) return;

        if (video.classList.contains('utic-iframe')) {
            const dx = (touch.clientX - startX);
            const dy = (touch.clientY - startY);

            transX += dx;
            transY += dy;

            video.style.setProperty('--tx', `${transX}px`);
            video.style.setProperty('--ty', `${transY}px`);
        } else {
            const deltaX = (touch.clientX - startX) * 0.15;
            const deltaY = (touch.clientY - startY) * 0.15;

            currentX = Math.max(0, Math.min(100, currentX - deltaX));
            currentY = Math.max(0, Math.min(100, currentY - deltaY));
            video.style.objectPosition = `${currentX}% ${currentY}%`;
        }

        startX = touch.clientX;
        startY = touch.clientY;
    };

    const onEnd = () => {
        isDragging = false;
        content.classList.remove('dragging');
    };

    const frame = document.getElementById('video-frame');
    if (frame) {
        frame.addEventListener('mousedown', onStart);
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onEnd);
        frame.addEventListener('touchstart', onStart, { passive: true });
        frame.addEventListener('touchmove', onMove, { passive: false });
        frame.addEventListener('touchend', onEnd);
    }
}

// Initialize video layer pan
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupVideoLayerPan);
} else {
    setupVideoLayerPan();
}

// === Dynamic UTIC Layout Calculation ===
function updateUticLayout() {
    const panels = document.querySelectorAll('.video-panel.expanded .utic-iframe');
    const layer = document.querySelector('.video-layer-content.maximized .utic-iframe');
    const targets = [...panels];
    if (layer) targets.push(layer);

    if (targets.length === 0) return;

    console.log('[Layout] Updating UTIC Layout for', targets.length, 'elements');

    targets.forEach(iframe => {
        const container = iframe.closest('.video-panel') || iframe.closest('.video-layer-content');
        if (!container) return;

        const cw = container.clientWidth;
        const ch = container.clientHeight;
        const cRatio = cw / ch;

        // Dynamic Aspect Ratio: Use hint if present (e.g. 4:3 for Namyangju/GITS)
        const is43 = iframe.dataset.aspectRatio === '4:3';
        const vRatio = is43 ? (4 / 3) : (16 / 9);

        let scale = 1;

        if (cRatio < vRatio) {
            // Container is Taller: Scale to fill HEIGHT
            scale = (ch * vRatio) / cw;
            iframe.style.setProperty('--origin-y', '0%');
        } else {
            // Container is Wider: Scale to fill WIDTH
            scale = cw / (ch * vRatio);
            iframe.style.setProperty('--origin-y', '50%');
        }

        // Apply a minimum scale of 1.0 and a tiny safety margin
        scale = Math.max(scale, 1.001);

        console.log(`[Layout] ${is43 ? '4:3' : '16:9'} | Container: ${cw}x${ch} (R:${cRatio.toFixed(2)}), Scale: ${scale.toFixed(3)}`);

        // Apply to CSS variable
        iframe.style.setProperty('--scale', scale.toFixed(3));

        // Enable drag if scaled
        if (scale > 1.01 && !iframe.dataset.dragEnabled) {
            enableIframeDrag(iframe);
        }
    });
}

// === UTIC Iframe Drag Handler ===
function enableIframeDrag(iframe) {
    if (iframe.dataset.dragEnabled) return;
    iframe.dataset.dragEnabled = 'true';

    let isDragging = false;
    let startX = 0, startY = 0;
    let translateX = 0, translateY = 0;
    let currentX = 0, currentY = 0;

    // Create drag overlay (to capture events over iframe)
    const overlay = document.createElement('div');
    overlay.className = 'utic-drag-overlay';
    overlay.style.cssText = `
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        cursor: grab;
        z-index: 10;
        touch-action: none;
    `;

    const container = iframe.parentElement;
    container.style.position = 'relative';
    container.appendChild(overlay);

    function getEventPos(e) {
        if (e.touches && e.touches.length > 0) {
            return { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }
        return { x: e.clientX, y: e.clientY };
    }

    function onStart(e) {
        isDragging = true;
        const pos = getEventPos(e);
        startX = pos.x - currentX;
        startY = pos.y - currentY;
        overlay.style.cursor = 'grabbing';
        e.preventDefault();
    }

    function onMove(e) {
        if (!isDragging) return;
        e.preventDefault();

        const pos = getEventPos(e);
        currentX = pos.x - startX;
        currentY = pos.y - startY;

        // Get scale and calculate bounds
        const scale = parseFloat(iframe.style.getPropertyValue('--scale')) || 1;
        const rect = container.getBoundingClientRect();
        const maxX = (rect.width * (scale - 1)) / 2;
        const maxY = (rect.height * (scale - 1)) / 2;

        // Clamp to bounds
        currentX = Math.max(-maxX, Math.min(maxX, currentX));
        currentY = Math.max(-maxY, Math.min(maxY, currentY));

        iframe.style.setProperty('--translate-x', `${currentX}px`);
        iframe.style.setProperty('--translate-y', `${currentY}px`);
    }

    function onEnd() {
        isDragging = false;
        overlay.style.cursor = 'grab';
    }

    // Mouse events
    overlay.addEventListener('mousedown', onStart);
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onEnd);

    // Touch events
    overlay.addEventListener('touchstart', onStart, { passive: false });
    document.addEventListener('touchmove', onMove, { passive: false });
    document.addEventListener('touchend', onEnd);

    // Double-tap to reset
    let lastTap = 0;
    overlay.addEventListener('click', (e) => {
        const now = Date.now();
        if (now - lastTap < 300) {
            // Double tap - reset position
            currentX = 0;
            currentY = 0;
            iframe.style.setProperty('--translate-x', '0px');
            iframe.style.setProperty('--translate-y', '0px');
        }
        lastTap = now;
    });

    // Store cleanup function
    iframe._cleanupDrag = () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        overlay.remove();
        delete iframe.dataset.dragEnabled;
    };
}

// Bind events
window.addEventListener('resize', updateUticLayout);
// Call periodically or on hooks? 
// We'll call checking visibility in animation loops or mutation observers?
// Simplest is to call whenever we expand/collapse.
