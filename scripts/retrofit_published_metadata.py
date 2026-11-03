"""Safely retrofit already-published live channel videos with Selar sanctuary links & clean metadata.

Uses `pipeline.upload.update_live_video_metadata` (`videos.list` -> merge -> `videos.update`)
so omitted `snippet` fields (`tags`, `categoryId`, `defaultLanguage`, `defaultAudioLanguage`)
are never wiped by YouTube Data API v3.

Usage:
  PYTHONPATH=. python scripts/retrofit_published_metadata.py --dry-run
  PYTHONPATH=. python scripts/retrofit_published_metadata.py --apply
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from pipeline.config import REPO_ROOT
from pipeline.localize_metadata import build_metadata_localizations
from pipeline.metadata import (
    build_description,
    build_tags,
    is_faith_doc,
    smart_truncate_title,
)
from pipeline.script_doc import parse_script
from pipeline.upload import update_live_video_metadata

PUBLISHED_DIR = REPO_ROOT / "content" / "published"

# Clean non-truncated title upgrades for live videos whose original titles exceeded 95 chars
TITLE_FIXES: dict[str, str] = {
    "0010": "Psalm 121 Night Prayer for Sleep & Peace | He Never Slumbers",
}


def collect_published_faith_targets() -> list[dict]:
    targets: list[dict] = []
    for path in sorted(PUBLISHED_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = re.search(r"youtube_video_id:\s*[\"']?([A-Za-z0-9_-]{11})[\"']?", raw)
        if not m:
            continue
        video_id = m.group(1)
        doc = parse_script(path)
        if not is_faith_doc(doc):
            continue
        is_short = doc.format == "short" or "short-" in path.name
        clean_title = TITLE_FIXES.get(str(doc.id), smart_truncate_title(doc.title, 95))
        desc = build_description(doc)
        tags = build_tags(doc)
        locs = build_metadata_localizations(clean_title, desc, "faith and prayer")
        targets.append(
            {
                "file": path.name,
                "id": doc.id,
                "video_id": video_id,
                "is_short": is_short,
                "title": clean_title,
                "description": desc,
                "tags": tags,
                "localizations": locs,
            }
        )
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Execute live videos.update calls")
    parser.add_argument("--dry-run", action="store_true", help="Preview payloads without API writes")
    args = parser.parse_args(argv)

    apply_live = bool(args.apply and not args.dry_run)
    targets = collect_published_faith_targets()
    print(f"[retrofit] Found {len(targets)} published faith video(s) with YouTube IDs.")

    for t in targets:
        print(
            f"  • {t['file']} ({t['video_id']}) -> title='{t['title']}' ({len(t['title'])}c), "
            f"desc={len(t['description'].encode('utf-8'))}B, tags={len(t['tags'])}"
        )
        if apply_live:
            update_live_video_metadata(
                t["video_id"],
                new_title=t["title"],
                new_description=t["description"],
                new_tags=t["tags"],
                localizations=t["localizations"],
            )
            print(f"    [updated] {t['video_id']}")

    if not apply_live:
        print("[retrofit] Dry-run complete (pass --apply to push updates to YouTube).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
