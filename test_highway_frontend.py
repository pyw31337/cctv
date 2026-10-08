"""Exercise the highway traffic matching code in js/app.js with Node.

The highway section is self-contained, so it is evaluated with small stubs
instead of a browser. Skipped when Node is not installed.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

APP_JS = (Path(__file__).resolve().parent / "js" / "app.js").read_text(encoding="utf-8")
MARKER = "// 10. Highway traffic"

SNAPSHOT = {
    "ok": True,
    "observed_at": "2026-07-21T15:30:00+09:00",
    "stale": False,
    "routes": [
        {"routeName": "경부선", "grade": 2, "avgSpeed": 62, "observed_at": "2026-07-21T15:30:00+09:00"},
        {"routeName": "서해안선", "grade": 1, "avgSpeed": 97, "observed_at": "2026-07-21T15:30:00+09:00"},
    ],
    "sections": [
        {"routeName": "경부선", "conzoneName": "서울TG-양재IC", "conzoneId": "0010CZE900", "grade": 3, "speed": 35,
         "observed_at": "2026-07-21T15:30:00+09:00", "directionCode": "S"},
        {"routeName": "경부선", "conzoneName": "양재IC-서울TG", "conzoneId": "0010CZS900", "grade": 1, "speed": 90,
         "observed_at": "2026-07-21T15:30:00+09:00", "directionCode": "E"},
        {"routeName": "용인서울선", "conzoneName": "고등IC-서판교IC", "conzoneId": "1710CZE010", "grade": 2, "speed": 48,
         "observed_at": "2026-07-21T15:30:00+09:00", "directionCode": "E"},
    ],
}

HARNESS = r"""
const PUBLIC_PROXY_BASE = 'https://proxy.example';
const NEAREST_RESULT_LIMIT = 100;
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { cctvData: [], nearestCctvs: [], center: { lat: 37.5, lng: 127 }, mode: 'video' };
const $ = () => null;
%(section)s
const snapshot = %(snapshot)s;
highwayTrafficState.data = snapshot;
highwayTrafficState.index = buildHighwayTrafficIndex(snapshot);
highwayTrafficState.fetchedAt = Date.now();
const badge = name => formatHighwayTrafficText(getHighwayTrafficForCctv({ name }));
console.log(JSON.stringify({
    parsed: parseHighwayCctvName('[경부선][부산]경부동탄터널(부산1)'),
    spaced: parseHighwayCctvName('[경부선] 서울TG'),
    localRoad: parseHighwayCctvName('[국도3호선] 어딘가'),
    cityRoad: parseHighwayCctvName('[금남로] 유동사거리'),
    sectionBadge: badge('[경부선] 서울TG'),
    suffixBadge: badge('[경부선]양재'),
    facilityBadge: badge('[용인서울선]고등IC서울'),
    routeBadge: badge('[경부선][부산]경부동탄터널(부산1)'),
    noData: badge('[중앙선]죽령터널'),
    nonHighway: getHighwayTrafficForCctv({ name: '서울역' }),
    html: buildHighwayTrafficBadgeHtml(getHighwayTrafficForCctv({ name: '[경부선] 서울TG' }))
}));
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class HighwayFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start = APP_JS.index(MARKER)
        script = HARNESS % {"section": APP_JS[start:], "snapshot": json.dumps(SNAPSHOT, ensure_ascii=False)}
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
        cls.out = json.loads(result.stdout.strip().splitlines()[-1])

    def test_names_are_parsed_by_route_prefix(self):
        self.assertEqual(self.out["parsed"]["route"], "경부선")
        self.assertEqual(self.out["parsed"]["point"], "경부동탄터널")
        self.assertEqual(self.out["spaced"]["pointKey"], "서울")
        self.assertIsNone(self.out["localRoad"])
        self.assertIsNone(self.out["cityRoad"])

    def test_section_match_shows_worst_direction_with_time(self):
        self.assertEqual(self.out["sectionBadge"], "정체 · 35km/h (7/21 15:30 기준)")
        self.assertEqual(self.out["suffixBadge"], "정체 · 35km/h (7/21 15:30 기준)")
        self.assertEqual(self.out["facilityBadge"], "서행 · 48km/h (7/21 15:30 기준)")

    def test_route_level_fallback(self):
        self.assertEqual(self.out["routeBadge"], "경부선 서행 · 평균 62km/h (7/21 15:30 기준)")

    def test_missing_data_hides_badge(self):
        self.assertEqual(self.out["noData"], "")
        self.assertIsNone(self.out["nonHighway"])

    def test_badge_html_has_no_direction_label(self):
        self.assertIn("tone-jam", self.out["html"])
        self.assertNotIn("상행", self.out["html"])
        self.assertNotIn("하행", self.out["html"])


if __name__ == "__main__":
    unittest.main()
