"""A watcher must not be woken by the watcher it wakes.

6 November, 09:42-09:54Z: `monitor.yml` ran on "Scheduler supervisor" completing and
`scheduler-supervisor.yml` runs on "Automation monitor" completing. Each finished run
started the other — 40+ runs alternating roughly once a minute, each writing a commit
and auditing the channel. The brain run dispatched at 09:34Z sat `queued` for over an
hour behind them, and the release slot never got a runner.

The fix is one-directional: the monitor may wake the supervisor, never the reverse.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(doc: dict) -> dict:
    return doc.get(True) or doc.get("on") or {}


def _woken_by(name: str) -> list[str]:
    run = _triggers(_workflow(name)).get("workflow_run") or {}
    return list(run.get("workflows") or [])


class TestWatchersDoNotPingPong(unittest.TestCase):
    def test_the_monitor_is_not_woken_by_the_supervisor(self):
        self.assertNotIn("Scheduler supervisor", _woken_by("monitor.yml"))

    def test_the_supervisor_may_be_woken_by_the_monitor(self):
        """One direction is the point: a stall the monitor found must reach the fixer."""
        self.assertIn("Automation monitor", _woken_by("scheduler-supervisor.yml"))

    def test_the_monitor_refuses_a_chain_of_runs(self):
        guard = _workflow("monitor.yml")["jobs"]["monitor"].get("if") or ""
        self.assertIn("workflow_run.event != 'workflow_run'", guard,
                      "a run started by a run must not start another run")

    def test_no_workflow_lists_itself(self):
        for path in WORKFLOWS.glob("*.yml"):
            doc = _workflow(path.name)
            name = (doc.get("name") or "").strip()
            if name:
                self.assertNotIn(name, _woken_by(path.name),
                                 f"{path.name} would run on its own completion")


if __name__ == "__main__":
    unittest.main()


class TestUpstreamOutagesKeepRetrying(unittest.TestCase):
    """An outage that ends by itself must not cost the whole day.

    6 November: gemini-3.8-flash returned `503 UNAVAILABLE — high demand` from 09:16Z
    through 10:30Z. The attempts were spent, the code fingerprint had not changed
    (nothing was wrong with it), so the slot would have gone unserved until 03:14Z
    the next morning even after Google recovered.
    """

    @property
    def sup(self):
        from scripts import scheduler_supervisor

        return scheduler_supervisor

    def _entry(self, *, result: str, minutes_ago: int, attempts: int = 3):
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
        entry = {"at": (now - timedelta(minutes=minutes_ago)).isoformat(),
                 "result": result, "attempts": attempts}
        return self.sup, entry, now

    def test_a_503_keeps_its_slot_retryable_after_a_cooldown(self):
        sup, entry, now = self._entry(result="service unavailable: 503 UNAVAILABLE",
                                      minutes_ago=45)
        self.assertTrue(sup.is_upstream_failure(entry))
        self.assertTrue(sup.upstream_retry_due(entry, now))

    def test_it_does_not_retry_before_the_cooldown(self):
        sup, entry, now = self._entry(result="503 UNAVAILABLE high demand", minutes_ago=5)
        self.assertFalse(sup.upstream_retry_due(entry, now))

    def test_a_code_failure_is_not_retried_as_an_outage(self):
        sup, entry, now = self._entry(result="BrainAuthoringError: mislabelled scripture",
                                      minutes_ago=120)
        self.assertFalse(sup.is_upstream_failure(entry))
        self.assertFalse(sup.upstream_retry_due(entry, now))

    def test_an_endless_outage_stops_hammering(self):
        sup, entry, now = self._entry(result="503 UNAVAILABLE", minutes_ago=45,
                                      attempts=self.sup.UPSTREAM_MAX_ATTEMPTS)
        self.assertFalse(sup.upstream_retry_due(entry, now))


class TestAnUnprovenFixIsNotRecovery(unittest.TestCase):
    """The monitor closed the stall issue at 10:37Z with the brain still 503-ing.

    Every merge turned the brain's red FAILING verdict into an amber UNTESTED FIX —
    "a fix is deployed and has never run green" — and `Report.healthy` only looked at
    fatal findings, so amber was silent and the issue closed itself. Today that
    closed the ticket while nothing had published since 5 November.
    """

    def test_a_warning_keeps_the_pipeline_unhealthy(self):
        from scripts.pipeline_watchdog import Report

        report = Report()
        report.add("automations", "gemini_brain.yml: UNTESTED FIX — a fix is deployed",
                   fatal=False, warning=True)
        self.assertFalse(report.healthy)

    def test_info_does_not(self):
        from scripts.pipeline_watchdog import Report

        report = Report()
        report.add("automations", "produce.yml: QUOTA WAIT — resets at 08:00Z",
                   fatal=False)
        self.assertTrue(report.healthy, "a documented wait is not a fault")

    def test_the_monitor_warning_becomes_a_warning_finding(self):
        import inspect

        from scripts import pipeline_watchdog

        source = inspect.getsource(pipeline_watchdog.check_automations)
        self.assertIn('warning=automation.severity == "warning"', source)
