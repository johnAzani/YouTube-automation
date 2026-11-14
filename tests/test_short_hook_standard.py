"""Shorts are where the views are, so their first sentence is not a template.

Measured on 13 November 2026 across all ten channels: 91 Shorts drew 7,513 views
(median 65); 95 long-form prayers drew 261, none over 20. On each channel every
Short opened with the same stock invitation the prompt supplied ("Gather your
home and loved ones in faith...", "Rise in spirit at this midnight hour...").
The counts do not prove the opening matters; ten channels each repeating one
line is reason enough to stop supplying it.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import short_script as ss
from pipeline.channel_capabilities import brand_for

CHANNELS = ("secret-place", "prayer2", "prayer3", "prayer4", "prayer5",
            "prayer6", "prayer7", "prayer8", "prayer9", "prayer10")


@pytest.mark.parametrize("channel", CHANNELS)
def test_every_channel_prompt_asks_for_its_own_opening(channel):
    prompt = ss.build_prompt("Psalm 23:1-3", key="short-x", channel_id=channel,
                             avoid_openings=[])
    brand = brand_for(channel)
    assert "THE OPENING SENTENCE" in prompt
    assert "written for this Short alone" in prompt
    # The brand's stock invitation is now described as mood, not handed over as line one.
    assert f'mood is "{brand.short_opening}"' in prompt
    assert "It opens by inviting" not in prompt
    assert "NOT the first sentence" in prompt
    # Nothing left unfilled, and the JSON skeleton is still there.
    assert "{hook_words}" not in prompt and "{avoid_block}" not in prompt
    assert '"key": "short-x"' in prompt and "Quote ONLY Psalm 23:1-3" in prompt


def test_hooks_stay_honest():
    prompt = ss.build_prompt("Psalm 23:1-3", avoid_openings=[])
    assert "no promised outcome" in prompt
    assert "No personal names" in prompt and "no clickbait" in prompt


def test_length_target_sits_inside_what_the_validator_accepts():
    low, high = ss.TARGET_WORDS_RANGE
    assert ss.MIN_WORDS <= low < ss.TARGET_WORDS < high <= ss.MAX_WORDS
    # Room for the model to undershoot the target and still pass the floor.
    assert ss.TARGET_WORDS - ss.MIN_WORDS >= 10
    prompt = ss.build_prompt("Psalm 23:1-3", avoid_openings=[])
    assert f"about {ss.TARGET_WORDS} words" in prompt
    assert f"never under {low}" in prompt


def test_first_sentence():
    assert ss.first_sentence("Pause now.  Then pray. Amen.") == "Pause now."
    assert ss.first_sentence("Are you awake? He is.") == "Are you awake?"
    assert ss.first_sentence("") == "" and ss.first_sentence(None) == ""


def _specs(tmp_path, monkeypatch, entries):
    """Fake spec files: name -> (channel, narration) or an Exception to raise."""
    for name in entries:
        (tmp_path / name).write_text("{}")

    def load(path):
        value = entries[Path(path).name]
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(channel=value[0], narration_text=value[1])

    monkeypatch.setattr(ss, "load_spec", load)
    return tmp_path


def test_recent_openings_lead_with_the_most_worn_skeleton(tmp_path, monkeypatch):
    directory = _specs(tmp_path, monkeypatch, {
        "a.json": ("prayer5", "Gather your home and loved ones in faith tonight. Then pray."),
        "b.json": ("prayer5", "Gather your home in faith. Then pray."),
        "c.json": ("prayer5", "Gather your home, and lift every child. Then pray."),
        "d.json": ("prayer5", "Before supper, look around the table. Then pray."),
        "e.json": ("prayer4", "Rise in spirit at this midnight hour. Then pray."),
        "f.json": ValueError("unreadable spec"),
    })
    found = ss.recent_openings("prayer5", spec_dir=directory)
    # Three Shorts share "gather your home": one example, the shortest, listed first.
    assert found == ["Gather your home in faith.", "Before supper, look around the table."]
    assert ss.recent_openings("prayer4", spec_dir=directory) == [
        "Rise in spirit at this midnight hour."]
    assert ss.recent_openings("prayer9", spec_dir=directory) == []
    assert ss.recent_openings("prayer5", limit=1, spec_dir=directory) == [
        "Gather your home in faith."]
    assert ss.recent_openings("prayer5", spec_dir=tmp_path / "missing") == []


def test_used_openings_are_shown_to_the_model():
    used = ["Gather your home in faith.", "Before supper, look around the table."]
    prompt = ss.build_prompt("Psalm 128:1-4", channel_id="prayer5", avoid_openings=used)
    for line in used:
        assert f'"{line}"' in prompt
    assert "or with their first three words" in prompt
    bare = ss.build_prompt("Psalm 128:1-4", channel_id="prayer5", avoid_openings=[])
    assert "already opened Shorts" not in bare


def test_a_broken_spec_folder_never_stops_a_short_being_written(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("disk")

    monkeypatch.setattr(ss, "recent_openings", boom)
    prompt = ss.build_prompt("Psalm 128:1-4", channel_id="prayer5")
    assert "THE OPENING SENTENCE" in prompt and "already opened Shorts" not in prompt


def test_the_committed_specs_show_why_this_exists():
    """Every channel with Shorts has openings to show; none crashes on real data."""
    for channel in CHANNELS:
        found = ss.recent_openings(channel)
        assert len(found) <= ss.RECENT_OPENINGS_SHOWN
        assert all(isinstance(o, str) and o for o in found)
