"""Measure, every day, how much the channels look made from one template.

Why this exists. Three YouTube rules bear on ten channels run by one program
(read 16 November 2026, quoted in docs/PROTECTION_AND_REVENUE_RESEARCH_2026-11-16.md):

* the monetisation policy refuses channels whose "content feels interchangeable
  from video to video" or "looks like it was made with a template";
* the spam policy covers "coordinated networks of channels" and names
  "using automated tools or AI to churn out high volumes of similar content
  with minimal changes" as a reason to suspend monetisation or end a channel;
* a termination is of the owner, not of one channel.

None of them gives a number, so nothing here is "YouTube's limit". These are
the repository's own measures of the things those rules describe, taken from
what was actually published (`content/published/`) and written
(`content/shorts-scripts/`), so that a drift toward sameness is seen the day it
starts and a fix can be shown to have worked:

* uploads per channel per day (the "high volumes" half);
* how many of a channel's recent Short titles say nothing of their own after
  the bar (the same question `short_release.hook_adds_nothing` asks when a
  title is built);
* titles used more than once on a channel;
* the long-prayer titles, which earn the hours that count: how many still carry
  the old form that opens with the passage, whether one opening word begins too
  many of a channel's titles, and needs worded almost alike on two channels
  (`pipeline/title_variety.py` holds the marks and refuses the same things when
  a title is written);
* prayer sentences, other than scripture and the closing invitation, spoken
  on more than one channel (the "coordinated network" half);
* passages prayed on more than one channel — the clearest form of "many
  similar videos across linked channels", counted from the network's own
  passage ledger (``pipeline/passage_ownership.py``), together with the
  unwritten roadmap entries that still name one of them.

    python -m scripts.channel_protection          # table, and a step summary in Actions
    python -m scripts.channel_protection --json   # the same as JSON

It reports and never fails a run for what it finds: a figure over its mark is
a `::warning::`, because publishing is not what is broken. A crash is not
hidden and exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.gemini_brain import _BOOK_RE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PUBLISHED_DIR = ROOT / "content" / "published"
QUEUE_DIR = ROOT / "content" / "queue"
SPEC_DIR = ROOT / "content" / "shorts-scripts"
SHORTS_QUEUE_DIR = ROOT / "content" / "shorts-queue"

#: A channel's most recent Shorts whose titles are read.
RECENT_TITLES = 20
#: Fewer than this and a share means nothing yet.
MIN_TITLES = 8
#: The repository's own mark, not a YouTube figure: more than a quarter of the
#: recent titles saying nothing of their own is reported.
WEAK_TITLE_SHARE = 0.25
#: A Short's title is `<what the channel says> | <its own hook>`. The words before
#: the bar are set per channel (`Brand.short_title_template`) and never vary, so
#: this is the share of a channel's recent Short titles built on one frame above
#: which it is said out loud. Three quarters, not one: the frame is the channel's
#: own wording, and the point is that it is the *only* one it has.
FRAME_SHARE = 0.75
#: A sentence shorter than this is too common a phrase to count as shared.
MIN_SENTENCE_WORDS = 8
#: Days averaged for the upload rate.
RATE_DAYS = 7

_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
#: A scripture reference, as written in a title. Book-aware on purpose: the
#: first version accepted any capitalised word before a number, so
#: "Say This 1 Peter 5:7 Prayer Before You Sleep" read its passage as "This 1",
#: and 19 published Short titles were measured against the wrong passage (§
#: "the measure undercounted"). `gemini_brain._BOOK_RE` is the one list of book
#: names in the repository, and `evergreen_shorts.reference_parts` reads it too.
_REFERENCE = _BOOK_RE


@dataclass(frozen=True)
class Receipt:
    channel: str
    title: str
    day: str          # YYYY-MM-DD (UTC)
    short: bool


@dataclass
class Row:
    channel: str
    name: str
    long_last_day: int = 0
    shorts_last_day: int = 0
    per_day: float = 0.0
    titles_read: int = 0
    weak_titles: int = 0
    repeated_titles: int = 0
    shared_sentences: int = 0
    #: Long-prayer titles: published ones still in the old form, the need-first
    #: titles read (published and queued), the opening used too often, needs
    #: worded almost as another channel words one, and queued titles the
    #: variety gate would refuse today (``pipeline/queue_titles.py``).
    old_form_titles: int = 0
    need_titles: int = 0
    tired_opening: str = ""
    tired_opening_uses: int = 0
    needs_alike_elsewhere: list[str] = field(default_factory=list)
    queued_refused: int = 0
    #: Passages prayed on more than one channel (``pipeline/passage_ownership.py``):
    #: this channel's videos whose passage another channel also has a video of,
    #: its unwritten roadmap entries that name one of those passages, and whether
    #: the prayer the brain would have written next for it is one of them.
    passages_shared: int = 0
    roadmap_shared: int = 0
    next_prayer_shared: int = 0
    #: The frame a Short's title is built on — everything before the bar, less the
    #: reference. ``frame_titles`` of the ``titles_read`` recent titles use the
    #: channel's most-used one, and ``frames_used`` is how many it has in total.
    frame_titles: int = 0
    frames_used: int = 0
    frame_text: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def weak_share(self) -> float:
        return self.weak_titles / self.titles_read if self.titles_read else 0.0


def _field(head: str, *names: str) -> str:
    for name in names:
        match = re.search(rf"^{name}:\s*[\"']?(.*?)[\"']?\s*$", head, re.M)
        if match and match.group(1).strip():
            return match.group(1).strip()
    return ""


def read_receipts(published_dir: Path | None = None) -> list[Receipt]:
    """Every published faith video with a channel, a title and a day."""
    from pipeline.channels import normalize_channel_id

    out: list[Receipt] = []
    folder = PUBLISHED_DIR if published_dir is None else published_dir
    for path in sorted(folder.glob("*.md")):
        match = _FRONT.match(path.read_text(encoding="utf-8", errors="replace"))
        if not match:
            continue
        head = match.group(1)
        if "faith" not in _field(head, "niche").lower():
            continue
        day = _field(head, "published_at", "published_on")[:10]
        title = _field(head, "title")
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", day) or not title:
            continue
        out.append(Receipt(
            channel=normalize_channel_id(_field(head, "channel") or None),
            title=title, day=day,
            short=_field(head, "format").lower() == "short" or path.name.startswith("short-"),
        ))
    return out


def split_title(title: str) -> tuple[str, str]:
    """(the reference in the title, the words after the bar) of a Short's title."""
    body = re.sub(r"\s*#shorts\s*$", "", title, flags=re.I)
    stem, _, hook = body.partition(" | ")
    found = _REFERENCE.search(stem)
    return (found.group(0) if found else ""), hook.strip()


def _before_the_bar(title: str) -> str:
    """Everything in a Short's title before the bar, without the #Shorts tag."""
    body = re.sub(r"\s*#shorts\s*$", "", str(title or ""), flags=re.I)
    return body.partition(" | ")[0]


def short_frame(title: str) -> str:
    """The frame a Short's title is built on: before the bar, less the reference.

    ``"Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts"``
    gives ``"say this prayer before you sleep"``: two Shorts on different passages
    are built on the same frame, and that is the thing a reviewer sees when they
    read a channel's uploads in a row.
    """
    stem = _before_the_bar(title)
    found = _REFERENCE.search(stem)
    if found:
        stem = f"{stem[:found.start()]} {stem[found.end():]}"
    return " ".join(re.findall(r"[a-z0-9']+", stem.lower()))


def frame_text(title: str) -> str:
    """The frame as a reader sees it, with the passage left as a slot."""
    stem = _before_the_bar(title)
    found = _REFERENCE.search(stem)
    if found:
        stem = f"{stem[:found.start()]}{{passage}}{stem[found.end():]}"
    return " ".join(stem.split()).strip(" ,:;—-")


def opener(title: str) -> str:
    """The first two words of a Short's title, lower-cased."""
    words = re.findall(r"[a-z0-9']+", str(title or "").lower())
    return " ".join(words[:2])


def _sentences(text: str) -> list[str]:
    out = []
    for piece in re.split(r"(?<=[.!?])\s+", str(text or "")):
        words = re.findall(r"[a-z']+", piece.lower())
        if len(words) >= MIN_SENTENCE_WORDS:
            out.append(" ".join(words))
    return out


_BIBLE_WORDS: list[str] = []


def _is_scripture(sentence: str) -> bool:
    """True when the Bible has these words in this order, whatever its punctuation.

    A sentence may also open with the speaker's own lead-in ("Psalm 23 says, ..."),
    so the words after any run of up to six opening words are tried as well.
    """
    from pipeline import scripture_text

    if not _BIBLE_WORDS:
        _BIBLE_WORDS.append(
            " " + " ".join(re.findall(r"[a-z']+", scripture_text._whole_text())) + " ")
    words = sentence.split()
    for skipped in range(0, 7):
        rest = words[skipped:]
        if len(rest) < MIN_SENTENCE_WORDS - 2:
            break
        if f" {' '.join(rest)} " in _BIBLE_WORDS[0]:
            return True
    return False


def shared_sentences(spec_dir: Path | None = None) -> dict[str, list[str]]:
    """Per channel, its own sentences that another channel's Short also speaks.

    Scripture is left out (two channels may pray the same verse), and so is any
    sentence that names a channel (each closing invitation names its own).
    """
    from pipeline.channel_capabilities import brand_for, known_channels
    from pipeline.channels import normalize_channel_id

    names = [brand_for(cid).display_name.lower() for cid in known_channels()]
    spoken: dict[str, set[str]] = defaultdict(set)
    folder = SPEC_DIR if spec_dir is None else spec_dir
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        channel = normalize_channel_id(data.get("channel"))
        lines = " ".join(str(c[2]) for c in (data.get("captions") or []) if len(c) == 3)
        for sentence in _sentences(lines):
            if any(name in sentence for name in names):
                continue
            spoken[sentence].add(channel)
    out: dict[str, list[str]] = defaultdict(list)
    for sentence, channels in spoken.items():
        if len(channels) < 2 or _is_scripture(sentence):
            continue
        for channel in channels:
            out[channel].append(sentence)
    return out


def network_openers(*, published_dir: Path | None = None) -> dict:
    """How many of the network's Short titles open with words another channel uses.

    A frame is each channel's own — "Prayer at Sunrise" on one, "Prayer at Noon"
    on another — so the frame table can read 20 of 20 on every channel and still
    say nothing about the network. What the ten channels share is the opening:
    on 17 November 2026, 237 of 238 published Short titles began "Say This" or
    "Pray This", and no other opening was used at all.

    Read from the receipts, so the figure moves when the writing does.
    """
    receipts = read_receipts(published_dir)
    openers_of = [opener(r.title) for r in receipts if r.short]
    channels = defaultdict(set)
    for receipt in receipts:
        if receipt.short:
            channels[opener(receipt.title)].add(receipt.channel)
    shared = sum(1 for word in openers_of if len(channels.get(word, ())) > 1)
    counts = Counter(word for word in openers_of if word)
    top, uses = counts.most_common(1)[0] if counts else ("", 0)
    return {"titles": len(openers_of), "shared": shared, "opener": top, "uses": uses,
            "openings": len(counts)}


def measure(*, today: datetime | None = None, published_dir: Path | None = None,
            spec_dir: Path | None = None, queue_dir: Path | None = None,
            shorts_queue_dir: Path | None = None) -> list[Row]:
    from pipeline import title_variety
    from pipeline.channel_capabilities import brand_for, known_channels
    from pipeline.short_release import hook_adds_nothing

    if queue_dir is None:
        # A caller that names its own published folder is not shown the real queue.
        queue_dir = QUEUE_DIR if published_dir is None else Path("/nonexistent-queue")
    if shorts_queue_dir is None:
        # Nor the real network's Shorts: the passage ledger is the whole network,
        # so a measure of a named folder must read only that folder's channels.
        shorts_queue_dir = (SHORTS_QUEUE_DIR if published_dir is None
                            else Path("/nonexistent-shorts-queue"))
    long_titles = title_variety.listed(
        published_dir=PUBLISHED_DIR if published_dir is None else published_dir,
        queue_dir=queue_dir)

    now = today or datetime.now(timezone.utc)
    last_day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    window = {(now - timedelta(days=n)).strftime("%Y-%m-%d") for n in range(1, RATE_DAYS + 1)}
    receipts = read_receipts(published_dir)
    shared = shared_sentences(spec_dir)
    passage_rows: list | None = None
    ledger = None

    rows: list[Row] = []
    for channel in known_channels():
        brand = brand_for(channel)
        mine = [r for r in receipts if r.channel == channel]
        row = Row(channel=channel, name=brand.display_name)
        row.long_last_day = sum(1 for r in mine if r.day == last_day and not r.short)
        row.shorts_last_day = sum(1 for r in mine if r.day == last_day and r.short)
        active_days = {r.day for r in mine if r.day in window}
        if active_days:
            # Over the days the channel actually published, so a channel a few
            # days old is not shown a rate diluted by days before it existed.
            row.per_day = round(sum(1 for r in mine if r.day in window) / len(active_days), 1)
        shorts = sorted((r for r in mine if r.short), key=lambda r: r.day)[-RECENT_TITLES:]
        row.titles_read = len(shorts)
        for receipt in shorts:
            label, hook = split_title(receipt.title)
            if not hook or hook_adds_nothing(hook, brand, label):
                row.weak_titles += 1
        # The frame each of those titles is built on, and how many frames the
        # channel has at all. One frame for every title is the mould YouTube's
        # inauthentic-content policy names; the hook after the bar varies, the
        # words before it do not.
        frames = [short_frame(r.title) for r in shorts]
        seen = Counter(frame for frame in frames if frame)
        row.frames_used = len(seen)
        if seen:
            common, uses = seen.most_common(1)[0]
            row.frame_titles = uses
            row.frame_text = next(frame_text(r.title) for r in shorts
                                  if short_frame(r.title) == common)
            if (row.titles_read >= MIN_TITLES
                    and uses / row.titles_read >= FRAME_SHARE):
                row.notes.append(
                    f"{uses} of its last {row.titles_read} Short titles are built on one "
                    f"frame: '{row.frame_text}'")
        counts = Counter(r.title for r in mine)
        row.repeated_titles = sum(n - 1 for n in counts.values() if n > 1)
        row.shared_sentences = len(shared.get(channel, []))
        if row.titles_read >= MIN_TITLES and row.weak_share > WEAK_TITLE_SHARE:
            row.notes.append(
                f"{row.weak_titles} of its last {row.titles_read} Short titles say nothing "
                "of their own after the bar")
        if row.shared_sentences:
            row.notes.append(
                f"{row.shared_sentences} prayer sentence(s) are also spoken on another channel")
        variety = title_variety.variety_for(channel, rows=long_titles)
        row.old_form_titles = sum(
            1 for listed in long_titles
            if listed.channel == channel and not listed.queued
            and title_variety.names_no_need(
                title_variety.need_of(listed.title, brand.display_name)))
        row.need_titles = len(variety.recent)
        for word, uses in variety.tired_openings().items():
            row.tired_opening, row.tired_opening_uses = word, uses
            row.notes.append(
                f"{uses} of its last {row.need_titles} long-prayer titles open with "
                f"'{word.capitalize()}'")
            break
        row.needs_alike_elsewhere = [
            need for need in variety.own
            if any(title_variety.alike(need, other) for other in variety.elsewhere)]
        if row.needs_alike_elsewhere:
            row.notes.append(
                f"{len(row.needs_alike_elsewhere)} long-prayer title(s) word the need "
                "almost as another channel does: "
                + "; ".join(f"'{need}'" for need in row.needs_alike_elsewhere[:3]))
        # Titles still waiting in the queue that the gate would refuse today. The
        # authoring gate keeps new ones out; this counts what was written before
        # it and would publish as it stands (``pipeline/queue_titles.py``).
        from pipeline import queue_titles
        row.queued_refused = len(queue_titles.failing(
            channel, published_dir=PUBLISHED_DIR if published_dir is None else published_dir,
            queue_dir=queue_dir, rows=long_titles))
        if row.queued_refused:
            row.notes.append(
                f"{row.queued_refused} queued title(s) would be refused by the variety "
                "gate today and publish as they stand")
        # Passages prayed on more than one channel. The seasonal lists have never
        # allowed one; the roadmaps were never compared with each other or with
        # what the channels have made, so they drifted.
        if passage_rows is None:
            # Read once for every channel: the ledger is the whole network.
            from pipeline import passage_ownership
            passage_rows = passage_ownership.passages(
                published_dir=PUBLISHED_DIR if published_dir is None else published_dir,
                queue_dir=queue_dir,
                spec_dir=spec_dir if spec_dir is not None else SPEC_DIR,
                shorts_queue_dir=shorts_queue_dir)
            ledger = passage_ownership.ledger(passage_rows)
        from pipeline import passage_ownership
        row.passages_shared = len(passage_ownership.overlaps(
            channel, rows=passage_rows, index=ledger))
        ahead = passage_ownership.roadmap_ahead(
            channel, passage_ownership.taken_longform_ids(
                queue_dir=queue_dir,
                published_dir=PUBLISHED_DIR if published_dir is None else published_dir))
        own, shared_entries = passage_ownership.own_first(ahead, channel, index=ledger)
        row.roadmap_shared = len(shared_entries)
        # The selector's own choice. It steps over a shared passage whenever the
        # channel still has one of its own unwritten, so this is 1 only when
        # nothing unique is left — the channel would then repeat a passage
        # rather than run dry.
        row.next_prayer_shared = int(bool(shared_entries) and not own)
        if row.passages_shared:
            row.notes.append(
                f"{row.passages_shared} video(s) pray a passage another channel "
                "already prays")
        if row.roadmap_shared:
            row.notes.append(
                f"{row.roadmap_shared} unwritten roadmap prayer(s) name a passage "
                "another channel already prays")
        if row.next_prayer_shared:
            row.notes.append(
                "the next prayer its roadmap would write is of a passage another "
                "channel already prays")
        rows.append(row)
    return rows


def render(rows: list[Row], network: dict | None = None) -> str:
    lines = [
        "### How alike the channels look",
        "",
        "These are this repository's own measures of what YouTube's monetisation and "
        "spam policies describe (videos that look made from a template; many similar "
        "videos across linked channels). YouTube publishes no numbers for them.",
        "",
        "| Channel | Yesterday (long + Shorts) | Per day, last "
        f"{RATE_DAYS} | Recent Short titles with nothing of their own | Titles used twice "
        "| Sentences shared with another channel |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.name} | {row.long_last_day} + {row.shorts_last_day} | {row.per_day:g} "
            f"| {row.weak_titles} of {row.titles_read} | {row.repeated_titles} "
            f"| {row.shared_sentences} |")
    total = sum(r.long_last_day + r.shorts_last_day for r in rows)
    lines += ["", f"All channels together published {total} videos yesterday (UTC)."]
    lines += [
        "",
        "#### Short titles built on one frame",
        "",
        "A Short's title is `<what the channel says> | <its own hook>`. The hook was "
        "fixed on 16 November so that it says something of its own; the words before "
        "the bar are set per channel in `pipeline/channel_capabilities.py` "
        "(`Brand.short_title_template`) and never change, so every Short on a channel "
        "is built on one frame with the passage swapped. YouTube's monetisation policy "
        "refuses content that \"feels interchangeable from video to video\", and its "
        "spam policy covers many similar videos across linked channels. No live title "
        "is edited by anything here.",
        "",
        "| Channel | Recent Short titles read | Built on the channel's one frame "
        "| Frames it has | The frame |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        frame = f"`{row.frame_text}`" if row.frame_text else "none"
        lines.append(
            f"| {row.name} | {row.titles_read} | {row.frame_titles} of {row.titles_read} "
            f"| {row.frames_used} | {frame} |")
    if network and network.get("titles"):
        lines += [
            "",
            f"Across the ten channels, **{network['shared']} of {network['titles']}** "
            f"published Short titles open with two words another channel also uses "
            f"(\"{network['opener'].title()}\", {network['uses']} of them); the network "
            f"uses {network['openings']} opening(s) in all.",
        ]
    lines += [
        "",
        "#### Long-prayer titles",
        "",
        "The long prayers earn the hours that count. The old form opens with the passage "
        "(\"Psalm 23:5 Provision Prayer\") and is replaced, at most two a channel a day, "
        "once a video is a week old and unwatched. The other columns watch that the titles "
        "replacing it do not become one mould themselves, and the last counts the queued "
        "titles the gate would refuse today — the ones written before it existed.",
        "",
        "| Channel | Published titles still in the old form | Need-first titles read "
        "| Opening word used too often | Needs worded as another channel words one "
        "| Queued titles the gate would refuse |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        tired = (f"'{row.tired_opening.capitalize()}' ({row.tired_opening_uses})"
                 if row.tired_opening else "none")
        lines.append(
            f"| {row.name} | {row.old_form_titles} | {row.need_titles} | {tired} "
            f"| {len(row.needs_alike_elsewhere)} | {row.queued_refused} |")
    lines += [
        "",
        "#### Passages prayed on more than one channel",
        "",
        "The seasonal lists have never given one passage to two channels "
        "(``pipeline/seasonal.py``: \"ten channels praying the same verse on the "
        "same day is the templated content YouTube's inauthentic-content policy "
        "describes\"). Nothing held the roadmaps to it, so they drifted: on "
        "16 November 2026 twenty passages were prayed on more than one channel "
        "and 104 unwritten roadmap entries still named one of them. The last "
        "column is the prayer the brain would write next for the channel: "
        "``select_next_scripture`` now steps over a shared passage whenever the "
        "channel still has one of its own unwritten, so it reads 0 on every "
        "channel — it read 1 on The Midday Watch, The Provision Table, The "
        "Covenant Shield and The Praise Garden before that. The first two "
        "columns are the owner's to decide: which channel keeps a passage is a "
        "content decision, not one a program should make.",
        "",
        "| Channel | Videos praying a passage another channel prays | Unwritten "
        "roadmap prayers of a shared passage | Next prayer repeats another "
        "channel's passage |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row.name} | {row.passages_shared} | {row.roadmap_shared} "
            f"| {row.next_prayer_shared} |")
    shared_passages = sum(1 for row in rows if row.passages_shared)
    lines += [
        "",
        f"{shared_passages} of {len(rows)} channels pray at least one passage "
        "another channel already prays.",
    ]
    noted = [f"- **{row.name}:** {note}" for row in rows for note in row.notes]
    if noted:
        lines += ["", "Over the repository's own mark:", *noted]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the rows as JSON")
    args = parser.parse_args(argv)

    rows = measure()
    if not rows:
        print("::error title=Channel sameness::no channel is registered", flush=True)
        return 1
    if args.json:
        print(json.dumps([{**asdict(row), "weak_share": round(row.weak_share, 3)}
                          for row in rows], indent=2))
        return 0
    report = render(rows, network_openers())
    print(report)
    for row in rows:
        for note in row.notes:
            # A comma would end the annotation's title.
            print(f"::warning title=Channels look alike ({row.channel})::{row.name}: {note}",
                  flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
