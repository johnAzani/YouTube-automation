"""Unit tests for the Multi-Hour Bedtime Sleep Sanctuary Engine."""
from __future__ import annotations

import os
import wave
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from pipeline.sleep_suite import (
    MOVEMENTS,
    SleepMovement,
    SleepVerse,
    build_sleep_suite_manifest,
    generate_chapter_timestamps,
    render_sanctuary_plate,
    render_sleep_thumbnail,
    synthesize_sleep_bed,
)


def test_movements_biblical_integrity():
    """Verify that all 5 canonical liturgical movements are defined with verses and keywords."""
    assert len(MOVEMENTS) >= 5
    psalms = [m.scripture for m in MOVEMENTS]
    assert "Psalm 91" in psalms
    assert "Psalm 23" in psalms
    assert "Psalm 121" in psalms
    assert "Psalm 27" in psalms

    for m in MOVEMENTS:
        assert m.movement_num >= 1
        assert len(m.title) > 0
        assert len(m.verses) > 0
        for v in m.verses:
            assert len(v.text) > 10
            assert len(v.verse_ref) > 0


def test_synthesize_sleep_bed_dsp(tmp_path: Path):
    """Test pure numpy DSP audio synthesis, binaural entrainment, and WAV export."""
    dur = 2.0  # 2 seconds test
    wav_out = tmp_path / "test_sleep_bed.wav"

    left, right = synthesize_sleep_bed(
        duration_seconds=dur,
        solfeggio_freq=432.0,
        binaural_hz=1.5,
        sample_rate=44100,
        out_path=wav_out,
    )

    # Check numpy array properties
    assert len(left) == int(dur * 44100)
    assert len(right) == int(dur * 44100)
    assert np.all(np.abs(left) <= 1.0)
    assert np.all(np.abs(right) <= 1.0)
    assert float(np.abs(left).max()) > 0.1  # Not silent

    # Check WAV file integrity
    assert wav_out.is_file()
    with wave.open(str(wav_out), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 44100
        frames = wf.getnframes()
        assert frames == int(dur * 44100)


def test_render_sanctuary_plate():
    """Test rendering of the 16:9 DOCOGA REELS v2 widescreen glassmorphic sanctuary plate."""
    m = MOVEMENTS[0]
    plate = render_sanctuary_plate(m, verse_idx=0, width=960, height=540)
    assert isinstance(plate, Image.Image)
    assert plate.size == (960, 540)
    assert plate.mode == "RGB"


def test_render_sleep_thumbnail(tmp_path: Path):
    """Test generating 1280x720 high-CTR bedroom sleep thumbnail."""
    thumb_path = tmp_path / "test_sleep_thumb.jpg"
    im = render_sleep_thumbnail(
        hook_title="8 HOURS OF PEACE",
        scripture_subtitle="PSALM 91, 23 & 121",
        sub_badge="432 Hz SLEEP FREQUENCY · UNDER HIS WINGS",
        width=1280,
        height=720,
        out_path=thumb_path,
    )
    assert im.size == (1280, 720)
    assert thumb_path.is_file()
    assert thumb_path.stat().st_size > 10000


def test_generate_chapter_timestamps():
    """Verify chapter calculation and formatting."""
    total_sec = 3600.0  # 1 hour
    chapters = generate_chapter_timestamps(MOVEMENTS, total_sec)

    assert len(chapters) == len(MOVEMENTS)
    assert chapters[0]["timestamp"] == "00:00"
    assert chapters[0]["seconds"] == 0.0

    # Ensure cumulative duration equals total_sec (within float tolerance)
    sum_dur = sum(c["duration"] for c in chapters)
    assert pytest.approx(sum_dur, rel=1e-2) == total_sec


def test_build_sleep_suite_manifest(tmp_path: Path):
    """Verify queue markdown manifest generation."""
    manifest_path = build_sleep_suite_manifest(
        job_id="0012",
        target_hours=1.0,
        out_dir=tmp_path,
    )
    assert manifest_path.is_file()
    text = manifest_path.read_text(encoding="utf-8")
    assert 'id: "0012"' in text
    assert "status: approved" in text
    assert "psalm-sleep-sanctuary-60min" in text
    assert "432 Hz" in text
    assert "Movement 1 — Psalm 91" in text
    assert "Movement 2 — Psalm 23" in text
