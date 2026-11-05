"""The supervisor exists because a dropped schedule cannot report itself.

On 2 November the brain's 03:14 slot, keepalive's 03:23 slot and produce's 06:14
slot all came and went with no run. Every workflow was green; nothing had run.
These tests pin that a missing slot is *dispatched*, and that the dispatcher cannot
loop, duplicate, or fire on a workflow that is simply late.
"""
from __future__ import annotations

import unittest
import unittest.mock
from unittest import mock
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


def pad_history(history, now):
    """Give every scheduled workflow absent from `history` a recent healthy run.

    These tests pin the supervisor's logic for the specific workflows they set up.
    When a new scheduled workflow is added to the repo (e.g. growth-autopilot.yml),
    it must not silently become an extra due-but-missing candidate and break an
    exact-set assertion. Padding keeps each test focused on its intended workflows
    while staying correct as the workflow roster grows.
    """
    from scripts.automation_monitor import workflow_files
    present = {(r.get("path") or "").split("/")[-1] for r in history}
    padded = list(history)
    for wf, _n, _c in workflow_files():
        if wf not in present:
            padded.append(run(wf, now - timedelta(minutes=30)))
    return padded


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
        found = {wf for wf, _ in sup.due_but_missing(now, pad_history(history, now))}
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
        self.assertEqual(sup.due_but_missing(early, pad_history(history, early)), [])

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
        out = sup.supervise(now, pad_history(history, now), dry_run=True, state=state)
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
        self.assertEqual(sup.MAX_ATTEMPTS_PER_SLOT, 3)

    def test_one_slot_is_dispatched_only_once(self):
        state = {}
        history = pad_history(self.runs(), self.now())
        first = sup.supervise(self.now(), history, dry_run=True, state=state)
        self.assertEqual(len(first["dispatched"]), 3)
        # a real pass writes the ledger; simulate that then re-run the same slot
        for row in first["dispatched"]:
            state[f"{row['workflow']}@{row['slot']}"] = {"at": "2099-01-01T00:00:00+00:00",
                                                        "attempts": sup.MAX_ATTEMPTS_PER_SLOT}
        second = sup.supervise(self.now(), history, dry_run=True, state=state)
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

    def test_it_also_rides_ci_because_ci_always_fires(self):
        """On 2 Nov CI started within seconds at 10:01 while this workflow's own
        push trigger and its 10:00/10:15 schedule slots produced nothing."""
        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        self.assertIn("Dry-run pipeline (CI proof)", text)

    def test_supervisor_can_actually_dispatch(self):
        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        self.assertIn("actions: write", text)

    def test_produce_recovery_dispatches_both_channels(self):
        """A dropped Produce slot now costs BOTH channels a video.

        Since 2026-11-05 a scheduled Produce run produces secret-place and
        prayer2, so the supervisor's recovery dispatch must fire one run
        per channel — a bare dispatch would silently recover only The
        Secret Place.
        """
        calls = []

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            return _Proc()

        with mock.patch.object(sup.subprocess, "run", side_effect=fake_run):
            ok, _msg = sup.dispatch("produce.yml")
        self.assertTrue(ok)
        self.assertEqual(
            calls,
            [["gh", "workflow", "run", "produce.yml", "-f", "channel=secret-place"],
             ["gh", "workflow", "run", "produce.yml", "-f", "channel=prayer2"]],
        )

    def test_non_produce_dispatch_is_unchanged(self):
        calls = []

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            return _Proc()

        with mock.patch.object(sup.subprocess, "run", side_effect=fake_run):
            ok, _msg = sup.dispatch("gemini_brain.yml")
        self.assertTrue(ok)
        self.assertEqual(calls, [["gh", "workflow", "run", "gemini_brain.yml"]])


class TestAWedgedRunIsNotAllowedToHoldTheLock(unittest.TestCase):
    """On 2 November a produce run sat in_progress 2h25m past its 120-minute cap.

    A dead runner does not enforce its own timeouts, so the run held the
    `content-state` lock forever: no other content writer could start, and the two
    watchers built to notice exactly that were themselves queued behind it.
    """

    def now(self):
        return datetime(2026, 11, 2, 18, 45, tzinfo=UTC)

    def test_a_run_past_its_cap_is_reported_stuck(self):
        # Just past JOB_CAP + STUCK_GRACE. It used to be 149 minutes, back when the
        # supervisor cancelled at 130 — which was shorter than the 170-minute step a
        # healthy render is allowed, so this test was encoding the bug.
        rows = [{"id": 99, "name": "Produce video", "status": "in_progress",
                 "run_started_at": "2026-11-02T14:30:00Z"}]
        stuck = sup.stuck_runs(self.now(), rows)
        self.assertEqual([r["id"] for r in stuck], [99])
        self.assertEqual(stuck[0]["minutes"], 255)

    def test_a_run_still_inside_its_cap_is_left_alone(self):
        # Three hours in: a slow-but-healthy release, exactly the one the old cap
        # killed at minute 167.
        rows = [{"id": 7, "name": "Produce video", "status": "in_progress",
                 "run_started_at": "2026-11-02T15:45:00Z"}]
        self.assertEqual(sup.stuck_runs(self.now(), rows), [])

    def test_a_finished_run_is_never_cancelled(self):
        rows = [{"id": 8, "name": "Produce video", "status": "completed",
                 "run_started_at": "2026-11-02T10:00:00Z"}]
        self.assertEqual(sup.stuck_runs(self.now(), rows), [])

    def test_the_supervisor_cancels_and_says_so(self):
        rows = [{"id": 99, "name": "Produce video", "status": "in_progress",
                 "run_started_at": "2026-11-02T16:15:34Z"}]
        calls = []
        with mock.patch.object(sup, "stuck_runs", return_value=[
                {"id": 99, "workflow": "Produce video",
                 "started": "2026-11-02T16:15:34+00:00", "minutes": 149}]), \
             mock.patch.object(sup, "cancel_run", side_effect=lambda i: (calls.append(i), (True, "cancelled"))[1]), \
             mock.patch.object(sup, "dispatch", return_value=(True, "dispatched")), \
             mock.patch.object(sup, "save_state"):
            result = sup.supervise(self.now(), runs=rows, state={})
        self.assertEqual(calls, [99])
        self.assertEqual(result["cancelled"][0]["result"], "cancelled")

    def test_a_dry_run_would_cancel_without_cancelling(self):
        with mock.patch.object(sup, "stuck_runs", return_value=[
                {"id": 99, "workflow": "Produce video", "started": "x", "minutes": 149}]), \
             mock.patch.object(sup, "cancel_run") as cancel, \
             mock.patch.object(sup, "dispatch", return_value=(True, "dispatched")):
            result = sup.supervise(self.now(), runs=[], state={}, dry_run=True)
        cancel.assert_not_called()
        self.assertEqual(result["cancelled"][0]["result"], "would cancel")

    def test_the_watchers_do_not_share_the_publish_lock(self):
        from pathlib import Path
        import yaml

        root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        for name in ("monitor.yml", "scheduler-supervisor.yml"):
            data = yaml.safe_load((root / name).read_text(encoding="utf-8"))
            self.assertNotEqual(data["concurrency"]["group"], "content-state", name)

    def test_an_external_tick_always_wakes_the_supervisor(self):
        """Every other trigger can be suppressed by the failure it watches for.

        Today's crons stopped firing at 18:05 UTC, and a wedged produce run never
        emits the `workflow_run` completion this supervisor reacts to — so it went
        silent exactly when a run was wedged.
        """
        from pathlib import Path
        import yaml

        root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        data = yaml.safe_load((root / "scheduler-supervisor.yml").read_text(encoding="utf-8"))
        self.assertIn("repository_dispatch", data[True])
        self.assertEqual(data[True]["repository_dispatch"]["types"], ["watchdog-tick"])

    def test_production_still_holds_one_lock_for_itself(self):
        from pathlib import Path
        import yaml

        root = Path(__file__).resolve().parents[1] / ".github" / "workflows"
        data = yaml.safe_load((root / "produce.yml").read_text(encoding="utf-8"))
        self.assertEqual(data["concurrency"]["group"], "content-state")


if __name__ == "__main__":
    unittest.main()
