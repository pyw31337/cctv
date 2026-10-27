import unittest
from datetime import datetime, timezone

from scripts.build_quality_policy import build_group_rollups, issue_group, score


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

    def test_low_sample_feed_is_evidence_collection_not_failure(self):
        key, issue, action = issue_group(
            {"source": "GITS", "region": "구리", "samples": 2, "success_rate": 0, "failure_rate": 1},
            "watch",
            45,
        )
        self.assertEqual(key, "GITS:구리:insufficient_evidence")
        self.assertEqual(issue, "insufficient_evidence")
        self.assertEqual(action, "collect_more_evidence")

    def test_failure_group_gets_fast_repair_cadence(self):
        key, issue, action = issue_group(
            {"source": "GITS", "region": "구리", "samples": 10, "success_rate": 0.2, "failure_rate": 0.8},
            "repair",
            20,
        )
        self.assertEqual(key, "GITS:구리:connection_failure")
        self.assertEqual(issue, "connection_failure")
        self.assertEqual(action, "reprobe_and_inspect_provider")

    def test_slow_group_is_separated_from_connection_failures(self):
        key, issue, action = issue_group(
            {"source": "UTIC", "region": "남양주", "samples": 20, "success_rate": 0.95, "failure_rate": 0.05, "slow_rate": 0.7, "avg_first_frame_ms": 14000},
            "watch",
            68,
        )
        self.assertEqual(key, "UTIC:남양주:slow_startup")
        self.assertEqual(issue, "slow_startup")
        self.assertEqual(action, "check_token_proxy_and_origin_latency")

    def test_group_rollup_contains_review_interval_and_camera_ids(self):
        groups, queue = build_group_rollups(
            {
                "cam-a": {"source": "NTIC", "region": "고속도로", "samples": 10, "success_rate": 0.1, "failure_rate": 0.9},
                "cam-b": {"source": "NTIC", "region": "고속도로", "samples": 10, "success_rate": 0.95, "failure_rate": 0.05},
            },
            datetime.now(timezone.utc),
        )
        self.assertIn("NTIC:고속도로:connection_failure", groups)
        group = groups["NTIC:고속도로:connection_failure"]
        self.assertEqual(group["review_interval_hours"], 6)
        self.assertIn("cam-a", group["camera_ids"])
        self.assertTrue(any(item["id"].startswith("group:") for item in queue))


if __name__ == "__main__":
    unittest.main()
