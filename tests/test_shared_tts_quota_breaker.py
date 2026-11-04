from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest
import yaml

from pipeline.quota_handler import active_gemini_tts_pause_until


def test_short_pause_blocks_shared_gemini_tts_for_both_formats(tmp_path: Path) -> None:
    content = tmp_path / "content"
    (content / "queue").mkdir(parents=True)
    shorts = content / "shorts-queue"
    shorts.mkdir(parents=True)
    reset = datetime.now(timezone.utc) + timedelta(hours=5)
    (shorts / "short-psalm91.yml").write_text(yaml.safe_dump({
        "status": "quota_paused",
        "pause_reason": "gemini_api_daily_quota_exhausted",
        "quota_reset_utc": reset.isoformat(),
    }), encoding="utf-8")

    assert active_gemini_tts_pause_until(content_dir=content) == reset


def test_expired_and_youtube_only_pauses_do_not_block_gemini_tts(tmp_path: Path) -> None:
    content = tmp_path / "content"
    queue = content / "queue"
    shorts = content / "shorts-queue"
    queue.mkdir(parents=True)
    shorts.mkdir(parents=True)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    (queue / "0001-psalm.md").write_text(
        "---\n" + yaml.safe_dump({
            "status": "quota_paused",
            "pause_reason": "gemini_api_daily_quota_exhausted",
            "quota_reset_utc": past.isoformat(),
        }) + "---\nPrayer text.\n", encoding="utf-8")
    (shorts / "short.yml").write_text(yaml.safe_dump({
        "status": "quota_paused",
        "pause_reason": "youtube_api_daily_quota_exhausted",
        "quota_reset_utc": (past + timedelta(days=1)).isoformat(),
    }), encoding="utf-8")

    assert active_gemini_tts_pause_until(content_dir=content) is None


def test_short_pause_also_stops_longform_release_gate(tmp_path: Path) -> None:
    from pipeline import run

    content = tmp_path / "content"
    queue = content / "queue"
    shorts = content / "shorts-queue"
    queue.mkdir(parents=True)
    shorts.mkdir(parents=True)
    reset = datetime.now(timezone.utc) + timedelta(hours=3)
    (shorts / "short.yml").write_text(yaml.safe_dump({
        "status": "quota_paused",
        "pause_reason": "gemini_api_daily_quota_exhausted",
        "quota_reset_utc": reset.isoformat(),
    }), encoding="utf-8")

    with mock.patch.object(run, "QUEUE_DIR", queue), mock.patch.object(run, "CONTENT_DIR", content):
        assert run.quota_blocked_until() == reset


def test_existing_pause_fails_before_any_gemini_request() -> None:
    from pipeline import gemini_tts
    from pipeline.quota_handler import GeminiQuotaExceededError

    reset = datetime.now(timezone.utc) + timedelta(hours=2)
    with mock.patch.object(gemini_tts, "_synthesize_single_chunk") as request, \
         mock.patch("pipeline.quota_handler.active_gemini_tts_pause_until", return_value=reset):
        with pytest.raises(GeminiQuotaExceededError, match="no new request was sent"):
            gemini_tts._guarded_chunk(
                object(), "words", "Charon", "read", "model", Path("raw"), 1, 1
            )
        request.assert_not_called()
