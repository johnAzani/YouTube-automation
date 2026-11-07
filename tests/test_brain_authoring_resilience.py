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
    brain._sleep = lambda _seconds: None
    return brain, calls


class AuthoringCase(unittest.TestCase):
    def setUp(self):
        # The real ladder, with the sleeping stubbed out: the budget arithmetic is what
        # these tests assert, so the delays must be recorded, not skipped.
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


class TestTheRetryBudgetIsPerPass(AuthoringCase):
    """R1 — measured on 7 November: 25 requests / 9m10s for ONE logical call.

    With five live models and five attempts each, a busy morning spent 125 % of a
    20-request/day model's whole day on a single authoring attempt, and an
    empty-queue pass (up to 8 logical calls) could not finish inside the 30-minute
    job timeout. The budget now belongs to the *pass*.
    """

    def test_a_twenty_request_model_gets_two_attempts_not_five(self):
        brain, calls = _brain(lambda m, c, n: RuntimeError("503 UNAVAILABLE"))
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError):
                brain.author_longform_script(self.scripture)
        per_model = {}
        for model, _ in calls:
            per_model[model] = per_model.get(model, 0) + 1
        for model in gemini_brain.TWENTY_A_DAY_MODELS:
            if model in per_model:
                self.assertEqual(per_model[model], 2, f"{model} spent a quarter of its day")
        self.assertEqual(gemini_brain.model_attempt_limit("gemini-3.5-flash-lite"), 3)
        self.assertEqual(gemini_brain.model_attempt_limit("gemini-3.8-flash"), 2)

    def test_the_whole_pass_sleeps_no_more_than_its_budget(self):
        slept: list[float] = []
        brain, _ = _brain(lambda m, c, n: RuntimeError("503 UNAVAILABLE"))
        brain._sleep = slept.append
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError):
                brain.author_longform_script(self.scripture)
        self.assertLessEqual(sum(slept), gemini_brain.MAX_TRANSIENT_SLEEP_SECONDS)
        # 2 lite waits + 2 lite waits + 1 + 1 + 1 for the 20-a-day pair and the alias:
        # every model is still tried, and the pass is bounded at two minutes.
        self.assertEqual(len(slept), 7, slept)

    def test_waits_carry_jitter(self):
        brain, _ = _brain(lambda m, c, n: COMPLETE)
        waits = [brain._budgeted_wait("gemini-3.5-flash-lite", 0, 4) for _ in range(40)]
        self.assertGreater(len(set(waits)), 1, "identical waits retry in lockstep")
        base = gemini_brain._TRANSIENT_BACKOFF[0]
        self.assertTrue(all(base * 0.79 <= w <= base * 1.21 for w in waits), waits)

    def test_a_spent_budget_stops_climbing_rather_than_waiting_zero(self):
        brain, calls = _brain(lambda m, c, n: RuntimeError("503 UNAVAILABLE"))
        brain._sleep = lambda _s: None
        brain.transient_slept = gemini_brain.MAX_TRANSIENT_SLEEP_SECONDS
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError) as ctx:
                brain.author_longform_script(self.scripture)
        self.assertEqual(len(calls), 5, "each model is asked exactly once")
        self.assertIn("backoff budget", str(ctx.exception))

    def test_the_failure_names_the_budget_when_it_is_what_ran_out(self):
        """Deterministic: the message logic is the assertion, not a jittered sum."""
        brain, _ = _brain(lambda m, c, n: COMPLETE)
        brand = gemini_brain.brand_for("prayer3")
        brain.transient_slept = gemini_brain.MAX_TRANSIENT_SLEEP_SECONDS
        message = brain._authoring_failure(
            brand, [{"model": "gemini-3.5-flash-lite", "outcome": "busy after retries"}])
        self.assertIn("backoff", message)
        self.assertIn("later slot", message)
        # and it stays quiet when the budget was not the thing that ran out
        brain.transient_slept = 0.0
        quiet = brain._authoring_failure(
            brand, [{"model": "gemini-3.5-flash-lite", "outcome": "missing id"}])
        self.assertNotIn("backoff", quiet)

    def test_quota_still_stops_the_chain_before_any_wait(self):
        slept: list[float] = []
        brain, calls = _brain(lambda m, c, n: RuntimeError("429 RESOURCE_EXHAUSTED"))
        brain._sleep = slept.append
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError):
                brain.author_longform_script(self.scripture)
        self.assertEqual(len(calls), 1)
        self.assertEqual(slept, [], "a spent daily allowance is not a patient problem")


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
