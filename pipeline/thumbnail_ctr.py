"""CTR pack — three thumbnail concepts built to win a *dark-mode* feed.

What this adds over `thumbnail_studio`
-------------------------------------
`thumbnail_studio` fixed legibility: contrast >= 7:1, a hero that survives 168 px,
safe zones, no duration-badge collisions. Measuring the frames it produced showed
three defects that legibility rules do not catch:

1. **The frame dissolves into the app.** YouTube's dark-mode page is #0F0F0F.
   The studio vignette crushes the corners to ~(2, 5, 14) — *darker* than the
   page behind it — so the thumbnail has no visible edge and reads as a hole in
   the feed rather than an object in it. A thumbnail has to be a lit object
   sitting on a near-black surface. Every frame here is lifted to sit clearly
   above #0F0F0F at the border (`EDGE_LUMA_MIN`).

2. **The focal mass was too small.** In the 500-thumbnail breakout study a tight
   chin-to-brow crop (>=40% of frame height) peaks at 7.6% CTR against 4.3% for
   a full-body subject. The moon is this channel's only "face", so it is scaled
   to 37-44% of frame height instead of 29%, with a halo that bleeds off-frame.

3. **The copy competed with the title.** The published title already reads
   "Psalm 121: He Who Keeps You Will Neither Slumber Nor Sleep — Night Prayer
   for Sleep…". "THE LORD IS YOUR KEEPER" and "HE NEVER SLEEPS" both restate it,
   which wastes the strongest surface on the page. The three concepts here carry
   copy the title does *not*: an imperative, a curiosity clause, or no copy at
   all.

The three concepts are deliberately different, because Test & Compare decides by
watch-time share and only accepts three variants:

* ``hook``   — "PRAY THIS TONIGHT"  (imperative + tonight; conversion play)
* ``quiet``  — "WHILE YOU SLEEP"    (curiosity; the title's promise inverted)
* ``poster`` — no text at all       (28% of breakout thumbnails use none; maximum
                                     differentiation in a text-dense niche)

Metrics reported per frame: mean and border luminance, bright mass, ink share in
the text box, text contrast, safe-zone and badge clearance, file size.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from .thumbnail_studio import (
    CANVAS,
    MIN_CONTRAST,
    Palette,
    _font,
    _mean_colour,
    _screen,
    _stars,
    _vertical_gradient,
    badge_zone_clear,
    box_within_safe,
    contrast_ratio,
    layout_hero,
)

# YouTube's dark-mode page colour. A frame whose border sits at or below this
# value has no visible edge in the app.
UI_DARK = 15
EDGE_LUMA_MIN = 26.0

# Bright ("ink") pixels: what survives the downscale to 168x94.
INK_THRESHOLD = 150


# --------------------------------------------------------------------------- #
# Palettes — all navy/gold, differentiated by light temperature
# --------------------------------------------------------------------------- #
NIGHT_LAMP = Palette("night-lamp", (5, 11, 28), (26, 52, 96), (255, 208, 128),
                     (255, 202, 74), (255, 250, 238))
NIGHT_STILL = Palette("night-still", (4, 9, 24), (18, 40, 80), (214, 232, 255),
                      (255, 214, 92), (255, 250, 238))
NIGHT_DAWN = Palette("night-dawn", (9, 15, 38), (82, 64, 82), (255, 194, 124),
                     (255, 210, 92), (255, 250, 238))


@dataclass(frozen=True)
class CtrVariant:
    label: str
    concept: str
    hero: str | None              # None = textless poster
    palette: Palette
    moon: tuple[float, float]     # centre as a fraction of the canvas
    moon_scale: float             # radius as a fraction of min(w, h)
    horizon: float                # ridge baseline as a fraction of height
    dawn: float                   # warm horizon band strength, 0..1
    rays: bool
    seed: int
    text_box: tuple[int, int, int, int]
    house: tuple[float, float] | None = None   # (x fraction, height fraction of h)
    accent_last: bool = True


CTR_VARIANTS = (
    CtrVariant(
        label="hook", concept="imperative — PRAY THIS TONIGHT",
        hero="PRAY THIS TONIGHT", palette=NIGHT_LAMP,
        moon=(0.775, 0.41), moon_scale=0.205, horizon=0.735, dawn=0.70,
        rays=True, seed=101, text_box=(86, 84, 690, 470), house=(0.315, 0.150),
    ),
    CtrVariant(
        label="quiet", concept="curiosity — WHILE YOU SLEEP",
        hero="WHILE YOU SLEEP", palette=NIGHT_STILL,
        moon=(0.800, 0.36), moon_scale=0.185, horizon=0.780, dawn=0.20,
        rays=False, seed=202, text_box=(86, 84, 706, 470), house=(0.300, 0.152),
    ),
    CtrVariant(
        label="poster", concept="textless — maximal differentiation",
        hero=None, palette=NIGHT_DAWN,
        moon=(0.545, 0.455), moon_scale=0.240, horizon=0.700, dawn=0.85,
        rays=True, seed=303, text_box=(0, 0, 0, 0), house=(0.205, 0.170),
    ),
)


# --------------------------------------------------------------------------- #
# Per-release variation
# --------------------------------------------------------------------------- #
def variations_for(doc_key: str, variants=CTR_VARIANTS) -> tuple["CtrVariant", ...]:
    """Re-seed the pack for one job, inside the bounds the CTR study validated.

    Two consecutive videos with the same seed and the same copy produce frames that
    are identical to the byte — which is what the channel looked like on 2 November:
    Psalm 46's thumbnail was Psalm 121's thumbnail. The composition stays in the
    measured sweet spot (moon at 66-82% width, 19-22% of frame height, ridge within
    a few percent); only the seed, the moon's placement and the ridge height move,
    deterministically from the job id, so a re-run of the same job reproduces the
    same frame.
    """
    digest = hashlib.sha1((doc_key or "default").encode("utf-8")).hexdigest()
    base = int(digest[:8], 16)
    out = []
    for index, variant in enumerate(variants):
        rng = random.Random(base + index * 17)
        moon = (min(0.820, max(0.660, variant.moon[0] + rng.uniform(-0.060, 0.060))),
                min(0.500, max(0.330, variant.moon[1] + rng.uniform(-0.055, 0.055))))
        scale = min(0.222, max(0.190, variant.moon_scale + rng.uniform(-0.012, 0.012)))
        horizon = min(0.800, max(0.680, variant.horizon + rng.uniform(-0.030, 0.030)))
        house = None
        if variant.house:
            house = (min(0.400, max(0.200, variant.house[0] + rng.uniform(-0.045, 0.045))),
                     variant.house[1])
        out.append(dataclasses.replace(
            variant, seed=variant.seed + base % 7919, moon=moon, moon_scale=scale,
            horizon=horizon, house=house))
    return tuple(out)


# --------------------------------------------------------------------------- #
# Photographic backdrops — the video's own imagery
# --------------------------------------------------------------------------- #
# On 2 November the copy changed per video but every frame was still the same
# drawing: moon, ridge, house. Re-seeding moved that drawing three percent and it
# read as the same image. A channel whose videos each show *their own* psalm should
# not have one illustrated template; the backdrop is now the footage the video is
# actually made of, graded to the same measured rules.
def pick_backdrop(paths) -> "Path | None":
    """The most visually interesting of the job's own assets.

    RMS contrast decides: a flat sky gives the type nothing to sit against, while a
    detailed mountain or storm cloud survives being darkened and still reads at
    168 px. Deterministic, so a retried run picks the same picture.
    """
    from pathlib import Path as _Path

    best = None
    for path in paths or ():
        path = _Path(path)
        if not path.is_file():
            continue
        try:
            with Image.open(path) as im:
                grey = im.convert("L")
                grey.thumbnail((320, 320))
                score = ImageStat.Stat(grey).stddev[0]
        except Exception:  # noqa: BLE001 - an unreadable asset is not a backdrop
            continue
        if best is None or score > best[0]:
            best = (score, path)
    return best[1] if best else None


def _night_grade(img: Image.Image, palette: Palette) -> Image.Image:
    """Cool the picture to the channel's night, then lift the black point.

    The lift is the whole point: a photo darkened the obvious way collapses into the
    #0F0F0F page behind it and the frame loses its edge in the dark feed.
    """
    tint = Image.new("RGB", img.size, palette.sky_top)
    img = Image.blend(img, tint, 0.42)
    return img.point(lambda v: int(40 + (v / 255.0) ** 1.08 * 215))


def _text_scrim(img: Image.Image, box, strength: float = 0.52) -> Image.Image:
    """Darken the side the type sits on, fading out across the frame."""
    w, h = img.size
    x0, y0, x1, y1 = box
    ramp_end = min(w, x1 + int(w * 0.22))
    grad = Image.new("L", (w, 1), 0)
    px = grad.load()
    for x in range(w):
        t = 1.0 if x <= x1 else max(0.0, 1.0 - (x - x1) / max(1, ramp_end - x1))
        px[x, 0] = int(255 * strength * t)
    mask = grad.resize((w, h))
    return Image.composite(Image.new("RGB", img.size, (3, 7, 18)), img, mask)


def _photo_backdrop(path, size, variant: "CtrVariant", palette: Palette) -> Image.Image:
    from PIL import ImageOps

    with Image.open(path) as src:
        img = ImageOps.fit(src.convert("RGB"), size, method=Image.LANCZOS,
                           centering=(variant.moon[0], variant.moon[1]))
    img = _night_grade(img, palette)
    if variant.hero and variant.text_box[2] > variant.text_box[0]:
        img = _text_scrim(img, variant.text_box)
    elif variant.hero:
        img = _text_scrim(img, (0, 0, size[0] // 2, size[1]))
    return img


# --------------------------------------------------------------------------- #
# Art
# --------------------------------------------------------------------------- #
def _radial_glow(size, centre, radius: float, colour, strength: float) -> Image.Image:
    """One ellipse, blurred hard — cheap, smooth, and impossible to over-brighten.

    The fill value *is* the light (screen blending), so keep it small.
    """
    layer = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = centre
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              fill=tuple(int(c * strength) for c in colour))
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.55))


def _moon(img: Image.Image, centre, radius: float, palette: Palette) -> Image.Image:
    """Halo, a genuine sphere (shaded limb, not a flat sticker), and a shaft."""
    cx, cy = centre
    r = int(radius)
    img = _screen(img, _radial_glow(img.size, centre, r * 4.3, palette.glow, 0.20))
    img = _screen(img, _radial_glow(img.size, centre, r * 1.45, palette.glow, 0.17))

    pad = 4
    size = (r * 2 + pad * 2, r * 2 + pad * 2)
    # fill the tile with the limb colour, never black: the paste mask is feathered
    # and any black outside the circle bleeds back as a dark ring around the moon
    disc = Image.new("RGB", size, (226, 216, 192))
    d = ImageDraw.Draw(disc)
    steps = 40
    for i in range(steps, 0, -1):
        rr = r * i / steps
        t = i / steps
        col = (int(255 - 18 * t ** 2), int(250 - 22 * t ** 2), int(236 - 34 * t ** 2))
        d.ellipse([pad + r - rr, pad + r - rr, pad + r + rr, pad + r + rr], fill=col)

    # faint maria
    rng = random.Random(5)
    maria = Image.new("L", size, 0)
    md = ImageDraw.Draw(maria)
    for _ in range(9):
        mx = pad + r + rng.uniform(-0.5, 0.5) * r
        my = pad + r + rng.uniform(-0.5, 0.5) * r
        mr = rng.uniform(0.10, 0.24) * r
        md.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=rng.randint(8, 18))
    maria = maria.filter(ImageFilter.GaussianBlur(r * 0.16))
    disc = Image.composite(Image.new("RGB", size, (216, 208, 194)), disc, maria)

    # sphere shading: light from the upper left, terminator to the lower right
    small = Image.new("L", (48, 48))
    small.putdata([max(40, min(255, int(255 - 84 * ((x / 47 * 0.40) + (y / 47 * 0.60)) ** 1.25)))
                   for y in range(48) for x in range(48)])
    shade = small.resize(size, Image.Resampling.BICUBIC)
    disc = ImageChops.multiply(disc, Image.merge("RGB", (shade, shade, shade)))

    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse([pad, pad, pad + r * 2, pad + r * 2], fill=255)
    img.paste(disc, (cx - r - pad, cy - r - pad), mask.filter(ImageFilter.GaussianBlur(3.2)))

    # a thin cloud streak across the disc gives the moon depth and scale
    streak = Image.new("RGB", img.size, (0, 0, 0))
    sd0 = ImageDraw.Draw(streak)
    sd0.polygon([(cx - r * 2.6, cy + r * 0.42), (cx + r * 2.6, cy + r * 0.10),
                 (cx + r * 2.6, cy + r * 0.30), (cx - r * 2.6, cy + r * 0.66)],
                fill=tuple(int(c * 0.10) for c in palette.glow))
    img = _screen(img, streak.filter(ImageFilter.GaussianBlur(r * 0.30)))

    # light shaft: a soft cone from the moon toward the water
    shaft = Image.new("RGB", img.size, (0, 0, 0))
    sd = ImageDraw.Draw(shaft)
    spread = r * 1.5
    sd.polygon([(cx - r * 0.5, cy), (cx + r * 0.5, cy),
                (cx + spread, img.size[1]), (cx - spread, img.size[1])],
               fill=tuple(int(c * 0.055) for c in palette.glow))
    img = _screen(img, shaft.filter(ImageFilter.GaussianBlur(r * 0.6)))
    return img


def _ridge_mask(size, baseline: float, amp: float, side: str, seed: int,
                blur: float = 0.0) -> Image.Image:
    w, h = size
    rng = random.Random(seed)
    layer = Image.new("L", size, 0)
    d = ImageDraw.Draw(layer)
    phase = [rng.uniform(0, 6.28) for _ in range(3)]
    pts = [(0, h)]
    x = 0
    while x <= w:
        y = h * baseline
        y += h * amp * math.sin(x / w * 3.1 + phase[0])
        y += h * amp * 0.40 * math.sin(x / w * 8.3 + phase[1])
        y += h * amp * 0.14 * math.sin(x / w * 17.0 + phase[2])
        pts.append((x, y))
        x += 6
    pts.append((w, h))
    d.polygon(pts, fill=255)
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return layer, pts[1:-1]


def _house(img: Image.Image, crest: list[tuple[float, float]], x_frac: float,
           height_frac: float, palette: Palette) -> Image.Image:
    """A lone lit window on the ridge.

    This is the emotional anchor. A human face lifts CTR ~33%, but this channel
    never shows faces — a single warm window implies someone asleep inside, puts
    a second small bright mass in the dead lower third, and gives the picture a
    subject at 168 px where a bare hill is just a black band.
    """
    w, h = img.size
    x = w * x_frac
    base = min(crest, key=lambda pt: abs(pt[0] - x))[1]
    height = h * height_frac
    width = height * 1.45
    body_top = base - height * 0.62
    roof_top = base - height
    dark = (7, 14, 30)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.polygon([(x - width / 2, body_top), (x + width / 2, body_top),
               (x + width / 2, base + 6), (x - width / 2, base + 6)], fill=dark + (255,))
    d.polygon([(x - width * 0.60, body_top + 2), (x + width * 0.60, body_top + 2),
               (x, roof_top)], fill=dark + (255,))
    # chimney
    d.rectangle([x + width * 0.20, roof_top + height * 0.10,
                 x + width * 0.30, roof_top + height * 0.30], fill=dark + (255,))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

    # roof edge catches the moonlight: the side facing the moon only
    edge = Image.new("RGB", img.size, (0, 0, 0))
    ed = ImageDraw.Draw(edge)
    face_right = x < w * 0.5
    if face_right:
        ed.line([(x, roof_top), (x + width * 0.60, body_top + 2)],
                fill=tuple(int(c * 0.30) for c in palette.glow), width=3)
        ed.line([(x + width / 2, body_top), (x + width / 2, base)],
                fill=tuple(int(c * 0.16) for c in palette.glow), width=2)
    img = _screen(img, edge.filter(ImageFilter.GaussianBlur(2.2)))

    # windows: crisp warm squares plus a contained bloom and a ground spill
    win = Image.new("RGB", img.size, (0, 0, 0))
    wd = ImageDraw.Draw(win)
    spots = []
    for wx_a, ww_a in ((0.34, 0.17), (0.63, 0.13)):
        wx = x - width / 2 + width * wx_a
        wy = body_top + height * 0.16
        ww = width * ww_a
        wh = height * 0.15
        wd.rectangle([wx, wy, wx + ww, wy + wh], fill=(255, 205, 120))
        spots.append((wx + ww / 2, wy + wh / 2, ww))
    img = _screen(img, win)
    bloom = Image.new("RGB", img.size, (0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    for sx, sy, ww in spots:
        rad = ww * 2.6
        bd.ellipse([sx - rad, sy - rad, sx + rad, sy + rad],
                   fill=tuple(int(c * 0.30) for c in palette.glow))
    img = _screen(img, bloom.filter(ImageFilter.GaussianBlur(width * 0.16)))
    spill = _radial_glow(img.size, (x, base + height * 0.18), width * 1.15,
                         palette.glow, 0.13)
    return _screen(img, spill)


def _terrain(img: Image.Image, variant: "CtrVariant") -> Image.Image:
    """Dawn wash, two ridges, crest catch-light, and the house."""
    w, h = img.size
    pal = variant.palette
    if variant.dawn > 0:
        band = Image.new("RGB", img.size, (0, 0, 0))
        bd = ImageDraw.Draw(band)
        top, bottom = h * (variant.horizon - 0.36), h * (variant.horizon + 0.05)
        steps = 50
        for i in range(steps):
            t = i / (steps - 1)
            y = top + (bottom - top) * t
            bd.rectangle([0, y, w, y + 4],
                         fill=tuple(int(c * variant.dawn * 0.30 * t ** 1.8) for c in pal.glow))
        img = _screen(img, band.filter(ImageFilter.GaussianBlur(30)))

    crest = []
    for baseline, amp, colour, seed in (
        (variant.horizon, 0.038, (24, 42, 80), variant.seed + 2),
        (variant.horizon + 0.075, 0.026, (8, 16, 36), variant.seed + 3),
    ):
        mask, pts = _ridge_mask(img.size, baseline, amp, "low", seed)
        img = Image.composite(Image.new("RGB", img.size, colour), img, mask)
        line = Image.new("RGB", img.size, (0, 0, 0))
        ld = ImageDraw.Draw(line)
        ld.line(pts, fill=tuple(int(c * 0.20) for c in pal.glow), width=3)
        img = _screen(img, line.filter(ImageFilter.GaussianBlur(2.6)))
        crest = pts   # keep the nearest ridge for house placement

    if variant.house:
        img = _house(img, crest, variant.house[0], variant.house[1], pal)
    return img


def _reflection(img: Image.Image, variant: "CtrVariant") -> Image.Image:
    """A broken vertical column of moonlight on the water, masked to the water."""
    w, h = img.size
    pal = variant.palette
    cx = int(w * variant.moon[0])
    radius = variant.moon_scale * min(w, h)
    top = h * (variant.horizon + 0.055)
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    rng = random.Random(variant.seed + 9)
    for _ in range(70):
        t = rng.random() ** 1.4
        y = top + t * (h - top) * 0.85
        half = max(3.0, radius * rng.uniform(0.15, 0.62) * (1.0 - 0.45 * t))
        dx = rng.uniform(-radius * 0.45, radius * 0.45)
        a = max(0.0, rng.uniform(0.10, 0.26) * (1.0 - t))
        d.line([(cx + dx - half, y), (cx + dx + half, y)],
               fill=tuple(int(c * a) for c in pal.glow), width=2)
    layer = layer.filter(ImageFilter.GaussianBlur(3.0))
    # fade the column out with distance from the waterline
    fade = Image.new("L", img.size, 0)
    fd = ImageDraw.Draw(fade)
    fd.rectangle([0, int(top), w, h], fill=255)
    fade = fade.filter(ImageFilter.GaussianBlur(40))
    layer = Image.composite(layer, Image.new("RGB", img.size, (0, 0, 0)), fade)
    return _screen(img, layer)


def paint_ctr_scene(variant: "CtrVariant", size=CANVAS, avoid=None,
                    backdrop=None) -> Image.Image:
    w, h = size
    pal = variant.palette
    if backdrop:
        return _photo_backdrop(backdrop, size, variant, pal)
    img = _vertical_gradient(size, pal.sky_top, pal.sky_bottom)
    centre = (int(w * variant.moon[0]), int(h * variant.moon[1]))
    radius = variant.moon_scale * min(w, h)

    # atmospheric haze, low strength: depth without lifting the sky out of night
    haze = Image.new("RGB", size, (0, 0, 0))
    hd = ImageDraw.Draw(haze)
    rng = random.Random(variant.seed + 4)
    for _ in range(6):
        cx = rng.uniform(0, w)
        cy = rng.uniform(0, h * 0.7)
        rx = rng.uniform(w * 0.20, w * 0.45)
        ry = rng.uniform(h * 0.10, h * 0.28)
        tint = pal.glow if rng.random() < 0.55 else (86, 126, 196)
        hd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                   fill=tuple(int(c * rng.uniform(0.05, 0.10)) for c in tint))
    img = _screen(img, haze.filter(ImageFilter.GaussianBlur(100)))

    img = _stars(img, 1100, variant.seed, avoid=avoid)
    img = _terrain(img, variant)
    img = _moon(img, centre, radius, pal)
    img = _reflection(img, variant)

    # vignette: darken the corners, but never below YouTube's #0F0F0F page, or
    # the thumbnail loses its edge in the dark-mode feed.
    vig = Image.new("L", size, 255)
    ImageDraw.Draw(vig).ellipse(
        [-int(w * 0.18), -int(h * 0.20), int(w * 0.98), int(h * 1.10)], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(170))
    dark = Image.new("RGB", size, (23, 30, 52))
    img = Image.composite(img, dark, vig.point(lambda v: 255 - v))
    return img


# --------------------------------------------------------------------------- #
# Type
# --------------------------------------------------------------------------- #
def _tracked(draw, xy, text, font, fill, tracking: float, stroke_width: int = 0,
             stroke_fill=None):
    """Draw with negative tracking — large display type needs to be tightened."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill,
                  stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def _tracked_width(draw, text, font, tracking: float) -> float:
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def _balanced_wrap(draw, words, font, tracking: float, max_w: float,
                   max_lines: int = 3) -> list[str] | None:
    """Break a short hero into lines that are *even*, not merely greedy.

    Greedy wrapping left "BE STILL / AND / KNOW" — a one-word line in the middle of
    a four-word hero, which reads as a stutter and wastes a quarter of the text box.
    For at most five words an exhaustive search is free, so pick the break that
    minimises the squared slack between lines: the block ends up rectangular, which
    is also what lets the type grow.
    """
    n = len(words)
    if n == 0:
        return None
    if n > 7:  # nothing here should ever be this long; greedy is fine
        return None
    from itertools import combinations

    best = None
    for count in range(1, min(max_lines, n) + 1):
        for breaks in combinations(range(1, n), count - 1):
            edges = (0, *breaks, n)
            lines = [" ".join(words[a:b]) for a, b in zip(edges, edges[1:])]
            widths = [_tracked_width(draw, line, font, tracking) for line in lines]
            if any(w > max_w for w in widths):
                continue
            widest = max(widths)
            slack = sum((widest - w) ** 2 for w in widths)
            score = (len(lines), slack)
            if best is None or score < best[0]:
                best = (score, lines)
    return best[1] if best else None


def _layout(draw, hero: str, box, tracking_ratio: float = -0.022):
    """Largest size that fits — preferring a block with no one-word line.

    Largest-first alone gives "BE STILL / AND / KNOW": the type is as big as it can
    be, but a lone conjunction in the middle reads as a stutter at 168 px. So the
    search keeps going a little smaller and takes the biggest size at which every
    line carries at least two words, provided that costs no more than ~15% of the
    type size. A hero that legitimately has one word per line ("PRAY THIS TONIGHT"
    at full width) still falls back to the largest fit.
    """
    x0, y0, x1, y1 = box
    max_w, max_h = x1 - x0, y1 - y0
    words = hero.split()
    best_fit = None
    clean = None
    for size in range(300, 95, -5):
        font = _font(size)
        tracking = tracking_ratio * size
        lines = _balanced_wrap(draw, words, font, tracking, max_w, max_lines=3)
        if not lines or len(lines) > 3:
            continue
        leading = int(size * 0.94)
        if leading * len(lines) > max_h:
            continue
        if max(_tracked_width(draw, line, font, tracking) for line in lines) > max_w:
            continue
        if best_fit is None:
            best_fit = (font, lines, tracking, leading, size)
        if clean is None and min(len(line.split()) for line in lines) >= 2:
            clean = (font, lines, tracking, leading, size)
    if clean and best_fit and clean[4] >= best_fit[4] * 0.75:
        return clean
    if best_fit:
        return best_fit
    font = _font(96)
    tracking = tracking_ratio * 96
    lines = hero.split()[:3]
    return font, lines, tracking, 90, 96


def draw_ctr_hero(img: Image.Image, hero: str, variant: CtrVariant):
    draw = ImageDraw.Draw(img)
    font, lines, tracking, leading, size = _layout(draw, hero, variant.text_box)
    x0, y0, x1, y1 = variant.text_box
    block_h = leading * len(lines)
    y = y0 + (y1 - y0 - block_h) // 2

    # shadow pass first, as one layer, so overlapping glyphs do not double-darken
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sy = y
    for line in lines:
        lw = _tracked_width(sd, line, font, tracking)
        lx = x0 if variant.text_box[2] - x0 > 0 else x0
        _tracked(sd, (lx, sy + int(size * 0.05)), line, font, (0, 0, 0, 215), tracking)
        sy += leading
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.055))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")

    draw = ImageDraw.Draw(img)
    contrast = 99.0
    sy = y
    stroke = max(2, int(size * 0.018))
    for i, line in enumerate(lines):
        lw = _tracked_width(draw, line, font, tracking)
        colour = variant.palette.accent if (variant.accent_last and i == len(lines) - 1) else variant.palette.text
        box = (int(x0), int(sy), int(x0 + lw), int(sy + leading))
        behind = _mean_colour(img, box)
        contrast = min(contrast, contrast_ratio(colour, behind))
        _tracked(draw, (x0, sy), line, font, colour, tracking,
                 stroke_width=stroke, stroke_fill=(4, 9, 22))
        sy += leading
    return img, size, len(lines), contrast


# --------------------------------------------------------------------------- #
# Finishing + rendering
# --------------------------------------------------------------------------- #
def _finish(img: Image.Image, lift: float = 1.0) -> Image.Image:
    """Lift the black point off the app background, then grade like film.

    The histogram should end up bimodal — a deep, quiet field plus one bright
    focal mass — not the uniform mid-grey that makes thumbnails look like stock
    wallpaper at 168 px.
    """
    # 1. shadow lift: keeps the border above YouTube's #0F0F0F page colour
    level = tuple(max(1, int(c * 0.05 * lift)) for c in (34, 40, 58))
    img = _screen(img, Image.new("RGB", img.size, level))
    # 2. filmic S: crush the toe, roll off the shoulder
    def s_curve(v: int) -> int:
        t = v / 255.0
        if t < 0.55:
            out = 0.55 * (t / 0.55) ** 1.55
        else:
            out = 1.0 - 0.45 * ((1.0 - t) / 0.45) ** 1.25
        return max(0, min(255, int(round(out * 255))))
    img = img.point(s_curve)
    # 3. cool shadows, warm highlights
    warm = Image.new("RGB", img.size, (255, 234, 202))
    mask = img.convert("L").point(lambda v: max(0, min(255, int((v - 130) * 1.05))))
    img = Image.composite(Image.blend(img, warm, 0.18), img, mask)
    # 4. fine grain so it reads photographed rather than generated
    w, h = img.size
    rng = random.Random(23)
    grain = Image.new("L", (w // 2, h // 2))
    grain.putdata([128 + rng.randint(-9, 9) for _ in range((w // 2) * (h // 2))])
    grain = grain.resize(img.size, Image.Resampling.BILINEAR)
    img = Image.blend(img, Image.merge("RGB", (grain, grain, grain)), 0.04)
    # 5. print floor. The S-curve above crushes the toe back under #0F0F0F; a hard
    # floor keeps every pixel — corners included — measurably lighter than the
    # page, so the frame always has an edge in the dark-mode feed.
    floor = UI_DARK + 7
    return img.point(lambda v: v if v >= floor + 6 else int(floor + (v * 6 / (floor + 6))))


@dataclass
class CtrReport:
    path: Path
    variant: str
    concept: str
    hero: str
    hero_px: int
    lines: int
    words: int
    contrast: float
    mean_luma: float
    edge_luma: float
    bright_share: float
    border_dark: float
    file_kb: int
    safe_zone_ok: bool
    badge_zone_ok: bool
    edge_visible: bool
    backdrop: str = "procedural"     # "procedural" or "photo:<file>"
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "file": self.path.name, "variant": self.variant, "concept": self.concept,
            "hero": self.hero, "hero_px": self.hero_px, "lines": self.lines,
            "words": self.words, "contrast": round(self.contrast, 2),
            "mean_luma": round(self.mean_luma, 1), "edge_luma": round(self.edge_luma, 1),
            "bright_share": round(self.bright_share, 3),
            "border_dark": round(self.border_dark, 4), "file_kb": self.file_kb,
            "safe_zone_ok": self.safe_zone_ok, "badge_zone_ok": self.badge_zone_ok,
            "edge_visible": self.edge_visible, "notes": self.notes,
        }


def edge_luma(img: Image.Image, band: int = 14) -> float:
    """Mean luminance of the outer border — the part that must not match the UI."""
    w, h = img.size
    g = img.convert("L")
    strips = [g.crop((0, 0, w, band)), g.crop((0, h - band, w, h)),
              g.crop((0, 0, band, h)), g.crop((w - band, 0, w, h))]
    return sum(ImageStat.Stat(s).mean[0] for s in strips) / len(strips)


def border_dark_share(img: Image.Image, band: int = 14, threshold: int = UI_DARK) -> float:
    """Share of border pixels at or below the app's own grey — should be near zero."""
    w, h = img.size
    g = img.convert("L")
    boxes = ((0, 0, w, band), (0, h - band, w, h), (0, 0, band, h), (w - band, 0, w, h))
    total = dark = 0
    for box in boxes:
        for v in g.crop(box).getdata():
            total += 1
            dark += v <= threshold
    return dark / max(1, total)


def bright_share(img: Image.Image, threshold: int = INK_THRESHOLD) -> float:
    g = img.convert("L")
    hist = g.histogram()
    return sum(hist[threshold:]) / sum(hist)


def render_ctr(variant: CtrVariant, out_path: Path, size=CANVAS,
               backdrop=None) -> CtrReport:
    avoid = None
    if variant.hero:
        x0, y0, x1, y1 = variant.text_box
        avoid = (x0 - 40, y0 - 40, x1 + 40, y1 + 40)
    img = paint_ctr_scene(variant, size, avoid=avoid, backdrop=backdrop)
    notes: list[str] = []
    hero_px, lines, contrast = 0, 0, 99.0
    if variant.hero:
        img, hero_px, lines, contrast = draw_ctr_hero(img, variant.hero, variant)
    img = _finish(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=62, threshold=2))
    if variant.hero and contrast < MIN_CONTRAST:
        notes.append(f"contrast {contrast:.1f} below {MIN_CONTRAST} — needs a scrim")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True, subsampling=0)
    el = edge_luma(img)
    return CtrReport(
        path=out_path, variant=variant.label, concept=variant.concept,
        hero=variant.hero or "", hero_px=hero_px, lines=lines,
        words=len(variant.hero.split()) if variant.hero else 0,
        contrast=contrast if variant.hero else 0.0,
        mean_luma=ImageStat.Stat(img.convert("L")).mean[0], edge_luma=el,
        bright_share=bright_share(img), border_dark=border_dark_share(img),
        file_kb=out_path.stat().st_size // 1024,
        safe_zone_ok=box_within_safe(variant.text_box) if variant.hero else True,
        badge_zone_ok=badge_zone_clear(img), edge_visible=el >= EDGE_LUMA_MIN,
        backdrop=f"photo:{Path(backdrop).name}" if backdrop else "procedural",
        notes=notes,
    )


def generate_ctr_pack(out_dir: Path, variants=CTR_VARIANTS,
                      hero_override: str | None = None,
                      doc_key: str | None = None,
                      backdrop=None) -> list[CtrReport]:
    """Render the pack for one job.

    `hero_override` replaces the copy on the text variants with the script's own
    ``thumb_text`` — the per-psalm line the brain authored, which the pipeline used
    to discard in favour of the fixed "PRAY THIS TONIGHT" on every video. The
    textless poster keeps no copy; that is the point of it. `doc_key` re-seeds the
    art so two releases never render the same frame.
    """
    if doc_key:
        variants = variations_for(doc_key, variants)

    out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for variant in variants:
        render = variant
        if hero_override and variant.hero:
            render = dataclasses.replace(variant, hero=hero_override.upper().strip())
        reports.append(render_ctr(render, out_dir / f"thumbnail_{variant.label}.jpg",
                                  backdrop=backdrop))
    return reports


def main(argv=None) -> int:  # pragma: no cover - CLI convenience
    import argparse
    parser = argparse.ArgumentParser(description="Render the CTR thumbnail pack.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mobile", action="store_true")
    args = parser.parse_args(argv)
    from .thumbnail_studio import mobile_preview
    for report in generate_ctr_pack(args.out):
        print(json.dumps(report.as_dict()))
        if args.mobile:
            mobile_preview(report.path, report.path.with_name(report.path.stem + "_mobile.png"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
