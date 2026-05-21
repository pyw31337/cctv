/**
 * CCTV Viewer 2.0 - Main Application Logic
 * Clean Rewrite: State-Driven, Event Delegation
 */

// === Z3 Cache (its.go.kr snapshot via Oracle first, static GitHub fallback) ===
let z3CacheData = null;
let z3CachePromise = null;
let z3CacheAgeMs = Infinity; // 캐시가 fetch된 이후 경과 시간 (ms)
let z3CacheFetchedAt = null;
let z3CacheSource = 'unknown';
// z3_cache 의 토큰 자체는 ktict 서버에서 매 호출마다 wmsAuthSign 을 새로 발급하므로
// 사실상 무기한 유효함이 실측됨. 60분 게이트는 strategy 1 을 거의 항상 무력화시켜
// playback이 strategy 2(URL 내장 토큰: 보통 수개월 묵은 데이터로 502) → strategy 3
// (Oracle /utic: 현재 hang) 으로 전부 떨어지는 원인이었음. → 24시간 으로 완화.
const Z3_CACHE_STALE_MS = 24 * 60 * 60 * 1000;
const CCTV_DATA_BUCKET_MS = 30 * 60 * 1000;
const HEALTH_STATUS_BUCKET_MS = 5 * 60 * 1000;
const HEALTH_STALE_MS = 2 * 60 * 60 * 1000;
const CAMERA_FAILURE_RECENT_MS = 3 * 60 * 60 * 1000;
const APP_BUILD_VERSION = '20260521-32a328ad';
const QUALITY_CONFIG = window.CCTV_QUALITY_CONFIG || {};
const QUALITY_TELEMETRY_ENDPOINT = QUALITY_CONFIG.telemetryEndpoint || 'https://cctv-quality.pyw31337.workers.dev/v1/events';
const QUALITY_SUMMARY_URL = QUALITY_CONFIG.summaryUrl || 'https://cctv-quality.pyw31337.workers.dev/v1/summary';
const QUALITY_SUMMARY_FALLBACK_URL = 'data/quality_summary.json';
const WORLD_TOUR_DATA_URL = `data/world_tour_cams.json?v=${APP_BUILD_VERSION}`;
const WORLD_TOUR_CHEVRON_LEFT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-left-icon lucide-chevron-left" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>';
const WORLD_TOUR_CHEVRON_RIGHT_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-chevron-right-icon lucide-chevron-right" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>';
const WORLD_TOUR_LIST_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg>';
const WORLD_TOUR_VIDEO_OFF_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="icon icon-tabler icons-tabler-outline icon-tabler-video-off" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 3l18 18"/><path d="M15 11v-1l4.553 -2.276a1 1 0 0 1 1.447 .894v6.764a1 1 0 0 1 -.675 .946"/><path d="M10 6h3a2 2 0 0 1 2 2v3m0 4v1a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2v-8a2 2 0 0 1 2 -2h1"/></svg>';
const QUALITY_SUMMARY_BUCKET_MS = 10 * 60 * 1000;
const QUALITY_SUMMARY_TIMEOUT_MS = 1800;
const QUALITY_TELEMETRY_SAMPLE_RATE = 0.35;
const QUALITY_TELEMETRY_DAILY_LIMIT = 20;
const QUALITY_TELEMETRY_QUEUE_LIMIT = 12;
const QUALITY_SLOW_FIRST_FRAME_MS = 8000;
const QUALITY_SORT_STORAGE_KEY = 'cctv_quality_sort_mode';
const TELEMETRY_SAMPLE_STORAGE_KEY = 'cctv_quality_sample_v1';
const TELEMETRY_DAILY_STORAGE_KEY = 'cctv_quality_daily_v1';
const WORLD_TOUR_FAVORITES_STORAGE_KEY = 'cctv_world_tour_favorites_v1';
const CCTV_FAVORITES_STORAGE_KEY = 'cctv_favorites_v1';
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
const QUALITY_SORT_LABELS = {
    recommended: '추천순',
    nearest: '가까운순',
    urban: '시내우선',
    traffic: '교통우선',
    stability: '안정우선',
    quality: '화질우선'
};
const SEARCH_HISTORY_PANEL_ITEM_LIMIT = 4;
const WORLD_TOUR_FAVORITE_REGION = 'Favorite';
const WORLD_TOUR_REGIONS = ['All', 'North America', 'Europe', 'Asia', 'Oceania', 'South America', 'Africa'];
const WORLD_TOUR_STAR_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-star-icon lucide-star"><path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/></svg>';
const WORLD_TOUR_REGION_LABELS = {
    All: 'All',
    Favorite: 'Favorite',
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
    webcamtaxi: 'Webcamtaxi',
    worldcam: 'WorldCam',
    baltic: 'Baltic Live Cam',
    windy: 'Windy Webcams',
    livebeaches: 'Live Beaches',
    camscape: 'Camscape',
    explore: 'Explore.org',
    whatsupcams: "What's Up Cam",
    bergfex: 'Bergfex',
    feratel: 'feratel',
    hdontap: 'HDOnTap',
    roundshot: 'Roundshot',
    twlivecam: 'TW Live CAM',
    worldcamlive: 'WorldCam.Live',
    liveworldwebcams: 'Live World Webcams',
    webcamhopper: 'Webcam Hopper',
    worldcamtv: 'WorldCam.tv',
    livecamcroatia: 'LiveCamCroatia',
    openwebcamdb: 'OpenWebcamDB',
    alertcalifornia: 'ALERTCalifornia',
    wetter: 'wetter.com',
    panoramask: 'Panorama.sk',
    idokep: 'Idokep',
    ptztv: 'PTZtv',
    railcam: 'Railcam',
    railcamuk: 'Railcam UK',
    airportwebcams: 'AirportWebcams.net',
    viewsurf: 'ViewSurf',
    panomax: 'Panomax',
    webcamsdemexico: 'Webcams de Mexico',
    climaaovivo: 'Clima Ao Vivo',
    hktraffic: 'HK Transport',
    usgsvolcano: 'USGS Volcano',
    aurorainfo: 'AuroraInfo',
    nswtraffic: 'NSW Live Traffic',
    dctraffic: 'Open Data DC',
    africam: 'Africam',
    weatherbug: 'WeatherBug',
    surfline: 'Surfline',
    japanwebcams: 'Japan Webcams',
    publictraffic: 'Public Traffic',
    spacecam: 'Space Cams',
    animalcam: 'Animal Cams',
    golfcam: 'Golf Cams',
    cctvworld: 'CCTV World',
    tabi: 'TabiCam',
    webcamera24: 'WebCamera24',
    'youtube-search': 'YouTube Search',
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

// === Source metadata (label + accent color for dot/badge) ===
const SOURCE_META = {
    SPATIC: { label: '서울교통정보', color: '#3b82f6' },
    TOPIS: { label: 'TOPIS', color: '#2563eb' },
    UTIC: { label: 'UTIC', color: '#94a3b8' },
    UTIC_DIRECT: { label: 'UTIC 직접영상', color: '#64748b' },
    UTIC_LEGACY: { label: 'UTIC 구형', color: '#64748b' },
    UTIC_Z3: { label: 'UTIC 국도', color: '#64748b' },
    NTIC: { label: '고속도로', color: '#0ea5e9' },
    BUSAN_ITS: { label: '부산 ITS', color: '#06b6d4' },
    INCHEON_ITS: { label: '인천 ITS', color: '#14b8a6' },
    DAEGU: { label: '대구', color: '#a855f7' },
    GWANGJU: { label: '광주', color: '#f97316' },
    ULSAN: { label: '울산', color: '#22c55e' },
    SEJONG: { label: '세종', color: '#eab308' },
    GANGWON: { label: '강원', color: '#10b981' },
    GITS: { label: '경기 ITS', color: '#0d9488' },
    GOYANG: { label: '고양', color: '#0d9488' },
    PAJU: { label: '파주', color: '#0d9488' },
    JEJU: { label: '제주', color: '#ec4899' },
    NOWJEJU: { label: '나우제주', color: '#f472b6' },
    KBS: { label: 'KBS', color: '#ef4444' },
    KNPS: { label: '국립공원', color: '#16a34a' },
    GIGAEYES: { label: '기가아이즈', color: '#84cc16' },
    YOUTUBE: { label: 'YouTube', color: '#dc2626' },
    YT_CUSTOM: { label: 'YouTube', color: '#dc2626' },
    YT: { label: 'YouTube', color: '#dc2626' },
    ICITS: { label: '인천도시공사', color: '#0ea5e9' },
    UNKNOWN: { label: '기타', color: '#94a3b8' }
};

function getSourceMeta(cctv) {
    if (!cctv) return SOURCE_META.UNKNOWN;
    const key = (cctv.source || '').toUpperCase();
    return SOURCE_META[key] || { label: cctv.source || '기타', color: '#94a3b8' };
}

// Parse a CCTV name into a main location label and a direction hint.
// e.g. "백양터널(모라방향입구)" => { main: "백양터널", direction: "모라방향입구" }
function parseCctvLabel(rawName) {
    const name = String(rawName || '').trim();
    if (!name) return { main: 'CCTV', direction: '', full: '' };
    const match = name.match(/^(.*?)\s*\(([^()]+)\)\s*$/);
    if (match && match[2]) {
        return { main: match[1].trim() || name, direction: match[2].trim(), full: name };
    }
    return { main: name, direction: '', full: name };
}

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
    const cacheBucket = Math.floor(Date.now() / 1800000);
    // Static GitHub snapshot first — Oracle /z3-cache.json was hanging 12s+ in May 2026,
    // blocking the entire Z3 playback pipeline. Static is hourly-refreshed by the GHA so
    // freshness loss vs Oracle is at most ~30min — well within Z3_CACHE_STALE_MS (60min).
    const urls = [
        `data/z3_cache.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`,
        `${ORACLE_BASE}/z3-cache.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`
    ];

    z3CachePromise = (async () => {
        let staleCandidate = null;
        const adoptCacheCandidate = (candidate) => {
            z3CacheData = candidate.data;
            z3CacheFetchedAt = candidate.fetched;
            z3CacheSource = candidate.source;
            z3CacheAgeMs = candidate.ageMs;
        };

        for (const url of urls) {
            try {
                const response = await fetch(url, { cache: 'no-store' });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const json = await response.json();
                const data = json.data || json;
                if (!data || Object.keys(data).length === 0) throw new Error('empty z3 cache');

                const candidate = {
                    data,
                    fetched: json.fetched || null,
                    source: json.source || (url.includes('/z3-cache.json') ? 'oracle' : 'static'),
                    ageMs: json.fetched ? Date.now() - new Date(json.fetched).getTime() : Infinity
                };
                const count = Object.keys(candidate.data).length;
                const ageMin = Math.round(candidate.ageMs / 60000);
                console.log(`[Z3] Cache candidate ${candidate.source}: ${count} entries (fetched: ${candidate.fetched}, age: ${ageMin}min)`);
                if (candidate.ageMs > Z3_CACHE_STALE_MS) {
                    console.warn(`[Z3] Cache candidate ${candidate.source} is ${ageMin}min old — checking next candidate`);
                    staleCandidate = staleCandidate || candidate;
                    continue;
                }
                adoptCacheCandidate(candidate);
                console.log(`[Z3] Cache loaded from ${z3CacheSource}: ${count} entries`);
                return z3CacheData;
            } catch (error) {
                console.warn('[Z3] Cache load skipped:', url, error.message || error);
            }
        }

        if (staleCandidate) {
            adoptCacheCandidate(staleCandidate);
            const count = Object.keys(z3CacheData).length;
            const ageMin = Math.round(z3CacheAgeMs / 60000);
            console.warn(`[Z3] Only stale cache is available from ${z3CacheSource}: ${count} entries (age: ${ageMin}min)`);
            return z3CacheData;
        }

        z3CachePromise = null; // allow retry
        z3CacheData = {};
        z3CacheAgeMs = Infinity;
        z3CacheFetchedAt = null;
        z3CacheSource = 'unavailable';
        return z3CacheData;
    })();
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
    worldTourCardScrollLeft: 0,
    worldTourRegionScrollLeft: 0,
    worldTourListOpen: false,
    worldTourListSearch: '',
    worldTourListRegion: 'All',
    worldTourListCountry: 'All',
    worldTourListSource: 'All',
    // When true, hide cams that can only be viewed on the original
    // source site (no in-app playback). Affects the panel list, the
    // bottom card rail, and the map markers.
    worldTourListExcludeExternal: false,
    worldTourFavorites: new Set(),
    cctvFavorites: new Set(),
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
    hydrateWorldTourFavorites();
    hydrateCctvFavorites();
    // initCompareModeButton(); // 전국 주요 도시 라이브 entry point removed per request

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

    loadZ3Cache().then(() => {
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
    $$('[data-quality-sort-select]').forEach(sortSelect => {
        sortSelect.value = state.sortMode;
    });
}

function setSortMode(mode) {
    if (!QUALITY_SORT_MODES.includes(mode)) return;
    state.sortMode = mode;
    try {
        localStorage.setItem(QUALITY_SORT_STORAGE_KEY, mode);
    } catch {}

    renderQualityControls();
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

        const resultsEl = $('#search-results');
        const resultsOpen = resultsEl && resultsEl.classList.contains('active');

        // ↑/↓ 로 결과 항목 하이라이트 이동
        if (resultsOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            const items = Array.from(resultsEl.querySelectorAll('.search-result-item'));
            if (items.length === 0) return;
            e.preventDefault();
            let idx = items.findIndex(el => el.classList.contains('keyboard-active'));
            if (e.key === 'ArrowDown') {
                idx = idx < 0 ? 0 : (idx + 1) % items.length;
            } else {
                idx = idx <= 0 ? items.length - 1 : idx - 1;
            }
            items.forEach(el => el.classList.remove('keyboard-active'));
            const active = items[idx];
            active.classList.add('keyboard-active');
            try { active.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (_) {}
            return;
        }

        if (e.key === 'Escape' && resultsOpen) {
            e.preventDefault();
            closeAllOverlays();
            return;
        }

        if (e.key === 'Enter') {
            e.preventDefault();
            // 하이라이트된 결과가 있으면 그것을 선택, 없으면 일반 검색 제출
            const active = resultsOpen ? resultsEl.querySelector('.search-result-item.keyboard-active') : null;
            if (active) {
                active.click();
                return;
            }
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

    $$('[data-quality-sort-select]').forEach(sortSelect => {
        sortSelect.addEventListener('change', () => {
            setSortMode(sortSelect.value);
        });
    });

    // Video Layer
    $('#video-layer-close').addEventListener('click', closeVideoLayer);
    $('#video-layer').addEventListener('click', (e) => {
        if (e.target.id === 'video-layer') closeVideoLayer();
    });

    // Location Button
    $('#location-btn').addEventListener('click', handleCurrentLocation);

    // Search Results Click (Delegation for items, bookmark, delete, cctv favorite, open compare)
    $('#search-results').addEventListener('click', (e) => {
        const favItem = e.target.closest('.cctv-favorite-item');
        if (favItem) {
            const isWorld = favItem.classList.contains('cctv-favorite-item--world');
            const removeWorldBtn = e.target.closest('[data-action="remove-favorite-world"]');
            const removeBtn = e.target.closest('[data-action="remove-favorite"]');
            if (removeWorldBtn || removeBtn) {
                e.stopPropagation();
                const targetId = isWorld ? favItem.dataset.worldCamId : favItem.dataset.cctvId;
                if (targetId) {
                    toggleUnifiedFavorite(targetId);
                    showSearchHistory();
                }
                return;
            }
            if (isWorld) {
                const id = favItem.dataset.worldCamId;
                $('#search-results').classList.remove('active');
                $('#dim-overlay').classList.remove('active');
                if (!id) return;
                state.selectedWorldTourId = id;
                state.worldTourRegion = 'All';
                state.worldTourViewMode = 'video';
                if (typeof openWorldTourPanel === 'function') {
                    Promise.resolve(openWorldTourPanel()).then(() => {
                        if (typeof renderWorldTourCams === 'function') {
                            renderWorldTourCams(id, { viewMode: 'video' });
                        }
                    }).catch(err => console.warn('[favorites] world tour open failed:', err));
                } else if (typeof renderWorldTourCams === 'function') {
                    renderWorldTourCams(id, { viewMode: 'video' });
                }
                return;
            }
            const id = favItem.dataset.cctvId;
            const cctv = id ? findCctvById(id) : null;
            if (cctv) {
                $('#search-results').classList.remove('active');
                $('#dim-overlay').classList.remove('active');
                openVideoLayer(cctv);
            }
            return;
        }

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

    $('#search-results').addEventListener('change', (e) => {
        const sortSelect = e.target.closest('[data-quality-sort-select]');
        if (sortSelect) {
            setSortMode(sortSelect.value);
        }
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
    const hasKakaoMaps = Boolean(window.kakao?.maps);
    if (mode === 'map' && !hasKakaoMaps) {
        console.warn('[Map] Kakao Maps SDK is not available; skipping domestic map initialization.');
    } else if (mode === 'map' && !state.mapInitialized) {
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
        const paddingLeft = parseFloat(getComputedStyle(indicator.parentElement).paddingLeft) || 4;
        const left = activeBtn.offsetLeft;
        const width = activeBtn.offsetWidth;
        const height = activeBtn.offsetHeight;

        indicator.style.transform = `translateX(${left - paddingLeft}px)`;
        indicator.style.width = `${width}px`;
        indicator.style.height = `${height}px`;
    }
}

// === Search ===
function shouldUseCompactSearchPanel() {
    return window.matchMedia && window.matchMedia('(max-width: 399px)').matches;
}

function renderSearchSortPanel() {
    return `
        <div class="search-sort-panel" aria-label="CCTV 추천 정렬">
            <select class="quality-sort-select search-sort-select" title="추천 기준" data-quality-sort-select>
                ${QUALITY_SORT_MODES.map(mode => `
                    <option value="${mode}" ${state.sortMode === mode ? 'selected' : ''}>${QUALITY_SORT_LABELS[mode]}</option>
                `).join('')}
            </select>
        </div>
    `;
}

function showSearchHistory() {
    // Close weather popup when opening search
    closeWeather();

    // Lazy-load World Tour cams the first time the search panel opens so
    // World Tour favorites (경복궁/광안대교/남산타워 등) appear in the
    // unified 즐겨찾기 섹션 even before the user has opened the world
    // tour view. Fire-and-forget; re-render when ready.
    try {
        const favIds = getUnifiedFavoriteIds();
        const camsLoaded = Array.isArray(state.worldTourCams)
            || Array.isArray(state.worldTourCams?.items);
        if (favIds && favIds.size && !camsLoaded && typeof loadWorldTourCams === 'function') {
            loadWorldTourCams()
                .then(() => {
                    const resultsEl = document.getElementById('search-results');
                    if (resultsEl && resultsEl.classList.contains('active')) {
                        showSearchHistory();
                    }
                })
                .catch(err => console.warn('[favorites] world tour cams lazy-load failed:', err));
        }
    } catch (_) { /* defensive */ }


    const resultsEl = $('#search-results');
    const compactPanel = shouldUseCompactSearchPanel();
    // Filter out undefined or invalid items
    const history = getSearchHistory().filter(item => item && item.name && item.name !== 'undefined')
        .slice(0, compactPanel ? SEARCH_HISTORY_PANEL_ITEM_LIMIT : undefined);
    const bookmarks = getBookmarks().filter(item => item && item.name && item.name !== 'undefined')
        .slice(0, compactPanel ? SEARCH_HISTORY_PANEL_ITEM_LIMIT : undefined);

    let html = '';
    if (compactPanel) {
        html += renderSearchSortPanel();
        html += '<div class="search-history-scroll" aria-label="즐겨찾기 및 최근 검색">';
    }

    // Unified favorites — places (formerly 북마크) + domestic CCTV + World Tour cams.
    // Single section, star icon, no more separate "북마크" terminology.
    const favoriteCctvs = getFavoriteCctvs();
    const favoriteWorldCams = getFavoriteWorldTourCams();
    const totalFavorites = bookmarks.length + favoriteCctvs.length + favoriteWorldCams.length;
    const STAR_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>';
    html += `<div class="search-section-title">
        ${STAR_SVG}
        <span>즐겨찾기 · Favorite</span>
        ${totalFavorites > 0 ? `<span class="search-section-count">${totalFavorites}</span>` : ''}
    </div>`;
    if (totalFavorites > 0) {
        const cap = compactPanel ? SEARCH_HISTORY_PANEL_ITEM_LIMIT : 24;
        let remaining = cap;
        const cappedBookmarks = bookmarks.slice(0, remaining); remaining -= cappedBookmarks.length;
        const cappedCctvs = favoriteCctvs.slice(0, Math.max(0, remaining)); remaining -= cappedCctvs.length;
        const cappedWorld = favoriteWorldCams.slice(0, Math.max(0, remaining));
        html += cappedBookmarks.map(item => renderSearchItem(item, true)).join('');
        html += cappedCctvs.map(cctv => renderCctvFavoriteSearchItem(cctv)).join('');
        html += cappedWorld.map(cam => renderWorldTourFavoriteSearchItem(cam)).join('');
    } else {
        html += '<div class="search-section-empty">아직 즐겨찾기한 항목이 없습니다 — 검색 결과의 별 아이콘을 눌러 추가하세요.</div>';
    }


    // History Section (always show)
    html += `<div class="search-section-title">최근 검색</div>`;
    if (history.length > 0) {
        html += history.map(item => renderSearchItem(item, false)).join('');
    } else {
        html += '<div class="search-section-empty">최근 검색 주소가 없습니다</div>';
    }

    if (compactPanel) {
        html += '</div>';
    }

    resultsEl.innerHTML = html;
    resultsEl.classList.add('active');
    $('#dim-overlay').classList.add('active');
    renderQualityControls();
}

function renderWorldTourFavoriteSearchItem(cam) {
    const escape = s => String(s ?? '').replace(/[<>&"']/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));
    const title = cam.title || cam.city || cam.country || 'World Cam';
    const city = cam.city || cam.country || cam.region || '';
    return `
        <div class="search-result-item cctv-favorite-item cctv-favorite-item--world" data-world-cam-id="${escape(cam.id)}">
            <div class="search-result-info">
                <div class="search-result-name">
                    <span class="source-dot" style="background:#34d399" aria-hidden="true"></span>
                    ${escape(title)}
                </div>
                <div class="search-result-address">전세계 · ${escape(city)}</div>
            </div>
            <div class="search-result-actions">
                <button class="btn-delete" data-action="remove-favorite-world" title="즐겨찾기 해제">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

function renderCctvFavoriteSearchItem(cctv) {
    const parsed = parseCctvLabel(cctv.name || 'CCTV');
    const sourceMeta = getSourceMeta(cctv);
    const directionHtml = parsed.direction
        ? `<span class="cctv-favorite-direction"> (${parsed.direction})</span>`
        : '';
    return `
        <div class="search-result-item cctv-favorite-item" data-cctv-id="${cctv.id}">
            <div class="search-result-info">
                <div class="search-result-name">
                    <span class="source-dot" style="background:${sourceMeta.color}" aria-hidden="true"></span>
                    ${parsed.main}${directionHtml}
                </div>
                <div class="search-result-address">${sourceMeta.label}</div>
            </div>
            <div class="search-result-actions">
                <button class="btn-delete" data-action="remove-favorite" title="즐겨찾기 해제">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
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
                <button class="btn-bookmark ${bookmarkClass}" data-action="bookmark" title="${isBookmarked ? '즐겨찾기 해제' : '즐겨찾기 추가'}" aria-pressed="${isBookmarked}" aria-label="${isBookmarked ? '즐겨찾기 해제' : '즐겨찾기 추가'}">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linejoin="round">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
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

    // audit_utic_broken.py 가 HTTP 404 로 확인된 카메라를 status='disabled' 로 마킹.
    // 검색·지도·grid 어디에도 노출되지 않도록 로드 시점에 걸러냄.
    if (cctv.status === 'disabled') return true;

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

function getZ3CctvIp(cctv) {
    const url = cctv ? (cctv.directUrl || cctv.url || '') : '';
    return getUrlParam(url, 'cctvip');
}

function isZ3PlaybackCandidate(cctv) {
    const url = cctv ? (cctv.directUrl || cctv.url || '') : '';
    const kind = getUrlParam(url, 'kind');
    return !!cctv && (cctv.source === 'NTIC' || kind === 'Z3') && !!getZ3CctvIp(cctv);
}

function getZ3CacheRiskMeta(cctv) {
    if (!isZ3PlaybackCandidate(cctv)) return null;
    if (!z3CacheData) return null;

    const cctvip = getZ3CctvIp(cctv);
    const lastUpdated = z3CacheFetchedAt || null;
    if (z3CacheAgeMs > Z3_CACHE_STALE_MS) {
        return {
            regionKey: 'UTIC_Z3',
            status: 'Z3_CACHE_STALE',
            shortLabel: '캐시 점검 중',
            longLabel: `UTIC 국도 토큰 캐시가 오래되어 서버 리졸버로 직접 확인합니다 (${z3CacheSource})`,
            tone: 'warn',
            penalty: 3.5,
            lastUpdated
        };
    }

    if (cctvip && !z3CacheData[String(cctvip)]) {
        return {
            regionKey: 'UTIC_Z3',
            status: 'Z3_CACHE_MISS',
            shortLabel: '최신 목록 제외',
            longLabel: `${cctv.name || '이 CCTV'}는 최신 its.go.kr Z3 목록에서 확인되지 않아 재생 실패 가능성이 높습니다`,
            tone: 'danger',
            penalty: 10,
            lastUpdated
        };
    }

    return null;
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

    const z3CacheMeta = getZ3CacheRiskMeta(cctv);
    if (z3CacheMeta) return z3CacheMeta;

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

    const z3CacheMeta = getZ3CacheRiskMeta(cctv);
    if (z3CacheMeta && z3CacheMeta.status === 'Z3_CACHE_MISS') {
        return true;
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
        || (source === 'UTIC' && kind === 'Z3' && !!getUrlParam(url, 'cctvip'))
        // GANGWON/HRFCO iframe 임베드 카메라는 health monitor 가 m3u8/mp4 못 받아서 frame_only 로 잘못 분류하지만
        // 클라이언트는 이미 iframe 으로 직접 임베드해서 정상 재생함. region DOWN 신호를 받아도 격리하지 않도록.
        || isFrameOnlyPlaybackCandidate(cctv)
        // YouTube 카메라(GIGAEYES) 도 동일 — 원본이 YouTube 라이브이므로 health monitor 의 frame_or_bad_content 는 오탐.
        || /(?:youtube\.com|youtu\.be)/.test(url);
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
    if (['CAMERA_CRITICAL', 'CAMERA_INVESTIGATE', 'PLAYBACK_ERROR', 'QUALITY_DOWN', 'Z3_CACHE_MISS'].includes(health.status)) {
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

    const z3CacheMeta = getZ3CacheRiskMeta(cctv);
    if (z3CacheMeta?.status === 'Z3_CACHE_MISS') {
        score -= 0.28;
    } else if (z3CacheMeta?.status === 'Z3_CACHE_STALE') {
        score -= 0.08;
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
    // The "● 재생 불안정" pill that used to sit next to the CCTV
    // name was redundant with the colored status dot inside the
    // .cctv-select-trigger button. Strip any leftover badge node
    // and skip rendering.
    panel?.querySelector?.('.panel-health-badge')?.remove?.();
}

function renderSelectTrigger(panel, cctv, fallbackLabel) {
    const trigger = panel.querySelector('.cctv-select-trigger');
    if (!trigger) return;

    const health = getCameraHealthMeta(cctv);
    const confidence = getCameraPlaybackConfidence(cctv, health);
    const fullLabel = cctv?.name || fallbackLabel || 'CCTV 선택';
    const parsed = parseCctvLabel(fullLabel);
    const sourceMeta = getSourceMeta(cctv);
    trigger.innerHTML = '';

    // The data-source dot (SPATIC / UTIC / NTIC) used to sit on the LEFT
    // of the name, paired with the playback-status dot on the right.
    // That made the trigger feel double-decorated. We keep only the
    // status dot (right) which conveys playback health — the more useful
    // signal — and surface the source label through the tooltip.

    const name = document.createElement('span');
    name.className = 'cctv-select-name';
    if (parsed.direction) {
        // "장소 (방향)" 형식 — direction은 흐리게 강조
        const mainSpan = document.createElement('span');
        mainSpan.className = 'cctv-select-main';
        mainSpan.textContent = parsed.main;
        const dirSpan = document.createElement('span');
        dirSpan.className = 'cctv-select-direction';
        dirSpan.textContent = ` (${parsed.direction})`;
        name.append(mainSpan, dirSpan);
    } else {
        name.textContent = parsed.main;
    }

    const dot = document.createElement('span');
    dot.className = `cctv-status-dot tone-${confidence.tone}`;
    dot.setAttribute('aria-hidden', 'true');

    trigger.append(name, dot);
    trigger.title = `${parsed.full} · ${sourceMeta.label} · ${confidence.label} · ${confidence.title} · ${formatRelativeTime(health.lastUpdated)}`;
    trigger.setAttribute('aria-label', `${parsed.full}, ${sourceMeta.label}, ${confidence.label}`);
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

    const health = getCameraHealthMeta(cctv);
    const sourceMeta = getSourceMeta(cctv);

    subTitle.innerHTML = `
        <span class="source-dot" style="background:${sourceMeta.color}" aria-hidden="true"></span>
        <span class="video-title-source">${sourceMeta.label}</span>
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

// Configure once the worker is deployed. Leave as null to disable dynamic OG.
const CCTV_OG_WORKER_URL = null; // e.g. 'https://cctv-og.pyw31337.workers.dev/og'

function buildOgImageUrl(cctv) {
    if (!CCTV_OG_WORKER_URL || !cctv) return null;
    const params = new URLSearchParams();
    params.set('id', cctv.id);
    const parsed = parseCctvLabel(cctv.name || '');
    const title = parsed.direction ? `${parsed.main} (${parsed.direction})` : parsed.main;
    params.set('title', title);
    const sourceMeta = getSourceMeta(cctv);
    if (cctv.city) params.set('city', cctv.city);
    else if (sourceMeta?.label) params.set('city', sourceMeta.label);
    if (cctv.snapshotUrl) params.set('snap', cctv.snapshotUrl);
    return `${CCTV_OG_WORKER_URL}?${params.toString()}`;
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
    // Dynamic OG image (no-op when CCTV_OG_WORKER_URL is null). Share APIs
    // that respect URL preview metadata will surface this richer card.
    const ogImageUrl = buildOgImageUrl(cctv);
    if (ogImageUrl) {
        try {
            document.querySelector('meta[property="og:image"]')?.setAttribute('content', ogImageUrl);
            document.querySelector('meta[name="twitter:image"]')?.setAttribute('content', ogImageUrl);
        } catch (_) { /* meta updates are best-effort */ }
    }

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

// (Mobile 1+3 layout removed by user request — keep simple 2×2 / 1×4 grid.)
function renderVideoGrid() {
    const grid = $('#video-grid');
    const strayStrip = grid.querySelector(':scope > .video-thumb-strip');
    if (strayStrip) {
        Array.from(strayStrip.children).forEach(child => grid.appendChild(child));
        strayStrip.remove();
        grid.classList.remove('video-grid-mobile-1plus3');
    }
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

    const originalPlaybackUrl = url;
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
    const isUtic = url.includes('utic.go.kr')
        || url.includes('openDataCctvStream')
        || (selectedKind === 'Z3' && url.includes('/utic?'));
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
    // Z3 kind: resolve from the Oracle-served fresh cache first, then fall back to
    // direct token and Oracle resolver paths. Other kinds use the UTIC resolver.
    if (isUtic) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        const uticSourceUrl = originalPlaybackUrl || url;
        const isZ3 = selectedKind === 'Z3' || uticSourceUrl.includes('kind=Z3') || url.includes('kind=Z3');
        const cctvipMatch = uticSourceUrl.match(/[?&]cctvip=(\d+)/) || url.match(/[?&]cctvip=(\d+)/);
        const z3CctvIp = isZ3 && cctvipMatch ? cctvipMatch[1] : null;

        (async () => {
            let streamUrl = null;

            try {
                if (isZ3 && z3CctvIp) {
                    // Z3 전략 1: Oracle /z3-cache.json 우선, 정적 GitHub 캐시는 긴급 fallback
                    try {
                        const cacheWorkerUrl = await getZ3StreamUrl(z3CctvIp);
                        if (cacheWorkerUrl) {
                            const cacheResp = await fetch(cacheWorkerUrl, { cache: 'no-store' });
                            if (cacheResp.ok) {
                                const cacheText = (await cacheResp.text()).trim();
                                if (cacheText && cacheText.startsWith('http')) {
                                    streamUrl = cacheText;
                                    console.log(`[Z3] Resolved ${z3CctvIp} through ${z3CacheSource} cache (${Math.round(z3CacheAgeMs / 60000)}min old)`);
                                }
                            }
                        }
                    } catch(e2) { console.warn('[Z3] 전략1 실패:', e2); }

                    // Z3 전략 2: cctv_data.json의 id 파라미터 사용 (fallback)
                    if (!streamUrl) {
                        try {
                            const idParam = new URL(uticSourceUrl).searchParams.get('id');
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

                    // Z3 전략 3: Oracle /utic가 서버 로컬 최신 캐시를 읽고 /proxy로 리다이렉트한다.
                    if (!streamUrl) {
                        try {
                            let uticSearch = '';
                            try { uticSearch = new URL(uticSourceUrl).search.substring(1); } catch(e3) {
                                try { uticSearch = new URL(url).search.substring(1); } catch(e4) {}
                            }
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
                        // Z3 매니페스트는 Oracle 프록시 경유로 RTT 변동이 큼 — 1회 재시도는 첫 패스 일시
                        // 실패에 너무 가혹. 9s→15s, retry 1→2 로 완화해 부팅 직후 cold-start 흡수.
                        fragLoadingTimeOut: isZ3 ? 18000 : 30000,
                        manifestLoadingTimeOut: isZ3 ? 15000 : 15000,
                        manifestLoadingMaxRetry: isZ3 ? 2 : 2,
                        levelLoadingMaxRetry: isZ3 ? 2 : 2,
                        fragLoadingMaxRetry: isZ3 ? 3 : 4,
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

// Strip raw playback IDs / hash-like tokens that some embedded players (YouTube/HLS)
// surface in their error text so we never expose stuff like
// "재생 ID는 rTlVQwEQfepKr_Dy입니다" to the user.
function sanitizeErrorMessage(text) {
    if (text == null) return '';
    let s = String(text);
    s = s.replace(/재생\s*ID(?:는|은|:)?\s*[A-Za-z0-9_\-]{6,}\s*입?니?다?\.?/g, '');
    s = s.replace(/playback\s*id\s*[:=]?\s*[A-Za-z0-9_\-]{6,}\.?/gi, '');
    s = s.replace(/(error|err)\s*code\s*[:=]?\s*[A-Za-z0-9_\-]{4,}\.?/gi, '');
    s = s.replace(/\b[A-Za-z0-9_\-]{16,}\b/g, '');
    s = s.replace(/\s+/g, ' ').trim();
    return s;
}

function findAnotherNearbyCctv(currentCctv) {
    if (!currentCctv || !Array.isArray(state.nearestCctvs)) return null;
    const list = state.nearestCctvs;
    const idx = list.findIndex(item => item && item.id === currentCctv.id);
    if (idx === -1) {
        return list.find(item => item && item.id !== currentCctv.id) || null;
    }
    for (let offset = 1; offset < list.length; offset += 1) {
        const candidate = list[(idx + offset) % list.length];
        if (candidate && candidate.id !== currentCctv.id) return candidate;
    }
    return null;
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
        cctv = null,
        onTryAnother = null,
        showTryAnother = true
    } = config;

    // Sanitize first so raw playback IDs never reach the DOM.
    const cleanMessage = sanitizeErrorMessage(message) || '영상을 불러올 수 없습니다';
    const cleanDetail = sanitizeErrorMessage(detail);
    const friendlyDetail = cleanDetail || '잠시 후 다시 시도하거나 다른 카메라를 골라 보세요.';

    const ph = document.createElement('div');
    ph.className = 'video-placeholder error';
    let html = `
        <div class="error-message-block">
            <span class="error-message-icon" aria-hidden="true">📡</span>
            <span class="error-message-title">영상 연결을 다시 시도해 주세요</span>
            <span class="error-message-body">${cleanMessage}</span>
            <span class="error-message-meta">${friendlyDetail}</span>
        </div>
    `;

    const actions = [];
    if (retryFn) {
        actions.push(`<button class="retry-btn" type="button">${retryLabel}</button>`);
    }
    const allowTryAnother = showTryAnother && cctv && (typeof onTryAnother === 'function' || findAnotherNearbyCctv(cctv));
    if (allowTryAnother) {
        actions.push(`<button class="try-another-btn" type="button"><svg class="try-another-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M19.95 11a8 8 0 1 0 -.5 4m.5 5v-5h-5"/></svg><span>다른 카메라 시도</span></button>`);
    }
    if (cctv) {
        actions.push('<button class="report-btn" type="button">문제 제보</button>');
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
    if (allowTryAnother) {
        const tryBtn = ph.querySelector('.try-another-btn');
        tryBtn.onclick = (e) => {
            e.stopPropagation();
            tryBtn.classList.add('pressed');
            setTimeout(() => tryBtn.classList.remove('pressed'), 120);
            try {
                if (typeof onTryAnother === 'function') {
                    onTryAnother();
                } else {
                    const next = findAnotherNearbyCctv(cctv);
                    if (next && typeof openVideoLayer === 'function') {
                        openVideoLayer(next);
                    }
                }
            } catch (err) {
                console.warn('[error-placeholder] tryAnother failed:', err);
            }
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
    // Cap the zoom-out so users don't end up looking at the empty
    // beige "kakaomap" background. Kakao's outer levels (>= 12) often
    // have no tiles for South Korea, leaving the map blank.
    if (typeof map.setMaxLevel === 'function') {
        map.setMaxLevel(11);
    }
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

    // Precipitation overlay toggle button + initial state
    initKmaPrecipOverlay();
}

// === KMA precipitation/snow overlay (domestic Kakao map) ===
// Loads data/kma_precip_current.json (refreshed every 30min by a GHA) and
// renders graduated circles colored by pty (rain/snow) and sized by amount.
// Toggle button sits next to the weather button so users can opt-in.

const KMA_PRECIP_DATA_URL = 'data/kma_precip_current.json';
let kmaPrecipOverlays = [];
let kmaPrecipData = null;
let kmaPrecipFetchPromise = null;
let kmaPrecipVisible = false;

function getKmaPtyStyle(point) {
    const pty = point.pty;
    const rain = point.rainMm6h || 0;
    const snow = point.snowCm6h || 0;
    if (pty === 'snow' || pty === 'snow_flurry') {
        return {
            color: '#c5d9f1',
            stroke: '#3b82f6',
            label: snow > 0 ? `❄ ${snow.toFixed(1)}cm` : '❄ 눈',
            value: snow,
            radiusBase: 16 + Math.min(snow * 6, 40)
        };
    }
    if (pty === 'sleet' || pty === 'drizzle_sleet') {
        return {
            color: '#bae6fd',
            stroke: '#0ea5e9',
            label: `🌨 ${rain.toFixed(1)}mm`,
            value: rain,
            radiusBase: 14 + Math.min(rain * 3, 30)
        };
    }
    if (pty === 'rain' || pty === 'drizzle') {
        return {
            color: '#93c5fd',
            stroke: '#2563eb',
            label: rain > 0 ? `🌧 ${rain.toFixed(1)}mm` : '🌧 비',
            value: rain,
            radiusBase: 14 + Math.min(rain * 3, 30)
        };
    }
    return null; // no precip — skip
}

async function loadKmaPrecipData() {
    if (kmaPrecipData) return kmaPrecipData;
    if (kmaPrecipFetchPromise) return kmaPrecipFetchPromise;
    kmaPrecipFetchPromise = fetch(`${KMA_PRECIP_DATA_URL}?v=${APP_BUILD_VERSION}`, { cache: 'no-cache' })
        .then(r => r.ok ? r.json() : null)
        .then(json => { kmaPrecipData = json; return json; })
        .catch(err => { console.warn('[KMA] failed to load precip grid:', err); return null; });
    return kmaPrecipFetchPromise;
}

function clearKmaPrecipOverlays() {
    kmaPrecipOverlays.forEach(o => {
        try { o.setMap(null); } catch (_) {}
    });
    kmaPrecipOverlays = [];
}

async function renderKmaPrecipOverlays() {
    if (!map || !window.kakao?.maps) return;
    clearKmaPrecipOverlays();
    const data = await loadKmaPrecipData();
    if (!data || !Array.isArray(data.points)) return;

    let hasAny = false;
    const renderedLatLngs = [];
    data.points.forEach(point => {
        const style = getKmaPtyStyle(point);
        if (!style) return;
        hasAny = true;
        const latLng = new kakao.maps.LatLng(point.lat, point.lng);
        renderedLatLngs.push(latLng);

        const circle = new kakao.maps.Circle({
            center: latLng,
            radius: style.radiusBase * 200,
            strokeWeight: 2,
            strokeColor: style.stroke,
            strokeOpacity: 0.7,
            strokeStyle: 'solid',
            fillColor: style.color,
            fillOpacity: 0.32
        });
        circle.setMap(map);
        kmaPrecipOverlays.push(circle);

        const overlay = new kakao.maps.CustomOverlay({
            position: latLng,
            content: `<div class="kma-precip-label" title="${point.name} · ${point.wfKor || ''}">${style.label}<span class="kma-precip-city">${point.name}</span></div>`,
            yAnchor: 0.5,
            zIndex: 5
        });
        overlay.setMap(map);
        kmaPrecipOverlays.push(overlay);
    });

    updateKmaPrecipEmptyHint(!hasAny);
    updateKmaPrecipButtonLabel(renderedLatLngs.length);

    // When the user just turned the toggle on, frame the map around the
    // precipitation points so they can see something change — otherwise
    // the toggle feels broken when the user happens to be staring at a
    // dry region. Only fits once per enable; subsequent renders leave
    // the user's pan/zoom alone.
    if (hasAny && kmaPrecipShouldFitOnNextRender) {
        kmaPrecipShouldFitOnNextRender = false;
        const bounds = new kakao.maps.LatLngBounds();
        renderedLatLngs.forEach(ll => bounds.extend(ll));
        try { map.setBounds(bounds); } catch (_) { /* tolerate */ }
    }
}

// Set true on every enable so the next render frames the rain points.
let kmaPrecipShouldFitOnNextRender = false;

function updateKmaPrecipButtonLabel(activeCount) {
    const btn = document.getElementById('kma-precip-toggle');
    if (!btn) return;
    const label = btn.querySelector('.kma-precip-toggle-label');
    if (!label) return;
    if (kmaPrecipVisible && activeCount > 0) {
        label.textContent = `강수 ${activeCount}곳`;
    } else if (kmaPrecipVisible) {
        label.textContent = '강수 없음';
    } else {
        label.textContent = '강수';
    }
}

function updateKmaPrecipEmptyHint(empty) {
    let hint = document.getElementById('kma-precip-empty-hint');
    if (empty && kmaPrecipVisible) {
        if (!hint) {
            hint = document.createElement('div');
            hint.id = 'kma-precip-empty-hint';
            hint.className = 'kma-precip-empty-hint';
            hint.textContent = '☀ 현재 비/눈 예보 없음';
            const mapView = document.getElementById('map-view');
            if (mapView) mapView.appendChild(hint);
        }
    } else if (hint) {
        hint.remove();
    }
}

function setKmaPrecipVisible(visible) {
    const wasVisible = kmaPrecipVisible;
    kmaPrecipVisible = visible;
    const btn = document.getElementById('kma-precip-toggle');
    if (btn) {
        btn.classList.toggle('active', visible);
        btn.setAttribute('aria-pressed', visible ? 'true' : 'false');
        btn.title = visible ? '강수/적설 오버레이 끄기' : '강수/적설 오버레이 보기';
    }
    if (visible) {
        // Only frame the precip points on a fresh enable, not on
        // subsequent re-renders from data refresh / map move handlers.
        if (!wasVisible) kmaPrecipShouldFitOnNextRender = true;
        renderKmaPrecipOverlays();
    } else {
        clearKmaPrecipOverlays();
        updateKmaPrecipEmptyHint(false);
        updateKmaPrecipButtonLabel(0);
    }
    try { localStorage.setItem('cctv_kma_precip_visible', visible ? '1' : '0'); } catch (_) {}
}

// === Multi-CCTV compare mode ("전국 주요 도시") ===
// Curated city → CCTV id mapping. Picked by nearest-distance + source quality
// at curation time. Falls back gracefully if any id has been removed.
const NATIONAL_COMPARE_CAMERAS = [
    { city: '서울', cctvId: 'TOPIS_190' },
    { city: '부산', cctvId: 'BUSAN_CTV0000016' },
    { city: '대구', cctvId: 'DAEGU_49' },
    { city: '인천', cctvId: 'INCHEON_39' },
    { city: '광주', cctvId: 'GWANGJU_CCTV000061' },
    { city: '대전', cctvId: 'E07048' },
    { city: '울산', cctvId: 'ULSAN_298' },
    { city: '제주', cctvId: 'L380020' }
];

let compareModeActive = false;
let compareLayer = null;

function getCompareCameras() {
    return NATIONAL_COMPARE_CAMERAS
        .map(entry => ({ ...entry, cctv: findCctvById(entry.cctvId) }))
        .filter(entry => entry.cctv);
}

function openCompareMode() {
    if (compareModeActive) return;
    compareModeActive = true;

    if (!compareLayer) {
        compareLayer = document.createElement('div');
        compareLayer.id = 'compare-layer';
        compareLayer.className = 'compare-layer';
        compareLayer.innerHTML = `
            <div class="compare-layer-header">
                <div>
                    <h2>전국 주요 도시 라이브</h2>
                    <p>같은 시각, 8개 광역시·도청 인근 카메라</p>
                </div>
                <button class="compare-layer-close" id="compare-layer-close" title="닫기" aria-label="비교 모드 닫기">×</button>
            </div>
            <div class="compare-grid" id="compare-grid"></div>
        `;
        document.body.appendChild(compareLayer);
        compareLayer.querySelector('#compare-layer-close').addEventListener('click', closeCompareMode);
    }

    const grid = compareLayer.querySelector('#compare-grid');
    grid.innerHTML = '';

    const entries = getCompareCameras();
    if (!entries.length) {
        grid.innerHTML = '<div class="compare-empty">curated 카메라를 찾을 수 없습니다. 새로고침 후 다시 시도해 주세요.</div>';
    }

    entries.forEach(entry => {
        const tile = document.createElement('div');
        tile.className = 'compare-tile';
        tile.dataset.cctvId = entry.cctv.id;
        const parsed = parseCctvLabel(entry.cctv.name || '');
        const sourceMeta = getSourceMeta(entry.cctv);
        tile.innerHTML = `
            <div class="compare-tile-header">
                <span class="compare-tile-city">${entry.city}</span>
                <span class="compare-tile-meta">
                    <span class="source-dot" style="background:${sourceMeta.color}" aria-hidden="true"></span>
                    <span>${parsed.main}${parsed.direction ? ` (${parsed.direction})` : ''}</span>
                </span>
                <button class="compare-tile-expand" type="button" title="크게 보기" aria-label="${entry.city} 카메라 크게 보기">⤢</button>
            </div>
            <div class="compare-tile-media"></div>
        `;
        const media = tile.querySelector('.compare-tile-media');
        const video = createVideoElement(entry.cctv);
        media.appendChild(video);
        if (video.tagName === 'VIDEO') {
            video.muted = true;
            video.dataset.activeCctvId = entry.cctv.id;
            video.dataset.sourceIndex = '0';
            video._activeCctv = entry.cctv;
            scheduleVideoHealthProbe(media, entry.cctv, video);
        }
        tile.querySelector('.compare-tile-expand').addEventListener('click', () => {
            closeCompareMode();
            openVideoLayer(entry.cctv);
        });
        grid.appendChild(tile);
    });

    compareLayer.classList.add('active');
    document.body.classList.add('compare-mode-active');
}

function closeCompareMode() {
    compareModeActive = false;
    if (!compareLayer) return;
    // Cleanup video elements to release HLS workers, sockets, etc.
    compareLayer.querySelectorAll('.compare-tile-media').forEach(media => cleanupVideo(media));
    compareLayer.classList.remove('active');
    document.body.classList.remove('compare-mode-active');
}

// lucide-cctv icon — used for the "전국 주요 도시 라이브" button on both the
// desktop header and inside the mobile search-results compact panel.
const COMPARE_MODE_ICON_SVG = `
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-cctv-icon lucide-cctv" aria-hidden="true">
        <path d="M16.75 12h3.632a1 1 0 0 1 .894 1.447l-2.034 4.069a1 1 0 0 1-1.708.134l-2.124-2.97"/>
        <path d="M17.106 9.053a1 1 0 0 1 .447 1.341l-3.106 6.211a1 1 0 0 1-1.342.447L3.61 12.3a2.92 2.92 0 0 1-1.3-3.91L3.69 5.6a2.92 2.92 0 0 1 3.92-1.3z"/>
        <path d="M2 19h3.76a2 2 0 0 0 1.8-1.1L9 15"/>
        <path d="M2 21v-4"/>
        <path d="M7 9h.01"/>
    </svg>
`;

function initCompareModeButton() {
    // 전국 주요 도시 라이브 feature removed per user request — function
    // is now a no-op AND defensively removes any leftover button node
    // a cached older bundle might have injected.
    document.getElementById('compare-mode-btn')?.remove?.();
}

function initKmaPrecipOverlay() {
    if (document.getElementById('kma-precip-toggle')) return;
    const mapView = document.getElementById('map-view');
    if (!mapView) return;

    const btn = document.createElement('button');
    btn.id = 'kma-precip-toggle';
    btn.className = 'kma-precip-toggle';
    btn.type = 'button';
    btn.title = '강수/적설 오버레이 보기';
    btn.setAttribute('aria-pressed', 'false');
    btn.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9"/>
            <path d="M8 19l1-2"/>
            <path d="M12 21l1-2"/>
            <path d="M16 19l1-2"/>
        </svg>
        <span class="kma-precip-toggle-label">강수</span>
    `;
    btn.addEventListener('click', () => setKmaPrecipVisible(!kmaPrecipVisible));
    mapView.appendChild(btn);

    // Restore prior preference.
    try {
        if (localStorage.getItem('cctv_kma_precip_visible') === '1') {
            setKmaPrecipVisible(true);
        }
    } catch (_) {}
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
    state.worldTourListOpen = false;
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
    state.worldTourListOpen = false;
    $('#weather-title').textContent = '세계 관광 라이브 지도';
    if (!isWorldTourRegionAvailable(state.worldTourRegion)) {
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
        .filter(item => item && (item.videoId || item.embedUrl || item.playUrl || item.sourceUrl))
        .sort((a, b) => (
            Number(b.qualityScore || b.stabilityScore || b.priority || 0)
            - Number(a.qualityScore || a.stabilityScore || a.priority || 0)
        ) || String(a.title).localeCompare(String(b.title)));
    pruneWorldTourFavorites(state.worldTourCams);
    return state.worldTourCams;
}

function getWorldTourEmbedUrl(cam) {
    if (cam.embedUrl) return cam.embedUrl;
    if (cam.playUrl) return cam.playUrl;
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
    // A cam is "playable in-app" if we can render *any* live representation
    // inside our page — either a video/iframe player or an auto-refreshing
    // snapshot image (HK Traffic / USGS / Panomax / Roundshot).
    return Boolean(cam?.videoId || cam?.embedUrl || cam?.playUrl || cam?.snapshotUrl);
}

// Returns a suggested refresh cadence (ms) for snapshot-based cameras.
// Conservative defaults keep CDN load reasonable while feeling "live".
function getWorldTourSnapshotRefreshMs(cam) {
    const sourceType = (cam?.sourceType || '').toLowerCase();
    if (sourceType === 'hktraffic') return 30_000;     // HK CCTV: 30s
    if (sourceType === 'usgsvolcano') return 60_000;   // USGS volc: 1min
    if (sourceType === 'baltic') return 2 * 60_000;    // Baltic thumbs CDN: ~2min
    if (sourceType === 'worldcam') return 3 * 60_000;  // WorldCam live JPG: ~3min
    if (sourceType === 'panomax') return 5 * 60_000;   // Panomax: 5min
    if (sourceType === 'roundshot') return 0;          // Roundshot URL is dated; no refresh
    return 60_000;
}

function isWorldTourHlsUrl(url) {
    return /\.m3u8(?:[?#].*)?$/i.test(String(url || '').trim());
}

function isWorldTourDirectVideoUrl(url) {
    return /\.(?:mp4|webm|ogv)(?:[?#].*)?$/i.test(String(url || '').trim());
}

function normalizeWorldTourText(value) {
    return String(value || '').toLowerCase().replace(/\s+/g, ' ').trim();
}

function getWorldTourSearchText(cam) {
    return normalizeWorldTourText([
        cam?.title,
        cam?.subtitle,
        cam?.city,
        cam?.country,
        cam?.region,
        cam?.channel,
        getWorldTourRegionLabel(cam?.region),
        getWorldTourSourceLabel(cam),
        ...(Array.isArray(cam?.tags) ? cam.tags : [])
    ].filter(Boolean).join(' '));
}

function getWorldTourListBaseCams(cams) {
    const region = isWorldTourRegionAvailable(state.worldTourListRegion)
        ? state.worldTourListRegion
        : 'All';
    if (region === WORLD_TOUR_FAVORITE_REGION) {
        const favorites = getWorldTourFavoriteIds();
        return cams.filter(cam => favorites.has(String(cam.id)));
    }
    if (region === 'All') return cams;
    return cams.filter(cam => cam.region === region);
}

function getWorldTourListCountries(cams) {
    const baseCams = getWorldTourListBaseCams(cams);
    const visibleCams = state.worldTourListExcludeExternal
        ? baseCams.filter(canPlayWorldTourInApp)
        : baseCams;
    const counts = visibleCams.reduce((acc, cam) => {
        const country = cam.country || 'Unknown';
        acc[country] = (acc[country] || 0) + 1;
        return acc;
    }, {});
    // Sort alphabetically (A → Z, case-insensitive) so the dropdown is
    // easy to scan regardless of which tab the user opened the list on.
    return Object.entries(counts).sort((a, b) =>
        a[0].localeCompare(b[0], undefined, { sensitivity: 'base' })
    );
}

function getWorldTourListSources(cams) {
    const counts = getWorldTourListBaseCams(cams).reduce((acc, cam) => {
        const sourceType = String(cam.sourceType || (cam.videoId ? 'youtube' : 'external')).toLowerCase();
        const label = getWorldTourSourceLabel(cam);
        const key = `${sourceType}::${label}`;
        acc[key] = acc[key] || { sourceType, label, count: 0 };
        acc[key].count += 1;
        return acc;
    }, {});
    return Object.values(counts).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function getWorldTourListFilteredCams(cams) {
    const search = normalizeWorldTourText(state.worldTourListSearch);
    // When the user is actively typing, ignore the region tab and search
    // across the entire dataset so a query never silently returns nothing
    // because of a stale tab selection.
    let filtered = search
        ? cams.slice()
        : getWorldTourListBaseCams(cams);

    if (state.worldTourListCountry && state.worldTourListCountry !== 'All') {
        filtered = filtered.filter(cam => cam.country === state.worldTourListCountry);
    }
    if (state.worldTourListExcludeExternal) {
        filtered = filtered.filter(canPlayWorldTourInApp);
    }
    if (search) {
        filtered = filtered.filter(cam => getWorldTourSearchText(cam).includes(search));
    }

    return filtered;
}

function sanitizeWorldTourListFilters(cams) {
    const region = isWorldTourRegionAvailable(state.worldTourListRegion) ? state.worldTourListRegion : 'All';
    state.worldTourListRegion = region;

    const countries = new Set(getWorldTourListCountries(cams).map(([country]) => country));
    if (state.worldTourListCountry !== 'All' && !countries.has(state.worldTourListCountry)) {
        state.worldTourListCountry = 'All';
    }

    // worldTourListSource is no longer surfaced in the UI but the state
    // field is retained for backwards compatibility — reset stale values
    // so they don't unexpectedly filter results.
    state.worldTourListSource = 'All';
    state.worldTourListExcludeExternal = !!state.worldTourListExcludeExternal;
}

function isWorldTourRegionAvailable(region) {
    return region === WORLD_TOUR_FAVORITE_REGION || WORLD_TOUR_REGIONS.includes(region);
}

// === Unified favorites store ===========================================
// One Set holds favorite IDs for both domestic CCTVs and World Tour cams.
// Migrates the two legacy keys on first run. All existing wrappers
// (isCctvFavorite, isWorldTourFavorite, etc.) delegate here so caller
// sites stay unchanged.
const UNIFIED_FAVORITES_STORAGE_KEY = 'cctv_favorites_unified_v1';
function hydrateUnifiedFavorites() {
    try {
        const raw = localStorage.getItem(UNIFIED_FAVORITES_STORAGE_KEY);
        const ids = raw ? JSON.parse(raw) : [];
        state.unifiedFavorites = new Set(Array.isArray(ids) ? ids.map(String).filter(Boolean) : []);
    } catch (error) {
        console.warn('[Favorites] failed to restore:', error);
        state.unifiedFavorites = new Set();
    }
    let migrated = false;
    [WORLD_TOUR_FAVORITES_STORAGE_KEY, CCTV_FAVORITES_STORAGE_KEY].forEach(legacyKey => {
        try {
            const raw = localStorage.getItem(legacyKey);
            if (!raw) return;
            const ids = JSON.parse(raw);
            if (Array.isArray(ids)) {
                ids.map(String).filter(Boolean).forEach(id => state.unifiedFavorites.add(id));
                localStorage.removeItem(legacyKey);
                migrated = true;
            }
        } catch (_) {}
    });
    if (migrated) persistUnifiedFavorites();
    state.worldTourFavorites = state.unifiedFavorites;
    state.cctvFavorites = state.unifiedFavorites;
}
function getUnifiedFavoriteIds() {
    if (!(state.unifiedFavorites instanceof Set)) hydrateUnifiedFavorites();
    return state.unifiedFavorites;
}
function persistUnifiedFavorites() {
    try { localStorage.setItem(UNIFIED_FAVORITES_STORAGE_KEY, JSON.stringify([...getUnifiedFavoriteIds()])); }
    catch (e) { console.warn('[Favorites] save failed:', e); }
}
function isUnifiedFavorite(o) {
    const id = typeof o === 'object' ? o?.id : o;
    return Boolean(id && getUnifiedFavoriteIds().has(String(id)));
}
function toggleUnifiedFavorite(o) {
    const id = typeof o === 'object' ? o?.id : o;
    if (!id) return false;
    const f = getUnifiedFavoriteIds(); const k = String(id);
    const will = !f.has(k);
    if (will) f.add(k); else f.delete(k);
    persistUnifiedFavorites();
    return will;
}
function hydrateWorldTourFavorites() { hydrateUnifiedFavorites(); }
function hydrateCctvFavorites() { hydrateUnifiedFavorites(); }
function getWorldTourFavoriteIds() { return getUnifiedFavoriteIds(); }
function getCctvFavoriteIds() { return getUnifiedFavoriteIds(); }
function persistWorldTourFavorites() { persistUnifiedFavorites(); }
function persistCctvFavorites() { persistUnifiedFavorites(); }
function isWorldTourFavorite(o) { return isUnifiedFavorite(o); }
function isCctvFavorite(o) { return isUnifiedFavorite(o); }
function toggleWorldTourFavorite(id) { return toggleUnifiedFavorite(id); }
function toggleCctvFavorite(o) { return toggleUnifiedFavorite(o); }

function pruneWorldTourFavorites(cams) {
    const f = getUnifiedFavoriteIds();
    if (!f.size) return;
    const camIds = new Set(cams.map(c => String(c.id)));
    // Only prune ids that match world-tour cam id patterns — leave domestic
    // CCTV ids (TOPIS_*, UTIC L*, BUSAN_CTV*, etc.) alone.
    const wtPrefix = /^(?:earthcam|baltic|skyline|hktraffic|usgsvolcano|panomax|roundshot|worldcam|webcamtaxi|youtube|external|africam|alertcalifornia|aurorainfo|bergfex|camscape|cctvworld|climaaovivo|dctraffic|explore|feratel|gigaeyes|hdontap|idokep|japanwebcams|liveworldwebcams|livecamcroatia|livebeaches|nswtraffic|openwebcamdb|panoramask|ptztv|publictraffic|railcam|spacecam|surfline|tabi|twlivecam|viewsurf|weatherbug|webcamhopper|webcamera24|webcamsdemexico|wetter|whatsupcams|windy|worldcamtv|worldcamlive)/i;
    let changed = false;
    f.forEach(id => { if (wtPrefix.test(id) && !camIds.has(id)) { f.delete(id); changed = true; } });
    if (changed) persistUnifiedFavorites();
}

function getFavoriteCctvs() {
    const f = getUnifiedFavoriteIds();
    if (!f.size) return [];
    const r = [];
    f.forEach(id => { const c = findCctvById(id); if (c) r.push(c); });
    return r;
}
function getFavoriteWorldTourCams() {
    const f = getUnifiedFavoriteIds();
    if (!f.size) return [];
    const cams = (state.worldTourCams && state.worldTourCams.items) || (Array.isArray(state.worldTourCams) ? state.worldTourCams : []);
    if (!Array.isArray(cams)) return [];
    return cams.filter(c => f.has(String(c.id)));
}

function renderCctvFavoriteButton(cctv) {
    const active = isCctvFavorite(cctv);
    const title = active ? '즐겨찾기 해제' : '즐겨찾기 추가';
    return `
        <button id="video-layer-favorite" class="layer-action-btn favorite-toggle ${active ? 'active' : ''}" title="${title}" aria-pressed="${active}" aria-label="${title}">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="${active ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
        </button>`;
}


function renderWorldTourFavoriteButton(cam, variant = 'card') {
    const isActive = isWorldTourFavorite(cam);
    const title = isActive ? '즐겨찾기 해제' : '즐겨찾기 추가';

    return `
        <button
            type="button"
            class="world-tour-favorite-btn world-tour-favorite-btn-${escapeWorldTourHtml(variant)} ${isActive ? 'active' : ''}"
            data-world-tour-favorite="${escapeWorldTourHtml(cam.id)}"
            aria-pressed="${isActive}"
            aria-label="${escapeWorldTourHtml(`${cam.title} ${title}`)}"
            title="${escapeWorldTourHtml(title)}"
        >${WORLD_TOUR_STAR_SVG}</button>
    `;
}

function getWorldTourRegionCounts(cams) {
    // Honor the "원본만 보기" toggle — when active, region chip counts
    // (All / North America / Europe / ...) drop to the playable-only set
    // so the count matches the map markers and card rail.
    const source = state.worldTourListExcludeExternal
        ? cams.filter(canPlayWorldTourInApp)
        : cams;
    const favorites = getWorldTourFavoriteIds();
    return source.reduce((counts, cam) => {
        const region = cam.region || 'Other';
        counts.All = (counts.All || 0) + 1;
        if (favorites.has(String(cam.id))) {
            counts[WORLD_TOUR_FAVORITE_REGION] = (counts[WORLD_TOUR_FAVORITE_REGION] || 0) + 1;
        }
        counts[region] = (counts[region] || 0) + 1;
        return counts;
    }, { All: 0, [WORLD_TOUR_FAVORITE_REGION]: 0 });
}

function getWorldTourVisibleCams(cams) {
    // The video-off toggle in the list panel is treated as a global
    // filter — it should also hide external-only cams from the bottom
    // rail and from the world-tour map markers, not just the panel list.
    const base = state.worldTourListExcludeExternal
        ? cams.filter(canPlayWorldTourInApp)
        : cams;
    if (state.worldTourRegion === WORLD_TOUR_FAVORITE_REGION) {
        const favorites = getWorldTourFavoriteIds();
        return base.filter(cam => favorites.has(String(cam.id)));
    }
    if (state.worldTourRegion === 'All') return base;
    return base.filter(cam => cam.region === state.worldTourRegion);
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
    const regions = [WORLD_TOUR_FAVORITE_REGION, ...WORLD_TOUR_REGIONS];

    return `
        <div class="world-tour-region-tabs" role="tablist" aria-label="대륙별 관광 라이브 필터">
            ${regions
                .filter(region => region === WORLD_TOUR_FAVORITE_REGION || counts[region] > 0)
                .map(region => `
                    <button
                        type="button"
                        class="world-tour-region-tab ${state.worldTourRegion === region ? 'active' : ''}"
                        data-world-region="${escapeWorldTourHtml(region)}"
                    >
                        <span class="world-tour-region-tab-label">
                            ${region === WORLD_TOUR_FAVORITE_REGION ? `<span class="world-tour-favorite-tab-icon active">${WORLD_TOUR_STAR_SVG}</span>` : ''}
                            <span>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</span>
                        </span>
                        <b>${counts[region]}</b>
                    </button>
                `).join('')}
        </div>
    `;
}

function renderWorldTourListToggle(cams) {
    return `
        <button
            type="button"
            class="world-tour-list-toggle ${state.worldTourListOpen ? 'active' : ''}"
            data-world-tour-list-toggle
            aria-label="세계 CCTV 리스트 열기"
            title="세계 CCTV 리스트"
        >
            ${WORLD_TOUR_LIST_SVG}
        </button>
    `;
}

function renderWorldTourRegionControls(cams) {
    return `
        <div class="world-tour-region-bar">
            ${renderWorldTourRegionTabs(cams)}
            ${renderWorldTourListToggle(cams)}
        </div>
    `;
}

function renderWorldTourCard(cam, selectedId) {
    const isActive = cam.id === selectedId;
    const regionColor = WORLD_TOUR_REGION_COLORS[cam.region] || '#86efac';
    const sourceLabel = getWorldTourSourceLabel(cam);
    const externalOnly = !canPlayWorldTourInApp(cam);
    const externalBadge = externalOnly
        ? `<span class="world-tour-external-badge" title="원본사이트에서만 재생 가능" aria-label="원본사이트에서만 재생 가능">${WORLD_TOUR_VIDEO_OFF_SVG}</span>`
        : '';

    return `
        <article class="world-tour-card ${isActive ? 'active' : ''}" data-id="${escapeWorldTourHtml(cam.id)}" tabindex="0" aria-label="${escapeWorldTourHtml(`${cam.title} 영상 선택`)}">
            <span class="world-tour-card-title-row">
                <span class="world-tour-card-title">${escapeWorldTourHtml(cam.title)}${externalBadge}</span>
                ${renderWorldTourFavoriteButton(cam, 'card')}
            </span>
            <span class="world-tour-card-sub">${escapeWorldTourHtml(cam.city)} · ${escapeWorldTourHtml(cam.country)}</span>
            <span class="world-tour-card-footer">
                <span class="world-tour-card-tag" style="--region-color:${regionColor}">${escapeWorldTourHtml(getWorldTourRegionLabel(cam.region))}</span>
                <span class="world-tour-source-tag ${canPlayWorldTourInApp(cam) ? 'playable' : 'external'}">${escapeWorldTourHtml(sourceLabel)}</span>
            </span>
        </article>
    `;
}

function renderWorldTourListRegionChips(cams) {
    const counts = getWorldTourRegionCounts(cams);
    const regions = [WORLD_TOUR_FAVORITE_REGION, ...WORLD_TOUR_REGIONS]
        .filter(region => region === WORLD_TOUR_FAVORITE_REGION || counts[region] > 0);

    return regions.map(region => `
        <button
            type="button"
            class="world-tour-list-chip ${state.worldTourListRegion === region ? 'active' : ''}"
            data-world-tour-list-region="${escapeWorldTourHtml(region)}"
        >
            ${region === WORLD_TOUR_FAVORITE_REGION ? `<span class="world-tour-favorite-tab-icon active">${WORLD_TOUR_STAR_SVG}</span>` : ''}
            <span>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</span>
            <b>${counts[region] || 0}</b>
        </button>
    `).join('');
}

function renderWorldTourListSelectOptions(entries, selectedValue, allLabel) {
    const options = [`<option value="All">${escapeWorldTourHtml(allLabel)}</option>`];
    entries.forEach(entry => {
        const value = Array.isArray(entry) ? entry[0] : entry.sourceType;
        const label = Array.isArray(entry) ? entry[0] : entry.label;
        const count = Array.isArray(entry) ? entry[1] : entry.count;
        options.push(`
            <option value="${escapeWorldTourHtml(value)}" ${selectedValue === value ? 'selected' : ''}>
                ${escapeWorldTourHtml(label)} (${count})
            </option>
        `);
    });
    return options.join('');
}

// Wraps every occurrence of `search` inside `text` with a <mark> element,
// returning HTML-safe output. The match is case-insensitive (we lowercase
// both haystack and needle). Use this anywhere we surface a field that
// might be why the row was matched, so users can see WHY their query hit.
function highlightWorldTourMatch(text, search) {
    const raw = text == null ? '' : String(text);
    if (!raw) return '';
    const needle = normalizeWorldTourText(search);
    if (!needle) return escapeWorldTourHtml(raw);

    const lower = raw.toLowerCase();
    const len = needle.length;
    const out = [];
    let cursor = 0;
    while (cursor < raw.length) {
        const idx = lower.indexOf(needle, cursor);
        if (idx < 0) {
            out.push(escapeWorldTourHtml(raw.slice(cursor)));
            break;
        }
        if (idx > cursor) out.push(escapeWorldTourHtml(raw.slice(cursor, idx)));
        out.push(`<mark class="world-tour-search-highlight">${escapeWorldTourHtml(raw.slice(idx, idx + len))}</mark>`);
        cursor = idx + len;
    }
    return out.join('');
}

function renderWorldTourListItems(items, selectedId) {
    if (!items.length) {
        return '<div class="world-tour-list-empty">조건에 맞는 세계 CCTV가 없습니다. 검색어나 필터를 줄여보세요.</div>';
    }

    const search = state.worldTourListSearch;

    return items.map(cam => {
        const isActive = cam.id === selectedId;
        const sourceLabel = getWorldTourSourceLabel(cam);
        const regionLabel = getWorldTourRegionLabel(cam.region);
        const externalOnly = !canPlayWorldTourInApp(cam);
        const externalBadge = externalOnly
            ? `<span class="world-tour-external-badge" title="원본사이트에서만 재생 가능" aria-label="원본사이트에서만 재생 가능">${WORLD_TOUR_VIDEO_OFF_SVG}</span>`
            : '';
        // Only render the subtitle row when a search is active and the
        // subtitle would actually help explain the match — otherwise we
        // keep list rows compact like before.
        const subtitle = cam.subtitle || '';
        const subtitleMatches = search
            && subtitle
            && normalizeWorldTourText(subtitle).includes(normalizeWorldTourText(search));
        const subtitleRow = subtitleMatches
            ? `<span class="world-tour-list-item-subtitle">${highlightWorldTourMatch(subtitle, search)}</span>`
            : '';
        return `
            <article class="world-tour-list-item ${isActive ? 'active' : ''}" data-world-tour-list-item="${escapeWorldTourHtml(cam.id)}" tabindex="0">
                ${renderWorldTourFavoriteButton(cam, 'list')}
                <div class="world-tour-list-item-main">
                    <strong class="world-tour-list-item-title">
                        <span class="world-tour-list-item-title-text">${highlightWorldTourMatch(cam.title, search)}</span>
                        ${externalBadge}
                    </strong>
                    <span>${highlightWorldTourMatch(cam.city, search)} · ${highlightWorldTourMatch(cam.country, search)}</span>
                    <em>${highlightWorldTourMatch(regionLabel, search)} · ${highlightWorldTourMatch(sourceLabel, search)}</em>
                    ${subtitleRow}
                </div>
                <div class="world-tour-list-item-actions">
                    <button type="button" data-world-tour-list-map="${escapeWorldTourHtml(cam.id)}">지도</button>
                    <button type="button" data-world-tour-list-video="${escapeWorldTourHtml(cam.id)}">영상</button>
                </div>
            </article>
        `;
    }).join('');
}

function renderWorldTourListPanel(cams, selected) {
    sanitizeWorldTourListFilters(cams);
    const filteredCams = getWorldTourListFilteredCams(cams);
    const countryOptions = renderWorldTourListSelectOptions(
        getWorldTourListCountries(cams),
        state.worldTourListCountry,
        '모든 국가'
    );
    const externalOnly = state.worldTourListExcludeExternal;

    return `
        <div class="world-tour-list-overlay" data-world-tour-list-overlay>
            <aside class="world-tour-list-panel" role="dialog" aria-modal="true" aria-label="세계 CCTV 리스트">
                <div class="world-tour-list-head">
                    <div>
                        <span>WORLD CCTV LIST</span>
                        <strong>세계 관광 라이브 검색</strong>
                    </div>
                    <button type="button" class="world-tour-list-close" data-world-tour-list-close aria-label="리스트 닫기">×</button>
                </div>
                <label class="world-tour-list-search">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/>
                    </svg>
                    <input
                        type="search"
                        data-world-tour-list-search
                        value="${escapeWorldTourHtml(state.worldTourListSearch)}"
                        placeholder="국가, 도시, 영상명 검색"
                        autocomplete="off"
                    >
                </label>
                <div class="world-tour-list-filter-group">
                    <div class="world-tour-list-chip-row" aria-label="대륙/즐겨찾기 필터">
                        ${renderWorldTourListRegionChips(cams)}
                    </div>
                    <div class="world-tour-list-select-row">
                        <select data-world-tour-list-country aria-label="국가 필터">${countryOptions}</select>
                        <button
                            type="button"
                            class="world-tour-list-external-toggle ${externalOnly ? 'active' : ''}"
                            data-world-tour-list-external-toggle
                            aria-pressed="${externalOnly}"
                            aria-label="${externalOnly ? '원본사이트 영상 포함' : '원본사이트 영상 제외'}"
                            title="${externalOnly ? '원본사이트 영상 제외중 — 클릭하면 포함' : '원본사이트로만 재생되는 영상을 제외'}"
                        >
                            ${WORLD_TOUR_VIDEO_OFF_SVG}
                            <span>원본만${externalOnly ? ' 숨김' : ' 보기'}</span>
                        </button>
                    </div>
                </div>
                <div class="world-tour-list-count" data-world-tour-list-count>
                    ${filteredCams.length}개 영상 · 선택 ${escapeWorldTourHtml(selected.title)}
                </div>
                <div class="world-tour-list-results" data-world-tour-list-results>
                    ${renderWorldTourListItems(filteredCams, selected.id)}
                </div>
            </aside>
        </div>
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
        ? `
            <a
                class="world-tour-open-btn"
                href="${escapeWorldTourHtml(selected.sourceUrl)}"
                target="_blank"
                rel="noopener"
                aria-label="원본 열기"
                title="원본 열기"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                    aria-hidden="true" focusable="false">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                    <path d="M5 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0" />
                    <path d="M9 10a3 3 0 1 0 6 0a3 3 0 1 0 -6 0" />
                    <path d="M8 16l-2.091 3.486a1 1 0 0 0 .857 1.514h10.468a1 1 0 0 0 .857 -1.514l-2.091 -3.486" />
                </svg>
            </a>
        `
        : '';
    const selectedIndex = Math.max(0, visibleCams.findIndex(cam => cam.id === selected.id));
    const nearbyCams = getWorldTourNearbyCams(selected, visibleCams, 2);
    const previousCam = nearbyCams[1] || (visibleCams.length
        ? visibleCams[(selectedIndex - 1 + visibleCams.length) % visibleCams.length]
        : null);
    const nextCam = nearbyCams[0] || (visibleCams.length
        ? visibleCams[(selectedIndex + 1) % visibleCams.length]
        : null);

    return `
        <section class="world-tour-bottom-menu" aria-label="세계 관광 라이브 선택 메뉴">
            <div class="world-tour-selected-summary">
                <span class="world-tour-kicker">${escapeWorldTourHtml(getWorldTourRegionLabel(selected.region))} live cam</span>
                <div class="world-tour-title-row">
                    <h3>${escapeWorldTourHtml(selected.title)}</h3>
                    ${renderWorldTourFavoriteButton(selected, 'summary')}
                    <div class="world-tour-title-nav" aria-label="인근 관광 라이브 이동">
                        <button
                            type="button"
                            class="world-tour-title-nav-btn"
                            data-world-tour-neighbor="${escapeWorldTourHtml(previousCam?.id || selected.id)}"
                            aria-label="이전 관광 라이브"
                        >${WORLD_TOUR_CHEVRON_LEFT_SVG}</button>
                        <button
                            type="button"
                            class="world-tour-title-nav-btn"
                            data-world-tour-neighbor="${escapeWorldTourHtml(nextCam?.id || selected.id)}"
                            aria-label="다음 관광 라이브"
                        >${WORLD_TOUR_CHEVRON_RIGHT_SVG}</button>
                    </div>
                </div>
                <p>${escapeWorldTourHtml(selected.subtitle || `${selected.city}, ${selected.country}`)}</p>
                ${renderWorldTourHashTags(selected)}
                <div class="world-tour-actions">
                    ${renderWorldTourModeSwitch()}
                    ${openLink}
                </div>
            </div>
            <div class="world-tour-bottom-main">
                ${renderWorldTourRegionControls(cams)}
                <div class="world-tour-card-rail" aria-label="선택 가능한 세계 관광 라이브">
                    ${visibleCams.length
                        ? visibleCams.map(cam => renderWorldTourCard(cam, selected.id)).join('')
                        : '<div class="world-tour-empty-favorites">아직 즐겨찾기한 세계 영상이 없습니다.</div>'}
                </div>
            </div>
        </section>
    `;
}

function renderWorldTourVideoHero(selected) {
    const embedUrl = getWorldTourEmbedUrl(selected);
    const sourceLabel = getWorldTourSourceLabel(selected);
    const isDirectVideo = isWorldTourHlsUrl(embedUrl) || isWorldTourDirectVideoUrl(embedUrl);
    const snapshotUrl = !embedUrl ? (selected.snapshotUrl || '') : '';

    let mediaHtml;
    if (embedUrl && isDirectVideo) {
        mediaHtml = `
            <div class="world-tour-video">
                <video
                    class="world-tour-direct-video"
                    data-world-tour-stream="${escapeWorldTourHtml(embedUrl)}"
                    data-world-tour-title="${escapeWorldTourHtml(selected.title)}"
                    autoplay muted playsinline controls
                ></video>
                <div class="world-tour-video-loading">영상을 불러오는 중...</div>
            </div>`;
    } else if (embedUrl) {
        mediaHtml = `
            <div class="world-tour-video">
                <iframe
                    src="${escapeWorldTourHtml(embedUrl)}"
                    title="${escapeWorldTourHtml(selected.title)}"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowfullscreen
                ></iframe>
            </div>`;
    } else if (snapshotUrl) {
        // In-app snapshot playback for sources without an embeddable player
        // (HK Traffic, USGS VolcView, Panomax, Roundshot). The image auto-
        // refreshes via initWorldTourSnapshotRefresh after the DOM mounts.
        const refreshMs = getWorldTourSnapshotRefreshMs(selected);
        mediaHtml = `
            <div class="world-tour-video world-tour-snapshot-hero">
                <img
                    class="world-tour-snapshot-img"
                    src="${escapeWorldTourHtml(snapshotUrl)}"
                    alt="${escapeWorldTourHtml(selected.title)} 실시간 스냅샷"
                    data-world-tour-snapshot="${escapeWorldTourHtml(snapshotUrl)}"
                    data-world-tour-snapshot-refresh="${refreshMs}"
                    loading="eager"
                    decoding="async"
                />
                <div class="world-tour-snapshot-overlay">
                    <span class="world-tour-snapshot-badge">${escapeWorldTourHtml(sourceLabel)} 실시간 스냅샷</span>
                    ${refreshMs > 0 ? `<span class="world-tour-snapshot-meta">${Math.round(refreshMs / 1000)}초마다 자동 새로고침</span>` : '<span class="world-tour-snapshot-meta">최신 캡처 이미지</span>'}
                </div>
            </div>`;
    } else {
        mediaHtml = `
            <div class="world-tour-video world-tour-external-preview">
                ${selected.thumbnailUrl ? `<img src="${escapeWorldTourHtml(selected.thumbnailUrl)}" alt="${escapeWorldTourHtml(selected.title)} preview" loading="lazy">` : ''}
                <div class="world-tour-external-copy">
                    <span>${escapeWorldTourHtml(sourceLabel)} 공식 플레이어</span>
                    <strong>이 영상은 원본 사이트에서 안정적으로 재생됩니다.</strong>
                    <a href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본에서 보기</a>
                </div>
            </div>`;
    }

    return `<section class="world-tour-hero">${mediaHtml}</section>`;
}

// Auto-refreshes the snapshot img every N ms. Adds a cache-busting query
// param so the browser doesn't serve a stale cached copy. Cleans up its
// interval when the element is removed.
let _worldTourSnapshotTimers = new WeakMap();
function initWorldTourSnapshotRefresh() {
    document.querySelectorAll('.world-tour-snapshot-img[data-world-tour-snapshot]').forEach(img => {
        // De-dupe — avoid stacking intervals when re-render happens.
        const prev = _worldTourSnapshotTimers.get(img);
        if (prev) {
            clearInterval(prev);
            _worldTourSnapshotTimers.delete(img);
        }
        const refreshMs = Number(img.dataset.worldTourSnapshotRefresh || 0);
        if (!refreshMs || refreshMs < 5000) return; // skip static-image sources
        const baseUrl = img.dataset.worldTourSnapshot;
        if (!baseUrl) return;
        const timer = setInterval(() => {
            if (!img.isConnected) {
                clearInterval(timer);
                _worldTourSnapshotTimers.delete(img);
                return;
            }
            if (document.hidden) return; // pause when tab not visible
            const sep = baseUrl.includes('?') ? '&' : '?';
            img.src = `${baseUrl}${sep}_=${Date.now()}`;
        }, refreshMs);
        _worldTourSnapshotTimers.set(img, timer);
    });
}

function renderWorldTourMapHero(selected, visibleCams) {
    return `
        <section class="world-tour-map-stage" aria-label="세계 관광 라이브 지도">
            <div class="world-tour-map-wrap">
                <div id="world-tour-map" class="world-tour-map" aria-label="${escapeWorldTourHtml(selected.title)} 주변 관광 라이브 지도">
                    <div class="world-tour-map-loading">OpenStreetMap 지도를 불러오는 중...</div>
                </div>
            </div>
        </section>
    `;
}

function createWorldTourMarkerPopup(cam) {
    const popup = document.createElement('div');
    popup.className = 'world-tour-marker-popup';
    popup.innerHTML = `
        <strong>${escapeWorldTourHtml(cam.title)}</strong>
        <span>${escapeWorldTourHtml(cam.city)} · ${escapeWorldTourHtml(cam.country)}</span>
        <button type="button" class="world-tour-marker-video-btn">영상보기</button>
    `;

    popup.querySelector('.world-tour-marker-video-btn')?.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        renderWorldTourCams(cam.id, { viewMode: 'video' });
    });

    return popup;
}

function enableHorizontalDragScroll(scroller, onScroll) {
    if (!scroller || scroller.dataset.dragScrollBound === 'true') return;
    scroller.dataset.dragScrollBound = 'true';

    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let startScrollLeft = 0;
    let didDrag = false;
    let suppressClick = false;
    const dragThreshold = 5;

    const finishDrag = event => {
        if (pointerId === null || event.pointerId !== pointerId) return;
        if (didDrag) {
            suppressClick = true;
            window.setTimeout(() => { suppressClick = false; }, 0);
        }
        scroller.classList.remove('is-dragging');
        try {
            scroller.releasePointerCapture?.(pointerId);
        } catch (error) {
            // Pointer capture can already be released by the browser.
        }
        pointerId = null;
        didDrag = false;
    };

    scroller.addEventListener('pointerdown', event => {
        if (event.button !== 0 || event.pointerType === 'touch') return;
        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        startScrollLeft = scroller.scrollLeft;
        didDrag = false;
    });

    scroller.addEventListener('pointermove', event => {
        if (pointerId === null || event.pointerId !== pointerId) return;
        const deltaX = event.clientX - startX;
        const deltaY = event.clientY - startY;
        if (!didDrag && Math.abs(deltaX) > dragThreshold && Math.abs(deltaX) >= Math.abs(deltaY)) {
            didDrag = true;
            scroller.classList.add('is-dragging');
            try {
                scroller.setPointerCapture?.(pointerId);
            } catch (error) {
                // Non-fatal: drag still works while the pointer stays inside.
            }
        }
        if (!didDrag) return;
        event.preventDefault();
        scroller.scrollLeft = startScrollLeft - deltaX;
        onScroll?.(scroller.scrollLeft);
    });

    scroller.addEventListener('pointerup', finishDrag);
    scroller.addEventListener('pointercancel', finishDrag);
    scroller.addEventListener('lostpointercapture', finishDrag);
    scroller.addEventListener('click', event => {
        if (!suppressClick) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);

    // Convert vertical mouse-wheel scroll into horizontal scroll so users on
    // a standard wheel mouse (without a trackpad) can also browse the chips.
    scroller.addEventListener('wheel', event => {
        if (event.deltaY === 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
        const maxScroll = scroller.scrollWidth - scroller.clientWidth;
        if (maxScroll <= 0) return;
        const current = scroller.scrollLeft;
        // Stop scroll bleed-through to the page only when we'll actually move.
        const headroom = event.deltaY > 0 ? maxScroll - current : current;
        if (headroom <= 0) return;
        event.preventDefault();
        scroller.scrollLeft = current + event.deltaY;
        onScroll?.(scroller.scrollLeft);
    }, { passive: false });
}

function cleanupWorldTourVideoPlayers(root = document) {
    root.querySelectorAll?.('.world-tour-direct-video').forEach(video => {
        if (video.hls) {
            video.hls.destroy();
            video.hls = null;
        }
        video.pause();
        video.removeAttribute('src');
        video.load();
    });
}

function initWorldTourVideoPlayback() {
    const video = document.querySelector('.world-tour-direct-video');
    if (!video) return;

    const streamUrl = video.dataset.worldTourStream;
    if (!streamUrl) return;

    const loading = video.parentElement?.querySelector('.world-tour-video-loading');
    const markReady = () => {
        video.classList.add('is-ready');
        loading?.classList.add('hidden');
    };
    const playSafely = () => video.play().then(markReady).catch(() => markReady());

    if (isWorldTourHlsUrl(streamUrl)) {
        if (window.Hls && window.Hls.isSupported()) {
            const hls = new window.Hls({
                enableWorker: true,
                lowLatencyMode: true,
                manifestLoadingTimeOut: 12000,
                levelLoadingTimeOut: 12000,
                fragLoadingTimeOut: 16000,
                manifestLoadingMaxRetry: 3,
                levelLoadingMaxRetry: 3,
                fragLoadingMaxRetry: 3
            });
            hls.on(window.Hls.Events.MANIFEST_PARSED, playSafely);
            hls.on(window.Hls.Events.ERROR, (event, data) => {
                if (!data?.fatal) return;
                loading?.classList.add('is-error');
                if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR && typeof hls.recoverMediaError === 'function') {
                    hls.recoverMediaError();
                    return;
                }
                hls.destroy();
            });
            hls.attachMedia(video);
            hls.loadSource(streamUrl);
            video.hls = hls;
            return;
        }

        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = streamUrl;
            video.addEventListener('loadedmetadata', playSafely, { once: true });
            return;
        }
    }

    video.src = streamUrl;
    video.addEventListener('loadedmetadata', playSafely, { once: true });
}

function bindWorldTourListPanel(root, cams, selected) {
    const overlay = root.querySelector('[data-world-tour-list-overlay]');
    const panel = root.querySelector('.world-tour-list-panel');
    if (!overlay || !panel) return;

    const shell = root.querySelector('.world-tour-shell');

    // Whenever the list panel is mounted, drop the overlay blur/dim and
    // hide the bottom menu so the user sees the live map/video on the
    // left while exploring results. The class disappears with the
    // panel on the next re-render.
    overlay.classList.add('is-searching');
    if (shell) shell.classList.add('is-searching');
    if (typeof worldTourLeafletMap !== 'undefined' && worldTourLeafletMap?.invalidateSize) {
        requestAnimationFrame(() => {
            try { worldTourLeafletMap.invalidateSize(false); } catch (e) { /* map gone */ }
        });
    }

    const rerenderWithList = (selectedId = state.selectedWorldTourId, extraOptions = {}) => {
        const cardRail = root.querySelector('.world-tour-card-rail');
        const regionTabs = root.querySelector('.world-tour-region-tabs');
        renderWorldTourCams(selectedId, {
            viewMode: state.worldTourViewMode,
            cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
            regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
            ...extraOptions
        });
    };

    const refreshResults = () => {
        const results = panel.querySelector('[data-world-tour-list-results]');
        const count = panel.querySelector('[data-world-tour-list-count]');
        const filtered = getWorldTourListFilteredCams(cams);
        if (count) {
            count.textContent = `${filtered.length}개 영상 · 선택 ${selected.title}`;
        }
        if (results) {
            results.innerHTML = renderWorldTourListItems(filtered, state.selectedWorldTourId);
        }
    };

    // Sync the active state of the region chips (Favorite / All / region)
    // without a full re-render — needed when search auto-switches to 'All'.
    const refreshRegionChips = () => {
        panel.querySelectorAll('[data-world-tour-list-region]').forEach(chip => {
            const region = chip.dataset.worldTourListRegion || 'All';
            chip.classList.toggle('active', region === state.worldTourListRegion);
        });
    };

    // Intentionally NOT closing the panel on overlay click — the overlay
    // covers the entire viewport, and the user wants the left side (map +
    // markers + card rail) to stay fully interactive while the right
    // panel is open. To dismiss the panel use the × close button in the
    // panel header (or the list-toggle button in the bottom menu).
    // Pointer-events: none on the overlay (set in CSS for is-searching)
    // means clicks pass through to the underlying map / cards anyway.

    const searchInput = panel.querySelector('[data-world-tour-list-search]');
    searchInput?.addEventListener('input', event => {
        state.worldTourListSearch = event.target.value;
        // Any active typing should force results to come from the full
        // dataset so users aren't accidentally filtered out by a region
        // tab they forgot was active. We don't full-rerender to avoid
        // losing the input focus / cursor position.
        if (state.worldTourListSearch && state.worldTourListRegion !== 'All') {
            state.worldTourListRegion = 'All';
            refreshRegionChips();
        }
        refreshResults();
    });

    panel.querySelector('[data-world-tour-list-country]')?.addEventListener('change', event => {
        state.worldTourListCountry = event.target.value;
        rerenderWithList();
    });

    panel.querySelector('[data-world-tour-list-external-toggle]')?.addEventListener('click', event => {
        event.preventDefault();
        state.worldTourListExcludeExternal = !state.worldTourListExcludeExternal;
        rerenderWithList();
    });

    panel.addEventListener('click', event => {
        const closeButton = event.target.closest('[data-world-tour-list-close]');
        if (closeButton) {
            state.worldTourListOpen = false;
            rerenderWithList();
            return;
        }

        const regionButton = event.target.closest('[data-world-tour-list-region]');
        if (regionButton) {
            state.worldTourListRegion = regionButton.dataset.worldTourListRegion || 'All';
            state.worldTourListCountry = 'All';
            state.worldTourListSource = 'All';
            // A region click is an explicit user action — clear any
            // active search so the user sees the new region's results.
            state.worldTourListSearch = '';
            rerenderWithList();
            return;
        }

        const favoriteButton = event.target.closest('.world-tour-favorite-btn');
        if (favoriteButton) {
            event.preventDefault();
            event.stopPropagation();
            toggleWorldTourFavorite(favoriteButton.dataset.worldTourFavorite);
            rerenderWithList();
            return;
        }

        const videoButton = event.target.closest('[data-world-tour-list-video]');
        if (videoButton) {
            renderWorldTourCams(videoButton.dataset.worldTourListVideo, { viewMode: 'video' });
            return;
        }

        const mapButton = event.target.closest('[data-world-tour-list-map]');
        if (mapButton) {
            renderWorldTourCams(mapButton.dataset.worldTourListMap, { viewMode: 'map' });
            return;
        }

        const item = event.target.closest('[data-world-tour-list-item]');
        if (item) {
            renderWorldTourCams(item.dataset.worldTourListItem, { viewMode: state.worldTourViewMode });
        }
    });

    panel.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const item = event.target.closest('[data-world-tour-list-item]');
        if (!item) return;
        event.preventDefault();
        renderWorldTourCams(item.dataset.worldTourListItem, { viewMode: state.worldTourViewMode });
    });
}

async function renderWorldTourCams(selectedId = state.selectedWorldTourId, options = {}) {
    const list = $('#weather-list');
    if (!list) return;
    cleanupWorldTourVideoPlayers(list);
    const previousCardRail = list.querySelector('.world-tour-card-rail');
    const previousRegionTabs = list.querySelector('.world-tour-region-tabs');
    const nextCardScrollLeft = Number.isFinite(Number(options.cardScrollLeft))
        ? Number(options.cardScrollLeft)
        : previousCardRail?.scrollLeft ?? state.worldTourCardScrollLeft ?? 0;
    const nextRegionScrollLeft = Number.isFinite(Number(options.regionScrollLeft))
        ? Number(options.regionScrollLeft)
        : previousRegionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft ?? 0;
    list.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">세계 관광 라이브를 불러오는 중...</div>';

    try {
        const cams = await loadWorldTourCams();
        if (!cams.length) {
            list.innerHTML = '<div style="padding:20px;">등록된 관광지 영상이 없습니다.</div>';
            return;
        }
        sanitizeWorldTourListFilters(cams);

        if (options.region && isWorldTourRegionAvailable(options.region)) {
            state.worldTourRegion = options.region;
        }
        if (options.viewMode) {
            state.worldTourViewMode = options.viewMode;
        }

        let visibleCams = getWorldTourVisibleCams(cams);
        if (!visibleCams.length && state.worldTourRegion !== WORLD_TOUR_FAVORITE_REGION) {
            state.worldTourRegion = 'All';
            visibleCams = state.worldTourListExcludeExternal
                ? cams.filter(canPlayWorldTourInApp)
                : cams;
            // If the exclude-external filter happens to wipe out the
            // entire dataset, fall back to the full list so the page
            // doesn't render empty.
            if (!visibleCams.length) visibleCams = cams;
        }

        const selectedFromVisible = visibleCams.find(cam => cam.id === selectedId);
        const selectedFromAll = cams.find(cam => cam.id === selectedId);
        const selected = selectedFromVisible || selectedFromAll || visibleCams[0] || cams[0];
        state.selectedWorldTourId = selected.id;
        destroyWorldTourMap();

        const isMapView = state.worldTourViewMode === 'map';
        list.innerHTML = `
            <div class="world-tour-shell ${isMapView ? 'world-tour-map-shell' : 'world-tour-video-shell'}">
                ${state.worldTourViewMode === 'map'
                    ? renderWorldTourMapHero(selected, visibleCams)
                    : renderWorldTourVideoHero(selected)}
                ${renderWorldTourBottomMenu(cams, visibleCams, selected)}
                ${state.worldTourListOpen ? renderWorldTourListPanel(cams, selected) : ''}
            </div>
        `;

        list.querySelector('[data-world-tour-list-toggle]')?.addEventListener('click', () => {
            state.worldTourListOpen = true;
            state.worldTourListRegion = state.worldTourRegion || 'All';
            const cardRail = list.querySelector('.world-tour-card-rail');
            const regionTabs = list.querySelector('.world-tour-region-tabs');
            renderWorldTourCams(state.selectedWorldTourId, {
                viewMode: state.worldTourViewMode,
                cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
            });
        });

        bindWorldTourListPanel(list, cams, selected);

        list.querySelectorAll('.world-tour-card').forEach(card => {
            const selectCard = () => {
                const cardRail = list.querySelector('.world-tour-card-rail');
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(card.dataset.id, {
                    viewMode: state.worldTourViewMode,
                    cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
                });
            };
            card.addEventListener('click', event => {
                if (event.target.closest('.world-tour-favorite-btn')) return;
                selectCard();
            });
            card.addEventListener('keydown', event => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                selectCard();
            });
        });
        list.querySelectorAll('.world-tour-favorite-btn').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                toggleWorldTourFavorite(button.dataset.worldTourFavorite);
                const cardRail = list.querySelector('.world-tour-card-rail');
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(state.selectedWorldTourId, {
                    viewMode: state.worldTourViewMode,
                    cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
                });
            });
        });
        list.querySelectorAll('.world-tour-title-nav-btn').forEach(button => {
            button.addEventListener('click', () => {
                const cardRail = list.querySelector('.world-tour-card-rail');
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(button.dataset.worldTourNeighbor, {
                    viewMode: state.worldTourViewMode,
                    cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
                });
            });
        });
        list.querySelectorAll('.world-tour-region-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const region = tab.dataset.worldRegion || 'All';
                const nextVisibleCams = region === WORLD_TOUR_FAVORITE_REGION
                    ? cams.filter(cam => isWorldTourFavorite(cam))
                    : region === 'All'
                        ? cams
                        : cams.filter(cam => cam.region === region);
                const nextSelected = nextVisibleCams.find(cam => cam.id === state.selectedWorldTourId)
                    || nextVisibleCams[0]
                    || cams.find(cam => cam.id === state.selectedWorldTourId)
                    || cams[0];
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(nextSelected.id, {
                    region,
                    viewMode: state.worldTourViewMode,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                    cardScrollLeft: 0
                });
            });
        });
        list.querySelectorAll('.world-tour-mode-option').forEach(button => {
            button.addEventListener('click', () => {
                const viewMode = button.dataset.worldTourView === 'map' ? 'map' : 'video';
                const cardRail = list.querySelector('.world-tour-card-rail');
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(state.selectedWorldTourId, {
                    viewMode,
                    cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
                });
            });
        });
        list.querySelectorAll('.world-tour-nearby-item').forEach(item => {
            item.addEventListener('click', () => renderWorldTourCams(item.dataset.id, { viewMode: 'map' }));
        });

        const cardRail = list.querySelector('.world-tour-card-rail');
        const regionTabs = list.querySelector('.world-tour-region-tabs');
        if (cardRail) {
            requestAnimationFrame(() => {
                cardRail.scrollLeft = nextCardScrollLeft;
                state.worldTourCardScrollLeft = cardRail.scrollLeft;
            });
            cardRail.addEventListener('scroll', () => {
                state.worldTourCardScrollLeft = cardRail.scrollLeft;
            }, { passive: true });
            enableHorizontalDragScroll(cardRail, scrollLeft => {
                state.worldTourCardScrollLeft = scrollLeft;
            });
        }
        if (regionTabs) {
            requestAnimationFrame(() => {
                regionTabs.scrollLeft = nextRegionScrollLeft;
                state.worldTourRegionScrollLeft = regionTabs.scrollLeft;
            });
            regionTabs.addEventListener('scroll', () => {
                state.worldTourRegionScrollLeft = regionTabs.scrollLeft;
            }, { passive: true });
            enableHorizontalDragScroll(regionTabs, scrollLeft => {
                state.worldTourRegionScrollLeft = scrollLeft;
            });
        }

        if (state.worldTourViewMode === 'map') {
            requestAnimationFrame(() => initWorldTourMap(selected, visibleCams));
        } else {
            requestAnimationFrame(() => {
                initWorldTourVideoPlayback();
                initWorldTourSnapshotRefresh();
            });
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

        // Tile choice: CartoDB Voyager — uses Latin (English) place names
        // worldwide, which is much more readable than OSM Standard (where
        // labels in CJK / Cyrillic / Arabic regions appear in the local script).
        // {r} adds @2x for HiDPI screens automatically.
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
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
                .bindPopup(createWorldTourMarkerPopup(cam), {
                    closeButton: false,
                    autoPan: true,
                    offset: [0, -6],
                    className: 'world-tour-leaflet-popup'
                })
                .on('mouseover', () => marker.openPopup())
                .on('click', () => marker.openPopup());

            worldTourLeafletMarkers.push(marker);

            if (isSelected) {
                worldTourLeafletMap.setView([lat, lng], Math.max(worldTourLeafletMap.getZoom(), state.worldTourRegion === 'All' ? 4 : 5), {
                    animate: false
                });
                setTimeout(() => marker.openPopup(), 120);
            }
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

    const parsedTitle = parseCctvLabel(cctv.name);
    const sourceMeta = getSourceMeta(cctv);
    const mainTitleHtml = parsedTitle.direction
        ? `<span class="video-title-main">${parsedTitle.main}<span class="video-title-direction"> (${parsedTitle.direction})</span></span>`
        : `<span class="video-title-main">${parsedTitle.main}</span>`;

    titleEl.innerHTML = `
        ${navHtml}
        <span class="video-title-block">
            ${mainTitleHtml}
            <span class="video-title-sub">
                <span class="source-dot" style="background:${sourceMeta.color}" aria-hidden="true"></span>
                <span class="video-title-source">${sourceMeta.label}</span>
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

    let favoriteBtn = $('#video-layer-favorite');
    if (!favoriteBtn) {
        const tempWrap = document.createElement('span');
        tempWrap.innerHTML = renderCctvFavoriteButton(displayCctv);
        favoriteBtn = tempWrap.firstElementChild;
        actionContainer.insertBefore(favoriteBtn, $('#video-layer-close'));
    } else {
        const active = isCctvFavorite(displayCctv);
        favoriteBtn.classList.toggle('active', active);
        favoriteBtn.setAttribute('aria-pressed', active ? 'true' : 'false');
        const title = active ? '즐겨찾기 해제' : '즐겨찾기 추가';
        favoriteBtn.title = title;
        favoriteBtn.setAttribute('aria-label', title);
        const svg = favoriteBtn.querySelector('svg');
        if (svg) svg.setAttribute('fill', active ? 'currentColor' : 'none');
    }
    favoriteBtn.onclick = (e) => {
        e.stopPropagation();
        const nowActive = toggleCctvFavorite(displayCctv);
        favoriteBtn.classList.toggle('active', nowActive);
        favoriteBtn.setAttribute('aria-pressed', nowActive ? 'true' : 'false');
        const t = nowActive ? '즐겨찾기 해제' : '즐겨찾기 추가';
        favoriteBtn.title = t;
        favoriteBtn.setAttribute('aria-label', t);
        const svg = favoriteBtn.querySelector('svg');
        if (svg) svg.setAttribute('fill', nowActive ? 'currentColor' : 'none');
    };

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
