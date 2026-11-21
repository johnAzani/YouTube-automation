"""The Shorts are measured and steer which passages are written next.

The long-form loop never produced a signal (no channel has three long-forms
with 25 views) while the Shorts drew 97% of the views and were set aside.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pipeline import evergreen_shorts as ev
from pipeline import performance_feedback as pf

TODAY = date(2026, 11, 14)


def _rows(shorts: list[tuple[str, int, str]]):
    """[(title, views, published)] -> (snapshots, published index)."""
    snapshots, index = [], {}
    for number, (title, views, published) in enumerate(shorts):
        vid = f"vid{number:03d}"
        snapshots.append({"video_id": vid, "title": title, "snapshot_date": TODAY.isoformat(),
                          "published_at": published, "views": views, "likes": 0, "comments": 0})
        index[vid] = {"title": title, "format": "short", "channel": "prayer2",
                      "scripture": pf.extract_scripture(title), "theme": pf.classify_theme(title),
                      "published_on": published}
    return snapshots, index


WATCHED = [
    ("Psalm 27:1 | The Morning Altar", 390, "2026-11-08"),
    ("Psalm 91:1 | The Morning Altar", 300, "2026-11-08"),
    ("Psalm 23:1 | The Morning Altar", 250, "2026-11-09"),
    ("Psalm 121:1 | The Morning Altar", 210, "2026-11-09"),
    ("Proverbs 3:5 | The Morning Altar", 20, "2026-11-09"),
    ("Proverbs 16:3 | The Morning Altar", 12, "2026-11-10"),
    ("Proverbs 4:23 | The Morning Altar", 8, "2026-11-10"),
    ("Isaiah 60:1 | The Morning Altar", 95, "2026-11-10"),
    ("Lamentations 3:22 | The Morning Altar", 9000, "2026-11-13"),   # published yesterday
]


def _report(shorts=WATCHED):
    snapshots, index = _rows(shorts)
    return pf.build_feedback_report(snapshots, index, today=TODAY)


def test_shorts_are_measured_by_book_and_only_once_they_are_two_days_old():
    shorts = _report()["shorts"]
    assert shorts["measured_shorts"] == 8 and shorts["total_shorts"] == 9
    assert "lamentations" not in shorts["by_book"], "yesterday's Short has not had its two days"
    assert shorts["sufficient_data"] is True
    assert shorts["by_book"]["psalm"]["shorts"] == 4
    assert shorts["by_book"]["psalm"]["ratio"] > 1.2 > 0.7 > shorts["by_book"]["proverbs"]["ratio"]


def test_the_report_carries_aggregates_and_no_video_ids():
    text = json.dumps(_report()["shorts"])
    assert "vid0" not in text and "The Morning Altar" not in text


def test_one_lucky_short_does_not_crown_its_book():
    lucky = WATCHED[:8] + [("Nahum 1:7 | The Morning Altar", 900, "2026-11-09")]
    shorts = _report(lucky)["shorts"]
    raw = 900 / shorts["avg_views"]
    assert 1.0 < shorts["by_book"]["nahum"]["ratio"] < raw * 0.6, "pulled toward the average"


def test_passages_from_the_books_that_are_watched_are_written_first():
    listed = ["Proverbs 3:6", "Isaiah 43:18-19", "Psalm 46:5", "Jeremiah 29:11", "Psalm 90:14"]
    ranked = pf.rank_short_passages(listed, _report())
    assert ranked == ["Psalm 46:5", "Psalm 90:14", "Isaiah 43:18-19", "Jeremiah 29:11", "Proverbs 3:6"]
    # promoted keep their listed order among equals; unmeasured books keep their place


def test_too_few_shorts_leaves_the_list_as_written():
    listed = ["Proverbs 3:6", "Psalm 46:5"]
    report = _report(WATCHED[:3])
    assert report["shorts"]["sufficient_data"] is False
    assert pf.rank_short_passages(listed, report) == listed
    assert pf.rank_short_passages(listed, None) == listed
    assert pf.rank_short_passages(listed, {"sufficient_data": False}) == listed


def test_a_new_channel_borrows_the_networks_numbers(tmp_path):
    for name, shorts in (("performance_feedback_prayer2.json", WATCHED),
                         ("performance_feedback_prayer3.json", WATCHED[:6])):
        (tmp_path / name).write_text(json.dumps(_report(shorts)), encoding="utf-8")
    (tmp_path / "performance_feedback_prayer9.json").write_text("{not json", encoding="utf-8")
    network = pf.network_shorts_signal(tmp_path)
    assert network["measured_shorts"] == 14 and network["scope"] == "network"
    assert network["by_book"]["psalm"]["shorts"] == 8
    listed = ["Proverbs 3:6", "Psalm 46:5"]
    new_channel = _report(WATCHED[:2])
    assert pf.rank_short_passages(listed, new_channel, network) == ["Psalm 46:5", "Proverbs 3:6"]


def test_no_network_signal_from_a_handful_of_shorts(tmp_path):
    (tmp_path / "performance_feedback.json").write_text(json.dumps(_report(WATCHED[:4])),
                                                         encoding="utf-8")
    assert pf.network_shorts_signal(tmp_path) is None


def test_the_candidate_list_is_ordered_by_what_is_watched(monkeypatch):
    monkeypatch.setitem(ev.EVERGREEN, "prayer2", ("Proverbs 3:6", "Isaiah 43:18-19", "Psalm 46:5"))
    monkeypatch.setattr(ev, "_roadmap_ahead", lambda channel, taken: ["Proverbs 16:9", "Psalm 5:3"])
    monkeypatch.setattr(pf, "load_feedback_report", lambda path=None, channel_id=None: _report())
    monkeypatch.setattr(pf, "network_shorts_signal", lambda research_dir=None: None)
    got = ev.candidates("prayer2", used=set())
    assert got == [("Psalm 46:5", "evergreen"), ("Isaiah 43:18-19", "evergreen"),
                   ("Proverbs 3:6", "evergreen"), ("Psalm 5:3", "roadmap"),
                   ("Proverbs 16:9", "roadmap")], "evergreen still comes before the roadmap"


def test_a_broken_feedback_file_never_stops_authoring(monkeypatch):
    monkeypatch.setitem(ev.EVERGREEN, "prayer2", ("Proverbs 3:6", "Psalm 46:5"))
    monkeypatch.setattr(ev, "_roadmap_ahead", lambda channel, taken: [])

    def boom(*_a, **_k):
        raise RuntimeError("unreadable")

    monkeypatch.setattr(pf, "load_feedback_report", boom)
    assert [ref for ref, _ in ev.candidates("prayer2", used=set())] == ["Proverbs 3:6", "Psalm 46:5"]


def test_committed_feedback_files_without_a_shorts_section_are_tolerated():
    """Files written before this change have no `shorts` key until the next daily run."""
    listed = list(ev.EVERGREEN["prayer2"])
    stale = {"sufficient_data": False, "themes": []}
    assert pf.rank_short_passages(listed, stale, None) == listed


LOOPED = [
    ("Psalm 27:1 | The Morning Altar", 200, "2026-11-08"),
    ("Psalm 91:1 | The Morning Altar", 200, "2026-11-08"),
    ("Psalm 23:1 | The Morning Altar", 200, "2026-11-09"),
    ("John 14:27 | The Morning Altar", 180, "2026-11-08"),
    ("John 14:1 | The Morning Altar", 180, "2026-11-08"),
    ("Proverbs 3:5 | The Morning Altar", 30, "2026-11-09"),
    ("Proverbs 16:3 | The Morning Altar", 30, "2026-11-10"),
    ("Isaiah 60:1 | The Morning Altar", 40, "2026-11-10"),
]


def test_a_looping_book_is_not_outranked_by_one_that_is_only_clicked(monkeypatch):
    """Psalm 27 had the most views at 76% watched; Psalm 16 looped at 191%.

    Views alone would keep writing the clicked book. Analytics average % viewed
    is what YouTube Help names after 'chose to view'. A 3-view 200% clip is
    ignored (MIN_VIEWS_FOR_ENGAGEMENT).
    """
    snapshots, index = _rows(LOOPED)
    apv = {f"vid{i:03d}": (160.0 if i in (3, 4) else 55.0) for i in range(8)}
    monkeypatch.setattr(pf, "load_retention_index", lambda *a, **k: apv)
    report = pf.build_feedback_report(snapshots, index, today=TODAY, channel_id="prayer2")
    shorts = report["shorts"]
    assert shorts["looped_shorts"] == 2
    assert shorts["by_book"]["john"]["loop_ratio"] > 1.2
    assert shorts["by_book"]["psalm"]["loop_ratio"] < 1.0
    ranked = pf.rank_short_passages(["Psalm 46:5", "John 14:27"], report)
    assert ranked[0] == "John 14:27"
    text = json.dumps(shorts)
    assert "vid0" not in text and "vid3" not in text


def test_a_handful_of_views_at_200_percent_does_not_crown_a_book(monkeypatch):
    snapshots, index = _rows(LOOPED + [("Nahum 1:7 | The Morning Altar", 3, "2026-11-09")])
    apv = {f"vid{i:03d}": 55.0 for i in range(8)}
    apv["vid008"] = 250.0
    monkeypatch.setattr(pf, "load_retention_index", lambda *a, **k: apv)
    shorts = pf.build_feedback_report(snapshots, index, today=TODAY, channel_id="prayer2")["shorts"]
    assert "loop_ratio" not in shorts["by_book"].get("nahum", {})


def test_without_analytics_the_ranking_is_still_views():
    ranked = pf.rank_short_passages(
        ["Proverbs 3:6", "Isaiah 43:18-19", "Psalm 46:5", "Jeremiah 29:11", "Psalm 90:14"],
        _report())
    assert ranked == ["Psalm 46:5", "Psalm 90:14", "Isaiah 43:18-19", "Jeremiah 29:11", "Proverbs 3:6"]


def test_retention_index_reads_the_channel_file_and_swallows_a_broken_one(tmp_path):
    (tmp_path / "secret-place.json").write_text(json.dumps({
        "videos_365d": [
            {"video_id": "kLgHN57fb1w", "average_view_percent": 145.1, "views": 258},
            {"video_id": "bad", "average_view_percent": "x"},
            {"views": 1},
        ]
    }), encoding="utf-8")
    got = pf.load_retention_index("secret-place", analytics_dir=tmp_path)
    assert got == {"kLgHN57fb1w": 145.1}
    (tmp_path / "prayer2.json").write_text("{not json", encoding="utf-8")
    assert pf.load_retention_index("prayer2", analytics_dir=tmp_path) == {}
    assert pf.load_retention_index(None) == {}
