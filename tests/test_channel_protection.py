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
    assert (row.titles_read, row.weak_titles) == (cp.RECENT_TITLES, 0)
    # The only note is the frame note (one mould, 20 of 20): no weak title is counted.
    assert [note for note in row.notes if "say nothing of their own" not in note] == \
        ["20 of its last 20 Short titles are built on one frame: "
         "'Say This {passage} Prayer at Noon'"]


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
    weak = [note for note in row.notes if "say nothing of their own" in note]
    assert len(weak) == 1, row.notes


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


def test_the_frame_is_the_words_before_the_bar_without_the_passage():
    """One frame per channel is the mould; the passage is the only thing swapped."""
    assert cp.short_frame(
        "Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts") == \
        "say this prayer before you sleep"
    # Two passages, one frame: that is the thing being counted.
    assert cp.short_frame(
        "Say This Psalm 23 Prayer Before You Sleep | Divine Peace #Shorts") == \
        "say this prayer before you sleep"
    assert cp.frame_text(
        "Pray This 2 Samuel 22:31 Prayer for Divine Protection | Daily Protection #Shorts") == \
        "Pray This {passage} Prayer for Divine Protection"


def test_a_numbered_book_is_read_as_the_passage_not_as_this_two():
    """`1 Peter 5:7` and `2 Samuel 22:31` are passages, not "This 1" and "This 2".

    The first reference matcher accepted any capitalised word before a number, so
    it read the `This` of "Say This 1 Peter 5:7 ..." and the `2` after it as the
    passage, and every check that compares a title's hook with its own passage was
    made against the wrong words on the 19 published Short titles that name a
    numbered book.
    """
    label, hook = cp.split_title(
        "Say This 1 Peter 5:7 Prayer Before You Sleep | 1 Peter 5:7 #Shorts")
    assert label == "1 Peter 5:7"
    assert hook == "1 Peter 5:7"
    assert cp.short_frame(
        "Say This 1 Peter 5:7 Prayer Before You Sleep | 1 Peter 5:7 #Shorts") == \
        "say this prayer before you sleep"
    assert cp.split_title(
        "Pray This 2 Samuel 22:31 Prayer for Divine Protection | Daily Protection #Shorts")[0] == \
        "2 Samuel 22:31"


def test_a_channel_with_one_frame_is_said_so(dirs):
    published, specs = dirs
    for n in range(9):
        _receipt(published, f"b{n}", channel="prayer3", day=f"2026-11-{n + 5:02d}",
                 title=f"Say This Psalm {n + 2}:1 Prayer at Noon | Hook {n} #Shorts")
    row = _row(cp.measure(today=NOW, published_dir=published, spec_dir=specs), "prayer3")
    assert row.titles_read == 9
    assert row.frames_used == 1
    assert row.frame_titles == 9
    assert row.frame_text == "Say This {passage} Prayer at Noon"
    assert any("built on one frame" in note for note in row.notes)


def test_more_than_one_frame_is_counted_and_the_common_one_named(dirs):
    published, specs = dirs
    for n in range(5):
        _receipt(published, f"c{n}", channel="prayer9", day=f"2026-11-{n + 5:02d}",
                 title=f"Pray This Psalm {n + 100}:1 Prayer of Thanksgiving | Thanks {n} #Shorts")
    for n in range(3):
        _receipt(published, f"d{n}", channel="prayer9", day=f"2026-11-{n + 10:02d}",
                 title=f"Psalm {n + 120}:1 Thanksgiving Prayer | Praise {n} #Shorts")
    for n in range(6):
        _receipt(published, f"e{n}", channel="prayer2", day=f"2026-11-{n + 5:02d}",
                 title=f"Say This Psalm {n + 130}:1 Prayer at Sunrise | Dawn {n} #Shorts")
    for n in range(2):
        _receipt(published, f"f{n}", channel="prayer2", day=f"2026-11-{n + 12:02d}",
                 title=f"Psalm {n + 150}:1 Prayer at Sunrise | Light {n} #Shorts")
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    row = _row(rows, "prayer9")
    assert row.titles_read == 8
    assert row.frames_used == 2
    assert row.frame_titles == 5
    # Five of eight is under the three-quarter mark, so nothing is said about it.
    assert not any("built on one frame" in note for note in row.notes)
    # Six of eight is exactly the mark, so it is.
    common = _row(rows, "prayer2")
    assert (common.frames_used, common.frame_titles) == (2, 6)
    assert any("built on one frame" in note for note in common.notes)


def test_the_network_opening_is_counted_across_channels(dirs):
    """The frame differs per channel; the opening is what the network shares."""
    published, _ = dirs
    for n in range(3):
        _receipt(published, f"e{n}", channel="prayer2", day="2026-11-15",
                 title=f"Say This Psalm {n + 1}:1 Prayer at Sunrise | Hook {n} #Shorts")
    for n in range(2):
        _receipt(published, f"f{n}", channel="prayer3", day="2026-11-15",
                 title=f"Say This Psalm {n + 40}:1 Prayer at Noon | Hook {n} #Shorts")
    _receipt(published, "g0", channel="prayer9", day="2026-11-15",
             title="How Enron Faked A Billion In Plain Sight #Shorts")
    figure = cp.network_openers(published_dir=published)
    assert figure["titles"] == 6
    assert figure["shared"] == 5           # the five "Say This" ones
    assert figure["opener"] == "say this"
    assert figure["uses"] == 5
    assert figure["openings"] == 2


def test_the_frame_section_is_in_the_report_and_reads_the_rows(dirs):
    published, specs = dirs
    for n in range(9):
        _receipt(published, f"h{n}", channel="prayer4", day=f"2026-11-{n + 5:02d}",
                 title=f"Pray This Psalm {n + 2}:1 Midnight Prayer | Watch {n} #Shorts")
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    report = cp.render(rows, cp.network_openers(published_dir=published))
    assert "#### Short titles built on one frame" in report
    assert "`Pray This {passage} Midnight Prayer`" in report
    assert "9 of 9" in report
    assert "published Short titles open with two words another channel also uses" in report
    # Without the figure the section still renders.
    assert "#### Short titles built on one frame" in cp.render(rows)


def test_backdrop_plates_count_the_fallback_photographs_and_who_shares_them(dirs):
    """The plate measure: a small pool, and a photograph on more than one channel.

    `curated_backdrop_for` hashes the job id into a pool of cleared plates, so the
    figure this reports is the pool's size and the sharing it forces — not what any
    single frame used.
    """
    published, _specs = dirs
    for n in range(8):
        _receipt(published, f"0{n}11", channel="secret-place" if n < 4 else "prayer8",
                 day="2026-11-15", short=False,
                 title=f"Psalm {n + 11}:1 Night Prayer | The Secret Place")
    plates = cp.backdrop_plates(published_dir=published)
    assert plates["videos"] == 8
    assert plates["plates"] <= 8
    assert plates["plates"] <= plates["pool_nocturnal"] + plates["pool_daylight"]
    assert plates["top_videos"] >= 1
    assert plates["top_plate"]
    # Pairs are counted for every two videos on the same plate, and the ones on
    # different channels are named separately because only those are a network.
    assert plates["shared_pairs"] <= plates["pairs"]


def test_backdrop_plates_ignores_shorts_and_reads_nothing_else(dirs):
    published, _specs = dirs
    _receipt(published, "s1", channel="prayer3", day="2026-11-15", short=True,
             title="Say This Psalm 5:3 Prayer at Noon | Stand Still #Shorts")
    assert cp.backdrop_plates(published_dir=published)["videos"] == 0


def test_the_report_says_where_the_backdrop_photographs_come_from(dirs):
    published, specs = dirs
    for n in range(6):
        _receipt(published, f"1{n}22", channel="prayer5", day="2026-11-15", short=False,
                 title=f"Psalm {n + 20}:1 Family Prayer | The Family Altar")
    rows = cp.measure(today=NOW, published_dir=published, spec_dir=specs)
    network = cp.network_openers(published_dir=published)
    network["plates"] = cp.backdrop_plates(published_dir=published)
    report = cp.render(rows, network)
    assert "#### Thumbnail backdrops" in report
    assert "photographs" in report
    assert "fallback" in report
