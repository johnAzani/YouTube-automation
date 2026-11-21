"""Compare public snapshot counts at the same release age, by channel and format."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from itertools import chain
from contextlib import ExitStack
from pathlib import Path
from statistics import median

from pipeline.channels import CHANNELS
from pipeline.performance_feedback import METRICS_CSV, load_published_index
from scripts.view_analytics import format_table

METRICS = ("views", "likes", "comments")


def observation_time(value, observed):
    """Accept only timestamps consistent with the UTC snapshot date."""
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is not None and stamp.astimezone(timezone.utc).date() == observed:
            return stamp
    except (TypeError, ValueError):
        pass
    return datetime.min.replace(tzinfo=timezone.utc)


def cohort_rows(snapshots, receipts, cutoff, *, age=7, window=28, today=None):
    """Use only exact-age, unambiguous snapshots and registered receipt owners."""
    today = today or datetime.now(timezone.utc).date()
    candidates = defaultdict(set)
    for row in snapshots:
        video = row.get("video_id")
        receipt = receipts.get(video, {})
        scope = (receipt.get("channel"), receipt.get("format"))
        if scope[0] not in CHANNELS or scope[1] not in {"short", "longform"}:
            continue
        if row.get("channel_key") and row["channel_key"] != scope[0]:
            continue
        try:
            release = date.fromisoformat(row.get("published_at", "")[:10])
            observed = date.fromisoformat(row.get("snapshot_date", ""))
        except (ValueError, TypeError):
            continue
        if observed > today or observed - release != timedelta(days=age):
            continue
        offset = (release - cutoff).days
        if not -window <= offset < window:
            continue
        values = []
        for key in METRICS:
            try:
                value = int(row.get(key, ""))
                values.append(value if value >= 0 else None)
            except (ValueError, TypeError):
                values.append(None)
        stamp = observation_time(row.get("observed_at"), observed)
        candidates[video].add((stamp, offset, tuple(values), scope))

    groups = defaultdict(list)
    for choices in candidates.values():
        newest = max(sample[0] for sample in choices)
        newest_rows = [sample for sample in choices if sample[0] == newest]
        if len(newest_rows) == 1:
            _, offset, values, (channel, fmt) = newest_rows[0]
            if values[0] is not None:
                groups[channel, fmt, offset >= 0].append(values)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", required=True, type=date.fromisoformat,
                        help="First calendar date of the comparison period (YYYY-MM-DD)")
    parser.add_argument("--metrics", type=Path, action="append",
                        help="CSV to read; repeat for downloaded metrics artifacts")
    parser.add_argument("--age", type=int, default=7)
    parser.add_argument("--window", type=int, default=28)
    args = parser.parse_args()
    if not 1 <= args.age <= 90 or not 1 <= args.window <= 365:
        parser.error("use an age of 1–90 days and a release window of 1–365 days")
    try:
        with ExitStack() as stack:
            readers = [csv.DictReader(stack.enter_context(path.open(newline="", encoding="utf-8")))
                       for path in (args.metrics or [METRICS_CSV])]
            groups = cohort_rows(chain.from_iterable(readers), load_published_index(), args.cutoff,
                                 age=args.age, window=args.window)
    except OSError:
        parser.exit(1, "No readable metrics CSV. Supply a local snapshot history with --metrics.\n")
    print(f"Snapshot age: {args.age} calendar days. Cutoff: {args.cutoff}. "
          f"Release window: {args.window} days on each side.")
    print("Cells show median (number measured), before → after. — means no measurement.")
    rows = []
    for channel in CHANNELS:
        for fmt in ("short", "longform"):
            before, after = (groups[channel, fmt, period] for period in (False, True))
            cells = []
            for i in range(len(METRICS)):
                values = [[row[i] for row in group if row[i] is not None] for group in (before, after)]
                cells.append(" → ".join(f"{median(series):g} ({len(series)})" if series else "—"
                                        for series in values))
            rows.append([channel, fmt, *cells, "descriptive" if min(len(before), len(after)) >= 5 else "sparse"])
    print(format_table(["Channel", "Format", *METRICS, "Coverage"], rows))
    print("Release dates do not prove authoring exposure. Check which drafts actually used the update. "
          "Use Studio separately for retention, shares and long-form watch time.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
