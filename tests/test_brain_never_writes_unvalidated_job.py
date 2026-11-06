"""The brain may not put a job in the queue it cannot itself validate.

On 6 November 2026 the 14:12Z production run authored a Morning Altar devotional
whose header read `job_id: 0040` instead of `id:`, carried no `slug:`, `niche:`,
`thumb_text:` or `originality:`, and had no fact-check worksheet. Three things
turned that into a defect on `main` rather than a failed authoring attempt:

1. the acceptance test was the substring `"id:" in text`, which matches *inside*
   `job_id:` — so the malformed script was accepted;
2. the file was written to `content/queue/` **before** `verify_and_stage` ran, so
   the niche gate's refusal left the file behind;
3. the production workflow commits everything under `content/` on `always()`, so
   the orphan was swept into `main`, where it failed nine integrity tests at once
   (including `test_every_queued_job_is_in_niche`, the guard written for exactly
   this class of bug).

YAML made it worse in a way nobody would guess: bare `0040` is octal, so the job
parsed with `job_id: 32`.

These tests hold the three fixes.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from pipeline import gemini_brain
from pipeline.gemini_brain import (BrainAuthoringError, GeminiBrain,
                                   missing_job_keys)

ROOT = Path(__file__).resolve().parents[1]

COMPLETE = """---
id: "0040"
slug: he-shall-direct-thy-paths
title: "HE SHALL DIRECT THY PATHS: A Morning Prayer of Trust & Guidance"
channel: prayer2
status: approved
format: longform
niche: faith
thumb_text: "HE DIRECTS MY PATH"
originality: "Original exposition; no copied commentary."
---

## Scene 1 — The Sunrise Invitation

Trust in the Lord with all thine heart, and lean not unto thine own understanding.

## Scene 2 — Surrendering the Day

In all thy ways acknowledge him, and he shall direct thy paths. Subscribe to
The Morning Altar to begin every sunrise with us.
"""

#: What the model actually returned on 6 November: a `job_id:` header, no slug,
#: no niche, no originality checklist. It still contained `## Scene`, and it still
#: satisfied the old `"id:" in text` test.
MALFORMED = """---
job_id: 0040
channel: prayer2
title: "HE SHALL DIRECT THY PATHS"
format: longform
privacy: public
voice: Charon
thumbnail_text: "HE DIRECTS MY PATH"
---

## Scene 1 — The Sunrise Invitation

Trust in the Lord with all thine heart, and lean not unto thine own understanding.
The Morning Altar meets you at sunrise.
"""


class TestTheQueueContractIsChecked(unittest.TestCase):
    def test_a_job_id_header_is_not_an_id_header(self):
        missing = missing_job_keys(MALFORMED)
        self.assertIn("id", missing, "`job_id:` must never satisfy the `id` key")
        self.assertIn("slug", missing)
        self.assertIn("niche", missing)
        self.assertIn("originality", missing)

    def test_a_complete_job_passes(self):
        self.assertEqual(missing_job_keys(COMPLETE), [])

    def test_every_file_the_brain_wrote_before_is_accepted_today(self):
        """The gate must describe the queue as it really is, not a stricter ideal."""
        for path in sorted((ROOT / "content" / "queue").glob("*.md")):
            if path.name.lower() == "readme.md":
                continue
            with self.subTest(job=path.name):
                self.assertEqual(missing_job_keys(path.read_text(encoding="utf-8")), [])

    def test_yaml_octal_is_why_the_bad_file_parsed_as_job_32(self):
        meta = gemini_brain.job_front_matter(MALFORMED)
        self.assertEqual(meta["job_id"], 32, "bare 0040 is octal, not forty")


class TestAuthoringClimbsInsteadOfWritingJunk(unittest.TestCase):
    def _brain(self, replies):
        brain = GeminiBrain(api_key="", channel_id="prayer2")
        brain._client = mock.MagicMock()

        def _generate(model, contents, config=None):
            return mock.MagicMock(text=replies(model))

        brain._client.models.generate_content.side_effect = _generate
        return brain

    def test_a_malformed_response_escalates_to_the_next_model(self):
        brain = self._brain(lambda model: MALFORMED if model == "gemini-3.5-flash-lite"
                            else COMPLETE)
        with mock.patch("builtins.print"):
            text = brain.author_longform_script({"id": "0040", "scripture": "Proverbs 3:5-6"})
        self.assertEqual(text.strip(), COMPLETE.strip())
        calls = [c.kwargs.get("model") or c.args[0]
                 for c in brain._client.models.generate_content.call_args_list]
        self.assertEqual(calls[0], "gemini-3.5-flash-lite")
        self.assertIn("gemini-3.1-flash-lite", calls, "the chain must be climbed")

    def test_when_every_model_is_malformed_nothing_is_returned(self):
        brain = self._brain(lambda model: MALFORMED)
        with mock.patch("builtins.print"):
            with self.assertRaises(BrainAuthoringError) as ctx:
                brain.author_longform_script({"id": "0040", "scripture": "Proverbs 3:5-6"})
        message = str(ctx.exception)
        self.assertIn("front matter the queue requires", message)
        self.assertIn("Nothing was written", message)


class TestTheFileCannotBePickedUpBeforeItIsValid(unittest.TestCase):
    def test_a_refused_job_never_reaches_the_queue(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue"
            queue.mkdir()
            brain = GeminiBrain(api_key="", channel_id="prayer2")

            with mock.patch.object(gemini_brain, "QUEUE_DIR", queue), \
                 mock.patch("pipeline.supply.publishable_longform", return_value=[]), \
                 mock.patch.object(brain, "select_next_scripture",
                                   return_value={"id": "0040", "scripture": "Proverbs 3:5-6"}), \
                 mock.patch.object(brain, "author_longform_script", return_value=COMPLETE), \
                 mock.patch.object(brain, "verify_and_stage",
                                   side_effect=RuntimeError("Refusing out-of-niche job 0040")), \
                 mock.patch("builtins.print"):
                with self.assertRaises(RuntimeError):
                    brain.replenish_pipeline(min_runway_days=999.0)

            self.assertEqual(list(queue.glob("*.md")), [],
                             "a job that failed validation is still pickable by the scheduler")
            self.assertEqual(list((queue / ".incoming").glob("*")), [],
                             "the staged copy was not cleaned up")

    def test_a_valid_job_is_moved_in_after_it_passes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp) / "queue"
            queue.mkdir()
            brain = GeminiBrain(api_key="", channel_id="prayer2")
            staged_seen = {}

            def _verify(path):
                staged_seen["path"] = Path(path)
                self.assertNotEqual(Path(path).parent.name, "queue",
                                    "validation must run outside the scheduler's glob")
                return gemini_brain.BrainGenerationResult(
                    job_id="0040", scripture="Proverbs 3:5-6", longform_path=Path(path),
                    short_manifest_path=None, factcheck_path=None, status="approved",
                    word_count=900, scene_count=6, used_gemini_api=True)

            with mock.patch.object(gemini_brain, "QUEUE_DIR", queue), \
                 mock.patch("pipeline.supply.publishable_longform", return_value=[]), \
                 mock.patch.object(brain, "select_next_scripture",
                                   return_value={"id": "0040", "scripture": "Proverbs 3:5-6"}), \
                 mock.patch.object(brain, "author_longform_script", return_value=COMPLETE), \
                 mock.patch.object(brain, "verify_and_stage", side_effect=_verify), \
                 mock.patch("builtins.print"):
                result = brain.replenish_pipeline(min_runway_days=999.0)

            landed = queue / "0040-he-shall-direct-thy-paths.md"
            self.assertTrue(landed.is_file(), "a validated job must land in the queue")
            self.assertEqual(result.longform_path, landed)
            self.assertTrue(str(staged_seen["path"]).endswith(landed.name))


if __name__ == "__main__":
    unittest.main()
