"""The one list of book names, and how a reference is split up.

This was `gemini_brain._BOOK_RE` until 25 November 2026, and two things needed it
from modules that must run with nothing installed: `pipeline/evergreen_shorts.py`
counting which passages a channel has used, and `pipeline/shorts_supply.py`
counting what is left. Importing `gemini_brain` for one regular expression meant
importing PyYAML as well, and the daily growth job installs no packages — so the
reading failed in CI and passed locally, which is the worst way for a reading to
behave.

The pattern is re-exported from `gemini_brain` under its old name, so every
existing caller keeps working.

    >>> split_reference("1 John 4:18")
    ('1 john', 4, 18)
"""
from __future__ import annotations

import re

#: Book name, optionally numbered, then chapter, then an optional verse span.
BOOK_RE = re.compile(
    r"(?i)\b((?:[123]\s+)?(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|"
    r"Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm[s]?|"
    r"Proverbs|Ecclesiastes|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|"
    r"Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|"
    r"Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|"
    r"Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|"
    r"Peter|Jude|Revelation))"
    r"\s+(\d+)(?::(\d+(?:[–\-]\d+(?:,\s*\d+)?)?))?"
)


def split_reference(reference: str) -> tuple[str, int, int | None] | None:
    """``(book, chapter, first verse or None)``, or ``None`` if it is not one.

    The book is lower-cased and singularised ("Psalms" -> "psalm"), so two
    spellings of the same passage compare equal.
    """
    match = BOOK_RE.search(str(reference or "").replace("–", "-"))
    if not match:
        return None
    book = re.sub(r"\s+", " ", match.group(1)).strip().lower()
    if book == "psalms":
        book = "psalm"
    verse = re.match(r"\d+", match.group(3) or "")
    return book, int(match.group(2)), int(verse.group(0)) if verse else None
