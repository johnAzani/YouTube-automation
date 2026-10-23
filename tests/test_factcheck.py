"""The fact-check worksheet generator must extract, and must never verify.

`scripts/factcheck.py` exists to take the mechanical part out of the human gate that
`pipeline/originality.py` enforces: pull every checkable claim out of a script and put it
next to the job's own sources. The judgement stays human. Two invariants matter more than
the extraction quality:

1. It must not assert a verdict. A pre-ticked box, or any wording that implies a claim was
   checked, would let an unverified script reach `status: approved` with a clean-looking
   worksheet next to it.
2. Its output must never land in `content/queue/`. That directory is globbed by
   `pipeline/run.py::select_jobs`, `scripts/doctor.py`, the queue-integrity tests and
   `dry-run.yml`, so a worksheet there would be picked up as a renderable job.
"""
from pathlib import Path
import unittest

from pipeline.script_doc import parse_script
from scripts import factcheck

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "content" / "queue"
OUT_DIR = ROOT / "content" / "factcheck"


class ClaimExtractionTests(unittest.TestCase):
    def test_spelled_out_figure_is_a_claim(self):
        """The narration spells numbers out for TTS, so digit-matching would find nothing."""
        ok, reasons = factcheck.classify(
            "By the end of two thousand and seven Lehman was running roughly thirty-one "
            "dollars of assets for every dollar of shareholder equity.")
        self.assertTrue(ok)
        self.assertIn("figure", reasons)

    def test_date_is_a_claim(self):
        ok, reasons = factcheck.classify("On the morning of September fifteenth the firm filed.")
        self.assertTrue(ok)
        self.assertIn("date", reasons)

    def test_plain_sentence_with_no_figure_or_name_is_not_a_claim(self):
        ok, reasons = factcheck.classify("That is a repurchase agreement, and in substance "
                                         "it is a secured loan.")
        self.assertFalse(ok, f"expected no reasons, got {reasons}")

    def test_sentence_initial_name_is_kept_when_it_is_clearly_a_name(self):
        _, reasons = factcheck.classify("Lehman Brothers had survived the Civil War.")
        named = [r for r in reasons if r.startswith("named:")]
        self.assertIn("Lehman Brothers", named[0],
                      "two capitals at index 0 is a name, not just sentence grammar")

    def test_lone_sentence_initial_capital_is_not_treated_as_a_name(self):
        ok, reasons = factcheck.classify("That was the whole problem with the structure.")
        self.assertFalse(ok, f"a normal capitalised first word is not a claim: {reasons}")

    def test_multiword_names_group_instead_of_splitting(self):
        _, reasons = factcheck.classify("It moved to New York and became a name on Wall Street.")
        named = [r for r in reasons if r.startswith("named:")]
        self.assertTrue(named)
        self.assertIn("New York", named[0])
        self.assertIn("Wall Street", named[0])

    def test_possessive_is_trimmed_without_mangling_the_word(self):
        """Regression: an earlier version used `rstrip("'s")`, which strips a character set
        and would have turned "Lehman Brothers" into "Lehman Brother"."""
        _, reasons = factcheck.classify("Lehman Brothers had survived the Civil War.")
        named = [r for r in reasons if r.startswith("named:")]
        self.assertTrue(named)
        self.assertIn("Lehman Brothers", named[0])
        self.assertNotIn("Lehman Brother,", named[0])


class WorksheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jobs = sorted(p for p in QUEUE_DIR.glob("*.md") if p.stem.lower() != "readme")
        if not cls.jobs:
            raise AssertionError(f"{QUEUE_DIR} is empty — nothing to generate worksheets for")

    def test_every_queued_job_has_a_worksheet_covering_every_scene(self):
        for path in self.jobs:
            doc = parse_script(path)
            sheet = OUT_DIR / f"{doc.id}-{doc.slug}.md"
            with self.subTest(job=path.name):
                self.assertTrue(sheet.is_file(),
                                f"{sheet.relative_to(ROOT)} missing — run `python scripts/factcheck.py`")
                text = sheet.read_text(encoding="utf-8")
                for scene in doc.scenes:
                    self.assertIn(f"### Scene {scene.index} — {scene.heading}", text,
                                  f"scene {scene.index} has no section in the worksheet")
                self.assertIn(f"job {doc.id}", text)

    def test_worksheet_never_asserts_a_verdict(self):
        """An unticked box is the only correct starting state."""
        for path in self.jobs:
            doc = parse_script(path)
            text = (OUT_DIR / f"{doc.id}-{doc.slug}.md").read_text(encoding="utf-8")
            with self.subTest(job=path.name):
                self.assertNotIn("- [x]", text, "the generator must not pre-tick anything")
                self.assertIn("verifies nothing", text,
                              "the worksheet must say plainly that it checked nothing")
                # Every extracted claim must carry a blank for the human to fill in.
                self.assertIn("→ source: ____", text)

    def test_worksheet_records_the_script_hash_it_was_built_from(self):
        for path in self.jobs:
            doc = parse_script(path)
            text = (OUT_DIR / f"{doc.id}-{doc.slug}.md").read_text(encoding="utf-8")
            with self.subTest(job=path.name):
                self.assertIn(factcheck._sha(path), text,
                              "worksheet must embed the source sha256 so staleness is visible")

    def test_worksheet_lists_the_jobs_own_declared_sources(self):
        doc = parse_script(QUEUE_DIR / "0003-how-lehman-brothers-died.md")
        text = (OUT_DIR / f"{doc.id}-{doc.slug}.md").read_text(encoding="utf-8")
        for source in factcheck._sources(doc):
            self.assertIn(source, text, f"declared source missing from worksheet: {source}")
        self.assertIn("Valukas", text, "the Lehman examiner report should be listed first")

    def test_no_substantive_sentence_is_silently_dropped(self):
        """The extractor is deliberately dumb, so it misses claims with no figure, date or
        proper noun — "a repo is in substance a secured loan" is load-bearing and has none.
        Those must still appear, as a reading prompt, or a human could tick every box and
        never see them."""
        for path in self.jobs:
            doc = parse_script(path)
            text = (OUT_DIR / f"{doc.id}-{doc.slug}.md").read_text(encoding="utf-8")
            flat = " ".join(text.split())
            for scene in doc.scenes:
                for sentence in factcheck._sentences(scene.narration):
                    if len(sentence.split()) < factcheck.MIN_UNFLAGGED_WORDS:
                        continue  # short connective sentences are not worth a line
                    with self.subTest(job=path.name, scene=scene.index):
                        self.assertIn(" ".join(sentence.split()), flat,
                                      "a substantive sentence appears nowhere in the worksheet")

    def test_worksheets_do_not_live_anywhere_the_scheduler_globs(self):
        """Regression guard: a worksheet in content/queue/ would be parsed as a job."""
        self.assertNotEqual(OUT_DIR, QUEUE_DIR)
        self.assertEqual(OUT_DIR.parent.name, "content")
        for path in QUEUE_DIR.glob("*.md"):
            self.assertNotIn("factcheck", path.name.lower(),
                             f"{path.name} sits in the scheduler's glob")
        # And the generator's own constant must not point at the queue.
        self.assertNotIn("queue", str(factcheck.OUT_DIR.relative_to(ROOT)))

    def test_regeneration_is_refused_without_force(self):
        """A filled-in worksheet is human work; the tool must not clobber it silently."""
        doc = parse_script(QUEUE_DIR / "0003-how-lehman-brothers-died.md")
        dest = factcheck.out_path(doc)
        original = dest.read_text(encoding="utf-8")
        marker = "\n- [x] I checked this one\n"
        dest.write_text(original + marker, encoding="utf-8")
        try:
            rc = factcheck.main([doc.id])
            self.assertEqual(rc, 0)
            self.assertIn(marker, dest.read_text(encoding="utf-8"),
                          "a plain re-run must leave the human's ticks alone")
        finally:
            dest.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
