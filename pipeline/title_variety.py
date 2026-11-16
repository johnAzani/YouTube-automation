"""Keep long-prayer titles from settling into one mould.

What was measured on 16 November 2026 (docs/PROTECTION_AND_REVENUE_RESEARCH_2026-11-16.md, §10):

* the older long-prayer titles are one sentence with the passage swapped
  ("Psalm 143:8 Morning Prayer | The Morning Altar", 15 times on that channel);
* the titles written since 14 November lead with the listener's need, which is
  better, but 30 of the 99 open with the word "When" (seven of nine on The
  Guided Path) and seven of the first eight retitled videos did too: one
  mould being replaced by another;
* the same need is worded the same way on two channels ("When You Don't Know
  What to Do" on The Morning Altar and The Midday Watch).

YouTube's monetisation policy refuses content that "feels interchangeable from
video to video" and its reviewers read titles; its spam policy covers many
similar videos across linked channels. Neither gives a number, so the marks
below are this repository's own.

This module reads the long-prayer titles already published and queued and says
what a new title must stay away from:

* an opening word that already begins a third of the channel's recent titles
  (half, for a word that names the kind of prayer: "Bedtime Prayer for ...");
* a need already worded almost the same way on this channel;
* a need already worded almost the same way on another channel;
* the old form, which opens with the scripture reference and names no need.

It is used when a title is written (``pipeline/retitle.py`` and the long-form
author in ``pipeline/gemini_brain.py``) and when the channels are measured
(``scripts/channel_protection.py``). It reads files only.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

#: A channel's most recent need-first titles that are read for a tired opening.
RECENT = 15
#: Fewer uses than this and an opening is not a habit yet.
MIN_USES = 3
#: The repository's own mark, not a YouTube figure: an opening word that begins
#: a third or more of a channel's recent titles may not begin another.
OPENING_SHARE = 1 / 3
#: Words that say what kind of prayer the video is ("Bedtime Prayer for
#: Anxiety", "Morning Prayer for Courage"). People type them into search, and
#: YouTube's policy allows a series whose videos each have their own subject,
#: so they are held to a looser mark: half of the recent titles, not a third.
KIND_WORDS = frozenset(
    "prayer prayers morning sunrise midday noon afternoon evening night bedtime "
    "midnight family healing".split())
KIND_SHARE = 1 / 2
#: Two needs sharing this fraction of their meaningful words read as one title.
ALIKE = 0.6

_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
_REFERENCE = re.compile(
    r"(?:[1-3] )?[A-Z][a-z]+(?: of [A-Z][a-z]+)? \d+(?::\d+(?:[-–]\d+)?)?")
_SMALL = frozenset(
    "a an and are as at be by for from his in is it my of on our that the thy to we with "
    "you your prayer".split())


@dataclass(frozen=True)
class Listed:
    """One long-prayer title, published or waiting in the queue."""
    channel: str
    title: str
    day: str            # YYYY-MM-DD for a published video, "" for a queued one
    queued: bool


def _field(head: str, name: str) -> str:
    match = re.search(rf"^{name}:[ \t]*(.*?)[ \t]*$", head, re.M)
    if not match:
        return ""
    value = re.sub(r"\s+#.*$", "", match.group(1)).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].replace('\\"', '"')
    return value.strip()


def listed(*, published_dir: Path | None = None, queue_dir: Path | None = None) -> list[Listed]:
    """Every long-form faith title: published ones oldest first, then the queue."""
    from .channels import normalize_channel_id
    from .config import PUBLISHED_DIR, QUEUE_DIR

    out: list[Listed] = []
    for folder, queued in ((PUBLISHED_DIR if published_dir is None else published_dir, False),
                           (QUEUE_DIR if queue_dir is None else queue_dir, True)):
        if not Path(folder).is_dir():
            continue
        rows: list[Listed] = []
        for path in sorted(Path(folder).glob("*.md")):
            if path.name.startswith("short-"):
                continue
            match = _FRONT.match(path.read_text(encoding="utf-8", errors="replace"))
            if not match:
                continue
            head = match.group(1)
            if "faith" not in _field(head, "niche").lower():
                continue
            if _field(head, "format").lower() == "short":
                continue
            title = _field(head, "title")
            if not title:
                continue
            day = "" if queued else (_field(head, "published_at")
                                     or _field(head, "published_on"))[:10]
            rows.append(Listed(normalize_channel_id(_field(head, "channel") or None),
                               title, day, queued))
        out += sorted(rows, key=lambda row: row.day)
    return out


def need_of(title: str, channel_name: str = "") -> str:
    """The words a title leads with, before the scripture reference or the bar.

    ``"When Money Is Tight: Philippians 4:19 | The Provision Table"`` gives
    ``"When Money Is Tight"``. The old form, ``"Psalm 23:5 Provision Prayer |
    The Provision Table"``, gives ``"Psalm 23:5 Provision Prayer"``: a colon
    inside a reference is not the colon that ends a need.
    """
    text = " ".join(str(title or "").replace("–", "-").split())
    if channel_name and text.lower().endswith(f"| {channel_name}".lower()):
        text = text[: -len(channel_name) - 1].rstrip(" |")
    text = text.split(" | ")[0]
    return re.split(r":\s", text, maxsplit=1)[0].strip()


def names_no_need(need: str) -> bool:
    """True for the old form: the title opens with the scripture reference."""
    return bool(_REFERENCE.match(need.strip()))


def opening(need: str) -> str:
    """The first word of a need, lower-cased: what makes a row of titles look alike.

    A leading "A", "An" or "The" is passed over: "The Lord Is My Rock" and "The
    Battle Is Not Yours" do not open alike.
    """
    words = [word.lower() for word in re.findall(r"[A-Za-z']+", need)]
    while len(words) > 1 and words[0] in {"a", "an", "the"}:
        words = words[1:]
    return words[0] if words else ""


def _mark(word: str) -> float:
    return KIND_SHARE if word in KIND_WORDS else OPENING_SHARE


def _words(need: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z']+", need.lower())) - _SMALL


def alike(one: str, other: str) -> bool:
    """True when two needs share most of their meaningful words."""
    first, second = _words(one), _words(other)
    if not first or not second:
        return False
    return len(first & second) / len(first | second) >= ALIKE


@dataclass(frozen=True)
class Variety:
    """What one channel's next title must stay away from."""
    channel: str
    own: tuple[str, ...] = ()        # this channel's need-first needs, oldest first
    elsewhere: tuple[str, ...] = ()  # need-first needs on the other channels

    @property
    def recent(self) -> tuple[str, ...]:
        return self.own[-RECENT:]

    def tired_openings(self) -> dict[str, int]:
        """``{opening word: uses}`` for openings a new title may not use here."""
        recent = self.recent
        counts = Counter(opening(need) for need in recent)
        return {word: uses for word, uses in counts.most_common()
                if word and uses >= MIN_USES and uses / len(recent) >= _mark(word)}

    def with_title(self, title: str, channel_name: str = "") -> "Variety":
        """This channel after one more title: two titles written in one run differ too."""
        return replace(self, own=(*self.own, need_of(title, channel_name)))

    def problems(self, title: str, channel_name: str = "") -> list[str]:
        """Why a title would make this channel, or the channels together, look templated."""
        need = need_of(title, channel_name)
        if not need:
            return ["the title names no need"]
        if names_no_need(need):
            return ["the title opens with the scripture reference; it must open with the "
                    "listener's need or the promise"]
        found: list[str] = []
        first = opening(need)
        tired = self.tired_openings()
        if first in tired:
            found.append(
                f"{tired[first]} of this channel's last {len(self.recent)} titles already "
                f"open with '{first.capitalize()}'; open this one another way")
        for mine in self.own:
            if alike(need, mine):
                found.append(f"too close to a title already on this channel: '{mine}'")
                break
        for theirs in self.elsewhere:
            if alike(need, theirs):
                found.append(f"too close to a title already in use: '{theirs}'")
                break
        return found

    def prompt_block(self) -> str:
        """Lines for a prompt: this channel's titles, and how not to begin."""
        if not self.own:
            return ""
        lines = ["Titles already on this channel (the new one must not read like any of them):"]
        lines += [f"  {need}" for need in self.recent]
        tired = self.tired_openings()
        if tired:
            words = ", ".join(f"'{word.capitalize()}'" for word in tired)
            lines.append(
                f"Too many of them begin the same way. Do NOT begin the new title with {words}. "
                "Begin another way: the promise itself (\"No Weapon Formed Against You\"), "
                "what is asked (\"Strength for a Long Afternoon\", \"Peace Over a Troubled "
                "Home\"), who it is for (\"For a Child Who Is Sick\"), or the hour "
                "(\"Before You Sleep Tonight\").")
        return "\n".join(lines) + "\n"


def variety_for(channel_id: str, *, published_dir: Path | None = None,
                queue_dir: Path | None = None, rows: list[Listed] | None = None) -> Variety:
    """Read the titles and return what ``channel_id``'s next title must avoid."""
    from .channel_capabilities import brand_for
    from .channels import normalize_channel_id

    wanted = normalize_channel_id(channel_id)
    rows = listed(published_dir=published_dir, queue_dir=queue_dir) if rows is None else rows
    own: list[str] = []
    elsewhere: list[str] = []
    for row in rows:
        try:
            name = brand_for(row.channel).display_name
        except Exception:  # noqa: BLE001 - an unregistered channel still has a title
            name = ""
        need = need_of(row.title, name)
        if not need or names_no_need(need):
            continue
        (own if row.channel == wanted else elsewhere).append(need)
    return Variety(channel=wanted, own=tuple(own), elsewhere=tuple(dict.fromkeys(elsewhere)))
