import re
import unittest
from pathlib import Path


APP_JS = (Path(__file__).resolve().parent / "js" / "app.js").read_text(encoding="utf-8")


def function_body(name):
    match = re.search(rf"\nfunction {name}\([^)]*\) \{{\n(.*?)\n\}}\n", APP_JS, re.S)
    assert match, f"{name} not found in js/app.js"
    return match.group(1)


class FrontendPlaybackResilienceTests(unittest.TestCase):
    """Guards for behaviour a 9/1 merge once dropped by taking one side of app.js wholesale."""

    def test_same_scene_backups_apply_to_every_source(self):
        body = function_body("ensureDynamicBackups")
        self.assertIn("findSameSceneBackups(cctv, knownUrls)", body)
        # The Jeju-only list may stay, but must not gate the same-scene step.
        before_same_scene = body.split("findSameSceneBackups", 1)[0]
        self.assertNotIn("return;\n", before_same_scene.split("_dynamicFallbacksAdded) return;", 1)[1])
        self.assertIn("backupUrls.concat(sameSceneBackups, nearbyBackups)", body)

    def test_same_scene_match_is_name_and_distance_bounded(self):
        body = function_body("findSameSceneBackups")
        self.assertIn("normalizeCctvSceneName(item.name) === sceneName", body)
        self.assertIn("SAME_SCENE_BACKUP_RADIUS_KM", body)
        self.assertRegex(APP_JS, r"const SAME_SCENE_BACKUP_RADIUS_KM = 0\.08;")

    def test_camera_selection_is_remembered_per_place(self):
        update = function_body("updateNearestCctvs")
        self.assertIn("applySelectionHysteresis(localAware, lat, lng)", update)
        self.assertIn("rememberSelection(selection, state.nearestCctvs, lat, lng)", update)
        self.assertRegex(APP_JS, r"const STICKY_SELECTION_TTL_MS = 30 \* 24 \* 60 \* 60 \* 1000;")
        self.assertIn("localStorage.setItem(STICKY_SELECTION_STORAGE_KEY", function_body("writeStickySelectionStore"))

    def test_dragging_the_map_cannot_overwrite_a_searched_place(self):
        body = function_body("getStickyLocationKey")
        self.assertIn("STICKY_KEYWORD_RADIUS_KM", body)
        self.assertIn("state.keyword", body)


if __name__ == "__main__":
    unittest.main()
