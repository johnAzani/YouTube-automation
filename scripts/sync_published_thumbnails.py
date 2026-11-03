"""Idempotent live-channel thumbnail & metadata repair for published long-form videos.

Why this exists
---------------
Code fixes in `pipeline/thumbnail_ctr.py` only improve *future* uploads unless the
already-live videos on YouTube are updated via `thumbnails.set`. Each receipt in
`content/published/*.md` is stamped with `thumbnail_revision` once its repaired
cinema thumbnail (and any privacy / short-teaser title correction) is confirmed by
the YouTube Data API, so subsequent monitor runs spend 0 API quota units.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from pipeline.config import CONFIG, OUTPUT_DIR, PUBLISHED_DIR
from pipeline.script_doc import parse_script
from pipeline.thumbnail_ctr import curated_backdrop_for, generate_ctr_pack
from pipeline.upload import _credentials, set_video_thumbnail

THUMBNAIL_REVISION = "ctr-v3-cinema"

# Curated 3-word mobile-maximised hooks for the initial published prayers so we do
# not have to alter historical frontmatter that existing unit tests assert against.
LIVE_HERO_OVERRIDES: dict[str, str] = {
    "0008": "UNDER HIS WINGS",
    "0009": "RESTORE MY SOUL",
    "0010": "HE NEVER SLEEPS",
    "0013": "BE STILL AND KNOW",
    "0018": "LIFT MY HEAD",
}


def parse_iso8601_duration(iso_dur: str) -> int:
    """Convert YouTube ISO-8601 duration (e.g. 'PT5M34S', 'PT40S', 'PT1H2M3S') to seconds."""
    m = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        (iso_dur or "").strip().upper(),
    )
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def stamp_frontmatter_field(path: Path, key: str, value: str) -> None:
    """Insert or update a top-level scalar field in a Markdown receipt's YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not m:
        raise ValueError(f"{path}: missing YAML frontmatter")
    metadata = m.group(1)
    line = f"{key}: {json.dumps(value)}"
    pattern = rf"(?m)^{re.escape(key)}\s*:.*$"
    if re.search(pattern, metadata):
        metadata = re.sub(pattern, line, metadata, count=1)
    else:
        metadata += f"\n{line}"
    updated = f"---\n{metadata}\n---{m.group('tail')}"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(updated, encoding="utf-8")
    tmp.replace(path)


def collect_pending_receipts(
    published_dir: Path = PUBLISHED_DIR,
    force: bool = False,
) -> list[tuple[Path, Any]]:
    """Return `(path, ScriptDoc)` for published longform jobs needing thumbnail sync."""
    pending: list[tuple[Path, Any]] = []
    if not published_dir.is_dir():
        return pending
    for path in sorted(published_dir.glob("*.md")):
        try:
            doc = parse_script(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[thumb-sync] skip unreadable {path.name}: {exc}")
            continue
        fmt = str(getattr(doc, "format", "") or doc.meta.get("format", "")).strip().lower()
        vid = str(doc.meta.get("youtube_video_id", "") or "").strip()
        if fmt != "longform" or not vid:
            continue
        rev = str(doc.meta.get("thumbnail_revision", "") or "").strip()
        if not force and rev == THUMBNAIL_REVISION:
            continue
        pending.append((path, doc))
    return pending


def _has_youtube_credentials() -> bool:
    return bool(
        (CONFIG.youtube_client_id or "").strip()
        and (CONFIG.youtube_client_secret or "").strip()
        and (CONFIG.youtube_refresh_token or "").strip()
    )


def _build_youtube_client():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def sync_published_thumbnails(
    published_dir: Path = PUBLISHED_DIR,
    out_root: Path = OUTPUT_DIR / "live-thumb-sync",
    force: bool = False,
    dry_run: bool = False,
    youtube_client: Any = None,
    thumb_setter=set_video_thumbnail,
) -> list[dict[str, Any]]:
    """Render and apply cinema thumbnails (+ privacy/title hygiene) for live videos."""
    pending = collect_pending_receipts(published_dir=published_dir, force=force)
    if not pending:
        print(f"[thumb-sync] all published long-form videos are at {THUMBNAIL_REVISION}")
        return []

    if not dry_run and youtube_client is None and not _has_youtube_credentials():
        print("[thumb-sync] skipped: YouTube OAuth credentials not present in environment")
        return []

    yt = None if dry_run else (youtube_client or _build_youtube_client())
    remote_by_id: dict[str, dict[str, Any]] = {}
    if yt is not None:
        vids = [str(doc.meta.get("youtube_video_id")).strip() for _, doc in pending]
        try:
            resp = (
                yt.videos()
                .list(part="snippet,status,contentDetails", id=",".join(vids[:50]))
                .execute()
            )
            for item in resp.get("items", []):
                if item.get("id"):
                    remote_by_id[str(item["id"])] = item
        except Exception as exc:  # noqa: BLE001
            print(f"[thumb-sync] warning: videos.list audit failed: {exc!r}")

    results: list[dict[str, Any]] = []
    for path, doc in pending:
        vid = str(doc.meta.get("youtube_video_id")).strip()
        doc_key = str(doc.id or doc.slug)
        hero = LIVE_HERO_OVERRIDES.get(doc_key) or str(doc.meta.get("thumb_text") or "").strip() or doc.title
        plate = curated_backdrop_for(doc_key)
        reports = generate_ctr_pack(
            out_root / doc_key,
            hero_override=hero,
            doc_key=doc_key,
            backdrop=plate,
        )
        primary = reports[0]
        row: dict[str, Any] = {
            "id": doc_key,
            "video_id": vid,
            "hero": primary.hero,
            "hero_px": primary.hero_px,
            "contrast": round(primary.contrast, 2),
            "backdrop": primary.backdrop,
            "thumbnail_status": "dry_run" if dry_run else "pending",
            "privacy_updated": False,
            "title_updated": False,
        }

        remote = remote_by_id.get(vid)
        if remote is not None:
            st = remote.get("status", {})
            sn = remote.get("snippet", {})
            cd = remote.get("contentDetails", {})
            dur_iso = str(cd.get("duration") or "")
            dur_sec = parse_iso8601_duration(dur_iso)
            live_priv = str(st.get("privacyStatus") or "")
            up_status = str(st.get("uploadStatus") or "")
            live_title = str(sn.get("title") or "")
            row.update(duration_seconds=dur_sec, live_privacy=live_priv, live_title=live_title)

            # 1. Promote valid full-length prayers (>= 3 min) stuck non-public when receipt wants public.
            desired_priv = str(doc.meta.get("privacy") or "public").strip().lower()
            if (
                not dry_run
                and yt is not None
                and desired_priv == "public"
                and dur_sec >= 180
                and up_status == "processed"
                and live_priv in {"private", "unlisted"}
            ):
                try:
                    yt.videos().update(
                        part="status",
                        body={
                            "id": vid,
                            "status": {
                                "privacyStatus": "public",
                                "selfDeclaredMadeForKids": bool(st.get("selfDeclaredMadeForKids", False)),
                            },
                        },
                    ).execute()
                    row["privacy_updated"] = True
                    row["live_privacy"] = "public"
                    print(f"[thumb-sync] promoted {doc_key} ({vid}, {dur_sec}s) from {live_priv} -> public")
                except Exception as exc:  # noqa: BLE001
                    print(f"[thumb-sync] could not promote {vid} to public: {exc!r}")

            # 2. Honest title on legacy sub-90s teaser upload (0008) claiming "Complete Prayer".
            if (
                not dry_run
                and yt is not None
                and 0 < dur_sec < 90
                and "complete prayer" in live_title.lower()
            ):
                honest_title = re.sub(
                    r"(?i)\b(?:the\s+)?complete\s+prayer\b",
                    "Night Prayer",
                    live_title,
                )
                if "brief" not in honest_title.lower() and len(honest_title) <= 82:
                    if " | The Secret Place" in honest_title:
                        honest_title = honest_title.replace(
                            " | The Secret Place",
                            " (Brief Blessing) | The Secret Place",
                        )
                    else:
                        honest_title = f"{honest_title} (Brief Blessing)"
                honest_title = honest_title[:100]
                if honest_title != live_title:
                    try:
                        snippet_body: dict[str, Any] = {
                            "title": honest_title,
                            "description": sn.get("description", ""),
                            "categoryId": str(sn.get("categoryId") or "27"),
                        }
                        if sn.get("tags"):
                            snippet_body["tags"] = sn["tags"]
                        if sn.get("defaultLanguage"):
                            snippet_body["defaultLanguage"] = sn["defaultLanguage"]
                        yt.videos().update(
                            part="snippet",
                            body={"id": vid, "snippet": snippet_body},
                        ).execute()
                        row["title_updated"] = True
                        row["live_title"] = honest_title
                        print(f"[thumb-sync] clarified short clip title on {vid} ({dur_sec}s) -> {honest_title!r}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[thumb-sync] could not clarify title on {vid}: {exc!r}")

        if not dry_run:
            status = thumb_setter(vid, primary.path)
            row["thumbnail_status"] = status
            if status == "ok":
                stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
        print(f"::notice title=Live thumbnail sync::{json.dumps(row)}")
        results.append(row)

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync repaired thumbnails to live published videos.")
    parser.add_argument("--force", action="store_true", help="Re-apply even when thumbnail_revision matches")
    parser.add_argument("--dry-run", action="store_true", help="Render locally without calling YouTube")
    args = parser.parse_args(argv)
    dry = args.dry_run or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    sync_published_thumbnails(force=args.force, dry_run=dry)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
