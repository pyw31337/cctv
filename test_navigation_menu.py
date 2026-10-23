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


if __name__ == "__main__":
    unittest.main()
