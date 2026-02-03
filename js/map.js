// Map Logic

let mapRetryCount = 0;

function initMap() {
    // Check for load failure first
    if (window.kakaoScriptFailed) {
        console.error('Kakao Script failed to load.');
        document.getElementById('map-status').textContent = '지도 스크립트 로드 실패 (차단됨/네트워크 오류). 광고 차단 기능을 끄고 새로고침 하세요.';
        return;
    }

    // Retry logic if Kakao is not ready yet
    if (!window.kakao || !window.kakao.maps) {
        if (mapRetryCount < 10) { // Try for 5 seconds
            mapRetryCount++;
            console.warn(`Kakao API not ready, retrying... (${mapRetryCount}/10)`);
            document.getElementById('map-status').textContent = `지도 로딩 중... (${mapRetryCount})`;
            setTimeout(initMap, 500);
            return;
        } else {
            console.error('Kakao Maps API timeout.');
            document.getElementById('map-status').textContent = '지도 로딩 시간 초과. (API키 도메인 미등록 또는 쿼터 초과 가능성)';
            return;
        }
    }

    try {
        const container = document.getElementById('map');
        const options = {
            center: new kakao.maps.LatLng(currentLat, currentLng),
            level: 5
        };
        map = new kakao.maps.Map(container, options);

        // Load data if needed
        if (allCCTVData.length === 0) {
            loadCCTVData().then(() => {
                refreshMapData();
            });
        } else {
            refreshMapData();
        }

        // Map Interaction Events
        const refreshBtn = document.getElementById('map-refresh-btn');
        const showRefreshBtn = () => {
            if (refreshBtn && !refreshBtn.classList.contains('active')) {
                refreshBtn.classList.add('active');
            }
        };

        kakao.maps.event.addListener(map, 'dragend', showRefreshBtn);
        kakao.maps.event.addListener(map, 'zoom_changed', showRefreshBtn);

        // Update Center Marker
        updateCenterMarker();

        // Safety Layout
        setTimeout(() => map.relayout(), 100);

    } catch (error) {
        console.error('Map initialization failed:', error);
        document.getElementById('map-status').textContent = '지도 초기화 오류: ' + error.message;
    }
}

function updateCenterMarker() {
    if (!map || !currentLat || !currentLng) return;

    if (centerMarker) centerMarker.setMap(null);

    const pinImage = new kakao.maps.MarkerImage(
        './pin.svg',
        new kakao.maps.Size(40, 40),
        { offset: new kakao.maps.Point(20, 20) }
    );
    centerMarker = new kakao.maps.Marker({
        position: new kakao.maps.LatLng(currentLat, currentLng),
        image: pinImage,
        zIndex: 100
    });
    centerMarker.setMap(map);
}


function refreshMapData() {
    if (!map) return;

    const bounds = map.getBounds();
    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();

    // Filter by Viewport
    const inView = allCCTVData.filter(c =>
        c.lat >= sw.getLat() && c.lat <= ne.getLat() &&
        c.lng >= sw.getLng() && c.lng <= ne.getLng()
    );

    // Limit Makers (Smart Sort by Distance from Center)
    const center = map.getCenter();
    const cLat = center.getLat();
    const cLng = center.getLng();

    // Sort by distance to center to ensure relevant markers are shown first
    inView.sort((a, b) => {
        const distA = (a.lat - cLat) ** 2 + (a.lng - cLng) ** 2;
        const distB = (b.lat - cLat) ** 2 + (b.lng - cLng) ** 2;
        return distA - distB;
    });

    const statusEl = document.getElementById('map-status');
    const limit = 200; // Increased limit
    const limitedList = inView.slice(0, limit);

    // Clear old markers
    markers.forEach(m => m.setMap(null));
    markers = [];

    // Add new markers
    limitedList.forEach(c => {
        // Marker image logic
        const image = new kakao.maps.MarkerImage(
            './marker.svg',
            new kakao.maps.Size(32, 32),
            { offset: new kakao.maps.Point(16, 16) }
        );

        const marker = new kakao.maps.Marker({
            position: new kakao.maps.LatLng(c.lat, c.lng),
            image: image,
            title: c.name
        });
        marker.setMap(map);

        // Click Event
        kakao.maps.event.addListener(marker, 'click', () => {
            openVideoLayer(c); // Global function from video.js? No, need to expose it or move it.
            // video.js functions are global if included in script tag.
        });

        markers.push(marker);
    });

    // Update Global List & Status
    currentCctvList = limitedList; // Important for Grid Sync

    // Sync Grid (If video.js is loaded)
    if (typeof populateVideoSelects === 'function') {
        populateVideoSelects(currentCctvList);
    }

    if (inView.length > limit) {
        statusEl.textContent = `${inView.length}개 중 ${limit}개 표시 (지도를 확대하세요)`;
    } else {
        statusEl.textContent = `현재 지역 CCTV ${inView.length}개`;
    }
}

// Map Video Layer Logic (Repeated from original, but uses Video Player)
// We need to ensure openVideoLayer is available globally. 
// It was in video logic but usually called from Map.
// Let's put it in app.js or video.js and ensure global access.
