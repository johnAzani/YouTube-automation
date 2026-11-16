"""A queued prayer that now reads like the ones beside it, retitled before it publishes.

Measured 16 November 2026, the day the variety gate landed
(``pipeline/title_variety.py``): the gate refuses a title that opens with a word
already beginning a third of a channel's recent need-first titles, or that words
a need the way this channel or another one already has. It is asked when a title
is *written* — by the author (``pipeline/gemini_brain.py``) and by the retitler
that fixes published videos nobody has watched (``pipeline/retitle.py``).

The queue already held titles written before the gate existed. Judged by it
today, **12 queued long-forms across six channels fail**: five on The Guided
Path open with "When" (six of its last eight need-first titles do, and two of
the five are near-duplicates of each other or of another channel's title), two
on The Morning Altar, two on The Midday Watch, and one each on The Midnight
Watch, The Provision Table and The Praise Garden — the last three word a need
almost exactly as another channel does ("When the Path Ahead Is Twisted" /
"... Blocked", "When Every Day Feels Heavy" / "When Every Plan Feels Heavy").

Those are not live videos yet. They are the cheapest titles to fix: nothing has
been published, no viewer has seen them, and the reference in each title stays
word for word. This module finds them and rewrites them through the same
gate-checked path the retitler uses, so a queued title is never replaced by one
the gate would refuse.

What it deliberately does not do:

* it does not touch a published receipt — that is ``pipeline/retitle.py``'s
  job, at most two a channel a day, once the video is a week old and unwatched;
* it does not touch the old form (``"Psalm 23:5 Provision Prayer | ..."``),
  which names no need at all: the retitler replaces those;
* it does not rewrite the script, the slug, the file name, the description or
  the thumbnail line. Only the title changes;
* it never proposes a title itself. The words come from a model, or from a
  person's proposals file, and every one of them is refused by
  ``retitle.title_problems`` and the leave-one-out variety check before it is
  written to disk.

A queued script is bound to its fact-check worksheet by sha256
(``tests/test_factcheck.py`` refuses a worksheet that does not embed the hash of
the script it was built from), so a changed title regenerates the worksheet. A
title change moves no claim — the narration is untouched — so any box a human
has already ticked is carried across rather than silently discarded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

#: Where a regenerated worksheet stops being header and starts being claims.
CLAIMS_MARKER = "## Candidate claims"


@dataclass(frozen=True)
class QueuedTitle:
    """One queued long-form whose title the variety gate would refuse today."""

    path: Path
    job_id: str
    title: str
    reference: str
    channel: str
    problems: tuple[str, ...]


def _channel_name(channel_id: str) -> str:
    from .channel_capabilities import brand_for

    try:
        return brand_for(channel_id).display_name
    except Exception:  # noqa: BLE001 - an unregistered channel still has a title
        return ""


def _rows(*, published_dir: Path | None = None, queue_dir: Path | None = None):
    from .title_variety import listed

    return listed(published_dir=published_dir, queue_dir=queue_dir)


def variety_without(title: str, channel_id: str, *, published_dir: Path | None = None,
                    queue_dir: Path | None = None,
                    rows: list | None = None):
    """The channel's titles as they will read once ``title`` is no longer one of them.

    A title is never judged against itself: "When You Need to Know the Next
    Step" and "When You Need Direction for Your Next Step" are each almost the
    other, and only one of them has to go. The tired opening is counted without
    it too, so the replacement is chosen for the channel that will exist.
    """
    from .title_variety import need_of, names_no_need, variety_for

    wanted = variety_for(channel_id, published_dir=published_dir, queue_dir=queue_dir,
                         rows=rows)
    target = need_of(title, _channel_name(channel_id))
    dropped = False
    own: list[str] = []
    for need in wanted.own:
        if not dropped and need == target:
            dropped = True  # this one occurrence is the title being replaced
            continue
        own.append(need)
    return replace(wanted, own=tuple(n for n in own if n and not names_no_need(n)))


def failing(channel_id: str, *, published_dir: Path | None = None,
            queue_dir: Path | None = None, rows: list | None = None) -> list[QueuedTitle]:
    """This channel's queued long-forms whose titles the gate would refuse now.

    Only approved faith long-forms whose title keeps a scripture reference the
    bundled text can verify: the rewrite has to leave that reference word for
    word. Oldest job first, which is publish order.
    """
    from .channels import channel_for_doc, normalize_channel_id
    from .config import QUEUE_DIR
    from .gemini_brain import extract_scripture_reference
    from .script_doc import parse_script
    from .scripture_text import exists as scripture_exists
    from .title_variety import need_of, names_no_need

    wanted = normalize_channel_id(channel_id)
    name = _channel_name(wanted)
    all_rows = _rows(published_dir=published_dir, queue_dir=queue_dir) if rows is None else rows
    folder = Path(queue_dir or QUEUE_DIR)
    found: list[QueuedTitle] = []
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("short-"):
            continue
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        meta = doc.meta
        if str(meta.get("status") or "").lower() != "approved":
            continue
        if "faith" not in str(meta.get("niche") or "").lower():
            continue
        if str(meta.get("format") or "").lower() == "short":
            continue
        if normalize_channel_id(channel_for_doc(meta)) != wanted:
            continue
        title = " ".join(str(doc.title).split())
        need = need_of(title, name)
        if not need or names_no_need(need):
            continue  # the old form is the retitler's work, not this module's
        reference = extract_scripture_reference(doc)
        if (not reference or not scripture_exists(reference)
                or reference.lower() not in title.lower().replace("–", "-")):
            continue  # the title keeps no passage this module could preserve
        variety = variety_without(title, wanted, rows=all_rows)
        problems = tuple(variety.problems(title, name))
        if problems:
            found.append(QueuedTitle(doc.path, str(doc.id), title, reference, wanted,
                                     problems))
    found.sort(key=lambda queued: queued.job_id)
    return found


def target_for(queued: QueuedTitle):
    """A ``retitle.Target`` for a queued script: no video, no views, no age."""
    from .retitle import Target
    from .script_doc import parse_script

    doc = parse_script(queued.path)
    context = " ".join(str(doc.meta.get(key) or "")
                       for key in ("seo_hook", "thumb_text")).strip()
    return Target(path=queued.path, video_id="", title=queued.title,
                  reference=queued.reference, channel=queued.channel,
                  views=0, age_days=0, context=context[:400])


def apply(path: Path, new_title: str, *, today: datetime | None = None) -> str:
    """Stamp one new title into a queued script: ``"stamped"`` or why it was not.

    The script is re-read from the tree it will be committed on and left
    untouched when its title is no longer the one the new title was written for,
    or when the edit would not read back. ``title_before`` keeps what it was.
    """
    from scripts.sync_published_thumbnails import stamp_frontmatter_field

    from .script_doc import parse_script

    if not path.is_file():
        return "queued script not found"
    original = path.read_text(encoding="utf-8")
    try:
        doc = parse_script(path)
    except Exception as exc:  # noqa: BLE001
        return f"unreadable script: {exc}"
    old_title = " ".join(str(doc.title).split())
    if not old_title:
        return "the script has no title to replace"
    if " ".join(str(new_title).split()) == old_title:
        return "the new title is the old title"
    when = today or datetime.now(timezone.utc)
    day = when.date() if isinstance(when, datetime) else when
    try:
        stamp_frontmatter_field(path, "title", " ".join(str(new_title).split()))
        stamp_frontmatter_field(path, "title_before", old_title)
        stamp_frontmatter_field(path, "queue_title_fixed_at", day.isoformat())
        check = parse_script(path)
        if " ".join(str(check.title).split()) != " ".join(str(new_title).split()):
            raise ValueError("the edited script does not read back as the new title")
        if str(check.meta.get("title_before") or "") != old_title:
            raise ValueError("the edited script does not keep the title it replaces")
    except Exception as exc:  # noqa: BLE001
        path.write_text(original, encoding="utf-8")
        return f"not stamped: {exc}"
    return "stamped"


def worksheet_path(path: Path) -> Path | None:
    """The fact-check worksheet bound to a queued script, if there is one."""
    from scripts import factcheck

    from .script_doc import parse_script

    try:
        doc = parse_script(path)
    except Exception:  # noqa: BLE001
        return None
    dest = factcheck.out_path(doc)
    return dest if dest.exists() else None


def has_human_ticks(text: str) -> bool:
    """True when a person has ticked a box. The instructions' own ``[x]`` is not one."""
    return bool(re.search(r"^- \[x\]", text, re.M))


def refresh_worksheet(path: Path) -> Path | None:
    """Rebuild the worksheet a changed script is bound to, keeping any ticks.

    The binding is the script's sha256 (``tests/test_factcheck.py``), so a new
    title needs a new worksheet. A title moves no claim, so the claims section
    is carried across byte for byte rather than reset: a box a human ticked
    stays ticked. Returns the worksheet written, or ``None``.
    """
    from scripts import factcheck

    from .script_doc import parse_script

    try:
        doc = parse_script(path)
    except Exception as exc:  # noqa: BLE001
        print(f"[queue-titles] {path.name}: worksheet not refreshed ({exc})")
        return None
    dest = factcheck.out_path(doc)
    previous = dest.read_text(encoding="utf-8") if dest.exists() else ""
    text = factcheck.build(doc, path)
    if previous and CLAIMS_MARKER in previous and CLAIMS_MARKER in text:
        head, _, _ = text.partition(CLAIMS_MARKER)
        _, _, claims = previous.partition(CLAIMS_MARKER)
        text = head + CLAIMS_MARKER + claims
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest
