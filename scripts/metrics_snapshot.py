#!/usr/bin/env python3
"""Weekly metrics snapshot — the measurement loop from docs/DEEP_DIVE.md §5.

Reads the channel's recent videos (Data API `videos.list`, 1 unit/call) and
writes a rolling 30-day snapshot of public-video data to content/metrics.csv
so growth can be reviewed. Private and unlisted video metadata is excluded; the
repository is public, so this boundary is deliberate. This does not collect
channel-level subscriber totals.

Needs the same credentials as upload.py, with the `youtube.readonly` scope
added to the OAuth consent screen + refresh token (scripts/youtube_oauth.py).

    python scripts/metrics_snapshot.py            # append snapshot + print table
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.config import CONFIG  # noqa: E402
from pipeline.upload import _credentials  # noqa: E402

CSV_PATH = REPO / "content" / "metrics.csv"
FIELDS = ["snapshot_date", "video_id", "title", "published_at", "views", "likes", "comments"]
RETENTION_DAYS = 30


def _public_video_rows(items: list[dict], today: str) -> list[dict]:
    """Keep only data for public videos; never export private/unlisted metadata."""
    rows = []
    for v in items:
        if v.get("status", {}).get("privacyStatus") != "public":
            continue
        s = v.get("statistics", {})
        rows.append({
            "snapshot_date": today,
            "video_id": v["id"],
            "title": v["snippet"]["title"][:80],
            "published_at": v["snippet"]["publishedAt"][:10],
            "views": s.get("viewCount", 0),
            "likes": s.get("likeCount", 0),
            "comments": s.get("commentCount", 0),
        })
    return rows


def _within_retention(rows: list[dict], today: dt.date) -> list[dict]:
    cutoff = today - dt.timedelta(days=RETENTION_DAYS)
    kept = []
    for row in rows:
        try:
            snapshot_date = dt.date.fromisoformat(row["snapshot_date"])
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff <= snapshot_date <= today:
            kept.append(row)
    return kept


def main() -> int:
    from googleapiclient.discovery import build

    if not CONFIG.youtube_refresh_token or not CONFIG.youtube_client_secret:
        print("no YouTube credentials in env — nothing to snapshot")
        return 0

    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items") or []
    if not items:
        print("no channel for these credentials")
        return 1
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print("authenticated channel found; collecting public-video metrics only")

    video_ids: list[str] = []
    page = None
    while True:
        resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50, pageToken=page
        ).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in resp.get("items", [])]
        page = resp.get("nextPageToken")
        if not page or len(video_ids) >= 50:
            break

    today = dt.date.today()
    today_text = today.isoformat()
    rows = []
    if video_ids:
        vresp = youtube.videos().list(
            part="snippet,statistics,status", id=",".join(video_ids)
        ).execute()
        rows = _public_video_rows(vresp.get("items", []), today_text)

    # The repository and its workflow pages are public. Keep only public-video
    # metrics, and retain a rolling 30-day window rather than accumulating API data.
    existing = []
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))
    combined = _within_retention(existing + rows, today)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(combined)
    print(f"stored {len(rows)} public-video rows; retained {len(combined)} rows (30-day window)")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## Public-video metrics snapshot {today_text}\n\n")
            f.write(f"Snapshot prepared for {len(rows)} public videos. "
                    "Private and unlisted metadata is excluded. Download the run artifact; "
                    "it expires after 30 days.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
