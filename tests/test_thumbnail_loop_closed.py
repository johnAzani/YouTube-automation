"""The campaign measured a winner every day and no release ever read it.

`pipeline/thumbnail_campaign.py` has computed a click rate per concept since it
landed. Until 25 November 2026 the release path called `concept_for(doc.id)` —
a rotation that nothing could influence — so the channels would have rotated
forever and adopted nothing. These tests hold the seam that closes it.
"""
from __future__ import annotations

import pytest

from pipeline import thumbnail_campaign as campaign


def _report(*, hook=1907, quiet=604, poster=412, leader="hook", approved=True):
    rows = []
    for concept, impressions in (("hook", hook), ("quiet", quiet), ("poster", poster)):
        rows.append({"concept": concept, "impressions": impressions,
                     "clicks": max(1, impressions // 40),
                     "measurable": approved, "approved": approved})
    return {"leader": leader, "concepts": rows}


def test_with_no_reading_the_release_still_takes_its_turn():
    decision = campaign.concept_decision("0027", {})
    assert decision["source"] == "rotation"
    assert decision["concept"] == campaign.concept_for("0027")
    assert "nothing to copy" in decision["why"]


def test_a_measured_winner_goes_live_instead_of_the_turn():
    decision = campaign.concept_decision("0027", _report())
    assert decision["source"] == "measured"
    assert decision["concept"] == "hook"


def test_the_rotation_is_what_it_overrides_not_what_it_is():
    """The winner must be able to differ from the release's own turn."""
    turn = {campaign.concept_for(f"{job:04d}") for job in range(40)}
    assert turn == set(campaign.CONCEPTS)
    for job in range(40):
        decision = campaign.concept_decision(f"{job:04d}", _report())
        assert decision["concept"] == "hook"


def test_one_measured_concept_against_two_unmeasured_is_not_a_comparison():
    """Copying the only concept that received traffic is a self-fulfilling choice."""
    report = _report()
    report["concepts"][1]["measurable"] = report["concepts"][1]["approved"] = False
    assert campaign.measured_leader(report) is None
    assert campaign.concept_decision("0027", report)["source"] == "rotation"


def test_a_leader_under_the_impression_floor_is_not_adopted():
    thin = _report(hook=310, quiet=4, poster=3)
    assert campaign.measured_leader(thin) is None
    decision = campaign.concept_decision("0027", thin)
    assert decision["source"] == "rotation"
    assert "impression" in decision["why"], decision["why"]
    assert "quiet" in decision["why"], "the reason must name what is short"


def test_a_report_with_no_leader_keeps_rotating():
    report = _report()
    report["leader"] = None
    assert campaign.measured_leader(report) is None


def test_a_leader_the_report_does_not_list_is_ignored():
    report = _report()
    report["leader"] = "cinematic"
    assert campaign.measured_leader(report) is None


def test_the_decision_says_which_of_the_two_it_did():
    """A receipt that records a concept should also be able to say why."""
    for report in ({}, _report()):
        decision = campaign.concept_decision("0027", report)
        assert decision["source"] in {"measured", "rotation"}
        assert decision["why"]


def test_the_release_path_asks_the_campaign_rather_than_the_rotation():
    import inspect

    from pipeline import prayer_pipeline

    source = inspect.getsource(prayer_pipeline.produce)
    assert "concept_decision(doc.id or doc.slug)" in source
    assert 'concept = decision["concept"]' in source
    # The old call, which no measurement could reach:
    assert "concept = concept_for(doc.id or doc.slug)" not in source


def test_the_rotation_report_still_describes_the_sequence():
    report = campaign.rotation_report("0027")
    assert report["sequence"] and report["concept"] in campaign.CONCEPTS
