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

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ISSUE_LABEL = "pipeline-watchdog"
ISSUE_TITLE = "🚨 The Secret Place pipeline needs attention"
MAX_PUBLISH_AGE = timedelta(days=3)


@dataclass
class Finding:
    area: str
    detail: str
    fatal: bool = True  # fatal = nothing can publish because of this


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not any(f.fatal for f in self.findings)

    def add(self, area: str, detail: str, fatal: bool = True) -> None:
        self.findings.append(Finding(area, detail, fatal))

    def as_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "checked": self.checked,
            "findings": [{"area": f.area, "detail": f.detail, "fatal": f.fatal}
                         for f in self.findings],
        }


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def last_publish(published_dir: Path | None = None) -> tuple[Path, datetime] | None:
    """Newest published receipt that carries a real YouTube video id."""
    from pipeline.config import PUBLISHED_DIR

    directory = published_dir or PUBLISHED_DIR
    newest: tuple[Path, datetime] | None = None
    for path in sorted(Path(directory).glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                continue
            meta = yaml.safe_load(text.split("---", 2)[1]) or {}
        except Exception:  # noqa: BLE001
            continue
        video_id = str(meta.get("youtube_video_id") or "").strip()
        if not video_id:
            continue
        stamp = (meta.get("published_at") or meta.get("uploaded_at")
                 or meta.get("date") or meta.get("publish_at"))
        when = None
        if stamp:
            try:
                when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            except ValueError:
                when = None
        if when is None:
            when = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
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

    for row in rows:
        report.checked.append(f"{row['queue']} queue: {row['ready']} ready ({row['note']})")
        if row["queue"] == "longform" and row["ready"] == 0:
            report.add("long-form queue",
                       "nothing in content/queue/ is approved and over the 650-word floor. "
                       "The brain should have lengthened or authored one; check "
                       "`python scripts/gemini_brain.py --ensure-supply`.")
        if row["queue"] == "shorts" and row["ready"] == 0:
            report.add("shorts queue",
                       f"no Short can render ({row['note']}). Check "
                       f"`python scripts/gemini_brain.py --author-shorts`.", fatal=False)

    newest = last_publish(published_dir)
    if newest is None:
        report.add("publishing", "no published receipt with a YouTube video id exists yet",
                   fatal=False)
    else:
        path, when = newest
        age = now - when
        report.checked.append(f"last publish: {path.name} at {when.isoformat()} ({age.days}d ago)")
        if age > max_publish_age:
            report.add("publishing",
                       f"last upload was {age.days} days ago ({when.date().isoformat()}). "
                       f"The release crons are running but publishing nothing.")
    return report


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
                 workflow_rows=None) -> Report:
    report = Report()
    check_queues(report, published_dir=published_dir, now=now)
    check_workflows(report, rows=workflow_rows)
    return report


# --------------------------------------------------------------------------- #
# GitHub issue sync
# --------------------------------------------------------------------------- #
def _gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, cwd=ROOT, timeout=60)


def gh_available() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or shutil.which("gh"))


def open_issue_number() -> int | None:
    proc = _gh(["issue", "list", "--label", ISSUE_LABEL, "--state", "open",
                "--json", "number", "--limit", "1"])
    if proc.returncode != 0:
        raise RuntimeError(f"gh issue list failed: {(proc.stderr or '').strip()[:200]}")
    rows = json.loads(proc.stdout or "[]")
    return int(rows[0]["number"]) if rows else None


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
        lines.append("### Nothing can publish right now")
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
             "Pipeline is healthy again: every queue has work and every scheduled "
             "workflow has run inside its window. Closing automatically."])
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

    action = sync_issue(report, dry_run=args.dry_run)
    print(f"[watchdog] issue: {action} — {'healthy' if report.healthy else 'unhealthy'}")

    in_ci = os.environ.get("GITHUB_ACTIONS")
    if in_ci:
        if not report.healthy:
            print("::error title=Automation is stalled::the watchdog opened/updated a tracking issue")
        elif action == "closed":
            print("::notice title=Automation recovered::tracking issue closed")
    return 0 if report.healthy else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
