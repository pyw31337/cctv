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
    const resultsContainer = document.getElementById('video-search-results');
    // If empty keyword, show history
    if (!keyword || keyword.trim() === '') {
        renderHistoryAndBookmarks();
        return;
    }

    // Use Kakao Places API
    const ps = new kakao.maps.services.Places();

    return new Promise((resolve) => {
        ps.keywordSearch(keyword, (data, status, pagination) => {
            if (status === kakao.maps.services.Status.OK) {
                if (isInitial) {
                    // Direct selection
                    resolve(data[0]);
                } else {
                    // Show dropdown results
                    displaySearchResults(data, type);
                    resolve(null);
                }
            } else if (status === kakao.maps.services.Status.ZERO_RESULT) {
                if (!isInitial) {
                    resultsContainer.innerHTML = '<div class="search-item" style="cursor:default; color:var(--text-sub);">검색 결과가 없습니다.</div>';
                    resultsContainer.classList.add('active');
                    document.getElementById('video-clear-btn').classList.add('visible');
                    document.querySelector('.dim-overlay').classList.add('active');
                    document.body.classList.add('search-active');
                    document.querySelector('.floating-search-container').classList.add('keyboard-active');

                } else {
                    // alert('검색 결과가 없습니다.'); // Initial load fail silent
                }
                resolve(null);
            } else {
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
        item.className = 'search-item bookmark-item'; // Reuse bookmark styling for alignment

        const isBk = isBookmarked(place.place_name);

        item.innerHTML = `
            <div class="bookmark-info" style="cursor:pointer">
                <div class="bookmark-text">${place.place_name}</div>
                <div class="bookmark-address">${place.address_name}</div>
            </div>
            <button class="bookmark-del-btn star-btn" style="background:transparent; color:${isBk ? '#eab308' : 'var(--text-sub)'}" title="북마크">
                <svg viewBox="0 0 24 24" fill="${isBk ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" style="width:20px;height:20px;">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                </svg>
            </button>
        `;

        // Place Click
        item.querySelector('.bookmark-info').addEventListener('click', () => {
            if (window.selectPlace) {
                window.selectPlace(place);
                saveSearchTerm(place); // Save to history
            }
        });

        // Star Click
        item.querySelector('.star-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBookmark(place);
            // Re-render icon
            const isNowBk = isBookmarked(place.place_name);
            const btn = e.currentTarget;
            btn.style.color = isNowBk ? '#eab308' : 'var(--text-sub)';
            btn.querySelector('svg').setAttribute('fill', isNowBk ? 'currentColor' : 'none');
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

// === Bookmark Functions ===
function getBookmarks() {
    return JSON.parse(localStorage.getItem('cctv_bookmarks')) || [];
}

function saveBookmark(place) {
    let bookmarks = getBookmarks();
    // Check duplicates
    if (!bookmarks.some(b => b.place_name === place.place_name)) {
        bookmarks.unshift(place);
        localStorage.setItem('cctv_bookmarks', JSON.stringify(bookmarks));
    }
}

function removeBookmark(placeName) {
    let bookmarks = getBookmarks();
    bookmarks = bookmarks.filter(b => b.place_name !== placeName);
    localStorage.setItem('cctv_bookmarks', JSON.stringify(bookmarks));
}

function isBookmarked(placeName) {
    const bookmarks = getBookmarks();
    return bookmarks.some(b => b.place_name === placeName);
}

function toggleBookmark(place) {
    if (isBookmarked(place.place_name)) {
        removeBookmark(place.place_name);
    } else {
        saveBookmark(place);
    }
}

// Search History (LocalStorage)
function saveSearchTerm(term) {
    let history = JSON.parse(localStorage.getItem('cctv_search_history')) || [];
    // Remove duplicate
    history = history.filter(item => item.place_name !== term.place_name); // Use place_name for consistency
    // Add to top
    history.unshift(term);
    // Limit to 10
    if (history.length > 10) history.pop();
    localStorage.setItem('cctv_search_history', JSON.stringify(history));
}

function getSearchHistory() {
    return JSON.parse(localStorage.getItem('cctv_search_history')) || [];
}

function removeHistoryItem(placeName) {
    let history = getSearchHistory();
    history = history.filter(h => h.place_name !== placeName);
    localStorage.setItem('cctv_search_history', JSON.stringify(history));
    renderHistoryAndBookmarks(); // Auto re-render
}

// Render Bookmarks & History
function renderHistoryAndBookmarks() {
    const resultsContainer = document.getElementById('video-search-results');
    const bookmarks = getBookmarks();
    const history = getSearchHistory();

    if (bookmarks.length === 0 && history.length === 0) {
        // resultsContainer.innerHTML = '<div style="padding:16px;color:var(--text-sub);text-align:center;">최근 검색 내역이 없습니다.</div>';
        // Keep it clean or show nothing? User wants specific layout.
        // If empty, maybe hide?
        resultsContainer.innerHTML = '';
        resultsContainer.classList.remove('active');
        return;
    }

    let html = '';

    // 1. Bookmarks Section
    if (bookmarks.length > 0) {
        html += `<div class="bookmark-section">`;
        bookmarks.forEach(place => {
            html += `
            <div class="search-item bookmark-item">
                <div class="bookmark-info" onclick="window.selectPlaceWrapper('${place.place_name}', '${place.address_name}', ${place.y}, ${place.x})">
                    <div style="display:flex;align-items:center;"> 
                         <svg viewBox="0 0 24 24" fill="#eab308" stroke="none" style="width:14px;height:14px;margin-right:6px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                         <div class="bookmark-text">${place.place_name}</div>
                    </div>
                    <div class="bookmark-address">${place.address_name}</div>
                </div>
                <button class="bookmark-del-btn" onclick="event.stopPropagation(); window.removeBookmarkWrapper('${place.place_name}')">✕</button>
            </div>`;
        });
        html += `</div>`;
    }

    // 2. History Section
    history.forEach(place => {
        html += `
        <div class="search-item bookmark-item">
            <div class="bookmark-info" onclick="window.selectPlaceWrapper('${place.place_name}', '${place.address_name}', ${place.y}, ${place.x})">
                <div class="bookmark-text">${place.place_name}</div>
                <div class="bookmark-address">${place.address_name}</div>
            </div>
            <button class="bookmark-del-btn" onclick="event.stopPropagation(); window.removeHistoryWrapper('${place.place_name}')">✕</button>
        </div>`;
    });

    resultsContainer.innerHTML = html;
    resultsContainer.classList.add('active');
    document.querySelector('.floating-search-container').classList.add('keyboard-active');
}

// Global Wrappers for Inline HTML Events (Simplest way to bridge innerHTML)
window.selectPlaceWrapper = function (name, addr, lat, lng) {
    const place = { place_name: name, address_name: addr, y: lat, x: lng };
    if (window.selectPlace) window.selectPlace(place);
};
window.removeBookmarkWrapper = function (name) {
    removeBookmark(name);
    renderHistoryAndBookmarks();
};
window.removeHistoryWrapper = function (name) {
    removeHistoryItem(name);
};
