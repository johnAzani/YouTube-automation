"""Unit tests for Autonomous End-Screen Slate Generator."""
from __future__ import annotations

from pathlib import Path
from PIL import Image

from pipeline.end_screens import render_endscreen_plate


def test_render_endscreen_plate(tmp_path: Path):
    """Verify rendering of 1920x1080 End Screen Slate plate."""
    out_png = tmp_path / "test_endscreen_plate.png"
    im = render_endscreen_plate(
        next_video_title="PSALM 23 · THE LORD IS MY SHEPHERD",
        playlist_title="BEDTIME SCRIPTURE MEDITATIONS (432 Hz)",
        channel_name="THE SECRET PLACE",
        width=960,
        height=540,
        out_path=out_png,
    )
    assert isinstance(im, Image.Image)
    assert im.size == (960, 540)
    assert out_png.is_file()
    assert out_png.stat().st_size > 15000
