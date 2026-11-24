"""How long a release should be: measured from where viewers actually leave.

Held fixed: a length is never argued from theory; a planned length is never used;
one viewer who fell asleep cannot decide a length; the cut is the median watched
time rounded down and held above the floor; and with too little evidence the
current length stands untouched.
"""
from __future__ import annotations

import pytest

from pipeline import viewer_length as vl


def _row(vid, length, watched, views, percent=None):
    return {"video_id": vid, "views": views, "average_view_seconds": watched,
            "average_view_percent": percent,
            "_length": length}


def _measured(rows):
    lengths = {row["_length"] and row["video_id"]: row.pop("_length") for row in rows}
    return vl.measured_views(rows, lengths)


def test_a_video_with_two_views_is_not_evidence():
    """The 50-minute outlier in the real data had exactly one view."""
    rows = [_row("a" * 11, 10800, 3000, 1), _row("b" * 11, 10800, 600, 45)]
    measured = _measured(rows)
    assert [row["video_id"] for row in measured] == ["b" * 11]


def test_a_planned_length_is_never_measured_against():
    rows = [{"video_id": "a" * 11, "views": 40, "average_view_seconds": 600}]
    assert vl.measured_views(rows, {}) == []


def test_seconds_watched_are_derived_from_the_share_when_absent():
    rows = [{"video_id": "a" * 11, "views": 40, "average_view_percent": 5.0,
             "average_view_seconds": None}]
    measured = vl.measured_views(rows, {"a" * 11: 10800})
    assert measured[0]["watched_seconds"] == pytest.approx(540.0)
    assert measured[0]["derived"] is True


def test_the_reading_is_the_shape_of_attention():
    rows = [_row("a" * 11, 10800, 300, 40), _row("b" * 11, 10800, 600, 40),
            _row("c" * 11, 10800, 900, 40)]
    reading = vl.read(_measured(rows))
    assert reading.videos == 3
    assert reading.median_seconds == 600
    assert reading.shortest_seconds == 300


def test_the_ceiling_is_the_median_watched_time_rounded_down():
    reading = vl.Reading(videos=5, median_seconds=634.0, average_seconds=685.0,
                         shortest_seconds=271.0, longest_seconds=1337.0)
    verdict = vl.ceiling_seconds(reading, current_seconds=10800)
    assert verdict["seconds"] == 600          # 634s rounded down to whole minutes
    assert verdict["minutes"] == 10.0
    assert verdict["changed"] is True
    assert "not built longer than that" in verdict["basis"]


def test_the_ceiling_never_cuts_below_the_prayers_own_floor():
    reading = vl.Reading(videos=4, median_seconds=45.0, average_seconds=60.0,
                         shortest_seconds=20.0, longest_seconds=120.0)
    verdict = vl.ceiling_seconds(reading, current_seconds=10800)
    assert verdict["seconds"] == vl.FLOOR_SECONDS


def test_the_ceiling_never_lengthens_a_video():
    reading = vl.Reading(videos=4, median_seconds=5000.0, average_seconds=5000.0,
                         shortest_seconds=4000.0, longest_seconds=6000.0)
    verdict = vl.ceiling_seconds(reading, current_seconds=600)
    assert verdict["seconds"] == 600
    assert verdict["changed"] is False


def test_too_little_evidence_leaves_the_length_alone():
    reading = vl.Reading(videos=2, median_seconds=300.0, average_seconds=300.0,
                         shortest_seconds=200.0, longest_seconds=400.0)
    verdict = vl.ceiling_seconds(reading, current_seconds=10800)
    assert verdict["seconds"] == 10800
    assert verdict["changed"] is False
    assert "keeping" in verdict["basis"]


def test_no_reading_at_all_leaves_the_length_alone():
    verdict = vl.ceiling_seconds(None, current_seconds=10800)
    assert verdict["seconds"] == 10800
    assert verdict["changed"] is False


def test_the_tail_is_named_as_the_problem_only_on_the_evidence():
    short = vl.Reading(videos=5, median_seconds=634.0, average_seconds=685.0,
                       shortest_seconds=271.0, longest_seconds=1337.0)
    assert vl.tail_is_the_problem(short, 10800) is True     # three-hour uploads
    assert vl.tail_is_the_problem(short, 360) is False      # a six-minute prayer
    assert vl.wasted_share(short, 10800) == pytest.approx(0.9413, abs=1e-3)


def test_the_real_channel_reports_the_number_this_was_built_on():
    """The repository's own analytics and receipts must keep producing a dozen-odd minutes.

    Deliberately a band, not a number: the reading moves every time Analytics is
    re-read (it went 10.6 -> 13.5 minutes as two more videos were measured), and a
    test that pins the exact value would fail on every honest update. What must
    hold is the conclusion: minutes, not hours.
    """
    from pipeline import growth_score

    channels, _missing = growth_score.load_channels()
    ceiling = growth_score.watch_ceiling(channels)
    assert ceiling["reading"] is not None
    assert 5.0 <= ceiling["reading"]["median_seconds"] / 60 <= 30.0
    assert ceiling["seconds"] <= 1800, "a three-hour tail must not survive this reading"
    assert ceiling["tail_is_the_problem"] is True
