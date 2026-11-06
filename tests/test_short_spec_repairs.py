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
