#!/usr/bin/env python3
"""Decisions the production plan job makes, kept here so they can be tested.

Three questions, each of which used to have no answer because production ran one
channel at a time:

* **Which channels does a manual or supervisor dispatch serve?** One dispatch can
  now carry several channels (``channels=prayer4,prayer7``) instead of one run
  per channel.
* **Has this slot already been served?** A slot is served once per channel, by
  whichever trigger arrives first. GitHub delivers the schedule event hours late
  and the supervisor dispatches the missing channels in the meantime, so without
  this check the late event publishes a second video for the same slot.
* **How many channels render at once?** ``PRODUCE_MAX_PARALLEL`` (a repository
  variable), clamped to a sane range. Setting it to ``1`` restores the serial
  matrix without a code change.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRODUCE_WORKFLOW = "produce.yml"
# Channels rendered at the same time when the repository variable is unset.
# Ten legs' work is about nine hours end to end; five lanes bring that to
# roughly two, and keep the shared stock-footage keys near their hourly limit
# rather than far over it (see docs/PARALLEL_PRODUCTION_2026-11-13.md).
DEFAULT_MAX_PARALLEL = 5
# GitHub allows this account 20 concurrent jobs across every workflow.
MAX_PARALLEL_CEILING = 10
# Scheduled publishing. A production slot is the moment work for a release
# becomes due (the workflow's cron); the release goes public this many minutes
# later, on the minute, because the video is uploaded private with a publish
# time and YouTube does the publishing. 0 means off: every upload is public the
# moment it finishes, as before.
#
# Turning it on is one change in two places: set the lead here and move the
# crons in produce.yml earlier by the same amount, so the public times stay
# where they are. The lead must stay SHORTER than the smallest gap between two
# crons (five hours today). Receipts are dated with the public time, and "this
# slot is served" means "a receipt dated at or after the slot": a public time
# that reached the next slot would mark that one served as well and it would
# never be produced. `publish_target` refuses such a lead instead of obeying it.
PUBLISH_LEAD_MINUTES = 0
# A leg that finishes closer to the public time than this publishes at once: a
# late video is never held back and never sent with a time YouTube might refuse.
PUBLISH_MARGIN_MINUTES = 15


def parse_channels(raw: str | None) -> list[str]:
    """``"prayer4, prayer7"`` -> ``["prayer4", "prayer7"]``; order kept, no repeats."""
    from pipeline.channels import normalize_channel_id

    out: list[str] = []
    for token in re.split(r"[\s,]+", str(raw or "").strip()):
        if not token:
            continue
        cid = normalize_channel_id(token)
        if cid not in out:
            out.append(cid)
    return out


def max_parallel(raw: str | None, channel_count: int) -> int:
    """The matrix's ``max-parallel``: never below 1, never above the leg count."""
    try:
        wanted = int(str(raw).strip())
    except (TypeError, ValueError):
        wanted = DEFAULT_MAX_PARALLEL
    if wanted < 1:
        wanted = DEFAULT_MAX_PARALLEL
    return max(1, min(wanted, MAX_PARALLEL_CEILING, max(channel_count, 1)))


def current_slot(now: datetime | None = None) -> datetime | None:
    """The production slot a run starting at ``now`` belongs to."""
    from scripts.automation_monitor import prev_occurrence, workflow_files

    now = now or datetime.now(timezone.utc)
    for filename, _name, crons in workflow_files():
        if filename == PRODUCE_WORKFLOW:
            return prev_occurrence(crons, now)
    return None


def split_served(channels: list[str], now: datetime | None = None,
                 published_dir: Path | None = None) -> tuple[list[str], list[str], datetime | None]:
    """``(still owed, already served, slot)`` for a scheduled run.

    Receipts decide, by the same rule the supervisor uses: a channel is served
    when it has a published long-form dated at or after the slot. If the slot
    cannot be worked out, nothing is treated as served.
    """
    from scripts.scheduler_supervisor import published_channels_since

    slot = current_slot(now)
    if slot is None:
        return list(channels), [], None
    done = published_channels_since(slot, published_dir)
    owed = [c for c in channels if c not in done]
    served = [c for c in channels if c in done]
    return owed, served, slot


def lead_minutes(raw: str | None = None) -> int:
    """The configured lead; ``raw`` (repository variable) overrides the default."""
    if raw is not None and str(raw).strip() != "":
        try:
            return max(0, int(str(raw).strip()))
        except ValueError:
            return PUBLISH_LEAD_MINUTES
    return PUBLISH_LEAD_MINUTES


def next_slot(now: datetime | None = None) -> datetime | None:
    """The first production slot strictly after ``now``."""
    from datetime import timedelta

    from scripts.automation_monitor import prev_occurrence, workflow_files

    now = now or datetime.now(timezone.utc)
    crons = next((c for f, _n, c in workflow_files() if f == PRODUCE_WORKFLOW), None)
    if not crons:
        return None
    current = prev_occurrence(crons, now)
    # Slots sit on a daily grid of whole minutes, so the successor is the first
    # minute in the next two days whose own "current slot" is a different one.
    probe = (current or now).replace(second=0, microsecond=0)
    for _ in range(2 * 24 * 60):
        probe += timedelta(minutes=1)
        found = prev_occurrence(crons, probe)
        if found is not None and found != current and found > now:
            return found
    return None


def publish_target(now: datetime | None = None, lead: int | None = None,
                   margin: int | None = None) -> datetime | None:
    """When a long-form finished at ``now`` should go public, or ``None`` for now.

    ``None`` means "publish immediately": scheduling is off, the slot cannot be
    worked out, the public time is too close or already past, or the lead is not
    safely inside the gap to the next slot.
    """
    from datetime import timedelta

    now = now or datetime.now(timezone.utc)
    lead = lead_minutes() if lead is None else lead
    margin = PUBLISH_MARGIN_MINUTES if margin is None else margin
    if lead <= 0:
        return None
    slot = current_slot(now)
    if slot is None:
        return None
    target = slot + timedelta(minutes=lead)
    following = next_slot(slot)
    if following is None or target >= following:
        return None
    if target - now < timedelta(minutes=margin):
        return None
    return target

