"""Draft thumbnail generator (Pillow-based — see pipeline/textplates.py).

The pipeline ships a *draft*: brand plate + big title text over the first scene
still. A human should always review/replace the thumbnail before publish — it
is the single highest-leverage CTR decision on the platform.
"""
from __future__ import annotations

from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc
from .textplates import render_text_plate


def generate_thumbnail(doc: ScriptDoc, background: Path | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{doc.slug}_thumb.jpg"
    # Never composite over our own generated title cards (double text); only real media.
    if background is not None and background.name.startswith("card_"):
        background = None
    try:
        render_text_plate(
            out,
            title=doc.thumb_text,
            subtitle="YouTube Automation Lab",
            background=background,
            title_size=64,
        )
    except Exception:
        # Never fail the build on art — solid plate with text, then bare plate.
        try:
            render_text_plate(out, title=doc.thumb_text, subtitle="YouTube Automation Lab")
        except Exception:
            from PIL import Image

            Image.new("RGB", (CONFIG.width, CONFIG.height), (22, 33, 62)).save(out, quality=92)
    return out
