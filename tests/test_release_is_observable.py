"""A release must be legible while it runs, not only after it fails.

Every failure on 2 November looked the same from outside: a step vanished for
ninety minutes and came back as "exit code 1". These tests pin the three things
that made that possible — no progress output, a job cap smaller than its own
steps, and an advisory check that was permanently red.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import progress

REPO = Path(__file__).resolve().parents[1]

ROOT = Path(__file__).resolve().parents[1]


class TestProgressIsVisibleWhileItRuns(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.summary = Path(self.tmp.name) / "summary.md"
        self.summary.touch()
        patcher = mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.summary)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_stage_writes_both_edges_to_the_run_page(self):
        with progress.stage("encode", "5.4 min"):
            pass
        text = self.summary.read_text()
        self.assertIn("▶ encode — 5.4 min", text)
        self.assertIn("✓ encode — 5.4 min in", text)

    def test_a_failing_stage_says_so_and_still_re_raises(self):
        with self.assertRaises(ValueError):
            with progress.stage("upload"):
                raise ValueError("no video id")
        text = self.summary.read_text()
        self.assertIn("✗ upload failed", text)
        self.assertIn("no video id", text)

    def test_progress_never_raises_when_the_summary_is_missing(self):
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": "/nonexistent/dir/x"}):
            progress.emit("still fine")

    def test_progress_is_silent_without_ci(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            progress.emit("local run")

    def test_the_heartbeat_reports_but_not_every_frame(self):
        beat = progress.Heartbeat("encode", total=1000, every_seconds=0.0,
                                  every_fraction=0.25)
        for frame in range(0, 1001):
            beat.tick(frame)
        text = self.summary.read_text()
        self.assertGreaterEqual(text.count("encode:"), 4)
        self.assertLess(text.count("encode:"), 12, "one line per 25%, not per frame")

    def test_the_heartbeat_estimates_the_time_left(self):
        beat = progress.Heartbeat("encode", total=100, every_seconds=0.0,
                                  every_fraction=0.5)
        beat.tick(50)
        self.assertIn("frames (50%)", self.summary.read_text())
        self.assertIn("min left", self.summary.read_text())


class TestTheReleaseCannotKillItself(unittest.TestCase):
    """The 0017 render died at the *job* boundary, not the step's."""

    def _job(self):
        import yaml

        data = yaml.safe_load((ROOT / ".github" / "workflows" / "produce.yml")
                              .read_text(encoding="utf-8"))
        return data["jobs"][next(iter(data["jobs"]))]

    def test_the_job_cap_exceeds_the_sum_of_its_step_caps(self):
        job = self._job()
        caps = [s["timeout-minutes"] for s in job["steps"] if s.get("timeout-minutes")]
        self.assertGreater(job["timeout-minutes"], sum(caps),
                           "a job cap below its own steps kills work that was inside budget")

    def test_the_render_step_covers_the_measured_worst_case(self):
        # 5:22 at 170 ms/frame is ~22 min of encode; a whole release measured at
        # 44 min. 170 leaves room on a slow runner without being unbounded.
        job = self._job()
        render = [s for s in job["steps"]
                  if s.get("name", "").startswith("Render and upload")][0]
        self.assertGreaterEqual(render["timeout-minutes"], 150)

    def test_the_release_step_reports_progress_to_the_summary(self):
        source = (ROOT / "pipeline" / "prayer_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("Heartbeat(", source)
        self.assertIn("progress=heartbeat.tick", source)


class TestARetryDoesNotRepayForSpeech(unittest.TestCase):
    """A 90-minute render that fails at minute 89 must not re-pay for speech."""

    def test_unchanged_narration_is_reused_and_edited_text_is_not(self):
        from pipeline import prayer_pipeline as pp

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            key = pp._fingerprint("tts-v1", pp.DEFAULT_MODEL, "Charon", "the words")
            pp._write_json(out / "narration.json", {"key": key, "duration": 322.0})
            self.assertEqual(pp._cached_json(out / "narration.json", key)["duration"], 322.0)
            other = pp._fingerprint("tts-v1", pp.DEFAULT_MODEL, "Charon", "changed words")
            self.assertIsNone(pp._cached_json(out / "narration.json", other))

    def test_a_truncated_sidecar_is_treated_as_absent(self):
        from pipeline import prayer_pipeline as pp

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(pp._cached_json(path, "any"))

    def test_the_sidecar_write_is_atomic(self):
        from pipeline import prayer_pipeline as pp

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "words.json"
            pp._write_json(path, {"key": "k", "words": [["a", 0.0, 0.1]]})
            self.assertEqual(json.loads(path.read_text())["key"], "k")
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])


class TestTheAdvisoryCheckIsNotPermanentlyRed(unittest.TestCase):
    """`General pipeline dry-run` failed on every push for weeks.

    A red that is always there is a red nobody reads, so the next real failure
    hides among it. It is advisory by design: the failure belongs in an
    annotation, not in the check list.
    """

    def _wf(self):
        import yaml

        data = yaml.safe_load((ROOT / ".github" / "workflows" / "dry-run.yml")
                              .read_text(encoding="utf-8"))
        return data["jobs"]["pipeline-dry-run"]

    def test_the_job_is_not_allow_to_fail_at_job_level(self):
        self.assertIsNone(self._wf().get("continue-on-error"))

    def test_the_render_step_carries_the_allowance(self):
        render = [s for s in self._wf()["steps"] if s.get("id") == "render"][0]
        self.assertTrue(render["continue-on-error"])

    def test_a_failure_is_annotated_as_a_warning(self):
        text = (ROOT / ".github" / "workflows" / "dry-run.yml").read_text(encoding="utf-8")
        self.assertIn("::warning title=Advisory dry-run failed::", text)


if __name__ == "__main__":
    unittest.main()


class AQuotaPauseIsNotARelease(unittest.TestCase):
    """Run 41596457350 finished GREEN in four minutes having published nothing.

    0017 hit exhausted Gemini quota, `produce()` returned a `quota_paused` dict
    instead of raising, and every caller treated a returned dict as success. A
    green tick with no upload is the exact report the owner keeps having to make
    himself — three slots a day can do this indefinitely.
    """

    def _run_main(self, result):
        from pipeline import run

        with mock.patch.object(run, "select_jobs", return_value=[Path("content/queue/0017.md")]), \
             mock.patch.object(run, "process", return_value=result):
            return run.main(["--next"])

    def test_a_quota_pause_exits_non_zero_and_names_the_reset(self):
        code = self._run_main({"job": "0017", "status": "quota_paused",
                               "quota_reset_utc": "2026-11-03T08:00:00+00:00"})
        self.assertEqual(code, 3, "a paused release must not report success")

    def test_a_pause_says_so_in_an_annotation(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self._run_main({"job": "0017", "status": "quota_paused",
                            "quota_reset_utc": "2026-11-03T08:00:00+00:00"})
        printed = buffer.getvalue()
        self.assertIn("::error title=Release did not publish::", printed)
        self.assertIn("2026-11-03T08:00:00", printed)

    def test_a_real_upload_announces_the_video(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self._run_main({"uploaded": True, "video_id": "abc123",
                                   "watch_url": "https://youtu.be/abc123",
                                   "privacy_status": "public", "duration_seconds": 372})
        self.assertEqual(code, 0)
        self.assertIn("::notice title=Published::abc123", buffer.getvalue())

    def test_a_success_with_no_upload_cannot_be_silent(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self._run_main({"slug": "x", "dry_run": False})
        self.assertIn("no upload", buffer.getvalue())

    def test_the_short_release_treats_a_pause_as_a_failure_too(self):
        text = (REPO / "pipeline" / "short_release.py").read_text(encoding="utf-8")
        self.assertIn('if outcome.get("paused"):', text)
        self.assertIn("Short did not upload", text)
        self.assertIn("::notice title=Short published::", text)

    def test_every_run_ships_a_readable_report(self):
        text = (REPO / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
        self.assertIn("release-report-${{ github.run_id }}", text,
                      "a green run must be interrogable without a 1 GB download")
        self.assertIn("output/report/summary.json", text)
