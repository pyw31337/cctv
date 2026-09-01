// Lazy-loaded World Tour module
export function createWorldTourApi(ctx) {
    const {
        state,
        cleanupDomesticVideoGrid,
        loadWorldTourCams,
        canPlayWorldTourInApp,
        isWorldTourFavorite,
        toggleWorldTourFavorite,
        getWorldTourFavoriteIds,
        isWorldTourRegionAvailable,
        getWorldTourRegionLabel,
        getWorldTourSourceLabel,
        normalizeWorldTourText,
        escapeWorldTourHtml,
        getWorldTourSearchText,
        getWorldTourListBaseCams,
        getWorldTourListCountries,
        getWorldTourCountryEntries,
        getWorldTourListSources,
        getWorldTourListFilteredCams,
        sanitizeWorldTourListFilters,
        syncWorldTourUrlState,
        copyWorldTourShareLink,
        proxyWithOracle,
        getDistance,
        WORLD_TOUR_FAVORITE_REGION,
        WORLD_TOUR_REGIONS,
        WORLD_TOUR_REGION_LABELS,
        WORLD_TOUR_REGION_COLORS,
        WORLD_TOUR_SOURCE_ONLY_MARKER,
        WORLD_TOUR_WARNING_MARKER,
        WORLD_TOUR_IN_APP_MARKER,
        WORLD_TOUR_STAR_SVG,
        WORLD_TOUR_SEARCH_SVG,
        WORLD_TOUR_VIDEO_OFF_SVG,
        WORLD_TOUR_CHEVRON_LEFT_SVG,
        WORLD_TOUR_CHEVRON_RIGHT_SVG,
        WORLD_TOUR_SOURCE_LABELS,
        BLOCKED_YOUTUBE_VIDEO_IDS,
        SEARCH_VIDEO_SHARE_SVG
    } = ctx;

    const $ = selector => document.querySelector(selector);
    let worldTourMapLibraryPromise = null;
    let worldTourLeafletMap = null;
    let worldTourLeafletMarkers = [];
    const WORLD_TOUR_RAIL_LIMIT = 120;
    const WORLD_TOUR_LIST_RENDER_LIMIT = 200;
    const WORLD_TOUR_MAP_MARKER_LIMIT = 600;

function getWorldTourRailCams(cams, selectedId) {
    if (cams.length <= WORLD_TOUR_RAIL_LIMIT) return cams;
    const selectedIndex = Math.max(0, cams.findIndex(cam => cam.id === selectedId));
    const halfWindow = Math.floor(WORLD_TOUR_RAIL_LIMIT / 2);
    const start = Math.min(
        Math.max(0, selectedIndex - halfWindow),
        cams.length - WORLD_TOUR_RAIL_LIMIT
    );
    return cams.slice(start, start + WORLD_TOUR_RAIL_LIMIT);
}

function getWorldTourMapCams(cams, selectedId) {
    if (cams.length <= WORLD_TOUR_MAP_MARKER_LIMIT) return cams;
    const sampled = [];
    const seen = new Set();
    const stride = cams.length / (WORLD_TOUR_MAP_MARKER_LIMIT - 1);
    for (let index = 0; index < WORLD_TOUR_MAP_MARKER_LIMIT - 1; index += 1) {
        const cam = cams[Math.floor(index * stride)];
        if (cam && !seen.has(cam.id)) {
            sampled.push(cam);
            seen.add(cam.id);
        }
    }
    const selected = cams.find(cam => cam.id === selectedId);
    if (selected && !seen.has(selected.id)) sampled.push(selected);
    return sampled;
}

function renderWorldTourFavoriteButton(cam, variant = 'card') {
    const isActive = isWorldTourFavorite(cam);
    const title = isActive ? '즐겨찾기 해제' : '즐겨찾기 추가';

    return `
        <button
            type="button"
            class="world-tour-favorite-btn world-tour-favorite-btn-${escapeWorldTourHtml(variant)} ${isActive ? 'active' : ''}"
            data-world-tour-favorite="${escapeWorldTourHtml(cam.id)}"
            aria-pressed="${isActive}"
            aria-label="${escapeWorldTourHtml(`${cam.title} ${title}`)}"
            title="${escapeWorldTourHtml(title)}"
        >${WORLD_TOUR_STAR_SVG}</button>
    `;
}

function getWorldTourRegionCounts(cams) {
    // Honor the "원본만 보기" toggle — when active, region chip counts
    // (All / North America / Europe / ...) drop to the playable-only set
    // so the count matches the map markers and card rail.
    const source = state.worldTourListExcludeExternal
        ? cams.filter(canPlayWorldTourInApp)
        : cams;
    const favorites = getWorldTourFavoriteIds();
    return source.reduce((counts, cam) => {
        const region = cam.region || 'Other';
        counts.All = (counts.All || 0) + 1;
        if (favorites.has(String(cam.id))) {
            counts[WORLD_TOUR_FAVORITE_REGION] = (counts[WORLD_TOUR_FAVORITE_REGION] || 0) + 1;
        }
        counts[region] = (counts[region] || 0) + 1;
        return counts;
    }, { All: 0, [WORLD_TOUR_FAVORITE_REGION]: 0 });
}

function getWorldTourVisibleCams(cams) {
    // The video-off toggle in the list panel is treated as a global
    // filter — it should also hide external-only cams from the bottom
    // rail and from the world-tour map markers, not just the panel list.
    const base = state.worldTourListExcludeExternal
        ? cams.filter(canPlayWorldTourInApp)
        : cams;
    let visible = base;
    if (state.worldTourRegion === WORLD_TOUR_FAVORITE_REGION) {
        const favorites = getWorldTourFavoriteIds();
        visible = base.filter(cam => favorites.has(String(cam.id)));
    } else if (state.worldTourRegion !== 'All') {
        visible = base.filter(cam => cam.region === state.worldTourRegion);
    }
    if (state.worldTourListCountry && state.worldTourListCountry !== 'All') {
        visible = visible.filter(cam => cam.country === state.worldTourListCountry);
    }
    return visible;
}

function getWorldTourNearbyCams(selected, cams, limit = 6) {
    if (!selected) return [];

    return cams
        .filter(cam => cam.id !== selected.id && Number.isFinite(Number(cam.lat)) && Number.isFinite(Number(cam.lng)))
        .map(cam => ({
            ...cam,
            distance: getDistance(Number(selected.lat), Number(selected.lng), Number(cam.lat), Number(cam.lng))
        }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, limit);
}

function renderWorldTourRegionTabs(cams) {
    const counts = getWorldTourRegionCounts(cams);
    const regions = [WORLD_TOUR_FAVORITE_REGION, ...WORLD_TOUR_REGIONS];

    return `
        <div class="world-tour-region-tabs" role="tablist" aria-label="대륙별 관광 라이브 필터">
            ${regions
                .filter(region => region === WORLD_TOUR_FAVORITE_REGION || counts[region] > 0)
                .map(region => `
                    <button
                        type="button"
                        class="world-tour-region-tab ${state.worldTourRegion === region ? 'active' : ''}"
                        data-world-region="${escapeWorldTourHtml(region)}"
                    >
                        <span class="world-tour-region-tab-label">
                            ${region === WORLD_TOUR_FAVORITE_REGION ? `<span class="world-tour-favorite-tab-icon active">${WORLD_TOUR_STAR_SVG}</span>` : ''}
                            <span>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</span>
                        </span>
                        <b>${counts[region]}</b>
                    </button>
                `).join('')}
        </div>
    `;
}

function renderWorldTourListToggle(cams) {
    return `
        <button
            type="button"
            class="world-tour-list-toggle ${state.worldTourListOpen ? 'active' : ''}"
            data-world-tour-list-toggle
            aria-label="세계 CCTV 리스트 열기"
            title="세계 CCTV 리스트"
        >
            ${WORLD_TOUR_SEARCH_SVG}
        </button>
    `;
}

function renderWorldTourCountrySelect(cams) {
    const entries = getWorldTourCountryEntries(cams, state.worldTourRegion || 'All');
    const selectedCountry = entries.some(([country]) => country === state.worldTourListCountry)
        ? state.worldTourListCountry
        : 'All';
    if (selectedCountry !== state.worldTourListCountry) {
        state.worldTourListCountry = 'All';
    }
    return `
        <select
            class="world-tour-country-select"
            data-world-tour-country-select
            aria-label="국가 필터"
            title="국가 필터"
        >
            <option value="All"${selectedCountry === 'All' ? ' selected' : ''}>모든국가</option>
            ${entries.map(([country, count]) => `
                <option value="${escapeWorldTourHtml(country)}"${selectedCountry === country ? ' selected' : ''}>
                    ${escapeWorldTourHtml(country)} (${count})
                </option>
            `).join('')}
        </select>
    `;
}

function renderWorldTourRegionControls(cams) {
    return `
        <div class="world-tour-region-bar">
            ${renderWorldTourRegionTabs(cams)}
            ${renderWorldTourCountrySelect(cams)}
        </div>
        ${renderWorldTourListToggle(cams)}
    `;
}

function renderWorldTourCard(cam, selectedId) {
    const isActive = cam.id === selectedId;
    const regionColor = WORLD_TOUR_REGION_COLORS[cam.region] || '#86efac';
    const sourceLabel = getWorldTourSourceLabel(cam);
    const externalOnly = !canPlayWorldTourInApp(cam);
    const externalBadge = externalOnly
        ? `<span class="world-tour-external-badge" title="원본사이트에서만 재생 가능" aria-label="원본사이트에서만 재생 가능">${WORLD_TOUR_VIDEO_OFF_SVG}</span>`
        : '';

    return `
        <article class="world-tour-card ${isActive ? 'active' : ''}" data-id="${escapeWorldTourHtml(cam.id)}" tabindex="0" aria-label="${escapeWorldTourHtml(`${cam.title} 영상 선택`)}">
            <span class="world-tour-card-title-row">
                <span class="world-tour-card-title">${escapeWorldTourHtml(cam.title)}${externalBadge}</span>
                <span class="world-tour-card-actions">
                    <button
                        type="button"
                        class="world-tour-share-card-btn"
                        data-world-tour-share="${escapeWorldTourHtml(cam.id)}"
                        title="단일 영상 공유 링크 복사"
                        aria-label="${escapeWorldTourHtml(cam.title)} 단일 영상 공유 링크 복사"
                    >${SEARCH_VIDEO_SHARE_SVG}</button>
                    ${renderWorldTourFavoriteButton(cam, 'card')}
                </span>
            </span>
            <span class="world-tour-card-sub">${escapeWorldTourHtml(cam.city)} · ${escapeWorldTourHtml(cam.country)}</span>
            <span class="world-tour-card-footer">
                <span class="world-tour-card-tag" style="--region-color:${regionColor}">${escapeWorldTourHtml(getWorldTourRegionLabel(cam.region))}</span>
                <span class="world-tour-source-tag ${canPlayWorldTourInApp(cam) ? 'playable' : 'external'}">${escapeWorldTourHtml(sourceLabel)}</span>
            </span>
        </article>
    `;
}

function renderWorldTourListRegionChips(cams) {
    const counts = getWorldTourRegionCounts(cams);
    const regions = [WORLD_TOUR_FAVORITE_REGION, ...WORLD_TOUR_REGIONS]
        .filter(region => region === WORLD_TOUR_FAVORITE_REGION || counts[region] > 0);

    return regions.map(region => `
        <button
            type="button"
            class="world-tour-list-chip ${state.worldTourListRegion === region ? 'active' : ''}"
            data-world-tour-list-region="${escapeWorldTourHtml(region)}"
        >
            ${region === WORLD_TOUR_FAVORITE_REGION ? `<span class="world-tour-favorite-tab-icon active">${WORLD_TOUR_STAR_SVG}</span>` : ''}
            <span>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</span>
            <b>${counts[region] || 0}</b>
        </button>
    `).join('');
}

function renderWorldTourListSelectOptions(entries, selectedValue, allLabel) {
    const options = [`<option value="All">${escapeWorldTourHtml(allLabel)}</option>`];
    entries.forEach(entry => {
        const value = Array.isArray(entry) ? entry[0] : entry.sourceType;
        const label = Array.isArray(entry) ? entry[0] : entry.label;
        const count = Array.isArray(entry) ? entry[1] : entry.count;
        options.push(`
            <option value="${escapeWorldTourHtml(value)}" ${selectedValue === value ? 'selected' : ''}>
                ${escapeWorldTourHtml(label)} (${count})
            </option>
        `);
    });
    return options.join('');
}

// Wraps every occurrence of `search` inside `text` with a <mark> element,
// returning HTML-safe output. The match is case-insensitive (we lowercase
// both haystack and needle). Use this anywhere we surface a field that
// might be why the row was matched, so users can see WHY their query hit.
function highlightWorldTourMatch(text, search) {
    const raw = text == null ? '' : String(text);
    if (!raw) return '';
    const needle = normalizeWorldTourText(search);
    if (!needle) return escapeWorldTourHtml(raw);

    const lower = raw.toLowerCase();
    const len = needle.length;
    const out = [];
    let cursor = 0;
    while (cursor < raw.length) {
        const idx = lower.indexOf(needle, cursor);
        if (idx < 0) {
            out.push(escapeWorldTourHtml(raw.slice(cursor)));
            break;
        }
        if (idx > cursor) out.push(escapeWorldTourHtml(raw.slice(cursor, idx)));
        out.push(`<mark class="world-tour-search-highlight">${escapeWorldTourHtml(raw.slice(idx, idx + len))}</mark>`);
        cursor = idx + len;
    }
    return out.join('');
}

function renderWorldTourListItems(items, selectedId) {
    if (!items.length) {
        return '<div class="world-tour-list-empty">조건에 맞는 세계 CCTV가 없습니다. 검색어나 필터를 줄여보세요.</div>';
    }

    const search = state.worldTourListSearch;

    return items.slice(0, WORLD_TOUR_LIST_RENDER_LIMIT).map(cam => {
        const isActive = cam.id === selectedId;
        const sourceLabel = getWorldTourSourceLabel(cam);
        const regionLabel = getWorldTourRegionLabel(cam.region);
        const externalOnly = !canPlayWorldTourInApp(cam);
        const externalBadge = externalOnly
            ? `<span class="world-tour-external-badge" title="원본사이트에서만 재생 가능" aria-label="원본사이트에서만 재생 가능">${WORLD_TOUR_VIDEO_OFF_SVG}</span>`
            : '';
        // Only render the subtitle row when a search is active and the
        // subtitle would actually help explain the match — otherwise we
        // keep list rows compact like before.
        const subtitle = cam.subtitle || '';
        const subtitleMatches = search
            && subtitle
            && normalizeWorldTourText(subtitle).includes(normalizeWorldTourText(search));
        const subtitleRow = subtitleMatches
            ? `<span class="world-tour-list-item-subtitle">${highlightWorldTourMatch(subtitle, search)}</span>`
            : '';
        return `
            <article class="world-tour-list-item ${isActive ? 'active' : ''}" data-world-tour-list-item="${escapeWorldTourHtml(cam.id)}" tabindex="0">
                ${renderWorldTourFavoriteButton(cam, 'list')}
                <div class="world-tour-list-item-main">
                    <strong class="world-tour-list-item-title">
                        <span class="world-tour-list-item-title-text">${highlightWorldTourMatch(cam.title, search)}</span>
                        ${externalBadge}
                    </strong>
                    <span>${highlightWorldTourMatch(cam.city, search)} · ${highlightWorldTourMatch(cam.country, search)}</span>
                    <em>${highlightWorldTourMatch(regionLabel, search)} · ${highlightWorldTourMatch(sourceLabel, search)}</em>
                    ${subtitleRow}
                </div>
                <div class="world-tour-list-item-actions">
                    <button type="button" data-world-tour-list-map="${escapeWorldTourHtml(cam.id)}">지도</button>
                    <button type="button" data-world-tour-list-video="${escapeWorldTourHtml(cam.id)}">영상</button>
                    <button type="button" data-world-tour-list-share="${escapeWorldTourHtml(cam.id)}" title="공유 링크 복사" aria-label="${escapeWorldTourHtml(cam.title)} 공유 링크 복사">${SEARCH_VIDEO_SHARE_SVG}</button>
                </div>
            </article>
        `;
    }).join('');
}

function renderWorldTourListPanel(cams, selected) {
    sanitizeWorldTourListFilters(cams);
    const filteredCams = getWorldTourListFilteredCams(cams);
    const countryOptions = renderWorldTourListSelectOptions(
        getWorldTourListCountries(cams),
        state.worldTourListCountry,
        '모든 국가'
    );
    const externalOnly = state.worldTourListExcludeExternal;

    return `
        <div class="world-tour-list-overlay" data-world-tour-list-overlay>
            <aside class="world-tour-list-panel" role="dialog" aria-modal="true" aria-label="세계 CCTV 리스트">
                <div class="world-tour-list-head">
                    <div>
                        <span>WORLD CCTV LIST</span>
                        <strong>세계 관광 라이브 검색</strong>
                    </div>
                    <button type="button" class="world-tour-list-close" data-world-tour-list-close aria-label="리스트 닫기">×</button>
                </div>
                <label class="world-tour-list-search">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="m21 21-4.34-4.34"/><circle cx="11" cy="11" r="8"/>
                    </svg>
                    <input
                        type="search"
                        data-world-tour-list-search
                        value="${escapeWorldTourHtml(state.worldTourListSearch)}"
                        placeholder="국가, 도시, 영상명 검색"
                        autocomplete="off"
                    >
                </label>
                <div class="world-tour-list-filter-group">
                    <div class="world-tour-list-chip-row" aria-label="대륙/즐겨찾기 필터">
                        ${renderWorldTourListRegionChips(cams)}
                    </div>
                    <div class="world-tour-list-select-row">
                        <select data-world-tour-list-country aria-label="국가 필터">${countryOptions}</select>
                        <button
                            type="button"
                            class="world-tour-list-external-toggle ${externalOnly ? 'active' : ''}"
                            data-world-tour-list-external-toggle
                            aria-pressed="${externalOnly}"
                            aria-label="${externalOnly ? '원본사이트 영상 포함' : '원본사이트 영상 제외'}"
                            title="${externalOnly ? '원본사이트 영상 제외중 — 클릭하면 포함' : '원본사이트로만 재생되는 영상을 제외'}"
                        >
                            ${WORLD_TOUR_VIDEO_OFF_SVG}
                            <span>원본만${externalOnly ? ' 숨김' : ' 보기'}</span>
                        </button>
                    </div>
                </div>
                <div class="world-tour-list-count" data-world-tour-list-count>
                    ${filteredCams.length}개 영상${filteredCams.length > WORLD_TOUR_LIST_RENDER_LIMIT ? ` · 상위 ${WORLD_TOUR_LIST_RENDER_LIMIT}개 표시` : ''} · 선택 ${escapeWorldTourHtml(selected.title)}
                </div>
                <div class="world-tour-list-results" data-world-tour-list-results>
                    ${renderWorldTourListItems(filteredCams, selected.id)}
                </div>
            </aside>
        </div>
    `;
}

function renderWorldTourModeSwitch(selected) {
    const videoLabel = '영상보기';
    return `
        <div class="world-tour-mode-switch" role="tablist" aria-label="관광 라이브 보기 방식">
            <button
                type="button"
                class="world-tour-mode-option ${state.worldTourViewMode === 'map' ? 'active' : ''}"
                data-world-tour-view="map"
                aria-selected="${state.worldTourViewMode === 'map'}"
            >지도보기</button>
            <button
                type="button"
                class="world-tour-mode-option ${state.worldTourViewMode === 'video' ? 'active' : ''}"
                data-world-tour-view="video"
                aria-selected="${state.worldTourViewMode === 'video'}"
            >${videoLabel}</button>
        </div>
    `;
}

function updateWorldTourHeaderSwitch(selected = null) {
    const switchEl = $('#world-tour-header-switch');
    if (!switchEl) return;
    const isWorldTour = document.body.classList.contains('world-tour-active');
    if (!isWorldTour || !selected) {
        switchEl.hidden = true;
        switchEl.innerHTML = '';
        return;
    }

    switchEl.hidden = false;
    switchEl.innerHTML = renderWorldTourModeSwitch(selected);
}

function switchWorldTourViewMode(viewMode) {
    const nextMode = viewMode === 'map' ? 'map' : 'video';
    if (!document.body.classList.contains('world-tour-active')) return;

    const list = $('#weather-list');
    const cardRail = list?.querySelector('.world-tour-card-rail');
    const regionTabs = list?.querySelector('.world-tour-region-tabs');
    renderWorldTourCams(state.selectedWorldTourId, {
        viewMode: nextMode,
        cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
        regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
        focusSelected: true
    });
}

function renderWorldTourSections(cams, selectedId) {
    if (state.worldTourRegion !== 'All') {
        return `
            <section class="world-tour-region-section">
                <div class="world-tour-section-title">
                    <h4>${escapeWorldTourHtml(getWorldTourRegionLabel(state.worldTourRegion))}</h4>
                    <span>${cams.length} live cams</span>
                </div>
                <div class="world-tour-grid">
                    ${cams.map(cam => renderWorldTourCard(cam, selectedId)).join('')}
                </div>
            </section>
        `;
    }

    return WORLD_TOUR_REGIONS
        .filter(region => region !== 'All')
        .map(region => {
            const regionCams = cams.filter(cam => cam.region === region);
            if (!regionCams.length) return '';
            return `
                <section class="world-tour-region-section">
                    <div class="world-tour-section-title">
                        <h4>${escapeWorldTourHtml(getWorldTourRegionLabel(region))}</h4>
                        <span>${regionCams.length} live cams</span>
                    </div>
                    <div class="world-tour-grid">
                        ${regionCams.map(cam => renderWorldTourCard(cam, selectedId)).join('')}
                    </div>
                </section>
            `;
        }).join('');
}

function renderWorldTourBottomMenu(cams, visibleCams, selected) {
    const shareButton = `
        <button
            type="button"
            class="world-tour-open-btn world-tour-share-btn"
            data-world-tour-share="${escapeWorldTourHtml(selected.id)}"
            aria-label="공유 링크 복사"
            title="공유 링크 복사"
        >${SEARCH_VIDEO_SHARE_SVG}</button>
    `;
    const openLink = selected.sourceUrl
        ? `
            <a
                class="world-tour-open-btn"
                href="${escapeWorldTourHtml(selected.sourceUrl)}"
                target="_blank"
                rel="noopener"
                aria-label="원본 열기"
                title="원본 열기"
            >
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                    aria-hidden="true" focusable="false">
                    <path stroke="none" d="M0 0h24v24H0z" fill="none" />
                    <path d="M5 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0" />
                    <path d="M9 10a3 3 0 1 0 6 0a3 3 0 1 0 -6 0" />
                    <path d="M8 16l-2.091 3.486a1 1 0 0 0 .857 1.514h10.468a1 1 0 0 0 .857 -1.514l-2.091 -3.486" />
                </svg>
            </a>
        `
        : '';
    const selectedIndex = Math.max(0, visibleCams.findIndex(cam => cam.id === selected.id));
    const nearbyCams = getWorldTourNearbyCams(selected, visibleCams, 2);
    const previousCam = nearbyCams[1] || (visibleCams.length
        ? visibleCams[(selectedIndex - 1 + visibleCams.length) % visibleCams.length]
        : null);
    const nextCam = nearbyCams[0] || (visibleCams.length
        ? visibleCams[(selectedIndex + 1) % visibleCams.length]
        : null);
    const railCams = getWorldTourRailCams(visibleCams, selected.id);

    return `
        <section class="world-tour-bottom-menu" aria-label="세계 관광 라이브 선택 메뉴">
            <div class="world-tour-selected-summary">
                <span class="world-tour-kicker">${escapeWorldTourHtml(getWorldTourRegionLabel(selected.region))} live cam</span>
                <div class="world-tour-title-row">
                    <h3>${escapeWorldTourHtml(selected.title)}</h3>
                    ${renderWorldTourFavoriteButton(selected, 'summary')}
                    <div class="world-tour-title-nav" aria-label="인근 관광 라이브 이동">
                        <button
                            type="button"
                            class="world-tour-title-nav-btn"
                            data-world-tour-neighbor="${escapeWorldTourHtml(previousCam?.id || selected.id)}"
                            aria-label="이전 관광 라이브"
                        >${WORLD_TOUR_CHEVRON_LEFT_SVG}</button>
                        <button
                            type="button"
                            class="world-tour-title-nav-btn"
                            data-world-tour-neighbor="${escapeWorldTourHtml(nextCam?.id || selected.id)}"
                            aria-label="다음 관광 라이브"
                        >${WORLD_TOUR_CHEVRON_RIGHT_SVG}</button>
                    </div>
                </div>
                <p>${escapeWorldTourHtml(selected.subtitle || `${selected.city}, ${selected.country}`)}</p>
                ${renderWorldTourHashTags(selected)}
                <div class="world-tour-actions">
                    ${renderWorldTourModeSwitch(selected)}
                    ${shareButton}
                    ${openLink}
                </div>
            </div>
            <div class="world-tour-bottom-main">
                ${renderWorldTourRegionControls(cams)}
                <div class="world-tour-card-rail" aria-label="선택 가능한 세계 관광 라이브">
                    ${railCams.length
                        ? railCams.map(cam => renderWorldTourCard(cam, selected.id)).join('')
                        : '<div class="world-tour-empty-favorites">아직 즐겨찾기한 세계 영상이 없습니다.</div>'}
                </div>
            </div>
        </section>
    `;
}

function renderWorldTourVideoHero(selected) {
    const isPlayable = canPlayWorldTourInApp(selected);
    const embedUrl = getWorldTourEmbedUrl(selected);
    const sourceLabel = getWorldTourSourceLabel(selected);
    const isDirectVideo = isWorldTourHlsUrl(embedUrl) || isWorldTourDirectVideoUrl(embedUrl);
    const snapshotUrl = !embedUrl ? (selected.snapshotUrl || '') : '';

    let mediaHtml;
    if (!isPlayable) {
        const playbackStatus = String(selected?.playbackStatus || '').toLowerCase();
        const isTemporaryOutage = !selected?.sourceOnly &&
            (['unavailable', 'source-only'].includes(playbackStatus) || selected?.sourceOnlyReason);

        const title = isTemporaryOutage ? '⚠️ 임시 점검 중' : '외부 원본 사이트 제공 영상';
        const msg = isTemporaryOutage
            ? '현재 해당 스트림에 일시적인 연결 장애가 발생했습니다.<br>우측 상단의 나침반 버튼 또는 아래 링크를 통해 원본 사이트에서 직접 확인하실 수 있습니다.'
            : '해당 채널은 외부 원본 사이트에서 직접 시청하실 수 있습니다.';

        const actionBtn = selected.sourceUrl
            ? `<a class="world-tour-action-btn" href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본 사이트에서 시청</a>`
            : '';

        mediaHtml = `
            <div class="world-tour-video world-tour-outage-hero">
                <div class="world-tour-outage-content">
                    <div class="world-tour-outage-title">${title}</div>
                    <div class="world-tour-outage-text">${msg}</div>
                    ${actionBtn}
                </div>
            </div>`;
    } else if (embedUrl && isDirectVideo) {
        mediaHtml = `
            <div class="world-tour-video">
                <video
                    class="world-tour-direct-video"
                    data-world-tour-stream="${escapeWorldTourHtml(embedUrl)}"
                    data-world-tour-title="${escapeWorldTourHtml(selected.title)}"
                    autoplay muted playsinline controls
                ></video>
                <div class="world-tour-video-loading">
                    <div class="world-tour-spinner"></div>
                    <div class="world-tour-loading-text">영상을 불러오는 중...</div>
                </div>
            </div>`;
    } else if (embedUrl) {
        mediaHtml = `
            <div class="world-tour-video world-tour-iframe-container">
                <iframe
                    src="${escapeWorldTourHtml(embedUrl)}"
                    title="${escapeWorldTourHtml(selected.title)}"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                    allowfullscreen
                ></iframe>
                <div class="world-tour-video-loading">
                    <div class="world-tour-spinner"></div>
                    <div class="world-tour-loading-text">영상을 불러오는 중...</div>
                </div>
            </div>`;
    } else if (snapshotUrl) {

        // In-app snapshot playback for sources without an embeddable player
        // (HK Traffic, USGS VolcView, Panomax, Roundshot). The image auto-
        // refreshes via initWorldTourSnapshotRefresh after the DOM mounts.
        const refreshMs = getWorldTourSnapshotRefreshMs(selected);
        mediaHtml = `
            <div class="world-tour-video world-tour-snapshot-hero">
                <img
                    class="world-tour-snapshot-img"
                    src="${escapeWorldTourHtml(snapshotUrl)}"
                    alt="${escapeWorldTourHtml(selected.title)} 실시간 스냅샷"
                    data-world-tour-snapshot="${escapeWorldTourHtml(snapshotUrl)}"
                    data-world-tour-snapshot-refresh="${refreshMs}"
                    loading="eager"
                    decoding="async"
                />
                <div class="world-tour-snapshot-overlay">
                    <span class="world-tour-snapshot-badge">${escapeWorldTourHtml(sourceLabel)} 정지 스냅샷</span>
                    ${refreshMs > 0 ? `<span class="world-tour-snapshot-meta">동영상 스트림 없음 · ${Math.round(refreshMs / 1000)}초마다 새 이미지 확인</span>` : '<span class="world-tour-snapshot-meta">동영상 스트림 없음 · 최신 캡처 이미지</span>'}
                </div>
            </div>`;
    } else {
        mediaHtml = `
            <div class="world-tour-video world-tour-external-preview">
                ${selected.thumbnailUrl ? `<img src="${escapeWorldTourHtml(selected.thumbnailUrl)}" alt="${escapeWorldTourHtml(selected.title)} preview" loading="lazy">` : ''}
                <div class="world-tour-external-copy">
                    <span>${escapeWorldTourHtml(sourceLabel)} 공식 플레이어</span>
                    <strong>이 영상은 원본 사이트에서 안정적으로 재생됩니다.</strong>
                    <a href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본에서 보기</a>
                </div>
            </div>`;
    }

    return `<section class="world-tour-hero">${mediaHtml}</section>`;
}

// Auto-refreshes the snapshot img every N ms. Adds a cache-busting query
// param so the browser doesn't serve a stale cached copy. Cleans up its
// interval when the element is removed.
let _worldTourSnapshotTimers = new WeakMap();
function initWorldTourSnapshotRefresh() {
    document.querySelectorAll('.world-tour-snapshot-img[data-world-tour-snapshot]').forEach(img => {
        // De-dupe — avoid stacking intervals when re-render happens.
        const prev = _worldTourSnapshotTimers.get(img);
        if (prev) {
            clearInterval(prev);
            _worldTourSnapshotTimers.delete(img);
        }
        const refreshMs = Number(img.dataset.worldTourSnapshotRefresh || 0);
        if (!refreshMs || refreshMs < 5000) return; // skip static-image sources
        const baseUrl = img.dataset.worldTourSnapshot;
        if (!baseUrl) return;
        const timer = setInterval(() => {
            if (!img.isConnected) {
                clearInterval(timer);
                _worldTourSnapshotTimers.delete(img);
                return;
            }
            if (document.hidden) return; // pause when tab not visible
            const sep = baseUrl.includes('?') ? '&' : '?';
            img.src = `${baseUrl}${sep}_=${Date.now()}`;
        }, refreshMs);
        _worldTourSnapshotTimers.set(img, timer);
    });
}

function renderWorldTourMapHero(selected, visibleCams) {
    return `
        <section class="world-tour-map-stage" aria-label="세계 관광 라이브 지도">
            <div class="world-tour-map-wrap">
                <div id="world-tour-map" class="world-tour-map" aria-label="${escapeWorldTourHtml(selected.title)} 주변 관광 라이브 지도">
                    <div class="world-tour-map-loading">OpenStreetMap 지도를 불러오는 중...</div>
                </div>
            </div>
        </section>
    `;
}

function createWorldTourMarkerPopup(cam) {
    const sourceOnly = !canPlayWorldTourInApp(cam);
    const primaryLabel = sourceOnly ? '원본보기' : '영상보기';
    const primaryClass = sourceOnly ? ' world-tour-marker-video-btn-source-only' : '';
    const popup = document.createElement('div');
    popup.className = 'world-tour-marker-popup';
    popup.innerHTML = `
        <strong>${escapeWorldTourHtml(cam.title)}</strong>
        <span>${escapeWorldTourHtml(cam.city)} · ${escapeWorldTourHtml(cam.country)}</span>
        <div class="world-tour-marker-popup-actions">
            <button type="button" class="world-tour-marker-video-btn${primaryClass}">${primaryLabel}</button>
            <button type="button" class="world-tour-marker-share-btn">공유</button>
        </div>
    `;

    popup.querySelector('.world-tour-marker-video-btn')?.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        if (sourceOnly && cam.sourceUrl) {
            const opened = window.open(cam.sourceUrl, '_blank', 'noopener,noreferrer');
            if (!opened) window.location.href = cam.sourceUrl;
            return;
        }
        renderWorldTourCams(cam.id, {
            viewMode: 'video',
            focusSelected: true,
            listScrollToSelected: true
        });
    });

    popup.querySelector('.world-tour-marker-share-btn')?.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        copyWorldTourShareLink(cam, { viewMode: 'video' });
    });

    return popup;
}

function enableHorizontalDragScroll(scroller, onScroll) {
    if (!scroller || scroller.dataset.dragScrollBound === 'true') return;
    scroller.dataset.dragScrollBound = 'true';

    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let startScrollLeft = 0;
    let didDrag = false;
    let suppressClick = false;
    const dragThreshold = 5;

    const finishDrag = event => {
        if (pointerId === null || event.pointerId !== pointerId) return;
        if (didDrag) {
            suppressClick = true;
            window.setTimeout(() => { suppressClick = false; }, 0);
        }
        scroller.classList.remove('is-dragging');
        try {
            scroller.releasePointerCapture?.(pointerId);
        } catch (error) {
            // Pointer capture can already be released by the browser.
        }
        pointerId = null;
        didDrag = false;
    };

    scroller.addEventListener('pointerdown', event => {
        if (event.button !== 0 || event.pointerType === 'touch') return;
        pointerId = event.pointerId;
        startX = event.clientX;
        startY = event.clientY;
        startScrollLeft = scroller.scrollLeft;
        didDrag = false;
    });

    scroller.addEventListener('pointermove', event => {
        if (pointerId === null || event.pointerId !== pointerId) return;
        const deltaX = event.clientX - startX;
        const deltaY = event.clientY - startY;
        if (!didDrag && Math.abs(deltaX) > dragThreshold && Math.abs(deltaX) >= Math.abs(deltaY)) {
            didDrag = true;
            scroller.classList.add('is-dragging');
            try {
                scroller.setPointerCapture?.(pointerId);
            } catch (error) {
                // Non-fatal: drag still works while the pointer stays inside.
            }
        }
        if (!didDrag) return;
        event.preventDefault();
        scroller.scrollLeft = startScrollLeft - deltaX;
        onScroll?.(scroller.scrollLeft);
    });

    scroller.addEventListener('pointerup', finishDrag);
    scroller.addEventListener('pointercancel', finishDrag);
    scroller.addEventListener('lostpointercapture', finishDrag);
    scroller.addEventListener('click', event => {
        if (!suppressClick) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);

    // Convert vertical mouse-wheel scroll into horizontal scroll so users on
    // a standard wheel mouse (without a trackpad) can also browse the chips.
    scroller.addEventListener('wheel', event => {
        if (event.deltaY === 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
        const maxScroll = scroller.scrollWidth - scroller.clientWidth;
        if (maxScroll <= 0) return;
        const current = scroller.scrollLeft;
        // Stop scroll bleed-through to the page only when we'll actually move.
        const headroom = event.deltaY > 0 ? maxScroll - current : current;
        if (headroom <= 0) return;
        event.preventDefault();
        scroller.scrollLeft = current + event.deltaY;
        onScroll?.(scroller.scrollLeft);
    }, { passive: false });
}

function enableWorldTourVideoPan(root = document) {
    root.querySelectorAll?.('.world-tour-video').forEach(container => {
        if (container.dataset.worldTourPanBound === '1') return;
        container.dataset.worldTourPanBound = '1';

        let pointerId = null;
        let startX = 0;
        let startY = 0;
        let startPan = 0;
        let panX = Number(container.dataset.worldTourPanX || 0);
        let maxPan = 0;
        let didPan = false;
        const dragThreshold = 5;

        const applyPan = nextPan => {
            panX = Math.max(-maxPan, Math.min(maxPan, nextPan));
            container.dataset.worldTourPanX = String(panX);
            container.style.setProperty('--world-tour-pan-x', `${panX}px`);
            const position = maxPan > 0
                ? Math.max(0, Math.min(100, 50 - (panX / maxPan) * 50))
                : 50;
            container.style.setProperty('--world-tour-object-position', `${position}% center`);
        };

        const refreshMetrics = () => {
            const rect = container.getBoundingClientRect();
            container.style.setProperty('--world-tour-frame-height', `${Math.max(0, rect.height)}px`);
            // Most global embeds are 16:9. When the viewport is portrait-ish,
            // cover layout crops left/right; keep that hidden width draggable.
            maxPan = Math.max(0, ((rect.height * 16 / 9) - rect.width) / 2);
            container.classList.toggle('is-pannable', maxPan > 8);
            applyPan(panX);
        };

        const finishPan = event => {
            if (pointerId === null || (event?.pointerId != null && event.pointerId !== pointerId)) return;
            container.classList.remove('is-panning');
            try {
                container.releasePointerCapture?.(pointerId);
            } catch (error) {
                // Pointer capture may already be released by the browser.
            }
            pointerId = null;
            didPan = false;
        };

        container.addEventListener('pointerdown', event => {
            if (event.target.closest('.world-tour-alternative-suggestions')) return;
            if (event.button !== 0 && event.pointerType !== 'touch') return;
            refreshMetrics();
            if (maxPan <= 8) return;
            pointerId = event.pointerId;
            startX = event.clientX;
            startY = event.clientY;
            startPan = panX;
            didPan = false;
            try {
                container.setPointerCapture?.(pointerId);
            } catch (error) {
                // Non-fatal: dragging still works while the pointer remains in bounds.
            }
        });

        container.addEventListener('pointermove', event => {
            if (pointerId === null || event.pointerId !== pointerId) return;
            const deltaX = event.clientX - startX;
            const deltaY = event.clientY - startY;
            if (!didPan && Math.abs(deltaX) > dragThreshold && Math.abs(deltaX) >= Math.abs(deltaY)) {
                didPan = true;
                container.classList.add('is-panning');
            }
            if (!didPan) return;
            event.preventDefault();
            applyPan(startPan + deltaX);
        });

        container.addEventListener('pointerup', finishPan);
        container.addEventListener('pointercancel', finishPan);
        container.addEventListener('lostpointercapture', finishPan);
        window.addEventListener('resize', refreshMetrics, { passive: true });
        requestAnimationFrame(refreshMetrics);
    });
}

function cleanupWorldTourVideoPlayers(root = document) {
    root.querySelectorAll?.('.world-tour-direct-video').forEach(video => {
        if (video.hls) {
            video.hls.destroy();
            video.hls = null;
        }
        video.pause();
        video.removeAttribute('src');
        video.load();
    });
}

function getNearbyDistanceText(cam1, cam2) {
    if (!cam1 || !cam2 || !cam1.lat || !cam1.lng || !cam2.lat || !cam2.lng) return '인근';
    const R = 6371; // Earth radius in km
    const dLat = (cam2.lat - cam1.lat) * Math.PI / 180;
    const dLng = (cam2.lng - cam1.lng) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(cam1.lat * Math.PI / 180) * Math.cos(cam2.lat * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    const d = R * c;
    return d < 1 ? `${Math.round(d * 1000)}m` : `${d.toFixed(1)}km`;
}

function getProbeTimeoutForCam(cam) {
    if (!cam) return 2000;
    const region = cam.region || '';
    switch (region) {
        case 'Asia': return 1500;
        case 'Europe': return 2500;
        case 'North America': return 2000;
        case 'South America': return 3000;
        case 'Oceania': return 2500;
        case 'Africa': return 3500;
        default: return 2000;
    }
}

const _worldTourProbeCache = new Map();
const PROBE_CACHE_TTL_MS = 5 * 60 * 1000;

async function probeWorldTourStreamLive(cam, timeoutMs = null) {
    if (!cam || !cam.id) return false;
    const cached = _worldTourProbeCache.get(cam.id);
    if (cached && (Date.now() - cached.ts < PROBE_CACHE_TTL_MS)) {
        return cached.result;
    }
    const result = await _probeWorldTourStreamLiveInternal(cam, timeoutMs);
    _worldTourProbeCache.set(cam.id, { result, ts: Date.now() });
    return result;
}

async function _probeWorldTourStreamLiveInternal(cam, timeoutMs = null) {
    const finalTimeout = (timeoutMs === null || timeoutMs === 1000) ? getProbeTimeoutForCam(cam) : timeoutMs;
    const embedUrl = getWorldTourEmbedUrl(cam);
    let streamUrl = isWorldTourHlsUrl(embedUrl) || isWorldTourDirectVideoUrl(embedUrl) ? embedUrl : (cam.playUrl || embedUrl);

    if (!streamUrl) return false;

    // Special case: scrape dynamic corolive stream URLs
    if (streamUrl.includes('corolive.nz')) {
        try {
            const proxiedEmbed = proxyWithOracle(streamUrl);
            const res = await fetch(proxiedEmbed);
            const text = await res.text();
            const match = text.match(/source:\s*['"](https?:\/\/[^'"]+\.m3u8)['"]/i);
            if (match && match[1]) {
                streamUrl = match[1];
            } else {
                return false;
            }
        } catch (e) {
            return false;
        }
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), finalTimeout);

    try {
        if (streamUrl.includes('.m3u8') || streamUrl.includes('.mp4')) {
            // Use oracle proxy for reliable client-side probing without CORS blocks
            const proxiedStream = proxyWithOracle(streamUrl);
            const response = await fetch(proxiedStream, {
                method: 'GET',
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response.ok;
        } else {
            // General website / YouTube embeds - use no-cors to test host responsiveness
            await fetch(streamUrl, {
                method: 'GET',
                mode: 'no-cors',
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return true;
        }
    } catch (err) {
        clearTimeout(timeoutId);
        return false;
    }
}

async function showOutageAlternativeSuggestions(container, selectedCam) {
    if (!container || !selectedCam) return;

    // If container is a video element, use its parent wrapper. Otherwise, use it directly.
    const wrapper = container.tagName === 'VIDEO' ? container.parentElement : container;
    if (!wrapper || wrapper.querySelector('.world-tour-alternative-suggestions')) return;

    const cams = (state.worldTourCams && state.worldTourCams.items)
        || (Array.isArray(state.worldTourCams) ? state.worldTourCams : []);
    if (!cams.length) return;

    let candidates = cams.filter(c =>
        c.id !== selectedCam.id &&
        c.playbackStatus === 'verified' &&
        !c.sourceOnly &&
        !c.sourceOnlyReason
    );
    if (!candidates.length) {
        candidates = cams.filter(c => c.id !== selectedCam.id && canPlayWorldTourInApp(c));
    }
    if (!candidates.length) return;

    // Fetch nearest 6 candidates to probe in parallel for maximum speed
    const nearestCandidates = getWorldTourNearbyCams(selectedCam, candidates, 6);
    if (!nearestCandidates.length) return;

    const probePromises = nearestCandidates.map(async (cam) => {
        const ok = await probeWorldTourStreamLive(cam);
        return { cam, ok };
    });

    const probeResults = await Promise.all(probePromises);
    let verifiedNearby = probeResults.filter(r => r.ok).map(r => r.cam).slice(0, 3);

    // Fallback to closest if none of them passed the fast probe
    if (!verifiedNearby.length) {
        verifiedNearby = nearestCandidates.slice(0, 3);
    }

    const suggestionsBox = document.createElement('div');
    suggestionsBox.className = 'world-tour-alternative-suggestions';

    let html = `
        <div class="world-tour-suggestion-header">근처의 추천 라이브 카메라</div>
        <div class="world-tour-suggestion-list">
    `;

    verifiedNearby.forEach(cam => {
        const title = escapeWorldTourHtml(cam.title);
        const distText = getNearbyDistanceText(selectedCam, cam);
        html += `
            <button type="button" class="world-tour-suggestion-btn" data-suggestion-id="${escapeWorldTourHtml(cam.id)}">
                <span class="suggestion-title">${title}</span>
                <span class="suggestion-dist">${distText}</span>
            </button>
        `;
    });

    html += `</div>`;
    suggestionsBox.innerHTML = html;

    suggestionsBox.querySelectorAll('.world-tour-suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.suggestionId;
            const targetCam = cams.find(c => c.id === targetId);
            if (targetCam) {
                // Clear any active search query and set region so the recommended cam is visible in results
                state.worldTourListSearch = '';
                state.worldTourRegion = targetCam.region || 'All';
                state.worldTourListCountry = 'All';

                renderWorldTourCams(targetId, {
                    viewMode: 'video',
                    focusSelected: true,
                    listScrollToSelected: true
                });
            }
        });
    });

    // Reset error loading state label if it exists
    const loading = wrapper.querySelector('.world-tour-video-loading');
    if (loading) {
        loading.innerHTML = '영상을 재생할 수 없습니다.<br>아래 추천 카메라로 이동해 보세요.';
    }

    wrapper.appendChild(suggestionsBox);
}

function initWorldTourVideoPlayback() {
    const iframe = document.querySelector('.world-tour-iframe-container iframe');
    if (iframe) {
        const loading = iframe.parentElement.querySelector('.world-tour-video-loading');
        iframe.addEventListener('load', () => {
            loading?.classList.add('hidden');
        });

        // Run background liveness probe on the iframe's underlying stream
        const selected = state.worldTourCams?.find(c => c.id === state.selectedWorldTourId);
        if (selected) {
            probeWorldTourStreamLive(selected, 3000).then(ok => {
                // Only modify DOM if user hasn't switched to another camera in the meantime
                if (!ok && state.selectedWorldTourId === selected.id) {
                    console.warn(`[WorldTour] background iframe probe failed for ${selected.title}. Triggering outage UI.`);
                    const parent = iframe.parentElement;
                    if (parent) {
                        parent.innerHTML = `
                            <div class="world-tour-outage-content">
                                <div class="world-tour-outage-title">⚠️ 임시 점검 중</div>
                                <div class="world-tour-outage-text">현재 해당 스트림에 일시적인 연결 장애가 발생했습니다.<br>우측 상단의 나침반 버튼 또는 아래 링크를 통해 원본 사이트에서 직접 확인하실 수 있습니다.</div>
                                <a class="world-tour-action-btn" href="${escapeWorldTourHtml(selected.sourceUrl)}" target="_blank" rel="noopener">원본 사이트에서 시청</a>
                            </div>
                        `;
                        parent.classList.add('world-tour-outage-hero');
                        showOutageAlternativeSuggestions(parent, selected);
                    }
                }
            });
        }

        // 8 seconds absolute timeout fallback in case of load event issues
        setTimeout(() => {
            loading?.classList.add('hidden');
        }, 8000);
    }

    const video = document.querySelector('.world-tour-direct-video');
    if (!video) return;

    const streamUrl = video.dataset.worldTourStream;
    if (!streamUrl) return;

    const selected = state.worldTourCams?.find(c => c.id === state.selectedWorldTourId);
    const loading = video.parentElement?.querySelector('.world-tour-video-loading');

    if (selected) {
        initVideoQualityTelemetry(null, selected, video);
    }

    const markReady = () => {
        video.classList.add('is-ready');
        loading?.classList.add('hidden');
        if (selected) recordVideoQualitySuccess(video, selected);
    };
    const playSafely = () => video.play().then(markReady).catch(() => markReady());

    const triggerOutageSuggestions = (reason = 'playback_error') => {
        if (loading) {
            loading.classList.add('is-error');
            loading.innerHTML = '영상을 재생할 수 없습니다.<br>근처의 정상 송출 추천 카메라를 검색 중...';
        }
        if (selected) recordVideoQualityFailure(video, selected, reason);
        showOutageAlternativeSuggestions(video, selected);
    };

    video.addEventListener('error', () => triggerOutageSuggestions('video_element_error'));

    if (isWorldTourHlsUrl(streamUrl)) {
        if (window.Hls && window.Hls.isSupported()) {
            const hls = new window.Hls({
                enableWorker: true,
                lowLatencyMode: true,
                capLevelToPlayerSize: true,
                maxBufferLength: 20,
                maxMaxBufferLength: 45,
                maxBufferSize: 20 * 1000 * 1000,
                backBufferLength: 0,
                manifestLoadingTimeOut: 12000,
                levelLoadingTimeOut: 12000,
                fragLoadingTimeOut: 16000,
                manifestLoadingMaxRetry: 3,
                levelLoadingMaxRetry: 3,
                fragLoadingMaxRetry: 3,
                fragLoadingRetryDelay: 700,
                fragLoadingMaxRetryTimeout: 6000,
                abrEwmaDefaultEstimate: _lastKnownBandwidth || 1500000,
            });
            hls.on(window.Hls.Events.FRAG_LOADED, function () {
                if (hls.bandwidthEstimate > 0) {
                    _lastKnownBandwidth = hls.bandwidthEstimate;
                }
            });
            hls.on(window.Hls.Events.MANIFEST_PARSED, playSafely);
            hls.on(window.Hls.Events.ERROR, (event, data) => {
                if (!data?.fatal) return;
                if (data.type === window.Hls.ErrorTypes.NETWORK_ERROR) {
                    switchActiveOracle();
                }
                triggerOutageSuggestions(data.details || 'hls_fatal_error');
                if (data.type === window.Hls.ErrorTypes.MEDIA_ERROR && typeof hls.recoverMediaError === 'function') {
                    hls.recoverMediaError();
                    return;
                }
                hls.destroy();
            });
            hls.attachMedia(video);
            hls.loadSource(streamUrl);
            video.hls = hls;
            return;
        }

        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = streamUrl;
            video.addEventListener('loadedmetadata', playSafely, { once: true });
            return;
        }
    }

    video.src = streamUrl;
    video.addEventListener('loadedmetadata', playSafely, { once: true });
}


function bindWorldTourListPanel(root, cams, selected) {
    const overlay = root.querySelector('[data-world-tour-list-overlay]');
    const panel = root.querySelector('.world-tour-list-panel');
    if (!overlay || !panel) return;

    const shell = root.querySelector('.world-tour-shell');

    // Whenever the list panel is mounted, drop the overlay blur/dim and
    // hide the bottom menu so the user sees the live map/video on the
    // left while exploring results. The class disappears with the
    // panel on the next re-render.
    overlay.classList.add('is-searching');
    if (shell) shell.classList.add('is-searching');
    if (typeof worldTourLeafletMap !== 'undefined' && worldTourLeafletMap?.invalidateSize) {
        requestAnimationFrame(() => {
            try { worldTourLeafletMap.invalidateSize(false); } catch (e) { /* map gone */ }
        });
    }

    const rerenderWithList = (selectedId = state.selectedWorldTourId, extraOptions = {}) => {
        const cardRail = root.querySelector('.world-tour-card-rail');
        const regionTabs = root.querySelector('.world-tour-region-tabs');
        renderWorldTourCams(selectedId, {
            viewMode: state.worldTourViewMode,
            cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
            regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
            ...extraOptions
        });
    };

    const refreshResults = () => {
        const results = panel.querySelector('[data-world-tour-list-results]');
        const count = panel.querySelector('[data-world-tour-list-count]');
        const filtered = getWorldTourListFilteredCams(cams);
        if (count) {
            count.textContent = `${filtered.length}개 영상 · 선택 ${selected.title}`;
        }
        if (results) {
            results.innerHTML = renderWorldTourListItems(filtered, state.selectedWorldTourId);
            requestAnimationFrame(() => scrollWorldTourListToSelected(results, state.selectedWorldTourId, { center: false }));
        }
    };

    // Sync the active state of the region chips (Favorite / All / region)
    // without a full re-render — needed when search auto-switches to 'All'.
    const refreshRegionChips = () => {
        panel.querySelectorAll('[data-world-tour-list-region]').forEach(chip => {
            const region = chip.dataset.worldTourListRegion || 'All';
            chip.classList.toggle('active', region === state.worldTourListRegion);
        });
    };

    // Intentionally NOT closing the panel on overlay click — the overlay
    // covers the entire viewport, and the user wants the left side (map +
    // markers + card rail) to stay fully interactive while the right
    // panel is open. To dismiss the panel use the × close button in the
    // panel header (or the list-toggle button in the bottom menu).
    // Pointer-events: none on the overlay (set in CSS for is-searching)
    // means clicks pass through to the underlying map / cards anyway.

    const searchInput = panel.querySelector('[data-world-tour-list-search]');
    searchInput?.addEventListener('input', event => {
        state.worldTourListSearch = event.target.value;
        // Any active typing should force results to come from the full
        // dataset so users aren't accidentally filtered out by a region
        // tab they forgot was active. We don't full-rerender to avoid
        // losing the input focus / cursor position.
        if (state.worldTourListSearch && state.worldTourListRegion !== 'All') {
            state.worldTourListRegion = 'All';
            refreshRegionChips();
        }
        refreshResults();
    });

    panel.querySelector('[data-world-tour-list-country]')?.addEventListener('change', event => {
        state.worldTourListCountry = event.target.value;
        state.worldTourRegion = state.worldTourListRegion || state.worldTourRegion || 'All';
        rerenderWithList();
    });

    panel.querySelector('[data-world-tour-list-external-toggle]')?.addEventListener('click', event => {
        event.preventDefault();
        state.worldTourListExcludeExternal = !state.worldTourListExcludeExternal;
        rerenderWithList();
    });

    const listChipRow = panel.querySelector('.world-tour-list-chip-row');
    enableHorizontalDragScroll(listChipRow);

    panel.addEventListener('click', event => {
        const closeButton = event.target.closest('[data-world-tour-list-close]');
        if (closeButton) {
            state.worldTourListOpen = false;
            rerenderWithList(state.selectedWorldTourId, { focusSelected: true });
            return;
        }

        const regionButton = event.target.closest('[data-world-tour-list-region]');
        if (regionButton) {
            state.worldTourListRegion = regionButton.dataset.worldTourListRegion || 'All';
            state.worldTourListCountry = 'All';
            state.worldTourListSource = 'All';
            // A region click is an explicit user action — clear any
            // active search so the user sees the new region's results.
            state.worldTourListSearch = '';
            rerenderWithList();
            return;
        }

        const favoriteButton = event.target.closest('.world-tour-favorite-btn');
        if (favoriteButton) {
            event.preventDefault();
            event.stopPropagation();
            toggleWorldTourFavorite(favoriteButton.dataset.worldTourFavorite);
            rerenderWithList();
            return;
        }

        const videoButton = event.target.closest('[data-world-tour-list-video]');
        if (videoButton) {
            event.preventDefault();
            event.stopPropagation();
            state.worldTourListScrollTop = panel.querySelector('[data-world-tour-list-results]')?.scrollTop ?? state.worldTourListScrollTop;
            renderWorldTourCams(videoButton.dataset.worldTourListVideo, {
                viewMode: 'video',
                focusSelected: true,
                listScrollToSelected: true
            });
            return;
        }

        const mapButton = event.target.closest('[data-world-tour-list-map]');
        if (mapButton) {
            event.preventDefault();
            event.stopPropagation();
            state.worldTourListScrollTop = panel.querySelector('[data-world-tour-list-results]')?.scrollTop ?? state.worldTourListScrollTop;
            if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
                selectWorldTourCam(mapButton.dataset.worldTourListMap, 'card');
            } else {
                renderWorldTourCams(mapButton.dataset.worldTourListMap, {
                    viewMode: 'map',
                    focusSelected: true,
                    listScrollToSelected: true
                });
            }
            return;
        }

        const shareButton = event.target.closest('[data-world-tour-list-share]');
        if (shareButton) {
            event.preventDefault();
            event.stopPropagation();
            copyWorldTourShareLinkById(shareButton.dataset.worldTourListShare);
            return;
        }

        const item = event.target.closest('[data-world-tour-list-item]');
        if (item) {
            state.worldTourListScrollTop = panel.querySelector('[data-world-tour-list-results]')?.scrollTop ?? state.worldTourListScrollTop;
            if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
                selectWorldTourCam(item.dataset.worldTourListItem, 'card');
            } else {
                renderWorldTourCams(item.dataset.worldTourListItem, {
                    viewMode: state.worldTourViewMode,
                    focusSelected: true,
                    listScrollToSelected: true
                });
            }
        }
    });

    panel.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const item = event.target.closest('[data-world-tour-list-item]');
        if (!item) return;
        event.preventDefault();
        if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
            selectWorldTourCam(item.dataset.worldTourListItem, 'card');
        } else {
            renderWorldTourCams(item.dataset.worldTourListItem, {
                viewMode: state.worldTourViewMode,
                focusSelected: true,
                listScrollToSelected: true
            });
        }
    });

    const results = panel.querySelector('[data-world-tour-list-results]');
    if (results) {
        requestAnimationFrame(() => {
            if (state.worldTourListScrollTop && !state.selectedWorldTourId) {
                results.scrollTop = state.worldTourListScrollTop;
            }
            scrollWorldTourListToSelected(results, state.selectedWorldTourId, {
                center: !!state.worldTourListScrollTop
            });
            state.worldTourListScrollTop = results.scrollTop;
        });
        results.addEventListener('scroll', () => {
            state.worldTourListScrollTop = results.scrollTop;
        }, { passive: true });
    }
}

function getWorldTourCardElement(scroller, id) {
    if (!scroller || !id) return null;
    return Array.from(scroller.querySelectorAll('.world-tour-card'))
        .find(card => card.dataset.id === id) || null;
}

function scrollWorldTourCardToSelected(scroller, id, options = {}) {
    const card = getWorldTourCardElement(scroller, id);
    if (!scroller || !card) return false;
    const padding = Number(options.padding ?? 18);
    const currentLeft = scroller.scrollLeft;
    const currentRight = currentLeft + scroller.clientWidth;
    const cardLeft = card.offsetLeft;
    const cardRight = cardLeft + card.offsetWidth;
    const fullyVisible = cardLeft >= currentLeft + padding && cardRight <= currentRight - padding;
    if (fullyVisible && !options.forceCenter) return true;

    const target = Math.max(
        0,
        cardLeft - Math.max(0, (scroller.clientWidth - card.offsetWidth) / 2)
    );
    if (options.behavior === 'smooth') {
        scroller.scrollTo({ left: target, behavior: 'smooth' });
    } else {
        scroller.scrollLeft = target;
    }
    state.worldTourCardScrollLeft = target;
    return true;
}

function scrollWorldTourListToSelected(results, id, options = {}) {
    if (!results || !id) return false;
    const item = Array.from(results.querySelectorAll('[data-world-tour-list-item]'))
        .find(el => el.dataset.worldTourListItem === id);
    if (!item) return false;

    const padding = Number(options.padding ?? 12);
    const currentTop = results.scrollTop;
    const currentBottom = currentTop + results.clientHeight;
    const itemTop = item.offsetTop;
    const itemBottom = itemTop + item.offsetHeight;
    const fullyVisible = itemTop >= currentTop + padding && itemBottom <= currentBottom - padding;
    if (fullyVisible && !options.center) return true;

    const target = options.center
        ? itemTop - Math.max(0, (results.clientHeight - item.offsetHeight) / 2)
        : itemTop - padding;
    results.scrollTop = Math.max(0, target);
    state.worldTourListScrollTop = results.scrollTop;
    return true;
}

async function renderWorldTourCams(selectedId = state.selectedWorldTourId, options = {}) {
    const list = $('#weather-list');
    if (!list) return;
    cleanupWorldTourVideoPlayers(list);
    const previousCardRail = list.querySelector('.world-tour-card-rail');
    const previousRegionTabs = list.querySelector('.world-tour-region-tabs');
    const nextCardScrollLeft = Number.isFinite(Number(options.cardScrollLeft))
        ? Number(options.cardScrollLeft)
        : previousCardRail?.scrollLeft ?? state.worldTourCardScrollLeft ?? 0;
    const nextRegionScrollLeft = Number.isFinite(Number(options.regionScrollLeft))
        ? Number(options.regionScrollLeft)
        : previousRegionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft ?? 0;
    list.innerHTML = '<div style="padding:20px;color:var(--text-secondary);">세계 관광 라이브를 불러오는 중...</div>';

    try {
        const cams = await loadWorldTourCams();
        if (!cams.length) {
            list.innerHTML = '<div style="padding:20px;">등록된 관광지 영상이 없습니다.</div>';
            return;
        }
        sanitizeWorldTourListFilters(cams);

        if (options.region && isWorldTourRegionAvailable(options.region)) {
            state.worldTourRegion = options.region;
        }
        if (options.viewMode) {
            state.worldTourViewMode = options.viewMode;
        }

        let visibleCams = getWorldTourVisibleCams(cams);
        if (!visibleCams.length && state.worldTourRegion !== WORLD_TOUR_FAVORITE_REGION) {
            state.worldTourRegion = 'All';
            state.worldTourListCountry = 'All';
            visibleCams = state.worldTourListExcludeExternal
                ? cams.filter(canPlayWorldTourInApp)
                : cams;
            // If the exclude-external filter happens to wipe out the
            // entire dataset, fall back to the full list so the page
            // doesn't render empty.
            if (!visibleCams.length) visibleCams = cams;
        }

        let selectedFromVisible = visibleCams.find(cam => cam.id === selectedId);
        const selectedFromAll = cams.find(cam => cam.id === selectedId);
        if (!selectedFromVisible && selectedFromAll) {
            // If the user picked an item from the right-side list/search that
            // is outside the current bottom rail filter, move the rail to the
            // selected camera's region so the active button remains visible.
            state.worldTourRegion = selectedFromAll.region || 'All';
            state.worldTourListCountry = selectedFromAll.country || 'All';
            visibleCams = getWorldTourVisibleCams(cams);
            selectedFromVisible = visibleCams.find(cam => cam.id === selectedId);
        }
        const selected = selectedFromVisible || selectedFromAll || visibleCams[0] || cams[0];
        state.selectedWorldTourId = selected.id;
        syncWorldTourUrlState(selected, { viewMode: state.worldTourViewMode });
        updateWorldTourHeaderSwitch(selected);
        destroyWorldTourMap();

        const isMapView = state.worldTourViewMode === 'map';
        list.innerHTML = `
            <div class="world-tour-shell ${isMapView ? 'world-tour-map-shell' : 'world-tour-video-shell'}">
                ${state.worldTourViewMode === 'map'
                    ? renderWorldTourMapHero(selected, visibleCams)
                    : renderWorldTourVideoHero(selected)}
                ${renderWorldTourBottomMenu(cams, visibleCams, selected)}
                ${state.worldTourListOpen ? renderWorldTourListPanel(cams, selected) : ''}
            </div>
        `;

        list.querySelector('[data-world-tour-list-toggle]')?.addEventListener('click', () => {
            state.worldTourListOpen = true;
            state.worldTourListRegion = state.worldTourRegion || 'All';
            const cardRail = list.querySelector('.world-tour-card-rail');
            const regionTabs = list.querySelector('.world-tour-region-tabs');
            renderWorldTourCams(state.selectedWorldTourId, {
                viewMode: state.worldTourViewMode,
                cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                focusSelected: true,
                listScrollToSelected: true
            });
        });

        bindWorldTourListPanel(list, cams, selected);

        list.querySelectorAll('[data-world-tour-share]').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                const cam = cams.find(item => String(item.id) === String(button.dataset.worldTourShare)) || selected;
                copyWorldTourShareLink(cam, { viewMode: state.worldTourViewMode || 'video' });
            });
        });

        list.querySelectorAll('.world-tour-card').forEach(card => {
            const selectCard = () => {
                if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
                    selectWorldTourCam(card.dataset.id, 'card');
                } else {
                    const cardRail = list.querySelector('.world-tour-card-rail');
                    const regionTabs = list.querySelector('.world-tour-region-tabs');
                    renderWorldTourCams(card.dataset.id, {
                        viewMode: state.worldTourViewMode,
                        cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                        regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                        focusSelected: true
                    });
                }
            };
            card.addEventListener('click', event => {
                if (event.target.closest('.world-tour-favorite-btn, .world-tour-share-card-btn')) return;
                selectCard();
            });
            card.addEventListener('keydown', event => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                selectCard();
            });
        });
        list.querySelectorAll('.world-tour-favorite-btn').forEach(button => {
            button.addEventListener('click', event => {
                event.preventDefault();
                event.stopPropagation();
                toggleWorldTourFavorite(button.dataset.worldTourFavorite);
                const cardRail = list.querySelector('.world-tour-card-rail');
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(state.selectedWorldTourId, {
                    viewMode: state.worldTourViewMode,
                    cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft
                });
            });
        });
        list.querySelectorAll('.world-tour-title-nav-btn').forEach(button => {
            button.addEventListener('click', () => {
                if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
                    selectWorldTourCam(button.dataset.worldTourNeighbor, 'card');
                } else {
                    const cardRail = list.querySelector('.world-tour-card-rail');
                    const regionTabs = list.querySelector('.world-tour-region-tabs');
                    renderWorldTourCams(button.dataset.worldTourNeighbor, {
                        viewMode: state.worldTourViewMode,
                        cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                        regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                        focusSelected: true
                    });
                }
            });
        });
        list.querySelectorAll('.world-tour-region-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const region = tab.dataset.worldRegion || 'All';
                state.worldTourListCountry = 'All';
                const nextVisibleCams = region === WORLD_TOUR_FAVORITE_REGION
                    ? cams.filter(cam => isWorldTourFavorite(cam))
                    : region === 'All'
                        ? cams
                        : cams.filter(cam => cam.region === region);
                const nextSelected = nextVisibleCams.find(cam => cam.id === state.selectedWorldTourId)
                    || nextVisibleCams[0]
                    || cams.find(cam => cam.id === state.selectedWorldTourId)
                    || cams[0];
                const regionTabs = list.querySelector('.world-tour-region-tabs');
                renderWorldTourCams(nextSelected.id, {
                    region,
                    viewMode: state.worldTourViewMode,
                    regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                    cardScrollLeft: 0,
                    focusSelected: true,
                    listScrollToSelected: true
                });
            });
        });
        list.querySelector('[data-world-tour-country-select]')?.addEventListener('change', event => {
            const cardRail = list.querySelector('.world-tour-card-rail');
            const regionTabs = list.querySelector('.world-tour-region-tabs');
            state.worldTourListCountry = event.target.value || 'All';
            state.worldTourListRegion = state.worldTourRegion || 'All';
            const nextVisibleCams = getWorldTourVisibleCams(cams);
            const nextSelected = nextVisibleCams.find(cam => cam.id === state.selectedWorldTourId)
                || nextVisibleCams[0]
                || cams.find(cam => cam.id === state.selectedWorldTourId)
                || cams[0];
            renderWorldTourCams(nextSelected?.id, {
                viewMode: state.worldTourViewMode,
                cardScrollLeft: cardRail?.scrollLeft ?? state.worldTourCardScrollLeft,
                regionScrollLeft: regionTabs?.scrollLeft ?? state.worldTourRegionScrollLeft,
                focusSelected: true,
                listScrollToSelected: true
            });
        });
        list.querySelectorAll('.world-tour-mode-option').forEach(button => {
            button.addEventListener('click', () => {
                switchWorldTourViewMode(button.dataset.worldTourView);
            });
        });
        list.querySelectorAll('.world-tour-nearby-item').forEach(item => {
            item.addEventListener('click', () => {
                if (state.worldTourViewMode === 'map' && worldTourLeafletMap) {
                    selectWorldTourCam(item.dataset.id, 'card');
                } else {
                    renderWorldTourCams(item.dataset.id, {
                        viewMode: state.worldTourViewMode || 'map',
                        focusSelected: true,
                        listScrollToSelected: true
                    });
                }
            });
        });

        const cardRail = list.querySelector('.world-tour-card-rail');
        const regionTabs = list.querySelector('.world-tour-region-tabs');
        if (cardRail) {
            requestAnimationFrame(() => {
                cardRail.scrollLeft = nextCardScrollLeft;
                if (options.focusSelected) {
                    scrollWorldTourCardToSelected(cardRail, state.selectedWorldTourId, {
                        forceCenter: options.forceCenterSelected !== false
                    });
                }
                state.worldTourCardScrollLeft = cardRail.scrollLeft;
            });
            cardRail.addEventListener('scroll', () => {
                state.worldTourCardScrollLeft = cardRail.scrollLeft;
            }, { passive: true });
            enableHorizontalDragScroll(cardRail, scrollLeft => {
                state.worldTourCardScrollLeft = scrollLeft;
            });
        }
        if (regionTabs) {
            requestAnimationFrame(() => {
                regionTabs.scrollLeft = nextRegionScrollLeft;
                state.worldTourRegionScrollLeft = regionTabs.scrollLeft;
            });
            regionTabs.addEventListener('scroll', () => {
                state.worldTourRegionScrollLeft = regionTabs.scrollLeft;
            }, { passive: true });
            enableHorizontalDragScroll(regionTabs, scrollLeft => {
                state.worldTourRegionScrollLeft = scrollLeft;
            });
        }

        if (state.worldTourViewMode === 'map') {
            const mapCams = getWorldTourMapCams(visibleCams, selected.id);
            requestAnimationFrame(() => initWorldTourMap(selected, mapCams));
        } else {
            requestAnimationFrame(() => {
                enableWorldTourVideoPan(list);
                initWorldTourVideoPlayback();
                initWorldTourSnapshotRefresh();

                // Show verified nearby recommendations on the outage/source-only landing screen
                const outageHero = list.querySelector('.world-tour-outage-hero');
                if (outageHero) {
                    showOutageAlternativeSuggestions(outageHero, selected);
                }
            });
        }
    } catch (error) {
        console.error('[WorldTour] failed to load:', error);
        list.innerHTML = '<div style="padding:20px;">세계 관광 라이브를 불러올 수 없습니다.</div>';
    }
}

function focusWorldTourCamOnMap(cam) {
    if (!cam) return;
    state.worldTourRegion = cam.region || 'All';
    renderWorldTourCams(cam.id, {
        viewMode: 'map',
        focusSelected: true,
        listScrollToSelected: true
    });
}

function loadWorldTourMapLibrary() {
    if (window.L) return Promise.resolve(window.L);
    if (worldTourMapLibraryPromise) return worldTourMapLibraryPromise;

    worldTourMapLibraryPromise = new Promise((resolve, reject) => {
        if (!document.querySelector('link[data-world-tour-leaflet]')) {
            const style = document.createElement('link');
            style.rel = 'stylesheet';
            style.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            style.dataset.worldTourLeaflet = 'true';
            document.head.appendChild(style);
        }

        const existingScript = document.querySelector('script[data-world-tour-leaflet]');
        if (existingScript) {
            existingScript.addEventListener('load', () => window.L ? resolve(window.L) : reject(new Error('Leaflet did not initialize')));
            existingScript.addEventListener('error', () => reject(new Error('Leaflet script failed to load')));
            return;
        }

        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.async = true;
        script.dataset.worldTourLeaflet = 'true';
        script.onload = () => window.L ? resolve(window.L) : reject(new Error('Leaflet did not initialize'));
        script.onerror = () => reject(new Error('Leaflet script failed to load'));
        document.head.appendChild(script);
    }).catch(error => {
        worldTourMapLibraryPromise = null;
        throw error;
    });

    return worldTourMapLibraryPromise;
}

function destroyWorldTourMap() {
    worldTourLeafletMarkers.forEach(marker => marker?.remove?.());
    worldTourLeafletMarkers = [];

    if (worldTourLeafletMap) {
        worldTourLeafletMap.remove();
        worldTourLeafletMap = null;
    }
}

async function initWorldTourMap(selected, visibleCams) {
    const mapEl = $('#world-tour-map');
    if (!mapEl || !selected) return;

    try {
        const L = await loadWorldTourMapLibrary();
        if (!document.body.contains(mapEl)) return;

        destroyWorldTourMap();
        mapEl.innerHTML = '';

        worldTourLeafletMap = L.map(mapEl, {
            worldCopyJump: true,
            zoomControl: false,
            attributionControl: true
        });

        L.control.zoom({ position: 'topright' }).addTo(worldTourLeafletMap);

        // Tile choice: CartoDB Voyager — uses Latin (English) place names
        // worldwide, which is much more readable than OSM Standard (where
        // labels in CJK / Cyrillic / Arabic regions appear in the local script).
        // {r} adds @2x for HiDPI screens automatically.
        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
            maxZoom: 19,
            subdomains: 'abcd',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }).addTo(worldTourLeafletMap);

        const mappableCams = visibleCams
            .filter(cam => Number.isFinite(Number(cam.lat)) && Number.isFinite(Number(cam.lng)));
        const bounds = L.latLngBounds(mappableCams.map(cam => [Number(cam.lat), Number(cam.lng)]));
        if (state.worldTourRegion === 'All') {
            const mobileWorldZoom = window.innerWidth <= 600 ? 1 : 2;
            worldTourLeafletMap.setView([18, 8], mobileWorldZoom);
        } else if (bounds.isValid()) {
            worldTourLeafletMap.fitBounds(bounds.pad(0.18), {
                maxZoom: 6
            });
        } else {
            worldTourLeafletMap.setView([Number(selected.lat), Number(selected.lng)], 4);
        }

        visibleCams.forEach(cam => {
            const lat = Number(cam.lat);
            const lng = Number(cam.lng);
            if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

            const isSelected = cam.id === selected.id;
            const marker = L.circleMarker([lat, lng], getWorldTourMarkerStyle(cam, isSelected)).addTo(worldTourLeafletMap);

            marker.worldTourCamId = cam.id;
            marker.worldTourCam = cam;

            marker
                .bindPopup(createWorldTourMarkerPopup(cam), {
                    closeButton: false,
                    autoPan: true,
                    offset: [0, -6],
                    className: 'world-tour-leaflet-popup'
                })
                .on('click', () => {
                    marker.openPopup();
                    selectWorldTourCam(cam.id, 'map');
                });

            worldTourLeafletMarkers.push(marker);

            if (isSelected) {
                worldTourLeafletMap.setView([lat, lng], Math.max(worldTourLeafletMap.getZoom(), state.worldTourRegion === 'All' ? 4 : 5), {
                    animate: false
                });
                setTimeout(() => {
                    if (worldTourLeafletMap && marker) {
                        marker.openPopup();
                        marker.bringToFront?.();
                    }
                }, 100);
            }
        });

        setTimeout(() => worldTourLeafletMap?.invalidateSize(), 80);
        setTimeout(() => worldTourLeafletMap?.invalidateSize(), 320);
    } catch (error) {
        console.error('[WorldTour] map failed:', error);
        if (mapEl) {
            mapEl.innerHTML = '<div class="world-tour-map-loading">지도를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</div>';
        }
    }
}

function selectWorldTourCam(camId, source = 'card') {
    if (state.selectedWorldTourId === camId) return;
    const oldId = state.selectedWorldTourId;
    state.selectedWorldTourId = camId;

    const list = $('#weather-list');
    if (!list) return;

    // 1. Update card active classes in the bottom rail
    const cards = list.querySelectorAll('.world-tour-card');
    cards.forEach(card => {
        if (card.dataset.id === camId) {
            card.classList.add('active');
        } else {
            card.classList.remove('active');
        }
    });

    const cardRail = list.querySelector('.world-tour-card-rail');
    if (cardRail) {
        scrollWorldTourCardToSelected(cardRail, camId, { forceCenter: true, behavior: 'smooth' });
    }

    // Update active class in the search list panel
    const results = list.querySelector('[data-world-tour-list-results]');
    if (results) {
        const listItems = results.querySelectorAll('.world-tour-list-item');
        listItems.forEach(item => {
            if (item.dataset.worldTourListItem === camId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        scrollWorldTourListToSelected(results, camId, { center: false });
    }

    // 2. Find camera data
    const cams = (state.worldTourCams && state.worldTourCams.items)
        || (Array.isArray(state.worldTourCams) ? state.worldTourCams : []);
    const selectedCam = cams.find(cam => cam.id === camId);

    // 3. Update marker styles and map viewport
    let targetMarker = null;
    worldTourLeafletMarkers.forEach(marker => {
        if (marker.worldTourCamId === camId) {
            marker.setStyle(getWorldTourMarkerStyle(marker.worldTourCam, true));
            marker.bringToFront?.();
            targetMarker = marker;
        } else if (marker.worldTourCamId === oldId) {
            marker.setStyle(getWorldTourMarkerStyle(marker.worldTourCam, false));
        }
    });

    if (worldTourLeafletMap && selectedCam) {
        const lat = Number(selectedCam.lat);
        const lng = Number(selectedCam.lng);
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
            if (source === 'card') {
                worldTourLeafletMap.setView([lat, lng], Math.max(worldTourLeafletMap.getZoom(), state.worldTourRegion === 'All' ? 4 : 5), {
                    animate: true,
                    duration: 0.25
                });
                if (targetMarker) {
                    targetMarker.openPopup();
                }
            }
        }
    }

    // 4. Update the left details panel / header switch if needed
    if (selectedCam) {
        updateWorldTourHeaderSwitch(selectedCam);
        syncWorldTourUrlState(selectedCam, { viewMode: state.worldTourViewMode });
    }
}

    return {
        cleanupWorldTourVideoPlayers,
        destroyWorldTourMap,
        updateWorldTourHeaderSwitch,
        renderWorldTourCams,
        switchWorldTourViewMode,
        focusWorldTourCamOnMap,
        selectWorldTourCam
    };
}
