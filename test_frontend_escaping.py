import re
import unittest
from pathlib import Path


APP_JS = (Path(__file__).resolve().parent / "js" / "app.js").read_text(encoding="utf-8")


class FrontendEscapingTests(unittest.TestCase):
    def test_url_and_third_party_values_are_escaped_before_innerhtml(self):
        # ?name= share-link params, reverse-geocoded addresses and Kakao POI
        # names are attacker-controllable and must never reach innerHTML raw.
        for raw in ("${state.keyword}", "${addressName}", "${place.place_name}",
                    "${place.address_name || ''}", "${nextCctv.name}", "${parsedTitle.main}"):
            self.assertNotIn(raw, APP_JS)

    def test_single_shared_escape_helper(self):
        self.assertIn("function escapeHtml(value)", APP_JS)
        self.assertIsNone(re.search(r"const escape = s =>", APP_JS))


if __name__ == "__main__":
    unittest.main()
