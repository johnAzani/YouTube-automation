"""Guards for the monitor — the thing that stops "it looked fine" being an answer.

The rules these tests pin are the ones that were violated in production:

* a workflow that never ran is a fault, not a clean sheet;
* a NEW workflow is not yet a fault (its first window has not closed);
* a workflow that failed *before* it was last edited is untested, not broken;
* one that fails with nothing changed since is blocking;
* "ran successfully" without an outcome is still worth reporting.
"""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import automation_monitor as am

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)


def run(filename, hours_ago, conclusion="success"):
    return {
        "path": f".github/workflows/{filename}",
        "created_at": (NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z"),
        "conclusion": conclusion,
    }


class MonitorCase(unittest.TestCase):
    def setUp(self):
        self.files = [("produce.yml", "Produce video", ["14 6 * * *"])]
        patch = mock.patch.object(am, "workflow_files", return_value=self.files)
        patch.start()
        self.addCleanup(patch.stop)

        patch = mock.patch.object(am, "first_commit_for", return_value=NOW - timedelta(days=30))
        patch.start()
        self.addCleanup(patch.stop)

        patch = mock.patch.object(am, "last_edit", return_value=NOW - timedelta(days=30))
        self.last_edit = patch.start()
        self.addCleanup(patch.stop)

    def classify(self, runs):
        report = am.MonitorReport()
        return am.classify(report, runs, now=NOW)


class TestRunEvidence(MonitorCase):
    def test_a_workflow_that_never_ran_is_blocking(self):
        report = self.classify([])
        row = report.automations[0]
        self.assertEqual(row.verdict, "NEVER RAN")
        self.assertEqual(row.severity, "blocking")
        self.assertFalse(report.healthy)

    def test_a_brand_new_workflow_is_not_a_fault_yet(self):
        with mock.patch.object(am, "last_edit", return_value=NOW - timedelta(hours=2)):
            report = self.classify([])
        row = report.automations[0]
        self.assertEqual(row.verdict, "NEW")
        self.assertEqual(row.severity, "warning")

    def test_a_fresh_success_is_ok(self):
        report = self.classify([run("produce.yml", 2)])
        self.assertEqual(report.automations[0].verdict, "OK")
        self.assertTrue(report.healthy)

    def test_a_stale_success_is_never_ok(self):
        # A daily cron with a 40h-old run has missed today's slot; it is caught
        # there rather than waiting for the generic overdue window.
        report = self.classify([run("produce.yml", 40)])
        self.assertIn(report.automations[0].verdict, {"MISSED SLOT", "OVERDUE"})
        self.assertEqual(report.automations[0].severity, "blocking")

    def test_a_cron_the_slot_parser_cannot_read_still_goes_overdue(self):
        self.files = [("produce.yml", "Produce video", ["14 6 1 * *"])]  # day-of-month
        patch = mock.patch.object(am, "workflow_files", return_value=self.files)
        patch.start()
        self.addCleanup(patch.stop)
        report = self.classify([run("produce.yml", 24 * 40)])
        self.assertEqual(report.automations[0].verdict, "OVERDUE")
        self.assertEqual(report.automations[0].severity, "blocking")

    def test_a_failure_with_nothing_changed_since_is_blocking(self):
        report = self.classify([run("produce.yml", 2, "failure")])
        self.assertEqual(report.automations[0].verdict, "FAILING")
        self.assertEqual(report.automations[0].severity, "blocking")

    def test_a_failure_older_than_the_last_edit_is_only_untested(self):
        self.last_edit.return_value = NOW - timedelta(hours=1)
        report = self.classify([run("produce.yml", 3, "failure")])
        row = report.automations[0]
        self.assertEqual(row.verdict, "UNTESTED FIX")
        self.assertEqual(row.severity, "warning")
        self.assertIn("needs one green run", row.detail)

    def test_repeated_failures_are_flagged_even_when_the_last_one_passed(self):
        runs = [run("produce.yml", 1), run("produce.yml", 7, "failure"),
                run("produce.yml", 13, "failure"), run("produce.yml", 19, "failure")]
        report = self.classify(runs)
        self.assertEqual(report.automations[0].verdict, "FLAKY")

    def test_an_empty_history_never_reports_healthy(self):
        report = self.classify([])
        self.assertFalse(report.healthy)
        self.assertEqual(len(report.blocking), 1)

    def test_the_rendered_table_names_the_workflow_and_verdict(self):
        text = am.render(self.classify([run("produce.yml", 2)]))
        self.assertIn("produce.yml", text)
        self.assertIn("OK", text)


class TestMissedSlots(unittest.TestCase):
    """A slot that produced no run is a fault the same day, not a week later."""

    def setUp(self):
        self.files = [("weekly.yml", "Weekly", ["23 3 * * 1"])]   # Mondays 03:23 UTC
        patch = mock.patch.object(am, "workflow_files", return_value=self.files)
        patch.start()
        self.addCleanup(patch.stop)

    def classify(self, last_run):
        patch = mock.patch.object(am, "last_edit", return_value=NOW - timedelta(days=30))
        patch.start()
        self.addCleanup(patch.stop)
        report = am.MonitorReport()
        return am.classify(report, [run("weekly.yml", last_run)], now=NOW)

    def test_the_monday_slot_is_recognised(self):
        # NOW is Monday 09:00; the slot was 03:23 — 5h37m ago.
        self.assertEqual(am.prev_occurrence(["23 3 * * 1"], NOW),
                         datetime(2026, 11, 2, 3, 23, tzinfo=timezone.utc))

    def test_no_run_since_todays_slot_is_blocking(self):
        row = self.classify(24 * 7 - 1).automations[0]      # last ran a week ago
        self.assertEqual(row.verdict, "MISSED SLOT")
        self.assertEqual(row.severity, "blocking")
        self.assertIn("did not run", row.detail)

    def test_a_run_just_after_the_slot_is_fine(self):
        row = self.classify(5).automations[0]               # 5h ago = 04:00
        self.assertEqual(row.verdict, "OK")

    def test_a_late_scheduler_within_grace_is_not_an_alarm(self):
        row = self.classify(4).automations[0]               # 05:00, ~1.6h after slot
        self.assertEqual(row.verdict, "OK")

    def test_grace_is_measured_after_the_slot_not_before_it(self):
        """A slot 30 minutes old with no run yet is late, not missed."""
        from scripts import automation_monitor as amod

        now = datetime(2026, 11, 2, 6, 45, tzinfo=timezone.utc)   # 06:14 slot +31m
        auto = amod.Automation(workflow="daily.yml", name="D", crons=["14 6 * * *"])
        auto.last_run = datetime(2026, 11, 1, 6, 14, tzinfo=timezone.utc)
        auto.last_slot = amod.prev_occurrence(auto.crons, now)
        auto.last_edited = datetime(2026, 10, 1, tzinfo=timezone.utc)
        amod._verdict(auto, now)
        self.assertNotEqual(auto.verdict, "MISSED SLOT")

    def test_every_three_hours_is_understood(self):
        slot = am.prev_occurrence(["23 */3 * * *"], NOW)
        self.assertEqual(slot, datetime(2026, 11, 2, 6, 23, tzinfo=timezone.utc))

    def test_the_slot_is_reported_in_the_owners_zone(self):
        """The owner reads WAT, so a 03:23 UTC Monday slot is 04:23 Monday morning."""
        row = self.classify(24 * 7 - 1).automations[0]
        self.assertIn("Mon 02 Nov 04:23 WAT", row.detail)
        self.assertNotIn("UTC", row.detail)

    def test_the_table_prints_wat_not_utc(self):
        report = self.classify(24 * 7 - 1)
        table = am.render(report)
        self.assertIn("all times WAT", table)
        self.assertIn("26 Oct 11:00", table)   # last run 26 Oct 10:00 UTC -> 11:00 WAT

    def test_day_of_week_lists_are_understood(self):
        slot = am.prev_occurrence(["14 19 * * 0,3"], NOW)   # Sunday & Wednesday
        self.assertEqual(slot, datetime(2026, 11, 1, 19, 14, tzinfo=timezone.utc))


class TestLastEditedIsHonest(unittest.TestCase):
    """A squashed checkout claims every file changed at the tip commit."""

    def test_local_git_is_not_trusted_without_history(self):
        with mock.patch.object(am, "history_depth", return_value=1):
            self.assertIsNone(am.last_commit_for(am.WORKFLOWS / "produce.yml"))

    def test_github_is_preferred_when_available(self):
        api = mock.Mock(returncode=0,
                        stdout='[{"commit": {"committer": {"date": "2026-10-30T22:37:39Z"}}}]')
        with mock.patch.object(am, "gh_available", return_value=True), \
             mock.patch.object(am, "_gh", return_value=api), \
             mock.patch.object(am, "repo_slug", return_value="o/r"):
            self.assertEqual(am.last_edit("metrics.yml"),
                             datetime(2026, 10, 30, 22, 37, 39, tzinfo=timezone.utc))

    def test_it_falls_back_to_git_when_the_api_is_unavailable(self):
        with mock.patch.object(am, "gh_available", return_value=False), \
             mock.patch.object(am, "last_commit_for",
                               return_value=datetime(2026, 10, 1, tzinfo=timezone.utc)):
            self.assertIsNotNone(am.last_edit("produce.yml"))


class TestOutcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pub = Path(self.tmp.name) / "published"
        self.pub.mkdir()
        self.queue = Path(self.tmp.name) / "content" / "queue"
        self.queue.mkdir(parents=True)

    def outcomes(self, log=None):
        report = am.MonitorReport()
        with mock.patch.object(am, "ROOT", Path(self.tmp.name)):
            return am.check_outcomes(report, now=NOW, published_dir=self.pub,
                                     log_path=log or Path(self.tmp.name) / "none.json")

    def test_no_upload_ever_is_blocking(self):
        report = self.outcomes()
        upload = [o for o in report.outcomes if o["outcome"] == "last upload"][0]
        self.assertEqual(upload["severity"], "blocking")

    def test_a_recent_upload_is_ok(self):
        receipt = self.pub / "0010-x.md"
        stamp = (NOW - timedelta(hours=3)).date().isoformat()
        receipt.write_text(f'---\nyoutube_video_id: abc\npublished_on: "{stamp}"\n---\n',
                           encoding="utf-8")
        report = self.outcomes()
        upload = [o for o in report.outcomes if o["outcome"] == "last upload"][0]
        self.assertEqual(upload["severity"], "ok")

    def test_file_mtime_never_counts_as_an_upload(self):
        """A fresh CI checkout stamps every file with today, which used to read as
        "uploaded minutes ago" on a channel that had published nothing for a day."""
        receipt = self.pub / "0010-x.md"
        receipt.write_text("---\nyoutube_video_id: abc\n---\n", encoding="utf-8")
        os.utime(receipt, (NOW.timestamp(), NOW.timestamp()))
        report = self.outcomes()
        upload = [o for o in report.outcomes if o["outcome"] == "last upload"][0]
        self.assertEqual(upload["detail"], "none recorded")
        self.assertEqual(upload["severity"], "blocking")

    def test_a_stale_upload_is_blocking_after_two_days(self):
        receipt = self.pub / "0010-x.md"
        stamp = (NOW - timedelta(days=3)).date().isoformat()
        receipt.write_text(f'---\nyoutube_video_id: abc\npublished_on: "{stamp}"\n---\n',
                           encoding="utf-8")
        report = self.outcomes()
        upload = [o for o in report.outcomes if o["outcome"] == "last upload"][0]
        self.assertEqual(upload["severity"], "blocking")

    def test_zero_publishable_scripts_block_the_next_slot(self):
        (self.queue / "0001-a.md").write_text(
            "---\nid: '0001'\nstatus: approved\nformat: longform\n---\n\n"
            "## Scene 1 — One\n" + "word " * 300, encoding="utf-8")
        (self.queue / "0002-b.md").write_text(
            "---\nid: '0002'\nstatus: approved\nformat: longform\n---\n\n"
            "## Scene 1 — One\n" + "word " * 900, encoding="utf-8")
        with mock.patch.object(am, "ROOT", Path(self.tmp.name)):
            report = am.check_outcomes(am.MonitorReport(), now=NOW, published_dir=self.pub,
                                       log_path=Path(self.tmp.name) / "none.json")
        runway = [o for o in report.outcomes if o["outcome"] == "publishable runway"][0]
        self.assertEqual(runway["severity"], "ok")
        self.assertIn("1 of 2 approved", runway["detail"])

    def test_an_empty_publishable_runway_is_blocking(self):
        (self.queue / "0001-a.md").write_text(
            "---\nid: '0001'\nstatus: approved\nformat: longform\n---\n\n"
            "## Scene 1 — One\n" + "word " * 300, encoding="utf-8")
        with mock.patch.object(am, "ROOT", Path(self.tmp.name)):
            report = am.check_outcomes(am.MonitorReport(), now=NOW, published_dir=self.pub,
                                       log_path=Path(self.tmp.name) / "none.json")
        runway = [o for o in report.outcomes if o["outcome"] == "publishable runway"][0]
        self.assertEqual(runway["severity"], "blocking")

    def test_replies_are_counted_from_the_ledger(self):
        log = Path(self.tmp.name) / "replied.json"
        log.write_text(json.dumps({
            "c1": {"reply_id": "r1"}, "c2": {"category": "CRISIS_ESCALATED"}}),
            encoding="utf-8")
        report = self.outcomes(log=log)
        row = [o for o in report.outcomes if o["outcome"] == "replies recorded"][0]
        self.assertIn("1 live", row["detail"])


class TestFindingsFeedTheWatchdog(unittest.TestCase):
    def test_findings_carry_severity_through(self):
        report = am.MonitorReport()
        auto = am.Automation(workflow="x.yml", name="X", crons=["14 6 * * *"])
        auto.verdict, auto.severity, auto.detail = "NEVER RAN", "blocking", "never"
        report.automations.append(auto)
        rows = am.findings(report)
        self.assertEqual(rows, [("x.yml", "NEVER RAN — never", True)])

    def test_ok_rows_produce_no_noise(self):
        report = am.MonitorReport()
        auto = am.Automation(workflow="x.yml", name="X", crons=["14 6 * * *"])
        auto.verdict, auto.severity, auto.detail = "OK", "ok", "fine"
        report.automations.append(auto)
        self.assertEqual(am.findings(report), [])


class TestMonitorWorkflow(unittest.TestCase):
    def setUp(self):
        import yaml

        path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "monitor.yml"
        self.text = path.read_text(encoding="utf-8")
        self.data = yaml.safe_load(self.text)

    def test_it_runs_at_least_every_six_hours(self):
        crons = self.data[True]["schedule"]
        hour_field = crons[0]["cron"].split()[1]
        self.assertIn("/3", hour_field, "monitoring must be continuous, not weekly")

    def test_it_can_file_issues(self):
        self.assertEqual(self.data["permissions"]["issues"], "write")

    def test_it_can_read_run_history(self):
        self.assertEqual(self.data["permissions"]["actions"], "read")

    def test_it_checks_out_full_history(self):
        # The monitor dates a workflow's edits against its runs.
        self.assertIn("fetch-depth: 0", self.text)

    def test_it_runs_both_the_monitor_and_the_watchdog(self):
        self.assertIn("scripts.automation_monitor", self.text)
        self.assertIn("scripts.pipeline_watchdog", self.text)

    def test_the_watchdog_is_allowed_to_fail_the_job(self):
        # A red monitor run is a signal; swallowing it would recreate the bug.
        self.assertNotIn("|| true", self.text.split("File or close the stall issue")[1]
                         .split("Commit the monitor snapshot")[0])


if __name__ == "__main__":
    unittest.main()
