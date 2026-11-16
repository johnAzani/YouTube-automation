#!/usr/bin/env python3
"""Once a week: how the most-watched recent videos of a channel's kind are titled.

Asked for by the owner on 16 November 2026 ("learn from what top videos in my
niche are doing"). It is one of the two places a lesson comes from; the other is
the channel's own search terms. `pipeline/lessons.py` explains what happens to a
lesson: it is tried in new titles and judged by the channel's own views.

What one reading does, for one channel:

1. asks YouTube's search (`search.list`) twice for the channel's kind of prayer
   ("night prayer", "night prayer scripture"): long videos published in the
   last 90 days, most viewed first, 25 results each;
2. asks `videos.list` once for the lengths of those videos (`contentDetails`
   only; view, like and subscriber counts are never requested);
3. keeps the word sequences that the titles of at least three different
   channels share (two to four words, none of them most of any one title), and
   the typical length;
4. writes those few phrases and that one length to the file named by `--out`,
   which the feedback step reads and then folds into the channel's artifact.

What it never does: read a page of youtube.com, download a video, a thumbnail
or captions, or keep any other channel's title, name, id or figure. Everything
it read is gone when the step ends, and nothing about a single video is printed.

Cost: 2 `search.list` calls (their own allowance of 100 a day) and 1 unit of the
10,000, once in seven days for each channel. It runs as a step of the daily
growth job that already exists, so it adds no workflow run. $0.

It never fails the job: any refusal is one warning line and the channel simply
learns from the reading it already has.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import lessons  # noqa: E402
from pipeline.channel_capabilities import brand_for, known_channels  # noqa: E402
from pipeline.channels import add_channel_arg, apply_channel_env, normalize_channel_id  # noqa: E402
from pipeline.performance_feedback import load_feedback_report  # noqa: E402

#: Days between two readings of one channel's niche.
EVERY_DAYS = 7
#: Only videos published in this many days: what is being watched now, not ten years of views.
RECENT_DAYS = 90
#: Results asked of each search (one page; the reading never pages).
RESULTS = 25
#: Searches in one reading.
MAX_QUERIES = 2

_DURATION = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def queries_for(channel_id: str) -> list[str]:
    """What the channel's own kind of prayer is called, as a person would search for it."""
    label = " ".join(brand_for(channel_id).longform_prayer_label.lower().split())
    return [label, f"{label} scripture"][:MAX_QUERIES]


def due(channel_id: str, today: dt.date, report: dict | None = None) -> tuple[bool, str]:
    """(read now?, why) from the date of the reading already in the channel's artifact."""
    if report is None:
        report = load_feedback_report(channel_id=channel_id) or {}
    block = report.get("niche") if isinstance(report, dict) else None
    try:
        last = dt.date.fromisoformat(str((block or {}).get("read_on") or ""))
    except ValueError:
        return True, "no reading yet"
    age = (today - last).days
    if 0 <= age < EVERY_DAYS:
        return False, (f"read {age} day(s) ago; the next reading is on "
                       f"{(last + dt.timedelta(days=EVERY_DAYS)).isoformat()}")
    return True, f"last read {last.isoformat()}"


def minutes(duration: str) -> float:
    """An ISO 8601 length ("PT1H2M3S") in minutes; 0 when it cannot be read."""
    found = _DURATION.fullmatch(str(duration or ""))
    if not found or not any(found.groups()):
        return 0.0
    days, hours, mins, secs = (int(part or 0) for part in found.groups())
    return days * 1440 + hours * 60 + mins + secs / 60.0


def own_names() -> set[str]:
    return {" ".join(brand_for(channel).display_name.lower().split()) for channel in known_channels()}


def read(youtube, channel_id: str, today: dt.date) -> dict:
    """One reading. Returns the block to keep; everything else is dropped here."""
    after = (dt.datetime.combine(today, dt.time(0), dt.timezone.utc)
             - dt.timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ours = own_names()
    titles: dict[str, tuple[str, str]] = {}
    for query in queries_for(channel_id):
        answer = youtube.search().list(
            part="snippet", q=query, type="video", order="viewCount", videoDuration="long",
            publishedAfter=after, relevanceLanguage="en", maxResults=RESULTS).execute()
        for item in answer.get("items") or []:
            video = str((item.get("id") or {}).get("videoId") or "")
            snippet = item.get("snippet") or {}
            maker = str(snippet.get("channelId") or "")
            if not video or not maker:
                continue
            if " ".join(str(snippet.get("channelTitle") or "").lower().split()) in ours:
                continue  # the owner's own channels are not "the niche"
            titles[video] = (str(snippet.get("title") or ""), maker)
    lengths: list[float] = []
    ids = list(titles)[:50]
    if ids:
        answer = youtube.videos().list(part="contentDetails", id=",".join(ids)).execute()
        for item in answer.get("items") or []:
            length = minutes((item.get("contentDetails") or {}).get("duration"))
            if length > 0:
                lengths.append(length)
    block: dict = {
        "read_on": today.isoformat(),
        "phrases": lessons.phrases_from_titles(titles.values(), lessons.label_words(channel_id)),
    }
    if len(lengths) >= 5:
        block["typical_minutes"] = int(round(median(lengths)))
    makers = len({maker for _title, maker in titles.values()})
    print(f"[niche] {channel_id}: read {len(titles)} long video(s) from {makers} other channel(s), "
          f"published in the last {RECENT_DAYS} days, most viewed first")
    return block


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_channel_arg(parser)
    parser.add_argument("--out", default="", help="where to leave the reading for the feedback step")
    parser.add_argument("--force", action="store_true", help="read even when the last reading is fresh")
    args = parser.parse_args(argv)
    channel_id = normalize_channel_id(args.channel) if args.channel else known_channels()[0]
    today = dt.datetime.now(dt.timezone.utc).date()

    ready, why = due(channel_id, today)
    if not ready and not args.force:
        print(f"[niche] {channel_id}: {why}. Nothing asked of YouTube.")
        return 0
    try:
        from googleapiclient.discovery import build

        from pipeline.config import CONFIG
        from pipeline.upload import _credentials

        apply_channel_env(args.channel)
        if args.channel:
            CONFIG.refresh()
        if not all((CONFIG.youtube_refresh_token, CONFIG.youtube_client_id,
                    CONFIG.youtube_client_secret)):
            print(f"::notice title=Niche reading skipped ({channel_id})::no YouTube credentials "
                  "in this run")
            return 0
        youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
        block = read(youtube, channel_id, today)
    except Exception as exc:  # noqa: BLE001 - a reading never costs the growth job
        text = re.sub(r"[^A-Za-z0-9 _.:,'()/-]", " ", str(exc))[:200]
        print(f"::warning title=Niche reading not made ({channel_id})::{type(exc).__name__}: {text}")
        return 0

    if block["phrases"]:
        print(f"[niche] {channel_id}: wording shared by at least {lessons.MIN_CHANNELS} channels: "
              + "; ".join(block["phrases"]))
    else:
        print(f"[niche] {channel_id}: no wording was shared by {lessons.MIN_CHANNELS} channels "
              "this week")
    if "typical_minutes" in block:
        print(f"[niche] {channel_id}: their typical length is {block['typical_minutes']} minutes")
    if args.out:
        Path(args.out).write_text(json.dumps(block, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
