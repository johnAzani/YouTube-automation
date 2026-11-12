import urllib.parse
from pathlib import Path

import pytest
import yaml

from scripts import guided_path_preflight as preflight
from scripts.praise_garden_preflight import PreflightError

CHANNEL = 'UC' + 'A' * 22
SCOPE = 'https://www.googleapis.com/auth/youtube.upload'


def env():
    return {'PRAYER10_YOUTUBE_CLIENT_ID': 'client10', 'PRAYER10_YOUTUBE_CLIENT_SECRET': 'secret10',
            'PRAYER10_YOUTUBE_REFRESH_TOKEN': 'refresh10', 'PRAYER10_YOUTUBE_CHANNEL_ID': CHANNEL}


def test_read_only_identity_and_scope_with_isolated_credentials():
    config = env()
    config.update({'PRAYER9_YOUTUBE_CLIENT_ID': 'other', 'YOUTUBE_REFRESH_TOKEN': 'other'})
    requests = []
    def fake(request):
        requests.append(request)
        return ({'access_token': 'access', 'scope': SCOPE} if len(requests) == 1
                else {'items': [{'id': CHANNEL}]})
    assert preflight.check(config, fake) == {'identity': 'matched', 'upload_scope': 'present', 'channel': 'prayer10'}
    assert [r.get_method() for r in requests] == ['POST', 'GET']
    assert requests[0].full_url == 'https://oauth2.googleapis.com/token'
    data = urllib.parse.parse_qs(requests[0].data.decode())
    assert data['client_id'] == ['client10'] and data['refresh_token'] == ['refresh10']
    assert requests[1].full_url == 'https://www.googleapis.com/youtube/v3/channels?part=id&mine=true'


def test_missing_channel10_credentials_never_fall_back_or_contact_network():
    config = env(); del config['PRAYER10_YOUTUBE_REFRESH_TOKEN']
    config['PRAYER9_YOUTUBE_REFRESH_TOKEN'] = 'other'
    config['YOUTUBE_REFRESH_TOKEN'] = 'other'
    with pytest.raises(PreflightError, match='PRAYER10_YOUTUBE_REFRESH_TOKEN'):
        preflight.check(config, lambda request: pytest.fail('must not call network'))


@pytest.mark.parametrize('scope', ['', 'https://www.googleapis.com/auth/youtube.readonly'])
def test_missing_upload_scope_fails_before_channel_request(scope):
    requests = []
    def fake(req):
        requests.append(req)
        return {'access_token': 'access', 'scope': scope}
    with pytest.raises(PreflightError):
        preflight.check(env(), fake)
    assert len(requests) == 1


@pytest.mark.parametrize('items', [[], [{'id': 'UC' + 'B' * 22}], [{'id': CHANNEL}, {'id': CHANNEL}]])
def test_wrong_or_ambiguous_identity_fails(items):
    replies = iter([{'access_token': 'access', 'scope': SCOPE}, {'items': items}])
    with pytest.raises(PreflightError):
        preflight.check(env(), lambda request: next(replies))


def test_workflow_manual_read_only_and_isolated():
    workflow = yaml.safe_load(Path('.github/workflows/guided-path-preflight.yml').read_text())
    assert set(workflow.get('on', workflow.get(True))) == {'workflow_dispatch'}
    assert workflow['permissions'] == {'contents': 'read'}
    steps = workflow['jobs']['preflight']['steps']
    assert steps[0]['with']['persist-credentials'] is False
    step = next(step for step in steps if 'run' in step)
    assert step['run'] == 'python3 scripts/guided_path_preflight.py'
    assert set(step['env']) == {'PRAYER10_' + name for name in preflight.shared.REQUIRED}
    for key, value in step['env'].items():
        assert value == '${{ secrets.' + key + ' }}'
