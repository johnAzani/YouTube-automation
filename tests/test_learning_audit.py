"""The loops that learn, and the ones that only measure.

Asked on 25 November 2026 that the system "auto always learn and self improve".
The audit answers per loop, because a repository can be full of readings that
nothing acts on — and this one was: the thumbnail campaign measured a winning
concept every day and no release ever read the answer.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

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


def test_a_measured_leader_is_not_acting_until_a_release_uses_it():
    """Wiring the loop is not the loop closing.

    On 25 November 2026 the audit was changed to this rule within an hour of the
    campaign becoming readable: until a Short actually goes out on the leader's
    concept, "acting" would be a claim about code that has never run.
    """
    loop = audit._thumbnail_choice()
    assert loop["state"] in {"measuring", "unwired", "acting"}
    if loop["leader"] and loop["state"] == "acting":
        assert audit._adopted_release(), "acting requires a receipt naming the leader"


def test_the_first_frame_loop_does_not_hide_the_citation_split():
    """A citation is not a second composition, and the audit must not let it pass.

    434 of 641 Shorts opened on a citation while the audit said "one composition
    across 639", which reads as though nothing had been varied at all.
    """
    loop = audit._first_frame()
    assert loop["loop"] == "first_frame_composition"
    if loop.get("compositions") == 1:
        assert "citation" in loop["evidence"], (
            "with one composition the citation-versus-need split is the only "
            "variable in the repository and has to be named")


class TestAReadingWithNoAgeCannotBeTrusted(unittest.TestCase):
    """Four of the five readings carried no timestamp on 26 November 2026.

    A stale reading and a fresh one were indistinguishable, so an `acting` verdict
    could rest on a file nobody had refreshed for a month —
    `channel_intelligence.json` had been frozen since 29 October while the docs
    still described it as the brain's input.
    """

    def _write(self, payload: str):
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                             encoding="utf-8")
        handle.write(payload)
        handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_a_file_with_no_timestamp_is_not_assumed_fresh(self):
        path = self._write('{"specs": 3}')
        age = audit.reading_age(path)
        self.assertTrue(age["stale"])
        self.assertIsNone(age["age_hours"])
        self.assertIn("no timestamp", age["why"])

    def test_an_old_reading_is_called_old(self):
        from datetime import datetime, timedelta, timezone

        stamp = (datetime.now(timezone.utc) - timedelta(days=4)).isoformat()
        age = audit.reading_age(self._write(json.dumps({"generated_at": stamp})))
        self.assertTrue(age["stale"])
        self.assertGreater(age["age_hours"], audit.MAX_READING_AGE_HOURS)

    def test_a_fresh_reading_is_fresh(self):
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).isoformat()
        age = audit.reading_age(self._write(json.dumps({"generated_at": stamp})))
        self.assertFalse(age["stale"], age)

    def test_the_audit_reports_the_age_of_the_evidence_it_used(self):
        """The first version looked for `growth_score` instead of
        `growth_score.json`, so every reading looked stamp-less and stale — a check
        that can only ever shout has the same value as one that never does."""
        report = audit.build_audit()
        self.assertTrue(report["evidence"])
        for name, age in report["evidence"].items():
            self.assertIn("stale", age, name)
        self.assertIn("growth_score", report["evidence"])
        self.assertFalse(report["evidence"]["growth_score"]["stale"])
