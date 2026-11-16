"""Lessons: phrases a channel tries in its titles, judged by its own videos.

The owner asked on 16 November 2026 that the channels learn on their own, from
what their audience searches for and from what the most-watched videos of their
kind are doing. These tests pin what that may and may not do.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
import yaml

from pipeline import lessons, performance_feedback as pf, retitle
from scripts import niche_reading

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date(2026, 11, 20)


def _day(back: int) -> str:
    return (TODAY - datetime.timedelta(days=back)).isoformat()


def _lesson(phrase="prayer before sleep", opened=10, **more):
    lesson = lessons._open(phrase, lessons.SEARCH_SOURCE, TODAY - datetime.timedelta(days=opened))
    lesson.update(more)
    return lesson


def _videos(with_views, without_views, back=5, phrase="Prayer Before Sleep"):
    rows = [{"title": f"{phrase} When Worry Stays: Psalm 4:8", "views": v, "published": _day(back)}
            for v in with_views]
    rows += [{"title": "Rest for a Tired Mind Tonight: Psalm 4:8", "views": v, "published": _day(back)}
             for v in without_views]
    return rows


# ------------------------------------------------------------ what a phrase is

@pytest.mark.parametrize("typed,phrase", [
    ("Prayer Before Sleep!", "prayer before sleep"),
    ("psalm 91 prayer for protection", "prayer for protection"),
    ("1 john 4:18 prayer against fear", "prayer against fear"),
    ("the prayer for my family", "prayer for my family"),
])
def test_a_phrase_is_plain_words_with_the_passage_taken_out(typed, phrase):
    assert lessons.clean_phrase(typed) == phrase


@pytest.mark.parametrize("typed", [
    "powerful night prayer", "miracle prayer for healing", "guaranteed breakthrough prayer",
    "the secret place", "morning altar prayers", "prayer", "prayer at 3 am", "night prayer 2026",
    "a very long search for a prayer to say before going to sleep tonight", "prayer video", "",
])
def test_promise_words_channel_names_and_noise_are_never_a_lesson(typed):
    assert lessons.clean_phrase(typed) == ""


def test_every_banned_title_word_is_refused_as_a_lesson():
    for banned in retitle.BANNED:
        assert lessons.clean_phrase(f"night {banned} prayer for rest") == "", banned


def test_a_phrase_that_only_repeats_the_channels_own_label_is_not_a_lesson():
    skip = lessons.label_words("secret-place")
    assert skip == {"night", "prayer"}
    assert lessons.clean_phrase("psalm 91 night prayer", skip) == ""
    assert lessons.clean_phrase("night prayer for sleep", skip) == "night prayer for sleep"


def test_search_terms_become_candidates_most_viewed_first():
    terms = [{"term": "psalm 23 prayer for peace", "views": 6}, {"term": "prayer before sleep", "views": 40},
             {"term": "prayer typed by two people", "views": 4}, {"term": "the secret place", "views": 90},
             {"term": "prayer before sleep", "views": 5}, "nonsense", {"term": "x", "views": "many"},
             {"term": "blackjack casino tonight", "views": 70}, {"term": "jesus de miguel", "views": 60}]
    assert lessons.candidates_from_search_terms(terms) == [
        ("prayer before sleep", lessons.SEARCH_SOURCE), ("prayer for peace", lessons.SEARCH_SOURCE)]


@pytest.mark.parametrize("term,about", [
    ("psalm 91", True), ("psalms 91", True), ("psalmul 91", True), ("deep sleep prayers", True),
    ("night prayer before going to bed", True), ("john 3 16", True), ("bible verses for sleep", True),
    ("melo funny moments", False), ("jesus de miguel", False), ("barbie", False), ("john funny moments", False),
    ("blackjack casino", False), ("google google", False), ("", False),
])
def test_a_search_term_is_a_lesson_only_when_it_is_about_prayer_or_scripture(term, about):
    # The right-hand column is the first real reading, The Secret Place, 16 November 2026.
    assert lessons.on_topic(term) is about


def test_a_phrase_may_only_use_words_the_channels_have_themselves_published(tmp_path):
    (tmp_path / "0001-a.md").write_text("---\ntitle: Rest Tonight\n---\nLet go of worry and fall asleep in "
                                        "God's presence, Prince of Peace.\n", encoding="utf-8")
    known = lessons.spoken_words(tmp_path)
    assert {"worry", "asleep", "presence", "prince"} <= known and "derek" not in known
    assert lessons.clean_phrase("let go of worry", known=known) == "let go of worry"
    assert lessons.clean_phrase("derek prince prayer", known=known) == "", "a preacher's name is not a lesson"
    titles = [("Derek Prince Prayer | Let Go of Worry Tonight", "UC_a"),
              ("Let Go of Worry: Derek Prince Prayer", "UC_b"),
              ("Derek Prince Prayer - Let Go of Worry and Rest", "UC_c")]
    assert lessons.phrases_from_titles(titles, known=known) == ["let go of worry"]
    assert "derek prince prayer" in lessons.phrases_from_titles(titles), "without the gate it would pass"
    real = lessons.spoken_words()
    assert len(real) > 3000 and "prayer" in real and "miguel" not in real and "barbie" not in real


# ------------------------------------------------- how a phrase is judged

def test_a_new_lesson_waits_for_videos_and_views():
    out = lessons.judge(_lesson(), _videos([3, 2], [1]), TODAY)
    assert out["status"] == "testing" and out["ratio"] is None
    assert (out["with_videos"], out["with_views"], out["without_videos"], out["without_views"]) == (2, 5, 1, 1)
    assert "a verdict needs 5 on each side and 100 views" in out["note"]


def test_a_phrase_whose_titles_drew_clearly_more_is_kept():
    out = lessons.judge(_lesson(), _videos([20] * 5, [8] * 5), TODAY)
    assert out["status"] == "kept" and out["ratio"] == 2.5 and out["decided"] == TODAY.isoformat()


def test_a_phrase_whose_titles_drew_clearly_fewer_is_dropped():
    out = lessons.judge(_lesson(), _videos([5] * 5, [20] * 5), TODAY)
    assert out["status"] == "dropped" and out["ratio"] == 0.25


def test_a_small_difference_is_no_verdict():
    out = lessons.judge(_lesson(), _videos([11] * 5, [10] * 5), TODAY)
    assert out["status"] == "testing" and out["ratio"] == 1.1 and out["decided"] == ""


def test_one_runaway_video_cannot_decide_a_phrase():
    out = lessons.judge(_lesson(), _videos([5000, 1, 1, 1, 1], [12] * 5), TODAY)
    assert out["with_views"] == lessons.VIEW_CAP + 4
    assert out["status"] == "testing", "10.8 a video against 12 is no verdict"


def test_a_video_is_counted_once_and_only_when_it_is_old_enough():
    videos = _videos([20] * 2, [8] * 2, back=5) + _videos([99], [99], back=2)   # two days old: too young
    first = lessons.judge(_lesson(), videos, TODAY)
    assert (first["with_videos"], first["without_videos"]) == (2, 2)
    again = lessons.judge(first, videos, TODAY)
    assert again == first, "the same day's videos are not counted twice"
    later = lessons.judge(first, videos, TODAY + datetime.timedelta(days=2))
    assert (later["with_videos"], later["without_videos"]) == (3, 3), "the young ones, now four days old"


def test_videos_published_before_the_lesson_opened_are_not_part_of_the_test():
    out = lessons.judge(_lesson(opened=5), _videos([50] * 5, [1] * 5, back=9), TODAY)
    assert (out["with_videos"], out["without_videos"]) == (0, 0) and out["status"] == "testing"


def test_an_empty_snapshot_does_not_move_the_count_forward():
    before = _lesson()
    assert lessons.judge(before, [], TODAY)["counted_through"] == before["counted_through"]


def test_a_lesson_with_no_verdict_in_sixty_days_gives_up_its_place():
    out = lessons.judge(_lesson(opened=lessons.EXPIRE_DAYS), _videos([1], [1]), TODAY)
    assert out["status"] == "retired" and out["note"].startswith("no verdict in 60 days")


def test_a_kept_phrase_that_falls_behind_is_dropped_and_one_that_only_narrows_stays():
    kept = _lesson(status="kept", with_videos=5, with_views=100, without_videos=5, without_views=40)
    narrowed = lessons.judge(kept, _videos([], [30] * 1), TODAY)       # 20 against 11.7 a video
    assert narrowed["status"] == "kept"
    fallen = lessons.judge(kept, _videos([0] * 15, [50] * 5), TODAY)   # 5 against 29 a video
    assert fallen["status"] == "dropped" and fallen["decided"] == TODAY.isoformat()


# ------------------------------------------------ what a channel tries

def test_only_three_phrases_are_tried_at_once_and_a_dropped_one_is_never_reopened():
    previous = [_lesson("prayer for peace", status="dropped", decided=_day(3))]
    candidates = [(p, lessons.SEARCH_SOURCE) for p in (
        "prayer for peace", "prayer before sleep", "prayer for my family", "prayer against fear",
        "prayer for healing")]
    out = lessons.update(previous, candidates, [], TODAY)
    assert [(l["phrase"], l["status"]) for l in out] == [
        ("prayer before sleep", "testing"), ("prayer for my family", "testing"),
        ("prayer against fear", "testing"), ("prayer for peace", "dropped")]
    assert lessons.update(out, candidates, [], TODAY) == out, "a second run on the same day changes nothing"


def test_no_two_channels_try_the_same_phrase():
    candidates = [("prayer before sleep", lessons.NICHE_SOURCE), ("prayer for my family", lessons.NICHE_SOURCE)]
    out = lessons.update([], candidates, [], TODAY, taken={"prayer before sleep"})
    assert [l["phrase"] for l in out] == ["prayer for my family"]
    # Two channels opened one phrase in the same hour: the later channel gives it up.
    raced = lessons.update([_lesson("prayer before sleep", opened=1)], [], [], TODAY,
                           taken={"prayer before sleep"}, taken_first={"prayer before sleep"})
    assert raced[0]["status"] == "retired" and "another of the channels" in raced[0]["note"]
    held = lessons.update([_lesson("prayer before sleep", opened=1)], [], [], TODAY,
                          taken={"prayer before sleep"})
    assert held[0]["status"] == "testing", "the earlier channel keeps it"


def test_a_damaged_record_is_left_out_and_the_rest_still_read():
    out = lessons.update([{"phrase": "prayer for peace"}, "x", None, _lesson(),
                          {"phrase": "most powerful prayer", "status": "kept", "opened": _day(9)}], [], [], TODAY)
    assert [l["phrase"] for l in out] == ["prayer before sleep"]


# ------------------------------------------------- what the writer is told

def test_the_title_writer_is_offered_phrases_never_ordered():
    block = lessons.prompt_block([_lesson("prayer before sleep", status="kept"), _lesson("prayer for peace"),
                                  _lesson("prayer for healing", status="dropped")])
    assert "Proven on this channel: prayer before sleep" in block
    assert "Being tried: prayer for peace" in block and "prayer for healing" not in block
    assert "true of THIS prayer" in block and "never copy another video's title" in block
    assert "Every other title rule still holds" in block
    assert lessons.prompt_block([]) == "" and lessons.prompt_block(None) == ""


def test_a_retitled_video_is_offered_only_what_is_proven():
    rows = [_lesson("prayer before sleep", status="kept"), _lesson("prayer for peace")]
    block = lessons.prompt_block(rows, proven_only=True)
    assert "prayer before sleep" in block and "prayer for peace" not in block
    assert lessons.prompt_block([_lesson("prayer for peace")], proven_only=True) == ""


def test_the_title_request_carries_the_block_and_the_checks_are_unchanged():
    target = retitle.Target(path=Path(), video_id="", title="Old", reference="Psalm 4:8",
                            channel="secret-place", views=0, age_days=9)
    words = lessons.prompt_block([_lesson()])
    assert words in retitle.build_prompt(target, "The Secret Place", words=words)
    assert "WORDS LISTENERS USE" not in retitle.build_prompt(target, "The Secret Place")
    # A lesson cannot buy a title past a refusal: the answer is still checked as any title is.
    title, why = retitle.propose_title(
        target, "The Secret Place", lambda prompt: "Powerful Prayer Before Sleep Tonight: Psalm 4:8",
        words=words)
    assert title is None and "powerful" in why


def test_the_brain_and_the_retitler_read_the_lessons():
    brain = (ROOT / "pipeline/gemini_brain.py").read_text(encoding="utf-8")
    assert "lessons_block(self.channel_id)" in brain and "words=lessons.block_for(self.channel_id)" in brain
    retitler = (ROOT / "scripts/retitle_unwatched.py").read_text(encoding="utf-8")
    assert "lessons.block_for(channel_id, proven_only=True)" in retitler


def test_a_channel_with_no_artifact_has_no_lessons(monkeypatch):
    monkeypatch.setattr(pf, "load_feedback_report", lambda path=None, channel_id=None: None)
    assert lessons.load("prayer9") == [] and lessons.block_for("prayer9") == ""


# ----------------------------------------- the feedback artifact carries them

def _snapshot(video_id, title, views, back):
    return {"video_id": video_id, "title": title, "snapshot_date": TODAY.isoformat(),
            "published_at": _day(back) + "T05:00:00Z", "views": views, "likes": 0, "comments": 0}


def test_the_report_holds_lessons_and_totals_and_no_video():
    snaps = [_snapshot(f"with{i}", "Prayer Before Sleep When Worry Stays: Psalm 4:8", 20, 5) for i in range(5)]
    snaps += [_snapshot(f"none{i}", "Rest for a Tired Mind Tonight: Psalm 4:8", 8, 5) for i in range(5)]
    snaps += [_snapshot("short1", "Prayer Before Sleep #shorts", 900, 5)]
    index = {row["video_id"]: {"title": row["title"], "format": "longform", "channel": "secret-place",
                               "scripture": "Psalm 4:8", "theme": "peace_rest", "published_on": _day(5)}
             for row in snaps}
    index["short1"]["format"] = "short"
    learning = {"previous": [_lesson()], "search_terms": [{"term": "prayer for peace", "views": 9},
                                                          {"term": "barbie doll house", "views": 99}],
                "niche": {"read_on": _day(1), "phrases": ["let go of worry"], "typical_minutes": 61},
                "taken": [], "taken_first": []}
    report = pf.build_feedback_report(snaps, index, TODAY, channel_id="secret-place", learning=learning)
    by_phrase = {l["phrase"]: l for l in report["lessons"]}
    assert by_phrase["prayer before sleep"]["status"] == "kept"
    assert by_phrase["prayer before sleep"]["with_videos"] == 5, "the Short is not a long prayer"
    assert by_phrase["prayer for peace"]["source"] == lessons.SEARCH_SOURCE
    assert by_phrase["let go of worry"]["source"] == lessons.NICHE_SOURCE
    assert len(by_phrase) == 3, "the search that was not about prayer opened nothing"
    assert report["niche"] == learning["niche"]
    assert any("Lesson 'prayer before sleep'" in line and "kept" in line for line in report["guidance"])
    text = json.dumps(report["lessons"]) + json.dumps(report["niche"])
    assert "with0" not in text and "Worry Stays" not in text, "totals only: no video id, no title"


def test_a_report_built_without_learning_has_no_lessons_and_reads_no_file():
    report = pf.build_feedback_report([], {}, TODAY)
    assert report["lessons"] == [] and "niche" not in report


def test_learning_is_read_from_the_channels_own_files(tmp_path, monkeypatch):
    (tmp_path / "secret-place.json").write_text(json.dumps(
        {"search_terms_90d": [{"term": "prayer before sleep", "views": 40, "watch_hours": 2.0}]}))
    niche_file = tmp_path / "niche.json"
    niche_file.write_text(json.dumps({"read_on": TODAY.isoformat(), "phrases": ["let go of worry"],
                                      "typical_minutes": 61, "titles": ["must not survive"]}))
    reports = {"secret-place": {"lessons": [_lesson("prayer for peace")]},
               "prayer2": {"lessons": [_lesson("prayer for my family")]},
               "prayer3": {"lessons": [_lesson("prayer for healing", status="dropped")]}}
    monkeypatch.setattr(pf, "load_feedback_report",
                        lambda path=None, channel_id=None: reports.get(channel_id or "secret-place"))
    got = pf.load_learning("secret-place", TODAY, niche_file=niche_file, analytics_dir=tmp_path)
    assert [l["phrase"] for l in got["previous"]] == ["prayer for peace"]
    assert got["search_terms"][0]["term"] == "prayer before sleep"
    assert got["niche"] == {"read_on": TODAY.isoformat(), "phrases": ["let go of worry"], "typical_minutes": 61}
    assert got["taken"] == ["prayer for my family"] and got["taken_first"] == []
    assert got["known"] == lessons.spoken_words()
    second = pf.load_learning("prayer2", TODAY, analytics_dir=tmp_path)
    assert second["taken_first"] == ["prayer for peace"] and second["search_terms"] == []
    assert second["niche"] is None


def test_a_niche_reading_older_than_thirty_days_is_not_carried_forward():
    fresh = {"niche": {"read_on": _day(30), "phrases": ["let go of worry"]}}
    stale = {"niche": {"read_on": _day(31), "phrases": ["let go of worry"]}}
    assert lessons.niche_block(fresh, TODAY)["phrases"] == ["let go of worry"]
    assert lessons.niche_block(stale, TODAY) is None
    assert lessons.niche_block({"niche": {"read_on": "soon"}}, TODAY) is None
    assert lessons.niche_block(None, TODAY) is None


# ------------------------------------------------------- the niche reading

NICHE = [
    ("Night Prayer Before Sleep | Fall Asleep in God's Presence (3 Hours)", "UC_a"),
    ("Fall Asleep in God's Presence: Psalm 91 Night Prayer", "UC_b"),
    ("A Night Prayer Before Sleep - Fall Asleep In God's Presence", "UC_c"),
    ("Prayer Before Sleep", "UC_d"), ("Prayer Before Sleep", "UC_e"), ("Prayer before sleep", "UC_f"),
    ("Bedtime Prayers for Deep Sleep and Peace of Mind | 8 HOURS", "UC_g"),
    ("Peace of Mind Tonight: Prayers for Deep Sleep", "UC_h"),
    ("Prayers for Deep Sleep | Let Go of Worry", "UC_i"),
    ("The Most Powerful Miracle Prayer Ever", "UC_j"), ("The Most Powerful Miracle Prayer Ever", "UC_k"),
    ("The Most Powerful Miracle Prayer Ever | Listen", "UC_l"),
    ("One Channel's Own Wording Repeated", "UC_m"), ("One Channel's Own Wording Repeated Again", "UC_m"),
    ("One Channel's Own Wording Repeated Thrice", "UC_m"),
]


def test_only_wording_shared_by_three_channels_survives_and_never_a_whole_title():
    phrases = lessons.phrases_from_titles(NICHE, lessons.label_words("secret-place"))
    assert phrases == ["asleep in god's presence", "prayers for deep sleep", "fall asleep"]
    assert "prayer before sleep" not in phrases, "it is the whole of three videos' titles"
    assert not any("powerful" in p or "miracle" in p or "ever" in p for p in phrases), \
        "a title that makes a banned promise is not read at all"
    assert not any("wording" in p for p in phrases), "one channel saying it three times is one channel"
    for phrase in phrases:
        assert 2 <= len(phrase.split()) <= 4


def test_two_channels_are_not_enough():
    assert lessons.phrases_from_titles(NICHE[:2], frozenset()) == []


class _Call:
    def __init__(self, answer):
        self.answer = answer

    def execute(self):
        return self.answer


class _YouTube:
    """A stand-in for the API client that records every question asked of it."""
    def __init__(self, titles):
        self.titles, self.asked = titles, []

    def search(self):
        return self

    def videos(self):
        return self

    def list(self, **kwargs):
        self.asked.append(kwargs)
        if "q" in kwargs:
            items = [{"id": {"videoId": f"v{n}"}, "snippet": {"title": title, "channelId": maker,
                                                              "channelTitle": f"Channel {maker}"}}
                     for n, (title, maker) in enumerate(self.titles)]
            items.append({"id": {"videoId": "ours"}, "snippet": {
                "title": "Fall Asleep in God's Presence", "channelId": "UC_ours",
                "channelTitle": "The Morning Altar"}})
            return _Call({"items": items})
        return _Call({"items": [{"id": i, "contentDetails": {"duration": "PT1H2M30S"}}
                                for i in kwargs["id"].split(",")]})


def test_one_reading_asks_two_searches_and_lengths_and_keeps_phrases_only(capsys):
    youtube = _YouTube(NICHE)
    block = niche_reading.read(youtube, "secret-place", TODAY)
    searches = [call for call in youtube.asked if "q" in call]
    assert [call["q"] for call in searches] == ["night prayer", "night prayer scripture"]
    for call in searches:
        assert call["order"] == "viewCount" and call["type"] == "video" and call["maxResults"] == 25
        assert call["videoDuration"] == "long" and call["publishedAfter"] == "2026-08-22T00:00:00Z"
        assert "pageToken" not in call
    lookups = [call for call in youtube.asked if "q" not in call]
    assert len(lookups) == 1 and lookups[0]["part"] == "contentDetails", "no view, like or subscriber count"
    assert "ours" not in lookups[0]["id"], "the owner's own channels are not the niche"
    assert block == {"read_on": TODAY.isoformat(), "typical_minutes": 62,
                     "phrases": ["asleep in god's presence", "prayers for deep sleep", "fall asleep"]}
    printed = capsys.readouterr().out
    assert "UC_" not in printed and "Fall Asleep" not in printed and "v0" not in printed


def test_a_fresh_reading_is_not_repeated_for_seven_days():
    assert niche_reading.due("secret-place", TODAY, {}) == (True, "no reading yet")
    ready, why = niche_reading.due("secret-place", TODAY, {"niche": {"read_on": _day(6)}})
    assert not ready and "next reading is on 2026-11-21" in why
    assert niche_reading.due("secret-place", TODAY, {"niche": {"read_on": _day(7)}})[0]


def test_a_reading_that_is_not_due_asks_youtube_nothing(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(niche_reading, "due", lambda channel, today: (False, "read 1 day(s) ago"))
    monkeypatch.setattr(niche_reading, "read", lambda *a: pytest.fail("YouTube must not be asked"))
    out = tmp_path / "niche.json"
    assert niche_reading.main(["--channel", "secret-place", "--out", str(out)]) == 0
    assert not out.exists() and "Nothing asked of YouTube" in capsys.readouterr().out


def test_a_refused_reading_is_one_warning_and_never_fails_the_job(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(niche_reading, "due", lambda channel, today: (True, "no reading yet"))
    for name in ("YOUTUBE_REFRESH_TOKEN", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET"):
        monkeypatch.setenv(name, "x")

    def refuse(*_args):
        raise RuntimeError("quotaExceeded <b>secret=abc</b>")
    monkeypatch.setattr(niche_reading, "read", refuse)
    import pipeline.upload as upload
    monkeypatch.setattr(upload, "_credentials", lambda: None)
    import googleapiclient.discovery as discovery
    monkeypatch.setattr(discovery, "build", lambda *a, **k: object())
    out = tmp_path / "niche.json"
    assert niche_reading.main(["--channel", "secret-place", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "::warning title=Niche reading not made (secret-place)::RuntimeError: quotaExceeded" in printed
    assert "<b>" not in printed and not out.exists()


@pytest.mark.parametrize("length,minutes", [("PT1H2M30S", 62.5), ("PT45S", 0.75), ("P1DT2H", 1560.0),
                                            ("PT3H", 180.0), ("", 0.0), ("P", 0.0), ("soon", 0.0)])
def test_a_length_is_read_in_minutes(length, minutes):
    assert niche_reading.minutes(length) == minutes


def test_each_channel_searches_for_its_own_kind_of_prayer():
    asked = {channel: tuple(niche_reading.queries_for(channel)) for channel in niche_reading.known_channels()}
    assert asked["secret-place"] == ("night prayer", "night prayer scripture")
    assert len(set(asked.values())) == len(asked), "ten channels, ten different searches"
    assert all(len(queries) == niche_reading.MAX_QUERIES == 2 for queries in asked.values())


def test_the_niche_reader_stays_inside_what_the_owner_allowed():
    source = (ROOT / "scripts/niche_reading.py").read_text(encoding="utf-8")
    code = source.split('"""', 2)[2].replace("sys.path.insert(", "")
    # The API only: no page of youtube.com is fetched, nothing is downloaded, nothing is written to YouTube.
    for banned in ("requests.", "urllib", "urlopen", "yt_dlp", "youtube-dl", "pytube", "captions(",
                   "thumbnails(", ".insert(", ".update(", ".delete(", "pageToken", '"statistics"', "part=\"snippet,statistics", "subscriberCount",
                   "viewCount\"]", "likeCount"):
        assert banned not in code, banned
    assert code.count(".search().list(") == 1 and code.count(".videos().list(") == 1
    assert niche_reading.EVERY_DAYS >= 7 and niche_reading.RESULTS <= 50


def test_the_reading_is_a_step_of_the_growth_job_and_adds_no_workflow():
    data = yaml.safe_load((ROOT / ".github/workflows/growth-autopilot.yml").read_text(encoding="utf-8"))
    steps = data["jobs"]["growth"]["steps"]
    names = [str(step.get("name", "")) for step in steps]
    niche = next(i for i, step in enumerate(steps) if "niche_reading.py" in str(step.get("run", "")))
    feedback = next(i for i, step in enumerate(steps) if "scripts/performance_feedback.py" in str(step.get("run", "")))
    assert niche < feedback, "the reading is made before the feedback that folds it in"
    assert steps[niche]["continue-on-error"] is True
    assert "--niche /tmp/niche.json" in steps[feedback]["run"]
    assert not any("niche" in str(step.get("with", {}).get("path", "")) for step in steps), \
        "the reading itself is not uploaded or committed"
    assert not (ROOT / ".github/workflows/niche.yml").exists() and names
    workflows = [p.name for p in (ROOT / ".github/workflows").glob("*.yml") if "niche" in p.name]
    assert workflows == []
