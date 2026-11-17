"""What the YouTube Data API charges, and what the pipeline's own records say it spent.

The prices are Google's published method-level costs, which the discovery
document bundled with the client does not carry: the only quota sentences in
``youtube.v3.json`` price `part` parameters and live-chat methods. A 2026-11-07
audit read the part sentence ("the snippet part has a quota cost of 2 units") as
the price of a comment reply and wrote 2 into two documents; the method's page
says 50 in its first line. These tests exist so the 2-unit belief cannot come
back quietly.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pipeline import api_budget
from scripts import automation_monitor as am

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


class TestPrices(unittest.TestCase):
    def test_the_prices_a_correction_got_wrong(self):
        self.assertEqual(api_budget.UNIT_COST["comments.insert"], 50)
        self.assertEqual(api_budget.UNIT_COST["commentThreads.insert"], 50)
        self.assertEqual(api_budget.UNIT_COST["captions.insert"], 400)
        self.assertEqual(api_budget.UNIT_COST["thumbnails.set"], 50)
        self.assertEqual(api_budget.UNIT_COST["videos.update"], 50)

    def test_an_upload_is_one_unit_of_its_own_allowance(self):
        """The receipts forbid the 1,600-unit model: a channel uploaded eight videos
        in one Pacific quota day (secret-place, 11 November 2026)."""
        self.assertEqual(api_budget.UNIT_COST["videos.insert"], 1)
        self.assertEqual(api_budget.UPLOADS_PER_DAY, 100)
        self.assertEqual(api_budget.SHARED_POOL_UNITS, 10_000)

    def test_a_bare_upload_costs_its_insert_and_the_list_calls_around_it(self):
        units, parts = api_budget.price_upload()
        self.assertEqual(units, 1 + api_budget.UPLOAD_VERIFY_UNITS)
        self.assertEqual(list(parts), ["videos.insert", "list calls"])

    def test_everything_an_upload_can_do_is_summed(self):
        units, parts = guess = api_budget.price_upload(
            thumbnail=True, comment=True, caption=True, playlist=True)
        self.assertEqual(units, 1 + 4 + 50 + 50 + 400 + 50)
        self.assertEqual(set(parts), {"videos.insert", "list calls", "thumbnails.set",
                                      "commentThreads.insert", "captions.insert",
                                      "playlistItems.insert"})

    def test_a_caption_track_costs_eight_comments(self):
        self.assertEqual(api_budget.UNIT_COST["captions.insert"],
                         8 * api_budget.UNIT_COST["commentThreads.insert"])


class TestPriceReceipt(unittest.TestCase):
    def test_what_a_receipt_records_is_what_is_priced(self):
        units, _ = api_budget.price_receipt({"thumbnail_revision": "ctr-v3-cinema"})
        self.assertEqual(units, 1 + 4 + 50)
        units, _ = api_budget.price_receipt({"thumbnail_revision": "ctr-v3-cinema",
                                             "top_comment": "ok", "caption_track": "ok"})
        self.assertEqual(units, 1 + 4 + 50 + 50 + 400)

    def test_a_failed_or_skipped_call_is_not_priced(self):
        units, _ = api_budget.price_receipt({"top_comment": "failed",
                                             "caption_track": "failed",
                                             "thumbnail_pending": True})
        self.assertEqual(units, 1 + 4)

    def test_a_short_track_status_that_starts_with_ok_counts(self):
        units, _ = api_budget.price_receipt({"caption_track": "ok"})
        self.assertEqual(units, 1 + 4 + 400)


class TestMonitorRow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pub = Path(self.tmp.name) / "published"
        self.pub.mkdir()
        self.ledger = Path(self.tmp.name) / "replied.json"

    def receipt(self, name, published_at, *, thumb=False, comment=False, caption=False,
                fmt="longform"):
        fields = [f'published_at: "{published_at}"', "youtube_video_id: abc", f"format: {fmt}"]
        if thumb:
            fields.append('thumbnail_revision: "ctr-v3-cinema"')
        if comment:
            fields.append('top_comment: "ok"')
        if caption:
            fields.append('caption_track: "ok"')
        self.pub.joinpath(f"{name}.md").write_text(
            "---\nchannel: prayer4\n" + "\n".join(fields) + "\n---\n\nbody\n", encoding="utf-8")

    def test_the_window_is_anchored_to_the_newest_receipt(self):
        self.receipt("old", "2026-11-01T10:00:00Z", caption=True)
        self.receipt("new", "2026-11-17T10:00:00Z", thumb=True)
        figure = am.api_budget(self.pub, days=7, ledger_path=self.ledger)
        self.assertEqual(figure["uploads"], 1)
        self.assertEqual(figure["units"], 1 + 4 + 50)

    def test_a_caption_track_is_eight_times_a_comment(self):
        self.receipt("a", "2026-11-17T10:00:00Z", caption=True)
        self.receipt("b", "2026-11-16T10:00:00Z", comment=True)
        figure = am.api_budget(self.pub, days=7, ledger_path=self.ledger)
        self.assertEqual(figure["captions"], 1)
        self.assertEqual(figure["comments"], 1)
        self.assertEqual(figure["caption_units"], 400)

    def test_replies_are_priced_from_the_ledger(self):
        self.receipt("a", "2026-11-17T10:00:00Z")
        self.ledger.write_text(json.dumps({
            "c1": {"replied_at": "2026-11-16T09:00:00+00:00"},
            "c2": {"replied_at": "2026-11-10T09:00:00+00:00"},   # outside the window
        }), encoding="utf-8")
        figure = am.api_budget(self.pub, days=7, ledger_path=self.ledger)
        self.assertEqual(figure["replies"], 1)
        self.assertEqual(figure["reply_units"], 50)

    def test_nothing_published_means_nothing_priced(self):
        figure = am.api_budget(self.pub, ledger_path=self.ledger)
        self.assertEqual(figure["uploads"], 0)
        self.assertIsNone(figure["per_upload"])

    def test_the_row_is_ok_severity_and_names_the_model(self):
        self.receipt("a", "2026-11-17T10:00:00Z", caption=True)
        with mock.patch.object(am, "ROOT", Path(self.tmp.name)):
            report = am.check_outcomes(am.MonitorReport(), now=NOW, published_dir=self.pub,
                                       log_path=Path(self.tmp.name) / "none.json")
        row = [o for o in report.outcomes if o["outcome"] == "api budget"][0]
        self.assertEqual(row["severity"], "ok")
        self.assertIn("1 caption track(s) at 400", row["detail"])
        self.assertIn("separate 100-a-day allowance", row["detail"])


if __name__ == "__main__":
    unittest.main()
