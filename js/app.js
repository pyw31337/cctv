// Main Application Logic

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Observer
    if ('IntersectionObserver' in window) {
        videoObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const video = entry.target;
                if (!entry.isIntersecting) {
                    video.pause();
                } else {
                    if (video.hls) video.hls.startLoad();
                    // Optional: Auto-resume? video.play(); 
                    // Better to let user play or attributes handle it
                }
            });
        }, { threshold: 0.1 });
    }

    // 2. Load Data
    loadCCTVData().then(() => {
        // Startup Logic
        initByUrlParams();
    });

    // 3. Resizer Init
    initCenterResizer();
});


// Tab Switching
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.tab-btn[data-tab="${tabId}"]`).classList.add('active');

    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabId}-tab`).classList.add('active');

    if (tabId === 'map') {
        if (!mapInitialized) {
            initMap();
            mapInitialized = true;
        } else {
            setTimeout(() => {
                if (map) {
                    map.relayout();
                    map.setCenter(new kakao.maps.LatLng(currentLat, currentLng));
                }
            }, 50);
        }
    }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// Location Selection Logic
async function selectPlace(place) {
    currentKeyword = place.place_name;
    currentLat = parseFloat(place.y);
    currentLng = parseFloat(place.x);

    // Save history
    saveSearchTerm({
        name: currentKeyword,
        address: place.address_name,
        lat: currentLat,
        lng: currentLng
    });

    // Update UI
    document.getElementById('video-keyword').value = currentKeyword;
    document.getElementById('map-keyword').value = currentKeyword;

    // Close Search
    document.getElementById('video-search-results').classList.remove('active');
    document.querySelector('.dim-overlay').classList.remove('active');
    document.body.classList.remove('search-active');

    // Trigger Update
    // 1. Filter Data (Distance based)
    // Simple filter by distance for Grid View immediately
    // Or just let refreshMapData handle it

    // Move Map
    if (map) {
        map.setCenter(new kakao.maps.LatLng(currentLat, currentLng));
        refreshMapData();
    } else {
        // If map not init, just filter list for grid
        // But refreshMapData requires map... 
        // We should init map in background? 
        // For now, let's just rely on allCCTVData being filtered when Map inits.
        // But for Video Tab Updates?
        // We need a non-map way to refresh grid based on location
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

    document.getElementById('video-status').textContent = `"${currentKeyword}" 주변 CCTV ${list.length}개`;
}

function initByUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const searchParam = params.get('search');

    if (searchParam) {
        document.getElementById('video-keyword').value = searchParam;
        handleSearch(searchParam, 'video', true).then(place => {
            if (place) selectPlace(place);
        });
    } else {
        // Default Grid Load
        filterGridByLocation(DEFAULT_LAT, DEFAULT_LNG);
    }
}


// UI Events (Grid Resizer)
function initCenterResizer() {
    const grid = document.querySelector('.grid-container');
    const handle = document.getElementById('resizer');
    if (!grid || !handle) return;

    let col1 = 1, col2 = 1, row1 = 1, row2 = 1;

    handle.addEventListener('touchstart', (e) => {
        grid.classList.add('resizing');
    }, { passive: true });

    handle.addEventListener('touchend', () => {
        grid.classList.remove('resizing');
    });

    // ... Implement full logic if needed, or simplified
}


// Video Layer Popup (Used by Map)
function openVideoLayer(cctvData) {
    const layer = document.getElementById('video-layer');
    const title = document.getElementById('video-layer-title');
    const frame = document.getElementById('video-frame');

    title.textContent = cctvData.name;
    frame.innerHTML = '';

    // Check for Broken/ActiveX
    const isActiveX = cctvData.url.includes('kind=MODE') && !cctvData.url.includes('openDataCctvStream.jsp');
    // New UTIC JSP URLs are kind=MODE but use Iframe/HLS internally, so we trust openDataCctvStream.jsp
    // But wait, the user said "Dalmoe IC" works now. It has openDataCctvStream.jsp.

    const isHLS = cctvData.url.includes('.m3u8');

    if (false) { // Disabled ActiveX Check for now
        // ...
    } else {
        // Standard Player
        // Always use createCCTVPlayer
        const player = createCCTVPlayer(cctvData.url, isHLS);
        // For popup, contain/cover?
        if (player.nodeName === 'VIDEO') {
            player.style.objectFit = 'contain'; // Popup should show full context
        }
        frame.appendChild(player);
    }

    layer.classList.add('active');

    // New Window Button logic provided in original...
    // We can add it below the frame easily
}

document.getElementById('video-layer-close').addEventListener('click', () => {
    document.getElementById('video-layer').classList.remove('active');
    document.getElementById('video-frame').innerHTML = '';
});
