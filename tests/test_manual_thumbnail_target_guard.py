"""Manual thumbnail writes require a verified owner and a matching video."""
from unittest.mock import MagicMock

import pytest
import yaml

from pipeline.thumbnail_target_guard import verified_video_snippet


@pytest.fixture
def youtube():
    service = MagicMock()
    service.channels().list().execute.return_value = {'items': [{'id': 'owner'}]}
    service.videos().list().execute.return_value = {
        'items': [{'id': 'video', 'snippet': {'channelId': 'owner'}}],
    }
    service.reset_mock()
    return service


def test_verified_token_and_video(youtube):
    snippet = verified_video_snippet(youtube, 'video', 'owner')
    assert snippet['channelId'] == 'owner'
    youtube.channels().list.assert_called_once_with(part='id', mine=True)
    youtube.videos().list.assert_called_once_with(part='snippet', id='video')
    youtube.thumbnails.assert_not_called()


@pytest.mark.parametrize(('video_id', 'expected'), [('', 'owner'), ('video', ''), ('video', '  ')])
def test_missing_inputs_fail_before_network(youtube, video_id, expected):
    with pytest.raises(RuntimeError):
        verified_video_snippet(youtube, video_id, expected)
    youtube.channels.assert_not_called()
    youtube.videos.assert_not_called()


@pytest.mark.parametrize('channels', [[], [{'id': 'other'}], [{'id': 'owner'}, {'id': 'owner'}], [{}], None])
def test_wrong_or_ambiguous_token_identity_fails_before_video_lookup(youtube, channels):
    youtube.channels().list().execute.return_value = {'items': channels}
    youtube.reset_mock()
    with pytest.raises(RuntimeError):
        verified_video_snippet(youtube, 'video', 'owner')
    youtube.videos.assert_not_called()
    youtube.thumbnails.assert_not_called()


@pytest.mark.parametrize('videos', [[], [{'id': 'video', 'snippet': {'channelId': 'other'}}],
                                    [{'id': 'wrong', 'snippet': {'channelId': 'owner'}}],
                                    [{'id': 'video', 'snippet': {}}],
                                    [{'id': 'video'}, {'id': 'video'}]])
def test_wrong_missing_or_ambiguous_video_fails(youtube, videos):
    youtube.videos().list().execute.return_value = {'items': videos}
    youtube.reset_mock()
    with pytest.raises(RuntimeError):
        verified_video_snippet(youtube, 'video', 'owner')
    youtube.thumbnails.assert_not_called()


def test_workflow_checks_channel_and_video_before_live_write():
    with open('.github/workflows/set-thumbnail.yml', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    step = next(step for step in data['jobs']['thumbnail']['steps'] if step.get('name') == 'Set the live thumbnail')
    run = step['run']
    assert run.index('not in scheduled_channels()') < run.index('_credentials()')
    assert run.index("not os.environ.get('YOUTUBE_EXPECTED_CHANNEL_ID'") < run.index('_credentials()')
    assert run.index('verified_video_snippet(youtube,') < run.index('youtube.thumbnails().set(')
    assert '!inputs.dry_run' in step['if']
