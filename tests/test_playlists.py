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


def test_channel_scoped_playlists_do_not_cross_contaminate():
    """Each channel gets its own branded playlists and never pulls Secret Place's anchor video."""
    from pipeline.playlists import playlists_for_channel

    p2_specs = playlists_for_channel("prayer2")
    p3_specs = playlists_for_channel("prayer3")
    assert set(p2_specs) == {"morning_prayers", "sunrise_guidance", "morning_psalms"}
    assert set(p3_specs) == {"midday_prayers", "afternoon_strength", "midday_psalms"}

    p2_vids = collect_published_videos(channel_id="prayer2")
    p3_vids = collect_published_videos(channel_id="prayer3")
    assert "7RDX0fbIOtQ" not in [v["video_id"] for v in p2_vids]
    assert "7RDX0fbIOtQ" not in [v["video_id"] for v in p3_vids]

    r3 = sync_all_series_playlists(youtube=None, dry_run=True, channel_id="prayer3")
    assert r3["channel"] == "prayer3"
    assert r3["playlists_synced"] == 3
    assert "midday_prayers" in r3["playlists"]


def test_series_playlists_exclude_shorts_across_all_three_channels():
    """Long-form Series Playlists never include vertical #Shorts on any channel."""
    from pipeline.playlists import collect_published_short_video_ids

    for cid in ("secret-place", "prayer2", "prayer3"):
        lf_vids = collect_published_videos(channel_id=cid)
        short_ids = collect_published_short_video_ids(channel_id=cid)
        assert len(lf_vids) >= 1
        assert len(short_ids) >= 1
        for v in lf_vids:
            assert v["video_id"] not in short_ids, f"{cid} Short {v['video_id']} leaked into longform playlist pool"
            assert "#shorts" not in v["title"].lower(), f"{cid} #Shorts title {v['title']!r} leaked into longform pool"


def test_sync_all_series_playlists_prunes_shorts_and_caches_api_calls(tmp_path):
    """Live sync caches playlists.list + playlistItems.list and deletes legacy #Shorts."""
    pub = tmp_path / "published"
    pub.mkdir()
    (pub / "0045-psalm-55-noon.md").write_text(
        "---\nid: '0045'\ntitle: 'Psalm 55:17 Midday Prayer | The Midday Watch'\n"
        "channel: prayer3\nstatus: published\nformat: longform\n"
        "tags: ['midday prayer', 'psalm']\nyoutube_video_id: 'lf_existing'\n---\n\n## Scene 1\nBody.\n",
        encoding="utf-8",
    )
    (pub / "0046-psalm-91-noon.md").write_text(
        "---\nid: '0046'\ntitle: 'Psalm 91:6 Noonday Prayer | The Midday Watch'\n"
        "channel: prayer3\nstatus: published\nformat: longform\n"
        "tags: ['midday prayer', 'psalm']\nyoutube_video_id: 'lf_new'\n---\n\n## Scene 1\nBody.\n",
        encoding="utf-8",
    )
    (pub / "short-midday-psalm55.md").write_text(
        "---\nid: 's1'\ntitle: 'Say This Psalm 55:17 Prayer at Noon | #Shorts'\n"
        "channel: prayer3\nstatus: published\nformat: short\n"
        "tags: ['midday prayer']\nyoutube_video_id: 'short_vid_1'\n---\n\nBody.\n",
        encoding="utf-8",
    )

    from pipeline.playlists import playlists_for_channel

    specs = playlists_for_channel("prayer3")
    mock_yt = MagicMock()
    mock_yt.playlists().list().execute.return_value = {
        "items": [
            {"id": f"pl_{k}", "snippet": {"title": s.title}}
            for k, s in specs.items()
        ]
    }
    mock_yt.playlistItems().list().execute.return_value = {
        "items": [
            {
                "id": "item_short_1",
                "snippet": {
                    "title": "Say This Psalm 55:17 Prayer at Noon | #Shorts",
                    "resourceId": {"videoId": "short_vid_1"},
                },
            },
            {
                "id": "item_lf_1",
                "snippet": {
                    "title": "Psalm 55:17 Midday Prayer | The Midday Watch",
                    "resourceId": {"videoId": "lf_existing"},
                },
            },
        ]
    }
    # Reset call counts accumulated while chaining return_value setup above
    mock_yt.playlists().list.reset_mock()
    mock_yt.playlistItems().list.reset_mock()

    report = sync_all_series_playlists(
        youtube=mock_yt,
        dry_run=False,
        channel_id="prayer3",
        published_dir=pub,
    )

    # Cached: 1 playlists.list call for the whole channel, 1 playlistItems.list per playlist (3 total)
    assert mock_yt.playlists().list.call_count == 1
    assert mock_yt.playlistItems().list.call_count == 3
    # Pruned the Short from all 3 playlists
    assert report["shorts_pruned"] == 3
    assert mock_yt.playlistItems().delete.call_count == 3
    # Inserted lf_new into matching playlists, skipped lf_existing, never inserted short_vid_1
    inserted_vids = [
        c.kwargs["body"]["snippet"]["resourceId"]["videoId"]
        for c in mock_yt.playlistItems().insert.call_args_list
    ]
    assert "short_vid_1" not in inserted_vids
    assert "lf_existing" not in inserted_vids
    assert set(inserted_vids) == {"lf_new"}


