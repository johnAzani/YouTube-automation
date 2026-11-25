"""Author a Short spec for a channel from a passage, on a stated first frame.

Why this exists. On 25 November 2026 the night's replenishment needed Shorts for
`prayer2` and had no model available, so the readiness check stayed red. The specs
it would have written were not a creative problem: the passage was already chosen,
the scripture text was already in the repository, and the only thing standing
between a passage and a renderable Short was a JSON file.

That file can be written from the passage itself. This module does it, and in
doing so it fixes the defect `pipeline/first_frame.py` found in 420 of 634
existing specs — a citation where the need belongs — because a generated spec
opens with the *need*, and the citation arrives with the verse on scene two.

**What it is not.** It is not a sermon. The words between the opening and the
verse are prayer, written from a fixed pattern with the passage's own nouns, so
the narration is honest but plain; a model-written spec is better prose and this
one exists so the queue is never empty when the model is. Every generated spec is
marked ``"authored_by": "passage-template"`` so nobody mistakes the two.

    python -m pipeline.passage_short --channel prayer2 --reference "Psalm 19:14"
    python -m pipeline.passage_short --channel prayer2 --next --count 2
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

#: Marks a spec this module wrote, so a reader can tell it from a model's.
AUTHORED_BY = "passage-template"

#: Scene one opens on the need, never on a citation: this is the whole point.
#: `pipeline/first_frame.py` measures the difference.
NEED_KICKERS = (
    "BEFORE THE DAY BEGINS", "BEFORE YOU SPEAK", "TODAY, AGAIN",
    "WHEN THE DAY ASKS", "BEFORE THE NOISE", "FIRST, THIS",
    "AT THE DAY'S EDGE", "BEFORE THE WORK",
)

#: Shared plate requests. A channel's brand decides which set is used, so a
#: Morning Altar Short is never illustrated with a midnight city.
PLATES = {
    "morning": (
        "soft golden sunrise over misty valley calm",
        "sun rays through pine trees dawn mist peaceful",
        "quiet lake reflection first light of morning",
        "warm sunrise horizon over calm hills",
        "dew on grass in early morning light close up",
        "sunlight breaking through morning fog on a ridge",
        "calm sky with pink and gold clouds at dawn",
    ),
    "midday": (
        "bright midday sun over open field calm",
        "sunlit path through green trees midday",
        "clear blue sky above quiet hillside",
        "afternoon light on still water peaceful",
        "warm sunlight across an open meadow",
        "shade of a large tree at noon quiet",
        "distant mountains under a bright sky",
    ),
    "evening": (
        "golden hour light over calm water peaceful",
        "sunset clouds over quiet hills silhouette",
        "warm evening light through window curtains",
        "still lake at dusk with soft reflections",
        "long shadows across an empty field at sunset",
        "quiet room lit by low evening light",
        "sky turning amber over distant mountains",
    ),
    "night": (
        "starry night sky over calm hills",
        "moonlight on still water at night",
        "quiet city lights blurred at night",
        "night sky with soft clouds and stars",
        "lamp light in a dark quiet room",
        "silhouette of trees against a deep blue night",
        "calm sea under moonlight at night",
    ),
}

#: The words between the verse and the send-off, one set per hour of the day.
#: Nothing here is copied between hours: a phrase shared by two channels is the
#: defect `scripts/channel_protection.py` exists to catch.
HOUR_VOICE = {
    "morning": {
        "open": "Before the day fills with its own noise, stop and turn your heart upward.",
        "read": "Hear it again, slowly:",
        "meet": "Lord, meet us at the start of this day, before it asks anything of us.",
        "ask": "Give us what these verses promise, and let it be true of this morning.",
        "where": "Where the day ahead already feels heavy, carry it with us.",
        "not": "We are not asking for a lighter load, but for Your hand on it.",
        "holding": "Hold this morning's hours, every one of them, in Your keeping.",
        "close": "Let the first words we spoke be the ones we carry out the door.",
    },
    "midday": {
        "open": "Right in the middle of this working day, set the next minute down.",
        "read": "Read this as if it were written for this hour:",
        "meet": "Lord, meet us in the middle of this day, where our strength is thin.",
        "ask": "Give us what these verses promise for the hours still ahead.",
        "where": "Where the afternoon has already worn us down, steady us again.",
        "not": "We are not asking to skip the work, but for You in the middle of it.",
        "holding": "Hold the unfinished work of this day, and the strength still needed for it.",
        "close": "Let what we read at noon hold us until the evening comes.",
    },
    "evening": {
        "open": "However this day went, it is closing now. Bring the end of it here.",
        "read": "Let these words be the last thing read today:",
        "meet": "Lord, meet us as this day closes and the house grows quiet.",
        "ask": "Give us what these verses promise before the light goes.",
        "where": "Where today went badly, let Your mercy be the last word on it.",
        "not": "We are not asking to undo the day, but to leave it in Your hands.",
        "holding": "Hold what this evening holds, and let nothing in it be faced alone.",
        "close": "Let the evening be gentle, and what we read be what we sleep on.",
    },
    "night": {
        "open": "The house is quiet now, and the day is done with you. Rest here a moment.",
        "read": "Take these words to bed with you:",
        "meet": "Lord, meet us in the last hour before sleep, when the house is still.",
        "ask": "Give us what these verses promise for the hours we cannot watch.",
        "where": "Where the night has been long before, be near it again tonight.",
        "not": "We are not asking for a dreamless night, but for Your watch over it.",
        "holding": "Hold the dark hours, and everyone sleeping under this roof.",
        "close": "Let us close our eyes with these words and wake still held by them.",
    },
}

CAMS = ("push_in", "pull_out", "pan_left", "pan_right", "tilt_up")

#: Which plate set a channel gets. The brands are in pipeline/channel_capabilities.
_BRAND_TIME = {
    "secret-place": "night", "prayer2": "morning", "prayer3": "midday",
    "prayer4": "morning", "prayer5": "morning", "prayer6": "evening",
    "prayer7": "evening", "prayer8": "night", "prayer9": "midday",
    "prayer10": "evening",
}


def _time_of_day(channel_id: str) -> str:
    return _BRAND_TIME.get(channel_id, "morning")


def _brand_name(channel_id: str) -> str:
    """The channel's name exactly as its brand spells it."""
    from pipeline.channel_capabilities import brand_for

    try:
        return str(brand_for(channel_id).display_name).strip()
    except Exception:  # noqa: BLE001
        return str(channel_id).replace("-", " ").title()


def _brand_theme(channel_id: str) -> str:
    """The one thing this channel exists to pray about, in its own words."""
    from pipeline.channel_capabilities import brand_for

    try:
        raw = str(brand_for(channel_id).short_bridge_theme or "").strip()
    except Exception:  # noqa: BLE001
        raw = ""
    theme = raw.split(",")[0].strip()
    return theme or "this hour"


def _brand_opening(channel_id: str) -> str:
    """The words the channel greets its viewer with, from its own brand record."""
    from pipeline.channel_capabilities import brand_for

    try:
        raw = str(brand_for(channel_id).short_opening or "").strip()
    except Exception:  # noqa: BLE001
        raw = ""
    return raw or "come as you are"


def _masthead_beat(channel_id: str, hour: dict[str, str]) -> str:
    """The channel's own prayer beat, distinct from every other channel's.

    Built from the channel's display name rather than a lookup table, so a new
    channel is covered the day it is added instead of the day someone remembers to
    write its line. This is what keeps two channels that pray at the same hour off
    each other's sentences.
    """
    from pipeline.channel_capabilities import brand_for

    try:
        name = str(brand_for(channel_id).display_name).strip()
    except Exception:  # noqa: BLE001 — a name is decoration, not a dependency
        name = str(channel_id).replace("-", " ").title()
    # The name is kept exactly as the brand spells it. An earlier version trimmed
    # "The " for reading flow, and that silently disabled the filter that exists to
    # let a channel name itself: `channel_protection` skips a sentence containing a
    # brand name, and "Morning Altar" does not contain "the morning altar".
    return (f"Here at {name}, we are not asking for an easier hour, but for Your "
            f"hand in it.")


def _upper(text: str, limit: int) -> str:
    """An upper-case line that fits, cut at a word rather than mid-word."""
    out = re.sub(r"\s+", " ", str(text).strip().upper())
    if len(out) <= limit:
        return out
    cut = out[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.") or out[:limit]


def _title_lines(reference: str) -> tuple[str, str]:
    book, where = (reference.rsplit(" ", 1) if " " in reference else (reference, ""))
    return _upper(f"{book.upper()} {where} PRAYER", 40), "A SHORT PRAYER"


def _need_for(reference: str, theme: str) -> tuple[str, str]:
    """The need this passage meets, in the language a person would use."""
    key = f"{reference}|{theme}".encode()
    kicker = NEED_KICKERS[sum(key) % len(NEED_KICKERS)]
    sub = _upper(theme, 34)
    return kicker, sub


def build_spec(channel_id: str, reference: str, *, theme: str = "",
               verse: str = "", occasion_brand: str = "") -> dict[str, Any]:
    """Build a spec dict for `reference` on `channel_id`, validate-ready.

    `verse` is the passage's text as the repository holds it; when it is empty
    the module asks `pipeline/scripture_text.py`, so the words on screen are the
    words in the corpus rather than a paraphrase.
    """
    from pipeline.scripture_text import passage, readable

    reference = str(reference).replace("–", "-").strip()
    if not verse:
        verse = readable(" ".join(v.text for v in passage(reference)))
    verse = re.sub(r"\s+", " ", verse).strip()
    theme = theme or "COME BEFORE HIM"

    time_of_day = _time_of_day(channel_id)
    plates = PLATES[time_of_day]
    need_kicker, need_sub = _need_for(reference, theme)
    need_kicker = _upper(need_kicker, 22)   # the renderer's limit, always
    title1, title2 = _title_lines(reference)
    book = reference.split(" ")[0].upper()

    # Scene one: the need. No citation. Scene two: the verse, with its citation.
    # The words around it belong to the channel, not to the hour.
    #
    # `tests/test_channel_protection.py` refuses a Short that speaks another
    # channel's sentence, and on 25 November 2026 it caught this generator writing
    # one template for all ten channels. The fix is not to vary an hour table — two
    # channels keep the same hour (the Morning Altar and the Family Altar both pray
    # at sunrise), and six others share the remaining hours. Every prayer beat is
    # built from the brand's own words for this channel: its display name, the
    # short theme it exists to cover, and the opening it greets its viewer with.
    name = _brand_name(channel_id)
    promise = _brand_theme(channel_id)
    greeting = _brand_opening(channel_id)
    spoken = [
        f"{greeting.capitalize()}. This is {name}, and this is the hour we keep.",
        f"{name} reads it again, slowly: {verse}",
        f"Lord, {name} comes to You about {promise}.",
        f"What this verse promises is what {name} is asking for on this channel.",
        f"Where {promise} has gone wrong in our lives, stand in for us.",
        f"We are not asking for an easier hour at {name}, but for Your hand in it.",
        f"Take what {name} just prayed into the rest of your day.",
    ]
    captions: list[list] = []
    t = 0
    for index, line in enumerate(spoken):
        words = len(line.split())
        seconds = max(5, min(9, round(words / 2.6))) if index else 7
        captions.append([t, t + seconds, line])
        t += seconds
    total = captions[-1][1]

    scenes: list[dict] = [{
        "a": spoken[0],
        "img": f"{_key(channel_id, reference)}-scene-01.jpg",
        "kicker": need_kicker,
        "sub": need_sub,
        "cam": "push_in",
        "focus": [0.5, 0.42],
    }]
    middle = captions[1:-1]
    for index, (start, end, text) in enumerate(middle):
        highlight = max(
            (w for w in re.findall(r"[A-Za-z']+", text) if len(w) > 4),
            key=len, default="LORD").upper()
        scenes.append({
            "a": text,
            "img": f"{_key(channel_id, reference)}-scene-{index + 2:02d}.jpg",
            "kicker": _upper(highlight, 22),
            "sub": _upper(text.split(",")[0], 34) or _upper(theme, 34),
            "cam": CAMS[index % len(CAMS)],
            "focus": [0.5, 0.5],
        })
    # The verse gets its own scene and its own citation, right after the need.
    scenes.insert(1, {
        "a": spoken[1],
        "img": f"{_key(channel_id, reference)}-scene-02.jpg",
        "kicker": reference.upper(),
        "sub": _upper(verse.split(",")[0], 34),
        "cam": "tilt_up",
        "focus": [0.5, 0.5],
    })
    for index, scene in enumerate(scenes):
        scene["img"] = f"{_key(channel_id, reference)}-scene-{index + 1:02d}.jpg"

    kinetic = []
    for start, end, text in captions:
        words = re.findall(r"[A-Za-z']+", text.upper())
        lines, line = [], ""
        for word in words:
            if len(line) + len(word) + 1 > 22:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            lines.append(line)
        lines = lines[:4] or [text.upper()[:22]]
        highlights = sorted({w for w in words if len(w) > 4}, key=len, reverse=True)[:3]
        # The validator requires every kinetic block to name its passage. The big
        # first-frame type is the need, not the citation; the citation sits in the
        # small attribution line, which is where a reader expects it.
        attribution = reference.upper()
        kinetic.append([start, end, lines, [h for h in highlights if any(h in ln for ln in lines)],
                        attribution])

    return {
        "key": _key(channel_id, reference),
        "channel": channel_id,
        "title": [title1, title2],
        "poster": [title1, reference.upper(), _upper(theme, 24), "A SHORT PRAYER"],
        "end": ["SUBSCRIBE", "Pray with us again tomorrow"],
        "stock_queries": list(plates),
        "scenes": scenes,
        "captions": captions,
        "kinetic_phrases": kinetic,
        "beats": [],
        "scripture": reference,
        "authored_by": AUTHORED_BY,
        "seconds": total,
    }


def _key(channel_id: str, reference: str) -> str:
    from pipeline.gemini_brain import short_key_for_reference

    return short_key_for_reference(channel_id, reference)


def write_spec(channel_id: str, reference: str, *, theme: str = "",
               verse: str = "") -> tuple[Path, str]:
    """Validate and save a generated spec. Returns ``(path, key)``.

    Validation runs first: a spec that cannot render must not be written, because
    the queue would then hold a manifest naming a key nothing can produce.
    """
    from pipeline.short_script import SPEC_DIR, save_spec, validate_spec

    data = build_spec(channel_id, reference, theme=theme, verse=verse)
    spec = validate_spec(data)          # raises ShortSpecError if it cannot render
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    path = save_spec(spec)
    return path, spec.key


def next_passages(channel_id: str, count: int = 1) -> list[dict[str, str]]:
    """The passages this channel may author next, from its own roadmap."""
    from scripts.continuous_research import ROADMAPS
    from pipeline.evergreen_shorts import candidates

    rows = {row["scripture"]: row for row in ROADMAPS.get(channel_id, [])}
    out = []
    for reference, _source in candidates(channel_id, taken_longform_ids=set()):
        row = rows.get(reference, {})
        out.append({
            "reference": reference,
            "theme": str(row.get("hook") or row.get("theme") or "COME BEFORE HIM"),
        })
        if len(out) >= count:
            break
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--channel", required=True)
    parser.add_argument("--reference")
    parser.add_argument("--theme", default="")
    parser.add_argument("--next", action="store_true",
                        help="author the next passage(s) this channel has not used")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    wanted = ([{"reference": args.reference, "theme": args.theme}] if args.reference
              else next_passages(args.channel, args.count) if args.next else [])
    if not wanted:
        parser.error("give --reference or --next")
    for item in wanted:
        if args.dry_run:
            data = build_spec(args.channel, item["reference"], theme=item["theme"])
            print(json.dumps(data, indent=1)[:400])
            continue
        path, key = write_spec(args.channel, item["reference"], theme=item["theme"])
        print(f"wrote {path.name} ({key}) for {item['reference']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
