import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import view_analytics


class ViewAnalyticsTests(unittest.TestCase):
    def test_saved_video_report_uses_video_specific_path(self):
        with patch("sys.argv", ["view_analytics.py", "--retention-video", "7RDX0fbIOtQ"]), \
                patch.object(view_analytics, "display_private_report", return_value=True) as display:
            self.assertEqual(view_analytics.main(), 0)
        display.assert_called_once_with(view_analytics.PRIVATE_REPORT.with_name("retention-7RDX0fbIOtQ.json"))

    def test_retention_landmarks_include_ending_and_do_not_invent_missing_values(self):
        columns = ["audienceWatchRatio", "elapsedVideoTimeRatio"]
        rows = [[0.31, 1], [1.25, 0.01], [0.4, 0.95], [0.5, 0.95], [0.6, 0.49]]
        values = dict(view_analytics.retention_landmarks(columns, rows))
        self.assertEqual(values["100%"], "31.0%")
        self.assertEqual(values["1%"], "125.0%")
        self.assertEqual(values["50%"], "—")
        self.assertEqual(values["95%"], "—")
        self.assertEqual(view_analytics.retention_landmarks(["day"], []), [])

    def test_growth_compares_equal_windows_and_preserves_missing_metrics(self):
        columns = ["day", "views", "subscribersGained", "subscribersLost", "shares"]
        rows = [[f"2026-11-{i:02d}", i, 0, 1, 0] for i in range(1, 15)]
        _, table = view_analytics.engagement_comparison(columns, rows[::-1])
        metrics = {label: values for label, *values in table}
        self.assertEqual(metrics["Views"], ["28", "77", "+49"])
        self.assertEqual(metrics["Net subscribers"], ["-7", "-7", "+0"])
        self.assertEqual(metrics["Shares"], ["0", "0", "+0"])
        self.assertEqual(metrics["Likes"], ["—", "—", "—"])
        self.assertIsNone(view_analytics.engagement_comparison(columns, rows[:7] + rows[8:]))
        self.assertIsNone(view_analytics.engagement_comparison(columns, rows + rows[:1]))

    def test_format_table_renders_aligned_text(self):
        headers = ["Col A", "Col B"]
        rows = [["Val 1", "Val 2"], ["100", "200"]]
        table = view_analytics.format_table(headers, rows)
        self.assertIn("Col A", table)
        self.assertIn("Val 1", table)
        self.assertIn("200", table)

    def test_format_table_empty_rows(self):
        self.assertEqual(view_analytics.format_table([], []), "(no rows to display)\n")

    def test_display_private_report_formats_collected_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "report.json"
            sample = {
                "start_date": "2026-10-01",
                "end_date": "2026-10-28",
                "collected_at": "2026-10-29T10:00:00Z",
                "reports": {
                    "daily": {
                        "status": "collected",
                        "columns": [{"name": "day"}, {"name": "views"}],
                        "rows": [["2026-10-28", 120]],
                    },
                    "videos": {
                        "status": "collected",
                        "columns": [{"name": "video"}, {"name": "views"}],
                        "rows": [["7RDX0fbIOtQ", 120]],
                    },
                    "traffic_sources": {"status": "collected", "columns": ["source", "views"], "rows": [["SUGGESTED", 80]]},
                },
            }
            p.write_text(json.dumps(sample), encoding="utf-8")
            self.assertTrue(view_analytics.display_private_report(p))

    def test_display_public_snapshot_formats_csv_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            json_p = Path(tmp) / "channel-metrics.json"
            csv_p = Path(tmp) / "metrics.csv"
            json_p.write_text(json.dumps({
                "snapshot_date": "2026-10-29",
                "channel_id": "UC_TEST",
                "subscriber_count": 520,
            }), encoding="utf-8")
            csv_p.write_text("snapshot_date,video_id,title,published_at,views,likes,comments\n2026-10-29,7RDX0fbIOtQ,Psalm 91,2026-10-29,150,12,3\n", encoding="utf-8")

            self.assertTrue(view_analytics.display_public_snapshot(csv_p, json_p))
