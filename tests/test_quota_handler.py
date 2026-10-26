from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
import yaml

from pipeline.upload import (
    QuotaExceededError,
    calculate_next_quota_reset_utc,
)
from pipeline.short_release import select_next_queued_short


def test_calculate_next_quota_reset_utc():
    reset_dt = calculate_next_quota_reset_utc()
    now_utc = datetime.now(timezone.utc)
    # The reset time must strictly be in the future (within 25 hours)
    assert reset_dt > now_utc
    delta_hours = (reset_dt - now_utc).total_seconds() / 3600.0
    assert 0 < delta_hours <= 25.0
    # Must have UTC timezone attached
    assert reset_dt.tzinfo == timezone.utc


def test_quota_exceeded_error_attributes():
    reset_time = datetime(2026, 10, 27, 8, 0, 0, tzinfo=timezone.utc)
    err = QuotaExceededError("YouTube upload quota exceeded", reset_utc=reset_time)
    assert "upload quota exceeded" in str(err)
    assert err.reset_utc == reset_time


def test_select_next_queued_short_skips_active_pause(tmp_path: Path):
    queue_file = tmp_path / "short-0002.yml"
    future_reset = datetime(2099, 1, 1, 8, 0, 0, tzinfo=timezone.utc).isoformat()
    queue_file.write_text(
        yaml.safe_dump(
            {
                "short": "short-psalm91",
                "status": "quota_paused",
                "quota_reset_utc": future_reset,
            }
        ),
        encoding="utf-8",
    )

    result = select_next_queued_short(queue_dir=tmp_path)
    assert result is None, "Should skip queue item whose quota reset is still in the future"


def test_select_next_queued_short_auto_resumes_expired_pause(tmp_path: Path):
    queue_file = tmp_path / "short-0002.yml"
    past_reset = datetime(2020, 1, 1, 8, 0, 0, tzinfo=timezone.utc).isoformat()
    queue_file.write_text(
        yaml.safe_dump(
            {
                "short": "short-psalm91",
                "status": "quota_paused",
                "quota_reset_utc": past_reset,
            }
        ),
        encoding="utf-8",
    )

    result = select_next_queued_short(queue_dir=tmp_path)
    assert result is not None
    path, key = result
    assert key == "short-psalm91"
    # Verify manifest was unpaused to 'approved'
    updated_data = yaml.safe_load(queue_file.read_text(encoding="utf-8"))
    assert updated_data["status"] == "approved"
