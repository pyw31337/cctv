import unittest

from scripts.build_quality_summary_fallback import row_from_check_registry
from scripts.canary_probe import select_candidates, summarize_region
from scripts.ingest_gits import merge_gits_catalog
from scripts.adaptive_collection import browser_grid_signal, effective_interval, source_quality_signal


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


class AdaptiveQualityTests(unittest.TestCase):
    def test_low_sample_telemetry_does_not_overreact(self):
        signal = source_quality_signal({"sources": {"GITS": {"samples": 1, "failure_rate": 1}}}, "GITS")
        self.assertLess(signal["confidence"], 0.1)

    def test_repeated_runtime_failures_shorten_next_collection_interval(self):
        data = [{"id": "G1", "source": "GITS", "status": "active", "url": "same", "name": "G1", "lat": 1, "lng": 1}]
        record = {"last_snapshot": {"fingerprints": {"G1": {"url": "same", "name": "G1", "lat": 1, "lng": 1}}}}
        healthy = {"sources": {"GITS": {"samples": 30, "failure_rate": 0, "slow_rate": 0, "avg_first_frame_ms": 1000}}}
        unhealthy = {"sources": {"GITS": {"samples": 30, "failure_rate": 0.8, "slow_rate": 0.7, "avg_first_frame_ms": 11000}}}
        self.assertLess(effective_interval("gits_ingest", record, data, unhealthy), effective_interval("gits_ingest", record, data, healthy))

    def test_browser_canary_failure_shortens_full_refresh(self):
        data = [{"id": "G1", "source": "GITS", "status": "active", "url": "same", "name": "G1", "lat": 1, "lng": 1}]
        record = {"last_snapshot": {"count": 1, "fingerprints": {"G1": {"url": "same", "name": "G1", "lat": 1, "lng": 1}}}}
        healthy = {"browser_canary": {"summary": {"checked": 4, "passed": 4}, "results": []}}
        unhealthy = {"browser_canary": {"summary": {"checked": 4, "passed": 0}, "results": []}}
        self.assertEqual(browser_grid_signal(healthy)["failure_rate"], 0)
        self.assertLess(effective_interval("full_refresh", record, data, unhealthy), effective_interval("full_refresh", record, data, healthy))

    def test_stale_browser_canary_loses_scheduling_influence(self):
        stale = {
            "browser_canary": {
                "generated_at": "2020-01-01T00:00:00Z",
                "summary": {"checked": 4, "passed": 0},
            }
        }
        self.assertEqual(browser_grid_signal(stale)["confidence"], 0)


if __name__ == "__main__":
    unittest.main()
