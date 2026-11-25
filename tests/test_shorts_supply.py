"""Every way a channel can make its next Short, counted before it runs out.

The failure that prompted this: the daily CI went red because one channel held a
single ready Short, and the reason took three separate queries to find — one
channel had no standalone passage left, another had no companion long-form left,
and a third had both. A single number cannot say that; this reading can.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline import shorts_supply as sup


def test_every_scheduled_channel_is_measured():
    from pipeline.channels import scheduled_channels

    report = sup.build_report()
    assert [r["channel"] for r in report["channels"]] == list(scheduled_channels())
    assert report["ready_floor"] == 2


def test_a_channel_with_sources_but_no_ready_shorts_is_authorable_not_dry():
    """`prayer2` on 25 November 2026: zero ready, eleven passages, so not dry."""
    row = sup.measure("prayer2")
    assert row["standalone_passages"] >= 1 or row["companion_longforms"] >= 1
    assert row["verdict"] in {"can author", "enough"}


def test_the_reading_names_the_binding_constraint():
    report = sup.build_report()
    for row in report["channels"]:
        assert row["binding"], row
        if row["verdict"] == "dry":
            assert row["sources"] == 0
            assert "cannot make another Short" in row["binding"]


def test_the_sentence_is_about_the_channels_not_about_nothing():
    report = sup.build_report()
    sentence = report["sentence"]
    assert sentence.endswith(".")
    assert "ready Shorts" in sentence


def test_a_dry_channel_is_reported_in_the_sentence_not_hidden():
    """The whole point of the file is that an empty pool is stated plainly."""
    assert "cannot make another Short" in sup._sentence(["x", "y"], ["y"])
    assert "passages to author from" in sup._sentence(["x"], [])


def test_the_report_says_what_it_does_not_claim():
    report = sup.build_report()
    assert report["not_claimed"]
    assert "views" in report["not_claimed"][0]


def test_it_writes_where_the_other_readings_are(tmp_path):
    out = sup.write_report(tmp_path / "shorts_supply.json",
                           {"schema": 1, "channels": [], "sentence": ".", "not_claimed": []})
    assert json.loads(Path(out).read_text())["schema"] == 1


def test_a_companion_is_only_counted_before_its_short_exists():
    """A queued long-form whose Short is already written is not a source."""
    rows = sup._companion_left("secret-place")
    from pipeline.gemini_brain import short_key_for_doc
    from pipeline.short_release import resolve_edition
    from pipeline.script_doc import parse_script

    for row in rows:
        found = [p for p in (sup.QUEUE_DIR).glob(f"{row['id']}*.md")]
        assert found, row
        doc = parse_script(found[0])
        edition = resolve_edition(short_key_for_doc(doc))
        if edition:
            assert not (sup.PUBLISHED_DIR / f"{edition.slug}.md").is_file()
