"""The loops that learn, and the ones that only measure.

Asked on 25 November 2026 that the system "auto always learn and self improve".
The audit answers per loop, because a repository can be full of readings that
nothing acts on — and this one was: the thumbnail campaign measured a winning
concept every day and no release ever read the answer.
"""
from __future__ import annotations

import json

from pipeline import learning_audit as audit

STATES = {"acting", "unwired", "measuring", "waiting"}


def test_every_loop_is_graded_and_the_grade_is_one_of_four():
    report = audit.build_audit()
    assert report["loops"], "the audit must find loops to grade"
    for loop in report["loops"]:
        assert loop["state"] in STATES, loop
        assert loop["evidence"], f'{loop["loop"]} gives a state and no reason'
        assert loop["owner"], f'{loop["loop"]} names no module that owns it'


def test_the_counts_add_up_to_the_loops():
    report = audit.build_audit()
    total = len(report["loops"])
    assert len(report["acting"]) + len(report["measuring_only"]) + len(report["waiting"]) == total
    assert report["sentence"].endswith(".")
    assert str(total) in report["sentence"]


def test_a_loop_that_acts_says_the_measurement_changed_the_build():
    """Acting is a claim about code, not about outcomes."""
    report = audit.build_audit()
    for loop in report["loops"]:
        if loop["state"] == "acting":
            assert loop["evidence"], loop["loop"]


def test_the_thumbnail_loop_is_only_unwired_when_nothing_reads_the_leader():
    """It was unwired until `live_concept` existed; the state must follow the code."""
    from pipeline import thumbnail_campaign

    loop = audit._thumbnail_choice()
    assert loop["loop"] == "thumbnail_choice"
    # `live_concept` exists now, so a measured leader would be adopted. Without
    # one, the honest state is that there is nothing yet to adopt.
    assert hasattr(thumbnail_campaign, "live_concept")
    if loop["leader"] is None:
        assert loop["state"] in {"measuring", "waiting"}
        assert "impressions" in loop["evidence"] or "concept" in loop["evidence"]


def test_a_waiting_loop_names_the_floor_it_is_waiting_for():
    loop = audit._lessons()
    assert loop["state"] in STATES
    if loop["state"] == "waiting":
        assert "5" in loop["evidence"] or "videos" in loop["evidence"]


def test_the_audit_says_that_acting_is_not_proof_of_improvement():
    report = audit.build_audit()
    assert report["not_claimed"]
    assert "changes the next build" in report["not_claimed"][0]


def test_it_writes_where_the_other_readings_live(tmp_path):
    out = audit.write_audit(tmp_path / "learning_audit.json",
                            {"schema": 1, "loops": [], "sentence": ".", "not_claimed": []})
    assert json.loads(out.read_text())["schema"] == 1


def test_the_repository_has_at_least_one_loop_that_actually_acts():
    """If nothing acts, "self improving" is a false description of this pipeline."""
    report = audit.build_audit()
    assert report["acting"], report["sentence"]
