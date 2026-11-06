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
