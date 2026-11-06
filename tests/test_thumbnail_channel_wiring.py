"""The token that writes must be the channel's own.

Diagnosed 09:15Z on 6 November: `--all-channels` repaired every receipt, but the
actual `thumbnails.set` went through `pipeline.upload.set_video_thumbnail`, which
builds its client from the global CONFIG — The Secret Place. So each Morning Altar
video was thumbnailed by another channel's account and answered

    HttpError: ... might not be properly authorized [forbidden]
    | auth_channel_id=UCtPI1r8vgtJ9n__7ksLBmCA (The Secret Place)
      video_channel_id=UCOaC5VWBGxA-UpOjP5bvkUQ (The Morning Altar), same_channel=False

Two videos sat with no thumbnail for a day because the message was identical to the
one a verification problem produces. The audit (`videos.list`) used the right client;
only the write did not.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from scripts import sync_published_thumbnails as sync


class TestSetterIsPerChannel(unittest.TestCase):
    def test_the_setter_is_bound_to_the_channel_client(self):
        client = mock.MagicMock()
        setter = sync._setter_for(client)
        with mock.patch("googleapiclient.http.MediaFileUpload", return_value=None):
            self.assertEqual(setter("_vp27ZYPYaY", Path(__file__)), "ok")
        client.thumbnails.return_value.set.assert_called_once()
        self.assertEqual(
            client.thumbnails.return_value.set.call_args.kwargs["videoId"], "_vp27ZYPYaY")

    def test_a_refusal_carries_the_channel_ids(self):
        client = mock.MagicMock()
        client.thumbnails.return_value.set.return_value.execute.side_effect = RuntimeError(
            "HttpError 403 forbidden")
        client.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "UC_other", "status": {"longUploadsStatus": "allowed"}}]}
        client.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"channelId": "UC_owner"},
                       "status": {"privacyStatus": "public", "uploadStatus": "processed"}}]}
        with mock.patch("googleapiclient.http.MediaFileUpload", return_value=None):
            msg = sync._setter_for(client)("_vp27ZYPYaY", Path(__file__))
        self.assertIn("auth_channel_id=UC_other", msg)
        self.assertIn("video_channel_id=UC_owner", msg)
        self.assertIn("same_channel=False", msg)

    def test_the_default_setter_is_not_used_when_a_client_exists(self):
        """The regression itself: a per-channel client must replace the global one."""
        import inspect

        params = inspect.signature(sync.sync_published_thumbnails).parameters
        self.assertIsNone(params["thumb_setter"].default,
                          "a non-None default silently falls back to CONFIG's token")


if __name__ == "__main__":
    unittest.main()
