/**
 * CctvVisibilityEngine
 * Manages whether a CCTV item is eligible to be displayed on Kakao Map markers & search lists.
 * Ensures temporary 404 / manual_check cameras are NEVER arbitrarily deleted or hidden from map.
 */
window.CctvVisibilityEngine = {
    isVisibleOnMap(cctv) {
        if (!cctv) return false;
        const status = String(cctv.status || '').toLowerCase();
        return status !== 'disabled';
    }
};
