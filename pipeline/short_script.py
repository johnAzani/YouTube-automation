"""Short specs as data, so the brain can author them.

Why this module exists
----------------------
`tools/shorts.py` holds `SCRIPTS`: a dict of hand-written Short definitions. The
renderer is data-driven — it reads `stock_queries`, `scenes`, `captions`,
`kinetic_phrases` and `beats` and builds the video from them — but the *data* lived
inside a Python literal. That made a new Short a code change, so the queue filled
with manifests for keys that could never render.

A Short spec is therefore just JSON. Given a spec the renderer needs nothing else:
it fetches plates from the scene queries, TTS-synthesises the narration from the
captions, and cuts to the beats.

Every field here is validated before it can reach production, because the failure
mode of a plausible-but-wrong spec is an uploaded video with mislabelled scripture
or text that overflows a 9:16 safe area.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "content" / "shorts-scripts"

CAMS = ("push_in", "pull_out", "pan_left", "pan_right", "tilt_up")
BEAT_KINDS = ("quote", "phrase")

MIN_SCENES, MAX_SCENES = 6, 10
MAX_KICKER_CHARS = 22      # fits 9:16 at 1080 wide beside the safe edges
MAX_SUB_CHARS = 34
MIN_SECONDS, MAX_SECONDS = 30, 180   # the shipped Psalm 91 Short runs 107s
MIN_WORDS = 90             # ~35s of calm narration
MAX_WORDS = 165
#: Documentary Shorts keep a subscribe card after the voice. Prayer Shorts
#: must not: measured 17 November 2026, two Secret Place Shorts sat at 98.8%
#: and 99.6% viewed (Psalm 18:2, 54.3s; Psalm 139:11-12, 62.2s). The encoder
#: used to add 1.6s after the narration so the card could play. Average %
#: viewed is duration-relative; 1.6s is 3% of a 54s clip — the gap between
#: watching to the last word and a loop. Specs still carry `end: SUBSCRIBE`;
#: the renderer does not paint it onto a prayer Short.
DOCUMENTARY_TAIL_SECONDS = 1.6
PRAYER_TAIL_SECONDS = 0.0


def clip_length(narration_seconds, *, is_prayer):
    """How long the encoded Short is, given the narration."""
    narration_seconds = max(0.0, float(narration_seconds or 0.0))
    tail = PRAYER_TAIL_SECONDS if is_prayer else DOCUMENTARY_TAIL_SECONDS
    return narration_seconds + tail


def paints_subscribe_card(*, is_prayer):
    """Prayer Shorts loop. A subscribe card is a closer."""
    return not bool(is_prayer)

BANNED_NAMES = ("azani", "john azani", "narrated by")

PSALM_FINGERPRINTS = {
    23: ("the lord is my shepherd", "green pastures"),
    27: ("the lord is my light and my salvation", "whom shall i fear"),
    34: ("the angel of the lord", "magnify the lord with me"),
    46: ("god is our refuge and strength", "be still, and know"),
    91: ("he who dwells in the secret place", "no evil shall befall"),
    121: ("i lift up my eyes", "he who keeps you", "neither slumber nor sleep"),
}


class ShortSpecError(RuntimeError):
    """Raised when a spec must not be rendered."""


@dataclass
class ShortSpec:
    key: str
    psalm: int | None
    title: tuple[str, str]
    poster: tuple[str, str, str, str]
    end: tuple[str, str]
    stock_queries: list[str]
    scenes: list[dict]
    captions: list[list]           # [[start, end, text], ...]
    kinetic_phrases: list[list]    # [[start, end, [lines], [highlights], attribution], ...]
    beats: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    #: Mechanical defects this validator fixed rather than rejected, so a reader can
    #: see exactly what was changed on the model's behalf.
    repairs: list[str] = field(default_factory=list)
    scripture: str = ""
    channel: str = "secret-place"

    @property
    def narration_text(self) -> str:
        return " ".join(str(c[2]).strip() for c in self.captions)

    @property
    def words(self) -> int:
        return len(self.narration_text.split())

    def as_dict(self) -> dict:
        out = {
            "key": self.key, "channel": self.channel, "psalm": self.psalm, "title": list(self.title),
            "poster": list(self.poster), "end": list(self.end),
            "stock_queries": self.stock_queries, "scenes": self.scenes,
            "captions": self.captions, "kinetic_phrases": self.kinetic_phrases,
            "beats": self.beats, "words": self.words, "problems": self.problems,
        }
        if self.repairs:
            out["repairs"] = list(self.repairs)
        if self.scripture:
            out["scripture"] = self.scripture
        return out

    def to_renderer(self) -> dict:
        """The exact shape `tools/shorts.py` SCRIPTS expects."""
        return {
            "is_prayer": True,
            "authored_spec": True,
            "channel": self.channel,
            "title": self.title,
            "poster": self.poster,
            "midpoint_poster_window": None,
            "end": self.end,
            "out": f"{self.key}.mp4",
            "narration": f"{self.key}.mp3",
            "stock_queries": self.stock_queries,
            "scenes": self.scenes,
            "teases": [],
            "sfx_cues": [],
            "beats": self.beats,
            "captions": [tuple(c) for c in self.captions],
            "kinetic_phrases": [
                (k[0], k[1], list(k[2]), list(k[3]), k[4]) for k in self.kinetic_phrases
            ],
        }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _norm_words(text: str) -> str:
    """Comparison form: lowercase, punctuation flattened, whitespace collapsed.

    `_norm` only collapses whitespace, so an anchor that *is* verbatim still failed
    when the model ended it with a full stop and the narration carried a comma. On 6
    November that false rejection cost the Morning Altar both of its Shorts: each spec
    was rejected twice, and on a 20-request-a-day model the re-prompt is not free.
    Punctuation is not content.
    """
    lowered = str(text or "").lower().replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", lowered)).strip()


def validate_spec(data: dict, key: str | None = None,
                  channel_id: str | None = None) -> ShortSpec:
    """Return a validated ShortSpec, accumulating every problem rather than the first.

    `channel_id` is the channel the spec must belong to (a spec is written for
    exactly one channel's voice); it defaults to whatever the spec declares, and
    an unreadable/unknown declaration fails closed to channel 1 so an old spec
    without the field keeps working.
    """
    from .channels import normalize_channel_id

    problems: list[str] = []
    declared_channel = normalize_channel_id(
        channel_id if channel_id is not None else data.get("channel"))
    key = key or str(data.get("key", "")).strip()
    if not re.fullmatch(r"short-[a-z0-9]+", key or ""):
        problems.append(f"invalid key {key!r} (expected short-<slug>)")

    title = tuple(_norm(t) for t in (data.get("title") or ()))
    if len(title) != 2 or not all(title):
        problems.append("title must be two non-empty lines")

    poster = tuple(_norm(t) for t in (data.get("poster") or ()))
    if len(poster) != 4 or not all(poster):
        problems.append("poster must be four non-empty lines")

    end = tuple(_norm(t) for t in (data.get("end") or ()))
    if len(end) != 2 or not all(end):
        problems.append("end card must be two non-empty lines")

    scriptural = _norm(data.get("scripture", ""))
    psalm = data.get("psalm") if isinstance(data.get("psalm"), int) else None
    match = re.search(r"(?i)\bpsalm[s]?\s+(\d+)", scriptural)
    if match:
        psalm = int(match.group(1))

    scenes = list(data.get("scenes") or [])
    queries = [_norm(q) for q in (data.get("stock_queries") or [])]
    if not MIN_SCENES <= len(scenes) <= MAX_SCENES:
        problems.append(f"{len(scenes)} scenes; Shorts here use {MIN_SCENES}-{MAX_SCENES}")
    if len(queries) != len(scenes):
        problems.append(f"{len(queries)} stock queries for {len(scenes)} scenes — one per scene")

    for i, scene in enumerate(scenes):
        cam = scene.get("cam")
        if cam not in CAMS:
            problems.append(f"scene {i + 1}: cam {cam!r} not one of {CAMS}")
        focus = scene.get("focus")
        if not (isinstance(focus, (list, tuple)) and len(focus) == 2
                and all(isinstance(v, (int, float)) and 0.0 <= v <= 1.0 for v in focus)):
            problems.append(f"scene {i + 1}: focus must be two fractions in 0..1")
        kicker = _norm(scene.get("kicker", ""))
        sub = _norm(scene.get("sub", ""))
        if not kicker:
            problems.append(f"scene {i + 1}: empty kicker")
        elif len(kicker) > MAX_KICKER_CHARS:
            problems.append(f"scene {i + 1}: kicker {len(kicker)} chars > {MAX_KICKER_CHARS}")
        if not sub:
            problems.append(f"scene {i + 1}: empty sub line")
        elif len(sub) > MAX_SUB_CHARS:
            problems.append(f"scene {i + 1}: sub {len(sub)} chars > {MAX_SUB_CHARS}")
        if not _norm(scene.get("img", "")):
            problems.append(f"scene {i + 1}: missing img filename")

    captions = [list(c) for c in (data.get("captions") or [])]
    if not captions:
        problems.append("no captions, so there is no narration to synthesise")
    previous_end = -1
    for i, cap in enumerate(captions):
        if len(cap) != 3:
            problems.append(f"caption {i + 1}: expected [start, end, text]")
            continue
        start, stop, text = cap
        if not isinstance(start, int) or not isinstance(stop, int) or stop <= start:
            problems.append(f"caption {i + 1}: bad timing {start}-{stop}")
        if start < previous_end:
            problems.append(f"caption {i + 1}: overlaps the previous caption")
        previous_end = stop
        # Caption 1 is the swipe-window hook: three words can name a need
        # ("Can't sleep tonight?"). Later lines stay at four so a scene is a
        # thought, not a fragment. Existing queued specs are all well above both.
        min_line = MIN_FIRST_CAPTION_WORDS if i == 0 else 4
        if len(_norm(text).split()) < min_line:
            problems.append(f"caption {i + 1}: too short to be a narration line")

    spec_words = len(" ".join(_norm(c[2]) for c in captions if len(c) == 3).split())
    if not MIN_WORDS <= spec_words <= MAX_WORDS:
        problems.append(f"{spec_words} narration words; keep within {MIN_WORDS}-{MAX_WORDS}")
    if captions and isinstance(captions[-1][1], int) and captions[-1][1] > MAX_SECONDS:
        problems.append(f"last caption ends at {captions[-1][1]}s, over the {MAX_SECONDS}s ceiling")

    phrases = [list(k) for k in (data.get("kinetic_phrases") or [])]
    # A blank highlight word highlights nothing; it is a formatting defect, not a
    # reason to reject the Short and spend another two requests re-prompting. Strip
    # the empties and record it — the renderer treats an empty list as "no highlight"
    # exactly as it would for a phrase that never had one.
    repairs: list[str] = []
    for i, phrase in enumerate(phrases):
        if len(phrase) == 5 and isinstance(phrase[3], list):
            kept = [w for w in phrase[3] if _norm(w)]
            if len(kept) != len(phrase[3]):
                phrase[3] = kept
                repairs.append(f"kinetic phrase {i + 1}: dropped blank highlight word(s)")
    if len(phrases) != len(captions):
        problems.append(f"{len(phrases)} kinetic phrases for {len(captions)} captions — one per caption")
    for i, phrase in enumerate(phrases):
        if len(phrase) != 5:
            problems.append(f"kinetic phrase {i + 1}: expected 5 fields")
            continue
        _, _, lines, highlights, attrib = phrase
        if not lines or not all(_norm(line) for line in lines):
            problems.append(f"kinetic phrase {i + 1}: empty line")
        if not _norm(attrib):
            problems.append(f"kinetic phrase {i + 1}: missing attribution line")
        if highlights and not all(_norm(word) for word in highlights):
            problems.append(f"kinetic phrase {i + 1}: blank highlight word")

    beats = [dict(b) for b in (data.get("beats") or [])]
    narration = _norm_words(" ".join(_norm(c[2]) for c in captions if len(c) == 3))
    for i, beat in enumerate(beats):
        if beat.get("kind") not in BEAT_KINDS:
            problems.append(f"beat {i + 1}: kind {beat.get('kind')!r} not in {BEAT_KINDS}")
        anchor = _norm_words(beat.get("a", ""))
        if not anchor:
            problems.append(f"beat {i + 1}: missing anchor phrase")
        elif anchor not in narration:
            problems.append(f"beat {i + 1}: anchor {anchor!r} does not appear in the narration")
        if not beat.get("words"):
            problems.append(f"beat {i + 1}: no highlight words")

    text_all = " ".join([*title, *poster, *end, *queries,
                         *[_norm(s.get("kicker", "")) + " " + _norm(s.get("sub", "")) for s in scenes],
                         *[" ".join(map(str, k[2])) for k in phrases if len(k) == 5]]).lower()
    for name in BANNED_NAMES:
        if name in text_all:
            problems.append(f"creator name leaked: {name}")

    if psalm is not None:
        lowered = narration + " " + " ".join(queries).lower() + " " + text_all
        leaked = sorted(
            other for other, prints in PSALM_FINGERPRINTS.items()
            if other != psalm and any(p in lowered for p in prints)
        )
        if leaked:
            problems.append(f"spec quotes Psalm {leaked} but declares Psalm {psalm}")

    return ShortSpec(
        key=key, psalm=psalm, title=title, poster=poster, end=end,
        stock_queries=queries, scenes=scenes, captions=captions,
        kinetic_phrases=phrases, beats=beats, problems=problems,
        repairs=repairs, scripture=scriptural, channel=declared_channel,
    )


def foreign_wording(spec: ShortSpec) -> str | None:
    """Another channel's wording carried by this Short, or ``None``.

    The long-form check (`GeminiBrain._check_channel_brand`) was never applied to
    Shorts. On 15 November 2026 The Family Altar published a Short whose prayer
    said "every bedtime prayer", which is The Secret Place's wording, and the
    test that reads every published description turned `main` red the next day.

    The spoken words are checked as written. The on-screen lines are checked in
    lower case, because they are always set in capitals and a verse set in
    capitals ("DWELL IN THE SECRET PLACE", Psalm 91:1) would otherwise read as a
    channel's name: that mistake stopped The Covenant Shield for days.

    This is asked when a Short is written, not in `validate_spec`: a Short that
    is already published is a record and must keep loading.
    """
    from .channel_capabilities import off_brand_phrase

    spoken = off_brand_phrase(spec.narration_text, spec.channel)
    if spoken:
        return spoken
    shown = " ".join([
        *map(str, spec.title), *map(str, spec.poster), *map(str, spec.end),
        *[f"{scene.get('kicker', '')} {scene.get('sub', '')}" for scene in spec.scenes],
    ]).lower()
    return off_brand_phrase(shown, spec.channel)


def require_valid(spec: ShortSpec) -> ShortSpec:
    if spec.problems:
        raise ShortSpecError("; ".join(spec.problems[:4]))
    return spec


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
def spec_path(key: str) -> Path:
    return SPEC_DIR / f"{key}.json"


def save_spec(spec: ShortSpec) -> Path:
    require_valid(spec)
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in spec.as_dict().items() if k not in {"words", "problems"}}
    path = spec_path(spec.key)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_spec(path: Path) -> ShortSpec:
    data = json.loads(path.read_text(encoding="utf-8"))
    return validate_spec(data, key=data.get("key") or path.stem)


def load_authored() -> dict[str, dict]:
    """Valid specs, in the shape `tools/shorts.py` merges into SCRIPTS.

    Invalid specs are skipped with a printed reason rather than crashing a render:
    one bad authored Short must not take down the whole renderer.
    """
    out: dict[str, dict] = {}
    if not SPEC_DIR.is_dir():
        return out
    for path in sorted(SPEC_DIR.glob("*.json")):
        try:
            spec = load_spec(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[short-script] skipping {path.name}: {exc}")
            continue
        if spec.problems:
            print(f"[short-script] skipping {path.name}: {'; '.join(spec.problems[:2])}")
            continue
        out[spec.key] = spec.to_renderer()
    return out


def authored_keys() -> set[str]:
    return set(load_authored())


# --------------------------------------------------------------------------- #
# Model contract
# --------------------------------------------------------------------------- #
PROMPT = """You are writing a 9:16 YouTube Short for {channel_label}.

Return ONLY compact JSON matching this schema, no prose and no code fences:

{{
  "key": "{key}",
  "scripture": "{scripture}",
  "title": ["LINE ONE", "LINE TWO"],
  "poster": ["LINE", "LINE", "LINE", "LINE"],
  "end": ["SUBSCRIBE", "{end_card}"],
  "stock_queries": ["calm mountain lake night", "..."],
  "scenes": [
    {{"a": "anchor phrase", "img": "{key}-scene-01.jpg", "kicker": "STILL HERE",
      "sub": "THE THING YOU CARRIED", "cam": "push_in", "focus": [0.5, 0.45]}}
  ],
  "captions": [[0, 3, "The thing you carried is still here."], [3, 12, "Second line."]],
  "kinetic_phrases": [[0, 3, ["STILL HERE"], ["HERE"], "PSALM NN : 1"]],
  "beats": [{{"a": "anchor phrase", "kind": "phrase", "words": ["HIGHLIGHT", "WORDS"], "hi": 0, "slot": "C"}}]
}}

HARD RULES — violations are rejected by code:
- The narration must be about {words} words (never under {floor}, never over
  {ceiling}), a calm second-person {prayer_kind} prayer, {min_seconds}-{max_seconds}
  seconds when read slowly. After the opening it quotes the scripture once,
  prays, and closes so the clip can replay.

THE FIRST THREE SECONDS — YouTube scores a Short on whether a stranger stays
or swipes in this window (percent who chose to view, then average percent viewed):
- Caption 1 ends at or before second {first_end}. It is {first_caption_words}
  words or fewer (never under 3), said to one person, naming the exact moment
  or need this scripture meets: the hour, the room, the weight still in the
  hand, the thought that will not lie down. A stranger who hears only those
  words must know this prayer is for them today.
- Sentence one of the whole narration is {hook_words} words or fewer and is
  that same caption, not a greeting stretched across eight seconds.
- This channel's mood is "{opening}". That is the mood, NOT the first sentence:
  do not open with those words, with a greeting, with the channel's name, or
  with a general invitation to breathe, pause, gather, rise or welcome the day.
- Do not reuse the opening of an earlier Short on this channel.{avoid_block}
- Never open with these worn first three words (they are already a template):
  "If you are", "Take a deep", "Rise in spirit", "Gather your home",
  "Close your eyes", "Bring every weary", "Welcome".
- Honest only: no "don't scroll", no "watch to the end", no promised outcome.
- Scene 1 is the first picture a stranger sees. Its kicker is the need in
  2-4 words (the weight, the hour, the room), never the scripture reference
  and never the channel's name. The reference belongs in later scenes and in
  kinetic attribution. Sub restates the moment, not a greeting.
- kinetic_phrases[0] uses the same start and end as caption 1 (ends by second
  {first_end}), and its stacked lines ARE those opening words, not the verse.

THE LAST SENTENCE — the clip restarts itself:
- Do not speak "subscribe", "follow", or "type amen". The renderer does not
  paint a subscribe card after the last word: the next frame is caption 1
  again. A spoken closer is a reason to swipe as the loop begins.
- The last spoken line may say Amen, then restates the opening need in a few
  words so a listener who stayed hears the first line again as it restarts.

{spoken_prayer_guidance}
THE PRAYER — give the listener words to pray with you:
- Carry the opening's specific need into one direct petition to God grounded
  in the quoted verse. Keep the channel's mood and speak to one listener;
  don't spend the remaining time explaining or repeating the opening.
- Make the title and poster promise something the narration actually prays for.
  Once the verse has been read, move straight into prayer; no second hook or
  recap. Let the petition finish before the single subscribe invitation.
- Silently read the captions in order before returning. Fix lines that sound
  breathless or repeat an idea, while preserving exact Scripture and the word
  and timing requirements. The last prayer line should finish the thought in
  the opening even for a viewer who never watches the companion long-form.
- Keep the petition honest even if nothing changes today. Don't tell listeners
  what they must feel or imply that subscribing makes the prayer more effective.

- Quote ONLY {scripture}. Never quote another psalm or verse reference.
{scripture_block}- One `stock_queries` entry per scene, describing {imagery} imagery suitable for
  a {prayer_kind} prayer (no people's faces, no text in the image).
- kicker <= {kicker} characters, sub <= {sub} characters, ALL CAPS.
- cam is one of {cams}. focus is [x, y] with x/y between 0 and 1.
- `kinetic_phrases` has exactly one entry per caption, same start/end seconds, with
  2-5 ALL-CAPS stacked lines covering the spoken words of that caption (3-6 words
  per line so each word illuminates as spoken) and ALL-CAPS highlight words.
- Every `beats[].a` anchor MUST be copied verbatim from the narration.
- No personal names, no "narrated by", no clickbait, no promises of healing.
{foreign_block}"""


#: Narration length asked of the model. The validator accepts MIN_WORDS-MAX_WORDS;
#: the target sits well inside it so an undershoot still passes.
#:
#: Measured 13 November 2026 on published Shorts at least two days old:
#: 90-99 words, median 114 views (10 Shorts); 100-114 words, 70 (22); 115-129
#: words, 56 (20). Small numbers and mixed channels, so this is a nudge toward
#: the shorter end, not a new floor.
TARGET_WORDS = 105
TARGET_WORDS_RANGE = (95, 118)
#: Longest opening sentence asked for. The view counts do not prove a specific
#: opening wins (the same stock line drew 104 views one day and 0 the next);
#: the reasons are that a Short is kept or swiped in its first seconds, and that
#: one opening line repeated across a channel's Shorts is templated content.
MAX_HOOK_WORDS = 16
#: Caption 1 is the swipe window. Measured 17 November 2026 on 353 authored
#: specs: every first caption ended after second 3 (median 8s, 15 words).
#: YouTube Help (Shorts search & discovery) ranks on "% of viewers who chose
#: to view", then average view duration and average % viewed. The example in
#: this prompt used to be ``[0, 8, ...]``, which is what the model copied.
MAX_FIRST_CAPTION_END = 3
MAX_FIRST_CAPTION_WORDS = 8
MIN_FIRST_CAPTION_WORDS = 3
#: First-three-word skeletons that have already become a template. Counted
#: on the same 353 specs: "if you are" 36, "take a deep" 8, "rise in spirit" 8,
#: "gather your home" 6, "close your eyes" 5, "bring every weary" 4, plus
#: openings that start "welcome".
WORN_HOOK_PREFIXES = (
    "if you are",
    "take a deep",
    "rise in spirit",
    "gather your home",
    "close your eyes",
    "bring every weary",
    "welcome",
)
#: How many of the channel's most recent openings the model is shown, to avoid.
RECENT_OPENINGS_SHOWN = 8
#: Scene-1 HUD. Counted 17 November 2026 on 353 specs: 285 first kickers were
#: a book+chapter ("PSALM 23:1", "PROVERBS 16:3"). The prompt's scene example
#: was ``"kicker": "PSALM NN:1"``. A stranger scrolling a muted autoplay reads
#: a citation, not a reason to stay. The reference belongs on later scenes.
VERSE_KICKER_RE = re.compile(
    r"(?i)^(?:\d+\s+)?(?:"
    r"psalm|proverbs|isaiah|matthew|mark|luke|john|acts|romans|"
    r"corinthians|galatians|ephesians|philippians|colossians|"
    r"thessalonians|timothy|titus|philemon|hebrews|james|peter|"
    r"jude|revelation|genesis|exodus|leviticus|numbers|deuteronomy|"
    r"joshua|judges|ruth|samuel|kings|chronicles|ezra|nehemiah|"
    r"esther|job|ecclesiastes|jeremiah|lamentations|ezekiel|daniel|"
    r"hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|zephaniah|"
    r"haggai|zechariah|malachi"
    r")s?\s+\d"
)
CHANNEL_KICKER_RE = re.compile(
    r"(?i)^(?:the\s+)?(?:"
    r"secret place|morning altar|midday watch|midnight watch|"
    r"family altar|healing balm|provision table|covenant shield|"
    r"praise garden|guided path"
    r")\s*$"
)


def first_sentence(text: str) -> str:
    """The opening sentence of a narration."""
    parts = re.split(r"(?<=[.!?])\s+", " ".join(str(text or "").split()), maxsplit=1)
    return parts[0].strip() if parts and parts[0] else ""


def authoring_defects(spec: ShortSpec) -> list[str]:
    """Reasons a NEW Short must not be saved. Existing specs still load.

    ``validate_spec`` is the load path: a queued Short with an eight-second
    first caption has to keep rendering. These checks run only when the brain
    authors, so the model is asked again instead of shipping another swipe.
    """
    defects: list[str] = []
    if spec.captions and len(spec.captions[0]) == 3:
        _start, stop, text = spec.captions[0]
        words = _norm(text).split()
        if isinstance(stop, int) and stop > MAX_FIRST_CAPTION_END:
            defects.append(
                f"first caption ends at {stop}s; the swipe happens by second "
                f"{MAX_FIRST_CAPTION_END}"
            )
        if len(words) > MAX_FIRST_CAPTION_WORDS:
            defects.append(
                f"first caption is {len(words)} words; keep it to "
                f"{MAX_FIRST_CAPTION_WORDS} so it lands in three seconds"
            )
        opening = first_sentence(spec.narration_text)
        folded = _norm_words(opening)
        for prefix in WORN_HOOK_PREFIXES:
            if folded.startswith(prefix):
                defects.append(f"opening starts with worn skeleton {prefix!r}")
                break
    if spec.captions and len(spec.captions[-1]) == 3:
        last = str(spec.captions[-1][2] or "")
        if re.search(r"\bsubscribe\b|\bfollow\b|type amen", last, re.I):
            defects.append(
                "last caption speaks subscribe; that belongs on the end card "
                "so the loop can restart"
            )
    if spec.scenes:
        kicker = _norm(spec.scenes[0].get("kicker", ""))
        if VERSE_KICKER_RE.search(kicker):
            defects.append(
                f"scene 1 kicker {kicker!r} is a scripture citation; the first "
                "picture must name the need, and the verse belongs on later scenes"
            )
        if CHANNEL_KICKER_RE.search(kicker):
            defects.append(
                f"scene 1 kicker {kicker!r} is the channel's name; a stranger "
                "scrolling has not come here for the brand"
            )
    if spec.kinetic_phrases and len(spec.kinetic_phrases[0]) >= 3:
        kin_end = spec.kinetic_phrases[0][1]
        kin_lines = spec.kinetic_phrases[0][2] or []
        kin_words = " ".join(str(line) for line in kin_lines).split()
        if isinstance(kin_end, int) and kin_end > MAX_FIRST_CAPTION_END:
            defects.append(
                f"first on-screen phrase ends at {kin_end}s; it has to match "
                f"caption 1 and land by second {MAX_FIRST_CAPTION_END}"
            )
        if len(kin_words) > MAX_FIRST_CAPTION_WORDS:
            defects.append(
                f"first on-screen phrase is {len(kin_words)} words; keep it to "
                f"{MAX_FIRST_CAPTION_WORDS} so the first picture is the hook"
            )
    return defects


def recent_openings(channel_id: str | None, limit: int = RECENT_OPENINGS_SHOWN,
                    spec_dir: Path | None = None) -> list[str]:
    """Openings this channel's Shorts have already used, most overused first.

    On 13 November every Family Altar Short began "Gather your home and loved
    ones in faith", every Midnight Watch Short "Rise in spirit at this midnight
    hour": the prompt handed the model one stock invitation per channel and the
    model used it. Showing it what the channel has already said is how it is
    asked not to say it again.

    One example per distinct first three words, ordered by how many Shorts
    start that way, so the most worn skeleton is always in the list. (File
    times are useless for "newest": a fresh checkout stamps every file alike.)
    A spec that cannot be read is skipped: this list is advice to the model and
    must never stop a Short being written.
    """
    from .channels import normalize_channel_id

    directory = SPEC_DIR if spec_dir is None else spec_dir
    wanted = normalize_channel_id(channel_id)
    if not directory.is_dir():
        return []
    by_start: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            spec = load_spec(path)
            if normalize_channel_id(spec.channel) != wanted:
                continue
            opening = first_sentence(spec.narration_text)
        except Exception:  # noqa: BLE001
            continue
        if not opening:
            continue
        start = " ".join(_norm_words(opening).split()[:3])
        by_start.setdefault(start, []).append(opening)
    ranked = sorted(by_start.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return [min(group, key=len) for _start, group in ranked[:max(0, limit)]]


def build_prompt(scripture: str, key: str = "short-psalmNN", words: int = TARGET_WORDS,
                 channel_id: str | None = None,
                 avoid_openings: list[str] | None = None,
                 occasion: str = "") -> str:
    """The model contract, in the voice of the channel the Short belongs to."""
    from .channel_capabilities import brand_for

    brand = brand_for(channel_id)
    if avoid_openings is None:
        try:
            avoid_openings = recent_openings(channel_id)
        except Exception:  # noqa: BLE001
            avoid_openings = []
    avoid_block = ""
    if avoid_openings:
        listed = "\n".join(f'    - "{o[:140]}"' for o in avoid_openings[:RECENT_OPENINGS_SHOWN])
        avoid_block = ("\n  This channel has already opened Shorts with these lines. Do not start"
                       "\n  with any of them, or with their first three words:\n" + listed)
    # The writer is shown the verses and told to copy them: a reference alone
    # left the quotation to the model's memory (pipeline/scripture_text.py).
    from .scripture_text import prompt_block

    occasion_block = ""
    if occasion:
        occasion_block = (
            f"\nTHE DAY THIS SHORT IS FOR — {occasion}.\n"
            "- The opening sentence or the first line of prayer names the day plainly, the\n"
            "  way a person would say it to a friend. The prayer is about this day; it is\n"
            "  not a general prayer with the day's name attached.\n"
            "- Do not name a date or a year: this Short may be watched in other years.\n")
    # Wording that belongs to the other channels. The writer is told, so a Short is
    # not written, refused by `foreign_wording` and written again on free quota.
    theirs = [phrase for phrase in brand.forbidden_phrases
              if not phrase.startswith("@") and phrase == phrase.lower()]
    foreign_block = ""
    if theirs:
        foreign_block = ("- These words belong to other channels. Do not use them, spoken or on\n"
                         "  screen, unless the scripture itself says them: "
                         + "; ".join(f'"{phrase}"' for phrase in theirs) + ".\n")
    from .prayer_pacing import SPOKEN_PRAYER_GUIDANCE

    return PROMPT.format(
        spoken_prayer_guidance=SPOKEN_PRAYER_GUIDANCE,
        key=key, scripture=scripture, words=words, foreign_block=foreign_block,
        scripture_block=prompt_block(scripture) + occasion_block,
        floor=max(MIN_WORDS, TARGET_WORDS_RANGE[0]), ceiling=TARGET_WORDS_RANGE[1],
        hook_words=MAX_HOOK_WORDS, first_end=MAX_FIRST_CAPTION_END,
        first_caption_words=MAX_FIRST_CAPTION_WORDS, avoid_block=avoid_block,
        min_seconds=MIN_SECONDS, max_seconds=MAX_SECONDS,
        kicker=MAX_KICKER_CHARS, sub=MAX_SUB_CHARS, cams=list(CAMS),
        channel_label=brand.short_channel_label,
        end_card=brand.short_end_card,
        prayer_kind=brand.short_prayer_kind,
        opening=brand.short_opening,
        imagery=brand.short_imagery,
    )


def parse_model_json(text: str) -> dict:
    """Accept a bare object, or one wrapped in prose/backticks, and return the dict."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ShortSpecError("model returned no JSON object")
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ShortSpecError(f"model JSON did not parse: {exc}") from exc
