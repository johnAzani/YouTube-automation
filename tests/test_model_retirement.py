"""A model lifetime is an outage we do not control — so it must not be hardcoded.

On 6 November 2026 `gemini-2.5-flash` was withdrawn. The API answered:

    404 NOT_FOUND. "This model models/gemini-2.5-flash is no longer available to
    new users. Please update your code to use models/gemini-3.8-flash..."

Every authoring run died on it (brain runs 42184621470 and 42184973219 at 08:00 and
08:03 UTC) — the same morning the scheduler stalled and `google-genai 3.0.0` broke
narration. Three unrelated outages, one quiet channel. These tests keep the brain
pointed at a live model, and keep a retirement loud when it happens again.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from pipeline import gemini_brain
from pipeline.gemini_brain import (
    DEFAULT_TEXT_MODEL,
    RETIRED_TEXT_MODELS,
    is_model_retired,
    live_model,
    text_model_candidates,
)

ROOT = Path(__file__).resolve().parent.parent


class TestTheBrainStartsWithALiveModel(unittest.TestCase):
    def test_the_default_is_not_a_retired_model(self):
        self.assertNotIn(DEFAULT_TEXT_MODEL, RETIRED_TEXT_MODELS)
        # Moved from gemini-3.8-flash on 6 November: its free tier is ~20 requests a
        # day and one brain pass needs more. See tests/test_model_quota_policy.py.
        self.assertEqual(DEFAULT_TEXT_MODEL, "gemini-3.5-flash-lite")

    def test_a_retired_configured_model_never_wins(self):
        for retired in RETIRED_TEXT_MODELS:
            with self.subTest(retired=retired):
                self.assertNotIn(live_model(retired), RETIRED_TEXT_MODELS)

    def test_retired_models_are_still_reachable_but_always_last(self):
        chain = text_model_candidates("gemini-2.5-flash")
        self.assertEqual(chain[0], DEFAULT_TEXT_MODEL,
                         "an explicitly configured retired model must not be tried first")
        self.assertIn("gemini-2.5-flash", chain, "still reachable for an older project key")
        self.assertEqual(len(chain), len(set(chain)), "no duplicate attempts")
        live = [m for m in chain if m not in RETIRED_TEXT_MODELS]
        self.assertEqual(chain[: len(live)], live, "a live model must come before any retired one")

    def test_the_brain_defaults_to_the_live_model(self):
        brain = gemini_brain.GeminiBrain(api_key="")   # no key, no network
        self.assertEqual(brain.model, DEFAULT_TEXT_MODEL)

    def test_authoring_tries_live_models_before_retired_ones(self):
        brain = gemini_brain.GeminiBrain(api_key="", model="gemini-2.5-flash")
        chain = text_model_candidates(brain.model)
        first_live = next(m for m in chain if m not in RETIRED_TEXT_MODELS)
        self.assertEqual(first_live, DEFAULT_TEXT_MODEL)


class TestRetirementIsLoud(unittest.TestCase):
    def test_the_404_is_recognised_as_a_retirement(self):
        exc = RuntimeError(
            "404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model "
            "models/gemini-2.5-flash is no longer available to new users.'}}"
        )
        self.assertTrue(is_model_retired(exc))

    def test_other_failures_are_not_called_retirements(self):
        for message in ("429 RESOURCE_EXHAUSTED quota", "503 UNAVAILABLE high demand",
                        "400 INVALID_ARGUMENT"):
            with self.subTest(message=message):
                self.assertFalse(is_model_retired(RuntimeError(message)))

    def test_the_annotation_names_the_model_and_the_fix(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            gemini_brain.report_retired_model("gemini-2.5-flash", RuntimeError("404 no longer available"))
        out = buffer.getvalue()
        self.assertIn("::error", out)
        self.assertIn("Gemini text model retired", out)
        self.assertIn("GEMINI_TEXT_MODEL", out)
        self.assertIn("DEFAULT_TEXT_MODEL", out)


class TestNoRetiredModelIsTheFirstChoice(unittest.TestCase):
    """A grep-level guard: the pattern that caused this must not come back."""

    def test_comment_replies_prefers_a_live_model(self):
        text = (ROOT / "pipeline/comment_replies.py").read_text(encoding="utf-8")
        first = text.split('models = [', 1)[1].split('"', 2)[1]
        self.assertNotIn(first, RETIRED_TEXT_MODELS, f"first choice is {first!r}")


if __name__ == "__main__":
    unittest.main()


class TestSpeechModelRedirect(unittest.TestCase):
    """Speech answers a withdrawn model with *text*, so the message must be read."""

    def test_the_suggested_model_is_extracted_from_the_prose(self):
        from pipeline.gemini_tts import suggested_model

        message = ("This model is no longer available. Please update your code to use "
                   "models/gemini-3.8-flash-tts for the latest features.")
        self.assertEqual(suggested_model(message), "gemini-3.8-flash-tts")

    def test_no_suggestion_is_reported_as_none_rather_than_guessed(self):
        from pipeline.gemini_tts import suggested_model, _response_parts

        self.assertIsNone(suggested_model(""))
        self.assertIsNone(suggested_model("stillness is a prayer"))

        class _Inline:
            mime_type = "audio/pcm;rate=24000"
            data = b"xx"

        class _Part:
            inline_data = _Inline()

        class _Content:
            parts = [_Part()]

        class _Cand:
            content = _Content()

        class _Resp:
            candidates = [_Cand()]

        text_back, mimes = _response_parts(_Resp())
        self.assertEqual(text_back, "")
        self.assertEqual(mimes, ["audio/pcm;rate=24000"])


class TestTransientServiceFailures(unittest.TestCase):
    """503 is the service being busy — wait it out instead of burning the slot.

    6 November 08:45Z: the brain reached a live model (the retirement fix worked) and
    still failed, because three calls in a row returned `503 UNAVAILABLE — high
    demand` and the loop skipped to the next candidate model instead of waiting.
    """

    def test_high_demand_is_transient(self):
        from pipeline.gemini_brain import is_transient

        exc = RuntimeError("503 UNAVAILABLE. This model is currently experiencing high demand.")
        self.assertTrue(is_transient(exc))

    def test_a_retirement_is_not_transient(self):
        from pipeline.gemini_brain import is_transient

        self.assertFalse(is_transient(RuntimeError("404 NOT_FOUND: no longer available")))

    def test_a_quota_error_is_not_transient(self):
        from pipeline.gemini_brain import is_transient

        self.assertFalse(is_transient(RuntimeError("429 RESOURCE_EXHAUSTED: quota")))

    def test_the_model_is_retried_before_giving_up(self):
        from unittest import mock

        from pipeline import gemini_brain

        brain = gemini_brain.GeminiBrain(api_key="")
        calls = {"n": 0}

        class _Resp:
            text = "id: 0038\n## Scene 1\n## Scene 2"

        def _generate(**kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("503 UNAVAILABLE. high demand")
            return _Resp()

        brain._client = mock.MagicMock()
        brain._client.models.generate_content.side_effect = _generate
        with mock.patch.object(gemini_brain, "_TRANSIENT_BACKOFF", (0, 0, 0)):
            text = brain._call_model("gemini-3.8-flash", "prompt")
        self.assertEqual(calls["n"], 3, "two 503s, then the same model answers")
        self.assertIn("## Scene", text)

    def test_a_retired_model_is_not_retried(self):
        from unittest import mock

        from pipeline import gemini_brain

        brain = gemini_brain.GeminiBrain(api_key="")
        brain._client = mock.MagicMock()
        brain._client.models.generate_content.side_effect = RuntimeError(
            "404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users")
        with mock.patch.object(gemini_brain, "_TRANSIENT_BACKOFF", (0, 0, 0)):
            self.assertEqual(brain._call_model("gemini-2.5-flash", "prompt"), "")
        self.assertEqual(brain._client.models.generate_content.call_count, 1,
                         "a withdrawn model will not become available on retry")


class TestPreflightSurvivesASpike(unittest.TestCase):
    """Preflight is the gate for the whole run, and it had no retry at all.

    6 November: three brain runs (09:16Z, 09:22Z, 09:24Z) died in preflight on one
    `503 UNAVAILABLE` before any authoring code ran — so the backoff added to the
    authoring path never got a chance to help.
    """

    def test_preflight_uses_the_bounded_retry(self):
        from unittest import mock

        from scripts import gemini_brain as runner

        brain = mock.MagicMock()
        brain.model = "gemini-3.8-flash"
        brain.api_status.return_value = {"key_present": True, "client_ready": True,
                                         "model": brain.model, "reason": "ok"}
        brain._call_model.return_value = "ready"
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": ""}):
            self.assertEqual(runner.cmd_preflight(brain), 0)
        brain._call_model.assert_called_once()

    def test_a_sustained_outage_is_named_upstream_not_silent(self):
        from unittest import mock

        from scripts import gemini_brain as runner

        brain = mock.MagicMock()
        brain.model = "gemini-3.8-flash"
        brain.api_status.return_value = {"key_present": True, "client_ready": True,
                                         "model": brain.model, "reason": "ok"}
        brain._call_model.return_value = ""
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
             mock.patch("builtins.print") as printed:
            self.assertEqual(runner.cmd_preflight(brain), 1)
        text = " ".join(str(c) for c in printed.call_args_list)
        self.assertIn("upstream capacity", text)
