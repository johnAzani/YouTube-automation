#!/usr/bin/env python3
"""Compute the closed-loop performance feedback artifact ($0.00 lock).

Reads the public-video metrics snapshot (content/metrics.csv, produced by
scripts/metrics_snapshot.py) plus the published receipts, scores each long-form
video by reach + engagement, aggregates by theme, and writes the public-safe
content/research/performance_feedback.json that the brain reads to favour the
themes that are actually winning.

Usage:
    python scripts/performance_feedback.py                 # compute + write artifact
    python scripts/performance_feedback.py --dry-run       # print report, write nothing
    python scripts/performance_feedback.py --json          # print raw JSON only

Fail-soft: with no snapshot or too little data it writes a neutral
"insufficient_data" report and exits 0 — it never blocks the pipeline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.channel_capabilities import brand_for  # noqa: E402
from pipeline.channels import add_channel_arg, normalize_channel_id  # noqa: E402
from pipeline.performance_feedback import (  # noqa: E402
    build_feedback_report,
    write_feedback_report,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Closed-loop performance feedback ($0.00 lock)")
    add_channel_arg(ap)
    ap.add_argument("--dry-run", action="store_true", help="Print the report without writing the artifact")
    ap.add_argument("--json", action="store_true", help="Print raw JSON only")
    args = ap.parse_args(argv)

    channel_id = normalize_channel_id(args.channel) if args.channel else None
    brand_title = brand_for(channel_id).display_name.upper() if channel_id else "THE SECRET PLACE"
    report = build_feedback_report(channel_id=channel_id)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("=" * 72)
    print(f"{brand_title} — CLOSED-LOOP PERFORMANCE FEEDBACK ($0.00 LOCK)")
    print("=" * 72)
    print(f"Measured long-form videos: {report['measured_longform_videos']} "
          f"of {report['total_longform_videos']}")
    print(f"Sufficient data to steer: {report['sufficient_data']}")
    shorts = report.get("shorts") or {}
    print(f"Shorts measured: {shorts.get('measured_shorts', 0)} of {shorts.get('total_shorts', 0)} "
          f"(average {shorts.get('avg_views', 0)} views); "
          f"enough to order the Shorts list: {shorts.get('sufficient_data', False)}")
    diag = report['input_diagnostics']
    print(f"Snapshot IDs: {diag['snapshot_video_ids']}; receipt IDs: {diag['receipt_video_ids']}; "
          f"matched IDs: {diag['matched_video_ids']}")
    print(f"Long-form below {diag['minimum_views']} views: {diag['longform_below_view_threshold']}; "
          f"missing view count: {diag['longform_missing_view_count']}; "
          f"too young/undated (<{diag['minimum_age_days']} days): {diag['longform_too_young_or_undated']}")
    if report["ranked_themes"]:
        print(f"Ranked themes: {' > '.join(report['ranked_themes'])}")
    for line in report["guidance"]:
        print(f"  • {line}")

    if args.dry_run:
        print("[dry-run] artifact not written")
        return 0

    path = write_feedback_report(report, channel_id=channel_id)
    print(f"[+] Feedback artifact written: {path.relative_to(ROOT)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
