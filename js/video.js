// Video Player & Grid Logic

// Unified CCTV Player Creator
function createCCTVPlayer(url, isHLS) {
    if (isHLS) {
        const video = document.createElement('video');
        // Force cover to fill the slot (User Request)
        video.style.cssText = 'width:100%;height:100%;object-fit:cover;background:black;';

        // Mobile optimizations
        video.autoplay = true;
        video.muted = true;
        video.playsInline = true;
        video.setAttribute('playsinline', '');
        video.preload = 'metadata';

        // Attach Observer for performance
        if (window.videoObserver) window.videoObserver.observe(video);

        // HLS.js logic
        if (Hls.isSupported()) {
            const hlsConfig = {
                capLevelToPlayerSize: true,
                maxBufferLength: 5,
                maxBufferSize: 3 * 1000 * 1000,
                enableWorker: true,
                lowLatencyMode: true,
                backBufferLength: 0,
                startLevel: 0,
                manifestLoadingTimeOut: 5000,
            };
            const hls = new Hls(hlsConfig);
            hls.loadSource(url);
            hls.attachMedia(video);

            hls.on(Hls.Events.ERROR, function (event, data) {
                if (data.fatal) {
                    switch (data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            hls.startLoad(); break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            hls.recoverMediaError(); break;
                        default:
                            hls.destroy(); break;
                    }
                }
            });
            video.hls = hls; // Save reference
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            // Safari Native HLS
            video.src = url;
        }
        return video;
    } else {
        // Iframe Logic (Standardized)
        const iframe = document.createElement('iframe');
        iframe.src = url;
        // Important: 'border:none' and 100% dimensions
        iframe.style.cssText = 'width:100%;height:100%;border:none;background:black;display:block;';
        iframe.allow = "autoplay; fullscreen";
        iframe.scrolling = "no";
        return iframe;
    }
}

// Attach Stream to Grid Slot
function attachStreamToSlot(slotIndex, cctvItem, listIndex) {
    const container = document.getElementById('cctv-' + slotIndex);
    if (!container) return;

    // Update Select Label
    const trigger = container.querySelector('.custom-select-trigger');
    if (trigger) {
        // [FIX] Use cctvItem.name consistently
        trigger.textContent = cctvItem ? (cctvItem.name || 'CCTV ' + (listIndex + 1)) : 'CCTV 선택';

        const optionsContainer = container.querySelector('.custom-select-options');
        if (optionsContainer) {
            optionsContainer.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
            if (listIndex !== -1 && optionsContainer.children[listIndex]) {
                optionsContainer.children[listIndex].classList.add('selected');
            }
        }
    }

    // Clear old content
    container.querySelectorAll('.placeholder, video, iframe, .cctv-fullscreen-btn').forEach(el => el.remove());

    if (!cctvItem) {
        // Show Placeholder
        const p = document.createElement('div');
        p.className = 'placeholder';
        p.textContent = '신호 없음';
        container.insertBefore(p, container.firstChild);
        return;
    }

    // Determine Type
    const isHLS = cctvItem.url.includes('.m3u8');
    const player = createCCTVPlayer(cctvItem.url, isHLS);

    // Insert Player (prepend to keep label on top)
    container.insertBefore(player, container.firstChild);

    // Add Fullscreen Button (Restored feature)
    const btn = document.createElement('button');
    btn.className = 'cctv-fullscreen-btn';
    btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>`;

    // Toggle Fullscreen Logic
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        container.classList.toggle('panel-fullscreen');

        // Re-layout grid if needed? No, CSS fixed position handles it.
        // Update Icon
        const isFull = container.classList.contains('panel-fullscreen');
        btn.innerHTML = isFull
            ? `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M10 14L3 21"/></svg>`
            : `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>`;
    });

    container.appendChild(btn);

    // Auto-remove button if video plays? No, keep it for controls.
}

// Populate Dropdowns for Grid
function populateVideoSelects(list) {
    const containers = document.querySelectorAll('.custom-select-container');

    containers.forEach((container, idx) => {
        const optionsContainer = container.querySelector('.custom-select-options');
        if (!optionsContainer) return;

        optionsContainer.innerHTML = ''; // Clear

        list.forEach((item, i) => {
            const div = document.createElement('div');
            div.className = 'custom-option';
            // [FIX] Use item.name
            div.textContent = item.name || ('CCTV ' + (i + 1));
            div.addEventListener('click', (e) => {
                e.stopPropagation();
                attachStreamToSlot(idx + 1, item, i);
                optionsContainer.classList.remove('active');
            });
            optionsContainer.appendChild(div);
        });

        // Initial Load for this Slot
        if (list[idx]) {
            attachStreamToSlot(idx + 1, list[idx], idx);
        } else {
            attachStreamToSlot(idx + 1, null, -1);
        }
    });
}
