"""Unit tests for Multi-Hour Bedtime Sleep Compilations Engine."""
from __future__ import annotations

from pathlib import Path
from pipeline.sleep_compilations import (
    COMPILATION_TIERS,
    build_compilation_queue_manifest,
    calculate_compilation_chapters,
    render_sleep_compilation_video,
)


def test_compilation_tiers():
    """Verify tier configuration (1hour, 3hour, 8hour)."""
    assert "1hour" in COMPILATION_TIERS
    assert "3hour" in COMPILATION_TIERS
    assert "8hour" in COMPILATION_TIERS

    assert COMPILATION_TIERS["1hour"].target_hours == 1.0
    assert COMPILATION_TIERS["3hour"].target_hours == 3.0
    assert COMPILATION_TIERS["8hour"].target_hours == 8.0


def test_calculate_compilation_chapters():
    """Verify chapter formatting and timestamps across durations."""
    # 1 hour
    ch_1h = calculate_compilation_chapters(3600.0)
    assert len(ch_1h) >= 4
    assert ch_1h[0]["timestamp"] == "00:00"
    assert "Psalm 91" in ch_1h[0]["title"]

    # 8 hours
    ch_8h = calculate_compilation_chapters(28800.0)
    assert len(ch_8h) >= 10
    assert any("Part" in c["title"] for c in ch_8h)


def test_build_compilation_queue_manifest(tmp_path: Path):
    """Verify queue job manifest generation with chapters and metadata."""
    manifest = build_compilation_queue_manifest(tier_id="1hour", job_id="TEST-0015", out_dir=tmp_path)
    assert manifest.is_file()
    text = manifest.read_text(encoding="utf-8")
    assert "id: \"TEST-0015\"" in text
    assert "1 HOUR OF PEACE" in text
    assert "CHAPTERS & SLEEP TIMESTAMPS" in text
    assert "The Secret Place" in text


def test_render_sleep_compilation_video_preview(tmp_path: Path):
    """Verify rendering of a fast preview clip."""
    out_mp4 = tmp_path / "test_compilation_preview.mp4"
    res = render_sleep_compilation_video(out_mp4, duration_seconds=1.0, tier_id="1hour", preview=True)
    assert res.is_file()
    assert res.stat().st_size > 1000
