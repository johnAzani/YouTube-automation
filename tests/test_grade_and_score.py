"""The colour and the music: whose they are, and what decides them.

Measured on 17 November 2026 (`docs/FRAME_GRADE_AND_SCORE_RESEARCH_2026-11-17.md`):
the still images a channel ships are graded per channel, the frames are not, and
`tools/score.py` builds every video's bed from one progression — its `key`
argument names the file and nothing else. These tests hold the last two facts
still, and pin the rule that decides a Short's plate colour so it cannot drift
back to being an unnamed string test.
"""
from __future__ import annotations

import inspect

import pytest
from PIL import Image

from pipeline.channels import CHANNELS
from pipeline.shorts_poster import _GRADES, grade_for, plate_grade_name
from tools.score import generate_score


def test_each_channel_has_its_own_poster_ramp():
    """Ten channels, ten ramps, and none of them the silent night fallback."""
    grades = {channel: grade_for(channel) for channel in CHANNELS}
    assert len(grades) == 10
    assert len(set(grades.values())) == 10
    # `_background` falls back to the night ramp for an unknown name, so a new
    # channel whose kind is not mapped would wear the night channel's colour in
    # silence. This is the check that fails instead.
    assert set(grades.values()) == set(_GRADES)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("short-psalm91-scene-01.jpg", "sanctuary"),
        ("short-prayer-psalm91-scene-02.jpg", "sanctuary"),
        ("PSALM-23-SCENE-01.JPG", "sanctuary"),
        ("short-1peter5v7-scene-01.jpg", "blue"),
        ("short-john14v1-scene-01.jpg", "blue"),
        ("candle-burning-dark-room.jpg", "blue"),
    ],
)
def test_a_scene_is_graded_by_its_file_name_not_its_channel(name, expected):
    """The rule, named: "psalm"/"prayer" in the name takes the night grade."""
    assert plate_grade_name(name) == expected


def test_prep_plate_grades_through_the_named_rule(tmp_path, monkeypatch):
    """The renderer reads the same rule this repository can count."""
    import tools.shorts as shorts

    seen: list[str] = []

    def sanctuary(image):
        seen.append("sanctuary")
        return image

    def blue(image, **_kwargs):
        seen.append("blue")
        return image

    monkeypatch.setattr(shorts, "grade_sanctuary", sanctuary)
    monkeypatch.setattr(shorts, "grade_blue", blue)
    for name in ("short-psalm91-scene-01.jpg", "short-1peter5v7-scene-01.jpg"):
        path = tmp_path / name
        Image.new("RGB", (400, 700), (90, 96, 104)).save(path)
        shorts.prep_plate(path)

    assert seen == ["sanctuary", "blue"]


def test_the_score_takes_no_channel_and_its_key_only_names_the_file(tmp_path):
    """Two videos, two keys, one piece of music — byte for byte.

    `generate_score(key, …)` writes `music-{key}.wav`; nothing else in it reads
    `key`. Asked for the long-form's key and a Short's key at the same length,
    with the same cuts, hushes and swells, it must produce identical bytes — and
    if that ever stops being true, every channel has stopped sharing one score.
    """
    assert "channel" not in inspect.signature(generate_score).parameters
    cuts = [0.0, 4.0, 8.0]
    hushes = [{"t": 5.0, "dur": 1.0, "depth": 0.55, "lead": 0.45}]
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    generate_score("prayer-longform", 9.0, cuts, [], [], hushes,
                   swell_hits=[6.0], out_dir=first)
    generate_score("sunrise-short", 9.0, cuts, [], [], hushes,
                   swell_hits=[6.0], out_dir=second)

    left = (first / "music-prayer-longform.wav").read_bytes()
    right = (second / "music-sunrise-short.wav").read_bytes()
    assert left == right
    assert len(left) > 1000
