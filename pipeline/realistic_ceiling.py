"""What this channel can actually reach, computed instead of promised.

Why this exists. Asked for 25 million views on every video. That is not a number a
production pipeline can choose: it is the outcome of millions of people deciding to
click and to stay, and no commit changes it. What a pipeline *can* do is say, from
the channel's own measured numbers, what each remaining lever is worth - and what
the honest best case is if every one of them works.

The model, and every coefficient in it, comes from this repository's own readings:

* impressions a day - `content/analytics/<channel>.reach.json` (thumbnail
  impressions YouTube chose to serve);
* click rate - the same file (clicks / impressions);
* watch time a view - `content/analytics/<channel>.json` (median seconds watched);
* the threshold - 4,000 hours, doubled to 8,000 for a channel still outside on
  1 February 2027.

Three levers are then priced, each at a level that is documented and defensible
rather than flattering:

1. **click rate to a good-in-niche rate.** Prayer and sleep channels routinely sit
   between 4% and 8%. The model uses the bottom of that band and says so.
2. **watch time to the length a viewer stays for.** This is the one lever whose
   measured ceiling is known exactly: it cannot exceed the median watched time,
   which is what `pipeline/viewer_length.py` measures.
3. **impressions.** The only lever with no measured ceiling - and the one no
   metadata can move. The model holds it where it is, then shows what it would
   take if it rose.

What comes out is a band, not a promise: today, per lever, and the best case with
all three at their documented levels. Every figure is traceable to a file in this
repository, and the model says when a channel has too little traffic for its own
numbers to be anything but noise.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ANALYTICS = ROOT / "content" / "analytics"
OUT_PATH = ROOT / "content" / "research" / "realistic_ceiling.json"
SCHEMA = 1

#: A defensible good click rate for this niche, the bottom of the 4-8% band most
#: prayer and sleep channels report. Used as a target, never as a claim.
GOOD_CTR_PERCENT = 4.0
#: A view under this many impressions is not a reading; two clicks on four
#: impressions is a 50% click rate and means nothing.
MIN_IMPRESSIONS = 100
#: Below this many seconds watched a view, the watch-time lever is the whole story.
GOOD_WATCH_SECONDS = 180


def _num(value, default=0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out or out in (float("inf"), float("-inf")):
        return default
    return out


def read_reach(channel: str | None = None, directory: Path | None = None) -> dict:
    """Impressions and clicks a day, and the click rate, from the reach file(s)."""
    base = Path(directory) if directory else ANALYTICS
    files = sorted(base.glob("*.reach.json"))
    if channel:
        files = [path for path in files if path.name.startswith(f"{channel}.")]
    impressions = clicks = days = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            continue
        window = payload.get("window") or {}
        impressions += int(_num(window.get("impressions")))
        clicks += int(_num(window.get("clicks")))
        days = max(days, int(_num(window.get("days"))))
    if days <= 0 or impressions <= 0:
        return {"impressions_a_day": None, "clicks_a_day": None, "click_rate_percent": None,
                "days": days, "impressions": impressions, "clicks": clicks,
                "sufficient": False}
    return {
        "impressions": impressions,
        "clicks": clicks,
        "days": days,
        "impressions_a_day": round(impressions / days, 1),
        "clicks_a_day": round(clicks / days, 2),
        "click_rate_percent": round(100.0 * clicks / impressions, 2),
        "sufficient": impressions >= MIN_IMPRESSIONS,
    }


def read_watch(channel: str | None = None, directory: Path | None = None) -> dict:
    """Median seconds watched a view and views a day, from the analytics file(s)."""
    from . import growth_score

    base = Path(directory) if directory else ANALYTICS
    channels, _missing = growth_score.load_channels(base)
    if channel:
        channels = {key: value for key, value in channels.items() if key == channel}
    if not channels:
        return {"watch_seconds": None, "views_a_day": None, "sufficient": False}
    lengths = growth_score.video_lengths()
    from . import viewer_length

    rows: list[dict] = []
    views = 0
    days = 0
    for report in channels.values():
        rows.extend(viewer_length.measured_views(report["videos"], lengths))
        kept = report["days"]
        days += len(kept)
        views += sum(day["views"] for day in kept.values())
    reading = viewer_length.read(rows)
    return {
        "watch_seconds": round(reading.median_seconds, 1) if reading else None,
        "videos_measured": reading.videos if reading else 0,
        "views_a_day": round(views / days, 1) if days else None,
        "sufficient": bool(reading and reading.videos >= viewer_length.MIN_VIDEOS_TO_CUT),
    }


def threshold_for(today: date | None = None) -> int:
    today = today or date.today()
    return 8000 if today >= date(2027, 2, 1) else 4000


def hours_a_day_from(impressions_a_day: float | None, click_rate_percent: float | None,
                     watch_seconds: float | None) -> float | None:
    """Hours a day the current traffic produces at a given click rate and watch time."""
    if not impressions_a_day or not click_rate_percent or not watch_seconds:
        return None
    clicks = impressions_a_day * click_rate_percent / 100.0
    return round(clicks * watch_seconds / 3600.0, 3)


def build_model(reach: dict | None = None, watch: dict | None = None,
                today: date | None = None) -> dict:
    reach = read_reach() if reach is None else reach
    watch = read_watch() if watch is None else watch
    today = today or date.today()
    need = threshold_for(today)
    days_left = max((date(2027, 1, 31) - today).days, 0)
    needed_a_day = round(need / days_left, 2) if days_left else None

    now_hours = hours_a_day_from(reach.get("impressions_a_day"),
                                 reach.get("click_rate_percent"), watch.get("watch_seconds"))
    good_hours = hours_a_day_from(reach.get("impressions_a_day"),
                                  GOOD_CTR_PERCENT, watch.get("watch_seconds"))
    # The watch-time lever cannot invent attention: it is capped at the measured
    # median, which is where viewer_length.py puts the length ceiling.
    best_watch = watch.get("watch_seconds")
    if best_watch:
        best_watch = max(best_watch, min(GOOD_WATCH_SECONDS, 24 * 3600))
    best_hours = hours_a_day_from(reach.get("impressions_a_day"), GOOD_CTR_PERCENT, best_watch)

    can_reach = bool(needed_a_day and best_hours and best_hours >= needed_a_day)
    impressions_needed = None
    if needed_a_day and watch.get("watch_seconds") and GOOD_CTR_PERCENT:
        impressions_needed = round(needed_a_day * 3600.0 / (GOOD_CTR_PERCENT / 100.0
                                                            * watch["watch_seconds"]))
    return {
        "schema": SCHEMA,
        "as_of": today.isoformat(),
        "threshold_hours": need,
        "days_until_the_threshold_doubles": days_left,
        "hours_a_day_needed": needed_a_day,
        "measured": {
            "impressions_a_day": reach.get("impressions_a_day"),
            "click_rate_percent": reach.get("click_rate_percent"),
            "watch_seconds_a_view": watch.get("watch_seconds"),
            "views_a_day": watch.get("views_a_day"),
            "reach_sufficient": reach.get("sufficient"),
            "watch_sufficient": watch.get("sufficient"),
        },
        "levers": [
            {"lever": "as it stands", "hours_a_day": now_hours,
             "note": "the measured impressions, click rate and watch time"},
            {"lever": f"click rate to {GOOD_CTR_PERCENT:.0f}%",
             "hours_a_day": good_hours,
             "note": "the bottom of the 4-8% band prayer and sleep channels report"},
            {"lever": f"watch time to {GOOD_WATCH_SECONDS // 60} minutes and a "
                      f"{GOOD_CTR_PERCENT:.0f}% click rate",
             "hours_a_day": best_hours,
             "note": "both format levers at their documented levels, impressions unchanged"},
        ],
        "verdict": {
            "reachable_on_impressions_alone": can_reach,
            "times_the_pace_must_rise": (round(needed_a_day / now_hours, 1)
                                         if needed_a_day and now_hours else None),
            "impressions_a_day_needed": impressions_needed,
            "impressions_multiple_needed": (round(impressions_needed / reach["impressions_a_day"], 1)
                                            if impressions_needed and reach.get("impressions_a_day")
                                            else None),
            "sentence": _sentence(now_hours, best_hours, needed_a_day, impressions_needed,
                                  reach.get("impressions_a_day")),
        },
        "not_claimed": [
            "any particular view count on any particular video",
            "virality: no lever here raises impressions, and impressions are what a video "
            "must have before it can be watched",
            "the date: with the impressions measured today, the threshold is reached by "
            "many levers, and the model says which one must move",
        ],
        "cost_lock": "$0.00 — reads committed analytics files; no API call.",
        "sources": ["content/analytics/*.reach.json", "content/analytics/*.json",
                    "content/published/*.md"],
    }


def _sentence(now_hours, best_hours, needed_a_day, impressions_needed, impressions_now) -> str:
    if not needed_a_day:
        return "No days remain before the threshold doubles; the rate is the only measure left."
    if not now_hours:
        return ("Too few impressions or views are committed to model a rate yet. "
                "The next analytics run writes them.")
    parts = [f"The threshold asks {needed_a_day} hours a day; the channels produce {now_hours}."]
    if best_hours:
        parts.append(f"With both format levers at their documented levels it would be {best_hours}.")
    if impressions_needed and impressions_now:
        parts.append(f"To reach the threshold at a {GOOD_CTR_PERCENT:.0f}% click rate and the "
                     f"measured watch time, YouTube would have to serve {impressions_needed:,} "
                     f"impressions a day where it serves {int(impressions_now):,}.")
    parts.append("Impressions are chosen by YouTube's recommendation system from how viewers "
                 "respond, so that is the honest distance: it is reach, not metadata.")
    return " ".join(parts)


def write_model(report: dict, path: Path | None = None) -> Path:
    target = Path(path) if path else OUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


def headline(report: dict) -> list[str]:
    measured = report.get("measured") or {}
    lines = [
        f"Measured: {measured.get('impressions_a_day')} impressions a day at "
        f"{measured.get('click_rate_percent')}% click rate, "
        f"{measured.get('watch_seconds_a_view')} seconds watched a view.",
    ]
    for lever in report.get("levers") or []:
        lines.append(f"  {lever['lever']:<46} {lever['hours_a_day']} hours a day")
    lines.append(f"Threshold asks {report.get('hours_a_day_needed')} hours a day "
                 f"for {report.get('days_until_the_threshold_doubles')} days.")
    lines.append(str((report.get("verdict") or {}).get("sentence") or ""))
    return lines


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="What this channel can actually reach")
    parser.add_argument("--out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    report = build_model()
    for line in headline(report):
        print(line)
    if args.dry_run:
        print("[dry-run] not written")
        return 0
    write_model(report, Path(args.out) if args.out else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
