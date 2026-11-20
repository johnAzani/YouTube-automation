"""Cheap editorial hints for generated narration; never an upload gate."""
import re
from collections import Counter

_SENTENCE = re.compile(r"[.!?]+(?=\s|$)")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_TEASERS = re.compile(r"\b(?:don['’]t (?:scroll|click away)|stay (?:with us )?(?:until|to) the end)\b", re.I)


def pacing_notes(narration: str) -> list[str]:
    """Flag concrete issues, not predictions of retention or emotional impact."""
    sentences = [tuple(_WORD.findall(part.casefold().replace('’', "'")))
                 for part in _SENTENCE.split(narration)]
    notes = []
    long_count = sum(len(words) > 40 for words in sentences)
    if long_count:
        notes.append(f"{long_count} sentence(s) over 40 words; check spoken breath and clarity")
    repeated = sum(count - 1 for count in Counter(words for words in sentences if len(words) >= 10).values())
    if repeated:
        notes.append(f"{repeated} repeated sentence(s) of 10+ words; check for repeated commentary or intentional Scripture")
    if _TEASERS.search(narration):
        notes.append("possible watch-to-the-end cue; check that the prayer delivers without withholding")
    return notes
