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


def test_click_only_marker_popup_cache_bust_is_deployed():
    index_html = (ROOT / "index.html").read_text(encoding="utf-8")
    sw_js = (ROOT / "sw.js").read_text(encoding="utf-8")

    assert "js/app.js?v=20260618-click-only-marker-popup" in index_html
    assert "sw.js?v=20260618-click-only-marker-popup" in index_html
    assert "v20260618-click-only-marker-popup" in sw_js


if __name__ == "__main__":
    test_world_tour_circle_marker_popup_opens_on_click_only()
    test_click_only_marker_popup_cache_bust_is_deployed()
    print("world tour marker popup tests passed")
