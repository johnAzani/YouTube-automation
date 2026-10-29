"""Unit tests for Procedural Sacred Audio Engine."""
from __future__ import annotations

import wave
from pathlib import Path
import numpy as np

from pipeline.sacred_audio import synthesize_sacred_chime


def test_synthesize_sacred_chime(tmp_path: Path):
    """Verify synthesis of 528 Hz sacred bell chime and WAV export."""
    out_wav = tmp_path / "test_chime.wav"
    left, right = synthesize_sacred_chime(
        fundamental_hz=528.0,
        duration_seconds=2.0,
        sample_rate=44100,
        out_path=out_wav,
    )

    assert len(left) == int(2.0 * 44100)
    assert len(right) == int(2.0 * 44100)
    assert np.all(np.abs(left) <= 1.0)
    assert np.all(np.abs(right) <= 1.0)
    assert float(np.abs(left).max()) > 0.1

    assert out_wav.is_file()
    with wave.open(str(out_wav), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getframerate() == 44100
        assert wf.getnframes() == int(2.0 * 44100)
