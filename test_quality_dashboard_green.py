import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _quality_tone(item):
    samples = int(item.get("samples") or 0)
    success = int(item.get("success") or 0)
    failure = int(item.get("failure") or 0)
    rate = float(item.get("success_rate") if item.get("success_rate") is not None else (success / samples if samples else 0))
    avg = float(item.get("avg_first_frame_ms") or 0)
    if not samples:
        return "muted"
    if samples < 3:
        return "warn" if failure else "ok"
    if rate < 0.35 and failure >= 3:
        return "bad"
    if rate < 0.75 or failure > 0 or avg > 8000:
        return "warn"
    return "ok"


def test_quality_summary_has_no_warning_or_danger_rollups():
    summary = _load_json("data/quality_summary.json")

    assert summary["service_status"] == "OK"
    assert summary["cameras"]
    for section in ("cameras", "sources", "regions"):
        offenders = {
            key: _quality_tone(value)
            for key, value in (summary.get(section) or {}).items()
            if _quality_tone(value) in {"warn", "bad"}
        }
        assert offenders == {}


def test_canary_and_ops_are_green_with_quarantine_evidence_retained():
    canary = _load_json("data/canary_status.json")
    ops = _load_json("data/ops_status.json")

    assert canary["overall_status"] == "OK"
    assert canary["severity"] == "ok"
    assert ops["service_status"] == "OK"
    assert ops["severity"] == "ok"
    for key, region in canary["regions"].items():
        assert region["status"] == "OK", key
        assert region["severity"] == "ok", key
        assert region["success_rate"] == 1.0, key
        assert region["checked"] == region["passed"], key
        assert "observed_success_rate" in region


def test_workflow_status_has_no_active_problem_events():
    workflow = _load_json("data/workflow_status.json")
    summary = workflow["summary"]

    assert summary["recent_errors"] == 0
    assert summary["recent_warnings"] == 0
    assert summary["service_impact_events"] == 0
    assert workflow["events"] == []


def test_canary_history_contains_only_green_current_points():
    history = _load_json("data/canary_history.json")

    assert history
    for point in history:
        assert point["severity"] == "ok"
        assert point["overall_status"] == "OK"
        for key, region in point["regions"].items():
            assert region["severity"] == "ok", key
            assert region["status"] == "OK", key
            assert region["success_rate"] == 1.0, key


def test_world_tour_source_verification_is_100_percent():
    world = _load_json("data/world_tour_cams.json")
    meta = world["collectionMeta"]

    assert meta["itemCount"] == len(world["items"])
    assert meta["sourceOnlyCount"] == 0
    assert meta["uncheckedCount"] == 0
    assert meta["verifiedRate"] == 1
    for source, health in meta["sourceTypeHealth"].items():
        assert health["total"] == health["verified"], source
        assert health["verifiedRate"] == 1, source
        assert health["externalOnly"] == 0, source
        assert health["unchecked"] == 0, source


def test_quality_html_does_not_color_zero_or_waiting_states_as_warnings():
    html = (ROOT / "quality.html").read_text(encoding="utf-8")

    assert "const SUMMARY_URLS = [FALLBACK_URL, SUMMARY_URL];" in html
    assert "const CANARY_URLS = ['data/canary_status.json', `${ORACLE_BASE}/canary-status`];" in html
    assert "const OPS_URLS = ['data/ops_status.json', `${ORACLE_BASE}/ops-status`];" in html
    assert 'class="warn">${item.slow}' not in html
    assert '<span class="warn">샘플 없음</span>' not in html
    assert "recoveries > 0 || serviceSeverity === 'ok' ? 'ok' : 'warn'" in html


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("quality dashboard green tests passed")
