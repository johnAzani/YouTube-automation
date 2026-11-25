"""A Short spec written from a passage, on a first frame that shows the need.

`pipeline/first_frame.py` found that 420 of 634 authored specs opened with a
citation the authoring prompt forbids, and that all 634 shared one composition.
`pipeline/passage_short.py` writes the other kind: scene one is the need, the
citation arrives with the verse on scene two. These tests hold it to that.
"""
from __future__ import annotations

import json

import pytest

from pipeline import first_frame as ff
from pipeline import passage_short as ps
from pipeline.short_script import MAX_KICKER_CHARS, MAX_SUB_CHARS, ShortSpecError


def test_a_generated_spec_opens_on_the_need_and_not_on_a_citation():
    data = ps.build_spec("prayer2", "Psalm 19:14", theme="WORDS OF MY MOUTH")
    frame = ff.first_frame(data)
    assert frame["kicker_is_reference"] is False
    assert frame["kicker"] == frame["kicker"].upper()
    assert frame["words_on_frame_one"] <= 24


def test_the_citation_is_still_on_the_frame_the_verse_is_read():
    data = ps.build_spec("prayer2", "Psalm 19:14")
    kickers = [scene["kicker"] for scene in data["scenes"]]
    assert "PSALM 19:14" in kickers
    assert kickers.index("PSALM 19:14") == 1, "the verse, and its citation, come second"


def test_every_generated_line_fits_the_renderer():
    for reference in ("Psalm 19:14", "Psalm 146:2", "Lamentations 3:23"):
        data = ps.build_spec("prayer2", reference)
        for scene in data["scenes"]:
            assert len(scene["kicker"]) <= MAX_KICKER_CHARS, scene["kicker"]
            assert len(scene["sub"]) <= MAX_SUB_CHARS, scene["sub"]


def test_the_words_on_screen_are_the_repositorys_words():
    """Not a paraphrase: the verse is read from scripture_text, not retyped."""
    from pipeline.scripture_text import passage, readable

    data = ps.build_spec("prayer2", "Psalm 19:14")
    verse = readable(" ".join(v.text for v in passage("Psalm 19:14")))
    narration = " ".join(str(c[2]) for c in data["captions"])
    assert verse.split(",")[0] in narration


def test_a_spec_that_cannot_render_is_never_written(tmp_path):
    data = ps.build_spec("prayer2", "Psalm 19:14")
    data["scenes"][0]["kicker"] = "A" * (MAX_KICKER_CHARS + 1)
    from pipeline.short_script import require_valid, validate_spec

    spec = validate_spec(data)      # collects problems rather than raising
    assert spec.problems, "a 23-character kicker must be reported"
    with pytest.raises(ShortSpecError):
        require_valid(spec)         # and must stop the write


def test_a_channel_is_illustrated_in_its_own_hour():
    morning = ps.build_spec("prayer2", "Psalm 19:14")
    night = ps.build_spec("secret-place", "Psalm 19:14")
    assert morning["stock_queries"] == list(ps.PLATES["morning"])
    assert night["stock_queries"] == list(ps.PLATES["night"])


def test_a_generated_spec_says_that_it_was_generated():
    data = ps.build_spec("prayer2", "Psalm 19:14")
    assert data["authored_by"] == ps.AUTHORED_BY


def test_the_generator_offers_only_passages_this_channel_has_not_used():
    from pipeline.evergreen_shorts import candidates, reference_parts, same_passage, used_references

    used = used_references("prayer2")
    for item in ps.next_passages("prayer2", count=3):
        parts = reference_parts(item["reference"])
        assert not any(same_passage(parts, u) for u in used), item


def test_the_repository_specs_this_module_wrote_are_on_need_first_frames():
    """The five it wrote on 25 November 2026, held to the rule it exists for."""
    from pathlib import Path

    folder = Path(ff.SPEC_DIR)
    written = [p for p in folder.glob("*.json")
               if json.loads(p.read_text()).get("authored_by") == ps.AUTHORED_BY]
    assert written, "expected at least one spec from pipeline/passage_short.py"
    for path in written:
        frame = ff.first_frame(json.loads(path.read_text()))
        assert frame["kicker_is_reference"] is False, path.name


def test_two_channels_never_speak_the_same_sentence_from_the_generator():
    """Caught on the real repository on 25 November 2026.

    The first version of this module wrote one prayer template for all ten
    channels, so `scripts/channel_protection.py` found the same seven sentences on
    The Secret Place and The Morning Altar. A prayer for waking and a prayer for
    the last hour before sleep are not the same words.
    """
    from pipeline.channels import scheduled_channels

    spoken: dict[str, set[str]] = {}
    for channel in scheduled_channels():
        spec = ps.build_spec(channel, "Psalm 19:14")
        spoken[channel] = {str(caption[2]) for caption in spec["captions"]}
    channels = list(spoken)
    for i, first in enumerate(channels):
        for second in channels[i + 1:]:
            shared = spoken[first] & spoken[second]
            # The verse itself is allowed to match; nothing else is.
            shared = {line for line in shared if "words of my mouth" not in line.lower()}
            assert not shared, f"{first} and {second} share {shared}"


def test_each_channel_is_prayed_for_in_its_own_hour():
    from pipeline.passage_short import HOUR_VOICE

    openings = {hour: voice["open"] for hour, voice in HOUR_VOICE.items()}
    assert len(set(openings.values())) == len(openings), "two hours share an opening"


def test_the_arc_is_the_size_the_renderer_requires():
    """6-10 scenes, one plate request each, and no caption without one."""
    spec = ps.build_spec("prayer2", "Psalm 19:14")
    assert len(spec["scenes"]) == len(spec["captions"]) == len(spec["stock_queries"])
    assert 6 <= len(spec["scenes"]) <= 10
