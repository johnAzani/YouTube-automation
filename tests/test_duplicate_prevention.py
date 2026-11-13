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


    def _client(self, pages):
        youtube = MagicMock()
        youtube.channels().list().execute.return_value = {
            'items': [{'contentDetails': {'relatedPlaylists': {'uploads': 'UU123'}}}]}
        youtube.playlistItems().list().execute.side_effect = pages
        youtube.playlistItems().list.reset_mock()
        return youtube

    @staticmethod
    def _item(vid, title):
        return {'snippet': {'title': title, 'resourceId': {'videoId': vid}}}

    def test_finds_a_match_after_the_first_fifty_uploads(self):
        youtube = self._client([{'items': [self._item('other', 'Other')], 'nextPageToken': 'next'},
                                {'items': [self._item('old', 'My Prayer')]}])
        result = check_existing_channel_duplicate(youtube, 'My Prayer')
        self.assertEqual(result['id'], 'old')
        calls = youtube.playlistItems().list.call_args_list
        self.assertEqual(calls[-1].kwargs['pageToken'], 'next')
        self.assertEqual(len(calls), 2)

    def test_finds_alternate_title_in_one_traversal(self):
        youtube = self._client([{'items': [self._item('old', 'Full Authored Title')]}])
        result = check_existing_channel_duplicate(youtube, 'Truncated Title',
                                                  additional_titles=('Full Authored Title',))
        self.assertEqual(result['id'], 'old')
        self.assertEqual(youtube.playlistItems().list().execute.call_count, 1)

    def test_multiple_title_matches_fail_closed_even_if_one_is_exact(self):
        youtube = self._client([{'items': [self._item('first', 'My Prayer')], 'nextPageToken': 'next'},
                                {'items': [self._item('second', 'My Prayer #Shorts')]}])
        with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
            check_existing_channel_duplicate(youtube, 'My Prayer')

    def test_repeated_token_and_exhausted_page_budget_fail_closed(self):
        from pipeline import upload as module
        for pages in ([{'items': [], 'nextPageToken': 'loop'}, {'items': [], 'nextPageToken': 'loop'}],
                      [{'items': [], 'nextPageToken': 'next'}]):
            youtube = self._client(pages)
            with patch.object(module, 'DUPLICATE_SCAN_MAX_PAGES', len(pages)):
                with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
                    check_existing_channel_duplicate(youtube, 'My Prayer')

    def test_later_page_failure_does_not_treat_an_early_match_as_verified(self):
        youtube = self._client([{'items': [self._item('first', 'My Prayer')], 'nextPageToken': 'next'},
                                RuntimeError('network failure')])
        with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
            check_existing_channel_duplicate(youtube, 'My Prayer')

    def test_malformed_playlist_item_fails_closed(self):
        youtube = self._client([{'items': [{'snippet': {'title': 'some title'}}]}])
        with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
            check_existing_channel_duplicate(youtube, 'My Prayer')

    def test_wrong_authenticated_channel_fails_closed(self):
        youtube = self._client([{'items': []}])
        with patch('pipeline.upload.CONFIG.expected_youtube_channel_id', 'expected'):
            with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
                check_existing_channel_duplicate(youtube, 'My Prayer')
        youtube.playlistItems().list.assert_not_called()

    def test_lookup_errors_and_ambiguous_results_are_not_treated_as_clear(self):
        youtube = MagicMock()
        youtube.channels().list().execute.side_effect = RuntimeError('network down')
        with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
            check_existing_channel_duplicate(youtube, 'A title')
        youtube.channels().list().execute.side_effect = None
        for items in ([], [{}, {}]):
            youtube.channels().list().execute.return_value = {'items': items}
            with self.subTest(items=items), self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
                check_existing_channel_duplicate(youtube, 'A title')

    def test_invalid_playlist_response_is_not_treated_as_clear(self):
        youtube = MagicMock()
        youtube.channels().list().execute.return_value = {
            'items': [{'contentDetails': {'relatedPlaylists': {'uploads': 'UU123'}}}]
        }
        youtube.playlistItems().list().execute.return_value = {}
        with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
            check_existing_channel_duplicate(youtube, 'A title')


class TestUploadDuplicateShield(unittest.TestCase):
    @patch("pipeline.upload._credentials")
    @patch("googleapiclient.discovery.build")
    def test_upload_refuses_when_duplicate_lookup_fails(self, mock_build, mock_creds):
        youtube = MagicMock()
        mock_build.return_value = youtube
        youtube.channels().list().execute.side_effect = RuntimeError('network down')
        doc = ScriptDoc(path=Path('/tmp/test.md'),
                        meta={'title': 'Test prayer', 'privacy': 'public', 'slug': 'test'}, scenes=[])
        with patch('pipeline.upload.CONFIG.allow_duplicate_uploads', False):
            with self.assertRaisesRegex(RuntimeError, 'refusing to upload'):
                upload(doc, Path('/tmp/fake.mp4'))
        youtube.videos().insert.assert_not_called()

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
