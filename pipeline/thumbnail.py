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
