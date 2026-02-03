// API & Data Functions

async function loadCCTVData() {
    try {
        const response = await fetch('cctv_data.json');
        const data = await response.json();
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
    const R = 6371e3;
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
        Math.cos(φ1) * Math.cos(φ2) *
        Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Search Logic
async function handleSearch(keyword, type, isInitial = false) {
    const resultsContainer = document.getElementById('video-search-results');

    // Empty keyword -> Show History
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
                    resolve(data[0]);
                } else {
                    displaySearchResults(data, type);
                    resolve(null);
                }
            } else if (status === kakao.maps.services.Status.ZERO_RESULT) {
                if (!isInitial) {
                    resultsContainer.innerHTML = '<div class="search-item" style="cursor:default; color:var(--text-sub);">검색 결과가 없습니다.</div>';
                    showSearchResultsUI();
                }
                resolve(null);
            } else {
                resolve(null);
            }
        });
    });
}

function showSearchResultsUI() {
    const resultsContainer = document.getElementById('video-search-results');
    resultsContainer.classList.add('active');
    document.getElementById('video-clear-btn').classList.add('visible');
    document.querySelector('.dim-overlay').classList.add('active');
    document.body.classList.add('search-active');
    // document.querySelector('.floating-search-container').classList.add('keyboard-active'); // Removed old class logic if container changed
}

function displaySearchResults(places, type) {
    const resultsContainer = document.getElementById('video-search-results');
    resultsContainer.innerHTML = '';

    places.forEach((place, index) => {
        const item = document.createElement('div');
        item.className = 'search-item bookmark-item';
        // Make focusable for keyboard nav
        item.setAttribute('tabindex', '0');

        const isBk = isBookmarked(place.place_name);
        const address = place.address_name || '';

        // Bookmark Icon (Ribbon)
        const ribbonSvg = `<svg viewBox="0 0 24 24" fill="${isBk ? '#eab308' : 'none'}" stroke="${isBk ? '#eab308' : 'currentColor'}" stroke-width="2" style="width:20px;height:20px;">
                            <path d="M5 3v18l7-6 7 6V3z"/>
                           </svg>`;

        item.innerHTML = `
            <div class="bookmark-info" style="cursor:pointer; display:flex; flex-direction:column; padding-left:4px;">
                <div class="bookmark-text" style="font-weight:600;">${place.place_name}</div>
                ${address ? `<div class="bookmark-address" style="font-size:12px; opacity:0.7;">${address}</div>` : ''}
            </div>
            <button class="bookmark-del-btn star-btn" style="background:transparent; color:${isBk ? '#eab308' : 'var(--text-sub)'}; border:none;" title="북마크">
                ${ribbonSvg}
            </button>
        `;

        // Click Logic
        const clickHandler = () => {
            if (window.selectPlace) {
                window.selectPlace(place);
                saveSearchTerm(place);
            }
        };

        item.addEventListener('click', (e) => {
            // If clicked on star-btn, ignore here (handled by btn listener)
            if (e.target.closest('.star-btn')) return;
            clickHandler();
        });

        // Keyboard Enter Logic
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                clickHandler();
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const next = item.nextElementSibling;
                if (next) next.focus();
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                const prev = item.previousElementSibling;
                if (prev) prev.focus();
                else document.getElementById('video-keyword').focus();
            }
        });

        // Star Click
        const starBtn = item.querySelector('.star-btn');
        starBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleBookmark(place);
            const isNowBk = isBookmarked(place.place_name);
            starBtn.style.color = isNowBk ? '#eab308' : 'var(--text-sub)';
            starBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="${isNowBk ? '#eab308' : 'none'}" stroke="${isNowBk ? '#eab308' : 'currentColor'}" stroke-width="2" style="width:20px;height:20px;">
                                    <path d="M5 3v18l7-6 7 6V3z"/>
                                 </svg>`;
        });

        resultsContainer.appendChild(item);
    });

    showSearchResultsUI();
}

// === Bookmark Functions ===
function getBookmarks() {
    return JSON.parse(localStorage.getItem('cctv_bookmarks')) || [];
}
function saveBookmark(place) {
    let bookmarks = getBookmarks();
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
    isBookmarked(place.place_name) ? removeBookmark(place.place_name) : saveBookmark(place);
}

// Search History
function saveSearchTerm(term) {
    let history = JSON.parse(localStorage.getItem('cctv_search_history')) || [];
    history = history.filter(item => item.place_name !== term.place_name);
    history.unshift(term);
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
    renderHistoryAndBookmarks();
}

// Render Bookmarks & History (Detail View)
function renderHistoryAndBookmarks() {
    const resultsContainer = document.getElementById('video-search-results');
    const bookmarks = getBookmarks();
    const history = getSearchHistory();

    if (bookmarks.length === 0 && history.length === 0) {
        resultsContainer.innerHTML = '';
        resultsContainer.classList.remove('active');
        return;
    }

    let html = '';

    const renderItem = (place, isBk, isHistory) => {
        const address = place.address_name || '';
        // Icon: Yellow Bookmark if Bookmarked, Clock if History
        // User requested: "Detailed search window 'Seoul Station' left bookmark icon"
        // And "Bookmark button is Bookmark Icon (not star)"

        let iconSvg = '';
        if (isBk) {
            // Bookmark Icon (Yellow Filled)
            iconSvg = `<svg viewBox="0 0 24 24" fill="#eab308" stroke="#eab308" stroke-width="2" style="width:18px;height:18px;margin-right:10px;"><path d="M5 3v18l7-6 7 6V3z"/></svg>`;
        } else {
            // Gray Outline Bookmark or Clock?
            // User said: "Detailed search window's undefined... Left of 'Seoul Station' bookmark icon missing... put it in."
            // Assuming for HISTORY items they want an icon too?
            // Or maybe they want the Bookmark Icon to indicate it IS a bookmark?
            // Let's use Clock for History, Bookmark for Bookmark Section.
            iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;margin-right:10px;opacity:0.5;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
        }

        const func = isHistory ? `window.removeHistoryWrapper('${place.place_name}')` : `window.removeBookmarkWrapper('${place.place_name}')`;

        return `
            <div class="search-item bookmark-item" tabindex="0" onclick="window.selectPlaceWrapper('${place.place_name}', '${place.address_name}', ${place.y}, ${place.x})">
                <div class="bookmark-info" style="display:flex; align-items:center;">
                    ${iconSvg}
                    <div style="display:flex; flex-direction:column;">
                        <div class="bookmark-text" style="font-weight:500;">${place.place_name}</div>
                        ${address ? `<div class="bookmark-address" style="font-size:12px;opacity:0.6;">${address}</div>` : ''}
                    </div>
                </div>
                <button class="bookmark-del-btn" onclick="event.stopPropagation(); ${func}">✕</button>
            </div>
        `;
    };

    // 1. Bookmarks Section
    if (bookmarks.length > 0) {
        html += `<div class="bookmark-section">`;
        bookmarks.forEach(place => {
            html += renderItem(place, true, false);
        });
        html += `</div>`;
    }

    // 2. History Section
    history.forEach(place => {
        html += renderItem(place, false, true);
    });

    resultsContainer.innerHTML = html;
    showSearchResultsUI();

    // Attach Keyboard listeners to new items
    const items = resultsContainer.querySelectorAll('.search-item');
    items.forEach(item => {
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                item.click();
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const next = item.nextElementSibling;
                if (next && next.classList.contains('search-item')) next.focus();
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                const prev = item.previousElementSibling;
                if (prev && prev.classList.contains('search-item')) prev.focus();
                else document.getElementById('video-keyword').focus();
            }
        });
    });
}

// Global Wrappers
window.selectPlaceWrapper = function (name, addr, lat, lng) {
    // Treat 'undefined' strings
    if (addr === 'undefined') addr = '';
    const place = { place_name: name, address_name: addr, y: lat, x: lng };
    if (window.selectPlace) window.selectPlace(place);
};
window.removeBookmarkWrapper = removeBookmark; // Direct ref update might fail if not exposed? 
// No, standard function hoists, but these are modules?
// api.js is loaded as standard script in html, show window globals work.
window.removeBookmarkWrapper = (name) => { removeBookmark(name); renderHistoryAndBookmarks(); };
window.removeHistoryWrapper = (name) => { removeHistoryItem(name); };
