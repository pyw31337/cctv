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
    mapInitialized: false,
    searchMarker: null // Reference to the red marker
};

let map = null;
const SEARCH_MARKER_SRC = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';


// === DOM References (Cached) ===
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// === Initialization ===
document.addEventListener('DOMContentLoaded', async () => {
    console.log('CCTV Viewer 2.0 Initializing...');

    // Load Data
    await loadCctvData();

    // Restore last searched location from history
    const history = getSearchHistory();
    if (history.length > 0 && history[0].lat && history[0].lng) {
        state.center = { lat: history[0].lat, lng: history[0].lng };
        state.keyword = history[0].name || '서울역';
        $('#search-input').value = state.keyword;
    }

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
    $('#weather-btn').addEventListener('click', toggleWeather);
    $('#weather-close').addEventListener('click', closeWeather);

    // Video Layer
    $('#video-layer-close').addEventListener('click', closeVideoLayer);
    $('#video-layer').addEventListener('click', (e) => {
        if (e.target.id === 'video-layer') closeVideoLayer();
    });

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

    // Kakao Local Search (supports 초성)
    const ps = new kakao.maps.services.Places();
    ps.keywordSearch(query, (data, status) => {
        const resultsEl = $('#search-results');

        if (status === kakao.maps.services.Status.OK && data.length > 0) {
            // Search results only - no history/bookmarks
            resultsEl.innerHTML = data.slice(0, 10).map(place => `
                <div class="search-result-item" data-lat="${place.y}" data-lng="${place.x}" data-name="${place.place_name}" data-address="${place.address_name || ''}">
                    <div class="search-result-info">
                        <div class="search-result-name">${place.place_name}</div>
                        <div class="search-result-address">${place.address_name || ''}</div>
                    </div>
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
        const resultsEl = $('#search-results');

        if (status === kakao.maps.services.Status.OK && data.length > 0) {
            if (data.length === 1) {
                // Only 1 result - select it directly
                const place = data[0];
                selectPlace(place.y, place.x, place.place_name, place.address_name);
            } else {
                // Multiple results - show them for user to choose
                resultsEl.innerHTML = data.slice(0, 10).map(place => `
                    <div class="search-result-item" data-lat="${place.y}" data-lng="${place.x}" data-name="${place.place_name}" data-address="${place.address_name || ''}">
                        <div class="search-result-info">
                            <div class="search-result-name">${place.place_name}</div>
                            <div class="search-result-address">${place.address_name || ''}</div>
                        </div>
                    </div>
                `).join('');
                resultsEl.classList.add('active');
                $('#dim-overlay').classList.add('active');
            }
        } else {
            resultsEl.innerHTML = '<div class="search-empty">검색 결과가 없습니다</div>';
            resultsEl.classList.add('active');
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
        const moveLatLon = new kakao.maps.LatLng(lat, lng);
        map.setCenter(moveLatLon);
    }

    // Update Search Marker (Red Pin)
    updateSearchMarker(lat, lng);
}

// === CCTV Logic ===
function updateNearestCctvs() {
    const { lat, lng } = state.center;

    state.nearestCctvs = state.cctvData
        .filter(cctv => {
            const url = cctv.url || '';
            // Filter out broken CCTVs:
            // - kind=EE: Gyeonggi local (UTIC bug + API blocked)
            // - kind=K: Jeju local (Server load error pages)
            if (url.includes('kind=EE') || url.includes('kind=K')) {
                return false;
            }
            return true;
        })
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

            // Update dropdown trigger text
            const trigger = panel.querySelector('.cctv-select-trigger');
            if (trigger) {
                trigger.textContent = cctv.name || `CCTV ${index + 1}`;
            }

            // Populate dropdown options (up to 20 nearby CCTVs)
            populateSelectOptions(panel, index);
        } else {
            // Show placeholder
            const ph = document.createElement('div');
            ph.className = 'video-placeholder';
            ph.textContent = 'No CCTV';
            wrapper.appendChild(ph);
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

    // Add up to 20 nearest CCTVs as options
    const cctvList = state.nearestCctvs.slice(0, 20);
    cctvList.forEach((cctv, i) => {
        const option = document.createElement('div');
        option.className = 'cctv-option' + (i === currentIndex ? ' selected' : '');
        option.textContent = cctv.name || `CCTV ${i + 1}`;
        option.dataset.cctvIndex = i;
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

    // Update trigger text
    const trigger = panel.querySelector('.cctv-select-trigger');
    if (trigger) {
        trigger.textContent = cctv.name || `CCTV ${cctvIndex + 1}`;
    }

    // Update selected option
    const options = panel.querySelectorAll('.cctv-option');
    options.forEach((opt, i) => {
        opt.classList.toggle('selected', i === cctvIndex);
    });
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
}

function createVideoElement(cctv) {
    const url = cctv.url;
    const isHls = url.includes('.m3u8');
    const isUtic = url.includes('utic.go.kr') || url.includes('openDataCctvStream');
    const isSecureStream = url.includes('cctvsec.ktict.co.kr');

    // UTIC Portal URLs - use iframe (kind=EE CCTVs are filtered out in updateNearestCctvs)
    if (isUtic) {
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;object-fit:cover;';
        iframe.allow = 'autoplay; fullscreen';
        iframe.scrolling = 'no';
        iframe.setAttribute('allowfullscreen', '');
        return iframe;
    }

    // HLS streams (.m3u8 or ktict) - use HLS.js
    if ((isHls || isSecureStream) && Hls.isSupported()) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        video.preload = 'metadata';

        const hls = new Hls({
            enableWorker: true,
            lowLatencyMode: true,
            capLevelToPlayerSize: true,
            maxBufferLength: 5,
            maxBufferSize: 3 * 1000 * 1000,
            backBufferLength: 0,
            startLevel: 0,
            manifestLoadingTimeOut: 5000,
        });
        hls.loadSource(url);
        hls.attachMedia(video);

        hls.on(Hls.Events.ERROR, function (event, data) {
            if (data.fatal) {
                switch (data.type) {
                    case Hls.ErrorTypes.NETWORK_ERROR:
                        hls.startLoad();
                        break;
                    case Hls.ErrorTypes.MEDIA_ERROR:
                        hls.recoverMediaError();
                        break;
                    default:
                        hls.destroy();
                        break;
                }
            }
        });

        video.hls = hls;
        return video;
    }

    // Safari native HLS
    if (isHls) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        video.src = url;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        return video;
    }

    // Fallback: iframe for any other URL type
    const iframe = document.createElement('iframe');
    iframe.src = url;
    iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;object-fit:cover;';
    iframe.allow = 'autoplay; fullscreen';
    iframe.scrolling = 'no';
    iframe.setAttribute('allowfullscreen', '');
    return iframe;
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
            `https://api.open-meteo.com/v1/forecast?latitude=${state.center.lat}&longitude=${state.center.lng}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto`
        );
        const data = await response.json();

        const days = ['일', '월', '화', '수', '목', '금', '토'];

        list.innerHTML = data.daily.time.slice(0, 7).map((time, i) => {
            const date = new Date(time);
            const dayName = i === 0 ? '오늘' : days[date.getDay()];
            const dateStr = `${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
            const icon = getWeatherIcon(data.daily.weathercode[i]);
            const max = Math.round(data.daily.temperature_2m_max[i]);
            const min = Math.round(data.daily.temperature_2m_min[i]);

            return `
                <div class="weather-item">
                    <div class="weather-day">${dayName} <span class="weather-date">${dateStr}</span></div>
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

    // Cleanup previous video
    cleanupVideo(frame);

    $('#video-layer-title').textContent = cctv.name;
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
        });
    }

    layer.classList.add('active');
}

function closeVideoLayer() {
    const layer = $('#video-layer');
    const frame = $('#video-frame');

    cleanupVideo(frame);
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
        let currentX = 50, currentY = 50; // Object position percentages

        const getVideoElement = () => panel.querySelector('video, iframe');

        const onStart = (e) => {
            if (!panel.classList.contains('expanded')) return;
            isDragging = true;
            panel.classList.add('dragging');
            const touch = e.touches ? e.touches[0] : e;
            startX = touch.clientX;
            startY = touch.clientY;
        };

        const onMove = (e) => {
            if (!isDragging) return;
            e.preventDefault();
            const touch = e.touches ? e.touches[0] : e;
            const deltaX = (touch.clientX - startX) * 0.15; // Sensitivity
            const deltaY = (touch.clientY - startY) * 0.15;
            
            currentX = Math.max(0, Math.min(100, currentX - deltaX));
            currentY = Math.max(0, Math.min(100, currentY - deltaY));
            
            const video = getVideoElement();
            if (video) {
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
