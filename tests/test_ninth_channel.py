"""Regression tests for the ninth prayer channel: The Praise Garden (prayer9).

Registered in full capability parity and provisioned on the owner's instruction
after successful read-only OAuth and Gemini preflights.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from pipeline import channel_capabilities as cc
from pipeline import shorts_poster, thumbnail_ctr
from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
from pipeline.channels import CHANNELS, get_channel, normalize_channel_id, scheduled_channels
from scripts.automation_health import queue_health
from scripts.continuous_research import PRAISE_GARDEN_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
CID = "prayer9"
SIBLINGS = tuple(c for c in CHANNELS if c != CID)


class TestNinthChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve(self):
        ch = get_channel(CID)
        self.assertEqual(ch.display_name, "The Praise Garden")
        self.assertEqual(ch.handle, "@ThePraiseGardenDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER9_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER9_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER9_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in ('prayer9', 'praise', 'praise-garden', 'the-praise-garden', 'thanksgiving', 'gratitude', 'channel9'):
            self.assertEqual(normalize_channel_id(alias), CID)

    def test_provisioned_channel_has_scheduler_and_health_rows(self):
        self.assertTrue(get_channel(CID).provisioned)
        self.assertIn(CID, scheduled_channels())
        rows = {row["queue"] for row in queue_health()}
        self.assertIn(f"longform:{CID}", rows)
        self.assertIn(f"shorts:{CID}", rows)

    def test_remaining_launch_content_is_well_formed(self):
        """Check queued items without requiring published work to remain queued."""
        from pipeline.script_doc import MIN_LONGFORM_WORDS, parse_script
        from pipeline.short_script import validate_spec

        brand = cc.brand_for(CID)
        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        for ident in ('0700', '0701'):
            with self.subTest(job=ident):
                for script in (ROOT / "content" / "queue").glob(f"{ident}-*.md"):
                    doc = parse_script(script)
                    self.assertIn(doc.status, ("approved", "quota_paused", "tts_blocked"))
                    self.assertEqual(doc.channel, CID)
                    self.assertGreaterEqual(doc.word_count, MIN_LONGFORM_WORDS)
                    self.assertTrue(doc.meta["title"].endswith(brand.title_suffix))
                    text = script.read_text(encoding="utf-8")
                    self.assertIn(brand.closing_cta, text)
                    for phrase in brand.forbidden_phrases:
                        self.assertNotIn(phrase.lower(), text.lower())
                    verified = {q for q, _n, _e in brand.verified_commons_queries}
                    self.assertTrue(set(doc.meta["asset_queries"]) <= verified)
                    self.assertGreaterEqual(
                        thumbnail_ctr._layout(draw, doc.meta["thumb_text"], (86, 76, 746, 568))[-1], 105)
                    self.assertTrue((ROOT / "content" / "factcheck" / script.name).is_file())
                for manifest in (ROOT / "content" / "shorts-queue").glob(f"{ident}-*.yml"):
                    entry = yaml.safe_load(manifest.read_text())
                    self.assertIn(entry["status"], ("approved", "quota_paused"))
                    self.assertEqual(entry["channel"], CID)
                    data = json.loads(
                        (ROOT / "content" / "shorts-scripts" / f"{entry['short']}.json").read_text())
                    self.assertEqual(data["channel"], CID)
                    self.assertFalse(validate_spec(data).problems)


class TestNinthChannelIdentityAndVisuals(unittest.TestCase):
    def test_brand_forbids_every_sibling_channel_and_vice_versa(self):
        mine = cc.brand_for(CID)
        for other_id in SIBLINGS:
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, mine.forbidden_phrases)
            self.assertIn(other.handle, mine.forbidden_phrases)
            self.assertIn(mine.display_name, other.forbidden_phrases)
            self.assertIn(mine.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_this_channel_only(self):
        prompt = compile_full_brain_prompt(CID)
        self.assertIn("The Praise Garden", prompt)
        self.assertIn(CID, prompt)
        self.assertNotIn("staged", prompt.lower())
        for other_id in SIBLINGS:
            other = cc.brand_for(other_id)
            self.assertNotIn(other.display_name, prompt)
            self.assertNotIn(other.handle, prompt)

    def test_short_keys_are_namespaced(self):
        key = cc.short_key(CID, "psalm100v4")
        self.assertEqual(key, "short-gardenpsalm100v4")
        self.assertEqual(cc.channel_for_short_key(key), CID)
        for other_id in SIBLINGS:
            self.assertNotEqual(key, cc.short_key(other_id, "psalm100v4"))

    def test_roadmap_has_30_unique_scriptures_in_own_range_and_legible_hooks(self):
        self.assertIs(ROADMAPS[CID], PRAISE_GARDEN_ROADMAP)
        self.assertGreaterEqual(len(PRAISE_GARDEN_ROADMAP), 30)
        ids = [entry["id"] for entry in PRAISE_GARDEN_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0700")
        self.assertTrue(all(i.startswith("07") for i in ids))
        self.assertEqual(PRAISE_GARDEN_ROADMAP[0]["scripture"], "Psalm 100:4")
        self.assertEqual(PRAISE_GARDEN_ROADMAP[1]["scripture"], "Psalm 103:1-5")
        scriptures = [entry["scripture"] for entry in PRAISE_GARDEN_ROADMAP]
        self.assertEqual(len(scriptures), len(set(scriptures)))
        other_ids = {r["id"] for cid in SIBLINGS for r in roadmap_for_channel(cid)}
        self.assertFalse(other_ids & set(ids))
        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        for entry in PRAISE_GARDEN_ROADMAP:
            hero = entry["hook"].upper()
            px = thumbnail_ctr._layout(draw, hero, (86, 76, 746, 568))[-1]
            self.assertGreaterEqual(px, 105, f"{entry['id']}: {hero} -> {px}px")

    def test_shorts_and_ctr_grades_use_dedicated_palette(self):
        self.assertEqual(shorts_poster.grade_for(CID), "garden")
        self.assertIn("garden", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel(CID)
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "garden")
        self.assertEqual(variants[0].hero, "GIVE THANKS")
        self.assertEqual(variants[1].hero, "HE IS GOOD")
        self.assertIsNone(variants[2].hero)

    def test_image_queries_reuse_only_previously_verified_strings(self):
        """No new Commons query is claimed as verified for this channel."""
        earlier = {
            row
            for cid in ("secret-place", "prayer2", "prayer3", "prayer4",
                        "prayer5", "prayer6", "prayer7", "prayer8")
            for row in cc.brand_for(cid).verified_commons_queries
        }
        for row in cc.brand_for(CID).verified_commons_queries:
            self.assertIn(row, earlier)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "praise-garden-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "praise-garden-banner.jpg").size, (2560, 1440))
        self.assertEqual(Image.open(MEDIA / "praise-garden-watermark.png").size, (150, 150))


class TestNinthChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_readiness_and_isolated_secrets(self):
        wf = lambda name: (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        produce, brain, comments = wf("produce.yml"), wf("gemini_brain.yml"), wf("comments.yml")
        self.assertIn("PRAYER9_READY", produce)
        self.assertIn("PRAYER9_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn('"prayer9":"PRAYER9_"', produce)
        self.assertIn("'The Praise Garden'", produce)
        self.assertIn("'@ThePraiseGardenDaily'", produce)
        self.assertIn("PRAYER9_READY", brain)
        self.assertIn("PRAYER9_GEMINI_API_KEY", brain)
        self.assertIn('"prayer9":"PRAYER9_"', brain)
        self.assertIn("PRAYER9_READY", comments)
        self.assertIn('"prayer9":"PRAYER9_"', comments)
        for name in ("metrics.yml", "monitor.yml", "growth-autopilot.yml", "community.yml"):
            self.assertIn("PRAYER9_YOUTUBE_REFRESH_TOKEN", wf(name), name)
        self.assertIn("PRAYER9_GEMINI_API_KEY", wf("monitor.yml"))
        for name in ("set-thumbnail.yml", "channel-credential-audit.yml", "metrics.yml",
                     "growth-autopilot.yml"):
            self.assertIn('"prayer9":"PRAYER9_"', wf(name), name)

    def test_channel_secrets_never_fall_back_to_another_channel(self):
        """Every prefix-map lookup for this channel resolves to its own prefix."""
        import re
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            for mapping in re.findall(r"fromJSON\('(\{[^']*\})'\)", path.read_text(encoding="utf-8")):
                data = json.loads(mapping)
                if CID in data:
                    self.assertEqual(data[CID], "PRAYER9_", path.name)


if __name__ == "__main__":
    unittest.main()
