import urllib.parse

import pytest

from scripts import praise_garden_preflight as preflight

CHANNEL = 'UC' + 'A' * 22
SCOPE = 'https://www.googleapis.com/auth/youtube.upload'


def env():
    return {'PRAYER9_YOUTUBE_CLIENT_ID': 'client', 'PRAYER9_YOUTUBE_CLIENT_SECRET': 'secret',
            'PRAYER9_YOUTUBE_REFRESH_TOKEN': 'refresh', 'PRAYER9_YOUTUBE_CHANNEL_ID': CHANNEL}


def test_read_only_requests_and_identity():
    requests = []
    def fake(request):
        requests.append(request)
        if len(requests) == 1:
            return {'access_token': 'access', 'scope': SCOPE}
        return {'items': [{'id': CHANNEL}]}
    assert preflight.check(env(), fake) == {'identity': 'matched', 'upload_scope': 'present', 'channel': 'prayer9'}
    assert [r.get_method() for r in requests] == ['POST', 'GET']
    assert requests[0].full_url == 'https://oauth2.googleapis.com/token'
    assert urllib.parse.parse_qs(requests[0].data.decode())['refresh_token'] == ['refresh']
    assert requests[1].full_url == 'https://www.googleapis.com/youtube/v3/channels?part=id&mine=true'
    assert requests[1].get_header('Authorization') == 'Bearer access'


def test_no_fallback_to_other_channels_or_network_when_missing():
    calls = []
    with pytest.raises(preflight.PreflightError, match='PRAYER9_YOUTUBE_REFRESH_TOKEN'):
        preflight.check({'YOUTUBE_REFRESH_TOKEN': 'other-channel'}, lambda request: calls.append(request))
    assert not calls


@pytest.mark.parametrize('scope', ['', 'https://www.googleapis.com/auth/youtube.readonly'])
def test_missing_or_insufficient_scope_never_queries_channel(scope):
    calls = []
    def fake(request):
        calls.append(request)
        return {'access_token': 'access', 'scope': scope}
    with pytest.raises(preflight.PreflightError):
        preflight.check(env(), fake)
    assert len(calls) == 1


@pytest.mark.parametrize('items', [[], [{'id': 'UC' + 'B' * 22}], [{'id': CHANNEL}, {'id': CHANNEL}]])
def test_wrong_or_ambiguous_channel_fails(items):
    replies = iter([{'access_token': 'access', 'scope': SCOPE}, {'items': items}])
    with pytest.raises(preflight.PreflightError):
        preflight.check(env(), lambda request: next(replies))


def test_invalid_channel_id_refuses_before_request():
    config = env(); config['PRAYER9_YOUTUBE_CHANNEL_ID'] = 'fake'
    with pytest.raises(preflight.PreflightError, match='invalid format'):
        preflight.check(config, lambda request: pytest.fail('must not call network'))


def test_no_secret_values_in_normal_errors():
    config = env(); config['PRAYER9_YOUTUBE_CHANNEL_ID'] = 'secret'
    with pytest.raises(preflight.PreflightError) as exc:
        preflight.check(config)
    assert 'secret' not in str(exc.value) and 'refresh' not in str(exc.value)
