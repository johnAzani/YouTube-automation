#!/usr/bin/env python3
"""Weekly metrics snapshot — the measurement loop from docs/DEEP_DIVE.md §5.

Reads the channel's recent videos (Data API `videos.list`, 1 unit/call) and
appends a row per video to content/metrics.csv so growth is reviewed against
benchmarks (CTR/AVD live in YouTube Studio; this captures the API-visible floor:
views, likes, comments, subs-relevant signals) and writes a GitHub job summary.

Needs the same credentials as upload.py, with the `youtube.readonly` scope
added to the OAuth consent screen + refresh token (scripts/youtube_oauth.py).

    python scripts/metrics_snapshot.py            # append snapshot + print table
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from pipeline.config import CONFIG  # noqa: E402
from pipeline.upload import _credentials  # noqa: E402

CSV_PATH = REPO / "content" / "metrics.csv"
FIELDS = ["snapshot_date", "video_id", "title", "published_at", "views", "likes", "comments"]


def main() -> int:
    from googleapiclient.discovery import build

    if not CONFIG.youtube_refresh_token or not CONFIG.youtube_client_secret:
        print("no YouTube credentials in env — nothing to snapshot")
        return 0

    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    ch = youtube.channels().list(part="contentDetails,statistics", mine=True).execute()
    items = ch.get("items") or []
    if not items:
        print("no channel for these credentials")
        return 1
    stats = items[0]["statistics"]
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"channel: subs={stats.get('subscriberCount')} views={stats.get('viewCount')} videos={stats.get('videoCount')}")

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

    rows = []
    if video_ids:
        vresp = youtube.videos().list(part="snippet,statistics", id=",".join(video_ids)).execute()
        today = dt.date.today().isoformat()
        for v in vresp.get("items", []):
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

    new_file = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    print(f"appended {len(rows)} rows to {CSV_PATH.relative_to(REPO)}")

    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(f"## 📈 Metrics snapshot {dt.date.today()}\n\n")
            f.write(f"Subs: **{stats.get('subscriberCount')}** · lifetime views: {stats.get('viewCount')}\n\n")
            f.write("| Published | Views | Likes | Title |\n|---|---|---|---|\n")
            for r in rows[:15]:
                f.write(f"| {r['published_at']} | {r['views']} | {r['likes']} | {r['title']} |\n")
            f.write("\nBenchmarks (DEEP_DIVE §3.1): CTR 4–6% healthy · AVD 50% (6–10 min) · "
                    "Shorts APV 65%+ (<30 s). Check Studio → Reach/Engagement weekly.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
