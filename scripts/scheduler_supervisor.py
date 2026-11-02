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


def dispatch(workflow: str) -> tuple[bool, str]:
    proc = subprocess.run(["gh", "workflow", "run", workflow], capture_output=True,
                          text=True, cwd=ROOT, timeout=120)
    if proc.returncode == 0:
        return True, "dispatched"
    return False, (proc.stderr or proc.stdout or "gh workflow run failed").strip()[:200]


def supervise(now: datetime | None = None, runs=None, dry_run: bool = False,
              state: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    state = load_state() if state is None else state
    result = {"dispatched": [], "skipped": [], "failed": []}

    try:
        missing = due_but_missing(now, runs)
    except Exception as exc:  # noqa: BLE001
        result["failed"].append({"workflow": "-", "reason": f"cannot read schedule: {exc}"})
        return result

    for workflow, slot in missing:
        key = f"{workflow}@{slot}"
        if key in state:
            result["skipped"].append({"workflow": workflow, "slot": slot,
                                      "reason": "already dispatched for this slot"})
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
        state[key] = {"at": now.isoformat(), "result": message}
        (result["dispatched"] if ok else result["failed"]).append(
            {"workflow": workflow, "slot": slot, "result": message})

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
        if not any(result[key] for key in ("dispatched", "skipped", "failed")):
            print("[supervisor] every scheduled workflow has run for its current slot")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and (result["dispatched"] or result["failed"]):
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### 🔁 Schedule supervisor\n\n")
            for row in result["dispatched"]:
                fh.write(f"- dispatched `{row['workflow']}` for the {row['slot']} slot\n")
            for row in result["failed"]:
                fh.write(f"- **could not dispatch** `{row['workflow']}`: "
                         f"{row.get('reason') or row.get('result')}\n")
            fh.write("\n")

    return 1 if result["failed"] else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
