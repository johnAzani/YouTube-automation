#!/usr/bin/env python3
"""Render a channel's YouTube brand assets: avatar, banner, watermark, thumbnail.

Why code and not a generated picture
-----------------------------------
Every asset here carries type the viewer is meant to *read* — the channel name, the
tagline, the verse. Generated imagery mangles letterforms, and a mangled wordmark is
worse than no wordmark. These are drawn with Pillow from real glyphs, so the letters
are exact, the palette is the documented palette, and re-running the command months
from now produces the same files.

The layout constants are YouTube's, not our preference:

  * avatar     800 x 800 px, shown as a circle — nothing readable may sit within
               ~12% of any edge;
  * banner     2560 x 1440 px, but every viewer sees the centre 1546 x 423 px
               (TV/desktop) or the centre 1235 x 338 px (mobile). All text lives
               inside the smaller of those, or it is cropped on a phone;
  * watermark  150 x 150 px with transparency, bottom-right of every video.

Usage
-----
    python tools/make_channel_brand_assets.py --channel prayer3
    python tools/make_channel_brand_assets.py --channel prayer3 --force

Existing files are never overwritten without --force: the live channels' current
art was approved by eye, and a redraw must be a deliberate act.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
OUT_DIR = ROOT / "docs" / "media"

#: YouTube layout constants.
AVATAR = (800, 800)
BANNER = (2560, 1440)
#: Text must live inside this box or mobile crops it.
BANNER_SAFE = (1235, 338)
WATERMARK = (150, 150)
THUMBNAIL = (1280, 720)

#: Per-channel palettes. A channel's palette is data here for the same reason its
#: brand strings live in pipeline/channel_capabilities.py: one place, no drift.
PALETTES = {
    "midday-watch": {
        "name": "The Midday Watch",
        "tagline": "Pause and pray at noon",
        "verse": "Psalm 55:17",
        "sky": (13, 51, 80),        # Zenith Blue   #0d3350
        "panel": (28, 93, 122),     # Noon Sky      #1c5d7a
        "sun": (255, 194, 71),      # High Sun      #ffc247
        "brass": (227, 154, 52),    # Warm Brass    #e39a34
        "ivory": (251, 246, 236),   # Ivory         #fbf6ec
        "haze": (217, 230, 234),    # Sand Haze     #d9e6ea
        "shadow": (10, 26, 38),     # Hard Shadow   #0a1a26
        "field": (185, 139, 78),    # Sunlit Field  #b98b4e
        "field_deep": (116, 82, 46),# Deep Furrow   #74522e
        "slug": "midday-watch",
    },
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def multi_stop_gradient(size, stops) -> Image.Image:
    """Vertical gradient through any number of (position 0-1, colour) stops.

    A two-colour blend through olive was the first version's mistake: noon is a
    *blue* sky with warm light in it, not a brown one.
    """
    w, h = size
    stops = sorted(stops, key=lambda s: s[0])
    column = Image.new("RGB", (1, h))
    px = column.load()
    for y in range(h):
        t = y / max(1, h - 1)
        left = stops[0]
        right = stops[-1]
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                left, right = stops[i], stops[i + 1]
                break
        span = max(1e-6, right[0] - left[0])
        k = min(1.0, max(0.0, (t - left[0]) / span))
        px[0, y] = tuple(int(round(a + (b - a) * k))
                         for a, b in zip(left[1], right[1]))
    return column.resize((w, h), Image.Resampling.BILINEAR)


def radial_glow(size, centre, radius, colour, strength: float) -> Image.Image:
    """A soft halo used behind the sun."""
    w, h = size
    layer = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(layer)
    steps = 28
    for i in range(steps, 0, -1):
        r = radius * i / steps
        d.ellipse([centre[0] - r, centre[1] - r, centre[0] + r, centre[1] + r],
                  fill=int(255 * strength * (1 - i / steps) ** 1.7))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.10))
    tint = Image.new("RGB", (w, h), colour)
    return Image.composite(tint, Image.new("RGB", (w, h), (0, 0, 0)), layer)


def sun(img: Image.Image, centre, radius, palette: dict, halo: float = 0.55) -> Image.Image:
    """Disc, concentric inner band, and a halo that stays behind the disc."""
    glow = radial_glow(img.size, centre, radius * 2.9, palette["sun"], halo)
    img = Image.blend(img, Image.blend(img, glow, 0.55), 0.85)
    d = ImageDraw.Draw(img)
    cx, cy = centre
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=palette["sun"])
    inner = radius * 0.60
    d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner], fill=palette["brass"])
    return img


def ridge_mask(size, base_y: float, amplitude: float, wavelength: float,
               phase: float, steps: int = 240) -> Image.Image:
    """A smooth hill ridge as a fill mask — calm, not a comb of hairlines."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    pts = []
    for i in range(steps + 1):
        x = w * i / steps
        t = (x / w) * wavelength + phase
        y = base_y + amplitude * (0.62 * math.sin(t) + 0.38 * math.sin(t * 2.3 + 1.1))
        pts.append((x, y))
    pts += [(w, h), (0, h)]
    d.polygon(pts, fill=255)
    return mask


def horizon_bloom(img: Image.Image, y: float, colour, strength: float = 0.30) -> Image.Image:
    """Warm light pooling on the horizon line: noon haze, not a hard edge."""
    w, h = img.size
    band = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(band)
    for i in range(40):
        t = i / 39
        off = t * h * 0.10
        d.rectangle([0, y - off * 0.5, w, y + off], fill=int(150 * strength * (1 - t) ** 1.5))
    band = band.filter(ImageFilter.GaussianBlur(h * 0.012))
    return Image.composite(Image.new("RGB", (w, h), colour), img, band)


def layered_landscape(img: Image.Image, palette: dict, horizon: float,
                      colours: tuple | None = None) -> Image.Image:
    """Warm field, three ridges, each a little deeper: depth without noise."""
    w, h = img.size
    # Two warm layers, not three: a third dark layer swallows the field and turns
    # the bottom of the frame into a black band, which reads as nightfall.
    colours = colours or (palette["field"], palette["field_deep"])
    for i, colour in enumerate(colours):
        y = horizon + i * h * 0.045
        amp = h * (0.022 - i * 0.007)
        mask = ridge_mask((w, h), y, amp, 2.5 - i * 0.45, i * 1.8)
        img.paste(colour, (0, 0), mask)
    return img


def watchtower(draw, size, base, width, height, colour):
    """A watchtower on the ridge: the mark that makes the name literal."""
    w, h = size
    bx, by = base
    tw, th = width, height
    draw.polygon([(bx - tw * 0.60, by), (bx + tw * 0.60, by),
                  (bx + tw * 0.38, by - th), (bx - tw * 0.38, by - th)], fill=colour)
    # parapet, slightly wider than the shaft
    draw.rectangle([bx - tw * 0.56, by - th - h * 0.028,
                    bx + tw * 0.56, by - th], fill=colour)


def tracked_text(draw, xy, text, fnt, fill, tracking: float):
    """Draw letter-spaced text; Pillow has no tracking, and brand type needs it."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += fnt.getlength(ch) + tracking
    return x


def tracked_width(text: str, fnt, tracking: float) -> float:
    return sum(fnt.getlength(ch) + tracking for ch in text) - (tracking if text else 0)


def centred_tracked(draw, centre_x, y, text, fnt, fill, tracking):
    width = tracked_width(text, fnt, tracking)
    tracked_text(draw, (centre_x - width / 2, y), text, fnt, fill, tracking)


def make_avatar(palette: dict) -> Image.Image:
    """800x800, shown as a circle: the mark lives inside the centre ~78%."""
    ss = 3
    w = h = AVATAR[0] * ss
    img = multi_stop_gradient((w, h), [
        (0.00, palette["sky"]),
        (0.46, palette["panel"]),
        (0.80, palette["haze"]),
    ])
    img = sun(img, (int(w * 0.385), int(h * 0.325)), int(w * 0.150), palette, halo=0.50)
    img = horizon_bloom(img, int(h * 0.655), palette["sun"], 0.22)
    img = layered_landscape(img, palette, int(h * 0.660))

    d = ImageDraw.Draw(img)
    watchtower(d, (w, h), (int(w * 0.660), int(h * 0.700)),
               int(w * 0.115), int(h * 0.320), palette["shadow"])
    return img.resize(AVATAR, Image.Resampling.LANCZOS)


def make_banner(palette: dict) -> Image.Image:
    w, h = BANNER
    img = multi_stop_gradient((w, h), [
        (0.00, palette["sky"]),
        (0.42, palette["panel"]),
        (0.74, (86, 122, 130)),
        (0.86, (196, 148, 92)),   # warm haze where the field begins
        (1.00, (150, 106, 66)),
    ])
    img = sun(img, (int(w * 0.775), int(h * 0.255)), int(w * 0.055), palette, halo=0.45)
    img = horizon_bloom(img, int(h * 0.800), palette["sun"], 0.30)
    img = layered_landscape(img, palette, int(h * 0.802))

    d = ImageDraw.Draw(img)
    watchtower(d, (w, h), (int(w * 0.842), int(h * 0.862)),
               int(w * 0.034), int(h * 0.180), palette["shadow"])

    # ---- text, all of it inside the mobile-safe box -------------------------
    safe_w, safe_h = BANNER_SAFE
    top = (h - safe_h) // 2
    centre_x = w // 2

    title_size = int(safe_h * 0.34)
    title = font("Inter-Black.ttf", title_size)
    tracking = title_size * 0.055
    width = tracked_width(palette["name"].upper(), title, tracking)
    if width > safe_w * 0.90:
        title_size = int(title_size * (safe_w * 0.90) / width)
        title = font("Inter-Black.ttf", title_size)
        tracking = title_size * 0.055
    title_y = top + int(safe_h * 0.10)
    centred_tracked(d, centre_x, title_y, palette["name"].upper(),
                    title, palette["ivory"], tracking)

    rule_y = title_y + int(title_size * 1.42)
    rule_w = int(safe_w * 0.26)
    d.rectangle([centre_x - rule_w // 2, rule_y, centre_x + rule_w // 2,
                 rule_y + max(4, int(safe_h * 0.015))], fill=palette["sun"])

    tag_size = int(safe_h * 0.125)
    tag = font("Inter-Medium.ttf", tag_size)
    tag_y = rule_y + int(safe_h * 0.085)
    centred_tracked(d, centre_x, tag_y, palette["tagline"], tag,
                    palette["haze"], tag_size * 0.02)

    verse_size = int(safe_h * 0.088)
    verse = font("Inter-Regular.ttf", verse_size)
    centred_tracked(d, centre_x, tag_y + int(tag_size * 1.70), palette["verse"],
                    verse, palette["sun"], verse_size * 0.16)
    return img


def make_watermark(palette: dict) -> Image.Image:
    """150x150 RGBA: gold disc with the tower cut out, legible at 22 px."""
    ss = 4
    s = WATERMARK[0] * ss
    disc = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(disc)
    pad = int(s * 0.05)
    d.ellipse([pad, pad, s - pad, s - pad], fill=palette["sun"] + (255,))
    inner = int(s * 0.16)
    d.ellipse([pad + inner, pad + inner, s - pad - inner, s - pad - inner],
              fill=palette["brass"] + (255,))
    watchtower(ImageDraw.Draw(disc), (s, s), (s // 2, s - pad - int(s * 0.06)),
               int(s * 0.19), int(s * 0.40), palette["shadow"] + (255,))
    return disc.resize(WATERMARK, Image.Resampling.LANCZOS)


def make_thumbnail_template(palette: dict) -> Image.Image:
    """1280x720: the CTR system in miniature, with placeholder declaration text.

    Text sits in the bottom-left third, clear of the duration badge (bottom-right)
    and of the title YouTube draws over the top of the tile.
    """
    w, h = THUMBNAIL
    img = multi_stop_gradient((w, h), [
        (0.00, palette["sky"]),
        (0.40, palette["panel"]),
        (0.72, (72, 108, 118)),
        (0.88, (186, 140, 86)),
    ])
    img = sun(img, (int(w * 0.735), int(h * 0.225)), int(w * 0.078), palette, halo=0.42)
    img = horizon_bloom(img, int(h * 0.775), palette["sun"], 0.28)
    img = layered_landscape(img, palette, int(h * 0.780))

    # The tower appears in every long-form tile: it is the channel's mark, and a
    # viewer should recognise a Midday Watch thumbnail from the search grid alone.
    watchtower(ImageDraw.Draw(img), (w, h), (int(w * 0.885), int(h * 0.818)),
               int(w * 0.052), int(h * 0.150), palette["shadow"])

    scrim = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(scrim)
    for i in range(h):
        sd.line([(0, i), (w, i)],
                fill=int(168 * max(0.0, (i - h * 0.36) / (h * 0.64)) ** 1.15))
    img = Image.composite(Image.new("RGB", (w, h), palette["shadow"]), img, scrim)

    d = ImageDraw.Draw(img)
    line1 = font("Inter-Black.ttf", int(h * 0.140))
    line2 = font("Inter-Black.ttf", int(h * 0.118))
    x = int(w * 0.065)
    d.text((x, int(h * 0.520)), "PAUSE", font=line1, fill=palette["sun"])
    d.text((x, int(h * 0.665)), "AND PRAY", font=line2, fill=palette["ivory"])

    verse = font("Inter-SemiBold.ttf", int(h * 0.040))
    d.text((x, int(h * 0.845)), "PSALM 55:17  ·  NOON", font=verse, fill=palette["brass"])
    return img


ASSETS = {
    "avatar": ("-avatar.png", make_avatar),
    "banner": ("-banner.png", make_banner),
    "watermark": ("-watermark.png", make_watermark),
    "thumbnail": ("-thumbnail-template.png", make_thumbnail_template),
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render a channel's brand assets.")
    ap.add_argument("--channel", default="midday-watch", choices=sorted(PALETTES))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing files (approved art must be redrawn on purpose)")
    args = ap.parse_args(argv)

    palette = PALETTES[args.channel]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for kind, (suffix, maker) in ASSETS.items():
        path = out_dir / f"{palette['slug']}{suffix}"
        if path.exists() and not args.force:
            print(f"skip {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} "
                  f"(exists; --force to redraw)")
            continue
        image = maker(palette)
        image.save(path, optimize=True)
        print(f"{kind:10s} {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path} "
              f"{image.size[0]}x{image.size[1]} {image.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
