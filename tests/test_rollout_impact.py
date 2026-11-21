from datetime import date
import unittest

from scripts.rollout_impact import cohort_rows


class RolloutImpactTests(unittest.TestCase):
    def test_exact_age_separate_cohorts_and_missing_engagement(self):
        receipts = {"a": {"channel": "prayer2", "format": "short"},
                    "b": {"channel": "prayer2", "format": "longform"},
                    "c": {"channel": "prayer3", "format": "short"}}

        def row(vid, day, observed, **counts):
            return dict(video_id=vid, published_at=f"2026-11-{day}T12:00:00Z",
                        snapshot_date=f"2026-11-{observed}", **counts)

        a = row("a", "01", "08", views="23", likes="0")
        b = row("b", "10", "17", views="8", comments="1")
        c = row("c", "10", "17", views="42")
        snapshots = [a, a, b, c, row("a", "01", "09", views="999"),
                     row("unknown", "10", "17", views="9")]
        groups = cohort_rows(snapshots, receipts, date(2026, 11, 10), today=date(2026, 11, 20))
        self.assertEqual(groups["prayer2", "short", False], [(23, 0, None)])
        self.assertEqual(groups["prayer2", "longform", True], [(8, None, 1)])
        self.assertEqual(groups["prayer3", "short", True], [(42, None, None)])
        self.assertEqual(len(groups), 3)
        snapshots.append(dict(c, views="43"))
        self.assertNotIn(("prayer3", "short", True), cohort_rows(
            snapshots, receipts, date(2026, 11, 10), today=date(2026, 11, 20)))

    def test_latest_same_day_observation_wins_without_accepting_other_channel(self):
        receipt = {"a": {"channel": "prayer2", "format": "short"}}
        base = dict(video_id="a", published_at="2026-11-10", snapshot_date="2026-11-17",
                    views="12", channel_key="prayer2")
        rows = [dict(base, views="18", observed_at="2026-11-17T21:00:00+00:00"),
                dict(base, observed_at="2026-11-17T09:00:00+00:00"),
                dict(base, views="600", channel_key="prayer5", observed_at="2026-11-17T22:00:00+00:00")]
        cohorts = cohort_rows(rows, receipt, date(2026, 11, 10), today=date(2026, 11, 20))
        self.assertEqual(cohorts["prayer2", "short", True], [(18, None, None)])
