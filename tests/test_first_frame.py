"""What the first frame of a Short is, and the claim it must not make.

The audit exists because six in ten plays end before the count of a play has
finished — 1,739 engaged views of 4,336 plays, measured 25 November 2026 — and
every instrument in the repository was measuring what happened afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import first_frame as ff


def spec(*, kicker="UNCLENCH YOUR HANDS", sub="BEFORE YOU SLEEP", kinetic=True,
         channel="secret-place", caption_end=8):
    return {
        "channel": channel,
        "captions": [[0, caption_end, "Rest your head upon your pillow."]],
        "scenes": [{"kicker": kicker, "sub": sub, "a": "line", "img": "x.jpg"}],
        "kinetic_phrases": [[0, caption_end, ["REST YOUR HEAD", "NEVER ALONE"], ["REST"], "BEDTIME"]] if kinetic else [],
    }


def test_a_need_kicker_is_not_a_reference():
    frame = ff.first_frame(spec())
    assert frame["kicker_is_reference"] is False
    assert frame["kicker"] == "UNCLENCH YOUR HANDS"
    assert frame["kinetic_lines"] == ["REST YOUR HEAD", "NEVER ALONE"]


@pytest.mark.parametrize("kicker", ["PSALM 91:11", "PSALMS 23", "1 JOHN 4:18",
                                    "HOSEA SIX ONE", "NEHEMIAH TWO FOUR"])
def test_a_citation_on_the_first_frame_is_counted(kicker):
    """The authoring prompt forbids this here. 420 of 634 specs shipped with it."""
    assert ff.first_frame(spec(kicker=kicker))["kicker_is_reference"] is True


def test_every_word_a_stranger_must_read_is_counted():
    frame = ff.first_frame(spec())
    # UNCLENCH YOUR HANDS (3) + BEFORE YOU SLEEP (3) + REST YOUR HEAD (3) +
    # NEVER ALONE (2) = 11
    assert frame["words_on_frame_one"] == 11


def test_the_composition_is_what_the_renderer_draws():
    with_kinetic = ff.build_audit([("a", spec())])
    without = ff.build_audit([("b", spec(kinetic=False))])
    assert with_kinetic["compositions"]["kicker + sub + kinetic"] == 1
    assert without["compositions"]["kicker + sub"] == 1


def test_the_audit_reports_the_real_repository():
    audit = ff.build_audit()
    assert audit["specs"] >= 500
    # Every frame is the same composition. That is the finding, not a bug.
    assert audit["compositions"]["kicker + sub + kinetic"] == audit["specs"]
    assert audit["first_frames_with_a_reference"] > 0
    assert audit["median_words_on_frame_one"] >= 5


def test_the_audit_says_what_it_cannot_conclude():
    audit = ff.build_audit()
    assert audit["not_claimed"], "a reading with no limit is a claim"
    assert "Twelve Shorts" in audit["not_claimed"][0]
    assert "engaged" not in json.dumps(audit["not_claimed"]).lower()


def test_a_citation_cannot_be_authored_again_however_it_is_spelled():
    """The existing guard caught 418 of 420; the two it missed were spelled out."""
    from pipeline.short_script import VERSE_KICKER_RE

    assert VERSE_KICKER_RE.search("1 JOHN 4:18")
    for spelled in ("PSALM 91:11", "HOSEA SIX ONE", "NEHEMIAH TWO FOUR", "LAMENTATIONS THREE TWENTY-TWO"):
        assert VERSE_KICKER_RE.search(spelled), spelled
    for need in ("UNCLENCH YOUR HANDS", "BEFORE YOU SLEEP", "HEAR HIS VOICE"):
        assert not VERSE_KICKER_RE.search(need), need


def test_the_audit_is_written_where_the_other_readings_are(tmp_path):
    out = ff.write_audit(tmp_path / "first_frame.json", {"schema": 1, "specs": 0,
                                                        "findings": [], "note": "empty"})
    assert json.loads(Path(out).read_text())["specs"] == 0


def test_headline_says_the_number_not_a_mood():
    audit = ff.build_audit()
    line = ff.headline(audit)
    assert str(audit["first_frames_with_a_reference"]) in line
    assert str(audit["specs"]) in line
