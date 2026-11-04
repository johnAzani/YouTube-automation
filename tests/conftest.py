from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_unit_tests_from_live_queue_quota_pauses(monkeypatch, request):
    """Do not let a real/main queue pause contaminate mocked TTS unit tests.

    PR CI can run against a merge commit whose base queue contains a production
    `quota_paused` item. Most tests exercise transport retry logic with fake
    clients and must be deterministic regardless of that live queue state. The
    dedicated shared-breaker tests exercise the real queue scanner using temporary
    content directories and explicitly mock the request guard where appropriate.
    """
    if "test_shared_tts_quota_breaker.py" not in request.node.nodeid:
        monkeypatch.setattr(
            "pipeline.quota_handler.active_gemini_tts_pause_until",
            lambda *args, **kwargs: None,
        )
