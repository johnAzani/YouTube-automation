"""Queue selection and bulk-run safety regressions."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from pipeline import run
from pipeline.script_doc import parse_script


class ResumedQueueJobs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = self.root / "queue"
        self.published = self.root / "published"
        self.queue.mkdir()
        self.published.mkdir()
        for name, value in (("QUEUE_DIR", self.queue), ("PUBLISHED_DIR", self.published)):
            patch = mock.patch.object(run, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(run.CONFIG, "channel_id", "secret-place")
        patch.start()
        self.addCleanup(patch.stop)
        # Keep the test's factcheck refresh away from the real repository.
        patch = mock.patch("scripts.factcheck.main")
        patch.start()
        self.addCleanup(patch.stop)

    def job(self, name, words, status="quota_paused", reset="2020-01-01T00:00:00Z"):
        path = self.queue / name
        path.write_text(
            f'---\nid: "{name[:4]}"\nstatus: {status}\n'
            f'quota_reset_utc: "{reset}"\nformat: longform\n---\n\n'
            '## Scene 1 — Prayer\n' + 'prayer ' * words + '\n', encoding="utf-8")
        return path

    def test_expired_short_script_is_unpaused_but_not_selected(self):
        short = self.job("0098-short.md", 3)
        good = self.job("0099-good.md", 850, status="approved")
        self.assertEqual(run.select_jobs(False, None, True), [good])
        self.assertEqual(parse_script(short).status, "approved")

    def test_expired_job_with_receipt_is_not_selected(self):
        job = self.job("0098-duplicate.md", 850)
        (self.published / job.name).write_text(
            '---\nstatus: published\nyoutube_video_id: existing123\n---\n\n'
            '## Scene 1 — Prayer\nAmen.\n', encoding="utf-8")
        self.assertEqual(run.select_jobs(False, None, True), [])
        self.assertEqual(parse_script(job).status, "approved")

    def test_different_slug_with_published_job_id_is_not_selected(self):
        job = self.job('0098-new-slug.md', 850, status='approved')
        # Even a malformed receipt is unresolved state, not permission to upload.
        (self.published / '0098-old-slug.md').write_text('unreadable receipt')
        self.assertEqual(run.select_jobs(False, None, True), [])
        self.assertEqual(run._existing_published_path(job).name, '0098-old-slug.md')

    def test_future_pause_is_not_unpaused(self):
        job = self.job("0098-paused.md", 850, reset="2999-01-01T00:00:00Z")
        self.assertEqual(run.select_jobs(False, None, True), [])
        self.assertEqual(parse_script(job).status, "quota_paused")


class BulkRuns(unittest.TestCase):
    def test_next_continues_after_duplicate_prevented(self):
        jobs = [Path('a.md'), Path('b.md')]
        with mock.patch.object(run, 'select_jobs', return_value=jobs), \
             mock.patch.object(run, 'process', side_effect=[
                 {'privacy_status': 'duplicate_prevented', 'uploaded': False},
                 {'privacy_status': 'public', 'uploaded': True},
             ]) as process, mock.patch.object(run, 'quota_blocked_until', return_value=None), \
             mock.patch.object(run, 'CONFIG') as config, \
             mock.patch.dict('os.environ', {'DRY_RUN': '0'}):
            config.dry_run = False
            self.assertEqual(run.main(['--next']), 0)
        self.assertEqual([call.args[0] for call in process.call_args_list], jobs)

    def test_all_processes_every_selected_job(self):
        jobs = [Path("a.md"), Path("b.md"), Path("c.md")]
        with mock.patch.object(run, "select_jobs", return_value=jobs), \
             mock.patch.object(run, "process", return_value={"dry_run": True}) as process, \
             mock.patch.object(run, "CONFIG") as config, \
             mock.patch.dict("os.environ", {"DRY_RUN": "0"}):
            config.dry_run = False
            self.assertEqual(run.main(["--all", "--dry-run"]), 0)
        self.assertEqual([call.args[0] for call in process.call_args_list], jobs)

    def test_all_stops_on_failure(self):
        jobs = [Path("a.md"), Path("b.md"), Path("c.md")]
        with mock.patch.object(run, "select_jobs", return_value=jobs), \
             mock.patch.object(run, "process", side_effect=[{"dry_run": True}, RuntimeError("failed")]) as process, \
             mock.patch.object(run, "CONFIG") as config, \
             mock.patch.dict("os.environ", {"DRY_RUN": "0"}):
            config.dry_run = False
            self.assertEqual(run.main(["--all", "--dry-run"]), 1)
        self.assertEqual([call.args[0] for call in process.call_args_list], jobs[:2])


if __name__ == "__main__":
    unittest.main()
