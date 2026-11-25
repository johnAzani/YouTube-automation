"""Moving a citation off a queued Short's first frame, without authoring anything.

The audit found 26 queued Shorts opening on a citation. The words were already
written; one line was in the wrong place. This repair moves an existing line and
refuses to invent one — a repair that writes new copy is authoring, and a module
that did both could not be checked.
"""
from __future__ import annotations

import json

from pipeline import first_frame as ff
from pipeline import first_frame_repair as repair


def spec(*, kicker="PSALM 91:11", sub="BEFORE YOU SLEEP", line="WHEN THE NIGHT IS LONG",
         verse_scene="Psalm 91:11"):
    return {
        "channel": "secret-place",
        "captions": [[0, 6, "The night is long tonight."],
                     [6, 13, "He shall give his angels charge over thee."]],
        "scenes": [
            {"kicker": kicker, "sub": sub, "a": "The night is long tonight.", "img": "a.jpg"},
            {"kicker": "ANGELS CHARGE", "sub": "HE KEEPS YOU", "a": verse_scene, "img": "b.jpg"},
        ],
        "kinetic_phrases": [[0, 6, [line], ["NIGHT"], "PSALM 91:11"],
                            [6, 13, ["HE KEEPS YOU"], ["KEEPS"], "PSALM 91:11"]],
    }


def test_a_need_first_frame_is_left_alone():
    decision = repair.plan(spec(kicker="BEFORE YOU SLEEP"))
    assert decision["action"] == "none"


def test_the_sub_line_is_promoted_when_it_fits():
    decision = repair.plan(spec())
    assert decision["action"] == "promote"
    assert decision["new_kicker"] == "BEFORE YOU SLEEP"
    assert decision["from"] == "sub"


def test_the_kinetic_line_is_used_when_the_sub_does_not_fit():
    decision = repair.plan(spec(sub="A VERY LONG SUB LINE THAT CANNOT BE THE KICKER AT ALL"))
    assert decision["action"] == "promote"
    assert decision["from"] == "kinetic"
    assert decision["new_kicker"] == "WHEN THE NIGHT IS LONG"


def test_no_existing_line_means_no_repair():
    """REFUSAL IS THE FEATURE: an invented line would be unreviewable copy."""
    decision = repair.plan(
        spec(sub="A VERY LONG SUB LINE THAT CANNOT BE THE KICKER AT ALL",
             line="ANOTHER LINE THAT IS ALSO MUCH TOO LONG FOR THE KICKER SLOT"))
    assert decision["action"] == "keep"
    assert decision["reason"] == "no need line to promote"


def test_a_line_that_is_itself_a_citation_is_never_promoted():
    decision = repair.plan(spec(sub="PSALM 23:1", line="PSALM 46:1"))
    assert decision["action"] == "keep"


def test_a_channel_name_is_never_promoted_onto_the_first_frame():
    decision = repair.plan(spec(sub="THE SECRET PLACE", line=""))
    assert decision["action"] == "keep"


def test_a_truncated_fragment_is_not_promoted():
    decision = repair.plan(spec(sub="STANDING IN THE", line=""))
    assert decision["action"] == "keep"


def test_the_citation_moves_to_the_scene_that_reads_the_verse():
    repaired = repair.apply(spec(), repair.plan(spec()))
    assert ff.first_frame(repaired)["kicker_is_reference"] is False
    assert repaired["scenes"][1]["kicker"] == "PSALM 91 : 11" or \
           repaired["scenes"][1]["kicker"] == "PSALM 91:11"


def test_the_repair_is_recorded_on_the_spec():
    repaired = repair.apply(spec(), repair.plan(spec()))
    record = repaired[repair.REPAIR_FIELD]
    assert record["moved"] == "PSALM 91:11"
    assert record["to"] == "BEFORE YOU SLEEP"
    assert "need" in record["why"]


def test_the_original_spec_is_not_mutated():
    original = spec()
    before = json.dumps(original, sort_keys=True)
    repair.apply(original, repair.plan(original))
    assert json.dumps(original, sort_keys=True) == before


def test_a_published_short_is_kept_as_the_control():
    """456 published Shorts open on a citation. Rewriting them would delete the
    experiment the need-first frames are supposed to be compared against."""
    published = repair.audit(include_published=False)
    assert published["citation_first_control"] >= 1
    control = [row for row in published["rows"] if row["action"] == "control"]
    assert control, "the published archive must be held as the control"
    assert all(row["published"] for row in control)
    assert "control" in control[0]["reason"]


def test_the_repository_state_is_reported_honestly():
    report = repair.audit()
    assert report["specs_examined"] >= 600
    assert report["citation_frames"] == (report["promotable"] + report["no_need_line"]
                                         + report["citation_first_control"])
    assert report["not_claimed"], "a repair with no stated limit is a claim"


def test_a_repaired_repository_spec_still_validates():
    """The repair must not break a real spec the renderer has to accept.

    Built on a repository spec rather than a fixture: the point is that the
    rewrite keeps every field `short_script.require_valid` insists on.
    """
    from pathlib import Path

    from pipeline.short_script import require_valid, validate_spec

    folder = Path(ff.SPEC_DIR)
    repaired = [json.loads(path.read_text()) for path in folder.glob("*.json")
                if repair.REPAIR_FIELD in json.loads(path.read_text())]
    assert repaired, "expected at least one repaired spec in the repository"
    for data in repaired:
        require_valid(validate_spec(data))
