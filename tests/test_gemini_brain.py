import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from pipeline.brain_equipment.equipment_registry import (
    compile_full_brain_prompt,
    list_equipped_modules,
)
from pipeline.gemini_brain import GeminiBrain
from pipeline.script_doc import parse_script


class TestGeminiBrain(unittest.TestCase):
    def test_equipment_registry_loads_all_modules(self):
        equipped = list_equipped_modules()
        self.assertIn("system_instruction.md", equipped)
        self.assertIn("theological_rubric.md", equipped)
        self.assertIn("docoga_reels_rules.md", equipped)

        prompt = compile_full_brain_prompt()
        self.assertIn("The Secret Place", prompt)
        self.assertIn("Charon", prompt)
        self.assertIn("DOCOGA REELS v2", prompt)
        self.assertIn("Spurgeon", prompt)

    def test_select_next_scripture_picks_valid_candidate(self):
        brain = GeminiBrain()
        cand = brain.select_next_scripture()
        self.assertIsNotNone(cand)
        self.assertTrue(cand.get("id"))
        self.assertTrue(cand.get("scripture"))
        self.assertTrue(cand.get("theme"))

    def test_authoring_is_model_only_on_every_channel(self):
        """No channel has an offline template, so no channel can emit one.

        The old Secret Place fallback was a fixed Psalm 121 exposition that was
        emitted for whatever scripture had been selected (that is how job 0011
        acquired Psalm 121 verses under a Psalm 27 title), and it was under the
        850-word publish floor anyway. Both channels now refuse identically.
        """
        from pipeline.channel_capabilities import known_channels
        from pipeline.gemini_brain import BrainAuthoringError

        for channel_id in known_channels():
            brain = GeminiBrain(api_key="", channel_id=channel_id)
            with self.assertRaises(BrainAuthoringError) as caught:
                brain.author_longform_script(
                    {"id": "0098", "scripture": "Psalm 121", "theme": "Keeper",
                     "hook": "KEEPER"})
            message = str(caught.exception)
            self.assertIn(brain.channel.display_name, message)
            self.assertIn("model-only", message)

    def _mock_model_output(self, channel_declaration: str, channel_name: str,
                          forbidden: str = "") -> MagicMock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = f"""---
id: "0010"
channel: {channel_declaration}
title: "Psalm 121: The Lord Is Your Keeper {channel_name}"
slug: psalm-121-the-lord-is-your-keeper
status: approved
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
tags: [psalm 121, prayer]
thumb_text: "THE LORD IS YOUR KEEPER"
description: "Psalm 121 Devotional for {channel_name}. {forbidden}"
asset_queries: ["peaceful mountain lake"]
originality:
  original_thesis: true
  unique_structure: true
  human_rewrite: true
  no_ai_persona: true
  source_notes: true
  ai_disclosure: false
---

## Scene 1 — The Keeper
I lift my eyes unto the hills.
"""
        mock_client.models.generate_content.return_value = mock_response
        return mock_client

    def test_mock_gemini_api_call_handling(self):
        brain = GeminiBrain(api_key="fake-test-key")
        brain._client = self._mock_model_output("secret-place", "| The Secret Place")

        cand = {"id": "0010", "scripture": "Psalm 121", "theme": "The Lord Is Your Keeper", "hook": "KEEPER"}
        result_text = brain.author_longform_script(cand)
        self.assertIn('id: "0010"', result_text)
        self.assertIn("Psalm 121", result_text)

    def test_morning_altar_accepts_its_own_model_output(self):
        brain = GeminiBrain(api_key="fake-test-key", channel_id="prayer2")
        brain._client = self._mock_model_output("prayer2", "| The Morning Altar")

        text = brain.author_longform_script(
            {"id": "0038", "scripture": "Lamentations 3:22-23",
             "theme": "New Mercies Every Morning", "hook": "NEW EVERY MORNING"})
        self.assertIn("The Morning Altar", text)

    def test_morning_altar_rejects_secret_place_branding(self):
        """Symmetric brand gate: wrong-channel output is refused, never written."""
        from pipeline.gemini_brain import BrainAuthoringError

        brain = GeminiBrain(api_key="fake-test-key", channel_id="prayer2")
        brain._client = self._mock_model_output(
            "prayer2", "| The Morning Altar", forbidden="Prayer before sleep at bedtime.")
        with self.assertRaises(BrainAuthoringError) as caught:
            brain.author_longform_script(
                {"id": "0038", "scripture": "Lamentations 3:22-23",
                 "theme": "New Mercies Every Morning", "hook": "NEW EVERY MORNING"})
        self.assertIn("another channel's branding", str(caught.exception))

    def test_secret_place_rejects_morning_altar_branding(self):
        from pipeline.gemini_brain import BrainAuthoringError

        brain = GeminiBrain(api_key="fake-test-key")
        brain._client = self._mock_model_output(
            "secret-place", "| The Secret Place", forbidden="Subscribe to The Morning Altar.")
        with self.assertRaises(BrainAuthoringError) as caught:
            brain.author_longform_script(
                {"id": "0010", "scripture": "Psalm 121", "theme": "Keeper", "hook": "KEEPER"})
        self.assertIn("another channel's branding", str(caught.exception))


class TestRoadmapExhaustionRefusesEverywhere(unittest.TestCase):
    """Running out of roadmap is refused, never papered over with a used scripture."""

    def test_every_channel_refuses_and_names_its_own_roadmap(self):
        from pipeline.channel_capabilities import capabilities_for, known_channels
        from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain
        from scripts.continuous_research import roadmap_for_channel

        for channel_id in known_channels():
            caps = capabilities_for(channel_id)
            used = {row["id"] for row in roadmap_for_channel(channel_id)}
            brain = GeminiBrain(api_key="", channel_id=channel_id)
            with patch.object(GeminiBrain, "_existing_job_ids", return_value=used):
                with self.assertRaises(BrainAuthoringError) as caught:
                    brain.select_next_scripture()
            message = str(caught.exception)
            self.assertIn(caps.roadmap_name, message)
            self.assertIn(caps.brand.display_name, message)
