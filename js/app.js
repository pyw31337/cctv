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
    markers: [], // Array to store Kakao map markers
    mapInitialized: false,
    searchMarker: null // Reference to the red marker
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
        const response = await fetch('cctv_data.json?t=' + Date.now());
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
        resultsEl.innerHTML = data.slice(0, 15).map(place => {
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
    renderVideoGrid();
    renderMapMarkers(); // Update markers on map

    // Update Map if Active
    if (map) {
        const moveLatLon = new kakao.maps.LatLng(lat, lng);
        map.setCenter(moveLatLon);
    }

    // Update Search Marker (Red Pin)
    updateSearchMarker(lat, lng);
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

    // Update layout for UTIC scaling
    setTimeout(updateUticLayout, 350); // Small delay for transition
}

function createVideoElement(cctv, sourceIndex = 0) {
    // Determine URL based on sourceIndex
    // Index 0 = Main URL, Index 1+ = Backup URLs
    let url, type;

    if (sourceIndex === 0) {
        url = cctv.directUrl || cctv.url;
        type = 'main';

        // Regional Proxy logic: Handle HTTP, CORS, and SSL issues for specific sources
        // Already proxied in data might happen, so we check first
        if (!url.includes('158.179.194.163.sslip.io')) {
            if (cctv.source === 'TRENDWORLD' || cctv.source === 'NOWJEJU' ||
                cctv.source === 'JEJU' || cctv.source === 'HRFCO' || cctv.source === 'GITS') {

                if (cctv.source === 'JEJU') {
                    // Use the standardized /jeju endpoint
                    url = `https://158.179.194.163.sslip.io/jeju?id=${cctv.original_id || cctv.id}&_t=${Date.now()}`;
                } else if (cctv.source === 'GITS') {
                    // Proxy GITS with specific Referer to bypass access restrictions
                    url = `https://158.179.194.163.sslip.io/proxy?url=${encodeURIComponent(url)}&referer=https://gits.gg.go.kr/&_t=${Date.now()}`;
                } else {
                    // Use general proxy for others (NOWJEJU, HRFCO, etc.)
                    url = `https://158.179.194.163.sslip.io/proxy?url=${encodeURIComponent(url)}&_t=${Date.now()}`;
                }
            }
        }
    } else {
        const backup = cctv.backup_urls && cctv.backup_urls[sourceIndex - 1];
        if (backup) {
            url = backup.url;
            type = `backup-${sourceIndex}`;
        } else {
            console.warn(`No backup source found at index ${sourceIndex}`);
            return createErrorPlaceholder('All Sources Failed');
        }
    }

    const is43 = cctv.aspectRatio === '4:3';

    // Default to 'cover' to fill the screen (premium look), 
    // but UTIC/4:3 sources can be toggled or handled specifically
    const defaultObjectFit = is43 ? 'contain' : 'cover';

    // Helper to trigger failover
    const triggerFailover = (wrapper) => {
        console.log(`[Failover] Stream failed for ${cctv.name} (Index ${sourceIndex}). Trying next...`);
        handleStreamFailover(wrapper, cctv, sourceIndex + 1);
    };

    // Handle Daejeon dynamic MP4 URLs (client-side generation to bypass oracle block)
    if (cctv.urlType === 'daejeon_mp4_dynamic' && sourceIndex === 0) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
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
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
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
            });
            hls.loadSource(jejuUrl);
            hls.attachMedia(video);

            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data.fatal) {
                    triggerFailover(video.parentElement);
                }
            });

            video.hls = hls;
        } else {
            video.src = jejuUrl;
            video.onerror = () => triggerFailover(video.parentElement);
        }
        return video;
    }

    const isHls = url.includes('.m3u8');
    const isMp4 = url.includes('.mp4');
    const isUtic = url.includes('utic.go.kr') || url.includes('openDataCctvStream');
    const isItsEmbed = url.includes('its.gn.go.kr/popup') || url.includes('gangneung_player.html') || url.includes('hrfco.go.kr');
    const isSecureStream = url.includes('cctvsec.ktict.co.kr');
    const isProxy = url.includes('cctv-proxy-hoon-001.fly.dev');
    const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
    const isGits = url.includes('gitsview.gg.go.kr');

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
            iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;object-fit:cover;';
            iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
            iframe.allowFullscreen = true;
            return iframe;
        }
    }

    // GITS / MP4 / Native
    if (isGits || isMp4) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        if (is43) video.dataset.aspectRatio = '4:3';
        video.src = url;
        video.muted = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');

        video.onerror = () => triggerFailover(video.parentElement);
        return video;
    }

    // UTIC Portal / ITS Popup URLs - iframe
    // iframe error handling is limited (cannot detect 404 inside iframe easily).
    // We assume if it's UTIC JSP it "works" or shows an error image.
    // But if we have backups, we might want to skip UTIC? 
    // For now, keep as is.
    if (isUtic || isItsEmbed) {
        const iframe = document.createElement('iframe');
        iframe.src = url;
        iframe.className = 'utic-iframe';
        iframe.style.cssText = 'width:100%;height:100%;border:none;display:block;object-fit:cover;';
        iframe.allow = 'autoplay; fullscreen';
        iframe.scrolling = 'no';
        iframe.setAttribute('allowfullscreen', '');
        if (is43) iframe.dataset.aspectRatio = '4:3';
        return iframe;
    }

    // HLS streams (Hls.js)
    if ((isHls || isSecureStream || isProxy) && Hls.isSupported()) {
        const video = document.createElement('video');
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
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
            maxBufferSize: 3 * 1000 * 1000,
        });

        hls.loadSource(url);
        hls.attachMedia(video);

        hls.on(Hls.Events.ERROR, function (event, data) {
            if (data.fatal) {
                // If fatal error, try failover
                // Need to ensure we don't loop infinitely if all fail
                hls.destroy();
                triggerFailover(video.parentElement);
            }
        });

        video.hls = hls;
        return video;
    }

    // Native HLS (Safari)
    const video = document.createElement('video');
    video.style.cssText = 'width:100%;height:100%;object-fit:cover;';
    if (is43) video.dataset.aspectRatio = '4:3';
    video.src = url;
    video.muted = true;
    video.autoplay = true;
    video.playsInline = true;

    video.onerror = () => triggerFailover(video.parentElement);

    return video;
}

function handleStreamFailover(wrapper, cctv, nextIndex) {
    if (!wrapper) return;

    // Cleanup existing content
    cleanupVideo(wrapper);

    // Check if we have backups
    if (cctv.backup_urls && nextIndex <= cctv.backup_urls.length) {
        // Show lightweight loading/switching indicator
        const indicator = document.createElement('div');
        indicator.className = 'video-loading-indicator';
        indicator.textContent = `Switching to backup source (${nextIndex}/${cctv.backup_urls.length})...`;
        indicator.style.cssText = 'position:absolute;top:0;left:0;width:100%;background:rgba(0,0,0,0.5);color:white;font-size:12px;padding:5px;z-index:10;';
        wrapper.appendChild(indicator);

        setTimeout(() => {
            if (wrapper.contains(indicator)) wrapper.removeChild(indicator);
            const newVideo = createVideoElement(cctv, nextIndex);
            wrapper.appendChild(newVideo);
        }, 500); // Small delay to visualize switch
    } else {
        // No more backups - Show improved error placeholder with retry
        const errPh = createErrorPlaceholder('Unavailable', () => {
            handleStreamFailover(wrapper, cctv, 0); // Reset and retry from index 0
        });
        wrapper.appendChild(errPh);
    }
}

function createErrorPlaceholder(msg, retryFn) {
    const ph = document.createElement('div');
    ph.className = 'video-placeholder error';
    ph.style.cssText = 'display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; background:#0f172a; color:#94a3b8; font-size:14px; gap:16px;';
    
    let html = `<span style="font-weight:500;">⚠️ ${msg}</span>`;
    if (retryFn) {
        html += `<button class="retry-btn" style="background:var(--accent); color:var(--bg-primary); border:none; padding:12px 24px; border-radius:var(--radius-md); font-size:16px; font-weight:700; cursor:pointer; box-shadow:0 4px 15px rgba(34, 197, 94, 0.3); transition: transform 0.2s;">재시도</button>`;
    }
    ph.innerHTML = html;

    if (retryFn) {
        const btn = ph.querySelector('.retry-btn');
        btn.onclick = (e) => {
            e.stopPropagation();
            btn.style.transform = 'scale(0.95)';
            setTimeout(() => {
                btn.style.transform = '';
                retryFn();
            }, 100);
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
        renderMapMarkers();
        // Also update video grid so it stays in sync when switching back
        renderVideoGrid();
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

    // Render new markers (max 50)
    state.nearestCctvs.slice(0, 50).forEach(cctv => {
        let lat = cctv.lat;
        let lng = cctv.lng;

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
            title: cctv.name
        };

        // Custom Icon for YouTube
        if (cctv.source === 'YOUTUBE') {
            const imageSize = new kakao.maps.Size(32, 32);
            const imageOption = { offset: new kakao.maps.Point(16, 16) }; // Center
            markerOptions.image = new kakao.maps.MarkerImage(YOUTUBE_MARKER_SRC, imageSize, imageOption);
        }

        const marker = new kakao.maps.Marker(markerOptions);

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

    titleEl.innerHTML = `${navHtml} ${cctv.name}`;

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
    setTimeout(updateUticLayout, 350); // Initial check
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
