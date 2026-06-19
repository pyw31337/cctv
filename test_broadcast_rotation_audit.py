import datetime as dt
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scripts.rotate_broadcast_audit as audit


def test_compute_budget_covers_catalog_within_window():
    assert audit.compute_budget(19814, window_hours=48, schedule_hours=4) == 1652
    assert audit.compute_budget(2424, window_hours=48, schedule_hours=4) == 202


def test_select_due_items_prefers_never_checked_then_failed_stale():
    now = dt.datetime(2026, 6, 19, tzinfo=dt.timezone.utc)
    items = [
        {"id": "fresh_ok", "source": "A"},
        {"id": "stale_failed", "source": "A"},
        {"id": "never", "source": "A"},
    ]
    state = {
        "local:fresh_ok": {"checkedAt": "2026-06-18T23:00:00Z", "ok": True, "status": "manifest_ok"},
        "local:stale_failed": {"checkedAt": "2026-06-01T00:00:00Z", "ok": False, "status": "timeout"},
    }

    selected = audit.select_due_items("local", items, state, 2, now)

    assert [item["id"] for item in selected] == ["never", "stale_failed"]


def test_local_url_candidates_deduplicates_primary_and_backups():
    item = {
        "url": "https://example.com/a.m3u8",
        "directUrl": "https://example.com/a.m3u8",
        "backup_urls": [{"url": "https://example.com/b.m3u8"}, "https://example.com/b.m3u8"],
    }

    assert audit.local_url_candidates(item) == [
        ("direct", "https://example.com/a.m3u8"),
        ("backup_1", "https://example.com/b.m3u8"),
    ]


def test_global_source_html_page_is_source_page_ok():
    def fake_probe(url, timeout):
        return False, "html_not_video", "html_response", 12

    with patch.object(audit, "probe_url", fake_probe):
        key, result = audit.audit_target(
            audit.AuditTarget(
                "global",
                {"id": "source-only", "title": "Source", "sourceType": "demo", "sourceUrl": "https://example.com/cam"},
                1.0,
            )
        )

    assert key == "global:source-only"
    assert result["ok"] is True
    assert result["status"] == "source_page_ok"


def test_dry_run_does_not_write_output():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        local_path = tmp_path / "local.json"
        global_path = tmp_path / "global.json"
        output_path = tmp_path / "status.json"
        local_path.write_text('[{"id":"local-a","url":"https://example.com/a.m3u8","source":"TEST"}]', encoding="utf-8")
        global_path.write_text('{"items":[{"id":"global-a","sourceUrl":"https://example.com/cam","sourceType":"TEST"}]}', encoding="utf-8")

        def fake_audit_target(target):
            return audit.camera_key(target.scope, target.item), {
                "checkedAt": "2026-06-19T00:00:00Z",
                "scope": target.scope,
                "name": "ok",
                "source": "TEST",
                "ok": True,
                "status": "manifest_ok",
                "reason": "test",
                "elapsedMs": 1,
            }

        args = Namespace(
            local_data=local_path,
            global_data=global_path,
            output=output_path,
            window_hours=48,
            schedule_hours=4,
            local_budget=1,
            global_budget=1,
            workers=1,
            timeout=1.0,
            dry_run=True,
        )

        with patch.object(audit, "audit_target", fake_audit_target):
            result = audit.run(args)

        assert result["summary"]["checkedThisRun"] == 2
        assert not Path(output_path).exists()


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")


if __name__ == "__main__":
    main()
