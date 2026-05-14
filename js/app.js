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
const APP_BUILD_VERSION = '20260514-banner1';
const SERVICE_BANNER_VISIBLE_MS = 5000;
const NEAREST_RESULT_LIMIT = 100;
const MAP_MARKER_LIMIT = 50;
const PANEL_OPTION_LIMIT = 20;
const SEARCH_RESULT_LIMIT = 15;
const GEO_CELL_SIZE = 0.08;
const GEO_SEARCH_RING_LIMIT = 8;
const GEO_CANDIDATE_TARGET = 220;
const ORACLE_BASE = 'https://158.179.194.163.sslip.io';
const ORACLE_PROXY_BASE = `${ORACLE_BASE}/proxy`;
const JEJU_PROXY_BASE = 'https://158.179.194.163.sslip.io/jeju';
const URBAN_CONTEXT_PATTERN = /(시청|구청|군청|읍사무소|면사무소|동부출장소|행정복지|주민센터|사거리|삼거리|교차로|로터리|터미널|역|아파트|시장|학교|초교|초등|중학교|고교|병원|마트|상가|대로변|단지내|시내|중앙|읍내)/;
const OUTSKIRT_CONTEXT_PATTERN = /(고속|고속도로|서울양양선|수도권제|국도|IC|JC|TG|영업소|터널|램프|휴게소|졸음쉼터|분기점|진입로|외부|하이패스)/i;

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
    healthSnapshot: null,
    healthSnapshotStale: false,
    geoIndex: new Map(),
    markers: [], // Array to store Kakao map markers
    mapInitialized: false,
    searchMarker: null, // Reference to the red marker
    initialSelectionId: null,
    activeCctvId: null,
    serviceBannerTimer: null,
    serviceBannerDismissedKey: null
};

let map = null;
const SEARCH_MARKER_SRC = 'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png';
const YOUTUBE_MARKER_SRC = 'https://img.icons8.com/color/48/youtube-play.png';


// === DOM References (Cached) ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Initialization ===
document.addEventListener('DOMContentLoaded', async () => {
    console.log('CCTV Viewer 2.0 Initializing...');

    await Promise.all([loadCctvData(), loadHealthStatus()]);
    restoreInitialViewState();

    // Setup Event Listeners
    setupEventListeners();

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
});

// === Data Loading ===
async function loadCctvData() {
    try {
        const cacheBucket = Math.floor(Date.now() / CCTV_DATA_BUCKET_MS);
        const response = await fetch(`cctv_data.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        state.cctvData = await response.json();
        buildGeoIndex(state.cctvData);
        console.log(`Loaded ${state.cctvData.length} CCTV entries.`);
    } catch (error) {
        console.error('Failed to load CCTV data:', error);
        state.cctvData = [];
        state.cctvById = new Map();
        state.geoIndex = new Map();
    }
}

async function loadHealthStatus() {
    try {
        const cacheBucket = Math.floor(Date.now() / HEALTH_STATUS_BUCKET_MS);
        const response = await fetch(`data/status.json?v=${APP_BUILD_VERSION}&t=${cacheBucket}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const snapshot = await response.json();
        state.healthSnapshot = snapshot;
        state.regionHealth = state.healthSnapshot.regions || {};
        state.healthSnapshotStale = isStaleHealthTimestamp(snapshot.last_updated);
        if (state.healthSnapshotStale) {
            console.warn('Using stale health status snapshot:', snapshot.last_updated);
        }
    } catch (error) {
        console.warn('Failed to load live health status:', error);
        state.healthSnapshot = null;
        state.regionHealth = {};
        state.healthSnapshotStale = false;
    }
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

    // Map Initialization (Lazy)
    if (mode === 'map' && !state.mapInitialized) {
        initMap();
    } else if (mode === 'map' && map) {
        map.relayout();
        map.setCenter(new kakao.maps.LatLng(state.center.lat, state.center.lng));
    }

    syncUrlState();
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

function isRawIpStreamUrl(url) {
    return /^https?:\/\/\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?/i.test(url || '');
}

function isUnsupportedBrowserStream(cctv) {
    const url = cctv ? (cctv.directUrl || cctv.url || '') : '';
    const source = cctv ? (cctv.source || '') : '';
    const kind = getUrlParam(url, 'kind');
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
    if (prefix && REGION_LABELS[prefix]) return prefix;
    if (REGION_ALIASES[source]) return REGION_ALIASES[source];
    if (id.includes('_')) return id.split('_')[0];
    if (source) return source;
    return 'UNKNOWN';
}

function getRegionLabel(regionKey) {
    return REGION_LABELS[regionKey] || regionKey || '미분류';
}

function getCameraHealthMeta(cctv) {
    const playbackHealth = cctv && cctv.id ? state.cameraPlaybackHealth.get(cctv.id) : null;
    if (playbackHealth) {
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
            shortLabel: (usingFallback ? '대체 소스' : '최근 장애') + staleSuffix,
            longLabel: usingFallback ? `${getRegionLabel(regionKey)} 대체 소스 사용 중${staleSuffix}` : `${getRegionLabel(regionKey)} 최근 장애 감지${staleSuffix}`,
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

function getStreamQualityScore(cctv) {
    const url = cctv.directUrl || cctv.url || '';
    const source = cctv.source || '';
    let score = SOURCE_QUALITY_SCORES[source] || 0.72;

    if (cctv.backup_urls && cctv.backup_urls.length > 0) {
        score += 0.04;
    }

    if (cctv.urlType === 'daejeon_mp4_dynamic') {
        score += 0.08;
    }
    if (url.includes('.m3u8') || url.includes('/kb?cctvip=') || url.includes('workers.dev')) {
        score += 0.06;
    }
    if (source === 'JEJU' || url.includes('158.179.194.163.sslip.io/jeju')) {
        score += 0.08;
    }
    if (url.includes('openDataCctvStream.jsp') || url.includes('utic.go.kr/jsp')) {
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

    return score;
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

    if (state.serviceBannerTimer) {
        clearTimeout(state.serviceBannerTimer);
        state.serviceBannerTimer = null;
    }

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

    const entries = currentRegionKeys
        .map(regionKey => [regionKey, state.healthSnapshot.regions[regionKey]])
        .filter(([, value]) => value);
    const downRegions = entries.filter(([, value]) => value.status === 'DOWN');
    const degradedRegions = entries.filter(([, value]) => value.status === 'DEGRADED');
    const lastUpdatedText = formatRelativeTime(state.healthSnapshot.last_updated);

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
        body = `${downRegions.slice(0, 3).map(([regionKey]) => getRegionLabel(regionKey)).join(', ')} 연결이 불안정합니다. 대체 소스를 우선 추천합니다.`;
    } else if (degradedRegions.length > 0) {
        tone = 'warn';
        title = '현재 지역 점검 중';
        body = `${degradedRegions.slice(0, 3).map(([regionKey]) => getRegionLabel(regionKey)).join(', ')} 품질이 일시적으로 흔들릴 수 있습니다.`;
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
            <div class="service-status-time">${lastUpdatedText}</div>
        </div>
    `;
    const closeButton = banner.querySelector('.service-status-close');
    if (closeButton) {
        closeButton.addEventListener('click', () => {
            state.serviceBannerDismissedKey = bannerKey;
            hideServiceStatusBanner();
        }, { once: true });
    }

    state.serviceBannerTimer = setTimeout(() => {
        hideServiceStatusBanner();
    }, SERVICE_BANNER_VISIBLE_MS);
}

function hideServiceStatusBanner(clearContent = false) {
    const banner = $('#service-status-banner');
    if (!banner) return;

    if (state.serviceBannerTimer) {
        clearTimeout(state.serviceBannerTimer);
        state.serviceBannerTimer = null;
    }

    banner.classList.add('hidden');
    if (clearContent) banner.innerHTML = '';
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
    const label = cctv?.name || fallbackLabel || 'CCTV 선택';
    trigger.innerHTML = '';

    const name = document.createElement('span');
    name.className = 'cctv-select-name';
    name.textContent = label;

    trigger.append(name);
    trigger.title = `${label} · ${health.longLabel} · ${formatRelativeTime(health.lastUpdated)}`;
    trigger.setAttribute('aria-label', `${label}, ${health.shortLabel}`);
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

function setPlaybackHealth(cctv, nextHealth) {
    if (!cctv || !cctv.id) return;
    state.cameraPlaybackHealth.set(cctv.id, {
        status: nextHealth.status,
        shortLabel: nextHealth.shortLabel,
        longLabel: nextHealth.longLabel,
        tone: nextHealth.tone,
        penalty: nextHealth.penalty,
        lastUpdated: new Date().toISOString()
    });
}

function handlePanelVideoHealthEvent(event) {
    const video = event.target;
    if (!video || video.tagName !== 'VIDEO') return;

    const panel = video.closest('.video-panel');
    const cctv = getPanelCctv(panel);
    if (!panel || !cctv) return;

    if (event.type === 'error') {
        setPlaybackHealth(cctv, {
            status: 'PLAYBACK_ERROR',
            shortLabel: '재생 불안정',
            longLabel: `${cctv.name || 'CCTV'} 영상 재생 오류 감지`,
            tone: 'danger',
            penalty: 6
        });
    } else {
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

    [600, 1600, 3200, 5200].forEach(delay => {
        setTimeout(() => {
            if (!video.parentElement || !panel.contains(video)) return;
            if (video.readyState >= 2 && video.videoWidth > 0) {
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
            const priorityScore = distance + health.penalty + ((1 - streamQuality) * 6) + roadContextPriority - backupBonus;

            return {
                ...cctv,
                distance,
                _health: health,
                _streamQuality: streamQuality,
                _roadContextPriority: roadContextPriority,
                _priorityScore: priorityScore
            };
        })
        .sort((a, b) => a._priorityScore - b._priorityScore || a.distance - b.distance);

    const supported = ranked.filter(cctv => cctv._health.status !== 'UNSUPPORTED');
    const unsupported = ranked.filter(cctv => cctv._health.status === 'UNSUPPORTED');
    const ordered = supported.length >= 4
        ? supported.concat(unsupported)
        : ranked;

    state.nearestCctvs = ordered.slice(0, NEAREST_RESULT_LIMIT);
}

function renderVideoGrid() {
    const grid = $('#video-grid');
    const panels = grid.querySelectorAll('.video-panel');

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

        if (cctv) {
            // Create and insert video element
            const video = createVideoElement(cctv);
            wrapper.appendChild(video);

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

function populateSelectOptions(panel, currentIndex) {
    const optionsContainer = panel.querySelector('.cctv-select-options');
    if (!optionsContainer) return;

    // Clear existing options
    optionsContainer.innerHTML = '';

    // Add up to 20 recommended CCTVs as options
    const cctvList = state.nearestCctvs.slice(0, PANEL_OPTION_LIMIT);
    cctvList.forEach((cctv, i) => {
        const option = document.createElement('div');
        option.className = 'cctv-option' + (i === currentIndex ? ' selected' : '');
        const health = getCameraHealthMeta(cctv);
        const name = document.createElement('span');
        name.className = 'cctv-option-name';
        name.textContent = cctv.name || `CCTV ${i + 1}`;
        option.append(name);
        option.dataset.cctvIndex = i;
        option.title = `${health.longLabel} · ${formatRelativeTime(health.lastUpdated)}`;
        option.setAttribute('aria-label', `${name.textContent}, ${health.shortLabel}`);
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
    let url, type, selectedSource;

    if (sourceIndex === 0) {
        url = cctv.directUrl || cctv.url;
        type = 'main';
        selectedSource = cctv.source || '';

    } else {
        const backup = cctv.backup_urls && cctv.backup_urls[sourceIndex - 1];
        if (backup) {
            url = backup.url;
            type = `backup-${sourceIndex}`;
            selectedSource = backup.source || cctv.source || '';
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
    const sourceFallbackId = cctv.original_id || ((cctv.id || '').includes('_') ? cctv.id.split('_').pop() : cctv.id);
    const selectedCctvIp = getUrlParam(url, 'cctvip') || sourceFallbackId;
    const selectedKind = getUrlParam(url, 'kind');
    const genericProxyBase = isRawIpStreamUrl(url)
        ? 'https://158.179.194.163.sslip.io/proxy'
        : 'https://cctv-proxy.pyw213.workers.dev/proxy';

    if (selectedSource === 'KBS' && selectedCctvIp) {
        url = `https://cctv-proxy.pyw213.workers.dev/kb?cctvip=${encodeURIComponent(selectedCctvIp)}&_t=${Date.now()}`;
    } else if (shouldProxy) {
        if (selectedSource === 'TRENDWORLD' || selectedSource === 'NOWJEJU' || selectedSource === 'HRFCO') {
            url = `${genericProxyBase}?url=${encodeURIComponent(url)}&_t=${Date.now()}`;
        } else if (selectedSource === 'JEJU') {
            const jejuStreamId = cctv.original_id || getUrlParam(url, 'id') || sourceFallbackId;
            url = `${JEJU_PROXY_BASE}?id=${encodeURIComponent(jejuStreamId)}&_t=${Date.now()}`;
        } else if (selectedSource === 'UTIC' && selectedCctvIp && ['EE', 'EEE', 'KB'].includes(selectedKind)) {
            url = `https://cctv-proxy.pyw213.workers.dev/kb?cctvip=${encodeURIComponent(selectedCctvIp)}&_t=${Date.now()}`;
        }
    }

    const is43 = cctv.aspectRatio === '4:3';

    // Helper to trigger failover
    const triggerFailover = (wrapper) => {
        console.log(`[Failover] Stream failed for ${cctv.name} (Index ${sourceIndex}). Trying next...`);
        handleStreamFailover(wrapper, cctv, sourceIndex + 1);
    };

    // Handle Daejeon dynamic MP4 URLs (client-side generation to bypass oracle block)
    if (cctv.urlType === 'daejeon_mp4_dynamic' && sourceIndex === 0) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';

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
            let streamId = cctv.original_id || cctv.id.replace('DAEJEON_', '');
            if (streamId.startsWith('CCTV')) {
                const num = streamId.substring(4);
                streamId = `CTV${num.padStart(4, '0')}`;
            }
            return `https://tportal.daejeon.go.kr:37084/01/media/${streamId}/${streamId}_${timestamp}.000.mp4`;
        };

        const url2min = getDaejeonUrl(2);
        video.src = url2min;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        video.onerror = () => {
            if (video.src === url2min) {
                console.log(`Daejeon ${cctv.name}: -2m failed, trying -3m`);
                video.src = getDaejeonUrl(3);
            } else {
                // If -3m also fails, try Failover
                triggerFailover(video.parentElement);
            }
        };
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
                fragLoadingTimeOut: 30000,
                manifestLoadingTimeOut: 15000,
                manifestLoadingMaxRetry: 8,
                manifestLoadingRetryDelay: 700,
                manifestLoadingMaxRetryTimeout: 8000,
                levelLoadingMaxRetry: 8,
                levelLoadingRetryDelay: 700,
                levelLoadingMaxRetryTimeout: 8000,
                fragLoadingMaxRetry: 8,
                fragLoadingRetryDelay: 700,
                fragLoadingMaxRetryTimeout: 8000,
            });
            hls.loadSource(jejuUrl);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function () {
                video.play().catch(() => {});
            });

            let recoveryAttempts = 0;
            hls.on(Hls.Events.ERROR, function (event, data) {
                if (!data.fatal) return;

                const isNetworkError = data.type === Hls.ErrorTypes.NETWORK_ERROR;
                const isMediaError = data.type === Hls.ErrorTypes.MEDIA_ERROR;
                if ((isNetworkError || isMediaError) && recoveryAttempts < 12) {
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

            video.hls = hls;
        } else {
            video.src = jejuUrl;
            video.onerror = () => triggerFailover(video.parentElement);
        }
        return video;
    }

    // EE kind cameras OR /kb proxy URLs: play full-size MP4 video via Korean server
    // directUrl in cctv_data.json is pre-set to /kb?cctvip=X for EE cameras
    if (url.includes('/kb?cctvip=') || (url.includes('kind=EE') && url.includes('cctvip='))) {
        let kbUrl = url;
        if (!url.includes('/kb?cctvip=')) {
            const cctvipMatch = url.match(/[?&]cctvip=(\d+)/);
            if (cctvipMatch) {
                kbUrl = `https://cctv-proxy.pyw213.workers.dev/kb?cctvip=${cctvipMatch[1]}`;
            }
        }
        if (!kbUrl.includes('_t=')) kbUrl += `&_t=${Date.now()}`;
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.src = kbUrl;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        video.onerror = () => triggerFailover(video.parentElement);
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
    const isGits = cctv.source === 'GITS' && sourceIndex === 0;

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

    // GITS: async real-time token fetch via CF Worker /gits endpoint
    if (isGits && cctv.original_id) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;object-position:center center;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        (async () => {
            try {
                const resp = await fetch(`https://cctv-proxy.pyw213.workers.dev/gits?id=${cctv.original_id}&_t=${Date.now()}`);
                if (!resp.ok) throw new Error('gits ' + resp.status);
                const streamUrl = (await resp.text()).trim();
                if (!streamUrl.startsWith('http')) throw new Error('bad url: ' + streamUrl.slice(0, 50));
                if (!video.parentElement) return;
                video.src = streamUrl;
                video.onerror = () => { if (video.parentElement) triggerFailover(video.parentElement); };
            } catch(e) {
                console.error('[GITS] Token fetch failed:', e);
                if (video.parentElement) triggerFailover(video.parentElement);
            }
        })();

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
        return video;
    }

    // UTIC Portal - play natively via CF Worker
    // Z3 kind: look up fresh stream URL from z3_cache.json (updated hourly by GitHub Actions)
    // Other kinds: extract real m3u8 URL via /utic endpoint, fall back to iframe
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
                            if (video.parentElement) fallbackToIframe(video.parentElement);
                        }
                    });
                    video.hls = hls;
                } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
                    video.src = streamUrl;
                    video.onerror = () => { if (video.parentElement) fallbackToIframe(video.parentElement); };
                } else {
                    if (video.parentElement) fallbackToIframe(video.parentElement);
                }
            } catch(e) {
                console.error('[UTIC] Stream resolve failed:', e);
                if (video.parentElement) fallbackToIframe(video.parentElement);
            }

            function fallbackToIframe(wrapper) {
                if (isZ3) {
                    triggerFailover(wrapper);
                    return;
                }
                wrapper.innerHTML = '';
                const iframe = document.createElement('iframe');
                iframe.src = url;
                iframe.className = 'utic-iframe';
                iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;';
                iframe.allow = 'autoplay; fullscreen';
                iframe.scrolling = 'no';
                iframe.setAttribute('allowfullscreen', '');
                wrapper.appendChild(iframe);
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

        const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
            capLevelToPlayerSize: true,
            maxBufferLength: 30,
            maxMaxBufferLength: 60,
            fragLoadingTimeOut: 30000,
            manifestLoadingTimeOut: 15000,
            manifestLoadingMaxRetry: 8,
            manifestLoadingRetryDelay: 700,
            manifestLoadingMaxRetryTimeout: 8000,
            levelLoadingMaxRetry: 8,
            levelLoadingRetryDelay: 700,
            levelLoadingMaxRetryTimeout: 8000,
            fragLoadingMaxRetry: 8,
            fragLoadingRetryDelay: 700,
            fragLoadingMaxRetryTimeout: 8000,
            maxBufferSize: 30 * 1000 * 1000,
        });

        hls.loadSource(url);
        hls.attachMedia(video);
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
            const shouldFailFast = selectedSource === 'NOWJEJU' && statusCode >= 400;
            const isJejuHls = selectedSource === 'JEJU';
            const isRecoverable = data.type === Hls.ErrorTypes.NETWORK_ERROR || data.type === Hls.ErrorTypes.MEDIA_ERROR;

            if (isJejuHls && data.fatal && isRecoverable && recoveryAttempts < 12) {
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

        video.hls = hls;
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

    return video;
}

function ensureDynamicBackups(cctv) {
    if (!cctv || cctv._dynamicFallbacksAdded) return;
    if (!['NOWJEJU', 'TRENDWORLD'].includes(cctv.source)) return;
    if (!Number.isFinite(Number(cctv.lat)) || !Number.isFinite(Number(cctv.lng))) return;

    const backupUrls = Array.isArray(cctv.backup_urls) ? cctv.backup_urls : [];
    const knownUrls = new Set([cctv.url, ...backupUrls.map(item => item && item.url)].filter(Boolean));
    const preferredSources = ['JEJU', 'GITS', 'UTIC'];

    const nearbyBackups = state.cctvs
        .filter(item => item && item.id !== cctv.id && preferredSources.includes(item.source))
        .map(item => ({
            item,
            distance: getDistance(cctv.lat, cctv.lng, item.lat, item.lng)
        }))
        .filter(({ item, distance }) => Number.isFinite(distance) && distance <= 5 && item.url && !knownUrls.has(item.url))
        .sort((a, b) => {
            const sourceDelta = preferredSources.indexOf(a.item.source) - preferredSources.indexOf(b.item.source);
            return sourceDelta || a.distance - b.distance;
        })
        .slice(0, 3)
        .map(({ item }) => ({
            source: item.source,
            url: item.url,
            name: item.name
        }));

    if (nearbyBackups.length > 0) {
        cctv.backup_urls = backupUrls.concat(nearbyBackups);
    } else {
        cctv.backup_urls = backupUrls;
    }
    cctv._dynamicFallbacksAdded = true;
}

function handleStreamFailover(wrapper, cctv, nextIndex) {
    if (!wrapper) return;
    ensureDynamicBackups(cctv);
    const backupCount = Array.isArray(cctv.backup_urls) ? cctv.backup_urls.length : 0;
    const isRetryingPrimary = nextIndex === 0;

    // Cleanup existing content
    cleanupVideo(wrapper);

    if (isRetryingPrimary || nextIndex <= backupCount) {
        const indicator = document.createElement('div');
        indicator.className = 'video-loading-indicator';
        indicator.innerHTML = isRetryingPrimary
            ? '<strong>영상을 다시 불러오는 중...</strong><span>잠시만 기다려 주세요.</span>'
            : `<strong>대체 영상으로 전환 중...</strong><span>${nextIndex}/${backupCount}번째 보조 소스를 시도합니다.</span>`;
        wrapper.appendChild(indicator);

        setTimeout(() => {
            if (wrapper.contains(indicator)) {
                wrapper.removeChild(indicator);
            }
            const newVideo = createVideoElement(cctv, isRetryingPrimary ? 0 : nextIndex);
            wrapper.appendChild(newVideo);
            scheduleVideoHealthProbe(wrapper.closest('.video-panel'), cctv, newVideo);
        }, isRetryingPrimary ? 160 : 180);
    } else {
        const errPh = createErrorPlaceholder({
            message: '지금은 연결이 불안정합니다',
            detail: '잠시 후 다시 시도하거나, 문제가 계속되면 바로 제보할 수 있습니다.',
            retryLabel: '다시 시도',
            retryFn: () => {
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

        const markerOptions = {
            position: new kakao.maps.LatLng(lat, lng),
            map: map,
            title: `${cctv.name} · ${health.shortLabel}`
        };

        // Custom Icon for YouTube
        if (cctv.source === 'YOUTUBE') {
            const imageSize = new kakao.maps.Size(32, 32);
            const imageOption = { offset: new kakao.maps.Point(16, 16) }; // Center
            markerOptions.image = new kakao.maps.MarkerImage(YOUTUBE_MARKER_SRC, imageSize, imageOption);
        }

        const marker = new kakao.maps.Marker(markerOptions);
        if (health.status === 'UNSUPPORTED' || (health.status === 'DOWN' && health.tone === 'danger')) {
            marker.setOpacity(0.65);
        } else if (health.status === 'DEGRADED' || health.tone === 'warn') {
            marker.setOpacity(0.82);
        }

        kakao.maps.event.addListener(marker, 'click', () => {
            openVideoLayer(cctv);
        });

        state.markers.push(marker);
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
        // Close weather
        layer.classList.remove('active');
        btn.classList.remove('active');
        $('#dim-overlay').classList.remove('active');
    } else {
        // Close search first
        $('#search-results').classList.remove('active');

        // Open weather
        layer.classList.add('active');
        btn.classList.add('active');
        $('#dim-overlay').classList.add('active');

        $('#weather-title').innerHTML = `<span style="color: var(--accent)">${state.keyword}</span> 주간 날씨`;
        fetchWeather();
    }
}

function closeWeather() {
    $('#weather-layer').classList.remove('active');
    $('#weather-btn').classList.remove('active');
    $('#dim-overlay').classList.remove('active');
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
    if (video.tagName === 'VIDEO') video.controls = true;

    frame.appendChild(video);

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
    $('#weather-layer').classList.remove('active');
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
