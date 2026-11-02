"""The watchdogs must be able to report the news they find.

On 2 November the monitor raised its alarm and then skipped the step that files
the issue — the run page showed only "exit code 1" and no issue was opened. Two of
its three workflows were red at the end of the day with nothing said about why.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


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
