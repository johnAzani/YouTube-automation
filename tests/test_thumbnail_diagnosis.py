"""A refused thumbnail must say *why*.

`thumbnails.set` answers every cause with the same sentence — "The request might not
be properly authorized" — so a receipt that stores only that sentence cannot be acted
on. Two Morning Altar videos carried it for a day: the owner verified the channel and
the refusal did not change, because the sentence never distinguished a verification
problem from an upload still processing or a token for another channel of the brand
account.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from pipeline import upload


class TestThumbnailDiagnosis(unittest.TestCase):
    def _client(self, *, auth_id="UC_auth", video_channel="UC_auth",
                upload_status="processed", long_uploads="allowed"):
        client = mock.MagicMock()
        client.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": auth_id,
                       "snippet": {"title": "The Morning Altar"},
                       "status": {"longUploadsStatus": long_uploads}}]}
        client.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"channelId": video_channel,
                                   "channelTitle": "The Morning Altar"},
                       "status": {"privacyStatus": "private",
                                  "uploadStatus": upload_status}}]}
        return client

    def test_it_separates_the_three_causes(self):
        with mock.patch("googleapiclient.discovery.build", return_value=self._client()), \
             mock.patch.object(upload, "_credentials", return_value=None):
            got = upload.diagnose_thumbnail_refusal("_vp27ZYPYaY")
        self.assertEqual(got["auth_channel_id"], "UC_auth")
        self.assertEqual(got["video_channel_id"], "UC_auth")
        self.assertTrue(got["same_channel"])
        self.assertEqual(got["upload_status"], "processed")
        self.assertEqual(got["long_uploads_status"], "allowed")
        self.assertEqual(got["video_privacy"], "private")

    def test_a_wrong_channel_is_visible(self):
        with mock.patch("googleapiclient.discovery.build",
                        return_value=self._client(auth_id="UC_other")), \
             mock.patch.object(upload, "_credentials", return_value=None):
            got = upload.diagnose_thumbnail_refusal("_vp27ZYPYaY")
        self.assertFalse(got["same_channel"], "the token is not the video's owner")

    def test_a_failed_lookup_does_not_hide_the_original_error(self):
        with mock.patch("googleapiclient.discovery.build", side_effect=RuntimeError("boom")), \
             mock.patch.object(upload, "_credentials", return_value=None):
            self.assertEqual(upload.diagnose_thumbnail_refusal("_vp27ZYPYaY"), {})

    def test_the_refusal_carries_the_diagnosis(self):
        class _Err(Exception):
            content = (b'{"error": {"message": "The thumbnail can\'t be set for the '
                       b'specified video. The request might not be properly authorized.", '
                       b'"errors": [{"reason": "forbidden"}]}}')

        client = self._client(auth_id="UC_other")
        client.thumbnails.return_value.set.return_value.execute.side_effect = _Err("403")
        with mock.patch("googleapiclient.discovery.build", return_value=client), \
             mock.patch.object(upload, "_credentials", return_value=None), \
             mock.patch("googleapiclient.http.MediaFileUpload", return_value=None):
            msg = upload.set_video_thumbnail("_vp27ZYPYaY", Path(__file__))
        self.assertIn("forbidden", msg, "the API's own reason is kept")
        self.assertIn("same_channel=False", msg,
                      "the diagnosis names the cause the message hides")
        self.assertIn("upload_status=processed", msg)


if __name__ == "__main__":
    unittest.main()
