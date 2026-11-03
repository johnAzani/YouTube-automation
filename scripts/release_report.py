"""Turn a bad release into a report the automation itself can read.

The problem this solves is narrow and embarrassing: on 2 November three renders
died at a step cap, and nobody — human or agent — could find out where the time
went. `gh run view --log-failed` returns `failed to get run log … EOF` for these
runs, the log archive lives on a host this environment cannot reach, and the run
page is behind a GitHub sign-in. The single most useful artefact of a failure was
unreachable by every party who needed it.

So the run writes its own report as a GitHub issue, which *is* readable:

    python -m scripts.release_report --trail output/progress-trail.log \\
        --log run.log --issue

The issue names the stage it died in (the last `▶`), every stage that closed and
how long it took, and the tail of the job log. It opens one issue per failure and
adds a comment to the existing one when the same stage fails again — so a repeat
is visible as a repeat rather than as a new alarm every night.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: `[progress 20:09:10Z] ▶ encode — 6.0 min, 8 scenes`
PROGRESS_RE = re.compile(r"^(\d\d:\d\d:\d\d)Z\s+(.*)$")
#: What a stage line looks like once the marker is stripped.
OPEN, OK, FAIL = "▶", "✓", "✗"


def parse_trail(text: str) -> list[tuple[str, str, str]]:
    """[(stamp, marker, body)] for every progress line in `text`."""
    rows = []
    for line in text.splitlines():
        match = PROGRESS_RE.match(line.strip())
        if not match:
            continue
        stamp, body = match.groups()
        marker = body[:1]
        if marker not in (OPEN, OK, FAIL):
            continue
        rows.append((stamp, marker, body[1:].strip()))
    return rows


def _stage_name(body: str) -> str:
    """`encode — 6.0 min, 8 scenes` → `encode`."""
    return body.split(" — ")[0].split(" in ")[0].strip()


def summarise(rows: list[tuple[str, str, str]]) -> dict:
    """Where we were, what finished, and what each stage cost."""
    still_open: list[str] = []
    finished: list[dict] = []
    failure = None
    for stamp, marker, body in rows:
        name = _stage_name(body)
        if marker == OPEN:
            still_open = [n for n in still_open if n != name]
            still_open.append(name)
        elif marker == OK:
            still_open = [n for n in still_open if n != name]
            seconds = None
            match = re.search(r"in ([\d.]+)s$", body)
            if match:
                seconds = float(match.group(1))
            finished.append({"stage": name, "stamp": stamp, "seconds": seconds})
        elif marker == FAIL:
            still_open = [n for n in still_open if n != name]
            failure = {"stage": name, "stamp": stamp, "detail": body}
    return {"open": still_open, "finished": finished, "failure": failure,
            "last": rows[-1] if rows else None, "count": len(rows),
            "rows": rows}


def render(summary: dict, log_tail: str = "", run_id: str = "") -> tuple[str, str]:
    """(title, body) for the issue. Pure, so it can be tested exactly."""
    failure = summary["failure"]
    dying_in = summary["open"][-1] if summary["open"] else None
    if failure:
        title = f"Release failed in {failure['stage']}"
    elif dying_in:
        title = f"Release died inside {dying_in}"
    else:
        title = "Release failed"
    if run_id:
        title += f" (run {run_id})"

    lines = ["The long-form release did not finish. This is what it was doing.", ""]
    if run_id:
        lines.append(f"- Run: https://github.com/johnAzani/YouTube-automation/actions/runs/{run_id}")
    if failure:
        lines.append(f"- **Failed stage:** `{failure['stage']}` at {failure['stamp']}Z")
        lines.append(f"- Reported: `{failure['detail']}`")
    if dying_in:
        lines.append(f"- **Never closed:** `{dying_in}` — the step ran out of time here, "
                     "so this stage is where the minutes went.")
    finished = [row for row in summary["finished"] if row.get("seconds") is not None]
    if finished:
        lines += ["", "| stage | finished at | took |", "| --- | --- | --- |"]
        for row in finished:
            lines.append(f"| `{row['stage']}` | {row['stamp']}Z | {row['seconds']:.0f}s |")
        total = sum(row["seconds"] for row in finished)
        lines.append(f"| **accounted for** | | **{total / 60:.1f} min** |")
    rows = summary.get("rows") or []
    moments = [f"{stamp}Z {marker} {body}" for stamp, marker, body in rows
               if not STALL_RE.search(body)]
    if moments:
        lines += ["", "### Last progress lines", "```", *moments[-10:], "```"]
    if not summary["finished"] and dying_in:
        lines += ["", f"Not one stage finished. `{dying_in}` was the only thing that "
                      "opened, and it never closed."]
    if not summary["count"]:
        lines += ["", "_No progress lines were written — the failure happened before the "
                      "first stage opened (checkout, deps, or the script itself)._"]
    if log_tail.strip():
        lines += ["", "### End of the job log", "```",
                  collapse_repeats(log_tail.strip())[-4000:], "```"]
    lines += ["", "_Filed automatically by `scripts/release_report.py`; the trail comes from "
                  "`pipeline/progress.py`, which writes it as the release runs._"]
    return title, "\n".join(lines)


#: `[progress 03:00:25Z] … still inside speech synthesis — 888 words, Charon after 82.0 min`
STALL_RE = re.compile(r"still inside (.+?) after ([\d.]+) min")


def collapse_repeats(text: str) -> str:
    """One line per stalled stage, not one per report.

    Issue #216 carried 85 identical "still inside speech synthesis after N min"
    lines and nothing else — the tail was all heartbeat, so the report hid the
    only fact that mattered behind its own noise. Consecutive stall notices for
    the same stage become a single line spanning the first and last.
    """
    out: list[str] = []
    run_stage = None
    run_first = run_last = 0.0
    run_count = 0

    def flush() -> None:
        nonlocal run_stage, run_count
        if run_stage is None:
            return
        if run_count == 1:
            out.append(f"... still inside {run_stage} after {run_first:.0f} min")
        else:
            out.append(f"... still inside {run_stage} for {run_count} reports, "
                       f"{run_first:.0f} → {run_last:.0f} min")
        run_stage, run_count = None, 0

    for line in text.splitlines():
        match = STALL_RE.search(line)
        if match:
            stage, minutes = match.group(1), float(match.group(2))
            if stage != run_stage:
                flush()
                run_stage, run_first = stage, minutes
            run_last = minutes
            run_count += 1
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def _tail(path: Path, lines: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def file_issue(title: str, body: str, repo: str) -> str:
    """Open it, or comment on the open one the same title already made."""
    existing = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--search", title.split(" (run ")[0] + " in:title", "--json", "number", "--limit", "5"],
        capture_output=True, text=True, check=False,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        try:
            numbers = [row["number"] for row in json.loads(existing.stdout)]
        except (ValueError, KeyError, TypeError):
            numbers = []
        if numbers:
            subprocess.run(["gh", "issue", "comment", str(numbers[0]), "--repo", repo,
                            "--body", body], check=False)
            return f"commented on #{numbers[0]}"
    created = subprocess.run(
        ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body],
        capture_output=True, text=True, check=False,
    )
    if created.returncode != 0:
        print(f"[release-report] could not file an issue: {created.stderr.strip()}",
              file=sys.stderr)
        return ""
    return created.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report where a release died.")
    parser.add_argument("--trail", default=os.environ.get("PROGRESS_TRAIL", ""))
    parser.add_argument("--log", default="run.log")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY",
                                                         "johnAzani/YouTube-automation"))
    parser.add_argument("--issue", action="store_true",
                        help="file (or comment on) a GitHub issue")
    args = parser.parse_args(argv)

    trail_text = ""
    if args.trail and Path(args.trail).is_file():
        trail_text = Path(args.trail).read_text(encoding="utf-8", errors="replace")
    summary = summarise(parse_trail(trail_text))
    title, body = render(summary, _tail(Path(args.log), 60), args.run_id)
    print(title)
    print(body)
    if args.issue:
        where = file_issue(title, body, args.repo)
        if where:
            print(f"[release-report] {where}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
