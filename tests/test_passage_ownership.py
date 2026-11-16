"""No two channels may pray the same passage, and the drift must stop growing.

Measured 16 November 2026. The seasonal lists have never given one passage to
two channels — ``pipeline/seasonal.py`` says so and ``tests/test_seasonal.py``
holds it. Nothing ever held the *roadmaps* to the same rule: no test compared
one channel's roadmap with another's, or with what the channels have actually
made. So they drifted. Twenty passages were prayed on more than one channel
(Proverbs 3:5-6, Numbers 6:24-26, Proverbs 16:3, Psalm 37:23 and Philippians
4:6-7 on three channels each), and 104 unwritten roadmap entries still named a
passage another channel had already prayed.

``pipeline/passage_ownership.py`` reads that ledger. ``select_next_scripture``
now steps over a roadmap passage another channel already prays, so the drift
stops growing — on 16 November the next prayer The Midday Watch, The Provision
Table, The Covenant Shield and The Praise Garden would have written was a
passage another channel already prays; all four now write their own instead.

The passages already queued or live are *not* touched here: which channel keeps
one is a content decision for the owner, and the count is what asks for it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline import passage_ownership as po
from pipeline.channel_capabilities import brand_for, known_channels
from pipeline.evergreen_shorts import reference_parts
from pipeline.gemini_brain import GeminiBrain
from scripts import channel_protection as cp

#: A passage the comparer reads the same way it reads a real one.
PSALM_23 = ("psalm", 23, 3)
PROVERBS = ("proverbs", 16, 9)


def _passage(channel: str, reference: str, source: str = "published",
             job: str = "0001") -> po.Passage:
    parts = reference_parts(reference)
    assert parts is not None, reference
    return po.Passage(channel=channel, reference=reference, parts=parts,
                      source=source, job=job, title=f"{reference} Prayer")


# --------------------------------------------------------------------------- #
# The ledger
# --------------------------------------------------------------------------- #
def test_the_ledger_reads_every_place_a_channel_prays_a_passage(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    specs, shorts = tmp_path / "specs", tmp_path / "shorts"
    for folder in (published, queue, specs, shorts):
        folder.mkdir()

    (published / "0001-a.md").write_text(
        "---\nid: \"0001\"\ntitle: \"Psalm 23:3 Prayer | The Guided Path\"\n"
        "format: longform\nniche: faith and prayer\nchannel: prayer10\n"
        "published_at: \"2026-11-02T06:00:00Z\"\n---\n\nLord.\n", encoding="utf-8")
    (queue / "0002-b.md").write_text(
        "---\nid: \"0002\"\ntitle: \"Proverbs 16:9 Prayer | The Morning Altar\"\n"
        "format: longform\nniche: faith and prayer\nchannel: prayer2\n"
        "status: approved\n---\n\nLord.\n", encoding="utf-8")
    (published / "short-abc.md").write_text(
        "---\ntitle: \"Pray This Psalm 91:6 Prayer | The Secret Place\"\n"
        "format: short\nchannel: secret-place\n---\n\nLord.\n", encoding="utf-8")
    (specs / "short-def.json").write_text(
        '{"channel": "prayer2", "scripture": "Psalm 27:11", "key": "short-def"}',
        encoding="utf-8")
    (shorts / "short-ghi.yml").write_text(
        "channel: prayer10\nscripture: Isaiah 30:21\nkey: short-ghi\n", encoding="utf-8")

    rows = po.passages(published_dir=published, queue_dir=queue, spec_dir=specs,
                       shorts_queue_dir=shorts)
    found = {(row.channel, row.source, row.parts) for row in rows}
    assert ("prayer10", "published", PSALM_23) in found
    assert ("prayer2", "queued", PROVERBS) in found
    assert ("secret-place", "short published", ("psalm", 91, 6)) in found
    assert ("prayer2", "short spec", ("psalm", 27, 11)) in found
    assert ("prayer10", "short queued", ("isaiah", 30, 21)) in found
    # A channel's own passages are not "elsewhere".
    assert po.prayed_elsewhere("prayer10", rows=rows) == {
        PROVERBS, ("psalm", 91, 6), ("psalm", 27, 11)}


def test_a_long_form_without_a_channel_is_the_first_channels(tmp_path):
    """An old receipt names no channel, exactly as ``read_receipts`` finds it."""
    published = tmp_path / "published"
    published.mkdir()
    (published / "0009-old.md").write_text(
        "---\nid: \"0009\"\ntitle: \"Psalm 23:3 Night Prayer | The Secret Place\"\n"
        "format: longform\nniche: faith and prayer\n"
        "published_at: \"2026-11-02T06:00:00Z\"\n---\n\nLord.\n", encoding="utf-8")
    rows = po.passages(published_dir=published, queue_dir=tmp_path / "none",
                       spec_dir=tmp_path / "none", shorts_queue_dir=tmp_path / "none")
    assert [row.channel for row in rows] == ["secret-place"]


def test_a_whole_chapter_is_the_same_passage_as_one_of_its_verses():
    """``Psalm 91`` and ``Psalm 91:6`` are one prayer to a listener."""
    assert po.passages and reference_parts("Psalm 91") == ("psalm", 91, None)
    whole, verse = reference_parts("Psalm 91"), reference_parts("Psalm 91:6")
    from pipeline.evergreen_shorts import same_passage
    assert same_passage(whole, verse)


# --------------------------------------------------------------------------- #
# The overlaps
# --------------------------------------------------------------------------- #
def test_a_channel_finds_the_videos_of_a_passage_another_channel_prays():
    rows = [_passage("prayer10", "Psalm 23:3"), _passage("prayer2", "Psalm 23:3"),
            _passage("prayer10", "Psalm 4:8")]
    assert [row.channel for row in po.overlaps("prayer10", rows=rows)] == ["prayer10"]
    assert po.overlaps("prayer2", rows=rows)[0].parts == PSALM_23
    # A passage only this channel has is not an overlap.
    assert [row.parts for row in po.overlaps("prayer10", rows=rows)] == [PSALM_23]


def test_one_channel_alone_has_no_overlap():
    rows = [_passage("prayer10", "Psalm 23:3"), _passage("prayer10", "Psalm 4:8")]
    assert po.overlaps("prayer10", rows=rows) == []
    assert po.prayed_elsewhere("prayer10", rows=rows) == set()


# --------------------------------------------------------------------------- #
# The step-over
# --------------------------------------------------------------------------- #
def test_the_channels_own_passages_come_first_and_keep_their_order():
    rows = [_passage("prayer2", "Psalm 23:3")]
    ahead = [{"id": "0816", "scripture": "Psalm 23:3"},
             {"id": "0801", "scripture": "James 1:5"},
             {"id": "0802", "scripture": "Psalm 25:4-5"},
             {"id": "0820", "scripture": "Psalm 27:11"}]
    own, shared = po.own_first(ahead, "prayer10", rows=rows)
    assert [row["id"] for row in own] == ["0801", "0802", "0820"]
    assert [row["id"] for row in shared] == ["0816"]


def test_a_channel_whose_list_is_clean_is_untouched():
    ahead = [{"id": "0801", "scripture": "James 1:5"},
             {"id": "0802", "scripture": "Psalm 25:4-5"}]
    own, shared = po.own_first(ahead, "prayer10", rows=[])
    assert own == ahead and shared == []


def test_nothing_unique_left_means_the_shared_passage_is_still_written():
    """The step-over never runs a channel dry: it is a preference, not a gate."""
    rows = [_passage("prayer2", "Psalm 23:3")]
    ahead = [{"id": "0816", "scripture": "Psalm 23:3"}]
    own, shared = po.own_first(ahead, "prayer10", rows=rows)
    assert own == [] and [row["id"] for row in shared] == ["0816"]


# --------------------------------------------------------------------------- #
# The brain
# --------------------------------------------------------------------------- #
@pytest.fixture
def brain_world(tmp_path, monkeypatch):
    """A brain whose queue and published folders are empty and whose roadmap is given."""
    import pipeline.gemini_brain as gb

    (tmp_path / "queue").mkdir()
    (tmp_path / "published").mkdir()
    monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "queue")
    monkeypatch.setattr(gb, "PUBLISHED_DIR", tmp_path / "published")
    # Feedback is an optimisation, never a gate: no artifact, roadmap order kept.
    monkeypatch.setattr("pipeline.performance_feedback.load_feedback_report",
                        lambda *a, **k: None)
    return gb


def _roadmap(*rows: tuple[str, str]) -> list[dict]:
    return [{"id": job, "scripture": scripture, "theme": "Guidance", "hook": "GUIDE"}
            for job, scripture in rows]


def test_the_brain_steps_over_a_passage_another_channel_prays(brain_world, monkeypatch):
    monkeypatch.setattr(brain_world, "roadmap_for_channel",
                        lambda channel: _roadmap(("0816", "Psalm 23:3"),
                                                 ("0801", "James 1:5")))
    monkeypatch.setattr(po, "prayed_elsewhere",
                        lambda channel, **kw: {PSALM_23})

    chosen = brain_world.GeminiBrain(channel_id="prayer10").select_next_scripture()
    assert chosen["scripture"] == "James 1:5"


def test_the_brain_still_writes_the_shared_passage_when_nothing_else_is_left(
        brain_world, monkeypatch):
    monkeypatch.setattr(brain_world, "roadmap_for_channel",
                        lambda channel: _roadmap(("0816", "Psalm 23:3")))
    monkeypatch.setattr(po, "prayed_elsewhere",
                        lambda channel, **kw: {PSALM_23})

    chosen = brain_world.GeminiBrain(channel_id="prayer10").select_next_scripture()
    assert chosen["scripture"] == "Psalm 23:3"


def test_a_clean_roadmap_keeps_its_order(brain_world, monkeypatch):
    monkeypatch.setattr(brain_world, "roadmap_for_channel",
                        lambda channel: _roadmap(("0801", "James 1:5"),
                                                 ("0802", "Psalm 25:4-5")))
    monkeypatch.setattr(po, "prayed_elsewhere", lambda channel, **kw: set())

    chosen = brain_world.GeminiBrain(channel_id="prayer10").select_next_scripture()
    assert chosen["scripture"] == "James 1:5"


def test_the_step_over_is_only_ever_a_step_over(brain_world):
    """Every channel's pick is either its own, or it had none left to write.

    The property that must hold on the repository as it stands, whatever the
    roadmaps have been reduced to: the brain never repeats another channel's
    passage while one of its own is still unwritten. Read against the real
    repository, so the drift is seen the day it starts.
    """
    index = po.ledger(po.passages())
    for channel_id in known_channels():
        brain = brain_world.GeminiBrain(api_key="", channel_id=channel_id)
        chosen = brain.select_next_scripture()
        parts = reference_parts(str(chosen.get("scripture") or ""))
        shared = any(po.same_passage(parts, other)
                     for other in po.prayed_elsewhere(channel_id, index=index))
        ahead = po.roadmap_ahead(channel_id, po.taken_longform_ids())
        own, _ = po.own_first(ahead, channel_id, index=index)
        assert not shared or not own, (
            f"{brand_for(channel_id).display_name} would write "
            f"{chosen['scripture']}, which another channel already prays, with "
            f"{len(own)} of its own passages unwritten")


# --------------------------------------------------------------------------- #
# The daily measure
# --------------------------------------------------------------------------- #
def test_the_daily_measure_counts_the_passages_two_channels_pray(tmp_path, monkeypatch):
    published, queue = tmp_path / "published", tmp_path / "queue"
    published.mkdir()
    queue.mkdir()
    (published / "0800-live.md").write_text(
        "---\nid: \"0800\"\ntitle: \"Psalm 23:3 Guidance Prayer | The Guided Path\"\n"
        "format: longform\nniche: faith and prayer\nchannel: prayer10\n"
        "published_at: \"2026-11-02T06:00:00Z\"\n---\n\nLord.\n", encoding="utf-8")
    (published / "0040-live.md").write_text(
        "---\nid: \"0040\"\ntitle: \"Psalm 23:3 Sunrise Prayer | The Morning Altar\"\n"
        "format: longform\nniche: faith and prayer\nchannel: prayer2\n"
        "published_at: \"2026-11-02T06:00:00Z\"\n---\n\nLord.\n", encoding="utf-8")

    rows = [_passage("prayer10", "Psalm 23:3", job="0800"),
            _passage("prayer2", "Psalm 23:3", job="0040")]
    monkeypatch.setattr(po, "passages", lambda **kw: rows)

    measured = cp.measure(published_dir=published, queue_dir=queue)
    by_channel = {row.channel: row for row in measured}
    assert by_channel["prayer10"].passages_shared == 1
    assert by_channel["prayer2"].passages_shared == 1
    assert by_channel["prayer3"].passages_shared == 0
    # The selector's own choice: never a shared passage while one of its own is left.
    assert all(row.next_prayer_shared == 0 for row in measured)

    report = cp.render(measured)
    assert "Passages prayed on more than one channel" in report
    assert "| The Guided Path | 1 |" in report
    assert "1 video(s) pray a passage another channel already prays" in report


def test_a_channel_forced_onto_a_shared_passage_is_reported(tmp_path, monkeypatch):
    """The one case the step-over cannot avoid, and the report must say so."""
    from scripts.continuous_research import roadmap_for_channel

    published, queue = tmp_path / "published", tmp_path / "queue"
    published.mkdir()
    queue.mkdir()
    # Every passage on every roadmap is already prayed elsewhere, so no channel
    # has anything of its own left to write.
    monkeypatch.setattr(po, "prayed_elsewhere", lambda channel, **kw: {
        reference_parts(str(row["scripture"])) for row in roadmap_for_channel(channel)})
    monkeypatch.setattr(po, "passages", lambda **kw: [])

    measured = cp.measure(published_dir=published, queue_dir=queue)
    forced = [row for row in measured if row.next_prayer_shared]
    assert forced, "a channel with nothing unique left must be reported"
    report = cp.render(measured)
    assert "the next prayer its roadmap would write is of a passage another " \
           "channel already prays" in report


def test_the_repository_itself_holds_the_invariant():
    """Read back on the real repository: no channel repeats a prayed passage."""
    rows = po.passages()
    index = po.ledger(rows)
    shared_passages = {parts for parts, group in _by_passage(rows).items()
                       if len({row.channel for row in group}) > 1}
    for channel_id in known_channels():
        ahead = po.roadmap_ahead(channel_id, po.taken_longform_ids())
        own, shared = po.own_first(ahead, channel_id, index=index)
        if own:
            # With something of its own to write, the next prayer is not shared.
            parts = reference_parts(str(own[0]["scripture"]))
            assert not any(po.same_passage(parts, other)
                           for other in po.prayed_elsewhere(channel_id, index=index)), (
                f"{brand_for(channel_id).display_name} would write "
                f"{own[0]['scripture']}, already prayed on another channel")
        else:
            # Nothing unique left: the count that asks the owner for a decision.
            assert shared, brand_for(channel_id).display_name
    # The 20 already-shared passages are counted, not hidden.
    assert len(shared_passages) >= 20


def _by_passage(rows):
    from collections import defaultdict

    out: dict = defaultdict(list)
    for row in rows:
        out[row.parts].append(row)
    return out


def test_the_roadmap_itself_is_not_rewritten_by_the_measure(tmp_path, monkeypatch):
    """Reading the ledger changes nothing: the entries stay for the owner to assign."""
    rows = [_passage("prayer2", "Psalm 23:3")]
    monkeypatch.setattr(po, "passages", lambda **kw: rows)
    before = po.roadmap_ahead("prayer10", po.taken_longform_ids())
    cp.measure(published_dir=tmp_path / "none", queue_dir=tmp_path / "none")
    assert po.roadmap_ahead("prayer10", po.taken_longform_ids()) == before
