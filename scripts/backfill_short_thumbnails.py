#!/usr/bin/env python3
"""Backfill custom 9:16 thumbnails onto Shorts that are already live.

Why this exists: until 2026-11-03 the YouTube Data API told nobody that
`thumbnails.set` works for Shorts, so `pipeline/short_release.py` skipped the call
and wrote `not_supported_for_shorts` into every receipt. YouTube therefore keeps
showing an auto-grabbed frame for those videos on the channel page, in search, in
subscriptions and in playlists (the swipe feed never shows a custom thumbnail).
The API now accepts the call, and it centre-crops to 9:16, so the only correct
input is a native 1080x1920 poster — see `pipeline/shorts_poster.py`.

Cost: `thumbnails.set` is 50 quota units per attempt against a 10,000/day bucket.
Nine live Shorts is 450 units. The script prints the estimate before wiring
anything, and `--dry-run` renders the posters without spending a single unit.

Usage (from the repo root, with that channel's OAuth secrets in the environment):

    python scripts/backfill_short_thumbnails.py --dry-run          # render only
    python scripts/backfill_short_thumbnails.py --channel secret-place
    python scripts/backfill_short_thumbnails.py --limit 3          # canary first

Exit code is 0 only when every Short it attempted is confirmed by YouTube
(`snippet.thumbnails.shortsAspectRatio` present after the upload).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_published_thumbnails import (  # noqa: E402
    SHORTS_POSTER_REVISION,
    collect_pending_short_receipts,
    sync_published_thumbnails,
)

QUOTA_PER_SET = 50


def _targets(channel: str | None) -> list[str]:
    from pipeline.channels import scheduled_channels

    if channel:
        return [channel]
    return sorted(scheduled_channels())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", help="channel id (default: every scheduled channel)")
    ap.add_argument("--dry-run", action="store_true",
                    help="render and report the posters without calling the API")
    ap.add_argument("--limit", type=int, default=None,
                    help="attempt at most N Shorts per channel (canary run)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    channels = _targets(args.channel)
    report: dict[str, list[dict]] = {}
    failures = 0

    for cid in channels:
        pending = collect_pending_short_receipts(channel_id=cid, force=False)
        if not args.json:
            print(f"[backfill] {cid}: {len(pending)} Short(s) without a confirmed "
                  f"{SHORTS_POSTER_REVISION} poster "
                  f"(estimate {len(pending) * QUOTA_PER_SET} quota units)")
        rows = sync_published_thumbnails(
            channel=cid, shorts_only=True, dry_run=args.dry_run, limit=args.limit
        )
        report[cid] = rows
        for row in rows:
            status = str(row.get("thumbnail_status") or "")
            if not args.dry_run and status != "ok":
                failures += 1
        if not args.json:
            for row in rows:
                poster = row.get("poster") or {}
                print(f"  {row.get('video_id'):>14}  {row.get('thumbnail_status'):<32} "
                      f"contrast={poster.get('contrast')} hero={poster.get('hero_px')}px "
                      f"kicker={poster.get('kicker')!r}")

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    attempted = sum(len(v) for v in report.values())
    if not args.json:
        mode = "rendered" if args.dry_run else "applied"
        print(f"[backfill] {mode} {attempted} poster(s); "
              f"{'spent ~' + str(attempted * QUOTA_PER_SET) + ' quota units' if not args.dry_run else 'no quota spent'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
