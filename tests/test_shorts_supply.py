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


def test_the_short_key_copy_agrees_with_the_real_derivation():
    """`shorts_supply` re-derives Short keys so it can run with nothing installed.

    A silent drift between the copy and `gemini_brain.short_key_for_doc` would make
    the reading optimistic or pessimistic without anyone noticing, so it is checked
    against every long-form in the queue.
    """
    from pipeline.gemini_brain import short_key_for_doc
    from pipeline.script_doc import parse_script

    checked = 0
    for path in sorted(sup.QUEUE_DIR.glob("*.md")):
        doc = parse_script(path)
        expected = short_key_for_doc(doc)
        actual = sup.short_key_from_parts(
            doc.channel, str(doc.title or ""), slug=str(doc.slug or ""),
            doc_id=str(doc.id))
        assert actual == expected, f"{doc.id}: {actual} != {expected}"
        checked += 1
    assert checked, "expected queued long-forms to check against"


def test_the_ready_count_agrees_with_the_release_module():
    from pipeline.channels import scheduled_channels
    from pipeline.short_release import count_ready_shorts

    for cid in scheduled_channels():
        assert sup._ready_count(cid) == count_ready_shorts(channel_id=cid), cid


def test_the_reading_runs_without_third_party_packages():
    """The daily growth job installs nothing, so importing this module must not."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(sup.__file__).resolve().parents[1]
    blocker = Path(__file__).resolve().parent / "_no_yaml"
    blocker.mkdir(exist_ok=True)
    (blocker / "yaml.py").write_text('raise ImportError("PyYAML is not installed")\n')
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pipeline.shorts_supply", "--json"],
            cwd=root, capture_output=True, text=True, timeout=300,
            env={"PYTHONPATH": str(blocker), "PATH": "/usr/bin:/bin"},
        )
    finally:
        (blocker / "yaml.py").unlink(missing_ok=True)
        try:
            blocker.rmdir()
        except OSError:
            pass
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout)["channels"]
