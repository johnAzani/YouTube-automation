from datetime import datetime, timezone
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

    def test_audit_longform_queue_finds_approved_job(self):
        items, approved = audit_longform_queue()
        self.assertGreater(len(items), 0)
        self.assertTrue(approved)
        self.assertTrue(all(parse_script(p).status == "approved" for p in approved))

    def test_audit_shorts_queue_finds_approved_manifest(self):
        items, approved = audit_shorts_queue()
        self.assertGreater(len(items), 0)
        self.assertTrue(any(it.identifier == "short-psalm23" and it.status == "approved" for it in items))

    def test_build_schedule_audit_structure(self):
        audit = build_schedule_audit()
        self.assertEqual(audit.subscribers, 1230)
        self.assertEqual(audit.watch_hours_target, 4000)
        self.assertGreaterEqual(audit.longform_approved_count, 1)
        self.assertGreaterEqual(audit.shorts_approved_count, 1)
        _, approved = audit_longform_queue()
        self.assertIn(parse_script(approved[0]).title, audit.next_longform or "")
        selected = select_next_queued_short()
        if selected:
            self.assertIn(selected[1], audit.next_short or "")
        else:
            self.assertIsNone(audit.next_short)
        self.assertGreater(audit.runway_days, 0)
