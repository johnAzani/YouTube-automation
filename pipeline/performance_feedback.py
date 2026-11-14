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
    "morning_mercy_renewal": [
        "psalm 5", "psalm 143", "lamentations 3", "psalm 59", "psalm 92",
        "psalm 30", "psalm 57", "psalm 108", "psalm 65", "psalm 88",
        "psalm 139", "mark 1", "hosea 6", "zephaniah 3", "exodus 16",
        "new mercies", "lovingkindness", "sunrise", "awake early", "dawn",
        "daybreak", "morning mercy", "fresh manna", "rising early",
    ],
    "daily_guidance_wisdom": [
        "psalm 25", "psalm 119", "psalm 118", "psalm 19", "proverbs 4",
        "isaiah 30", "isaiah 33", "isaiah 50", "joshua 1", "matthew 6",
        "james 1", "micah 7", "2 samuel 23", "exodus 33", "deuteronomy 33",
        "romans 12", "ephesians 6", "colossians 3", "direct my",
        "ordered steps", "wisdom", "guidance", "lamp unto my feet",
        "seek ye first", "armour of god",
    ],
    "midday_strength_endurance": [
        "psalm 55", "psalm 63", "psalm 73", "psalm 84", "psalm 62",
        "psalm 90", "isaiah 40", "isaiah 49", "isaiah 58", "isaiah 25",
        "isaiah 32", "daniel 6", "acts 10", "galatians 6", "1 corinthians 15",
        "2 corinthians 12", "2 chronicles 20", "nehemiah 2", "nehemiah 6",
        "jeremiah 17", "john 4", "1 thessalonians 5", "hebrews 4",
        "hebrews 12", "1 peter 4", "proverbs 15", "proverbs 18", "psalm 37",
        "noonday", "midday", "at noon", "sixth hour", "endurance",
        "renewed strength", "work of our hands", "living water",
    ],
}

_SCRIPTURE_BOOK_NAMES = (
    r"(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm|Psalms|Proverbs|"
    r"Ecclesiastes|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|"
    r"Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|"
    r"Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|"
    r"Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|"
    r"Hebrews|James|Peter|Jude|Revelation)"
)


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
            if re.match(rf"^(?:[123]\s+)?{_SCRIPTURE_BOOK_NAMES}\s+\d+$", kw, re.IGNORECASE):
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
        rf"\b((?:[123]\s+)?{_SCRIPTURE_BOOK_NAMES}\s+\d+)",
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
                        "views": int(r["views"]) if r.get("views") not in (None, "") else None,
                        "likes": int(r.get("likes", 0) or 0),
                        "comments": int(r.get("comments", 0) or 0),
                    })
                except (ValueError, TypeError):
                    continue
    except OSError:
        return []
    return rows


def feedback_path_for(channel_id: str | None = None) -> Path:
    """Path to the committed aggregate feedback artifact for `channel_id`."""
    if not channel_id:
        return FEEDBACK_JSON
    from .channel_capabilities import brand_for
    from .channels import normalize_channel_id

    brand = brand_for(normalize_channel_id(channel_id))
    return REPO_ROOT / "content" / "research" / brand.feedback_artifact_name


def load_published_index(
    published_dir: Path | None = None,
    channel_id: str | None = None,
) -> dict[str, dict]:
    """Index published receipts by YouTube video ID (`{video_id: {...}}`)."""
    from .channels import normalize_channel_id
    from .script_doc import parse_script

    wanted = normalize_channel_id(channel_id) if channel_id else None
    pdir = Path(published_dir) if published_dir else PUBLISHED_DIR
    index: dict[str, dict] = {}
    if not pdir.exists():
        return index
    for p in sorted(pdir.glob("*.md")):
        try:
            doc = parse_script(p)
        except Exception:
            continue
        if wanted and doc.channel != wanted:
            continue
        vid = str(doc.meta.get("youtube_video_id", "") or "")
        if not vid:
            continue
        title = doc.title
        index[vid] = {
            "title": title,
            "format": doc.format,
            "channel": doc.channel,
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
    views_known: bool = True
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
            "views": self.views if self.views_known else None,
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
        # The API's public timestamp is preferable to a potentially later
        # receipt-recovery date; use receipt metadata only when it is absent.
        pub = _parse_date(row.get("published_at", "")) or _parse_date(meta.get("published_on", ""))
        snapshot_date = _parse_date(row.get("snapshot_date", ""))
        # Compare views with age at the time they were collected, not today.
        # A stale/future/undated reading must not become a mature signal merely
        # because time passed after the snapshot.
        valid_dates = bool(pub and snapshot_date and pub <= snapshot_date <= today)
        age_days = (snapshot_date - pub).days if valid_dates else 0
        raw_views = row.get("views")
        views_known = raw_views is not None and raw_views != ""
        views = int(raw_views) if views_known else 0
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
            views_known=views_known,
            likes=likes,
            comments=comments,
            age_days=age_days,
            views_per_day=velocity,
            engagement_rate=engagement,
            measured=(views_known and views >= MIN_VIEWS_FOR_ENGAGEMENT and valid_dates
                      and age_days >= MIN_AGE_DAYS_FOR_VELOCITY),
        ))

    # Normalise velocity and engagement across the measured long-form cohort, then
    # blend. Reach and satisfaction both matter; weight them equally.
    longform = [v for v in results if v.format != "short" and v.measured]
    max_vel = max((v.views_per_day for v in longform), default=0.0)
    max_eng = max((v.engagement_rate for v in longform), default=0.0)
    for v in results:
        if v.format == "short" or not v.measured:
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
        # Only measured videos influence rankings; retain unmeasured themes with
        # zero scores for visibility, never as evidence for steering.
        cohort = measured
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


# ---------------------------------------------------------------------------
# Shorts: the format that is watched
# ---------------------------------------------------------------------------
# Until 14 November 2026 this module set Shorts aside ("a separate lane") and
# steered only by long-forms. No channel has ever had three long-forms with 25
# views, so the loop never produced a signal, while 91 Shorts drew 97% of all
# views (docs/GROWTH_EVIDENCE_2026-11-14.md). The Shorts are measured here.

#: A Short gathers most of its views in its first two days; younger is not counted.
MIN_SHORT_AGE_DAYS = 2
#: Fewer measured Shorts than this on a channel is not a signal.
MIN_SHORTS_FOR_SIGNAL = 6
#: Shrinkage: a bucket is pulled toward the channel average as if it held this
#: many average Shorts as well, so one lucky Short does not crown its book.
SHORT_BUCKET_PRIOR = 2
#: A passage whose book and theme together run this far above (below) the
#: channel average moves to the front (back) of the list.
SHORT_PROMOTE_RATIO = 1.2
SHORT_DEMOTE_RATIO = 0.7


def scripture_book(reference: str) -> str:
    """``"1 John 4:4"`` -> ``"1 john"``; ``""`` when no book is named."""
    try:
        from .scripture_text import UnknownReference, parse_reference
    except Exception:  # noqa: BLE001
        return ""
    try:
        return parse_reference(reference)[0]
    except UnknownReference:
        return ""


def aggregate_shorts(perf: list[VideoPerformance]) -> dict:
    """Views of this channel's Shorts by book and by theme: aggregates only.

    Each bucket carries its count and a ``ratio``: its shrunk average divided by
    the channel's average Short. 1.0 is an average Short for this channel.
    """
    measured = [v for v in perf if v.format == "short" and v.views_known
                and v.age_days >= MIN_SHORT_AGE_DAYS]
    total = sum(v.views for v in measured)
    average = total / len(measured) if measured else 0.0
    views_sorted = sorted(v.views for v in measured)
    median = views_sorted[len(views_sorted) // 2] if views_sorted else 0

    def buckets(key) -> dict[str, dict]:
        groups: dict[str, list[int]] = {}
        for video in measured:
            name = key(video)
            if name:
                groups.setdefault(name, []).append(video.views)
        out: dict[str, dict] = {}
        for name, views in sorted(groups.items()):
            shrunk = (sum(views) + SHORT_BUCKET_PRIOR * average) / (len(views) + SHORT_BUCKET_PRIOR)
            out[name] = {"shorts": len(views),
                         "avg_views": round(sum(views) / len(views), 1),
                         "ratio": round(shrunk / average, 3) if average > 0 else 1.0}
        return out

    return {
        "measured_shorts": len(measured),
        "total_shorts": sum(1 for v in perf if v.format == "short"),
        "sufficient_data": len(measured) >= MIN_SHORTS_FOR_SIGNAL and average > 0,
        "avg_views": round(average, 1),
        "median_views": median,
        "total_views": total,
        "minimum_age_days": MIN_SHORT_AGE_DAYS,
        "by_book": buckets(lambda v: scripture_book(v.title) or scripture_book(v.scripture)),
        "by_theme": buckets(lambda v: v.theme),
    }


def network_shorts_signal(research_dir: Path | None = None) -> dict | None:
    """Every channel's committed Shorts aggregates, pooled: the prior for a channel with too few of its own.

    Views are pooled as counts, so a channel with 24 Shorts weighs more than one
    with two. Returns ``None`` when the network itself has too little.
    """
    directory = Path(research_dir) if research_dir else FEEDBACK_JSON.parent
    books: dict[str, list[float]] = {}
    themes: dict[str, list[float]] = {}
    measured = 0
    total = 0.0
    for path in sorted(directory.glob("performance_feedback*.json")):
        try:
            shorts = (json.loads(path.read_text(encoding="utf-8")) or {}).get("shorts") or {}
        except (OSError, json.JSONDecodeError):
            continue
        measured += int(shorts.get("measured_shorts") or 0)
        total += float(shorts.get("total_views") or 0)
        for target, source in ((books, "by_book"), (themes, "by_theme")):
            for name, row in (shorts.get(source) or {}).items():
                count = int(row.get("shorts") or 0)
                entry = target.setdefault(name, [0, 0.0])
                entry[0] += count
                entry[1] += float(row.get("avg_views") or 0) * count
    if measured < MIN_SHORTS_FOR_SIGNAL * 2 or total <= 0:
        return None
    average = total / measured

    def ratios(groups: dict[str, list[float]]) -> dict[str, dict]:
        return {name: {"shorts": int(count),
                       "ratio": round(((views + SHORT_BUCKET_PRIOR * average)
                                       / (count + SHORT_BUCKET_PRIOR)) / average, 3)}
                for name, (count, views) in groups.items() if count}

    return {"measured_shorts": measured, "sufficient_data": True, "avg_views": round(average, 1),
            "by_book": ratios(books), "by_theme": ratios(themes), "scope": "network"}


def short_passage_ratio(reference: str, shorts: dict | None) -> float:
    """Expected views of a Short on this passage, as a multiple of the average Short: 1.0 = unknown or average."""
    if not shorts or not shorts.get("sufficient_data"):
        return 1.0
    seen: list[float] = []
    book = (shorts.get("by_book") or {}).get(scripture_book(reference))
    if book:
        seen.append(float(book.get("ratio") or 1.0))
    theme = (shorts.get("by_theme") or {}).get(classify_theme(reference))
    if theme and classify_theme(reference) != "general_prayer":
        seen.append(float(theme.get("ratio") or 1.0))
    return sum(seen) / len(seen) if seen else 1.0


def rank_short_passages(references: list[str], feedback: dict | None,
                        network: dict | None = None) -> list[str]:
    """Reorder passages a channel can make a Short of: what its viewers watch first.

    Three bands, as for long-forms: passages expected well above the average
    Short move to the front (best first), those well below move to the back, and
    the rest keep the order they were listed in. The channel's own numbers are
    used when it has enough Shorts; otherwise the network's; otherwise the list
    is returned as it came.
    """
    shorts = (feedback or {}).get("shorts") if feedback else None
    if not shorts or not shorts.get("sufficient_data"):
        shorts = network
    if not shorts or not shorts.get("sufficient_data"):
        return list(references)

    def sort_key(item: tuple[int, str]) -> tuple:
        index, reference = item
        ratio = short_passage_ratio(reference, shorts)
        if ratio >= SHORT_PROMOTE_RATIO:
            return (0, -ratio, index)
        if ratio <= SHORT_DEMOTE_RATIO:
            return (2, -ratio, index)
        return (1, 0.0, index)

    return [reference for _, reference in sorted(enumerate(references), key=sort_key)]


def build_feedback_report(
    snapshots: list[dict] | None = None,
    published_index: dict[str, dict] | None = None,
    today: date | None = None,
    channel_id: str | None = None,
) -> dict:
    """Build the committed, public-safe feedback artifact."""
    snapshots = snapshots if snapshots is not None else load_metric_snapshots()
    published_index = (
        published_index
        if published_index is not None
        else load_published_index(channel_id=channel_id)
    )
    snapshot_ids = {str(r.get("video_id")) for r in snapshots if r.get("video_id")}
    receipt_ids = set(published_index)
    if channel_id and snapshots:
        # Restrict snapshot rows to videos belonging to this channel's published index
        snapshots = [r for r in snapshots if r.get("video_id") in published_index]
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
            f"Only {len(measured)} long-form video(s) have at least {MIN_VIEWS_FOR_ENGAGEMENT} views "
            f"and are at least {MIN_AGE_DAYS_FOR_VELOCITY} days old; need {MIN_VIDEOS_FOR_SIGNAL}. "
            "Keeping roadmap order until the signal is real."
        )
    else:
        measured_themes = [t for t in themes if t.measured_videos > 0]
        if measured_themes:
            top = measured_themes[0]
            guidance.append(
                f"'{top.theme}' is the strongest measured theme "
                f"(avg score {top.avg_score:.2f}, {top.measured_videos} measured video(s)). "
                f"Favour it when choosing the next devotional."
            )
        if len(measured_themes) > 1:
            bottom = measured_themes[-1]
            guidance.append(
                f"'{bottom.theme}' is currently the weakest measured theme; "
                f"deprioritise it until the audience signal changes."
            )

    shorts = aggregate_shorts(perf)
    shorts_guidance: list[str] = []
    shorts["guidance"] = shorts_guidance
    if shorts["sufficient_data"]:
        strong = sorted(((row["ratio"], name) for name, row in shorts["by_book"].items()
                         if row["shorts"] >= 2 and row["ratio"] >= SHORT_PROMOTE_RATIO), reverse=True)
        if strong:
            shorts_guidance.append(
                f"Shorts: {strong[0][1].title()} runs {strong[0][0]:.1f}x this channel's average "
                f"Short ({shorts['avg_views']:.0f} views over {shorts['measured_shorts']} Shorts); "
                "its passages are written first.")
    else:
        shorts_guidance.append(
            f"Shorts: {shorts['measured_shorts']} measured (need {MIN_SHORTS_FOR_SIGNAL}, each at "
            f"least {MIN_SHORT_AGE_DAYS} days old); the network's pooled numbers order this "
            "channel's Shorts until it has its own.")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": today.isoformat(),
        "sufficient_data": sufficient,
        "measured_longform_videos": len(measured),
        "total_longform_videos": len(longform),
        # Aggregates only: distinguish an unmatched snapshot from a matched video
        # below the signal gate without publishing raw per-video metrics.
        "input_diagnostics": {
            "snapshot_video_ids": len(snapshot_ids),
            "receipt_video_ids": len(receipt_ids),
            "matched_video_ids": len(snapshot_ids & receipt_ids),
            "longform_below_view_threshold": sum(v.views_known and v.views < MIN_VIEWS_FOR_ENGAGEMENT for v in longform),
            "longform_missing_view_count": sum(not v.views_known for v in longform),
            "longform_too_young_or_undated": sum(v.age_days < MIN_AGE_DAYS_FOR_VELOCITY for v in longform),
            "minimum_views": MIN_VIEWS_FOR_ENGAGEMENT,
            "minimum_age_days": MIN_AGE_DAYS_FOR_VELOCITY,
        },
        "ranked_themes": ranked_themes,
        "themes": [t.as_dict() for t in themes],
        "shorts": shorts,
        "guidance": guidance,
        "cost_lock": "$0.00 — public Data API statistics only; no new quota or secret.",
        "privacy": "Aggregate theme scores only; raw per-video snapshot stays an Actions artifact.",
    }


def write_feedback_report(
    report: dict,
    out_path: Path | None = None,
    channel_id: str | None = None,
) -> Path:
    path = Path(out_path) if out_path else feedback_path_for(channel_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def load_feedback_report(
    path: Path | None = None,
    channel_id: str | None = None,
) -> dict | None:
    p = Path(path) if path else feedback_path_for(channel_id)
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
