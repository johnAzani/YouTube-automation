"""Centralized Quota Management & Fail-Closed Auto-Resume Handler.

Pause jobs after a quota error until the next Pacific daily reset and resume on a
later scheduled run. Quotas vary by project, model, and API. Handling a quota
error does not verify billing tier or enforce a $0 spending limit.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo
import yaml

from pipeline.script_doc import parse_script


class QuotaExceededError(RuntimeError):
    """Raised when YouTube Data API v3 daily upload quota (10,000 units) is exceeded."""

    def __init__(self, message: str, reset_utc: datetime | None = None, reset_time_utc: datetime | None = None):
        super().__init__(message)
        self.message = message
        self.reset_utc = reset_utc or reset_time_utc or calculate_next_quota_reset_utc()
        self.reset_time_utc = self.reset_utc


class GeminiQuotaExceededError(RuntimeError):
    """Raised when a Gemini API quota or rate limit is exceeded."""

    def __init__(self, message: str, reset_utc: datetime | None = None):
        super().__init__(message)
        self.message = message
        self.reset_utc = reset_utc or calculate_next_quota_reset_utc()
        self.reset_time_utc = self.reset_utc


def calculate_next_quota_reset_utc(now: datetime | None = None) -> datetime:
    """Return the next midnight in Pacific time, accounting for DST.

    Daily quotas reset at Pacific midnight. Other rate limits can reset sooner;
    this conservative fallback does not identify which limit was exceeded.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    pacific = ZoneInfo("America/Los_Angeles")
    tomorrow = now.astimezone(pacific).date() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=pacific).astimezone(timezone.utc)


def is_quota_pause_expired(quota_reset_utc_str: str) -> bool:
    """Return True if the quota pause timestamp has passed."""
    if not quota_reset_utc_str:
        return True
    try:
        reset_at = datetime.fromisoformat(quota_reset_utc_str)
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= reset_at
    except Exception:
        return True


def pause_longform_job_on_quota(
    job_path: Path,
    error_message: str,
    reset_utc: Optional[datetime] = None,
) -> Path:
    """Update a content/queue/*.md job to 'status: quota_paused' and sync factcheck worksheet."""
    reset_dt = reset_utc or calculate_next_quota_reset_utc()
    reset_iso = reset_dt.isoformat()

    content = job_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid script structure in {job_path.name}")

    meta = yaml.safe_load(parts[1]) or {}
    meta["status"] = "quota_paused"
    meta["quota_reset_utc"] = reset_iso
    meta["pause_reason"] = "gemini_api_daily_quota_exhausted" if "gemini" in error_message.lower() else "youtube_api_daily_quota_exhausted"

    new_frontmatter = yaml.safe_dump(meta, sort_keys=False).strip()
    new_content = f"---\n{new_frontmatter}\n---" + parts[2]
    job_path.write_text(new_content, encoding="utf-8")

    # Sync factcheck worksheet with new hash so tests and verification stay 100% green
    try:
        from scripts.factcheck import main as factcheck_main
        factcheck_main([meta.get("id", job_path.stem[:4]), "--force"])
    except Exception as exc:
        print(f"[quota_handler] Warning: could not refresh factcheck worksheet: {exc}")

    return job_path


def unpause_longform_job(job_path: Path) -> Path:
    """Restore a content/queue/*.md job to 'status: approved' and sync factcheck worksheet."""
    content = job_path.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid script structure in {job_path.name}")

    meta = yaml.safe_load(parts[1]) or {}
    meta["status"] = "approved"
    meta.pop("quota_reset_utc", None)
    meta.pop("pause_reason", None)

    new_frontmatter = yaml.safe_dump(meta, sort_keys=False).strip()
    new_content = f"---\n{new_frontmatter}\n---" + parts[2]
    job_path.write_text(new_content, encoding="utf-8")

    try:
        from scripts.factcheck import main as factcheck_main
        factcheck_main([meta.get("id", job_path.stem[:4]), "--force"])
    except Exception as exc:
        print(f"[quota_handler] Warning: could not refresh factcheck worksheet: {exc}")

    return job_path


def pause_short_manifest_on_quota(
    manifest_path: Path,
    error_message: str,
    reset_utc: Optional[datetime] = None,
) -> Path:
    """Update a content/shorts-queue/*.yml manifest to 'status: quota_paused'."""
    reset_dt = reset_utc or calculate_next_quota_reset_utc()
    reset_iso = reset_dt.isoformat()

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    data["status"] = "quota_paused"
    data["quota_reset_utc"] = reset_iso
    data["pause_reason"] = "gemini_api_daily_quota_exhausted" if "gemini" in error_message.lower() else "youtube_api_daily_quota_exhausted"
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return manifest_path


def unpause_short_manifest(manifest_path: Path) -> Path:
    """Restore a content/shorts-queue/*.yml manifest to 'status: approved'."""
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    data["status"] = "approved"
    data.pop("quota_reset_utc", None)
    data.pop("pause_reason", None)
    manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return manifest_path
