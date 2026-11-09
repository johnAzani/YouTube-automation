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


def two_channel_world():
    """Pin the supervisor's channel list to the 2 November fixture.

    These tests model the morning of 2 November, when two channels existed. The
    live registry has three now, and a test that silently changes what it asserts
    when a channel is added stops pinning anything. The wiring — that the
    supervisor's list *is* the scheduled-channel list — is pinned separately, in
    `test_the_supervisor_watches_every_scheduled_channel`.
    """
    return mock.patch.object(sup, "_channels", return_value=("secret-place", "prayer2"))


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
        # Produce is judged by receipts now: no channel has published for this slot.
        with mock.patch.object(sup, "published_channels_since", return_value=set()):
            found = {wf for wf, _ in sup.due_but_missing(now, pad_history(history, now))}
        self.assertEqual(found, {"gemini_brain.yml", "keepalive.yml", "produce.yml"})

    def test_a_produce_run_is_not_evidence_that_a_channel_published(self):
        """The half-recovery that started this: one leg's success certified both.

        At 08:00 on 6 November the supervisor dispatched both channels, GitHub
        cancelled the first one while it was still pending, and the pass recorded
        "dispatched secret-place + prayer2". A *successful* produce run is not a
        published video either, so the slot stays open until receipts say otherwise.
        """
        now = self.now()
        history = pad_history(
            [run("produce.yml", now - timedelta(hours=1, minutes=30))], now
        )
        with two_channel_world(), \
             mock.patch.object(sup, "published_channels_since",
                               return_value={"secret-place"}):
            found = {wf for wf, _ in sup.due_but_missing(now, history)}
        self.assertIn("produce.yml", found, "prayer2 still has no video for this slot")

        with two_channel_world(), \
             mock.patch.object(sup, "published_channels_since",
                               return_value={"secret-place", "prayer2"}):
            found = {wf for wf, _ in sup.due_but_missing(now, history)}
        self.assertNotIn("produce.yml", found)

    def test_a_produce_run_in_flight_is_never_raced(self):
        now = self.now()
        history = pad_history([], now) + [
            {"name": "Produce video", "path": ".github/workflows/produce.yml",
             "created_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
             "status": "in_progress", "conclusion": None}]
        with mock.patch.object(sup, "published_channels_since", return_value=set()):
            found = {wf for wf, _ in sup.due_but_missing(now, history)}
        self.assertNotIn("produce.yml", found)

    def test_a_workflow_that_ran_for_the_slot_is_left_alone(self):
        now = self.now()
        # every workflow ran 30 min ago, including the brain's 03:14 slot
        with two_channel_world():
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

    def test_a_daily_slot_stays_recoverable_until_its_successor_is_due(self):
        """10 hours late is *normal* here, so it must still be recovered.

        Measured over 1-6 November: this repo's brain slot (03:14) is delivered at
        ~10:53 — 7h39m late — almost every day. The old flat 6-hour window threw
        exactly those deliveries away, so a night when the scheduler delivered
        nothing had no recovery path at all (5-6 November: nothing ran 02:52-07:52).
        """
        now = self.now()
        history = runs(("gemini_brain.yml", now - timedelta(days=3)))
        late = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)    # 10h after the 03:14 slot
        found = {wf for wf, _ in sup.due_but_missing(late, pad_history(history, late))}
        self.assertIn("gemini_brain.yml", found)

    def test_a_weekly_slot_older_than_a_day_is_not_dispatched(self):
        """A weekly slot keeps a one-day leash — the MAX_SLOT_WINDOW cap."""
        # metrics.yml is weekly (Fri 18:41). Two days after the slot, its window is
        # over: the next Friday is the right time to run it, not now.
        now = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)     # Wed, 37h after Fri 18:41
        history = runs(("metrics.yml", datetime(2026, 10, 23, 18, 41, tzinfo=UTC)))
        found = {wf for wf, _ in sup.due_but_missing(now, pad_history(history, now))}
        self.assertNotIn("metrics.yml", found)

    def test_publishing_keeps_a_tighter_leash_than_authoring(self):
        """A video hours late is worse than no video: produce stays at 6 hours."""
        now = self.now()
        history = runs(("produce.yml", now - timedelta(days=2)))
        late = datetime(2026, 11, 2, 14, 0, tzinfo=UTC)    # 06:14 slot, 7h46m old
        found = {wf for wf, _ in sup.due_but_missing(late, pad_history(history, late))}
        self.assertNotIn("produce.yml", found)

    def test_only_the_newest_missed_slot_is_dispatched_per_workflow(self):
        """Catching up must publish once, not once per missed slot."""
        now = self.now()
        rows = sup._newest_per_workflow([
            ("produce.yml", "2026-11-01T19:14:00+00:00"),
            ("produce.yml", "2026-11-02T06:14:00+00:00"),
            ("gemini_brain.yml", "2026-11-02T03:14:00+00:00"),
        ])
        self.assertEqual(rows, [("gemini_brain.yml", "2026-11-02T03:14:00+00:00"),
                                ("produce.yml", "2026-11-02T06:14:00+00:00")])

    def test_supervisor_workflows_never_dispatch_themselves(self):
        now = self.now()
        history = healthy(now) + [run(w, now - timedelta(days=2)) for w in sup.NEVER_DISPATCH]
        with two_channel_world():
            self.assertEqual([wf for wf, _ in sup.due_but_missing(now, history)], [])

    def test_a_workflow_whose_runs_are_absent_for_the_slot_is_still_caught(self):
        """Empty run history must not read as "nothing to do"."""
        now = self.now()
        found = {wf for wf, _ in sup.due_but_missing(now, [])}
        self.assertIn("gemini_brain.yml", found)


class TestTheChannelListIsNotMaintainedByHand(unittest.TestCase):
    def test_the_supervisor_watches_every_scheduled_channel(self):
        """One source of truth: the registry's live channels, in registry order.

        The tests above pin produce's logic against a fixed two-channel fixture so
        that adding a channel does not quietly rewrite what they assert. This is
        the other half of that bargain: the supervisor's list really is the live
        one — when The Midday Watch was provisioned on 2026-11-07 it joined here
        with no second place to remember.
        """
        from pipeline.channels import scheduled_channels

        self.assertEqual(tuple(sup._channels()), tuple(scheduled_channels()))
        self.assertIn("prayer3", sup._channels())


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
        with two_channel_world():
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertNotIn("produce.yml", [r["workflow"] for r in out["dispatched"]])
        self.assertTrue(any("succeeded" in r["reason"] for r in out["skipped"]))

    def test_a_permanently_failing_slot_stops_being_retried(self):
        """No code change since the failure -> the budget holds."""
        now = self.now()
        history = self.runs() + [run("produce.yml", now - timedelta(minutes=20),
                                     conclusion="failure")]
        state = {"produce.yml@2026-11-02T06:14:00+00:00":
                 {"at": "2026-11-02T07:00:00+00:00",
                  "attempts": sup._attempt_cap("produce.yml")}}
        with two_channel_world(), \
             mock.patch.object(sup, "published_channels_since", return_value=set()), \
             mock.patch.object(sup, "code_changed_since", return_value=False):
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertNotIn("produce.yml", [r["workflow"] for r in out["dispatched"]])
        self.assertTrue(any("not trying again" in r["reason"] for r in out["skipped"]))
        # Produce gets one attempt per channel (plus a retry each), everything else 3.
        self.assertEqual(sup.MAX_ATTEMPTS_PER_SLOT, 3)
        with two_channel_world():
            self.assertEqual(sup._attempt_cap("produce.yml"), 5)
        # …and the cap follows the channel count: three channels means 7, not a
        # number that silently keeps the two-channel budget forever.
        self.assertEqual(sup._attempt_cap("produce.yml"), 2 * len(sup._channels()) + 1)

    def test_one_slot_is_dispatched_only_once(self):
        state = {}
        history = pad_history(self.runs(), self.now())
        with two_channel_world(), \
             mock.patch.object(sup, "published_channels_since", return_value=set()):
            first = sup.supervise(self.now(), history, dry_run=True, state=state)
        self.assertEqual(len(first["dispatched"]), 3)
        # a real pass writes the ledger; simulate that then re-run the same slot
        for row in first["dispatched"]:
            state[f"{row['workflow']}@{row['slot']}"] = {
                "at": "2099-01-01T00:00:00+00:00",
                # the cap this workflow actually has: produce's is per channel
                "attempts": sup._attempt_cap(row["workflow"]),
                # a real pass stamps the code it dispatched, so nothing was fixed since
                "code_id": sup.code_fingerprint(row["workflow"]),
            }
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

    def test_a_fix_gets_a_fresh_budget(self):
        """A retired model burned the brain's three attempts; the fix must still run.

        On 6 November the brain failed three times against `gemini-2.5-flash`, the
        model fix merged at 08:30, and the ledger would have refused to run it again
        until the next day's slot — the fix locked out by the failures it fixes.
        """
        now = self.now()
        state = {"gemini_brain.yml@2026-11-02T03:14:00+00:00":
                 {"at": "2026-11-02T07:00:00+00:00",
                  "attempts": sup.MAX_ATTEMPTS_PER_SLOT}}
        history = pad_history(self.runs(), now)
        with mock.patch.object(sup, "code_changed_since", return_value=True):
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertIn("gemini_brain.yml", [r["workflow"] for r in out["dispatched"]])

    def test_the_fingerprint_ignores_monitor_commits(self):
        """Only code counts. Actions rewrites content/monitor every few hours.

        If those renewals counted, a genuinely broken workflow would retry forever
        with nothing having been fixed — the loop guard would be gone.
        """
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "job.py").write_text("print('v1')\n")
            (root / "content" / "monitor").mkdir(parents=True)
            (root / "content" / "monitor" / "schedule-health.json").write_text("{}")
            with mock.patch.object(sup, "ROOT", root):
                first = sup.code_fingerprint("x.yml", _cache={})
                (root / "content" / "monitor" / "schedule-health.json").write_text(
                    '{"updated": "later"}')
                self.assertEqual(first, sup.code_fingerprint("x.yml", _cache={}),
                                 "content is not code")
                (root / "scripts" / "job.py").write_text("print('v2')\n")
                self.assertNotEqual(first, sup.code_fingerprint("x.yml", _cache={}),
                                    "a code change must renew the budget")

    def test_an_attempt_without_a_fingerprint_is_renewed_once(self):
        head = sup.code_fingerprint("gemini_brain.yml")
        entry = {"at": "2026-11-02T07:00:00+00:00", "attempts": 3}
        self.assertTrue(sup.code_changed_since(entry, "gemini_brain.yml"))
        entry["code_id"] = head          # the renewal stamps what it ran
        self.assertFalse(sup.code_changed_since(entry, "gemini_brain.yml"))
        entry["code_id"] = "0000000000000000"
        self.assertTrue(sup.code_changed_since(entry, "gemini_brain.yml"))

    def test_a_failed_dispatch_is_retried_once_the_code_changes(self):
        """The retry path has its own cap, and it must honour a fix too.

        `due_but_missing` treats "a run exists after the slot" as served, so retries
        of *failed* dispatched runs come from `_failed_dispatches`. Renewing only in
        the other path left the brain locked out after three failures against the
        retired model — the fix merged at 08:30 and nothing would have used it.
        """
        now = self.now()
        history = pad_history(
            [run("gemini_brain.yml", now - timedelta(minutes=25), conclusion="failure")],
            now,
        )
        state = {"gemini_brain.yml@2026-11-02T03:14:00+00:00":
                 {"at": "2026-11-02T07:00:00+00:00", "attempts": 3}}
        with mock.patch.object(sup, "code_changed_since", return_value=True), \
             mock.patch.object(sup, "published_channels_since", return_value=set()):
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertIn("gemini_brain.yml", [r["workflow"] for r in out["dispatched"]])

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


class TestScheduleHealth(unittest.TestCase):
    """Silence is a property of the repo, so it must be measurable and reportable."""

    def now(self):
        return datetime(2026, 11, 6, 7, 52, tzinfo=UTC)

    def history(self, now):
        """Something ran at 02:49; then nothing. The 5-6 November night, exactly."""
        return [run("scheduler-supervisor.yml", datetime(2026, 11, 6, 2, 49, tzinfo=UTC)),
                run("comments.yml", datetime(2026, 11, 6, 0, 16, tzinfo=UTC))]

    def test_silence_is_measured_across_every_workflow(self):
        health = sup.schedule_health(self.now(), self.history(self.now))
        self.assertEqual(health["silence_minutes"], 303)   # 02:49 -> 07:52
        self.assertEqual(health["last_run_at"], "2026-11-06T02:49:00+00:00")

    def test_a_five_hour_stall_is_an_error_annotation(self):
        health = sup.schedule_health(self.now(), self.history(self.now))
        with mock.patch("builtins.print") as printed:
            sup.report_schedule_health(health)
        out = " ".join(str(c) for c in printed.call_args_list)
        self.assertIn("::error", out)
        self.assertIn("Schedule stalled", out)

    def test_a_normal_gap_is_not_an_alarm(self):
        now = self.now()
        health = sup.schedule_health(now, [run("comments.yml", now - timedelta(minutes=20))])
        with mock.patch("builtins.print") as printed:
            sup.report_schedule_health(health)
        out = " ".join(str(c) for c in printed.call_args_list)
        self.assertNotIn("::error", out)
        self.assertNotIn("::warning", out)

    def test_a_late_delivery_is_recorded_with_its_lateness(self):
        """The brain serves its 03:14 slot at 10:53 here. That is a fact worth keeping."""
        now = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
        rows = pad_history(
            [run("gemini_brain.yml", datetime(2026, 11, 5, 10, 53, tzinfo=UTC))], now
        )
        health = sup.schedule_health(now, rows)
        brain = [r for r in health["delivered_late"] if r["workflow"] == "gemini_brain.yml"]
        self.assertEqual(len(brain), 1)
        self.assertEqual(brain[0]["late_minutes"], 459)     # 03:14 -> 10:53
        self.assertEqual(brain[0]["slot"], "2026-11-05T03:14:00+00:00")

    def test_a_real_pass_leaves_the_measurement_behind(self):
        now = self.now()
        # A "real" pass in the sense that matters here: the ledger and the health
        # snapshot are written. Both writes are redirected — this test must never
        # touch content/monitor/ (it did once, and overwrote the dispatch ledger) and
        # must never call `gh workflow run` for real.
        with mock.patch.object(sup, "save_schedule_health") as saved, \
             mock.patch.object(sup, "save_state") as ledger, \
             mock.patch.object(sup, "dispatch", return_value=(True, "dispatched")):
            sup.supervise(now, self.history(now), dry_run=False, state={})
        saved.assert_called_once()
        ledger.assert_called_once()
        self.assertEqual(saved.call_args[0][0]["silence_minutes"], 303)

    def test_the_watchdog_files_a_stalled_schedule(self):
        from scripts import pipeline_watchdog as wd

        with mock.patch.object(sup, "schedule_health",
                               return_value={"silence_minutes": 303,
                                             "last_run_at": "2026-11-06T02:49:00+00:00",
                                             "delivered_late": []}):
            report = wd.Report()
            wd.check_schedule_health(report, now=self.now())
        self.assertFalse(report.healthy)
        self.assertTrue(any("nothing has run" in f.detail for f in report.findings))


class TestWorkflowFile(unittest.TestCase):
    def test_supervisor_asks_for_slots_the_scheduler_can_actually_deliver(self):
        """`*/15` was an illusion: 96 cron events a day, ~4 runs delivered.

        Workflows with a handful of crons get every one of them (comments 3/3,
        produce 3/3, brain 1/1, growth 1/1 over the same period); the supervisor's
        96 asked for far more than the scheduler hands out and got thinned and
        shifted at random. Eight spread-out slots are the honest request, and each
        one recovers whatever is overdue.
        """
        import re

        from scripts.automation_monitor import cron_gap

        text = (sup.ROOT / ".github/workflows/scheduler-supervisor.yml").read_text()
        crons = re.findall(r'cron:\s*["\']([^"\']+)["\']', text)
        self.assertTrue(crons, "the supervisor must still run on a schedule")
        self.assertFalse([c for c in crons if c.startswith("*/")],
                         f"no high-frequency cron: {crons}")
        hours: list[int] = []
        for expr in crons:
            hours.extend(int(h) for h in expr.split()[1].split(",") if h.isdigit())
        hours.sort()
        self.assertGreaterEqual(len(hours), 6, "spread the passes across the day")
        # Never more than three hours between passes, wrapping midnight.
        gaps = [(b - a) for a, b in zip(hours, hours[1:])] + [24 - hours[-1] + hours[0]]
        self.assertLessEqual(max(gaps), 3, f"passes at {hours}")
        self.assertTrue(cron_gap(crons) > timedelta(0))

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

    def test_produce_recovery_targets_the_channel_that_has_no_video(self):
        """A dropped Produce slot costs BOTH channels a video — recover them one at a time.

        Not both at once: the two legs share `content-state`, which allows a single
        *pending* run, so the second dispatch cancels the first (6 November 08:00).
        """
        calls = []

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            return _Proc()

        with two_channel_world(), \
             mock.patch.object(sup, "_channel_has_supply", return_value=True), \
             mock.patch("scripts.automation_monitor.active_quota_cooldown", return_value=None), \
             mock.patch.object(sup.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(sup, "published_channels_since", return_value={"secret-place"}):
            ok, msg = sup.dispatch("produce.yml", "2026-11-06T06:14:00+00:00")
        self.assertTrue(ok)
        self.assertEqual(calls, [["gh", "workflow", "run", "produce.yml",
                                  "-f", "channel=prayer2"]])
        self.assertIn("dispatched prayer2", msg)

    def test_produce_recovery_dispatches_nothing_when_both_channels_published(self):
        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        with two_channel_world(), \
             mock.patch.object(sup.subprocess, "run") as proc, \
             mock.patch.object(sup, "published_channels_since",
                               return_value={"secret-place", "prayer2"}):
            ok, msg = sup.dispatch("produce.yml", "2026-11-06T06:14:00+00:00")
        self.assertTrue(ok)
        proc.assert_not_called()
        self.assertIn("already published", msg)

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
             mock.patch.object(sup, "save_schedule_health"), \
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

    def test_a_just_dispatched_slot_is_not_duplicated_within_spawn_grace(self):
        """7 Nov 16:33 -> 16:38 race: while a newly dispatched run is spawning or in flight, never double-dispatch."""
        now = datetime(2026, 11, 7, 16, 34, 20, tzinfo=UTC)
        slot = "2026-11-07T14:14:00+00:00"
        history = pad_history(
            [run("produce.yml", now - timedelta(hours=5))],
            now,
        )
        state = {
            f"produce.yml@{slot}": {
                "at": (now - timedelta(seconds=24)).isoformat(),
                "attempts": 1,
                "code_id": sup.code_fingerprint("produce.yml"),
                "attempted_channels": ["prayer3"],
            }
        }
        with mock.patch.object(sup, "published_channels_since", return_value={"secret-place", "prayer2"}):
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertEqual(out["dispatched"], [])
        self.assertTrue(any("waiting for its dispatched run" in r["reason"] for r in out["skipped"]))

    def test_an_inflight_run_blocks_failed_dispatch_retry_too(self):
        now = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
        history = pad_history(
            [
                run("produce.yml", now - timedelta(minutes=30), conclusion="failure"),
                run("produce.yml", now - timedelta(minutes=2), status="queued", conclusion=None),
            ],
            now,
        )
        state = {"produce.yml@2026-11-02T06:14:00+00:00": {"at": "2026-11-02T07:00:00+00:00", "attempts": 1}}
        with mock.patch.object(sup, "published_channels_since", return_value={"secret-place"}):
            out = sup.supervise(now, history, dry_run=True, state=state)
        self.assertNotIn("produce.yml", [r["workflow"] for r in out["dispatched"]])



if __name__ == "__main__":
    unittest.main()
