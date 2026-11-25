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
    prayer_body = [
        f"Lord, You have not left this hour to us alone. Meet us here in {theme.lower()}.",
        f"Your word says it plainly: {verse}",
        f"So we ask for what this verse promises. Let it be true of us today, not only read.",
        f"Where our own strength runs out, stand in for us. Where our thoughts wander, call them home.",
        f"We are not asking for an easier day, but for Your presence through this one.",
        f"Keep us steady, and let what we have read shape what we do next.",
        "Get up and carry His words with you.",
    ]
    captions: list[list] = []
    t = 0
    first = f"Before this hour fills with its own noise, stop and turn your heart to God."
    captions.append([0, 7, first])
    t = 7
    for line in [f"Your word says it plainly: {verse}"] + prayer_body[2:]:
        words = len(line.split())
        seconds = max(5, min(9, round(words / 2.6)))
        captions.append([t, t + seconds, line])
        t += seconds
    # The last line is a send-off, not a prayer; keep it short and last.
    total = captions[-1][1]

    scenes: list[dict] = [{
        "a": first,
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
        "a": f"Your word says it plainly: {verse}",
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
