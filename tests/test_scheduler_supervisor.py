"""The supervisor exists because a dropped schedule cannot report itself.

On 2 November the brain's 03:14 slot, keepalive's 03:23 slot and produce's 06:14
slot all came and went with no run. Every workflow was green; nothing had run.
These tests pin that a missing slot is *dispatched*, and that the dispatcher cannot
loop, duplicate, or fire on a workflow that is simply late.
"""
from __future__ import annotations

import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone

from scripts import scheduler_supervisor as sup

UTC = timezone.utc


def run(workflow, when, status="completed", conclusion="success"):
    """One run, shaped the way `fetch_runs()` returns it (flat, with `path`)."""
    return {"name": workflow, "path": f".github/workflows/{workflow}",
            "created_at": when.isoformat().replace("+00:00", "Z"),
            "status": status, "conclusion": conclusion}


def runs(*spec):
    return [run(wf, when) for wf, when in spec]


def healthy(now):
    """Every workflow ran half an hour ago: the baseline a quiet system looks like."""
    from scripts.automation_monitor import workflow_files
    return [run(wf, now - timedelta(minutes=30)) for wf, _n, _c in workflow_files()]


class TestSlotDetection(unittest.TestCase):
    def now(self):
        return datetime(2026, 11, 2, 8, 0, tzinfo=UTC)

    def test_a_missed_slot_is_dispatched(self):
        now = self.now()
        history = runs(("gemini_brain.yml", now - timedelta(days=1)))
        missing = sup.due_but_missing(now, history)
        self.assertIn(("gemini_brain.yml", "2026-11-02T03:14:00+00:00"), missing)

    def test_the_morning_that_started_all_this_finds_three_workflows(self):
        """2 Nov: brain 03:14, keepalive 03:23 and produce 06:14 all silently dropped."""
        now = self.now()
        history = runs(
            ("gemini_brain.yml", now - timedelta(hours=21)),
            ("keepalive.yml", now - timedelta(days=6)),
            ("produce.yml", now - timedelta(hours=9)),
            ("comments.yml", now - timedelta(hours=9)),
        )
        found = {wf for wf, _ in sup.due_but_missing(now, history)}
        self.assertEqual(found, {"gemini_brain.yml", "keepalive.yml", "produce.yml"})

    def test_a_workflow_that_ran_for_the_slot_is_left_alone(self):
        now = self.now()
        # every workflow ran 30 min ago, including the brain's 03:14 slot
        found = {wf for wf, _ in sup.due_but_missing(now, healthy(now))}
        self.assertEqual(found, set())

    def test_a_merely_late_schedule_is_not_duplicated(self):
        """A slot under 90 minutes old may still be queued; do not race it."""
        now = self.now()
        history = runs(("gemini_brain.yml", now - timedelta(days=1)),
                       ("comments.yml", now - timedelta(days=1)))
        early = datetime(2026, 11, 2, 4, 0, tzinfo=UTC)    # 46 min after 03:14
        self.assertEqual(sup.due_but_missing(early, history), [])

    def test_comments_due_at_0714_is_not_raced_mid_morning(self):
        """The exact false positive this threshold was widened to prevent."""
        now = self.now()
        history = runs(("comments.yml", now - timedelta(hours=9)))
        found = {wf for wf, _ in sup.due_but_missing(now, history)}
        self.assertNotIn("comments.yml", found)

    def test_a_slot_too_old_to_be_useful_is_not_dispatched(self):
        now = self.now()
        history = runs(("gemini_brain.yml", now - timedelta(days=3)))
        late = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)    # 10h after the slot
        self.assertEqual(sup.due_but_missing(late, history), [])

    def test_supervisor_workflows_never_dispatch_themselves(self):
        now = self.now()
        history = healthy(now) + [run(w, now - timedelta(days=2)) for w in sup.NEVER_DISPATCH]
        self.assertEqual([wf for wf, _ in sup.due_but_missing(now, history)], [])

    def test_a_workflow_whose_runs_are_absent_for_the_slot_is_still_caught(self):
        """Empty run history must not read as "nothing to do"."""
        now = self.now()
        found = {wf for wf, _ in sup.due_but_missing(now, [])}
        self.assertIn("gemini_brain.yml", found)


class TestDispatchRails(unittest.TestCase):
    def now(self):
        return datetime(2026, 11, 2, 8, 0, tzinfo=UTC)

    def runs(self):
        now = self.now()
        return runs(
            ("gemini_brain.yml", now - timedelta(hours=21)),
            ("keepalive.yml", now - timedelta(days=6)),
            ("produce.yml", now - timedelta(hours=9)),
            ("comments.yml", now - timedelta(hours=9)),
        )

    def test_a_failed_dispatch_is_retried_once(self):
        """2 Nov: produce's 07:14 slot was dispatched at 08:59 and the run failed."""
        now = self.now()
        history = self.runs() + [run("produce.yml", now - timedelta(minutes=20),
                                     conclusion="failure")]
        state = {"produce.yml@2026-11-02T06:14:00+00:00": {"at": "2026-11-02T07:00:00+00:00",
                                                          "attempts": 1}}
        out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertIn("produce.yml", [r["workflow"] for r in out["dispatched"]])

    def test_a_successful_dispatch_is_never_repeated(self):
        now = self.now()
        history = self.runs() + [run("produce.yml", now - timedelta(minutes=20))]
        state = {"produce.yml@2026-11-02T06:14:00+00:00": {"at": "2026-11-02T07:00:00+00:00",
                                                          "attempts": 1}}
        out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertNotIn("produce.yml", [r["workflow"] for r in out["dispatched"]])
        self.assertTrue(any("succeeded" in r["reason"] for r in out["skipped"]))

    def test_a_permanently_failing_slot_stops_being_retried(self):
        now = self.now()
        history = self.runs() + [run("produce.yml", now - timedelta(minutes=20),
                                     conclusion="failure")]
        state = {"produce.yml@2026-11-02T06:14:00+00:00": {"at": "2026-11-02T07:00:00+00:00",
                                                          "attempts": sup.MAX_ATTEMPTS_PER_SLOT}}
        out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertNotIn("produce.yml", [r["workflow"] for r in out["dispatched"]])
        self.assertTrue(any("not trying again" in r["reason"] for r in out["skipped"]))

    def test_one_slot_is_dispatched_only_once(self):
        state = {}
        first = sup.supervise(self.now(), self.runs(), dry_run=True, state=state)
        self.assertEqual(len(first["dispatched"]), 3)
        # a real pass writes the ledger; simulate that then re-run the same slot
        for row in first["dispatched"]:
            state[f"{row['workflow']}@{row['slot']}"] = {"at": "2099-01-01T00:00:00+00:00",
                                                        "attempts": sup.MAX_ATTEMPTS_PER_SLOT}
        second = sup.supervise(self.now(), self.runs(), dry_run=True, state=state)
        self.assertEqual(second["dispatched"], [])
        self.assertTrue(all(r["reason"].startswith("already dispatched")
                            for r in second["skipped"]))

    def test_a_systemic_outage_cannot_cause_a_burst(self):
        now = self.now()
        history = [run(w, now - timedelta(days=3)) for w in
                   ("comments.yml", "community.yml", "produce.yml", "gemini_brain.yml",
                    "keepalive.yml")]
        self.assertGreaterEqual(len(sup.due_but_missing(now, history)), 3)
        with unittest.mock.patch.object(sup, "MAX_DISPATCHES", 1):
            out = sup.supervise(now, history, dry_run=True, state={})
        self.assertEqual(len(out["dispatched"]), 1)
        self.assertTrue(any("limit" in r["reason"] for r in out["skipped"]))

    def test_unreadable_schedule_is_a_failure_not_a_silent_pass(self):
        from unittest import mock
        with mock.patch.object(sup, "due_but_missing", side_effect=RuntimeError("gh down")):
            out = sup.supervise(self.now(), runs=[], dry_run=True, state={})
        self.assertEqual(out["dispatched"], [])
        self.assertEqual(len(out["failed"]), 1)
        self.assertIn("gh down", out["failed"][0]["reason"])

    def test_the_ledger_is_not_written_on_a_dry_run(self):
        from unittest import mock
        with mock.patch.object(sup, "save_state") as save:
            sup.supervise(self.now(), self.runs(), dry_run=True, state={})
        save.assert_not_called()


class TestWorkflowFile(unittest.TestCase):
    def test_supervisor_runs_often_enough_to_catch_a_slot_the_same_morning(self):
        from scripts.automation_monitor import cron_gap
        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        self.assertIn('cron: "*/15 * * * *"', text)
        self.assertGreater(cron_gap(["*/15 * * * *"]), timedelta(0))

    def test_supervisor_does_not_depend_only_on_a_schedule(self):
        """The scheduler is the thing that fails; the fallback must not be it."""
        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        self.assertIn("push:", text)
        self.assertIn("workflow_run:", text)
        for name in ("Produce video", "Keepalive", "Automation monitor"):
            self.assertIn(name, text)

    def test_supervisor_can_actually_dispatch(self):
        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        self.assertIn("actions: write", text)


if __name__ == "__main__":
    unittest.main()
