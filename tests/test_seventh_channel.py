"""Regression tests for the seventh prayer channel: The Provision Table (prayer7).

Registered in full capability parity with provisioned=False until the owner creates
@TheProvisionTableDaily on YouTube and saves its separate Google Cloud credentials
(PRAYER7_YOUTUBE_* + PRAYER7_GEMINI_API_KEY).
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
from scripts.continuous_research import PROVISION_TABLE_ROADMAP, ROADMAPS, roadmap_for_channel

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"


class TestSeventhChannelRegistration(unittest.TestCase):
    def test_profile_and_aliases_resolve_to_prayer7(self):
        self.assertIn("prayer7", CHANNELS)
        ch = get_channel("prayer7")
        self.assertEqual(ch.display_name, "The Provision Table")
        self.assertEqual(ch.handle, "@TheProvisionTableDaily")
        self.assertEqual(ch.secret_prefix, "PRAYER7_")
        self.assertEqual(ch.secret_name("YOUTUBE_REFRESH_TOKEN"), "PRAYER7_YOUTUBE_REFRESH_TOKEN")
        self.assertEqual(ch.secret_name("GEMINI_API_KEY"), "PRAYER7_GEMINI_API_KEY")
        self.assertEqual(ch.default_privacy, "public")
        self.assertTrue(ch.auto_publish)
        self.assertFalse(ch.include_sanctuary_links)
        for alias in (
            "prayer7",
            "provision",
            "provision-table",
            "the-provision-table",
            "stewardship",
            "open-doors",
            "channel7",
        ):
            self.assertEqual(normalize_channel_id(alias), "prayer7")

    def test_unprovisioned_channel_waits_quietly_until_secrets_exist(self):
        ch = get_channel("prayer7")
        self.assertFalse(ch.provisioned)
        self.assertNotIn("prayer7", scheduled_channels())
        health_rows = {row["queue"]: row for row in queue_health()}
        self.assertNotIn("longform:prayer7", health_rows)
        self.assertNotIn("shorts:prayer7", health_rows)


class TestSeventhChannelIdentityAndVisuals(unittest.TestCase):
    def test_provision_brand_forbids_all_six_sibling_channels_and_vice_versa(self):
        b7 = cc.brand_for("prayer7")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5", "prayer6"):
            other = cc.brand_for(other_id)
            self.assertIn(other.display_name, b7.forbidden_phrases)
            self.assertIn(other.handle, b7.forbidden_phrases)
            self.assertIn(b7.display_name, other.forbidden_phrases)
            self.assertIn(b7.handle, other.forbidden_phrases)

    def test_compiled_brain_prompt_targets_provision_table_only(self):
        prompt = compile_full_brain_prompt("prayer7")
        self.assertIn("The Provision Table", prompt)
        self.assertIn("prayer7", prompt)
        for forbidden in (
            "The Secret Place",
            "The Morning Altar",
            "The Midday Watch",
            "The Midnight Watch",
            "The Family Altar",
            "The Healing Balm",
            "@TheSecretPlace",
            "@TheMorningAltarDaily",
            "@TheMiddayWatch",
            "@TheMidnightWatchDaily",
            "@TheFamilyAltarDaily",
            "@TheHealingBalmDaily",
        ):
            self.assertNotIn(forbidden, prompt)

    def test_short_keys_are_namespaced_to_provision(self):
        key = cc.short_key("prayer7", "psalm23v5")
        self.assertEqual(key, "short-provisionpsalm23v5")
        for other_id in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5", "prayer6"):
            self.assertNotEqual(key, cc.short_key(other_id, "psalm23v5"))

    def test_roadmap_has_30_unique_provision_scriptures_in_0500_range(self):
        self.assertIs(ROADMAPS["prayer7"], PROVISION_TABLE_ROADMAP)
        self.assertGreaterEqual(len(PROVISION_TABLE_ROADMAP), 30)
        ids = [entry["id"] for entry in PROVISION_TABLE_ROADMAP]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "0500")
        self.assertEqual(PROVISION_TABLE_ROADMAP[0]["scripture"], "Psalm 23:5")
        self.assertEqual(PROVISION_TABLE_ROADMAP[1]["scripture"], "Deuteronomy 28:12")
        other_ids = {
            r["id"]
            for cid in ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5", "prayer6")
            for r in roadmap_for_channel(cid)
        }
        self.assertFalse(other_ids & set(ids))

    def test_shorts_and_ctr_grades_use_dedicated_harvest_palette(self):
        self.assertEqual(shorts_poster.grade_for("prayer7"), "harvest")
        self.assertIn("harvest", shorts_poster._GRADES)
        variants = thumbnail_ctr.variants_for_channel("prayer7")
        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].grade, "harvest")
        self.assertEqual(variants[0].hero, "OPEN THIS DOOR")
        self.assertEqual(variants[1].hero, "MY CUP OVERFLOWS")
        self.assertIsNone(variants[2].hero)

    def test_brand_assets_are_rendered_to_youtube_specs(self):
        self.assertEqual(Image.open(MEDIA / "provision-table-avatar.png").size, (800, 800))
        self.assertEqual(Image.open(MEDIA / "provision-table-banner.png").size, (2560, 1440))
        wm = Image.open(MEDIA / "provision-table-watermark.png")
        self.assertEqual(wm.size, (150, 150))
        self.assertEqual(wm.mode, "RGBA")
        self.assertEqual(wm.getpixel((0, 0))[3], 0)
        self.assertEqual(Image.open(MEDIA / "provision-table-thumbnail-template.png").size, (1280, 720))


class TestSeventhChannelWorkflowWiring(unittest.TestCase):
    def test_workflows_wire_prayer7_readiness_and_isolated_secrets(self):
        produce = (ROOT / ".github/workflows/produce.yml").read_text(encoding="utf-8")
        brain = (ROOT / ".github/workflows/gemini_brain.yml").read_text(encoding="utf-8")
        comments = (ROOT / ".github/workflows/comments.yml").read_text(encoding="utf-8")
        metrics = (ROOT / ".github/workflows/metrics.yml").read_text(encoding="utf-8")
        monitor = (ROOT / ".github/workflows/monitor.yml").read_text(encoding="utf-8")
        growth = (ROOT / ".github/workflows/growth-autopilot.yml").read_text(encoding="utf-8")
        community = (ROOT / ".github/workflows/community.yml").read_text(encoding="utf-8")
        set_thumb = (ROOT / ".github/workflows/set-thumbnail.yml").read_text(encoding="utf-8")
        setup_doc = ROOT / "docs/SEVENTH_CHANNEL_SETUP.md"

        self.assertTrue(setup_doc.is_file())
        self.assertIn("PRAYER7_READY", produce)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", produce)
        self.assertIn("PRAYER7_GEMINI_API_KEY", produce)

        self.assertIn("PRAYER7_READY", brain)
        self.assertIn("PRAYER7_GEMINI_API_KEY", brain)

        self.assertIn("PRAYER7_READY", comments)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", comments)

        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", metrics)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", monitor)
        self.assertIn("PRAYER7_GEMINI_API_KEY", monitor)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", growth)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", community)
        self.assertIn("PRAYER7_YOUTUBE_REFRESH_TOKEN", set_thumb)

    def test_upload_credentials_fallback_to_inherent_token_scopes_on_invalid_scope(self):
        from unittest import mock
        from pipeline import upload

        calls = []

        class FakeCreds:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                calls.append(kwargs)

            def refresh(self, _req):
                if self.kwargs.get("scopes") is not None:
                    raise RuntimeError("RefreshError: ('invalid_scope: Bad Request')")

        with mock.patch.object(upload.CONFIG, "youtube_client_id", "cid"), \
             mock.patch.object(upload.CONFIG, "youtube_client_secret", "csec"), \
             mock.patch.object(upload.CONFIG, "youtube_refresh_token", "rtok"), \
             mock.patch("google.oauth2.credentials.Credentials", FakeCreds):
            creds = upload._credentials()
        self.assertEqual(len(calls), 2)
        self.assertIsNotNone(calls[0]["scopes"])
        self.assertIsNone(calls[1]["scopes"])
        self.assertIsNone(creds.kwargs["scopes"])


if __name__ == "__main__":
    unittest.main()
