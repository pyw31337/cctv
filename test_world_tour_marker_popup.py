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
    assert app_js.index("if (cam.playUrl) return cam.playUrl;") < app_js.index("if (cam.embedUrl && !isWorldTourEmbedBlocked")
    offenders = [
        item for item in items
        if str(item.get("sourceType", "")).lower() == "hdontap"
        and (item.get("sourceOnly") or (not item.get("playUrl") and not item.get("videoId")))
    ]
    assert offenders == []
    hdotap_health = world_tour["collectionMeta"]["sourceTypeHealth"]["hdontap"]
    assert hdotap_health["total"] == hdotap_health["verified"] == 20
    assert hdotap_health["externalOnly"] == 0


def test_click_only_marker_popup_cache_bust_is_deployed():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_js = (ROOT / "sw.js").read_text(encoding="utf-8")

    assert "js/app.js?v=20260618-remove-refused-originals" in index_html
    assert "sw.js?v=20260618-remove-refused-originals" in index_html
    assert "v20260618-remove-refused-originals" in sw_js


if __name__ == "__main__":
    test_world_tour_circle_marker_popup_opens_on_click_only()
    test_source_only_world_tour_markers_are_red_and_direct_to_source()
    test_refused_hdontap_originals_are_removed_and_hls_is_preferred()
    test_click_only_marker_popup_cache_bust_is_deployed()
    print("world tour marker popup tests passed")
