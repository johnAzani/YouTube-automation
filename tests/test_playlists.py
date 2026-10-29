"""Unit tests for the Official Series Playlist Management Engine."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from pipeline.playlists import (
    OFFICIAL_PLAYLISTS,
    PlaylistSpec,
    add_video_to_playlist,
    collect_published_videos,
    ensure_playlist_exists,
    get_playlist_video_ids,
    sync_all_series_playlists,
)


def test_official_playlists_specs():
    """Verify that all 3 official channel series playlists are configured."""
    assert len(OFFICIAL_PLAYLISTS) == 3
    assert "night_prayers" in OFFICIAL_PLAYLISTS
    assert "bedtime_sleep" in OFFICIAL_PLAYLISTS
    assert "complete_psalms" in OFFICIAL_PLAYLISTS

    for key, spec in OFFICIAL_PLAYLISTS.items():
        assert len(spec.title) > 0
        assert len(spec.description) > 0
        assert spec.privacy_status == "public"
        assert len(spec.matching_keywords) > 0


def test_collect_published_videos():
    """Verify collecting published channel videos always includes live anchor video."""
    vids = collect_published_videos()
    assert len(vids) >= 1
    ids = [v["video_id"] for v in vids]
    assert "7RDX0fbIOtQ" in ids


def test_ensure_playlist_exists_dry_run():
    """Test playlist creation in dry run mode returns mock ID."""
    spec = OFFICIAL_PLAYLISTS["night_prayers"]
    pl_id = ensure_playlist_exists(None, spec, dry_run=True)
    assert pl_id == "mock_pl_night_prayers"


def test_add_video_to_playlist_dry_run():
    """Test idempotent video addition in dry run."""
    res = add_video_to_playlist(None, "pl_123", "vid_456", title="Test", dry_run=True)
    assert res is True


def test_add_video_to_playlist_mocked_idempotent():
    """Test that existing playlist video prevents duplicate insertion."""
    mock_youtube = MagicMock()
    # Mock playlistItems().list() to return vid_456 already present
    mock_list_req = MagicMock()
    mock_list_req.execute.return_value = {
        "items": [
            {
                "snippet": {
                    "resourceId": {"videoId": "vid_456"}
                }
            }
        ]
    }
    mock_youtube.playlistItems().list.return_value = mock_list_req

    # Should detect existing and skip insert
    success = add_video_to_playlist(mock_youtube, "pl_real", "vid_456")
    assert success is True
    # Verify insert was NOT called
    mock_youtube.playlistItems().insert.assert_not_called()


def test_sync_all_series_playlists_dry_run():
    """Test full playlist sync dry run."""
    report = sync_all_series_playlists(youtube=None, dry_run=True)
    assert report["playlists_synced"] == 3
    assert report["videos_assigned"] >= 3
    assert "night_prayers" in report["playlists"]
    assert "bedtime_sleep" in report["playlists"]
    assert "complete_psalms" in report["playlists"]
