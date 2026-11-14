"""The words of the passage, and the check that a script quotes them as written.

Until 14 November 2026 the writer was handed a reference ("Psalm 55:22") and
quoted the verse from memory. Fifteen of the first sixteen standalone Shorts
came back faithful. The sixteenth read "He will never permit. He will sustain
the righteous to be moved." and was two publishes from going out; it was caught
by a person reading it, not by the pipeline. A prayer channel that misquotes the
verse it is praying has lost the one thing it is trusted for.

Two things are done here, both offline:

1. ``passage(reference)`` returns the verses themselves, from the King James
   Version bundled at ``assets/scripture/kjv.json.gz`` (31,102 verses, public
   domain; the JSON edition is github.com/aruljohn/Bible-kjv, MIT). The writer
   is shown these words and told to quote them exactly (``prompt_block``).
2. ``quote_problems(narration, reference)`` refuses a script that does not carry
   at least one whole verse of its passage word for word, or that carries a
   verse nearly but not exactly (a dropped or swapped word).

Why the King James Version and not the translation a script happened to use:
it is the only widely known English text that is free to quote in full, so it
can be shipped in the repository and checked against without a network call or
a licence. Scripts written before this module quote several translations; some
of those translations are under copyright, which is a second reason to stop
letting the writer pick one.

What this does not prove: that the prayer around the verse says something true.
It proves that the words presented as scripture are scripture.
"""
from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

KJV_PATH = Path(__file__).resolve().parent.parent / "assets" / "scripture" / "kjv.json.gz"
TRANSLATION = "King James Version"

#: A verse the narration carries this much of, in order, without carrying it
#: exactly, is treated as a misquotation rather than as prayer in the writer's
#: own words. Measured on the Shorts in the repository on 14 November 2026: the
#: prayers that follow a correctly quoted verse share at most about half of its
#: words in order; the lowest score of a quotation with one changed word in a
#: twelve-word verse is 0.92.
NEAR_QUOTE = 0.75
#: Verses shorter than this are not tested for a near-quotation: five common
#: words in a row prove nothing.
NEAR_QUOTE_MIN_WORDS = 8
#: How many words of the passage the writer is shown. A whole psalm is not put
#: in the prompt; the verses shown are the ones that may be quoted.
PROMPT_MAX_WORDS = 260

#: A verse longer than this may be quoted in part: whole clauses of it, in a row.
LONG_VERSE_WORDS = 30
#: ...and the part must be at least this long ("as for me and my house, we will
#: serve the LORD" is eleven words of a fifty-eight word verse; "the joy of the LORD is your
#: strength" is eight of forty-six).
LONG_VERSE_PART_MIN = 8
#: What is left of a long verse after the quoted part is tested for drift only
#: when it is at least this many words.
REMAINDER_MIN_WORDS = 3

#: Spelling only, never a different word: the 1769 text's "shew" is today's
#: "show", and a script may use either side of the Atlantic.
_SPELLING = {
    "shew": "show", "shewed": "showed", "shewing": "showing", "shewn": "shown",
    "shewest": "showest", "sheweth": "showeth", "shewedst": "showedst",
    "saviour": "savior", "saviours": "saviors", "honour": "honor", "honours": "honors",
    "honoured": "honored", "honoureth": "honoreth", "honourable": "honorable",
    "favour": "favor", "favoured": "favored", "favourable": "favorable",
    "neighbour": "neighbor", "neighbours": "neighbors", "labour": "labor",
    "labours": "labors", "laboured": "labored", "colour": "color", "colours": "colors",
    "counsellor": "counselor", "counsellors": "counselors", "marvellous": "marvelous",
    "rumour": "rumor", "rumours": "rumors", "armour": "armor", "vapour": "vapor",
    "odour": "odor", "odours": "odors", "behaviour": "behavior", "succour": "succor",
    "valour": "valor", "clamour": "clamor", "rigour": "rigor", "endeavour": "endeavor",
    "endeavours": "endeavors", "plough": "plow", "musick": "music", "publick": "public",
}
#: A marker in the Psalms and Habakkuk, not part of the sentence; rarely read aloud.
_MARKERS = ("selah",)

_BOOKS = (
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Psalm", "Proverbs", "Ecclesiastes",
    "Song of Solomon", "Song of Songs", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel",
    "Daniel", "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus",
    "Philemon", "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
    "Jude", "Revelation",
)
# Longest name first, so "1 John" is not read as "John" and "Psalms" not as "Psalm".
_REF_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])("
    + "|".join(re.escape(b).replace(r"\ ", r"\s+") for b in sorted(_BOOKS, key=len, reverse=True))
    + r")\s+(\d+)(?:\s*:\s*(\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-–]\s*\d+)?)*))?"
)
_ALIASES = {"psalms": "psalm", "song of songs": "song of solomon"}


class UnknownReference(ValueError):
    """The reference names a book, chapter or verse the text does not have."""


@dataclass(frozen=True)
class Verse:
    book: str
    chapter: int
    number: int
    text: str

    @property
    def label(self) -> str:
        return f"{self.book.title()} {self.chapter}:{self.number}"


@lru_cache(maxsize=1)
def _bible() -> dict[str, dict[str, list[str]]]:
    with gzip.open(KJV_PATH, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def parse_reference(reference: str) -> tuple[str, int, list[int] | None]:
    """``"1 John 4:4"`` -> ``("1 john", 4, [4])``; ``"Psalm 23"`` -> ``("psalm", 23, None)``.

    Ranges and lists are expanded: ``"Psalm 121:1-2, 5"`` -> ``[1, 2, 5]``.
    Raises ``UnknownReference`` when no known book is named.
    """
    text = str(reference or "").replace("–", "-")
    for match in _REF_RE.finditer(text):
        book = re.sub(r"\s+", " ", match.group(1)).strip().lower()
        book = _ALIASES.get(book, book)
        if book not in _bible():
            continue
        verses: list[int] | None = None
        if match.group(3):
            verses = []
            for part in match.group(3).split(","):
                bounds = [int(n) for n in re.findall(r"\d+", part)]
                if len(bounds) == 2 and bounds[1] >= bounds[0]:
                    verses.extend(range(bounds[0], bounds[1] + 1))
                else:
                    verses.append(bounds[0])
        return book, int(match.group(2)), verses
    raise UnknownReference(f"no book of the Bible found in {reference!r}")


def passage(reference: str) -> list[Verse]:
    """The verses a reference names, in order. A bare chapter is the whole chapter."""
    book, chapter, wanted = parse_reference(reference)
    verses = _bible()[book].get(str(chapter))
    if verses is None:
        raise UnknownReference(f"{book.title()} has no chapter {chapter} ({reference!r})")
    if wanted is None:
        wanted = list(range(1, len(verses) + 1))
    out: list[Verse] = []
    for number in wanted:
        if not 1 <= number <= len(verses):
            raise UnknownReference(
                f"{book.title()} {chapter} has {len(verses)} verses, not {number} ({reference!r})")
        out.append(Verse(book, chapter, number, verses[number - 1]))
    return out


def exists(reference: str) -> bool:
    try:
        return bool(passage(reference))
    except UnknownReference:
        return False


def _words(text: str) -> list[str]:
    """Lower-case words with punctuation dropped: ``"LORD's"`` -> ``"lords"``."""
    cleaned = re.sub(r"[’'`]", "", str(text or "").lower())
    return [_SPELLING.get(word, word) for word in re.findall(r"[a-z0-9]+", cleaned)
            if word not in _MARKERS]


def readable(text: str) -> str:
    """The verse as the writer is shown it: today's spelling of "shew", no "Selah"."""
    def swap(match: "re.Match[str]") -> str:
        word = match.group(0)
        new = _SPELLING.get(word.lower())
        if new is None:
            return word
        return new.upper() if word.isupper() else new.capitalize() if word[0].isupper() else new
    out = re.sub(r"[A-Za-z]+", swap, str(text or ""))
    out = re.sub(r"\s*\bSelah\b\.?", "", out)
    return re.sub(r"\s+", " ", out).strip()


def _clause_runs(text: str) -> list[str]:
    """Every run of whole clauses of a long verse that is long enough to stand as a quotation."""
    clauses = [c.strip() for c in re.split(r"(?<=[,;:.?!])\s+", readable(text)) if c.strip()]
    runs: list[str] = []
    for start in range(len(clauses)):
        for end in range(start + 1, len(clauses) + 1):
            run = " ".join(clauses[start:end])
            if len(_words(run)) >= LONG_VERSE_PART_MIN:
                runs.append(run)
    return runs


def _letters(text: str) -> str:
    """Only the letters, so "for ever" and "forever" are the same words spoken."""
    return "".join(_words(text))


#: A quotation may leave off the joining word a verse opens with: "For God so
#: loved the world" is quoted as "God so loved the world" in every pulpit.
_LEADING_JOINERS = ("and", "but", "for", "then", "yet", "now", "or", "so",
                    "therefore", "wherefore")


def _spoken_forms(text: str) -> list[str]:
    """The letter-strings that count as this text quoted: as written, or without its joining first word."""
    words = _words(text)
    forms = ["".join(words)]
    if len(words) > 3 and words[0] in _LEADING_JOINERS:
        forms.append("".join(words[1:]))
    return forms


def _carried(text: str, spoken_letters: str) -> bool:
    return any(form and form in spoken_letters for form in _spoken_forms(text))


def _lcs(a: list[str], b: list[str]) -> int:
    """Length of the longest common subsequence of two word lists."""
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    for word in a:
        current = [0]
        for index, other in enumerate(b, start=1):
            current.append(previous[index - 1] + 1 if word == other
                           else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def nearness(verse_text: str, narration: str) -> float:
    """How much of a verse the narration carries in order, within one stretch: 0-1.

    The verse's words are looked for, in order, inside each stretch of narration
    about as long as the verse. 1.0 means every word is there in order.
    """
    verse = _words(verse_text)
    spoken = _words(narration)
    if not verse or not spoken:
        return 0.0
    span = int(len(verse) * 1.4) + 2
    best = 0
    for start in range(0, max(1, len(spoken) - len(verse) // 2)):
        best = max(best, _lcs(verse, spoken[start:start + span]))
        if best == len(verse):
            break
    return best / len(verse)


def _find(needle: list[str], haystack: list[str]) -> int:
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start:start + len(needle)] == needle:
            return start
    return -1


def _drift(before: list[str], part: list[str], after: list[str],
           spoken: list[str]) -> list[str]:
    """Which side of a faithfully quoted part carries the rest of the verse reworded.

    Looks only at the words right beside the quoted part: the rest of the verse
    echoed later, in the prayer, is the writer's own words and is not this.
    """
    at = _find(part, spoken)
    if at < 0 and len(part) > 3 and part[0] in _LEADING_JOINERS:
        part = part[1:]
        at = _find(part, spoken)
    if at < 0:
        return []
    sides: list[str] = []
    if len(after) >= REMAINDER_MIN_WORDS:
        window = spoken[at + len(part): at + len(part) + int(len(after) * 1.4) + 3]
        if window[:len(after)] != after and _lcs(after, window) / len(after) >= NEAR_QUOTE:
            sides.append("after")
    if len(before) >= REMAINDER_MIN_WORDS:
        window = spoken[max(0, at - int(len(before) * 1.4) - 3): at]
        if window[-len(before):] != before and _lcs(before, window) / len(before) >= NEAR_QUOTE:
            sides.append("before")
    return sides


@dataclass
class QuoteCheck:
    reference: str
    quoted: list[str]            # labels of the verses carried word for word
    problems: list[str]
    in_part: list[str] = field(default_factory=list)   # long verses quoted by whole clauses

    @property
    def ok(self) -> bool:
        return not self.problems


def check_quote(narration: str, reference: str) -> QuoteCheck:
    """Does this narration carry its passage as written?"""
    try:
        verses = passage(reference)
    except UnknownReference as exc:
        return QuoteCheck(reference, [], [f"scripture reference not found: {exc}"])
    spoken = _letters(narration)
    quoted: list[str] = []
    problems: list[str] = []
    in_part: set[str] = set()
    for verse in verses:
        if _carried(verse.text, spoken):
            quoted.append(verse.label)
            continue
        if len(_words(verse.text)) <= LONG_VERSE_WORDS:
            continue
        carried = [run for run in _clause_runs(verse.text) if _carried(run, spoken)]
        if not carried:
            continue
        # The longest part quoted as written. What is left of the verse must not
        # also be there with words changed: a quotation that starts faithful and
        # drifts ("they shall walk step by step, and not faint") is a misquotation.
        best = max(carried, key=lambda run: len(_words(run)))
        whole, part = readable(verse.text), best
        before, _, after = whole.partition(part)
        drifted = _drift(_words(before), _words(best), _words(after), _words(narration))
        drifted = [before if side == "before" else after for side in drifted]
        if drifted:
            problems.append(
                f"{verse.label} is quoted in part and then with words changed "
                f"(\"{drifted[0].strip()}\"). Quote it exactly or stop at the punctuation: "
                f"\"{whole}\"")
            continue
        quoted.append(verse.label)
        in_part.add(verse.label)
    flagged = {p.split(" is quoted", 1)[0] for p in problems}
    for verse in verses:
        if (verse.label in quoted or verse.label in flagged
                or len(_words(verse.text)) < NEAR_QUOTE_MIN_WORDS):
            continue
        score = nearness(verse.text, narration)
        if score >= NEAR_QUOTE:
            problems.append(
                f"{verse.label} is quoted with words changed ({score:.0%} of it, in order). "
                f"Quote it exactly or leave it out: \"{readable(verse.text)}\"")
    if not quoted:
        first = verses[0]
        problems.insert(0, (
            f"the narration does not quote any whole verse of {reference} word for word "
            f"({TRANSLATION}). Copy at least this exactly: \"{readable(first.text)}\""))
    return QuoteCheck(reference, quoted, problems, sorted(in_part))


def quote_problems(narration: str, reference: str) -> list[str]:
    """Reasons to refuse the script; an empty list means it quotes its passage faithfully."""
    return check_quote(narration, reference).problems


def prompt_block(reference: str, *, max_words: int = PROMPT_MAX_WORDS) -> str:
    """The passage as the writer is shown it, with the rule for quoting it.

    Returns ``""`` when the reference is not in the text; the caller refuses the
    script later with the reason, so a bad reference is reported, not hidden.
    """
    try:
        verses = passage(reference)
    except UnknownReference:
        return ""
    shown: list[Verse] = []
    count = 0
    for verse in verses:
        size = len(_words(verse.text))
        if shown and count + size > max_words:
            break
        shown.append(verse)
        count += size
    lines = "\n".join(f"  {v.number} {readable(v.text)}" for v in shown)
    long_note = ""
    if all(len(_words(v.text)) > LONG_VERSE_WORDS for v in shown):
        long_note = (
            f"  A verse above of more than {LONG_VERSE_WORDS} words may be quoted in part: whole\n"
            f"  clauses of it in a row (from one punctuation mark to another), at least\n"
            f"  {LONG_VERSE_PART_MIN} words, with no word changed.\n")
    book = shown[0].book.title()
    return (
        f"\nTHE WORDS OF {reference.upper()} ({TRANSLATION}; {book} {shown[0].chapter}, "
        "verse numbers shown for you, do not read them out):\n"
        f"{lines}\n"
        "- When the narration quotes scripture it uses THESE words, exactly as written:\n"
        "  the same words in the same order, nothing added, dropped, modernised or\n"
        "  swapped. Do not quote from memory and do not use another translation.\n"
        "- Quote at least one whole verse from the lines above, from its first word to\n"
        "  its last. Code compares the narration to these lines and rejects a changed word.\n"
        f"{long_note}"
        "- Everything outside the quotation is prayer in your own words. Do not put a\n"
        "  reworded verse in it: either a verse is quoted exactly or it is not quoted.\n"
    )
