"""The read-only permission probe in the credential audit.

It runs against all ten channels' real credentials inside a public repository,
so the things held fixed here are: it only reads, it prints no secret and no
message text from Google, it cannot fail the job, and the copy inside the
workflow is the file in scripts/ word for word.
"""
import io
import json
import re
import urllib.error
from pathlib import Path

import pytest
import yaml

from scripts import permission_probe as probe
from scripts.youtube_oauth import FULL_SCOPES, scopes_for

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github/workflows/channel-credential-audit.yml'
AUTH = 'https://www.googleapis.com/auth/'


def _steps():
    return yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))['jobs']['audit']['steps']


def test_the_workflow_runs_this_file_word_for_word():
    step = next(s for s in _steps() if s['name'].startswith('Permission probe'))
    body = step['run'].split("<<'PROBE'\n", 1)[1].rsplit('PROBE', 1)[0]
    assert body.rstrip('\n') == (ROOT / 'scripts/permission_probe.py').read_text(encoding='utf-8').rstrip('\n')
    assert step['if'] == 'always()'


def test_the_probe_step_gets_only_what_it_needs_and_the_job_stays_permissionless():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
    assert workflow['permissions'] == {}
    step = next(s for s in _steps() if s['name'].startswith('Permission probe'))
    assert set(step['env']) == {'CHANNEL', 'CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN',
                                'HAS_PEXELS', 'HAS_PIXABAY', 'HAS_PLAYLIST'}
    for name in ('HAS_PEXELS', 'HAS_PIXABAY', 'HAS_PLAYLIST'):       # true/false, never the key itself
        assert step['env'][name].rstrip(' }').endswith("!= ''")
    assert 'uses' not in ''.join(str(s.keys()) for s in _steps())     # no checkout, no third-party action


def test_it_only_reads():
    source = (ROOT / 'scripts/permission_probe.py').read_text(encoding='utf-8')
    assert source.count('data=') == 1 and "'grant_type': 'refresh_token'" in source   # the token refresh
    assert 'method=' not in source
    for word in ('videos.insert', 'thumbnails.set', '/upload/', 'jobs.create', '/revoke'):
        assert word not in source


def test_scope_names_are_shortened_and_sorted():
    field = AUTH + 'youtube.upload ' + AUTH + 'youtube.force-ssl ' + AUTH + 'yt-analytics.readonly'
    assert probe.short_scopes(field) == ['youtube.force-ssl', 'youtube.upload', 'yt-analytics.readonly']
    assert probe.short_scopes(None) == [] and probe.short_scopes('') == []


@pytest.mark.parametrize('have, missing', [
    (['youtube.force-ssl', 'youtube.readonly', 'youtube.upload'],
     ['yt-analytics.readonly', 'yt-analytics-monetary.readonly']),
    (['youtube', 'youtube.force-ssl', 'youtube.upload'],
     ['yt-analytics.readonly', 'yt-analytics-monetary.readonly']),
    (['youtube.force-ssl', 'yt-analytics-monetary.readonly'], []),
    (['youtube.upload'], ['youtube', 'youtube.force-ssl', 'youtube.readonly',
                          'yt-analytics.readonly', 'yt-analytics-monetary.readonly']),
    ([s for s in FULL_SCOPES], []),
])
def test_missing_scopes_counts_a_broad_scope_as_covering_the_narrow_ones(have, missing):
    assert probe.missing_scopes(have) == missing


def test_one_full_token_carries_every_scope_a_channel_can_grant():
    full = scopes_for('full')
    assert full == [AUTH + s for s in FULL_SCOPES]
    assert probe.missing_scopes(probe.short_scopes(' '.join(full))) == []
    for scope in scopes_for('upload') + scopes_for('analytics-revenue'):
        assert scope in full
    assert not [s for s in full if 'youtubepartner' in s]     # Content Manager only; a channel cannot grant it


def test_a_refusal_is_reported_by_code_only_never_by_message_text():
    body = json.dumps({'error': {'code': 403, 'status': 'PERMISSION_DENIED',
                                 'message': 'YouTube Analytics API has not been used in project 123456789012 before',
                                 'errors': [{'reason': 'accessNotConfigured', 'message': 'project 123456789012'}],
                                 'details': [{'reason': 'SERVICE_DISABLED', 'metadata': {'consumer': 'projects/123456789012'}}]}})
    text = probe.refusal(403, body.encode())
    assert text == '403 PERMISSION_DENIED accessNotConfigured SERVICE_DISABLED'
    assert '123456789012' not in text
    assert probe.refusal(400, b'{"error":"invalid_grant","error_description":"Token has been expired or revoked."}') \
        == '400 invalid_grant'
    assert probe.refusal(500, b'<html>not json</html>') == '500'
    assert probe.refusal(403, json.dumps({'error': {'status': 'X::warning::y\n z'}}).encode()) == '403 Xwarningyz'


def test_a_token_with_an_end_date_is_called_out():
    assert probe.token_lifetime({'refresh_token_expires_in': 604799}) == 'ENDS in 7.0 days'
    assert probe.token_lifetime({}) == 'no end date reported'


def test_the_project_fingerprint_groups_without_showing_the_project_number():
    a = probe.project_group('123456789012-abcdef.apps.googleusercontent.com')
    assert a == probe.project_group('123456789012-zzzzzz.apps.googleusercontent.com')
    assert a != probe.project_group('999999999999-abcdef.apps.googleusercontent.com')
    assert re.fullmatch(r'[0-9a-f]{6}', a) and probe.project_group('') == 'none'


class _Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_google(calls, analytics_enabled=False):
    def urlopen(request, timeout=0):
        url = request.full_url
        calls.append((request.get_method(), url))
        if url.endswith('/token'):
            return _Answer(json.dumps({'access_token': 'ACCESS-SECRET', 'scope':
                                       AUTH + 'youtube.upload ' + AUTH + 'youtube.force-ssl'}).encode())
        if 'youtubeanalytics' in url and not analytics_enabled:
            raise urllib.error.HTTPError(url, 403, 'Forbidden', {}, io.BytesIO(json.dumps(
                {'error': {'status': 'PERMISSION_DENIED', 'message': 'private wording',
                           'errors': [{'reason': 'accessNotConfigured'}]}}).encode()))
        if 'channels?' in url:
            return _Answer(json.dumps({'items': [{
                'status': {'longUploadsStatus': 'allowed'},
                'brandingSettings': {'channel': {'country': 'NG', 'keywords': 'private keywords'}},
                'contentDetails': {'relatedPlaylists': {'uploads': 'UUprivate'}}}]}).encode())
        if 'playlistItems?' in url:
            return _Answer(json.dumps({'items': [{'contentDetails': {'videoId': 'vidPRIVATE'}}]}).encode())
        return _Answer(json.dumps({'items': [{}, {}], 'reportTypes': [{'id': 'channel_reach_basic_a1'}],
                                   'jobs': [], 'rows': [[987654]]}).encode())
    return urlopen


def test_a_whole_run_reads_reports_and_gives_nothing_away(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(probe.urllib.request, 'urlopen', _fake_google(calls))
    for name, value in (('CHANNEL', 'prayer3'), ('CLIENT_ID', '123456789012-abc.apps.googleusercontent.com'),
                        ('CLIENT_SECRET', 'CLIENT-SECRET'), ('REFRESH_TOKEN', 'REFRESH-SECRET'),
                        ('HAS_PEXELS', 'false'), ('HAS_PIXABAY', 'true'), ('HAS_PLAYLIST', 'false')):
        monkeypatch.setenv(name, value)
    assert probe.main() == 0
    out = capsys.readouterr().out
    assert [method for method, url in calls if not url.endswith('/token')] and \
        all(method == 'GET' for method, url in calls if not url.endswith('/token'))
    assert sum(1 for _m, url in calls if url.endswith('/token')) == 1
    lines = out.strip().splitlines()
    assert len(lines) == 5 and all(line.startswith('::notice title=Permissions prayer3: ') for line in lines)
    assert 'scopes=[youtube.force-ssl, youtube.upload]' in lines[0]
    assert 'missing=[yt-analytics.readonly, yt-analytics-monetary.readonly]' in lines[0]
    assert 'videos over 15 min=allowed' in lines[1] and 'country=NG' in lines[1]
    assert 'views: REFUSED 403 PERMISSION_DENIED accessNotConfigured' in lines[2]
    assert 'reach report offered' in lines[3] and 'pexels=false' in lines[4]
    for secret in ('ACCESS-SECRET', 'CLIENT-SECRET', 'REFRESH-SECRET', '123456789012', 'private wording',
                   'private keywords', 'UUprivate', 'vidPRIVATE', '987654'):
        assert secret not in out


def test_a_dead_token_is_reported_and_the_job_still_passes(monkeypatch, capsys):
    def urlopen(request, timeout=0):
        raise urllib.error.HTTPError(request.full_url, 400, 'Bad Request', {}, io.BytesIO(
            b'{"error":"invalid_grant","error_description":"Token has been expired or revoked."}'))
    monkeypatch.setattr(probe.urllib.request, 'urlopen', urlopen)
    monkeypatch.setenv('CHANNEL', 'prayer4')
    assert probe.main() == 0
    assert capsys.readouterr().out.strip() == '::notice title=Permissions prayer4: token::refresh REFUSED 400 invalid_grant'
