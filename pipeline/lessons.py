"""What a channel has learned to try, and whether it worked on its own videos.

The owner asked on 16 November 2026 that the channels learn on their own, from
what their audience looks for and from what the most-watched videos of their
kind are doing. Until then the automation learned only which of its own themes
drew views (``pipeline/performance_feedback.py``); its "niche benchmarks" were
numbers typed in by hand.

A lesson here is one short phrase (two to five words) from one of two places:

* **the words viewers typed into YouTube search to find this channel**
  (``scripts/analytics_reader.py``, the channel's own Analytics);
* **word sequences shared by the titles of the most-watched videos of this
  kind**, from at least three different channels (``scripts/niche_reading.py``,
  once a week). Only the phrases leave that script: no other channel's title,
  name, id or view count is written anywhere.

A lesson is a guess until the channel's own videos say otherwise. Each one is
offered to the title writer ("use one where it is true of this prayer"). From
the day a lesson is opened, every long prayer the channel publishes is counted
once, when it is ``JUDGE_AGE_DAYS`` old: on the side of the titles that carry
the phrase, or on the side of those that do not, with the views it had by then.
When both sides hold enough videos and enough views, the phrase is kept if its
titles drew clearly more views a video, and dropped (never offered again) if
they drew clearly fewer. A phrase with no verdict in ``EXPIRE_DAYS`` is retired
and another takes its place. That is the whole of "learning on its own":
nothing is believed because a bigger channel does it.

Only the totals are stored (how many videos and how many views on each side),
never a table of videos.

No two channels try the same phrase at once (``taken``), so a lesson cannot
pull the channels' titles toward each other.

Limits, said plainly:

* it is a comparison, not an experiment: the videos differ in passage and day
  as well as in wording, so a verdict needs several videos on each side and a
  floor of real views (``MIN_VIEWS_TO_JUDGE``) before it is given, and no one
  video counts for more than ``VIEW_CAP`` views;
* a channel whose long prayers are barely watched cannot learn this way: its
  lessons end "retired, no verdict", and that is the honest answer;
* it cannot see why another channel's video is watched: retention, click rate
  and revenue of other channels are not available to anyone but their owners;
* a phrase is never a title. The title writer still has to pass every check a
  title passes (``pipeline/retitle.py``, ``pipeline/title_variety.py``), and
  promise words are refused here before a phrase is ever offered.

Nothing in this module talks to YouTube. It reads and returns plain data; the
lessons are stored inside the channel's committed feedback artifact.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

#: Phrases under test at once on one channel. Few, so each can gather videos.
MAX_TESTING = 3
#: Words in a phrase. One word is not a lesson; six is somebody's title.
MIN_WORDS, MAX_WORDS = 2, 5
#: A search term must have brought at least this many views in its 90 days to be worth
#: trying. The first real reading (The Secret Place, 16 November 2026) had 8 views on its
#: best term and one or two on most: one person typing something once is not an audience.
MIN_TERM_VIEWS = 5
#: A long prayer is counted once, with the views it has at this age. The daily
#: snapshot sees a channel's latest 50 uploads (about a week), so the age must
#: stay well inside that.
JUDGE_AGE_DAYS = 4
#: Long prayers on each side before a phrase is judged.
MIN_VIDEOS_EACH_SIDE = 5
#: Views across both sides before any verdict: below this the difference is noise.
MIN_VIEWS_TO_JUDGE = 100
#: The most one video may add to a side, so one runaway video cannot decide a phrase.
VIEW_CAP = 50
#: Views a video with the phrase, over views a video without it.
KEEP_RATIO, DROP_RATIO = 1.25, 0.8
#: A lesson with no verdict after this many days gives its place to another.
EXPIRE_DAYS = 60
#: Lessons remembered per channel.
MAX_REMEMBERED = 60
#: Niche reading: a word sequence must be in the titles of this many different channels.
MIN_CHANNELS = 3
#: Niche reading: phrases kept from one reading.
MAX_NICHE_PHRASES = 8
#: Niche phrases are other channels' wording, so they are not kept past this many days
#: without a fresh reading (YouTube's 30-day rule for data that is not the channel's own).
NICHE_KEEP_DAYS = 30

SEARCH_SOURCE = "what viewers typed into YouTube search"
NICHE_SOURCE = "titles of the most-watched videos of this kind"
STATUSES = ("testing", "kept", "dropped", "retired")

_BOOKS = (
    "genesis|exodus|leviticus|numbers|deuteronomy|joshua|judges|ruth|samuel|kings|chronicles|"
    "ezra|nehemiah|esther|job|psalm|psalms|proverbs|ecclesiastes|song of solomon|isaiah|"
    "jeremiah|lamentations|ezekiel|daniel|hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|"
    "zephaniah|haggai|zechariah|malachi|matthew|mark|luke|john|acts|romans|corinthians|"
    "galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon|hebrews|"
    "james|peter|jude|revelation")
_REFERENCE = re.compile(
    rf"\b(?:[1-3] )?(?:{_BOOKS}) \d+(?: ?: ?\d+(?: ?- ?\d+)?)?(?!\d)")
_SMALL = frozenset(
    "a an and are as at be by for from his in is it my of on our that the thy to we with "
    "you your this these those when".split())
#: Words that say nothing about a prayer and only name the site, the format or the year.
_NOISE = frozenset(
    "youtube video videos shorts short channel full hd live new official subscribe kjv esv niv "
    "nkjv hour hours hr hrs minute minutes min mins".split())
#: What makes a search term about these channels' subject at all. The first real reading
#: held "barbie", "blackjack casino" and people's names beside "psalm 91": YouTube counts
#: every search that ended on a video, most of them a Short met by chance.
_ANCHOR = re.compile(r"\b(?:pray\w*|psalm\w*|bible|biblical|scriptures?|verses?|devotion\w*|"
                     r"bless\w*|worship\w*|gospel)\b")
_BREAK = re.compile(r"[|:;,.!?()\[\]{}/\\\"\u2013\u2014\u2022~*#+=<>]| - ")


def _banned() -> tuple[str, ...]:
    from .retitle import BANNED
    return BANNED


def _brand_names() -> list[str]:
    """Every channel's display name, lower-cased, without a leading 'the'."""
    from .channel_capabilities import brand_for, known_channels
    names = []
    for channel in known_channels():
        name = brand_for(channel).display_name.lower()
        names.append(name[4:] if name.startswith("the ") else name)
    return names


def on_topic(term: str) -> bool:
    """True when a search term names prayer, a psalm, scripture, or a passage (book and number)."""
    text = " ".join(str(term or "").lower().split())
    return bool(_ANCHOR.search(text) or _REFERENCE.search(text))


_SPOKEN: dict[str, frozenset[str]] = {}


def spoken_words(published_dir: Any = None) -> frozenset[str]:
    """Every word the channels have themselves published (titles, descriptions, scripts).

    A phrase may only be made of these. It is what keeps a person's name, a brand
    or another subject out of a lesson: a word these channels have never once used
    in a prayer is not theirs to put in a title because somebody else did.
    """
    from .config import PUBLISHED_DIR

    folder = Path(published_dir) if published_dir else PUBLISHED_DIR
    key = str(folder)
    if key not in _SPOKEN:
        words: set[str] = set()
        for path in sorted(folder.glob("*.md")):
            try:
                words |= set(re.findall(r"[a-z']+", path.read_text(encoding="utf-8").lower()))
            except OSError:
                continue
        _SPOKEN[key] = frozenset(words)
    return _SPOKEN[key]


def _content(phrase: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z']+", str(phrase or "").lower())) - _SMALL


def label_words(channel_id: str | None) -> frozenset[str]:
    """The words every long-prayer title on the channel already carries ("night prayer")."""
    from .channel_capabilities import brand_for
    try:
        return _content(brand_for(channel_id).longform_prayer_label)
    except Exception:  # noqa: BLE001 - an unregistered channel has no label
        return frozenset()


def clean_phrase(text: str, skip: frozenset[str] = frozenset(),
                 known: frozenset[str] | None = None) -> str:
    """A phrase fit to offer a title writer, or ``""``.

    Scripture references are taken out (the title carries its own), then what is
    left must be two to five plain words, with no channel's name, no promise word
    and no word that only names the site. ``skip`` is the channel's own label:
    a phrase that says nothing more than the label is not a lesson. ``known`` is
    ``spoken_words()``: with it, every word must be one the channels have used.
    """
    raw = " ".join(re.sub(r"[^a-z0-9':\- ]+", " ", str(text or "").lower()).split())
    raw = _REFERENCE.sub(" ", raw)
    if re.search(r"\d", raw):
        return ""
    words = [word.strip("'") for word in re.sub(r"[^a-z' ]+", " ", raw).split()]
    words = [word for word in words if word]
    while words and words[0] in _SMALL:
        words = words[1:]
    while words and words[-1] in _SMALL:
        words = words[:-1]
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        return ""
    if any(word in _NOISE for word in words):
        return ""
    phrase = " ".join(words)
    padded = f" {phrase} "
    for banned in _banned():
        if f" {banned} " in padded:
            return ""
    if any(name and name in phrase for name in _brand_names()):
        return ""
    content = _content(phrase)
    if not content or content <= skip:
        return ""
    if known is not None and not all(word in known or word in _SMALL for word in words):
        return ""
    return phrase


def phrase_in_title(phrase: str, title: str) -> bool:
    """True when every meaningful word of the phrase is in the title."""
    wanted = _content(phrase)
    return bool(wanted) and wanted <= frozenset(re.findall(r"[a-z']+", str(title or "").lower()))


def candidates_from_search_terms(terms: Iterable[Any] | None,
                                 skip: frozenset[str] = frozenset(),
                                 known: frozenset[str] | None = None) -> list[tuple[str, str]]:
    """``(phrase, source)`` from the channel's own search terms, most views first.

    A term must be about prayer or scripture (``on_topic``) and have brought
    ``MIN_TERM_VIEWS`` views.
    """
    rows = []
    for row in terms or []:
        if not isinstance(row, dict):
            continue
        try:
            views = float(row.get("views") or 0)
        except (TypeError, ValueError):
            continue
        if views >= MIN_TERM_VIEWS and on_topic(str(row.get("term") or "")):
            rows.append((views, str(row.get("term") or "")))
    found: list[tuple[str, str]] = []
    for _views, term in sorted(rows, key=lambda item: -item[0]):
        phrase = clean_phrase(term, skip, known)
        if phrase and all(phrase != seen for seen, _ in found):
            found.append((phrase, SEARCH_SOURCE))
    return found


def candidates_from_niche(phrases: Iterable[Any] | None,
                          skip: frozenset[str] = frozenset(),
                          known: frozenset[str] | None = None) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for text in phrases or []:
        phrase = clean_phrase(str(text), skip, known)
        if phrase and all(phrase != seen for seen, _ in found):
            found.append((phrase, NICHE_SOURCE))
    return found


def phrases_from_titles(titles: Iterable[tuple[str, str]], skip: frozenset[str] = frozenset(),
                        limit: int = MAX_NICHE_PHRASES,
                        known: frozenset[str] | None = None) -> list[str]:
    """Word sequences that several different channels' titles share.

    ``titles`` is ``(title, channel)`` for the videos a niche reading found. What
    comes back is two to four words long, is in the titles of at least
    ``MIN_CHANNELS`` different channels, and is not most of any one title
    (``pipeline/title_variety.py``'s measure): common wording, never somebody's
    title. A title carrying a promise word (``pipeline/retitle.py``'s ``BANNED``) is
    not read at all, and with ``known`` (``spoken_words()``) a phrase holding a word
    these channels have never used, such as a preacher's name, is left out. Nothing
    else about the videos is returned.
    """
    from .title_variety import ALIKE

    where: dict[str, set[str]] = {}
    whole: list[frozenset[str]] = []
    for title, channel in titles:
        text = _REFERENCE.sub(" | ", " ".join(str(title or "").lower().split()))
        plain = " %s " % " ".join(re.sub(r"[^a-z0-9%' ]+", " ", text).split())
        if any(f" {banned} " in plain for banned in _banned()):
            continue  # a title that promises what these channels refuse to promise teaches nothing
        whole.append(_content(re.sub(r"[^a-z' ]+", " ", text)))
        for part in _BREAK.split(text):
            words: list[str] = []
            runs: list[list[str]] = [words]
            for token in part.split():
                token = token.strip("'-")
                if re.fullmatch(r"[a-z']+", token):
                    runs[-1].append(token)
                else:  # a number or a symbol ends the run of words
                    runs.append([])
            for run in runs:
                for size in range(MIN_WORDS, 5):
                    for at in range(len(run) - size + 1):
                        where.setdefault(" ".join(run[at:at + size]), set()).add(str(channel))
    ranked = sorted(((len(channels), len(phrase.split()), phrase)
                     for phrase, channels in where.items() if len(channels) >= MIN_CHANNELS),
                    key=lambda item: (-item[0], -item[1], item[2]))
    kept: list[str] = []
    for _count, _size, phrase in ranked:
        if clean_phrase(phrase, skip, known) != phrase:
            continue
        content = _content(phrase)
        if any(other and len(content & other) / len(content | other) >= ALIKE for other in whole):
            continue  # it is most of one video's title: that would be copying
        if phrase.endswith("'s"):
            continue  # cut off in the middle ("fall asleep in god's")
        if any(len(content & _content(other)) / len(content | _content(other)) >= 0.5
               for other in kept):
            continue  # a longer or shorter cut of a phrase already kept
        kept.append(phrase)
        if len(kept) >= limit:
            break
    return kept


def _count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _valid(lesson: Any) -> dict | None:
    if not isinstance(lesson, dict):
        return None
    phrase = clean_phrase(str(lesson.get("phrase") or ""))
    status = str(lesson.get("status") or "")
    opened = _day(lesson.get("opened"))
    if not phrase or status not in STATUSES or opened is None:
        return None
    through = _day(lesson.get("counted_through")) or opened - timedelta(days=1)
    ratio = lesson.get("ratio")
    return {
        "phrase": phrase,
        "source": str(lesson.get("source") or SEARCH_SOURCE)[:80],
        "opened": opened.isoformat(),
        "status": status,
        "decided": (_day(lesson.get("decided")) or opened).isoformat()
        if lesson.get("decided") else "",
        "counted_through": through.isoformat(),
        "with_videos": _count(lesson.get("with_videos")),
        "with_views": _count(lesson.get("with_views")),
        "without_videos": _count(lesson.get("without_videos")),
        "without_views": _count(lesson.get("without_views")),
        "ratio": ratio if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) else None,
        "note": str(lesson.get("note") or "")[:240],
    }


def _open(phrase: str, source: str, today: date) -> dict:
    return {"phrase": phrase, "source": source, "opened": today.isoformat(), "status": "testing",
            "decided": "", "counted_through": (today - timedelta(days=1)).isoformat(),
            "with_videos": 0, "with_views": 0, "without_videos": 0, "without_views": 0,
            "ratio": None, "note": ""}


def judge(lesson: dict, videos: Iterable[dict], today: date) -> dict:
    """The lesson with today's long prayers counted in, and a verdict when there is one.

    ``videos`` are the channel's own long prayers as the day's snapshot shows
    them: ``{"title", "views", "published"}``. One is counted when it was
    published on or after the day the lesson opened, is ``JUDGE_AGE_DAYS`` old
    or more, and has not been counted before.
    """
    out = dict(lesson)
    opened = date.fromisoformat(out["opened"])
    through = date.fromisoformat(out["counted_through"])
    ripe = today - timedelta(days=JUDGE_AGE_DAYS)
    seen_any = False
    for video in videos:
        published = _day(video.get("published"))
        if published is None or video.get("views") is None:
            continue
        seen_any = True
        if not through < published <= ripe:
            continue
        views = min(_count(video.get("views")), VIEW_CAP)
        if phrase_in_title(out["phrase"], str(video.get("title") or "")):
            out["with_videos"] += 1
            out["with_views"] += views
        else:
            out["without_videos"] += 1
            out["without_views"] += views
    if seen_any and ripe > through:
        out["counted_through"] = ripe.isoformat()

    with_n, without_n = out["with_videos"], out["without_videos"]
    views_seen = out["with_views"] + out["without_views"]
    counted = (f"{with_n} long prayer(s) titled with it drew {out['with_views']} views and "
               f"{without_n} without it drew {out['without_views']}, each counted at "
               f"{JUDGE_AGE_DAYS} days old")
    expired = (today - opened).days >= EXPIRE_DAYS
    enough = (with_n >= MIN_VIDEOS_EACH_SIDE and without_n >= MIN_VIDEOS_EACH_SIDE
              and views_seen >= MIN_VIEWS_TO_JUDGE)
    if not enough:
        out["ratio"] = None
        if out["status"] == "testing" and expired:
            out.update(status="retired", decided=today.isoformat(),
                       note=f"no verdict in {EXPIRE_DAYS} days: {counted}")
        elif out["status"] == "testing":
            out["note"] = (f"{counted}; a verdict needs {MIN_VIDEOS_EACH_SIDE} on each side and "
                           f"{MIN_VIEWS_TO_JUDGE} views in all")
        return out
    mine = out["with_views"] / with_n
    base = out["without_views"] / without_n
    ratio = mine / base if base > 0 else KEEP_RATIO
    out["ratio"] = round(ratio, 2)
    compared = f"{ratio:.2f} times the views a video; {counted}"
    if ratio >= KEEP_RATIO:
        verdict = "kept"
    elif ratio <= DROP_RATIO:
        verdict = "dropped"
    elif out["status"] == "kept":
        verdict = "kept"          # still ahead, only by less: the verdict stands
    elif expired:
        verdict = "retired"
        compared = f"no clear difference in {EXPIRE_DAYS} days: {compared}"
    else:
        verdict = "testing"
    if verdict != out["status"]:
        out["decided"] = today.isoformat()
    out.update(status=verdict, note=compared)
    return out


def update(previous: Iterable[Any] | None, candidates: Iterable[tuple[str, str]] | None,
           videos: Iterable[dict], today: date, *, taken: Iterable[str] = (),
           taken_first: Iterable[str] = ()) -> list[dict]:
    """Today's lessons: yesterday's counted forward, then new ones while there is room.

    A dropped or retired phrase is remembered so that it is not opened again.
    ``taken`` are the phrases other channels are trying or have kept: none of
    them is opened here. ``taken_first`` are those on channels earlier in the
    registry: when two channels opened the same phrase on the same day, the
    later channel gives it up.
    """
    videos = list(videos)
    taken = set(taken)
    taken_first = set(taken_first)
    lessons: list[dict] = []
    seen: set[str] = set()
    for item in previous or []:
        lesson = _valid(item)
        if lesson is None or lesson["phrase"] in seen:
            continue
        seen.add(lesson["phrase"])
        if lesson["status"] == "testing" and lesson["phrase"] in taken_first:
            lesson.update(status="retired", decided=today.isoformat(),
                          note="another of the channels is already trying this phrase")
        elif lesson["status"] in ("testing", "kept"):
            lesson = judge(lesson, videos, today)
        lessons.append(lesson)
    testing = sum(1 for lesson in lessons if lesson["status"] == "testing")
    for phrase, source in candidates or []:
        if testing >= MAX_TESTING:
            break
        phrase = clean_phrase(phrase)
        if not phrase or phrase in seen or phrase in taken:
            continue
        seen.add(phrase)
        lessons.append(judge(_open(phrase, source, today), videos, today))
        testing += 1
    live = [lesson for lesson in lessons if lesson["status"] == "kept"]
    live += [lesson for lesson in lessons if lesson["status"] == "testing"]
    done = sorted((lesson for lesson in lessons if lesson["status"] in ("dropped", "retired")),
                  key=lambda lesson: lesson["decided"] or lesson["opened"], reverse=True)
    return (live + done)[:MAX_REMEMBERED]


def guidance(lessons: Iterable[dict], today: date) -> list[str]:
    """One plain line for each lesson opened or decided today."""
    lines = []
    for lesson in lessons:
        if lesson.get("decided") == today.isoformat():
            lines.append(f"Lesson '{lesson['phrase']}' ({lesson['source']}): {lesson['status']}; "
                         f"{lesson['note']}.")
        elif lesson.get("opened") == today.isoformat() and lesson.get("status") == "testing":
            lines.append(f"Lesson '{lesson['phrase']}' ({lesson['source']}): now being tried in "
                         "new long-prayer titles.")
    return lines


def offered(lessons: Iterable[Any] | None) -> tuple[list[str], list[str]]:
    """(phrases proven on this channel, phrases being tried)."""
    kept, testing = [], []
    for item in lessons or []:
        lesson = _valid(item)
        if lesson is None:
            continue
        if lesson["status"] == "kept":
            kept.append(lesson["phrase"])
        elif lesson["status"] == "testing":
            testing.append(lesson["phrase"])
    return kept, testing


def prompt_block(lessons: Iterable[Any] | None, *, proven_only: bool = False) -> str:
    """Lines for the title writer, or ``""`` when the channel has no lesson to offer.

    ``proven_only`` is for a video that is being retitled: its views are not part
    of any test, so only phrases the channel has already proven are offered.
    """
    kept, testing = offered(lessons)
    if proven_only:
        testing = []
    if not kept and not testing:
        return ""
    lines = [
        "WORDS LISTENERS USE. People looking for a prayer like this one type these words, or "
        "choose videos titled with them. Where one of them is true of THIS prayer, work it into "
        "the need in your own sentence. Use at most one, never force it, and never copy another "
        "video's title. Every other title rule still holds."]
    if kept:
        lines.append("  Proven on this channel: " + "; ".join(kept))
    if testing:
        lines.append("  Being tried: " + "; ".join(testing))
    return "\n".join(lines) + "\n"


def load(channel_id: str | None) -> list[dict]:
    """The channel's lessons from its committed feedback artifact; ``[]`` when there are none."""
    from .performance_feedback import load_feedback_report

    try:
        report = load_feedback_report(channel_id=channel_id) or {}
    except Exception:  # noqa: BLE001 - a missing artifact is no lessons
        return []
    return [lesson for lesson in (_valid(item) for item in report.get("lessons") or [])
            if lesson is not None]


def block_for(channel_id: str | None, *, proven_only: bool = False) -> str:
    """``prompt_block`` for a channel; never raises (a title is still written without it)."""
    try:
        return prompt_block(load(channel_id), proven_only=proven_only)
    except Exception:  # noqa: BLE001
        return ""


def niche_block(report: Any, today: date) -> dict | None:
    """A feedback artifact's niche reading while it is fresh enough to keep, else ``None``."""
    block = (report or {}).get("niche") if isinstance(report, dict) else None
    if not isinstance(block, dict):
        return None
    read_on = _day(block.get("read_on"))
    if read_on is None or not 0 <= (today - read_on).days <= NICHE_KEEP_DAYS:
        return None
    phrases = [phrase for phrase in (clean_phrase(str(item)) for item in block.get("phrases") or [])
               if phrase][:MAX_NICHE_PHRASES]
    out: dict[str, Any] = {"read_on": read_on.isoformat(), "phrases": phrases}
    minutes = block.get("typical_minutes")
    if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and 0 < minutes < 1500:
        out["typical_minutes"] = int(minutes)
    return out
