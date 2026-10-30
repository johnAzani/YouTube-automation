"""Unit tests for High-Intent Search Query & SEO Taxonomy Synthesizer."""
from __future__ import annotations

from pipeline.seo_suggest import (
    SEO_TAXONOMY,
    enrich_video_tags,
    generate_high_intent_search_title,
    get_taxonomy_for_scripture,
    synthesize_seo_metadata,
)


def test_taxonomy_retrieval():
    """Verify scripture-specific and general fallback taxonomy."""
    psalm91 = get_taxonomy_for_scripture("Psalm 91: Prayer of Protection")
    assert "primary_searches" in psalm91
    assert any("psalm 91" in s for s in psalm91["primary_searches"])

    psalm23 = get_taxonomy_for_scripture("Psalm 23")
    assert any("psalm 23" in s for s in psalm23["primary_searches"])

    general = get_taxonomy_for_scripture("Unknown Passage 123")
    assert any("bedtime prayer" in s for s in general["primary_searches"])


def test_enrich_video_tags():
    """Verify tag enrichment with high-intent search terms."""
    base_tags = ["psalm 91", "night prayer"]
    enriched = enrich_video_tags(base_tags, scripture="Psalm 91", target_count=12)
    assert len(enriched) == 12
    assert "psalm 91" in enriched
    assert any("protection" in t for t in enriched)


def test_generate_high_intent_search_title():
    """Verify title authoring under 95 character limit."""
    title = generate_high_intent_search_title(
        scripture="Psalm 91",
        benefit_theme="Divine Protection Before Sleep",
        duration_label="8 Hours",
        is_black_screen=True,
    )
    assert len(title) <= 95
    assert "BLACK SCREEN" in title
    assert "Psalm 91" in title


def test_synthesize_seo_metadata():
    """Verify full SEO synthesis package."""
    meta = synthesize_seo_metadata("Psalm 23", duration_minutes=180, is_black_screen=False)
    assert "Psalm 23" in meta["title"]
    assert len(meta["tags"]) >= 10
    assert "primary_search_query" in meta
    assert "top_pain_point" in meta
