"""Regression tests for the sixth prayer channel: The Healing Balm (prayer6).

Registered in full capability parity with provisioned=False until the owner creates
@TheHealingBalmDaily on YouTube and saves its separate Google Cloud credentials
(PRAYER6_YOUTUBE_* + PRAYER6_GEMINI_API_KEY).
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
from scripts.continuous_research import HEALING_BALM_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"


class TestSixthChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve_to_prayer6(self):
        self.assertIn("prayer6", CHANNELS)
        ch = get_channel("prayer6")
        self.assertEqual(ch.display_name, "The Healing Balm")
        self.assertEqual(ch.handle, "@TheHealingBalmDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER6_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER6_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER6_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in ("prayer6", "healing", "healing-balm", "the-healing-balm", "restoration", "channel6"):
            self.assertEqual(normalize_channel_id(alias), "prayer6")

    def test_provisioned_channel_is_active_in_scheduler_and_watchdog(self):
        ch = get_channel("prayer6")
        self.assertTrue(ch.provisioned)
        self.assertIn("prayer6", scheduled_channels())
        health_rows = {row["queue"]: row for row in queue_health()}
        self.assertIn("longform:prayer6", health_rows)
        self.assertIn("shorts:prayer6", health_rows)
        self.assertGreater(health_rows["longform:prayer6"]["ready"], 0)
        self.assertGreater(health_rows["shorts:prayer6"]["ready"], 0)


class TestSixthChannelIdentityAndVisuals(unittest.TestCase):
    def test_healing_brand_forbids_all_five_sibling_channels_and_vice_versa(self):
        b6 = cc.brand_for("prayer6")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5"):
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, b6.forbidden_phrases)
            self.assertIn(other.handle, b6.forbidden_phrases)
            self.assertIn(b6.display_name, other.forbidden_phrases)
            self.assertIn(b6.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_healing_balm_only(self):
        prompt = compile_full_brain_prompt("prayer6")
        self.assertIn("The Healing Balm", prompt)
        self.assertIn("prayer6", prompt)
        for forbidden in (
            "The Secret Place",
            "The Morning Altar",
            "The Midday Watch",
            "The Midnight Watch",
            "The Family Altar",
            "@TheSecretPlace",
            "@TheMorningAltarDaily",
            "@TheMiddayWatch",
            "@TheMidnightWatchDaily",
            "@TheFamilyAltarDaily",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_short_keys_are_namespaced_to_healing(self):
        key = cc.short_key("prayer6", "jeremiah30v17")
        self.assertEqual(key, "short-healingjeremiah30v17")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5"):
            self.assertNotEqual(key, cc.short_key(other_id, "jeremiah30v17"))

    def test_roadmap_has_30_unique_healing_scriptures_in_0400_range(self):
        self.assertIs(ROADMAPS["prayer6"], HEALING_BALM_ROADMAP)
        self.assertGreaterEqual(len(HEALING_BALM_ROADMAP), 30)
        ids = [entry["id"] for entry in HEALING_BALM_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0400")
        self.assertEqual(HEALING_BALM_ROADMAP[0]["scripture"], "Jeremiah 30:17")
        self.assertEqual(HEALING_BALM_ROADMAP[1]["scripture"], "Psalm 103:1-5")
        other_ids = {
            r["id"]
            for cid in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5")
            for r in roadmap_for_channel(cid)
        }
        self.assertFalse(other_ids & set(ids))

    def test_shorts_and_ctr_grades_use_dedicated_balm_palette(self):
        self.assertEqual(shorts_poster.grade_for("prayer6"), "balm")
        self.assertIn("balm", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel("prayer6")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "balm")
        self.assertEqual(variants[0].hero, "HEAL ME O LORD")
        self.assertEqual(variants[1].hero, "PEACE BE STILL")
        self.assertIsNone(variants[2].hero)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "healing-balm-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "healing-balm-banner.png").size, (2560, 1440))
        wm = Image.open(MEDIA / "healing-balm-watermark.png")
        self.assertEqual(wm.size, (150, 150))
        self.assertEqual(wm.mode, "RGBA")
        self.assertEqual(wm.getpixel((0, 0))[3], 0)
        self.assertEqual(Image.open(MEDIA / "healing-balm-thumbnail-template.png").size, (1280, 720))


class TestSixthChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_prayer6_readiness_and_isolated_secrets(self):
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        comments = (ROOT / ".github/workflows/comments.yml").read_text(encoding="utf-8")
        metrics = (ROOT / ".github/workflows/metrics.yml").read_text(encoding="utf-8")
        monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
        growth = (ROOT / ".github/workflows/growth-autopilot.yml").read_text(encoding="utf-8")
        community = (ROOT / ".github/workflows/community.yml").read_text(encoding="utf-8")
        set_thumb = (ROOT / ".github/workflows/set-thumbnail.yml").read_text(encoding="utf-8")
        setup_doc = ROOT / "docs/SIXTH_CHANNEL_SETUP.md"

        self.assertTrue(setup_doc.is_file())
        self.assertIn("PRAYER6_READY", produce)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn("PRAYER6_GEMINI_API_KEY", produce)

        self.assertIn("PRAYER6_READY", brain)
        self.assertIn("PRAYER6_GEMINI_API_KEY", brain)

        self.assertIn("PRAYER6_READY", comments)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", comments)

        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", metrics)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", monitor)
        self.assertIn("PRAYER6_GEMINI_API_KEY", monitor)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", growth)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", community)
        self.assertIn("PRAYER6_YOUTUBE_REFRESH_TOKEN", set_thumb)


if __name__ == "__main__":
    unittest.main()
