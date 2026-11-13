#!/usr/bin/env python3
"""Weekly metrics snapshot — the measurement loop from docs/DEEP_DIVE.md §5.

Reads the channel's recent videos (Data API `videos.list`, 1 unit/call) and
writes a rolling 30-day snapshot of public-video data to content/metrics.csv
so growth can be reviewed. Private and unlisted video metadata is excluded; the
repository is public, so this boundary is deliberate. Also collects the channel's public subscriber count (rounded by YouTube) when it is not hidden.

Needs the same credentials as upload.py, with the `youtube.readonly` scope
added to the OAuth consent screen + refresh token (scripts/youtube_oauth.py).

    python scripts/metrics_snapshot.py            # append snapshot + print table
"""
from __future__ import annotations

import csv
import json
import datetime as dt
import os
import subprocess
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
            # Missing statistics are unknown, not evidence of zero views.
            "views": s.get("viewCount", ""),
            "likes": s.get("likeCount", 0),
            "comments": s.get("commentCount", 0),
        })
    return rows


def _check_snapshot_channel(items: list[dict], expected_id: str) -> dict:
    """Do not label another account's metrics as the requested channel."""
    if len(items) != 1 or not isinstance(items[0], dict) or not items[0].get("id"):
        raise RuntimeError("Metrics credentials returned a missing or ambiguous channel")
    expected = (expected_id or "").strip()
    if expected and items[0]["id"] != expected:
        raise RuntimeError("Metrics credentials do not match the expected channel ID")
    if not expected:
        print("::warning title=Channel identity unverified::No expected channel ID is configured; "
              "metrics cannot be checked against the requested channel.")
    return items[0]


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


def _subscriber_snapshot(channel: dict, today: str) -> dict:
    """Export only public subscriber data; missing/hidden is not zero."""
    stats = channel.get("statistics") or {}
    hidden = stats.get("hiddenSubscriberCount") is True
    count = None if hidden else stats.get("subscriberCount")
    return {
        "snapshot_date": today,
        "channel_id": channel.get("id"),
        "subscriber_count": int(count) if count is not None else None,
        "subscriber_count_hidden": hidden,
        "note": "YouTube rounds subscriberCount to three significant figures; not an exact live count.",
    }


def _subscriber_summary(snapshot: dict) -> str:
    count = snapshot["subscriber_count"]
    if count is None:
        return "Subscribers: unavailable (hidden or omitted by YouTube)."
    return f"Subscribers (YouTube-reported): {count:,}. YouTube rounds this count to three significant figures."


def _post_github_issue(
    channel_snapshot: dict,
    rows: list[dict],
    today_text: str,
    channel_key: str | None = None,
) -> None:
    """Post an analytics snapshot issue to GitHub so the autonomous pipeline & agent have live tracking."""
    from pipeline.channel_capabilities import brand_for

    env = {**os.environ}
    if not env.get("GH_TOKEN") and env.get("GITHUB_TOKEN"):
        env["GH_TOKEN"] = env["GITHUB_TOKEN"]
    if not env.get("GH_TOKEN"):
        return

    brand_name = brand_for(channel_key).display_name
    title = f"📊 Channel Analytics Snapshot ({brand_name}): {today_text}"
    lines = [
        f"## 📊 {brand_name} — Channel & Video Metrics ({today_text})",
        "",
        _subscriber_summary(channel_snapshot),
        "",
        "### Public Video Performance",
        "",
        "| Video ID | Title | Published | Views | Likes | Comments | Link |",
        "| :--- | :--- | :--- | :---: | :---: | :---: | :--- |",
    ]
    for r in rows:
        vid = r.get("video_id", "")
        t = str(r.get("title", ""))[:45]
        pub = r.get("published_at", "")
        v = r.get("views")
        if v is None or v == "":
            v = "unknown"
        l = r.get("likes", 0)
        c = r.get("comments", 0)
        watch_link = f"[Watch](https://youtu.be/{vid})"
        lines.append(f"| `{vid}` | {t} | {pub} | {v} | {l} | {c} | {watch_link} |")

    lines.extend([
        "",
        "---",
        "*Automated analytics snapshot generated by `scripts/metrics_snapshot.py` for autonomous agent monitoring.*",
    ])
    body = "\n".join(lines)

    try:
        proc = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            check=False, capture_output=True, text=True, env=env,
        )
        if proc.returncode == 0:
            created_out = (proc.stdout or "").strip()
            print(f"analytics snapshot issue created: {created_out[:200]}")
            _close_superseded_snapshot_issues(brand_name, created_out, env=env)
    except Exception as exc:
        print(f"analytics issue creation skipped: {exc!r}")


def _close_superseded_snapshot_issues(brand_name: str, created_url: str, *, env: dict) -> list[int]:
    """Close older open analytics snapshot issues for the same channel once a new one is filed."""
    import re
    from pipeline.channels import DEFAULT_CHANNEL_ID, normalize_channel_id

    m = re.search(r"/issues/(\d+)\s*$", created_url or "")
    keep_num = int(m.group(1)) if m else 0
    found = subprocess.run(
        [
            "gh", "issue", "list", "--state", "open",
            "--search", '"Channel Analytics Snapshot" in:title',
            "--json", "number,title", "--limit", "50",
        ],
        check=False, capture_output=True, text=True, env=env,
    )
    if found.returncode != 0:
        return []
    try:
        rows = json.loads(found.stdout or "[]")
    except (ValueError, TypeError):
        return []
    prefixes = {f"📊 Channel Analytics Snapshot ({brand_name}):"}
    if normalize_channel_id(os.environ.get("CHANNEL_ID")) == DEFAULT_CHANNEL_ID:
        prefixes.add("📊 Channel Analytics Snapshot:")
    closed: list[int] = []
    for row in rows:
        num = int(row.get("number") or 0)
        t = str(row.get("title") or "")
        if not num or num == keep_num:
            continue
        if any(t.startswith(p) for p in prefixes):
            res = subprocess.run(
                [
                    "gh", "issue", "close", str(num),
                    "--comment", "Closing automatically: superseded by a newer weekly analytics snapshot.",
                ],
                check=False, capture_output=True, text=True, env=env,
            )
            if res.returncode == 0:
                closed.append(num)
    return closed


def scopes_for_refresh() -> list[str]:
    """The scopes `_credentials()` asks for when it refreshes the token."""
    from pipeline.upload import SCOPES

    return list(SCOPES)


def main(argv: list[str] | None = None) -> int:
    import argparse
    from googleapiclient.discovery import build
    from pipeline.channels import add_channel_arg, apply_channel_env

    parser = argparse.ArgumentParser(description=__doc__)
    add_channel_arg(parser)
    eff_argv = argv if argv is not None else (
        sys.argv[1:] if sys.argv and "metrics_snapshot" in sys.argv[0] else []
    )
    args = parser.parse_args(eff_argv)
    channel_key = apply_channel_env(args.channel)
    if args.channel:
        CONFIG.refresh()

    if not all((CONFIG.youtube_refresh_token, CONFIG.youtube_client_id, CONFIG.youtube_client_secret)):
        missing = [name for name, value in (
            ("YOUTUBE_CLIENT_ID", CONFIG.youtube_client_id),
            ("YOUTUBE_CLIENT_SECRET", CONFIG.youtube_client_secret),
            ("YOUTUBE_REFRESH_TOKEN", CONFIG.youtube_refresh_token),
        ) if not value]
        # This exited 1 on 30 October with nothing in the log but "exit code 1", and
        # the run log was unreachable, so the fault sat undiagnosed for three days.
        # Name the missing secret in an annotation the run page shows.
        print(f"::error title=Metrics snapshot cannot run::missing {', '.join(missing)}")
        print("missing " + ", ".join(missing))
        return 1

    try:
        creds = _credentials()
    except Exception as exc:  # noqa: BLE001
        # A RefreshError here is almost always `invalid_scope`: the stored refresh
        # token was minted with a different scope set than the code asks for. That
        # arrived as a bare stack trace for a week, which reads as "the analytics
        # code is broken" when the fix is to mint the token again.
        text = str(exc).lower()
        if "invalid_scope" in text or "refresh" in text:
            print("::error title=YouTube token rejected::the stored refresh token cannot "
                  "be exchanged for the scopes this script needs")
            print("requested scopes:")
            for scope in scopes_for_refresh():
                print(f"  - {scope}")
            print("fix: re-mint YOUTUBE_REFRESH_TOKEN with "
                  "`python scripts/youtube_oauth.py --client-secret <file>` (purpose upload) "
                  "and update the repository secret. The upload path needs the same scopes.")
            return 2
        raise

    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    ch = youtube.channels().list(part="contentDetails,statistics", mine=True).execute()
    items = ch.get("items") or []
    try:
        channel = _check_snapshot_channel(items, CONFIG.expected_youtube_channel_id)
    except RuntimeError as exc:
        print(f"::error title=Metrics channel identity check failed::{exc}")
        return 1
    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
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
    channel_snapshot = _subscriber_snapshot(channel, today_text)
    channel_snapshot["channel_key"] = channel_key
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSV_PATH.with_name("channel-metrics.json").write_text(
        json.dumps(channel_snapshot, indent=2) + "\n", encoding="utf-8"
    )
    CSV_PATH.with_name(f"channel-metrics-{channel_key}.json").write_text(
        json.dumps(channel_snapshot, indent=2) + "\n", encoding="utf-8"
    )
    print(_subscriber_summary(channel_snapshot))
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
            f.write(_subscriber_summary(channel_snapshot) + "\n\n")
            f.write(f"Snapshot prepared for {len(rows)} public videos. "
                    "Private and unlisted metadata is excluded. Download the run artifact; "
                    "it expires after 30 days.\n")

    if os.environ.get("METRICS_POST_ISSUE", "1") != "0":
        _post_github_issue(channel_snapshot, rows, today_text, channel_key=channel_key)
    return 0


if __name__ == "__main__":
    import traceback

    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a bare "exit code 1" is not a diagnosis
        traceback.print_exc()
        line = traceback.extract_tb(sys.exc_info()[2])[-1].lineno
        print(f"::error file=scripts/metrics_snapshot.py,line={line}::"
              "metrics snapshot raised (see traceback above)")
        sys.exit(1)
