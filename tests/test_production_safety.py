"""Fail-closed behavior for production video runs."""
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.run import (
    _mark_job_uploaded,
    _open_release_ticket,
    _require_production_prerequisites,
    _require_real_narration,
)


class ProductionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.approved_doc = SimpleNamespace(id="test-job", status="approved", meta={})

    def test_production_requires_all_youtube_credentials(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET",
        ):
            _require_production_prerequisites(self.approved_doc, False, "", "", "")

    def test_production_rejects_unapproved_job_even_with_credentials(self):
        draft = SimpleNamespace(id="test-job", status="draft", meta={})
        with self.assertRaisesRegex(RuntimeError, "status='draft'"):
            _require_production_prerequisites(draft, False, "refresh", "client-id", "client-secret")

    def test_dry_run_can_run_without_credentials(self):
        _require_production_prerequisites(self.approved_doc, True, "", "", "")

    def test_production_rejects_placeholder_narration(self):
        with self.assertRaisesRegex(RuntimeError, "placeholder"):
            _require_real_narration("placeholder", False)

    def test_dry_run_allows_placeholder_narration(self):
        _require_real_narration("placeholder", True)

    def test_production_accepts_real_tts(self):
        _require_real_narration("edge-tts", False)

    def test_missing_video_id_leaves_queue_job_in_place(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "job.md"
            queue_path.write_text("---\nstatus: approved\n---\nbody\n", encoding="utf-8")
            published_dir = Path(temp_dir) / "published"
            with patch("pipeline.run.PUBLISHED_DIR", published_dir):
                with self.assertRaisesRegex(RuntimeError, "no video ID"):
                    _mark_job_uploaded(queue_path, self.approved_doc, "")
            self.assertTrue(queue_path.exists())
            self.assertFalse(published_dir.exists())

    def test_confirmed_video_id_moves_and_stamps_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            queue_path = Path(temp_dir) / "job.md"
            queue_path.write_text("---\nstatus: approved\n---\nbody\n", encoding="utf-8")
            published_dir = Path(temp_dir) / "published"
            with patch("pipeline.run.PUBLISHED_DIR", published_dir):
                dest = _mark_job_uploaded(queue_path, self.approved_doc, "video-123")
            self.assertFalse(queue_path.exists())
            self.assertTrue(dest.exists())
            self.assertEqual(self.approved_doc.meta["status"], "published")
            self.assertEqual(self.approved_doc.meta["published_on"].count("-"), 2)
            self.assertIn("status: published", dest.read_text(encoding="utf-8"))
            self.assertIn('youtube_video_id: "video-123"', dest.read_text(encoding="utf-8"))


    def test_release_ticket_opens_in_actions_with_token_and_studio_link(self):
        doc = SimpleNamespace(title="How Test Died")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "1", "GH_TOKEN": "tok"}, clear=False), \
             patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout="https://github.com/o/r/issues/1\n", stderr="")
            _open_release_ticket(doc, "https://youtu.be/abc", "private", "abc")
        self.assertEqual(run.call_count, 1)
        args, kwargs = run.call_args
        self.assertEqual(args[0][:3], ["gh", "issue", "create"])
        body = args[0][args[0].index("--body") + 1]
        self.assertIn("https://studio.youtube.com/video/abc/edit", body)
        self.assertIn("Publish / schedule in YouTube Studio", body)
        self.assertEqual(kwargs["env"].get("GH_TOKEN"), "tok")

    def test_release_ticket_failure_is_logged_not_raised(self):
        doc = SimpleNamespace(title="How Test Died")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "1", "GH_TOKEN": ""}, clear=False), \
             patch("subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="gh: To get started with GitHub CLI")
            with patch("pipeline.run._log") as log:
                _open_release_ticket(doc, "https://youtu.be/abc", "private", "abc")  # must not raise
        self.assertTrue(any("release ticket creation failed" in str(c) for c in log.call_args_list))

    def test_release_ticket_is_absent_outside_actions(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}, clear=False), \
             patch("subprocess.run") as run:
            _open_release_ticket(SimpleNamespace(title="x"), "u", "private")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
