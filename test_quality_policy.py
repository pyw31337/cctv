import unittest
from datetime import datetime, timezone

from scripts.build_quality_policy import score


class QualityPolicyTests(unittest.TestCase):
    def test_reliable_high_resolution_feed_is_preferred(self):
        value, confidence, tier, action = score({
            "samples": 30, "success_rate": .97, "failure_rate": .03,
            "avg_first_frame_ms": 1800, "avg_width": 1920, "avg_height": 1080,
            "updated_at": "2026-10-23T12:00:00Z",
        }, datetime(2026, 10, 23, 13, tzinfo=timezone.utc))
        self.assertGreaterEqual(value, 75)
        self.assertEqual(confidence, 100)
        self.assertEqual(tier, "preferred")
        self.assertIsNone(action)

    def test_repeated_failures_are_repaired_not_deleted(self):
        value, confidence, tier, action = score({
            "samples": 12, "success_rate": .2, "failure_rate": .8,
            "updated_at": "2026-10-23T12:00:00Z",
        }, datetime(2026, 10, 23, 13, tzinfo=timezone.utc))
        self.assertLess(value, 50)
        self.assertGreater(confidence, 0)
        self.assertEqual(tier, "repair")
        self.assertEqual(action, "probe_stream")


if __name__ == "__main__":
    unittest.main()
