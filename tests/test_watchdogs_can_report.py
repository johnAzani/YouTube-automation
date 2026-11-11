"""The watchdogs must be able to report the news they find.

On 2 November the monitor raised its alarm and then skipped the step that files
the issue — the run page showed only "exit code 1" and no issue was opened. Two of
its three workflows were red at the end of the day with nothing said about why.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT


def code_only(text: str) -> str:
    """Workflow text with comment lines removed — prose may name anything."""
    return "\n".join(line for line in text.splitlines()
                     if not line.strip().startswith("#"))


def wf(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def steps(name: str, job: str | None = None) -> list[dict]:
    jobs = wf(name)["jobs"]
    return jobs[job or next(iter(jobs))]["steps"]


def by_name(rows: list[dict], prefix: str) -> dict:
    return [s for s in rows if str(s.get("name", "")).startswith(prefix)][0]


class TestTheMonitorCanReportWhatItFound(unittest.TestCase):
    def test_the_audit_cannot_stop_the_issue_being_filed(self):
        audit = by_name(steps("monitor.yml"), "Audit every automation")
        self.assertTrue(audit.get("continue-on-error"),
                        "an exit 1 alarm must not skip the step that reports it")
        self.assertEqual(audit.get("id"), "audit")

    def test_the_issue_step_runs_even_after_a_failed_audit(self):
        filing = by_name(steps("monitor.yml"), "File or close the stall issue")
        self.assertIn("always()", filing.get("if", ""))

    def test_the_run_still_ends_red_when_the_audit_found_something(self):
        rows = steps("monitor.yml")
        last = rows[-1]
        self.assertIn("stalled automation", last["name"])
        self.assertIn("steps.audit.outcome == 'failure'", last["if"])
        self.assertIn("exit 1", last["run"])

    def test_the_snapshot_commits_before_the_run_turns_red(self):
        names = [s.get("name", "") for s in steps("monitor.yml")]
        self.assertLess(names.index("Commit the monitor snapshot"),
                        len(names) - 1)

    def test_the_snapshot_never_rebases(self):
        source = code_only((ROOT / ".github" / "workflows" / "monitor.yml")
                           .read_text(encoding="utf-8"))
        self.assertNotIn("pull --rebase", source)


class TestTheWatchdogSaysWhatIsWrong(unittest.TestCase):
    def test_a_blocking_finding_becomes_a_named_annotation(self):
        source = (ROOT / "scripts" / "pipeline_watchdog.py").read_text(encoding="utf-8")
        self.assertIn("::error title=Automation is stalled (", source)

    def test_every_blocking_finding_is_reported_not_just_the_first(self):
        source = (ROOT / "scripts" / "pipeline_watchdog.py").read_text(encoding="utf-8")
        self.assertIn("for finding in blocking:", source)


class TestKeepaliveCoversEveryWorkflow(unittest.TestCase):
    """It re-enabled three hardcoded workflows out of seventeen.

    GitHub disables scheduled workflows after 60 days of repository inactivity, and
    can disable an individual one whose YAML stops parsing. A hardcoded list does not
    notice a workflow added after the list was written.
    """

    def test_it_asks_the_repository_for_the_list(self):
        step = by_name(steps("keepalive.yml"), "Re-enable every workflow")
        self.assertIn("actions/workflows?per_page=100", step["run"])
        self.assertNotIn("for wf in produce.yml dry-run.yml keepalive.yml", step["run"])

    def test_it_reports_workflows_it_could_not_enable(self):
        step = by_name(steps("keepalive.yml"), "Re-enable every workflow")
        self.assertIn("::warning::", step["run"])


class TestNoWorkflowIsPinnedToADeadBranch(unittest.TestCase):
    def test_no_trigger_watches_a_session_branch(self):
        offenders = []
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = code_only(path.read_text(encoding="utf-8"))
            for token in ("arena/564c86c7", "arena/eb029c66", "arena/79365da2"):
                if token in text:
                    offenders.append(f"{path.name}: {token}")
        self.assertEqual(offenders, [])

    def test_the_alignment_check_runs_on_main(self):
        on = wf("prayer-alignment-check.yml")[True]
        self.assertEqual(on["push"]["branches"], ["main"])

    def test_the_preview_renders_the_shipping_code(self):
        text = (ROOT / ".github" / "workflows" / "preview-render.yml").read_text(encoding="utf-8")
        self.assertIn("ref: main", text)

    def test_the_gemini_diagnostic_can_actually_run(self):
        on = wf("gemini-key-diagnostic.yml")[True]
        self.assertIn("workflow_dispatch", on)
        self.assertNotIn("arena/", str(on))
        job = wf("gemini-key-diagnostic.yml")["jobs"]["check"]
        self.assertIsNone(job.get("if"), "a job-level branch guard made this unrunnable")


class TestOnePythonVersionAcrossTheFleet(unittest.TestCase):
    def test_every_workflow_pins_the_same_python(self):
        versions = set()
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            for job in (data.get("jobs") or {}).values():
                for step in job.get("steps") or []:
                    value = (step.get("with") or {}).get("python-version")
                    if value:
                        versions.add(str(value))
        self.assertEqual(versions, {"3.12"})


if __name__ == "__main__":
    unittest.main()


class AWorkflowCannotLatchItselfRed(unittest.TestCase):
    """Two watchdogs were stuck red because they counted their own red runs.

    On 3 November `automation-health.yml` and `monitor.yml` both read FAILING with
    "failed 41m ago and nothing was changed since". The failure they were reading
    was their own previous verdict, so neither could ever recover — a loop with no
    exit condition, in the two jobs whose job is to notice loops.
    """

    def _automation(self, workflow, conclusion="failure"):
        from datetime import datetime, timedelta, timezone
        from scripts import automation_monitor as am

        auto = am.Automation(workflow=workflow, name=workflow, crons=["0 * * * *"])
        auto.last_run = datetime.now(timezone.utc) - timedelta(minutes=41)
        auto.last_conclusion = conclusion
        auto.last_edited = auto.last_run - timedelta(days=1)
        auto.max_gap = timedelta(days=1)
        return auto

    def test_its_own_red_run_is_not_evidence_against_itself(self):
        from datetime import datetime, timezone
        from scripts import automation_monitor as am

        auto = self._automation("Automation monitor")
        with mock.patch.dict(os.environ, {"GITHUB_WORKFLOW": "Automation monitor"}):
            # GITHUB_WORKFLOW carries the display name; the check must match either.
            am._verdict(auto, datetime.now(timezone.utc))
        self.assertEqual(auto.verdict, "SELF-REPORT")
        self.assertEqual(auto.severity, "info")

    def test_another_workflows_red_run_is_still_a_stall(self):
        from datetime import datetime, timezone
        from scripts import automation_monitor as am

        auto = self._automation("produce.yml")
        with mock.patch.dict(os.environ, {"GITHUB_WORKFLOW": "Automation monitor"}):
            am._verdict(auto, datetime.now(timezone.utc))
        self.assertEqual(auto.verdict, "FAILING")
        self.assertEqual(auto.severity, "blocking")

    def test_the_health_job_installs_its_dependencies(self):
        text = (REPO / ".github" / "workflows" / "automation-health.yml").read_text()
        self.assertIn("pip install -r requirements.txt", text,
                      "the watchdog imports PyYAML; without deps it dies before it can report")

    def test_a_blanket_true_cannot_hide_a_crash(self):
        text = (REPO / ".github" / "workflows" / "automation-health.yml").read_text()
        self.assertNotIn("scripts.automation_health || true", text,
                         "`|| true` turned a ModuleNotFoundError into a green tick")
        self.assertIn("no audit table was produced", text)


class TheReporterCannotCrashOnItsOwnVocabulary(unittest.TestCase):
    """`render()` raised ValueError on any severity it had not seen before.

    Adding one verdict ("info", for the self-report case) took the whole monitor
    down inside its own renderer — the alarm dying on the way to the alarm bell.
    """

    def test_an_unfamiliar_severity_still_renders(self):
        from datetime import datetime, timezone
        from scripts import automation_monitor as am

        auto = am.Automation(workflow="x.yml", name="X", crons=["0 * * * *"])
        auto.verdict, auto.detail, auto.severity = "WEIRD", "something new", "novel"
        auto.last_run = datetime.now(timezone.utc)
        report = am.MonitorReport(generated_at=datetime.now(timezone.utc),
                                  automations=[auto], outcomes=[])
        text = am.render(report)
        self.assertIn("WEIRD", text)
        self.assertIn("something new", text)


class AFailedDeliveryMustNotDestroyTheFinding(unittest.TestCase):
    def test_the_watchdog_still_reports_when_filing_fails(self):
        from scripts import pipeline_watchdog as pw

        report = pw.Report()
        report.add("queues", "nothing is publishable")
        with mock.patch.object(pw, "sync_issue", side_effect=RuntimeError("gh exploded")), \
             mock.patch.object(pw, "build_report", return_value=report), \
             mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            code = pw.main([])
        self.assertEqual(code, 1, "an unhealthy pipeline must still exit non-zero")

    def test_the_issue_is_found_by_title_when_the_label_did_not_stick(self):
        from scripts import pipeline_watchdog as pw

        seen = []

        class Result:
            def __init__(self, stdout="", returncode=0):
                self.stdout, self.returncode, self.stderr = stdout, returncode, ""

        def fake_gh(args):
            seen.append(args)
            if "--label" in args:
                return Result("[]")          # labels are not applied on this repo
            return Result('{"number": 42}'.replace("{", "[{").replace("}", "}]"))

        with mock.patch.object(pw, "_gh", fake_gh):
            self.assertEqual(pw.open_issue_number(), 42)
        self.assertTrue(any("--search" in args for args in seen))


class TestADegradedVerdictNamesItself(unittest.TestCase):
    """A red run whose annotation says only "the watchdog opened an issue" has not
    reported anything. That is exactly what run 42235642633 showed on 6 November:
    the exit 1 came from warnings (a fix never run green, a flaky workflow), no
    blocking finding existed, and the annotation named none of them.
    """

    def _run_main(self, report):
        import io
        from contextlib import redirect_stdout
        from scripts import pipeline_watchdog as wd

        buf = io.StringIO()
        with mock.patch.object(wd, "build_report", return_value=report), \
             mock.patch.object(wd, "sync_issue", return_value="updated"), \
             mock.patch.object(wd, "cleanup_stale_issues", return_value=[]), \
             mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), \
             redirect_stdout(buf):
            code = wd.main([])
        return code, buf.getvalue()

    def test_each_warning_is_named_on_the_run_page(self):
        from scripts import pipeline_watchdog as wd

        report = wd.Report()
        report.add("automations", "gemini_brain.yml: FLAKY — 4 of its last 5 runs failed",
                   fatal=False, warning=True)
        code, out = self._run_main(report)
        self.assertEqual(code, 1, "degraded is not healthy; the run must stay red")
        self.assertIn("::error title=Pipeline is degraded (automations)", out)
        self.assertIn("gemini_brain.yml: FLAKY", out)

    def test_a_blocking_finding_still_wins_the_title(self):
        from scripts import pipeline_watchdog as wd

        report = wd.Report()
        report.add("long-form queue", "Secret Place has nothing approved", fatal=True)
        report.add("automations", "comments.yml: FLAKY", fatal=False, warning=True)
        code, out = self._run_main(report)
        self.assertEqual(code, 1)
        self.assertIn("::error title=Automation is stalled (long-form queue)", out)
        self.assertNotIn("Pipeline is degraded", out)


def test_keepalive_respects_manual_workflow_pauses():
    run = by_name(steps("keepalive.yml"), "Re-enable every workflow")["run"]
    assert 'select(.state == "disabled_inactivity")' in run
    assert '.state != "deleted_by_user"' not in run
