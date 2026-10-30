"""Unit tests for Sacred Sonic Branding & Watermark Engine."""
from __future__ import annotations

import wave
from pathlib import Path
import numpy as np

from pipeline.sonic_branding import inject_sonic_branding


def _create_dummy_wav(path: Path, duration_seconds: float = 1.0):
    sr = 44100
    t = np.linspace(0, duration_seconds, int(sr * duration_seconds), endpoint=False)
    sig = 0.4 * np.sin(2 * np.pi * 432.0 * t)
    int_sig = (sig * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_sig.tobytes())


def test_inject_sonic_branding(tmp_path: Path):
    """Verify injection of 528 Hz intro and 432 Hz outro sacred chimes."""
    in_wav = tmp_path / "voice_narration.wav"
    out_wav = tmp_path / "branded_narration.wav"

    _create_dummy_wav(in_wav, duration_seconds=1.0)
    res = inject_sonic_branding(in_wav, out_wav)

    assert res.is_file()
    # Total duration should be: 2.5s (intro) + 1.0s (main) + 3.5s (outro) = ~7.0s
    with wave.open(str(res), "rb") as wf:
        dur = float(wf.getnframes()) / float(wf.getframerate())
        assert 6.5 <= dur <= 7.5
