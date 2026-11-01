from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

from pipeline.script_doc import parse_script
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
        # Derive the expectation from the queue instead of naming a job: 0009 was
        # published and moved out of content/queue/, which made a hardcoded
        # "0009" assertion fail forever after.
        approved_ids = {parse_script(path).id for path in approved}
        self.assertTrue(approved_ids, "the queue must keep at least one approved job")
        self.assertEqual(approved_ids,
                         {item.identifier for item in items if item.status == "approved"})

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
        # The next long-form job must be the first approved queue entry, whatever
        # it happens to be today (hardcoding "Psalm 23" broke once 0009 published).
        queue_items, approved_paths = audit_longform_queue()
        self.assertTrue(approved_paths)
        self.assertTrue((audit.next_longform or "").startswith(
            f"Job {parse_script(approved_paths[0]).id}"))
        # Same treatment for Shorts: a manifest can be approved yet not selectable
        # (already published, or the renderer has no script for its key), in which
        # case select_next_queued_short legitimately returns nothing.
        short_items, short_approved = audit_shorts_queue()
        self.assertTrue(short_approved, "the Shorts queue must keep approved manifests")
        if audit.next_short:
            approved_short_keys = {item.identifier for item in short_items
                                   if item.status == "approved"}
            self.assertTrue(any(audit.next_short.startswith(key)
                                for key in approved_short_keys), audit.next_short)
        self.assertGreater(audit.runway_days, 0)
