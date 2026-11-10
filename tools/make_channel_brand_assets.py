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
               inside the smaller of those, or it is cropped on a phone. The
               *scenery* has to survive the taller band a phone really shows —
               measured, not assumed: see PHONE_CROP;
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

#: The window a phone actually shows: the centre 1546 x 423 of the file.
#:
#: This is YouTube's documented "TV/mobile safe area" — but the phone does not
#: merely keep the type inside it, it *crops* to it and scales what is left up to
#: the card. Two screenshots of the live channel (2026-11-06, 1080x2400 Android)
#: measured card ratios of 3.63:1 and 3.63:1, which is 2560 x 705 if the card were
#: showing the full width — it is not. The wordmark is 1091 px wide in the file and
#: rendered 699 px wide in a 984 px card, so the card shows 984 * 1091 / 699 =
#: 1535 px of the 2560: the middle six-tenths. Fitting every candidate crop to the
#: screenshot confirmed it (MAE 7.6 at 1526x443, 7.8 at 1546x423, 11+ at 2560x705).
#:
#: A first fix read the card's aspect ratio and assumed the full width, decided the
#: window was 2560 x 753, and left the sun straddling its edge — on the phone that
#: is a gold crescent in the corner. Scenery must now be laid out so that no hard
#: shape crosses this box: it is either wholly inside, or wholly outside.
PHONE_CROP = (1546, 423)
WATERMARK = (150, 150)
THUMBNAIL = (1280, 720)
#: The one-page brand sheet. Tall enough that the notes column and the footer
#: clear the thumbnail: at 1700 the footer sat under it.
SHEET = (1800, 1760)

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
    "midnight-watch": {
        "name": "The Midnight Watch",
        "tagline": "Rise and pray at midnight",
        "verse": "Psalm 119:62",
        "sky": (10, 14, 42),        # Midnight Indigo #0a0e2a
        "panel": (34, 32, 92),      # Royal Vigil     #22205c
        "sun": (255, 208, 96),      # Watchtower Gold #ffd060
        "brass": (222, 162, 62),    # Covenant Brass  #dea23e
        "ivory": (251, 247, 238),   # Watch Ivory     #fbf7ee
        "haze": (212, 220, 242),    # Starlight Mist  #d4dcf2
        "shadow": (5, 7, 22),       # Deep Bastion    #050716
        "field": (56, 52, 108),     # Fortress Ridge  #38346c
        "field_deep": (26, 24, 62), # Night Rampart   #1a183e
        "slug": "midnight-watch",
    },
    "family-altar": {
        "name": "The Family Altar",
        "tagline": "As for me and my house",
        "verse": "Joshua 24:15",
        "sky": (12, 28, 19),        # Covenant Emerald #0c1c13
        "panel": (26, 48, 34),      # Olive Sanctuary  #1a3022
        "sun": (247, 212, 132),     # Hearth Gold      #f7d484
        "brass": (214, 162, 74),    # Oil Lamp Brass   #d6a24a
        "ivory": (252, 246, 232),   # Parchment Ivory  #fcf6e8
        "haze": (208, 222, 206),    # Olive Mist       #d0dece
        "shadow": (6, 15, 10),      # Deep Hearth      #060f0a
        "field": (88, 68, 36),      # Timber Table     #584424
        "field_deep": (52, 38, 20), # Stone Hearth     #342614
        "slug": "family-altar",
    },
}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def phone_crop_box(size, crop=PHONE_CROP):
    """The centred window a phone shows of a banner, as a PIL crop box."""
    w, h = size
    cw, ch = crop
    left, top = (w - cw) // 2, (h - ch) // 2
    return (left, top, left + cw, top + ch)


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


def mix_colour(a, b, k: float):
    """Blend two RGB tuples; k=0 is a, k=1 is b."""
    return tuple(int(round(x + (y - x) * k)) for x, y in zip(a, b))


def noon_field(img: Image.Image, palette: dict, horizon: float) -> Image.Image:
    """The banner's ground: bright at the horizon, furrow-dark at the foot.

    Two flat warm layers (what the avatar and thumbnail use) put a 300 px slab of
    one brown across the bottom third of a 16:9 banner, which read as a painted
    rectangle rather than a field — seen in QA 2026-11-06. A gradient carries the
    recession, and two ridge silhouettes give it form, so the light stays noon at
    the horizon and only deepens toward the frame edge.
    """
    w, h = img.size
    t0 = horizon / h
    mid = mix_colour(palette["field"], palette["field_deep"], 0.55)
    ground = multi_stop_gradient((w, h), [
        (0.00, palette["field"]),
        (t0, palette["field"]),
        (min(1.0, (t0 + 1.0) / 2), mid),
        (1.00, palette["field_deep"]),
    ])
    far = ridge_mask((w, h), horizon, h * 0.022, 2.5, 0.0)
    img.paste(ground, (0, 0), far)
    # Front ridge, a little deeper: form without a hard band across the frame.
    shade = Image.new("RGB", (w, h), palette["field_deep"])
    front = ridge_mask((w, h), horizon + h * 0.075, h * 0.016, 3.1, 1.8)
    img.paste(Image.blend(ground, shade, 0.35), (0, 0), front)
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
    """2560x1440: the mark inside the phone band, the type inside the safe box.

    Two boxes, not one. Type has to sit in the centre 1235x338 (BANNER_SAFE) so it
    never comes near a crop edge. Scenery has to sit wholly outside the centre
    1546x423 window a phone shows (PHONE_CROP), or wholly inside it — a shape that
    straddles the edge is the gold crescent that appeared in the corner of the live
    channel on 2026-11-06. So the sun rides high in the top-right and the tower
    stands right of the window: the phone gets a clean wordmark card, and the TV's
    wider frame gets the full noon landscape.
    """
    w, h = BANNER
    box = phone_crop_box((w, h))
    img = multi_stop_gradient((w, h), [
        (0.00, palette["sky"]),
        (0.42, palette["panel"]),
        (0.60, (86, 122, 130)),
        (0.70, (196, 148, 92)),   # warm haze where the field begins
        (1.00, (150, 106, 66)),
    ])
    # Sun: wholly above the phone window (box[1] = 508), with 11 px to spare even
    # against the wider-and-shorter crop a 16:9 TV card would show (top 343).
    sun_y = int(h * 0.140)
    img = sun(img, (int(w * 0.838), sun_y), int(w * 0.051), palette, halo=0.45)
    # Horizon below the phone window: the phone sees the haze at its foot, the TV
    # sees the whole field.
    horizon = box[3] + int(h * 0.055)
    img = horizon_bloom(img, horizon - int(h * 0.002), palette["sun"], 0.30)
    img = noon_field(img, palette, horizon)

    d = ImageDraw.Draw(img)
    # Tower stands on that field, wholly right of the window (right edge 2053).
    watchtower(d, (w, h), (int(w * 0.852), horizon + int(h * 0.016)),
               int(w * 0.042), int(h * 0.150), palette["shadow"])

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



def make_brand_sheet(palette: dict, media_dir: Path) -> Image.Image:
    """One image showing every asset, so a reviewer can judge the set at a glance.

    Includes the mobile crop of the banner (the centre 1235x338 a phone shows) and
    the watermark on a checkerboard, because both are things a flat preview hides.
    """
    W, H = SHEET
    ink = (16, 22, 28)
    sheet = Image.new("RGB", (W, H), ink)
    d = ImageDraw.Draw(sheet)

    title = font("Inter-Black.ttf", 46)
    sub = font("Inter-Regular.ttf", 24)
    label = font("Inter-SemiBold.ttf", 22)
    small = font("Inter-Regular.ttf", 19)

    tracked_text(d, (80, 62), palette["name"].upper(), title, palette["ivory"], 3.0)
    d.text((80, 122), f"{palette['verse']}  ·  {palette['tagline']}", font=sub,
           fill=palette["haze"])

    # --- avatar + watermark ---------------------------------------------------
    avatar = Image.open(media_dir / f"{palette['slug']}-avatar.png").convert("RGB")
    avatar = avatar.resize((360, 360), Image.Resampling.LANCZOS)
    sheet.paste(avatar, (80, 200))
    d.text((80, 572), "AVATAR  800 × 800", font=label, fill=palette["sun"])

    # watermark on a checkerboard: transparency is invisible on a flat colour
    wm = Image.open(media_dir / f"{palette['slug']}-watermark.png").convert("RGBA")
    wm = wm.resize((220, 220), Image.Resampling.LANCZOS)
    tile = 22
    board = Image.new("RGB", (240, 240), (58, 62, 66))
    bd = ImageDraw.Draw(board)
    for y in range(0, 240, tile):
        for x in range(0, 240, tile):
            if (x // tile + y // tile) % 2 == 0:
                bd.rectangle([x, y, x + tile - 1, y + tile - 1], fill=(96, 101, 106))
    board.paste(wm, (10, 10), wm)
    sheet.paste(board, (480, 270))
    d.text((480, 572), "WATERMARK  150 × 150 (transparent)", font=label,
           fill=palette["sun"])

    # --- palette --------------------------------------------------------------
    swatch_x, swatch_y = 820, 210
    d.text((swatch_x, swatch_y - 44), "PALETTE", font=label, fill=palette["sun"])
    roles = [("sky", "Zenith Blue"), ("panel", "Noon Sky"), ("sun", "High Sun"),
             ("brass", "Warm Brass"), ("ivory", "Ivory"), ("haze", "Sand Haze"),
             ("shadow", "Hard Shadow"), ("field", "Sunlit Field"),
             ("field_deep", "Deep Furrow")]
    for i, (key, name) in enumerate(roles):
        col = palette[key]
        cx = swatch_x + (i % 3) * 250
        cy = swatch_y + (i // 3) * 118
        d.rounded_rectangle([cx, cy, cx + 84, cy + 84], radius=10, fill=col)
        hex_code = "#{:02x}{:02x}{:02x}".format(*col)
        d.text((cx + 96, cy + 14), name, font=small, fill=palette["ivory"])
        d.text((cx + 96, cy + 42), hex_code, font=small, fill=palette["haze"])

    # --- banner: the band a phone actually shows ------------------------------
    # The phone band, not BANNER_SAFE: the safe box is where the *type* must fit,
    # the window the phone crops to (see PHONE_CROP): type inside it, scenery out.
    banner = Image.open(media_dir / f"{palette['slug']}-banner.png").convert("RGB")
    crop = banner.crop(phone_crop_box(banner.size))
    scale = 1640 / crop.width
    crop = crop.resize((1640, int(crop.height * scale)), Image.Resampling.LANCZOS)
    y = 660
    sheet.paste(crop, (80, y))
    d.text((80, y - 40), "BANNER  2560 × 1440 — this is exactly what a phone shows "
                         f"(centre {PHONE_CROP[0]} × {PHONE_CROP[1]})",
           font=label, fill=palette["sun"])

    # --- thumbnail ------------------------------------------------------------
    thumb = Image.open(media_dir / f"{palette['slug']}-thumbnail-template.png").convert("RGB")
    ty = y + crop.height + 66
    thumb = thumb.resize((760, 428), Image.Resampling.LANCZOS)
    sheet.paste(thumb, (80, ty))
    d.text((80, ty - 40), "THUMBNAIL  1280 × 720", font=label, fill=palette["sun"])
    notes = [
        "Mark: a high sun over a watchtower on a warm noon field.",
        "No lettering in the avatar or watermark — at 48 px and 22 px",
        "a wordmark is mush; a disc and a tower still read.",
        "",
        "Thumbnail type sits above the field and clear of the",
        "duration badge, so it survives the 246 × 138 phone tile.",
        "",
        "Redraw: python tools/make_channel_brand_assets.py",
        "        --channel midday-watch --force",
    ]
    for i, line in enumerate(notes):
        d.text((900, ty + 10 + i * 34), line, font=small, fill=palette["haze"])

    footer = font("Inter-Regular.ttf", 20)
    d.text((80, H - 54), "The Midday Watch · prayer3 · live on @TheMiddayWatch, "
                         "uploads not yet provisioned · kit: docs/MIDDAY_WATCH_BRANDING.md",
           font=footer, fill=(120, 132, 140))
    return sheet

#: The download-and-hand-off archive. Rebuilt by --kit, never edited by hand: the
#: test suite compares every byte inside it with the file in docs/media, because the
#: copy that gets uploaded to YouTube is the copy in the zip.
KIT_DIR = "midday-watch-brand-kit"
KIT_ZIP = "midday-watch-brand-assets.zip"

START_HERE = """THE MIDDAY WATCH — brand kit
prayer3 · handle @TheMiddayWatch · Psalm 55:17

WHAT IS IN HERE
  midday-watch-avatar.png              800 x 800   profile picture (shown as a circle)
  midday-watch-banner.png             2560 x 1440  channel banner (all type inside 1235 x 338)
  midday-watch-watermark.png           150 x 150   video watermark, transparent
  midday-watch-thumbnail-template.png 1280 x 720   reference for the thumbnail system, not uploaded
  midday-watch-brand-sheet.png        1800 x 1760  every asset + the palette on one page
  MIDDAY_WATCH_BRANDING.md                         the full identity document
  THIRD_CHANNEL_SETUP.md                           how the channel is wired into the pipeline
  START_HERE.txt                                   this file

UPLOAD ORDER (Studio -> Customization -> Branding)
  1. Picture        midday-watch-avatar.png
  2. Banner image   midday-watch-banner.png
  3. Video watermark (Entire video)   midday-watch-watermark.png   [desktop Studio only]
  Then paste the About text and the keywords from MIDDAY_WATCH_BRANDING.md sections 2 and 3.

CHECK THE BANNER ON A PHONE, NOT IN THE PREVIEW
  A phone crops the banner to the centre 1546 x 423 and scales that up to the card,
  so nothing hard may cross that edge: the sun and the watchtower sit wholly outside
  it (they play on the TV's wider frame) and all the type sits wholly inside it. The
  Edit-channel preview zoom-crops and is not what viewers see.

PALETTE
  Zenith Blue   #0d3350    Noon Sky      #1c5d7a    High Sun      #ffc247
  Warm Brass    #e39a34    Ivory         #fbf6ec    Sand Haze     #d9e6ea
  Hard Shadow   #0a1a26    Sunlit Field  #b98b4e    Deep Furrow   #74522e

REDRAW FROM SOURCE
  python tools/make_channel_brand_assets.py --channel midday-watch --sheet --kit
  (add --force to overwrite art that already exists; nothing is replaced silently)
"""


def build_kit(zip_path: Path, media_dir: Path, docs_dir: Path) -> Path:
    """Write the hand-off archive: four uploads, the sheet, both docs, START_HERE.

    Generated rather than staged by hand, because a kit that is half hand-copied
    drifts from the art it claims to contain — and the file that reaches YouTube is
    the one inside the zip.
    """
    import zipfile

    palette = PALETTES["midday-watch"]
    members = [(media_dir / f"{palette['slug']}{suffix}", f"{palette['slug']}{suffix}")
               for suffix, _ in ASSETS.values()]
    members.append((media_dir / f"{palette['slug']}-brand-sheet.png",
                    f"{palette['slug']}-brand-sheet.png"))
    members.append((docs_dir / "MIDDAY_WATCH_BRANDING.md", "MIDDAY_WATCH_BRANDING.md"))
    members.append((docs_dir / "THIRD_CHANNEL_SETUP.md", "THIRD_CHANNEL_SETUP.md"))

    missing = [str(src) for src, _ in members if not src.exists()]
    if missing:
        raise SystemExit("cannot build the kit, these files are missing:\n  "
                         + "\n  ".join(missing))

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{KIT_DIR}/START_HERE.txt", START_HERE)   # reads first in the list
        for src, name in members:
            zf.write(src, f"{KIT_DIR}/{name}")
    return zip_path


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
    ap.add_argument("--sheet", action="store_true",
                    help="also render the one-page brand sheet (all assets at a glance)")
    ap.add_argument("--kit", action="store_true",
                    help="also build the downloadable zip (art + sheet + both docs)")
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

    if args.sheet:
        sheet_path = out_dir / f"{palette['slug']}-brand-sheet.png"
        sheet = make_brand_sheet(palette, out_dir)
        sheet.save(sheet_path, optimize=True)
        print(f"{'sheet':10s} {sheet_path} {sheet.size[0]}x{sheet.size[1]}")

    if args.kit:
        zip_path = build_kit(out_dir / KIT_ZIP, out_dir, ROOT / "docs")
        size_kb = zip_path.stat().st_size / 1024
        print(f"{'kit':10s} {zip_path} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
