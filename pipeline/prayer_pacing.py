"""Cheap editorial hints for generated narration; never an upload gate."""
import re
from collections import Counter

_SENTENCE = re.compile(r"[.!?]+(?=\s|$)")
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_TEASERS = re.compile(r"\b(?:don['’]t (?:scroll|click away)|stay (?:with us )?(?:until|to) the end)\b", re.I)

_FORMAL_OPEN = re.compile(
    r"^(?:in conclusion|in summary|it is worth noting|let us now turn our attention|"
    r"in this devotional we will)\b", re.I
)


def pacing_notes(narration: str) -> list[str]:
    """Flag concrete issues, not predictions of retention or emotional impact."""
    parts = _SENTENCE.split(narration)
    sentences = [tuple(_WORD.findall(part.casefold().replace('’', "'")))
                 for part in parts]
    notes = []
    long_count = sum(len(words) > 40 for words in sentences)
    if long_count:
        notes.append(f"{long_count} sentence(s) over 40 words; check spoken breath and clarity")
    repeated = sum(count - 1 for count in Counter(words for words in sentences if len(words) >= 10).values())
    if repeated:
        notes.append(f"{repeated} repeated sentence(s) of 10+ words; check for repeated commentary or intentional Scripture")
    if _TEASERS.search(narration):
        notes.append("possible watch-to-the-end cue; check that the prayer delivers without withholding")
    formal = sum(bool(_FORMAL_OPEN.match(part.lstrip())) for part in parts)
    if formal:
        notes.append(f"{formal} essay-style transition(s); check whether a plain spoken transition would fit")
    return notes


SPOKEN_PRAYER_GUIDANCE = """WRITE FOR THE EAR, NOT THE PAGE:
- Speak to one listener. Choose one ordinary detail that belongs to this passage,
  this channel, and this moment in the day. Present it as a possibility, not as
  something you know about them. Don't invent a personal memory, testimony,
  credential, or conversation, and don't claim a human wrote or spoke this.
- In your own narration, choose everyday verbs and natural contractions where
  they fit. Use a short sentence at moments of weight; let the sentences around
  it carry the thought. Don't fake warmth with fragments, slang, or a string of
  rhetorical questions. Leave the exact KJV quotation untouched.
- When you talk to the listener, speak plainly. When you turn to God, give the
  listener words they could pray themselves. Let the turn be clear without
  announcing a section or explaining what the script is doing.
- On the silent read-through, replace broad introductions, stacked synonyms,
  and polished but empty transitions with one concrete thought or petition.
  If a line could fit any passage on any channel, make it belong to this one.
  Don't copy wording or use these instructions as a fixed rhythm for every video.
"""
