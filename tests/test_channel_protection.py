"""The daily measure of how alike the channels look (`scripts/channel_protection.py`).

It reads what was published and what was written, and reports. It must count
rightly, must not call scripture or a closing invitation "shared", and must
never fail a run for what it finds.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from scripts import channel_protection as cp

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc)


def _receipt(folder: Path, name: str, *, channel: str, title: str, day: str,
             short: bool = True, niche: str = "faith and prayer") -> None:
    channel_line = f"channel: {channel}\n" if channel else ""
    folder.joinpath(f"{'short-' if short else ''}{name}.md").write_text(
        f'---\nid: "{name}"\ntitle: "{title}"\n{channel_line}'
        f'format: {"short" if short else "long"}\nniche: {niche}\n'
        f'published_at: "{day}T08:00:00Z"\n---\n\nbody\n', encoding="utf-8")


def _spec(folder: Path, key: str, channel: str, lines: list[str]) -> None:
    captions = [[i * 7, i * 7 + 6, line] for i, line in enumerate(lines)]
    folder.joinpath(f"{key}.json").write_text(
        json.dumps({"key": key, "channel": channel, "captions": captions}), encoding="utf-8")


@pytest.fixture()
def dirs(tmp_path):
    published, specs = tmp_path / "published", tmp_path / "specs"
    published.mkdir()
    specs.mkdir()
    return published, specs


def _row(rows, channel):
    return next(row for row in rows if row.channel == channel)


def test_uploads_are_counted_for_the_last_whole_day_and_by_kind(dirs):
    published, specs = dirs
    for n in range(5):
        _receipt(published, f"a{n}", channel="prayer2", day="2026-11-15",
                 title=f"Say This Psalm {n + 1}:1 Prayer at Sunrise | Awaken The Dawn {n} #Shorts")
    _receipt(published, "long1", channel="prayer2", day="2026-11-15", short=False,
             title="Psalm 5:3 Morning Prayer | The Morning Altar")
    _receipt(published, "today", channel="prayer2", day="2026-11-16",
             title="Say This Psalm 9:1 Prayer at Sunrise | Sing To Him #Shorts")
    _receipt(published, "old", channel="prayer2", day="2026-11-13",
             title="Say This Psalm 8:1 Prayer at Sunrise | Look Up Today #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer2")
    assert (row.long_last_day, row.shorts_last_day) == (1, 5)
    assert row.per_day == 3.5, "seven videos over the two days it published in the window"


def test_a_receipt_without_a_channel_is_the_first_channels(dirs):
    published, specs = dirs
    _receipt(published, "x", channel="", day="2026-11-15",
             title="Say This Psalm 91 Prayer Before You Sleep | Under His Wings #Shorts")
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert _row(rows, "secret-place").shorts_last_day == 1


def test_videos_from_before_the_prayer_channels_are_not_counted(dirs):
    published, specs = dirs
    _receipt(published, "enron", channel="", day="2026-11-15", niche="finance and business",
             title="How Enron Faked $70 Billion in Plain Sight #Shorts")
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert sum(r.shorts_last_day + r.long_last_day for r in rows) == 0


@pytest.mark.parametrize("title, weak", [
    ("Say This Psalm 5:3 Prayer at Sunrise | The Morning Altar #Shorts", True),
    ("Say This Psalm 5:3 Prayer at Sunrise | Psalm 5:3 #Shorts", True),
    ("Say This Psalm 5:3 Prayer at Sunrise | Today #Shorts", True),
    ("Say This Psalm 5:3 Prayer at Sunrise | Of Light #Shorts", True),
    ("Say This Psalm 5:3 Prayer at Sunrise #Shorts", True),
    ("Say This Psalm 5:3 Prayer at Sunrise | Awaken The Dawn #Shorts", False),
])
def test_a_title_is_weak_when_the_words_after_the_bar_say_nothing(dirs, title, weak):
    published, specs = dirs
    _receipt(published, "one", channel="prayer2", day="2026-11-15", title=title)
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer2")
    assert (row.titles_read, row.weak_titles) == (1, int(weak))


def test_only_the_most_recent_titles_are_read_so_a_fix_shows(dirs):
    published, specs = dirs
    for n in range(cp.RECENT_TITLES):
        _receipt(published, f"old{n}", channel="prayer3", day="2026-11-10",
                 title=f"Say This Psalm {n + 1}:1 Prayer at Noon | The Midday Watch #Shorts")
    for n in range(cp.RECENT_TITLES):
        _receipt(published, f"new{n}", channel="prayer3", day="2026-11-15",
                 title=f"Say This Psalm {n + 30}:1 Prayer at Noon | Lay The Weight Down {n} #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer3")
    assert (row.titles_read, row.weak_titles, row.notes) == (cp.RECENT_TITLES, 0, [])


def test_a_few_weak_titles_on_a_new_channel_are_not_called_a_pattern(dirs):
    published, specs = dirs
    for n in range(cp.MIN_TITLES - 1):
        _receipt(published, f"n{n}", channel="prayer9", day="2026-11-15",
                 title=f"Pray This Psalm {n + 1}:1 Prayer of Thanksgiving | The Praise Garden #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer9")
    assert row.weak_titles == cp.MIN_TITLES - 1 and row.notes == []


def test_many_weak_titles_are_said(dirs):
    published, specs = dirs
    for n in range(cp.MIN_TITLES):
        _receipt(published, f"n{n}", channel="prayer9", day="2026-11-15",
                 title=f"Pray This Psalm {n + 1}:1 Prayer of Thanksgiving | The Praise Garden #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer9")
    assert len(row.notes) == 1 and "say nothing of their own" in row.notes[0]


def test_a_title_used_twice_is_counted(dirs):
    published, specs = dirs
    for name in ("a", "b", "c"):
        _receipt(published, name, channel="prayer4", day="2026-11-15",
                 title="Pray This Psalm 63:6 Midnight Prayer | Remember Him In The Night #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer4")
    assert row.repeated_titles == 2


OWN = "Father, quiet the worry that has followed me through every hour of this long day."


def test_a_prayer_sentence_spoken_on_two_channels_is_counted_on_both(dirs):
    published, specs = dirs
    _spec(specs, "short-a", "prayer2", [OWN, "Lord, wake my heart to Your mercy before the day begins again."])
    _spec(specs, "short-b", "prayer3", [OWN])
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert _row(rows, "prayer2").shared_sentences == 1
    assert _row(rows, "prayer3").shared_sentences == 1
    assert "also spoken on another channel" in _row(rows, "prayer3").notes[0]
    assert _row(rows, "prayer4").shared_sentences == 0


def test_the_same_sentence_twice_on_one_channel_is_not_a_network(dirs):
    published, specs = dirs
    _spec(specs, "short-a", "prayer2", [OWN])
    _spec(specs, "short-b", "prayer2", [OWN])
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert _row(rows, "prayer2").shared_sentences == 0


def test_two_channels_may_pray_the_same_verse(dirs):
    """Whatever the commas, and with the speaker's own lead-in before it."""
    published, specs = dirs
    verse = "Yea, though I walk through the valley of the shadow of death, I will fear no evil: for thou art with me."
    _spec(specs, "short-a", "secret-place", [verse])
    _spec(specs, "short-b", "prayer8", [verse.replace(",", "").replace(":", ",")])
    led = "Psalm twenty-three says, " + verse
    _spec(specs, "short-c", "prayer6", [led])
    _spec(specs, "short-d", "prayer10", [led])
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert sum(row.shared_sentences for row in rows) == 0


def test_a_closing_invitation_that_names_a_channel_is_not_shared_wording(dirs):
    published, specs = dirs
    line = "Type Amen and subscribe to The Morning Altar to begin every sunrise in prayer."
    _spec(specs, "short-a", "prayer2", [line])
    _spec(specs, "short-b", "prayer3", [line])
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    assert sum(row.shared_sentences for row in rows) == 0


def test_a_spec_that_cannot_be_read_is_passed_over(dirs):
    published, specs = dirs
    specs.joinpath("short-broken.json").write_text("{not json", encoding="utf-8")
    assert cp.shared_sentences(specs) == {}


def test_the_report_names_every_channel_and_says_whose_numbers_these_are(dirs):
    published, specs = dirs
    report = cp.render(cp.measure(today=NOW, published_dir=published, spec_dir=specs))
    assert "The Secret Place" in report and "The Guided Path" in report
    assert "YouTube publishes no numbers" in report


def test_what_it_finds_never_fails_the_run(dirs, monkeypatch, capsys, tmp_path):
    published, specs = dirs
    for n in range(cp.MIN_TITLES):
        _receipt(published, f"n{n}", channel="prayer9", day="2026-11-15",
                 title=f"Pray This Psalm {n + 1}:1 Prayer of Thanksgiving | The Praise Garden #Shorts")
    monkeypatch.setattr(cp, "PUBLISHED_DIR", published)
    monkeypatch.setattr(cp, "SPEC_DIR", specs)
    # The measure also reads the queued long-prayer titles since 16 November.
    monkeypatch.setattr(cp, "QUEUE_DIR", tmp_path / "queue")
    # ...and the network's passage ledger since 16 November: its Shorts come from
    # the real shorts queue unless the folder is named.
    monkeypatch.setattr(cp, "SHORTS_QUEUE_DIR", tmp_path / "shorts-queue")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert cp.main([]) == 0
    out = capsys.readouterr().out
    warnings = [line for line in out.splitlines() if line.startswith("::warning")]
    assert any("say nothing of their own" in line for line in warnings), warnings
    for line in warnings:
        # A comma would end the annotation's title.
        title = line.split("::")[1]
        assert "," not in title, line
    assert "How alike the channels look" in summary.read_text(encoding="utf-8")


def test_json_output_is_one_row_per_channel(dirs, monkeypatch, capsys):
    published, specs = dirs
    monkeypatch.setattr(cp, "PUBLISHED_DIR", published)
    monkeypatch.setattr(cp, "SPEC_DIR", specs)
    assert cp.main(["--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [row["channel"] for row in rows][:2] == ["secret-place", "prayer2"]
    assert {"per_day", "weak_titles", "weak_share", "shared_sentences"} <= set(rows[0])


def test_a_crash_is_not_swallowed(monkeypatch):
    def boom(**_):
        raise RuntimeError("cannot count")
    monkeypatch.setattr(cp, "measure", boom)
    with pytest.raises(RuntimeError):
        cp.main([])


def test_it_runs_on_the_real_repository():
    rows = cp.measure()
    assert len(rows) >= 10
    assert all(row.shared_sentences == 0 for row in rows), [
        (row.name, row.shared_sentences) for row in rows if row.shared_sentences]


class TestTheHealthCheckRunsIt:
    @pytest.fixture()
    def step(self):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / "automation-health.yml")
                             .read_text(encoding="utf-8"))
        steps = [s for job in doc["jobs"].values() for s in job.get("steps", [])
                 if "scripts.channel_protection" in str(s.get("run", ""))]
        assert len(steps) == 1
        return steps[0]

    def test_it_runs_even_when_an_earlier_check_is_red(self, step):
        assert "always()" in step["if"]

    def test_a_merge_does_not_run_it(self, step):
        assert "github.event_name != 'push'" in step["if"]

    def test_it_needs_no_token_and_writes_nothing(self, step):
        assert "env" not in step
        assert "continue-on-error" not in step, "a crash must show"
