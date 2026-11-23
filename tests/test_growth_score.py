"""Where the counted watch hours come from: the reading that steers the releases.

Held fixed: only channels with an Analytics grant are read and the others are
named; the shared window is the days every channel reports, so a share is never
computed across different days; the Shorts feed is counted and never steered
toward; a channel with too little history is never judged; a looped Short is
never read as a long-form's retention; a planned length is never used as a real
one; the budget stays inside what the pipeline can actually build; and nothing
here writes a revenue figure.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline import growth_score as score
from pipeline import night_tail


def _analytics(channel, days, sources=None, videos=None, by_kind=None, counted=None):
    """One channel file as scripts/analytics_reader.py writes it."""
    return {
        "channel": channel,
        "generated_at": "2026-11-21T11:40:04Z",
        "last_28_days": {
            "by_day": [{"day": day, "views": views, "watch_hours": hours}
                       for day, views, hours in days],
            "views_by_kind": by_kind or {"videoondemand": 100, "shorts": 900},
            "traffic_sources": [{"source": code, "views": views, "watch_hours": hours}
                                for code, views, hours in (sources or [])],
        },
        "videos_365d": videos or [],
        "partner_program": {"watch_hours_365d": {"long_form_and_live": counted or 41.0}},
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / f"{payload['channel']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_only_granted_channels_are_read_and_the_rest_are_named(tmp_path):
    _write(tmp_path, _analytics("secret-place", [("2026-11-01", 10, 1.0)]))
    (tmp_path / "prayer3.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "secret-place.reach.json").write_text("{}", encoding="utf-8")
    channels, missing = score.load_channels(tmp_path)
    assert list(channels) == ["secret-place"]
    assert missing == ["prayer3"]
    assert "reach" not in json.dumps(channels)  # impressions are another question


def test_the_window_is_the_days_every_channel_reports(tmp_path):
    early = _analytics("secret-place", [("2026-11-01", 5, 1.0), ("2026-11-02", 5, 1.0),
                                        ("2026-11-03", 5, 3.0)])
    late = _analytics("prayer2", [("2026-11-02", 5, 2.0), ("2026-11-03", 5, 2.0),
                                  ("2026-11-04", 5, 99.0)])
    channels, _ = score.load_channels(tmp_path)
    channels = {"secret-place": score.read_channel(_write(tmp_path, early)),
                "prayer2": score.read_channel(_write(tmp_path, late))}
    assert score.shared_days(channels) == ["2026-11-02", "2026-11-03"]


def test_a_stale_channel_does_not_shrink_its_share_by_missing_days():
    """The share is computed on the shared days only, so file age cannot decide it."""
    fresh = {
        "channel": "secret-place",
        "days": {"2026-11-02": {"views": 5, "hours": 2.0}, "2026-11-03": {"views": 5, "hours": 2.0}},
        "sources": {}, "videos": [], "watch_hours_365d": 10.0,
    }
    stale = {"channel": "prayer2",
             "days": {"2026-10-01": {"views": 5, "hours": 500.0},
                      "2026-11-02": {"views": 5, "hours": 2.0},
                      "2026-11-03": {"views": 5, "hours": 2.0}},
             "sources": {}, "videos": [], "watch_hours_365d": 10.0}
    channels = {"secret-place": fresh, "prayer2": stale}
    rows = score.channel_readings(channels, score.shared_days(channels))
    shares = {row["channel"]: row["share_of_network_hours"]
              for row in score.allocate(rows, 180)}
    assert shares == {"secret-place": 0.5, "prayer2": 0.5}  # not 4/508


def test_source_codes_are_named_and_an_unknown_door_is_kept():
    report = score.read_channel(_write(Path("/tmp"), _analytics(
        "secret-place", [("2026-11-01", 1, 1.0)],
        sources=[("RELATED_VIDEO", 10, 5.0), ("SHORTS", 900, 20.0), ("BRAND_NEW", 2, 0.5)])))
    assert set(report["sources"]) == {"suggested", "shorts_feed", "brand_new"}
    assert report["sources"]["suggested"]["hours"] == 5.0


def test_counted_hours_leave_the_shorts_feed_out():
    by_source = {"suggested": {"hours": 10.0}, "shorts_feed": {"hours": 90.0},
                 "yt_search": {"hours": 2.0}, "playlist": {"hours": 1.0},
                 "end_screen": {"hours": 1.0}}
    assert score.counted_hours(by_source) == 14.0
    assert "shorts_feed" not in score.SHARE_MEDIA


def test_a_looped_short_is_never_read_as_a_long_forms_retention(monkeypatch):
    """Shorts report past 100% watched when they loop; that is not a prayer's retention."""
    monkeypatch.setattr(score, "short_video_ids", lambda: frozenset({"shortsid001"}))
    channel = {"channel": "secret-place",
               "days": {"2026-11-02": {"views": 10, "hours": 1.0}},
               "sources": {},
               "videos": [{"video_id": "shortsid001", "hours": 2.0, "views": 100,
                           "average_view_percent": 240.0},
                          {"video_id": "prayer00001", "hours": 1.0, "views": 10,
                           "average_view_percent": 9.0}],
               "watch_hours_365d": 41.0, "long_form_view_share": 0.1}
    row = score.channel_readings({"secret-place": channel}, ["2026-11-02"])[0]
    assert row["held_percent"] == 9.0
    assert row["videos_read"] == 1


def test_a_channel_with_no_history_is_never_judged():
    thin = {"channel": "prayer9",
            "days": {"2026-11-01": {"views": 1, "hours": 0.01}, "2026-11-02": {"views": 1, "hours": 0.01}},
            "sources": {}, "videos": [], "watch_hours_365d": 0.0}
    reading = score.night_tail_reading({"prayer9": thin})
    assert reading["channels"][0]["verdict"] == "not_enough_reading"
    assert reading["verdict"] == "unknown"  # nothing eligible, so nothing is claimed
    assert reading["keep"] is True          # unmeasured keeps the tail


def test_a_flat_channel_reads_as_flat_and_the_tail_loses_its_keep():
    days = {f"2026-11-{day:02d}": {"views": 10, "hours": 1.0} for day in range(1, 21)}
    flat = {"channel": "prayer2", "days": days, "sources": {}, "videos": [],
            "watch_hours_365d": 100.0}
    reading = score.night_tail_reading({"prayer2": flat})
    assert reading["channels"][0]["verdict"] == "flat"
    assert reading["keep"] is False


def test_a_daily_step_up_reads_as_a_hold():
    days = {}
    for day in range(1, 22):
        hours = 1.0 if day <= 10 else 4.0
        days[f"2026-11-{day:02d}"] = {"views": 10, "hours": hours}
    stepped = {"channel": "secret-place", "days": days, "sources": {}, "videos": [],
               "watch_hours_365d": 100.0}
    reading = score.night_tail_reading({"secret-place": stepped})
    assert reading["channels"][0]["verdict"] == "hold"
    assert reading["keep"] is True


def test_a_planned_length_is_never_priced_as_a_real_one(monkeypatch):
    """192 of 201 long-form receipts carry only target_minutes: what was planned."""
    monkeypatch.setattr(score, "video_lengths", lambda: {})
    channels = {"secret-place": {
        "channel": "secret-place",
        "days": {"2026-11-02": {"views": 10, "hours": 1.0}},
        "sources": {}, "videos": [{"video_id": "prayer00001", "hours": 1.0, "views": 10,
                                   "average_view_percent": 9.0}],
        "watch_hours_365d": 41.0, "long_form_view_share": 0.1}}
    payoff = score.length_payoff(channels)
    assert payoff["bands"] == []
    assert payoff["best_band"] is None
    assert payoff["videos_without_a_length"] == 1


def test_the_budget_is_a_length_a_view_has_actually_rewarded(monkeypatch):
    """Two priced bands, two videos each: the better-paying length wins."""
    monkeypatch.setattr(score, "video_lengths", lambda: {
        "shorta00011": 600, "shortb00011": 600,          # 10 minutes
        "longa000111": 10800, "longb000111": 10800,      # 3 hours
    })
    videos = [{"video_id": "shorta00011", "hours": 0.4, "views": 10, "average_view_percent": 60.0},
              {"video_id": "shortb00011", "hours": 0.4, "views": 10, "average_view_percent": 60.0},
              {"video_id": "longa000111", "hours": 2.0, "views": 10, "average_view_percent": 8.0},
              {"video_id": "longb000111", "hours": 2.0, "views": 10, "average_view_percent": 8.0}]
    channels = {"secret-place": {"channel": "secret-place",
                                 "days": {"2026-11-02": {"views": 10, "hours": 1.0}},
                                 "sources": {}, "videos": videos,
                                 "watch_hours_365d": 41.0, "long_form_view_share": 0.1}}
    payoff = score.length_payoff(channels)
    assert [band["measured"] for band in payoff["bands"]] == [True, True]
    budget = score.budget_from_payoff(payoff, need_a_day=57.0)
    # 2.0 hours / 10 views = 0.20 hours a view for the long band, against 0.04
    # for the ten-minute one: the length that pays best a view is chosen.
    assert budget["minutes"] == score.MAX_BUDGET_MINUTES
    assert "over 3 hours" in budget["basis"]
    assert "0.2 hours" in budget["basis"]


def test_one_video_a_band_is_not_enough_to_move_the_budget(monkeypatch):
    monkeypatch.setattr(score, "video_lengths", lambda: {"longone0111": 10800})
    channels = {"secret-place": {"channel": "secret-place",
                                 "days": {"2026-11-02": {"views": 10, "hours": 1.0}},
                                 "sources": {},
                                 "videos": [{"video_id": "longone0111", "hours": 1.5, "views": 10,
                                             "average_view_percent": 8.0}],
                                 "watch_hours_365d": 41.0, "long_form_view_share": 0.1}}
    payoff = score.length_payoff(channels)
    assert all(not band["measured"] for band in payoff["bands"])
    budget = score.budget_from_payoff(payoff, need_a_day=57.0)
    assert budget["minutes"] == score.DEFAULT_BUDGET_MINUTES
    assert "no length has two measured videos" in budget["basis"]


def test_the_budget_never_leaves_what_the_pipeline_can_build():
    payoff = {"bands": [{"band": "over 3 hours", "videos": 6, "views": 100, "hours": 10.0,
                         "minutes": 600, "hours_a_view": 0.1, "measured": True}],
              "videos_without_a_length": 0}
    budget = score.budget_from_payoff(payoff, need_a_day=57.0)
    assert budget["minutes"] == score.MAX_BUDGET_MINUTES
    assert score.MIN_BUDGET_MINUTES <= budget["minutes"] <= score.MAX_BUDGET_MINUTES


def test_no_readings_at_all_still_produces_a_usable_report():
    report = score.build_report({}, today=__import__("datetime").date(2026, 11, 21),
                                sources_reading={})
    assert report["window"]["days"] == 0
    assert report["targets"] == []
    assert report["budget"]["minutes"] == score.DEFAULT_BUDGET_MINUTES
    assert report["network"]["counted_hours"] == 0.0
    assert report["hints"]["night_tail"]["keep"] is True
    # The report states its own default, and a channel reading it gets that:
    # a report that was written is authoritative, an absent one is not.
    assert score.budget_minutes_from_report(report) == report["budget"]["minutes"]
    assert score.budget_minutes_from_report({}) == score.DEFAULT_BUDGET_MINUTES


def test_the_report_carries_no_figure_of_money_and_no_viewer():
    """The word may appear only in the sentence that says it is not carried."""
    report = score.build_report({}, sources_reading={})
    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
    walk(report)
    text = json.dumps({k: v for k, v in report.items() if k != "privacy"}).lower()
    for forbidden in ("revenue", "earnings", "cpm", "rpm", "viewer_id", "email", "payee"):
        assert forbidden not in text
    assert "no revenue" in json.dumps(report["privacy"]).lower()


def test_the_threshold_doubles_from_february_2027():
    after = score.need_reading({}, today=__import__("datetime").date(2027, 2, 1))
    before = score.need_reading({}, today=__import__("datetime").date(2026, 11, 21))
    assert before["threshold_hours"] == 4000
    assert after["threshold_hours"] == 8000
    assert before["days_until_the_threshold_doubles"] == (date(2027, 1, 31) - date(2026, 11, 21)).days


def test_the_night_tail_reads_its_length_from_the_report(monkeypatch, tmp_path):
    report = {"budget": {"minutes": 180, "basis": "measured"}, "hints": {"night_tail": {"keep": True}}}
    monkeypatch.setattr(score, "REPORT_PATH", tmp_path / "growth_score.json")
    (tmp_path / "growth_score.json").write_text(json.dumps(report), encoding="utf-8")
    assert night_tail.configured_minutes("secret-place", {}) == 180


def test_the_night_tail_can_be_turned_off_by_a_flat_verdict(monkeypatch, tmp_path):
    report = {"budget": {"minutes": 180}, "hints": {"night_tail": {"keep": False, "verdict": "flat"}}}
    monkeypatch.setattr(score, "REPORT_PATH", tmp_path / "growth_score.json")
    (tmp_path / "growth_score.json").write_text(json.dumps(report), encoding="utf-8")
    assert night_tail.configured_minutes("secret-place", {}) == 0


def test_the_explicit_switch_still_wins_over_the_report(monkeypatch, tmp_path):
    report = {"budget": {"minutes": 180}, "hints": {"night_tail": {"keep": True}}}
    monkeypatch.setattr(score, "REPORT_PATH", tmp_path / "growth_score.json")
    (tmp_path / "growth_score.json").write_text(json.dumps(report), encoding="utf-8")
    assert night_tail.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "0"}) == 0
    assert night_tail.configured_minutes("secret-place", {"NIGHT_TAIL_MINUTES": "45"}) == 45


def test_a_daytime_channel_never_gets_a_tail_from_the_report(monkeypatch, tmp_path):
    report = {"budget": {"minutes": 180}, "hints": {"night_tail": {"keep": True}}}
    monkeypatch.setattr(score, "REPORT_PATH", tmp_path / "growth_score.json")
    (tmp_path / "growth_score.json").write_text(json.dumps(report), encoding="utf-8")
    assert night_tail.configured_minutes("prayer3", {}) == 0


def test_the_upload_stamps_the_real_length_not_the_planned_one():
    """A receipt has to say what the file is; target_minutes says what was planned."""
    import inspect

    from pipeline import run

    parameters = inspect.signature(run._mark_job_uploaded).parameters
    assert "duration_seconds" in parameters
    source = inspect.getsource(run._mark_job_uploaded)
    assert 'stamped.append(("duration_seconds", measured_length))' in source
    assert 'doc.meta["duration_seconds"] = measured_length' in source


def test_the_prayer_pipeline_passes_the_length_of_the_file_it_uploaded():
    import inspect

    from pipeline import prayer_pipeline

    source = inspect.getsource(prayer_pipeline.produce)
    assert "duration_seconds=(night['total_seconds'] if night else duration)" in source


def test_the_measured_week_beats_the_bump_count():
    """scripts/growth_ab.py compares the same channels before and after; it wins."""
    channels = {"secret-place": {
        "channel": "secret-place",
        "days": {f"2026-11-{day:02d}": {"views": 10, "hours": 1.0} for day in range(1, 21)},
        "sources": {}, "videos": [], "watch_hours_365d": 41.0, "long_form_view_share": 0.1}}
    report = score.build_report(channels, sources_reading={
        "readings": {"night_tail": {"verdict": "flat", "note": "a measured week"}}})
    assert report["hints"]["night_tail"]["verdict"] == "flat"
    assert report["hints"]["night_tail"]["keep"] is False
    assert score.keep_night_tail(report) is False


def test_headline_says_where_the_hours_come_from():
    channels = {"secret-place": {
        "channel": "secret-place",
        "days": {"2026-11-02": {"views": 10, "hours": 1.0}},
        "sources": {"suggested": {"views": 5, "hours": 9.0},
                    "shorts_feed": {"views": 900, "hours": 30.0}},
        "videos": [], "watch_hours_365d": 41.0, "long_form_view_share": 0.1}}
    lines = score.headline(score.build_report(channels, sources_reading={}))
    assert any("counted 9.0 hours" in line for line in lines)
    assert any("Release budget:" in line for line in lines)
    assert any("Night tail:" in line for line in lines)


@pytest.mark.parametrize("value,expected", [
    ("12.5", 12.5), (None, 0.0), ("nonsense", 0.0), (-5, 0.0), (float("nan"), 0.0), (True, 0.0),
])
def test_hours_never_crashes_on_a_bad_row(value, expected):
    assert score._hours(value) == expected


def test_the_analytics_page_gets_the_four_figures_a_person_acts_on(monkeypatch, tmp_path):
    """The engine's record goes where a person already reads, not to a new dashboard."""
    from scripts import analytics_reader as reader

    report = {
        "network": {
            "hours_by_source": {"suggested": 22.05, "shorts_feed": 24.68, "yt_search": 0.95},
            "counted_hours": 23.0,
            "counted_share": 0.435,
            "need": {"hours_a_day_needed": 57.38, "hours_a_day_now": 2.03,
                     "days_until_the_threshold_doubles": 69},
            "held_percent_median": 8.9,
        },
        "budget": {"minutes": 180, "basis": "measured"},
        "hints": {"night_tail": {"verdict": "hold", "keep": True}},
    }
    monkeypatch.setattr(reader, "ROOT", tmp_path)
    (tmp_path / "content" / "research").mkdir(parents=True, exist_ok=True)
    (tmp_path / "content" / "research" / "growth_score.json").write_text(
        json.dumps(report), encoding="utf-8")
    text = "\n".join(reader.growth_lines())
    assert "Where the counted watch hours come from" in text
    assert "Shorts feed — does not count" in text
    assert "Counted: 23 hours" in text
    assert "Release length: 180 minutes" in text
    assert "8.9%" in text


def test_the_analytics_page_says_nothing_when_there_is_no_reading(monkeypatch, tmp_path):
    from scripts import analytics_reader as reader

    monkeypatch.setattr(reader, "ROOT", tmp_path)
    assert reader.growth_lines() == []
