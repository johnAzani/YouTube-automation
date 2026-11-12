"""The tenth-channel Gemini probe is read-only and isolated."""
import io
from pathlib import Path
import urllib.error

import pytest
import yaml

from scripts import guided_path_gemini_preflight as probe


def test_only_target_key_and_read_only_model_list():
    seen = []
    def opener(request, timeout):
        seen.append((request, timeout))
        return io.BytesIO(b'{"models": [{"name": "models/example"}]}')
    probe.check({'PRAYER10_GEMINI_API_KEY': 'private10', 'PRAYER9_GEMINI_API_KEY': 'other',
                 'GEMINI_API_KEY': 'other'}, opener)
    request, timeout = seen[0]
    assert request.full_url == 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1'
    assert request.get_method() == 'GET' and request.data is None
    assert request.get_header('X-goog-api-key') == 'private10'
    assert timeout == 20


def test_missing_key_no_fallback_or_network():
    with pytest.raises(probe.shared.PreflightError, match='PRAYER10_GEMINI_API_KEY is missing'):
        probe.check({'PRAYER9_GEMINI_API_KEY': 'other', 'GEMINI_API_KEY': 'other'},
                    lambda *a, **kw: pytest.fail('network called'))


@pytest.mark.parametrize('response', [b'{}', b'{"models": []}', b'{"models": "no"}', b'not json'])
def test_bad_responses_do_not_disclose_key(response):
    with pytest.raises(probe.shared.PreflightError) as error:
        probe.check({'PRAYER10_GEMINI_API_KEY': 'private10'}, lambda *a, **kw: io.BytesIO(response))
    assert 'private10' not in str(error.value)


def test_http_error_is_sanitized():
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://example/private10', 403, 'private10', {}, None)
    with pytest.raises(probe.shared.PreflightError, match='HTTP 403') as error:
        probe.check({'PRAYER10_GEMINI_API_KEY': 'private10'}, fail)
    assert 'private10' not in str(error.value)


def test_workflow_manual_read_only_and_isolated():
    workflow = yaml.safe_load(Path('.github/workflows/guided-path-gemini-preflight.yml').read_text())
    assert set(workflow.get('on', workflow.get(True))) == {'workflow_dispatch'}
    assert workflow['permissions'] == {'contents': 'read'}
    steps = workflow['jobs']['preflight']['steps']
    assert steps[0]['with']['persist-credentials'] is False
    step = next(step for step in steps if 'run' in step)
    assert step['run'] == 'python3 scripts/guided_path_gemini_preflight.py'
    assert step['env'] == {'PRAYER10_GEMINI_API_KEY': '${{ secrets.PRAYER10_GEMINI_API_KEY }}'}
