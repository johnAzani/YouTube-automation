"""The validator rejected two valid Shorts for punctuation and empty strings.

6 November, the first green brain run in hours: it reached the Morning Altar queue and
both specs were rejected twice, so `shorts:prayer2` stayed at 0 ready.

* `0038` — "beat 3: anchor 'his mercies never come to an end.' does not appear in the
  narration". The anchor *was* verbatim; it ended with a full stop where the narration
  carried a comma, and `_norm` only collapsed whitespace. Punctuation is not content.
* `0039` — "kinetic phrase 1: blank highlight word" ×4. A blank highlight highlights
  nothing: a formatting defect the validator can fix, not a reason to spend two more
  requests of a twenty-a-day allowance.

Both are now handled: comparison ignores punctuation, and blank highlight words are
dropped with the repair recorded on the spec.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.short_script import validate_spec

SPECS = Path(__file__).resolve().parents[1] / "content" / "shorts-scripts"


def _baseline() -> dict:
    return json.loads((SPECS / "short-isaiah26v3.json").read_text(encoding="utf-8"))


class TestPunctuationIsNotContent(unittest.TestCase):
    def test_a_verbatim_anchor_with_other_punctuation_matches(self):
        data = _baseline()
        caption = data["captions"][1][2].rstrip(".,!?;:")
        data["beats"][0]["a"] = caption + "."
        self.assertIn(caption.split()[0], data["captions"][1][2])
        spec = validate_spec(data, key=data["key"])
        self.assertFalse([p for p in spec.problems if "does not appear" in p],
                         spec.problems)

    def test_an_anchor_that_was_never_said_still_fails(self):
        data = _baseline()
        data["beats"][0]["a"] = "the mountains will sing before breakfast"
        spec = validate_spec(data, key=data["key"])
        self.assertTrue([p for p in spec.problems if "does not appear" in p])


class TestBlankHighlightsAreRepaired(unittest.TestCase):
    def test_blank_entries_are_dropped_and_recorded(self):
        data = _baseline()
        data["kinetic_phrases"][0][3] = [" ", ""]
        spec = validate_spec(data, key=data["key"])
        self.assertFalse([p for p in spec.problems if "blank highlight" in p], spec.problems)
        self.assertEqual(spec.kinetic_phrases[0][3], [])
        self.assertTrue(any("blank highlight" in r for r in spec.repairs), spec.repairs)

    def test_real_highlights_survive_untouched(self):
        data = _baseline()
        original = list(data["kinetic_phrases"][0][3])
        spec = validate_spec(data, key=data["key"])
        self.assertEqual(spec.kinetic_phrases[0][3], original)
        self.assertEqual(spec.repairs, [])

    def test_the_baseline_spec_is_clean(self):
        spec = validate_spec(_baseline(), key="short-isaiah26v3")
        self.assertEqual(spec.problems, [], "the fixture must be a valid spec")


if __name__ == "__main__":
    unittest.main()


class TestEscalationAcrossModels(unittest.TestCase):
    """A capability defect is not fixed by re-asking the same model.

    6 November: `gemini-3.5-flash-lite` returned a 43-word Short where 90-165 is
    enforced, twice, and the run gave up — five scenes instead of six, and no retry
    left. The chain already holds stronger models; a rejected spec should climb it.
    """

    def test_a_thin_spec_escalates_to_the_next_model(self):
        from unittest import mock

        from pipeline import gemini_brain

        brain = gemini_brain.GeminiBrain(api_key="")
        brain._client = mock.MagicMock()
        thin = json.dumps({"title": ["A", "B"]})          # rejected by validation
        good = json.dumps(_baseline())

        def _generate(model, contents, config=None):
            text = thin if model == "gemini-3.5-flash-lite" else good
            return mock.MagicMock(text=text)

        brain._client.models.generate_content.side_effect = _generate
        from pipeline.script_doc import parse_script

        doc = parse_script(Path(__file__).resolve().parents[1] / "content" / "published"
                           / "0013-psalm-46-god-is-our-refuge-and-strength.md")
        with mock.patch.object(gemini_brain, "_TRANSIENT_BACKOFF", ()), \
             mock.patch("builtins.print"):
            spec = brain.author_short_spec(doc, key="short-isaiah26v3")
        self.assertEqual(spec.key, "short-isaiah26v3")
        models = [c.kwargs["model"] if c.kwargs else c.args[0]
                  for c in brain._client.models.generate_content.call_args_list]
        self.assertEqual(models[0], "gemini-3.5-flash-lite")
        self.assertIn("gemini-3.1-flash-lite", models, "the chain must be climbed")
