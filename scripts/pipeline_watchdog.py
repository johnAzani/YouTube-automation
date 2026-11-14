"""Tell the owner when the automation is broken, without him asking.

Every failure mode this channel has hit was silent:

* the Community workflow never ran at all — a scheduled workflow that never
  starts never fails, so the Actions page stayed green;
* the Shorts stage printed "nothing to do" and exited 0 while five manifests
  waited for a renderer that did not exist;
* twenty-one long-form scripts sat approved and under the word floor while
  production cheerfully reported no eligible jobs every three hours;
* the expansion pass had never executed once, and when it finally would have it
  would have crashed on an import error.

GitHub already knows how to reach a person: an issue sends an email. So this
watchdog keeps exactly one issue open while the pipeline is unhealthy, updates it
with what is wrong, and closes it when the pipeline is demonstrably working
again. Nothing to remember, nothing to check.

    python -m scripts.pipeline_watchdog            # report + sync the issue
    python -m scripts.pipeline_watchdog --dry-run  # report only

"Healthy" is deliberately behavioural, not cosmetic: there must be something
publishable in the long-form queue, something renderable in the Shorts queue, a
publish in the last few days, and every scheduled workflow must have actually run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - bare CI plan runner without PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ISSUE_LABEL = "pipeline-watchdog"
ISSUE_TITLE = "🚨 The Secret Place pipeline needs attention"
# The channel releases at every production slot (five a day since 14 November
# 2026; three when this was written). Three days —
# the old value — meant a release path that uploaded nothing could stay "healthy"
# for 24 missed slots. On 3 November the last upload was already 31 hours old and
# the watchdog called the pipeline healthy. One day and two hours is long enough to
# ride out a single failed slot and short enough to say so the same day.
MAX_PUBLISH_AGE = timedelta(hours=26)


@dataclass
class Finding:
    area: str
    detail: str
    fatal: bool = True   # fatal = nothing can publish because of this
    warning: bool = False  # not proven either way: a deployed fix that never ran


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        """Is the pipeline *proven* working — not merely "nothing is red right now"?

        A warning used to be silent here: it appeared in the run summary and nowhere
        else, so the tracking issue was closed while the pipeline was untested. On
        6 November at 10:37Z the monitor closed it with the brain still returning
        `503` on every call, because each merge had turned its red FAILING verdict
        into the amber UNTESTED FIX — "a fix is deployed and has never run green".
        That is not recovery. Recovery is a successful run, and until one exists the
        issue stays open.
        """
        return not any(f.fatal or f.warning for f in self.findings)

    def add(self, area: str, detail: str, fatal: bool = True,
            warning: bool = False) -> None:
        self.findings.append(Finding(area, detail, fatal, warning))

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "checked": self.checked,
            "findings": [{"area": f.area, "detail": f.detail, "fatal": f.fatal,
                          "warning": f.warning}
                         for f in self.findings],
        }


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
# Receipts with a video id but no date. Module-level because `last_publish` is
# called from a few places and each caller reports them alongside.
_undated: list[str] = []


def undated_receipts() -> list[str]:
    """Published receipts with a video id but no date. Reported, never inferred."""
    return list(_undated)


# Receipts whose date was written without a time: their age is a lower bound.
_approximate: set[str] = set()


def approximate_receipts() -> list[str]:
    return sorted(_approximate)


def last_publish(published_dir: Path | None = None) -> tuple[Path, datetime] | None:
    """Newest published receipt that carries a real YouTube video id."""
    from pipeline.config import PUBLISHED_DIR
    from pipeline.script_doc import _load_yaml_mapping

    directory = published_dir or PUBLISHED_DIR
    newest: tuple[Path, datetime] | None = None
    _undated.clear()
    _approximate.clear()
    for path in sorted(Path(directory).glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            meta = _load_yaml_mapping(text.split("---", 2)[1])
        except Exception:  # noqa: BLE001
            continue
        video_id = str(meta.get("youtube_video_id") or "").strip()
        if not video_id:
            continue
        # `published_on` is what the publisher actually writes. Without it this
        # fell through to the file's mtime — and a CI checkout stamps every file
        # with the checkout time, so the watchdog read "uploaded 0d ago" on a
        # channel that had not published in a day. It could never report a stale
        # publish, which is the one thing it exists to do.
        stamp = (meta.get("published_at") or meta.get("uploaded_at")
                 or meta.get("published_on") or meta.get("date") or meta.get("publish_at"))
        when = None
        approximate = False
        if stamp:
            raw = str(stamp).strip()
            try:
                when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            except ValueError:
                when = None
            if when is not None and len(raw) == 10:
                # A bare date proves a publish happened *that day*, not at 00:00.
                # Measuring from midnight invented up to 24 hours of staleness: a
                # video uploaded at 5pm today read as "20h ago" at 8pm, and the
                # owner's own question — when did it last publish — got a wrong
                # answer. Measure from the end of that day instead, so the reported
                # age is a lower bound and only an actually-stale channel alarms.
                approximate = True
                when = when.replace(hour=23, minute=59, second=59)
        if when is None:
            # No date on the receipt: do not guess from mtime. An undated receipt
            # is evidence of *a* publish, not of a recent one.
            _undated.append(path.name)
            continue
        if newest is None or when > newest[1]:
            newest = (path, when)
        if approximate:
            _approximate.add(path.name)
    return newest


def last_publish_for_channel(
    channel_id: str | None = None,
    published_dir: Path | None = None,
    *,
    longform_only: bool = False,
) -> tuple[Path, datetime] | None:
    """Newest published receipt carrying a real YouTube video id for `channel_id`."""
    from pipeline.channels import channel_for_doc, normalize_channel_id
    from pipeline.config import PUBLISHED_DIR
    from pipeline.script_doc import _load_yaml_mapping

    wanted = normalize_channel_id(channel_id)
    directory = published_dir or PUBLISHED_DIR
    newest: tuple[Path, datetime] | None = None
    for path in sorted(Path(directory).glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            meta = _load_yaml_mapping(text.split("---", 2)[1])
        except Exception:  # noqa: BLE001
            continue
        if channel_for_doc(meta) != wanted:
            continue
        if longform_only:
            fmt = str(meta.get("format") or "").strip().lower()
            if fmt == "short" or path.name.startswith("short-"):
                continue
        video_id = str(meta.get("youtube_video_id") or "").strip()
        if not video_id:
            continue
        stamp = (
            meta.get("published_at")
            or meta.get("uploaded_at")
            or meta.get("published_on")
            or meta.get("date")
            or meta.get("publish_at")
        )
        if not stamp:
            continue
        raw = str(stamp).strip()
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if len(raw) == 10:
            when = when.replace(hour=23, minute=59, second=59)
        if newest is None or when > newest[1]:
            newest = (path, when)
    return newest


def check_queues(report: Report, max_publish_age: timedelta = MAX_PUBLISH_AGE,
                 published_dir: Path | None = None, now: datetime | None = None) -> Report:
    from scripts.automation_health import queue_health

    now = now or datetime.now(timezone.utc)
    try:
        rows = queue_health()
    except Exception as exc:  # noqa: BLE001
        report.add("queues", f"could not read the queues: {exc}")
        return report

    from pipeline.channel_capabilities import capabilities_for
    from pipeline.script_doc import MIN_LONGFORM_WORDS

    channel_rows = {row["queue"] for row in rows if ":" in str(row.get("queue", ""))}

    for row in rows:
        queue_name = str(row.get("queue", ""))
        report.checked.append(f"{queue_name} queue: {row['ready']} ready ({row['note']})")
        if row["ready"] > 0:
            continue

        kind, _, suffix = queue_name.partition(":")
        per_channel = bool(suffix)
        # The row name is authoritative; `channel` is only a convenience.
        channel_id = suffix or row.get("channel")
        if not per_channel and channel_id and f"{queue_name}:{channel_id}" in channel_rows:
            # The unprefixed row is the historic alias for channel 1; when the
            # per-channel rows exist they carry this finding, so it is not said
            # twice.
            continue

        try:
            caps = capabilities_for(channel_id)
            display = caps.brand.display_name
        except ValueError:
            display = f"channel {channel_id}"
            caps = None

        if kind == "longform":
            # Starvation on one channel must never hide behind a healthy queue on
            # the other: each channel's own row raises its own finding.
            report.add(
                "long-form queue",
                f"{display} has nothing in content/queue/ that is approved and over "
                f"the {MIN_LONGFORM_WORDS}-word floor. Its brain should have lengthened "
                f"or authored one; check `python scripts/gemini_brain.py "
                f"--ensure-supply-for {channel_id or '<channel>'}`.",
            )
        elif kind == "shorts":
            if not row.get("blocked", 1):
                # An empty Shorts queue is not a stall; a queue of manifests that
                # cannot be built is. Say nothing until there is something stuck.
                continue
            report.add(
                "shorts queue",
                f"{display} has no Short that can render ({row['note']}). Check "
                f"`CHANNEL_ID={channel_id or '<channel>'} python scripts/gemini_brain.py "
                f"--author-shorts`.",
                fatal=False,
            )

    newest = last_publish(published_dir)
    if newest is None:
        undated = undated_receipts()
        if undated:
            # A receipt exists but carries no date; it proves a publish happened,
            # not that one happened recently. Say that rather than "none yet".
            report.checked.append(
                f"undated receipt (not counted as recent): {', '.join(undated[:3])}")
            report.add("publishing",
                       f"{len(undated)} published receipt(s) carry no date, so recency is "
                       f"unknown — newest is {undated[-1]}. Add `published_on` when publishing.",
                       fatal=False)
        else:
            report.add("publishing", "no published receipt with a YouTube video id exists yet",
                       fatal=False)
    else:
        path, when = newest
        age = now - when
        if path.name in _approximate:
            # A date-only receipt is measured from the *end* of its day, so this is
            # a lower bound on the real age. Clamp it at zero: "published today"
            # must not print as "-4h ago".
            age = max(age, timedelta(0))
            report.checked.append(
                f"last publish: {path.name} on {when.date().isoformat()} "
                f"(within the last {age.total_seconds() / 3600:.0f}h; the receipt "
                f"records a date, not a time)")
        elif age < timedelta(0):
            # A scheduled upload: the receipt carries the time it goes public.
            report.checked.append(
                f"last publish: {path.name} on {when.date().isoformat()} "
                f"(scheduled; public in {-age.total_seconds() / 3600:.1f}h)")
            age = timedelta(0)
        else:
            report.checked.append(
                f"last publish: {path.name} on {when.date().isoformat()} "
                f"({age.total_seconds() / 3600:.0f}h ago)")
        for name in undated_receipts():
            report.checked.append(f"undated receipt (not counted as recent): {name}")
        if age > max_publish_age:
            report.add("publishing",
                       f"last upload was {age.days} days ago ({when.date().isoformat()}). "
                       f"The release crons are running but publishing nothing.")

        from pipeline.channels import scheduled_channels

        per_channel_latest: list[tuple[str, Path, datetime]] = []
        for ch in scheduled_channels():
            ch_hit = last_publish_for_channel(ch, published_dir)
            if ch_hit is not None:
                per_channel_latest.append((ch, ch_hit[0], ch_hit[1]))

        for ch, ch_path, ch_when in per_channel_latest:
            ch_age = max(now - ch_when, timedelta(0))
            report.checked.append(
                f"last publish:{ch}: {ch_path.name} on {ch_when.date().isoformat()} "
                f"({ch_age.total_seconds() / 3600:.0f}h ago)"
            )
            if len(per_channel_latest) > 1 and ch_age > max_publish_age:
                try:
                    ch_display = capabilities_for(ch).brand.display_name
                except ValueError:
                    ch_display = f"channel {ch}"
                report.add(
                    "publishing",
                    f"{ch_display} ({ch}) last uploaded {ch_age.total_seconds() / 3600:.0f}h ago "
                    f"({ch_when.date().isoformat()} — {ch_path.name}), exceeding the "
                    f"{int(max_publish_age.total_seconds() // 3600)}h per-channel threshold.",
                )
    return report


def expects_brain() -> bool:
    """Does this runner declare that it is supposed to hold the API key?

    Presence of GITHUB_ACTIONS is the wrong test: the unit-test job and the health
    job run in Actions without the secret, and marking them fatal would file a
    false alarm every night. The workflow says so explicitly instead.
    """
    return os.environ.get("EXPECT_BRAIN_API", "").strip().lower() in {"1", "true", "yes"}


def check_brain_api(report: Report, expect: bool | None = None) -> Report:
    """Can the authoring brain reach Gemini from here, and if not, why exactly?

    Reported verbatim: "the key is not set" and "the key is set but the client
    could not start" are different faults, and conflating them wasted weeks —
    the same key narrates every video.
    """
    try:
        from pipeline.gemini_brain import GeminiBrain

        status = GeminiBrain().api_status()
    except Exception as exc:  # noqa: BLE001
        report.add("brain api", f"could not even inspect the brain: {exc}")
        return report
    report.checked.append(f"brain api: {status['reason']} (model {status['model']})")
    if not status["client_ready"]:
        # Fatal only where the workflow promised the runner holds the key. Elsewhere
        # it is context: nothing new can be authored here, but queued work still can.
        report.add("brain api",
                   f"the brain cannot author or lengthen anything: {status['reason']}",
                   fatal=expects_brain() if expect is None else expect)
    return report


def check_automations(report: Report) -> bool:
    """Every scheduled workflow, via the monitor's evidence-based verdicts.

    `automation_health.audit()` only asks "is it overdue?". This asks the harder
    question — did the run achieve anything — and marks a failure as blocking only
    when the workflow has not been changed since it failed.
    """
    try:
        from scripts.automation_monitor import MonitorReport, check_outcomes, classify, fetch_runs

        monitored = MonitorReport()
        try:
            classify(monitored, fetch_runs())
        except Exception as exc:  # noqa: BLE001
            report.add("automations", f"could not read run history: {exc}", fatal=False)
            return False
        check_outcomes(monitored)
    except Exception as exc:  # noqa: BLE001
        report.add("automations", f"monitor unavailable: {exc}", fatal=False)
        return False

    for automation in monitored.automations:
        state = f"{automation.workflow}: {automation.verdict} — {automation.detail}"
        if automation.severity == "ok":
            report.checked.append(state)
            continue
        report.add("automations", state, fatal=automation.severity == "blocking",
                   warning=automation.severity == "warning")

    for row in monitored.outcomes:
        state = f"{row['outcome']}: {row['detail']}"
        if row["severity"] == "ok":
            report.checked.append(state)
        else:
            report.add("outcome", state, fatal=row["severity"] == "blocking",
                       warning=row["severity"] == "warning")
    return bool(monitored.automations)


def check_schedule_health(report: Report, now: datetime | None = None) -> dict:
    """Is the repository running at all — and if it ran, was it on time?

    Every other check in this file is a verdict about a workflow, and each of those
    verdicts is produced by a workflow. On the night of 5-6 November nothing started
    between 02:52 and 07:52, so no verdict was recomputed and `status.json` still
    read healthy at breakfast: the alarm was starved by the same outage it exists to
    report. Silence is a property of the whole repo, so it is measured here from the
    run history directly, and whichever pass is alive files it.
    """
    try:
        from scripts.scheduler_supervisor import (
            SILENCE_ALARM_MINUTES,
            SILENCE_WARN_MINUTES,
            schedule_health,
        )

        health = schedule_health(now)
    except Exception as exc:  # noqa: BLE001
        report.add("schedule", f"could not measure scheduler health: {exc}", fatal=False)
        return {}

    silence = health.get("silence_minutes")
    late = health.get("delivered_late") or []
    if silence is None:
        report.add("schedule", "no run history at all — the scheduler has delivered nothing",
                   fatal=True)
        return health

    if silence >= SILENCE_ALARM_MINUTES:
        worst = ", ".join(f"{r['name']} +{r['late_minutes']}m" for r in late[:3]) or "none"
        report.add(
            "schedule",
            f"**nothing has run for {silence // 60}h{silence % 60:02d}m** (last start "
            f"`{health.get('last_run_at')}`). GitHub delivered no cron event; the next "
            f"delivery runs a supervisor pass that performs every overdue job. Late "
            f"deliveries: {worst}",
            fatal=True,
        )
    elif silence >= SILENCE_WARN_MINUTES:
        report.checked.append(
            f"schedule: quiet {silence} min (warning threshold {SILENCE_WARN_MINUTES})"
        )
    else:
        report.checked.append(f"schedule: last start {silence} min ago")

    for row in late[:3]:
        report.checked.append(
            f"late delivery: {row['name']} served {row['slot']} +{row['late_minutes']} min"
        )
    return health


def check_workflows(report: Report, rows=None) -> Report:
    """Every scheduled workflow must have run inside its own cron window."""
    if rows is None:
        try:
            from scripts.automation_health import audit
            rows = audit()
        except Exception as exc:  # noqa: BLE001
            report.add("workflows", f"could not audit scheduled workflows: {exc}", fatal=False)
            return report
    for row in rows:
        if row.status == "ok":
            continue
        report.add("workflows", f"{row.workflow}: {row.status} — {row.detail}", fatal=False)
    return report


def build_report(now: datetime | None = None, published_dir: Path | None = None,
                 workflow_rows=None, expect_brain: bool | None = None) -> Report:
    report = Report()
    check_schedule_health(report, now=now)
    check_queues(report, published_dir=published_dir, now=now)
    check_brain_api(report, expect=expect_brain)
    check_workflows(report, rows=workflow_rows)
    if workflow_rows is None:
        check_automations(report)
    return report


# --------------------------------------------------------------------------- #
# GitHub issue sync
# --------------------------------------------------------------------------- #
def _gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, cwd=ROOT, timeout=60)


def gh_available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or shutil.which("gh"))


def open_issue_number() -> int | None:
    """The open tracking issue, found by label *or* by title.

    The label search alone is not enough: on this repository `gh issue create
    --label ...` returns success while the label is silently not applied, so a
    label-only lookup finds nothing and every pass opens a fresh issue. That is
    exactly how one viewer's disclosure became #203, #204, #205, #206, #207,
    #209, #211, #213, #214, #217 and #218.
    """
    for args in (["--label", ISSUE_LABEL],
                 ["--search", f'"{ISSUE_TITLE}" in:title']):
        proc = _gh(["issue", "list", *args, "--state", "open", "--json", "number",
                    "--limit", "1"])
        if proc.returncode != 0:
            continue
        try:
            rows = json.loads(proc.stdout or "[]")
        except ValueError:
            rows = []
        if rows:
            return int(rows[0]["number"])
    return None


def ensure_label() -> None:
    _gh(["label", "create", ISSUE_LABEL, "--color", "b60205",
         "--description", "Automation stall reported by scripts/pipeline_watchdog.py"])


def issue_body(report: Report, now: datetime) -> str:
    fatal = [f for f in report.findings if f.fatal]
    warn = [f for f in report.findings if not f.fatal]
    lines = [
        f"Checked at {now.strftime('%Y-%m-%d %H:%M')} UTC "
        f"({(now + timedelta(hours=1)).strftime('%A %-d %B, %-I:%M%p')} Nigeria time).",
        "",
    ]
    if fatal:
        lines.append("### Blocking findings requiring attention")
        lines += [f"- **{f.area}** — {f.detail}" for f in fatal]
        lines.append("")
    if warn:
        lines.append("### Degraded")
        lines += [f"- **{f.area}** — {f.detail}" for f in warn]
        lines.append("")
    lines.append("### What was checked")
    lines += [f"- {c}" for c in report.checked] or ["- (nothing)"]
    lines += [
        "",
        "---",
        "This issue is maintained automatically. It closes itself on the first run "
        "where the queues have work and every scheduled workflow has run. "
        "Nothing here needs a reply.",
    ]
    return "\n".join(lines)


def sync_issue(report: Report, now: datetime | None = None, dry_run: bool = False) -> str:
    """Open/update the tracking issue when unhealthy; close it when healthy."""
    now = now or datetime.now(timezone.utc)
    if dry_run or not gh_available():
        return "skipped"

    ensure_label()
    number = open_issue_number()

    if report.healthy:
        if number is None:
            return "healthy"
        _gh(["issue", "close", str(number), "--comment",
             "Pipeline is healthy again: every queue has work, every scheduled "
             "workflow has run inside its window, and none is carrying an unproven "
             "fix. Closing automatically."])
        return "closed"

    body = issue_body(report, now)
    if number is None:
        proc = _gh(["issue", "create", "--title", ISSUE_TITLE, "--label", ISSUE_LABEL,
                    "--body", body])
        if proc.returncode != 0:
            raise RuntimeError(f"gh issue create failed: {(proc.stderr or '').strip()[:200]}")
        return "opened"
    _gh(["issue", "edit", str(number), "--body", body])
    return "updated"


def cleanup_stale_issues(report: Report, dry_run: bool = False) -> list[int]:
    """Close synthetic test-fixture crisis issues and superseded public release tickets."""
    if dry_run or not gh_available():
        return []
    proc = _gh(["issue", "list", "--state", "open", "--json", "number,title,body", "--limit", "100"])
    if proc.returncode != 0:
        return []
    try:
        issues = json.loads(proc.stdout or "[]")
    except ValueError:
        return []

    pub_titles: set[str] = set()
    for p in sorted((ROOT / "content" / "published").glob("*.md")):
        try:
            from pipeline.script_doc import parse_script
            doc = parse_script(p)
            if doc.meta.get("youtube_video_id") and str(doc.meta.get("privacy", "public")).lower() == "public":
                pub_titles.add(str(doc.title).strip())
        except Exception:  # noqa: BLE001
            continue

    closed: list[int] = []
    for item in issues:
        num = item.get("number")
        title = str(item.get("title") or "")
        body = str(item.get("body") or "")
        if not num:
            continue
        reason = ""
        if title.startswith("Viewer in distress") and (
            "`c4`" in body or "`c_sim_6`" in body
            or ("**Ann**" in body and "I want to end my life tonight" in body)
            or "**AnonymousSoul**" in body
        ):
            reason = "Closing synthetic test/simulation fixture issue (`c4`/`c_sim_6`); hermetic test guards are active."
        elif title.startswith("Release ticket: "):
            t_clean = title.removeprefix("Release ticket: ").strip()
            if t_clean in pub_titles or "Enron" in t_clean:
                reason = "Closing superseded release ticket (video is already published publicly on YouTube)."
        elif report.healthy and title.startswith(("Release failed", "Release died inside")):
            reason = "Closing resolved release-failure report (pipeline and queues are healthy)."

        if reason:
            res = _gh(["issue", "close", str(num), "--comment", reason])
            if res.returncode == 0:
                closed.append(int(num))
    return closed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Report and file pipeline stalls.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="report only, do not touch issues")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        for row in report.checked:
            print(f"[watchdog] checked: {row}")
        for finding in report.findings:
            tag = "BLOCKING" if finding.fatal else "warning"
            print(f"[watchdog] {tag}: {finding.area} — {finding.detail}")

    delivery_note = ""
    try:
        action = sync_issue(report, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - reporting must never replace reporting
        # The findings above are the message. If the issue cannot be filed we say
        # so, loudly, and still return the verdict — on 3 November `gh issue list`
        # raised here and the step ended with a bare exit code, so the alarm that
        # was supposed to hold the findings destroyed them on the way out.
        action = "could not deliver"
        delivery_note = f"{type(exc).__name__}: {exc}"
    print(f"[watchdog] issue: {action} — {'healthy' if report.healthy else 'unhealthy'}")
    if delivery_note:
        print(f"::warning title=The stall report could not be filed::{delivery_note[:300]}")

    in_ci = os.environ.get("GITHUB_ACTIONS")
    if in_ci and not args.dry_run:
        try:
            swept = cleanup_stale_issues(report, dry_run=args.dry_run)
            if swept:
                print(f"[watchdog] swept {len(swept)} synthetic/superseded issue(s): {swept}")
        except Exception as exc:  # noqa: BLE001
            print(f"[watchdog] issue hygiene skipped: {exc}")
    if in_ci:
        if not report.healthy:
            # Name every blocking finding in the annotation. The step used to fail
            # with a bare "exit code 1" and a run log that could not be opened, so
            # the one question the owner asks — *what* is stalled — had no answer on
            # the page where the red X appeared.
            blocking = [f for f in report.findings if f.fatal]
            for finding in blocking:
                detail = " ".join(str(finding.detail).split())
                print(f"::error title=Automation is stalled ({finding.area})::{detail[:400]}")
            if not blocking:
                # Unhealthy without a blocking finding means a *warning* is holding
                # the issue open — a fix deployed but never run green, or a workflow
                # flaky enough to be untrustworthy. Those kept the run red while the
                # only annotation said "the watchdog opened/updated a tracking issue"
                # (run 42235642633, 6 November 14:37Z), so the red X named nothing.
                # A degraded verdict is still a verdict and has to say which one.
                degraded = [f for f in report.findings if f.warning]
                for finding in degraded:
                    detail = " ".join(str(finding.detail).split())
                    print(f"::error title=Pipeline is degraded ({finding.area})::{detail[:400]}")
                if not degraded:
                    print("::error title=Automation is stalled::the watchdog opened/updated a tracking issue")
        elif action == "closed":
            print("::notice title=Automation recovered::tracking issue closed")
    return 0 if report.healthy else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
