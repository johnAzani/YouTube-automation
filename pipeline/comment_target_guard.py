"""Read-only, fail-closed verification of a live comment-reply target.

This helper is staged for integration; calling it alone does not reply, gate the
comment engine, or alter a channel. It checks the token owner, video owner and
parent comment relationship using API responses rather than trusting a caller's
CommentItem. Callers must separately gate inactive channel profiles.
"""
from __future__ import annotations

from pipeline.thumbnail_target_guard import verified_video_snippet


def verify_reply_target(youtube, expected_channel_id: str, video_id: str, comment_id: str) -> None:
    """Reject missing, foreign, mismatched or ambiguous owner/video/thread data."""
    expected = (expected_channel_id or '').strip()
    video = (video_id or '').strip()
    comment = (comment_id or '').strip()
    if not expected or not video or not comment:
        raise RuntimeError('Expected channel, video and parent comment IDs are required.')

    verified_video_snippet(youtube, video, expected)
    response = youtube.commentThreads().list(part='snippet', id=comment).execute()
    items = response.get('items') if isinstance(response, dict) else None
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise RuntimeError('Target comment thread is missing or ambiguous.')
    thread = items[0]
    snippet = thread.get('snippet')
    if not isinstance(snippet, dict):
        raise RuntimeError('Target comment thread has no valid snippet.')
    top = snippet.get('topLevelComment')
    if (thread.get('id') != comment or snippet.get('videoId') != video
            or not isinstance(top, dict) or top.get('id') != comment):
        raise RuntimeError('Target comment does not match the verified video and parent thread.')
