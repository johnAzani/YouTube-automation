"""Regression tests for the fourth prayer channel: The Midnight Watch (prayer4).

Registered in full capability parity with provisioned=False until the owner saves
its separate Google Cloud credentials (PRAYER4_YOUTUBE_* + PRAYER4_GEMINI_API_KEY).
While unprovisioned:
  * every capability, brand, equipment, roadmap, Short namespace, CTR grade, brand
    artwork, and workflow secret-mapping invariant holds identically to the three
    live channels;
  * scheduled_channels() and queue_health() exclude prayer4 so the supervisor and
    watchdog stay green instead of alerting on an unprovisioned channel.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image

from pipeline import channel_capabilities as cc
from pipeline import shorts_poster, thumbnail_ctr
from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
from pipeline.channels import CHANNELS, get_channel, normalize_channel_id, scheduled_channels
from scripts.automation_health import queue_health
from scripts.continuous_research import MIDNIGHT_WATCH_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"


class TestFourthChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve_to_prayer4(self):
        self.assertIn("prayer4", CHANNELS)
        ch = get_channel("prayer4")
        self.assertEqual(ch.display_name, "The Midnight Watch")
        self.assertEqual(ch.handle, "@TheMidnightWatchDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER4_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER4_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER4_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in ("prayer4", "midnight", "midnight-watch", "the-midnight-watch", "channel4"):
            self.assertEqual(normalize_channel_id(alias), "prayer4")

    def test_provisioned_channel_is_active_in_scheduler_and_watchdog(self):
        ch = get_channel("prayer4")
        self.assertTrue(ch.provisioned)
        self.assertIn("prayer4", scheduled_channels())
        health_rows = {row["queue"]: row for row in queue_health()}
        self.assertIn("longform:prayer4", health_rows)
        self.assertIn("shorts:prayer4", health_rows)
        self.assertGreater(health_rows["longform:prayer4"]["ready"], 0)
        self.assertGreater(health_rows["shorts:prayer4"]["ready"], 0)


class TestFourthChannelIdentityAndVisuals(unittest.TestCase):
    def test_midnight_brand_forbids_all_three_sibling_channels_and_vice_versa(self):
        b4 = cc.brand_for("prayer4")
        for other_id in ("secret-place", "prayer2", "prayer3"):
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, b4.forbidden_phrases)
            self.assertIn(other.handle, b4.forbidden_phrases)
            self.assertIn(b4.display_name, other.forbidden_phrases)
            self.assertIn(b4.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_midnight_watch_only(self):
        prompt = compile_full_brain_prompt("prayer4")
        self.assertIn("The Midnight Watch", prompt)
        self.assertIn("prayer4", prompt)
        for forbidden in (
            "The Secret Place",
            "The Morning Altar",
            "The Midday Watch",
            "@TheSecretPlace",
            "@TheMorningAltarDaily",
            "@TheMiddayWatch",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_short_keys_are_namespaced_to_midnight(self):
        key = cc.short_key("prayer4", "psalm119")
        self.assertEqual(key, "short-midnightpsalm119")
        for other_id in ("secret-place", "prayer2", "prayer3"):
            self.assertNotEqual(key, cc.short_key(other_id, "psalm119"))

    def test_roadmap_has_30_unique_midnight_scriptures_in_0200_range(self):
        self.assertIs(ROADMAPS["prayer4"], MIDNIGHT_WATCH_ROADMAP)
        self.assertGreaterEqual(len(MIDNIGHT_WATCH_ROADMAP), 30)
        ids = [entry["id"] for entry in MIDNIGHT_WATCH_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0200")
        self.assertEqual(MIDNIGHT_WATCH_ROADMAP[0]["scripture"], "Psalm 119:62")
        self.assertEqual(MIDNIGHT_WATCH_ROADMAP[1]["scripture"], "Acts 16:25-26")
        other_ids = {
            r["id"]
            for cid in ("secret-place", "prayer2", "prayer3")
            for r in roadmap_for_channel(cid)
        }
        self.assertFalse(other_ids & set(ids))

    def test_shorts_and_ctr_grades_use_dedicated_midnight_palette(self):
        self.assertEqual(shorts_poster.grade_for("prayer4"), "midnight")
        self.assertIn("midnight", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel("prayer4")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "midnight")
        self.assertEqual(variants[0].hero, "PRAY AT MIDNIGHT")
        self.assertEqual(variants[1].hero, "CHAINS MUST BREAK")
        self.assertIsNone(variants[2].hero)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "midnight-watch-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "midnight-watch-banner.png").size, (2560, 1440))
        wm = Image.open(MEDIA / "midnight-watch-watermark.png")
        self.assertEqual(wm.size, (150, 150))
        self.assertEqual(wm.mode, "RGBA")
        self.assertEqual(wm.getpixel((0, 0))[3], 0)
        self.assertEqual(Image.open(MEDIA / "midnight-watch-thumbnail-template.png").size, (1280, 720))


class TestFourthChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_prayer4_readiness_and_isolated_secrets(self):
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        comments = (ROOT / ".github/workflows/comments.yml").read_text(encoding="utf-8")
        metrics = (ROOT / ".github/workflows/metrics.yml").read_text(encoding="utf-8")
        monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
        setup_doc = ROOT / "docs/FOURTH_CHANNEL_SETUP.md"

        self.assertTrue(setup_doc.is_file())
        self.assertIn("PRAYER4_READY", produce)
        self.assertIn("PRAYER4_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn('"prayer4":"PRAYER4_"', produce)
        self.assertIn("format('{0}GEMINI_API_KEY'", produce)

        self.assertIn("PRAYER4_READY", brain)
        self.assertIn("PRAYER4_GEMINI_API_KEY", brain)

        self.assertIn("PRAYER4_READY", comments)
        self.assertIn("PRAYER4_YOUTUBE_REFRESH_TOKEN", comments)

        self.assertIn("PRAYER4_YOUTUBE_REFRESH_TOKEN", metrics)
        self.assertIn("PRAYER4_YOUTUBE_REFRESH_TOKEN", monitor)
        self.assertIn("PRAYER4_GEMINI_API_KEY", monitor)


if __name__ == "__main__":
    unittest.main()
