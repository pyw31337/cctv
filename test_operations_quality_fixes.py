import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.build_quality_summary_fallback import row_from_check_registry
from scripts.canary_probe import SimpleResponse, resolve_probe_url, select_candidates, summarize_region, verify_hls_segment
from scripts.ingest_gits import merge_gits_catalog
from scripts.adaptive_collection import TASKS, browser_grid_signal, effective_interval, source_quality_signal
from scripts.renew_cctv_urls import kbs_renewal_candidates, kbs_token_expires_soon, quality_repair_candidates
from cctv_runtime import NAMYANGJU_GOLDEN_STREAMS


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


class NamyangjuMappingTests(unittest.TestCase):
    def test_rokone_and_maseok_use_distinct_verified_streams(self):
        data = json.loads((Path(__file__).parent / "cctv_data.json").read_text(encoding="utf-8"))
        by_id = {item.get("id"): item for item in data}
        self.assertEqual(NAMYANGJU_GOLDEN_STREAMS["L180074"][1], "L180188")
        self.assertEqual(NAMYANGJU_GOLDEN_STREAMS["L180076"][1], "L180009")
        self.assertIn("/L180188/", by_id["L180074"]["url"])
        self.assertIn("/L180009/", by_id["L180076"]["url"])


class CanarySelectionTests(unittest.TestCase):
    REGION = {"key": "test", "label": "Test", "lat": 37.5, "lng": 127.0, "radius_km": 30, "max_candidates": 4, "min_ok": 1}

    def test_review_cameras_do_not_crowd_out_active_candidates(self):
        cameras = [
            {"id": "bad", "name": "near", "source": "UTIC", "status": "manual_check", "lat": 37.5, "lng": 127.0},
            {"id": "good", "name": "near", "source": "GITS", "status": "active", "lat": 37.51, "lng": 127.0},
        ]
        selected = select_candidates(cameras, self.REGION)
        self.assertEqual([item["id"] for item in selected], ["good"])

    def test_pinned_customer_cameras_are_probed_even_when_marked_for_review(self):
        cameras = [
            {"id": "locked", "name": "locked", "source": "UTIC", "status": "manual_check", "lat": 37.5, "lng": 127.0},
            {"id": "good", "name": "good", "source": "GITS", "status": "active", "lat": 37.51, "lng": 127.0},
        ]
        region = {**self.REGION, "pinned_ids": ["locked"]}
        selected = select_candidates(cameras, region)
        self.assertEqual(selected[0]["id"], "locked")

    def test_verified_fallback_keeps_service_status_green(self):
        candidates = [{"id": "ok"}, {"id": "bad"}]
        results = [
            {"id": "ok", "ok": True, "elapsed_ms": 100},
            {"id": "bad", "ok": False, "category": "not_found", "source": "UTIC"},
        ]
        summary = summarize_region(self.REGION, candidates, results)
        self.assertEqual(summary["status"], "OK")
        self.assertEqual(summary["severity"], "ok")

    def test_shared_resolver_outage_is_recorded_once_for_the_region(self):
        candidates = [{"id": "one"}, {"id": "two"}]
        results = [
            {"id": "one", "ok": False, "category": "network_error", "source": "UTIC", "resolver": "oracle_z3"},
            {"id": "two", "ok": False, "category": "network_error", "source": "UTIC", "resolver": "oracle_z3"},
        ]
        summary = summarize_region({**self.REGION, "key": "jindo"}, candidates, results)
        self.assertEqual(summary["shared_incident"]["code"], "SHARED_RESOLVER_OUTAGE")
        self.assertIn("공통 해석 경로", summary["recommended_action"])

    def test_kbs_canary_probes_the_fresh_signed_url_not_legacy_oracle_resolver(self):
        camera = {"id": "KBS_9957", "source": "KBS", "original_id": "9957", "url": "https://kbs.example/live.m3u8?token=fresh"}
        url, resolver, _ = resolve_probe_url(camera, {})
        self.assertEqual(url, camera["url"])
        self.assertEqual(resolver, "direct_kbs_signed")


class HlsSegmentProbeTests(unittest.TestCase):
    def test_hls_probe_requires_a_current_media_segment(self):
        responses = [
            (SimpleResponse(200, {"Content-Type": "application/vnd.apple.mpegurl"}, "https://example.test/master.m3u8"), b"#EXTM3U\nvariant.m3u8\n"),
            (SimpleResponse(200, {"Content-Type": "application/vnd.apple.mpegurl"}, "https://example.test/variant.m3u8"), b"#EXTM3U\n#EXTINF:2,\nlatest.ts\n"),
            (SimpleResponse(200, {"Content-Type": "video/mp2t"}, "https://example.test/latest.ts"), b"G" * 512),
        ]
        with patch("scripts.canary_probe.read_probe_prefix", side_effect=responses):
            ok, category, _, meta = verify_hls_segment("https://example.test/master.m3u8")

        self.assertTrue(ok)
        self.assertEqual(category, "ok_hls_segment")
        self.assertEqual(meta["bytes"], 512)

    def test_hls_probe_rejects_manifest_when_latest_segment_is_unavailable(self):
        responses = [
            (SimpleResponse(200, {"Content-Type": "application/vnd.apple.mpegurl"}, "https://example.test/live.m3u8"), b"#EXTM3U\n#EXTINF:2,\nmissing.ts\n"),
            (SimpleResponse(404, {"Content-Type": "text/plain"}, "https://example.test/missing.ts"), b"not found"),
        ]
        with patch("scripts.canary_probe.read_probe_prefix", side_effect=responses):
            ok, category, _, meta = verify_hls_segment("https://example.test/live.m3u8")

        self.assertFalse(ok)
        self.assertEqual(category, "hls_segment_error")
        self.assertEqual(meta["http_status"], 404)

    def test_hls_probe_accepts_another_recent_segment_during_playlist_rotation(self):
        responses = [
            (SimpleResponse(200, {"Content-Type": "application/vnd.apple.mpegurl"}, "https://example.test/live.m3u8"), b"#EXTM3U\n#EXTINF:2,\nprevious.ts\n#EXTINF:2,\nrotating.ts\n"),
            (SimpleResponse(404, {"Content-Type": "text/plain"}, "https://example.test/rotating.ts"), b"not found"),
            (SimpleResponse(200, {"Content-Type": "video/mp2t"}, "https://example.test/previous.ts"), b"G" * 512),
        ]
        with patch("scripts.canary_probe.read_probe_prefix", side_effect=responses):
            ok, category, _, _ = verify_hls_segment("https://example.test/live.m3u8")

        self.assertTrue(ok)
        self.assertEqual(category, "ok_hls_segment")


class AdaptiveQualityTests(unittest.TestCase):
    def test_quality_reprobe_actions_reach_safe_utic_url_refresh(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as handle:
            json.dump({"items": [
                {"id": "UTIC_BAD", "action": "reprobe_and_inspect_provider"},
                {"id": "UTIC_SLOW", "action": "check_token_proxy_and_origin_latency"},
                {"id": "group:UTIC:서울:connection_failure", "action": "reprobe_and_inspect_provider"},
                {"id": "UTIC_OLD", "action": "maintain_cadence"},
            ]}, handle)
            handle.flush()
            data = {
                "UTIC_BAD": {"id": "UTIC_BAD", "source": "UTIC"},
                "UTIC_SLOW": {"id": "UTIC_SLOW", "source": "UTIC"},
                "UTIC_OLD": {"id": "UTIC_OLD", "source": "UTIC"},
            }
            self.assertEqual(quality_repair_candidates(data, handle.name), ["UTIC_BAD", "UTIC_SLOW"])

    def test_kbs_tokens_are_scheduled_before_they_expire(self):
        self.assertIn("kbs_renew", TASKS)
        self.assertTrue(kbs_token_expires_soon("https://example.test/live.m3u8?wowzatokenendtime=100", now=100))
        self.assertFalse(kbs_token_expires_soon("https://example.test/live.m3u8?wowzatokenendtime=999999", now=100, within_seconds=60))
        candidates = kbs_renewal_candidates({
            "KBS_1": {"source": "KBS", "url": "https://example.test/live.m3u8?wowzatokenendtime=100"},
            "UTIC_1": {"source": "UTIC", "url": "https://example.test/live.m3u8?wowzatokenendtime=100"},
        }, now=100)
        self.assertEqual(candidates, ["KBS_1"])

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
