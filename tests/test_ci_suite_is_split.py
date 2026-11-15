"""The unit tests must be quick on GitHub, and `main` must be tested daily.

Two things are held here.

**1. The suite is split across the runner's processors.** On 15 November 2026
the suite (about 1,980 tests) took 19 to 26 minutes in one process on GitHub's
runners (runs 43737911292, 43740479521, 43740476661) under a 35-minute limit,
and a job cancelled at its limit shows on a pull request as a failed check with
nothing to read. Split, it takes about 4 minutes. The split has two rules that
make it safe: a test that fails while split is run again alone before the job
fails, and that second run can never quietly turn into "run nothing and pass".

**2. `main` is tested once a day.** Queue, publish and monitor commits carry
`[skip ci]`, and several tests read what those commits change. On 15 November
The Provision Table had 14 planned passages left against a floor of 15 and
`main` failed its own tests unseen; it was found only because an unrelated pull
request failed (PR #444). `tests-on-main.yml` runs the same command on a
schedule, which puts it under the automation monitor: a failed run is reported
in the watchdog's tracking issue.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
SCRIPT = ROOT / "scripts" / "ci_unit_tests.sh"
COMMAND = "bash scripts/ci_unit_tests.sh"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(name: str) -> dict:
    doc = _workflow(name)
    return doc.get("on") or doc.get(True) or {}      # PyYAML reads `on:` as True


def _unit_test_step(job: dict) -> str:
    step = [s for s in job["steps"] if s.get("name") == "Unit tests"]
    assert len(step) == 1, "the job must have exactly one 'Unit tests' step"
    return step[0]["run"]


def _script_code() -> str:
    return "\n".join(line for line in SCRIPT.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def _lines_running_pytest() -> list[str]:
    return [line.strip() for line in _script_code().splitlines()
            if line.strip().startswith("python -m pytest")]


class TheSuiteIsSplitAcrossProcessors(unittest.TestCase):
    def test_the_first_run_uses_every_processor(self):
        self.assertIn("-n auto", _lines_running_pytest()[0])

    def test_a_file_stays_in_one_process(self):
        # Tests in one file share module-level state and files on disk. Spreading
        # them over processes would change their order and their neighbours.
        self.assertIn("--dist loadfile", _lines_running_pytest()[0])

    def test_the_pull_request_job_runs_the_shared_command(self):
        run = _unit_test_step(_workflow("dry-run.yml")["jobs"]["checks"])
        self.assertIn("pytest-xdist", run, "the tool that splits the suite is not installed")
        self.assertIn(COMMAND, run)
        self.assertNotIn("python -m pytest", run,
                         "a second copy of the test command would drift from the shared one")

    def test_the_limit_still_fits_a_run_in_one_process(self):
        self.assertGreaterEqual(_workflow("dry-run.yml")["jobs"]["checks"]["timeout-minutes"], 30)


class AFailureWhileSplitIsCheckedAlone(unittest.TestCase):
    def test_there_is_a_second_run_of_only_the_failed_tests(self):
        runs = _lines_running_pytest()
        self.assertEqual(len(runs), 2, runs)
        self.assertIn("--last-failed", runs[1])
        self.assertNotIn("-n ", runs[1], "the second run must be one process")

    def test_the_second_run_cannot_pass_by_running_nothing(self):
        # When no failure was recorded, plain `--last-failed` runs the whole
        # suite again in one process (another 20 minutes). With `none` pytest
        # runs nothing and exits non-zero, so the job fails and says so.
        self.assertIn("--last-failed-no-failures none", _lines_running_pytest()[1])

    def test_only_the_tests_failed_code_gets_a_second_run(self):
        self.assertIn('if [ "$rc" -eq 1 ]; then', _script_code())

    def test_a_test_that_passes_only_alone_is_named(self):
        code = _script_code()
        self.assertIn("::warning title=Tests passed only when run alone::", code)
        self.assertIn("${split_failures", code)

    def test_a_real_failure_still_fails_the_job(self):
        code = _script_code()
        self.assertIn("::error title=Unit test failure::", code)
        self.assertIn('exit "$rc"', code)
        # The verdict is taken after the second run, so its exit code decides.
        self.assertLess(code.index("--last-failed"), code.index('exit "$rc"'))

    def test_no_failure_is_swallowed(self):
        code = _script_code()
        self.assertNotIn("|| true", code)
        self.assertNotIn("exit 0", code)


class MainIsTestedEveryDay(unittest.TestCase):
    NAME = "tests-on-main.yml"

    def _job(self) -> dict:
        return _workflow(self.NAME)["jobs"]["tests"]

    def test_it_has_a_daily_schedule(self):
        crons = [row["cron"] for row in _triggers(self.NAME)["schedule"]]
        self.assertEqual(len(crons), 1, crons)
        minute, hour, dom, month, dow = crons[0].split()
        self.assertTrue(minute.isdigit() and hour.isdigit(), crons[0])
        self.assertEqual((dom, month, dow), ("*", "*", "*"), "not every day")

    def test_the_merge_that_fixes_a_failure_clears_it(self):
        self.assertEqual(_triggers(self.NAME)["push"]["branches"], ["main"])

    def test_it_never_runs_on_a_session_branch(self):
        # The monitor reads every run of a scheduled workflow, whatever branch it
        # ran on. A run on a branch with a failing test would be reported to the
        # owner as "main is failing".
        triggers = _triggers(self.NAME)
        self.assertNotIn("pull_request", triggers)
        self.assertNotIn("arena/", str(triggers))

    def test_the_supervisor_can_start_it_when_the_schedule_is_late(self):
        from scripts import scheduler_supervisor

        self.assertIn("workflow_dispatch", _triggers(self.NAME))
        self.assertNotIn(self.NAME, scheduler_supervisor.NEVER_DISPATCH)

    def test_it_runs_the_same_command_as_a_pull_request(self):
        run = _unit_test_step(self._job())
        self.assertIn("pytest-xdist", run)
        self.assertIn(COMMAND, run)
        self.assertNotIn("python -m pytest", run)

    def test_it_prepares_the_runner_as_a_pull_request_does(self):
        def uses(job: dict) -> list[str]:
            return [s["uses"] for s in job["steps"] if "uses" in s]

        self.assertEqual(uses(self._job()),
                         uses(_workflow("dry-run.yml")["jobs"]["checks"]))

    def test_a_failure_is_a_red_run(self):
        # The monitor's verdict is the run's conclusion. A step allowed to fail
        # would leave the run green and the monitor satisfied.
        job = self._job()
        self.assertIsNone(job.get("continue-on-error"))
        for step in job["steps"]:
            self.assertIsNone(step.get("continue-on-error"), step.get("name"))
        self.assertNotIn("|| true", _unit_test_step(job))

    def test_it_holds_no_secret_and_cannot_write(self):
        text = (WORKFLOWS / self.NAME).read_text(encoding="utf-8")
        self.assertNotIn("secrets.", text)
        self.assertEqual(_workflow(self.NAME)["permissions"], {"contents": "read"})

    def test_it_has_a_time_limit(self):
        self.assertLessEqual(self._job()["timeout-minutes"], 35)
        self.assertGreaterEqual(self._job()["timeout-minutes"], 30)


class AFailureOnMainReachesTheOwner(unittest.TestCase):
    """The workflow files no issue itself: the monitor's verdict does that."""

    NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)      # 7h after the slot

    def _verdict(self, runs):
        from scripts import automation_monitor as am

        mine = [f for f in am.workflow_files() if f[0] == "tests-on-main.yml"]
        self.assertEqual(len(mine), 1, "the monitor does not see the workflow's schedule")
        long_ago = self.NOW - timedelta(days=4)
        with mock.patch.object(am, "workflow_files", return_value=mine), \
             mock.patch.object(am, "first_commit_for", return_value=long_ago), \
             mock.patch.object(am, "last_edit", return_value=long_ago), \
             mock.patch.object(am, "active_quota_cooldown", return_value=None):
            report = am.classify(am.MonitorReport(), runs, now=self.NOW)
        return report.automations[0]

    def _run(self, hours_ago: float, conclusion: str = "success") -> dict:
        stamp = (self.NOW - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z")
        return {"path": ".github/workflows/tests-on-main.yml", "created_at": stamp,
                "conclusion": conclusion, "status": "completed"}

    def test_a_failed_run_is_a_blocking_finding(self):
        row = self._verdict([self._run(7, "failure"), self._run(31)])
        self.assertEqual((row.verdict, row.severity), ("FAILING", "blocking"))

    def test_a_passing_run_after_it_clears_the_finding(self):
        row = self._verdict([self._run(1), self._run(7, "failure")])
        self.assertEqual((row.verdict, row.severity), ("OK", "ok"))

    def test_a_day_without_a_run_is_reported_too(self):
        row = self._verdict([self._run(31)])
        self.assertEqual((row.verdict, row.severity), ("MISSED SLOT", "blocking"))

    def test_the_report_says_what_the_workflow_is_for(self):
        from scripts import automation_monitor as am

        self.assertIn("main", am.EFFECTS["tests-on-main.yml"])


if __name__ == "__main__":
    unittest.main()
