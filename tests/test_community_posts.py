"""Unit tests for YouTube Community Tab post and visual card generation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from PIL import Image

import pipeline.community_posts as cp
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


class TestPublishIsHonest(unittest.TestCase):
    """The old code returned status "published" without touching the network, which is
    how a workflow that posted nothing looked healthy for weeks."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patcher = mock.patch.object(cp, "COMMUNITY_DIR", Path(self.tmp.name))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_never_claims_success(self):
        result = cp.publish_community_post(cp.select_today_community_post(), dry_run=True)
        self.assertNotEqual(result["status"], "published")
        self.assertEqual(result["status"], "ready_for_manual_post")
        self.assertIn("studio.youtube.com", result["composer"])

    def test_writes_a_ready_pack_with_the_body(self):
        post = cp.select_today_community_post()
        result = cp.publish_community_post(post, dry_run=True)
        pack = Path(result["ready_pack"])
        self.assertTrue(pack.is_file())
        text = pack.read_text(encoding="utf-8")
        self.assertIn("cannot create community posts", text.lower())
        self.assertIn(post.body_text.strip()[:40], text)

    def test_card_path_matches_what_the_manifest_writes(self):
        """card_comm_00N.png was never written by the manifest, so publish re-rendered a
        duplicate card instead of reusing the committed one."""
        cp.export_weekly_community_manifest(Path(self.tmp.name))
        for post in cp.CANONICAL_COMMUNITY_SCHEDULE:
            self.assertTrue((Path(self.tmp.name) / post.image_rel_path).is_file(), post.image_rel_path)


if __name__ == "__main__":
    unittest.main()
