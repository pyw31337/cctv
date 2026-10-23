import datetime as dt
import unittest

from scripts.audit_world_tour_playability import record_attempt, should_prune


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


if __name__ == "__main__":
    unittest.main()
