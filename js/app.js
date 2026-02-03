/**
 * CCTV Viewer 2.0 - Main Application Logic
 * Clean Rewrite: State-Driven, Event Delegation
 */

// === State ===
const state = {
    mode: 'video', // 'video' | 'map'
    center: { lat: 37.5559, lng: 126.9723 }, // Seoul Station
    keyword: '서울역',
    cctvData: [],
    nearestCctvs: [],
    mapInitialized: false
};

let map = null;

// === DOM References (Cached) ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Initialization ===
document.addEventListener('DOMContentLoaded', async () => {
    console.log('CCTV Viewer 2.0 Initializing...');

    // Load Data
    await loadCctvData();

    // Setup Event Listeners
    setupEventListeners();

    // Initial State
    updateNearestCctvs();
    renderVideoGrid();
    updateSegmentIndicator();

    console.log('Initialization Complete.');
});

// === Data Loading ===
async function loadCctvData() {
    try {
        const response = await fetch('cctv_data.json');
        state.cctvData = await response.json();
        console.log(`Loaded ${state.cctvData.length} CCTV entries.`);
    } catch (error) {
        console.error('Failed to load CCTV data:', error);
        state.cctvData = [];
    }
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
        if (e.key === 'Enter') handleSearchSubmit();
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
    $('#weather-btn').addEventListener('click', openWeather);
    $('#weather-close').addEventListener('click', closeWeather);

    // Video Layer
    $('#video-layer-close').addEventListener('click', closeVideoLayer);
    $('#video-layer').addEventListener('click', (e) => {
        if (e.target.id === 'video-layer') closeVideoLayer();
    });

    // Search Results Click
    $('#search-results').addEventListener('click', (e) => {
        const item = e.target.closest('.search-result-item');
        if (item) selectSearchResult(item);
    });
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
    const resultsEl = $('#search-results');
    const history = getSearchHistory();

    if (history.length === 0) {
        resultsEl.innerHTML = '<div class="search-empty">최근 검색 기록이 없습니다</div>';
    } else {
        resultsEl.innerHTML = history.map(item => `
            <div class="search-result-item" data-lat="${item.lat}" data-lng="${item.lng}" data-name="${item.name}">
                <div class="search-result-name">${item.name}</div>
                <div class="search-result-address">${item.address || ''}</div>
            </div>
        `).join('');
    }

    resultsEl.classList.add('active');
    $('#dim-overlay').classList.add('active');
}

async function handleSearchInput(e) {
    const query = e.target.value.trim();
    if (query.length < 2) {
        showSearchHistory();
        return;
    }

    // Kakao Local Search
    const ps = new kakao.maps.services.Places();
    ps.keywordSearch(query, (data, status) => {
        const resultsEl = $('#search-results');

        if (status === kakao.maps.services.Status.OK) {
            resultsEl.innerHTML = data.slice(0, 10).map(place => `
                <div class="search-result-item" data-lat="${place.y}" data-lng="${place.x}" data-name="${place.place_name}">
                    <div class="search-result-name">${place.place_name}</div>
                    <div class="search-result-address">${place.address_name || ''}</div>
                </div>
            `).join('');
        } else {
            resultsEl.innerHTML = '<div class="search-empty">검색 결과가 없습니다</div>';
        }

        resultsEl.classList.add('active');
    });
}

function handleSearchSubmit() {
    const query = $('#search-input').value.trim();
    if (!query) return;

    const ps = new kakao.maps.services.Places();
    ps.keywordSearch(query, (data, status) => {
        if (status === kakao.maps.services.Status.OK && data.length > 0) {
            const place = data[0];
            selectPlace(place.y, place.x, place.place_name, place.address_name);
        }
    });
}

function selectSearchResult(item) {
    const lat = parseFloat(item.dataset.lat);
    const lng = parseFloat(item.dataset.lng);
    const name = item.dataset.name;

    selectPlace(lat, lng, name, '');
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
    renderVideoGrid();

    // Update Map if Active
    if (map) {
        map.setCenter(new kakao.maps.LatLng(lat, lng));
    }
}

// === CCTV Logic ===
function updateNearestCctvs() {
    const { lat, lng } = state.center;

    state.nearestCctvs = state.cctvData
        .map(cctv => ({
            ...cctv,
            distance: getDistance(lat, lng, cctv.lat, cctv.lng)
        }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 100);
}

function renderVideoGrid() {
    const grid = $('#video-grid');
    const panels = grid.querySelectorAll('.video-panel');

    panels.forEach((panel, index) => {
        const cctv = state.nearestCctvs[index];

        if (cctv) {
            const video = createVideoElement(cctv);
            panel.innerHTML = '';
            panel.appendChild(video);
            panel.dataset.cctvId = cctv.id;
        } else {
            panel.innerHTML = '<div class="video-placeholder">No CCTV</div>';
        }
    });
}

function createVideoElement(cctv) {
    const isHls = cctv.url.includes('.m3u8');

    if (isHls && Hls.isSupported()) {
        const video = document.createElement('video');
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.loop = true;

        const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true
        });
        hls.loadSource(cctv.url);
        hls.attachMedia(video);

        return video;
    } else {
        const video = document.createElement('video');
        video.src = cctv.url;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.loop = true;

        return video;
    }
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

    // Add Markers for nearest CCTVs
    renderMapMarkers();
}

function renderMapMarkers() {
    if (!map) return;

    state.nearestCctvs.slice(0, 50).forEach(cctv => {
        const marker = new kakao.maps.Marker({
            position: new kakao.maps.LatLng(cctv.lat, cctv.lng),
            map: map
        });

        kakao.maps.event.addListener(marker, 'click', () => {
            openVideoLayer(cctv);
        });
    });
}

// === Weather ===
function openWeather() {
    const layer = $('#weather-layer');
    layer.classList.add('active');
    $('#dim-overlay').classList.add('active');

    $('#weather-title').textContent = `${state.keyword} 주간 날씨`;
    fetchWeather();
}

function closeWeather() {
    $('#weather-layer').classList.remove('active');
    $('#dim-overlay').classList.remove('active');
}

async function fetchWeather() {
    const list = $('#weather-list');
    list.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">로딩 중...</div>';

    try {
        const response = await fetch(
            `https://api.open-meteo.com/v1/forecast?latitude=${state.center.lat}&longitude=${state.center.lng}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto`
        );
        const data = await response.json();

        const days = ['일', '월', '화', '수', '목', '금', '토'];

        list.innerHTML = data.daily.time.slice(0, 7).map((time, i) => {
            const date = new Date(time);
            const dayName = i === 0 ? '오늘' : days[date.getDay()];
            const icon = getWeatherIcon(data.daily.weathercode[i]);
            const max = Math.round(data.daily.temperature_2m_max[i]);
            const min = Math.round(data.daily.temperature_2m_min[i]);

            return `
                <div class="weather-item">
                    <div class="weather-day">${dayName}</div>
                    <div class="weather-icon">${icon}</div>
                    <div class="weather-temp">${Math.round((max + min) / 2)}°</div>
                    <div class="weather-range">${min}° / ${max}°</div>
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

// === Video Layer ===
function openVideoLayer(cctv) {
    const layer = $('#video-layer');
    const frame = $('#video-frame');

    $('#video-layer-title').textContent = cctv.name;
    frame.innerHTML = '';

    const video = createVideoElement(cctv);
    video.controls = true;
    frame.appendChild(video);

    layer.classList.add('active');
}

function closeVideoLayer() {
    const layer = $('#video-layer');
    const frame = $('#video-frame');

    frame.innerHTML = '';
    layer.classList.remove('active');
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
