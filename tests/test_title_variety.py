"""Long-prayer titles must not settle into one mould.

Measured 16 November 2026: the old form ("Psalm 143:8 Morning Prayer | The
Morning Altar") was one sentence with the passage swapped; the need-first
titles replacing it opened with "When" 30 times in 99, seven of nine on The
Guided Path, and one need was worded identically on two channels. These tests
pin the rules that stop the second mould (pipeline/title_variety.py) at the
three places a title is written or measured.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pipeline import gemini_brain as gb
from pipeline import retitle
from pipeline import title_variety as tv
from scripts import channel_protection as cp
from scripts import retitle_unwatched as cli

PATH = "The Guided Path"
NOW = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)


def _doc(folder: Path, name: str, title: str, channel: str, *, day: str = "2026-11-10",
         extra: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.md"
    path.write_text(
        "---\n"
        f'id: "{name[:4]}"\n'
        f"title: {json.dumps(title)}\n"
        f"slug: {name}\n"
        "format: longform\n"
        "niche: faith and devotion\n"
        f"channel: {channel}\n"
        + (f'published_at: "{day}T06:00:00Z"\n' if day else "")
        + extra
        + "---\n\n## Scene 1\nLord, hear us.\n",
        encoding="utf-8")
    return path


def _variety(own=(), elsewhere=(), channel="prayer10") -> tv.Variety:
    return tv.Variety(channel=channel, own=tuple(own), elsewhere=tuple(elsewhere))


WHENS = ("When You Need to Know the Next Step", "When Your Plans Fall Short",
         "When Every Plan Feels Heavy", "When the Way Ahead Is Dry")


# --------------------------------------------------------------------------- #
# Reading a title
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("title,need", [
    ("When Money Is Tight: Philippians 4:19 | The Provision Table", "When Money Is Tight"),
    ("When Money Is Tight: Philippians 4:19", "When Money Is Tight"),
    ("He Hath Broken the Gates of Brass | Psalm 107:13-16 | The Provision Table",
     "He Hath Broken the Gates of Brass"),
    # A colon inside a reference does not end a need: the old form has none.
    ("Psalm 23:5 Provision Prayer | The Provision Table", "Psalm 23:5 Provision Prayer"),
    ("1 John 4:18 Night Prayer | The Provision Table", "1 John 4:18 Night Prayer"),
])
def test_the_need_is_what_the_title_leads_with(title, need):
    assert tv.need_of(title, "The Provision Table") == need


@pytest.mark.parametrize("need,old_form", [
    ("Psalm 23:5 Provision Prayer", True),
    ("1 John 4:18 Night Prayer", True),
    ("Song of Solomon 2:4 Morning Prayer", True),
    ("When Money Is Tight", False),
    ("Prayer Before a Big Decision", False),
    ("Night Prayer When Dread Keeps You Awake", False),
])
def test_the_old_form_opens_with_the_passage(need, old_form):
    assert tv.names_no_need(need) is old_form


def test_an_article_is_not_an_opening():
    assert tv.opening("The Lord Is My Rock") == "lord"
    assert tv.opening("A Blessing to Fall Asleep Under") == "blessing"
    assert tv.opening("When You Don't Know What to Do") == "when"
    assert tv.opening("") == ""


@pytest.mark.parametrize("one,other,same", [
    ("When You Don't Know What to Do", "When You Don't Know What to Do", True),
    ("When the Path Ahead Is Twisted", "When the Path Ahead Is Blocked", True),
    ("When Every Day Feels Heavy", "When Every Plan Feels Heavy", True),
    # Small words and the word "prayer" do not make two titles alike.
    ("Prayer for Your Family", "Prayer for a Sick Child", False),
    ("When Money Is Tight", "When Fear Keeps You Awake", False),
    ("Morning Prayer for Courage Today", "Morning Prayer for a Clear Path Today", False),
])
def test_alike_means_most_of_the_meaningful_words(one, other, same):
    assert tv.alike(one, other) is same


# --------------------------------------------------------------------------- #
# What a channel's next title must avoid
# --------------------------------------------------------------------------- #
def test_an_opening_that_begins_a_third_of_the_titles_is_tired():
    variety = _variety(WHENS + ("Prayer Before a Big Decision",
                                "Prayer for Guidance When You Feel Lost"))
    assert variety.tired_openings() == {"when": 4}
    found = variety.problems("When You Cannot See the Road: Psalm 32:8 | The Guided Path", PATH)
    assert found and "already open with 'When'" in found[0]
    assert variety.problems("Counsel for a Hard Choice Ahead: Psalm 32:8", PATH) == []


def test_two_uses_are_not_a_habit():
    variety = _variety(("When You Need Rest", "When Fear Is Loud", "Strength for Today",
                        "Peace Over Your Home"))
    assert variety.tired_openings() == {}


def test_a_word_that_names_the_kind_of_prayer_has_a_looser_mark():
    """"Bedtime Prayer for ..." is what people search for, and a series is allowed."""
    titles = ("Bedtime Prayer for Anxiety", "Bedtime Prayer When You Are Worn Out",
              "Bedtime Prayer for a Quiet Mind", "A Blessing to Fall Asleep Under",
              "Angels Stand Watch", "Rest for the Weary", "Fear Not the Night")
    assert _variety(titles).tired_openings() == {}, "3 of 7 is under one half"
    most = titles[:3] + ("Bedtime Prayer for Your Children", "Rest for the Weary")
    assert _variety(most).tired_openings() == {"bedtime": 4}


def test_only_the_recent_titles_decide_a_tired_opening():
    old = tuple(f"When Trouble Number {word} Comes" for word in ("One", "Two", "Three", "Four"))
    fresh = tuple(f"{word} for Today" for word in (
        "Strength", "Peace", "Courage", "Mercy", "Wisdom", "Rest", "Hope", "Joy", "Light",
        "Help", "Grace", "Favour", "Counsel", "Comfort", "Shelter"))
    assert len(fresh) == tv.RECENT
    assert _variety(old + fresh).tired_openings() == {}


def test_a_need_already_on_this_channel_is_refused():
    variety = _variety(("Prayer Before a Big Decision", "Strength for a Long Afternoon"))
    found = variety.problems("Strength for the Long Afternoon: Isaiah 40:31", PATH)
    assert found == ["too close to a title already on this channel: "
                     "'Strength for a Long Afternoon'"]


def test_a_need_already_on_another_channel_is_refused_without_naming_the_channel():
    variety = _variety((), elsewhere=("When You Don't Know What to Do",))
    found = variety.problems("When You Don't Know What to Do: James 1:5 | The Guided Path", PATH)
    assert found == ["too close to a title already in use: 'When You Don't Know What to Do'"]
    for name in ("Morning Altar", "Midday Watch", "Secret Place"):
        assert name not in found[0], "a prompt must not carry another channel's name"


def test_the_old_form_is_refused():
    found = _variety().problems("Psalm 32:8 Guidance Prayer | The Guided Path", PATH)
    assert found and "opens with the scripture reference" in found[0]


def test_two_titles_written_in_one_run_differ():
    variety = _variety(("Prayer Before a Big Decision",))
    first = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    assert variety.problems(first, PATH) == []
    after = variety.with_title(first, PATH)
    assert after.problems("Counsel for the Hard Choice Ahead: Proverbs 3:5-6", PATH)
    assert variety.problems("Counsel for the Hard Choice Ahead: Proverbs 3:5-6", PATH) == []


def test_the_prompt_lists_the_titles_and_names_the_opening_not_to_use():
    block = _variety(WHENS + ("Prayer Before a Big Decision",)).prompt_block()
    assert "When Every Plan Feels Heavy" in block
    assert "Do NOT begin the new title with 'When'" in block
    quiet = _variety(("Prayer Before a Big Decision", "Strength for Today")).prompt_block()
    assert "Do NOT begin" not in quiet and "Strength for Today" in quiet
    assert _variety().prompt_block() == ""


# --------------------------------------------------------------------------- #
# Reading the files
# --------------------------------------------------------------------------- #
def test_published_and_queued_long_prayers_are_read_and_nothing_else(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    _doc(published, "0801-a", "Prayer Before a Big Decision: Proverbs 15:22 | The Guided Path",
         "prayer10")
    _doc(published, "0802-b", "Psalm 32:8 Guidance Prayer | The Guided Path", "prayer10",
         day="2026-11-02")
    _doc(published, "short-guidedpsalm32v8", "Pray This Psalm 32:8 Prayer | Lead Me", "prayer10")
    _doc(published, "0803-c", "A Short Among Long", "prayer10", extra="format_note: x\n")
    (published / "0803-c.md").write_text(
        (published / "0803-c.md").read_text().replace("format: longform", "format: short"))
    _doc(queue, "0804-d", "When Your Steps Feel Uncertain: Psalm 37:23-24", "prayer10", day="")
    _doc(queue, "0003-e", "How a Bank Failed", "prayer10", day="")
    (queue / "0003-e.md").write_text(
        (queue / "0003-e.md").read_text().replace("faith and devotion", "finance and business"))
    _doc(published, "0101-f", "When You Need Direction Today: Psalm 143:8 | The Morning Altar",
         "prayer2")

    rows = tv.listed(published_dir=published, queue_dir=queue)
    assert [(row.channel, row.queued) for row in rows] == [
        ("prayer10", False), ("prayer2", False), ("prayer10", False), ("prayer10", True)]
    variety = tv.variety_for("prayer10", published_dir=published, queue_dir=queue)
    assert variety.own == ("Prayer Before a Big Decision", "When Your Steps Feel Uncertain"), \
        "the old form is not a need and is not counted as one"
    assert variety.elsewhere == ("When You Need Direction Today",)


def test_a_missing_folder_is_no_titles(tmp_path):
    assert tv.listed(published_dir=tmp_path / "none", queue_dir=tmp_path / "nor") == []


# --------------------------------------------------------------------------- #
# The retitler
# --------------------------------------------------------------------------- #
OLD = "Psalm 32:8 Guidance Prayer | The Guided Path"


def _target() -> retitle.Target:
    return retitle.Target(Path("x.md"), "AAAAAAAAAAA", OLD, "Psalm 32:8", "prayer10", 0, 9)


def test_a_sound_title_is_refused_when_it_reads_like_the_others():
    title = "When You Cannot See the Road: Psalm 32:8 | The Guided Path"
    assert retitle.title_problems(title, "Psalm 32:8", PATH, OLD) == []
    found = retitle.title_problems(title, "Psalm 32:8", PATH, OLD, _variety(WHENS))
    assert found and "already open with 'When'" in found[0]


def test_the_retitler_is_told_and_asks_again():
    prompts: list[str] = []
    answers = iter(["When You Cannot See the Road: Psalm 32:8 | The Guided Path",
                    "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"])

    def ask(prompt):
        prompts.append(prompt)
        return next(answers)

    title, why = retitle.propose_title(_target(), PATH, ask, variety=_variety(WHENS))
    assert title == "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path" and why == ""
    assert "Do NOT begin the new title with 'When'" in prompts[0]
    assert "already open with 'When'" in prompts[1]


def test_without_titles_to_compare_the_prompt_is_as_it_was():
    plain = retitle.build_prompt(_target(), PATH)
    assert "Titles already on this channel" not in plain
    assert "has had almost no views" in plain
    assert retitle.build_prompt(_target(), PATH, variety=_variety()) == plain


def test_a_draft_is_not_described_as_a_video_nobody_watched():
    prompt = retitle.build_prompt(_target(), PATH, draft=True)
    assert "almost no views" not in prompt and "was drafted under this title" in prompt


def test_the_command_reads_the_channels_titles(tmp_path):
    published, queue = tmp_path / "published", tmp_path / "queue"
    receipt = _doc(published, "0802-psalm-32-8", OLD, "prayer10", day="2026-11-02",
                   extra='youtube_video_id: "AAAAAAAAAAA"\nscripture: "Psalm 32:8"\n')
    for number, need in enumerate(WHENS):
        _doc(queue, f"081{number}-q", f"{need}: Psalm 1:{number + 1}", "prayer10", day="")
    snapshots = [{"video_id": "AAAAAAAAAAA", "views": 0, "snapshot_date": "2026-11-13"}]
    prompts: list[str] = []

    def ask(prompt):
        prompts.append(prompt)
        return "When You Cannot See the Road: Psalm 32:8 | The Guided Path"

    ledger = tmp_path / "ledger.json"
    entries = cli.choose("prayer10", ledger, ask=ask, snapshots=snapshots,
                         today=date(2026, 11, 16), published_dir=published, queue_dir=queue)
    assert entries == [] and json.loads(ledger.read_text()) == []
    assert len(prompts) == 2 and "Do NOT begin the new title with 'When'" in prompts[0]
    assert receipt.read_text().count(OLD) == 1, "a refused title changes no receipt"

    good = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    entries = cli.choose("prayer10", ledger, ask=lambda prompt: good, snapshots=snapshots,
                         today=date(2026, 11, 16), published_dir=published, queue_dir=queue)
    assert [entry["new_title"] for entry in entries] == [good]


# --------------------------------------------------------------------------- #
# The author
# --------------------------------------------------------------------------- #
SCRIPT = """---
id: "0820"
title: "{title}"
slug: psalm-32-8
channel: prayer10
tags: [guidance, "the guided path"]
thumb_text: "I WILL GUIDE THEE"
---

## Scene 1
I will instruct thee and teach thee in the way which thou shalt go.
"""


def test_only_the_title_line_is_replaced():
    text = SCRIPT.format(title=OLD)
    new = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    edited = gb._replace_title(text, new)
    assert edited == text.replace(f'title: "{OLD}"', f'title: "{new}"')
    assert gb.job_front_matter(edited)["thumb_text"] == "I WILL GUIDE THEE"


def test_a_folded_title_is_replaced_whole():
    text = SCRIPT.format(title=OLD).replace(f'title: "{OLD}"',
                                            "title: >-\n  Psalm 32:8 Guidance\n  Prayer")
    edited = gb._replace_title(text, "Counsel for a Hard Choice: Psalm 32:8")
    assert gb.job_front_matter(edited)["title"] == "Counsel for a Hard Choice: Psalm 32:8"
    assert "Guidance\n" not in edited


@pytest.mark.parametrize("text", [
    "## Scene 1\nno front matter\n",
    '---\ntitle: "one"\ntitle: "two"\nslug: x\n---\nbody\n',
    "---\nslug: no-title\n---\nbody\n",
])
def test_a_title_that_cannot_be_replaced_safely_is_left(text):
    assert gb._replace_title(text, "Counsel for a Hard Choice: Psalm 32:8") is None


class _Brain(gb.GeminiBrain):
    """The author with a scripted model and no network."""

    def __init__(self, answers, available=True):
        self.channel_id = "prayer10"
        self.model = "fake-model"
        self.authoring_outcomes = [{"model": "accepted-model", "outcome": "accepted"}]
        self._answers = list(answers)
        self._available = available
        self.calls: list[tuple[str, str]] = []

    def is_api_available(self) -> bool:
        return self._available

    def _call_model(self, model: str, prompt: str) -> str:
        self.calls.append((model, prompt))
        return self._answers.pop(0)


@pytest.fixture
def titles(tmp_path, monkeypatch):
    published, queue = tmp_path / "published", tmp_path / "queue"
    for number, need in enumerate(WHENS):
        _doc(queue, f"081{number}-q", f"{need}: Psalm 1:{number + 1}", "prayer10", day="")
    _doc(published, "0101-f", "Strength for a Long Afternoon: Isaiah 40:31 | The Midday Watch",
         "prayer3")
    monkeypatch.setattr(gb, "PUBLISHED_DIR", published)
    monkeypatch.setattr(gb, "QUEUE_DIR", queue)
    return published, queue


JOB = {"id": "0820", "scripture": "Psalm 32:8", "theme": "Guidance for the road ahead"}


def test_a_draft_title_in_the_tired_mould_is_replaced_with_one_call(titles, capsys):
    good = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    brain = _Brain([good])
    draft = SCRIPT.format(title="When You Cannot See the Road: Psalm 32:8 | The Guided Path")
    out = brain.vary_title(draft, JOB)
    assert gb.job_front_matter(out)["title"] == good
    assert out.split("---", 2)[2] == draft.split("---", 2)[2], "the prayer is untouched"
    assert len(brain.calls) == 1 and brain.calls[0][0] == "accepted-model"
    prompt = brain.calls[0][1]
    assert "was drafted under this title" in prompt and "already open with 'When'" in prompt


def test_the_old_form_from_the_author_is_replaced(titles):
    good = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    brain = _Brain([good])
    out = brain.vary_title(SCRIPT.format(title=OLD), JOB)
    assert gb.job_front_matter(out)["title"] == good


def test_a_draft_worded_like_another_channels_title_is_replaced(titles):
    good = "Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path"
    brain = _Brain([good])
    out = brain.vary_title(
        SCRIPT.format(title="Strength for the Long Afternoon: Psalm 32:8 | The Guided Path"), JOB)
    assert gb.job_front_matter(out)["title"] == good
    assert "The Midday Watch" not in brain.calls[0][1]


def test_a_title_that_is_its_own_costs_no_call(titles):
    brain = _Brain([])
    draft = SCRIPT.format(title="Counsel for a Hard Choice Ahead: Psalm 32:8 | The Guided Path")
    assert brain.vary_title(draft, JOB) == draft and brain.calls == []


def test_a_bad_second_answer_keeps_the_script_and_says_so(titles, capsys):
    brain = _Brain(["When You Are Lost Again: Psalm 32:8 | The Guided Path"])
    draft = SCRIPT.format(title="When You Cannot See the Road: Psalm 32:8 | The Guided Path")
    assert brain.vary_title(draft, JOB) == draft, "a thousand words are not lost for a title"
    assert len(brain.calls) == 1, "one request, never a loop"
    assert "::warning title=Title reads like the others (prayer10)" in capsys.readouterr().out


def test_no_model_means_a_warning_and_the_same_script(titles, capsys):
    brain = _Brain([], available=False)
    draft = SCRIPT.format(title="When You Cannot See the Road: Psalm 32:8 | The Guided Path")
    assert brain.vary_title(draft, JOB) == draft and brain.calls == []
    assert "::warning title=Title reads like the others" in capsys.readouterr().out


def test_a_crash_in_the_check_never_costs_a_script(titles, monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise OSError("disk")
    monkeypatch.setattr(tv, "variety_for", boom)
    draft = SCRIPT.format(title="When You Cannot See the Road: Psalm 32:8 | The Guided Path")
    assert _Brain([]).vary_title(draft, JOB) == draft
    assert "Title check skipped" in capsys.readouterr().out


def test_the_authoring_standard_tells_the_writer_to_vary_the_opening():
    from pipeline.brain_equipment.equipment_registry import get_viewer_first_standard
    standard = get_viewer_first_standard()
    assert "Do not begin every title the same way" in standard
    assert "compile_full_brain_prompt"  # the standard is part of every authoring prompt
    from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
    assert "Do not begin every title the same way" in compile_full_brain_prompt("prayer10")


# --------------------------------------------------------------------------- #
# The daily measure
# --------------------------------------------------------------------------- #
def _row(rows, channel):
    return next(row for row in rows if row.channel == channel)


def test_the_measure_reports_the_long_prayer_titles(tmp_path):
    published, queue, specs = tmp_path / "published", tmp_path / "queue", tmp_path / "specs"
    specs.mkdir()
    _doc(published, "0801-a", "Psalm 32:8 Guidance Prayer | The Guided Path", "prayer10")
    _doc(published, "0802-b", "James 1:5 Guidance Prayer | The Guided Path", "prayer10")
    for number, need in enumerate(WHENS):
        _doc(queue, f"081{number}-q", f"{need}: Psalm 1:{number + 1}", "prayer10", day="")
    _doc(queue, "0815-q", "Psalm 5:8 Guidance Prayer | The Guided Path", "prayer10", day="")
    _doc(published, "0711-g", "When Every Day Feels Heavy: Psalm 118:24 | The Praise Garden",
         "prayer9")

    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs, queue_dir=queue)
    path = _row(rows, "prayer10")
    assert path.old_form_titles == 2, "only published titles wait for the retitler"
    assert (path.need_titles, path.tired_opening, path.tired_opening_uses) == (4, "when", 4)
    assert path.needs_alike_elsewhere == ["When Every Plan Feels Heavy"]
    assert any("4 of its last 4 long-prayer titles open with 'When'" in note
               for note in path.notes)
    assert any("almost as another channel does" in note for note in path.notes)
    garden = _row(rows, "prayer9")
    assert garden.needs_alike_elsewhere == ["When Every Day Feels Heavy"]
    assert garden.tired_opening == "" and garden.old_form_titles == 0

    report = cp.render(rows)
    assert "#### Long-prayer titles" in report
    assert "| The Guided Path | 2 | 4 | 'When' (4) | 1 |" in report
    assert "| The Secret Place | 0 | 0 | none | 0 |" in report


def test_a_measure_of_a_named_folder_does_not_read_the_real_queue(tmp_path):
    published, specs = tmp_path / "published", tmp_path / "specs"
    published.mkdir()
    specs.mkdir()
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert all(row.need_titles == 0 and not row.notes for row in rows)


def test_the_real_repository_is_measured_without_error():
    rows = cp.measure()
    assert len(rows) == 10
    assert sum(row.need_titles for row in rows) > 0
    json.dumps([row.needs_alike_elsewhere for row in rows])
