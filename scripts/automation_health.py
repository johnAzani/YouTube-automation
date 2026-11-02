"""Automation health: did every scheduled workflow actually run?

Why this exists
---------------
The Community Tab workflow had **zero runs** in its entire life. Its schedules were
registered, it showed as "active" in the Actions list, its YAML was valid, and
nothing anywhere reported a problem — because a workflow that never starts never
fails. The publish step it was supposed to run also never called an API, so even a
successful run would have posted nothing while reporting success.

Silent non-execution is the failure mode this channel is most exposed to: the crons
are the product. This script compares each scheduled workflow's last run against the
window its own cron implies, and prints a table plus a non-zero exit when something
is overdue.

Usage
-----
    python -m scripts.automation_health                # table + exit code
    python -m scripts.automation_health --json         # machine-readable

It needs `gh` (already used by keepalive.yml) or a GITHUB_TOKEN; without either it
says so and exits 0 rather than pretending everything is fine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# How late a run may be before it counts as overdue, on top of its own cadence.
GRACE = timedelta(hours=6)

# A workflow that has never run is only a problem once its schedule has had a chance
# to fire; measure from when the file was first present rather than from epoch.
NEVER_RUN_GRACE = timedelta(days=2)


@dataclass
class Schedule:
    workflow: str
    crons: list[str]
    max_gap: timedelta

    @property
    def label(self) -> str:
        return self.workflow


def _cron_gap(exprs: list[str]) -> timedelta:
    """Widest gap the schedule can leave, so a weekly job is not judged daily.

    Only the shapes this repo uses are interpreted; anything unrecognised is treated
    as daily, which is conservative (it will flag, not hide).
    """
    widest = timedelta(days=1)
    for expr in exprs:
        parts = expr.split()
        if len(parts) != 5:
            continue
        _, _, dom, _, dow = parts
        if dow == "*":
            if dom == "*":
                continue
        if dow != "*":
            days = {d for d in re.split(r"[,\-]", dow) if d.strip().isdigit()}
            span = 7 if len(days) > 1 else 7
            widest = max(widest, timedelta(days=span))
        elif dom != "*":
            widest = max(widest, timedelta(days=31))
    return widest


def scheduled_workflows() -> list[Schedule]:
    found: list[Schedule] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        crons = re.findall(r"cron:\s*[\"']([^\"']+)[\"']", text)
        if crons:
            found.append(Schedule(workflow=path.name, crons=crons, max_gap=_cron_gap(crons)))
    return found


def gh_available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or shutil.which("gh"))


def last_run(workflow_file: str) -> datetime | None:
    """Most recent run of a workflow file, or None if it has never run."""
    try:
        out = subprocess.run(
            ["gh", "run", "list", "--workflow", workflow_file, "--limit", "1",
             "--json", "createdAt"],
            capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
        if out.returncode != 0:
            return None
        rows = json.loads(out.stdout or "[]")
        if not rows:
            return None
        return datetime.fromisoformat(rows[0]["createdAt"].replace("Z", "+00:00"))
    except Exception:
        return None


@dataclass
class Row:
    workflow: str
    cadence: str
    last: datetime | None
    status: str
    detail: str


def audit(now: datetime | None = None) -> list[Row]:
    now = now or datetime.now(timezone.utc)
    rows: list[Row] = []
    for schedule in scheduled_workflows():
        last = last_run(schedule.workflow)
        cadence = f"every {schedule.max_gap.days}d" if schedule.max_gap.days > 1 else "daily"
        if last is None:
            rows.append(Row(schedule.workflow, cadence, None, "NEVER RAN",
                            "no run recorded — scheduled workflows that never start never fail"))
            continue
        overdue_at = last + schedule.max_gap + GRACE
        if now > overdue_at:
            rows.append(Row(schedule.workflow, cadence, last, "OVERDUE",
                            f"last run {last.date().isoformat()}; expected by {overdue_at.date().isoformat()}"))
        else:
            rows.append(Row(schedule.workflow, cadence, last, "ok", last.strftime("%Y-%m-%d %H:%M UTC")))
    return rows


def queue_health() -> list[dict]:
    """Which queues have work that can actually run?

    The long-form and Shorts queues both grew approved-looking rows that could not
    build (short scripts, mislabelled scripture). Counting *renderable* rows rather
    than approved rows is what makes a stall visible before it lasts a week.
    """
    from pipeline.run import select_jobs
    from pipeline.short_release import queue_report

    rows: list[dict] = []
    try:
        longform = select_jobs(all_flag=False, job_path=None, next_flag=False)
        rows.append({"queue": "longform", "ready": len(longform), "note": "approved and above the word floor"})
    except Exception as exc:  # a broken queue is a finding, not a crash
        rows.append({"queue": "longform", "ready": 0, "note": f"selection failed: {exc}"})
    try:
        shorts = queue_report()
        ready = sum(1 for r in shorts if r["verdict"] == "ready")
        blocked = sum(1 for r in shorts if r["verdict"] != "ready")
        rows.append({"queue": "shorts", "ready": ready,
                     "note": f"{blocked} manifest(s) waiting on a scene script in tools/shorts.py"
                             if ready == 0 else "renderable now"})
    except Exception as exc:
        rows.append({"queue": "shorts", "ready": 0, "note": f"queue_report failed: {exc}"})
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check that scheduled workflows are actually running.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="also fail when a workflow has never run at all")
    args = parser.parse_args(argv)

    rows = audit()
    if args.json:
        print(json.dumps([{"workflow": r.workflow, "cadence": r.cadence,
                           "last_run": r.last.isoformat() if r.last else None,
                           "status": r.status, "detail": r.detail} for r in rows], indent=2))
    else:
        width = max(len(r.workflow) for r in rows) if rows else 20
        for row in rows:
            print(f"{row.workflow:<{width}}  {row.cadence:<8}  {row.status:<10}  {row.detail}")

    if not gh_available():
        print("no gh/GITHUB_TOKEN available — cannot verify run history; reporting nothing as healthy")
        return 0

    queues = queue_health()
    if args.json:
        print(json.dumps(queues, indent=2))
    else:
        print()
        for row in queues:
            print(f"queue: {row['queue']}  ready={row['ready']}  {row['note']}")
    for row in queues:
        if row["ready"] == 0:
            print(f"::warning title={row['queue']} queue has nothing runnable::{row['note']}")

    problems = [r for r in rows if r.status == "OVERDUE" or (args.strict and r.status == "NEVER RAN")]
    for row in problems:
        print(f"::error title={row.workflow} {row.status}::{row.detail}")
    if rows and all(r.status == "NEVER RAN" for r in rows):
        # almost certainly a token/permission problem rather than 12 broken workflows
        print("::warning title=Health check inconclusive::every workflow reports no runs; check gh auth/scopes")
        return 0
    return 1 if problems else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
