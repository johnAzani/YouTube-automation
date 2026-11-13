"""When a finished long-form goes public: now, or on its slot minute.

Rendering cannot land on a slot. GitHub starts the scheduled run hours late and
a render takes most of an hour, so "public the moment it uploads" means public
whenever the run happened to finish. The alternative is to finish early, upload
private with a publish time, and let YouTube publish on the minute.

This module only answers one question for the upload step and never blocks a
release: any doubt at all (no slot, bad value, too close, an exception) answers
"publish now", which is what every upload did before this existed.

Sources, in order:

1. ``publish_at:`` in the job's own front matter (one video).
2. ``PUBLISH_AT`` in the environment: an explicit time from a manual dispatch
   (``gh workflow run produce.yml -f channels=prayer2 -f publish_at=...``).
   Either may be a time with a timezone, no later than the next production
   slot, or the word ``next-slot``.
3. The production slot plus ``scripts.produce_plan.PUBLISH_LEAD_MINUTES``
   (``PUBLISH_LEAD_MINUTES`` in the environment overrides it; ``0`` is off).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

STAMP = "%Y-%m-%dT%H:%M:%SZ"


def parse_instant(raw: object) -> datetime | None:
    """An aware UTC datetime from an ISO-8601 string, or ``None``."""
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return None
    return when.astimezone(timezone.utc)


#: Words that mean "the next production slot" instead of a written-out time.
NEXT_SLOT_WORDS = frozenset({"next-slot", "next_slot", "next slot", "nextslot"})


def is_next_slot_word(raw: object) -> bool:
    return str(raw or "").strip().lower() in NEXT_SLOT_WORDS


def _explicit_time(raw: str, now: datetime, source: str) -> str | None:
    """Check one requested publish time; ``None`` means publish now."""
    from scripts import produce_plan

    margin = timedelta(minutes=produce_plan.PUBLISH_MARGIN_MINUTES)
    following = produce_plan.next_slot(now)
    if is_next_slot_word(raw):
        if following is None:
            print(f"[publish-schedule] {source}: no production slot is configured; publishing now")
            return None
        if following - now < margin:
            print(f"[publish-schedule] {source}: the next slot ({following.strftime(STAMP)}) is "
                  f"less than {produce_plan.PUBLISH_MARGIN_MINUTES} minutes away; publishing now")
            return None
        return following.strftime(STAMP)
    explicit = parse_instant(raw)
    if explicit is None:
        print(f"[publish-schedule] {source}={raw!r} is not a time with a "
              "timezone; publishing now")
        return None
    if explicit - now < margin:
        print(f"[publish-schedule] {source}: {explicit.strftime(STAMP)} is less than "
              f"{produce_plan.PUBLISH_MARGIN_MINUTES} minutes away; publishing now")
        return None
    # The receipt will be dated with this time, and a channel counts as
    # served for every production slot up to its newest receipt. A time
    # beyond the next slot would therefore cancel that slot's video (and
    # a typo of next week would silence the channel for a week).
    limit = following if following is not None else now + timedelta(hours=12)
    if explicit > limit:
        print(f"::warning title=Publish time too far ahead::{explicit.strftime(STAMP)} "
              f"({source}) is after the next production slot ({limit.strftime(STAMP)}); "
              "publishing now instead")
        return None
    return explicit.strftime(STAMP)


def resolve_longform_publish_at(now: datetime | None = None,
                                environ: dict | None = None,
                                requested: object = None) -> str | None:
    """The ``status.publishAt`` value for this upload, or ``None`` to publish now.

    ``requested`` is a time written on the job itself (``publish_at:`` in its
    front matter). It is held to the same rules as ``PUBLISH_AT`` and wins over
    it: it names one video, the environment names a whole run.
    """
    env = os.environ if environ is None else environ
    now = now or datetime.now(timezone.utc)
    try:
        from scripts import produce_plan

        requested_raw = str(requested or "").strip()
        if requested_raw:
            return _explicit_time(requested_raw, now, "publish_at on the job")
        explicit_raw = str(env.get("PUBLISH_AT") or "").strip()
        if explicit_raw:
            return _explicit_time(explicit_raw, now, "PUBLISH_AT")
        lead = produce_plan.lead_minutes(env.get("PUBLISH_LEAD_MINUTES"))
        target = produce_plan.publish_target(now, lead=lead)
        if target is None:
            if lead > 0:
                print("[publish-schedule] no public time far enough ahead for this slot; "
                      "publishing now")
            return None
        return target.strftime(STAMP)
    except Exception as exc:  # noqa: BLE001 - scheduling must never block a release
        print(f"[publish-schedule] could not work out a public time ({exc!r}); publishing now")
        return None
