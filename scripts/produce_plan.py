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
