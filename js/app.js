// Main Application Logic

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Video Observer (Auto Pause/Play)
    if ('IntersectionObserver' in window) {
        videoObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const video = entry.target;
                if (!entry.isIntersecting) {
                    if (!video.paused) video.pause();
                } else {
                    if (video.hls) video.hls.startLoad();
                    // Attempt autoplay if needed
                    video.play().catch(() => { });
                }
            });
        }, { threshold: 0.1 });
    }

    // 2. Load Data & Init
    loadCCTVData().then(() => {
        initByUrlParams();
    });

    // 3. Init UI Components
    initCenterResizer();
    initWeatherFeature();
    initSearchEvents();

    // Tab Init
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
});

// === Tab Logic ===
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll(`.tab-btn[data-tab="${tabId}"]`).forEach(btn => btn.classList.add('active'));

    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    // Map Tab Special Handling
    if (tabId === 'map') {
        document.getElementById('map-tab').classList.add('active');
        if (!mapInitialized) {
            // Tiny delay to ensure visibility before init
            setTimeout(() => {
                initMap();
                mapInitialized = true;
            }, 50);
        } else {
            setTimeout(() => {
                if (map) {
                    map.relayout();
                    map.setCenter(new kakao.maps.LatLng(currentLat, currentLng));
                }
            }, 50);
        }
    } else {
        document.getElementById('video-tab').classList.add('active');
    }
}

// === Search Events ===
function initSearchEvents() {
    const vInput = document.getElementById('video-keyword');
    if (vInput) {
        vInput.addEventListener('focus', () => {
            renderHistoryAndBookmarks(); // Show history/bookmarks
            document.querySelector('.dim-overlay').classList.add('active');
            document.querySelector('.floating-search-container').classList.add('keyboard-active');
        });

        // Hide on blur (delayed to allow clicks on items)
        /* 
        vInput.addEventListener('blur', () => {
             setTimeout(() => {
                 // Only hide if result wasn't clicked
             }, 200);
        });
        */
    }

    // Dim Overlay Click
    document.querySelector('.dim-overlay').addEventListener('click', () => {
        document.getElementById('video-search-results').classList.remove('active');
        document.querySelector('.dim-overlay').classList.remove('active');
        document.querySelector('.floating-search-container').classList.remove('keyboard-active');
        document.getElementById('video-keyword').blur();
    });

    // Clear Button
    document.getElementById('video-clear-btn').addEventListener('click', () => {
        document.getElementById('video-keyword').value = '';
        renderHistoryAndBookmarks(); // Show history again
        document.getElementById('video-keyword').focus();
    });
}

// === Weather Feature ===
function initWeatherFeature() {
    const weatherBtn = document.getElementById('weather-btn');
    const weatherClose = document.getElementById('weather-close');
    const weatherLayer = document.getElementById('weather-layer');

    if (weatherBtn) {
        weatherBtn.addEventListener('click', async () => {
            if (weatherLayer) weatherLayer.classList.add('active');
            const title = document.getElementById('weather-title');
            if (title) title.textContent = `${currentKeyword} 주간 날씨`;
            await fetchAndRenderWeather(currentLat, currentLng);
        });
    }

    if (weatherClose) {
        weatherClose.addEventListener('click', () => {
            if (weatherLayer) weatherLayer.classList.remove('active');
        });
    }

    if (weatherLayer) {
        weatherLayer.addEventListener('click', (e) => {
            if (e.target === weatherLayer) weatherLayer.classList.remove('active');
        });
    }
}

async function fetchAndRenderWeather(lat, lng) {
    const weatherListEl = document.getElementById('weather-list');
    if (!weatherListEl) return;
    weatherListEl.innerHTML = '<div style="padding:24px;color:var(--text-sub);">날씨 불러오는 중...</div>';

    try {
        const res = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto`);
        const data = await res.json();

        if (!data.daily) throw new Error('No Data');

        const daily = data.daily;
        let html = '';
        const days = ['일', '월', '화', '수', '목', '금', '토'];

        for (let i = 0; i < 7 && i < daily.time.length; i++) {
            const date = new Date(daily.time[i]);
            const dayName = i === 0 ? '오늘' : days[date.getDay()];
            const code = daily.weathercode[i];
            const max = Math.round(daily.temperature_2m_max[i]);
            const min = Math.round(daily.temperature_2m_min[i]);
            const icon = getWeatherIcon(code);

            html += `
                <div class="weather-item">
                    <div class="weather-day">${dayName}</div>
                    <div class="weather-icon-display">${icon}</div>
                    <div class="weather-temp">${Math.round((max + min) / 2)}°</div>
                    <div class="weather-temp-range">${min}° / ${max}°</div>
                </div>
            `;
        }
        weatherListEl.innerHTML = html;

    } catch (e) {
        console.error(e);
        weatherListEl.innerHTML = '<div style="padding:20px;">날씨 정보를 불러오는데 실패했습니다.</div>';
    }
}

function getWeatherIcon(code) {
    if (code === 0) return '☀️';
    if (code >= 1 && code <= 3) return '⛅';
    if (code === 45 || code === 48) return '🌫️';
    if (code >= 51 && code <= 67) return '🌧️';
    if (code >= 71 && code <= 77) return '🌨️';
    if (code >= 80 && code <= 82) return '🌦️';
    if (code >= 95) return '⚡';
    return '☁️';
}

// === Location Selection Logic ===
async function selectPlace(place) {
    currentKeyword = place.place_name;
    currentLat = parseFloat(place.y);
    currentLng = parseFloat(place.x);

    // Save history handled by caller usually, but to be safe:
    saveSearchTerm(place);

    // Update UI
    document.getElementById('video-keyword').value = currentKeyword;

    // Close Search
    document.getElementById('video-search-results').classList.remove('active');
    document.querySelector('.dim-overlay').classList.remove('active');
    document.querySelector('.floating-search-container').classList.remove('keyboard-active');

    // Filter Logic
    if (map) {
        map.setCenter(new kakao.maps.LatLng(currentLat, currentLng));
        refreshMapData();
    } else {
        filterGridByLocation(currentLat, currentLng);
    }
}

function filterGridByLocation(lat, lng) {
    // Find nearest CCTVs
    const list = allCCTVData.map(c => ({
        ...c,
        dist: getDistance(lat, lng, c.lat, c.lng)
    })).sort((a, b) => a.dist - b.dist).slice(0, 100);

    currentCctvList = list;
    populateVideoSelects(list);
    const statusEl = document.getElementById('video-status');
    if (statusEl) statusEl.textContent = `"${currentKeyword}" 주변 CCTV ${list.length}개`;
}

// Globals
let map;
let mapInitialized = false;
let currentLat = 37.5559; // Seoul Station
let currentLng = 126.9723;
let currentKeyword = '서울역';
let allCCTVData = [];
let currentCctvList = [];
let videoObserver;

// ...

function initByUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const searchParam = params.get('search');
    if (searchParam) {
        document.getElementById('video-keyword').value = searchParam;
        handleSearch(searchParam, 'video', true).then(place => {
            if (place) selectPlace(place);
        });
    } else {
        // Default: Seoul Station
        currentKeyword = '서울역';
        document.getElementById('video-keyword').value = '서울역';
        // Need to fetch coords for Seoul Station if not hardcoded, 
        // but easier to just search it initially or use hardcoded coords above.
        // We set currentLat/Lng above.
        filterGridByLocation(currentLat, currentLng);
    }
}

// === Grid Resizer (Full Logic) ===
function initCenterResizer() {
    const grid = document.querySelector('.grid-container');
    const handle = document.getElementById('resizer');
    if (!grid || !handle) return;

    let col1 = 1, col2 = 1, row1 = 1, row2 = 1;

    function applyGrid() {
        grid.style.gridTemplateColumns = `${col1}fr ${col2}fr`;
        grid.style.gridTemplateRows = `${row1}fr ${row2}fr`;

        // Update handle position
        // Assuming equal initial weights, we can just center it visually or calc true pos.
        // But with fr units, css grid handles resizing. 
        // We just need to ensure handle follows the center.
        // Actually, 'resizer' is absolute centered. 
        // If we change grid rows/cols, we need to move handle?
        // Yes, if top-left gets bigger, center moves right-down.
        const totalW = col1 + col2;
        const totalH = row1 + row2;
        handle.style.left = `${(col1 / totalW) * 100}%`;
        handle.style.top = `${(row1 / totalH) * 100}%`;
    }

    let dragging = false;
    let startX, startY;

    const onStart = (x, y) => {
        dragging = true;
        startX = x;
        startY = y;
        grid.classList.add('resizing');
    };

    const onMove = (x, y) => {
        if (!dragging) return;
        const rect = grid.getBoundingClientRect();

        // Calculate delta percentage
        const dx = (x - startX) / rect.width * 2; // Factor 2 for sensitivity
        const dy = (y - startY) / rect.height * 2;

        col1 = Math.max(0.2, Math.min(1.8, col1 + dx));
        col2 = Math.max(0.2, Math.min(1.8, col2 - dx));
        row1 = Math.max(0.2, Math.min(1.8, row1 + dy));
        row2 = Math.max(0.2, Math.min(1.8, row2 - dy));

        applyGrid();
        startX = x;
        startY = y;
    };

    const onEnd = () => {
        dragging = false;
        grid.classList.remove('resizing');
    };

    // Mouse
    handle.addEventListener('mousedown', e => { e.preventDefault(); onStart(e.clientX, e.clientY); });
    window.addEventListener('mousemove', e => onMove(e.clientX, e.clientY));
    window.addEventListener('mouseup', onEnd);

    // Touch
    handle.addEventListener('touchstart', e => { e.preventDefault(); onStart(e.touches[0].clientX, e.touches[0].clientY); }, { passive: false });
    window.addEventListener('touchmove', e => { if (dragging) e.preventDefault(); onMove(e.touches[0].clientX, e.touches[0].clientY); }, { passive: false });
    window.addEventListener('touchend', onEnd);
}

// === Video Layer / Popups ===
function openVideoLayer(cctvData) {
    const layer = document.getElementById('video-layer');
    const title = document.getElementById('video-layer-title');
    const frame = document.getElementById('video-frame');

    title.textContent = cctvData.name;
    frame.innerHTML = '';

    const isHLS = cctvData.url.includes('.m3u8') || cctvData.url.includes('cctvsec.ktict.co.kr');

    // Check Mixed Content
    if (window.location.protocol === 'https:' && cctvData.url.startsWith('http:')) {
        frame.innerHTML = `
            <div style="color:white;text-align:center;padding:20px;">
                <p>보안 연결 문제로 재생할 수 없습니다.</p>
                <button onclick="window.open('${cctvData.url}', '_blank', 'width=600,height=480')">새 창에서 보기</button>
            </div>
         `;
    } else {
        const player = createCCTVPlayer(cctvData.url, isHLS);
        if (player.nodeName === 'VIDEO') player.style.objectFit = 'contain';
        frame.appendChild(player);
    }

    layer.classList.add('active');
}

document.getElementById('video-layer-close') && document.getElementById('video-layer-close').addEventListener('click', () => {
    document.getElementById('video-layer').classList.remove('active');
    document.getElementById('video-frame').innerHTML = '';
});
