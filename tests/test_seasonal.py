"""The church year: seasonal Shorts are written ahead, go first on their days, and are withdrawn after."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from pipeline import evergreen_shorts as ev
from pipeline import gemini_brain as gb
from pipeline import scripture_text as st
from pipeline import seasonal as se
from pipeline import short_release as sr
from pipeline import short_script as ss
from pipeline.channels import scheduled_channels


# --------------------------------------------------------------------------- #
# The calendar
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("year, easter, advent", [
    (2026, date(2026, 4, 5), date(2026, 11, 29)),
    (2027, date(2027, 3, 28), date(2027, 11, 28)),
    (2028, date(2028, 4, 16), date(2028, 12, 3)),
    (2030, date(2030, 4, 21), date(2030, 12, 1)),
])
def test_moving_dates_are_worked_out_not_listed(year, easter, advent):
    assert se.easter_sunday(year) == easter
    assert se.advent_sunday(year) == advent
    assert se.advent_sunday(year).weekday() == 6 and se.easter_sunday(year).weekday() == 6


def test_seasons_of_2026_and_the_new_year_that_crosses_into_2027():
    by_day = lambda d: [s.name for s in se.open_seasons(d)]
    assert by_day(date(2026, 11, 28)) == []
    assert by_day(date(2026, 11, 29)) == ["advent"]
    assert by_day(date(2026, 12, 23)) == ["advent"]
    assert by_day(date(2026, 12, 25)) == ["christmas"]
    assert by_day(date(2026, 12, 27)) == []
    assert by_day(date(2026, 12, 31)) == ["new_year"]
    assert by_day(date(2027, 1, 1)) == ["new_year"]
    assert by_day(date(2027, 1, 3)) == []
    assert by_day(date(2027, 3, 22)) == ["holy_week"]
    assert by_day(date(2027, 3, 28)) == ["easter"]
    assert se.next_season(date(2026, 11, 14)).name == "advent"


def test_the_calendar_day_is_read_in_nigeria():
    late = datetime(2026, 12, 23, 23, 30, tzinfo=timezone.utc)   # 00:30 on the 24th in Lagos
    assert se.today(late) == date(2026, 12, 24)


def test_a_seasons_shorts_are_spread_across_it_and_written_two_days_ahead():
    advent = se.due("prayer2", date(2026, 11, 27))
    assert [d.reference for d in advent] == [se.PASSAGES["advent"]["prayer2"][0]]
    assert advent[0].not_before == date(2026, 11, 29) and advent[0].not_after == date(2026, 12, 23)
    assert se.due("prayer2", date(2026, 11, 26)) == []
    both = se.due("prayer2", date(2026, 12, 10))
    assert [d.not_before for d in both] == [date(2026, 11, 29), date(2026, 12, 11)]
    christmas = [d for d in se.due("prayer2", date(2026, 12, 23)) if d.season.name == "christmas"]
    assert [d.not_before for d in christmas] == [date(2026, 12, 24), date(2026, 12, 25)]
    crossover = se.due("prayer9", date(2026, 12, 31))
    assert [d.not_before for d in crossover] == [date(2026, 12, 30), date(2027, 1, 1)]
    assert se.due("prayer9", date(2027, 1, 2)) and not se.due("prayer9", date(2027, 1, 3))


# --------------------------------------------------------------------------- #
# The passages
# --------------------------------------------------------------------------- #
def _key(reference: str):
    book, chapter, verses = st.parse_reference(reference)
    return book, chapter, (verses or [None])[0]


def test_every_channel_has_passages_for_every_season_and_they_exist():
    assert set(se.PASSAGES) == set(se.OCCASIONS)
    for season, table in se.PASSAGES.items():
        assert set(table) == set(scheduled_channels()), season
        for channel, references in table.items():
            assert references, (season, channel)
            for reference in references:
                assert st.exists(reference), (season, channel, reference)


def test_no_seasonal_passage_is_given_to_two_channels_or_is_on_another_channels_list():
    from scripts.continuous_research import ROADMAPS

    elsewhere: dict[tuple, set[str]] = {}
    for channel, references in ev.EVERGREEN.items():
        for reference in references:
            elsewhere.setdefault(_key(reference), set()).add(channel)
    for channel, rows in ROADMAPS.items():
        for row in rows:
            elsewhere.setdefault(_key(row["scripture"]), set()).add(channel)
    seen: dict[tuple, tuple[str, str]] = {}
    for season, table in se.PASSAGES.items():
        for channel, references in table.items():
            for reference in references:
                key = _key(reference)
                assert key not in seen, f"{reference}: {season}/{channel} and {seen[key]}"
                seen[key] = (season, channel)
                others = elsewhere.get(key, set()) - {channel}
                assert not others, f"{reference} ({season}/{channel}) is also on {sorted(others)}"


def test_the_writer_is_told_what_day_the_short_is_for():
    prompt = ss.build_prompt("Isaiah 9:6", key="short-morningisaiah9v6", channel_id="prayer2",
                             avoid_openings=[], occasion=se.OCCASIONS["christmas"])
    assert "THE DAY THIS SHORT IS FOR" in prompt and "birth of Jesus Christ" in prompt
    assert "Do not name a date or a year" in prompt
    plain = ss.build_prompt("Isaiah 9:6", key="short-morningisaiah9v6", channel_id="prayer2",
                            avoid_openings=[])
    assert "THE DAY THIS SHORT IS FOR" not in plain


# --------------------------------------------------------------------------- #
# The queue
# --------------------------------------------------------------------------- #
def _spec(key: str, scripture: str, channel: str) -> dict:
    verse = " ".join(v.text for v in st.passage(scripture))
    lines = [
        "When the weight you carried all day will not lift, this word is for you tonight.",
        verse,
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
                       "kicker": "A WORD FOR TODAY", "sub": "REST IN WHAT HE SAID",
                       "cam": "push_in", "focus": [0.5, 0.5]})
        start = stop + 1
    return {
        "key": key, "channel": channel, "scripture": scripture,
        "title": ["A WORD", "FOR TODAY"],
        "poster": ["REST TODAY", "IN HIS WORD", "A PRAYER FOR", "A QUIET MIND"],
        "end": ["SUBSCRIBE", "A prayer every day"],
        "stock_queries": [f"calm sky {i}" for i in range(len(lines))],
        "scenes": scenes, "captions": captions, "kinetic_phrases": phrases, "beats": [],
    }


@pytest.fixture
def world(tmp_path, monkeypatch):
    queue, specs, published = tmp_path / "queue", tmp_path / "specs", tmp_path / "published"
    for directory in (queue, specs, published):
        directory.mkdir()
    monkeypatch.setattr(gb, "SHORTS_QUEUE_DIR", queue)
    monkeypatch.setattr(sr, "SHORTS_QUEUE_DIR", queue)
    monkeypatch.setattr(ss, "SPEC_DIR", specs)
    monkeypatch.setattr(gb, "PUBLISHED_DIR", published)
    monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "longform-queue")
    monkeypatch.setattr(sr, "_renderer_script_keys", lambda: set(ss.authored_keys()))
    monkeypatch.setattr(sr, "resolve_edition", lambda key, channel_id=None: SimpleNamespace(slug=key))
    monkeypatch.setattr(ev, "used_references", lambda channel, **_k: set())
    monkeypatch.setattr(ev, "_roadmap_ahead", lambda channel, taken: [])
    monkeypatch.setitem(ev.EVERGREEN, "prayer2", ("Psalm 23:1", "Psalm 121:1-2"))
    # Advent is still open until 23 December; these tests are about Christmas.
    monkeypatch.setitem(se.PASSAGES["advent"], "prayer2", ())
    monkeypatch.setenv("CHANNEL_ID", "prayer2")
    monkeypatch.setattr(gb.GeminiBrain, "is_api_available", lambda self: True)
    clock = SimpleNamespace(day=date(2026, 12, 23))
    monkeypatch.setattr(se, "today", lambda now=None: clock.day)
    brain = gb.GeminiBrain(api_key="fake", channel_id="prayer2")
    asked: list[tuple[str, str]] = []

    def author(_doc, key=None, *, scripture=None, occasion=""):
        asked.append((scripture, occasion))
        return ss.require_valid(ss.validate_spec(_spec(key, scripture, "prayer2"),
                                                 key=key, channel_id="prayer2"))

    monkeypatch.setattr(brain, "author_short_spec", author)

    def pick():
        return sr.select_next_queued_short(queue_dir=queue, published_dir=published,
                                           channel_id="prayer2")

    return SimpleNamespace(queue=queue, brain=brain, asked=asked, clock=clock, pick=pick)


def _fill(world, count: int = 10):
    """An already-full queue of ordinary Shorts."""
    for verse in range(1, count + 1):
        key = f"short-morningpsalm119v{verse}"
        ss.save_spec(ss.require_valid(ss.validate_spec(
            _spec(key, f"Psalm 119:{verse}", "prayer2"), key=key, channel_id="prayer2")))
        (world.queue / f"0000-{key}.yml").write_text(yaml.safe_dump(
            {"short": key, "channel": "prayer2", "scripture": f"Psalm 119:{verse}",
             "status": "approved", "standalone": True}, sort_keys=False), encoding="utf-8")


def test_seasonal_shorts_are_written_even_when_the_queue_is_full(world):
    _fill(world)
    rows = world.brain.replenish_shorts_queue(min_ready=10)
    seasonal = [row for row in rows if row["verdict"] == "authored"]
    christmas = se.PASSAGES["christmas"]["prayer2"]
    asked = [reference for reference, _ in world.asked]
    assert christmas[0] in asked and christmas[1] in asked, "both Christmas Shorts are due on the 23rd"
    assert len(seasonal) == se.MAX_SEASONAL_PER_PASS
    assert all("birth of Jesus Christ" in occasion for _, occasion in world.asked), \
        "each was written for its day"
    key = gb.short_key_for_reference("prayer2", christmas[0])
    data = yaml.safe_load((world.queue / f"0000-{key}.yml").read_text(encoding="utf-8"))
    assert data["season"] == "christmas" and data["source"] == "seasonal"
    assert data["not_before"] == "2026-12-24" and data["not_after"] == "2026-12-26"
    assert data["status"] == "approved" and data["standalone"] is True


def test_nothing_seasonal_is_written_outside_a_season(world):
    world.clock.day = date(2026, 11, 14)
    _fill(world)
    assert world.brain.replenish_shorts_queue(min_ready=10) == []
    assert world.asked == []


def test_a_seasonal_short_waits_for_its_day_then_goes_first_then_is_withdrawn(world):
    _fill(world, 3)
    world.brain.replenish_shorts_queue(min_ready=3)
    first, second = (gb.short_key_for_reference("prayer2", r) for r in se.PASSAGES["christmas"]["prayer2"])

    world.clock.day = date(2026, 12, 23)
    assert world.pick()[1] == "short-morningpsalm119v1", "not before Christmas Eve"

    world.clock.day = date(2026, 12, 24)
    assert world.pick()[1] == first, "first in line on its day, ahead of the ordinary queue"
    (world.queue / f"0000-{first}.yml").unlink()        # published
    assert world.pick()[1] == "short-morningpsalm119v1", "the second one is for Christmas Day"

    world.clock.day = date(2026, 12, 25)
    assert world.pick()[1] == second

    world.clock.day = date(2026, 12, 27)                 # never published; the season is over
    assert world.pick()[1] == "short-morningpsalm119v1"
    data = yaml.safe_load((world.queue / f"0000-{second}.yml").read_text(encoding="utf-8"))
    assert data["status"] == "draft" and data["season_closed"] is True
    assert "ended on 2026-12-26" in data["pause_reason"]


def test_a_withdrawn_short_returns_next_year_with_new_dates_and_is_not_rewritten(world):
    _fill(world, 3)
    world.brain.replenish_shorts_queue(min_ready=3)
    world.clock.day = date(2026, 12, 27)
    world.pick()                                          # withdraws both Christmas Shorts
    world.asked.clear()

    world.clock.day = date(2027, 12, 22)
    rows = world.brain.replenish_shorts_queue(min_ready=3)
    returned = [row for row in rows if row["verdict"] == "returned"]
    assert returned, rows
    christmas = set(se.PASSAGES["christmas"]["prayer2"])
    assert not christmas & {reference for reference, _ in world.asked}, "not written a second time"
    key = gb.short_key_for_reference("prayer2", se.PASSAGES["christmas"]["prayer2"][0])
    data = yaml.safe_load((world.queue / f"0000-{key}.yml").read_text(encoding="utf-8"))
    assert data["status"] == "approved" and data["not_before"] == "2027-12-24"
    assert "season_closed" not in data and "pause_reason" not in data


def test_a_short_waiting_for_its_day_is_not_counted_as_ready_to_publish(world):
    world.clock.day = date(2026, 12, 22)                  # two days before Christmas Eve
    world.brain.replenish_shorts_queue(min_ready=2)
    ordinary = [ref for ref, occasion in world.asked if not occasion]
    assert ordinary == ["Psalm 23:1", "Psalm 121:1-2"], \
        "the ordinary top-up still fills the queue; waiting seasonal Shorts do not count"


def test_manifest_dates_are_read_whether_yaml_gave_a_string_or_a_date():
    day = date(2026, 12, 25)
    assert se.manifest_window({}, day) == "none"
    assert se.manifest_window({"not_before": "2026-12-26"}, day) == "early"
    assert se.manifest_window({"not_before": date(2026, 12, 24), "not_after": "2026-12-26"}, day) == "open"
    assert se.manifest_window({"not_after": date(2026, 12, 24)}, day) == "closed"
    assert se.manifest_window({"not_before": "not a date"}, day) == "none"
