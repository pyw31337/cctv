import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import audit_world_tour_playability as audit
from scripts.audit_world_tour_playability import audit_priority, record_attempt, should_prune


class WorldTourPlayabilityHistoryTests(unittest.TestCase):
    def test_five_failed_checks_prune(self):
        now = dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc)
        history = {"cameras": {}}
        item = {"id": "failed", "title": "Failed", "playbackStatus": "source-only", "sourceOnly": True}
        for _ in range(5):
            record_attempt(history, item, now)
        self.assertTrue(should_prune(history, item, now))

    def test_one_success_prevents_pruning(self):
        now = dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc)
        history = {"cameras": {}}
        failed = {"id": "recovered", "playbackStatus": "source-only", "sourceOnly": True}
        for _ in range(4):
            record_attempt(history, failed, now)
        record_attempt(history, {"id": "recovered", "playbackStatus": "verified", "playUrl": "https://example.test/live.m3u8"}, now)
        self.assertFalse(should_prune(history, failed, now))

    def test_run_removes_only_after_fifth_failed_audit(self):
        item = {"id": "failed", "title": "Failed", "sourceType": "test", "playbackStatus": "source-only", "sourceOnly": True}
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "world.json"
            history_path = Path(tmp) / "history.json"
            data_path.write_text(json.dumps({"items": [item]}), encoding="utf-8")
            with patch.object(audit, "audit_item", side_effect=lambda value: dict(value)):
                for _ in range(4):
                    result = audit.run(data_path, history_path, max_workers=1)
                    self.assertEqual(result["items"], 1)
                result = audit.run(data_path, history_path, max_workers=1)
            self.assertEqual(result["items"], 0)
            self.assertEqual(result["removedAfterFiveFailedChecks"], 1)

    def test_near_threshold_failure_is_rechecked_before_lower_attempt_failure(self):
        now = dt.datetime.now(dt.timezone.utc)
        history = {"cameras": {}}
        near_threshold = {"id": "four", "title": "Four", "playbackStatus": "source-only", "sourceOnly": True}
        lower_attempt = {"id": "two", "title": "Two", "playbackStatus": "source-only", "sourceOnly": True}
        for _ in range(4):
            record_attempt(history, near_threshold, now)
        for _ in range(2):
            record_attempt(history, lower_attempt, now)
        self.assertLess(audit_priority(near_threshold, history), audit_priority(lower_attempt, history))


if __name__ == "__main__":
    unittest.main()
