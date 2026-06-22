import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class ServiceStatusBannerTests(unittest.TestCase):
    def test_banner_markup_is_not_rendered(self):
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('id="service-status-banner"', index_html)

    def test_region_maintenance_message_is_absent(self):
        app_js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("현재 지역 점검 중", app_js)
        self.assertNotIn("품질이 일시적으로 흔들릴 수 있습니다", app_js)

    def test_cache_version_forces_updated_shell(self):
        index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        service_worker = (ROOT / "sw.js").read_text(encoding="utf-8")
        app_version = re.search(r'js/app\.js\?v=([^"\']+)', index_html)
        cache_version = re.search(r"CACHE_VERSION = 'v([^']+)'", service_worker)
        self.assertIsNotNone(app_version)
        self.assertIsNotNone(cache_version)
        self.assertEqual(app_version.group(1), cache_version.group(1))


if __name__ == "__main__":
    unittest.main()
