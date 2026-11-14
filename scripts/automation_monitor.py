"""Watch every automation, not just the ones someone asked about.

Three rounds of "is X working?" produced the same answer three times — no, and
nothing said so. Each subsystem was checked only when the owner asked, and each
check found a green workflow that did nothing:

* `comments.yml` — wrong API parameter, caught by a broad except, "no comments
  found", exit 0;
* `expand-scripts.yml` — never ran at all, and would have failed on import;
* `gemini_brain.yml` — ran daily, asked its own queue for permission, and the
  queue (counting unbuildable rows as runway) always said "no work needed";
* `produce.yml` — failed every slot on a job that could never render.

A green tick is not evidence. This module is the evidence:

1. **Did each workflow run at all?** (a workflow that never starts never fails)
2. **Did the runs succeed?** (and is the last failure older than the last fix?)
3. **Did the run leave any trace?** — a publish, a ledger row, a queued script.
4. **Is the channel actually publishing?** — the only outcome that matters.

It prints a table, writes machine-readable JSON, and hands the severity-ranked
findings to `scripts/pipeline_watchdog.py`, which keeps one issue open while
anything is wrong.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORKFLOWS = ROOT / ".github" / "workflows"
MONITOR_STATE = ROOT / "content" / "monitor" / "status.json"

# A workflow is "fresh" if it ran inside its own cadence plus this grace.
GRACE = timedelta(hours=6)
# A scheduled slot is considered missed once this long has passed with no run.
# GitHub's scheduler is best-effort and routinely 10-60 minutes late, so a tight
# window would cry wolf; three hours is long enough to be sure and short enough
# to act inside the same working day.
SLOT_GRACE = timedelta(hours=3)
# Every stamp this module prints is in the owner's zone. WAT is UTC+1 with no DST,
# so this is a fixed offset and cannot drift.
WAT = timezone(timedelta(hours=1))


@dataclass
class Automation:
    workflow: str
    name: str
    crons: list[str]
    last_run: datetime | None = None
    last_conclusion: str | None = None
    last_success: datetime | None = None
    failures_5: int = 0
    runs_14d: int = 0
    last_edited: datetime | None = None
    last_slot: datetime | None = None
    missed_slots: int = 0
    max_gap: timedelta = timedelta(days=1)
    effect: str = ""
    verdict: str = ""
    detail: str = ""
    severity: str = "ok"

    def as_dict(self) -> dict:
        return {
            "workflow": self.workflow,
            "name": self.name,
            "crons": self.crons,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_conclusion": self.last_conclusion,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "runs_14d": self.runs_14d,
            "last_edited": self.last_edited.isoformat() if self.last_edited else None,
            "last_slot": self.last_slot.isoformat() if self.last_slot else None,
            "missed_slots": self.missed_slots,
            "failures_5": self.failures_5,
            "effect": self.effect,
            "verdict": self.verdict,
            "detail": self.detail,
            "severity": self.severity,
        }


@dataclass
class MonitorReport:
    automations: list[Automation] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def blocking(self) -> list[Automation]:
        return [a for a in self.automations if a.severity == "blocking"]

    @property
    def warnings(self) -> list[Automation]:
        return [a for a in self.automations if a.severity == "warning"]

    @property
    def healthy(self) -> bool:
        return not self.blocking and not any(o.get("severity") == "blocking" for o in self.outcomes)

    def as_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "healthy": self.healthy,
            "automations": [a.as_dict() for a in self.automations],
            "outcomes": self.outcomes,
        }


# --------------------------------------------------------------------------- #
# GitHub data
# --------------------------------------------------------------------------- #
def _gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True,
                          cwd=ROOT, timeout=120)


def gh_available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
                or shutil.which("gh"))


def fetch_runs(per_page: int = 20) -> list[dict]:
    """Recent runs for every scheduled workflow, keyed by file name.

    The repo-wide `/actions/runs` feed is dominated by push-triggered CI, which
    pushed the weekly jobs off the first page and made them look like they had never
    run. Asking each workflow for its own history is the only reliable way to tell
    "never runs" from "ran a week ago".
    """
    proc = _gh(["api", f"repos/{repo_slug()}/actions/workflows?per_page=100"])
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip()[:300] or "gh api failed")
    workflows = json.loads(proc.stdout or "{}").get("workflows", [])
    by_file = {w["path"].split("/")[-1]: w["id"] for w in workflows}

    runs: list[dict] = []
    for filename, _name, _crons in workflow_files():
        wid = by_file.get(filename)
        if not wid:
            continue
        resp = _gh(["api", f"repos/{repo_slug()}/actions/workflows/{wid}/runs?per_page={per_page}"])
        if resp.returncode != 0:
            continue
        for run in json.loads(resp.stdout or "{}").get("workflow_runs", []):
            run["path"] = filename
            runs.append(run)
    return runs


def repo_slug() -> str:
    proc = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True,
                          text=True, cwd=ROOT, timeout=30)
    url = (proc.stdout or "").strip()
    if url.endswith(".git"):
        url = url[:-4]
    if ":" in url and "@" in url:            # git@github.com:owner/repo
        return url.split(":", 1)[1]
    return "/".join(url.split("/")[-2:])


def _parse(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def cron_gap(crons: list[str]) -> timedelta:
    widest = timedelta(days=1)
    for expr in crons:
        parts = expr.split()
        if len(parts) != 5:
            continue
        _, _, dom, _, dow = parts
        if dow != "*":
            days = {d for d in dow.replace(",", " ").split() if d.isdigit()}
            widest = max(widest, timedelta(days=7 if len(days) <= 1 else 7))
        elif dom != "*":
            widest = max(widest, timedelta(days=31))
    return widest


def _expand(field: str, low: int, high: int) -> set[int] | None:
    """Expand a cron field. None means 'any' (unbounded)."""
    field = field.strip()
    if field == "*":
        return None
    values: set[int] = set()
    for part in field.split(","):
        if part.startswith("*/"):
            step = int(part[2:])
            values |= set(range(low, high + 1, step))
        elif part.isdigit():
            values.add(int(part))
    return values or None


def prev_occurrence(crons: list[str], now: datetime) -> datetime | None:
    """The most recent time one of these crons was due, at or before `now`.

    Needed because "last run was 9 days ago" is a different fault from "the Monday
    4:23am slot came and went today": the first is a broken workflow, the second is
    a scheduler that dropped a slot, and only this comparison can tell them apart.
    """
    latest: datetime | None = None
    for expr in crons:
        parts = expr.split()
        if len(parts) != 5:
            continue
        minute_s, hour_s, dom_s, _mon, dow_s = parts
        if dom_s != "*":
            continue  # day-of-month shapes are not used here; do not guess
        if not minute_s.isdigit():
            continue
        minute = int(minute_s)
        hours = _expand(hour_s, 0, 23) or set(range(24))
        dows = _expand(dow_s, 0, 7)
        # Each cron line is searched on its own. Stopping as soon as *any* line
        # had an answer meant that with several lines (production: 06:14, 14:14,
        # 19:14) the later ones never looked at yesterday: from midnight until
        # 06:14 UTC the "most recent slot" came back as yesterday 06:14, not
        # yesterday 19:14, and the evening slot stopped being recoverable at
        # midnight.
        best: datetime | None = None
        for back in range(0, 9):
            day = (now - timedelta(days=back)).date()
            if dows is not None:
                cron_dow = (day.weekday() + 1) % 7      # cron: Sunday = 0
                if cron_dow not in dows and not (cron_dow == 0 and 7 in dows):
                    continue
            for hour in sorted(hours, reverse=True):
                candidate = datetime(day.year, day.month, day.day, hour, minute,
                                     tzinfo=timezone.utc)
                if candidate <= now:
                    best = candidate
                    break
            if best is not None:
                break
        if best is not None and (latest is None or best > latest):
            latest = best
    return latest


def workflow_files() -> list[tuple[str, str, list[str]]]:
    out = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        crons = [c for c in _crons(text)]
        if not crons:
            continue
        name = ""
        for line in text.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
                break
        out.append((path.name, name or path.stem, crons))
    return out


def _crons(text: str) -> list[str]:
    import re

    return re.findall(r"cron:\s*[\"']([^\"']+)[\"']", text)


def first_commit_for(path: Path) -> datetime | None:
    """When the workflow file first appeared — a brand-new cron cannot have run yet."""
    proc = subprocess.run(["git", "log", "--diff-filter=A", "--follow", "--format=%cI",
                           "--", str(path)],
                          capture_output=True, text=True, cwd=ROOT, timeout=30)
    stamps = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    return _parse(stamps[-1]) if stamps else None


def history_depth() -> int:
    """How many commits this clone actually has."""
    proc = subprocess.run(["git", "rev-list", "--count", "HEAD"], capture_output=True,
                          text=True, cwd=ROOT, timeout=30)
    try:
        return int((proc.stdout or "0").strip())
    except ValueError:
        return 0


def last_commit_for(path: Path) -> datetime | None:
    """Local git answer, or None when the clone cannot answer honestly.

    A squashed or shallow checkout has one commit that "touched" every file, so
    `git log -1 -- <path>` returns the tip for everything. That reads as "every
    workflow was edited minutes ago", which silently downgraded real failures to
    "untested fix". When the depth is 1, say so instead of guessing.
    """
    if history_depth() < 2:
        return None
    proc = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(path)],
                          capture_output=True, text=True, cwd=ROOT, timeout=30)
    stamp = (proc.stdout or "").strip()
    return _parse(stamp) if stamp else None


#: Underlying Python modules whose edits fix or alter a scheduled workflow's behavior.
WORKFLOW_CODE_PATHS: dict[str, tuple[str, ...]] = {
    "gemini_brain.yml": ("pipeline/gemini_brain.py", "scripts/gemini_brain.py", "pipeline/supply.py", "scripts/continuous_research.py"),
    "community.yml": ("pipeline/community_posts.py", "scripts/post_community.py"),
    "metrics.yml": ("scripts/metrics_snapshot.py", "pipeline/channels.py"),
    "produce.yml": ("pipeline/run.py", "pipeline/prayer_pipeline.py", "pipeline/prayer_alignment.py", "pipeline/short_release.py"),
    "comments.yml": ("pipeline/comment_responder.py", "scripts/reply_comments.py"),
    "growth-autopilot.yml": ("scripts/growth_autopilot.py",),
    "automation-health.yml": ("scripts/pipeline_watchdog.py", "scripts/automation_monitor.py"),
    "monitor.yml": ("scripts/automation_monitor.py", "scripts/pipeline_watchdog.py"),
}


def last_edit(workflow: str) -> datetime | None:
    """When this workflow (or its primary implementation module) last changed."""
    candidates = [f".github/workflows/{workflow}", *WORKFLOW_CODE_PATHS.get(workflow, ())]
    best: datetime | None = None
    if gh_available():
        slug = repo_slug()
        for rel in candidates:
            proc = _gh(["api", f"repos/{slug}/commits?path={rel}&per_page=1"])
            if proc.returncode != 0:
                continue
            rows = json.loads(proc.stdout or "[]")
            if rows:
                stamp = (rows[0].get("commit") or {}).get("committer", {}).get("date")
                parsed = _parse(stamp)
                if parsed and (best is None or parsed > best):
                    best = parsed
        if best is not None:
            return best
    for rel in candidates:
        local = last_commit_for(ROOT / rel)
        if local and (best is None or local > best):
            best = local
    return best


# --------------------------------------------------------------------------- #
# Verdicts
# --------------------------------------------------------------------------- #
EFFECTS = {
    "produce.yml": "publishes a video: content/published/ gains a receipt with a video id",
    "comments.yml": "posts replies and records them in content/comments/replied.json",
    "gemini_brain.yml": "writes content/queue/ or content/shorts-scripts/",
    "community.yml": "writes content/community/<id>-READY.md",
    "metrics.yml": "writes content/metrics.csv and opens a snapshot issue",
    "keepalive.yml": "re-arms scheduled workflows",
    "automation-health.yml": "reports and files stalls",
    "monitor.yml": "this report",
}


def _servable_scheduled_channels() -> list[str]:
    from pipeline.channels import scheduled_channels
    from pipeline.short_release import select_next_queued_short
    from pipeline.supply import publishable_longform

    channels = list(scheduled_channels())
    supplied = [
        c for c in channels
        if publishable_longform(channel_id=c) or select_next_queued_short(channel_id=c) is not None
    ]
    return supplied or channels


def active_quota_cooldown(
    now: datetime | None = None,
    channel_id: str | None = None,
) -> datetime | None:
    """Return `quota_reset_utc` when daily TTS quota is waiting (<25h) after a recent (<24h) publish.

    When `channel_id` is given, evaluates that channel's own quota pool only.
    When `channel_id` is None (repo-wide `produce.yml` verdict), returns a cooldown
    only if *every* servable scheduled channel is quota-blocked — one channel's
    exhausted free-tier pool never masks or blocks another channel that can publish.
    """
    now = now or datetime.now(timezone.utc)
    try:
        from pipeline.run import quota_blocked_until
        from scripts.pipeline_watchdog import last_publish

        newest = last_publish()
        if newest is None:
            return None
        _, published_when = newest
        if now - published_when > timedelta(hours=24):
            return None

        def _valid_block(ch: str) -> datetime | None:
            blocked = quota_blocked_until(now, channel_id=ch)
            if blocked is None:
                return None
            wait = blocked - now
            if wait <= timedelta(0) or wait > timedelta(hours=25):
                return None
            return blocked

        if channel_id is not None:
            return _valid_block(channel_id)

        targets = _servable_scheduled_channels()
        if not targets:
            return None
        blocks: list[datetime] = []
        for ch in targets:
            b = _valid_block(ch)
            if b is None:
                return None
            blocks.append(b)
        return min(blocks)
    except Exception as exc:  # noqa: BLE001
        print(f"[monitor] active_quota_cooldown check failed: {exc!r}", file=sys.stderr)
        return None


def classify(report: MonitorReport, runs: list[dict], now: datetime | None = None,
             expect_gh: bool = True) -> MonitorReport:
    now = now or datetime.now(timezone.utc)
    by_workflow: dict[str, list[dict]] = {}
    for run in runs:
        path = (run.get("path") or "").split("/")[-1]
        by_workflow.setdefault(path, []).append(run)

    cooldown_until = active_quota_cooldown(now)

    for filename, name, crons in workflow_files():
        auto = Automation(workflow=filename, name=name, crons=crons,
                          max_gap=cron_gap(crons), effect=EFFECTS.get(filename, ""))
        mine = sorted(by_workflow.get(filename, []),
                      key=lambda r: r.get("created_at") or "", reverse=True)
        auto.last_edited = last_edit(filename)
        if mine:
            auto.last_run = _parse(mine[0].get("created_at"))
            auto.last_conclusion = mine[0].get("conclusion")
            successes = [r for r in mine if r.get("conclusion") == "success"]
            auto.last_success = _parse(successes[0]["created_at"]) if successes else None
            recent = [r for r in mine
                      if _parse(r.get("created_at")) and now - _parse(r["created_at"]) <= timedelta(days=14)]
            auto.runs_14d = len(recent)
            window = recent[:5]
            if auto.last_edited is not None:
                # Judge flakiness strictly on runs created at or after the latest
                # workflow/module edit so superseded pre-fix failures never keep a
                # repaired workflow pinned to FLAKY before (or after) its next slot.
                post_edit = [
                    r for r in recent
                    if (_parse(r.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= auto.last_edited
                ]
                window = post_edit[:5]
            auto.failures_5 = sum(1 for r in window if r.get("conclusion") == "failure")
        auto.last_slot = prev_occurrence(crons, now)
        # A slot is only missed once the grace window after it has closed: GitHub's
        # scheduler is routinely late, and crying wolf 20 minutes in would be noise.
        if (auto.last_slot and now > auto.last_slot + SLOT_GRACE
                and (auto.last_run is None or auto.last_run < auto.last_slot)):
            auto.missed_slots = 1
        report.automations.append(auto)
        _verdict(auto, now, quota_cooldown=cooldown_until if filename == "produce.yml" else None)
    return report


def _wat(then: datetime) -> str:
    """A slot, in the owner's zone with the weekday that belongs to it."""
    return then.astimezone(WAT).strftime("%a %d %b %H:%M")


def _ago(then: datetime | None, now: datetime) -> str:
    if then is None:
        return "never"
    delta = now - then
    if delta < timedelta(minutes=1):
        return "just now"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)}m ago"
    if delta < timedelta(days=2):
        return f"{delta.total_seconds() / 3600:.1f}h ago"
    return f"{delta.days}d ago"


def _running_workflow() -> str:
    """The `name:` of the workflow executing this check, if any.

    A self-reporting job cannot judge its own exit code. On 3 November this
    workflow went red once, and from then on every pass read its own previous
    red run as evidence — "failed 41m ago and nothing was changed since" — and
    failed again, forever. `automation-health.yml` latched the same way. Two
    workflows stuck red because they were watching themselves is the opposite of
    a monitor; the loop has no exit condition.
    """
    return (os.environ.get("GITHUB_WORKFLOW") or "").strip()


_WATCHDOG_REPORTERS = frozenset({
    "monitor.yml",
    "monitor",
    "automation monitor",
    "automation-health.yml",
    "automation-health",
    ".github/workflows/automation-health.yml",
})


def _is_self(auto: Automation) -> bool:
    """Is this row the workflow running the check (or its twin watchdog reporter)?

    Both `monitor.yml` and `automation-health.yml` exit non-zero on the exact same
    `pipeline_watchdog` verdict. Treating only the single running file as self let
    `monitor.yml` latch on `automation-health.yml`'s red exit and vice versa.
    """
    running = _running_workflow().strip().lower()
    if not running:
        return False
    names = {str(auto.workflow).lower(), str(auto.name).lower(),
             str(auto.workflow).lower().removesuffix(".yml")}
    if running in names:
        return True
    if running in _WATCHDOG_REPORTERS and (names & _WATCHDOG_REPORTERS):
        return True
    return False


def _verdict(auto: Automation, now: datetime,
             quota_cooldown: datetime | None = None) -> None:
    if auto.last_run is None:
        added = auto.last_edited
        if added and now - added < auto.max_gap + GRACE:
            auto.verdict, auto.severity = "NEW", "warning"
            auto.detail = (f"added {added.date().isoformat()}; its first scheduled "
                           f"window has not closed yet")
            return
        auto.verdict, auto.severity = "NEVER RAN", "blocking"
        auto.detail = ("no run recorded. A scheduled workflow that never starts never "
                       "fails, so nothing reports this unless something looks for it")
        return

    # A failed run that was followed by an edit is untested, not fixed. The edit has
    # to be a real one: this comparison is why "last edited" is read from GitHub
    # rather than from a squashed checkout that claims every file changed today.
    if auto.last_conclusion == "failure":
        if quota_cooldown is not None:
            auto.verdict, auto.severity = "QUOTA WAIT", "info"
            auto.detail = (f"daily $0.00 TTS allowance spent after today's upload(s); "
                           f"resumes {_wat(quota_cooldown)} WAT")
        elif auto.last_edited and auto.last_run < auto.last_edited:
            auto.verdict, auto.severity = "UNTESTED FIX", "warning"
            auto.detail = (f"failed {_ago(auto.last_run, now)}; edited "
                           f"{_ago(auto.last_edited, now)} — needs one green run")
        elif _is_self(auto):
            # Its own last run is this check's own previous verdict. Judging it
            # would make the monitor permanently red after one bad night, with no
            # way to clear — so it is reported, and not counted as a stall.
            auto.verdict, auto.severity = "SELF-REPORT", "info"
            auto.detail = (f"this is the check itself; its previous run ended "
                           f"{auto.last_conclusion} {_ago(auto.last_run, now)}, which "
                           f"is its own verdict and not independent evidence")
        else:
            auto.verdict, auto.severity = "FAILING", "blocking"
            auto.detail = (f"failed {_ago(auto.last_run, now)} and nothing was changed "
                           f"since; the next slot will fail the same way")
        return

    # The slot that should have produced a run and did not. This is how a weekly
    # job is caught the same day, instead of a week later.
    if (auto.last_slot and now > auto.last_slot + SLOT_GRACE
            and (auto.last_run is None or auto.last_run < auto.last_slot)):
        auto.verdict, auto.severity = "MISSED SLOT", "blocking"
        auto.detail = (f"was due {_wat(auto.last_slot)} WAT and did not run; "
                       f"last run {_ago(auto.last_run, now)}")
        return

    overdue_at = auto.last_run + auto.max_gap + GRACE
    if now > overdue_at:
        auto.verdict, auto.severity = "OVERDUE", "blocking"
        auto.detail = (f"last run {auto.last_run.date().isoformat()}; expected again by "
                       f"{overdue_at.date().isoformat()}")
        return

    if auto.failures_5 >= 3:
        # The monitor and automation-health exit non-zero *because* the pipeline is
        # unhealthy — their own red runs are this report, not a fault in them.
        if str(auto.workflow).lower() in _WATCHDOG_REPORTERS:
            auto.verdict, auto.severity = "SELF-REPORT", "info"
            auto.detail = ("its red runs are the verdicts below, not failures of it")
            return
        auto.verdict, auto.severity = "FLAKY", "warning"
        auto.detail = f"{auto.failures_5} of its last 5 runs failed"
        return

    auto.verdict, auto.severity = "OK", "ok"
    age = now - (auto.last_success or auto.last_run)
    auto.detail = f"last success {age.total_seconds() / 3600:.1f}h ago"


# --------------------------------------------------------------------------- #
# Outcomes: did the channel actually gain anything?
# --------------------------------------------------------------------------- #
def check_outcomes(report: MonitorReport, now: datetime | None = None,
                   published_dir: Path | None = None,
                   log_path: Path | None = None) -> MonitorReport:
    now = now or datetime.now(timezone.utc)
    published = Path(published_dir or ROOT / "content" / "published")
    # File mtime is useless here: a fresh CI checkout stamps every file with the
    # checkout time, which is why this used to report "last upload 0.1h ago" on a
    # channel that had not published in a day. `published_on` is written by the
    # publisher and travels with the file.
    newest_date = None
    for path in sorted(published.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "youtube_video_id:" not in text:
            continue
        m_at = re.search(r"""^published_at:\s*['"]?([0-9]{4}-[0-9]{2}-[0-9]{2}T[^'"\n]+)['"]?""", text, re.M)
        if m_at:
            try:
                stamp = datetime.fromisoformat(m_at.group(1).strip().replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                newest_date = max(newest_date or stamp, stamp)
                continue
            except ValueError:
                pass
        match = re.search(r"""^published_on:\s*['"]?([0-9]{4}-[0-9]{2}-[0-9]{2})""", text, re.M)
        if not match:
            continue
        try:
            stamp = datetime.fromisoformat(match.group(1)).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        newest_date = max(newest_date or stamp, stamp)

    if newest_date:
        # A scheduled upload is dated with its public time, which can be ahead.
        age = max(now - newest_date, timedelta(0))
        report.outcomes.append({
            "outcome": "last upload",
            "detail": f"{newest_date.date().isoformat()} ({age.total_seconds() / 3600:.0f}h ago)",
            "severity": "blocking" if age > timedelta(hours=48)
                        else ("warning" if age > timedelta(hours=26) else "ok")})
    else:
        report.outcomes.append({"outcome": "last upload", "detail": "none recorded",
                                "severity": "blocking"})

    # Per-channel publish recency: prevent an active channel from masking a stalled sibling channel.
    try:
        from pipeline.channel_capabilities import brand_for
        from pipeline.channels import scheduled_channels
        from scripts.pipeline_watchdog import last_publish_for_channel

        for ch in scheduled_channels():
            hit = last_publish_for_channel(ch, published)
            disp = brand_for(ch).display_name
            if hit is None:
                report.outcomes.append({
                    "outcome": f"last upload ({ch})",
                    "detail": f"{disp}: no published receipt recorded; launch status unconfirmed",
                    "severity": "blocking",
                })
                continue
            ch_path, ch_when = hit
            ch_age = max(now - ch_when, timedelta(0))
            sev = (
                "blocking" if ch_age > timedelta(hours=48)
                else ("warning" if ch_age > timedelta(hours=26) else "ok")
            )
            report.outcomes.append({
                "outcome": f"last upload ({ch})",
                "detail": (
                    f"{disp}: {ch_when.date().isoformat()} "
                    f"({ch_age.total_seconds() / 3600:.0f}h ago — {ch_path.name})"
                ),
                "severity": sev,
            })
    except Exception as exc:  # noqa: BLE001
        report.outcomes.append({
            "outcome": "per-channel publish audit",
            "detail": f"Could not inspect channel receipts: {type(exc).__name__}",
            "severity": "blocking",
        })

    # A production run that finishes successfully and uploads nothing is the exact
    # failure the owner kept reporting: green tick, no video.
    produce = next((a for a in report.automations if a.workflow == "produce.yml"), None)
    if produce is not None and newest_date is not None and produce.last_success is not None:
        # "Nothing" is judged against the slot the run belonged to, not the
        # calendar. GitHub delivers a slot's schedule event hours late; by then
        # the supervisor has had every channel published, so the late run
        # correctly does nothing. One that started after midnight UTC (00:19 on
        # 14 November 2026, for the 19:14 slot) used to be reported as "green
        # tick, no video" until the next morning's upload, and kept this
        # monitor red for six hours with nothing wrong.
        slot = None
        for filename, _name, crons in workflow_files():
            if filename == "produce.yml":
                slot = prev_occurrence(crons, produce.last_success)
        served = slot is not None and newest_date >= slot
        if produce.last_success.date() > newest_date.date() and not served:
            report.outcomes.append({
                "outcome": "produce published nothing",
                "detail": (f"last successful production run "
                           f"{produce.last_success.astimezone(WAT).strftime('%d %b %H:%M')} WAT "
                           f"added no upload; newest video is {newest_date.date().isoformat()}"),
                "severity": "blocking"})

    queue = list((ROOT / "content" / "queue").glob("*.md"))
    from pipeline.script_doc import MIN_LONGFORM_WORDS, parse_script

    publishable = 0
    approved = 0
    for path in queue:
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        if doc.status != "approved":
            continue
        approved += 1
        if doc.word_count >= MIN_LONGFORM_WORDS:
            publishable += 1
    report.outcomes.append({
        "outcome": "publishable runway",
        "detail": (f"{publishable} of {approved} approved script(s) over the "
                   f"{MIN_LONGFORM_WORDS}-word floor ({len(queue)} in queue)"),
        # Zero publishable scripts means the next production slot cannot upload,
        # whatever its exit code says. That is a blocking fault, not a note.
        "severity": "ok" if publishable else "blocking"})

    specs = list((ROOT / "content" / "shorts-scripts").glob("*.json"))
    report.outcomes.append({"outcome": "authored Short specs",
                            "detail": f"{len(specs)} spec(s)", "severity": "ok"})

    log = Path(log_path or ROOT / "content" / "comments" / "replied.json")
    if log.is_file():
        try:
            replied = json.loads(log.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            replied = {}
        posted = sum(1 for v in replied.values()
                     if isinstance(v, dict) and v.get("reply_id"))
        report.outcomes.append({"outcome": "replies recorded",
                                "detail": f"{posted} live repl(ies), {len(replied)} row(s)",
                                "severity": "ok"})
    return report


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(report: MonitorReport) -> str:
    lines = ["", "AUTOMATION MONITOR — every scheduled workflow, plus the outcome that matters"]
    lines.append("=" * 100)
    lines.append(f"{'workflow':<26}{'verdict':<14}{'last run':<15}{'edited':<15}{'runs':<6}detail")
    lines.append("all times WAT (Africa/Lagos)")
    lines.append("-" * 108)
    def stamp(d):
        return d.astimezone(WAT).strftime("%d %b %H:%M") if d else "never"
    # Rank by a dict, not tuple.index: one unknown severity used to raise
    # ValueError *inside the renderer*, so a new verdict took the whole monitor
    # down instead of printing. A reporter must not be able to crash on its own
    # vocabulary.
    rank = {"blocking": 0, "warning": 1, "info": 2, "ok": 3}
    for a in sorted(report.automations, key=lambda x: rank.get(x.severity, 9)):
        lines.append(f"{a.workflow:<26}{a.verdict:<14}{stamp(a.last_run):<15}"
                     f"{stamp(a.last_edited):<15}{a.runs_14d:<6}{a.detail}")
    lines.append("")
    lines.append("OUTCOMES")
    for row in report.outcomes:
        mark = {"blocking": "!!", "warning": " ~", "info": " i", "ok": "  "}.get(
            row["severity"], " ?")
        lines.append(f" {mark} {row['outcome']:<24}{row['detail']}")
    lines.append("")
    return "\n".join(lines)


def findings(report: MonitorReport) -> list[tuple[str, str, bool]]:
    """(area, detail, fatal) in the shape the watchdog already understands."""
    out: list[tuple[str, str, bool]] = []
    for a in report.automations:
        if a.severity == "ok":
            continue
        out.append((a.workflow, f"{a.verdict} — {a.detail}", a.severity == "blocking"))
    for row in report.outcomes:
        if row["severity"] == "ok":
            continue
        out.append((row["outcome"], row["detail"], row["severity"] == "blocking"))
    return out


_AGE_NOISE_RE = re.compile(r"\b(?:just now|\d+(?:\.\d+)?[mhd] ago)\b")


def _status_material(payload: dict) -> dict:
    """Strip clock-ticking fields so unchanged monitor checks do not spam commits."""
    norm = json.loads(json.dumps(payload))
    norm.pop("generated_at", None)
    for row in norm.get("automations") or []:
        if isinstance(row, dict) and isinstance(row.get("detail"), str):
            row["detail"] = _AGE_NOISE_RE.sub("<age>", row["detail"])
    for row in norm.get("outcomes") or []:
        if isinstance(row, dict) and isinstance(row.get("detail"), str):
            row["detail"] = _AGE_NOISE_RE.sub("<age>", row["detail"])
    return norm


def save_monitor_state(payload: dict, path: Path = MONITOR_STATE) -> bool:
    """Write `status.json` only when verdicts, counts, or run timestamps changed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if _status_material(existing) == _status_material(payload):
                return False
        except (OSError, ValueError, TypeError):
            pass
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Audit every automation and its outcomes.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", action="store_true", help="write content/monitor/status.json")
    parser.add_argument("--offline", action="store_true",
                        help="skip GitHub calls (unit tests, no network)")
    args = parser.parse_args(argv)

    report = MonitorReport()
    if args.offline or not gh_available():
        print("[monitor] no GitHub access — reporting outcomes only (workflow history unknown)")
        runs: list[dict] = []
    else:
        try:
            runs = fetch_runs()
        except Exception as exc:  # noqa: BLE001
            print(f"[monitor] could not read run history: {exc}")
            runs = []
    classify(report, runs)
    check_outcomes(report)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(render(report))

    if args.save:
        save_monitor_state(report.as_dict(), MONITOR_STATE)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("### 📡 Automation monitor\n\n")
            fh.write("| workflow | verdict | last run | detail |\n|---|---|---|---|\n")
            for a in report.automations:
                last = a.last_run.strftime("%Y-%m-%d %H:%M") if a.last_run else "never"
                fh.write(f"| `{a.workflow}` | {a.verdict} | {last} | {a.detail} |\n")
            fh.write("\n")

    if not runs:
        return 0
    return 0 if report.healthy else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
