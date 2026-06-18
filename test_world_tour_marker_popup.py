import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_world_tour_circle_marker_popup_opens_on_click_only():
    app_js = (ROOT / "js/app.js").read_text(encoding="utf-8")
    marker_block = re.search(
        r"visibleCams\.forEach\(cam => \{.*?worldTourLeafletMarkers\.push\(marker\);",
        app_js,
        re.S,
    )

    assert marker_block, "world tour marker block not found"
    marker_code = marker_block.group(0)
    assert ".on('click', () => marker.openPopup())" in marker_code
    assert ".on('mouseover'" not in marker_code
    assert ".on('mouseenter'" not in marker_code
    assert "setTimeout(() => marker.openPopup()" not in marker_code


def test_source_only_world_tour_markers_are_red_and_direct_to_source():
    app_js = (ROOT / "js/app.js").read_text(encoding="utf-8")

    assert "WORLD_TOUR_SOURCE_ONLY_MARKER" in app_js
    assert "fillColor: '#ef4444'" in app_js
    assert "color: '#991b1b'" in app_js
    assert "getWorldTourMarkerStyle(cam, isSelected)" in app_js
    assert "const sourceOnly = !canPlayWorldTourInApp(cam);" in app_js
    assert "const primaryLabel = sourceOnly ? '원본보기' : '영상보기';" in app_js
    assert "window.open(cam.sourceUrl, '_blank', 'noopener,noreferrer')" in app_js


def test_refused_hdontap_originals_are_removed_and_hls_is_preferred():
    app_js = (ROOT / "js/app.js").read_text(encoding="utf-8")
    world_tour = json.loads((ROOT / "data/world_tour_cams.json").read_text(encoding="utf-8"))
    items = world_tour["items"]

    assert "function isWorldTourRejectedOriginalOnlyCam(cam)" in app_js
    assert ".filter(item => !isWorldTourRejectedOriginalOnlyCam(item))" in app_js
    assert app_js.index("if (cam.playUrl) return getWorldTourPlayableStreamUrl(cam.playUrl);") < app_js.index("if (cam.embedUrl && !isWorldTourEmbedBlocked")
    offenders = [
        item for item in items
        if str(item.get("sourceType", "")).lower() == "hdontap"
        and (item.get("sourceOnly") or (not item.get("playUrl") and not item.get("videoId")))
    ]
    assert offenders == []
    hdotap_health = world_tour["collectionMeta"]["sourceTypeHealth"]["hdontap"]
    assert hdotap_health["total"] == hdotap_health["verified"] == 20
    assert hdotap_health["externalOnly"] == 0


def test_world_tour_http_hls_is_proxied_for_https_pages():
    app_js = (ROOT / "js/app.js").read_text(encoding="utf-8")
    build_py = (ROOT / "scripts/build_world_tour_cams.py").read_text(encoding="utf-8")
    world_tour = json.loads((ROOT / "data/world_tour_cams.json").read_text(encoding="utf-8"))

    assert "function getWorldTourPlayableStreamUrl(url)" in app_js
    assert "isWorldTourHlsUrl(value)) return proxyWithOracle(value);" in app_js
    assert "WORLD_TOUR_HTTP_HLS_PROXY_BASE" in build_py
    assert "'directPlaybackStatus'] = 'proxied_hls' if hls_url != raw_hls_url else 'direct_hls'" in build_py

    raw_hls = [
        (item.get("id"), key, item.get(key))
        for item in world_tour["items"]
        for key in ("playUrl", "embedUrl")
        if isinstance(item.get(key), str)
        and item[key].startswith("http://")
        and ".m3u8" in item[key].lower()
    ]
    assert raw_hls == []

    ongjin = [item for item in world_tour["items"] if item.get("sourceType") == "ongjin"]
    assert ongjin
    assert all(item.get("playUrl", "").startswith("https://158.179.194.163.sslip.io/proxy?url=") for item in ongjin)
    assert all(item.get("directPlaybackStatus") == "proxied_hls" for item in ongjin)


def test_world_tour_header_switch_is_next_to_close_button():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "js/app.js").read_text(encoding="utf-8")
    style_css = (ROOT / "css/style.css").read_text(encoding="utf-8")

    assert '<div id="world-tour-header-switch" class="world-tour-header-switch"' in index_html
    assert index_html.index('id="world-tour-header-switch"') < index_html.index('id="weather-close"')
    assert "$('#world-tour-header-switch')?.addEventListener('click'" in app_js
    assert "function updateWorldTourHeaderSwitch(selected = null)" in app_js
    assert "function switchWorldTourViewMode(viewMode)" in app_js
    assert "updateWorldTourHeaderSwitch(selected);" in app_js
    assert "updateWorldTourHeaderSwitch(null);" in app_js
    assert ".world-tour-header-switch" in style_css
    assert ".world-tour-header-switch .world-tour-mode-switch" in style_css
    assert "--world-tour-action-height: 38px;" in style_css
    assert "background: #31c690;" in style_css


def test_click_only_marker_popup_cache_bust_is_deployed():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_js = (ROOT / "sw.js").read_text(encoding="utf-8")

    assert "js/app.js?v=20260618-header-pill-switch" in index_html
    assert "sw.js?v=20260618-header-pill-switch" in index_html
    assert "v20260618-header-pill-switch" in sw_js


if __name__ == "__main__":
    test_world_tour_circle_marker_popup_opens_on_click_only()
    test_source_only_world_tour_markers_are_red_and_direct_to_source()
    test_refused_hdontap_originals_are_removed_and_hls_is_preferred()
    test_world_tour_http_hls_is_proxied_for_https_pages()
    test_world_tour_header_switch_is_next_to_close_button()
    test_click_only_marker_popup_cache_bust_is_deployed()
    print("world tour marker popup tests passed")
