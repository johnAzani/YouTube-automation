from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

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
        # Second slot should be 06:14 UTC tomorrow
        self.assertEqual(slots[1], datetime(2026, 10, 30, 6, 14, tzinfo=timezone.utc))
        # Third slot should be 14:14 UTC tomorrow
        self.assertEqual(slots[2], datetime(2026, 10, 30, 14, 14, tzinfo=timezone.utc))
        # Fourth slot should be 06:14 UTC day after tomorrow
        self.assertEqual(slots[3], datetime(2026, 10, 31, 6, 14, tzinfo=timezone.utc))

    def test_audit_longform_queue_finds_approved_job(self):
        items, approved = audit_longform_queue()
        self.assertGreater(len(items), 0)
        # Job 0009 should be approved
        approved_ids = [p.name for p in approved]
        self.assertTrue(any("0009" in name for name in approved_ids))

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
        self.assertIn("Psalm 23", audit.next_longform or "")
        self.assertIn("short-psalm23", audit.next_short or "")
        self.assertGreater(audit.runway_days, 0)
