"""One long-form and five Shorts a day per channel (14 November 2026).

Measured the night before: 91 Shorts drew 7,513 views and 95 long-forms drew 261.
The uploads moved to the format that is watched without adding any: six a day per
channel before and after. These tests hold the pieces of that together:

* the slots (five crons) and which one owes each channel its long-form;
* what "this slot is served" means now that most slots owe only a Short;
* the workflow step that skips the long-form in a Shorts-only slot, and what
  happens when it cannot decide;
* Shorts that have no long-form behind them, and where their passages come from.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import evergreen_shorts as ev  # noqa: E402
from pipeline import gemini_brain as gb  # noqa: E402
from pipeline import short_release as sr  # noqa: E402
from pipeline import short_script as ss  # noqa: E402
from pipeline.channels import scheduled_channels  # noqa: E402
from scripts import automation_monitor as mon  # noqa: E402
from scripts import produce_plan as plan  # noqa: E402
from scripts import scheduler_supervisor as sup  # noqa: E402

UTC = timezone.utc
WORKFLOW = ROOT / ".github" / "workflows" / "produce.yml"


def at(day: int, hour: int, minute: int = 14) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def slot_times() -> list[str]:
    out = []
    for row in workflow()[True]["schedule"]:
        minute, hour = row["cron"].split()[:2]
        out.append(f"{int(hour):02d}:{int(minute):02d}")
    return sorted(out)


def receipt(directory: Path, name: str, channel: str, when: datetime, fmt: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    (directory / name).write_text(
        "---\n"
        f'id: "{name[:4]}"\ntitle: "T {name}"\nslug: {name[:-3]}\nstatus: published\n'
        f"format: {fmt}\nchannel: {channel}\n"
        f'published_at: "{stamp}"\nyoutube_video_id: "vid{name[:6]}"\n'
        "---\n\nbody\n", encoding="utf-8")


# ------------------------------------------------------------------ the slots

def test_there_are_five_slots_and_every_channel_has_one_for_its_long_form():
    slots = slot_times()
    assert slots == ["06:14", "10:14", "14:14", "19:14", "23:14"]
    for channel in scheduled_channels():
        assert plan.LONGFORM_SLOT_UTC.get(channel) in slots, channel
    # No table entry for a channel that does not exist: a typo would silently
    # leave the real channel on "a long-form at every slot".
    assert set(plan.LONGFORM_SLOT_UTC) <= set(scheduled_channels())


def test_the_long_renders_are_spread_two_to_a_slot():
    per_slot: dict[str, int] = {}
    for slot in plan.LONGFORM_SLOT_UTC.values():
        per_slot[slot] = per_slot.get(slot, 0) + 1
    assert max(per_slot.values()) <= 2, per_slot


def test_slots_are_further_apart_than_the_gap_between_a_channels_shorts():
    """A Short is held back if the channel published one under three hours ago."""
    minutes = sorted(int(t[:2]) * 60 + int(t[3:]) for t in slot_times())
    gaps = [b - a for a, b in zip(minutes, minutes[1:])] + [minutes[0] + 1440 - minutes[-1]]
    assert min(gaps) >= 3 * 60 + 30, gaps


def test_a_channel_is_owed_a_long_form_only_at_its_own_slot():
    assert plan.slot_owes_longform("secret-place", at(14, 19))
    for hour in (6, 10, 14, 23):
        assert not plan.slot_owes_longform("secret-place", at(14, hour))
    assert plan.slot_owes_longform("prayer2", at(14, 6))
    assert not plan.slot_owes_longform("prayer2", at(14, 19))
    owed_per_day = {
        channel: sum(plan.slot_owes_longform(channel, at(14, int(t[:2]))) for t in slot_times())
        for channel in scheduled_channels()
    }
    assert set(owed_per_day.values()) == {1}, owed_per_day


def test_what_cannot_be_worked_out_is_owed_a_long_form():
    """The old behaviour is the safe one: never a channel with no long-form."""
    assert plan.slot_owes_longform("secret-place", None)
    with mock.patch.dict(plan.LONGFORM_SLOT_UTC, clear=True):
        assert plan.slot_owes_longform("secret-place", at(14, 6))
    with mock.patch.object(plan, "LONGFORM_EVERY_SLOT", True):
        assert plan.slot_owes_longform("secret-place", at(14, 6))


# ------------------------------------------------------- the leg's own decision

def test_the_leg_makes_a_long_form_at_the_channels_slot(tmp_path):
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    due, why = plan.longform_due("secret-place", at(14, 19, 30), tmp_path)
    assert due and "long-form slot" in why


def test_the_leg_skips_the_long_form_once_the_slots_short_is_out(tmp_path):
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    receipt(tmp_path, "short-x.md", "secret-place", at(14, 10, 25), "short")
    due, why = plan.longform_due("secret-place", at(14, 10, 30), tmp_path)
    assert not due
    assert "19:14" in why and "short-x.md" in why
    # Another channel's Short is not this channel's.
    due, _ = plan.longform_due("prayer6", at(14, 10, 30), tmp_path)
    assert due


def test_a_slot_whose_short_failed_gets_a_long_form_instead_of_nothing(tmp_path):
    """Shorts were failing on seven channels on 13 November. If that happens in
    a Shorts-only slot, the slot publishes what every slot used to publish."""
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    due, why = plan.longform_due("secret-place", at(14, 10, 30), tmp_path)
    assert due and "instead of nothing" in why


def test_the_fallback_is_no_more_often_than_the_old_three_a_day(tmp_path):
    """A day of broken Shorts must not turn into five long-forms."""
    receipt(tmp_path, "0030-a.md", "secret-place", at(14, 6, 50), "longform")
    due, why = plan.longform_due("secret-place", at(14, 10, 30), tmp_path)     # 3h40m later
    assert not due and "nothing more this slot" in why
    due, _ = plan.longform_due("secret-place", at(14, 14, 30), tmp_path)       # 7h40m later
    assert due


def test_a_short_held_back_by_the_pacing_guard_is_not_a_failed_short(tmp_path):
    """The previous slot's Short landed 20 minutes before this slot began, so
    this slot's Short was held back. That is pacing, not a reason for a long-form."""
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    receipt(tmp_path, "short-x.md", "secret-place", at(14, 9, 54), "short")
    due, _ = plan.longform_due("secret-place", at(14, 10, 30), tmp_path)
    assert not due
    # A Short from the slot before, five hours ago, is not this slot's Short.
    receipt(tmp_path, "short-x.md", "secret-place", at(14, 5, 30), "short")
    due, _ = plan.longform_due("secret-place", at(14, 10, 30), tmp_path)
    assert due


def test_a_late_leg_still_counts_the_short_it_published_hours_ago(tmp_path):
    """The leg ran at 10:20, the Short went out, and the step is asked at 13:50."""
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    receipt(tmp_path, "short-x.md", "secret-place", at(14, 10, 25), "short")
    due, _ = plan.longform_due("secret-place", at(14, 13, 50), tmp_path)
    assert not due


def test_a_missed_long_form_is_made_up_at_the_next_slot(tmp_path):
    """The 19:14 leg failed. At 23:14 the newest long-form is 27 hours old."""
    receipt(tmp_path, "0030-a.md", "secret-place", at(13, 19, 50), "longform")
    receipt(tmp_path, "short-x.md", "secret-place", at(14, 19, 40), "short")   # not a long-form
    due, why = plan.longform_due("secret-place", at(14, 23, 20), tmp_path)
    assert due and "catches up" in why


def test_a_channel_with_no_long_form_yet_gets_one_at_any_slot(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    due, why = plan.longform_due("prayer9", at(14, 19, 30), tmp_path)
    assert due and "no long-form receipt" in why


def test_the_step_output_says_false_only_when_it_is_sure(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    with mock.patch.object(plan, "longform_due", return_value=(False, "a Short only")):
        assert plan.main(["--longform-due", "prayer4"]) == 0
    assert out.read_text(encoding="utf-8") == "longform=false\n"

    out.write_text("", encoding="utf-8")
    with mock.patch.object(plan, "longform_due", return_value=(False, "a Short only")):
        plan.main(["--longform-due", "prayer4", "--force", "true"])
    assert out.read_text(encoding="utf-8") == "longform=true\n"

    out.write_text("", encoding="utf-8")
    with mock.patch.object(plan, "longform_due", side_effect=RuntimeError("no receipts dir")):
        assert plan.main(["--longform-due", "prayer4"]) == 0
    assert out.read_text(encoding="utf-8") == "longform=true\n"


def test_the_workflow_skips_the_long_form_only_on_an_explicit_false():
    steps = workflow()["jobs"]["produce"]["steps"]
    names = [step.get("name", "") for step in steps]
    short = names.index("Render the Short (9:16)")
    mix = names.index("Decide whether this slot owes a long-form")
    release = names.index("Render and upload the long-form edition")
    # After the Short: whether the slot's Short went out is part of the answer.
    assert short < mix < release
    assert steps[mix]["id"] == "mix"
    assert steps[mix].get("continue-on-error") is True
    assert "scripts.produce_plan --longform-due" in steps[mix]["run"]
    condition = steps[release]["if"]
    assert "steps.mix.outputs.longform != 'false'" in condition
    # A named job is the owner asking for that long-form: the mix never blocks it.
    assert "inputs.job != ''" in condition
    assert "longform" in workflow()[True]["workflow_dispatch"]["inputs"]


# ------------------------------------------------------ "this slot is served"

def test_a_short_serves_a_shorts_only_slot(tmp_path):
    receipt(tmp_path, "short-a.md", "secret-place", at(14, 10, 40), "short")
    assert sup.published_channels_since(at(14, 10), tmp_path) == {"secret-place"}


def test_a_short_does_not_serve_the_long_form_slot(tmp_path):
    """Otherwise the ride-along would certify a release that never happened."""
    receipt(tmp_path, "short-a.md", "secret-place", at(14, 19, 40), "short")
    assert sup.published_channels_since(at(14, 19), tmp_path) == set()
    receipt(tmp_path, "0031-b.md", "secret-place", at(14, 20, 5), "longform")
    assert sup.published_channels_since(at(14, 19), tmp_path) == {"secret-place"}


def test_a_long_form_serves_whatever_slot_it_lands_in(tmp_path):
    receipt(tmp_path, "0031-b.md", "secret-place", at(14, 10, 50), "longform")
    assert sup.published_channels_since(at(14, 10), tmp_path) == {"secret-place"}


def test_a_short_from_before_the_slot_serves_nothing(tmp_path):
    receipt(tmp_path, "short-a.md", "prayer4", at(14, 9, 50), "short")
    assert sup.published_channels_since(at(14, 10), tmp_path) == set()


def test_each_channel_is_judged_by_what_the_slot_owes_it(tmp_path):
    """06:14 owes The Morning Altar a long-form and The Midnight Watch a Short."""
    receipt(tmp_path, "short-a.md", "prayer2", at(14, 6, 40), "short")
    receipt(tmp_path, "short-b.md", "prayer4", at(14, 6, 41), "short")
    assert sup.published_channels_since(at(14, 6), tmp_path) == {"prayer4"}
    owed, served, slot = plan.split_served(["prayer2", "prayer4"], at(14, 7, 30), tmp_path)
    assert slot == at(14, 6)
    assert owed == ["prayer2"] and served == ["prayer4"]


def test_a_moment_inside_a_slot_is_judged_as_that_slot(tmp_path):
    """The supervisor's fallback passes a time that is not a cron instant."""
    assert plan.slot_containing(at(14, 12, 0)) == at(14, 10)
    receipt(tmp_path, "short-a.md", "secret-place", at(14, 12, 30), "short")
    assert sup.published_channels_since(at(14, 12, 0), tmp_path) == {"secret-place"}


# -------------------------------------------- the monitor's "published nothing"

def _monitor_report(last_success: datetime) -> mon.MonitorReport:
    report = mon.MonitorReport()
    report.automations.append(mon.Automation(
        workflow="produce.yml", name="Produce video", crons=[], last_success=last_success))
    return report


def _nothing_rows(report) -> list[dict]:
    return [row for row in report.outcomes if row["outcome"] == "produce published nothing"]


def test_a_late_run_with_nothing_left_to_do_is_not_a_failure(tmp_path):
    """00:19 UTC on the 14th: the run found the slot served at 22:40 the evening
    before and did nothing. That is the run working, not "green tick, no video"."""
    receipt(tmp_path, "0031-b.md", "secret-place", at(13, 22, 40), "longform")
    slot_then = ["14 6 * * *", "14 14 * * *", "14 19 * * *"]
    report = _monitor_report(at(14, 0, 19))
    with mock.patch.object(mon, "workflow_files",
                           return_value=[("produce.yml", "Produce video", slot_then)]):
        mon.check_outcomes(report, now=at(14, 3, 30), published_dir=tmp_path)
    assert _nothing_rows(report) == []


def test_a_run_that_published_nothing_for_its_slot_is_still_reported(tmp_path):
    receipt(tmp_path, "0031-b.md", "secret-place", at(13, 18, 0), "longform")   # before 23:14
    report = _monitor_report(at(14, 0, 19))
    mon.check_outcomes(report, now=at(14, 3, 30), published_dir=tmp_path)
    rows = _nothing_rows(report)
    assert len(rows) == 1 and rows[0]["severity"] == "blocking"


# ----------------------------------------------------- passages for the Shorts

def test_every_channel_has_evergreen_passages_and_none_is_shared():
    seen: dict[str, str] = {}
    for channel in scheduled_channels():
        references = ev.EVERGREEN.get(channel, ())
        assert len(references) >= 12, channel
        for reference in references:
            assert reference not in seen, f"{reference}: {seen.get(reference)} and {channel}"
            seen[reference] = channel
    assert set(ev.EVERGREEN) <= set(scheduled_channels())


def test_every_evergreen_reference_is_one_the_pipeline_can_read():
    for channel, references in ev.EVERGREEN.items():
        keys = set()
        for reference in references:
            match = gb._BOOK_RE.search(reference)
            assert match and match.group(0) == reference, f"{channel}: {reference!r}"
            parts = ev.reference_parts(reference)
            assert parts is not None and parts[2] is not None, f"{reference}: name a verse"
            key = gb.short_key_for_reference(channel, reference)
            assert ss.validate_spec({"key": key}, key=key).key == key
            assert key.startswith("short-") and key not in keys, f"{channel}: {key} twice"
            keys.add(key)


def test_a_reference_reads_to_book_chapter_and_first_verse():
    assert ev.reference_parts("Psalm 91:4-7") == ("psalm", 91, 4)
    assert ev.reference_parts("Psalms 23") == ("psalm", 23, None)
    assert ev.reference_parts("1 Corinthians 13:4-7") == ("1 corinthians", 13, 4)
    assert ev.reference_parts("Isaiah 40:28–31") == ("isaiah", 40, 28)
    assert ev.reference_parts("Say This Psalm 121:7-8 Prayer | Protection") == ("psalm", 121, 7)
    assert ev.reference_parts("no scripture here") is None


def test_the_same_passage_is_the_same_first_verse_or_the_whole_chapter():
    whole, first, fourth = ("psalm", 23, None), ("psalm", 23, 1), ("psalm", 23, 4)
    assert ev.same_passage(whole, fourth) and ev.same_passage(fourth, whole)
    assert ev.same_passage(first, ("psalm", 23, 1))
    assert not ev.same_passage(first, fourth)
    assert not ev.same_passage(first, ("psalm", 24, 1))
    assert not ev.same_passage(None, first)


def test_a_standalone_short_and_a_later_companion_share_one_key():
    from types import SimpleNamespace

    doc = SimpleNamespace(title="Protection Prayer for Tonight: Psalm 91:4 | The Covenant Shield",
                          slug="x", id="0699", channel="prayer8")
    assert gb.short_key_for_reference("prayer8", "Psalm 91:4") == gb.short_key_for_doc(doc)
    assert gb.short_key_for_reference("secret-place", "Romans 8:28") == "short-romans8v28"


def test_candidates_leave_out_what_the_channel_already_has(monkeypatch):
    monkeypatch.setattr(ev, "_roadmap_ahead", lambda channel, taken: ["Psalm 23", "Nahum 1:7"])
    monkeypatch.setitem(ev.EVERGREEN, "prayer8", ("Psalm 23:4", "Psalm 91:4", "Psalm 91:7"))
    used = {("psalm", 91, 4)}
    got = ev.candidates("prayer8", used=used)
    # Psalm 91:4 is already made. The roadmap's whole Psalm 23 is the evergreen
    # Psalm 23:4 again, so it is not offered a second time.
    assert got == [("Psalm 23:4", "evergreen"), ("Psalm 91:7", "evergreen"),
                   ("Nahum 1:7", "roadmap")]


def test_the_roadmap_offers_only_passages_with_no_long_form_yet(monkeypatch):
    rows = [
        {"id": "0901", "scripture": "Psalm 1:1-3", "search_volume_tier": "Tier 2 (x)"},
        {"id": "0902", "scripture": "Psalm 2:1", "search_volume_tier": "Tier 1 (x)"},
        {"id": "0903", "scripture": "Isaiah 40:28–31", "search_volume_tier": "Tier 1 (x)"},
    ]
    monkeypatch.setattr("scripts.continuous_research.roadmap_for_channel", lambda channel: rows)
    assert ev._roadmap_ahead("prayer8", {"0902"}) == ["Isaiah 40:28-31", "Psalm 1:1-3"]


def test_used_references_are_read_from_specs_queue_and_receipts(tmp_path):
    specs, queue, published = tmp_path / "specs", tmp_path / "queue", tmp_path / "published"
    for directory in (specs, queue, published):
        directory.mkdir()
    (specs / "short-a.json").write_text(json.dumps(
        {"key": "short-a", "channel": "prayer8", "scripture": "Psalm 34:7"}), encoding="utf-8")
    (specs / "short-b.json").write_text(json.dumps(
        {"key": "short-b", "channel": "prayer8", "psalm": 46}), encoding="utf-8")
    (specs / "short-c.json").write_text(json.dumps(
        {"key": "short-c", "channel": "prayer2", "scripture": "Psalm 5:3"}), encoding="utf-8")
    (specs / "short-broken.json").write_text("{not json", encoding="utf-8")
    (queue / "0601-short-d.yml").write_text(
        "short: short-d\nchannel: prayer8\nscripture: Genesis 15:1\n", encoding="utf-8")
    (published / "short-e.md").write_text(
        '---\ntitle: "Pray This Psalm 121:7-8 Prayer | Protection #Shorts"\nchannel: prayer8\n---\n',
        encoding="utf-8")
    got = ev.used_references("prayer8", spec_dir=specs, queue_dir=queue, published_dir=published)
    assert got == {("psalm", 34, 7), ("psalm", 46, None), ("genesis", 15, 1), ("psalm", 121, 7)}


# ------------------------------------------------- authoring a standalone Short

def good_spec(key: str, scripture: str, channel: str) -> dict:
    lines = [
        "When the house is quiet and your thoughts are not, this word is for you.",
        f"Hear it as it is written in {scripture}, slowly, and let it be enough for tonight.",
        "Father, I bring You the thing I have carried all day and could not put down.",
        "I thank You that nothing in it is hidden from You, and nothing in it is too heavy.",
        "Teach my heart to rest in what You have said and not in what I can see.",
        "Keep me and the ones I love until morning, and wake us in Your peace. Amen.",
    ]
    captions, phrases, scenes, start = [], [], [], 0
    for index, line in enumerate(lines):
        stop = start + 6
        captions.append([start, stop, line])
        phrases.append([start, stop, [" ".join(line.split()[:3]).upper()], ["WORD"], scripture.upper()])
        scenes.append({"a": " ".join(line.split()[:4]), "img": f"{key}-scene-{index + 1:02d}.jpg",
                       "kicker": "A WORD FOR TONIGHT", "sub": "REST IN WHAT HE SAID",
                       "cam": "push_in", "focus": [0.5, 0.5]})
        start = stop + 1
    return {
        "key": key, "channel": channel, "scripture": scripture,
        "title": ["A WORD", "FOR TONIGHT"],
        "poster": ["REST TONIGHT", "IN HIS WORD", "A PRAYER FOR", "A QUIET MIND"],
        "end": ["SUBSCRIBE", "A prayer every night"],
        "stock_queries": [f"calm night sky {i}" for i in range(len(lines))],
        "scenes": scenes, "captions": captions, "kinetic_phrases": phrases, "beats": [],
    }


@pytest.fixture
def brain(tmp_path, monkeypatch):
    """A Covenant Shield brain whose model answers with a valid spec for whatever it is asked."""
    queue, specs, published = tmp_path / "queue", tmp_path / "specs", tmp_path / "published"
    for directory in (queue, specs, published):
        directory.mkdir()
    monkeypatch.setattr(gb, "SHORTS_QUEUE_DIR", queue)
    monkeypatch.setattr(sr, "SHORTS_QUEUE_DIR", queue)
    monkeypatch.setattr(ss, "SPEC_DIR", specs)
    monkeypatch.setattr(gb, "PUBLISHED_DIR", published)
    monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "longform-queue")
    monkeypatch.setattr(sr, "_renderer_script_keys", lambda: set(ss.authored_keys()))
    monkeypatch.setattr(ev, "used_references", lambda channel, **_k: ev_used(queue))
    monkeypatch.setattr(ev, "_roadmap_ahead", lambda channel, taken: ["Nahum 1:7", "Psalm 125:2"])
    monkeypatch.setitem(ev.EVERGREEN, "prayer8", ("Psalm 23:4", "Psalm 91:4", "Psalm 91:7"))
    monkeypatch.setenv("CHANNEL_ID", "prayer8")
    made = gb.GeminiBrain(api_key="fake", channel_id="prayer8")
    asked: list[str] = []

    def author(_doc, key=None, *, scripture=None):
        asked.append(scripture)
        if scripture in made.refuse:
            raise gb.BrainAuthoringError(f"{scripture} rejected on every candidate model")
        return ss.require_valid(ss.validate_spec(good_spec(key, scripture, "prayer8"),
                                                 key=key, channel_id="prayer8"))

    made.refuse = set()
    made.asked = asked
    monkeypatch.setattr(made, "author_short_spec", author)
    monkeypatch.setattr(gb.GeminiBrain, "is_api_available", lambda self: True)
    made.dirs = (queue, specs, published)
    return made


def ev_used(queue: Path) -> set:
    found = set()
    for path in queue.glob("*.yml"):
        parts = ev.reference_parts(str((yaml.safe_load(path.read_text()) or {}).get("scripture")))
        if parts:
            found.add(parts)
    return found


def test_a_standalone_short_is_queued_with_no_long_form_behind_it(brain):
    queue, specs, _ = brain.dirs
    path, key = brain.generate_standalone_short("Psalm 91:4", source="evergreen")
    assert key == "short-shieldpsalm91v4"
    assert path == queue / "0000-short-shieldpsalm91v4.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["status"] == "approved" and data["renderer_ready"] is True
    assert data["standalone"] is True and data["source"] == "evergreen"
    assert data["channel"] == "prayer8" and data["scripture"] == "Psalm 91:4"
    assert "companion_longform_id" not in data
    assert (specs / f"{key}.json").is_file()
    assert ss.load_spec(specs / f"{key}.json").scripture == "Psalm 91:4"


def test_a_standalone_short_that_cannot_be_authored_leaves_nothing_behind(brain):
    queue, specs, _ = brain.dirs
    brain.refuse = {"Psalm 91:4"}
    path, key = brain.generate_standalone_short("Psalm 91:4")
    assert path is None and key == "short-shieldpsalm91v4"
    assert list(queue.iterdir()) == [] and list(specs.iterdir()) == []


def test_standalone_shorts_go_out_ahead_of_the_companions_already_waiting(brain):
    queue, specs, published = brain.dirs
    companion = "short-shieldgenesis15v1"
    ss.save_spec(ss.validate_spec(good_spec(companion, "Genesis 15:1", "prayer8"),
                                  key=companion, channel_id="prayer8"))
    (queue / f"0601-{companion}.yml").write_text(yaml.safe_dump({
        "short": companion, "channel": "prayer8", "companion_longform_id": "0601",
        "scripture": "Genesis 15:1", "status": "approved", "renderer_ready": True}),
        encoding="utf-8")
    brain.generate_standalone_short("Psalm 23:4")
    picked = sr.select_next_queued_short(queue_dir=queue, published_dir=published,
                                         channel_id="prayer8")
    assert picked is not None and picked[1] == "short-shieldpsalm23v4"
    # Another channel's leg never takes it.
    assert sr.select_next_queued_short(queue_dir=queue, published_dir=published,
                                       channel_id="prayer4") is None


def test_the_queue_is_topped_up_from_evergreen_first_then_the_roadmap(brain):
    queue, _, _ = brain.dirs
    rows = brain.replenish_shorts_queue(min_ready=5)
    assert brain.asked == ["Psalm 23:4", "Psalm 91:4", "Psalm 91:7", "Nahum 1:7", "Psalm 125:2"]
    assert [row["verdict"] for row in rows] == ["authored"] * 5
    assert len(list(queue.glob("0000-*.yml"))) == 5
    sources = [yaml.safe_load(p.read_text())["source"] for p in sorted(queue.glob("*.yml"))]
    assert sorted(sources) == ["evergreen"] * 3 + ["roadmap"] * 2
    # Full: a second pass asks for nothing.
    brain.asked.clear()
    assert brain.replenish_shorts_queue(min_ready=5) == []
    assert brain.asked == []


def test_one_pass_authors_a_bounded_number_of_standalone_shorts(brain, monkeypatch):
    monkeypatch.setattr(gb, "MAX_STANDALONE_PER_PASS", 2)
    brain.replenish_shorts_queue(min_ready=5)
    assert brain.asked == ["Psalm 23:4", "Psalm 91:4"]


def test_two_refusals_in_a_row_end_the_pass(brain):
    """A model that is down answers the third request like the first two."""
    queue, _, _ = brain.dirs
    brain.refuse = {"Psalm 23:4", "Psalm 91:4"}
    rows = brain.replenish_shorts_queue(min_ready=5)
    # Evergreen stops after two; the roadmap list is a separate list and is tried.
    assert brain.asked[:2] == ["Psalm 23:4", "Psalm 91:4"]
    assert "Psalm 91:7" not in brain.asked
    assert [row["verdict"] for row in rows[:2]] == ["failed", "failed"]
    assert not list(queue.glob("*psalm23v4*")) and not list(queue.glob("*psalm91v4*"))


def test_a_low_pool_is_said_out_loud(brain, capsys):
    brain.replenish_shorts_queue(min_ready=2)
    printed = capsys.readouterr().out
    assert "::warning title=Short passages running low (prayer8)::" in printed
    assert "pipeline/evergreen_shorts.py" in printed


def test_a_standalone_manifest_that_lost_its_spec_is_written_again(brain):
    queue, specs, _ = brain.dirs
    path, key = brain.generate_standalone_short("Psalm 91:7")
    (specs / f"{key}.json").unlink()
    brain.asked.clear()
    rows = brain.author_missing_shorts()
    assert brain.asked == ["Psalm 91:7"]
    assert [row["verdict"] for row in rows] == ["authored"]
    assert (specs / f"{key}.json").is_file()
    assert yaml.safe_load(path.read_text())["status"] == "approved"


def test_the_daily_brain_run_keeps_two_days_of_shorts_ready():
    from pipeline import supply

    assert supply.SHORTS_PER_DAY == len(slot_times())
    assert supply.SHORTS_READY_TARGET == 2 * supply.SHORTS_PER_DAY
    source = (ROOT / "scripts" / "gemini_brain.py").read_text(encoding="utf-8")
    assert "replenish_shorts_queue(min_ready=SHORTS_READY_TARGET)" in source


def test_a_long_form_written_later_does_not_queue_the_same_short_twice(brain, monkeypatch):
    """The roadmap passage became a Short first. When its long-form is written,
    the companion would be a second manifest for the same key."""
    from types import SimpleNamespace

    queue, _, _ = brain.dirs
    path, key = brain.generate_standalone_short("Psalm 91:4")
    doc = SimpleNamespace(title="Protection Prayer for Tonight: Psalm 91:4 | The Covenant Shield",
                          slug="x", id="0699", channel="prayer8")
    monkeypatch.setattr(gb, "extract_scripture_reference", lambda _doc: "Psalm 91:4")
    brain.asked.clear()
    made, same_key = brain.generate_companion_short(doc, require_renderable=True)
    assert made is None and same_key == key
    assert brain.asked == []
    assert [p.name for p in queue.glob("*.yml")] == [path.name]
