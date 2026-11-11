"""Regression tests for the eighth prayer channel: The Covenant Shield (prayer8).

Registered in full capability parity with provisioned=False until the owner creates
@TheCovenantShieldDaily on YouTube and saves its separate Google Cloud credentials
(PRAYER8_YOUTUBE_* + PRAYER8_GEMINI_API_KEY).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from pipeline import channel_capabilities as cc
from pipeline import shorts_poster, thumbnail_ctr
from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
from pipeline.channels import CHANNELS, get_channel, normalize_channel_id, scheduled_channels
from scripts.automation_health import queue_health
from scripts.continuous_research import COVENANT_SHIELD_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"


class TestEighthChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve_to_prayer8(self):
        self.assertIn("prayer8", CHANNELS)
        ch = get_channel("prayer8")
        self.assertEqual(ch.display_name, "The Covenant Shield")
        self.assertEqual(ch.handle, "@TheCovenantShieldDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER8_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER8_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER8_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in (
            "prayer8",
            "shield",
            "covenant-shield",
            "the-covenant-shield",
            "protection",
            "strong-tower",
            "channel8",
        ):
            self.assertEqual(normalize_channel_id(alias), "prayer8")

    def test_channel_waits_for_launch_review(self):
        ch = get_channel("prayer8")
        self.assertFalse(ch.provisioned)
        self.assertNotIn("prayer8", scheduled_channels())
        health_rows = {row["queue"]: row for row in queue_health()}
        self.assertNotIn("longform:prayer8", health_rows)
        self.assertNotIn("shorts:prayer8", health_rows)

    def test_launch_drafts_and_short_specs_meet_structural_checks(self):
        import json
        import yaml
        from pipeline.script_doc import MIN_LONGFORM_WORDS, parse_script
        from pipeline.short_script import validate_spec
        from pipeline import thumbnail_ctr
        from PIL import ImageDraw

        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        for ident in ("0600", "0601", "0602", "0603"):
            with self.subTest(job=ident):
                script = next((ROOT / "content" / "queue").glob(f"{ident}-*.md"))
                doc = parse_script(script)
                self.assertEqual(doc.status, "draft")
                self.assertEqual(doc.channel, "prayer8")
                self.assertGreaterEqual(doc.word_count, MIN_LONGFORM_WORDS)
                self.assertGreaterEqual(thumbnail_ctr._layout(draw, doc.meta["thumb_text"], (86, 76, 746, 568))[-1], 105)
                self.assertTrue((ROOT / "content" / "factcheck" / script.name).is_file())
                manifest = next((ROOT / "content" / "shorts-queue").glob(f"{ident}-*.yml"))
                entry = yaml.safe_load(manifest.read_text())
                self.assertEqual(entry["status"], "draft")
                self.assertEqual(entry["channel"], "prayer8")
                data = json.loads((ROOT / "content" / "shorts-scripts" / f"{entry['short']}.json").read_text())
                self.assertFalse(validate_spec(data).problems)



class TestEighthChannelIdentityAndVisuals(unittest.TestCase):
    def test_shield_brand_forbids_all_seven_sibling_channels_and_vice_versa(self):
        b8 = cc.brand_for("prayer8")
        for other_id in (
            "secret-place",
            "prayer2",
            "prayer3",
            "prayer4",
            "prayer5",
            "prayer6",
            "prayer7",
        ):
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, b8.forbidden_phrases)
            self.assertIn(other.handle, b8.forbidden_phrases)
            self.assertIn(b8.display_name, other.forbidden_phrases)
            self.assertIn(b8.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_covenant_shield_only(self):
        prompt = compile_full_brain_prompt("prayer8")
        self.assertIn("The Covenant Shield", prompt)
        self.assertIn("prayer8", prompt)
        for forbidden in (
            "The Secret Place",
            "The Morning Altar",
            "The Midday Watch",
            "The Midnight Watch",
            "The Family Altar",
            "The Healing Balm",
            "The Provision Table",
            "@TheSecretPlace",
            "@TheMorningAltarDaily",
            "@TheMiddayWatch",
            "@TheMidnightWatchDaily",
            "@TheFamilyAltarDaily",
            "@TheHealingBalmDaily",
            "@TheProvisionTableDaily",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_short_keys_are_namespaced_to_shield(self):
        key = cc.short_key("prayer8", "psalm121v7")
        self.assertEqual(key, "short-shieldpsalm121v7")
        for other_id in (
            "secret-place",
            "prayer2",
            "prayer3",
            "prayer4",
            "prayer5",
            "prayer6",
            "prayer7",
        ):
            self.assertNotEqual(key, cc.short_key(other_id, "psalm121v7"))

    def test_roadmap_has_30_unique_protection_scriptures_in_0600_range_and_legible_hooks(self):
        self.assertIs(ROADMAPS["prayer8"], COVENANT_SHIELD_ROADMAP)
        self.assertGreaterEqual(len(COVENANT_SHIELD_ROADMAP), 30)
        ids = [entry["id"] for entry in COVENANT_SHIELD_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0600")
        self.assertEqual(COVENANT_SHIELD_ROADMAP[0]["scripture"], "Psalm 121:7-8")
        self.assertEqual(COVENANT_SHIELD_ROADMAP[1]["scripture"], "Genesis 15:1")
        other_ids = {
            r["id"]
            for cid in (
                "secret-place",
                "prayer2",
                "prayer3",
                "prayer4",
                "prayer5",
                "prayer6",
                "prayer7",
            )
            for r in roadmap_for_channel(cid)
        }
        self.assertFalse(other_ids & set(ids))
        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        for entry in COVENANT_SHIELD_ROADMAP:
            hero = entry["hook"].upper()
            _f, _lines, _tr, _ld, px = thumbnail_ctr._layout(draw, hero, (86, 76, 746, 568))
            self.assertGreaterEqual(px, 105, f"{entry['id']}: {hero} -> {px}px")

    def test_shorts_and_ctr_grades_use_dedicated_fortress_palette(self):
        self.assertEqual(shorts_poster.grade_for("prayer8"), "fortress")
        self.assertIn("fortress", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel("prayer8")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "fortress")
        self.assertEqual(variants[0].hero, "GUARD MY STEPS")
        self.assertEqual(variants[1].hero, "STRONG TOWER")
        self.assertIsNone(variants[2].hero)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "covenant-shield-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "covenant-shield-banner.png").size, (2560, 1440))
        wm = Image.open(MEDIA / "covenant-shield-watermark.png")
        self.assertEqual(wm.size, (150, 150))
        self.assertEqual(wm.mode, "RGBA")
        self.assertEqual(wm.getpixel((0, 0))[3], 0)
        self.assertEqual(Image.open(MEDIA / "covenant-shield-thumbnail-template.png").size, (1280, 720))


class TestEighthChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_prayer8_readiness_and_isolated_secrets(self):
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        comments = (ROOT / ".github/workflows/comments.yml").read_text(encoding="utf-8")
        metrics = (ROOT / ".github/workflows/metrics.yml").read_text(encoding="utf-8")
        monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
        growth = (ROOT / ".github/workflows/growth-autopilot.yml").read_text(encoding="utf-8")
        community = (ROOT / ".github/workflows/community.yml").read_text(encoding="utf-8")
        set_thumb = (ROOT / ".github/workflows/set-thumbnail.yml").read_text(encoding="utf-8")

        self.assertIn("PRAYER8_READY", produce)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn("PRAYER8_GEMINI_API_KEY", produce)
        self.assertIn("PRAYER8_READY", brain)
        self.assertIn("PRAYER8_GEMINI_API_KEY", brain)
        self.assertIn("PRAYER8_READY", comments)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", comments)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", metrics)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", monitor)
        self.assertIn("PRAYER8_GEMINI_API_KEY", monitor)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", growth)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", community)
        self.assertIn("PRAYER8_YOUTUBE_REFRESH_TOKEN", set_thumb)


if __name__ == "__main__":
    unittest.main()
