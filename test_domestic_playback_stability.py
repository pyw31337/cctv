import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def _distance_km(a_lat, a_lng, b_lat, b_lng):
    radius = 6371
    p1 = math.radians(a_lat)
    p2 = math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lng - a_lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def test_service_status_banner_is_removed_from_home_screen():
    app = _read("js/app.js")
    index = _read("index.html")
    css = _read("css/style.css")
    sw = _read("sw.js")

    assert 'id="service-status-banner"' not in index
    assert "현재 지역 장애" not in app
    assert "현재 지역 점검 중" not in app
    assert "점검 정보 지연" not in app
    assert "js/app.js?v=20260618-no-region-status-popup" in index
    assert "sw.js?v=20260618-no-region-status-popup" in index
    assert "v20260618-no-region-status-popup" in sw
    assert re.search(
        r"function\s+renderServiceStatusBanner\(\)\s*{\s*removeLegacyServiceStatusBanner\(\);\s*}",
        app,
    )
    assert "document.querySelectorAll('#service-status-banner, .service-status-banner')" in app
    assert "#service-status-banner,\n.service-status-banner" in css
    assert "display: none !important" in css


def test_hrfco_popup_failover_covers_encoded_urls_and_nearby_sources():
    app = _read("js/app.js")
    dynamic_backup_block = re.search(
        r"function\s+ensureDynamicBackups\(cctv\)\s*{.*?function\s+normalizeBackupEntry",
        app,
        re.S,
    ).group(0)

    assert "safeDecodeUrlText" in app
    assert "getHrfcoPopupRequestUrl" in app
    assert "isHrfcoPopupUrl(url) || isHrfcoPopupUrl(originalPlaybackUrl)" in app
    assert "reason || 'hrfco-popup-unavailable'" in app
    assert "'HRFCO'" in dynamic_backup_block
    assert "'GITS', 'SPATIC'" in dynamic_backup_block


def test_neobudaegyo_has_verified_nearby_replacement_pool():
    data = json.loads(_read("cctv_data.json"))
    source = next(item for item in data if item.get("id") == "E600016")
    assert source["name"] == "서울시(너부대교)"
    assert source["url"].startswith("https://hrfco.go.kr/sumun/cctvPopup.do")

    nearby = [
        item for item in data
        if item.get("id") != source["id"]
        and item.get("source") in {"GITS", "SPATIC"}
        and item.get("url")
        and _distance_km(source["lat"], source["lng"], item.get("lat", 0), item.get("lng", 0)) <= 2
    ]

    assert nearby
