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
import shutil
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


def is_quota_cooldown_only(summary: dict, log_tail: str) -> bool:
    """True when the log shows a clean $0.00 daily free-tier TTS quota pause rather than a crash."""
    if summary.get("open") or summary.get("failure"):
        return False
    low = (log_tail or "").lower()
    return (
        "free-tier tts allowance (10 requests/day) is spent until" in low
        or ("gemini quota is exhausted;" in low and "is paused until" in low)
    )


def _published_public_index(
    published_dir: Path | None = None,
) -> tuple[set[str], set[str], dict[str, str]]:
    """Return `(public_titles, public_video_ids, canonical_vid_by_title)` from `content/published/`."""
    import yaml

    pdir = published_dir or (REPO / "content" / "published")
    titles: set[str] = set()
    video_ids: set[str] = set()
    canonical_by_title: dict[str, str] = {}
    if not pdir.is_dir():
        return titles, video_ids, canonical_by_title
    for md in pdir.glob("*.md"):
        try:
            raw = md.read_text(encoding="utf-8")
            if not raw.startswith("---"):
                continue
            meta = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except Exception:  # noqa: BLE001
            continue
        vid = str(meta.get("youtube_video_id") or "").strip()
        status = str(meta.get("status") or "").strip().lower()
        privacy = str(meta.get("privacy") or meta.get("privacy_status") or "").strip().lower()
        title = str(meta.get("title") or "").strip()
        if status == "published" and vid and title:
            canonical_by_title[title] = vid
        if status == "published" and privacy == "public" and vid:
            video_ids.add(vid)
            if title:
                titles.add(title)
                titles.add(title.split("|")[0].strip())
    return titles, video_ids, canonical_by_title


def _published_public_titles(published_dir: Path | None = None) -> set[str]:
    return _published_public_index(published_dir)[0]


def sweep_stale_release_issues(repo: str, published_dir: Path | None = None) -> list[int]:
    """Close non-failure quota-pause `Release failed` issues and resolved/superseded `Release ticket:` issues."""
    if not shutil.which("gh"):
        return []
    found = subprocess.run(
        [
            "gh", "issue", "list", "--repo", repo, "--state", "open",
            "--search", '"Release " in:title',
            "--json", "number,title,body", "--limit", "50",
        ],
        capture_output=True, text=True, check=False,
    )
    if found.returncode != 0:
        return []
    try:
        rows = json.loads(found.stdout or "[]")
    except (ValueError, TypeError):
        return []

    public_titles, public_vids, canonical_by_title = _published_public_index(published_dir)
    closed: list[int] = []
    for row in rows:
        num = int(row.get("number", 0) or 0)
        title = str(row.get("title") or "")
        body = str(row.get("body") or "")
        if not num:
            continue
        comment = ""
        if title.startswith("Release failed") and is_quota_cooldown_only({}, body):
            comment = (
                "Closing automatically: this run paused cleanly on the daily $0.00 "
                "free-tier TTS quota limit (not a pipeline failure)."
            )
        elif title.startswith("Release ticket:"):
            video_title = title[len("Release ticket:") :].strip()
            title_head = video_title.split("|")[0].strip()
            vid_matches = re.findall(r"(?:youtu\.be/|watch\?v=|/video/)([A-Za-z0-9_-]{11})", body)
            canonical_vid = canonical_by_title.get(video_title, "")
            if (
                (video_title and video_title in public_titles)
                or (title_head and title_head in public_titles)
                or any(v in public_vids for v in vid_matches)
            ):
                comment = (
                    "Closing automatically: this video is already `published` and `public` "
                    "in `content/published/`."
                )
            elif canonical_vid and vid_matches and all(v != canonical_vid for v in vid_matches):
                comment = (
                    f"Closing automatically: this draft upload was superseded by canonical upload "
                    f"`{canonical_vid}` in `content/published/`."
                )
        if comment:
            res = subprocess.run(
                ["gh", "issue", "close", str(num), "--repo", repo, "--comment", comment],
                capture_output=True, text=True, check=False,
            )
            if res.returncode == 0:
                closed.append(num)

    # Also keep only the single newest open `📊 Channel Analytics Snapshot` issue per
    # channel prefix so weekly snapshots do not accumulate indefinitely (#78, #248, ...).
    snap = subprocess.run(
        [
            "gh", "issue", "list", "--repo", repo, "--state", "open",
            "--search", '"Channel Analytics Snapshot" in:title',
            "--json", "number,title", "--limit", "50",
        ],
        capture_output=True, text=True, check=False,
    )
    if snap.returncode == 0:
        try:
            snap_rows = json.loads(snap.stdout or "[]")
        except (ValueError, TypeError):
            snap_rows = []
        by_group: dict[str, list[int]] = {}
        for row in snap_rows:
            num = int(row.get("number", 0) or 0)
            t = str(row.get("title") or "")
            if not num or "Channel Analytics Snapshot" not in t:
                continue
            group = t.split(":", 1)[0].strip()
            by_group.setdefault(group, []).append(num)
        for group, nums in by_group.items():
            ordered = sorted(nums, reverse=True)
            newest = ordered[0]
            for stale_num in ordered[1:]:
                res = subprocess.run(
                    [
                        "gh", "issue", "close", str(stale_num), "--repo", repo,
                        "--comment",
                        f"Closing automatically: superseded by newer analytics snapshot #{newest}.",
                    ],
                    capture_output=True, text=True, check=False,
                )
                if res.returncode == 0:
                    closed.append(stale_num)
    return closed


def close_resolved_issues(repo: str, run_id: str = "") -> list[int]:
    """Close open `Release failed...` / `Release died inside...` issues after a green release."""
    if not shutil.which("gh"):
        return []
    closed = sweep_stale_release_issues(repo)
    found = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "open",
         "--search", '"Release " in:title',
         "--json", "number,title", "--limit", "50"],
        capture_output=True, text=True, check=False,
    )
    if found.returncode != 0:
        return closed
    try:
        rows = json.loads(found.stdout or "[]")
        numbers = [
            int(r["number"]) for r in rows
            if str(r.get("title", "")).startswith(("Release failed", "Release died inside"))
            and int(r["number"]) not in closed
        ]
    except (ValueError, KeyError, TypeError):
        return closed
    note = (
        f"Resolved automatically: a subsequent Production Release succeeded"
        + (f" (run `{run_id}`)." if run_id else ".")
    )
    for num in numbers:
        res = subprocess.run(
            ["gh", "issue", "close", str(num), "--repo", repo, "--comment", note],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0:
            closed.append(num)
    return closed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report where a release died.")
    parser.add_argument("--trail", default=os.environ.get("PROGRESS_TRAIL", ""))
    parser.add_argument("--log", default="run.log")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", ""))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY",
                                                         "johnAzani/YouTube-automation"))
    parser.add_argument("--issue", action="store_true",
                        help="file (or comment on) a GitHub issue")
    parser.add_argument("--close-resolved", action="store_true",
                        help="close open Production Release failed issues after a successful release")
    parser.add_argument("--sweep-stale", action="store_true",
                        help="close non-failure quota-pause issues and already-public release tickets")
    args = parser.parse_args(argv)

    if args.sweep_stale:
        swept = sweep_stale_release_issues(args.repo)
        if swept:
            print(f"[release-report] swept stale release issues: {swept}")
        return 0

    if args.close_resolved:
        closed = close_resolved_issues(args.repo, args.run_id)
        if closed:
            print(f"[release-report] closed resolved failure issues: {closed}")
        return 0

    trail_text = ""
    if args.trail and Path(args.trail).is_file():
        trail_text = Path(args.trail).read_text(encoding="utf-8", errors="replace")
    summary = summarise(parse_trail(trail_text))
    log_tail = _tail(Path(args.log), 60)
    title, body = render(summary, log_tail, args.run_id)
    print(title)
    print(body)
    if args.issue:
        if is_quota_cooldown_only(summary, log_tail):
            print("[release-report] daily free-tier TTS quota pause; skipping issue creation")
            return 0
        where = file_issue(title, body, args.repo)
        if where:
            print(f"[release-report] {where}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
