"""Dark Bedroom Sanctuary & Fade-to-Black Video Engine.

Engineered specifically to solve the #1 cause of bedtime viewer abandonment:
bright smartphone, tablet, or TV screens illuminating a dark bedroom and waking sleepers.

Key Architecture:
  1. Opening Visual Sanctuary: Displays DOCOGA REELS v2 sapphire glassmorphic typography
     for the first 3 minutes (180s) so the viewer settles in and reads along.
  2. Gentle OLED Fade: Over 45 seconds, the visual display gently cross-fades into
     a pure pitch-black screen (RGB 0,0,0), saving battery and eliminating blue light.
  3. Continuous Sacred Audio: Procedural 432 Hz Solfeggio soundscapes and sacred prayer
     continue uninterrupted for the full 1, 3, or 8 hours.
  4. High-Intent Black Screen SEO: Formats metadata targeting massive search volume for
     'black screen sleep prayer', 'dark screen bible verses', and 'oled bedtime meditation'.
  5. 100% $0.00 Cost Lock: Pure FFmpeg video filter graph with zero cloud rendering fees.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .assemble import ffmpeg_bin
from .config import CONFIG, REPO_ROOT


def build_black_screen_metadata(
    scripture: str = "Psalm 91",
    theme: str = "Divine Protection",
    duration_hours: float = 8.0,
) -> dict[str, Any]:
    """Generate high-intent metadata optimized for YouTube Black Screen / Dark Mode searches."""
    dur_label = f"{int(duration_hours)} HOURS" if duration_hours >= 1.0 else f"{int(duration_hours * 60)} MINS"

    title = f"{scripture}: {theme} Before You Sleep | {dur_label} BLACK SCREEN (432 Hz Peace)"
    if len(title) > 95:
        title = f"{scripture}: {theme} | {dur_label} BLACK SCREEN (432 Hz)"

    description = (
        f"Rest peacefully in God's presence with this {dur_label.lower()} continuous scripture prayer.\n\n"
        f"🌙 BEDROOM SLEEP SANCTUARY (BLACK SCREEN MODE):\n"
        f"This video features an initial scripture visual plate that gently fades to a completely black screen "
        f"after 3 minutes. This eliminates blue light glare, protects your sleep cycle, and prevents your room "
        f"from being illuminated while you rest.\n\n"
        f"🎧 AUDIO RESTORATION:\n"
        f"• 432 Hz Sacred Solfeggio Harmonic Tuning\n"
        f"• Delta Wave 1.5 Hz Sleep Frequency\n"
        f"• Continuous unbroken nighttime scripture\n\n"
        f"Rest tonight under the shadow of the Almighty. He who keeps you neither slumbers nor sleeps."
    )

    tags = [
        f"{scripture.lower()} black screen",
        "black screen sleep prayer",
        "bible verses sleep dark screen",
        "sleep prayer black screen",
        "psalm 91 sleep prayer",
        "432 hz sleep music black screen",
        "oled sleep meditation",
        "peaceful bedtime prayer",
        "christian meditation black screen",
        "the secret place",
    ]

    return {
        "title": title[:95],
        "description": description,
        "tags": tags[:15],
        "thumb_text": "BLACK SCREEN SLEEP",
        "screen_mode": "dark_sanctuary_fade",
    }


def render_dark_screen_sanctuary(
    output_mp4: Path,
    audio_path: Path,
    plate_img_path: Path,
    duration_seconds: float = 30.0,
    fade_start_sec: float = 5.0,
    fade_duration_sec: float = 3.0,
) -> Path:
    """Render a video that starts with a visual plate and gently fades to black screen."""
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    audio_path = Path(audio_path)
    plate_img_path = Path(plate_img_path)

    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if not plate_img_path.is_file():
        raise FileNotFoundError(f"Plate image not found: {plate_img_path}")

    ffmpeg = ffmpeg_bin()

    # Safety clamp: fade start cannot exceed duration
    if fade_start_sec + fade_duration_sec > duration_seconds:
        fade_start_sec = max(0.5, duration_seconds * 0.4)
        fade_duration_sec = max(0.5, duration_seconds * 0.3)

    # Filter: loop image, fade to black at fade_start_sec over fade_duration_sec
    filter_graph = f"[0:v]fade=t=out:st={fade_start_sec:.2f}:d={fade_duration_sec:.2f}[v]"

    cmd = [
        ffmpeg,
        "-y",
        "-loop", "1",
        "-i", str(plate_img_path),
        "-i", str(audio_path),
        "-filter_complex", filter_graph,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-t", f"{duration_seconds:.2f}",
        str(output_mp4),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg dark screen render failed: {proc.stderr[-800:]}")

    return output_mp4
