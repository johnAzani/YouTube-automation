"""Guards for the automation health check.

The point of the check is to notice a scheduled workflow that never starts, so the
tests pin the arithmetic that decides "overdue" and the cases that must not raise a
false alarm.

Written with unittest (the CI suite runs `unittest discover`, which ignores
pytest-style classes entirely — a test that never runs is worse than no test).
"""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import automation_health as ah

NOW = datetime(2026, 11, 1, 21, 0, tzinfo=timezone.utc)


class TestCronGap(unittest.TestCase):
    def test_daily_schedule_is_one_day(self):
        self.assertEqual(ah._cron_gap(["14 6 * * *"]), timedelta(days=1))

    def test_two_days_a_week_is_a_week(self):
        self.assertEqual(ah._cron_gap(["14 19 * * 0,3"]), timedelta(days=7))

    def test_weekly_is_a_week(self):
        self.assertEqual(ah._cron_gap(["41 18 * * 5"]), timedelta(days=7))

    def test_unknown_shape_falls_back_to_daily(self):
        # conservative: a schedule we cannot parse is checked more often, not less
        self.assertEqual(ah._cron_gap(["nonsense"]), timedelta(days=1))


class TestScheduledWorkflows(unittest.TestCase):
    def test_finds_the_workflows_this_repo_actually_schedules(self):
        names = {s.workflow for s in ah.scheduled_workflows()}
        self.assertIn("produce.yml", names)
        self.assertIn("community.yml", names)
        self.assertIn("keepalive.yml", names)

    def test_manual_only_workflows_are_not_included(self):
        names = {s.workflow for s in ah.scheduled_workflows()}
        self.assertNotIn("set-thumbnail.yml", names)  # workflow_dispatch only


class TestAudit(unittest.TestCase):
    def _audit(self, last):
        schedule = ah.Schedule("x.yml", ["14 6 * * *"], timedelta(days=1))
        with mock.patch.object(ah, "scheduled_workflows", return_value=[schedule]), \
             mock.patch.object(ah, "last_run", return_value=last):
            return ah.audit(NOW)

    def test_recent_run_is_ok(self):
        self.assertEqual(self._audit(NOW - timedelta(hours=3))[0].status, "ok")

    def test_missing_run_is_flagged(self):
        self.assertEqual(self._audit(NOW - timedelta(days=3))[0].status, "OVERDUE")

    def test_grace_period_prevents_a_false_alarm(self):
        # one-day cadence plus a six-hour grace: overdue only past 30h
        self.assertEqual(self._audit(NOW - timedelta(hours=29))[0].status, "ok")
        self.assertEqual(self._audit(NOW - timedelta(hours=31))[0].status, "OVERDUE")

    def test_never_ran_is_reported_as_such(self):
        row = self._audit(None)[0]
        self.assertEqual(row.status, "NEVER RAN")
        self.assertIn("never fail", row.detail)


class TestMain(unittest.TestCase):
    def test_json_output_is_machine_readable(self):
        rows = [ah.Row("x.yml", "daily", NOW, "ok", "fine")]
        with mock.patch.object(ah, "audit", return_value=rows), \
             mock.patch("builtins.print") as printed:
            self.assertEqual(ah.main(["--json"]), 0)
        self.assertIn('"workflow": "x.yml"', printed.call_args[0][0])

    def test_overdue_exits_non_zero(self):
        rows = [ah.Row("x.yml", "daily", NOW, "OVERDUE", "late")]
        with mock.patch.object(ah, "audit", return_value=rows), \
             mock.patch.object(ah, "gh_available", return_value=True), \
             mock.patch("builtins.print"):
            self.assertEqual(ah.main([]), 1)

    def test_all_never_ran_is_a_token_problem_not_a_failure(self):
        rows = [ah.Row(f"w{i}.yml", "daily", None, "NEVER RAN", "none") for i in range(5)]
        with mock.patch.object(ah, "audit", return_value=rows), \
             mock.patch.object(ah, "gh_available", return_value=True), \
             mock.patch("builtins.print"):
            self.assertEqual(ah.main([]), 0)

    def test_without_gh_it_refuses_to_claim_health(self):
        with mock.patch.object(ah, "gh_available", return_value=False), \
             mock.patch("builtins.print") as printed:
            self.assertEqual(ah.main([]), 0)
        texts = " ".join(str(c.args[0]) for c in printed.call_args_list)
        self.assertIn("cannot verify", texts)


class TestWiring(unittest.TestCase):
    def test_the_health_workflow_exists_and_is_scheduled(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/automation-health.yml").read_text()
        self.assertIn("cron:", text)
        self.assertIn("scripts.automation_health", text)


if __name__ == "__main__":
    unittest.main()
