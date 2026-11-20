#!/usr/bin/env python3
"""Format and display YouTube Analytics and channel metrics.

Reads either:
1. Private Analytics report: output/private-analytics/report.json
2. Public metrics snapshot: content/metrics.csv & content/channel-metrics.json

Run:
    python scripts/view_analytics.py                  # auto-detect and display available data
    python scripts/view_analytics.py --private        # display private Analytics report only
    python scripts/view_analytics.py --public         # display public metrics snapshot only
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import csv
import json
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_REPORT = ROOT / "output" / "private-analytics" / "report.json"
PUBLIC_CSV = ROOT / "content" / "metrics.csv"
PUBLIC_CHANNEL_JSON = ROOT / "content" / "channel-metrics.json"


def format_table(headers: list[str], rows: list[list[str]], max_col_width: int = 40) -> str:
    """Format an aligned ASCII table."""
    if not headers or not rows:
        return "(no rows to display)\n"

    widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            str_val = str(val)[:max_col_width]
            if idx < len(widths):
                widths[idx] = max(widths[idx], len(str_val))
            else:
                widths.append(len(str_val))

    line_sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header_row = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"

    lines = [line_sep, header_row, line_sep]
    for row in rows:
        row_cells = []
        for i in range(len(widths)):
            cell = str(row[i])[:max_col_width] if i < len(row) else ""
            row_cells.append(cell.ljust(widths[i]))
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append(line_sep)
    return "\n".join(lines) + "\n"


ENGAGEMENT = (
    ("Views", "views"), ("Subscribers gained", "subscribersGained"),
    ("Subscribers lost", "subscribersLost"), ("Net subscribers", None),
    ("Comments", "comments"), ("Likes", "likes"), ("Shares", "shares"),
)


def engagement_comparison(columns, rows):
    """Compare the latest 14 returned calendar days; never fill gaps with zero."""
    if "day" not in columns:
        return None
    by_day = {}
    for row in rows:
        if len(row) != len(columns):
            return None
        record = dict(zip(columns, row))
        try:
            day = date.fromisoformat(record["day"])
        except (ValueError, TypeError):
            return None
        if day in by_day:
            return None
        by_day[day] = record
    if len(by_day) < 14:
        return None
    end = max(by_day)
    days = [end - timedelta(days=i) for i in range(13, -1, -1)]
    if any(day not in by_day for day in days):
        return None

    def totals(window):
        data = {}
        for _, key in ENGAGEMENT:
            if key is not None:
                values = [by_day[day].get(key) for day in window]
                data[key] = sum(values) if all(type(v) is int and v >= 0 for v in values) else None
        gained, lost = data["subscribersGained"], data["subscribersLost"]
        data[None] = gained - lost if gained is not None and lost is not None else None
        return data

    prior, latest = totals(days[:7]), totals(days[7:])
    table = []
    for label, key in ENGAGEMENT:
        a, b = prior[key], latest[key]
        table.append([label, "—" if a is None else str(a), "—" if b is None else str(b),
                      "—" if a is None or b is None else f"{b - a:+d}"])
    return days, table


def retention_landmarks(columns, rows):
    """Show reported playback ratios at fixed points, without interpolation."""
    required = ("elapsedVideoTimeRatio", "audienceWatchRatio")
    if not all(key in columns for key in required):
        return []
    position, audience = (columns.index(key) for key in required)
    points = {}
    for row in rows:
        if len(row) != len(columns):
            continue
        x, y = row[position], row[audience]
        if type(x) not in (int, float) or not 0 < x <= 1:
            continue
        value = (f"{y:.1%}" if type(y) in (int, float) and math.isfinite(y) and y >= 0
                 else "—")
        points[x] = "—" if x in points else value
    return [[f"{x:.0%}", points.get(x, "—")] for x in (0.01, 0.25, 0.5, 0.75, 0.95, 1)]


def display_private_report(path: Path = PRIVATE_REPORT) -> bool:
    """Read and format the private Analytics report JSON."""
    if not path.is_file():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error parsing private report at {path}: {exc}", file=sys.stderr)
        return False

    print("\n" + "=" * 70)
    print("PRIVATE YOUTUBE ANALYTICS REPORT")
    print(f"Window: {data.get('start_date')} to {data.get('end_date')}")
    print(f"Collected at: {data.get('collected_at')}")
    print("=" * 70)

    reports = data.get("reports", {})

    # 1. Daily Performance
    daily = reports.get("daily", {})
    if daily.get("status") == "collected" and daily.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(daily.get("columns", []))]
        print("\n[Daily Performance (Recent 10 days)]")
        rows = daily["rows"][-10:]
        print(format_table(cols, rows))
    else:
        print(f"\n[Daily Performance]: {daily.get('status', 'not_collected')} ({daily.get('reason', '')})")

    print("\n[Audience Growth: Week over Week]")
    comparison = (engagement_comparison(cols, daily["rows"])
                  if daily.get("status") == "collected" and daily.get("rows") else None)
    if comparison is None:
        print("Not enough data: need 14 consecutive, unique reported days.")
    else:
        days, table = comparison
        print(f"Previous: {days[0]} to {days[6]} | Latest: {days[7]} to {days[-1]}")
        print(format_table(["Metric", "Previous", "Latest", "Change"], table))
        print("— means unavailable, not zero. These totals mix video formats; changes do not prove cause.")

    # 2. Top Videos
    videos = reports.get("videos", {})
    if videos.get("status") == "collected" and videos.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(videos.get("columns", []))]
        print("\n[Video Performance Breakdown]")
        print(format_table(cols, videos["rows"][:10]))
    else:
        print(f"\n[Video Performance]: {videos.get('status', 'not_collected')}")

    # 3. Traffic Sources
    traffic = reports.get("traffic_sources", {})
    if traffic.get("status") == "collected" and traffic.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(traffic.get("columns", []))]
        print("\n[Traffic Sources]")
        print(format_table(cols, traffic["rows"]))

    # 4. Countries / Geographies
    countries = reports.get("countries", {})
    if countries.get("status") == "collected" and countries.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(countries.get("columns", []))]
        print("\n[Top Countries / Audience Geographies]")
        print(format_table(cols, countries["rows"][:10]))

    # 5. Devices
    devices = reports.get("devices", {})
    if devices.get("status") == "collected" and devices.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(devices.get("columns", []))]
        print("\n[Device Distribution]")
        print(format_table(cols, devices["rows"]))

    # 6. Retention (if requested)
    retention = reports.get("retention", {})
    if retention.get("status") == "collected" and retention.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(retention.get("columns", []))]
        print("\n[Audience Retention Profile]")
        print(f"Video: {retention.get('video_id') or 'unknown (older report)'}")
        landmarks = retention_landmarks(cols, retention["rows"])
        if landmarks:
            print(format_table(["Video position", "Audience watch ratio"], landmarks))
            print("— means unavailable. Replays can push the ratio over 100%; "
                  "it is not the percentage of unique viewers who finished.")
        else:
            print(format_table(cols, retention["rows"][:15]))
    elif retention.get("status") != "not_requested":
        print(f"\n[Audience Retention]: {retention.get('status')} ({retention.get('reason', '')})")

    # 7. Revenue (if requested)
    revenue = reports.get("revenue", {})
    if revenue.get("status") == "collected" and revenue.get("rows"):
        cols = [c.get("name", f"col_{i}") if isinstance(c, dict) else str(c) for i, c in enumerate(revenue.get("columns", []))]
        print("\n[Estimated Revenue Report]")
        print(format_table(cols, revenue["rows"]))
    elif revenue.get("status") != "not_requested":
        print(f"\n[Estimated Revenue]: {revenue.get('status')} ({revenue.get('reason', '')})")

    return True


def display_public_snapshot(csv_path: Path = PUBLIC_CSV, json_path: Path = PUBLIC_CHANNEL_JSON) -> bool:
    """Read and format public channel & video metrics snapshot."""
    found = False
    if json_path.is_file():
        found = True
        try:
            ch_data = json.loads(json_path.read_text(encoding="utf-8"))
            print("\n" + "=" * 70)
            print("PUBLIC CHANNEL METRICS SNAPSHOT")
            print(f"Snapshot Date: {ch_data.get('snapshot_date')}")
            print(f"Channel ID: {ch_data.get('channel_id')}")
            sub_count = ch_data.get("subscriber_count")
            if sub_count is not None:
                print(f"Subscribers: {sub_count:,} (rounded to 3 significant figures)")
            else:
                print("Subscribers: Hidden or unavailable")
            print("=" * 70)
        except Exception as exc:
            print(f"Error reading channel metrics JSON: {exc}", file=sys.stderr)

    if csv_path.is_file():
        found = True
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
            if reader:
                headers = ["date", "video_id", "title", "published", "views", "likes", "comments"]
                rows = []
                for r in reader[-15:]:
                    rows.append([
                        r.get("snapshot_date", ""),
                        r.get("video_id", ""),
                        r.get("title", "")[:35],
                        r.get("published_at", ""),
                        r.get("views", "0"),
                        r.get("likes", "0"),
                        r.get("comments", "0"),
                    ])
                print("\n[Recent Public Video Performance (Last 15 Snapshot Rows)]")
                print(format_table(headers, rows))
            else:
                print("\n[Public Video Metrics]: content/metrics.csv is empty.")
        except Exception as exc:
            print(f"Error reading metrics CSV: {exc}", file=sys.stderr)

    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--private", action="store_true", help="Display private Analytics report only")
    ap.add_argument("--public", action="store_true", help="Display public metrics snapshot only")
    ap.add_argument("--retention-video", help="Display a saved private report for a video ID")
    args = ap.parse_args()
    if args.retention_video is not None:
        if args.public or not re.fullmatch(r"[A-Za-z0-9_-]{11}", args.retention_video):
            ap.error("--retention-video needs an 11-character video ID and cannot be used with --public.")
        path = PRIVATE_REPORT.with_name(f"retention-{args.retention_video}.json")
        if not display_private_report(path):
            print("No readable saved report. Collect retention for this video first.", file=sys.stderr)
            return 1
        return 0

    displayed_any = False

    if not args.public:
        has_private = display_private_report()
        displayed_any = displayed_any or has_private

    if not args.private:
        has_public = display_public_snapshot()
        displayed_any = displayed_any or has_public

    if not displayed_any:
        print("\n" + "=" * 70)
        print("NO LOCAL ANALYTICS DATA FOUND")
        print("=" * 70)
        print("To collect channel analytics:")
        print("1. PUBLIC METRICS:")
        print("   Run locally: python scripts/metrics_snapshot.py")
        print("   Or trigger in GitHub Actions: Actions -> 'Weekly metrics snapshot' -> 'Run workflow'")
        print("\n2. PRIVATE YOUTUBE ANALYTICS API:")
        print("   Run: python scripts/channel_analytics.py --start YYYY-MM-DD --end YYYY-MM-DD")
        print("   (Requires ANALYTICS_CLIENT_ID, ANALYTICS_CLIENT_SECRET, ANALYTICS_REFRESH_TOKEN)")
        print("\n3. LIVE YOUTUBE STUDIO DASHBOARD:")
        print("   Direct web link: https://studio.youtube.com/channel/UC.../analytics")
        print("   Video 7RDX0fbIOtQ: https://studio.youtube.com/video/7RDX0fbIOtQ/analytics")
        print("=" * 70 + "\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
