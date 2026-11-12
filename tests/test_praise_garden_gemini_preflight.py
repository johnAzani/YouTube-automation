"""The ninth-channel Gemini probe is read-only and never discloses secrets."""
import io
import urllib.error

import pytest
from scripts import praise_garden_gemini_preflight as probe


def test_only_target_key_and_read_only_model_list():
    seen = []
    def opener(request, timeout):
        seen.append((request, timeout))
        return io.BytesIO(b'{"models": [{"name": "models/example"}]}')
    probe.check({'PRAYER9_GEMINI_API_KEY': 'private', 'GEMINI_API_KEY': 'other'}, opener)
    request, timeout = seen[0]
    assert request.full_url == 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1'
    assert request.get_method() == 'GET' and request.data is None
    assert request.get_header('X-goog-api-key') == 'private'
    assert timeout == 20


def test_missing_key_never_falls_back_or_calls_network():
    with pytest.raises(probe.PreflightError, match='PRAYER9_GEMINI_API_KEY is missing'):
        probe.check({'GEMINI_API_KEY': 'other'}, lambda *a, **kw: pytest.fail('network called'))


@pytest.mark.parametrize('response', [b'{}', b'{"models": []}', b'{"models": "no"}', b'not json'])
def test_invalid_responses_fail_without_disclosure(response):
    with pytest.raises(probe.PreflightError) as error:
        probe.check({'PRAYER9_GEMINI_API_KEY': 'private'}, lambda *a, **kw: io.BytesIO(response))
    assert 'private' not in str(error.value)


def test_http_error_is_sanitized():
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://example/private', 403, 'private', {}, None)
    with pytest.raises(probe.PreflightError, match='HTTP 403') as error:
        probe.check({'PRAYER9_GEMINI_API_KEY': 'private'}, fail)
    assert 'private' not in str(error.value)
