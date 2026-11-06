"""Idempotently retrofit published live channel videos with Selar sanctuary links & SEO metadata.

Uses `pipeline.upload.update_live_video_metadata` (`videos.list` -> merge -> `videos.update`)
so omitted `snippet` fields (`tags`, `categoryId`, `defaultLanguage`, `defaultAudioLanguage`)
are never wiped by YouTube Data API v3, and stamps `metadata_revision: "selar-seo-v1"` on each
updated receipt in `content/published/*.md` so subsequent runs spend 0 API quota units.

Usage:
  PYTHONPATH=. python scripts/retrofit_published_metadata.py --dry-run
  PYTHONPATH=. python scripts/retrofit_published_metadata.py --sync-pending
  PYTHONPATH=. python scripts/retrofit_published_metadata.py --apply --force
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from pipeline.channels import channel_for_doc, get_channel
from pipeline.config import CONFIG, REPO_ROOT
from pipeline.localize_metadata import build_metadata_localizations
from pipeline.metadata import (
    build_description,
    build_tags,
    is_faith_doc,
    smart_truncate_title,
)
from pipeline.quota_handler import QuotaExceededError
from pipeline.script_doc import parse_script
from pipeline.shorts_bridge import enrich_short_description_with_bridge
from pipeline.upload import update_live_video_metadata
from scripts.sync_published_thumbnails import stamp_frontmatter_field

PUBLISHED_DIR = REPO_ROOT / "content" / "published"
METADATA_REVISION = "selar-seo-v1"

# Clean non-truncated, mobile-optimised titles for pre-PR-#230 published videos.
# 0008 is a 40s blessing clip and explicitly keeps "(Brief Blessing)".
TITLE_FIXES: dict[str, str] = {
    "0008": "Psalm 91 Night Prayer Before You Sleep (Brief Blessing)",
    "0010": "Psalm 121 Night Prayer for Sleep & Peace | He Never Slumbers",
    "0013": "Psalm 46 Night Prayer for Sleep & Peace | Be Still & Know",
    "0018": "Psalm 3:3-5 Night Prayer for Sleep & Peace | Lift My Head",
}


def _has_youtube_credentials() -> bool:
    return bool(
        (CONFIG.youtube_client_id or "").strip()
        and (CONFIG.youtube_client_secret or "").strip()
        and (CONFIG.youtube_refresh_token or "").strip()
    )


def collect_published_faith_targets(
    published_dir: Path | None = None,
    only_pending: bool = False,
) -> list[dict]:
    directory = published_dir or PUBLISHED_DIR
    targets: list[dict] = []
    if not directory.is_dir():
        return targets

    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = re.search(r"youtube_video_id:\s*[\"']?([A-Za-z0-9_-]{11})[\"']?", raw)
        if not m:
            continue
        video_id = m.group(1)
        doc = parse_script(path)
        if not is_faith_doc(doc):
            continue
        if str(doc.meta.get("youtube_status", "")).strip() == "deleted_or_missing":
            continue
        if only_pending and str(doc.meta.get("metadata_revision", "")).strip() == METADATA_REVISION:
            continue

        is_short = doc.format == "short" or "short-" in path.name
        clean_title = TITLE_FIXES.get(str(doc.id), smart_truncate_title(doc.title, 95))
        if is_short:
            short_key_match = re.search(r"psalm-(\d+)", path.name)
            short_key = f"short-psalm{short_key_match.group(1)}" if short_key_match else doc.slug
            base_desc = doc.full_narration.split("## Custom Thumbnail")[0].strip() or build_description(doc)
            desc = enrich_short_description_with_bridge(base_desc, short_key)
        else:
            desc = build_description(doc)

        tags = build_tags(doc)
        locs = build_metadata_localizations(clean_title, desc, "faith and prayer")
        targets.append(
            {
                "path": path,
                "file": path.name,
                "id": doc.id,
                "video_id": video_id,
                "is_short": is_short,
                # Which token may touch this video. Same defect as the thumbnail
                # sync: one global token repaired both channels, so every Morning
                # Altar video answered 403 to The Secret Place's account.
                "channel": channel_for_doc(doc.meta),
                "title": clean_title,
                "description": desc,
                "tags": tags,
                "localizations": locs,
            }
        )
    return targets


def sync_published_metadata(
    published_dir: Path | None = None,
    only_pending: bool = True,
    dry_run: bool = False,
    updater=update_live_video_metadata,
) -> list[dict]:
    targets = collect_published_faith_targets(
        published_dir=published_dir,
        only_pending=only_pending,
    )
    if not targets:
        print(f"[retrofit] All live faith videos are already at {METADATA_REVISION}.")
        return []

    if not dry_run and updater is update_live_video_metadata and not _has_youtube_credentials():
        print("[retrofit] Skipped: YouTube OAuth credentials not present in environment.")
        return []

    clients: dict[str, Any] = {}

    def _client_for(channel_id: str):
        """One authenticated client per channel, built from that channel's secrets."""
        if channel_id not in clients:
            from scripts.sync_published_thumbnails import _build_youtube_client

            clients[channel_id] = _build_youtube_client(get_channel(channel_id))
        return clients[channel_id]

    outcomes: list[dict] = []
    for t in targets:
        summary = {
            "file": t["file"],
            "video_id": t["video_id"],
            "title": t["title"],
            "desc_bytes": len(t["description"].encode("utf-8")),
            "tag_count": len(t["tags"]),
            "status": "dry_run" if dry_run else "pending",
        }
        print(
            f"  • {t['file']} ({t['video_id']}) -> title='{t['title']}' ({len(t['title'])}c), "
            f"desc={summary['desc_bytes']}B, tags={summary['tag_count']}"
        )
        if not dry_run:
            try:
                # The token that owns this video, not whichever one CONFIG holds.
                extra = ({} if updater is not update_live_video_metadata
                         else {"youtube": _client_for(t.get("channel") or CONFIG.channel_id)})
                updater(
                    t["video_id"],
                    new_title=t["title"],
                    new_description=t["description"],
                    new_tags=t["tags"],
                    localizations=t["localizations"],
                    **extra,
                )
                stamp_frontmatter_field(t["path"], "metadata_revision", METADATA_REVISION)
                summary["status"] = "updated"
                print(f"::notice title=Live metadata sync::{json.dumps(summary)}")
            except QuotaExceededError as exc:
                summary["status"] = "quota_deferred"
                print(f"[retrofit] YouTube quota limit reached; deferring remaining videos until next reset: {exc}")
                outcomes.append(summary)
                break
            except Exception as exc:  # noqa: BLE001
                err_txt = str(exc)
                if "not found" in err_txt.lower() or "404" in err_txt:
                    stamp_frontmatter_field(t["path"], "youtube_status", "deleted_or_missing")
                    stamp_frontmatter_field(t["path"], "metadata_revision", METADATA_REVISION)
                    summary["status"] = "video_not_found"
                else:
                    summary["status"] = f"error: {err_txt[:160]}"
                    print(f"[retrofit] Could not update {t['video_id']}: {exc!r}")
        outcomes.append(summary)
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Execute live videos.update calls")
    parser.add_argument("--sync-pending", action="store_true", help="Idempotently update receipts missing metadata_revision")
    parser.add_argument("--force", action="store_true", help="Re-apply even when metadata_revision matches")
    parser.add_argument("--dry-run", action="store_true", help="Preview payloads without API writes")
    args = parser.parse_args(argv)

    dry = bool(args.dry_run or (not args.apply and not args.sync_pending) or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"})
    only_pending = bool(args.sync_pending and not args.force)
    sync_published_metadata(only_pending=only_pending, dry_run=dry)
    if dry:
        print("[retrofit] Dry-run complete (pass --apply or --sync-pending to push updates to YouTube).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
