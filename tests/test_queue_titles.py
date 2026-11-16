"""Queued titles the gate would refuse must not publish as they stand.

Measured 16 November 2026, the day the variety gate landed
(``pipeline/title_variety.py``): the queue already held titles written before it
existed. 13 queued long-forms across six channels failed it — five on The Guided
Path opened with "When" (six of its last eight need-first titles did), two on The
Morning Altar, two on The Midday Watch, and one each on The Midnight Watch, The
Provision Table and The Praise Garden, the last three wording a need almost
exactly as another channel does. ``pipeline/queue_titles.py`` finds them and
rewrites them through the same gate-checked path the retitler uses. These tests
pin that the rewrite can never put back a title the gate refuses, that the
fact-check worksheet a queued script is bound to is rebuilt, and that a box a
human has already ticked survives it.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import queue_titles, retitle, title_variety
from scripts import channel_protection as cp
from scripts import factcheck
from scripts import retitle_queue as cli

PATH = "The Guided Path"
ALTAR = "The Morning Altar"


def _queued(folder: Path, name: str, title: str, channel: str = "prayer10", *,
            status: str = "approved", niche: str = "faith and prayer",
            reference: str = "Psalm 4:8", scene: str = "Lord, hear us tonight.",
            extra: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(
        "---\n"
        f'id: "{name[:4]}"\n'
        f"title: {json.dumps(title)}\n"
        f"slug: {name}\n"
        "format: longform\n"
        f"niche: {niche}\n"
        f"channel: {channel}\n"
        f"status: {status}\n"
        "privacy: public\n"
        + extra
        + "---\n\n"
        f"## Scene 1\n{scene}\n",
        encoding="utf-8")
    return path


def _published(folder: Path, name: str, title: str, channel: str = "prayer10",
               day: str = "2026-11-02") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(
        "---\n"
        f'id: "{name[:4]}"\n'
        f"title: {json.dumps(title)}\n"
        f"slug: {name}\n"
        "format: longform\n"
        "niche: faith and prayer\n"
        f"channel: {channel}\n"
        f'published_at: "{day}T06:00:00Z"\n'
        'youtube_video_id: "AAAAAAAAAAA"\n'
        "---\n\n## Scene 1\nLord, hear us.\n",
        encoding="utf-8")
    return path


def _three_when_titles(published: Path) -> None:
    """Three need-first titles that open with "When": a habit, by the repository's mark."""
    for number, need in enumerate(("When the Night Feels Long", "When Worry Won't Settle",
                                   "When Sleep Will Not Come")):
        _published(published, f"080{number}-live", f"{need}: Psalm 4:{number + 1}",
                   day=f"2026-11-0{number + 1}")


# --------------------------------------------------------------------------- #
# The audit
# --------------------------------------------------------------------------- #
def test_a_queued_title_that_reads_like_the_others_is_found(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    tired = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    other = _queued(queue, "0811-q", "Prayer for a Quiet Heart: Psalm 4:8")

    found = queue_titles.failing("prayer10", published_dir=published, queue_dir=queue)
    assert [f.job_id for f in found] == ["0810"]
    assert tired.exists() and other.exists()
    assert "open with 'When'" in found[0].problems[0]
    # Judged without itself: three of the channel's last four, not four of four.
    assert "3 of this channel's last 4" in found[0].problems[0]


def test_a_queued_title_of_its_own_is_left_alone(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _queued(queue, "0810-q", "Prayer for a Quiet Heart: Psalm 4:8")
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_the_old_form_is_the_retitlers_work_not_this_modules(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _queued(queue, "0810-q", "Psalm 4:8 Evening Prayer | The Guided Path")
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_only_this_channels_queued_titles_are_audited(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)                       # The Guided Path's habit
    for number, need in enumerate(("When the Coffee Goes Cold",
                                   "When the Inbox Is Full",
                                   "When the Afternoon Drags")):
        _published(published, f"007{number}-live", f"{need}: Psalm 4:{number + 1}",
                   channel="prayer2", day=f"2026-11-0{number + 1}")
    _queued(queue, "0810-q", "Prayer for a Quiet Heart: Psalm 4:8")
    _queued(queue, "0072-q", "When the Day Begins Wrong: Psalm 4:8", channel="prayer2")

    assert [f.job_id for f in queue_titles.failing("prayer2", published_dir=published,
                                                   queue_dir=queue)] == ["0072"]
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_only_approved_faith_longforms_are_audited(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8", status="draft")
    _queued(queue, "0811-q", "When the Dark Feels Heavy: Psalm 4:8", niche="finance")
    _queued(queue, "0812-q", "When the Dark Feels Heavy: Psalm 4:8", status="quota_paused")
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_a_title_with_no_verifiable_reference_is_left_alone(tmp_path):
    """Without a passage the rewrite could keep word for word, nothing is changed."""
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _queued(queue, "0810-q", "When the Dark Feels Heavy: Nephi 3:16")
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_a_need_worded_as_another_channel_words_one_is_found(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _published(published, "0090-live", "When the Path Ahead Is Blocked: Isaiah 45:2-3",
               channel="prayer7", day="2026-11-01")
    _queued(queue, "0219-q", "When the Path Ahead Is Twisted: Isaiah 45:2-3",
            channel="prayer4")
    found = queue_titles.failing("prayer4", published_dir=published, queue_dir=queue)
    assert [f.job_id for f in found] == ["0219"]
    assert "already in use" in found[0].problems[0]


# --------------------------------------------------------------------------- #
# The rewrite
# --------------------------------------------------------------------------- #
def test_apply_stamps_the_new_title_and_keeps_the_old_one(tmp_path):
    queue = tmp_path / "queue"
    path = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    before = path.read_text(encoding="utf-8")
    assert queue_titles.apply(path, "Prayer for a Heavy Night: Psalm 4:8",
                              today=date(2026, 11, 16)) == "stamped"
    text = path.read_text(encoding="utf-8")
    assert "Prayer for a Heavy Night: Psalm 4:8" in text
    assert 'title_before: "When the Dark Feels Heavy: Psalm 4:8"' in text
    assert 'queue_title_fixed_at: "2026-11-16"' in text
    assert "## Scene 1" in text, "the script itself is untouched"
    assert before != text


def test_apply_restores_the_script_when_the_edit_does_not_read_back(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    path = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    original = path.read_text(encoding="utf-8")
    from scripts import sync_published_thumbnails as stamping

    real = stamping.stamp_frontmatter_field
    calls = {"n": 0}

    def flaky(target, key, value, raw=False):
        calls["n"] += 1
        if calls["n"] == 2:            # the title_before stamp fails
            raise OSError("disk said no")
        return real(target, key, value, raw)

    monkeypatch.setattr(stamping, "stamp_frontmatter_field", flaky)
    outcome = queue_titles.apply(path, "Prayer for a Heavy Night: Psalm 4:8")
    assert outcome.startswith("not stamped")
    assert path.read_text(encoding="utf-8") == original, "the script is left as it was"


def test_the_worksheet_is_rebuilt_and_keeps_the_human_ticks(tmp_path, monkeypatch):
    queue, factcheck_dir = tmp_path / "queue", tmp_path / "factcheck"
    factcheck_dir.mkdir()
    monkeypatch.setattr(factcheck, "OUT_DIR", factcheck_dir)
    path = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8",
                   scene="In the year two thousand and eight the LORD delivered us.")
    first = queue_titles.refresh_worksheet(path)
    assert first is not None and "two thousand and eight" in first.read_text(encoding="utf-8")
    # A human ticks the one box the extractor flagged.
    ticked = first.read_text(encoding="utf-8").replace(
        "- [ ] In the year two thousand and eight the LORD delivered us.",
        "- [x] In the year two thousand and eight the LORD delivered us.", 1)
    first.write_text(ticked, encoding="utf-8")
    assert queue_titles.has_human_ticks(ticked)

    assert queue_titles.apply(path, "Prayer for a Heavy Night: Psalm 4:8") == "stamped"
    second = queue_titles.refresh_worksheet(path)
    text = second.read_text(encoding="utf-8")
    assert "Prayer for a Heavy Night" in text, "the worksheet names the new title"
    assert factcheck._sha(path) in text, "the binding hash is the new file's"
    assert "- [x] In the year two thousand and eight the LORD delivered us." in text, \
        "a title moves no claim, so the human's tick survives"
    assert "- [ ] Narration rewritten in my own words" in text, "and so do the sign-off boxes"


def test_a_refused_title_changes_nothing(tmp_path):
    published, queue = _tired_channel(tmp_path)
    path = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    original = path.read_text(encoding="utf-8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps([{
        "file": str(path), "job_id": "0810",
        "old_title": "When the Dark Feels Heavy: Psalm 4:8",
        "new_title": "When the Silence Is Loud: Psalm 4:8",   # still opens with "When"
        "reference": "Psalm 4:8", "problems": [], "date": "2026-11-16",
    }]), encoding="utf-8")
    assert cli.apply(ledger, published_dir=published, queue_dir=queue) == []
    assert path.read_text(encoding="utf-8") == original


def test_an_entry_whose_title_changed_since_is_refused(tmp_path):
    published, queue = _tired_channel(tmp_path)
    path = _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps([{
        "file": str(path), "job_id": "0810", "old_title": "Some Other Title Entirely",
        "new_title": "Prayer for a Heavy Night: Psalm 4:8",
        "reference": "Psalm 4:8", "problems": [], "date": "2026-11-16",
    }]), encoding="utf-8")
    assert cli.apply(ledger, published_dir=published, queue_dir=queue) == []
    assert "When the Dark Feels Heavy" in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #
def _tired_channel(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    _queued(queue, "0810-q", "When the Dark Feels Heavy: Psalm 4:8")
    return published, queue


def test_the_command_accepts_a_persons_proposal_and_refuses_a_bad_one(tmp_path):
    published, queue = _tired_channel(tmp_path)
    ledger = tmp_path / "ledger.json"
    proposals = tmp_path / "proposals.json"
    proposals.write_text(json.dumps({"0810": "When the Silence Is Loud: Psalm 4:8"}),
                         encoding="utf-8")
    assert cli.choose("prayer10", ledger, proposals=proposals,
                      published_dir=published, queue_dir=queue) == []
    assert json.loads(ledger.read_text()) == []

    proposals.write_text(json.dumps({"0810": "Prayer for a Heavy Night: Psalm 4:8"}),
                         encoding="utf-8")
    entries = cli.choose("prayer10", ledger, proposals=proposals,
                         published_dir=published, queue_dir=queue)
    assert [e["new_title"] for e in entries] == ["Prayer for a Heavy Night: Psalm 4:8"]
    assert entries[0]["problems"] and "When" in entries[0]["problems"][0]


def test_the_command_prints_the_paths_it_changed(tmp_path, monkeypatch, capsys):
    published, queue = _tired_channel(tmp_path)
    factcheck_dir = tmp_path / "factcheck"
    factcheck_dir.mkdir()
    monkeypatch.setattr(factcheck, "OUT_DIR", factcheck_dir)
    ledger = tmp_path / "ledger.json"
    entries = cli.choose("prayer10", ledger, ask=lambda prompt: "Prayer for a Heavy Night: Psalm 4:8",
                         published_dir=published, queue_dir=queue)
    assert len(entries) == 1
    capsys.readouterr()

    changed = cli.apply(ledger)
    assert len(changed) == 2, "the script and the worksheet it is bound to"
    assert changed[0].endswith("0810-q.md") and changed[1].endswith("0810-q.md")
    # The queue is clean afterwards.
    assert queue_titles.failing("prayer10", published_dir=published, queue_dir=queue) == []


def test_without_a_model_or_proposals_nothing_is_written(tmp_path, monkeypatch, capsys):
    published, queue = _tired_channel(tmp_path)
    monkeypatch.setattr(cli, "_model_asker", lambda channel_id: None)
    ledger = tmp_path / "ledger.json"
    assert cli.choose("prayer10", ledger, published_dir=published, queue_dir=queue) == []
    assert "no text model is available" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# The daily measure
# --------------------------------------------------------------------------- #
def test_the_daily_measure_counts_the_queued_backlog(tmp_path):
    published, queue = _tired_channel(tmp_path)
    rows = cp.measure(today=None, published_dir=published, queue_dir=queue)
    guided = next(row for row in rows if row.channel == "prayer10")
    assert guided.queued_refused == 1
    report = cp.render(rows)
    assert "Queued titles the gate would refuse" in report
    assert "| The Guided Path | 0 | 4 | 'When' (4) | 0 | 1 |" in report
    assert "1 queued title(s) would be refused by the variety gate today" in report


def test_the_measure_shows_zero_once_the_backlog_is_cleared(tmp_path, monkeypatch):
    published, queue = _tired_channel(tmp_path)
    factcheck_dir = tmp_path / "factcheck"
    factcheck_dir.mkdir()
    monkeypatch.setattr(factcheck, "OUT_DIR", factcheck_dir)
    ledger = tmp_path / "ledger.json"
    cli.choose("prayer10", ledger, ask=lambda prompt: "Prayer for a Heavy Night: Psalm 4:8",
               published_dir=published, queue_dir=queue)
    cli.apply(ledger)
    rows = cp.measure(today=None, published_dir=published, queue_dir=queue)
    guided = next(row for row in rows if row.channel == "prayer10")
    assert guided.queued_refused == 0


def test_the_gate_still_refuses_a_title_that_reads_like_the_others(tmp_path):
    """The rewrite is not a way past the gate: the same check that found the old
    title refuses its replacement."""
    published, queue = tmp_path / "published", tmp_path / "queue"
    _three_when_titles(published)
    variety = queue_titles.variety_without("When the Dark Feels Heavy: Psalm 4:8",
                                           "prayer10", published_dir=published,
                                           queue_dir=queue)
    problems = retitle.title_problems("When the Silence Is Loud: Psalm 4:8", "Psalm 4:8",
                                      PATH, "When the Dark Feels Heavy: Psalm 4:8", variety)
    assert any("open with 'When'" in problem for problem in problems)
    ok = retitle.title_problems("Prayer for a Heavy Night: Psalm 4:8", "Psalm 4:8", PATH,
                                "When the Dark Feels Heavy: Psalm 4:8", variety)
    assert ok == []
