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
CURATED_SANCTUARY_PLATES: dict[str, str] = {
    "0008": "long-prayer-scene-05.jpg",   # Psalm 91 — golden wings over mountain valley
    "0009": "long-prayer-scene-01.jpg",   # Psalm 23 — still alpine waters at dawn
    "0010": "long-prayer-scene-04.jpg",   # Psalm 121 — starry night & lit cabin over lake
    "0011": "long-prayer-thumb-hero.jpg", # Psalm 27 — blazing light breaking storm clouds
    "0013": "long-prayer-scene-02.jpg",   # Psalm 46 — mountain stone fortress in sunbeams
    "0018": "long-prayer-scene-06.jpg",   # Psalm 3  — triumphant golden dawn over peaks
}

_ALL_CURATED_PLATES: tuple[str, ...] = (
    "long-prayer-thumb-hero.jpg",
    "long-prayer-scene-01.jpg",
    "long-prayer-scene-02.jpg",
    "long-prayer-scene-03.jpg",
    "long-prayer-scene-04.jpg",
    "long-prayer-scene-05.jpg",
    "long-prayer-scene-06.jpg",
)

_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def curated_backdrop_for(doc_key: str | None = None) -> "Path | None":
    """Deterministic cleared 16:9 sanctuary plate when stock clips yield no bright still."""
    plate_dir = Path(__file__).resolve().parent.parent / "image-search"
    clean_key = (doc_key or "").strip()
    if clean_key in CURATED_SANCTUARY_PLATES:
        candidate = plate_dir / CURATED_SANCTUARY_PLATES[clean_key]
        if candidate.is_file():
            return candidate
    available = [plate_dir / name for name in _ALL_CURATED_PLATES if (plate_dir / name).is_file()]
    if not available:
        return None
    digest = hashlib.sha1((clean_key or "default").encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(available)
    return available[idx]


def _ffmpeg_exe() -> str | None:
    import shutil

    try:
        from .assemble import ffmpeg_bin

        exe = ffmpeg_bin()
        if exe:
            return exe
    except Exception:
        pass
    try:
        import imageio_ffmpeg  # type: ignore

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


def _extract_video_frames(video_path: Path) -> list[Path]:
    """Sample up to 4 candidate stills from a video asset so .mp4 B-roll can be scored."""
    import subprocess

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg or not video_path.is_file():
        return []
    cache_dir = video_path.parent / "_backdrop_frames"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return []

    stamps = (0.4, 1.5, 4.0, 7.5)
    frames: list[Path] = []
    for idx, sec in enumerate(stamps):
        dest = cache_dir / f"{video_path.stem}_f{idx}.jpg"
        if not dest.is_file() or dest.stat().st_size < 1024:
            cmd = [
                ffmpeg, "-y", "-loglevel", "error",
                "-ss", f"{sec:.2f}", "-i", str(video_path),
                "-frames:v", "1", "-vf", "scale=1280:-2",
                "-q:v", "3", str(dest),
            ]
            try:
                subprocess.run(cmd, check=False, capture_output=True, timeout=15)
            except Exception:
                continue
        if dest.is_file() and dest.stat().st_size >= 1024:
            frames.append(dest)
    return frames


def _percentile_from_hist(hist: list[int], pct: float) -> int:
    total = sum(hist)
    if total <= 0:
        return 0
    target = total * pct
    acc = 0
    for idx, count in enumerate(hist):
        acc += count
        if acc >= target:
            return idx
    return 255


def _score_backdrop_image(path: Path) -> tuple[float, float] | None:
    """Return (composite_score, p95_luma) for a candidate image, or None if unreadable."""
    try:
        with Image.open(path) as im:
            grey = im.convert("L")
            grey.thumbnail((320, 180))
            w, h = grey.size
            if w < 16 or h < 16:
                return None
            stddev = ImageStat.Stat(grey).stddev[0]
            full_hist = grey.histogram()
            p95 = _percentile_from_hist(full_hist, 0.95)
            right = grey.crop((int(w * 0.44), int(h * 0.08), int(w * 0.95), int(h * 0.82)))
            r_hist = right.histogram()
            r_mean = ImageStat.Stat(right).mean[0]
            r_p90 = _percentile_from_hist(r_hist, 0.90)
            r_p15 = _percentile_from_hist(r_hist, 0.15)
    except Exception:  # noqa: BLE001 - an unreadable asset is not a backdrop
        return None

    if stddev < 4.0:
        return (stddev * 0.1, float(p95))
    focal_span = max(0, r_p90 - r_p15)
    dark_penalty = 0.35 if (p95 < 55 and r_p90 < 48) else 1.0
    score = (stddev + 0.32 * focal_span + 0.16 * min(r_mean, 155.0)) * dark_penalty
    return (score, float(p95))


def pick_backdrop(paths) -> "Path | None":
    """The most visually compelling of the job's own assets (photos AND .mp4 clips).

    Scores both contrast and right-side focal illumination so a pitch-black night
    sky cannot beat a mountain dawn clip, and extracts candidate frames from .mp4
    video B-roll automatically. Deterministic, so a retried run picks the same frame.
    """
    from pathlib import Path as _Path

    candidates: list[Path] = []
    for raw in paths or ():
        path = _Path(raw)
        if not path.is_file():
            continue
        if path.suffix.lower() in _VIDEO_EXTS:
            candidates.extend(_extract_video_frames(path))
        else:
            candidates.append(path)

    best: tuple[float, float, Path] | None = None
    for cand in candidates:
        scored = _score_backdrop_image(cand)
        if scored is None:
            continue
        score, p95 = scored
        if best is None or score > best[0]:
            best = (score, p95, cand)
    if best is None:
        return None
    # Reject pitch-black mud frames from live video extraction so a curated plate can step in,
    # while still allowing synthetic greyscale/colour stills passed in unit tests.
    if best[1] < 28.0 and "_backdrop_frames" in str(best[2]):
        return None
    return best[2]


def _night_grade(img: Image.Image, palette: Palette) -> Image.Image:
    """Adaptive exposure + split-tone nocturnal grade that preserves bright focal light.

    Previously a flat 42% blend with (5, 11, 28) crushed dark/twilight photographs
    into muddy charcoal before `_finish()`'s S-curve crushed them a second time.
    Now dark frames are lifted first, deep shadows cool to sapphire, and highlights
    stay radiant warm gold/cream so the right-hand subject pops on mobile feeds.
    """
    w, h = img.size
    right = img.convert("L").crop((int(w * 0.45), int(h * 0.08), int(w * 0.95), int(h * 0.80)))
    r_hist = right.histogram()
    r_p50 = _percentile_from_hist(r_hist, 0.50)
    r_p94 = _percentile_from_hist(r_hist, 0.94)

    # 1. Auto-expose under-lit night/dusk frames so the focal subject reads at 168 px.
    gamma = 0.88
    if r_p50 < 45:
        gamma = 0.54
    elif r_p50 < 75:
        gamma = 0.66
    elif r_p50 < 105:
        gamma = 0.78
    gain = 1.0
    if 12 < r_p94 < 205:
        gain = min(1.55, 218.0 / max(40.0, float(r_p94)))

    lut = [
        min(255, max(0, int(round(38 + (((i / 255.0) ** gamma) * 217.0 * gain)))))
        for i in range(256)
    ]
    lifted = img.point(lut * 3)

    # 2. Cool shadows toward deep sapphire while keeping highlights warm and luminous.
    lum = lifted.convert("L")
    shadow_tint = Image.new("RGB", img.size, (14, 28, 62))
    shadow_mask = lum.point(lambda v: max(0, min(135, int((155 - v) * 0.85))))
    graded = Image.composite(shadow_tint, lifted, shadow_mask)

    warm_tint = Image.new("RGB", img.size, palette.glow)
    hi_mask = lum.point(lambda v: max(0, min(95, int((v - 135) * 0.75))))
    return Image.composite(warm_tint, graded, hi_mask)


def _text_scrim(img: Image.Image, box, strength: float = 0.72) -> Image.Image:
    """Silky cosine-feathered left scrim + soft local cushion with zero hard seam."""
    w, h = img.size
    x0, y0, x1, y1 = box
    fade_start = max(0, int(w * 0.14))
    fade_end = min(w, x1 + int(w * 0.24))
    grad = Image.new("L", (w, 1), 0)
    px = grad.load()
    for x in range(w):
        if x <= fade_start:
            t = 1.0
        elif x >= fade_end:
            t = 0.0
        else:
            u = (x - fade_start) / max(1, fade_end - fade_start)
            # Smooth cosine ease-out: zero derivative at both endpoints, no visible seam
            t = 0.5 * (1.0 + math.cos(math.pi * u))
        px[x, 0] = int(255 * strength * t)
    mask = grad.resize((w, h), Image.Resampling.BILINEAR)

    # Reinforce softly right behind the text block so contrast clears 9:1 without darkening the sky
    local = Image.new("L", (w, h), 0)
    ImageDraw.Draw(local).rounded_rectangle(
        [max(0, x0 - 44), max(0, y0 - 28), min(w, x1 + 24), min(h, y1 + 28)],
        radius=72, fill=int(255 * strength * 0.55),
    )
    local = local.filter(ImageFilter.GaussianBlur(58))
    combined = ImageChops.lighter(mask, local)
    return Image.composite(Image.new("RGB", img.size, (4, 10, 26)), img, combined)


def _calm_badge_zone(img: Image.Image) -> Image.Image:
    """Soften high-frequency detail under YouTube's bottom-right duration badge."""
    w, h = img.size
    blurred = img.filter(ImageFilter.GaussianBlur(14))
    cushion = Image.blend(blurred, Image.new("RGB", img.size, (20, 28, 50)), 0.58)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([995, 565, w + 30, h + 30], radius=48, fill=235)
    mask = mask.filter(ImageFilter.GaussianBlur(24))
    return Image.composite(cushion, img, mask)


def _photo_backdrop(path, size, variant: "CtrVariant", palette: Palette) -> Image.Image:
    from PIL import ImageOps

    with Image.open(path) as src:
        fitted = ImageOps.fit(
            src.convert("RGB"), size, method=Image.LANCZOS,
            centering=(variant.moon[0], variant.moon[1]),
        )
    w, h = size
    if variant.hero:
        # Place the brightest natural light source on the right opposite the left text stack.
        grey = fitted.convert("L")
        left_p90 = _percentile_from_hist(
            grey.crop((int(w * 0.05), int(h * 0.08), int(w * 0.45), int(h * 0.75))).histogram(),
            0.90,
        )
        right_p90 = _percentile_from_hist(
            grey.crop((int(w * 0.55), int(h * 0.08), int(w * 0.95), int(h * 0.75))).histogram(),
            0.90,
        )
        if left_p90 > right_p90 + 28:
            fitted = ImageOps.mirror(fitted)

    img = _night_grade(fitted, palette)

    # Guarantee a warm celestial focal bloom on the right even if the source photo is dark.
    focal_crop = img.convert("L").crop((int(w * 0.52), int(h * 0.12), int(w * 0.94), int(h * 0.72)))
    focal_p95 = _percentile_from_hist(focal_crop.histogram(), 0.95)
    glow_centre = (int(w * variant.moon[0]), int(h * variant.moon[1]))
    glow_r = variant.moon_scale * min(w, h)
    bloom_strength = 0.36 if focal_p95 < 135 else 0.14
    img = _screen(img, _radial_glow(size, glow_centre, glow_r * 2.4, palette.glow, bloom_strength))
    if focal_p95 < 95:
        img = _screen(img, _radial_glow(size, glow_centre, glow_r * 0.95, (255, 240, 200), 0.34))

    if variant.hero and variant.text_box[2] > variant.text_box[0]:
        img = _text_scrim(img, variant.text_box)
    elif variant.hero:
        img = _text_scrim(img, (0, 0, size[0] // 2, size[1]))
    return _calm_badge_zone(img)


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

    # shadow + warm gold accent bloom pass, as one layer, so glyphs pop at 168 px
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sy = y
    for i, line in enumerate(lines):
        lx = x0
        is_accent = variant.accent_last and i == len(lines) - 1
        if is_accent:
            _tracked(sd, (lx, sy), line, font, (255, 198, 56, 105), tracking)
        _tracked(sd, (lx, sy + int(size * 0.055)), line, font, (0, 0, 0, 235), tracking)
        sy += leading
    shadow = shadow.filter(ImageFilter.GaussianBlur(size * 0.058))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")

    draw = ImageDraw.Draw(img)
    contrast = 99.0
    sy = y
    stroke = max(3, int(size * 0.024))
    for i, line in enumerate(lines):
        lw = _tracked_width(draw, line, font, tracking)
        colour = variant.palette.accent if (variant.accent_last and i == len(lines) - 1) else variant.palette.text
        box = (int(x0), int(sy), int(x0 + lw), int(sy + leading))
        behind = _mean_colour(img, box)
        contrast = min(contrast, contrast_ratio(colour, behind))
        _tracked(draw, (x0, sy), line, font, colour, tracking,
                 stroke_width=stroke, stroke_fill=(3, 7, 18))
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
    active = variant
    if backdrop and variant.hero and variant.text_box[2] > variant.text_box[0]:
        active = dataclasses.replace(variant, text_box=(82, 76, 728, 568))
    avoid = None
    if active.hero:
        x0, y0, x1, y1 = active.text_box
        avoid = (x0 - 40, y0 - 40, x1 + 40, y1 + 40)
    img = paint_ctr_scene(active, size, avoid=avoid, backdrop=backdrop)
    notes: list[str] = []
    hero_px, lines, contrast = 0, 0, 99.0
    if active.hero:
        base_scene = img.copy()
        img, hero_px, lines, contrast = draw_ctr_hero(img, active.hero, active)
        if contrast < MIN_CONTRAST:
            reinforced = _text_scrim(base_scene, active.text_box, strength=0.48)
            img, hero_px, lines, contrast = draw_ctr_hero(reinforced, active.hero, active)
            notes.append(f"scrim reinforced to {contrast:.1f}:1")
    img = _finish(img)
    if backdrop:
        img = _calm_badge_zone(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=62, threshold=2))
    if active.hero and contrast < MIN_CONTRAST:
        notes.append(f"contrast {contrast:.1f} below {MIN_CONTRAST} — needs a scrim")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True, subsampling=0)
    el = edge_luma(img)
    return CtrReport(
        path=out_path, variant=active.label, concept=active.concept,
        hero=active.hero or "", hero_px=hero_px, lines=lines,
        words=len(active.hero.split()) if active.hero else 0,
        contrast=contrast if active.hero else 0.0,
        mean_luma=ImageStat.Stat(img.convert("L")).mean[0], edge_luma=el,
        bright_share=bright_share(img), border_dark=border_dark_share(img),
        file_kb=out_path.stat().st_size // 1024,
        safe_zone_ok=box_within_safe(active.text_box) if active.hero else True,
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
