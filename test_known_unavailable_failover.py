import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class KnownUnavailableFailoverTests(unittest.TestCase):
    def test_neobudaegyo_retains_hard_failure_evidence(self):
        cameras = json.loads((ROOT / "cctv_data.json").read_text(encoding="utf-8"))
        camera = next(item for item in cameras if item.get("id") == "E600016")
        self.assertEqual(camera.get("status"), "manual_check")
        self.assertIn("http_404", camera.get("health_reason", ""))

    def test_hard_failures_are_filtered_before_selection(self):
        app_js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function isKnownUnavailableCamera", app_js)
        self.assertIn("ranked.filter(cctv => !isKnownUnavailableCamera(cctv))", app_js)
        self.assertIn("정상 카메라로 자동 전환 중", app_js)

    def test_cache_version_forces_failover_release(self):
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn("20260622-auto-failover", index_html)
        self.assertIn("20260622-auto-failover", service_worker)


if __name__ == "__main__":
    unittest.main()
