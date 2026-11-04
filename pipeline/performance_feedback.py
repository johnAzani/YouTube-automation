"""Closed-loop performance feedback — the missing keystone of the growth engine.

The brain used to author scripture from a *static* roadmap in fixed order and never
read which videos actually performed. This module closes that loop: it reads the
public metrics snapshots already collected by ``scripts/metrics_snapshot.py`` plus
the published receipts, computes per-video performance (view velocity + engagement
rate), aggregates it by scripture/theme, and emits a ranked signal the brain uses
to favour the themes that are actually winning.

Cost & safety invariants ($0.00 lock):
  * Uses ONLY public YouTube Data API statistics (views/likes/comments) that the
    existing upload token already collects. No new secret, no paid tier, no extra
    quota beyond the ``videos.list`` (1 unit) the snapshot already spends.
  * Privacy: the committed artifact carries aggregate theme scores and guidance,
    never a raw per-video metrics table. The public-video snapshot itself stays a
    short-lived Actions artifact, exactly as ``metrics.yml`` already enforces.
  * Fail-soft: with too little data it returns a neutral "insufficient_data" report
    and the brain falls back to its roadmap order. It never blocks authoring.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import PUBLISHED_DIR, REPO_ROOT

METRICS_CSV = REPO_ROOT / "content" / "metrics.csv"
FEEDBACK_JSON = REPO_ROOT / "content" / "research" / "performance_feedback.json"

# A video needs a few days of age before its view velocity is meaningful; a video
# published this morning would otherwise show an absurd views/day from 3 views.
MIN_AGE_DAYS_FOR_VELOCITY = 3
# Below this many measured videos the signal is noise, not evidence. The brain
# keeps its roadmap order until there is enough data to steer by.
MIN_VIDEOS_FOR_SIGNAL = 3
# Minimum lifetime views before a video's engagement rate is trusted (1 like on
# 2 views is 50% engagement but statistically meaningless).
MIN_VIEWS_FOR_ENGAGEMENT = 25


# ---------------------------------------------------------------------------
# Theme taxonomy — map a scripture/title to the intent bucket it serves.
# ---------------------------------------------------------------------------
THEME_KEYWORDS: dict[str, list[str]] = {
    "protection": [
        "psalm 91", "psalm 3", "psalm 34", "protection", "shield", "guard",
        "angel", "deliver", "refuge from terror", "terror by night", "encamp",
    ],
    "peace_rest": [
        "psalm 23", "psalm 4", "psalm 121", "peace", "rest", "shepherd",
        "still waters", "lie down", "sleep", "restore my soul", "keeper",
        "slumber", "green pastures",
    ],
    "stillness_refuge": [
        "psalm 46", "be still", "refuge", "strength", "god is our refuge",
        "very present help",
    ],
    "light_courage": [
        "psalm 27", "light", "salvation", "fear no", "courage", "fear",
        "the lord is my light",
    ],
    "trust_surrender": [
        "psalm 31", "psalm 16", "commit", "trust", "surrender", "into your hand",
        "counsel in the night", "my rock", "my fortress", "psalm 18",
    ],
    "anxiety_peace": [
        "philippians 4", "matthew 11", "john 14", "1 peter 5", "2 timothy 1",
        "anxiety", "weary", "rest for the weary", "peace that guards",
        "casting all your care", "power love", "sound mind", "perfect peace",
        "isaiah 26", "isaiah 41", "proverbs 3",
    ],
    "blessing_benediction": [
        "numbers 6", "benediction", "priestly", "the lord bless",
    ],
}


def classify_theme(title: str, tags: Iterable[str] = ()) -> str:
    """Return the dominant intent bucket for a title (+optional tags).

    Scripture-specific matches win over generic keywords so "Psalm 91 … peace"
    is classified as protection, not peace_rest.
    """
    hay = (title or "").lower()
    tag_hay = " ".join(t.lower() for t in tags)
    # Scripture references are the strongest signal. Match with a digit boundary so
    # "psalm 4" does not accidentally match "psalm 46".
    for theme, kws in THEME_KEYWORDS.items():
        for kw in kws:
            if re.match(r"^(?:[123]\s+)?(?:psalm|isaiah|matthew|john|philippians|"
                        r"numbers|proverbs|peter|timothy|mark|luke|romans|hebrews)", kw):
                if re.search(r"\b" + re.escape(kw) + r"(?!\d)", hay):
                    return theme
    # Then keyword matches in title, then tags.
    for theme, kws in THEME_KEYWORDS.items():
        for kw in kws:
            if kw in hay:
                return theme
    for theme, kws in THEME_KEYWORDS.items():
        for kw in kws:
            if kw in tag_hay:
                return theme
    return "general_prayer"


def extract_scripture(title: str) -> str:
    """Pull a normalised scripture reference (e.g. 'Psalm 91') from a title."""
    m = re.search(
        r"\b((?:[123]\s+)?(?:Psalm|Psalms|Proverbs|Isaiah|Matthew|Mark|Luke|John|"
        r"Romans|Philippians|Timothy|Peter|Numbers|Jude|Hebrews|Corinthians|Ephesians)"
        r"\s+\d+)",
        title or "",
        re.IGNORECASE,
    )
    if not m:
        return ""
    ref = " ".join(m.group(1).split())
    # Normalise "Psalms" -> "Psalm" and collapse whitespace.
    ref = re.sub(r"^Psalms\b", "Psalm", ref, flags=re.IGNORECASE)
    return ref.title()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_metric_snapshots(csv_path: Path | None = None) -> list[dict]:
    """Read the rolling public-video snapshot rows (one row per video per day)."""
    path = Path(csv_path) if csv_path else METRICS_CSV
    if not path.is_file():
        return []
    rows: list[dict] = []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    rows.append({
                        "video_id": r.get("video_id", ""),
                        "title": r.get("title", ""),
                        "snapshot_date": r.get("snapshot_date", ""),
                        "published_at": r.get("published_at", ""),
                        "views": int(r.get("views", 0) or 0),
                        "likes": int(r.get("likes", 0) or 0),
                        "comments": int(r.get("comments", 0) or 0),
                    })
                except (ValueError, TypeError):
                    continue
    except OSError:
        return []
    return rows


def load_published_index(published_dir: Path | None = None) -> dict[str, dict]:
    """Map video_id -> receipt metadata (title, format, scripture, theme)."""
    from .script_doc import parse_script

    pdir = Path(published_dir) if published_dir else PUBLISHED_DIR
    index: dict[str, dict] = {}
    if not pdir.exists():
        return index
    for p in sorted(pdir.glob("*.md")):
        try:
            doc = parse_script(p)
        except Exception:
            continue
        vid = str(doc.meta.get("youtube_video_id", "") or "")
        if not vid:
            continue
        title = doc.title
        index[vid] = {
            "title": title,
            "format": doc.format,
            "scripture": extract_scripture(title),
            "theme": classify_theme(title, doc.tags),
            "published_on": str(doc.meta.get("published_on", "") or ""),
        }
    return index


# ---------------------------------------------------------------------------
# Per-video performance
# ---------------------------------------------------------------------------
@dataclass
class VideoPerformance:
    video_id: str
    title: str
    theme: str
    scripture: str
    format: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    age_days: int = 0
    views_per_day: float = 0.0
    engagement_rate: float = 0.0
    score: float = 0.0
    measured: bool = False

    def as_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "theme": self.theme,
            "scripture": self.scripture,
            "format": self.format,
            "views": self.views,
            "age_days": self.age_days,
            "views_per_day": round(self.views_per_day, 3),
            "engagement_rate": round(self.engagement_rate, 4),
            "score": round(self.score, 4),
            "measured": self.measured,
        }


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def compute_video_performance(
    snapshots: list[dict],
    published_index: dict[str, dict],
    today: date | None = None,
) -> list[VideoPerformance]:
    """Collapse the rolling snapshots to the latest reading per video and score it.

    Score blends normalised view velocity (reach) and engagement rate (satisfaction).
    Only long-form videos steer the long-form brain; Shorts are tracked but kept in
    a separate lane because their discovery engine is different.
    """
    today = today or datetime.now(timezone.utc).date()
    latest: dict[str, dict] = {}
    for row in snapshots:
        vid = row.get("video_id", "")
        if not vid:
            continue
        prev = latest.get(vid)
        if prev is None or row.get("snapshot_date", "") >= prev.get("snapshot_date", ""):
            latest[vid] = row

    results: list[VideoPerformance] = []
    for vid, row in latest.items():
        meta = published_index.get(vid, {})
        title = meta.get("title") or row.get("title", "")
        fmt = meta.get("format", "longform")
        pub = _parse_date(meta.get("published_on") or row.get("published_at", ""))
        age_days = max(0, (today - pub).days) if pub else 0
        views = int(row.get("views", 0))
        likes = int(row.get("likes", 0))
        comments = int(row.get("comments", 0))

        velocity = views / max(age_days, 1) if age_days >= MIN_AGE_DAYS_FOR_VELOCITY else 0.0
        engagement = (likes + comments) / views if views >= MIN_VIEWS_FOR_ENGAGEMENT else 0.0

        results.append(VideoPerformance(
            video_id=vid,
            title=title,
            theme=meta.get("theme") or classify_theme(title),
            scripture=meta.get("scripture") or extract_scripture(title),
            format=fmt,
            views=views,
            likes=likes,
            comments=comments,
            age_days=age_days,
            views_per_day=velocity,
            engagement_rate=engagement,
            measured=views >= MIN_VIEWS_FOR_ENGAGEMENT,
        ))

    # Normalise velocity and engagement across the measured long-form cohort, then
    # blend. Reach and satisfaction both matter; weight them equally.
    longform = [v for v in results if v.format != "short"]
    max_vel = max((v.views_per_day for v in longform), default=0.0)
    max_eng = max((v.engagement_rate for v in longform), default=0.0)
    for v in results:
        if v.format == "short":
            continue
        nv = (v.views_per_day / max_vel) if max_vel > 0 else 0.0
        ne = (v.engagement_rate / max_eng) if max_eng > 0 else 0.0
        v.score = round(0.5 * nv + 0.5 * ne, 4)
    return results


# ---------------------------------------------------------------------------
# Theme aggregation + guidance
# ---------------------------------------------------------------------------
@dataclass
class ThemeScore:
    theme: str
    videos: int = 0
    measured_videos: int = 0
    avg_score: float = 0.0
    total_views: int = 0
    avg_engagement: float = 0.0
    top_scripture: str = ""

    def as_dict(self) -> dict:
        return {
            "theme": self.theme,
            "videos": self.videos,
            "measured_videos": self.measured_videos,
            "avg_score": round(self.avg_score, 4),
            "avg_engagement": round(self.avg_engagement, 4),
            "top_scripture": self.top_scripture,
        }


def aggregate_themes(perf: list[VideoPerformance]) -> list[ThemeScore]:
    """Aggregate long-form performance by theme, ranked best-first."""
    buckets: dict[str, list[VideoPerformance]] = {}
    for v in perf:
        if v.format == "short":
            continue
        buckets.setdefault(v.theme, []).append(v)

    themes: list[ThemeScore] = []
    for theme, vids in buckets.items():
        measured = [v for v in vids if v.measured]
        # Average over measured videos when present, else over all (with a penalty
        # baked into the confidence gate downstream).
        cohort = measured or vids
        avg_score = sum(v.score for v in cohort) / len(cohort) if cohort else 0.0
        avg_eng = sum(v.engagement_rate for v in cohort) / len(cohort) if cohort else 0.0
        # Top scripture = the highest-scoring measured video's reference.
        best = max(cohort, key=lambda v: v.score) if cohort else None
        themes.append(ThemeScore(
            theme=theme,
            videos=len(vids),
            measured_videos=len(measured),
            avg_score=avg_score,
            total_views=sum(v.views for v in vids),
            avg_engagement=avg_eng,
            top_scripture=(best.scripture if best else ""),
        ))
    themes.sort(key=lambda t: (t.avg_score, t.measured_videos, t.total_views), reverse=True)
    return themes


def build_feedback_report(
    snapshots: list[dict] | None = None,
    published_index: dict[str, dict] | None = None,
    today: date | None = None,
) -> dict:
    """Build the committed, public-safe feedback artifact."""
    snapshots = snapshots if snapshots is not None else load_metric_snapshots()
    published_index = published_index if published_index is not None else load_published_index()
    today = today or datetime.now(timezone.utc).date()

    perf = compute_video_performance(snapshots, published_index, today)
    themes = aggregate_themes(perf)
    longform = [v for v in perf if v.format != "short"]
    measured = [v for v in longform if v.measured]

    sufficient = len(measured) >= MIN_VIDEOS_FOR_SIGNAL
    ranked_themes = [t.theme for t in themes if t.measured_videos > 0]

    guidance: list[str] = []
    if not sufficient:
        guidance.append(
            f"Only {len(measured)} long-form video(s) have enough views to measure; "
            f"need {MIN_VIDEOS_FOR_SIGNAL}. Keeping roadmap order until the signal is real."
        )
    else:
        if themes:
            top = themes[0]
            guidance.append(
                f"'{top.theme}' is the strongest measured theme "
                f"(avg score {top.avg_score:.2f}, {top.measured_videos} measured video(s)). "
                f"Favour it when choosing the next devotional."
            )
        if len(themes) > 1:
            bottom = themes[-1]
            guidance.append(
                f"'{bottom.theme}' is currently the weakest measured theme; "
                f"deprioritise it until the audience signal changes."
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": today.isoformat(),
        "sufficient_data": sufficient,
        "measured_longform_videos": len(measured),
        "total_longform_videos": len(longform),
        "ranked_themes": ranked_themes,
        "themes": [t.as_dict() for t in themes],
        "guidance": guidance,
        "cost_lock": "$0.00 — public Data API statistics only; no new quota or secret.",
        "privacy": "Aggregate theme scores only; raw per-video snapshot stays an Actions artifact.",
    }


def write_feedback_report(report: dict, out_path: Path | None = None) -> Path:
    path = Path(out_path) if out_path else FEEDBACK_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def load_feedback_report(path: Path | None = None) -> dict | None:
    p = Path(path) if path else FEEDBACK_JSON
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Brain steering
# ---------------------------------------------------------------------------
def candidate_theme(candidate: dict) -> str:
    """Theme bucket for a roadmap candidate (uses scripture + theme + intent)."""
    scripture = str(candidate.get("scripture", ""))
    theme = str(candidate.get("theme", ""))
    intent = str(candidate.get("primary_intent", ""))
    return classify_theme(f"{scripture} {theme} {intent}")


def rank_candidates(candidates: list[dict], feedback: dict | None) -> list[dict]:
    """Reorder roadmap candidates to favour winning themes.

    Three bands, so the brain doubles down on what works without burying the
    unmeasured:
      * themes scoring at/above the measured average move to the front (best first);
      * themes with no measured score keep their relative roadmap order in the middle;
      * themes scoring below the measured average move to the back.

    With insufficient data the list is returned unchanged so the brain never steers
    on noise.
    """
    if not feedback or not feedback.get("sufficient_data"):
        return list(candidates)
    themes = feedback.get("themes", [])
    score_by_theme = {
        t["theme"]: t["avg_score"]
        for t in themes
        if t.get("measured_videos", 0) > 0
    }
    if not score_by_theme:
        return list(candidates)

    mean_score = sum(score_by_theme.values()) / len(score_by_theme)

    def sort_key(item: tuple[int, dict]) -> tuple:
        idx, cand = item
        theme = candidate_theme(cand)
        if theme in score_by_theme:
            score = score_by_theme[theme]
            if score >= mean_score:
                return (0, -score, idx)   # winners: best first
            return (2, -score, idx)       # underperformers: deprioritised
        return (1, 0.0, idx)              # unmeasured: keep roadmap place

    ordered = sorted(enumerate(candidates), key=sort_key)
    return [cand for _, cand in ordered]
