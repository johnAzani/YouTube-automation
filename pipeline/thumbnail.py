"""Draft thumbnail generator (Pillow-based — see pipeline/textplates.py).

The pipeline ships *drafts*: brand plate + big title text over the first scene
still, plus A/B/C variants for YouTube Studio's Test & Compare (winner is
decided by watch-time share — docs/GROWTH.md §4.3). A human should always
review/replace before publish: the thumbnail is the highest-leverage CTR
decision on the platform.
"""
from __future__ import annotations

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


def _safe_plate(doc: ScriptDoc, background: Path | None, out: Path,
                title_size: int, bg_color: tuple[int, int, int], use_bg: bool) -> None:
    bg = background if (use_bg and background is not None) else None
    try:
        render_text_plate(
            out,
            title=doc.thumb_text,
            subtitle="Money, Explained",
            background=bg,
            bg_color=bg_color,
            title_size=title_size,
        )
    except Exception:
        try:
            render_text_plate(out, title=doc.thumb_text, subtitle="Money, Explained", bg_color=bg_color)
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

    tw, th = 1280, 720
    if bg_path is not None and bg_path.is_file():
        raw = Image.open(bg_path).convert("RGB")
        scale = max(tw / max(1, raw.width), th / max(1, raw.height))
        sw, sh = max(tw, int(round(raw.width * scale))), max(th, int(round(raw.height * scale)))
        base = raw.resize((sw, sh), Image.Resampling.LANCZOS)
        x0, y0 = (sw - tw) // 2, (sh - th) // 2
        base = base.crop((x0, y0, x0 + tw, y0 + th))
        base = ImageEnhance.Color(base).enhance(1.18)
        base = ImageEnhance.Contrast(base).enhance(1.12)
    else:
        base = Image.new("RGB", (tw, th), (12, 24, 52))

    # Focused center contrast glow so giant type pops at 16:1 contrast while keeping background vivid
    scrim = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    sd.ellipse([410, 120, 870, 650], fill=(4, 10, 24, 158))
    sd.ellipse([455, 210, 825, 590], fill=(255, 42, 56, 44))
    scrim = scrim.filter(ImageFilter.GaussianBlur(42))
    canvas = Image.alpha_composite(base.convert("RGBA"), scrim)

    overlay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx = tw // 2

    # 1. Top glowing crimson kicker badge inside 9:16 center safe width (<= 368px)
    kw = d.textlength(kicker, font=f_kick)
    bpw, bph = int(kw + 44), 42
    bx0, by0 = cx - bpw // 2, 188
    d.rounded_rectangle([bx0, by0 + 4, bx0 + bpw, by0 + bph + 4], radius=10, fill=(0, 0, 0, 150))
    d.rounded_rectangle(
        [bx0, by0, bx0 + bpw, by0 + bph],
        radius=10,
        fill=(228, 34, 46, 248),
        outline=(255, 220, 220, 210),
        width=2,
    )
    d.text((cx - kw / 2, by0 + 8), kicker, font=f_kick, fill=(255, 255, 255, 255))

    # 2. Giant "$70B" headline (fits strictly inside 376px center 9:16 width)
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

    # 3. Bottom high-contrast gold-bordered punchline pill inside 9:16 safe column
    tw_tag = d.textlength(tag, font=f_tag)
    tpw, tph = int(tw_tag + 46), 40
    tx0, ty0 = cx - tpw // 2, 488
    d.rounded_rectangle(
        [tx0, ty0, tx0 + tpw, ty0 + tph],
        radius=10,
        fill=(8, 20, 44, 235),
        outline=(255, 204, 52, 235),
        width=2,
    )
    d.text((cx - tw_tag / 2, ty0 + 8), tag, font=f_tag, fill=(255, 255, 255, 255))

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, "JPEG", quality=93, optimize=True)
    return out_path

