"""Unit tests for pastoral pinned comments and multi-language metadata localizations."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from pipeline.localize_metadata import LOCALIZATION_DICTIONARY, build_metadata_localizations
from pipeline.pinned_comments import generate_pastoral_pinned_comment, post_pastoral_pinned_comment
from pipeline.script_doc import ScriptDoc


def test_generate_pastoral_pinned_comment():
    """Verify pastoral pinned comments are context-aware, reverent, and omit personal names."""
    psalms = ["Psalm 91", "Psalm 23", "Psalm 121", "Psalm 27"]
    for p in psalms:
        doc = ScriptDoc(
            path=Path("/tmp/fake.md"),
            meta={"title": f"{p}: Night Prayer", "privacy": "public"},
            scenes=[],
        )
        comment = generate_pastoral_pinned_comment(doc)
        assert len(comment) > 50
        assert "AMEN" in comment
        assert "prayer request" in comment.lower()
        # Invariant: strictly avoid personal creator names
        assert "John Azani" not in comment
        assert "Azani" not in comment


def test_post_pastoral_pinned_comment_dry_run():
    """Verify dry-run mode returns mock comment ID without API call."""
    res = post_pastoral_pinned_comment(None, "vid_123", "Test comment", dry_run=True)
    assert res == "mock_comment_vid_123"


def test_post_pastoral_pinned_comment_mock():
    """Verify YouTube API call structure."""
    mock_youtube = MagicMock()
    mock_insert = MagicMock()
    mock_insert.execute.return_value = {"id": "comm_real_456"}
    mock_youtube.commentThreads().insert.return_value = mock_insert

    comm_id = post_pastoral_pinned_comment(mock_youtube, "vid_123", "Real comment text", dry_run=False)
    assert comm_id == "comm_real_456"
    mock_youtube.commentThreads().insert.assert_called_once()


def test_build_metadata_localizations():
    """Verify Spanish and Portuguese localizations generation for Psalm 91 and fallbacks."""
    locs = build_metadata_localizations(
        title="Psalm 91: The Complete Prayer of Divine Protection Before You Sleep",
        description="Full devotional prayer over Psalm 91.",
    )
    assert "es" in locs
    assert "pt" in locs
    assert "Salmo 91" in locs["es"]["title"]
    assert "Salmo 91" in locs["pt"]["title"]
    assert len(locs["es"]["description"]) > 50
    assert len(locs["pt"]["description"]) > 50


def test_build_metadata_localizations_fallback():
    """Verify fallback localizations for non-indexed titles."""
    locs = build_metadata_localizations(
        title="General Night Prayer for Peace",
        description="General evening prayer.",
    )
    assert "es" in locs
    assert "pt" in locs
    assert len(locs["es"]["title"]) > 0
    assert len(locs["pt"]["title"]) > 0
