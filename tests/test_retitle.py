"""Unwatched long-forms get one need-first title, checked by code, pushed by the existing sync."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from pipeline import retitle
from pipeline.script_doc import parse_script
from scripts import retitle_unwatched as cli

REPO = Path(__file__).resolve().parent.parent
TODAY = date(2026, 11, 14)
OLD = "Psalm 23:5 Provision Prayer | The Provision Table"
GOOD = "Prayer When Money Is Short: Psalm 23:5 | The Provision Table"


def _receipt(directory: Path, name: str, *, title: str = OLD, video_id: str = "AAAAAAAAAAA",
             published: str = "2026-11-01", fmt: str = "longform", channel: str = "prayer7",
             job_id: str = "0500", **extra) -> Path:
    meta = {"id": job_id, "title": title, "slug": name, "status": "published", "channel": channel,
            "format": fmt, "niche": "faith and prayer", "thumb_text": "CUP RUNNETH OVER",
            "seo_hook": "Pray for open doors, favour over honest work, and daily provision.",
            "youtube_video_id": video_id, "published_on": published,
            "published_at": f"{published}T06:00:00Z", "metadata_revision": "selar-seo-v1", **extra}
    path = directory / f"{name}.md"
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n\n## Scene 1\n\nLord, hear us.\n",
                    encoding="utf-8")
    return path


def _views(**by_video) -> list[dict]:
    return [{"video_id": vid, "snapshot_date": TODAY.isoformat(), "views": views}
            for vid, views in by_video.items()]


def _targets(directory, snapshots, channel="prayer7"):
    return retitle.find_targets(channel, snapshots, published_dir=directory, today=TODAY)


# --------------------------------------------------------------------------- #
# Which videos
# --------------------------------------------------------------------------- #
def test_an_old_unwatched_long_form_is_chosen(tmp_path):
    path = _receipt(tmp_path, "0500-psalm-23-5")
    (target,) = _targets(tmp_path, _views(AAAAAAAAAAA=1))
    assert target.path == path and target.reference == "Psalm 23:5"
    assert target.views == 1 and target.age_days == 13


@pytest.mark.parametrize("change, snapshot", [
    ({"published": "2026-11-10"}, {"AAAAAAAAAAA": 0}),                 # four days old
    ({}, {"AAAAAAAAAAA": 3}),                                          # it has an audience
    ({}, {"BBBBBBBBBBB": 0}),                                          # no reading for it
    ({"retitled_at": "2026-11-08"}, {"AAAAAAAAAAA": 0}),               # once per video
    ({"fmt": "short"}, {"AAAAAAAAAAA": 0}),
    ({"channel": "prayer8"}, {"AAAAAAAAAAA": 0}),                      # another channel's video
    ({"receipt_recovered_from_youtube": True}, {"AAAAAAAAAAA": 0}),
    ({"youtube_status": "deleted_or_missing"}, {"AAAAAAAAAAA": 0}),
    ({"title": "A Prayer With No Passage In Its Title At All"}, {"AAAAAAAAAAA": 0}),
    ({"job_id": "0008"}, {"AAAAAAAAAAA": 0}),                          # the sync pins this title
])
def test_everything_else_keeps_its_title(tmp_path, change, snapshot):
    _receipt(tmp_path, "0500-psalm-23-5", **change)
    assert _targets(tmp_path, _views(**snapshot)) == []


def test_at_most_two_a_run_and_the_oldest_first(tmp_path):
    for number, published in enumerate(("2026-11-05", "2026-10-20", "2026-11-01", "2026-10-28")):
        _receipt(tmp_path, f"05{number:02d}-psalm-23-5", video_id=f"VIDEO{number:06d}",
                 published=published, job_id=f"05{number:02d}")
    snapshot = _views(**{f"VIDEO{n:06d}": 0 for n in range(4)})
    chosen = _targets(tmp_path, snapshot)
    assert [t.video_id for t in chosen] == ["VIDEO000001", "VIDEO000003"]


def test_no_snapshot_means_nothing_is_changed(tmp_path):
    _receipt(tmp_path, "0500-psalm-23-5")
    ledger = tmp_path / "ledger.json"
    assert cli.choose("prayer7", ledger, ask=lambda prompt: GOOD, snapshots=[], today=TODAY) == []
    assert json.loads(ledger.read_text()) == []


# --------------------------------------------------------------------------- #
# Which titles
# --------------------------------------------------------------------------- #
def _problems(title: str) -> list[str]:
    return retitle.title_problems(title, "Psalm 23:5", "The Provision Table", OLD)


def test_a_need_first_title_with_the_reference_kept_is_accepted():
    assert _problems(GOOD) == []
    assert _problems("Prayer for Daily Bread and Open Doors: Psalm 23:5") == []


@pytest.mark.parametrize("title, why", [
    (OLD, "must read"),
    ("Prayer When Money Is Short: Psalm 23 | The Provision Table", "must read"),       # reference changed
    ("Prayer When Money Is Short: Psalm 23:5 | The Morning Altar", "must read"),       # another channel
    ("Provision Prayer: Psalm 23:5 | The Provision Table", "at least three words"),
    ("Short: Psalm 23:5", "characters"),
    ("A Prayer for the Day the Rent Is Due and Nothing Is Left: Psalm 23:5 | The Provision Table",
     "characters"),
    ("MIRACLE Money Prayer for Today: Psalm 23:5 | The Provision Table", "capitals"),
    ("Miracle Money Prayer for Today: Psalm 23:5 | The Provision Table", "miracle"),
    ("Is Money Short Today? Pray This Now: Psalm 23:5", "question marks"),
    ("Prayer for 7 Days of Open Doors: Psalm 23:5 | The Provision Table", "digits"),
    ("Guaranteed Open Doors This Week: Psalm 23:5 | The Provision Table", "guaranteed"),
])
def test_other_titles_are_refused(title, why):
    assert any(why in problem for problem in _problems(title)), _problems(title)


def test_a_refused_title_is_sent_back_with_the_reason_then_given_up_on(tmp_path):
    _receipt(tmp_path, "0500-psalm-23-5")
    (target,) = _targets(tmp_path, _views(AAAAAAAAAAA=0))
    prompts: list[str] = []
    answers = iter(["MIRACLE MONEY!!! Psalm 23:5", f"  `{GOOD}`\n(a calmer title)"])

    def ask(prompt):
        prompts.append(prompt)
        return next(answers)

    title, why = retitle.propose_title(target, "The Provision Table", ask)
    assert title == GOOD and why == ""
    assert "Your last answer was refused" in prompts[1]
    assert "Psalm 23:5" in prompts[0] and OLD in prompts[0]

    title, why = retitle.propose_title(target, "The Provision Table", lambda prompt: "Psalm 23:5")
    assert title is None and "must read" in why


# --------------------------------------------------------------------------- #
# The receipt
# --------------------------------------------------------------------------- #
def test_the_ledger_is_written_and_then_stamped_into_the_receipt(tmp_path, monkeypatch):
    path = _receipt(tmp_path, "0500-psalm-23-5")
    real = retitle.find_targets
    monkeypatch.setattr(retitle, "find_targets",
                        lambda channel, snapshots, today=None: real(
                            channel, snapshots, published_dir=tmp_path, today=TODAY))
    ledger = tmp_path / "ledger.json"
    entries = cli.choose("prayer7", ledger, ask=lambda prompt: GOOD,
                         snapshots=_views(AAAAAAAAAAA=0), today=TODAY)
    assert [(e["old_title"], e["new_title"], e["date"]) for e in entries] == [(OLD, GOOD, "2026-11-14")]
    assert parse_script(path).title == OLD, "choosing a title changes no receipt"

    assert cli.apply(ledger) == [entries[0]["file"]]
    doc = parse_script(path)
    assert doc.title == GOOD
    assert doc.meta["title_before"] == OLD and doc.meta["retitled_at"] == "2026-11-14"
    assert doc.meta["metadata_revision"] == retitle.PENDING_REVISION, \
        "the monitor's sync treats the receipt as pending and pushes the new title"
    assert doc.meta["youtube_video_id"] == "AAAAAAAAAAA" and doc.meta["thumb_text"] == "CUP RUNNETH OVER"

    assert cli.apply(ledger) == [], "applying the same ledger twice changes nothing"
    assert real("prayer7", _views(AAAAAAAAAAA=0), published_dir=tmp_path, today=TODAY) == [], \
        "and the video is never retitled again"


def test_a_receipt_whose_title_changed_upstream_is_left_alone(tmp_path):
    path = _receipt(tmp_path, "0500-psalm-23-5", title="A Title Someone Else Already Changed: Psalm 23:5")
    before = path.read_text(encoding="utf-8")
    outcome = retitle.apply_ledger_entry(path, {"old_title": OLD, "new_title": GOOD, "date": "2026-11-14"})
    assert outcome == "title changed since the new one was written"
    assert path.read_text(encoding="utf-8") == before


def test_a_title_wrapped_over_two_lines_is_not_half_replaced(tmp_path):
    long_old = ("Psalm 23:5 Provision Prayer For Every Household That Is Waiting On The Lord "
                "| The Provision Table")
    path = _receipt(tmp_path, "0500-psalm-23-5", title=long_old)
    assert "\n  " in path.read_text(encoding="utf-8").split("slug:")[0], "the fixture title is folded"
    before = path.read_text(encoding="utf-8")
    outcome = retitle.apply_ledger_entry(path, {"old_title": long_old, "new_title": GOOD,
                                                "date": "2026-11-14"})
    if outcome == "stamped":
        assert parse_script(path).title == GOOD
    else:
        assert path.read_text(encoding="utf-8") == before, "a failed edit is rolled back whole"


def test_the_sync_pushes_a_receipt_waiting_for_its_new_title(tmp_path):
    """`--sync-pending` selects a receipt whose revision is not the current one."""
    from scripts import retrofit_published_metadata as retrofit

    _receipt(tmp_path, "0500-psalm-23-5", title=GOOD, metadata_revision=retitle.PENDING_REVISION)
    _receipt(tmp_path, "0501-psalm-23-6", title=OLD.replace("23:5", "23:6"), video_id="CCCCCCCCCCC",
             job_id="0501")
    pending = retrofit.collect_published_faith_targets(published_dir=tmp_path, only_pending=True)
    assert [(t["video_id"], t["title"]) for t in pending] == [("AAAAAAAAAAA", GOOD)]


def test_the_daily_growth_run_chooses_and_commits_new_titles():
    workflow = (REPO / ".github" / "workflows" / "growth-autopilot.yml").read_text(encoding="utf-8")
    assert "scripts/retitle_unwatched.py --channel" in workflow
    assert "scripts/retitle_unwatched.py --apply-ledger" in workflow
    assert "GEMINI_API_KEY:" in workflow, "the title writer needs the channel's text model"
    choose_at = workflow.index("retitle_unwatched.py --channel")
    assert workflow.index("scripts/metrics_snapshot.py") < choose_at, "view counts come first"
    assert "git checkout origin/main --" in workflow, "receipts are stamped on a fresh copy"
