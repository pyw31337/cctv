import os
import unittest
from unittest.mock import patch

from collectors.pipeline import merge_cctv_item, normalize_cctv_record, refine_cctv_data
from cctv_runtime import (
    apply_camera_id_aliases,
    apply_namyangju_golden_mappings,
    validate_namyangju_golden_mappings,
    validate_stream_identity,
    validate_stream_mapping_registry,
    validate_unique_playback_streams,
)


class PipelineNormalizationTests(unittest.TestCase):
    def test_verified_namyangju_mapping_is_applied_and_validated(self):
        items = [{
            "id": "L180075",
            "name": "마석사거리(웹)",
            "source": "UTIC",
            "url": "https://211.57.45.101/media/L180054/chunklist.m3u8",
        }]

        self.assertTrue(validate_namyangju_golden_mappings(items))
        apply_namyangju_golden_mappings(items)
        self.assertEqual(items[0]["url"].split("/media/")[1].split("/")[0], "L180111")
        self.assertEqual(validate_namyangju_golden_mappings(items), [])

    def test_wrong_camera_stream_is_rejected(self):
        items = [{
            "id": "L180076",
            "name": "마석윗3",
            "source": "UTIC",
            "url": "https://211.57.45.101/media/L180233/chunklist.m3u8",
        }]

        errors = validate_namyangju_golden_mappings(items, require_all=True)
        self.assertTrue(any("L180076" in error and "L180009" in error for error in errors))

    def test_locked_registry_rejects_catalog_identity_drift(self):
        item = {"id": "L180074", "name": "마석사거리(웹)", "source": "UTIC", "lat": 37.65, "lng": 127.30,
                "url": "https://211.57.45.101/media/L180188/chunklist.m3u8"}
        self.assertTrue(any("name mismatch" in error for error in validate_stream_mapping_registry([item])))

    def test_duplicate_playback_stream_is_rejected(self):
        items = [{"id": "L180074", "url": "https://211.57.45.101/media/L180188/chunklist.m3u8"},
                 {"id": "L180999", "url": "https://211.57.45.101/media/L180188/chunklist.m3u8"}]
        self.assertEqual(len(validate_unique_playback_streams(items)), 1)

    def test_utic_url_camera_id_mismatch_is_rejected(self):
        items = [{
            "id": "L933066",
            "source": "UTIC",
            "url": "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?cctvid=L933067",
        }]

        self.assertEqual(len(validate_stream_identity(items)), 1)
        self.assertEqual(apply_camera_id_aliases(items), 1)
        self.assertEqual(items[0]["id"], "L933067")
        self.assertEqual(validate_stream_identity(items), [])

    def test_normalize_cctv_record_fills_stable_identity_fields(self):
        item = normalize_cctv_record({
            "name": "서울역",
            "lat": 37.556,
            "lng": 126.972,
            "source": "utic",
            "original_id": "L12345",
        })

        self.assertEqual(item["source"], "UTIC")
        self.assertEqual(item["source_id"], "L12345")
        self.assertEqual(item["canonical_id"], "UTIC:L12345")
        self.assertTrue(item["id"])
        self.assertEqual(item["original_id"], "L12345")

    def test_merge_uses_canonical_identity_for_duplicates(self):
        first = {
            "name": "서울역",
            "lat": 37.556,
            "lng": 126.972,
            "source": "UTIC",
            "original_id": "L12345",
            "url": "https://example.com/a.m3u8",
        }
        second = {
            "name": "서울역",
            "lat": 37.556,
            "lng": 126.972,
            "source": "UTIC",
            "original_id": "L12345",
            "url": "https://example.com/b.m3u8",
        }

        merged = []
        self.assertEqual(merge_cctv_item(merged, first), "added")
        self.assertEqual(merge_cctv_item(merged, second), "added_backup")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["canonical_id"], "UTIC:L12345")

    def test_refine_injects_utic_key_only_for_probe(self):
        observed_urls = []

        class Response:
            status_code = 404

        def fake_get(url, **kwargs):
            observed_urls.append(url)
            return Response()

        item = {
            "id": "UTIC:L12345",
            "source": "UTIC",
            "url": "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?cctvid=L12345",
        }
        with patch.dict(os.environ, {"UTIC_API_KEY": "probe-only-secret"}), patch(
            "collectors.pipeline.requests.get", side_effect=fake_get
        ):
            refine_cctv_data([item], max_workers=1, delay_seconds=0)

        self.assertEqual(len(observed_urls), 1)
        self.assertIn("key=probe-only-secret", observed_urls[0])
        self.assertNotIn("probe-only-secret", item["url"])


def _scan_merge(batches, priority_map=None):
    """Reference: the original quadratic merge (a full scan per camera)."""
    merged, all_stats = [], {}
    for name, data in batches:
        stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in data:
            result = merge_cctv_item(merged, item, priority_map=priority_map)
            stats[result] = stats.get(result, 0) + 1
        all_stats[name] = stats
    return merged, all_stats


class IndexedMergeEquivalenceTests(unittest.TestCase):
    def _random_batches(self, rng, count):
        sources = ["UTIC", "NTIC", "GITS", "BUSAN_ITS", "KBS"]
        base_lat, base_lng = 37.5, 127.0
        batches = []
        for source in sources:
            items = []
            for _ in range(count):
                lat = base_lat + rng.choice([0, 0.0005, 0.0019, 0.002, 0.0021, 0.004]) * rng.choice([-1, 1]) + rng.random() * 0.01
                lng = base_lng + rng.choice([0, 0.0015, 0.002, 0.0025]) * rng.choice([-1, 1]) + rng.random() * 0.01
                item = {
                    "source": rng.choice([source, source, rng.choice(sources)]),
                    "name": f"cam{rng.randrange(40)}",
                    "lat": lat,
                    "lng": lng,
                    "url": rng.choice([f"https://h/{rng.randrange(60)}.m3u8", f"https://h/{rng.randrange(60)}.jsp"]),
                }
                if rng.random() < 0.7:
                    item["id"] = f"ID{rng.randrange(80)}"
                roll = rng.random()
                if roll < 0.03:
                    item["lat"] = None
                elif roll < 0.05:
                    item["lat"] = "not-a-number"
                elif roll < 0.06:
                    item["lng"] = float("nan")
                elif roll < 0.07:
                    del item["lng"]
                elif roll < 0.10:
                    item["lat"] = f"{lat:.6f}"  # string coordinates are accepted
                items.append(item)
            batches.append((source, items))
        return batches

    def test_indexed_merge_matches_full_scan(self):
        import copy
        import io
        import random
        from contextlib import redirect_stdout

        from collectors.pipeline import merge_named_batches

        for seed in range(40):
            rng = random.Random(seed)
            batches = self._random_batches(rng, 60)
            expected, expected_stats = _scan_merge(copy.deepcopy(batches))
            merged = []
            with redirect_stdout(io.StringIO()):
                stats = merge_named_batches(merged, copy.deepcopy(batches))
            self.assertEqual(merged, expected, f"seed {seed}")
            self.assertEqual(stats, expected_stats, f"seed {seed}")


if __name__ == "__main__":
    unittest.main()
