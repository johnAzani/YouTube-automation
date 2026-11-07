"""A script that names no channel is published on the wrong one.

On 7 November 2026, 25 of the 27 scripts in `content/queue/` declared no `channel:`
line, so all 25 parsed as `secret-place`. The Midday Watch's queue was empty while
the other channels' queues filled with scripts written for it, and its brain failed
five runs in a row because `_enforce_channel_metadata` refuses an unowned script —
but `channel` was not a required key, so the envelope repair was never asked to
supply it and every candidate answer was discarded.

Two fixes hold it: the prompt now *shows* the block (it used to describe it in
prose, and the one key the model had to invent is the one it dropped), and the write
to the queue refuses a script whose owner is absent or foreign.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain, missing_job_keys
from pipeline.script_doc import parse_script

BODY = """
## Scene 1 — The Noonday Pause

Be still, and know that I am God. Psalm 46:10.

## Scene 2 — Sent Back Into the Day

Type Amen to agree with this prayer, and subscribe to The Midday Watch.
"""


def script(channel: str | None) -> str:
    head = [
        '---',
        'id: "0041"',
        'slug: the-noonday-pause',
        'title: "THE NOONDAY PAUSE: A Midday Prayer of Stillness"',
        'status: approved',
        'format: longform',
        'niche: faith',
        'thumb_text: "PAUSE AND PRAY"',
        'originality: "Original exposition; no copied commentary."',
    ]
    if channel is not None:
        head.append(f'channel: {channel}')
    return "\n".join(head) + "\n---\n" + BODY


class ThePromptShowsTheBlockTests(unittest.TestCase):
    def test_every_channel_is_shown_its_own_channel_line(self):
        for channel in ("secret-place", "prayer2", "prayer3"):
            prompt = compile_full_brain_prompt(channel)
            self.assertIn(f"channel: {channel}", prompt,
                          f"{channel}'s prompt must show the literal key")
            self.assertIn("slug:", prompt,
                          "the block must show every key, not just the channel")

    def test_the_block_is_shown_not_merely_described(self):
        prompt = compile_full_brain_prompt("prayer3")
        # A YAML block, not a sentence: the failure mode was prose-only guidance.
        start = prompt.index("---\nid:")
        block = prompt[start:prompt.index("\n---", start + 4)]
        for key in ("id", "title", "slug", "status", "channel", "privacy", "format",
                    "niche", "voice", "target_minutes"):
            self.assertIn(f"\n{key}:", block, f"`{key}` must appear in the block")


class ChannelIsARequiredKeyTests(unittest.TestCase):
    def test_an_envelope_without_channel_is_incomplete(self):
        self.assertEqual(missing_job_keys(script(None)), ["channel"])

    def test_a_complete_envelope_has_no_missing_keys(self):
        self.assertEqual(missing_job_keys(script("prayer3")), [])

    def test_the_envelope_repair_is_told_the_channel_verbatim(self):
        seen = {}

        def fake_call(model, prompt, **kwargs):
            seen["prompt"] = prompt
            return '---\nchannel: prayer3\n---\n'

        brain = GeminiBrain(channel_id="prayer3")
        with mock.patch.object(brain, "_call_model", side_effect=fake_call):
            brain._repair_envelope("m", BODY, {"id": "0041"}, ["channel"])
        self.assertIn("- channel: prayer3", seen["prompt"],
                      "the repair must hand over the run's own channel, not ask for it")


class TheWriteRefusesAnUnownedScriptTests(unittest.TestCase):
    def _stage(self, text: str, channel: str = "prayer3"):
        brain = GeminiBrain(channel_id=channel)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0041-the-noonday-pause.md"
            path.write_text(text, encoding="utf-8")
            with mock.patch("scripts.factcheck.main",
                            side_effect=AssertionError("factcheck must not run")) as fc:
                brain.verify_and_stage(path)
        return fc

    def test_a_script_with_no_channel_is_refused_before_any_work(self):
        with self.assertRaises(BrainAuthoringError) as raised:
            self._stage(script(None))
        self.assertIn("no `channel:` line", str(raised.exception))
        self.assertIn("prayer3", str(raised.exception),
                      "the refusal must name the channel that should have been declared")

    def test_another_channels_script_is_refused(self):
        with self.assertRaises(BrainAuthoringError) as raised:
            self._stage(script("prayer2"))
        self.assertIn("prayer2", str(raised.exception))
        self.assertIn("prayer3", str(raised.exception))

    def test_the_guard_accepts_the_channels_own_script(self):
        brain = GeminiBrain(channel_id="prayer3")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.md"
            path.write_text(script("prayer3"), encoding="utf-8")
            brain._require_own_channel(parse_script(path), path)   # must not raise
