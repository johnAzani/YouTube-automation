"""Starting YouTube's daily "reach" report, once per channel.

Held fixed: the only thing ever created is a reporting job, never a second one for
the same report, never for a channel that has not been granted; nothing is deleted;
no secret and no figure is printed; a channel that is not ready does not fail the run.
"""
import io
import json
import urllib.error
from pathlib import Path

import pytest
import yaml

from scripts import reporting_jobs as rj

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github/workflows/reporting-jobs.yml'
REACH = 'channel_reach_basic_a1'


class _Answer(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _refuse(url, code, body):
    return urllib.error.HTTPError(url, code, 'refused', {}, io.BytesIO(json.dumps(body).encode()))


def _google(calls, *, jobs=(), offered=(REACH, 'channel_basic_a3'), types_error=None, reports=()):
    def urlopen(request, timeout=0):
        url, method = request.full_url, request.get_method()
        calls.append((method, url, request.data))
        if url.endswith('/token'):
            return _Answer(json.dumps({'access_token': 'ACCESS-SECRET'}).encode())
        if 'reportTypes' in url:
            if types_error:
                raise _refuse(url, 403, types_error)
            return _Answer(json.dumps({'reportTypes': [{'id': i} for i in offered]}).encode())
        if url.endswith('/jobs') and method == 'POST':
            return _Answer(json.dumps({'id': 'job-NEW', 'reportTypeId': json.loads(request.data)['reportTypeId'],
                                       'createTime': '2026-11-14T16:40:02Z'}).encode())
        if url.endswith('/jobs'):
            return _Answer(json.dumps({'jobs': list(jobs)}).encode())
        if '/reports' in url:
            return _Answer(json.dumps({'reports': list(reports)}).encode())
        raise AssertionError('unexpected request ' + url)
    return urlopen


@pytest.fixture
def run(monkeypatch, capsys):
    def _run(argv=(), **kw):
        calls = []
        monkeypatch.setattr(rj.urllib.request, 'urlopen', _google(calls, **kw))
        monkeypatch.setattr(rj.probe.urllib.request, 'urlopen', _google(calls, **kw))
        for name, value in (('CHANNEL', 'secret-place'), ('CLIENT_ID', '123456789012-abc'),
                            ('CLIENT_SECRET', 'CLIENT-SECRET'), ('REFRESH_TOKEN', 'REFRESH-SECRET')):
            monkeypatch.setenv(name, value)
        code = rj.main(list(argv))
        return code, calls, capsys.readouterr().out
    return _run


def _posts(calls):
    return [c for c in calls if c[0] == 'POST' and not c[1].endswith('/token')]


def test_a_granted_channel_with_no_job_gets_exactly_one(run):
    code, calls, out = run()
    assert code == 0
    posts = _posts(calls)
    assert len(posts) == 1 and posts[0][1].endswith('/v1/jobs')
    assert json.loads(posts[0][2]) == {'reportTypeId': REACH, 'name': rj.WANTED[REACH]}
    assert out.strip() == ('::notice title=Reporting jobs secret-place::STARTED channel_reach_basic_a1 '
                           'on 2026-11-14; first daily file within 48 hours')


def test_a_report_that_already_has_a_job_is_never_given_a_second(run):
    code, calls, out = run(jobs=[{'id': 'job-1', 'reportTypeId': REACH, 'createTime': '2026-11-14T16:40:02Z'}],
                           reports=[{'id': 'r1', 'endTime': '2026-11-15T08:00:00Z'},
                                    {'id': 'r2', 'endTime': '2026-11-16T08:00:00Z'}])
    assert code == 0 and _posts(calls) == []
    assert out.strip().endswith('channel_reach_basic_a1 running since 2026-11-14; 2 daily files ready, '
                                'newest up to 2026-11-16')


def test_youtubes_own_system_job_does_not_count_as_ours(run):
    _code, calls, _out = run(jobs=[{'id': 'sys', 'reportTypeId': REACH, 'systemManaged': True}])
    assert len(_posts(calls)) == 1


def test_a_channel_not_granted_yet_is_reported_and_left_alone(run):
    code, calls, out = run(types_error={'error': {'status': 'PERMISSION_DENIED', 'message': 'private wording',
                                                  'details': [{'reason': 'ACCESS_TOKEN_SCOPE_INSUFFICIENT'}]}})
    assert code == 0 and _posts(calls) == []
    assert out.strip() == ('::notice title=Reporting jobs secret-place::not granted yet '
                           '(403 PERMISSION_DENIED ACCESS_TOKEN_SCOPE_INSUFFICIENT); nothing started')


def test_a_report_youtube_does_not_offer_is_not_asked_for(run):
    code, calls, out = run(offered=('channel_basic_a3',))
    assert code == 0 and _posts(calls) == []
    assert '::warning title=Reporting jobs secret-place::channel_reach_basic_a1 is not offered' in out


def test_dry_run_starts_nothing(run):
    code, calls, out = run(['--dry-run'])
    assert code == 0 and _posts(calls) == []
    assert out.strip().endswith('would start channel_reach_basic_a1')


def test_nothing_secret_is_printed_and_nothing_is_deleted_or_downloaded(run):
    _code, calls, out = run(jobs=[{'id': 'job-1', 'reportTypeId': REACH, 'createTime': '2026-11-14T16:40:02Z'}],
                            reports=[{'id': 'r1', 'endTime': '2026-11-15T08:00:00Z',
                                      'downloadUrl': 'https://youtubereporting.googleapis.com/v1/media/PRIVATE'}])
    for secret in ('ACCESS-SECRET', 'CLIENT-SECRET', 'REFRESH-SECRET', '123456789012', 'PRIVATE', 'job-1'):
        assert secret not in out
    assert all(method in ('GET', 'POST') for method, _u, _d in calls)
    assert not [u for _m, u, _d in calls if '/media/' in u]
    source = (ROOT / 'scripts/reporting_jobs.py').read_text(encoding='utf-8')
    assert "method='DELETE'" not in source and source.count("method='POST'") == 1


def test_a_dead_token_does_not_fail_the_run(monkeypatch, capsys):
    def urlopen(request, timeout=0):
        raise _refuse(request.full_url, 400, {'error': 'invalid_grant', 'error_description': 'private wording'})
    monkeypatch.setattr(rj.urllib.request, 'urlopen', urlopen)
    monkeypatch.setenv('CHANNEL', 'prayer4')
    assert rj.main([]) == 0
    out = capsys.readouterr().out
    assert out.strip() == ('::warning title=Reporting jobs prayer4::token refresh REFUSED 400 invalid_grant; '
                           'nothing started')


def test_plan_sorts_wanted_reports_into_start_have_and_absent():
    assert rj.plan([REACH], []) == ([REACH], [], [])
    assert rj.plan([REACH], [{'reportTypeId': REACH}]) == ([], [REACH], [])
    assert rj.plan([], []) == ([], [], [REACH])
    assert rj.day('2026-11-14T16:40:02Z') == '2026-11-14' and rj.day('<b>') == 'unknown date'


def test_the_workflow_covers_all_ten_channels_reads_only_the_repository_and_runs_daily():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))
    assert workflow['permissions'] == {'contents': 'read'}
    job = workflow['jobs']['reporting']
    assert job['strategy']['fail-fast'] is False
    assert job['strategy']['matrix']['channel'] == ['secret-place'] + ['prayer%d' % n for n in range(2, 11)]
    step = job['steps'][-1]
    assert set(step['env']) == {'CHANNEL', 'CLIENT_ID', 'CLIENT_SECRET', 'REFRESH_TOKEN'}
    assert step['run'].strip() == 'python3 -u scripts/reporting_jobs.py'
    assert job['steps'][0]['with'] == {'persist-credentials': False}
    assert len(workflow[True]['schedule']) == 1
