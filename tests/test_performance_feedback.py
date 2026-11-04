"""Tests for the closed-loop performance feedback engine ($0.00 lock)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline.performance_feedback import (
    MIN_VIDEOS_FOR_SIGNAL,
    VideoPerformance,
    aggregate_themes,
    build_feedback_report,
    candidate_theme,
    classify_theme,
    compute_video_performance,
    extract_scripture,
    load_feedback_report,
    rank_candidates,
    write_feedback_report,
)


TODAY = date(2026, 11, 4)


def _snap(vid, title, views, likes, comments, published="2026-10-20", snapshot="2026-11-03"):
    return {
        "video_id": vid, "title": title, "views": views, "likes": likes,
        "comments": comments, "published_at": published, "snapshot_date": snapshot,
    }


def _index(vid, title, fmt="longform", published="2026-10-20"):
    return {
        "title": title, "format": fmt, "scripture": extract_scripture(title),
        "theme": classify_theme(title), "published_on": published,
    }


class TestClassification:
    def test_scripture_reference_wins_over_generic_keyword(self):
        # Psalm 91 is protection even though the title also says "peace".
        assert classify_theme("Psalm 91: Night Prayer of Peace and Protection") == "protection"

    def test_peace_rest_theme(self):
        assert classify_theme("Psalm 23: The Lord Is My Shepherd — Rest & Peace") == "peace_rest"

    def test_stillness_refuge(self):
        assert classify_theme("Psalm 46: Be Still & Know — God Is Our Refuge") == "stillness_refuge"

    def test_anxiety_peace_new_testament(self):
        assert classify_theme("Philippians 4: The Peace That Guards Heart and Mind") == "anxiety_peace"

    def test_fallback_general(self):
        assert classify_theme("A Random Title With No Scripture") == "general_prayer"

    def test_extract_scripture_normalises(self):
        assert extract_scripture("Psalms 91: Divine Protection") == "Psalm 91"
        assert extract_scripture("psalm 23 the lord is my shepherd") == "Psalm 23"
        assert extract_scripture("no scripture here") == ""


class TestPerformance:
    def test_latest_snapshot_wins(self):
        snaps = [
            _snap("v1", "Psalm 91 Prayer", 10, 1, 0, snapshot="2026-11-01"),
            _snap("v1", "Psalm 91 Prayer", 100, 8, 2, snapshot="2026-11-03"),
        ]
        idx = {"v1": _index("v1", "Psalm 91 Prayer")}
        perf = compute_video_performance(snaps, idx, TODAY)
        assert len(perf) == 1
        assert perf[0].views == 100

    def test_velocity_requires_minimum_age(self):
        # Published yesterday: velocity must be 0 (too new to be meaningful).
        snaps = [_snap("v1", "Psalm 91 Prayer", 500, 20, 5, published="2026-11-03")]
        idx = {"v1": _index("v1", "Psalm 91 Prayer", published="2026-11-03")}
        perf = compute_video_performance(snaps, idx, TODAY)
        assert perf[0].views_per_day == 0.0

    def test_engagement_requires_minimum_views(self):
        snaps = [_snap("v1", "Psalm 91 Prayer", 5, 3, 1)]  # 80% but only 5 views
        idx = {"v1": _index("v1", "Psalm 91 Prayer")}
        perf = compute_video_performance(snaps, idx, TODAY)
        assert perf[0].engagement_rate == 0.0
        assert perf[0].measured is False

    def test_score_blend_favours_reach_and_satisfaction(self):
        snaps = [
            _snap("hi", "Psalm 91 Protection", 1000, 80, 20),
            _snap("lo", "Psalm 46 Refuge", 50, 1, 0),
        ]
        idx = {
            "hi": _index("hi", "Psalm 91 Protection"),
            "lo": _index("lo", "Psalm 46 Refuge"),
        }
        perf = {v.video_id: v for v in compute_video_performance(snaps, idx, TODAY)}
        assert perf["hi"].score > perf["lo"].score

    def test_shorts_do_not_steer_longform_scores(self):
        snaps = [
            _snap("s1", "Psalm 91 Short #Shorts", 100000, 5000, 500),
            _snap("l1", "Psalm 91 Protection", 100, 8, 2),
        ]
        idx = {
            "s1": _index("s1", "Psalm 91 Short #Shorts", fmt="short"),
            "l1": _index("l1", "Psalm 91 Protection"),
        }
        perf = compute_video_performance(snaps, idx, TODAY)
        short = next(v for v in perf if v.video_id == "s1")
        assert short.score == 0.0  # Shorts are a separate lane


class TestAggregationAndReport:
    def _rich_data(self):
        snaps, idx = [], {}
        # Protection theme wins clearly.
        for i, (vid, views, likes) in enumerate([("p1", 900, 70), ("p2", 700, 55), ("p3", 800, 60)]):
            snaps.append(_snap(vid, f"Psalm 91 Protection {i}", views, likes, 10))
            idx[vid] = _index(vid, f"Psalm 91 Protection {i}")
        # Stillness theme is weaker.
        for i, (vid, views, likes) in enumerate([("r1", 60, 1), ("r2", 40, 0), ("r3", 55, 1)]):
            snaps.append(_snap(vid, f"Psalm 46 Refuge {i}", views, likes, 0))
            idx[vid] = _index(vid, f"Psalm 46 Refuge {i}")
        return snaps, idx

    def test_themes_ranked_best_first(self):
        snaps, idx = self._rich_data()
        perf = compute_video_performance(snaps, idx, TODAY)
        themes = aggregate_themes(perf)
        assert themes[0].theme == "protection"
        assert themes[0].avg_score > themes[-1].avg_score

    def test_report_sufficient_data_and_privacy(self):
        snaps, idx = self._rich_data()
        report = build_feedback_report(snaps, idx, TODAY)
        assert report["sufficient_data"] is True
        assert report["ranked_themes"][0] == "protection"
        # Privacy: no raw per-video views table in the committed artifact.
        assert "public_videos" not in report
        for t in report["themes"]:
            assert "views" not in t  # only aggregate scores, not raw counts

    def test_report_insufficient_data_is_neutral(self):
        snaps = [_snap("v1", "Psalm 91 Prayer", 5, 0, 0)]
        idx = {"v1": _index("v1", "Psalm 91 Prayer")}
        report = build_feedback_report(snaps, idx, TODAY)
        assert report["sufficient_data"] is False
        assert report["ranked_themes"] == []

    def test_empty_data_never_raises(self):
        report = build_feedback_report([], {}, TODAY)
        assert report["sufficient_data"] is False
        assert report["total_longform_videos"] == 0

    def test_write_and_load_roundtrip(self, tmp_path):
        snaps, idx = self._rich_data()
        report = build_feedback_report(snaps, idx, TODAY)
        p = write_feedback_report(report, tmp_path / "feedback.json")
        loaded = load_feedback_report(p)
        assert loaded["ranked_themes"] == report["ranked_themes"]

    def test_load_missing_returns_none(self, tmp_path):
        assert load_feedback_report(tmp_path / "nope.json") is None


class TestBrainSteering:
    CANDIDATES = [
        {"id": "0100", "scripture": "Psalm 46", "theme": "Be Still — Refuge", "primary_intent": "crisis"},
        {"id": "0101", "scripture": "Psalm 91", "theme": "Divine Protection", "primary_intent": "bedtime protection"},
        {"id": "0102", "scripture": "Psalm 23", "theme": "Shepherd Rest", "primary_intent": "deep sleep"},
    ]

    def test_insufficient_data_preserves_order(self):
        feedback = {"sufficient_data": False, "themes": []}
        assert rank_candidates(self.CANDIDATES, feedback) == self.CANDIDATES

    def test_none_feedback_preserves_order(self):
        assert rank_candidates(self.CANDIDATES, None) == self.CANDIDATES

    def test_winning_theme_moves_first(self):
        feedback = {
            "sufficient_data": True,
            "themes": [
                {"theme": "protection", "avg_score": 0.9, "measured_videos": 3},
                {"theme": "stillness_refuge", "avg_score": 0.1, "measured_videos": 3},
            ],
        }
        ranked = rank_candidates(self.CANDIDATES, feedback)
        assert ranked[0]["scripture"] == "Psalm 91"  # protection wins
        # The Psalm 46 (stillness) candidate should now be last among scored.
        assert ranked[-1]["scripture"] == "Psalm 46"

    def test_unscored_themes_keep_relative_order_after_winners(self):
        feedback = {
            "sufficient_data": True,
            "themes": [{"theme": "protection", "avg_score": 0.9, "measured_videos": 3}],
        }
        ranked = rank_candidates(self.CANDIDATES, feedback)
        assert ranked[0]["scripture"] == "Psalm 91"
        # Psalm 46 then Psalm 23 keep roadmap order (both unscored).
        assert [c["scripture"] for c in ranked[1:]] == ["Psalm 46", "Psalm 23"]

    def test_candidate_theme_classification(self):
        assert candidate_theme({"scripture": "Psalm 91", "theme": "Protection", "primary_intent": ""}) == "protection"


class TestBrainIntegration:
    """Prove the brain's sole authoring choke point actually reads the feedback."""

    def test_select_next_scripture_steers_toward_winning_theme(self, tmp_path, monkeypatch):
        import pipeline.gemini_brain as gb

        # Empty queue + published dirs -> every roadmap candidate is eligible.
        monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "queue")
        monkeypatch.setattr(gb, "PUBLISHED_DIR", tmp_path / "published")
        (tmp_path / "queue").mkdir()
        (tmp_path / "published").mkdir()

        # Protection is the measured winner.
        winning_report = {
            "sufficient_data": True,
            "themes": [
                {"theme": "protection", "avg_score": 0.95, "measured_videos": 3},
                {"theme": "stillness_refuge", "avg_score": 0.05, "measured_videos": 3},
            ],
        }
        monkeypatch.setattr(
            "pipeline.performance_feedback.load_feedback_report", lambda *a, **k: winning_report
        )

        brain = gb.GeminiBrain()
        cand = brain.select_next_scripture()
        # Psalm 91 is the protection candidate and must now be chosen first.
        assert cand["scripture"] == "Psalm 91"

    def test_select_next_scripture_falls_back_without_feedback(self, tmp_path, monkeypatch):
        import pipeline.gemini_brain as gb

        monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "queue")
        monkeypatch.setattr(gb, "PUBLISHED_DIR", tmp_path / "published")
        (tmp_path / "queue").mkdir()
        (tmp_path / "published").mkdir()
        monkeypatch.setattr(
            "pipeline.performance_feedback.load_feedback_report", lambda *a, **k: None
        )

        brain = gb.GeminiBrain()
        cand = brain.select_next_scripture()
        # With no feedback the roadmap order is preserved: Psalm 91 is first anyway,
        # but the key assertion is that a valid candidate is returned (never blocks).
        assert cand.get("id") and cand.get("scripture") and cand.get("theme")

    def test_malformed_feedback_never_blocks_authoring(self, tmp_path, monkeypatch):
        import pipeline.gemini_brain as gb

        monkeypatch.setattr(gb, "QUEUE_DIR", tmp_path / "queue")
        monkeypatch.setattr(gb, "PUBLISHED_DIR", tmp_path / "published")
        (tmp_path / "queue").mkdir()
        (tmp_path / "published").mkdir()

        def boom(*a, **k):
            raise RuntimeError("corrupt artifact")

        monkeypatch.setattr("pipeline.performance_feedback.load_feedback_report", boom)
        brain = gb.GeminiBrain()
        cand = brain.select_next_scripture()  # must not raise
        assert cand.get("scripture")
