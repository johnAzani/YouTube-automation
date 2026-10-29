"""Draft thumbnail generator (Pillow-based — see pipeline/textplates.py).

The pipeline ships *drafts*: brand plate + big title text over the first scene
still, plus A/B/C variants for YouTube Studio's Test & Compare (winner is
decided by watch-time share — docs/GROWTH.md §4.3). A human should always
review/replace before publish: the thumbnail is the highest-leverage CTR
decision on the platform.
"""
from __future__ import annotations

from __future__ import annotations

import textwrap
from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc
from .textplates import render_text_plate

# Variant recipes: (background use, title size, plate color)
_VARIANTS = [
    ("main", 64, (22, 33, 62)),
    ("a", 72, (90, 22, 22)),     # red plate, bigger text
    ("b", 56, (18, 74, 56)),     # green plate, smaller text
    ("c", 64, (22, 33, 62)),     # same as main but no bg image
]


def render_studio_thumbnail(
    out_path: Path,
    title: str,
    subtitle: str = "",
    kicker: str = "",
    tag: str = "",
    bg_path: Path | None = None,
    width: int = 1280,
    height: int = 720,
    is_prayer: bool = True,
    bg_color: tuple[int, int, int] = (12, 32, 74),
) -> Path:
    """Render a high-CTR, scroll-stopping 1280x720 studio thumbnail with frosted sapphire
    glassmorphism, Inter-Black kinetic typography, golden amber borders, and safe-zone margin."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

    font_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    f_kick = ImageFont.truetype(str(font_dir / "Inter-ExtraBold.ttf"), 22)
    f_hero = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 82)
    f_sub = ImageFont.truetype(str(font_dir / "Inter-SemiBold.ttf"), 26)
    f_tag = ImageFont.truetype(str(font_dir / "Inter-Bold.ttf"), 20)

    if bg_path is not None and bg_path.is_file():
        raw = Image.open(bg_path).convert("RGB")
        scale = max(width / max(1, raw.width), height / max(1, raw.height))
        sw, sh = max(width, int(round(raw.width * scale))), max(height, int(round(raw.height * scale)))
        base = raw.resize((sw, sh), Image.Resampling.LANCZOS)
        x0, y0 = (sw - width) // 2, (sh - height) // 2
        base = base.crop((x0, y0, x0 + width, y0 + height))

        if is_prayer:
            gamma = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** 0.88))))) for i in range(256)]
            lifted = base.point(gamma * 3)
            shadow, mid, high = (4, 14, 40), (16, 62, 136), (196, 226, 255)
            lr, lg, lb = [], [], []
            for i in range(256):
                t = i / 255.0
                if t < 0.54:
                    u = t / 0.54
                    c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
                else:
                    u = (t - 0.54) / 0.46
                    c = [mid[k] + (high[k] - mid[k]) * (u ** 1.08) for k in range(3)]
                lr.append(int(c[0]))
                lg.append(int(c[1]))
                lb.append(int(c[2]))
            lum = lifted.convert("L")
            duo = Image.merge("RGB", (lum.point(lr), lum.point(lg), lum.point(lb)))
            base = Image.blend(lifted, duo, 0.78)
            base = ImageEnhance.Contrast(base).enhance(1.15)
    else:
        base = Image.new("RGB", (width, height), bg_color)

    # Scrim for text readability on left-center
    scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.ellipse([20, 60, 880, 680], fill=(4, 12, 32, 185))
    sd.ellipse([100, 140, 720, 600], fill=(12, 38, 88, 110))
    scrim = scrim.filter(ImageFilter.GaussianBlur(54))
    canvas = Image.alpha_composite(base.convert("RGBA"), scrim)

    # Frosted glass card behind typography (left-aligned, safe from right-hand duration badge)
    cw, ch = 820, 484
    cx, cy = 60, 110
    card_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_img)
    cd.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=24, fill=(8, 24, 56, 175), outline=(235, 198, 92, 215), width=2)
    cd.rounded_rectangle([2, 2, cw - 3, ch - 3], radius=22, outline=(255, 255, 255, 45), width=1)
    canvas.alpha_composite(card_img, (cx, cy))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Kicker badge pill
    kicker_txt = kicker or (subtitle.upper() if subtitle else "THE SECRET PLACE · NIGHT PRAYER")
    kw = d.textlength(kicker_txt, font=f_kick)
    bx0, by0 = cx + 42, cy + 36
    d.rounded_rectangle([bx0, by0, bx0 + int(kw + 36), by0 + 38], radius=8, fill=(12, 36, 82, 240), outline=(255, 218, 64, 220), width=1)
    d.text((bx0 + 18, by0 + 7), kicker_txt, font=f_kick, fill=(255, 228, 130, 255))

    # 2. Main title text
    words = title.upper().split()
    if len(words) <= 2:
        lines = [" ".join(words)]
    elif len(words) == 3:
        lines = [" ".join(words[:2]), words[2]]
    elif len(words) <= 5:
        mid_idx = len(words) // 2
        lines = [" ".join(words[:mid_idx]), " ".join(words[mid_idx:])]
    else:
        lines = textwrap.wrap(title.upper(), width=18)[:3]

    y_cur = cy + 96
    for idx, line in enumerate(lines):
        is_last = (idx == len(lines) - 1)
        fill_col = (255, 218, 64, 255) if (is_last and len(lines) > 1) else (255, 255, 255, 255)
        # Drop shadow
        d.text((cx + 42, y_cur + 6), line, font=f_hero, fill=(0, 0, 0, 240))
        if fill_col == (255, 218, 64, 255):
            for gx, gy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                d.text((cx + 42 + gx, y_cur + gy), line, font=f_hero, fill=(255, 200, 40, 140))
        d.text((cx + 42, y_cur), line, font=f_hero, fill=fill_col)
        y_cur += 88

    # 3. Gold underline rule
    uy = y_cur + 8
    d.rounded_rectangle([cx + 42, uy, cx + 42 + 420, uy + 5], radius=3, fill=(255, 218, 64, 245))

    # 4. Subtitle
    sub_txt = subtitle if subtitle and subtitle.upper() != kicker_txt else "DIVINE PROTECTION BEFORE YOU SLEEP"
    d.text((cx + 42, uy + 20), sub_txt.upper(), font=f_sub, fill=(225, 240, 255, 245))

    # 5. Tag pill
    tag_txt = tag or "16 VERSES · FULL SCRIPTURE MEDITATION"
    tw_tag = d.textlength(tag_txt, font=f_tag)
    d.rounded_rectangle([cx + 42, uy + 64, cx + 42 + int(tw_tag + 32), uy + 102], radius=8, fill=(16, 48, 108, 230), outline=(148, 198, 255, 180), width=1)
    d.text((cx + 58, uy + 72), tag_txt, font=f_tag, fill=(255, 255, 255, 240))

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "JPEG", quality=95, optimize=True)
    return out_path


def generate_short_vertical_poster(
    bg_path: Path | None,
    out_path: Path,
    kicker: str = "PRAYER BEFORE SLEEP",
    line1: str = "BEFORE YOU SLEEP",
    line2: str = "PRAY PSALM 91",
    sub: str = "DIVINE PROTECTION OVER YOUR HOME",
    tag: str = "HE WHO DWELLS IN THE SECRET PLACE",
    width: int = 720,
    height: int = 1280,
) -> Path:
    """Render a high-impact 9:16 vertical poster thumbnail for YouTube Shorts with
    frosted sapphire glassmorphism, Inter typography, and radiant gold illumination."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

    font_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    f_kick = ImageFont.truetype(str(font_dir / "Inter-ExtraBold.ttf"), 20)
    f_l1 = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 62)
    f_l2 = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 62)
    f_sub = ImageFont.truetype(str(font_dir / "Inter-SemiBold.ttf"), 22)
    f_tag = ImageFont.truetype(str(font_dir / "Inter-Bold.ttf"), 19)

    if bg_path is not None and bg_path.is_file():
        raw = Image.open(bg_path).convert("RGB")
        scale = max(width / max(1, raw.width), height / max(1, raw.height))
        sw, sh = max(width, int(round(raw.width * scale))), max(height, int(round(raw.height * scale)))
        base = raw.resize((sw, sh), Image.Resampling.LANCZOS)
        x0, y0 = (sw - width) // 2, (sh - height) // 2
        base = base.crop((x0, y0, x0 + width, y0 + height))

        gamma = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** 0.88))))) for i in range(256)]
        lifted = base.point(gamma * 3)
        shadow, mid, high = (4, 14, 40), (16, 62, 136), (196, 226, 255)
        lr, lg, lb = [], [], []
        for i in range(256):
            t = i / 255.0
            if t < 0.54:
                u = t / 0.54
                c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
            else:
                u = (t - 0.54) / 0.46
                c = [mid[k] + (high[k] - mid[k]) * (u ** 1.08) for k in range(3)]
            lr.append(int(c[0]))
            lg.append(int(c[1]))
            lb.append(int(c[2]))
        lum = lifted.convert("L")
        duo = Image.merge("RGB", (lum.point(lr), lum.point(lg), lum.point(lb)))
        base = Image.blend(lifted, duo, 0.78)
        base = ImageEnhance.Contrast(base).enhance(1.15)
    else:
        base = Image.new("RGB", (width, height), (8, 22, 52))

    scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.ellipse([40, 360, 680, 1020], fill=(4, 12, 32, 180))
    sd.ellipse([100, 440, 620, 940], fill=(12, 38, 88, 120))
    sd.ellipse([180, 500, 540, 880], fill=(255, 198, 50, 35))
    scrim = scrim.filter(ImageFilter.GaussianBlur(48))
    canvas = Image.alpha_composite(base.convert("RGBA"), scrim)

    cw, ch = 640, 480
    cx, cy = (width - cw) // 2, 430
    card_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_img)
    cd.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=26, fill=(8, 22, 52, 180), outline=(235, 198, 92, 215), width=2)
    cd.rounded_rectangle([2, 2, cw - 3, ch - 3], radius=24, outline=(255, 255, 255, 45), width=1)
    canvas.alpha_composite(card_img, (cx, cy))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # 1. Kicker badge
    kw = d.textlength(kicker, font=f_kick)
    bx0, by0 = (width - int(kw + 36)) // 2, cy + 34
    d.rounded_rectangle([bx0, by0, bx0 + int(kw + 36), by0 + 36], radius=8, fill=(12, 36, 82, 240), outline=(255, 218, 64, 220), width=1)
    d.text((bx0 + 18, by0 + 6), kicker, font=f_kick, fill=(255, 228, 130, 255))

    # 2. Main titles
    w1 = d.textlength(line1, font=f_l1)
    x1 = (width - w1) // 2
    y1 = cy + 96
    d.text((x1, y1 + 5), line1, font=f_l1, fill=(0, 0, 0, 230))
    d.text((x1, y1), line1, font=f_l1, fill=(255, 255, 255, 255))

    w2 = d.textlength(line2, font=f_l2)
    x2 = (width - w2) // 2
    y2 = y1 + 78
    for gx, gy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        d.text((x2 + gx, y2 + gy), line2, font=f_l2, fill=(255, 200, 40, 160))
    d.text((x2, y2 + 5), line2, font=f_l2, fill=(0, 0, 0, 230))
    d.text((x2, y2), line2, font=f_l2, fill=(255, 218, 64, 255))

    # 3. Gold underline rule
    uy = y2 + 90
    d.rounded_rectangle([(width - 380) // 2, uy, (width + 380) // 2, uy + 4], radius=2, fill=(255, 218, 64, 240))

    # 4. Subtitle
    sw = d.textlength(sub, font=f_sub)
    d.text(((width - sw) // 2, uy + 18), sub, font=f_sub, fill=(215, 235, 255, 240))

    # 5. Tag pill
    tw_tag = d.textlength(tag, font=f_tag)
    tx0 = (width - int(tw_tag + 32)) // 2
    d.rounded_rectangle([tx0, uy + 62, tx0 + int(tw_tag + 32), uy + 98], radius=8, fill=(16, 48, 108, 230), outline=(148, 198, 255, 180), width=1)
    d.text((tx0 + 16, uy + 70), tag, font=f_tag, fill=(255, 255, 255, 240))

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "JPEG", quality=95, optimize=True)
    return out_path


def _safe_plate(doc: ScriptDoc, background: Path | None, out: Path,
                title_size: int, bg_color: tuple[int, int, int], use_bg: bool) -> None:
    bg = background if (use_bg and background is not None) else None
    niche = getattr(doc, "niche", "") or str(doc.meta.get("niche", ""))
    is_prayer = any(k in niche.lower() or k in doc.slug.lower() for k in ("faith", "prayer", "scripture", "devotional", "psalm"))
    sub = "The Secret Place" if is_prayer else "Money, Explained"
    try:
        render_studio_thumbnail(
            out,
            title=doc.thumb_text or doc.title,
            subtitle=sub,
            kicker="PRAYER BEFORE SLEEP · PSALM 91" if is_prayer else sub.upper(),
            tag="16 VERSES · FULL SCRIPTURE MEDITATION" if is_prayer else "DOCUMENTARY",
            bg_path=bg,
            is_prayer=is_prayer,
            bg_color=bg_color,
        )
    except Exception:
        try:
            render_text_plate(
                out,
                title=doc.thumb_text,
                subtitle=sub,
                background=bg,
                bg_color=bg_color,
                title_size=title_size,
            )
        except Exception:
            try:
                render_text_plate(out, title=doc.thumb_text, subtitle=sub, bg_color=bg_color)
            except Exception:
                from PIL import Image

                Image.new("RGB", (CONFIG.width, CONFIG.height), bg_color).save(out, quality=92)


def generate_thumbnail(doc: ScriptDoc, background: Path | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{doc.slug}_thumb.jpg"
    # Never composite over our own generated title cards (double text); only real media.
    if background is not None and background.name.startswith("card_"):
        background = None
    _safe_plate(doc, background, out, title_size=64, bg_color=(22, 33, 62), use_bg=True)
    return out


def generate_thumbnail_variants(doc: ScriptDoc, background: Path | None, out_dir: Path) -> list[Path]:
    """Main + A/B/C drafts for Studio → A/B test titles & thumbnails."""
    paths = [generate_thumbnail(doc, background, out_dir)]
    if background is not None and background.name.startswith("card_"):
        background = None
    for label, size, color in _VARIANTS[1:]:
        p = out_dir / f"{doc.slug}_thumb_{label}.jpg"
        _safe_plate(doc, background if label != "c" else None, p,
                    title_size=size, bg_color=color, use_bg=(label != "c"))
        paths.append(p)
    return paths


def generate_short_scroll_stopper_thumbnail(
    bg_path: Path | None,
    out_path: Path,
    kicker: str = "WALL STREET'S LIE",
    line1: str = "$70B",
    line2: str = "FRAUD",
    tag: str = "GONE IN 24 DAYS",
) -> Path:
    """Render a high-CTR 1280x720 thumbnail whose hero lockup also fits cleanly inside
    the center 405x720 (9:16) column so both 16:9 surfaces and 9:16 Shorts shelves pop."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

    font_dir = Path(__file__).resolve().parent.parent / "assets" / "fonts"
    f_kick = ImageFont.truetype(str(font_dir / "Inter-ExtraBold.ttf"), 22)
    f_l1 = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 126)
    f_l2 = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 92)
    f_tag = ImageFont.truetype(str(font_dir / "Inter-Black.ttf"), 21)

    is_prayer = any(
        k in kicker.lower() or k in tag.lower() or k in line1.lower() or k in line2.lower()
        for k in ("prayer", "psalm", "faith", "secret place", "covenant", "sleep", "devotional", "god", "divine")
    )

    tw, th = 1280, 720
    if bg_path is not None and bg_path.is_file():
        from PIL import ImageChops

        raw = Image.open(bg_path).convert("RGB")
        scale = max(tw / max(1, raw.width), th / max(1, raw.height))
        sw, sh = max(tw, int(round(raw.width * scale))), max(th, int(round(raw.height * scale)))
        base = raw.resize((sw, sh), Image.Resampling.LANCZOS)
        x0, y0 = (sw - tw) // 2, (sh - th) // 2
        base = base.crop((x0, y0, x0 + tw, y0 + th))
        gamma = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** (0.88 if is_prayer else 0.84)))))) for i in range(256)]
        lifted = base.point(gamma * 3)
        shadow, mid, high = (4, 14, 40), (16, 62, 136), (196, 226, 255)
        lr, lg, lb = [], [], []
        for i in range(256):
            t = i / 255.0
            if t < 0.54:
                u = t / 0.54
                c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
            else:
                u = (t - 0.54) / 0.46
                c = [mid[k] + (high[k] - mid[k]) * (u ** 1.08) for k in range(3)]
            lr.append(int(c[0]))
            lg.append(int(c[1]))
            lb.append(int(c[2]))
        lum = lifted.convert("L")
        duo = Image.merge("RGB", (lum.point(lr), lum.point(lg), lum.point(lb)))
        blue_graded = Image.blend(lifted, duo, 0.82)
        blue_graded = ImageEnhance.Contrast(blue_graded).enhance(1.15 if is_prayer else 1.12)

        if is_prayer:
            base = blue_graded
        else:
            # Preserve glowing red crash candlesticks cutting across the deep sapphire-blue grade
            r_ch, g_ch, _b_ch = lifted.split()
            diff = ImageChops.subtract(r_ch, g_ch)
            red_mask = diff.point(lambda d: 0 if d < 62 else min(235, int((d - 62) * 3.2)))
            base = Image.composite(lifted, blue_graded, red_mask.filter(ImageFilter.GaussianBlur(1.5)))
    else:
        base = Image.new("RGB", (tw, th), (8, 22, 52) if is_prayer else (12, 32, 74))

    # Focused center contrast glow so giant type pops at 16:1 contrast while keeping background vivid
    scrim = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    if is_prayer:
        sd.ellipse([410, 120, 870, 650], fill=(4, 12, 32, 175))
        sd.ellipse([455, 210, 825, 590], fill=(255, 198, 50, 48))
    else:
        sd.ellipse([410, 120, 870, 650], fill=(4, 10, 24, 158))
        sd.ellipse([455, 210, 825, 590], fill=(255, 42, 56, 44))
    scrim = scrim.filter(ImageFilter.GaussianBlur(42))
    canvas = Image.alpha_composite(base.convert("RGBA"), scrim)

    overlay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx = tw // 2

    # 1. Top kicker badge inside 9:16 center safe width (<= 368px)
    kw = d.textlength(kicker, font=f_kick)
    bpw, bph = int(kw + 44), 42
    bx0, by0 = cx - bpw // 2, 188
    d.rounded_rectangle([bx0, by0 + 4, bx0 + bpw, by0 + bph + 4], radius=10, fill=(0, 0, 0, 150))
    if is_prayer:
        d.rounded_rectangle(
            [bx0, by0, bx0 + bpw, by0 + bph],
            radius=10,
            fill=(12, 38, 88, 240),
            outline=(255, 218, 64, 220),
            width=2,
        )
        d.text((cx - kw / 2, by0 + 8), kicker, font=f_kick, fill=(255, 228, 130, 255))
    else:
        d.rounded_rectangle(
            [bx0, by0, bx0 + bpw, by0 + bph],
            radius=10,
            fill=(228, 34, 46, 248),
            outline=(255, 220, 220, 210),
            width=2,
        )
        d.text((cx - kw / 2, by0 + 8), kicker, font=f_kick, fill=(255, 255, 255, 255))

    # 2. Giant headline (fits strictly inside 376px center 9:16 width)
    w1 = d.textlength(line1, font=f_l1)
    y1 = 238
    shadow = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    shd = ImageDraw.Draw(shadow)
    shd.text((cx - w1 / 2, y1 + 8), line1, font=f_l1, fill=(0, 0, 0, 235), stroke_width=10, stroke_fill=(0, 0, 0, 235))
    w2 = d.textlength(line2, font=f_l2)
    y2 = 368
    shd.text((cx - w2 / 2, y2 + 7), line2, font=f_l2, fill=(0, 0, 0, 235), stroke_width=9, stroke_fill=(0, 0, 0, 235))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    canvas = Image.alpha_composite(canvas, shadow)

    d = ImageDraw.Draw(overlay)
    d.text(
        (cx - w1 / 2, y1),
        line1,
        font=f_l1,
        fill=(255, 255, 255, 255),
        stroke_width=6,
        stroke_fill=(8, 16, 34, 255),
    )
    d.text(
        (cx - w2 / 2, y2),
        line2,
        font=f_l2,
        fill=(255, 204, 52, 255),
        stroke_width=5,
        stroke_fill=(12, 18, 34, 255),
    )

    # 3. Bottom punchline pill inside 9:16 safe column
    tw_tag = d.textlength(tag, font=f_tag)
    tpw, tph = int(tw_tag + 46), 40
    tx0, ty0 = cx - tpw // 2, 488
    d.rounded_rectangle(
        [tx0, ty0, tx0 + tpw, ty0 + tph],
        radius=10,
        fill=(12, 38, 88, 240) if is_prayer else (8, 20, 44, 235),
        outline=(255, 218, 64, 235) if is_prayer else (255, 204, 52, 235),
        width=2,
    )
    d.text((cx - tw_tag / 2, ty0 + 8), tag, font=f_tag, fill=(255, 255, 255, 255))

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "JPEG", quality=93, optimize=True)
    return out_path

