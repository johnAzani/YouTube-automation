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
# crons (four hours since 14 November 2026). Receipts are dated with the public time, and "this
# slot is served" means "a receipt dated at or after the slot": a public time
# that reached the next slot would mark that one served as well and it would
# never be produced. `publish_target` refuses such a lead instead of obeying it.
PUBLISH_LEAD_MINUTES = 0
# A leg that finishes closer to the public time than this publishes at once: a
# late video is never held back and never sent with a time YouTube might refuse.
PUBLISH_MARGIN_MINUTES = 15

# The daily mix. Every slot owes each channel a Short; only one slot a day owes
# it a long-form. Measured on 13 November 2026 across all ten channels: 91 Shorts
# drew 7,513 views and 95 long-forms drew 261 (docs/GROWTH_EVIDENCE_2026-11-14.md),
# so the uploads moved to the format that is watched. The number of uploads a
# day is unchanged (six: it was three long-forms and three Shorts, it is one
# long-form and five Shorts), which keeps each channel inside its own YouTube
# API allowance (an upload costs 1,600 of 10,000 units a day) and uses fewer
# speech requests (a long-form takes two of the ten free ones, a Short one).
#
# Each channel's long-form goes out at the slot that suits what it is for, two
# channels to a slot so no slot carries all ten long renders. The values are
# the UTC ``HH:MM`` of a cron line in produce.yml; a test holds the two together.
LONGFORM_SLOT_UTC: dict[str, str] = {
    "prayer2": "06:14",        # The Morning Altar: 7:14am Nigeria time
    "prayer9": "06:14",        # The Praise Garden
    "prayer7": "10:14",        # The Provision Table: 11:14am
    "prayer10": "10:14",       # The Guided Path
    "prayer3": "14:14",        # The Midday Watch: 3:14pm
    "prayer5": "14:14",        # The Family Altar
    "secret-place": "19:14",   # The Secret Place: 8:14pm, the bedtime prayer
    "prayer6": "19:14",        # The Healing Balm
    "prayer4": "23:14",        # The Midnight Watch: 12:14am
    "prayer8": "23:14",        # The Covenant Shield
}
# The way back: True makes every slot owe every channel a long-form again, as it
# did before 14 November 2026. Remove the 10:14 and 23:14 crons with it, or five
# long-forms a day will be attempted against ten speech requests.
LONGFORM_EVERY_SLOT = False
# A channel whose newest long-form is older than this is owed one at whatever
# slot runs next, so a failed long-form slot costs hours, not a day. A healthy
# channel never reaches it: the slot before its own sees a long-form at most
# about twenty hours old.
LONGFORM_CATCH_UP_HOURS = 26
# A slot must not come up empty. If a Shorts-only slot has no Short to show for
# itself (the render failed, or nothing was ready), the leg makes a long-form
# instead, as every slot did before the mix changed. Not more often than this,
# so a day of broken Shorts yields about three long-forms, the old number, and
# not five.
LONGFORM_FALLBACK_MIN_GAP_HOURS = 7
# A Short this recent counts as the slot's Short even if it was published just
# before the slot began: it is why the pacing guard held the next one back
# (SHORTS_MIN_GAP_HOURS in pipeline/short_release.py).
SHORT_COUNTS_FOR_HOURS = 3


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


def slot_owes_longform(channel_id: str | None, slot: datetime | None) -> bool:
    """Does ``slot`` owe this channel a long-form (as well as a Short)?

    Fails towards the old behaviour: an unknown channel, or a slot that cannot
    be worked out, owes a long-form. A channel must never go without one
    because this table was not kept up.
    """
    from pipeline.channels import normalize_channel_id

    if LONGFORM_EVERY_SLOT or slot is None:
        return True
    wanted = LONGFORM_SLOT_UTC.get(normalize_channel_id(channel_id))
    if not wanted:
        return True
    return slot.astimezone(timezone.utc).strftime("%H:%M") == wanted


def slot_containing(moment: datetime) -> datetime | None:
    """The production slot ``moment`` falls in (``moment`` itself if it is one)."""
    from scripts.automation_monitor import prev_occurrence, workflow_files

    crons = next((c for f, _n, c in workflow_files() if f == PRODUCE_WORKFLOW), None)
    if not crons:
        return None
    return prev_occurrence(crons, moment)


def longform_due(channel_id: str | None, now: datetime | None = None,
                 published_dir: Path | None = None) -> tuple[bool, str]:
    """``(due, why)`` for a production leg at ``now``, asked after its Short step.

    Due when any of these holds, in this order:

    * this is the channel's long-form slot;
    * its newest long-form is older than ``LONGFORM_CATCH_UP_HOURS`` (its own
      slot failed, or it has never published one);
    * the slot has no Short to show for itself and the newest long-form is
      older than ``LONGFORM_FALLBACK_MIN_GAP_HOURS``: a slot never comes up
      empty because Shorts are failing.

    The reason is a sentence for the run's notice.
    """
    from datetime import timedelta

    from pipeline.channels import normalize_channel_id
    from pipeline.short_release import recent_short_published_within
    from scripts.pipeline_watchdog import last_publish_for_channel

    now = now or datetime.now(timezone.utc)
    channel = normalize_channel_id(channel_id)
    slot = current_slot(now)
    if slot_owes_longform(channel, slot):
        when = slot.strftime("%H:%M UTC") if slot else "an unknown slot"
        return True, f"{when} is this channel's long-form slot"
    newest = last_publish_for_channel(channel, published_dir, longform_only=True)
    if newest is None:
        return True, "the channel has no long-form receipt yet"
    age = now - newest[1]
    hours = age.total_seconds() / 3600
    if age > timedelta(hours=LONGFORM_CATCH_UP_HOURS):
        return True, (f"its newest long-form is {hours:.0f} hours old "
                      f"(over {LONGFORM_CATCH_UP_HOURS}), so this slot catches up")
    since_slot = (now - slot).total_seconds() / 3600 if slot else 0.0
    window = max(float(SHORT_COUNTS_FOR_HOURS), since_slot)
    short = recent_short_published_within(hours=window, published_dir=published_dir,
                                          now=now, channel_id=channel)
    own = LONGFORM_SLOT_UTC.get(channel, "its own slot")
    if short is None:
        if age > timedelta(hours=LONGFORM_FALLBACK_MIN_GAP_HOURS):
            return True, (f"no Short was published for this slot, so it gets a long-form "
                          f"instead of nothing (newest long-form is {hours:.0f} hours old)")
        return False, (f"no Short was published for this slot, and a long-form went out "
                       f"{hours:.0f} hours ago (under {LONGFORM_FALLBACK_MIN_GAP_HOURS}); "
                       f"nothing more this slot")
    return False, (f"this slot's Short is published ({short[0].name}); the long-form goes "
                   f"out at {own} UTC (newest is {hours:.0f} hours old)")


def main(argv: list[str] | None = None) -> int:
    """``--longform-due <channel>``: print the decision and set a step output."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--longform-due", dest="longform_due", metavar="CHANNEL",
                        help="say whether a leg for CHANNEL starting now owes a long-form")
    parser.add_argument("--force", default="",
                        help="'true' makes the answer yes (the owner's manual switch)")
    args = parser.parse_args(argv)
    if not args.longform_due:
        parser.print_help()
        return 2
    if str(args.force).strip().lower() in {"1", "true", "yes"}:
        due, why = True, "a long-form was asked for by hand"
    else:
        try:
            due, why = longform_due(args.longform_due)
        except Exception as exc:  # noqa: BLE001 - never lose a long-form to this check
            due, why = True, f"the check could not run ({exc!r}), so nothing is held back"
    print(f"long-form due for {args.longform_due}: {'yes' if due else 'no'} ({why})")
    title = "Long-form due" if due else "Shorts-only slot"
    print(f"::notice title={title} ({args.longform_due})::{why}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"longform={'true' if due else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
