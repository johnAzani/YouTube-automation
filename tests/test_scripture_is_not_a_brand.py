"""The Bible's own words are not another channel's branding.

On 15 November 2026 The Covenant Shield ran out of long-form prayers. Its brain had
written nothing since the channel started: the next passage on its roadmap was
Psalm 91:1-2, "He that dwelleth in the secret place of the most High", and every
script that quoted the verse was refused for carrying "The Secret Place", the
name of another channel. The brain always takes the next passage, so it tried the
same one every day and was refused every day, while the job that ran it ended
green because one older script was still waiting.

The rule now: words the Bible uses count as a brand only when written as a name.
"""
from __future__ import annotations

from unittest import mock

import pytest

from pipeline import scripture_text
from pipeline.channel_capabilities import (brand_for, known_channels, off_brand_phrase,
                                           scripture_name_note)
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain
from scripts.continuous_research import roadmap_for_channel

VERSE = "He that dwelleth in the secret place of the most High shall abide under the shadow of the Almighty."


def script(body_line: str = VERSE, title: str = "Psalm 91:1-2 Prayer for God's Protection Today",
           thumb: str = "GOD MY REFUGE") -> str:
    return "\n".join([
        "---", 'id: "0607"', "slug: psalm-91-1-2-prayer-for-protection", f'title: "{title}"',
        "status: approved", "format: longform", "niche: faith", f'thumb_text: "{thumb}"',
        'originality: "Original exposition; no copied commentary."', "channel: prayer8", "---", "",
        "## Scene 1 — Under His Shadow", "", "Psalm 91, verse 1. " + body_line, "",
        "## Scene 2 — Amen", "", "Type Amen, and subscribe to The Covenant Shield.", ""])


def _author(text: str) -> str:
    brain = GeminiBrain(channel_id="prayer8")
    with mock.patch.object(brain, "is_api_available", return_value=True), \
            mock.patch.object(brain, "_call_model", return_value=text), \
            mock.patch("pipeline.gemini_brain.text_model_candidates", return_value=["model-a"]):
        return brain.author_longform_script(
            {"id": "0607", "scripture": "Psalm 91:1-2", "theme": "Abiding", "hook": "GOD MY REFUGE"})


def test_the_covenant_shield_can_write_its_psalm_91_prayer():
    assert "the secret place of the most High" in _author(script())


@pytest.mark.parametrize("text", [
    script(VERSE + " Welcome back to The Secret Place."),
    script(title="Dwelling in the Secret Place: Psalm 91:1-2"),
    script(thumb="THE SECRET PLACE"),
    script(VERSE + " Subscribe at @SecretPlaceSanctuary."),
    script(VERSE + " Pray this before you sleep."),
])
def test_the_name_of_another_channel_is_still_refused(text):
    with pytest.raises(BrainAuthoringError) as refused:
        _author(text)
    assert "branding" in str(refused.value)


@pytest.mark.parametrize("text, found", [
    ("He that dwelleth in the secret place of the most High", None),
    ("The secret place of the Most High is not a building.", None),
    ("Thou shalt hide them in the secret of thy presence.", None),
    ("Welcome to The Secret Place.", "The Secret Place"),
    ("Rest in the Secret Place tonight.", "The Secret Place"),
    ("DWELL IN THE SECRET PLACE", "The Secret Place"),
    ("Join us at the morning altar tomorrow.", "The Morning Altar"),  # not Bible words: any capitals
    ("see @themorningaltardaily", "@TheMorningAltarDaily"),
    ("A prayer for protection.", None),
])
def test_one_rule_for_what_counts_as_another_channels_name(text, found):
    assert off_brand_phrase(text, "prayer8") == found


def test_the_secret_place_itself_may_use_its_own_name():
    assert off_brand_phrase("Welcome to The Secret Place.", "secret-place") is None


def test_only_words_the_bible_has_are_excused():
    assert scripture_text.says("The Secret Place") and scripture_text.says("the  secret place")
    for channel in known_channels():
        for phrase in brand_for(channel).forbidden_phrases:
            if scripture_text.says(phrase):
                assert phrase.lower() == "the secret place", phrase


def test_the_lengthening_pass_and_the_reply_engine_follow_the_same_rule():
    from pipeline.comment_replies import _reply_is_safe
    from tools import expand_scripts
    import inspect

    assert _reply_is_safe("Amen. May you dwell in the secret place of the Most High today.", "prayer8")
    assert not _reply_is_safe("Amen. Visit The Secret Place for more prayers.", "prayer8")
    assert "off_brand_phrase(expanded, declared_channel)" in inspect.getsource(expand_scripts.validate)


def test_the_writer_is_told_only_when_the_passage_holds_such_words():
    note = scripture_name_note("prayer8", "Psalm 91:1-2")
    assert '"the secret place"' in note and "Never write them with capital letters" in note
    assert note.count('"the secret place"') == 1
    assert scripture_name_note("prayer8", "Psalm 91:4") == ""
    assert scripture_name_note("secret-place", "Psalm 91:1-2") == ""
    assert scripture_name_note("prayer8", "Not A Book 3:1") == ""

    seen = {}
    brain = GeminiBrain(channel_id="prayer8")

    def fake(model, prompt, **kwargs):
        seen["prompt"] = prompt
        return script()
    with mock.patch.object(brain, "is_api_available", return_value=True), \
            mock.patch.object(brain, "_call_model", side_effect=fake), \
            mock.patch("pipeline.gemini_brain.text_model_candidates", return_value=["model-a"]):
        brain.author_longform_script({"id": "0607", "scripture": "Psalm 91:1-2", "theme": "t", "hook": "h"})
    assert "THIS PASSAGE CONTAINS THE WORDS" in seen["prompt"]


def test_no_passage_on_any_roadmap_is_impossible_for_its_own_channel():
    """Whatever verse a channel is given to pray, quoting it must not get the script refused."""
    checked = 0
    for channel in known_channels():
        for job in roadmap_for_channel(channel):
            try:
                verses = scripture_text.passage(job["scripture"])
            except scripture_text.UnknownReference:
                continue
            for verse in verses:
                checked += 1
                assert off_brand_phrase(scripture_text.readable(verse.text), channel) is None, (
                    channel, job["id"], verse.label)
            for field in ("theme", "hook"):
                assert off_brand_phrase(str(job.get(field, "")), channel) is None, (channel, job["id"], field)
    assert checked > 300


# ---------------------------------------------------------------------------
# One passage the gates will not take must not hold up the passages behind it,
# and the refusal must be readable without opening a log.
# ---------------------------------------------------------------------------

def _queued(directory, job_id: str, channel: str = "prayer8"):
    words = " ".join(["mercy"] * 900)
    (directory / f"{job_id}-x.md").write_text(
        f'---\nid: "{job_id}"\nslug: x-{job_id}\ntitle: "T {job_id}"\nstatus: approved\nformat: longform\n'
        f"niche: faith\nchannel: {channel}\n---\n\n## Scene 1 — One\n\n{words}\n", encoding="utf-8")


class _Brain:
    channel_id = "prayer8"

    def __init__(self, refused: bool):
        self._refused = refused

    def passage_was_refused(self):
        return self._refused


def _supply(monkeypatch, tmp_path, brain, rows):
    from pipeline import supply

    calls = []

    def author_new(_brain, expand_target=0):
        row = rows[min(len(calls), len(rows) - 1)]
        calls.append(row)
        if row.get("ok"):
            _queued(tmp_path, row["job_id"])
        return row
    monkeypatch.setattr(supply, "author_new", author_new)
    monkeypatch.setattr(supply, "expand_backlog", lambda **kwargs: [])
    report = supply.ensure_supply(brain, queue_dir=tmp_path, write=False, min_publishable=2,
                                  channel_id="prayer8")
    return report, calls


def test_a_refused_passage_is_passed_over_once_and_the_next_one_is_written(monkeypatch, tmp_path):
    _queued(tmp_path, "0606")
    report, calls = _supply(monkeypatch, tmp_path, _Brain(refused=True), [
        {"ok": False, "reason": "branding: refused"}, {"ok": True, "job_id": "0608", "words": 900}])
    assert len(calls) == 2 and report.publishable_after == 2
    assert report.blocked == ["authoring: branding: refused"]  # still said, although the run recovered


def test_it_moves_on_once_only(monkeypatch, tmp_path):
    report, calls = _supply(monkeypatch, tmp_path, _Brain(refused=True),
                            [{"ok": False, "reason": "branding: refused"}])
    assert len(calls) == 2 and report.publishable_after == 0 and not report.ok


def test_it_does_not_move_on_when_google_could_not_be_reached(monkeypatch, tmp_path):
    _queued(tmp_path, "0606")
    report, calls = _supply(monkeypatch, tmp_path, _Brain(refused=False), [
        {"ok": False, "reason": "daily allowance spent"}, {"ok": True, "job_id": "0608", "words": 900}])
    assert len(calls) == 1 and report.publishable_after == 1


def test_the_brain_remembers_the_refused_passage_for_this_run_only(tmp_path):
    from pipeline import gemini_brain

    brain = GeminiBrain(channel_id="prayer8")
    roadmap = [{"id": "9001", "scripture": "Psalm 91:1-2", "theme": "t", "hook": "h"},
               {"id": "9002", "scripture": "Psalm 91:4", "theme": "t", "hook": "h"}]
    refused_text = script(VERSE + " Welcome back to The Secret Place.")
    with mock.patch.object(gemini_brain, "roadmap_for_channel", return_value=roadmap), \
            mock.patch.object(brain, "_existing_job_ids", return_value=set()), \
            mock.patch.object(brain, "is_api_available", return_value=True), \
            mock.patch.object(brain, "_call_model", return_value=refused_text), \
            mock.patch("pipeline.gemini_brain.text_model_candidates", return_value=["model-a"]), \
            mock.patch("pipeline.performance_feedback.rank_candidates", side_effect=lambda rows, _r: rows):
        assert brain.select_next_scripture()["id"] == "9001"
        with pytest.raises(BrainAuthoringError):
            brain.replenish_pipeline(min_runway_days=999.0)
        assert brain.passage_was_refused() and brain.refused_ids == {"9001"}
        assert brain.select_next_scripture()["id"] == "9002"
    assert GeminiBrain(channel_id="prayer8").refused_ids == set()


@pytest.mark.parametrize("outcomes, quota, verdict", [
    ([{"model": "a", "outcome": "branding: x"}], "", True),
    ([{"model": "a", "outcome": "503 busy"}, {"model": "b", "outcome": "scripture: no verse"}], "", True),
    ([{"model": "a", "outcome": "branding: x"}], "2026-11-16T08:00:00+00:00", False),
    ([{"model": "a", "outcome": "no response"}], "", False),
    ([{"model": "a", "outcome": "branding: x"}, {"model": "b", "outcome": "accepted"}], "", False),
    ([], "", False),
])
def test_what_counts_as_the_passage_being_refused(outcomes, quota, verdict):
    brain = GeminiBrain(channel_id="prayer8")
    brain.authoring_outcomes, brain.quota_stop = outcomes, quota
    assert brain.passage_was_refused() is verdict


def test_a_blocked_authoring_pass_is_said_in_an_annotation(monkeypatch, capsys):
    from pipeline import supply
    from scripts import gemini_brain as cli

    report = supply.SupplyReport()
    report.channel, report.publishable_before, report.publishable_after = "prayer8", 1, 1
    report.blocked = ["authoring: The Covenant Shield: no candidate model could author this scripture —\n"
                      "model-a: branding: carries another channel's branding: 'The Secret Place'."]
    monkeypatch.setattr(supply, "ensure_supply", lambda *args, **kwargs: report)
    assert cli.cmd_ensure_supply(_Brain(refused=True), 3, 900, min_publishable=6) == 0  # one is still ready
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("::warning")]
    assert lines == ["::warning title=Long-form authoring blocked (prayer8)::1 of 6 wanted are ready. "
                     "authoring: The Covenant Shield: no candidate model could author this scripture — "
                     "model-a: branding: carries another channel's branding: 'The Secret Place'."]
