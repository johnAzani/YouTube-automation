"""The four ways this pipeline went green while publishing nothing.

Each test here is a post-mortem that has been turned into a guard:

1. **Two gates disagreed.** Production refused scripts under 650 words, and the
   renderer separately refused narration under 300 seconds. At Charon's measured
   pace 650 words is about four minutes, so the word gate admitted scripts that
   could never render — and each one cost a full TTS call before failing.
2. **The expansion instruction contradicted itself.** "Add 2-4 sentences per
   scene" cannot reach 900 words, so a rule-following model returned valid,
   permanently-short output, `validate` refused it, and 21 scripts sat at
   227-443 words while every run reported success.
3. **Nothing was ever kept.** Because a short-but-safe expansion was discarded,
   each run restarted from the same short script and made no progress, forever.
4. **An empty queue was not an error.** `pipeline.run` returned 0 with a friendly
   notice, so three production slots a day could pass with no upload and a green
   tick, and the monitor did not look at uploads at all.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import script_doc
from pipeline.script_doc import (CHARON_WORDS_PER_MINUTE, MIN_LONGFORM_WORDS,
                                 MIN_NARRATION_SECONDS, required_words)
from tools import expand_scripts as ex

FRONT = """---
id: "9001"
title: "Psalm 121: He Who Keeps You | The Secret Place"
status: approved
format: longform
voice: Charon
---

"""
BODY = """## Scene 1 — The Watchman (Verse 1)
I will lift up mine eyes unto the hills, from whence cometh my help.
He that keepeth thee will not slumber.
Rest quietly now, because the One watching over you does not grow tired.

## Scene 2 — Coming and Going (Verse 2)
The Lord is thy keeper: the Lord is thy shade upon thy right hand.
Sleep deeply, and let tomorrow arrive without your worry.
"""


def write_job(tmp: Path, body: str = BODY) -> Path:
    path = tmp / "9001-test.md"
    path.write_text(FRONT + body, encoding="utf-8")
    return path


def filler_sentences(n: int) -> list[str]:
    """n sentences that are distinct, long enough to count, and about the psalm."""
    return [f"Stay with the promise in verse {i % 9} and let your breathing slow "
            f"while the night settles quietly around the house number {i}." for i in range(n)]


def incremental(ratio: float = 0.5):
    """A model that delivers only `ratio` of the budget it is given.

    This is the real behaviour that stalled the queue: output that is safe,
    additive and short. It *does* respond to a larger budget, which is why the
    prompt now states the shortfall in words instead of asking for "2-4 sentences".
    """

    calls = {"n": 0, "cursor": 0}
    pool = filler_sentences(6000)

    def provider(job, target=900):
        calls["n"] += 1
        sections = max(1, len(job.sections()))
        need = max(0, target - job.words)
        add = max(28, int(need * ratio))
        per_scene = max(1, (add // 24) // sections)
        parts = []
        for heading, paragraphs in job.sections():
            added = pool[calls["cursor"]:calls["cursor"] + per_scene]
            calls["cursor"] += per_scene
            parts.append(f"## {heading}\n" + "\n".join(paragraphs + added))
        return "\n\n".join(parts) + "\n"

    return provider, calls


class TestTheGatesAgree(unittest.TestCase):
    def test_the_word_floor_can_actually_reach_five_minutes(self):
        """The old failure: 650 words passed the floor and died at 300 seconds."""
        self.assertEqual(MIN_NARRATION_SECONDS, 300)
        self.assertGreaterEqual(MIN_LONGFORM_WORDS, required_words(MIN_NARRATION_SECONDS))
        minutes = MIN_LONGFORM_WORDS / CHARON_WORDS_PER_MINUTE
        self.assertGreaterEqual(minutes, 5.0)

    def test_the_old_floor_would_fail_this_check(self):
        """650 words is 3.9 minutes at Charon's pace — it was never a 5-minute gate."""
        self.assertLess(650, required_words(300))

    def test_the_renderer_uses_the_shared_seconds_not_a_literal(self):
        source = (Path(__file__).resolve().parents[1] / "pipeline" / "prayer_pipeline.py").read_text()
        self.assertIn("MIN_NARRATION_SECONDS", source)
        self.assertNotIn("duration < 300", source)

    def test_required_words_matches_the_published_measurement(self):
        """Job 0010 rendered 5:22 from 884 words — about 165 words a minute."""
        self.assertAlmostEqual(884 / (322 / 60), CHARON_WORDS_PER_MINUTE, delta=2)


class TestTheInstructionIsArithmetic(unittest.TestCase):
    def test_the_budget_covers_the_shortfall(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = ex.load_job(write_job(Path(tmp)))
            need, per_scene = ex.budget_for(job, target=ex.TARGET_WORDS)
            self.assertEqual(need, max(0, ex.MIN_WORDS - job.words))
            self.assertGreaterEqual(per_scene * len(job.sections()), need)

    def test_a_script_already_over_the_floor_needs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = ex.load_job(write_job(Path(tmp)))
            job.body = job.body + " word" * ex.MIN_WORDS
            need, _ = ex.budget_for(job, target=900)
            self.assertEqual(need, 0)

    def test_the_prompt_states_the_arithmetic_and_the_floor(self):
        source = (Path(__file__).resolve().parents[1] / "tools" / "expand_scripts.py").read_text()
        self.assertIn("{need}", source)          # words you must add
        self.assertIn("{per_scene}", source)     # spread over existing scenes
        self.assertIn("{min_words}", source)     # the floor itself
        self.assertNotIn("Add 2-4 sentences of new narration per existing scene", source)


class TestItConvergesInsteadOfStalling(unittest.TestCase):
    def test_repeatedly_short_but_safe_output_is_kept_and_grows(self):
        """The 21-script stall: every attempt was discarded, so nothing grew."""
        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            provider, calls = incremental(ratio=0.5)
            job = ex.load_job(path)
            with mock.patch.dict(ex.PROVIDERS, {"_slow": provider}):
                result = ex.expand_job(job, provider="_slow", target=ex.MIN_WORDS + 40,
                                       write=True, attempts=6)
            self.assertTrue(result.written)
            self.assertGreater(result.after, result.before)
            self.assertGreater(calls["n"], 1, "should have needed more than one attempt")
            self.assertTrue(result.problems == [] or result.after < ex.MIN_WORDS)
            after = ex.load_job(path).words
            self.assertGreater(after, result.before)

    def test_it_stops_at_the_floor_rather_than_padding_forever(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            provider, calls = incremental(ratio=0.6)
            job = ex.load_job(path)
            with mock.patch.dict(ex.PROVIDERS, {"_slow": provider}):
                result = ex.expand_job(job, provider="_slow", target=ex.MIN_WORDS + 40,
                                       write=True, attempts=8)
            self.assertEqual(result.problems, [])
            words = ex.load_job(path).words
            self.assertGreaterEqual(words, ex.MIN_WORDS)
            self.assertLessEqual(words, ex.MAX_WORDS)
            self.assertLessEqual(calls["n"], 8)

    def test_a_rule_violation_is_still_never_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            before = path.read_text(encoding="utf-8")

            def rewrite(job, target=900):
                return "## Scene 1 — The Watchman\nTotally different words now.\n"

            with mock.patch.dict(ex.PROVIDERS, {"_bad": rewrite}):
                result = ex.expand_job(ex.load_job(path), provider="_bad", write=True,
                                       attempts=3)
            self.assertFalse(result.written)
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertTrue(any("dropped" in p for p in result.problems))

    def test_a_provider_that_never_varies_does_not_loop_forever(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            calls = []

            def stuck(job, target=900):
                calls.append(1)
                return job.body            # identical body: safe, but zero progress

            with mock.patch.dict(ex.PROVIDERS, {"_stuck": stuck}):
                result = ex.expand_job(ex.load_job(path), provider="_stuck", write=True,
                                       attempts=3)
            self.assertLessEqual(len(calls), 3)
            self.assertTrue(result.problems)
            self.assertIn("under the", result.problems[0])


class TestApprovalMeansPublishable(unittest.TestCase):
    def test_set_status_refuses_to_approve_a_short_script(self):
        from pipeline import supply as sp

        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                sp.set_status(path, "approved", approved_by="brain")
            self.assertIn(f"{MIN_LONGFORM_WORDS}", str(ctx.exception))
            self.assertIn("status: approved", path.read_text(encoding="utf-8"))  # unchanged

    def test_set_status_still_approves_a_script_over_the_floor(self):
        from pipeline import supply as sp

        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp), body=BODY + "\n" + " ".join(filler_sentences(80)))
            sp.set_status(path, "approved", approved_by="brain")
            self.assertIn("approved_by: brain", path.read_text(encoding="utf-8"))

    def test_a_draft_may_be_marked_draft_at_any_length(self):
        from pipeline import supply as sp

        with tempfile.TemporaryDirectory() as tmp:
            path = write_job(Path(tmp))
            sp.set_status(path, "draft")          # never raises
            self.assertIn("status: draft", path.read_text(encoding="utf-8"))


class TestAnEmptySlotIsAFailure(unittest.TestCase):
    def test_the_reason_names_the_worst_script(self):
        from pipeline import run as pr

        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp)
            (queue / "0001-a.md").write_text(
                "---\nid: '0001'\nstatus: approved\nformat: longform\n---\n\n"
                "## Scene 1 — One\n" + "word " * 300, encoding="utf-8")
            with mock.patch.object(pr, "QUEUE_DIR", queue):
                reason = pr.empty_reason()
            self.assertIn(f"{MIN_LONGFORM_WORDS}-word floor", reason)
            self.assertIn("0001-a.md", reason)
            self.assertIn(str(MIN_LONGFORM_WORDS - 300), reason)

    def test_no_approved_script_at_all_is_reported_as_a_supply_fault(self):
        from pipeline import run as pr

        with tempfile.TemporaryDirectory() as tmp:
            queue = Path(tmp)
            (queue / "0001-a.md").write_text(
                "---\nid: '0001'\nstatus: draft\nformat: longform\n---\n\nbody\n",
                encoding="utf-8")
            with mock.patch.object(pr, "QUEUE_DIR", queue):
                reason = pr.empty_reason()
            self.assertIn("no approved long-form script", reason)

    def test_run_next_exits_non_zero_when_nothing_is_publishable(self):
        """It used to return 0 — that is the green tick the owner kept reporting."""
        from pipeline import run as pr

        with mock.patch.object(pr, "select_jobs", return_value=[]), \
             mock.patch.object(pr, "empty_reason", return_value="21 scripts under the floor"):
            self.assertEqual(pr.main(["--next"]), 2)


class TestTheDuplicateIsCaughtBeforeTheRender(unittest.TestCase):
    """A publish whose commit failed leaves the script in the queue looking new.

    On 2 November that happened: Psalm 46 was live, main still listed 0013 as
    approved. Without a pre-render check the next release slot re-renders the whole
    video and only then discovers the duplicate at upload time.
    """

    def test_a_title_already_on_the_channel_is_recorded_not_re_rendered(self):
        import tempfile
        from unittest import mock

        from pipeline import prayer_pipeline as pp
        from pipeline.script_doc import parse_script

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "0013-x.md"
            path.write_text("---\nid: '0013'\nslug: psalm-46\nstatus: approved\n"
                            "format: longform\nniche: faith and prayer\nvoice: Charon\n"
                            "title: Psalm 46\n---\n\n## Scene 1 — One\n" + "word " * 900,
                            encoding="utf-8")
            doc = parse_script(path)
            with mock.patch.object(pp, "already_published", return_value="live123"), \
                 mock.patch.object(pp, "enforce", lambda doc: doc), \
                 mock.patch("pipeline.run._require_production_prerequisites",
                            lambda *a, **k: None), \
                 mock.patch("pipeline.run._mark_job_uploaded") as marked, \
                 mock.patch.object(pp, "OUTPUT_DIR", Path(tmp) / "out"):
                result = pp.produce(path, dry_run=False, model_dir=Path(tmp))
        self.assertEqual(result["video_id"], "live123")
        self.assertEqual(result["privacy_status"], "already_published")
        self.assertFalse(result["uploaded"])
        marked.assert_called_once()

    def test_the_pre_check_never_blocks_a_release(self):
        from unittest import mock

        from pipeline import prayer_pipeline as pp

        class Doc:
            title, slug = "x", "y"

        with mock.patch("pipeline.upload._credentials", side_effect=RuntimeError("no creds")):
            self.assertIsNone(pp.already_published(Doc()))

    def test_it_is_skipped_when_duplicates_are_allowed(self):
        from unittest import mock

        from pipeline import prayer_pipeline as pp

        class Doc:
            title, slug = "x", "y"

        with mock.patch.object(pp.CONFIG, "allow_duplicate_uploads", True, create=True):
            self.assertIsNone(pp.already_published(Doc()))


class TestRecordingADuplicateDoesNotConsumeTheSlot(unittest.TestCase):
    """Bookkeeping is not a release.

    With 0013 live but unrecorded, the 3:14pm slot would have found it, filed it,
    and exited — publishing nothing new for the day.
    """

    def test_run_next_moves_on_to_the_next_job_after_an_already_live_one(self):
        from unittest import mock

        from pipeline import run as pr

        a, b = Path("content/queue/0013-a.md"), Path("content/queue/0017-b.md")
        seen = []

        def fake_process(path, dry):
            seen.append(path)
            if path == a:
                return {"privacy_status": "already_published", "video_id": "live1"}
            return {"privacy_status": "public", "video_id": "new1"}

        # first call is the --next selection, second the re-selection after recording
        selections = [[a], [b]]

        def fake_select(all_flag, job_path, next_flag):
            return selections.pop(0) if selections else []

        with mock.patch.object(pr, "select_jobs", side_effect=fake_select), \
             mock.patch.object(pr, "process", fake_process), \
             mock.patch.object(pr, "CONFIG") as cfg, \
             mock.patch.dict("os.environ", {"DRY_RUN": "0"}):
            cfg.dry_run = False
            cfg.ensure_dirs = lambda: None
            code = pr.main(["--next"])
        self.assertEqual(code, 0)
        self.assertEqual(seen, [a, b], "should record the duplicate, then publish the next job")

    def test_it_stops_once_something_is_actually_published(self):
        from unittest import mock

        from pipeline import run as pr

        a, b = Path("content/queue/0017-a.md"), Path("content/queue/0018-b.md")
        seen = []

        def fake_process(path, dry):
            seen.append(path)
            return {"privacy_status": "public", "video_id": "new1"}

        with mock.patch.object(pr, "select_jobs", return_value=[a, b]), \
             mock.patch.object(pr, "process", fake_process), \
             mock.patch.object(pr, "CONFIG") as cfg, \
             mock.patch.dict("os.environ", {"DRY_RUN": "0"}):
            cfg.dry_run = False
            cfg.ensure_dirs = lambda: None
            pr.main(["--next"])
        self.assertEqual(len(seen), 1, "one release per slot, not a queue drain")


class TestTheVideoWearsItsOwnThumbnail(unittest.TestCase):
    """Psalm 46 premiered with Psalm 121's thumbnail.

    The pack was rendered with no knowledge of the job: fixed copy, fixed seed. Every
    script in the queue already carries a distinct ``thumb_text``; nothing passed it
    to the renderer.
    """

    def _source(self):
        return (Path(__file__).resolve().parents[1]
                / "pipeline" / "prayer_pipeline.py").read_text(encoding="utf-8")

    def test_the_render_is_handed_the_scripts_own_line(self):
        self.assertIn('hero_override=doc.meta.get("thumb_text")', self._source())

    def test_the_render_is_reseeded_per_job(self):
        self.assertIn('doc_key=doc.id or doc.slug', self._source())

    def test_a_duplicate_receipt_also_repairs_the_live_picture(self):
        self.assertIn("_refresh_live_thumbnail(doc, existing, job_dir)", self._source())

    def test_every_queued_script_has_a_distinct_line(self):
        seen = {}
        for path in sorted((Path(__file__).resolve().parents[1] / "content" / "queue").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            line = ""
            for row in text.splitlines():
                if row.startswith("thumb_text:"):
                    line = row.split(":", 1)[1].strip().strip('"').upper()
                    break
            self.assertTrue(line, f"{path.name} has no thumb_text")
            self.assertNotIn(line, seen, f"{path.name} repeats {seen.get(line)}'s thumbnail line")
            seen[line] = path.name


class TestTheHealthAuditCannotGoSilent(unittest.TestCase):
    """A workflow that never starts never fails.

    automation-health.yml is the job that reports silent crons, and on 2 November it
    had zero runs: its nightly cron had not come round and its workflow_run only
    fires when a production run finishes. The auditor was the thing going silent.
    """

    def _wf(self):
        import yaml
        path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "automation-health.yml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_it_runs_on_a_push_not_only_on_a_schedule(self):
        on = self._wf()[True]
        self.assertIn("push", on, "the audit must not wait for a cron that may not fire")
        self.assertEqual(on["push"]["branches"], ["main"])

    def test_a_push_audits_but_does_not_file_an_issue(self):
        steps = self._wf()["jobs"]["health"]["steps"]
        filing = [s for s in steps if "pipeline_watchdog" in str(s.get("run", ""))]
        self.assertEqual(len(filing), 1)
        self.assertIn("github.event_name != 'push'", str(filing[0].get("if", "")))


class TestTheWorkflowCannotLoseState(unittest.TestCase):
    def workflow(self, name):
        return (Path(__file__).resolve().parents[1] / ".github" / "workflows" / name).read_text()

    def test_production_and_the_supervisor_share_one_content_lock(self):
        self.assertIn("group: content-state", self.workflow("produce.yml"))
        self.assertIn("group: content-state", self.workflow("scheduler-supervisor.yml"))

    def test_the_publish_commit_cannot_loop_on_the_same_conflict(self):
        """On 2 Nov it retried `pull --rebase` five times and hit the same conflict
        every time, so a video that was live on the channel left no record."""
        text = self.workflow("produce.yml")
        self.assertNotIn("git pull --rebase --autostash origin main", text)
        self.assertIn("git reset --mixed origin/main", text)
        self.assertIn("git push --quiet origin HEAD:main", text)
        self.assertIn("Queue state lost", text)

    def test_a_stock_video_scene_without_a_photo_does_not_kill_the_render(self):
        body = (Path(__file__).resolve().parents[1] / "tools" / "shorts.py").read_text()
        self.assertNotIn("raise SystemExit(f'missing fallback image {fallback}')", body)


class TestTheReleaseIsObservable(unittest.TestCase):
    """A 30-minute render and a wedged one used to look identical.

    Both were one step called "Render and upload target edition": nothing in the
    log, nothing in the summary, no bound of its own until the job's 120-minute
    cap. On 2 November that cost the owner half an hour of watching a run that was
    simply working. The stages are separate now, each with its own timeout, and the
    Short can no longer hide the release.
    """

    def setUp(self):
        import yaml

        self.data = yaml.safe_load((Path(__file__).resolve().parents[1] / ".github"
                                    / "workflows" / "produce.yml").read_text())
        self.steps = {s.get("name"): s for s in self.data["jobs"]["produce"]["steps"]}

    def test_short_and_release_are_separate_steps(self):
        self.assertIn("Render the Short (9:16)", self.steps)
        self.assertIn("Render and upload the long-form edition", self.steps)
        self.assertNotIn("Render and upload target edition", self.steps)

    def test_each_stage_has_its_own_timeout(self):
        short = self.steps["Render the Short (9:16)"]["timeout-minutes"]
        release = self.steps["Render and upload the long-form edition"]["timeout-minutes"]
        self.assertLess(short, release)
        job_cap = self.data["jobs"]["produce"]["timeout-minutes"]
        self.assertLessEqual(release, job_cap)

    def test_a_short_failure_cannot_fail_the_release(self):
        self.assertTrue(self.steps["Render the Short (9:16)"].get("continue-on-error"))
        self.assertFalse(self.steps["Render and upload the long-form edition"]
                         .get("continue-on-error", False))

    def test_the_release_step_is_the_one_that_uploads(self):
        release = self.steps["Render and upload the long-form edition"]["run"]
        self.assertIn("pipeline.run", release)
        short = self.steps["Render the Short (9:16)"]["run"]
        self.assertIn("short_release", short)

    def test_both_stages_report_into_the_run_summary(self):
        for name in ("Render the Short (9:16)", "Render and upload the long-form edition"):
            self.assertIn("GITHUB_STEP_SUMMARY", self.steps[name]["run"])


if __name__ == "__main__":
    unittest.main()
