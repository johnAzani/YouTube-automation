"""Unit tests for Google Search Key Moments & Video SEO Enhancer."""
from __future__ import annotations

from pipeline.video_seo_enhancer import (
    KeyMoment,
    build_serp_key_moments,
    enhance_description_with_key_moments,
    format_seconds_to_timestamp,
    generate_video_schema_json_ld,
    parse_timestamp_to_seconds,
    validate_key_moments,
)


def test_format_and_parse_timestamp():
    """Verify conversion between seconds and formatted timestamps."""
    assert format_seconds_to_timestamp(0.0) == "00:00"
    assert format_seconds_to_timestamp(75.0) == "01:15"
    assert format_seconds_to_timestamp(3665.0) == "01:01:05"

    assert parse_timestamp_to_seconds("00:00") == 0.0
    assert parse_timestamp_to_seconds("01:15") == 75.0
    assert parse_timestamp_to_seconds("01:01:05") == 3665.0


def test_validate_key_moments_valid():
    """Verify that a compliant chapter list passes Google Key Moments validation."""
    chapters = [
        {"timestamp": "00:00", "seconds": 0.0, "title": "Opening Scripture"},
        {"timestamp": "01:30", "seconds": 90.0, "title": "Covenant of Protection"},
        {"timestamp": "03:15", "seconds": 195.0, "title": "Sacred Night Benediction"},
    ]
    valid, issues = validate_key_moments(chapters)
    assert valid is True
    assert len(issues) == 0


def test_validate_key_moments_invalid_first_timestamp():
    """Verify rejection when the first chapter does not begin at 00:00."""
    chapters = [
        {"timestamp": "00:15", "seconds": 15.0, "title": "Late Start"},
        {"timestamp": "01:30", "seconds": 90.0, "title": "Second Clip"},
        {"timestamp": "03:00", "seconds": 180.0, "title": "Third Clip"},
    ]
    valid, issues = validate_key_moments(chapters)
    assert valid is False
    assert any("00:00" in err for err in issues)


def test_build_serp_key_moments():
    """Verify enhancing raw chapters with search intent keywords."""
    raw = [
        {"timestamp": "00:00", "seconds": 0.0, "title": "1. Psalm 91: The Secret Place"},
        {"timestamp": "01:45", "seconds": 105.0, "title": "2. Under His Wings & Shield"},
        {"timestamp": "03:30", "seconds": 210.0, "title": "3. Angelic Army Watch"},
    ]
    moments = build_serp_key_moments(raw, target_search_keywords=["psalm 91 sleep prayer", "under his wings", "angels watch"])
    assert len(moments) == 3
    assert moments[0].timestamp == "00:00"
    assert "Psalm 91" in moments[0].label


def test_enhance_description_with_key_moments():
    """Verify description formatting with Google Key Moments block."""
    base = "Say this powerful Psalm prayer before you sleep tonight."
    moments = [
        KeyMoment(0.0, "00:00", "Opening Scripture", "psalm 91"),
        KeyMoment(90.0, "01:30", "Divine Protection", "divine protection"),
        KeyMoment(210.0, "03:30", "Nighttime Blessing", "night prayer"),
    ]
    enhanced = enhance_description_with_key_moments(base, moments)
    assert "TIMESTAMPS & KEY MOMENTS:" in enhanced
    assert "00:00 Opening Scripture" in enhanced
    assert "01:30 Divine Protection" in enhanced


def test_generate_video_schema_json_ld():
    """Verify Schema.org VideoObject JSON-LD generation."""
    moments = [
        KeyMoment(0.0, "00:00", "Opening Prayer", "psalm 91"),
        KeyMoment(120.0, "02:00", "Divine Shield", "divine shield"),
        KeyMoment(240.0, "04:00", "Angelic Watch", "angels"),
    ]
    schema = generate_video_schema_json_ld(
        title="Psalm 91 Prayer",
        description="Bedtime scripture meditation.",
        video_id="7RDX0fbIOtQ",
        upload_date_iso="2026-10-29T14:00:00Z",
        duration_iso="PT6M30S",
        thumbnail_url="https://example.com/thumb.jpg",
        key_moments=moments,
    )
    assert schema["@context"] == "https://schema.org"
    assert schema["@type"] == "VideoObject"
    assert len(schema["hasPart"]) == 3
    assert schema["hasPart"][0]["@type"] == "Clip"
    assert schema["hasPart"][0]["startOffset"] == 0
