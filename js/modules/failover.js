/**
 * GridFailoverController & Toast Notification UI
 * Controls centralized geofenced grid failovers (4.5km max radius) and active panel de-duplication.
 */
window.GridFailoverController = {
    MAX_GEODISTANCE_KM: 4.5,

    getActiveGridCctvIds() {
        const activeIds = new Set();
        const videos = document.querySelectorAll('.video-panel video, #video-frame video');
        videos.forEach(video => {
            const id = video.dataset.activeCctvId || (video._activeCctv && video._activeCctv.id);
            if (id) activeIds.add(id);
        });
        const panels = document.querySelectorAll('.video-panel');
        panels.forEach(panel => {
            if (panel._activeCctv && panel._activeCctv.id) {
                activeIds.add(panel._activeCctv.id);
            }
        });
        return activeIds;
    },

    findFailoverCandidate(currentCctv) {
        if (!currentCctv) return null;

        const state = window.state || {};
        if (!state.failedSessionCams) {
            state.failedSessionCams = new Set();
        }

        const list = Array.isArray(state.nearestCctvs) ? state.nearestCctvs : [];
        const idx = list.findIndex(item => item && item.id === currentCctv.id);
        const activeGridIds = this.getActiveGridCctvIds();

        const currentLat = Number(currentCctv.lat) || Number(state.center?.lat) || 37.5665;
        const currentLng = Number(currentCctv.lng) || Number(state.center?.lng) || 126.9780;

        const isFailed = (id) => state.failedSessionCams.has(id);
        const isNotDuplicate = (id) => id !== currentCctv.id && !activeGridIds.has(id);

        const isGeofencedAndPlayable = (item) => {
            if (!item || (window.CctvPlayabilityEngine && !window.CctvPlayabilityEngine.isPlayableCandidate(item))) return false;
            const itemLat = Number(item.lat);
            const itemLng = Number(item.lng);
            if (!Number.isFinite(itemLat) || !Number.isFinite(itemLng)) return false;

            const distKm = typeof window.getDistance === 'function' 
                ? window.getDistance(currentLat, currentLng, itemLat, itemLng)
                : Math.sqrt((itemLat - currentLat)**2 + (itemLng - currentLng)**2) * 111;
            return distKm <= this.MAX_GEODISTANCE_KM;
        };

        // 1st stage: search in nearest list for non-duplicate, geofenced, playable candidate
        if (idx !== -1) {
            for (let offset = 1; offset < list.length; offset += 1) {
                const candidate = list[(idx + offset) % list.length];
                if (candidate && !isFailed(candidate.id) && isNotDuplicate(candidate.id) && isGeofencedAndPlayable(candidate)) {
                    return candidate;
                }
            }
        } else {
            const found = list.find(item => item && !isFailed(item.id) && isNotDuplicate(item.id) && isGeofencedAndPlayable(item));
            if (found) return found;
        }

        // 2nd stage: search in full cctvData for closest geofenced, playable candidate
        if (Array.isArray(state.cctvData) && state.cctvData.length > 0) {
            const candidates = state.cctvData
                .filter(item => item && !isFailed(item.id) && isNotDuplicate(item.id) && isGeofencedAndPlayable(item))
                .map(item => ({ 
                    item, 
                    distKm: typeof window.getDistance === 'function' 
                        ? window.getDistance(currentLat, currentLng, Number(item.lat), Number(item.lng))
                        : Math.sqrt((Number(item.lat) - currentLat)**2 + (Number(item.lng) - currentLng)**2) * 111
                }))
                .sort((a, b) => a.distKm - b.distKm);

            if (candidates.length > 0) {
                return candidates[0].item;
            }
        }

        // 3rd stage: relax de-duplication filter within geofence if grid is full
        if (idx !== -1) {
            for (let offset = 1; offset < list.length; offset += 1) {
                const candidate = list[(idx + offset) % list.length];
                if (candidate && candidate.id !== currentCctv.id && !isFailed(candidate.id) && isGeofencedAndPlayable(candidate)) {
                    return candidate;
                }
            }
        } else {
            const found = list.find(item => item && item.id !== currentCctv.id && !isFailed(item.id) && isGeofencedAndPlayable(item));
            if (found) return found;
        }

        // 4th stage: cycle back within geofence after clearing session failures
        state.failedSessionCams.clear();
        if (idx !== -1) {
            for (let offset = 1; offset < list.length; offset += 1) {
                const candidate = list[(idx + offset) % list.length];
                if (candidate && candidate.id !== currentCctv.id && isGeofencedAndPlayable(candidate)) return candidate;
            }
        }
        return list.find(item => item && item.id !== currentCctv.id && isGeofencedAndPlayable(item)) || null;
    }
};

window.showFailoverNoticeToast = function(panel, nextCctv, prevCctv) {
    if (!panel || !nextCctv) return;
    const existing = panel.querySelector('.failover-notice-toast');
    if (existing) existing.remove();

    let distStr = '';
    if (prevCctv && prevCctv.lat && prevCctv.lng && nextCctv.lat && nextCctv.lng) {
        const getDist = typeof window.getDistance === 'function' ? window.getDistance : null;
        if (getDist) {
            const distM = Math.round(getDist(prevCctv.lat, prevCctv.lng, nextCctv.lat, nextCctv.lng) * 1000);
            if (distM > 0) distStr = `${distM}m `;
        }
    }

    const toast = document.createElement('div');
    toast.className = 'failover-notice-toast';
    toast.style.cssText = 'position:absolute; bottom:12px; left:50%; transform:translateX(-50%); z-index:40; background:rgba(15,23,42,0.88); backdrop-filter:blur(8px); border:1px solid rgba(59,130,246,0.4); color:#93c5fd; padding:6px 14px; border-radius:20px; font-size:12px; font-weight:600; box-shadow:0 4px 12px rgba(0,0,0,0.3); pointer-events:none; transition:opacity 0.4s ease; opacity:0; text-align:center; white-space:nowrap;';
    toast.innerHTML = `<span style="color:#60a5fa; margin-right:4px;">↺</span>인근 ${distStr}<strong>[${nextCctv.name}]</strong> 영상으로 우회 연결되었습니다`;

    panel.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 3800);
};
