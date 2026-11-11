"""Regression tests for the fifth prayer channel: The Family Altar (prayer5).

Registered in full capability parity with provisioned=False until the owner creates
@TheFamilyAltarDaily on YouTube and saves its separate Google Cloud credentials
(PRAYER5_YOUTUBE_* + PRAYER5_GEMINI_API_KEY).
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
from scripts.continuous_research import FAMILY_ALTAR_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"


class TestFifthChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve_to_prayer5(self):
        self.assertIn("prayer5", CHANNELS)
        ch = get_channel("prayer5")
        self.assertEqual(ch.display_name, "The Family Altar")
        self.assertEqual(ch.handle, "@TheFamilyAltarDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER5_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER5_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER5_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in ("prayer5", "family", "family-altar", "the-family-altar", "household", "channel5"):
            self.assertEqual(normalize_channel_id(alias), "prayer5")

    def test_provisioned_channel_is_active_in_scheduler_and_watchdog(self):
        ch = get_channel("prayer5")
        self.assertTrue(ch.provisioned)
        self.assertIn("prayer5", scheduled_channels())
        health_rows = {row["queue"]: row for row in queue_health()}
        self.assertIn("longform:prayer5", health_rows)
        self.assertIn("shorts:prayer5", health_rows)
        self.assertGreater(health_rows["longform:prayer5"]["ready"], 0)
        self.assertGreater(health_rows["shorts:prayer5"]["ready"], 0)


class TestFifthChannelIdentityAndVisuals(unittest.TestCase):
    def test_family_brand_forbids_all_four_sibling_channels_and_vice_versa(self):
        b5 = cc.brand_for("prayer5")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4"):
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, b5.forbidden_phrases)
            self.assertIn(other.handle, b5.forbidden_phrases)
            self.assertIn(b5.display_name, other.forbidden_phrases)
            self.assertIn(b5.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_family_altar_only(self):
        prompt = compile_full_brain_prompt("prayer5")
        self.assertIn("The Family Altar", prompt)
        self.assertIn("prayer5", prompt)
        for forbidden in (
            "The Secret Place",
            "The Morning Altar",
            "The Midday Watch",
            "The Midnight Watch",
            "@TheSecretPlace",
            "@TheMorningAltarDaily",
            "@TheMiddayWatch",
            "@TheMidnightWatchDaily",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_short_keys_are_namespaced_to_family(self):
        key = cc.short_key("prayer5", "joshua24v15")
        self.assertEqual(key, "short-familyjoshua24v15")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4"):
            self.assertNotEqual(key, cc.short_key(other_id, "joshua24v15"))

    def test_roadmap_has_30_unique_family_scriptures_in_0300_range(self):
        self.assertIs(ROADMAPS["prayer5"], FAMILY_ALTAR_ROADMAP)
        self.assertGreaterEqual(len(FAMILY_ALTAR_ROADMAP), 30)
        ids = [entry["id"] for entry in FAMILY_ALTAR_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0300")
        self.assertEqual(FAMILY_ALTAR_ROADMAP[0]["scripture"], "Joshua 24:15")
        self.assertEqual(FAMILY_ALTAR_ROADMAP[1]["scripture"], "Psalm 128:1-4")
        other_ids = {
            r["id"]
            for cid in ("secret-place", "prayer2", "prayer3", "prayer4")
            for r in roadmap_for_channel(cid)
        }
        self.assertFalse(other_ids & set(ids))

    def test_shorts_and_ctr_grades_use_dedicated_hearth_palette(self):
        self.assertEqual(shorts_poster.grade_for("prayer5"), "hearth")
        self.assertIn("hearth", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel("prayer5")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "hearth")
        self.assertEqual(variants[0].hero, "BLESS THIS HOME")
        self.assertEqual(variants[1].hero, "COVER MY FAMILY")
        self.assertIsNone(variants[2].hero)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "family-altar-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "family-altar-banner.png").size, (2560, 1440))
        wm = Image.open(MEDIA / "family-altar-watermark.png")
        self.assertEqual(wm.size, (150, 150))
        self.assertEqual(wm.mode, "RGBA")
        self.assertEqual(wm.getpixel((0, 0))[3], 0)
        self.assertEqual(Image.open(MEDIA / "family-altar-thumbnail-template.png").size, (1280, 720))


class TestFifthChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_prayer5_readiness_and_isolated_secrets(self):
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        comments = (ROOT / ".github/workflows/comments.yml").read_text(encoding="utf-8")
        metrics = (ROOT / ".github/workflows/metrics.yml").read_text(encoding="utf-8")
        monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
        growth = (ROOT / ".github/workflows/growth-autopilot.yml").read_text(encoding="utf-8")
        community = (ROOT / ".github/workflows/community.yml").read_text(encoding="utf-8")
        setup_doc = ROOT / "docs/FIFTH_CHANNEL_SETUP.md"

        self.assertTrue(setup_doc.is_file())
        self.assertIn("PRAYER5_READY", produce)
        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn('"prayer5":"PRAYER5_"', produce)
        self.assertIn("format('{0}GEMINI_API_KEY'", produce)

        self.assertIn("PRAYER5_READY", brain)
        self.assertIn("PRAYER5_GEMINI_API_KEY", brain)

        self.assertIn("PRAYER5_READY", comments)
        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", comments)

        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", metrics)
        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", monitor)
        self.assertIn("PRAYER5_GEMINI_API_KEY", monitor)
        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", growth)
        self.assertIn("PRAYER5_YOUTUBE_REFRESH_TOKEN", community)


if __name__ == "__main__":
    unittest.main()
