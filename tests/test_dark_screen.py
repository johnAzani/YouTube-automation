"""Unit tests for Dark Bedroom Sanctuary & Black Screen Engine."""
from __future__ import annotations

import wave
from pathlib import Path
import numpy as np
from PIL import Image

from pipeline.dark_screen import (
    build_black_screen_metadata,
    render_dark_screen_sanctuary,
)


def _create_dummy_wav(path: Path, duration_seconds: float = 2.0):
    sr = 44100
    t = np.linspace(0, duration_seconds, int(sr * duration_seconds), endpoint=False)
    sig = 0.5 * np.sin(2 * np.pi * 432.0 * t)
    int_sig = (sig * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_sig.tobytes())


def _create_dummy_plate(path: Path):
    im = Image.new("RGB", (640, 360), (4, 12, 26))
    im.save(path)


def test_build_black_screen_metadata():
    """Verify black screen metadata generation."""
    meta = build_black_screen_metadata(scripture="Psalm 91", duration_hours=8.0)
    assert "BLACK SCREEN" in meta["title"]
    assert "black screen sleep prayer" in meta["tags"]
    assert "BLUE LIGHT" in meta["description"].upper() or "BLACK SCREEN" in meta["description"]
    assert meta["thumb_text"] == "BLACK SCREEN SLEEP"


def test_render_dark_screen_sanctuary(tmp_path: Path):
    """Verify rendering of a fast preview fade-to-black MP4."""
    wav_path = tmp_path / "audio.wav"
    plate_path = tmp_path / "plate.png"
    out_mp4 = tmp_path / "black_screen_preview.mp4"

    _create_dummy_wav(wav_path, duration_seconds=2.0)
    _create_dummy_plate(plate_path)

    res = render_dark_screen_sanctuary(
        output_mp4=out_mp4,
        audio_path=wav_path,
        plate_img_path=plate_path,
        duration_seconds=2.0,
        fade_start_sec=0.5,
        fade_duration_sec=0.5,
    )

    assert res.is_file()
    assert res.stat().st_size > 1000
