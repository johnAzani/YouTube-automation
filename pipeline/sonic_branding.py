"""Automated Sacred Sonic Branding & Watermark Engine.

Injects The Secret Place's signature acoustic brand watermarks into videos and
audio podcasts using pure NumPy procedural DSP synthesis under the $0.00 cost lock.

Signature Sonic Markers:
  1. Intro Sacred Chime (528 Hz 'Transformation & Peace'): A gentle 2.5s acoustic bell strike
     with natural harmonic decay that establishes immediate reverence and sanctuary feeling.
  2. Outro Benediction Chime (432 Hz 'Universal Rest'): A calming 4.0s harmonic resonance
     that smoothly guides the listener into nighttime rest.
  3. 100% Procedural Synthesis: Zero stock audio sample licenses; zero Content ID copyright claims.
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .assemble import ffmpeg_bin
from .config import CONFIG, REPO_ROOT
from .sacred_audio import synthesize_sacred_chime


def inject_sonic_branding(
    input_audio: Path,
    output_audio: Path,
    intro_chime_hz: float = 528.0,
    outro_chime_hz: float = 432.0,
) -> Path:
    """Prepend intro 528 Hz sacred chime and append outro 432 Hz peace chime."""
    input_audio = Path(input_audio)
    output_audio = Path(output_audio)
    output_audio.parent.mkdir(parents=True, exist_ok=True)

    temp_intro = output_audio.parent / f"{output_audio.stem}_intro_chime.wav"
    temp_outro = output_audio.parent / f"{output_audio.stem}_outro_chime.wav"

    try:
        # 1. Synthesize intro and outro procedural chimes
        synthesize_sacred_chime(
            fundamental_hz=intro_chime_hz,
            duration_seconds=2.5,
            sample_rate=44100,
            out_path=temp_intro,
        )
        synthesize_sacred_chime(
            fundamental_hz=outro_chime_hz,
            duration_seconds=3.5,
            sample_rate=44100,
            out_path=temp_outro,
        )

        # 2. Concat via FFmpeg audio filter
        ffmpeg = ffmpeg_bin()
        cmd = [
            ffmpeg,
            "-y",
            "-i", str(temp_intro),
            "-i", str(input_audio),
            "-i", str(temp_outro),
            "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[aout]",
            "-map", "[aout]",
            "-c:a", "pcm_s16le" if output_audio.suffix.lower() == ".wav" else "aac",
            "-b:a", "192k",
            str(output_audio),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg sonic branding concat failed: {proc.stderr[-800:]}")

        return output_audio
    finally:
        for f in (temp_intro, temp_outro):
            if f.exists():
                f.unlink(missing_ok=True)
