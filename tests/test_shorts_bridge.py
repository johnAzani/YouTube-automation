"""Unit tests for Shorts-to-Longform Conversion Bridge Engine."""
from __future__ import annotations

from pipeline.script_doc import ScriptDoc
from pipeline.shorts_bridge import (
    SHORT_LONGFORM_CATALOG,
    enrich_short_description_with_bridge,
    generate_short_bridge_comment,
    resolve_longform_counterpart,
    resolve_short_key,
)
from pipeline.pinned_comments import generate_pastoral_pinned_comment


def test_resolve_short_key():
    """Verify normalization of short slugs, keys, and titles."""
    assert resolve_short_key("short-psalm91") == "short-psalm91"
    assert resolve_short_key("short-0002-psalm-91-prayer-of-protection") == "short-psalm91"
    assert resolve_short_key("Say This Psalm 23 Prayer Before You Sleep #Shorts") == "short-psalm23"
    assert resolve_short_key("short-psalm121") == "short-psalm121"
    assert resolve_short_key("Psalm 46 Prayer #Shorts") == "short-psalm46"
    assert resolve_short_key("Psalm 34 Bedtime") == "short-psalm34"
    assert resolve_short_key("completely-unrelated-key") is None


def test_resolve_longform_counterpart():
    """Verify matching of Short to long-form counterpart."""
    # Psalm 91 has live fallback video 7RDX0fbIOtQ
    res_91 = resolve_longform_counterpart("short-psalm91")
    assert res_91["found"] is True
    assert res_91["video_id"] == "7RDX0fbIOtQ"
    assert "https://youtu.be/7RDX0fbIOtQ" in res_91["url"]
    assert "Psalm 91" in res_91["title"]

    # Psalm 23 falls back to playlist if not yet published
    res_23 = resolve_longform_counterpart("short-psalm23")
    assert res_23["found"] is True
    assert "playlist" in res_23["url"] or "youtu.be" in res_23["url"]


def test_generate_short_bridge_comment():
    """Verify generated pinned comment has clear call to action and URL."""
    comment = generate_short_bridge_comment("short-psalm91")
    assert "PRAY THE FULL NIGHTTIME SCRIPTURE MEDITATION" in comment
    assert "7RDX0fbIOtQ" in comment
    assert "AMEN" in comment


def test_enrich_short_description_with_bridge():
    """Verify description is enriched with prominent link at the top."""
    orig_desc = "Rest tonight under God's divine shield. Psalm 91."
    enriched = enrich_short_description_with_bridge(orig_desc, "short-psalm91")
    assert "PRAY THE COMPLETE 8-MINUTE PSALM 91 MEDITATION" in enriched
    assert "https://youtu.be/7RDX0fbIOtQ" in enriched
    assert orig_desc in enriched

    # Idempotence: enriching again does not duplicate
    re_enriched = enrich_short_description_with_bridge(enriched, "short-psalm91")
    assert re_enriched.count("https://youtu.be/7RDX0fbIOtQ") == 1


def test_pinned_comment_auto_bridges_for_shorts(tmp_path: Path):
    """Verify generate_pastoral_pinned_comment detects Short and uses bridge."""
    doc_path = tmp_path / "short-0002.md"
    doc = ScriptDoc(
        path=doc_path,
        meta={"format": "short", "title": "Say This Psalm 91 Prayer #Shorts", "slug": "short-0002-psalm-91"},
    )
    comment = generate_pastoral_pinned_comment(doc)
    assert "PRAY THE FULL NIGHTTIME SCRIPTURE MEDITATION" in comment
    assert "7RDX0fbIOtQ" in comment
