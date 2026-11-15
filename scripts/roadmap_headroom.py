"""Say so before a channel runs short of planned passages.

Each channel has a roadmap in `scripts/continuous_research.py`: the Bible
passages planned for its future long-form prayers. A passage is used up when
its job id appears in `content/queue/` or `content/published/`, which happens
about once a day per channel (one long-form a day since 14 November 2026).

`tests/test_multi_channel_resilience.py` fails when any channel has fewer than
`FLOOR` passages left. That is a cliff with no warning: on 15 November 2026 The
Provision Table was at 14 and `main` had been failing its own tests unseen
(PR #444). The daily test run (`tests-on-main.yml`) now reports that the day it
happens. This reports it `WARN_DAYS` earlier, in one issue of its own.

Why an issue of its own, and not a finding in the stall issue: a warning there
makes the watchdog unhealthy, which turns the monitor's runs red and holds the
stall issue open for as long as the warning lasts. A week of that for a list
that is merely getting short would bury a real stall.

    python -m scripts.roadmap_headroom               # print the table
    python -m scripts.roadmap_headroom --sync-issue  # and open/update/close the issue

A wrong count is a bug and exits non-zero. An issue that cannot be delivered is
said in a warning and exits zero: the table above it is still the report.
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
sys.path.insert(0, str(ROOT))

#: Fewer passages left than this fails the unit tests (the test imports it).
FLOOR = 15
#: Start saying so this many days before the floor is crossed.
WARN_DAYS = 7
#: Design rate: one long-form per channel per day.
USED_PER_DAY = 1

ISSUE_TITLE = "📖 Planned passages are running low"
#: The counts the open issue was last written with, so an unchanged table is not
#: written again and a channel newly on the list gets a comment (an email).
_MARKER = re.compile(r"<!-- roadmap-headroom: (.*?) -->")


@dataclass(frozen=True)
class Row:
    channel: str
    name: str
    planned: int
    left: int

    @property
    def low(self) -> bool:
        return self.left <= FLOOR + WARN_DAYS * USED_PER_DAY

    @property
    def below_floor(self) -> bool:
        return self.left < FLOOR

    @property
    def days_until_tests_fail(self) -> int:
        """Days of use until fewer than `FLOOR` are left; 0 when already there."""
        return max(0, -(-(self.left - FLOOR + 1) // USED_PER_DAY))


def used_ids(queue_dir: Path | None = None, published_dir: Path | None = None) -> set[str]:
    """Job ids already written or published: the same rule as the unit test."""
    queue = Path(queue_dir or ROOT / "content" / "queue")
    published = Path(published_dir or ROOT / "content" / "published")
    return ({p.name[:4] for p in queue.glob("[0-9]*.md")}
            | {p.name[:4] for p in published.glob("[0-9]*.md")})


def headroom(queue_dir: Path | None = None, published_dir: Path | None = None,
             channels: tuple[str, ...] | None = None, roadmap_for=None) -> list[Row]:
    from pipeline.channel_capabilities import brand_for
    from pipeline.channels import scheduled_channels
    from scripts.continuous_research import roadmap_for_channel

    roadmap_for = roadmap_for or roadmap_for_channel
    used = used_ids(queue_dir, published_dir)
    rows = []
    for cid in (channels if channels is not None else scheduled_channels()):
        roadmap = roadmap_for(cid)
        left = sum(1 for entry in roadmap if entry["id"] not in used)
        rows.append(Row(cid, brand_for(cid).display_name, len(roadmap), left))
    return rows


def _when(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).strftime("%-d %B")


def describe(row: Row, now: datetime) -> str:
    if row.below_floor:
        return (f"{row.name} ({row.channel}): {row.left} left, under the floor of {FLOOR}. "
                f"The unit tests are failing on main now.")
    days = row.days_until_tests_fail
    return (f"{row.name} ({row.channel}): {row.left} left. At one a day the unit tests "
            f"start failing in about {days} day{'s' if days != 1 else ''} "
            f"(around {_when(now, days)}).")


def marker(rows: list[Row]) -> str:
    return ",".join(f"{r.channel}={r.left}" for r in rows if r.low)


def issue_body(rows: list[Row], now: datetime) -> str:
    low = sorted((r for r in rows if r.low), key=lambda r: r.left)
    lines = [
        f"Checked at {now.strftime('%Y-%m-%d %H:%M')} UTC "
        f"({(now + timedelta(hours=1)).strftime('%A %-d %B, %-I:%M%p')} Nigeria time).",
        "",
        "Each channel has a list of Bible passages planned for its future long-form "
        "prayers. A channel uses about one a day. Nothing has stopped: videos are "
        "still being written and published.",
        "",
        f"### Running low ({FLOOR + WARN_DAYS * USED_PER_DAY} or fewer left)",
    ]
    lines += [f"- {describe(r, now)}" for r in low]
    lines += [
        "",
        "### What happens if nothing is done",
        f"- Under {FLOOR} left, the unit tests fail on `main`. Every pull request then "
        "shows a failed check for this reason, whatever it changes.",
        "- At none left, that channel has no passage to write its next long-form from.",
        "",
        "### What to do",
        "Ask for more passages to be added to the roadmap of each channel above "
        "(`scripts/continuous_research.py`). Fifteen more is about two weeks.",
        "",
        "### Every channel",
        "| Channel | Planned | Left |",
        "|---|---:|---:|",
    ]
    lines += [f"| {r.name} ({r.channel}) | {r.planned} | {r.left} |" for r in rows]
    lines += [
        "",
        "---",
        "This issue is maintained automatically (`scripts/roadmap_headroom.py`). It "
        f"closes itself when every channel has more than {FLOOR + WARN_DAYS * USED_PER_DAY} "
        "left. Nothing here needs a reply.",
        "",
        f"<!-- roadmap-headroom: {marker(rows)} -->",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# GitHub issue
# --------------------------------------------------------------------------- #
def _gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, cwd=ROOT, timeout=60)


def gh_available() -> bool:
    return bool(shutil.which("gh")
                and (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")))


def open_issue() -> dict | None:
    """The open issue with exactly this title.

    Found by title, because labels are not applied reliably on this repository
    (see `pipeline_watchdog.open_issue_number`). Read from the plain list of open
    issues and not from a search: the search index lags a new issue by a minute
    or more, and two runs close together would each open one.
    """
    proc = _gh(["issue", "list", "--state", "open", "--json", "number,title,body",
                "--limit", "200"])
    if proc.returncode != 0:
        raise RuntimeError(f"gh issue list failed: {(proc.stderr or '').strip()[:200]}")
    for item in json.loads(proc.stdout or "[]"):
        if str(item.get("title") or "").strip() == ISSUE_TITLE:
            return item
    return None


def _low_channels(text: str) -> dict[str, int]:
    match = _MARKER.search(text or "")
    out: dict[str, int] = {}
    if not match:
        return out
    for part in match.group(1).split(","):
        name, _, count = part.partition("=")
        if name and count.strip().lstrip("-").isdigit():
            out[name.strip()] = int(count)
    return out


def sync_issue(rows: list[Row], now: datetime | None = None, dry_run: bool = False) -> str:
    """Open, update or close the one issue. Returns what was done."""
    now = now or datetime.now(timezone.utc)
    low = [r for r in rows if r.low]
    if dry_run or not gh_available():
        return "skipped"

    current = open_issue()
    if not low:
        if current is None:
            return "nothing to report"
        proc = _gh(["issue", "close", str(current["number"]), "--comment",
                    f"Every channel has more than {FLOOR + WARN_DAYS * USED_PER_DAY} planned "
                    "passages left again. Closing automatically."])
        if proc.returncode != 0:
            raise RuntimeError(f"gh issue close failed: {(proc.stderr or '').strip()[:200]}")
        return "closed"

    body = issue_body(rows, now)
    if current is None:
        proc = _gh(["issue", "create", "--title", ISSUE_TITLE, "--body", body])
        if proc.returncode != 0:
            raise RuntimeError(f"gh issue create failed: {(proc.stderr or '').strip()[:200]}")
        return "opened"

    before = _low_channels(current.get("body") or "")
    after = {r.channel: r.left for r in low}
    if before == after:
        return "unchanged"
    proc = _gh(["issue", "edit", str(current["number"]), "--body", body])
    if proc.returncode != 0:
        raise RuntimeError(f"gh issue edit failed: {(proc.stderr or '').strip()[:200]}")
    # Editing an issue sends no email. A channel that joins the list, or one that
    # crosses the floor, is news: say it in a comment, which does.
    news = [r for r in low
            if r.channel not in before or (r.below_floor and before[r.channel] >= FLOOR)]
    if news:
        _gh(["issue", "comment", str(current["number"]), "--body",
             "\n".join(f"- {describe(r, now)}" for r in news)])
        return "updated and commented"
    return "updated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sync-issue", action="store_true",
                        help="open, update or close the tracking issue")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    rows = headroom()
    if not rows:
        print("::error title=Planned passages could not be counted::no scheduled channel found")
        return 1
    if args.json:
        print(json.dumps([{"channel": r.channel, "name": r.name, "planned": r.planned,
                           "left": r.left, "low": r.low} for r in rows], indent=2))
    else:
        for r in rows:
            flag = "UNDER THE FLOOR" if r.below_floor else ("low" if r.low else "ok")
            print(f"[headroom] {r.channel:13s} planned {r.planned:3d}  left {r.left:3d}  {flag}")
    for r in rows:
        if r.low:
            level = "error" if r.below_floor else "warning"
            print(f"::{level} title=Planned passages running low ({r.channel})::{describe(r, now)}")

    if args.sync_issue:
        try:
            action = sync_issue(rows, now)
        except Exception as exc:  # noqa: BLE001 - the table above is still the report
            print(f"::warning title=The planned-passages issue could not be written::"
                  f"{type(exc).__name__}: {str(exc)[:300]}")
            action = "could not deliver"
        print(f"[headroom] issue: {action}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
