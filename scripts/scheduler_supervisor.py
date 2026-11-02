"""Dispatch the workflows GitHub's scheduler drops.

The monitor compares when each workflow was last *edited* with when it last *ran*,
and that comparison is what exposed the real problem: the crons themselves are not
firing. On the morning of 2 November the brain's 03:14 slot and keepalive's 03:23
slot both came and went with no run, and nothing anywhere said so.

A dropped schedule cannot be reported by the thing that was dropped. So something
other than the scheduler has to notice. This supervisor runs every fifteen minutes,
compares each workflow's last run against its most recent scheduled slot, and
dispatches whatever was missed via `workflow_dispatch` — which works from inside
Actions with an `actions: write` token.

Safety rails, because a dispatcher that loops is worse than a dropped cron:

* only workflows that were **due and did not run** are dispatched, never on a hunch;
* a slot is dispatched at most once — the slot key is recorded in
  `content/monitor/dispatched.json` and the same slot is never tried twice;
* at most `MAX_DISPATCHES` workflows per pass, so a systemic outage cannot turn
  into a burst of runs;
* monitoring and supervising workflows are never dispatched by themselves.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE = ROOT / "content" / "monitor" / "dispatched.json"

# Dispatch a slot this long after it was due. GitHub's scheduler is routinely 10-40
# minutes late, so anything shorter races it and risks a *duplicate* run — which for
# produce.yml means a duplicate upload. Wider than the monitor's alarm (3h) is not
# needed; 90 minutes still catches a dropped slot the same morning.
DISPATCH_AFTER = timedelta(minutes=90)
# Never dispatch a slot older than this: by then the release window has passed and
# publishing late is worse than waiting for the next one.
DISPATCH_WINDOW = timedelta(hours=6)
MAX_DISPATCHES = 3
# A dispatch is not a success. On 2 November the 07:14 produce slot was
# dispatched at 08:59 and the run then failed; treating the slot as settled would
# have left the channel with no video until the next day.
#
# Three attempts, because a failed run is often a bug that has since been fixed:
# attempt one finds it, attempt two proves the fix, and the third covers a retry
# that failed for an unrelated reason. The cap still stops a permanently broken
# workflow from hammering the queue every fifteen minutes.
MAX_ATTEMPTS_PER_SLOT = 3

# A run whose runner has died holds the `content-state` lock forever, and a wedged
# run does not enforce its own timeouts: on 2 November a produce run sat
# `in_progress` for two and a half hours past both its 90-minute step cap and its
# 120-minute job cap. Everything else that writes content/ queued behind it,
# including this supervisor and the monitor — the watchers were stuck behind the
# thing they exist to catch. So the supervisor cancels them.
JOB_CAP = timedelta(minutes=120)
STUCK_GRACE = timedelta(minutes=10)

NEVER_DISPATCH = {"monitor.yml", "automation-health.yml", "scheduler-supervisor.yml",
                  "dry-run.yml", "preview-render.yml", "prayer-alignment-check.yml"}


def load_state() -> dict:
    if not STATE.is_file():
        return {}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def due_but_missing(now: datetime | None = None,
                    runs: list[dict] | None = None) -> list[tuple[str, str]]:
    """[(workflow_file, slot_iso)] for every slot that is due and produced no run.

    Deliberately computed from `workflow_files()` and the run list alone: calling
    `classify()` here would fetch each workflow's last-edit date over the API once
    per pass, and this has to stay cheap enough to run every fifteen minutes.
    """
    from scripts.automation_monitor import fetch_runs, prev_occurrence, workflow_files

    now = now or datetime.now(timezone.utc)
    if runs is None:
        runs = fetch_runs()

    latest: dict[str, datetime] = {}
    for run in runs:
        path = (run.get("path") or "").split("/")[-1]
        stamp = run.get("created_at")
        if not path or not stamp:
            continue
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if path not in latest or when > latest[path]:
            latest[path] = when

    out: list[tuple[str, str]] = []
    for filename, _name, crons in workflow_files():
        if filename in NEVER_DISPATCH:
            continue
        slot = prev_occurrence(crons, now)
        if slot is None:
            continue
        if now < slot + DISPATCH_AFTER or now > slot + DISPATCH_WINDOW:
            continue
        last_run = latest.get(filename)
        if last_run is not None and last_run >= slot:
            continue          # it ran for this slot; nothing to do
        out.append((filename, slot.isoformat()))
    return out


def _safe_runs() -> list[dict]:
    try:
        from scripts.automation_monitor import fetch_runs

        return fetch_runs()
    except Exception:  # noqa: BLE001
        return []


FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure"}


def _failed_dispatches(state: dict, latest: dict[str, tuple[datetime, str | None]],
                       now: datetime) -> list[tuple[str, str]]:
    """Ledger entries whose dispatched run has finished badly and can be retried."""
    out: list[tuple[str, str]] = []
    for key, entry in state.items():
        if "@" not in key:
            continue
        workflow, slot = key.rsplit("@", 1)
        if workflow in NEVER_DISPATCH:
            continue
        try:
            slot_at = datetime.fromisoformat(slot)
            dispatched_at = datetime.fromisoformat(entry.get("at", ""))
        except (TypeError, ValueError):
            continue
        if now < slot_at + DISPATCH_AFTER or now > slot_at + DISPATCH_WINDOW:
            continue
        if int(entry.get("attempts", 1)) >= MAX_ATTEMPTS_PER_SLOT:
            continue
        finished = latest.get(workflow)
        if finished is None:
            continue
        when, conclusion = finished
        if when < dispatched_at:
            continue                      # the dispatched run has not appeared yet
        if conclusion in FAILED_CONCLUSIONS:
            out.append((workflow, slot))
    return out


def _latest_runs(runs: list[dict]) -> dict[str, tuple[datetime, str | None]]:
    """{workflow_file: (created_at, conclusion)} for the newest run of each."""
    out: dict[str, tuple[datetime, str | None]] = {}
    for run in runs:
        path = (run.get("path") or "").split("/")[-1]
        stamp = run.get("created_at")
        if not path or not stamp:
            continue
        try:
            when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if path not in out or when > out[path][0]:
            out[path] = (when, run.get("conclusion"))
    return out


def dispatch(workflow: str) -> tuple[bool, str]:
    proc = subprocess.run(["gh", "workflow", "run", workflow], capture_output=True,
                          text=True, cwd=ROOT, timeout=120)
    if proc.returncode == 0:
        return True, "dispatched"
    return False, (proc.stderr or proc.stdout or "gh workflow run failed").strip()[:200]


def stuck_runs(now: datetime | None = None, runs=None) -> list[dict]:
    """Runs that are `in_progress` well past the cap their workflow declares.

    Only timed-out-by-wall-clock counts: a run that is genuinely working reports
    step progress, but GitHub's API does not expose that cheaply, so the test is
    the job cap plus a grace period. Ten minutes of grace is enough that a long
    step which is about to finish is not killed underneath itself.
    """
    now = now or datetime.now(timezone.utc)
    payload = runs if runs is not None else _safe_runs()
    rows = payload.get("workflow_runs", payload) if isinstance(payload, dict) else payload
    out = []
    for run in rows or []:
        if str(run.get("status")) != "in_progress":
            continue
        created = run.get("run_started_at") or run.get("created_at")
        if not created:
            continue
        try:
            started = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - started > JOB_CAP + STUCK_GRACE:
            out.append({
                "id": run.get("id"),
                "workflow": (run.get("name") or "").strip(),
                "started": started.isoformat(),
                "minutes": int((now - started).total_seconds() // 60),
            })
    return out


def cancel_run(run_id) -> tuple[bool, str]:
    from scripts.automation_monitor import repo_slug

    proc = subprocess.run(["gh", "api", "--method", "POST",
                           f"repos/{repo_slug()}/actions/runs/{run_id}/cancel"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)
    if proc.returncode == 0:
        return True, "cancelled"
    return False, (proc.stderr or proc.stdout or "cancel failed").strip()[:200]


def supervise(now: datetime | None = None, runs=None, dry_run: bool = False,
              state: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    state = load_state() if state is None else state
    result = {"dispatched": [], "skipped": [], "failed": [], "cancelled": []}

    try:
        missing = due_but_missing(now, runs)
    except Exception as exc:  # noqa: BLE001
        result["failed"].append({"workflow": "-", "reason": f"cannot read schedule: {exc}"})
        return result

    latest = _latest_runs(runs if runs is not None else _safe_runs())

    # Two kinds of work: slots that produced no run at all, and slots whose
    # *dispatched* run has since failed. The second kind looks healthy to
    # `due_but_missing` (a run exists after the slot) which is exactly how today's
    # produce failure would have been left for tomorrow.
    candidates = list(missing)
    for workflow, slot in _failed_dispatches(state, latest, now):
        if (workflow, slot) not in candidates:
            candidates.append((workflow, slot))

    # Say out loud what the ledger decided, so a slot that is deliberately not
    # retried is visible in the log instead of merely absent.
    for key, entry in state.items():
        if "@" not in key:
            continue
        workflow, slot = key.rsplit("@", 1)
        if (workflow, slot) in candidates:
            continue
        try:
            slot_at = datetime.fromisoformat(slot)
        except ValueError:
            continue
        if now < slot_at + DISPATCH_AFTER or now > slot_at + DISPATCH_WINDOW:
            continue
        attempts = int(entry.get("attempts", 1))
        finished = latest.get(workflow)
        if finished is not None and finished[1] == "success" \
                and finished[0].isoformat() >= entry.get("at", ""):
            reason = "its dispatched run succeeded"
        elif attempts >= MAX_ATTEMPTS_PER_SLOT:
            reason = f"already dispatched {attempts}x for this slot; not trying again"
        else:
            reason = "waiting for its dispatched run to appear"
        result["skipped"].append({"workflow": workflow, "slot": slot, "reason": reason})

    for workflow, slot in candidates:
        key = f"{workflow}@{slot}"
        previous = state.get(key)
        attempts = int(previous.get("attempts", 1)) if previous else 0
        if previous:
            finished = latest.get(workflow)
            if finished is not None and finished[1] == "success" \
                    and finished[0].isoformat() >= previous.get("at", ""):
                result["skipped"].append({"workflow": workflow, "slot": slot,
                                          "reason": "its dispatched run succeeded"})
                continue
            if attempts >= MAX_ATTEMPTS_PER_SLOT:
                result["skipped"].append({"workflow": workflow, "slot": slot,
                                          "reason": f"already dispatched {attempts}x for this "
                                                    f"slot; not trying again"})
                continue
        if len(result["dispatched"]) >= MAX_DISPATCHES:
            result["skipped"].append({"workflow": workflow, "slot": slot,
                                      "reason": "per-pass dispatch limit reached"})
            continue
        if dry_run:
            result["dispatched"].append({"workflow": workflow, "slot": slot,
                                         "result": "would dispatch"})
            continue
        ok, message = dispatch(workflow)
        state[key] = {"at": now.isoformat(), "result": message, "attempts": attempts + 1}
        (result["dispatched"] if ok else result["failed"]).append(
            {"workflow": workflow, "slot": slot, "result": message})

    # A wedged run holds the content-state lock, so nothing else that writes
    # content/ can start — including this pass, once it queues behind the very run
    # it should be cleaning up. Cancel first, dispatch second.
    try:
        for stuck in stuck_runs(now, runs):
            if dry_run:
                result["cancelled"].append({**stuck, "result": "would cancel"})
                continue
            ok, message = cancel_run(stuck["id"])
            result["cancelled"].append({**stuck, "result": message,
                                        "ok": ok})
            if not ok:
                result["failed"].append({"workflow": stuck["workflow"],
                                         "reason": f"could not cancel run {stuck['id']}: {message}"})
    except Exception as exc:  # noqa: BLE001 - never lose the dispatch pass over this
        result["failed"].append({"workflow": "-", "reason": f"stuck-run check failed: {exc}"})

    if not dry_run:
        save_state(state)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch scheduled workflows that never fired.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = supervise(dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result["dispatched"]:
            print(f"[supervisor] {row['workflow']}: {row['result']} (slot {row['slot']})")
        for row in result["skipped"]:
            print(f"[supervisor] skip {row['workflow']}: {row['reason']}")
        for row in result["failed"]:
            print(f"[supervisor] FAILED {row['workflow']}: {row.get('reason') or row.get('result')}")
        for row in result.get("cancelled", []):
            print(f"[supervisor] cancelled {row['workflow']} run {row['id']} "
                  f"(in progress {row['minutes']}m): {row['result']}")
        if not any(result[key] for key in ("dispatched", "skipped", "failed", "cancelled")):
            print("[supervisor] every scheduled workflow has run for its current slot")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and (result["dispatched"] or result["failed"] or result.get("cancelled")):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### 🔁 Schedule supervisor\n\n")
            for row in result["dispatched"]:
                fh.write(f"- dispatched `{row['workflow']}` for the {row['slot']} slot\n")
            for row in result.get("cancelled", []):
                fh.write(f"- cancelled `{row['workflow']}` run {row['id']}: "
                         f"in progress {row['minutes']} minutes with no result\n")
            for row in result["failed"]:
                fh.write(f"- **could not dispatch** `{row['workflow']}`: "
                         f"{row.get('reason') or row.get('result')}\n")
            fh.write("\n")

    return 1 if result["failed"] else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
