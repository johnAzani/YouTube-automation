#!/usr/bin/env python3
"""Finish what a scheduled upload starts: confirm the video really went public.

A long-form uploaded with a publish time is private until YouTube publishes it.
Its receipt says so (``scheduled_publish: true``). Three things are still owed
after the publish time, and nothing else in the repository does them:

* **Proof.** A receipt must not go on claiming a release that did not happen.
  Once YouTube reports the video public the flag is cleared and
  ``publish_confirmed_at`` records when that was seen.
* **The pinned comment**, when YouTube refused it on the private video
  (``pinned_comment_pending: true``).
* **A nudge.** A video still private well after its time is published here,
  with a warning, rather than left for somebody to notice. That is the state an
  immediate upload would have been in anyway.
* **Honesty about a release that will never happen.** A video YouTube rejected,
  or one that is gone, gets ``scheduled_publish_failed: true``. The supervisor
  stops counting that receipt as the slot's video, so the channel is produced
  again instead of sitting behind a receipt for nothing.

Before the publish time this script makes no API call at all, and with no
scheduled receipt it does not even build a client: it costs nothing while
scheduled publishing is off.

``published_at`` is never rewritten. It is the planned public time, the one the
slot accounting is built on; ``publish_confirmed_at`` is the observation.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Still private this long after its time: publish it ourselves.
PUBLISH_GRACE = timedelta(minutes=20)
# Stop asking YouTube about a receipt this long after its time. The error stays
# on the receipt; the question has been answered as far as an API can.
GIVE_UP_AFTER = timedelta(hours=48)
STAMP = "%Y-%m-%dT%H:%M:%SZ"
# The status fields `videos.update(part="status")` resets when they are omitted.
MUTABLE_STATUS = ("embeddable", "license", "publicStatsViewable",
                  "selfDeclaredMadeForKids", "containsSyntheticMedia")


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def pending_receipts(channel_id: str, published_dir: Path | None = None) -> list[tuple[Path, Any]]:
    """This channel's receipts that still say ``scheduled_publish: true``."""
    from pipeline.channels import channel_for_doc
    from pipeline.config import PUBLISHED_DIR
    from pipeline.script_doc import parse_script

    directory = published_dir or PUBLISHED_DIR
    found: list[tuple[Path, Any]] = []
    if not Path(directory).is_dir():
        return found
    for path in sorted(Path(directory).glob("*.md")):
        try:
            # Cheap pre-filter: most receipts never carried the flag.
            if "scheduled_publish:" not in path.read_text(encoding="utf-8"):
                continue
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        if not _truthy(doc.meta.get("scheduled_publish")):
            continue
        if not str(doc.meta.get("youtube_video_id") or "").strip():
            continue
        if channel_for_doc(doc.meta) != channel_id:
            continue
        found.append((path, doc))
    return found


def _publish_now(youtube, video_id: str, status: dict) -> None:
    body_status = {key: status[key] for key in MUTABLE_STATUS if key in status}
    body_status["privacyStatus"] = "public"
    youtube.videos().update(part="status", body={"id": video_id, "status": body_status}).execute()


def _post_owed_comment(youtube, doc, video_id: str) -> bool:
    from pipeline.pinned_comments import (
        generate_pastoral_pinned_comment,
        post_pastoral_pinned_comment,
    )

    text = generate_pastoral_pinned_comment(doc)
    if not text or not text.strip():
        return True  # nothing to post is not a debt
    return bool(post_pastoral_pinned_comment(youtube, video_id, text, dry_run=False))


def confirm_channel(channel: str, *, now: datetime | None = None, youtube_client: Any = None,
                    published_dir: Path | None = None, dry_run: bool = False) -> list[dict]:
    """Settle one channel's scheduled receipts. Returns one row per receipt."""
    from pipeline.channels import get_channel
    from pipeline.publish_schedule import parse_instant
    from scripts.sync_published_thumbnails import (
        _build_youtube_client,
        _has_youtube_credentials,
        clear_frontmatter_field,
        stamp_frontmatter_field,
    )

    now = now or datetime.now(timezone.utc)
    profile = get_channel(channel)
    rows: list[dict] = []
    receipts = pending_receipts(profile.id, published_dir)
    due = []
    for path, doc in receipts:
        video_id = str(doc.meta.get("youtube_video_id")).strip()
        planned = parse_instant(doc.meta.get("published_at"))
        row = {"channel": profile.id, "file": path.name, "video_id": video_id,
               "planned": planned.strftime(STAMP) if planned else ""}
        rows.append(row)
        if planned is None:
            row["state"] = "unreadable publish time"
            print(f"::warning title=Scheduled receipt has no usable time ({profile.id})::"
                  f"{path.name} says scheduled_publish but published_at cannot be read.")
        elif now < planned:
            row["state"] = "waiting for its time"
        elif now - planned > GIVE_UP_AFTER:
            row["state"] = "unresolved for two days"
        else:
            due.append((path, doc, video_id, planned, row))
    if not due:
        return rows
    if dry_run:
        for *_rest, row in due:
            row["state"] = "would check"
        return rows
    if youtube_client is None and not _has_youtube_credentials(profile):
        for *_rest, row in due:
            row["state"] = "skipped: no credentials for this channel here"
        return rows
    youtube = youtube_client or _build_youtube_client(profile)

    for path, doc, video_id, planned, row in due:
        response = youtube.videos().list(part="status", id=video_id).execute()
        items = response.get("items") or []
        if len(items) != 1 or items[0].get("id") != video_id:
            row["state"] = "video not found"
            stamp_frontmatter_field(path, "scheduled_publish_error", "video not found on YouTube")
            stamp_frontmatter_field(path, "scheduled_publish_failed", "true", raw=True)
            print(f"::error title=Scheduled video is missing ({profile.id})::{video_id} "
                  f"({path.name}) was due public at {row['planned']} and YouTube no longer "
                  "returns it.")
            continue
        status = items[0].get("status") or {}
        privacy = str(status.get("privacyStatus") or "")
        upload_status = str(status.get("uploadStatus") or "")
        seen = now.strftime(STAMP)

        if privacy == "private" and upload_status in {"rejected", "failed", "deleted"}:
            reason = status.get("rejectionReason") or status.get("failureReason") or upload_status
            row["state"] = f"not publishable: {reason}"
            stamp_frontmatter_field(path, "scheduled_publish_error", f"{upload_status}: {reason}")
            stamp_frontmatter_field(path, "scheduled_publish_failed", "true", raw=True)
            print(f"::error title=Scheduled video was refused ({profile.id})::{video_id} "
                  f"({path.name}) is {upload_status} ({reason}); it will not go public.")
            continue

        if privacy == "private":
            if now - planned < PUBLISH_GRACE:
                row["state"] = "past its time, still private; giving YouTube a few minutes"
                continue
            try:
                _publish_now(youtube, video_id, status)
            except Exception as exc:  # noqa: BLE001
                row["state"] = f"still private; publishing it failed: {exc}"[:200]
                stamp_frontmatter_field(path, "scheduled_publish_error", str(exc)[:300])
                print(f"::error title=Scheduled video is still private ({profile.id})::"
                      f"{video_id} ({path.name}) was due at {row['planned']} and could not "
                      f"be published: {exc}")
                continue
            privacy = "public"
            row["published_here"] = True
            late = int((now - planned).total_seconds() // 60)
            print(f"::warning title=Scheduled video published late ({profile.id})::"
                  f"{video_id} ({path.name}) was still private {late} minutes after "
                  f"{row['planned']}; it has been made public now.")

        # Public, or unlisted by somebody's deliberate hand: either way the
        # schedule is over and the receipt should stop saying otherwise.
        stamp_frontmatter_field(path, "scheduled_publish", "false", raw=True)
        stamp_frontmatter_field(path, "privacy_status", privacy)
        stamp_frontmatter_field(path, "publish_confirmed_at", seen)
        clear_frontmatter_field(path, "scheduled_publish_error")
        row["state"] = f"confirmed {privacy}"

        if privacy == "public" and _truthy(doc.meta.get("pinned_comment_pending")):
            try:
                posted = _post_owed_comment(youtube, doc, video_id)
            except Exception as exc:  # noqa: BLE001
                posted = False
                print(f"[confirm-publish] {video_id}: pinned comment failed: {exc}")
            if posted:
                clear_frontmatter_field(path, "pinned_comment_pending")
                row["pinned_comment"] = "posted"
            else:
                row["pinned_comment"] = "still owed"
    return rows


def confirm_all_channels(*, now: datetime | None = None, dry_run: bool = False,
                         published_dir: Path | None = None) -> dict[str, list[dict]]:
    """Every scheduled channel, each with its own credentials; one cannot stop another."""
    from pipeline.channels import scheduled_channels

    out: dict[str, list[dict]] = {}
    for channel in sorted(scheduled_channels()):
        try:
            rows = confirm_channel(channel, now=now, dry_run=dry_run, published_dir=published_dir)
        except Exception as exc:  # noqa: BLE001
            print(f"::warning title=Scheduled-publish check failed ({channel})::{exc!r}")
            rows = [{"channel": channel, "state": f"error: {exc}"[:200]}]
        if rows:
            out[channel] = rows
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-channels", action="store_true")
    group.add_argument("--channel")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.all_channels:
        results = confirm_all_channels(dry_run=args.dry_run)
    else:
        from pipeline.channels import normalize_channel_id

        channel = normalize_channel_id(args.channel)
        results = {channel: confirm_channel(channel, dry_run=args.dry_run)}
    rows = [row for channel_rows in results.values() for row in channel_rows]
    if not rows:
        print("[confirm-publish] no scheduled receipts")
        return 0
    for row in rows:
        print(f"::notice title=Scheduled publish::{json.dumps(row)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
