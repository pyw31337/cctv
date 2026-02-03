// API & Data Functions

async function loadCCTVData() {
    try {
        const response = await fetch('cctv_data.json');
        const data = await response.json();

        // Filter valid data
        allCCTVData = data.filter(c => c.url && c.status !== 'broken');
        console.log(`Loaded ${allCCTVData.length} CCTVs`);
        return allCCTVData;
    } catch (err) {
        console.error('Error loading CCTV data:', err);
        return [];
    }
}

// Distance Calculation (Haversine Formula)
function getDistance(lat1, lng1, lat2, lng2) {
    const R = 6371e3; // Earth radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c; // Distance in meters
}

// Search Logic
async function handleSearch(keyword, type, isInitial = false) {
    if (!keyword) {
        alert('검색어를 입력하세요');
        return;
    }
    const resultsContainer = document.getElementById('video-search-results');
    const input = document.getElementById('video-keyword');

    // Use Kakao Places API
    const ps = new kakao.maps.services.Places();

    return new Promise((resolve) => {
        ps.keywordSearch(keyword, (data, status, pagination) => {
            if (status === kakao.maps.services.Status.OK) {
                if (isInitial) {
                    // Direct selection (e.g. from history or top result)
                    resolve(data[0]);
                } else {
                    // Show dropdown results
                    displaySearchResults(data, type);
                    resolve(null);
                }
            } else if (status === kakao.maps.services.Status.ZERO_RESULT) {
                // If no place found, try searching our CCTV list names directly? 
                // (Optional enhancement, sticking to Places API for now)
                if (!isInitial) {
                    resultsContainer.innerHTML = '<div class="search-item" style="cursor:default">검색 결과가 없습니다.</div>';
                    resultsContainer.classList.add('active');
                    document.getElementById('video-clear-btn').classList.add('visible');
                    // Add dim overlay
                    document.querySelector('.dim-overlay').classList.add('active');
                    document.body.classList.add('search-active');
                    document.querySelector('.floating-search-container').classList.add('keyboard-active');

                } else {
                    alert('검색 결과가 없습니다.');
                }
                resolve(null);
            } else {
                alert('검색 중 오류가 발생했습니다.');
                resolve(null);
            }
        });
    });
}

function displaySearchResults(places, type) {
    const resultsContainer = document.getElementById('video-search-results');
    resultsContainer.innerHTML = '';

    places.forEach((place, index) => {
        const item = document.createElement('div');
        item.className = 'search-item';
        item.innerHTML = `
            <div class="search-item-name">${place.place_name}</div>
            <div class="search-item-addr">${place.address_name}</div>
        `;
        item.addEventListener('click', () => {
            // Use the global selectPlace function (defined in app.js or attached to window)
            if (window.selectPlace) {
                window.selectPlace(place);
            }
        });
        resultsContainer.appendChild(item);
    });

    resultsContainer.classList.add('active');

    // UI states
    document.getElementById('video-clear-btn').classList.add('visible');
    document.querySelector('.dim-overlay').classList.add('active');
    document.body.classList.add('search-active');
    document.querySelector('.floating-search-container').classList.add('keyboard-active');
}

// Search History (LocalStorage)
function saveSearchTerm(term) {
    let history = JSON.parse(localStorage.getItem('cctv_search_history')) || [];
    // Remove duplicate
    history = history.filter(item => item.name !== term.name);
    // Add to top
    history.unshift(term);
    // Limit to 10
    if (history.length > 10) history.pop();
    localStorage.setItem('cctv_search_history', JSON.stringify(history));
}

function getSearchHistory() {
    return JSON.parse(localStorage.getItem('cctv_search_history')) || [];
}
