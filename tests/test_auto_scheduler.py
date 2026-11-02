from datetime import datetime, timezone
from unittest import mock
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from pipeline.script_doc import parse_script
from pipeline.short_release import select_next_queued_short

from scripts.auto_scheduler import (
    audit_longform_queue,
    audit_shorts_queue,
    build_schedule_audit,
    get_next_cron_times,
)


class TestAutoScheduler(unittest.TestCase):
    def test_get_next_cron_times_returns_ordered_future_utc_slots(self):
        base = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
        slots = get_next_cron_times(base, count=4)
        self.assertEqual(len(slots), 4)
        # First slot after 12:00 UTC should be 14:14 UTC today
        self.assertEqual(slots[0], datetime(2026, 10, 29, 14, 14, tzinfo=timezone.utc))
        # Second slot should be 19:14 UTC today (8:14pm local bedtime release)
        self.assertEqual(slots[1], datetime(2026, 10, 29, 19, 14, tzinfo=timezone.utc))
        # Third slot should be 06:14 UTC tomorrow (morning devotional)
        self.assertEqual(slots[2], datetime(2026, 10, 30, 6, 14, tzinfo=timezone.utc))
        # Fourth slot should be 14:14 UTC tomorrow
        self.assertEqual(slots[3], datetime(2026, 10, 30, 14, 14, tzinfo=timezone.utc))

    def test_audit_longform_queue_only_counts_runnable_jobs(self):
        """`approved` means it can actually publish: approved AND above the word floor.
        An approved-but-short script is queued work that fails at the publisher."""
        from pipeline.script_doc import MIN_LONGFORM_WORDS
        items, approved = audit_longform_queue()
        self.assertGreater(len(items), 0)
        for path in approved:
            doc = parse_script(path)
            self.assertEqual(doc.status, "approved")
            self.assertGreaterEqual(doc.word_count, MIN_LONGFORM_WORDS, path.name)

    def test_audit_shorts_queue_marks_unrenderable_as_blocked(self):
        """Approved scripture with no scene script cannot publish; counting it as
        approved inflated the runway and hid a stalled queue."""
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.yml").write_text(
                "short: short-psalm23\nstatus: approved\n", encoding="utf-8")
            (Path(tmp) / "b.yml").write_text(
                "short: short-psalm91\nstatus: approved\n", encoding="utf-8")
            with mock.patch("scripts.auto_scheduler.SHORTS_QUEUE_DIR", Path(tmp)), \
                 mock.patch("pipeline.short_release._renderer_script_keys",
                            return_value={"short-psalm91"}):
                items, approved = audit_shorts_queue()
        by_id = {i.identifier: i.status for i in items}
        self.assertEqual(by_id["short-psalm23"], "blocked")
        self.assertEqual(by_id["short-psalm91"], "approved")
        self.assertEqual([p.name for p in approved], ["b.yml"])

    def test_build_schedule_audit_structure(self):
        audit = build_schedule_audit()
        self.assertEqual(audit.subscribers, 1230)
        self.assertEqual(audit.watch_hours_target, 4000)
        # counts must agree with what is actually runnable, not with a magic number:
        # the queue can legitimately hold nothing publishable (scripts awaiting
        # expansion, Shorts awaiting a scene script)
        self.assertEqual(audit.longform_approved_count, len(audit_longform_queue()[1]))
        self.assertEqual(audit.shorts_approved_count, len(audit_shorts_queue()[1]))
        _, approved = audit_longform_queue()
        if approved:
            self.assertIn(parse_script(approved[0]).title, audit.next_longform or "")
        else:
            # nothing runnable is a valid state — it must read as None, not as a lie
            self.assertIsNone(audit.next_longform)
        selected = select_next_queued_short()
        if selected:
            self.assertIn(selected[1], audit.next_short or "")
        else:
            self.assertIsNone(audit.next_short)
        # runway is derived from runnable work, so zero is a legitimate reading and
        # must be reported as zero rather than flattered by unbuildable queue rows
        self.assertGreaterEqual(audit.runway_days, 0)
