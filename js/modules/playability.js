/**
 * CctvPlayabilityEngine
 * Determines whether a CCTV stream is genuinely playable for failover candidate selection.
 * Isolates playback health from map visibility.
 */
window.CctvPlayabilityEngine = {
    isPlayableCandidate(cctv) {
        if (!cctv) return false;
        if (window.CctvVisibilityEngine && !window.CctvVisibilityEngine.isVisibleOnMap(cctv)) return false;

        const status = String(cctv.status || '').toLowerCase();
        const reason = String(cctv.health_reason || cctv.disabled_reason || cctv.status_note || '').toLowerCase();

        if (status === 'manual_check' && /(?:http[_ -]?(?:404|410)|maintenance|점검|no[_ -]?stream|stream[_ -]?missing|not[_ -]?found|invalid[_ -]?(?:url|stream))/.test(reason)) {
            return false;
        }

        if (typeof window.isUnsupportedBrowserStream === 'function' && window.isUnsupportedBrowserStream(cctv)) {
            return false;
        }

        return true;
    }
};
