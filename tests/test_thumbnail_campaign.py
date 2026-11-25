"""Which thumbnail concept earns the click: the rotation and the reading.

Held fixed: the rotation is deterministic and uses all three concepts; a receipt
that never recorded a concept is not guessed at; a concept under the impression
floor is shown and not trusted; and the design states plainly that a per-video
Test & Compare cannot be opened or read from the Data API.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import thumbnail_campaign as campaign


def test_the_rotation_is_deterministic():
    assert campaign.sequence_for("0027") == campaign.sequence_for("0027")
    assert campaign.concept_for("0027") == campaign.concept_for("0027")


def test_the_rotation_uses_every_concept():
    """A rotation that never shows the poster tests nothing about it."""
    seen = {campaign.concept_for(f"{job:04d}") for job in range(40)}
    assert seen == set(campaign.CONCEPTS)


def test_each_sequence_is_a_full_rotation():
    for job in range(20):
        sequence = campaign.sequence_for(f"{job:04d}")
        assert sorted(sequence) == ["A", "B", "B", "C"]


def test_letters_map_to_the_packs_own_labels():
    assert campaign.letter_to_concept("A") == "hook"
    assert campaign.letter_to_concept("B") == "quiet"
    assert campaign.letter_to_concept("C") == "poster"
    assert campaign.letter_to_concept("Z") == "hook"   # never an exception in a render


def test_a_receipt_without_a_concept_is_not_guessed_at(tmp_path):
    (tmp_path / "0027-old.md").write_text(
        "---\ntitle: Old prayer\nformat: longform\nyoutube_video_id: abcdefghijk\n"
        "thumbnail_revision: ctr-v3-cinema\n---\nbody\n", encoding="utf-8")
    assert campaign.read_assignments(tmp_path) == {}


def test_a_receipt_with_a_concept_is_read(tmp_path):
    (tmp_path / "0028-new.md").write_text(
        "---\ntitle: New prayer\nformat: longform\nyoutube_video_id: abcdefghijk\n"
        "thumbnail_concept: poster\n---\nbody\n", encoding="utf-8")
    assert campaign.read_assignments(tmp_path) == {"abcdefghijk": "poster"}


def test_a_short_is_never_counted_as_a_long_form_test(tmp_path):
    (tmp_path / "short-foo.md").write_text(
        "---\ntitle: A Short\nformat: short\nyoutube_video_id: abcdefghijk\n"
        "thumbnail_concept: hook\n---\nbody\n", encoding="utf-8")
    assert campaign.read_assignments(tmp_path) == {}


def test_the_campaign_pools_impressions_per_concept():
    assignments = {"a" * 11: "hook", "b" * 11: "hook", "c" * 11: "poster"}
    reach = {"a" * 11: {"impressions": 1000, "clicks": 50, "click_rate_percent": 5.0},
             "b" * 11: {"impressions": 1000, "clicks": 30, "click_rate_percent": 3.0},
             "c" * 11: {"impressions": 900, "clicks": 9, "click_rate_percent": 1.0}}
    report = campaign.build_campaign(assignments, reach)
    by_concept = {row["concept"]: row for row in report["concepts"]}
    assert by_concept["hook"]["impressions"] == 2000
    assert by_concept["hook"]["click_rate_percent"] == 4.0
    assert by_concept["poster"]["click_rate_percent"] == 1.0
    assert report["leader"] == "hook"


def test_a_concept_under_the_floor_is_shown_and_not_trusted():
    assignments = {"a" * 11: "poster"}
    reach = {"a" * 11: {"impressions": 50, "clicks": 25, "click_rate_percent": 50.0}}
    report = campaign.build_campaign(assignments, reach)
    poster = next(row for row in report["concepts"] if row["concept"] == "poster")
    assert poster["click_rate_percent"] == 50.0   # shown
    assert poster["measurable"] is False          # not trusted
    assert report["leader"] is None               # nothing to trust yet


def test_the_report_says_a_per_video_test_is_not_available():
    report = campaign.build_campaign({}, {})
    assert "Test & Compare cannot be opened" in report["note"]
    # The word may appear only in the sentence that says it is not carried.
    text = json.dumps({k: v for k, v in report.items() if k != "privacy"}).lower()
    for forbidden in ("revenue", "earnings", "cpm"):
        assert forbidden not in text
    assert "no revenue" in report["privacy"].lower()


def test_the_prayer_pipeline_uploads_the_rotated_concept_not_always_the_first():
    import inspect

    from pipeline import prayer_pipeline

    source = inspect.getsource(prayer_pipeline.produce)
    # The concept is now decided by `concept_decision`, which returns the measured
    # winner once every concept has cleared the impression floor and the release's
    # own turn in the rotation until then. When this test was written the call was
    # `concept_for(doc.id or doc.slug)` alone — a rotation no measurement could
    # reach, which is why the campaign's leader was never adopted.
    assert "concept_decision(doc.id or doc.slug)" in source
    assert 'concept = decision["concept"]' in source
    assert "thumbnail_concept=live_concept" in source
    # the old behaviour: thumbs[0] was both the file uploaded and the receipt's claim
    assert "upload(doc, final, thumbs[0]" in source
    assert "thumbs = [chosen.path] + [r.path for r in thumb_reports if r is not chosen]" in source


def test_the_receipt_carries_the_concept_only_when_the_upload_was_new():
    import inspect

    from pipeline import run

    assert "thumbnail_concept" in inspect.signature(run._mark_job_uploaded).parameters
    source = inspect.getsource(run._mark_job_uploaded)
    assert 'stamped.append(("thumbnail_concept", thumbnail_concept))' in source
    assert 'doc.meta["thumbnail_concept"] = thumbnail_concept' in source


def test_the_workflow_reads_the_campaign_without_a_credential():
    import yaml

    path = Path(__file__).resolve().parents[1] / ".github/workflows/thumbnail-campaign.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = data["jobs"]["campaign"]
    steps = " ".join(str(step.get("run", "")) for step in job["steps"])
    assert "pipeline.thumbnail_campaign" in steps
    assert "secrets." not in path.read_text(encoding="utf-8")
