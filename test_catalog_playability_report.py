import unittest
from scripts.build_catalog_playability_report import domestic_report, world_report

class CatalogPlayabilityReportTests(unittest.TestCase):
    def test_domestic_requires_measured_success_for_strict_count(self):
        result = domestic_report([{"id": "ok", "source": "TEST", "url": "https://example.test/a.m3u8"}, {"id": "unknown", "source": "TEST", "url": "player.html"}], {"cameras": {"ok": {"samples": 3, "success_rate": .9, "failure_rate": .1}}})
        self.assertEqual(result["native_or_proxy_candidate"], 1); self.assertEqual(result["recently_verified_in_app"], 1); self.assertEqual(result["strict_removed_if_verified_only"], 1)
    def test_world_strict_count_keeps_only_verified_in_app_entries(self):
        result = world_report({"items": [{"playbackStatus": "verified", "playUrl": "https://example.test/a.m3u8"}, {"playbackStatus": "source-only", "sourceOnly": True}, {"playbackStatus": "unchecked", "embedUrl": "https://example.test/embed"}]})
        self.assertEqual(result["strict_in_app_playable"], 1); self.assertEqual(result["strict_removed_if_in_app_only"], 2)

if __name__ == "__main__": unittest.main()
