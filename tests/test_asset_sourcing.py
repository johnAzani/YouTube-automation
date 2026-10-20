"""Regression tests for clip-first ordering and full-frame aspect safety."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import assets
from pipeline.assemble import _contain_filter
from pipeline.config import CONFIG
from tools.deep_dive import SCRIPTS as DEEP_SCRIPTS
from tools.shorts import SCRIPTS as SHORT_SCRIPTS


class AssetSourcingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.openverse_key = CONFIG.enable_keyless_sources
        self.addCleanup(setattr, CONFIG, "enable_keyless_sources", self.openverse_key)
        CONFIG.enable_keyless_sources = True

    def test_moving_media_is_checked_before_any_photo_provider(self):
        calls = []
        clip = assets.Asset(Path(self.tmp.name) / "clip.mp4", "openverse", "https://example.invalid/clip",
                            "CC0", "video", "dam break", 1080, 1920)
        with patch.object(assets, "_pexels", side_effect=lambda q, video, w, h: calls.append(("pexels", video)) or None), \
             patch.object(assets, "_pixabay", side_effect=lambda q, video, w, h: calls.append(("pixabay", video)) or None), \
             patch.object(assets, "_openverse", side_effect=lambda q, video, w, h: calls.append(("openverse", video)) or (clip if video else None)), \
             patch.object(assets, "_wikimedia", return_value=None), \
             patch.object(assets, "_internet_archive", return_value=None), \
             patch.object(assets, "_nasa", return_value=None):
            result = assets.fetch_scene_assets("dam break", 1, Path(self.tmp.name), 1, 720, 1280, False)
        self.assertEqual(result[0].kind, "video")
        self.assertEqual(calls, [("pexels", True), ("pixabay", True), ("openverse", True)])

    def test_no_match_is_not_silently_replaced_with_a_title_card(self):
        with patch.object(assets, "_pexels", return_value=None), \
             patch.object(assets, "_pixabay", return_value=None), \
             patch.object(assets, "_openverse", return_value=None), \
             patch.object(assets, "_wikimedia", return_value=None), \
             patch.object(assets, "_internet_archive", return_value=None), \
             patch.object(assets, "_nasa", return_value=None):
            result = assets.fetch_scene_assets("no match", 2, Path(self.tmp.name), 1, 1280, 720, False)
        self.assertEqual(result, [])

    def test_render_filter_contains_without_crop_or_stretch(self):
        vf = _contain_filter()
        self.assertIn("force_original_aspect_ratio=decrease", vf)
        self.assertIn("pad=1280:720", vf)
        self.assertNotIn("crop=", vf)

    def test_every_authored_scene_has_a_real_photo_fail_safe(self):
        for scripts in (DEEP_SCRIPTS, SHORT_SCRIPTS):
            for cfg in scripts.values():
                for scene in cfg["scenes"]:
                    self.assertTrue((Path("image-search") / scene["img"]).is_file(), scene["img"])


if __name__ == "__main__":
    unittest.main()
