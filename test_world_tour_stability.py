import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "world_tour_cams.json"
APP_JS_PATH = ROOT / "js" / "app.js"
INDEX_PATH = ROOT / "index.html"
AUDIT_PATH = ROOT / "scripts" / "audit_world_tour_playability.py"

STILL_IMAGE_URL_RE = re.compile(r"\.(?:jpe?g|png|webp|gif)(?:[?#]|$)", re.I)
STILL_IMAGE_ONLY_SOURCE_TYPES = {"hktraffic", "usgsvolcano"}


def _world_tour_items():
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return payload, payload["items"]


def _is_still_image_url(value):
    return bool(STILL_IMAGE_URL_RE.search(str(value or "").strip()))


def _has_playable_video_field(item):
    return bool(item.get("videoId")) or any(
        item.get(key) and not _is_still_image_url(item.get(key))
        for key in ("embedUrl", "playUrl")
    )


def _is_still_image_only_item(item):
    source_type = str(item.get("sourceType") or "").lower()
    has_still_media = any(
        _is_still_image_url(item.get(key))
        for key in ("sourceUrl", "snapshotUrl", "embedUrl", "playUrl")
    )
    return (has_still_media or source_type in STILL_IMAGE_ONLY_SOURCE_TYPES) and not _has_playable_video_field(item)


def test_world_tour_data_excludes_still_image_only_sources():
    payload, items = _world_tour_items()
    offenders = [item["id"] for item in items if _is_still_image_only_item(item)]

    assert payload["collectionMeta"]["itemCount"] == len(items)
    assert offenders == []
    assert not any(item.get("sourceType") in STILL_IMAGE_ONLY_SOURCE_TYPES for item in items)
    assert "usgsvolcano-amchitka-aht" not in {item.get("id") for item in items}


def test_world_tour_data_is_verified_app_playback_only():
    payload, items = _world_tour_items()
    meta = payload["collectionMeta"]

    assert items
    assert meta["sourceOnlyCount"] == 0
    assert meta["uncheckedCount"] == 0
    assert meta["verifiedRate"] == 1
    assert all(item.get("playbackStatus") == "verified" for item in items)
    assert not any(item.get("sourceOnly") for item in items)
    assert all(_has_playable_video_field(item) for item in items)

    for source, health in meta["sourceTypeHealth"].items():
        assert health["total"] == health["verified"], source
        assert health["verifiedRate"] == 1, source
        assert health["externalOnly"] == 0, source
        assert health["unchecked"] == 0, source


def test_world_tour_filter_preserves_country_selection_contract():
    app_js = APP_JS_PATH.read_text(encoding="utf-8")
    index_html = INDEX_PATH.read_text(encoding="utf-8")

    assert "js/app.js?v=20260618-no-region-status-popup" in index_html
    assert "const preserveListFilters = options.preserveListFilters === true;" in app_js
    assert "if (!selectedFromVisible && selectedFromAll && !preserveListFilters)" in app_js
    assert "preserveListFilters: true" in app_js
    assert "state.worldTourListCountry = selectedFromAll.country || 'All';" in app_js


def test_world_tour_marker_popup_opens_on_click_only():
    app_js = APP_JS_PATH.read_text(encoding="utf-8")
    marker_block = re.search(
        r"visibleCams\.forEach\(cam => \{.*?worldTourLeafletMarkers\.push\(marker\);",
        app_js,
        re.S,
    ).group(0)

    assert ".on('click', () => marker.openPopup())" in marker_block
    assert ".on('mouseover'" not in marker_block
    assert ".on('mouseenter'" not in marker_block
    assert "setTimeout(() => marker.openPopup()" not in marker_block


def test_world_tour_external_toggle_uses_clear_action_labels():
    app_js = APP_JS_PATH.read_text(encoding="utf-8")

    assert "앱 재생만" in app_js
    assert "전체 보기" in app_js
    assert "원본사이트 전용 영상을 숨기고 앱 재생 가능한 영상만 보기" in app_js


def test_world_tour_audit_prunes_still_images_before_rotating_audit():
    audit_script = AUDIT_PATH.read_text(encoding="utf-8")

    assert "raw_items = payload.get('items', [])" in audit_script
    assert "items = [item for item in raw_items if not world.is_snapshot_only_item(item)]" in audit_script
    assert "world.is_user_facing_world_tour_item(item)" in audit_script
    assert "stillImageOnlyRemovedThisRun" in audit_script
    assert "appPlaybackRemovedThisRun" in audit_script


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("world tour stability tests passed")
