import unittest

from scripts.build_quality_summary_fallback import row_from_check_registry
from scripts.canary_probe import select_candidates, summarize_region
from scripts.ingest_gits import merge_gits_catalog


class GitsDeltaMergeTests(unittest.TestCase):
    def test_missing_gits_ids_are_preserved_for_recheck(self):
        existing = [
            {"id": "OTHER", "source": "UTIC"},
            {"id": "GITS_A", "source": "GITS", "status": "active", "url": "old-a"},
            {"id": "GITS_B", "source": "GITS", "status": "active", "url": "old-b"},
        ]
        fresh = [
            {"id": "GITS_B", "source": "GITS", "url": "new-b"},
            {"id": "GITS_C", "source": "GITS", "url": "new-c"},
        ]

        merged, stats = merge_gits_catalog(existing, fresh, "2026-06-22T00:00:00Z")
        by_id = {item["id"]: item for item in merged}

        self.assertEqual(set(by_id), {"OTHER", "GITS_A", "GITS_B", "GITS_C"})
        self.assertEqual(by_id["GITS_B"]["url"], "new-b")
        self.assertEqual(by_id["GITS_A"]["status"], "manual_check")
        self.assertIn("stream_missing", by_id["GITS_A"]["health_reason"])
        self.assertEqual(stats, {"fresh": 2, "retained": 1, "new": 1, "updated": 1})


class QualityEvidenceTests(unittest.TestCase):
    def test_cumulative_rechecks_are_not_collapsed_to_one_sample(self):
        row = row_from_check_registry(
            "CAM_1",
            {
                "check_count": 12,
                "success_count": 10,
                "failure_count": 2,
                "last_ok": True,
                "source": "GITS",
            },
            {"id": "CAM_1", "source": "GITS"},
        )

        self.assertEqual(row["samples"], 12)
        self.assertEqual(row["direct_playable_samples"], 12)
        self.assertEqual(row["success"], 10)
        self.assertEqual(row["failure"], 2)


class CanarySelectionTests(unittest.TestCase):
    REGION = {"key": "test", "label": "Test", "lat": 37.5, "lng": 127.0, "radius_km": 30, "max_candidates": 4, "min_ok": 1}

    def test_review_cameras_do_not_crowd_out_active_candidates(self):
        cameras = [
            {"id": "bad", "name": "near", "source": "UTIC", "status": "manual_check", "lat": 37.5, "lng": 127.0},
            {"id": "good", "name": "near", "source": "GITS", "status": "active", "lat": 37.51, "lng": 127.0},
        ]
        selected = select_candidates(cameras, self.REGION)
        self.assertEqual([item["id"] for item in selected], ["good"])

    def test_verified_fallback_keeps_service_status_green(self):
        candidates = [{"id": "ok"}, {"id": "bad"}]
        results = [
            {"id": "ok", "ok": True, "elapsed_ms": 100},
            {"id": "bad", "ok": False, "category": "not_found", "source": "UTIC"},
        ]
        summary = summarize_region(self.REGION, candidates, results)
        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["severity"], "ok")


if __name__ == "__main__":
    unittest.main()
