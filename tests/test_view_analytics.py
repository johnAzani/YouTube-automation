import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import view_analytics


class ViewAnalyticsTests(unittest.TestCase):
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
