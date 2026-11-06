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
        self.assertEqual(DEFAULT_TEXT_MODEL, "gemini-3.8-flash")

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
        self.assertEqual(first_live, "gemini-3.8-flash")


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
