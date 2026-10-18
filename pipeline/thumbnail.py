"""Draft thumbnail generator (1280x720).

The pipeline ships a *draft*: first-scene still + brand plate + big title text.
A human should always review/replace the thumbnail before publish — it is the
single highest-leverage CTR decision on the platform.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .assemble import _find_font, ffmpeg_bin  # reuse font discovery
from .config import CONFIG
from .script_doc import ScriptDoc


def generate_thumbnail(doc: ScriptDoc, background: Path | None, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{doc.slug}_thumb.jpg"
    fontfile = _find_font()
    font_opt = f":fontfile={fontfile}" if fontfile else ""

    text = doc.thumb_text.upper()[:64]
    # ffmpeg drawtext escaping: \ : '
    text = text.replace("\\", "").replace(":", r"\:").replace("'", r"'\''")

    overlay = (
        f"drawtext=text='{text}':fontcolor=white:fontsize=64:"
        f"x=60:y=h-220:line_spacing=10{font_opt}:"
        f"borderw=3:bordercolor=black@0.7,"
        f"drawtext=text='YouTube Automation Lab':fontcolor=white@0.85:fontsize=28:"
        f"x=60:y=48{font_opt}"
    )

    if background and background.exists():
        is_image = background.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        if is_image:
            cmd = [
                ffmpeg_bin(), "-y", "-loop", "1", "-t", "1", "-i", str(background),
                "-vf", f"scale={CONFIG.width}:{CONFIG.height}:force_original_aspect_ratio=increase,"
                       f"crop={CONFIG.width}:{CONFIG.height},{overlay}",
                "-frames:v", "1", "-q:v", "2", str(out),
            ]
        else:
            cmd = [
                ffmpeg_bin(), "-y", "-i", str(background), "-vf",
                f"scale={CONFIG.width}:{CONFIG.height}:force_original_aspect_ratio=increase,"
                f"crop={CONFIG.width}:{CONFIG.height},{overlay}",
                "-frames:v", "1", "-q:v", "2", str(out),
            ]
    else:
        cmd = [
            ffmpeg_bin(), "-y", "-f", "lavfi",
            "-i", f"color=c=0x16213e:s={CONFIG.width}x{CONFIG.height}:d=1",
            "-vf", overlay, "-frames:v", "1", "-q:v", "2", str(out),
        ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.exists():
        # Last resort: plain plate without text (never fail the build on art)
        subprocess.run([
            ffmpeg_bin(), "-y", "-f", "lavfi",
            "-i", f"color=c=0x16213e:s={CONFIG.width}x{CONFIG.height}:d=1",
            "-frames:v", "1", "-q:v", "2", str(out),
        ], check=True, capture_output=True)
    return out
