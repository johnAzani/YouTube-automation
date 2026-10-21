"""Fail-closed behavior for production video runs."""
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pipeline.run import (
    _mark_job_uploaded,
    _require_production_prerequisites,
    _require_real_narration,
)


class ProductionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.approved_doc = SimpleNamespace(id="test-job", status="approved", meta={})

    def test_production_requires_both_youtube_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_SECRET"):
            _require_production_prerequisites(self.approved_doc, False, "", "")

    def test_production_rejects_unapproved_job_even_with_credentials(self):
        draft = SimpleNamespace(id="test-job", status="draft", meta={})
        with self.assertRaisesRegex(RuntimeError, "status='draft'"):
            _require_production_prerequisites(draft, False, "refresh", "client-secret")

    def test_dry_run_can_run_without_credentials(self):
        _require_production_prerequisites(self.approved_doc, True, "", "")

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


if __name__ == "__main__":
    unittest.main()
