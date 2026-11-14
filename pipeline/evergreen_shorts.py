"""Shorts that stand on their own: which passage a channel's next one is about.

Until 14 November 2026 a Short existed only as the companion of a long-form: one
long-form published, one Short authored from the same passage. That tied the
number of Shorts to the number of long-forms, and it tied their subjects to the
long-form roadmap's order. The view counts say the Shorts are the format that is
watched (91 Shorts drew 7,513 views against 261 for 95 long-forms) and that the
passages people already know by heart lead among them (Psalm 27, 91, 23, 100:4,
Numbers 6:24-26, Isaiah 54:17). See docs/GROWTH_EVIDENCE_2026-11-14.md; the lead
of well-known passages is an observation over a few days, not a proven law.

So a channel now publishes one long-form and five Shorts a day, and four of the
five have no long-form behind them. This module answers "about what?", in order:

1. ``EVERGREEN``: for each channel, passages a listener is likely to know and to
   search for, chosen for what that channel is for. No passage appears on two
   channels' lists.
2. The channel's own long-form roadmap, ahead of the long-forms: a passage the
   channel will make a long-form of later can have its Short today. When the
   long-form arrives its companion Short already exists and is not made twice.

Nothing here writes a word of a Short. The brain authors each one from the
reference alone (``GeminiBrain.generate_standalone_short``); this is the list of
references and the rule for not repeating one.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

# Most familiar first: the order is the order they are authored and published in.
EVERGREEN: dict[str, tuple[str, ...]] = {
    # The Secret Place: the bed, the dark, the mind that will not stop.
    "secret-place": (
        "Romans 8:28", "Psalm 56:3", "Psalm 55:22", "John 14:1-3", "Matthew 6:34",
        "Psalm 94:19", "Isaiah 41:13", "Psalm 62:1-2", "Isaiah 30:15",
        "Psalm 139:7-10", "Philippians 4:8", "Matthew 28:20", "Psalm 119:165",
        "Psalm 145:18", "Psalm 4:4",
    ),
    # The Morning Altar: the first minutes of the day.
    "prayer2": (
        "Psalm 23:1", "Jeremiah 29:11", "Psalm 121:1-2", "Isaiah 60:1",
        "Psalm 51:10", "Isaiah 43:18-19", "Psalm 37:4", "Matthew 5:14-16",
        "2 Corinthians 5:17", "Deuteronomy 31:8", "Psalm 46:5", "Psalm 90:14",
        "Psalm 113:3", "Psalm 16:8", "Psalm 138:8",
    ),
    # The Midday Watch: the middle of the working day, strength running low.
    "prayer3": (
        "Nehemiah 8:10", "Matthew 19:26", "Zechariah 4:6", "Deuteronomy 31:6",
        "1 Corinthians 10:13", "Romans 12:12", "Psalm 29:11", "Psalm 31:24",
        "Mark 6:31", "2 Corinthians 4:16-18", "Psalm 118:14", "Psalm 68:19",
        "Psalm 138:3", "Colossians 3:2", "Psalm 119:28",
    ),
    # The Midnight Watch: the hour of the long fight.
    "prayer4": (
        "Romans 8:37", "1 John 4:4", "James 4:7", "Psalm 50:15", "Mark 11:23-24",
        "Joel 2:25", "Luke 10:19", "Deuteronomy 28:7", "Matthew 18:18",
        "Job 22:28", "Psalm 138:7", "Psalm 126:1-3", "2 Timothy 4:18",
        "Colossians 2:14-15", "Psalm 124:7",
    ),
    # The Family Altar: the home, the marriage, the children.
    "prayer5": (
        "Matthew 6:9-13", "1 Corinthians 13:4-7", "Psalm 133:1", "Psalm 91:10",
        "Mark 10:13-16", "Ephesians 6:1-4", "3 John 1:4", "Acts 2:39",
        "Luke 15:20-24", "Mark 10:9", "Isaiah 44:3", "Psalm 68:6",
        "Genesis 18:19", "Isaiah 59:21", "Psalm 101:2",
    ),
    # The Healing Balm: the body and the heart that hurt.
    "prayer6": (
        "1 Peter 2:24", "John 16:33", "Mark 5:34", "Proverbs 17:22",
        "Psalm 91:16", "2 Corinthians 1:3-4", "Isaiah 58:8", "Matthew 8:17",
        "Exodus 23:25", "Romans 8:11", "Luke 8:50", "Deuteronomy 7:15",
        "Psalm 119:50", "Hosea 6:1", "Isaiah 57:18-19",
    ),
    # The Provision Table: work, bread, money, an open door.
    "prayer7": (
        "Matthew 7:7-8", "Malachi 3:10", "Luke 6:38", "Matthew 6:26",
        "Deuteronomy 8:18", "Proverbs 3:9-10", "Psalm 81:10", "Deuteronomy 28:8",
        "2 Kings 4:1-7", "Isaiah 1:19", "1 Corinthians 16:9", "Psalm 35:27",
        "Genesis 26:12-13", "Psalm 132:15", "Haggai 2:8",
    ),
    # The Covenant Shield: fear, danger, the journey.
    "prayer8": (
        "Psalm 23:4", "Psalm 91:4", "Psalm 91:7", "Psalm 121:3-4", "Psalm 118:6",
        "2 Kings 6:16-17", "John 10:28-29", "Isaiah 54:14", "Psalm 20:1-2",
        "Exodus 12:13", "Psalm 5:11", "Psalm 16:1", "Psalm 97:10",
        "Proverbs 1:33", "Psalm 31:20",
    ),
    # The Praise Garden: thanks and praise.
    "prayer9": (
        "Psalm 100:1-2", "Psalm 139:14", "Philippians 4:4", "Psalm 47:1",
        "1 Chronicles 16:34", "Psalm 18:3", "Psalm 22:3", "Revelation 4:11",
        "Psalm 33:1-3", "Luke 1:46-49", "Psalm 104:33", "Psalm 147:1",
        "Psalm 66:1-4", "1 Chronicles 29:11-13", "Isaiah 25:1",
    ),
    # The Guided Path: the decision, the next step.
    "prayer10": (
        "John 14:6", "Ecclesiastes 3:1", "Micah 6:8", "Isaiah 55:8-9",
        "Jeremiah 29:13", "Psalm 119:133", "John 10:27", "Proverbs 19:21",
        "Proverbs 14:12", "Psalm 48:14", "Psalm 31:3", "Jeremiah 10:23",
        "Psalm 25:9", "James 4:13-15", "Psalm 107:7",
    ),
}

# Fewer than this many passages left for a channel is said out loud, in the run
# that noticed: at four a day it is about two days' warning that the lists above
# (or the roadmap) need more passages.
LOW_POOL = 8


def reference_parts(reference: str) -> tuple[str, int, int | None] | None:
    """``"Psalm 91:4-7"`` -> ``("psalm", 91, 4)``; ``"Psalm 23"`` -> ``("psalm", 23, None)``.

    The book is lower-cased with its number kept (``"1 corinthians"``), "Psalms"
    reads as "Psalm", and only the first verse of a range is kept: two Shorts
    that begin at the same verse are the same Short to a listener.
    """
    from .gemini_brain import _BOOK_RE

    match = _BOOK_RE.search(str(reference or "").replace("–", "-"))
    if not match:
        return None
    book = re.sub(r"\s+", " ", match.group(1)).strip().lower()
    if book == "psalms":
        book = "psalm"
    verse = re.match(r"\d+", match.group(3) or "")
    return book, int(match.group(2)), int(verse.group(0)) if verse else None


def same_passage(a: tuple[str, int, int | None] | None,
                 b: tuple[str, int, int | None] | None) -> bool:
    """Same book and chapter, and the same first verse or one of them is the whole chapter."""
    if a is None or b is None:
        return False
    if a[:2] != b[:2]:
        return False
    return a[2] is None or b[2] is None or a[2] == b[2]


def used_references(channel_id: str, *, spec_dir: Path | None = None,
                    queue_dir: Path | None = None,
                    published_dir: Path | None = None) -> set[tuple[str, int, int | None]]:
    """Every passage this channel already has a Short of: written, queued or published.

    Read three ways because no single place holds them all. An old published
    Short has no spec file, and a spec written before the ``scripture`` field
    existed names only its psalm.
    """
    import yaml

    from .channels import normalize_channel_id
    from .config import PUBLISHED_DIR
    from .short_release import SHORTS_QUEUE_DIR
    from .short_script import SPEC_DIR

    wanted = normalize_channel_id(channel_id)
    found: set[tuple[str, int, int | None]] = set()

    def note(reference: str) -> None:
        parts = reference_parts(reference)
        if parts is not None:
            found.add(parts)

    for path in sorted(Path(spec_dir or SPEC_DIR).glob("short-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if normalize_channel_id(data.get("channel")) != wanted:
            continue
        if str(data.get("scripture") or "").strip():
            note(str(data["scripture"]))
        elif isinstance(data.get("psalm"), int):
            note(f"Psalm {data['psalm']}")
    for path in sorted(Path(queue_dir or SHORTS_QUEUE_DIR).glob("*.yml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if normalize_channel_id(data.get("channel")) == wanted:
            note(str(data.get("scripture") or ""))
    for path in sorted(Path(published_dir or PUBLISHED_DIR).glob("short-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        owner = re.search(r"^channel:\s*(\S+)", text, re.M)
        if normalize_channel_id(owner.group(1) if owner else None) != wanted:
            continue
        title = re.search(r"^title:\s*(.+)$", text, re.M)
        if title:
            note(title.group(1))
    return found


def _roadmap_ahead(channel_id: str, taken_ids: Iterable[str]) -> list[str]:
    """The channel's roadmap passages that have no long-form yet, best tier first."""
    from scripts.continuous_research import roadmap_for_channel

    taken = set(taken_ids)
    rows = [row for row in roadmap_for_channel(channel_id)
            if str(row.get("id")) not in taken and str(row.get("scripture") or "").strip()]
    # Stable sort: "Tier 1" rows first, the roadmap's own order within a tier.
    rows.sort(key=lambda row: 0 if "tier 1" in str(row.get("search_volume_tier", "")).lower() else 1)
    return [str(row["scripture"]).replace("–", "-") for row in rows]


def candidates(channel_id: str, *, taken_longform_ids: Iterable[str] = (),
               used: set[tuple[str, int, int | None]] | None = None,
               ) -> list[tuple[str, str]]:
    """``[(reference, source)]`` this channel can still make a standalone Short of.

    ``source`` is ``"evergreen"`` or ``"roadmap"``. Evergreen passages come first.
    A passage the channel already has a Short of is left out, and so is a second
    candidate for a passage listed earlier.
    """
    from .channels import normalize_channel_id

    channel = normalize_channel_id(channel_id)
    seen = set(used_references(channel) if used is None else used)
    out: list[tuple[str, str]] = []
    pools = (
        ("evergreen", EVERGREEN.get(channel, ())),
        ("roadmap", _roadmap_ahead(channel, taken_longform_ids)),
    )
    for source, references in pools:
        for reference in references:
            parts = reference_parts(reference)
            if parts is None or any(same_passage(parts, other) for other in seen):
                continue
            seen.add(parts)
            out.append((reference, source))
    return out
