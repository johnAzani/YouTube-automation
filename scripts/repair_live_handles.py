#!/usr/bin/env python3
"""Take a retired @handle out of descriptions that are already on YouTube.

Why this exists: The Secret Place's descriptions linked to a handle the channel
never had (`pipeline/channels.py`, `RETIRED_HANDLES`). Its subscribe link and its
Shorts' "pray the complete prayer" fallback link both opened "404 Not Found" on
44 published videos. Correcting the registry fixes every upload from now on; the
videos already published keep the dead link until somebody rewrites it. This
does that, and nothing else.

What it changes, per video: the description, and the description of each
translation. In those texts the retired handle becomes the channel's handle.
Title, tags, category, language, thumbnail, privacy and schedule are sent back
exactly as YouTube returned them or not sent at all. A video whose text does
not contain the retired handle is never written to.

How it stays cheap: a receipt is stamped `live_handle: "<handle>"` once its
video is known to be right, and a stamped receipt costs no API call again. One
run reads up to fifty videos per unit of quota and writes at most
`LIVE_HANDLE_MAX_UPDATES` (default 30, 50 units each), so the day's uploads
keep their quota; the next monitor run carries on where this one stopped.

It never fails the job that runs it: a broken link is not a reason to lose the
thumbnail sync or the health report in the same step.

Usage:
  python -m scripts.repair_live_handles            # dry run: says what it would do
  python -m scripts.repair_live_handles --apply    # rewrite, then stamp receipts

Not covered: pinned comments that mention the retired handle. A comment's text
is a mention, not the link people tap, and finding each comment costs a search
per video.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any, Callable

from pipeline.channels import CHANNELS, RETIRED_HANDLES, channel_for_doc, get_channel
from pipeline.config import REPO_ROOT
from pipeline.script_doc import parse_script

PUBLISHED_DIR = REPO_ROOT / "content" / "published"
STAMP = "live_handle"
DEFAULT_MAX_UPDATES = 30
BATCH = 50
#: The only snippet fields `videos.update` accepts back. Everything else YouTube
#: returns in a snippet (channel, publish time, thumbnails, the viewer-language
#: copy) is read-only, and an omitted writable field is wiped, so all six go back.
WRITABLE = ("title", "description", "tags", "categoryId", "defaultLanguage", "defaultAudioLanguage")
_VIDEO_ID = re.compile(r"^youtube_video_id:\s*[\"']?([A-Za-z0-9_-]{11})[\"']?\s*$", re.M)


def swap(text: str, retired: str, current: str) -> str:
    """`text` with the retired handle replaced, and nothing that merely contains it.

    The handle is followed by `/playlists`, by `?sub_confirmation=1`, by a space,
    or by the full stop that ends a sentence. Left alone: a longer name that
    starts the same way, a hashtag (`#Name`, no `@`), and an e-mail address
    whose domain happens to match (`someone@name.media`). Handles are not
    case-sensitive on YouTube, so neither is the match.
    """
    if not text or not retired:
        return text
    pattern = (r"(?<![A-Za-z0-9._%+-])" + re.escape(retired)
               + r"(?![A-Za-z0-9_-])(?!\.[A-Za-z0-9])")
    return re.sub(pattern, current, text, flags=re.IGNORECASE)


def corrected_body(video: dict, retired: tuple[str, ...], current: str) -> dict | None:
    """The `videos.update` body that fixes this video, or None when it is already right."""
    snippet = video.get("snippet") or {}
    localizations = video.get("localizations") or {}

    def fix(text: str) -> str:
        for name in retired:
            text = swap(text, name, current)
        return text

    description = fix(str(snippet.get("description") or ""))
    new_localizations = {
        language: {**entry, "description": fix(str(entry.get("description") or ""))}
        if isinstance(entry, dict) and entry.get("description") else entry
        for language, entry in localizations.items()
    }
    if description == (snippet.get("description") or "") and new_localizations == localizations:
        return None
    body: dict[str, Any] = {
        "id": video.get("id"),
        "snippet": {key: snippet[key] for key in WRITABLE if snippet.get(key) not in (None, "", [])},
    }
    body["snippet"]["description"] = description
    if new_localizations:
        body["localizations"] = new_localizations
    return body


def still_broken(video: dict, retired: tuple[str, ...]) -> bool:
    """True when a retired handle is still in any description YouTube now holds."""
    texts = [str((video.get("snippet") or {}).get("description") or "")]
    texts += [str((entry or {}).get("description") or "")
              for entry in (video.get("localizations") or {}).values() if isinstance(entry, dict)]
    return any(swap(text, name, "") != text for text in texts for name in retired)


def pending(published_dir: Path | None = None) -> dict[str, list[tuple[Path, str]]]:
    """Receipts not yet known to be right, by channel: (receipt, video id), oldest name first.

    Only channels with a retired handle are looked at, so nine of the ten
    channels cost nothing here, not even a file read past the registry.
    """
    directory = published_dir or PUBLISHED_DIR
    found: dict[str, list[tuple[Path, str]]] = {}
    if not RETIRED_HANDLES or not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        match = _VIDEO_ID.search(raw)
        if not match:
            continue
        meta = parse_script(path).meta
        channel = channel_for_doc(meta)
        if channel not in RETIRED_HANDLES or channel not in CHANNELS:
            continue
        if str(meta.get("youtube_status", "")).strip() == "deleted_or_missing":
            continue
        if str(meta.get(STAMP, "")).strip() == get_channel(channel).handle:
            continue
        found.setdefault(channel, []).append((path, match.group(1)))
    return found


def _default_stamp(path: Path, key: str, value: str) -> None:
    from scripts.sync_published_thumbnails import stamp_frontmatter_field

    stamp_frontmatter_field(path, key, value)


def _default_client(channel: str):
    from scripts.sync_published_thumbnails import _build_youtube_client, _has_youtube_credentials

    profile = get_channel(channel)
    if not _has_youtube_credentials(profile):
        return None
    return _build_youtube_client(profile)


def repair(
    *,
    apply: bool = False,
    published_dir: Path | None = None,
    client_for: Callable[[str], Any] = _default_client,
    stamp: Callable[[Path, str, str], None] = _default_stamp,
    max_updates: int = DEFAULT_MAX_UPDATES,
) -> dict[str, dict[str, int]]:
    """Correct live descriptions channel by channel; returns the counts per channel."""
    report: dict[str, dict[str, int]] = {}
    budget = max(0, int(max_updates))
    for channel, receipts in pending(published_dir).items():
        counts = {"pending": len(receipts), "corrected": 0, "already_right": 0, "would_correct": 0,
                  "not_found": 0, "failed": 0, "left": 0, "no_credentials": 0}
        report[channel] = counts
        current = get_channel(channel).handle
        retired = RETIRED_HANDLES[channel]
        try:
            youtube = client_for(channel)
        except Exception as exc:  # noqa: BLE001 - a dead token must not stop the monitor
            print(f"[handles] {channel}: could not sign in ({type(exc).__name__})")
            youtube = None
        if youtube is None:
            counts["no_credentials"] = 1
            counts["left"] = len(receipts)
            continue

        stopped = False
        for start in range(0, len(receipts), BATCH):
            chunk = receipts[start:start + BATCH]
            if stopped:
                counts["left"] += len(chunk)
                continue
            try:
                listed = youtube.videos().list(
                    part="snippet,localizations", id=",".join(vid for _path, vid in chunk), maxResults=BATCH,
                ).execute()
            except Exception as exc:  # noqa: BLE001
                print(f"[handles] {channel}: could not read {len(chunk)} videos ({type(exc).__name__})")
                counts["left"] += len(chunk)
                stopped = True
                continue
            live = {item.get("id"): item for item in listed.get("items", [])}
            for path, video_id in chunk:
                video = live.get(video_id)
                if video is None:
                    # Deleted, or not this account's to read. Left unstamped: the
                    # next look costs a fiftieth of a unit and may find it again.
                    counts["not_found"] += 1
                    continue
                body = corrected_body(video, retired, current)
                if body is None:
                    counts["already_right"] += 1
                    if apply:
                        stamp(path, STAMP, current)
                    continue
                if not apply:
                    counts["would_correct"] += 1
                    continue
                if stopped or budget <= 0:
                    counts["left"] += 1
                    continue
                parts = "snippet,localizations" if "localizations" in body else "snippet"
                try:
                    answer = youtube.videos().update(part=parts, body=body).execute()
                except Exception as exc:  # noqa: BLE001
                    text = str(exc)
                    if "quota" in text.lower() or "rateLimitExceeded" in text:
                        print(f"[handles] {channel}: YouTube quota reached; the rest waits for the next run")
                        stopped = True
                        counts["left"] += 1
                    else:
                        print(f"[handles] {channel}: {video_id} was refused ({type(exc).__name__})")
                        counts["failed"] += 1
                    continue
                budget -= 1
                if still_broken(answer or {}, retired):
                    # YouTube accepted the write and still shows the old name:
                    # do not stamp, so the next run looks at it again.
                    counts["failed"] += 1
                    continue
                stamp(path, STAMP, current)
                counts["corrected"] += 1
    return report


def sentence(channel: str, counts: dict[str, int], apply: bool) -> str:
    """One plain line per channel for the run's annotations."""
    handle = get_channel(channel).handle
    if counts["no_credentials"]:
        return f"{counts['pending']} videos not checked: this run has no sign-in for the channel"
    parts = []
    if apply:
        parts.append(f"{counts['corrected']} descriptions now link to {handle}")
    else:
        parts.append(f"{counts['would_correct']} descriptions would be corrected to {handle} (dry run)")
    parts.append(f"{counts['already_right']} already right")
    if counts["left"]:
        parts.append(f"{counts['left']} left for the next run")
    if counts["not_found"]:
        parts.append(f"{counts['not_found']} not found on the channel")
    if counts["failed"]:
        parts.append(f"{counts['failed']} refused or unchanged after the write")
    return "; ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="rewrite descriptions and stamp receipts")
    args = parser.parse_args(argv)
    try:
        limit = int(os.environ.get("LIVE_HANDLE_MAX_UPDATES", DEFAULT_MAX_UPDATES))
    except ValueError:
        limit = DEFAULT_MAX_UPDATES
    try:
        report = repair(apply=args.apply, max_updates=limit)
    except Exception as exc:  # noqa: BLE001 - never cost the caller its other work
        print(f"::warning title=Live handle repair::stopped early ({type(exc).__name__})")
        return 0
    if not report:
        print("[handles] every published video is stamped with its channel's handle; nothing to do.")
        return 0
    for channel, counts in report.items():
        level = "warning" if counts["failed"] or counts["no_credentials"] else "notice"
        print(f"::{level} title=Live handle repair {channel}::{sentence(channel, counts, args.apply)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
