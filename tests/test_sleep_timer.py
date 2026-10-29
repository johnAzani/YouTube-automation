"""Unit tests for Liturgical Sleep Timer & Google SERP Key Moments Engine."""
from __future__ import annotations

import json
from pipeline.sleep_timer import (
    DEFAULT_SLEEP_TIMERS,
    format_sleep_timer_description_block,
    generate_sleep_schema_jsonld,
    generate_sleep_timer_chapters,
)


def test_generate_sleep_timer_chapters():
    """Verify sleep timer intervals generated up to duration."""
    chapters = generate_sleep_timer_chapters(total_duration_minutes=60)
    assert len(chapters) >= 4
    assert chapters[0]["timestamp"] == "00:00"
    assert any("15 Min Sleep Drift" in c["title"] for c in chapters)
    assert any("30 Min Deep Peace" in c["title"] for c in chapters)


def test_format_sleep_timer_description_block():
    """Verify description block formatting."""
    block = format_sleep_timer_description_block(total_duration_minutes=60)
    assert "BEDTIME SLEEP TIMER & CHAPTERS:" in block
    assert "15 Min Sleep Drift" in block


def test_generate_sleep_schema_jsonld():
    """Verify Schema.org VideoObject JSON-LD generation."""
    jsonld_str = generate_sleep_schema_jsonld(
        title="1 Hour Bedtime Prayer for Peaceful Sleep",
        description="Bedtime scripture meditation.",
        video_id="mock_vid_123",
        duration_iso="PT1H0M0S",
    )
    data = json.loads(jsonld_str)
    assert data["@context"] == "https://schema.org"
    assert data["@type"] == "VideoObject"
    assert data["name"] == "1 Hour Bedtime Prayer for Peaceful Sleep"
    assert len(data["hasPart"]) >= 4
    assert data["hasPart"][0]["@type"] == "Clip"
    assert "mock_vid_123" in data["hasPart"][0]["url"]
