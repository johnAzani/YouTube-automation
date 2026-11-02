"""Guards for the script expansion pass.

The dangerous failure here is not a crash — it is a plausible-looking rewrite that
drops a reviewed sentence or labels a psalm wrongly and then publishes itself. Every
test below pins one of those refusals.
"""
import tempfile
import unittest
from pathlib import Path

from tools import expand_scripts as ex

FRONT = """---
id: "9001"
title: "{title}"
status: approved
format: longform
voice: Charon
---

"""

BODY = """## Scene 1 — The Watchman (Verse 1)
The Lord is thy keeper: the Lord is thy shade upon thy right hand.
Rest quietly now, because the One watching over you does not grow tired.

## Scene 2 — Coming and Going (Verse 2)
He shall preserve thy going out and thy coming in for evermore.
Sleep deeply, and let tomorrow arrive without your worry.
"""

GOOD_ADDITIONS = {
    "## Scene 1 — The Watchman (Verse 1)": [
        "Notice how gently the promise is worded; it asks nothing of you but trust.",
        "Your part tonight is simply to lie down and let the watchman take the night shift.",
        "Every sound in the house is already known to Him, and none of it alarms Him.",
    ],
    "## Scene 2 — The Watchman (Verse 2)": [
        "Tomorrow's road is not uncharted to the God who walks it ahead of you.",
        "Release the list you have been carrying and let it rest until morning.",
        "There is nothing left for you to guard tonight; that post has been filled.",
    ],
}


def make_job(tmp: Path, title: str = "Psalm 121: He Who Keeps You | The Secret Place") -> ex.Job:
    path = tmp / "9001-test.md"
    path.write_text(FRONT.format(title=title) + BODY, encoding="utf-8")
    return ex.load_job(path)


OPENINGS = [
    "Breathe in slowly through your nose and let the room grow quiet around you",
    "Unclench your hands where they rest and let your jaw soften into the pillow",
    "Let the weight of the day slide off your shoulders and onto the floor",
    "Notice the stillness that has been waiting for you all evening long",
    "Let every muscle in your back remember that it is allowed to rest",
    "Feel the cool of the sheets and let that small comfort be enough",
    "Release the conversation you have been rehearsing in your head",
    "Let your breathing slow until it matches the quiet of the house",
]
CLOSINGS = [
    "and let the night carry what you cannot.",
    "and let tomorrow wait outside the door.",
    "and let the watchman keep the hours for you.",
    "and let your last thought be a peaceful one.",
    "and let sleep arrive without being called.",
    "and let the silence do its gentle work.",
    "and let nothing be solved until sunrise.",
    "and let yourself be held without effort.",
]


def good_provider(job: ex.Job, target: int) -> str:
    """Aims to be what a good model would return: additive, unique, long enough."""
    out = []
    for heading, paragraphs in job.sections():
        out.append(f"## {heading}")
        out.extend(paragraphs)
        out.extend(GOOD_ADDITIONS.get(heading, []))
    filler = [f"{a}, {b}" for a in OPENINGS for b in CLOSINGS]
    body = "\n\n".join(out) + "\n"
    for sentence in filler:
        if len(body.split()) >= target:
            break
        body = body.replace("\n\n## ", f"\n\n{sentence}\n\n## ", 1)
    return body


class TestGate(unittest.TestCase):
    def test_gate_matches_production(self):
        """The floor is shared, not copied: one constant, three consumers."""
        from pipeline.script_doc import MIN_LONGFORM_WORDS
        source = (Path(__file__).resolve().parents[1] / "pipeline" / "prayer_pipeline.py").read_text()
        self.assertEqual(ex.MIN_WORDS, MIN_LONGFORM_WORDS)
        self.assertIn("MIN_LONGFORM_WORDS", source)
        self.assertNotIn("doc.word_count < 650", source)

    def test_under_gate_ignores_drafts_and_long_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            def write(name, job_id, status="approved", extra=""):
                path = d / name
                text = (FRONT.format(title=f"Psalm 121: {job_id}")
                        .replace('"9001"', f'"{job_id}"')
                        .replace("status: approved", f"status: {status}"))
                path.write_text(text + BODY + extra, encoding="utf-8")
                return path

            short = write("9002-short.md", "9002")
            draft = write("9003-draft.md", "9003", status="draft")
            long = write("9004-long.md", "9004", extra="word " * ex.MIN_WORDS)
            found = {j.job_id for j in ex.under_gate([short, draft, long])}
            self.assertEqual(found, {"9002"})


class TestAdditiveGuarantee(unittest.TestCase):
    def test_expansion_keeps_every_original_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            expanded = good_provider(job, ex.MIN_WORDS + 40)
            self.assertEqual(ex.validate(job, expanded), [])
            for line in BODY.strip().splitlines():
                if line.strip():
                    self.assertIn(line.strip(), expanded)

    def test_dropped_line_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            broken = good_provider(job, 700).replace(
                "Rest quietly now, because the One watching over you does not grow tired.", ""
            )
            self.assertTrue(any("dropped or altered" in p for p in ex.validate(job, broken)))

    def test_rewritten_scripture_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            broken = good_provider(job, 700).replace(
                "He shall preserve thy going out", "He will preserve your going out"
            )
            self.assertTrue(any("dropped or altered" in p for p in ex.validate(job, broken)))

    def test_reordered_scenes_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            text = good_provider(job, 700)
            head, _, rest = text.partition("## Scene 2")
            body1 = head.split("## Scene 1")[1]
            broken = "## Scene 1" + rest + "\n## Scene 1" + body1
            self.assertTrue(any("heading" in p for p in ex.validate(job, broken)))


class TestPaddingRefusals(unittest.TestCase):
    def test_duplicate_sentence_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            expanded = good_provider(job, ex.MIN_WORDS + 40)
            first = expanded.strip().split("\n\n")[2]      # an inserted filler sentence
            self.assertTrue(any("repeated verbatim" in p
                                for p in ex.validate(job, expanded + "\n\n" + first + "\n")))

    def test_too_short_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            self.assertTrue(any(f"under the {ex.MIN_WORDS} gate" in p
                                for p in ex.validate(job, job.body + "\nTwo more words.")))

    def test_runaway_length_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            words = " ".join(f"w{i}." for i in range(ex.MAX_WORDS + 50))
            self.assertTrue(any("ceiling" in p for p in ex.validate(job, job.body + words)))

    def test_creator_name_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            expanded = good_provider(job, ex.MIN_WORDS + 40) + "\nNarrated by John Azani.\n"
            problems = ex.validate(job, expanded)
            self.assertTrue(any("creator name" in p for p in problems))


class TestScriptureLabels(unittest.TestCase):
    def test_wrong_psalm_in_body_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp), title="Psalm 27: The Lord Is My Light | The Secret Place")
            job.body = BODY  # Psalm 121 verses under a Psalm 27 title
            self.assertEqual(ex.scripture_mismatch(job), [121])

    def test_matching_psalm_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            self.assertEqual(ex.scripture_mismatch(job), [])

    def test_non_psalm_job_is_never_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp), title="Matthew 11:28-30 Rest for the Weary | The Secret Place")
            job.body = BODY  # quoting a psalm inside a gospel devotional is legitimate
            self.assertEqual(ex.scripture_mismatch(job), [])

    def test_job_with_wrong_scripture_cannot_be_expanded(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp), title="Psalm 27: The Lord Is My Light | The Secret Place")
            job.body = BODY
            problems = ex.validate(job, good_provider(job, 700))
            self.assertTrue(any("re-author it before expanding" in p for p in problems))


class TestWriteSafety(unittest.TestCase):
    def test_dry_run_never_touches_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            before = job.path.read_text(encoding="utf-8")
            ex.expand_job(job, provider="template", write=False)
            self.assertEqual(job.path.read_text(encoding="utf-8"), before)

    def test_write_requires_a_passing_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            before = job.path.read_text(encoding="utf-8")
            result = ex.expand_job(job, provider="template", write=True)  # padding -> fails
            self.assertFalse(result.written)
            self.assertEqual(job.path.read_text(encoding="utf-8"), before)

    def test_write_keeps_frontmatter_and_approved_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            ex.PROVIDERS["_good"] = good_provider
            try:
                result = ex.expand_job(job, provider="_good", target=ex.MIN_WORDS + 40,
                                       write=True)
            finally:
                del ex.PROVIDERS["_good"]
            self.assertTrue(result.written)
            text = job.path.read_text(encoding="utf-8")
            self.assertIn('id: "9001"', text)
            self.assertIn("status: approved", text)
            self.assertGreaterEqual(len(ex.split_frontmatter(text)[1].split()), ex.MIN_WORDS)

    def test_provider_failure_leaves_the_file_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = make_job(Path(tmp))
            before = job.path.read_text(encoding="utf-8")

            def boom(j, t):
                raise RuntimeError("network down")

            ex.PROVIDERS["_boom"] = boom
            try:
                result = ex.expand_job(job, provider="_boom", write=True)
            finally:
                del ex.PROVIDERS["_boom"]
            self.assertFalse(result.written)
            self.assertTrue(any("provider error" in p for p in result.problems))
            self.assertEqual(job.path.read_text(encoding="utf-8"), before)


class TestCli(unittest.TestCase):
    def test_refuses_to_write_with_the_template_provider(self):
        self.assertEqual(ex.main(["--provider", "template", "--write"]), 2)


if __name__ == "__main__":
    unittest.main()
