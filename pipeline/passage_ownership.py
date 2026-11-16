"""Which channel prays which passage — the network's own passage ledger.

Why this exists. Ten channels run by one program are a "coordinated network of
channels" to YouTube's spam policy, and the pattern that policy names is "many
similar videos across linked channels". The clearest version of it is two
channels praying the same verse: the same words, the same need, the same
invitation, uploaded a day apart under two different names.

The seasonal lists have known this since 14 November 2026
(``pipeline/seasonal.py``: "No passage is given to two channels, and none is on
another channel's evergreen list or roadmap"). Nothing held the *roadmaps* to
it: a test checks that no seasonal passage is shared, but no test ever compared
one channel's roadmap with another's, or with what the channels have actually
made. So the lists drifted — on 16 November 2026, twenty passages were already
prayed on more than one channel, and ninety unwritten roadmap entries still
named a passage another channel had prayed.

What this module does is read the ledger and say so, in the two places that
matter:

* the brain's next-prayer choice (``GeminiBrain.select_next_scripture``) steps
  over a roadmap passage another channel already prays, so the drift stops
  growing without anyone deciding which channel owns a passage;
* ``scripts/channel_protection.py`` counts the overlaps that already exist, so
  the ones needing a decision are listed rather than quietly accumulated.

Nothing here changes a passage that is already queued or live: those are the
owner's to reassign, and the count is what asks for that decision.

Passages are compared the way ``pipeline/evergreen_shorts.py`` compares them:
the same book and chapter, and the same first verse or one of them naming the
whole chapter. ``"Psalm 91"`` and ``"Psalm 91:6"`` are the same passage to a
listener.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

import yaml

from .channels import normalize_channel_id
from .config import PUBLISHED_DIR, QUEUE_DIR
from .evergreen_shorts import reference_parts, same_passage
from .short_script import SPEC_DIR
from .short_release import SHORTS_QUEUE_DIR

#: A passage as the comparer sees it: (book, chapter, first verse or None).
Parts = tuple[str, int, "int | None"]

_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def _field(head: "str | Mapping", *names: str) -> str:
    """The first of `names` present in a front-matter head, as a string.

    Takes either the raw front-matter text or the mapping
    :func:`_front_matter` makes of it, because the same field is read from both
    a long-form's markdown and a Short's JSON or YAML.
    """
    if isinstance(head, Mapping):
        for name in names:
            value = str(head.get(name) or "").strip().strip("'\"")
            if value:
                return value
        return ""
    for name in names:
        match = re.search(rf"^{name}:\s*[\"']?(.*?)[\"']?\s*$", head, re.M)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return ""


def _front_matter(path: Path) -> dict[str, str]:
    """A markdown file's front matter as a plain mapping (no YAML types wanted)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    match = _FRONT.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line[:1].isspace():
            continue
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _label(parts: Parts) -> str:
    """``("psalm", 91, 4)`` back to ``"Psalm 91:4"``, for the report."""
    book, chapter, verse = parts
    name = "Psalm" if book == "psalm" else book.title()
    return f"{name} {chapter}" + (f":{verse}" if verse else "")


@dataclass(frozen=True)
class Passage:
    """One passage one channel has a video of, and where it was read from."""

    channel: str
    reference: str
    parts: Parts
    #: ``published`` / ``queued`` for a long-form prayer, ``short published`` /
    # ``short queued`` / ``short spec`` for a Short.
    source: str
    #: A long-form's job id, or a Short's key.
    job: str = ""
    title: str = ""


def _longforms(folder: Path, source: str) -> list[Passage]:
    """The passages named in long-form titles, read from their front matter.

    A long-form carries its reference in its title, not in a field of its own:
    the title is what the writer was given the passage in, and what a viewer
    reads.
    """
    if not folder.is_dir():
        return []
    out: list[Passage] = []
    for path in sorted(folder.glob("*.md")):
        if path.name.startswith("short-"):
            continue
        head = _front_matter(path)
        if "faith" not in _field(head, "niche").lower():
            continue
        if _field(head, "format").lower() == "short":
            continue
        title = _field(head, "title")
        parts = reference_parts(title) if title else None
        if parts is None:
            continue
        out.append(Passage(channel=normalize_channel_id(_field(head, "channel") or None),
                           reference=_label(parts), parts=parts, source=source,
                           job=_field(head, "id") or path.name[:4], title=title))
    return out


def _shorts(folder: Path, pattern: str, source: str,
            read: Callable[[Path], Mapping]) -> list[Passage]:
    """The passages of a channel's Shorts, from one of the three places they live."""
    if not folder.is_dir():
        return []
    out: list[Passage] = []
    for path in sorted(folder.glob(pattern)):
        try:
            data = read(path)
        except Exception:  # noqa: BLE001 — a broken file is not the ledger's business
            continue
        if not isinstance(data, Mapping):
            continue
        scripture = str(data.get("scripture") or "").strip()
        if not scripture and isinstance(data.get("psalm"), int):
            scripture = f"Psalm {data['psalm']}"
        if not scripture:
            # An old published Short has no spec file: the reference is its title.
            scripture = str(data.get("title") or "")
        parts = reference_parts(scripture)
        if parts is None:
            continue
        out.append(Passage(channel=normalize_channel_id(data.get("channel")),
                           reference=scripture, parts=parts, source=source,
                           job=str(data.get("key") or path.stem),
                           title=str(data.get("title") or "")))
    return out


def _json(path: Path) -> Mapping:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _yaml(path: Path) -> Mapping:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def passages(*, published_dir: Path | None = None, queue_dir: Path | None = None,
             spec_dir: Path | None = None,
             shorts_queue_dir: Path | None = None) -> list[Passage]:
    """Every passage any channel has a video of: long-form and Short, live or waiting.

    Read from five places because no single one holds them all, exactly as
    ``evergreen_shorts.used_references`` reads a channel's Shorts.
    """
    published = Path(published_dir or PUBLISHED_DIR)
    return (_longforms(published, "published")
            + _longforms(Path(queue_dir or QUEUE_DIR), "queued")
            + _shorts(published, "short-*.md", "short published", _front_matter)
            + _shorts(Path(spec_dir or SPEC_DIR), "short-*.json", "short spec", _json)
            + _shorts(Path(shorts_queue_dir or SHORTS_QUEUE_DIR), "*.yml",
                      "short queued", _yaml))


def ledger(rows: Sequence[Passage] | None = None, **dirs) -> dict[str, set[Parts]]:
    """Channel -> every passage it has a video of."""
    index: dict[str, set[Parts]] = {}
    for row in (rows if rows is not None else passages(**dirs)):
        index.setdefault(row.channel, set()).add(row.parts)
    return index


def prayed_elsewhere(channel_id: str, *, rows: Sequence[Passage] | None = None,
                     index: Mapping[str, set[Parts]] | None = None, **dirs) -> set[Parts]:
    """Every passage a channel *other* than this one already has a video of."""
    wanted = normalize_channel_id(channel_id)
    table = index if index is not None else ledger(rows, **dirs)
    found: set[Parts] = set()
    for channel, parts in table.items():
        if channel != wanted:
            found |= parts
    return found


def overlaps(channel_id: str, *, rows: Sequence[Passage] | None = None,
             index: Mapping[str, set[Parts]] | None = None, **dirs) -> list[Passage]:
    """This channel's videos whose passage another channel also has a video of."""
    wanted = normalize_channel_id(channel_id)
    elsewhere = prayed_elsewhere(wanted, rows=rows, index=index, **dirs)
    if not elsewhere:
        return []
    mine = [row for row in (rows if rows is not None else passages(**dirs))
            if row.channel == wanted]
    return [row for row in mine
            if any(same_passage(row.parts, other) for other in elsewhere)]


def roadmap_ahead(channel_id: str, taken_ids: Iterable[str] = ()) -> list[dict]:
    """The channel's roadmap entries with no long-form yet, in roadmap order."""
    from scripts.continuous_research import roadmap_for_channel

    taken = {str(i) for i in taken_ids}
    return [row for row in roadmap_for_channel(channel_id)
            if str(row.get("id")) not in taken and str(row.get("scripture") or "").strip()]


def taken_longform_ids(*, queue_dir: Path | None = None,
                       published_dir: Path | None = None) -> set[str]:
    """Job ids already used by a long-form, queued or published.

    Roadmap ids are global, so this is deliberately repository-wide, exactly as
    ``GeminiBrain._existing_job_ids`` reads it.
    """
    ids: set[str] = set()
    for folder in (Path(queue_dir or QUEUE_DIR), Path(published_dir or PUBLISHED_DIR)):
        if folder.is_dir():
            ids |= {path.name[:4] for path in folder.glob("*.md")}
    return ids


def split_roadmap(channel_id: str, taken_ids: Iterable[str] = (), *, rows=None, index=None,
                  **dirs) -> tuple[list[dict], list[dict]]:
    """The unwritten roadmap in two stable halves.

    The first holds entries whose passage no other channel has a video of; the
    second holds the ones another channel already prays. Each half keeps the
    roadmap's own order, so a channel whose list is clean is unaffected and one
    that is not simply prays its own passages first.
    """
    return own_first(roadmap_ahead(channel_id, taken_ids), channel_id,
                     rows=rows, index=index, **dirs)


def own_first(entries: Sequence[Mapping], channel_id: str, *, rows=None, index=None,
              **dirs) -> tuple[list, list]:
    """`entries` in two stable halves: passages no other channel prays, then the rest.

    The order inside each half is the order it was given — roadmap order, or
    whatever the performance feedback made of it — so this only ever steps over
    a shared passage, never reorders the channel's own.
    """
    elsewhere = prayed_elsewhere(channel_id, rows=rows, index=index, **dirs)
    mine: list = []
    theirs: list = []
    for entry in entries:
        parts = reference_parts(str(entry.get("scripture") or ""))
        if parts is not None and any(same_passage(parts, other) for other in elsewhere):
            theirs.append(entry)
        else:
            mine.append(entry)
    return mine, theirs


def collisions(channel_id: str, taken_ids: Iterable[str] = (), *, rows=None, index=None,
               **dirs) -> list[dict]:
    """The unwritten roadmap entries whose passage another channel already prays."""
    return split_roadmap(channel_id, taken_ids, rows=rows, index=index, **dirs)[1]
