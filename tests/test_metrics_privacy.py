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


if __name__ == "__main__":
    unittest.main()
