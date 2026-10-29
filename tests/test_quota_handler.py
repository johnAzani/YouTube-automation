from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
import yaml

from pipeline.quota_handler import (
    GeminiQuotaExceededError,
    QuotaExceededError,
    calculate_next_quota_reset_utc,
    is_quota_pause_expired,
    pause_longform_job_on_quota,
    unpause_longform_job,
)
from pipeline.run import select_jobs
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


def test_gemini_quota_exceeded_error_attributes():
    reset_time = datetime(2026, 10, 29, 8, 0, 0, tzinfo=timezone.utc)
    err = GeminiQuotaExceededError("Google Gemini free tier 429 quota exhausted", reset_utc=reset_time)
    assert "Gemini free tier" in str(err)
    assert err.reset_utc == reset_time


def test_is_quota_pause_expired():
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    future_iso = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert is_quota_pause_expired(past_iso) is True
    assert is_quota_pause_expired(future_iso) is False
    assert is_quota_pause_expired("") is True


def test_pause_and_unpause_longform_job(tmp_path: Path):
    job_file = tmp_path / "0099-test-script.md"
    job_file.write_text(
        """---
id: "0099"
title: "Test Script | The Secret Place"
slug: test-script
status: approved
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
tags: [prayer]
thumb_text: "TEST"
description: "Test description"
asset_queries: ["test meadow"]
originality:
  original_thesis: true
  unique_structure: true
  human_rewrite: true
  no_ai_persona: true
  source_notes: true
  ai_disclosure: false
---

## Scene 1 — Test
Test sentence for verification.
""",
        encoding="utf-8",
    )

    reset_time = datetime(2026, 10, 30, 8, 0, 0, tzinfo=timezone.utc)
    pause_longform_job_on_quota(job_file, "Gemini 429 Resource Exhausted", reset_utc=reset_time)

    # Check that status is now quota_paused and reset timestamp is embedded
    content_paused = job_file.read_text(encoding="utf-8")
    assert "status: quota_paused" in content_paused
    assert reset_time.isoformat() in content_paused
    assert "gemini_api_daily_quota_exhausted" in content_paused

    # Now unpause
    unpause_longform_job(job_file)
    content_unpaused = job_file.read_text(encoding="utf-8")
    assert "status: approved" in content_unpaused
    assert "quota_reset_utc" not in content_unpaused
    assert "pause_reason" not in content_unpaused


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


def test_select_jobs_auto_resumes_expired_longform_pause(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("pipeline.run.QUEUE_DIR", tmp_path)
    job_file = tmp_path / "0098-test-expired-pause.md"
    past_reset = datetime(2020, 1, 1, 8, 0, 0, tzinfo=timezone.utc).isoformat()
    job_file.write_text(
        f"""---
id: "0098"
title: "Expired Pause Job | The Secret Place"
slug: test-expired-pause
status: quota_paused
quota_reset_utc: "{past_reset}"
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
tags: [prayer]
thumb_text: "EXPIRED"
description: "Test description"
asset_queries: ["test meadow"]
originality:
  original_thesis: true
  unique_structure: true
  human_rewrite: true
  no_ai_persona: true
  source_notes: true
  ai_disclosure: false
---

## Scene 1 — Test
Test sentence for verification.
""",
        encoding="utf-8",
    )

    selected = select_jobs(all_flag=False, job_path=None, next_flag=True)
    assert len(selected) == 1
    assert selected[0] == job_file
    # Check that job file was unpaused to 'approved'
    content = job_file.read_text(encoding="utf-8")
    assert "status: approved" in content
    assert "quota_reset_utc" not in content

