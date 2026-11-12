"""Read-only target guard: no foreign video or comment may pass as ours."""
from unittest.mock import MagicMock

import pytest

from pipeline.comment_target_guard import verify_reply_target


@pytest.fixture
def api():
    service = MagicMock()
    service.channels().list().execute.return_value = {'items': [{'id': 'owner'}]}
    service.videos().list().execute.return_value = {
        'items': [{'id': 'video', 'snippet': {'channelId': 'owner'}}]}
    service.commentThreads().list().execute.return_value = {
        'items': [{'id': 'comment', 'snippet': {'videoId': 'video', 'topLevelComment': {'id': 'comment'}}}]}
    service.reset_mock()
    return service


def test_validated_target_only_uses_read_endpoints(api):
    assert verify_reply_target(api, 'owner', 'video', 'comment') is None
    api.channels().list.assert_called_once_with(part='id', mine=True)
    api.videos().list.assert_called_once_with(part='snippet', id='video')
    api.commentThreads().list.assert_called_once_with(part='snippet', id='comment')
    api.comments.assert_not_called()


@pytest.mark.parametrize(('owner', 'video', 'comment'), [('', 'video', 'comment'),
    ('owner', '', 'comment'), ('owner', 'video', ''), ('  ', 'video', 'comment')])
def test_missing_target_fails_before_network(api, owner, video, comment):
    with pytest.raises(RuntimeError):
        verify_reply_target(api, owner, video, comment)
    api.channels.assert_not_called()
    api.videos.assert_not_called()
    api.commentThreads.assert_not_called()


@pytest.mark.parametrize('items', [[], [{'id': 'other'}], [{'id': 'owner'}, {'id': 'owner'}], None])
def test_wrong_or_ambiguous_identity_fails_before_video_and_thread(api, items):
    api.channels().list().execute.return_value = {'items': items}
    api.reset_mock()
    with pytest.raises(RuntimeError):
        verify_reply_target(api, 'owner', 'video', 'comment')
    api.videos.assert_not_called()
    api.commentThreads.assert_not_called()
    api.comments.assert_not_called()


@pytest.mark.parametrize('items', [[], [{'id': 'video', 'snippet': {'channelId': 'other'}}],
    [{'id': 'wrong', 'snippet': {'channelId': 'owner'}}], [{'id': 'video'}, {'id': 'video'}]])
def test_wrong_or_ambiguous_video_fails_before_thread(api, items):
    api.videos().list().execute.return_value = {'items': items}
    api.reset_mock()
    with pytest.raises(RuntimeError):
        verify_reply_target(api, 'owner', 'video', 'comment')
    api.commentThreads.assert_not_called()
    api.comments.assert_not_called()


@pytest.mark.parametrize('items', [[], None, [{}],
    [{'id': 'other', 'snippet': {'videoId': 'video', 'topLevelComment': {'id': 'comment'}}}],
    [{'id': 'comment', 'snippet': {'videoId': 'other', 'topLevelComment': {'id': 'comment'}}}],
    [{'id': 'comment', 'snippet': {'videoId': 'video', 'topLevelComment': {'id': 'other'}}}],
    [{'id': 'comment', 'snippet': {'videoId': 'video'}}],
    [{'id': 'comment'}, {'id': 'comment'}]])
def test_mismatched_missing_or_ambiguous_thread_fails(api, items):
    api.commentThreads().list().execute.return_value = {'items': items}
    api.reset_mock()
    with pytest.raises(RuntimeError):
        verify_reply_target(api, 'owner', 'video', 'comment')
    api.comments.assert_not_called()
