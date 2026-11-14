#!/usr/bin/env python3
"""Set a channel's search keywords, visitor trailer and home-page shelves. See pipeline/channel_page.py.

    python scripts/setup_channel_page.py --channel prayer5            # read, plan, write
    python scripts/setup_channel_page.py --channel prayer5 --dry-run  # read and plan only

Runs in the daily growth job after the metrics snapshot and the playlist sync.
Never fails the job: a channel page is not worth a red run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import channel_page  # noqa: E402
from pipeline.channel_capabilities import brand_for  # noqa: E402
from pipeline.channels import (  # noqa: E402
    add_channel_arg, apply_channel_env, channel_for_doc, normalize_channel_id)
from pipeline.config import CONFIG, PUBLISHED_DIR  # noqa: E402


def channel_longforms(channel_id: str, snapshots: list[dict], published_dir: Path | None = None) -> list[dict]:
    """This channel's public long-forms with their latest view counts."""
    from pipeline.retitle import latest_views
    from pipeline.script_doc import parse_script

    views = latest_views(snapshots)
    rows: list[dict] = []
    for path in sorted(Path(published_dir or PUBLISHED_DIR).glob("*.md")):
        if path.name.startswith("short-"):
            continue
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        meta = doc.meta
        video_id = str(meta.get("youtube_video_id") or "").strip()
        if (doc.format == "short" or not video_id
                or normalize_channel_id(channel_for_doc(meta)) != channel_id
                or str(meta.get("privacy_status") or "public") != "public"
                or str(meta.get("scheduled_publish")).lower() == "true"
                or str(meta.get("youtube_status") or "") == "deleted_or_missing"):
            continue
        rows.append({"video_id": video_id, "views": views.get(video_id, 0),
                     "published": str(meta.get("published_at") or meta.get("published_on") or "")})
    return rows


def series_playlists(youtube, channel_id: str) -> list[dict]:
    """The channel's series playlists that exist on YouTube, in the brand's order, with item counts."""
    from pipeline.playlists import playlists_for_channel

    rows = (youtube.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50)
            .execute().get("items") or [])
    live = {str((row.get("snippet") or {}).get("title") or "").strip().lower(): row for row in rows}
    found: list[dict] = []
    for spec in playlists_for_channel(channel_id).values():
        row = live.get(spec.title.strip().lower())
        if row and row.get("id"):
            found.append({"id": row["id"],
                          "items": int((row.get("contentDetails") or {}).get("itemCount") or 0)})
    return found


def run(channel_id: str, youtube, *, dry_run: bool = False, snapshots: list[dict] | None = None) -> list[str]:
    from pipeline.performance_feedback import load_metric_snapshots

    channel_id = normalize_channel_id(channel_id)
    snapshots = load_metric_snapshots() if snapshots is None else snapshots
    channel, sections = channel_page.read_page(youtube)
    changes = channel_page.plan(
        channel, sections,
        keywords=brand_for(channel_id).seo_tag_seeds,
        longforms=channel_longforms(channel_id, snapshots),
        playlists=series_playlists(youtube, channel_id),
    )
    lines = list(changes.notes)
    if changes.empty:
        lines.append("nothing to write")
    elif dry_run:
        lines.append("dry run: nothing written")
    else:
        lines += channel_page.apply(youtube, channel, changes)
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    add_channel_arg(parser)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    channel_id = apply_channel_env(args.channel)
    CONFIG.refresh()
    if not (CONFIG.youtube_client_id and CONFIG.youtube_client_secret and CONFIG.youtube_refresh_token):
        print("[channel-page] no YouTube credentials in this run; nothing read, nothing written")
        return 0
    try:
        from googleapiclient.discovery import build

        from pipeline.upload import _credentials

        youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
        for line in run(channel_id, youtube, dry_run=args.dry_run):
            print(f"[channel-page] {channel_id}: {line}")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning title=Channel page not set up ({channel_id})::{str(exc)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
