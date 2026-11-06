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

from pipeline.channels import CHANNELS, channel_for_doc, get_channel
from pipeline.config import CONFIG, OUTPUT_DIR, PUBLISHED_DIR
from pipeline.script_doc import parse_script
from pipeline.thumbnail_ctr import (
    THUMBNAIL_REVISION,
    curated_backdrop_for,
    generate_ctr_pack,
)
from pipeline.upload import set_video_thumbnail

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
    channel_id: str | None = None,
) -> list[tuple[Path, Any]]:
    """Return `(path, ScriptDoc)` for published longform jobs needing thumbnail sync.

    ``channel_id`` restricts the scan to one channel's receipts. It is not
    optional bookkeeping: each channel has its own OAuth token, and a token can
    only touch its own channel's videos, so repairing The Morning Altar with
    The Secret Place's credentials fails with 403 (and vice versa).
    """
    pending: list[tuple[Path, Any]] = []
    want = str(channel_id).strip().lower() if channel_id else ""
    if not published_dir.is_dir():
        return pending
    for path in sorted(published_dir.glob("*.md")):
        try:
            doc = parse_script(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[thumb-sync] skip unreadable {path.name}: {exc}")
            continue
        if want and channel_for_doc(doc.meta) != want:
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


def _channel_credentials(profile) -> tuple[str, str, str]:
    """(client_id, client_secret, refresh_token) for one channel, from its env names."""
    names = profile.secret_names()
    return (
        os.environ.get(names["client_id"], "").strip(),
        os.environ.get(names["client_secret"], "").strip(),
        os.environ.get(names["refresh_token"], "").strip(),
    )


def _has_youtube_credentials(profile=None) -> bool:
    profile = profile or get_channel(CONFIG.channel_id)
    return all(_channel_credentials(profile))


def _build_youtube_client(profile=None):
    """A YouTube client authorized as `profile`'s channel (never anyone else's)."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    from pipeline.upload import SCOPES

    profile = profile or get_channel(CONFIG.channel_id)
    client_id, client_secret, refresh_token = _channel_credentials(profile)
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _setter_for(youtube) -> Any:
    """A `thumbnails.set` caller bound to one channel's authenticated client."""
    from pipeline.upload import _api_error_text, diagnose_thumbnail_refusal

    def _set(video_id: str, thumbnail_path: Path) -> str:
        from googleapiclient.http import MediaFileUpload

        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
            ).execute()
            return "ok"
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {_api_error_text(exc)}"
            diagnosis = diagnose_thumbnail_refusal(video_id, youtube=youtube)
            if diagnosis:
                msg += " | " + "; ".join(f"{k}={v}" for k, v in diagnosis.items())
            return msg[:900]

    return _set


def sync_published_thumbnails(
    published_dir: Path = PUBLISHED_DIR,
    out_root: Path = OUTPUT_DIR / "live-thumb-sync",
    force: bool = False,
    dry_run: bool = False,
    youtube_client: Any = None,
    thumb_setter=None,
    channel: str | None = None,
) -> list[dict[str, Any]]:
    """Render and apply cinema thumbnails (+ privacy/title hygiene) for live videos.

    Only the receipts belonging to `channel` (default: the run's CHANNEL_ID) are
    touched, and only that channel's OAuth token is used — a token can repair its
    own channel and nothing else.
    """
    profile = get_channel(channel or CONFIG.channel_id)
    pending = collect_pending_receipts(
        published_dir=published_dir, force=force, channel_id=profile.id
    )
    if not pending:
        print(f"[thumb-sync] {profile.id}: all published long-form videos are at "
              f"{THUMBNAIL_REVISION}")
        return []

    if not dry_run and youtube_client is None and not _has_youtube_credentials(profile):
        print(f"[thumb-sync] {profile.id}: skipped — this channel's YouTube OAuth "
              f"secrets ({profile.secret_names()['client_id']} / _SECRET / "
              f"_REFRESH_TOKEN) are not present in the environment. The videos stay "
              f"marked thumbnail_pending, so the next monitor pass retries them.")
        return []

    yt = None if dry_run else (youtube_client or _build_youtube_client(profile))
    # The setter must use *this* channel's client. It defaulted to
    # `pipeline.upload.set_video_thumbnail`, which builds its own client from the
    # global CONFIG — The Secret Place's token. So every Morning Altar receipt was
    # thumbnailed by The Secret Place's account and answered `403 forbidden`, and
    # the reason was unknowable from the message: the videos.list audit above used
    # the right client, only the write did not. Diagnosed 09:15Z 6 Nov:
    # auth_channel_id=UCtPI1r8vgtJ9n__7ksLBmCA (Secret Place) vs
    # video_channel_id=UCOaC5VWBGxA-UpOjP5bvkUQ (Morning Altar), same_channel=False.
    if thumb_setter is None:
        thumb_setter = _setter_for(yt) if yt is not None else set_video_thumbnail
    remote_by_id: dict[str, dict[str, Any]] = {}
    videos_list_ok = False
    if yt is not None:
        vids = [str(doc.meta.get("youtube_video_id")).strip() for _, doc in pending]
        try:
            resp = (
                yt.videos()
                .list(part="snippet,status,contentDetails", id=",".join(vids[:50]))
                .execute()
            )
            videos_list_ok = True
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
            if videos_list_ok and remote is None:
                row["thumbnail_status"] = "video_not_found"
                stamp_frontmatter_field(path, "youtube_status", "deleted_or_missing")
                stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
            else:
                status = thumb_setter(vid, primary.path)
                row["thumbnail_status"] = status
                if status == "ok":
                    stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
                    stamp_frontmatter_field(path, "thumbnail_pending", False)
                elif "HttpError 404" in str(status):
                    stamp_frontmatter_field(path, "youtube_status", "deleted_or_missing")
                    stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
                    stamp_frontmatter_field(path, "thumbnail_pending", False)
                else:
                    # Still not fixed. Say so, keep it queued for the next pass, and
                    # put the API's own words in the frontmatter — "no thumbnail"
                    # with no reason is what made this invisible for two videos.
                    stamp_frontmatter_field(path, "thumbnail_pending", True)
                    # Long enough to keep the diagnosis (`same_channel=`, `upload_status=`)
                    # that explains *why* the refusal happened.
                    stamp_frontmatter_field(path, "thumbnail_error", str(status)[:900])
                    print(f"::warning title=Thumbnail still refused "
                          f"({profile.id})::{vid} — {status}. The receipt keeps "
                          f"thumbnail_pending: true and the next monitor pass retries "
                          f"it (50 quota units per attempt).")
        print(f"::notice title=Live thumbnail sync::{json.dumps(row)}")
        results.append(row)

    return results


def sync_all_channels(force: bool = False, dry_run: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Repair every channel, each with its own credentials.

    One channel's failure must never silence the other's repair — the two pools
    are separate, so a 403 on one says nothing about the other.
    """
    results: dict[str, list[dict[str, Any]]] = {}
    for cid in sorted(CHANNELS):
        try:
            results[cid] = sync_published_thumbnails(
                force=force, dry_run=dry_run, channel=cid
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[thumb-sync] {cid}: aborted — {exc!r}")
            results[cid] = [{"id": "-", "thumbnail_status": f"error: {exc}"[:220]}]
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync repaired thumbnails to live published videos.")
    parser.add_argument("--force", action="store_true", help="Re-apply even when thumbnail_revision matches")
    parser.add_argument("--dry-run", action="store_true", help="Render locally without calling YouTube")
    parser.add_argument("--channel", default="", help="Channel to repair (default: the run's CHANNEL_ID)")
    parser.add_argument("--all-channels", action="store_true",
                        help="Repair every registered channel with its own credentials")
    args = parser.parse_args(argv)
    dry = args.dry_run or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    if args.all_channels:
        results = sync_all_channels(force=args.force, dry_run=dry)
        for cid, rows in results.items():
            fixed = sum(1 for r in rows if r.get("thumbnail_status") == "ok")
            print(f"[thumb-sync] {cid}: {fixed}/{len(rows)} thumbnail(s) applied")
        return 0
    sync_published_thumbnails(force=args.force, dry_run=dry, channel=args.channel or None)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
