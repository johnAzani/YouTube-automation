"""Empty target credentials cannot inherit another channel's credentials."""
import os
from unittest.mock import patch

import pytest
from pipeline.channels import apply_channel_env


@pytest.mark.parametrize('previous', ['', 'secret-place', 'prayer3'])
def test_switching_channels_clears_empty_target_secrets(previous):
    values = {
        'YOUTUBE_CLIENT_ID': 'wrong-id', 'YOUTUBE_CLIENT_SECRET': 'wrong-secret',
        'YOUTUBE_REFRESH_TOKEN': 'wrong-refresh', 'YOUTUBE_PLAYLIST_ID': 'wrong-playlist',
        'GEMINI_API_KEY': 'wrong-key',
        'PRAYER2_YOUTUBE_CLIENT_ID': '', 'PRAYER2_YOUTUBE_CLIENT_SECRET': '',
        'PRAYER2_YOUTUBE_REFRESH_TOKEN': '', 'PRAYER2_YOUTUBE_PLAYLIST_ID': '',
        'PRAYER2_GEMINI_API_KEY': '',
    }
    if previous:
        values['CHANNEL_ID'] = previous
    with patch.dict(os.environ, values, clear=True):
        assert apply_channel_env('prayer2') == 'prayer2'
        for key in ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN',
                    'YOUTUBE_PLAYLIST_ID', 'GEMINI_API_KEY'):
            assert key not in os.environ


def test_same_channel_preserves_already_mapped_workflow_values():
    with patch.dict(os.environ, {'CHANNEL_ID': 'prayer2', 'YOUTUBE_CLIENT_ID': 'mapped',
                                 'PRAYER2_YOUTUBE_CLIENT_ID': ''}, clear=True):
        apply_channel_env('prayer2')
        assert os.environ['YOUTUBE_CLIENT_ID'] == 'mapped'


def test_nonempty_target_secret_wins_when_switching():
    with patch.dict(os.environ, {'CHANNEL_ID': 'secret-place', 'YOUTUBE_REFRESH_TOKEN': 'old',
                                 'PRAYER2_YOUTUBE_REFRESH_TOKEN': 'new'}, clear=True):
        apply_channel_env('prayer2')
        assert os.environ['YOUTUBE_REFRESH_TOKEN'] == 'new'
