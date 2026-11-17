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
    # The length is the linked video's own, read from its receipt (six minutes),
    # not the fixed "8-MINUTE" this sentence carried on every Short until 17
    # November 2026.
    assert "PRAY THE COMPLETE 6-MINUTE PSALM 91 MEDITATION" in enriched
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


def test_the_length_in_the_header_is_the_video_s_own(tmp_path: Path):
    """A Short's description states the length of the video it links, or none."""
    from pipeline.shorts_bridge import length_phrase, minutes_on_record

    short = tmp_path / "0016-night-prayer.md"
    short.write_text(
        "---\nid: '0016'\ntarget_minutes: 6\nduration_seconds: 371.2\n---\n\nBody.\n",
        encoding="utf-8")
    assert minutes_on_record(short) == 6

    # A night-tail prayer is three hours, and says so.
    tail = tmp_path / "0024-darkness.md"
    tail.write_text(
        "---\nid: '0024'\ntarget_minutes: 6\nduration_seconds: 11189.1\n---\n\nBody.\n",
        encoding="utf-8")
    assert minutes_on_record(tail) == 186
    assert length_phrase(minutes_on_record(tail)) == "3-HOUR "

    # Nothing on record: no number is invented.
    bare = tmp_path / "0027-unknown.md"
    bare.write_text("---\nid: '0027'\n---\n\nBody.\n", encoding="utf-8")
    assert minutes_on_record(bare) is None
    assert length_phrase(None) == ""
    assert length_phrase(0) == ""
    missing = tmp_path / "not-there.md"
    assert minutes_on_record(missing) is None
