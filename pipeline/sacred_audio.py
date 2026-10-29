"""Procedural Sacred Audio Engine: Solfeggio Chimes & Sonic Branding.

Synthesizes sacred acoustic bell chimes and signature sonic watermarks
using pure vectorized NumPy DSP under the strict $0.00 / month cost lock.
Zero external audio samples, zero royalty claims, zero Content ID conflicts.

Frequencies:
  • 528 Hz: Solfeggio sacred frequency of peace, restoration, and clarity.
  • 432 Hz: Pythagorean natural acoustic harmonic resonance.
"""
from __future__ import annotations

import math
import os
import wave
from pathlib import Path
import numpy as np

SAMPLE_RATE = 44100
CHIME_DURATION = 3.5  # 3.5 seconds gentle natural decay


def synthesize_sacred_chime(
    fundamental_hz: float = 528.0,
    duration_seconds: float = CHIME_DURATION,
    sample_rate: int = SAMPLE_RATE,
    stereo_chorus: bool = True,
    out_path: Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesize a rich acoustic sacred bell chime with exponential decay."""
    n_samples = int(duration_seconds * sample_rate)
    t = np.arange(n_samples, dtype=np.float64) / sample_rate

    # Natural acoustic bell overtones (relative freq, relative amplitude, decay rate multiplier)
    overtones = [
        (1.00, 1.00, 1.0),   # Fundamental
        (2.00, 0.45, 1.2),   # Octave
        (2.76, 0.30, 1.5),   # Strike tone
        (3.00, 0.20, 1.8),   # Twelfth
        (4.15, 0.12, 2.2),   # High acoustic shimmer
        (5.42, 0.06, 2.8),   # Top sparkle
    ]

    left = np.zeros(n_samples, dtype=np.float64)
    right = np.zeros(n_samples, dtype=np.float64)

    # Fast 8ms attack envelope to prevent clicks
    attack_samples = int(0.008 * sample_rate)
    attack_env = np.ones(n_samples, dtype=np.float64)
    if attack_samples > 0:
        attack_env[:attack_samples] = np.linspace(0.0, 1.0, attack_samples) ** 1.5

    for ratio, amp, decay_rate in overtones:
        freq = fundamental_hz * ratio
        # Exponential natural decay envelope
        decay_env = np.exp(-t * (1.8 * decay_rate)) * attack_env

        if stereo_chorus:
            # Slight detune (+/- 0.4 Hz) for rich acoustic stereo width
            left += amp * np.sin(2 * np.pi * (freq - 0.4) * t) * decay_env
            right += amp * np.sin(2 * np.pi * (freq + 0.4) * t) * decay_env
        else:
            tone = amp * np.sin(2 * np.pi * freq * t) * decay_env
            left += tone
            right += tone

    # Normalize to -2.0 dB peak (0.79) to prevent clipping
    max_val = max(float(np.abs(left).max()), float(np.abs(right).max()))
    if max_val > 1e-6:
        left = (left / max_val) * 0.79
        right = (right / max_val) * 0.79

    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        stereo = np.stack([left, right], axis=1)
        stereo = np.clip(stereo, -1.0, 1.0)
        i16 = (stereo * 32767).astype("<i2").tobytes()
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(i16)

    return left, right
