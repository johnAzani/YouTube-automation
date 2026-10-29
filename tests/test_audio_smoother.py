"""Unit tests for Bedtime Audio Smoothing & Dynamic Range Normalizer."""
from __future__ import annotations

import wave
from pathlib import Path
import numpy as np

from pipeline.audio_smoother import (
    TARGET_TRUE_PEAK_DB,
    inspect_audio_profile,
    smooth_audio_with_ffmpeg,
    smooth_audio_with_numpy,
)


def _create_dummy_wav(path: Path, duration_seconds: float = 1.0, freq: float = 432.0):
    sr = 44100
    t = np.linspace(0, duration_seconds, int(sr * duration_seconds), endpoint=False)
    # Loud burst with peak near 1.0
    sig = 0.95 * np.sin(2 * np.pi * freq * t)
    int_sig = (sig * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_sig.tobytes())


def test_smooth_audio_with_numpy(tmp_path: Path):
    """Verify numpy fallback limiter and loudness normalization."""
    in_wav = tmp_path / "raw.wav"
    out_wav = tmp_path / "smoothed.wav"
    _create_dummy_wav(in_wav, duration_seconds=1.0)

    res = smooth_audio_with_numpy(in_wav, out_wav, target_lufs=-16.0)
    assert res.is_file()

    prof = inspect_audio_profile(res)
    assert prof["channels"] == 1
    assert prof["sample_rate"] == 44100
    assert prof["duration_seconds"] == 1.0
    assert prof["peak_db"] <= TARGET_TRUE_PEAK_DB + 0.1


def test_smooth_audio_with_ffmpeg(tmp_path: Path):
    """Verify FFmpeg filter chain smoothing."""
    in_wav = tmp_path / "raw_ffmpeg.wav"
    out_wav = tmp_path / "smoothed_ffmpeg.wav"
    _create_dummy_wav(in_wav, duration_seconds=1.5)

    res = smooth_audio_with_ffmpeg(in_wav, out_wav, target_lufs=-16.0)
    assert res.is_file()

    prof = inspect_audio_profile(res)
    assert prof["duration_seconds"] >= 1.4
    assert prof["peak_db"] <= TARGET_TRUE_PEAK_DB + 0.5
