"""Where the watch hours actually come from, per channel, and what to do about it.

Why this exists (docs/GROWTH_SCORE_2026-11-21.md). The channels are watched
mostly in the Shorts feed, and Shorts-feed watch time does not count toward the
4,000 hours the Partner Program asks for. The hours that do count arrive through
a different door: suggested videos, YouTube search, playlists, end screens. Until
now nothing in this repository said which door each channel's hours came through,
so nothing could say what would make them larger.

What this reads
---------------
``content/analytics/<channel>.json`` — written by ``scripts/analytics_reader.py``
from the channel's own YouTube Analytics, for channels that have granted the
read-only Analytics scope. It holds, per channel, the last 28 days of watch hours
by day and by traffic source, and the video-by-video hours over 365 days.

What this writes
----------------
``content/research/growth_score.json``: a public-safe file holding

* the network's hours by source over the days every channel reports on (the
  same days for every channel, so the shares add up to one);
* how much of the 4,000-hour need that budget accounts for, over the 365-day
  figure, and what pace the last seven days ran at;
* each channel's target: its share of the network's counted hours in the
  windows this job can actually move (suggested, search, playlists, end
  screens), multiplied by the network budget;
* a reading from ``content/research/growth_sources.json`` (built by
  ``scripts/growth_ab.py``) that says, by how much, each format change moved the
  hours coming in through that door;
* the ``GROWTH_BUDGET_MINUTES`` the release pipeline should use now, and
  ``GROWTH_KEEP_TAIL`` — whether the bedtime channel's night tail earns its
  keep.

It never writes a revenue figure, a viewer's identity, or another channel's
title. Only hours, views, minutes and shares.

Fail-soft by design
-------------------
A channel without an Analytics grant, a file that cannot be read, or a week with
no reading keeps whatever it had and is named in the report. Nothing here talks
to YouTube, and nothing here can fail a release.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # ``python -m`` runs this as a module, the CLI as a script
    sys.path.insert(0, str(ROOT))

ANALYTICS_DIR = ROOT / "content" / "analytics"
REPORT_PATH = ROOT / "content" / "research" / "growth_score.json"
#: Written by scripts/growth_ab.py: what each format change did to the hours.
SOURCES_PATH = ROOT / "content" / "research" / "growth_sources.json"
SCHEMA = 1

#: The windows a change to a release can move. The Shorts feed is deliberately
#: absent: its hours do not count toward the 4,000, and steering the channels
#: toward it would raise a number that never reaches the threshold.
SHARE_MEDIA = ("suggested", "yt_search", "playlist", "end_screen")
#: Every source the reader writes, in the order a reader should meet them.
SOURCE_KEYS = ("suggested", "shorts_feed", "yt_search", "home_subs", "other_pages",
               "playlist", "end_screen", "notifications", "ext_url", "direct_unknown",
               "embedded", "channel_page")
#: YouTube's own names for a traffic source (``insightTrafficSourceType``) and the
#: name used here. An unknown code is kept, lower-cased, rather than dropped: a new
#: door is worth seeing even before it is understood.
SOURCE_NAMES = {
    "RELATED_VIDEO": "suggested",
    "SHORTS": "shorts_feed",
    "YT_SEARCH": "yt_search",
    "SUBSCRIBER": "home_subs",
    "YT_OTHER_PAGE": "other_pages",
    "PLAYLIST": "playlist",
    "END_SCREEN": "end_screen",
    "NOTIFICATION": "notifications",
    "EXT_URL": "ext_url",
    "NO_LINK_OTHER": "direct_unknown",
    "NO_LINK_EMBEDDED": "embedded",
    "YT_CHANNEL": "channel_page",
    "CAMPAIGN_CARD": "campaign_card",
    "ANNOTATION": "cards",
    "HASHTAGS": "hashtags",
    "SOUND_PAGE": "sound_pages",
    "VIDEO_REMIXES": "remixes",
    "LIVE_REDIRECT": "live_redirects",
    "PROMOTED": "promoted",
    "PRODUCT_PAGE": "product_pages",
    "ADVERTISING": "advertising",
}
#: A hold has to survive this many days of reading before its budget is spent.
MIN_DAYS_FOR_PACE = 7
#: A bump is only counted on a video this old, so a new release's first day is
#: never mistaken for a step change in what an existing video earns.
MIN_AGE_FOR_BUMP_DAYS = 4
#: Previous days of a video needed before its usual day can be called usual.
MIN_DAYS_FOR_USUAL = 3
#: Below this many hours a channel has no pace worth projecting: a target built
#: on four minutes a day is noise dressed as a plan.
MIN_HOURS_FOR_PACE = 0.5
#: The length a release falls back to when nothing has been measured yet: the
#: night tail's own three hours, which is what the bedtime channel publishes
#: today. It has to sit inside the limits below or the fallback could not be used.
DEFAULT_BUDGET_MINUTES = 180
#: Never ask the render to hold a video longer than this: the runner's cap, the
#: upload time and the night tail's own ten-hour ceiling both have to survive it.
MAX_BUDGET_MINUTES = 180
MIN_BUDGET_MINUTES = 3
#: How many of the most recent bumps decide a verdict (most recent first).
BUMPS_READ = 12


# --------------------------------------------------------------------------- #
# Reading one channel's Analytics file
# --------------------------------------------------------------------------- #
def _hours(value: Any) -> float:
    if isinstance(value, bool):  # a flag is not a measurement
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return 0.0
    return round(max(number, 0.0), 2)


def _int(value: Any) -> int:
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


def read_channel(path: Path) -> dict | None:
    """One channel's days, sources and videos, or ``None`` when unreadable.

    The file is written by another job, so every field is treated as untrusted:
    a malformed row is dropped, never raised.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    channel = str(payload.get("channel") or "").strip()
    if not channel:
        return None

    days: dict[str, dict] = {}
    for row in payload.get("last_28_days", {}).get("by_day") or []:
        if not isinstance(row, dict):
            continue
        day = str(row.get("day") or "").strip()
        if len(day) != 10:
            continue
        days[day] = {"views": _int(row.get("views")), "hours": _hours(row.get("watch_hours"))}

    sources: dict[str, dict] = {}
    traffic = (payload.get("last_28_days") or {}).get("traffic_sources") or []
    if isinstance(traffic, list):
        for row in traffic:
            if not isinstance(row, dict):
                continue
            code = str(row.get("source") or "").strip()
            if not code:
                continue
            key = SOURCE_NAMES.get(code, code.lower())
            slot = sources.setdefault(key, {"views": 0, "hours": 0.0})
            slot["views"] += _int(row.get("views"))
            slot["hours"] = round(slot["hours"] + _hours(row.get("watch_hours")), 2)

    videos = []
    for row in payload.get("videos_365d") or []:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("video_id") or "").strip()
        if not vid:
            continue
        videos.append({
            "video_id": vid,
            "hours": _hours(row.get("watch_hours")),
            "views": _int(row.get("views")),
            "average_view_percent": _hours(row.get("average_view_percent")),
            # Seconds watched a view: where the length ceiling is measured from.
            "average_view_seconds": _hours(row.get("average_view_seconds")),
        })

    by_kind = (payload.get("last_28_days") or {}).get("views_by_kind") or {}
    long_form_views = _int(by_kind.get("videoondemand")) + _int(by_kind.get("livestream"))
    shorts_views = _int(by_kind.get("shorts"))
    kind_total = long_form_views + shorts_views

    partner = payload.get("partner_program") or {}
    counted = _hours((partner.get("watch_hours_365d") or {}).get("long_form_and_live")
                     if isinstance(partner.get("watch_hours_365d"), dict) else None)
    return {
        "channel": channel,
        "generated_at": str(payload.get("generated_at") or ""),
        "days": days,
        "sources": sources,
        "videos": videos,
        "watch_hours_365d": counted,
        # What share of the views a day are long-form rather than Shorts. The
        # daily series mixes both, and a Short view is worth seconds where a
        # long-form view is worth minutes, so the budget is priced on this share.
        "long_form_view_share": round(long_form_views / kind_total, 4) if kind_total else None,
    }


def load_channels(directory: Path | None = None) -> tuple[dict[str, dict], list[str]]:
    """Every readable channel file: ``(reports, unreadable)``."""
    base = Path(directory) if directory else ANALYTICS_DIR
    found: dict[str, dict] = {}
    missing: list[str] = []
    if not base.is_dir():
        return found, missing
    for path in sorted(base.glob("*.json")):
        if path.name.endswith(".reach.json"):
            continue  # impressions and click rate: another file, another question
        report = read_channel(path)
        if report is None:
            missing.append(path.stem)
            continue
        found[report["channel"]] = report
    return found, missing


# --------------------------------------------------------------------------- #
# The shared window: the days every channel can be compared on
# --------------------------------------------------------------------------- #
def shared_days(channels: dict[str, dict], limit: int = 28) -> list[str]:
    """The most recent days *every* channel reports, newest last.

    Comparing channels over different days is how a share is made to say the
    wrong thing: a channel whose file is a week stale would look tiny beside one
    that was read this morning.
    """
    if not channels:
        return []
    common: set[str] | None = None
    for report in channels.values():
        days = set(report["days"])
        common = days if common is None else (common & days)
    ordered = sorted(common or ())
    return ordered[-limit:]


def network_sources(channels: dict[str, dict]) -> dict[str, dict]:
    """Hours and views by source, summed over every channel as each one stands."""
    total: dict[str, dict] = {}
    for report in channels.values():
        for key, row in report["sources"].items():
            slot = total.setdefault(key, {"hours": 0.0, "views": 0})
            slot["hours"] = round(slot["hours"] + row["hours"], 2)
            slot["views"] += row["views"]
    return {key: total[key] for key in sorted(total, key=lambda k: -total[k]["hours"])}


def shares(hours_by_key: dict[str, float], keys: Iterable[str]) -> dict[str, float]:
    """Each key's share of the total across ``keys``; ``{}`` when there is no total."""
    wanted = [key for key in keys if key in hours_by_key]
    total = round(sum(hours_by_key[key] for key in wanted), 2)
    if not wanted or total <= 0:
        return {}
    return {key: round(hours_by_key[key] / total, 4) for key in wanted}


# --------------------------------------------------------------------------- #
# Bumps: did an existing video start earning more through a door we control?
# --------------------------------------------------------------------------- #
def _usual(history: list[float]) -> float | None:
    """A video's usual day, from the days before the one being judged."""
    if len(history) < MIN_DAYS_FOR_USUAL:
        return None
    return statistics.median(history)


def daily_bumps(report: dict, *, source_key: str | None = None) -> list[dict]:
    """Days on which this channel's hours rose above the recent usual.

    ``source_key`` restricts the question to one traffic source (the file holds
    sources for the 28-day window only). Without it the bump is measured on the
    channel's own daily total, which is what a night tail or an end screen is
    meant to move.
    """
    days = sorted(report["days"])
    series = [(day, report["days"][day]["hours"]) for day in days]
    if source_key:
        series = [(day, report["sources"].get(source_key, {}).get("hours", 0.0)) for day in days]
    bumps: list[dict] = []
    for index, (day, hours) in enumerate(series):
        history = [value for _, value in series[max(0, index - 10):index]]
        usual = _usual(history)
        if usual is None or hours <= usual:
            continue
        bumps.append({"day": day, "hours": hours, "usual": round(usual, 2),
                      "rise": round(hours - usual, 2)})
    return bumps


def night_tail_reading(channels: dict[str, dict]) -> dict:
    """Whether a night-length video earns more than the same channel's usual day.

    This is a reading of watch hours on days, not a per-format comparison: the
    Analytics file does not say which video a day's hours came from. A channel
    whose videos are all short cannot pass a ``hold`` verdict by accident; a
    channel with one hour of history in total passes nothing, because
    ``MIN_HOURS_FOR_PACE`` keeps a noise-sized series from being judged.
    """
    rows = []
    eligible = 0
    for channel, report in sorted(channels.items()):
        hours = round(sum(row["hours"] for row in report["days"].values()), 2)
        row = {"channel": channel, "hours_read": hours, "days_read": len(report["days"]),
               "bump_share": None, "verdict": "not_enough_reading"}
        if hours >= MIN_HOURS_FOR_PACE and len(report["days"]) >= MIN_DAYS_FOR_PACE:
            eligible += 1
            bumps = daily_bumps(report)
            big = [b for b in bumps if b["rise"] >= round(hours / max(len(report["days"]), 1) * 0.5, 2)]
            row["bump_share"] = round(len(big) / len(report["days"]), 4)
            row["bumps"] = big[-BUMPS_READ:]
            row["verdict"] = "hold" if len(big) >= 3 and row["bump_share"] >= 0.15 else "flat"
        rows.append(row)
    verdict = "unknown"
    if eligible:
        holds = [row for row in rows if row["verdict"] == "hold"]
        if holds and len(holds) * 2 >= eligible:
            verdict = "hold"      # the format shows up as a step on most channels read
        elif not holds:
            verdict = "flat"      # nobody's day ever stepped up
        else:
            verdict = "mixed"
    return {
        "verdict": verdict,
        "keep": verdict != "flat",
        "channels_read": eligible,
        "note": ("a bump is a day whose hours rose above the channel's recent usual; "
                 "three or more such days in 15% of the days read is a hold"),
        "channels": rows,
    }


def end_screen_reading(channels: dict[str, dict]) -> dict:
    """The same question for the end-screen door: are hours arriving from it at all?"""
    rows = []
    for channel, report in sorted(channels.items()):
        row = {"channel": channel,
               "end_screen_hours": round(report["sources"].get("end_screen", {}).get("hours", 0.0), 2),
               "suggested_hours": round(report["sources"].get("suggested", {}).get("hours", 0.0), 2),
               "views": report["sources"].get("end_screen", {}).get("views", 0)}
        both = row["end_screen_hours"] + row["suggested_hours"]
        row["end_screen_share_of_tail"] = round(row["end_screen_hours"] / both, 4) if both else None
        rows.append(row)
    total = round(sum(row["end_screen_hours"] for row in rows), 2)
    return {
        "hours": total,
        "verdict": "used" if total > 0 else "unmeasured_or_unused",
        "note": ("end screens are only reported by Analytics when a viewer reaches one; "
                 "zero hours means nobody did, or the channel has not been read"),
        "channels": rows,
    }


# --------------------------------------------------------------------------- #
# The budget and the per-channel targets
# --------------------------------------------------------------------------- #
def counted_hours(by_source: dict[str, dict]) -> float:
    """Hours arriving through the doors a release can steer."""
    return round(sum(by_source.get(key, {}).get("hours", 0.0) for key in SHARE_MEDIA), 2)


@lru_cache(maxsize=1)
def short_video_ids() -> frozenset[str]:
    """Video ids of every published Short, so a looped Short is never read as a
    long-form's retention (a looping Short reports past 100% watched)."""
    from .script_doc import parse_script

    found: set[str] = set()
    directory = ROOT / "content" / "published"
    if not directory.is_dir():
        return frozenset()
    for path in directory.glob("short-*.md"):
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001 - one unreadable receipt is not a failure
            continue
        vid = str(doc.meta.get("youtube_video_id") or "").strip()
        if vid:
            found.add(vid)
    return frozenset(found)


#: The lengths worth comparing: what a release can be made in today. The night
#: tail already builds three hours from ten-minute units, and the runner's cap and
#: the upload both have to survive the length, so ten hours is not on this list
#: even though the model would happily ask for it.
LENGTH_BANDS = (
    ("up to 15 minutes", 0, 900),
    ("15 to 60 minutes", 900, 3600),
    ("1 to 2 hours", 3600, 7200),
    ("2 to 3 hours", 7200, 10800),
    ("over 3 hours", 10800, 10**9),
)
#: A band needs this many measured videos before its hours-per-view is trusted.
MIN_VIDEOS_FOR_BAND = 2


def video_lengths() -> dict[str, int]:
    """``video_id -> length in seconds``, from the receipt or, failing that, YouTube.

    A receipt written before this job measured lengths carries only
    ``target_minutes``: what the script was *planned* to be. Pricing a length on
    that is how a six-minute prayer reads as a three-hour one. Real seconds win,
    and ``content/analytics/<channel>.reach.json`` (built from the daily reach
    files) carries the upload's real length beside its impressions, so the
    recordings that never stamped one still get an honest figure.
    """
    from .script_doc import parse_script

    lengths: dict[str, int] = {}
    directory = ROOT / "content" / "published"
    if not directory.is_dir():
        return lengths
    for path in directory.glob("*.md"):
        if path.name.startswith("short-"):
            continue
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        vid = str(doc.meta.get("youtube_video_id") or "").strip()
        try:
            seconds = int(float(doc.meta.get("duration_seconds") or 0))
        except (TypeError, ValueError):
            seconds = 0
        if vid and seconds > 0:
            lengths[vid] = seconds
    for path in sorted((ROOT / "content" / "analytics").glob("*.reach.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            continue
        for row in payload.get("videos") or []:
            if not isinstance(row, dict):
                continue
            vid = str(row.get("video_id") or "").strip()
            if vid in lengths:
                continue  # the receipt's own recording is the same figure
            try:
                seconds = int(float(row.get("duration_seconds") or 0))
            except (TypeError, ValueError):
                seconds = 0
            if vid and seconds > 0:
                lengths[vid] = seconds
    return lengths


def length_payoff(channels: dict[str, dict]) -> dict:
    """Hours earned a view, by how long the video is: the one thing length proves.

    A long video is only worth making if a view of it returns more watch time than
    a view of a short one. Every published video with a receipt (its length) and a
    reading (its hours and views) is put in a length band, and each band's hours a
    view is compared. A band under ``MIN_VIDEOS_FOR_BAND`` videos is shown and not
    used: two videos can differ by more than their length.
    """
    lengths = video_lengths()
    bands: dict[str, dict] = {}
    unknown = 0
    for report in channels.values():
        for video in report["videos"]:
            seconds = lengths.get(video["video_id"])
            if not seconds:
                unknown += 1
                continue
            if video["views"] < 1:
                continue
            for label, low, high in LENGTH_BANDS:
                if low <= seconds < high:
                    slot = bands.setdefault(label, {"band": label, "videos": 0, "views": 0,
                                                    "hours": 0.0, "minutes": 0})
                    slot["videos"] += 1
                    slot["views"] += video["views"]
                    slot["hours"] = round(slot["hours"] + video["hours"], 2)
                    slot["minutes"] = int(round(seconds / 60))
                    break
    rows = []
    for label, _low, _high in LENGTH_BANDS:
        slot = bands.get(label)
        if not slot:
            continue
        hours_a_view = round(slot["hours"] / slot["views"], 4) if slot["views"] else 0.0
        rows.append(dict(slot, hours_a_view=hours_a_view,
                         measured=slot["videos"] >= MIN_VIDEOS_FOR_BAND))
    measured = [row for row in rows if row["measured"]]
    best = max(measured, key=lambda row: row["hours_a_view"]) if measured else None
    return {
        "bands": rows,
        "best_band": best["band"] if best else None,
        "best_hours_a_view": best["hours_a_view"] if best else None,
        "longest_measured_band": rows[-1]["band"] if rows else None,
        "videos_without_a_length": unknown,
        "note": ("hours a view, by the video's own length. Only videos whose real length is "
                 "known are compared, and a band needs two videos to count. A video whose "
                 "receipt carries only the planned length is counted above, not guessed at."),
    }


def budget_from_payoff(payoff: dict, need_a_day: float | None) -> dict:
    """The longest length a view has actually been seen to reward.

    The question a release length has to answer is not how long it can be made but
    how much watch time a view of it returns. So the budget is the length of the
    best-paying band measured so far - never a band with too few videos to count,
    never longer than the pipeline can build and upload. With nothing measured the
    slots-a-day default stands and says why.
    """
    bands = payoff.get("bands") or []
    measured = [row for row in bands if row.get("measured")]
    if not measured:
        return {"minutes": DEFAULT_BUDGET_MINUTES,
                "basis": ("no length has two measured videos yet; the slots a day, "
                          f"{payoff.get('videos_without_a_length', 0)} videos have no real length recorded"),
                "considered": bands}
    best = max(measured, key=lambda row: row["hours_a_view"])
    minutes = int(max(MIN_BUDGET_MINUTES, min(MAX_BUDGET_MINUTES, best["minutes"])))
    return {
        "minutes": minutes,
        "basis": (f"a view of a video {best['band']} returned {best['hours_a_view']} hours, "
                  f"the most of any length measured ({best['videos']} videos); "
                  f"the threshold asks {need_a_day} hours a day"),
        "considered": bands,
    }


def watch_ceiling(channels: dict[str, dict], current_seconds: int | None = None) -> dict:
    """How long a release should be, from where viewers actually leave.

    ``pipeline/viewer_length.py`` holds the argument and the arithmetic; this only
    feeds it the two things it needs: every video that has both a real length and a
    reading, and the length the channel publishes today.
    """
    from . import viewer_length

    lengths = video_lengths()
    rows: list[dict] = []
    for report in channels.values():
        rows.extend(viewer_length.measured_views(report["videos"], lengths))
    reading = viewer_length.read(rows)
    current = current_seconds
    if current is None:
        current = DEFAULT_BUDGET_MINUTES * 60
    verdict = viewer_length.ceiling_seconds(reading, current_seconds=current)
    verdict["wasted_share"] = viewer_length.wasted_share(reading, current)
    verdict["tail_is_the_problem"] = viewer_length.tail_is_the_problem(reading, current)
    return verdict


def channel_readings(channels: dict[str, dict], days: list[str]) -> list[dict]:
    """What each channel's own figures say, over the shared window.

    ``hours_a_day`` and ``views_a_day`` are the channel's real output. ``held`` is
    the median share of a video a viewer watched (from the 365-day video table):
    it is the one number here that says whether a longer release is watched or
    abandoned. ``hours_a_minute_watched`` is the figure the budget is priced
    against: minutes watched per view divided by the release's own length.
    """
    rows = []
    for channel, report in channels.items():
        kept = [day for day in days if day in report["days"]]
        hours = round(sum(report["days"][day]["hours"] for day in kept), 2)
        views = sum(report["days"][day]["views"] for day in kept)
        shorts = short_video_ids()
        videos = [v for v in report["videos"]
                  if v["average_view_percent"] > 0 and v["video_id"] not in shorts]
        held = round(statistics.median(v["average_view_percent"] for v in videos), 1) if videos else None
        per_day = max(len(kept), 1)
        share = report.get("long_form_view_share")
        rows.append({
            "channel": channel,
            "hours": hours,
            "views": views,
            "days": len(kept),
            "hours_a_day": round(hours / per_day, 2),
            "views_a_day": round(views / per_day, 1),
            # A Short view and a prayer view are not the same unit of attention.
            "long_form_view_share": share,
            "long_form_views_a_day": (round(views / per_day * float(share), 2)
                                      if share is not None else None),
            "held_percent": held,
            "videos_read": len(videos),
        })
    return rows


def allocate(rows: list[dict], budget_minutes: int) -> list[dict]:
    """Each channel's share of the cost of making the budget, and what it owes.

    A channel's target is its share of the network's hours *after* the budget has
    been held: the biggest channel carries the most, and a channel that is barely
    read carries almost none. The division is over the hours, not the minutes, so
    it does not reward publishing more videos for the same hours.
    """
    total = round(sum(row["hours"] for row in rows), 2)
    out = []
    for row in sorted(rows, key=lambda item: -item["hours"]):
        share = round(row["hours"] / total, 4) if total > 0 else 0.0
        held = row["held_percent"]
        out.append(dict(row, share_of_network_hours=share,
                        target_minutes=int(round(share * budget_minutes)),
                        longer_is_watched=bool(held is not None and held >= 25)))
    return out


def watchers_needed(hours_a_day: float, budget_minutes: int, held_percent: float | None = None) -> float | None:
    """How many viewers a day would have to play one release to make this pace.

    One viewer is worth the share of the release they actually watch, not its
    whole length: a three-hour video nobody stays past two minutes is two
    minutes of watch time, not three hours.
    """
    if budget_minutes <= 0:
        return None
    held = max(min(float(held_percent or 12.0), 100.0), 1.0) / 100.0
    per_view = budget_minutes * held / 60.0
    if per_view <= 0:
        return None
    return round(max(hours_a_day, 0.0) / per_view, 1)


def pace(channels: dict[str, dict], days: list[str]) -> dict:
    """Hours a day over the shared window, and the last seven days of it."""
    per_day = []
    for day in days:
        per_day.append(round(sum(report["days"].get(day, {}).get("hours", 0.0)
                                 for report in channels.values()), 2))
    last_seven = per_day[-7:] if len(per_day) >= 7 else per_day
    return {
        "days": len(days),
        "hours_a_day": round(sum(per_day) / len(per_day), 2) if per_day else 0.0,
        "hours_a_day_last_7": round(sum(last_seven) / len(last_seven), 2) if last_seven else 0.0,
        "by_day": [{"day": day, "hours": hours} for day, hours in zip(days, per_day)],
    }


def need_reading(channels: dict[str, dict], today: date | None = None,
                 network_hours_a_day: float = 0.0) -> dict:
    """What the threshold asks, against what the channels do now."""
    today = today or datetime.now(timezone.utc).date()
    needed = 8000 if today >= date(2027, 2, 1) else 4000
    counted = round(sum(report.get("watch_hours_365d", 0.0) for report in channels.values()), 2)
    remaining = round(max(needed - counted, 0.0), 2)
    days_left = max((date(2027, 1, 31) - today).days, 0)
    needed_a_day = round(remaining / days_left, 2) if days_left else None
    return {
        "threshold_hours": needed,
        "counted_hours_365d": counted,
        "remaining_hours": remaining,
        "days_until_the_threshold_doubles": days_left,
        "hours_a_day_needed": needed_a_day,
        "hours_a_day_now": network_hours_a_day,
        "times_the_pace_must_rise": (round(needed_a_day / network_hours_a_day, 1)
                                     if needed_a_day and network_hours_a_day > 0 else None),
        "note": ("counted hours are long-form and live only; Shorts-feed hours do not count. "
                 "Only channels with the Analytics grant are in this figure."),
    }


def load_source_reading(path: Path | None = None) -> dict:
    """``scripts/growth_ab.py``'s verdict on the format changes, or a null reading."""
    target = Path(path) if path else SOURCES_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        data = {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
# The report
# --------------------------------------------------------------------------- #
def build_report(channels: dict[str, dict] | None = None, *, today: date | None = None,
                 sources_reading: dict | None = None, budget_minutes: int | None = None,
                 missing: list[str] | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    channels = channels if channels is not None else {}
    days = shared_days(channels)
    by_source = network_sources(channels)
    source_hours = {key: row["hours"] for key, row in by_source.items()}
    ordered = {key: source_hours[key] for key in SOURCE_KEYS if key in source_hours}
    for key in source_hours:  # anything the reader named that this list has not met
        ordered.setdefault(key, source_hours[key])
    source_shares = shares(ordered, list(ordered))

    rows = channel_readings(channels, days)
    hours_a_day = pace(channels, days)["hours_a_day"]
    need = need_reading(channels, today, hours_a_day)

    payoff = length_payoff(channels)
    ceiling = watch_ceiling(channels)
    if budget_minutes is not None:
        budget = {"minutes": int(budget_minutes), "basis": "given", "considered": payoff["bands"]}
    else:
        # Where viewers leave is the last word on length: a band's hours a view
        # cannot argue for a video longer than the median viewer stays for.
        budget = {
            "minutes": max(MIN_BUDGET_MINUTES, int(round(ceiling["minutes"]))),
            "basis": ceiling["basis"],
            "considered": payoff["bands"],
            "ceiling": ceiling,
        }
    minutes = int(budget.get("minutes") or DEFAULT_BUDGET_MINUTES)
    targets = allocate(rows, minutes)

    held = [row["held_percent"] for row in targets if row["held_percent"] is not None]
    tail = night_tail_reading(channels)
    ends = end_screen_reading(channels)

    sources_reading = sources_reading if sources_reading is not None else load_source_reading()
    reading = sources_reading.get("readings") or {}
    tail_reading = reading.get("night_tail") or {}
    if tail_reading.get("verdict") in {"hold", "flat"}:
        # A measured week beats a bump count: it compares the same channels
        # before and after, which the day series alone cannot do.
        tail = dict(tail, verdict=tail_reading["verdict"], keep=tail_reading["verdict"] != "flat",
                    measured=tail_reading)

    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": today.isoformat(),
        "window": {"first_day": days[0] if days else "", "last_day": days[-1] if days else "",
                   "days": len(days)},
        "channels_read": sorted(channels),
        "channels_not_read": sorted(missing or []),
        "network": {
            "hours_by_source": ordered,
            "share_by_source": source_shares,
            "counted_hours": counted_hours(by_source),
            "counted_share": round(
                counted_hours(by_source) / sum(ordered.values()), 4) if sum(ordered.values()) else 0.0,
            "pace": pace(channels, days),
            "need": need,
            "held_percent_median": round(statistics.median(held), 1) if held else None,
        },
        "targets": targets,
        "budget": budget,
        "length_payoff": payoff,
        "watch_ceiling": ceiling,
        "hints": {
            "night_tail": tail,
            "end_screen": ends,
            "related_video": reading.get("related_video") or {
                "verdict": "not_measured",
                "note": "a Related video needs advanced access and an edit in Studio; "
                        "scripts/growth_ab.py reads the hours before and after one is added",
            },
        },
        "watchers_needed_a_day": watchers_needed(
            hours_a_day, int(budget.get("minutes") or 0),
            None if not held else statistics.median(held)),
        "cost_lock": "$0.00 — reads committed Analytics files; no API call, no new secret.",
        "privacy": "Hours, views, minutes and shares only. No revenue, no viewer, no other channel's title.",
    }


def write_report(report: dict, path: Path | None = None) -> Path:
    target = Path(path) if path else REPORT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return target


def load_report(path: Path | None = None) -> dict:
    """The committed report, or ``{}`` when there is none (a channel release still runs)."""
    try:
        data = json.loads((Path(path) if path else REPORT_PATH).read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def budget_minutes_from_report(report: dict | None, default: int = DEFAULT_BUDGET_MINUTES) -> int:
    """The minutes a release should hold, clamped, from a report that may be absent."""
    try:
        minutes = int((report or {}).get("budget", {}).get("minutes") or default)
    except (TypeError, ValueError):
        minutes = default
    return int(max(MIN_BUDGET_MINUTES, min(MAX_BUDGET_MINUTES, minutes)))


def keep_night_tail(report: dict | None, default: bool = True) -> bool:
    """Whether the night tail still earns its keep; unmeasured keeps it."""
    hint = ((report or {}).get("hints") or {}).get("night_tail") or {}
    if hint.get("verdict") not in {"hold", "flat", "mixed"}:
        return default
    return bool(hint.get("keep", default))


def headline(report: dict) -> list[str]:
    """The report as a handful of lines a person can read in the run summary."""
    network = report.get("network") or {}
    need = network.get("need") or {}
    lines = [
        f"Hours by door: counted {network.get('counted_hours', 0)} hours "
        f"({network.get('counted_share', 0):.0%} of all watch hours read).",
    ]
    for key, hours in (network.get("hours_by_source") or {}).items():
        lines.append(f"  {key}: {hours} hours")
    pace_now = (network.get("pace") or {}).get("hours_a_day", 0)
    lines.append(f"Pace: {pace_now} hours a day; the threshold asks "
                 f"{need.get('hours_a_day_needed')} a day for the {need.get('days_until_the_threshold_doubles')} "
                 f"days left before it doubles.")
    budget = report.get("budget") or {}
    lines.append(f"Release budget: {budget.get('minutes')} minutes ({budget.get('basis')}).")
    tail = (report.get("hints") or {}).get("night_tail") or {}
    lines.append(f"Night tail: {tail.get('verdict')} — keep: {tail.get('keep')}.")
    for row in report.get("targets") or []:
        lines.append(f"  {row['channel']}: target {row['target_minutes']} minutes "
                     f"from {row['share_of_network_hours']:.0%} of counted hours.")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Where each channel's counted watch hours come from")
    parser.add_argument("--analytics-dir", default="", help="Directory of channel Analytics files")
    parser.add_argument("--out", default="", help="Where to write the report")
    parser.add_argument("--dry-run", action="store_true", help="Print, write nothing")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    parser.add_argument("--budget", type=int, default=None,
                        help="Force the release budget in minutes instead of deriving it")
    parser.add_argument("--summary-only", action="store_true",
                        help="Read the committed report and print it as lines; write nothing")
    args = parser.parse_args(argv)

    if args.summary_only:
        report = load_report(Path(args.out) if args.out else None)
        if not report:
            print("no report yet")
            return 0
        for line in headline(report):
            print(line)
        return 0

    channels, missing = load_channels(Path(args.analytics_dir) if args.analytics_dir else None)
    report = build_report(channels, missing=missing, budget_minutes=args.budget)
    if args.json or args.dry_run:
        print(json.dumps(report, indent=2))
    else:
        for line in headline(report):
            print(line)
    if args.dry_run:
        print("[dry-run] report not written")
        return 0
    path = write_report(report, Path(args.out) if args.out else None)
    if not args.json:
        print(f"[+] Growth score written: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
