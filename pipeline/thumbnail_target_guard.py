"""Fail-closed checks before the manual live-thumbnail workflow changes a video."""
from __future__ import annotations


def verified_video_snippet(youtube, video_id: str, expected_channel_id: str) -> dict:
    """Read and verify both credential identity and video ownership; never write.

    A selected channel is not proof that its refresh token or video ID is right.
    Refuse missing, ambiguous, or mismatched API results before thumbnails.set.
    """
    expected = (expected_channel_id or '').strip()
    video_id = (video_id or '').strip()
    if not expected or not video_id:
        raise RuntimeError('Expected channel ID and video ID are required for a live thumbnail update.')
    response = youtube.channels().list(part='id', mine=True).execute()
    channels = response.get('items') if isinstance(response, dict) else None
    if (not isinstance(channels, list) or len(channels) != 1
            or not isinstance(channels[0], dict) or channels[0].get('id') != expected):
        raise RuntimeError('Authorized channel is missing, ambiguous, or does not match the expected channel ID.')
    response = youtube.videos().list(part='snippet', id=video_id).execute()
    videos = response.get('items') if isinstance(response, dict) else None
    if not isinstance(videos, list) or len(videos) != 1 or not isinstance(videos[0], dict):
        raise RuntimeError('Target video is missing or ambiguous.')
    video = videos[0]
    snippet = video.get('snippet')
    if (video.get('id') != video_id or not isinstance(snippet, dict)
            or snippet.get('channelId') != expected):
        raise RuntimeError('Target video does not belong to the expected channel.')
    return snippet
