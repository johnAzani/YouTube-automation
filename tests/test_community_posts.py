"""Unit tests for YouTube Community Tab post and visual card generation."""
from __future__ import annotations

import json
from pathlib import Path
from PIL import Image

from pipeline.community_posts import (
    CANONICAL_COMMUNITY_SCHEDULE,
    CommunityPost,
    export_weekly_community_manifest,
    render_community_card,
)


def test_canonical_community_schedule():
    """Verify that community posts are configured with liturgical copy and options."""
    assert len(CANONICAL_COMMUNITY_SCHEDULE) >= 4
    for post in CANONICAL_COMMUNITY_SCHEDULE:
        assert len(post.post_id) > 0
        assert post.post_type in ["POLL", "PRAYER_WALL", "SCRIPTURE_DEVOTIONAL", "VIDEO_SPOTLIGHT"]
        assert len(post.title) > 0
        assert len(post.body_text) > 20
        if post.poll:
            assert len(post.poll.question) > 0
            assert len(post.poll.options) >= 3


def test_render_community_card(tmp_path: Path):
    """Verify rendering of 1080x1080 square DOCOGA REELS v2 glassmorphism card."""
    post = CANONICAL_COMMUNITY_SCHEDULE[0]
    out_png = tmp_path / "test_community_card.png"
    card = render_community_card(post, width=540, height=540, out_path=out_png)

    assert isinstance(card, Image.Image)
    assert card.size == (540, 540)
    assert out_png.is_file()
    assert out_png.stat().st_size > 10000


def test_export_weekly_community_manifest(tmp_path: Path):
    """Verify exporting full 7-day community schedule and cards."""
    files = export_weekly_community_manifest(out_dir=tmp_path)
    assert len(files) >= 8  # At least 4 JSONs + 4 PNGs

    json_files = [f for f in files if f.suffix == ".json"]
    png_files = [f for f in files if f.suffix == ".png"]
    assert len(json_files) >= 4
    assert len(png_files) >= 4

    # Check JSON validity
    first_json = json_files[0]
    data = json.loads(first_json.read_text(encoding="utf-8"))
    assert "post_id" in data
    assert "title" in data
    assert "body_text" in data
