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

    def test_author_longform_script_generates_valid_script(self):
        brain = GeminiBrain()
        cand = {"id": "0010", "scripture": "Psalm 121", "theme": "He Who Keeps You Will Neither Slumber Nor Sleep", "hook": "THE LORD IS YOUR KEEPER"}
        text = brain.author_longform_script(cand)

        self.assertIn('id: "0010"', text)
        self.assertIn("Psalm 121", text)
        # template output is a draft: nothing reaches the publishing cron until a
        # human flips the status, per pipeline/run.py
        self.assertIn("status: draft", text)
        self.assertIn("privacy: public", text)
        self.assertIn("voice: Charon", text)
        self.assertIn("## Scene 1", text)
        self.assertIn("## Scene 6", text)
        self.assertIn("Spurgeon", text)
        self.assertNotIn("John Azani", text)
        self.assertNotIn("Azani John", text)

    def test_mock_gemini_api_call_handling(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = """---
id: "0010"
title: "Psalm 121: The Lord Is Your Keeper | The Secret Place"
slug: psalm-121-the-lord-is-your-keeper
status: approved
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
tags: [psalm 121, prayer before sleep]
thumb_text: "THE LORD IS YOUR KEEPER"
description: "Psalm 121 Devotional"
asset_queries: ["peaceful mountain lake sunset"]
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

        brain = GeminiBrain(api_key="fake-test-key")
        brain._client = mock_client

        cand = {"id": "0010", "scripture": "Psalm 121", "theme": "The Lord Is Your Keeper", "hook": "KEEPER"}
        result_text = brain.author_longform_script(cand)
        self.assertIn('id: "0010"', result_text)
        self.assertIn("Psalm 121", result_text)


class TestOfflineFallbackIsScoped(unittest.TestCase):
    """The equipped template is Psalm 121 text. Emitting it for another psalm is the
    0011 incident: Psalm 121 verses published under a Psalm 27 title."""

    def test_refuses_to_emit_psalm_121_under_another_psalm(self):
        from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain
        brain = GeminiBrain(api_key="")
        with self.assertRaises(BrainAuthoringError):
            brain.author_longform_script({"id": "0099", "scripture": "Psalm 27",
                                          "theme": "The Lord Is My Light", "hook": "LIGHT"})

    def test_psalm_121_still_uses_the_template(self):
        from pipeline.gemini_brain import GeminiBrain
        text = GeminiBrain(api_key="").author_longform_script(
            {"id": "0098", "scripture": "Psalm 121", "theme": "Keeper", "hook": "KEEPER"})
        self.assertIn("Psalm 121", text)
        self.assertIn("scripture_verified: false", text)
