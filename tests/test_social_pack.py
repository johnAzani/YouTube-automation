"""Unit tests for Social Funnel Pack & Persona Sanitization."""
from __future__ import annotations

from pipeline.social_pack import (
    SUBSCRIBE_URL,
    build_standardized_description_footer,
    sanitize_persona_integrity,
)


def test_build_standardized_description_footer():
    """Verify footer contains subscription link, playlist links, and crisis support."""
    footer = build_standardized_description_footer()
    assert "https://www.youtube.com/@TheSecretPlace" in footer
    assert "988" in footer
    assert "111" in footer
    assert "OFFICIAL SERIES PLAYLISTS" in footer
    assert "PODCAST" in footer


def test_sanitize_persona_integrity():
    """Verify that personal creator names are replaced with channel identity."""
    bad_text = "Produced by John Azani for Azani John Channel."
    clean = sanitize_persona_integrity(bad_text)
    assert "John Azani" not in clean
    assert "Azani John" not in clean
    assert "The Secret Place" in clean
