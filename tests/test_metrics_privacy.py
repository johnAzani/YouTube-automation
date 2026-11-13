from __future__ import annotations

import datetime as dt
import unittest

from scripts.metrics_snapshot import _public_video_rows, _within_retention


class MetricsPrivacyTests(unittest.TestCase):
    def test_private_and_unlisted_video_metadata_is_excluded(self) -> None:
        items = [
            {
                "id": "public-id",
                "status": {"privacyStatus": "public"},
                "snippet": {"title": "Public title", "publishedAt": "2026-10-01T00:00:00Z"},
                "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
            },
            {
                "id": "private-id",
                "status": {"privacyStatus": "private"},
                "snippet": {"title": "Do not expose this", "publishedAt": "2026-10-02T00:00:00Z"},
                "statistics": {"viewCount": "0"},
            },
            {
                "id": "unlisted-id",
                "status": {"privacyStatus": "unlisted"},
                "snippet": {"title": "Do not expose this either", "publishedAt": "2026-10-03T00:00:00Z"},
                "statistics": {"viewCount": "0"},
            },
        ]

        rows = _public_video_rows(items, "2026-10-21")

        self.assertEqual([row["video_id"] for row in rows], ["public-id"])
        self.assertNotIn("Do not expose this", repr(rows))

    def test_missing_view_count_is_not_exported_as_zero(self) -> None:
        item = {'id': 'public-id', 'status': {'privacyStatus': 'public'},
                'snippet': {'title': 'Public', 'publishedAt': '2026-10-01T00:00:00Z'},
                'statistics': {}}
        self.assertEqual(_public_video_rows([item], '2026-10-21')[0]['views'], '')

    def test_snapshot_retention_is_30_days_and_discards_future_or_invalid_dates(self) -> None:
        today = dt.date(2026, 10, 21)
        rows = [
            {"snapshot_date": "2026-09-21", "video_id": "cutoff"},
            {"snapshot_date": "2026-09-20", "video_id": "expired"},
            {"snapshot_date": "2026-10-22", "video_id": "future"},
            {"snapshot_date": "not-a-date", "video_id": "invalid"},
        ]

        kept = _within_retention(rows, today)

        self.assertEqual([row["video_id"] for row in kept], ["cutoff"])

class MetricsChannelIdentityTests(unittest.TestCase):
    def test_matches_expected_channel_without_an_extra_api_request(self):
        from scripts.metrics_snapshot import _check_snapshot_channel
        channel = {'id': 'UC-right'}
        self.assertIs(_check_snapshot_channel([channel], 'UC-right'), channel)

    def test_wrong_missing_or_ambiguous_channel_is_rejected(self):
        from scripts.metrics_snapshot import _check_snapshot_channel
        for items, expected in (([{'id': 'UC-wrong'}], 'UC-right'),
                                ([], 'UC-right'), ([{}], ''),
                                ([{'id': 'UC-a'}, {'id': 'UC-b'}], '')):
            with self.subTest(items=items), self.assertRaises(RuntimeError):
                _check_snapshot_channel(items, expected)

    def test_unconfigured_channel_warns_rather_than_claims_verification(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from scripts.metrics_snapshot import _check_snapshot_channel
        output = StringIO()
        with redirect_stdout(output):
            _check_snapshot_channel([{'id': 'UC-a'}], '')
        self.assertIn('Channel identity unverified', output.getvalue())

    def test_wrong_channel_aborts_snapshot_before_writing_or_querying_videos(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest import mock
        from scripts import metrics_snapshot as ms
        youtube = mock.MagicMock()
        youtube.channels().list().execute.return_value = {'items': [{'id': 'UC-wrong'}]}
        with TemporaryDirectory() as tmp, \
             mock.patch.object(ms, 'CSV_PATH', Path(tmp) / 'metrics.csv'), \
             mock.patch.multiple(ms.CONFIG, youtube_refresh_token='token', youtube_client_id='id',
                                 youtube_client_secret='secret', expected_youtube_channel_id='UC-right'), \
             mock.patch('pipeline.channels.apply_channel_env', return_value='prayer2'), \
             mock.patch.object(ms, '_credentials', return_value=object()), \
             mock.patch('googleapiclient.discovery.build', return_value=youtube):
            self.assertEqual(ms.main([]), 1)
            self.assertFalse(ms.CSV_PATH.exists())
            youtube.playlistItems.assert_not_called()
            youtube.videos.assert_not_called()

    def test_growth_workflow_passes_channel_specific_expected_id(self):
        import yaml
        from pathlib import Path
        data = yaml.safe_load((Path(__file__).resolve().parents[1] / '.github/workflows/growth-autopilot.yml').read_text())
        expected = data['jobs']['growth']['env']['YOUTUBE_EXPECTED_CHANNEL_ID']
        self.assertIn('matrix.channel', expected)
        self.assertIn('YOUTUBE_CHANNEL_ID', expected)


class ChannelSubscriberTests(unittest.TestCase):
    def test_public_count_is_reported_without_exporting_other_channel_fields(self):
        from scripts.metrics_snapshot import _subscriber_snapshot, _subscriber_summary
        snapshot = _subscriber_snapshot({
            'id': 'channel-id', 'contentDetails': {'private': 'not exported'},
            'statistics': {'subscriberCount': '12300', 'hiddenSubscriberCount': False},
        }, '2026-10-23')
        self.assertEqual(snapshot['subscriber_count'], 12300)
        self.assertNotIn('private', repr(snapshot))
        self.assertIn('12,300', _subscriber_summary(snapshot))
        self.assertIn('rounds', _subscriber_summary(snapshot))

    def test_hidden_and_missing_counts_are_not_reported_as_zero(self):
        from scripts.metrics_snapshot import _subscriber_snapshot
        for stats in ({}, {'subscriberCount': '12', 'hiddenSubscriberCount': True}):
            self.assertIsNone(_subscriber_snapshot({'statistics': stats}, '2026-10-23')['subscriber_count'])
        self.assertEqual(_subscriber_snapshot({'statistics': {'subscriberCount': '0'}}, '2026-10-23')['subscriber_count'], 0)


class MetricsRunsOftenEnoughToNotice(unittest.TestCase):
    """A weekly cron hid a broken snapshot for three days.

    On 30 October the run failed with "Process completed with exit code 1" and an
    unreachable log. Nothing else ever exercised the script, so the fault could have
    sat there until the following Friday.
    """

    def _wf(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "metrics.yml"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_it_also_runs_after_a_production_run(self):
        on = self._wf()[True]
        self.assertIn("workflow_run", on)
        self.assertEqual(on["workflow_run"]["workflows"], ["Produce video"])

    def test_a_post_publish_run_does_not_file_an_issue(self):
        steps = self._wf()["jobs"]["snapshot"]["steps"]
        snapshot = [s for s in steps if "metrics_snapshot.py" in str(s.get("run", ""))]
        self.assertEqual(len(snapshot), 1)
        self.assertIn("METRICS_POST_ISSUE", snapshot[0]["env"])
        self.assertIn("workflow_run", snapshot[0]["env"]["METRICS_POST_ISSUE"])

    def test_a_failure_names_its_cause(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "scripts" / "metrics_snapshot.py").read_text()
        self.assertIn("::error title=Metrics snapshot cannot run::", source)
        self.assertIn("traceback.print_exc()", source)


if __name__ == "__main__":
    unittest.main()
