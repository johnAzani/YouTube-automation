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
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STATE = ROOT / "content" / "monitor" / "dispatched.json"

# Dispatch a slot this long after it was due. GitHub's scheduler is routinely 10-40
# minutes late, so anything shorter races it and risks a *duplicate* run — which for
# produce.yml means a duplicate upload.
DISPATCH_AFTER = timedelta(minutes=90)
# How long a dropped slot stays worth recovering. This used to be a flat 6 hours for
# every workflow, and that single constant is why the night of 5-6 November published
# nothing: measured over 1-6 November, this repo's scheduled runs land a median of
# ~57 minutes late, p95 ~3.4 hours, and the brain's 03:14 slot is delivered at ~10:53
# — 7 hours 39 minutes late, every single day. The supervisor itself is cron-driven
# and was delivered ~4 times a day despite asking for 96, so by the time it looked,
# the slot it was built to recover had expired out of its own window. A slot is now
# recoverable until its **successor is due** (i.e. for one occurrence period), which
# is the only interval in which "this occurrence did not happen" still means
# something. upload-shaped work keeps a tighter leash: publishing hours late is worse
# than waiting for the next slot.
USEFUL_WINDOW: dict[str, timedelta] = {"produce.yml": timedelta(hours=6)}
MAX_SLOT_WINDOW = timedelta(hours=24)
# At most one dispatch per workflow per pass (see `_newest_per_workflow`), so the cap
# only has to be larger than the roster of dispatchable workflows.
MAX_DISPATCHES = 8
# Silence thresholds, from this repo's own delivery record (1-6 Nov: 14 scheduled
# deliveries in 16 active hours; inter-delivery gap median 57 min, p90 ~3.3 h, max
# 3.4 h). 2 hours is worth saying out loud on a run; 4 hours is outside anything the
# scheduler has ever done while healthy and belongs in the issue tracker.
SILENCE_WARN_MINUTES = 120
SILENCE_ALARM_MINUTES = 240
# A delivery this much later than the slot it serves is "late", not "on time".
LATE_SLOT_MINUTES = 120
SCHEDULE_HEALTH = ROOT / "content" / "monitor" / "schedule-health.json"
# A dispatch is not a success. On 2 November the 07:14 produce slot was
# dispatched at 08:59 and the run then failed; treating the slot as settled would
# have left the channel with no video until the next day.
#
# Three attempts, because a failed run is often a bug that has since been fixed:
# attempt one finds it, attempt two proves the fix, and the third covers a retry
# that failed for an unrelated reason. The cap still stops a permanently broken
# workflow from hammering the queue every fifteen minutes.
MAX_ATTEMPTS_PER_SLOT = 3

# A whole workflow run may contain ten sequential channel jobs. Its age is not a
# job timeout: cancelling at 210 minutes interrupted healthy late matrix legs.
# Produce's per-job timeout is 240 minutes; wait an additional 10 minutes and
# inspect every active job before considering a cancellation. Unknown job state is
# never evidence that an upload is safe to cancel.
JOB_CAP = timedelta(minutes=240)
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


def _attempt_cap(workflow: str) -> int:
    """Attempts allowed per slot. Produce needs one per channel, plus a retry each."""
    if workflow == "produce.yml":
        return 2 * len(_channels()) + 1
    return MAX_ATTEMPTS_PER_SLOT


def published_channels_since(slot: datetime, published_dir: Path | None = None) -> set[str]:
    """Channels with a *published* long-form receipt at or after `slot`.

    The schedule's unit of work is a video per channel, so a produce run is only
    evidence that the slot was served if a receipt exists for each channel. Judging
    that by "a produce run happened" is how one leg's completion silently certified
    the other channel's missing video.
    """
    from pipeline.channels import channel_for_doc
    from pipeline.config import PUBLISHED_DIR
    from pipeline.script_doc import parse_script

    directory = published_dir or PUBLISHED_DIR
    done: set[str] = set()
    if not directory.is_dir():
        return done
    for path in directory.glob("*.md"):
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        fmt = str(getattr(doc, "format", "") or doc.meta.get("format", "")).strip().lower()
        if fmt != "longform" or not str(doc.meta.get("youtube_video_id") or "").strip():
            continue
        stamps = [str(doc.meta.get(key) or "") for key in ("published_at", "published_on")]
        when = None
        for stamp in stamps:
            try:
                when = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                break
            except ValueError:
                continue
        if when is None:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= slot:
            done.add(channel_for_doc(doc.meta))
    return done


def _slot_window(workflow: str, crons: list[str], slot: datetime) -> timedelta:
    """How long `slot` stays worth recovering: until its successor is due.

    The previous occurrence before `slot` is exactly one period earlier, so
    `slot - prev` is that period (a daily cron -> 24h, three-a-day -> 8h). The
    flat 6-hour rule this replaces expired *before* the supervisor's own next
    delivery on this repo, which is how a missed night went unrepaired.
    """
    from scripts.automation_monitor import prev_occurrence

    window = USEFUL_WINDOW.get(workflow)
    if window is not None:
        return window
    previous = prev_occurrence(crons, slot - timedelta(minutes=1))
    if previous is None:
        return DISPATCH_AFTER * 2
    period = slot - previous
    return min(max(period, DISPATCH_AFTER * 2), MAX_SLOT_WINDOW)


#: Files whose contents *are* the code a workflow runs. `content/` is deliberately
#: absent: Actions rewrites `content/monitor/*.json` every few hours on its own, and
#: if those renewals counted, a broken workflow would retry forever with nothing fixed.
_CODE_ROOTS = ("pipeline", "scripts")
_CODE_EXTRA = ("requirements.txt", ".github/actions")


def code_fingerprint(workflow: str | None = None, _cache: dict[str, str] = {}) -> str:
    """A stable id for the code a workflow would run right now.

    A commit date cannot answer this question here: the supervisor runs in a
    depth-1 checkout, where the tip commit *is* the whole history and looks like it
    touched every file. A content hash can, and it is what gets compared.
    """
    cache_key = workflow or ""
    if cache_key in _cache:
        return _cache[cache_key]
    digest = hashlib.sha256()
    for name in _CODE_ROOTS:
        root = ROOT / name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
    for name in _CODE_EXTRA:
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    if workflow:
        wf = ROOT / ".github" / "workflows" / workflow
        if wf.is_file():
            digest.update(wf.read_bytes())
    _cache[cache_key] = digest.hexdigest()[:16]
    return _cache[cache_key]


def code_changed_since(entry: dict, workflow: str | None = None) -> bool:
    """Has the code changed since that attempt was made?

    Attempt budgets exist to stop a permanently broken workflow from hammering the
    queue. They must not stop a *fixed* one: on the morning of 6 November the brain
    burned all three attempts against a retired Gemini model, the fix landed at
    08:30, and the ledger would have refused to run it again until the next day's
    slot. Different code means different failures, so the budget is renewed — once
    per fingerprint, so the loop guard still holds.
    """
    if not entry.get("at"):
        return False
    known = str(entry.get("code_id") or "")
    current = code_fingerprint(workflow)
    if not known:
        return True           # attempt predates the fingerprint; renew once and stamp
    return known != current


def _cron_map() -> dict[str, list[str]]:
    """{workflow_file: crons} — the schedule each workflow actually declares."""
    from scripts.automation_monitor import workflow_files

    return {name: crons for name, _display, crons in workflow_files()}


def _newest_per_workflow(rows: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Keep only the newest missing slot per workflow — catching up publishes once.

    Three missed produce slots are three uploads if each is dispatched, and two of
    them would be hours stale besides. The newest missed slot is the one a run
    should serve; the older ones are superseded by it, not queued behind it. The
    same holds for authoring and replying: one pass catches up everything that is
    due.
    """
    newest: dict[str, tuple[str, str]] = {}
    for workflow, slot in rows:
        current = newest.get(workflow)
        if current is None or slot > current[1]:
            newest[workflow] = (workflow, slot)
    return sorted(newest.values(), key=lambda row: row[1])


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
    inflight: set[str] = set()
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
        if str(run.get("status")) in {"queued", "in_progress", "waiting", "requested", "pending"}:
            inflight.add(path)

    out: list[tuple[str, str]] = []
    for filename, _name, crons in workflow_files():
        if filename in NEVER_DISPATCH:
            continue
        slot = prev_occurrence(crons, now)
        if slot is None:
            continue
        if now < slot + DISPATCH_AFTER:
            continue
        if now > slot + _slot_window(filename, crons, slot):
            continue
        last_run = latest.get(filename)
        if filename in inflight:
            continue          # a run is working on it right now; never race it
        if filename == "produce.yml":
            # The $0.00 lock, evaluated per channel: one channel exhausting its
            # 10-request speech allowance must never hold back another channel's
            # independent GCP quota pool, and an empty-queue channel is a brain
            # supply fault rather than a produce dispatch target.
            from scripts.automation_monitor import active_quota_cooldown

            if active_quota_cooldown(now) is not None:
                continue
            done = published_channels_since(slot)
            missing = _unserved_produce_channels(done, now=now)
            if not missing:
                continue
            out.append((filename, slot.isoformat()))
            continue
        if last_run is not None and last_run >= slot:
            continue          # it ran for this slot; nothing to do
        out.append((filename, slot.isoformat()))
    return _newest_per_workflow(out)


def _channels() -> list[str]:
    from pipeline.channels import scheduled_channels

    return list(scheduled_channels())


def _channel_has_supply(channel_id: str) -> bool:
    try:
        from pipeline.short_release import select_next_queued_short
        from pipeline.supply import publishable_longform

        return bool(
            publishable_longform(channel_id=channel_id)
            or select_next_queued_short(channel_id=channel_id) is not None
        )
    except Exception:  # noqa: BLE001
        return True


def _unserved_produce_channels(
    done: set[str],
    *,
    now: datetime | None = None,
    attempted: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Servable channels that still owe a receipt for this slot, least-tried first."""
    from scripts.automation_monitor import active_quota_cooldown

    channels = _channels()
    supplied = [c for c in channels if _channel_has_supply(c)]
    pool = supplied or channels
    ready = [
        c for c in pool
        if c not in done and active_quota_cooldown(now, channel_id=c) is None
    ]
    prior = list(attempted or ())
    counts = {c: prior.count(c) for c in ready}
    return [
        c for _idx, c in sorted(
            enumerate(ready),
            key=lambda pair: (counts.get(pair[1], 0), pair[0]),
        )
    ]


def _safe_runs() -> list[dict]:
    try:
        from scripts.automation_monitor import fetch_runs

        return fetch_runs()
    except Exception:  # noqa: BLE001
        return []


FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out", "startup_failure"}

#: Failures that are not the code's fault: the *service* was unavailable. Google's
#: gemini-3.8-flash answered 503 "high demand" for hours on 6 November, and every
#: brain attempt in that window was burned by an outage the repo could not fix.
#: Once the budget is spent, such a slot keeps retrying on a timer — a fixed code
#: fingerprint cannot describe an outage that ends by itself.
#: Deliberately narrow on *generic* errors. The evidence is now a run's full annotation
#: text, which also carries runner boilerplate ("Node.js 20 is deprecated…"), so a loose
#: marker such as "500" or "internal" would read an ordinary failure as an outage.
#: "no candidate model" and "supply empty" are deliberately absent: they are the
#: wrapper around *every* authoring failure, including the deterministic ones a retry
#: cannot fix (retired model, wrong branding, missing front matter). Those are handled
#: by `code_changed_since` instead.
UPSTREAM_MARKERS = ("service unavailable", "503", "high demand", "upstream capacity",
                    "unavailable —", "deadline exceeded", "timed out",
                    # Added 7 November, from the annotations the supervisor was
                    # already fetching and then ignoring: a 429 answered "daily free
                    # tier quota reached", a busy fleet answered "busy after retries",
                    # and neither matched a marker, so the slot was marked served by a
                    # run that had failed. Each is a state that ends by itself — the
                    # allowance resets at midnight Pacific, capacity returns in
                    # minutes — which is exactly what the retry timer exists for.
                    "quota", "resource_exhausted", "rate limit", "busy after retries")
UPSTREAM_RETRY_AFTER = timedelta(minutes=30)
UPSTREAM_MAX_ATTEMPTS = 8


def is_upstream_failure(entry: dict, evidence: str = "") -> bool:
    """Did that attempt fail because the service was down rather than the code?

    Two sources, because the ledger alone cannot answer it: `entry["result"]` records
    what the *dispatch* said ("dispatched"), not why the run later failed. The first
    version of this checked only that string and so never fired — the brain kept
    sitting out the outage until the next day. `evidence` is the failed run's own
    annotations, quoted from the API.
    """
    text = f"{entry.get('result') or ''} {evidence or ''}".lower()
    return any(marker in text for marker in UPSTREAM_MARKERS)


def run_annotations(run_id: Any, _cache: dict[str, str] = {}) -> str:
    """Every annotation on a run's jobs, as one searchable string (cached per pass)."""
    from scripts.automation_monitor import repo_slug

    key = str(run_id)
    if key in _cache:
        return _cache[key]
    text = ""
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo_slug()}/actions/runs/{run_id}/jobs"],
            capture_output=True, text=True, timeout=60)
        jobs = json.loads(proc.stdout or "{}").get("jobs", [])[:4]
        for job in jobs:
            resp = subprocess.run(
                ["gh", "api", f"repos/{repo_slug()}/check-runs/{job.get('id')}/annotations"],
                capture_output=True, text=True, timeout=60)
            for ann in json.loads(resp.stdout or "[]") or []:
                if isinstance(ann, dict):
                    text += f" {ann.get('title', '')} {ann.get('message', '')}"
    except Exception:  # noqa: BLE001
        text = ""
    _cache[key] = text
    return text


def last_failure_evidence(workflow: str, runs: list[dict], after: str = "") -> str:
    """The annotations of that workflow's most recent failure (empty when unknown)."""
    failed = [r for r in runs
              if r.get("path") == workflow and r.get("conclusion") in FAILED_CONCLUSIONS]
    if after:
        try:
            cutoff = datetime.fromisoformat(str(after))
            failed = [r for r in failed
                      if datetime.fromisoformat(str(r.get("created_at") or "").replace("Z", "+00:00")) >= cutoff]
        except (TypeError, ValueError):
            pass
    if not failed:
        return ""
    latest = max(failed, key=lambda r: str(r.get("created_at") or ""))
    return run_annotations(latest.get("id"))


def upstream_retry_due(entry: dict, now: datetime, evidence: str = "") -> bool:
    """May a spent slot be tried again because the outage may have ended?

    Cooldown-priced, not open-ended: at most one attempt per 30 minutes and at most
    8 in total, so an outage that lasts all day cannot hammer the queue either.
    """
    if not is_upstream_failure(entry, evidence):
        return False
    if int(entry.get("attempts", 0)) >= UPSTREAM_MAX_ATTEMPTS:
        return False
    try:
        last = datetime.fromisoformat(str(entry.get("at") or ""))
    except (TypeError, ValueError):
        return False
    return (now - last) >= UPSTREAM_RETRY_AFTER


def _failed_dispatches(state: dict, latest: dict[str, tuple[datetime, str | None]],
                       now: datetime, evidence_lookup=None) -> list[tuple[str, str]]:
    """Ledger entries whose dispatched run has finished badly and can be retried."""
    from scripts.automation_monitor import active_quota_cooldown

    produce_cooldown = active_quota_cooldown(now)
    crons_by_workflow = _cron_map()
    out: list[tuple[str, str]] = []
    for key, entry in state.items():
        if "@" not in key:
            continue
        workflow, slot = key.rsplit("@", 1)
        if workflow in NEVER_DISPATCH:
            continue
        if workflow == "produce.yml" and produce_cooldown is not None:
            continue
        try:
            slot_at = datetime.fromisoformat(slot)
            dispatched_at = datetime.fromisoformat(entry.get("at", ""))
        except (TypeError, ValueError):
            continue
        if now < slot_at + DISPATCH_AFTER:
            continue
        if now > slot_at + _slot_window(workflow, crons_by_workflow.get(workflow, []), slot_at):
            continue
        if int(entry.get("attempts", 1)) >= _attempt_cap(workflow):
            # A slot whose attempts were burned by code that has since been fixed must
            # be retryable: the failures came from older code, not from the workflow.
            # Likewise an outage that has since cleared (see UPSTREAM_MARKERS).
            evidence = evidence_lookup(workflow, entry) if evidence_lookup else ""
            if not code_changed_since(entry, workflow) and not upstream_retry_due(
                    entry, now, evidence):
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


DISPATCH_SPAWN_GRACE = timedelta(minutes=2)


def _inflight_workflows(runs: list[dict]) -> set[str]:
    """Workflow filenames that currently have a queued or running job."""
    active: set[str] = set()
    for run in runs:
        path = (run.get("path") or "").split("/")[-1]
        if not path:
            continue
        if str(run.get("status")) in {"queued", "in_progress", "waiting", "requested", "pending"}:
            active.add(path)
    return active


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


def dispatch(
    workflow: str,
    slot: str | None = None,
    *,
    now: datetime | None = None,
    attempted: list[str] | tuple[str, ...] | None = None,
) -> tuple[bool, str]:
    """Dispatch a workflow, returning (ok, message).

    ``produce.yml`` is special in three ways:

    1. **One channel per dispatch.** Legs share ``content-state``, which allows
       only one pending run at a time.
    2. **Receipts, not runs, decide.** `published_channels_since()` is the only
       evidence that a channel's video exists.
    3. **Per-channel supply, quota isolation, and rotation.** Channels with no
       queued content or in active quota cooldown are skipped, and unattempted
       channels go ahead of previously attempted ones so a failing first channel
       never starves the rest.
    """
    if workflow == "produce.yml":
        if slot:
            try:
                since = datetime.fromisoformat(slot)
            except ValueError:
                since = (now or datetime.now(timezone.utc)) - timedelta(hours=24)
        else:
            since = (now or datetime.now(timezone.utc)) - timedelta(hours=24)
        missing = _unserved_produce_channels(
            published_channels_since(since),
            now=now,
            attempted=attempted,
        )
        if not missing:
            return True, "every servable channel already published (or in quota cooldown) for this slot"
        channel = missing[0]
        proc = subprocess.run(
            ["gh", "workflow", "run", workflow, "-f", f"channel={channel}"],
            capture_output=True, text=True, cwd=ROOT, timeout=120,
        )
        if proc.returncode == 0:
            rest = [c for c in missing[1:]]
            note = f"dispatched {channel}"
            if rest:
                note += f"; {', '.join(rest)} next pass (content-state takes one pending run)"
            return True, note[:300]
        return False, (proc.stderr or proc.stdout or "gh workflow run failed").strip()[:240]
    proc = subprocess.run(["gh", "workflow", "run", workflow], capture_output=True,
                          text=True, cwd=ROOT, timeout=120)
    if proc.returncode == 0:
        return True, "dispatched"
    return False, (proc.stderr or proc.stdout or "gh workflow run failed").strip()[:200]


def _run_jobs(run_id: int) -> list[dict] | None:
    """Read all job pages; an API failure must not trigger cancellation."""
    from scripts.automation_monitor import repo_slug

    try:
        proc = subprocess.run(
            ["gh", "api", "--paginate", "--slurp",
             f"repos/{repo_slug()}/actions/runs/{run_id}/jobs?per_page=100"],
            capture_output=True, text=True, cwd=ROOT, timeout=60,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or "GitHub jobs API failed")
        pages = json.loads(proc.stdout)
        if not isinstance(pages, list) or any(not isinstance(p, dict) or
                not isinstance(p.get("jobs"), list) or
                any(not isinstance(job, dict) for job in p["jobs"]) for p in pages):
            raise ValueError("invalid GitHub jobs response")
        return [job for page in pages for job in page["jobs"]]
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as exc:
        print(f"[supervisor] cannot inspect jobs for run {run_id}; not cancelling: {exc}")
        return None


def stuck_runs(now: datetime | None = None, runs=None) -> list[dict]:
    """Find production runs with all active jobs beyond their job timeout.

    GitHub can report a matrix workflow as queued even while a job is running.
    Do not infer a hung job from the workflow's age or a missing jobs response.
    A run with another fresh or undated active job is never cancelled.
    """
    now = now or datetime.now(timezone.utc)
    payload = runs if runs is not None else _safe_runs()
    rows = payload.get("workflow_runs", payload) if isinstance(payload, dict) else payload
    out = []
    for run in rows or []:
        name = (run.get("name") or "").strip()
        path = (run.get("path") or "").split("/")[-1]
        if path != "produce.yml" and not (not path and name == "Produce video"):
            continue  # other workflows have different job timeouts and matrices
        if str(run.get("status")) not in {"queued", "in_progress"} or not run.get("id"):
            continue
        started = run.get("run_started_at") or run.get("created_at")
        try:
            run_started = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
            if run_started.tzinfo is None or now - run_started <= JOB_CAP + STUCK_GRACE:
                continue
        except (TypeError, ValueError):
            continue
        jobs = _run_jobs(run["id"])
        if jobs is None:
            continue
        # Unknown states must not be ignored while deciding to cancel an entire
        # matrix run: they may represent a job which is still doing useful work.
        known_statuses = {"queued", "in_progress", "completed", "waiting", "requested", "pending"}
        if any(job.get("status") not in known_statuses for job in jobs):
            continue
        active = [job for job in jobs if job.get("status") == "in_progress"]
        if not active:
            continue
        starts = []
        for job in active:
            try:
                stamp = datetime.fromisoformat(str(job.get("started_at", "")).replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    raise ValueError("missing timezone")
                starts.append(stamp)
            except (TypeError, ValueError):
                break
        if len(starts) != len(active) or any(now - stamp <= JOB_CAP + STUCK_GRACE for stamp in starts):
            continue
        oldest = min(starts)
        out.append({"id": run["id"], "workflow": name, "started": oldest.isoformat(),
                    "minutes": int((now - oldest).total_seconds() // 60)})
    return out


def cancel_run(run_id) -> tuple[bool, str]:
    from scripts.automation_monitor import repo_slug

    proc = subprocess.run(["gh", "api", "--method", "POST",
                           f"repos/{repo_slug()}/actions/runs/{run_id}/cancel"],
                          capture_output=True, text=True, cwd=ROOT, timeout=120)
    if proc.returncode == 0:
        return True, "cancelled"
    return False, (proc.stderr or proc.stdout or "cancel failed").strip()[:200]


def schedule_health(now: datetime | None = None, runs=None) -> dict:
    """How quiet the repo is, and how late each delivery actually was.

    Silence is the fault this whole file exists for and could not previously
    describe: on the night of 5-6 November nothing ran between 02:52 and 07:52 and
    every verdict in `content/monitor/status.json` still read OK, because each one
    was last computed hours earlier by a workflow that itself never started. Silence
    is a property of the repo, not of any single workflow, so it is measured here,
    across every run, and reported by whatever pass happens to be alive.
    """
    from scripts.automation_monitor import fetch_runs, prev_occurrence, workflow_files

    now = now or datetime.now(timezone.utc)
    if runs is None:
        runs = _safe_runs()
    rows = runs.get("workflow_runs", runs) if isinstance(runs, dict) else runs
    rows = rows or []

    by_workflow: dict[str, list[datetime]] = {}
    newest: datetime | None = None
    for run in rows:
        path = (run.get("path") or "").split("/")[-1]
        stamp = run.get("created_at")
        if not path or not stamp:
            continue
        try:
            when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            continue
        by_workflow.setdefault(path, []).append(when)
        if newest is None or when > newest:
            newest = when

    silence = int((now - newest).total_seconds() // 60) if newest else None

    late: list[dict] = []
    on_time: list[dict] = []
    for filename, name, crons in workflow_files():
        slot = prev_occurrence(crons, now)
        if slot is None:
            continue
        stamps = sorted(t for t in by_workflow.get(filename, []) if t >= slot)
        if not stamps:
            continue                      # missed, not late — this is dispatch work
        lag = int((stamps[0] - slot).total_seconds() // 60)
        row = {"workflow": filename, "name": name, "slot": slot.isoformat(),
               "ran_at": stamps[0].isoformat(), "late_minutes": lag}
        (late if lag >= LATE_SLOT_MINUTES else on_time).append(row)

    return {
        "generated_at": now.isoformat(),
        "silence_minutes": silence,
        "last_run_at": newest.isoformat() if newest else None,
        "delivered_late": sorted(late, key=lambda r: -r["late_minutes"]),
        "on_time": on_time,
        "warn_minutes": SILENCE_WARN_MINUTES,
        "alarm_minutes": SILENCE_ALARM_MINUTES,
    }


def report_schedule_health(health: dict) -> None:
    """Say it on the run — an annotation nobody has to go looking for."""
    silence = health.get("silence_minutes")
    late = health.get("delivered_late") or []
    if silence is not None and silence >= SILENCE_ALARM_MINUTES:
        worst = ", ".join(f"{r['name']} +{r['late_minutes']}m" for r in late[:4]) or "—"
        print(f"::error title=Schedule stalled::no workflow has started for "
              f"{silence} minutes ({silence // 60}h{silence % 60:02d}m). GitHub delivered "
              f"no cron event in that time; every overdue job is being dispatched by this "
              f"pass. Deliveries that did arrive were late: {worst}.")
    elif silence is not None and silence >= SILENCE_WARN_MINUTES:
        print(f"::warning title=Schedule quiet::no workflow has started for {silence} "
              f"minutes. Normal here is under an hour; this pass recovers anything overdue.")
    for row in late[:5]:
        print(f"[supervisor] late delivery: {row['name']} served "
              f"{row['slot']} at {row['ran_at']} (+{row['late_minutes']}m)")
    if silence is not None and silence < SILENCE_WARN_MINUTES:
        print(f"[supervisor] scheduler healthy: last start {silence} min ago")


def _schedule_health_material(health: dict) -> dict:
    """Fields whose change warrants a repo commit (ignores wall-clock ticks)."""
    silence = health.get("silence_minutes")
    warn = int(health.get("warn_minutes") or SILENCE_WARN_MINUTES)
    alarm = int(health.get("alarm_minutes") or SILENCE_ALARM_MINUTES)
    band = (
        "alarm" if (silence is not None and silence >= alarm)
        else "warn" if (silence is not None and silence >= warn)
        else "ok"
    )
    return {
        "band": band,
        "delivered_late": health.get("delivered_late") or [],
        "on_time": health.get("on_time") or [],
    }


def save_schedule_health(health: dict) -> None:
    SCHEDULE_HEALTH.parent.mkdir(parents=True, exist_ok=True)
    if SCHEDULE_HEALTH.is_file():
        try:
            existing = json.loads(SCHEDULE_HEALTH.read_text(encoding="utf-8"))
            if _schedule_health_material(existing) == _schedule_health_material(health):
                return
        except (OSError, ValueError):
            pass
    SCHEDULE_HEALTH.write_text(json.dumps(health, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")


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

    run_history = runs if runs is not None else _safe_runs()
    latest = _latest_runs(run_history)
    inflight = _inflight_workflows(run_history)

    def evidence_for(workflow: str, entry: dict) -> str:
        """Why that workflow's most recent failure happened, from its own annotations."""
        return last_failure_evidence(workflow, run_history, str(entry.get("at") or ""))
    crons_by_workflow = _cron_map()

    # Two kinds of work: slots that produced no run at all, and slots whose
    # *dispatched* run has since failed. The second kind looks healthy to
    # `due_but_missing` (a run exists after the slot) which is exactly how today's
    # produce failure would have been left for tomorrow.
    candidates = list(missing)
    for workflow, slot in _failed_dispatches(state, latest, now,
                                             evidence_lookup=evidence_for):
        if (workflow, slot) not in candidates:
            candidates.append((workflow, slot))
    candidates = _newest_per_workflow(candidates)

    from scripts.automation_monitor import active_quota_cooldown

    produce_cooldown = active_quota_cooldown(now)

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
        if now < slot_at + DISPATCH_AFTER:
            continue
        if now > slot_at + _slot_window(workflow, crons_by_workflow.get(workflow, []), slot_at):
            continue
        attempts = int(entry.get("attempts", 1))
        finished = latest.get(workflow)
        if finished is not None and finished[1] == "success" \
                and finished[0].isoformat() >= entry.get("at", ""):
            reason = "its dispatched run succeeded"
        elif workflow == "produce.yml" and produce_cooldown is not None:
            reason = "waiting for daily free-tier TTS quota reset"
        elif attempts >= MAX_ATTEMPTS_PER_SLOT:
            reason = f"already dispatched {attempts}x for this slot; not trying again"
        else:
            reason = "waiting for its dispatched run to appear"
        result["skipped"].append({"workflow": workflow, "slot": slot, "reason": reason})

    for workflow, slot in candidates:
        key = f"{workflow}@{slot}"
        previous = state.get(key)
        attempts = int(previous.get("attempts", 1)) if previous else 0
        if workflow in inflight:
            result["skipped"].append({"workflow": workflow, "slot": slot,
                                      "reason": "a run is already in progress or queued"})
            continue
        if previous:
            finished = latest.get(workflow)
            if workflow != "produce.yml" and finished is not None \
                    and finished[1] == "success" \
                    and finished[0].isoformat() >= previous.get("at", ""):
                # For produce this shortcut is wrong: a successful run for one
                # channel says nothing about the other's video, and it would leave
                # that channel with no publish and no second dispatch.
                result["skipped"].append({"workflow": workflow, "slot": slot,
                                          "reason": "its dispatched run succeeded"})
                continue
            if attempts >= _attempt_cap(workflow):
                if code_changed_since(previous, workflow):
                    # The code that failed has been replaced. Run the new code.
                    attempts = 0
                    print(f"[supervisor] {workflow}: attempts renewed — the code changed "
                          f"since the last attempt ({str(previous.get('code_id') or '?'):8} -> "
                          f"{code_fingerprint(workflow)}), so those failures came from "
                          f"older code")
                elif upstream_retry_due(previous, now, evidence_for(workflow, previous)):
                    # The outage, not the code, burned those attempts.
                    print(f"[supervisor] {workflow}: retrying after an upstream "
                          f"failure (attempt {attempts + 1}/{UPSTREAM_MAX_ATTEMPTS}, "
                          f"cooldown {int(UPSTREAM_RETRY_AFTER.total_seconds() // 60)}m)")
                else:
                    result["skipped"].append({"workflow": workflow, "slot": slot,
                                              "reason": f"already dispatched {attempts}x for this "
                                                        f"slot; not trying again"})
                    continue
            try:
                dispatched_at = datetime.fromisoformat(str(previous.get("at") or "").replace("Z", "+00:00"))
            except ValueError:
                dispatched_at = None
            if (
                dispatched_at is not None
                and timedelta(0) <= (now - dispatched_at) < DISPATCH_SPAWN_GRACE
                and (finished is None or finished[0] < dispatched_at)
            ):
                result["skipped"].append({"workflow": workflow, "slot": slot,
                                          "reason": "waiting for its dispatched run to appear"})
                continue
        if len(result["dispatched"]) >= MAX_DISPATCHES:
            result["skipped"].append({"workflow": workflow, "slot": slot,
                                      "reason": "per-pass dispatch limit reached"})
            continue
        if dry_run:
            result["dispatched"].append({"workflow": workflow, "slot": slot,
                                         "result": "would dispatch"})
            continue
        prior_attempted = list((previous or {}).get("attempted_channels") or [])
        import inspect

        params = inspect.signature(dispatch).parameters
        if "now" in params and "attempted" in params:
            ok, message = dispatch(workflow, slot, now=now, attempted=prior_attempted)
        else:
            ok, message = dispatch(workflow, slot)
        entry_out: dict = {
            "at": now.isoformat(),
            "result": message,
            "attempts": attempts + 1,
            "code_id": code_fingerprint(workflow),
        }
        if workflow == "produce.yml":
            dispatched_ch = ""
            if ok and message.startswith("dispatched "):
                dispatched_ch = message[len("dispatched "):].split(";", 1)[0].strip()
            if dispatched_ch:
                prior_attempted.append(dispatched_ch)
            if prior_attempted:
                entry_out["attempted_channels"] = prior_attempted
        state[key] = entry_out
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

    try:
        health = schedule_health(now, runs)
        result["health"] = health
        report_schedule_health(health)
        if not dry_run:
            save_schedule_health(health)
    except Exception as exc:  # noqa: BLE001 - the dispatch pass must survive this
        result["failed"].append({"workflow": "-", "reason": f"schedule health failed: {exc}"})

    if not dry_run:
        save_state(state)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch scheduled workflows that never fired.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--health-only", action="store_true",
                        help="report scheduler silence/lateness and dispatch nothing")
    args = parser.parse_args(argv)

    if args.health_only:
        health = schedule_health()
        report_schedule_health(health)
        if not args.dry_run:
            save_schedule_health(health)
        if args.json:
            print(json.dumps(health, indent=2))
        return 0

    result = supervise(dry_run=args.dry_run, runs=_safe_runs())
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
            health = result.get("health") or {}
            if health.get("silence_minutes") is not None:
                fh.write(f"- scheduler silence: **{health['silence_minutes']} min** since the "
                         f"last workflow started (`{health.get('last_run_at')}`)\n")
            for row in (health.get("delivered_late") or [])[:5]:
                fh.write(f"- late delivery: `{row['workflow']}` served {row['slot']} "
                         f"+{row['late_minutes']} min\n")
            fh.write("\n")
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
