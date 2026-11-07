"""The Shorts poster: a native 9:16 thumbnail, measured before it is written.

Why this module exists
----------------------
Until 2026-11-03 the YouTube Data API refused custom thumbnails for Shorts, so
`pipeline/upload.py` returned `by_design_short` and `pipeline/short_release.py`
recorded `not_supported_for_shorts` without ever calling the API. That premise
changed: the thumbnails.set documentation (last updated 2026-11-03 UTC) now says
it "sets it for a video, including YouTube Shorts", and the thumbnails resource
gained `shortsAspectRatio` for the 9:16 variant.

The art had to change with it. The old path rendered a 1280x720 landscape plate
whose docstring claimed the lockup "fits cleanly inside the center 405x720 (9:16)
column". Measured on 2026-11-07: "PSALM" at 126px is 459px wide, so YouTube's own
crop rule -- "For YouTube Shorts, the image is cropped to a 9:16 portrait aspect
ratio" -- would have sliced the first and last letters off, then upscaled the
surviving 405px strip 2.67x to fill a 1080px tile.

This module renders the poster at the size the surface actually uses, with the
same lockup language as `tools/shorts.py::poster_lockup_overlay` (kicker ribbon,
two display lines, gold rule, pill), and it measures what the studio engine
measures for long form: WCAG contrast of the hero against the pixels behind it
(floor `thumbnail_studio.MIN_CONTRAST`), and that every word lands inside the
Shorts UI safe zone. It refuses to write an image that fails either check.

Design constants are the Shorts player's, not ours:
  * canvas 1080x1920 (9:16, the size YouTube documents for Shorts thumbnails);
  * safe box (72, 200, 1008, 1500): the title/channel overlay owns the bottom
    ~20%, the like/comment rail the right ~15%, the status bar the top ~7%.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .channel_capabilities import brand_for
from .config import REPO_ROOT
from .thumbnail_studio import MIN_CONTRAST, contrast_ratio

#: Bumped when the artwork changes, so receipts can be repaired without guessing.
POSTER_REVISION = "shorts-poster-v1"

CANVAS = (1080, 1920)
#: left, top, right, bottom — everything a viewer must read goes in here.
SAFE_BOX = (72, 200, 1008, 1500)

PLATE_DIR = REPO_ROOT / "image-search"
DEFAULT_PLATE = "short-prayer-cover-poster.jpg"
SPECS_DIR = REPO_ROOT / "content" / "shorts-scripts"

CARD_FILL = (8, 22, 52, 216)
GOLD = (255, 218, 64)
WHITE = (255, 255, 255)
PALE_GOLD = (255, 206, 60)


class PosterRefused(RuntimeError):
    """The poster could not be made legible. Better no upload than a muddy one."""


@dataclass
class PosterReport:
    path: Path
    width: int
    height: int
    contrast: float
    hero_px: int
    kicker: str
    lines: tuple[str, ...]
    plate: str
    grade: str
    safe_zone_ok: bool
    notes: list[str] = field(default_factory=list)

    @property
    def revision(self) -> str:
        return POSTER_REVISION

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "contrast": round(self.contrast, 2),
            "hero_px": self.hero_px,
            "kicker": self.kicker,
            "lines": list(self.lines),
            "plate": self.plate,
            "grade": self.grade,
            "safe_zone_ok": self.safe_zone_ok,
            "revision": POSTER_REVISION,
        }


def _font_dir() -> Path:
    return REPO_ROOT / "assets" / "fonts"


def _font(size: int, weight: str = "Black"):
    from PIL import ImageFont

    return ImageFont.truetype(str(_font_dir() / f"Inter-{weight}.ttf"), size)


def grade_for(channel_id: Optional[str] = None) -> str:
    """The daypart the channel lives in: night / dawn / noon."""
    kind = (brand_for(channel_id).short_prayer_kind or "").strip().lower()
    return {"pre-sleep": "night", "sunrise": "dawn", "midday": "noon"}.get(kind, "night")


def kicker_for(channel_id: Optional[str] = None) -> str:
    """The ribbon above the lockup, in the channel's own daypart."""
    return brand_for(channel_id).shorts_poster_kicker


def kicker_is_redundant(kicker: str, lines: Sequence[str], threshold: float = 0.5) -> bool:
    """True when the ribbon just says the hero again.

    "BEGIN YOUR DAY IN PRAYER" over the authored hero "BEGIN YOUR / DAY IN QUIET
    / PRAYER WITH" repeats three of its four words in 200 px of premium space. The
    ribbon is a daypart cue, not a second headline: when it echoes the lockup it
    is dropped and the card gives that space back to the hero.
    """
    import re as _re

    def _tokens(text: str) -> set[str]:
        return {t for t in _re.findall(r"[A-Z0-9$']{3,}", str(text).upper())}

    ribbon = _tokens(kicker)
    if not ribbon:
        return False
    hero = _tokens(" ".join(str(x) for x in (lines or [])[:2]))
    return len(ribbon & hero) / len(ribbon) >= threshold


def poster_lines(spec: dict) -> tuple[str, str, str, str]:
    """Read the four authored poster lines out of a Short spec.

    The brain authors one four-line lockup, not four labelled slots. The old
    thumbnail path used line 0 as a kicker pill and line 3 as a tag pill and threw
    the hook away, which is how a Morning Altar Short ended up reading
    "BEGIN YOUR / MARK / 1 / THE MORNING ALTAR".
    """
    raw = [str(x).strip() for x in (spec.get("poster") or []) if str(x).strip()]
    while len(raw) < 4:
        raw.append("")
    h1, h2, sub, tag = raw[0], raw[1], raw[2], raw[3]

    # The brain authors one four-line *stack*, which reads "BEGIN YOUR / DAY IN
    # QUIET / PRAYER WITH / THE MORNING ALTAR". Painted as a poster, line 2 is a
    # dangling connector and line 3 is the phrase completing it: fold them into
    # the gold sub-line instead of printing "PRAYER WITH" under a rule.
    connectors = {"WITH", "AND", "IN", "OF", "TO", "FOR", "ON", "BY", "THE", "A",
                  "AN", "MY", "YOUR", "OUR", "AT"}
    words = sub.upper().split()
    if sub and tag and words and words[-1] in connectors:
        sub, tag = f"{sub} {tag}", ""
    return h1, h2, sub, tag


def spec_path_for_key(key: str) -> Optional[Path]:
    path = SPECS_DIR / f"{key}.json"
    return path if path.is_file() else None


def spec_path_for_slug(slug: str) -> Optional[Path]:
    """Find the spec a published receipt came from, by slug prefix.

    Receipts name the artifact (`short-psalm91v11-pre-sleep-prayer`), specs name
    the key (`short-psalm91v11`). Repairing a live Short must not depend on the
    queue still holding the manifest.
    """
    text = (slug or "").strip().lower()
    if not text or not SPECS_DIR.is_dir():
        return None
    best: Optional[Path] = None
    for candidate in sorted(SPECS_DIR.glob("*.json")):
        if text.startswith(candidate.stem.lower()):
            if best is None or len(candidate.stem) > len(best.stem):
                best = candidate
    return best


def _plate_image(plate: Optional[str]):
    from PIL import Image

    name = (plate or DEFAULT_PLATE).strip()
    for base in (PLATE_DIR, REPO_ROOT / "assets"):
        path = base / name if name else None
        if path and path.is_file():
            return Image.open(path).convert("RGB")
    return None


def _cover_crop(img, size: tuple[int, int]):
    from PIL import Image

    w, h = size
    scale = max(w / max(1, img.width), h / max(1, img.height))
    resized = img.resize((max(w, int(img.width * scale)), max(h, int(img.height * scale))),
                         Image.Resampling.LANCZOS)
    x0, y0 = (resized.width - w) // 2, (resized.height - h) // 2
    return resized.crop((x0, y0, x0 + w, y0 + h))


def _duotone(img, shadow, mid, high, blend: float):
    """Map luminance through a three-stop ramp, then blend with the source."""
    from PIL import Image

    lifted = img.point([min(255, int(v * 1.06)) for v in range(256)] * 3)
    lum = lifted.convert("L")
    ramps = []
    for chan in range(3):
        lut = []
        for i in range(256):
            t = i / 255.0
            if t < 0.54:
                u = t / 0.54
                c = shadow[chan] + (mid[chan] - shadow[chan]) * u
            else:
                u = (t - 0.54) / 0.46
                c = mid[chan] + (high[chan] - mid[chan]) * (u ** 1.08)
            lut.append(int(max(0, min(255, c))))
        ramps.append(lum.point(lut))
    duo = Image.merge("RGB", tuple(ramps))
    return Image.blend(lifted, duo, blend)


#: One plate, three dayparts. The channel's `short_prayer_kind` picks the ramp, so
#: a sunrise Short is not dressed in the night channel's navy (parity, 2026-11-07).
_GRADES = {
    "night": {"shadow": (4, 14, 40), "mid": (16, 62, 136), "high": (196, 226, 255),
              "blend": 0.78, "brightness": 0.62, "tint": ((8, 22, 52), 0.45)},
    "dawn": {"shadow": (28, 16, 34), "mid": (150, 92, 74), "high": (255, 226, 176),
             "blend": 0.62, "brightness": 0.74, "tint": ((42, 26, 40), 0.36)},
    "noon": {"shadow": (18, 30, 38), "mid": (120, 150, 156), "high": (246, 250, 240),
             "blend": 0.55, "brightness": 0.80, "tint": ((16, 34, 44), 0.30)},
}


def _background(size: tuple[int, int], plate: Optional[str], grade: str):
    from PIL import Image, ImageEnhance

    spec = _GRADES.get(grade, _GRADES["night"])
    w, h = size
    img = _plate_image(plate)
    if img is None:
        # No plate is not a reason to fail the release: paint the gradient the
        # studio engine uses for its own scenes.
        from .thumbnail_studio import _vertical_gradient, Palette, NAVY_MOON

        img = _vertical_gradient(size, NAVY_MOON.sky_top, NAVY_MOON.sky_bottom)
    img = _cover_crop(img, size)
    img = _duotone(img, spec["shadow"], spec["mid"], spec["high"], spec["blend"])
    img = ImageEnhance.Brightness(img).enhance(spec["brightness"])
    tint_colour, tint_alpha = spec["tint"]
    img = Image.blend(img, Image.new("RGB", (w, h), tint_colour), tint_alpha)
    return img.convert("RGBA")


def _fit(draw, text: str, max_width: int, start: int, floor: int = 40):
    size = start
    while size > floor and draw.textlength(text, font=_font(size)) > max_width:
        size -= 2
    return _font(size)


def _text_box(draw, text: str, font, xy) -> tuple[int, int, int, int]:
    x, y = xy
    left, top, right, bottom = draw.textbbox((x, y), text, font=font)
    return int(left), int(top), int(right), int(bottom)


def _inside(box, safe) -> bool:
    return box[0] >= safe[0] and box[1] >= safe[1] and box[2] <= safe[2] and box[3] <= safe[3]


def render_shorts_poster(
    out_path: Path,
    *,
    lines: Sequence[str],
    kicker: Optional[str] = None,
    channel_id: Optional[str] = None,
    plate: Optional[str] = None,
    grade: Optional[str] = None,
) -> PosterReport:
    """Render and measure a 1080x1920 Shorts poster. Raises if it is not legible."""
    from PIL import Image, ImageDraw, ImageFilter

    hero1, hero2, sub, tag = (list(lines) + ["", "", "", ""])[:4]
    notes: list[str] = []
    if not str(tag).strip():
        # Every poster carries the channel, even when the copy came from a title
        # rather than an authored spec: an unbranded card is a card nobody can
        # attribute on a search results page.
        tag = (brand_for(channel_id).display_name or "").strip().upper()
    grade_name = grade or grade_for(channel_id)
    kicker = (kicker or "").strip() or kicker_for(channel_id)
    if kicker and kicker_is_redundant(kicker, (hero1, hero2, sub, tag)):
        notes.append(f"kicker {kicker!r} echoed the hero lockup; ribbon dropped")
        kicker = ""
    width, height = CANVAS

    canvas = _background(CANVAS, plate, grade_name)
    measure = ImageDraw.Draw(canvas)

    inner = (SAFE_BOX[2] - SAFE_BOX[0]) - 140
    f_kick = _fit(measure, kicker, inner, 50, 34)
    f1 = _fit(measure, hero1, inner, 132, 64) if hero1 else None
    f2 = _fit(measure, hero2, inner, 132, 64) if hero2 else None
    f_sub = _fit(measure, sub, inner, 54, 32) if sub else None
    f_tag = _fit(measure, tag, inner, 38, 26) if tag else None

    # Layout: hug the lockup, centre the card inside the safe box.
    pad = 78
    heights = [pad] + ([62] if kicker else [])
    if f1:
        heights.append(int(f1.size * 1.14))
    if f2:
        heights.append(int(f2.size * 1.14))
    if f_sub:
        heights += [30, 34, int(f_sub.size * 1.5)]
    if f_tag:
        heights += [40, 56]
    heights.append(pad)
    block_h = sum(heights)
    top = (SAFE_BOX[1] + SAFE_BOX[3]) // 2 - block_h // 2
    card = (SAFE_BOX[0] + 8, top, SAFE_BOX[2] - 8, top + block_h)

    layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        card, radius=44, fill=CARD_FILL, outline=(235, 198, 92, 240), width=4)
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.4)))
    draw = ImageDraw.Draw(canvas)

    # Contrast is measured on the pixels that were actually painted behind the
    # hero, not on the intended fill: the card is translucent.
    patch = canvas.crop((card[0] + 20, card[1] + 20, card[0] + 60, card[1] + 60)).convert("RGB")
    behind = tuple(int(sum(c) / len(c)) for c in zip(*list(patch.getdata())))
    contrast = contrast_ratio(WHITE, behind)
    if contrast < MIN_CONTRAST:
        raise PosterRefused(
            f"shorts poster contrast {contrast:.2f} < floor {MIN_CONTRAST} behind the hero "
            f"(plate {plate or DEFAULT_PLATE!r}, grade {grade_name}); darken the card or the plate"
        )

    boxes = []
    y = card[1] + pad
    if kicker:
        kw = draw.textlength(kicker, font=f_kick)
        kx = (width - kw) / 2
        draw.rounded_rectangle([kx - 26, y - 10, kx + kw + 26, y + 50], radius=12,
                               fill=(12, 36, 82, 245), outline=(255, 218, 64, 220), width=2)
        draw.text((kx, y + 2), kicker, font=f_kick, fill=(255, 228, 130, 255))
        boxes.append(_text_box(draw, kicker, f_kick, (kx, y + 2)))
        y += 62

    for line, font in ((hero1, f1), (hero2, f2)):
        if not line or font is None:
            continue
        w = draw.textlength(line, font=font)
        x = (width - w) / 2
        draw.text((x + 4, y + 7), line, font=font, fill=(0, 0, 0, 210))
        draw.text((x, y), line, font=font, fill=WHITE)
        boxes.append(_text_box(draw, line, font, (x, y)))
        y += int(font.size * 1.14)

    if f_sub:
        y += 30
        draw.rounded_rectangle([(width - 440) / 2, y, (width + 440) / 2, y + 6], radius=3,
                               fill=(255, 218, 64, 245))
        y += 34
        sw = draw.textlength(sub, font=f_sub)
        sx = (width - sw) / 2
        draw.text((sx, y), sub, font=f_sub, fill=PALE_GOLD)
        boxes.append(_text_box(draw, sub, f_sub, (sx, y)))
        y += int(f_sub.size * 1.5)

    if f_tag:
        y += 40
        tw = draw.textlength(tag, font=f_tag)
        tx = (width - tw) / 2
        draw.rounded_rectangle([tx - 26, y - 10, tx + tw + 26, y + 46], radius=12,
                               fill=(16, 48, 108, 240), outline=(148, 198, 255, 190), width=2)
        draw.text((tx, y + 2), tag, font=f_tag, fill=(255, 255, 255, 245))
        boxes.append(_text_box(draw, tag, f_tag, (tx, y + 2)))

    safe_ok = all(_inside(box, SAFE_BOX) for box in boxes) and _inside(
        (card[0], card[1], card[2], card[3]), SAFE_BOX)
    if not safe_ok:
        worst = next((box for box in boxes if not _inside(box, SAFE_BOX)), card)
        raise PosterRefused(
            f"shorts poster text escapes the UI safe zone {SAFE_BOX}: {worst}; "
            "shorten the authored lockup or reduce its size"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final = canvas.convert("RGB")
    final.save(out_path, quality=93, optimize=True)
    if out_path.stat().st_size > 50 * 1024 * 1024:
        raise PosterRefused("shorts poster exceeds the API's 50MB upload limit")

    return PosterReport(
        path=out_path,
        width=width,
        height=height,
        contrast=contrast,
        hero_px=(f1.size if f1 else 0),
        kicker=kicker,
        lines=(hero1, hero2, sub, tag),
        plate=plate or DEFAULT_PLATE,
        grade=grade_name,
        safe_zone_ok=safe_ok,
        notes=notes,
    )


def _spec_dict(spec) -> dict:
    """Accept a spec dict, a loaded `ShortSpec`, a key, or a path to a spec JSON."""
    if isinstance(spec, (str, Path)):
        raw = str(spec)
        path = spec_path_for_key(raw) or spec_path_for_slug(raw) or Path(raw)
        if not path.is_file():
            raise FileNotFoundError(f"no Short spec for {raw!r}")
        return json.loads(path.read_text(encoding="utf-8"))
    if isinstance(spec, dict):
        return spec
    data = getattr(spec, "__dict__", None)
    if isinstance(data, dict) and "poster" in data:
        return data
    raise TypeError(f"cannot read a poster out of {type(spec).__name__}")


def poster_for_spec(
    spec,
    out_path: Path,
    *,
    channel_id: Optional[str] = None,
    plate: Optional[str] = None,
) -> PosterReport:
    """Render the poster for one Short spec, in its channel's voice.

    `spec` may be the spec dict, the `ShortSpec` dataclass, the queue key
    (`short-psalm91v11`), or a path to the JSON — the repair script, the release
    path and the tests all want to name the same thing differently.
    """
    spec = _spec_dict(spec)
    # A spec states the channel it belongs to; trusting the caller instead is how
    # a Short on the morning channel gets the pre-sleep ribbon.
    channel_id = channel_id or str(spec.get("channel") or "").strip() or None
    h1, h2, sub, tag = poster_lines(spec)
    return render_shorts_poster(
        out_path,
        lines=(h1, h2, sub, tag),
        kicker=kicker_for(channel_id),
        channel_id=channel_id,
        plate=plate,
    )


def poster_for_slug(
    slug: str,
    out_path: Path,
    *,
    channel_id: Optional[str] = None,
    plate: Optional[str] = None,
) -> Optional[PosterReport]:
    """Repair path: rebuild a live Short's poster from its spec, if it still exists."""
    path = spec_path_for_slug(slug)
    if path is None:
        return None
    return poster_for_spec(path, out_path, channel_id=channel_id, plate=plate)


def lines_from_title(title: str, tag: str) -> tuple[str, str, str, str]:
    """A lockup for a Short whose spec is gone (hand-written editions).

    Keeps the same four-slot shape as an authored spec: two hero lines, a
    scripture or promise line, and the channel's pill. Numbers and currency stay
    ("$70 Billion" is the hook of the Enron Short); only the "Say this" prefix,
    the hashtag and the trailing brand claim are removed.
    """
    import re as _re

    text = _re.sub(r"#shorts\s*$", "", (title or "").strip(), flags=_re.I).strip()
    head, _, tail = text.partition("|")
    head = _re.sub(r"^say\s+this\s+", "", head.strip(), flags=_re.I)
    scripture = _re.search(r"\b((?:1|2)\s?[A-Z][a-z]+|[A-Z][a-z]+)\s*(\d+)(?::\d+(?:-\d+)?)?", head)
    sub = (tail.strip().upper() if tail.strip()
           else (f"{scripture.group(1).upper()} {scripture.group(2)}" if scripture else ""))
    tokens = _re.findall(r"[A-Za-z0-9$'.]+", head)
    tokens = [t for t in tokens if t.lower() not in {"say", "this"}]
    mid = max(1, (len(tokens) + 1) // 2)
    hero1 = " ".join(tokens[:mid]).upper()
    hero2 = " ".join(tokens[mid:]).upper()
    return hero1, hero2, sub, tag
