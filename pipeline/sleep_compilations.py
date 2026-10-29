"""Multi-Hour Bedtime Sleep Compilation Engine.

Fast-tracks 4,000 Valid Public Watch Hours for the YouTube Partner Program (YPP)
by autonomously compiling 1-Hour, 3-Hour, and 8-Hour bedtime scripture sanctuaries
under the permanent $0.00 / month cost lock.

A single viewer sleeping through an 8-hour compilation logs 8 valid watch hours.
With procedural 432 Hz Solfeggio soundscapes, Delta binaural entrainment, and
DOCOGA REELS v2 glassmorphism visual sanctuary plates, this engine compiles
broadcast-quality sleep meditations with zero external paid assets or cloud rendering fees.
"""
from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .assemble import ffmpeg_bin
from .audio_smoother import smooth_audio_with_ffmpeg
from .config import CONFIG, QUEUE_DIR, REPO_ROOT
from .sleep_suite import (
    MOVEMENTS,
    SleepMovement,
    render_sanctuary_plate,
    render_sleep_thumbnail,
    synthesize_sleep_bed,
)
from .social_pack import build_standardized_description_footer


@dataclass(frozen=True)
class CompilationTier:
    tier_id: str
    target_hours: float
    title: str
    hook_kicker: str
    thumb_title: str
    thumb_subtitle: str
    description_hook: str
    default_job_id: str


COMPILATION_TIERS: dict[str, CompilationTier] = {
    "1hour": CompilationTier(
        tier_id="1hour",
        target_hours=1.0,
        title="1 HOUR OF PEACE: Psalms 91, 23 & 121 Night Prayer Before Sleep (432 Hz Solfeggio)",
        hook_kicker="1 HOUR SLEEP PRAYER",
        thumb_title="1 HOUR OF PEACE",
        thumb_subtitle="PSALM 91, 23 & 121",
        description_hook=(
            "Rest tonight in God's unbroken sanctuary of peace. This 1-hour bedtime prayer and "
            "scripture meditation covers Psalms 91, 23, and 121, set to soothing 432 Hz Solfeggio "
            "frequencies and Delta wave binaural rest to release stress and insomnia."
        ),
        default_job_id="0015",
    ),
    "3hour": CompilationTier(
        tier_id="3hour",
        target_hours=3.0,
        title="3 HOURS OF DEEP SLEEP: Continuous Night Prayers & Psalms of Protection (432 Hz Sanctuary)",
        hook_kicker="3 HOURS DEEP SLEEP",
        thumb_title="3 HOURS OF SLEEP",
        thumb_subtitle="PSALMS OF PROTECTION",
        description_hook=(
            "Allow God's Word to wash over your spirit as you sleep. 3 hours of continuous peaceful scripture, "
            "angelic protection prayers, and calming 432 Hz Solfeggio rain soundscapes designed to calm "
            "racing thoughts and induce deep restorative sleep."
        ),
        default_job_id="0016",
    ),
    "8hour": CompilationTier(
        tier_id="8hour",
        target_hours=8.0,
        title="8 HOURS ALL NIGHT PRAYER: Fall Asleep in God's Presence | Psalms 91, 23, 121, 27 (Sleep Peacefully)",
        hook_kicker="ALL NIGHT PROTECTION",
        thumb_title="8 HOURS OF PEACE",
        thumb_subtitle="PSALM 91, 23 & 121",
        description_hook=(
            "Play this throughout the entire night. 8 hours of continuous divine protection, calming biblical "
            "meditations, and sacred 432 Hz Delta sleep frequencies. Sleep soundly knowing the Lord neither slumbers nor sleeps."
        ),
        default_job_id="0017",
    ),
}


def calculate_compilation_chapters(
    target_seconds: float,
    movements: Sequence[SleepMovement] = MOVEMENTS,
) -> list[dict[str, Any]]:
    """Calculate exact timestamped chapters across the target duration."""
    total_weight = sum(m.relative_weight for m in movements)
    chapters = []
    current_time = 0.0

    # If long duration (e.g. 3h or 8h), cycle movements naturally
    cycle_count = max(1, math.ceil(target_seconds / 3600.0))
    cycle_target = target_seconds / cycle_count

    for c_idx in range(cycle_count):
        for m in movements:
            if current_time >= target_seconds:
                break
            dur = (m.relative_weight / total_weight) * cycle_target
            if current_time + dur > target_seconds:
                dur = target_seconds - current_time

            hours = int(current_time // 3600)
            mins = int((current_time % 3600) // 60)
            secs = int(current_time % 60)

            if hours > 0:
                ts = f"{hours:02d}:{mins:02d}:{secs:02d}"
            else:
                ts = f"{mins:02d}:{secs:02d}"

            cycle_label = f" (Part {c_idx + 1})" if cycle_count > 1 else ""
            chapters.append({
                "timestamp": ts,
                "seconds": round(current_time, 1),
                "duration": round(dur, 1),
                "scripture": m.scripture,
                "title": f"{m.scripture} — {m.title}{cycle_label}",
                "ambient": m.ambient_focus,
            })
            current_time += dur

    return chapters


COMPILATIONS_DIR = REPO_ROOT / "content" / "compilations"


def build_compilation_queue_manifest(
    tier_id: str = "1hour",
    job_id: str | None = None,
    out_dir: Path = COMPILATIONS_DIR,
) -> Path:
    """Generate an approved production compilation manifest for autonomous scheduling."""
    if tier_id not in COMPILATION_TIERS:
        raise ValueError(f"Unknown tier {tier_id!r}. Expected one of {list(COMPILATION_TIERS.keys())}")

    tier = COMPILATION_TIERS[tier_id]
    jid = job_id or tier.default_job_id
    total_seconds = tier.target_hours * 3600.0
    total_minutes = int(tier.target_hours * 60)

    chapters = calculate_compilation_chapters(total_seconds)
    chapters_str = "\n".join(f"    {c['timestamp']} {c['title']}" for c in chapters)

    raw_footer = build_standardized_description_footer()
    footer_indented = "\n".join(f"    {line}" if line else "" for line in raw_footer.splitlines())

    content = f"""---
id: "{jid}"
title: "{tier.title}"
slug: "sleep-compilation-{tier.tier_id}"
status: approved
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: {total_minutes}
tags:
  - psalm 91 sleep prayer
  - 8 hours of peace
  - bedtime scripture meditation
  - christian sleep meditation
  - 432 hz sleep music
  - fall asleep with bible verses
  - the secret place
  - prayers for peaceful sleep
  - deep sleep prayer
  - divine protection
thumb_text: "{tier.thumb_title}"
description: |
  {tier.description_hook}

  ⏱️ CHAPTERS & SLEEP TIMESTAMPS:
{chapters_str}

  🕊️ SACRED SLEEP ENGINEERING ($0.00 ZERO-COST IN-HOUSE DSP):
  • 432 Hz Solfeggio Harmonics: Eases emotional tension and nervous system fatigue.
  • Delta Wave Binaural Entrainment (1.5 Hz): Promotes restorative REM and slow-wave sleep.
  • Pure Procedural Acoustic Stream & Rain: Zero external sample licenses; 100% original synthesis.

{footer_indented}
---

## Movement I — Psalm 91 Divine Shelter
He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty.
I will say of the Lord, He is my refuge and my fortress: my God; in Him will I trust.

## Movement II — Psalm 23 Still Waters
The Lord is my shepherd; I shall not want.
He makes me to lie down in green pastures; He leads me beside the still waters.
He restores my soul.

## Movement III — Psalm 121 The Keeper of Israel
I will lift up mine eyes unto the hills, from whence cometh my help.
My help cometh from the Lord, which made heaven and earth.
He that keepeth thee will not slumber.

## Movement IV — The Benediction of Rest
The Lord bless you and keep you; the Lord make His face shine upon you and give you peace.
Sleep under His wings tonight. Amen.
"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug_path = out_dir / f"{jid}-sleep-compilation-{tier.tier_id}.md"
    slug_path.write_text(content.strip() + "\n", encoding="utf-8")
    return slug_path


def render_sleep_compilation_video(
    output_mp4: Path,
    duration_seconds: float = 30.0,
    tier_id: str = "1hour",
    preview: bool = False,
) -> Path:
    """Render high-efficiency sleep compilation MP4 with 432 Hz DSP audio and DOCOGA REELS v2 visuals."""
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    temp_raw_audio = output_mp4.parent / f"{output_mp4.stem}_raw_audio.wav"
    temp_smooth_audio = output_mp4.parent / f"{output_mp4.stem}_smooth_audio.wav"
    temp_plate = output_mp4.parent / f"{output_mp4.stem}_plate.png"

    try:
        # 1. Synthesize procedural 432 Hz audio bed
        synthesize_sleep_bed(
            duration_seconds=duration_seconds,
            out_path=temp_raw_audio,
        )

        # 2. Smooth audio via EBU R128 sleep mastering
        smooth_audio_with_ffmpeg(
            input_audio=temp_raw_audio,
            output_audio=temp_smooth_audio,
            target_lufs=-16.0,
        )

        # 3. Render DOCOGA REELS v2 sanctuary plate
        plate_img = render_sanctuary_plate(MOVEMENTS[0], verse_idx=0, width=1920, height=1080)
        plate_img.save(temp_plate)

        # 4. Assemble via FFmpeg
        ffmpeg = ffmpeg_bin()
        cmd = [
            ffmpeg,
            "-y",
            "-loop", "1",
            "-i", str(temp_plate),
            "-i", str(temp_smooth_audio),
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
            raise RuntimeError(f"FFmpeg compilation render failed: {proc.stderr[-800:]}")

        return output_mp4
    finally:
        for f in (temp_raw_audio, temp_smooth_audio, temp_plate):
            if f.exists():
                f.unlink(missing_ok=True)
