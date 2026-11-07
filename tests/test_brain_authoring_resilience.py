"""The authoring chain must survive a bad morning and say what actually happened.

Reproduced from the 7 November 2026 prayer3 supply run (job summary, 06:39Z). The
Midday Watch had zero publishable scripts, so the brain had to author one, and the
chain produced this:

    gemini-3.1-flash-lite returned no scenes — trying the next model
    gemini-3.6-flash: service busy (ServerError). Waiting 5s ...
    gemini-3.6-flash returned a script missing queue front matter (...)
    gemini-3.8-flash: service busy ... 503 UNAVAILABLE (four backoffs)
    gemini-3.7-flash: service busy ... 503 UNAVAILABLE (four backoffs)
    ::error Gemini text model retired:: gemini-2.5-flash is gone (404 NOT_FOUND)
    ::error Gemini text model retired:: gemini-2.0-flash is gone (404 NOT_FOUND)
    [brain] blocked: authoring: ... every candidate model returned ...

Three defects are visible in those nine lines: retired models were still being
tried, a quota-exhausted pass kept calling models, and a single formatting miss
threw away a script the model had actually written. These tests hold the fixes.
"""
from __future__ import annotations

import unittest
from unittest import mock

from pipeline import gemini_brain
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain

BODY = """## Scene 1 — Stillness Before the Meal

Be still, and know that I am God. The middle of the day is not an interruption of
prayer; it is where prayer is most needed.

## Scene 2 — The Table and the Altar

Sit down. Breathe. Say the name of Jesus once, slowly, and let the room be quiet.
Subscribe to The Midday Watch and pause with us at noon.
"""

ENVELOPE = """---
id: "0044"
slug: psalm-46-be-still-and-know
title: "PSALM 46: Be Still and Know — A Midday Prayer"
channel: prayer3
status: approved
format: longform
niche: faith
thumb_text: "BE STILL AND KNOW"
originality: "Original exposition in the channel's own voice; no copied commentary."
---"""

COMPLETE = ENVELOPE + "\n\n" + BODY


class _Resp:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeModels:
    """Answers `generate_content` per model from a script of actions."""

    def __init__(self, script, calls: list[tuple[str, str]]) -> None:
        self._script = script
        self._calls = calls

    def generate_content(self, model: str, contents: str, config: dict | None = None):
        self._calls.append((model, contents))
        action = self._script(model, contents, len(self._calls))
        if isinstance(action, BaseException):
            raise action
        return _Resp(action)


class _FakeClient:
    def __init__(self, script, calls: list[tuple[str, str]]) -> None:
        self.models = _FakeModels(script, calls)


def _brain(script, channel_id: str = "prayer3"):
    """A brain wired to a fake SDK client, with the backoff collapsed to nothing."""
    brain = GeminiBrain(api_key="", channel_id=channel_id)
    calls: list[tuple[str, str]] = []
    brain._client = _FakeClient(script, calls)
    return brain, calls


class AuthoringCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(gemini_brain, "_TRANSIENT_BACKOFF", ())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.scripture = {"id": "0044", "scripture": "Psalm 46:10",
                          "theme": "Stillness at Noon", "hook": "BE STILL AND KNOW"}


class TestRetiredModelsAreNotSpent(AuthoringCase):
    def test_a_404_is_not_attempted_by_default(self):
        brain, calls = _brain(lambda m, c, n: COMPLETE)
        brain.author_longform_script(self.scripture)
        tried = [model for model, _ in calls]
        for retired in gemini_brain.RETIRED_TEXT_MODELS:
            self.assertNotIn(retired, tried,
                             "a retired model costs a request and a red annotation")

    def test_the_chain_starts_with_the_high_allowance_model(self):
        brain, calls = _brain(lambda m, c, n: COMPLETE)
        brain.author_longform_script(self.scripture)
        self.assertEqual(calls[0][0], gemini_brain.DEFAULT_TEXT_MODEL)


class TestServiceFailuresAreNamed(AuthoringCase):
    def test_a_503_fleet_does_not_report_a_format_problem(self):
        brain, calls = _brain(lambda m, c, n: RuntimeError("503 UNAVAILABLE: high demand"))
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError) as ctx:
                brain.author_longform_script(self.scripture)
        message = str(ctx.exception)
        self.assertIn("busy after retries", message)
        self.assertIn("503 UNAVAILABLE", message)
        self.assertNotIn("returned a script without the front matter", message)
        self.assertIn("Nothing was written", message)
        self.assertTrue(all("busy after retries" in row["outcome"]
                            for row in brain.authoring_outcomes))

    def test_quota_exhaustion_stops_the_chain_immediately(self):
        """Every model shares the project's daily allowance; six more calls buy nothing."""
        brain, calls = _brain(
            lambda m, c, n: RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError) as ctx:
                brain.author_longform_script(self.scripture)
        self.assertEqual(len(calls), 1, "stop at the first quota answer")
        self.assertIn("allowance is spent", str(ctx.exception))
        self.assertIn("resets at", str(ctx.exception))

    def test_one_dead_model_falls_through_to_the_next(self):
        def script(model, contents, n):
            if model == gemini_brain.DEFAULT_TEXT_MODEL:
                return RuntimeError("503 UNAVAILABLE")
            return COMPLETE

        brain, calls = _brain(script)
        text = brain.author_longform_script(self.scripture)
        self.assertIn("## Scene 1", text)
        self.assertEqual(calls[0][0], gemini_brain.DEFAULT_TEXT_MODEL)
        self.assertGreater(len(calls), 1)


class TestUsableTextIsNotThrownAway(AuthoringCase):
    def test_heading_variants_are_normalised_not_rejected(self):
        variant = COMPLETE.replace("## Scene 1", "### SCENE 1").replace("## Scene 2", "**Scene 2**")
        brain, _ = _brain(lambda m, c, n: variant)
        text = brain.author_longform_script(self.scripture)
        self.assertIn("## Scene 1", text)
        self.assertIn("## Scene 2", text)
        self.assertEqual(gemini_brain.missing_job_keys(text), [])

    def test_a_fenced_answer_is_unwrapped_even_with_leading_prose_noise(self):
        fenced = "```markdown\n" + COMPLETE + "\n```"
        brain, _ = _brain(lambda m, c, n: fenced)
        text = brain.author_longform_script(self.scripture)
        self.assertFalse(text.startswith("```"), text[:20])

    def test_a_body_without_an_envelope_gets_one_cheap_repair(self):
        def script(model, contents, n):
            if "ONLY a YAML front matter block" in contents:
                return ENVELOPE
            return BODY          # the model wrote a script, but no header

        brain, calls = _brain(script)
        text = brain.author_longform_script(self.scripture)
        self.assertEqual(len(calls), 2, "one script call plus one envelope call")
        self.assertEqual(calls[1][0], calls[0][0], "repair asks the same model")
        self.assertTrue(text.startswith("---"), text[:40])
        self.assertEqual(gemini_brain.missing_job_keys(text), [])
        self.assertIn("## Scene 1", text)

    def test_the_repair_budget_is_bounded(self):
        """Two repairs per run, so a model that cannot write headers is left alone."""
        brain, calls = _brain(lambda m, c, n: BODY if "ONLY a YAML front matter" not in c else BODY)
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError) as ctx:
                brain.author_longform_script(self.scripture)
        repairs = [c for c in calls if "ONLY a YAML front matter" in c[1]]
        self.assertEqual(len(repairs), 2)
        self.assertIn("repair budget spent", str(ctx.exception))

    def test_the_envelope_is_never_invented_when_the_repair_returns_nothing(self):
        def script(model, contents, n):
            if "ONLY a YAML front matter block" in contents:
                return ""
            return BODY

        brain, _ = _brain(script)
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError):
                brain.author_longform_script(self.scripture)


if __name__ == "__main__":
    unittest.main()
