import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class NavigationMenuTests(unittest.TestCase):
    def test_bottom_bar_keeps_search_and_single_menu_entry(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="app-menu-trigger"', html)
        self.assertIn('id="app-menu-backdrop"', html)
        self.assertNotIn('id="segment-control"', html)
        self.assertNotIn('id="highway-btn"', html)
        self.assertNotIn('id="weather-btn"', html)

    def test_menu_exposes_the_product_priority_order(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for action in ("video", "map", "highway", "world", "weather", "location"):
            self.assertIn(f'data-menu-action="{action}"', html)

    def test_actions_reuse_existing_feature_entry_points(self):
        app_js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function setupAppMenu()", app_js)
        self.assertIn("if (action === 'highway') openHighwayPanel();", app_js)
        self.assertIn("if (action === 'world') openWorldTourFromMenu();", app_js)
        self.assertIn("if (action === 'weather') openWeatherFromMenu();", app_js)

    def test_open_menu_owns_the_full_viewport(self):
        css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
        app_js = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn("z-index: 2100", css)
        self.assertIn("body.app-menu-open #header", css)
        self.assertIn("document.body.classList.toggle('app-menu-open', isOpen)", app_js)

    def test_icon_and_manifest_urls_have_a_release_cache_key(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        manifest = (ROOT / "site.webmanifest").read_text(encoding="utf-8")
        self.assertIn("favicon-16x16.png?v=20261023-menu-ui-1", html)
        self.assertIn("favicon-32x32.png?v=20261023-menu-ui-1", html)
        self.assertIn("site.webmanifest?v=20261023-menu-ui-1", html)
        self.assertIn("android-chrome-192x192.png?v=20261023-menu-ui-1", manifest)


if __name__ == "__main__":
    unittest.main()
