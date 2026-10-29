"""Pillow-based text rendering (thumbnails, title cards).

Works everywhere: no ffmpeg drawtext filter or libass dependency — only a TTF
font, which we discover from common paths (DejaVu ships with Ubuntu runners).
ffmpeg is then only used for image→video plumbing.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from .config import CONFIG

FONT_CANDIDATES = [
    str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-Black.ttf"),
    str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-ExtraBold.ttf"),
    str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-Bold.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def find_font(bold: bool = True) -> str | None:
    candidates = FONT_CANDIDATES if bold else [c for c in FONT_CANDIDATES if "Bold" not in c] + FONT_CANDIDATES
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def render_text_plate(
    out_path: Path,
    title: str,
    subtitle: str = "",
    width: int | None = None,
    height: int | None = None,
    background: Path | None = None,
    bg_color: tuple[int, int, int] = (22, 33, 62),
    title_size: int = 64,
    accent: tuple[int, int, int] = (255, 210, 60),
) -> Path:
    """Composite title text over `background` (or a solid plate) and save JPEG/PNG."""
    from PIL import Image, ImageDraw, ImageFont

    width = width or CONFIG.width
    height = height or CONFIG.height

    if background and background.exists():
        try:
            img = Image.open(background).convert("RGB")
            # cover-fit
            scale = max(width / img.width, height / img.height)
            img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
            left = (img.width - width) // 2
            top = (img.height - height) // 2
            img = img.crop((left, top, left + width, top + height))
            # darken lower two-thirds for text legibility
            overlay = Image.new("RGB", (width, height), (0, 0, 0))
            mask = Image.new("L", (width, height), 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rectangle([0, int(height * 0.30), width, height], fill=200)
            img = Image.composite(overlay, img, mask)
        except Exception:
            img = Image.new("RGB", (width, height), bg_color)
    else:
        img = Image.new("RGB", (width, height), bg_color)

    draw = ImageDraw.Draw(img)
    font_path = find_font()
    try:
        font = ImageFont.truetype(font_path, title_size) if font_path else ImageFont.load_default()
        small = ImageFont.truetype(font_path, max(28, title_size // 2)) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
        small = font

    # wrapped title, bottom-left
    chars = max(12, width // (title_size // 2))
    lines = textwrap.wrap(title.upper(), width=chars)[:4]
    y = height - 70 - len(lines) * (title_size + 8)
    for line in lines:
        # soft shadow for readability on any background
        for dx, dy in ((-2, 2), (2, 2)):
            draw.text((60 + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((60, y), line, font=font, fill=(255, 255, 255))
        y += title_size + 8

    if subtitle:
        # crisp small text: light shadow only
        draw.text((62, 50), subtitle, font=small, fill=(0, 0, 0))
        draw.text((60, 48), subtitle, font=small, fill=(255, 255, 255))
        draw.rectangle([60, 48 + small.size + 12, 60 + 120, 48 + small.size + 18], fill=accent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path
