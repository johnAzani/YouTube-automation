"""Unit tests for duplicate and unintentional upload prevention systems."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.script_doc import ScriptDoc
from pipeline.short_release import select_next_queued_short
from pipeline.upload import _normalize_title, check_existing_channel_duplicate, upload


class TestTitleNormalization(unittest.TestCase):
    def test_strips_hashtags_and_punctuation(self):
        t1 = "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts"
        t2 = "say this psalm 91 prayer before you sleep divine protection"
        t3 = "Say This Psalm 91 Prayer Before You Sleep: Divine Protection! #shorts #psalm91"
        self.assertEqual(_normalize_title(t1), t2)
        self.assertEqual(_normalize_title(t3), t2)

    def test_handles_multiple_whitespace_and_casing(self):
        t = "  Psalm 91:   Under   His   Wings  "
        self.assertEqual(_normalize_title(t), "psalm 91 under his wings")


class TestRemoteDuplicateDetection(unittest.TestCase):
    def test_detects_exact_match(self):
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts",
                        "resourceId": {"videoId": "SG69BbNlfRw"},
                    }
                }
            ]
        }
        dup = check_existing_channel_duplicate(
            mock_youtube,
            "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts",
        )
        self.assertIsNotNone(dup)
        self.assertEqual(dup["id"], "SG69BbNlfRw")
        self.assertEqual(dup["match"], "exact")

    def test_detects_normalized_match(self):
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts",
                        "resourceId": {"videoId": "SG69BbNlfRw"},
                    }
                }
            ]
        }
        # Subtle variation in hashtag and casing
        dup = check_existing_channel_duplicate(
            mock_youtube,
            "Say This Psalm 91 Prayer Before You Sleep: Divine Protection #SHORTS",
        )
        self.assertIsNotNone(dup)
        self.assertEqual(dup["id"], "SG69BbNlfRw")
        self.assertEqual(dup["match"], "normalized")

    def test_returns_none_when_no_match(self):
        mock_youtube = MagicMock()
        mock_youtube.channels().list().execute.return_value = {
            "items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU123"}}}]
        }
        mock_youtube.playlistItems().list().execute.return_value = {
            "items": [
                {
                    "snippet": {
                        "title": "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts",
                        "resourceId": {"videoId": "SG69BbNlfRw"},
                    }
                }
            ]
        }
        dup = check_existing_channel_duplicate(mock_youtube, "Psalm 23 The Lord Is My Shepherd")
        self.assertIsNone(dup)


class TestUploadDuplicateShield(unittest.TestCase):
    @patch("pipeline.upload._credentials")
    @patch("googleapiclient.discovery.build")
    @patch("pipeline.upload.check_existing_channel_duplicate")
    def test_upload_aborts_when_duplicate_detected(self, mock_check, mock_build, mock_creds):
        mock_check.return_value = {"id": "SG69BbNlfRw", "title": "Existing Psalm 91", "match": "exact"}
        mock_youtube = MagicMock()
        mock_build.return_value = mock_youtube

        doc = ScriptDoc(
            path=Path("/tmp/test.md"),
            meta={"title": "Existing Psalm 91", "privacy": "public", "slug": "existing-psalm-91"},
            scenes=[],
        )
        result = upload(doc, Path("/tmp/fake.mp4"))
        self.assertEqual(result.video_id, "SG69BbNlfRw")
        self.assertEqual(result.privacy_status, "duplicate_prevented")
        # Ensure videos().insert was NOT called!
        mock_youtube.videos().insert.assert_not_called()


class TestQueueDuplicatePurge(unittest.TestCase):
    def test_select_next_queued_short_purges_already_published(self):
        import tempfile
        from pipeline.config import PUBLISHED_DIR

        with tempfile.TemporaryDirectory() as tmp_dir:
            q_dir = Path(tmp_dir) / "shorts-queue"
            q_dir.mkdir()
            rogue_manifest = q_dir / "short-0002-psalm-91.yml"
            rogue_manifest.write_text(
                "short: short-psalm91\nstatus: approved\nreplace: true\n",
                encoding="utf-8",
            )
            # Since short-0002-psalm-91-prayer-of-protection.md exists in content/published/,
            # select_next_queued_short should recognize it, unlink it, and return None!
            res = select_next_queued_short(queue_dir=q_dir, published_dir=PUBLISHED_DIR)
            self.assertIsNone(res)
            self.assertFalse(rogue_manifest.exists())


if __name__ == "__main__":
    unittest.main()
