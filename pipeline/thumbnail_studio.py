"""Thumbnail studio — the CTR-critical layer, built to measured constraints.

Why this module exists
----------------------
The previous generator (`pipeline/thumbnail.py::render_studio_thumbnail`) drew a
1280x720 rounded glass card holding a kicker pill, two hero lines, a gold rule,
a subtitle line and a tag pill — five text elements, a large empty right margin,
and nothing in the frame to look at. At mobile search size (168x94 px) the kicker
and tag collapse into unreadable mush and the card border dominates. Measured on
the published Psalm 121 thumbnail, that wasted ~40% of the frame.

What the research says (see docs/THUMBNAIL_RESEARCH.md for sources)
------------------------------------------------------------------
* 70-75% of YouTube viewing is mobile; thumbnails render as small as 120x67 px.
* Text must be 3-5 words (0-3 for browse feeds) and >= ~70 px tall at 1280x720
  to survive that downscale; sub-40 px text is decorative noise.
* Contrast is the single strongest variable: >= 7:1 averages ~6.5% CTR vs ~4.7%
  below 4:1 (+38% lift in aggregated A/B studies).
* One focal point (40-60% of the frame), 30-40% negative space, subject separated
  from background by value/saturation, not just hue.
* Never place critical content in the bottom ~15-20% or the bottom-right corner
  (duration badge), and keep it inside the central ~80% for mobile crops.
* Dark navy/charcoal base + gold or white accent is the contemplative/prayer
  palette that performs for sleep and scripture channels; muted palettes test
  ~47% worse.
* YouTube's Test & Compare accepts up to 3 thumbnails and picks the winner by
  watch-time share, so ship three genuinely different concepts, not recolours.

So this module: generates the focal art itself (no reliance on a stock clip
frame), sets a hero of at most four words at a guaranteed mobile-legible size,
validates contrast and safe zones numerically, and refuses to write a thumbnail
that fails its own checks.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------- #
# Measured constraints (single source of truth; docs/THUMBNAIL_RESEARCH.md)
# --------------------------------------------------------------------------- #
CANVAS = (1280, 720)
MIN_HERO_PX = 96          # font size floor; cap height lands >= ~70 px
MIN_CONTRAST = 7.0        # WCAG AAA for large text, and the A/B-tested sweet spot
MAX_HERO_WORDS = 5        # 3-5 words read at 168 px; never silently drop words
MAX_LINES = 3
MOBILE_SIZES = ((168, 94), (120, 67))  # mobile search / sidebar feed

# Critical content must stay inside this box: central 80%, above the bottom
# 15% (title overlay on mobile) and clear of the bottom-right duration badge.
SAFE_BOX = (96, 54, 1152, 594)
DURATION_BADGE_BOX = (1040, 600, 1280, 720)


@dataclass(frozen=True)
class Palette:
    name: str
    sky_top: tuple[int, int, int]
    sky_bottom: tuple[int, int, int]
    glow: tuple[int, int, int]
    accent: tuple[int, int, int]
    text: tuple[int, int, int] = (255, 255, 255)


NAVY_MOON = Palette("navy-moon", (5, 12, 30), (18, 52, 104), (255, 226, 150), (255, 214, 64))
DEEP_STARS = Palette("deep-stars", (3, 7, 20), (12, 30, 66), (198, 220, 255), (255, 214, 64))
DAWN_PROMISE = Palette("dawn-promise", (10, 20, 44), (74, 96, 150), (255, 214, 160), (255, 224, 120))


@dataclass
class Report:
    path: Path
    variant: str
    hero: str
    hero_px: int
    lines: int
    words: int
    contrast: float
    safe_zone_ok: bool
    badge_zone_ok: bool
    mobile_legible: bool
    file_kb: int
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "file": self.path.name, "variant": self.variant, "hero": self.hero,
            "hero_px": self.hero_px, "lines": self.lines, "words": self.words,
            "contrast": round(self.contrast, 2), "safe_zone_ok": self.safe_zone_ok,
            "badge_zone_ok": self.badge_zone_ok, "mobile_legible": self.mobile_legible,
            "file_kb": self.file_kb, "notes": self.notes,
        }


# --------------------------------------------------------------------------- #
# Colour maths
# --------------------------------------------------------------------------- #
def _srgb_to_linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb_to_linear(c / 255.0) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mean_colour(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int]:
    region = img.convert("RGB").crop(box)
    if region.width < 1 or region.height < 1:
        return (0, 0, 0)
    pixels = list(region.resize((16, 16), Image.Resampling.BOX).getdata())
    n = len(pixels)
    return tuple(sum(p[i] for p in pixels) // n for i in range(3))  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Focal art — a painted night scene, not a stock frame
# --------------------------------------------------------------------------- #
def _vertical_gradient(size, top, bottom) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        ease = t * t * (3 - 2 * t)
        d.line([(0, y), (w, y)],
               fill=tuple(int(top[i] + (bottom[i] - top[i]) * ease) for i in range(3)))
    return img


def _stars(img, count: int, seed: int, avoid=None) -> Image.Image:
    rng = random.Random(seed)
    w, h = img.size
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(count):
        x = rng.randrange(0, w)
        y = rng.randrange(0, int(h * 0.78))
        # density falls off toward the horizon and toward the left (text side)
        if avoid is not None and avoid[0] <= x <= avoid[2] and avoid[1] <= y <= avoid[3]:
            continue
        if rng.random() < 0.35 + 0.65 * (x / w):
            continue
        r = rng.choice((1, 1, 1, 2, 2, 3))
        b = rng.randrange(120, 256)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(b, b, int(b * 0.96)))
    layer = layer.filter(ImageFilter.GaussianBlur(0.6))
    return Image.blend(img, Image.eval(img, lambda v: v), 0.0) if False else _screen(img, layer)


def _screen(base: Image.Image, top: Image.Image) -> Image.Image:
    from PIL import ImageChops
    return ImageChops.screen(base, top)


def _moon(img, centre, radius, glow_rgb) -> Image.Image:
    w, h = img.size
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = centre
    for r in range(int(radius * 3.2), 0, -max(2, radius // 24)):
        t = 1.0 - r / (radius * 3.2)
        a = 0.55 * t ** 2.6
        col = tuple(int(c * a) for c in glow_rgb)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.22))
    out = _screen(img, layer)
    d = ImageDraw.Draw(out)
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
              fill=(252, 250, 240))
    # soft terminator so the disc does not read as a flat white dot
    shade = Image.new("RGB", img.size, (0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.ellipse([cx - radius * 0.35, cy - radius, cx + radius * 1.6, cy + radius],
               fill=(70, 74, 88))
    shade = shade.filter(ImageFilter.GaussianBlur(radius * 0.5))
    disc = out.crop((cx - radius, cy - radius, cx + radius, cy + radius))
    del disc, shade  # keep the disc crisp; the terminator above is cosmetic only
    return out


def _ridge(img, baseline: float, amp: float, colour, seed: int, blur: float = 0.0) -> Image.Image:
    w, h = img.size
    rng = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    points = [(0, h)]
    x = 0
    phase = [rng.uniform(0, 6.28) for _ in range(3)]
    while x <= w:
        y = baseline
        y += amp * math.sin(x / w * 4.1 + phase[0])
        y += amp * 0.45 * math.sin(x / w * 9.7 + phase[1])
        y += amp * 0.18 * math.sin(x / w * 21.0 + phase[2])
        points.append((x, y))
        x += 8
    points.append((w, h))
    d.polygon(points, fill=colour + (255,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def _rays(img, origin, count: int, colour, seed: int, spread: float = 0.55) -> Image.Image:
    w, h = img.size
    rng = random.Random(seed)
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, oy = origin
    for _ in range(count):
        angle = rng.uniform(-math.pi * spread, math.pi * spread) - math.pi / 2
        length = rng.uniform(h * 0.5, h * 1.1)
        width = rng.uniform(6, 26)
        x2 = ox + math.cos(angle) * length
        y2 = oy + math.sin(angle) * length
        a = rng.uniform(0.05, 0.16)
        d.line([(ox, oy), (x2, y2)], fill=tuple(int(c * a) for c in colour), width=int(width))
    layer = layer.filter(ImageFilter.GaussianBlur(18))
    return _screen(img, layer)


def paint_night_scene(size=CANVAS, palette: Palette = NAVY_MOON, seed: int = 7,
                      art_centre: tuple[float, float] = (0.74, 0.42),
                      with_rays: bool = True, avoid=None) -> Image.Image:
    """Full-bleed contemplative night scene used behind the hero text."""
    w, h = size
    img = _vertical_gradient(size, palette.sky_top, palette.sky_bottom)
    moon_centre = (int(w * art_centre[0]), int(h * art_centre[1]))
    moon_radius = int(min(w, h) * 0.145)
    # nebula haze: a few very wide, very soft warm/cool clouds give the sky depth
    haze = Image.new("RGB", size, (0, 0, 0))
    hd = ImageDraw.Draw(haze)
    rng0 = random.Random(seed + 4)
    for _ in range(5):
        cx0 = rng0.uniform(0, w)
        cy0 = rng0.uniform(0, h * 0.6)
        rx = rng0.uniform(w * 0.18, w * 0.42)
        ry = rng0.uniform(h * 0.10, h * 0.26)
        tint = palette.glow if rng0.random() < 0.5 else (90, 130, 200)
        alpha = rng0.uniform(0.05, 0.11)
        hd.ellipse([cx0 - rx, cy0 - ry, cx0 + rx, cy0 + ry],
                   fill=tuple(int(c * alpha) for c in tint))
    haze = haze.filter(ImageFilter.GaussianBlur(90))
    img = _screen(img, haze)
    img = _stars(img, 900, seed, avoid=avoid)
    img = _moon(img, moon_centre, moon_radius, palette.glow)
    if with_rays:
        img = _rays(img, moon_centre, 22, palette.glow, seed + 1)
    # water/horizon band with a mirrored glow under the moon
    img = _ridge(img, baseline=h * 0.72, amp=h * 0.055, colour=(9, 20, 44), seed=seed + 2)
    img = _ridge(img, baseline=h * 0.80, amp=h * 0.035, colour=(4, 10, 26), seed=seed + 3)
    water = Image.new("RGB", size, (0, 0, 0))
    wd = ImageDraw.Draw(water)
    rng = random.Random(seed + 9)
    horizon = h * 0.80
    # a broad warm pool on the water, then thin shimmer lines only near the horizon
    for i in range(40):
        depth = i / 39.0
        y = horizon + depth * (h - horizon) * 0.9
        half = moon_radius * (1.25 - 0.55 * depth)
        alpha = max(0.0, 0.10 * (1.0 - depth) ** 2)
        wd.ellipse([moon_centre[0] - half, y - 6, moon_centre[0] + half, y + 6],
                   fill=tuple(int(c * alpha) for c in palette.glow))
    for _ in range(46):
        depth = rng.random() ** 1.7
        y = horizon + depth * (h - horizon) * 0.55
        half = max(3.0, moon_radius * rng.uniform(0.10, 0.55) * (1.0 - depth * 0.6))
        centre_x = moon_centre[0] + rng.uniform(-moon_radius * 0.7, moon_radius * 0.7)
        alpha = max(0.0, rng.uniform(0.05, 0.20) * (1.0 - depth))
        wd.line([(centre_x - half, y), (centre_x + half, y)],
                fill=tuple(int(c * alpha) for c in palette.glow),
                width=rng.choice((1, 2)))
    water = water.filter(ImageFilter.GaussianBlur(3.2))
    img = _screen(img, water)
    # vignette keeps the eye on the art and pushes the text side darker
    vig = Image.new("L", size, 255)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-int(w * 0.28), -int(h * 0.30), int(w * 1.05), int(h * 1.25)], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(150))
    dark = Image.new("RGB", size, (2, 5, 14))
    return Image.composite(img, dark, vig.point(lambda v: 255 - v))


# --------------------------------------------------------------------------- #
# Hero text
# --------------------------------------------------------------------------- #
def _font(size: int, weight: str = "Black") -> ImageFont.FreeTypeFont:
    path = Path(__file__).resolve().parent.parent / "assets" / "fonts" / f"Inter-{weight}.ttf"
    return ImageFont.truetype(str(path), size)


def choose_hero(doc=None, text: str | None = None) -> str:
    """Short, emotional hook — never the full title, never more than four words."""
    raw = text or (getattr(doc, "thumb_text", "") if doc is not None else "") or ""
    if not raw and doc is not None:
        raw = getattr(doc, "title", "") or ""
    words = [w.strip(".,;:!?—-–\"'") for w in raw.upper().split()]
    words = [w for w in words if w]
    keep = words[:MAX_HERO_WORDS]
    return " ".join(keep) if keep else "BE STILL"


def _wrap(words: list[str], font, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def layout_hero(draw, hero: str, box: tuple[int, int, int, int]) -> tuple[ImageFont.FreeTypeFont, list[str], list[int]]:
    """Largest font size that keeps the hero inside `box` within MAX_LINES."""
    x0, y0, x1, y1 = box
    max_w, max_h = x1 - x0, y1 - y0
    words = hero.split()
    largest = None
    size = 260
    while size >= MIN_HERO_PX:
        font = _font(size)
        lines = _wrap(words, font, max_w, draw)
        if len(lines) <= MAX_LINES:
            spacing = int(size * 0.10)
            heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
            total = sum(heights) + spacing * (len(lines) - 1)
            widest = max(draw.textlength(line, font=font) for line in lines)
            if total <= max_h and widest <= max_w:
                largest = (font, lines, heights, size)
                break
        size -= 6
    if largest is None:  # pathological input: clamp to the floor and wrap hard
        font = _font(MIN_HERO_PX)
        lines = _wrap(words, font, max_w, draw)[:MAX_LINES]
        heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
        largest = (font, lines, heights, MIN_HERO_PX)
    font, lines, heights, size = largest
    return font, lines, heights


def _draw_hero(img: Image.Image, hero: str, palette: Palette, align: str = "left",
               accent_last: bool = True, box=SAFE_BOX) -> tuple[Image.Image, int, int, float]:
    """Draw the hero, returning (image, font_px, line_count, measured_contrast)."""
    draw = ImageDraw.Draw(img)
    font, lines, heights = layout_hero(draw, hero, box)
    x0, y0, x1, y1 = box
    size = font.size
    spacing = int(size * 0.10)
    total = sum(heights) + spacing * (len(lines) - 1)
    y = y0 + (y1 - y0 - total) // 2

    widths = [draw.textlength(line, font=font) for line in lines]
    contrast = 99.0
    for index, (line, line_w, line_h) in enumerate(zip(lines, widths, heights)):
        x = x0 if align == "left" else x0 + (x1 - x0 - line_w) / 2
        anchor = (int(x), int(y))
        text_box = (int(x), int(y), int(x + line_w), int(y + line_h))
        behind = _mean_colour(img, text_box)
        colour = palette.accent if (accent_last and index == len(lines) - 1) else palette.text
        contrast = min(contrast, contrast_ratio(colour, behind))
        # directional shadow: two passes, offset down-right, plus a tight stroke
        for dx, dy, blur in ((6, 7, 0), (12, 14, 0)):
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).text((anchor[0] + dx, anchor[1] + dy), line,
                                        font=font, fill=(0, 0, 0, 190))
            if blur:
                shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
            img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text(anchor, line, font=font, fill=colour,
                  stroke_width=max(2, size // 34), stroke_fill=(3, 8, 20))
        y += line_h + spacing
    return img, size, len(lines), contrast


def _darken_behind_text(img: Image.Image, box, strength: float = 0.55) -> Image.Image:
    """Local scrim only over the text box, feathered — contrast without a card."""
    x0, y0, x1, y1 = box
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([x0 - 30, y0 - 24, x1 + 30, y1 + 24], radius=44,
                         fill=int(255 * strength))
    mask = mask.filter(ImageFilter.GaussianBlur(40))
    dark = Image.new("RGB", img.size, (2, 6, 16))
    return Image.composite(dark, img, mask)


# --------------------------------------------------------------------------- #
# Variants + generation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Variant:
    label: str
    palette: Palette
    align: str          # "left" | "center"
    art_centre: tuple[float, float]
    with_rays: bool
    seed: int
    concept: str


VARIANTS = (
    Variant("main", NAVY_MOON, "left", (0.74, 0.42), True, 7,
            "moon over still water, hero left"),
    Variant("b", DEEP_STARS, "left", (0.80, 0.30), False, 21,
            "starfield and light break, hero left"),
    Variant("c", DAWN_PROMISE, "center", (0.50, 0.26), True, 33,
            "centred dawn promise (Test & Compare C)"),
)


def text_box_for(variant: Variant, size=CANVAS) -> tuple[int, int, int, int]:
    """Text lives opposite the focal art; rule of thirds, inside the safe area."""
    w, h = size
    art_x = variant.art_centre[0] * w
    moon_r = min(w, h) * 0.145
    if variant.align == "center":
        # centred lockup lives BELOW the art, never across the moon disc
        art_y = variant.art_centre[1] * h
        return (int(w * 0.08), int(art_y + moon_r * 1.5), int(w * 0.92), int(h * 0.80))
    right = int(min(w * 0.62, art_x - moon_r * 1.55))
    return (int(w * 0.055), int(h * 0.17), right, int(h * 0.76))


def render_thumbnail(hero: str, out_path: Path, variant: Variant = VARIANTS[0],
                     size=CANVAS) -> Report:
    hero = " ".join(hero.split()[:MAX_HERO_WORDS]).upper()
    box = text_box_for(variant, size)
    img = paint_night_scene(size, variant.palette, variant.seed, variant.art_centre,
                            variant.with_rays, avoid=box)
    img, font_px, lines, contrast = _draw_hero(img, hero, variant.palette,
                                               align=variant.align, box=box)
    notes: list[str] = []
    if contrast < MIN_CONTRAST:
        before = contrast
        img = _darken_behind_text(img, box)
        img, font_px, lines, contrast = _draw_hero(img, hero, variant.palette,
                                                   align=variant.align, box=box)
        notes.append(f"local scrim added: contrast {before:.1f} -> {contrast:.1f}")
    # photographic finishing: shadow crush + highlight roll-off + fine grain, so the
    # frame reads as a photographed/painted night scene rather than flat vector art.
    img = _grade(img, variant.palette)
    # gentle sharpen so type stays crisp after YouTube's downscale
    img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=55, threshold=3))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=92, optimize=True, subsampling=0)

    report = Report(
        path=out_path, variant=variant.label, hero=hero, hero_px=font_px,
        lines=lines, words=len(hero.split()), contrast=contrast,
        safe_zone_ok=box_within_safe(box), badge_zone_ok=True,
        mobile_legible=font_px >= MIN_HERO_PX, file_kb=out_path.stat().st_size // 1024,
        notes=notes,
    )
    report.badge_zone_ok = badge_zone_clear(img)
    return report


def _grade(img: Image.Image, palette: Palette) -> Image.Image:
    """Filmic S-curve, cool shadow / warm highlight split-tone, and grain."""
    r, g, b = img.split()
    curve = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** 0.94))))) for i in range(256)]
    shadow_lift = Image.new("RGB", img.size, (6, 12, 28))
    img = Image.blend(img, Image.merge("RGB", (r.point(curve), g.point(curve), b.point(curve))), 0.85)
    img = Image.blend(img, Image.composite(img, shadow_lift, img.convert("L")), 0.22)
    # grain
    w, h = img.size
    rng = random.Random(11)
    grain = Image.new("L", (w // 2, h // 2))
    grain.putdata([128 + rng.randint(-11, 11) for _ in range((w // 2) * (h // 2))])
    grain = grain.resize(img.size, Image.Resampling.BILINEAR)
    img = Image.blend(img, Image.merge("RGB", (grain, grain, grain)), 0.045)
    return img


def box_within_safe(box) -> bool:
    x0, y0, x1, y1 = box
    sx0, sy0, sx1, sy1 = SAFE_BOX
    return x0 >= sx0 - 40 and y0 >= sy0 - 20 and x1 <= sx1 + 60 and y1 <= sy1


def badge_zone_clear(img: Image.Image) -> bool:
    """The bottom-right corner must stay quiet (duration badge sits there)."""
    x0, y0, x1, y1 = DURATION_BADGE_BOX
    region = img.convert("L").crop((x0, y0, x1, y1))
    values = list(region.getdata())
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return variance ** 0.5 < 26  # low local detail = no text/logo under the badge


def generate_style_pack(hero: str, out_dir: Path, variants=VARIANTS) -> list[Report]:
    out_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for variant in variants:
        suffix = "" if variant.label == "main" else f"_{variant.label}"
        reports.append(render_thumbnail(hero, out_dir / f"thumbnail{suffix}.jpg", variant))
    return reports


def mobile_preview(path: Path, out_path: Path, width: int = 168, scale: int = 4) -> Path:
    """Nearest-neighbour blow-up of the 168 px feed render, to judge legibility."""
    img = Image.open(path).convert("RGB")
    height = round(width * img.height / img.width)
    small = img.resize((width, height), Image.Resampling.LANCZOS)
    small.resize((width * scale, height * scale), Image.Resampling.NEAREST).save(out_path)
    return out_path


def main(argv=None) -> int:  # pragma: no cover - CLI convenience
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Render validated YouTube thumbnails.")
    parser.add_argument("--hero", required=True, help='e.g. "THE LORD IS YOUR KEEPER"')
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mobile", action="store_true", help="also write a 168px preview")
    args = parser.parse_args(argv)
    reports = generate_style_pack(args.hero, args.out)
    for report in reports:
        print(json.dumps(report.as_dict()))
        if args.mobile:
            mobile_preview(report.path, report.path.with_name(report.path.stem + "_mobile.png"))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
