"""Guards for the monitor — the thing that stops "it looked fine" being an answer.

The rules these tests pin are the ones that were violated in production:

* a workflow that never ran is a fault, not a clean sheet;
* a NEW workflow is not yet a fault (its first window has not closed);
* a workflow that failed *before* it was last edited is untested, not broken;
* one that fails with nothing changed since is blocking;
* "ran successfully" without an outcome is still worth reporting.
"""
import json
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

        patch = mock.patch.object(am, "last_commit_for", return_value=NOW - timedelta(days=30))
        self.last_commit = patch.start()
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
        with mock.patch.object(am, "first_commit_for", return_value=NOW - timedelta(hours=2)):
            report = self.classify([])
        row = report.automations[0]
        self.assertEqual(row.verdict, "NEW")
        self.assertEqual(row.severity, "warning")

    def test_a_fresh_success_is_ok(self):
        report = self.classify([run("produce.yml", 2)])
        self.assertEqual(report.automations[0].verdict, "OK")
        self.assertTrue(report.healthy)

    def test_a_success_older_than_the_cron_window_is_overdue(self):
        report = self.classify([run("produce.yml", 40)])
        self.assertEqual(report.automations[0].verdict, "OVERDUE")
        self.assertEqual(report.automations[0].severity, "blocking")

    def test_a_failure_with_nothing_changed_since_is_blocking(self):
        report = self.classify([run("produce.yml", 2, "failure")])
        self.assertEqual(report.automations[0].verdict, "FAILING")
        self.assertEqual(report.automations[0].severity, "blocking")

    def test_a_failure_older_than_the_last_edit_is_only_untested(self):
        self.last_commit.return_value = NOW - timedelta(hours=1)
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


class TestOutcomes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pub = Path(self.tmp.name) / "published"
        self.pub.mkdir()
        self.queue = Path(self.tmp.name) / "queue"
        self.queue.mkdir()

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
        receipt.write_text("---\nyoutube_video_id: abc\n---\n", encoding="utf-8")
        report = self.outcomes()
        upload = [o for o in report.outcomes if o["outcome"] == "last upload"][0]
        self.assertEqual(upload["severity"], "ok")

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
