"""What this channel can actually reach — and what it cannot be promised.

Held fixed: every coefficient is measured or is a documented level; a click rate
on too few impressions is not used as evidence; the model never claims a view count
or virality; and when the honest answer is "this needs far more reach", it says so.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pipeline import realistic_ceiling as rc


def _reach(impressions=350.0, clicks=4.6, days=34):
    return {"impressions": int(impressions * days), "clicks": int(clicks * days), "days": days,
            "impressions_a_day": impressions, "clicks_a_day": clicks,
            "click_rate_percent": round(100.0 * clicks / impressions, 2),
            "sufficient": impressions * days >= rc.MIN_IMPRESSIONS}


def _watch(seconds=634.0, views_a_day=200.0):
    return {"watch_seconds": seconds, "videos_measured": 5, "views_a_day": views_a_day,
            "sufficient": True}


def test_hours_a_day_is_impressions_times_click_rate_times_watch_time():
    hours = rc.hours_a_day_from(3600.0, 5.0, 600.0)
    # 3600 impressions -> 180 clicks -> 180 * 600s = 30 hours
    assert hours == 30.0


def test_no_reading_produces_no_number_rather_than_a_guess():
    assert rc.hours_a_day_from(None, 5.0, 600.0) is None
    assert rc.hours_a_day_from(350.0, None, 600.0) is None
    assert rc.hours_a_day_from(350.0, 5.0, None) is None


def test_the_model_prices_each_lever_from_measured_values():
    report = rc.build_model(_reach(), _watch(), today=date(2026, 11, 21))
    levers = {lever["lever"]: lever["hours_a_day"] for lever in report["levers"]}
    assert levers["as it stands"] == rc.hours_a_day_from(350.0, 1.31, 634.0)
    assert levers[f"click rate to {rc.GOOD_CTR_PERCENT:.0f}%"] == rc.hours_a_day_from(350.0, 4.0, 634.0)


def test_the_watch_time_lever_cannot_invent_attention():
    """A view already watched 634 seconds is not improved by asking for 3 minutes."""
    report = rc.build_model(_reach(), _watch(seconds=634.0), today=date(2026, 11, 21))
    best = report["levers"][-1]["hours_a_day"]
    middle = report["levers"][1]["hours_a_day"]
    assert best == middle  # the measured median is already past the good level


def test_a_short_watch_time_is_worth_improving():
    report = rc.build_model(_reach(), _watch(seconds=45.0), today=date(2026, 11, 21))
    middle = report["levers"][1]["hours_a_day"]
    best = report["levers"][-1]["hours_a_day"]
    assert best > middle


def test_the_verdict_says_how_much_more_reach_the_threshold_needs():
    report = rc.build_model(_reach(), _watch(), today=date(2026, 11, 21))
    verdict = report["verdict"]
    assert verdict["reachable_on_impressions_alone"] is False
    assert verdict["impressions_a_day_needed"] > 350
    assert verdict["impressions_multiple_needed"] > 1
    assert "impressions" in verdict["sentence"]


def test_the_threshold_doubles_from_february_2027():
    assert rc.threshold_for(date(2026, 11, 21)) == 4000
    assert rc.threshold_for(date(2027, 2, 1)) == 8000


def test_the_model_refuses_to_claim_a_view_count_or_virality():
    report = rc.build_model(_reach(), _watch(), today=date(2026, 11, 21))
    claimed = " ".join(report["not_claimed"]).lower()
    assert "view count" in claimed
    assert "virality" in claimed


def test_nothing_measured_still_produces_an_honest_report():
    report = rc.build_model({"sufficient": False}, {"sufficient": False}, today=date(2026, 11, 21))
    assert report["levers"][0]["hours_a_day"] is None
    assert "Too few impressions" in report["verdict"]["sentence"]


def test_the_report_carries_no_figure_of_money():
    report = rc.build_model(_reach(), _watch(), today=date(2026, 11, 21))
    text = json.dumps(report).lower()
    for forbidden in ("revenue", "earnings", "cpm", "rpm"):
        assert forbidden not in text


def test_the_real_repository_reports_its_own_distance():
    """The committed analytics must keep producing the honest comparison."""
    report = rc.build_model(today=date(2026, 11, 21))
    measured = report["measured"]
    assert measured["impressions_a_day"] > 0
    assert measured["watch_seconds_a_view"] is not None
    assert report["verdict"]["times_the_pace_must_rise"] > 1


def test_the_daily_job_writes_the_model():
    import yaml

    path = Path(__file__).resolve().parents[1] / ".github/workflows/growth-score.yml"
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    steps = " ".join(str(step.get("run", "")) for step in data["jobs"]["score"]["steps"])
    assert "pipeline.realistic_ceiling" in steps
    assert "realistic_ceiling.json" in steps
