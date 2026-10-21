"""Regression tests for clip-first ordering and full-frame aspect safety."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from pipeline import assets
from pipeline.assemble import _contain_filter
from pipeline.config import CONFIG
from pipeline.run import _validate_finance_niche
from pipeline.script_doc import ScriptDoc
from tools.deep_dive import SCRIPTS as DEEP_SCRIPTS
from tools.shorts import SCRIPTS as SHORT_SCRIPTS


class AssetSourcingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.openverse_key = CONFIG.enable_keyless_sources
        self.addCleanup(setattr, CONFIG, "enable_keyless_sources", self.openverse_key)
        CONFIG.enable_keyless_sources = True

    def test_automation_rejects_nonfinance_niche(self):
        history = ScriptDoc(path=Path("draft.md"), meta={"id": "history-1", "niche": "history"})
        finance = ScriptDoc(path=Path("finance.md"), meta={"id": "finance-1", "niche": "finance and business"})
        with self.assertRaisesRegex(RuntimeError, "finance, business, markets, or economics only"):
            _validate_finance_niche(history)
        _validate_finance_niche(finance)

    def test_moving_media_is_checked_before_any_photo_provider(self):
        calls = []
        clip = assets.Asset(Path(self.tmp.name) / "clip.mp4", "wikimedia", "https://example.invalid/clip",
                            "CC0", "video", "dam break", 1080, 1920)
        with patch.object(assets, "_pexels", side_effect=lambda q, video, w, h: calls.append(("pexels", video)) or None), \
             patch.object(assets, "_pixabay", side_effect=lambda q, video, w, h: calls.append(("pixabay", video)) or None), \
             patch.object(assets, "_openverse", side_effect=lambda q, video, w, h: calls.append(("openverse", video)) or None), \
             patch.object(assets, "_wikimedia", side_effect=lambda q, video, w, h: calls.append(("wikimedia", video)) or (clip if video else None)), \
             patch.object(assets, "_internet_archive", side_effect=lambda q, video, w, h: calls.append(("archive", video)) or None), \
             patch.object(assets, "_nasa", side_effect=lambda q, video, w, h: calls.append(("nasa", video)) or None):
            result = assets.fetch_scene_assets("dam break", 1, Path(self.tmp.name), 1, 720, 1280, False)
        self.assertEqual(result[0].kind, "video")
        # video providers first; Openverse is photos-only (no /v1/videos/ endpoint)
        self.assertEqual(calls, [("pexels", True), ("pixabay", True), ("wikimedia", True)])
        self.assertTrue(all(video for _, video in calls), "no photo provider may run before moving media is found")

    def test_wikimedia_prefers_the_rendered_thumbnail_over_the_original_file(self):
        # Commons originals are often 100+ MB TIFFs (size cap / timeout deaths);
        # the 1920px thumburl is what the pipeline should actually download.
        page = {"title": "File:Ledger.tif",
                "imageinfo": [{"url": "https://upload.wikimedia.org/wikipedia/commons/l/ledger-huge.tif",
                               "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/l/ledger-huge.tif/1920px-ledger-huge.tif.jpg",
                               "mime": "image/tiff", "width": 8000, "height": 6000,
                               "descriptionurl": "https://commons.wikimedia.org/wiki/File:Ledger.tif",
                               "extmetadata": {"LicenseShortName": {"value": "Public domain"},
                                               "Artist": {"value": "Library of Congress"}}}]}

        class FakeResp:
            def json(self):
                return {"query": {"pages": {"1": page}}}

        downloaded = []
        with patch.object(assets, "_http_get", return_value=FakeResp()), \
             patch.object(assets, "_download", side_effect=lambda url, dest: downloaded.append(url) or True):
            got = assets._wikimedia("accounting ledger documents", False, 1280, 720)
        self.assertIsNotNone(got)
        self.assertEqual(downloaded, ["https://upload.wikimedia.org/wikipedia/commons/thumb/l/ledger-huge.tif/1920px-ledger-huge.tif.jpg"])
        self.assertTrue(got.license_note.startswith("Wikimedia Commons — Public domain"))

    def test_no_match_is_not_silently_replaced_with_a_title_card(self):
        with patch.object(assets, "_pexels", return_value=None), \
             patch.object(assets, "_pixabay", return_value=None), \
             patch.object(assets, "_openverse", return_value=None), \
             patch.object(assets, "_wikimedia", return_value=None), \
             patch.object(assets, "_internet_archive", return_value=None), \
             patch.object(assets, "_nasa", return_value=None):
            result = assets.fetch_scene_assets("no match", 2, Path(self.tmp.name), 1, 1280, 720, False)
        self.assertEqual(result, [])
        # A failed scene must leave a self-diagnosing report behind, not just "no match":
        report = Path(self.tmp.name) / "sourcing-attempts.json"
        self.assertTrue(report.is_file(), "sourcing-attempts.json must be written on failure")
        rows = json.loads(report.read_text(encoding="utf-8"))["2"]
        providers = {r["provider"] for r in rows}
        self.assertIn("Pexels video", providers)   # video-first phase ran
        self.assertIn("NASA photo", providers)     # photo phase ran to the end
        self.assertTrue(all(r["status"] != "ok" for r in rows))
        summary = assets.attempts_summary(2, Path(self.tmp.name))
        self.assertIn("attempts:", summary)
        self.assertIn("Wikimedia photo=", summary)

    def test_missing_api_key_is_reported_as_skipped_not_as_a_miss(self):
        # Real key providers (no network — they return before any HTTP call) but the
        # keyless ones are stubbed so the test stays hermetic.
        with patch.object(CONFIG, "pexels_api_key", ""), \
             patch.object(CONFIG, "pixabay_api_key", ""), \
             patch.object(assets, "_openverse", return_value=None), \
             patch.object(assets, "_wikimedia", return_value=None), \
             patch.object(assets, "_internet_archive", return_value=None), \
             patch.object(assets, "_nasa", return_value=None):
            result = assets.fetch_scene_assets("no key", 7, Path(self.tmp.name), 1, 1280, 720, False)
        self.assertEqual(result, [])
        rows = json.loads((Path(self.tmp.name) / "sourcing-attempts.json").read_text(encoding="utf-8"))["7"]
        by_provider = {r["provider"]: r for r in rows}
        self.assertEqual(by_provider["Pexels video"]["status"], "skipped")
        self.assertEqual(by_provider["Pexels video"]["detail"], "no API key")
        self.assertEqual(by_provider["Pixabay photo"]["status"], "skipped")
        # keyed-but-no-key must not be confused with a provider that searched and missed
        self.assertNotEqual(by_provider["Wikimedia photo"]["status"], "skipped")

    def test_cache_path_resolves_into_the_asset_cache_dir(self):
        # Regression: this used to read CONFIG.ASSET_CACHE_DIR, which never
        # existed on Config — every provider that reached caching crashed and
        # the failure masqueraded as "no licensed match" (MAINTENANCE.md §3).
        with patch.object(assets, "ASSET_CACHE_DIR", Path(self.tmp.name)):
            path = assets._cache_path("testsource", "ident", "jpg")
        self.assertEqual(path.parent, Path(self.tmp.name))
        self.assertTrue(path.name.startswith("testsource_"))
        self.assertTrue(path.parent.is_dir())

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
