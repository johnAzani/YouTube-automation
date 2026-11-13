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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipeline.channels import CHANNELS, channel_for_doc, get_channel
from pipeline.config import CONFIG, OUTPUT_DIR, PUBLISHED_DIR
from pipeline.script_doc import parse_script
from pipeline.shorts_poster import (
    POSTER_REVISION as SHORTS_POSTER_REVISION,
    PosterRefused,
    poster_for_slug,
    render_shorts_poster,
)
from pipeline.thumbnail_ctr import (
    THUMBNAIL_REVISION,
    curated_backdrop_for,
    generate_ctr_pack,
)
from pipeline.upload import apply_shorts_thumbnail, set_video_thumbnail

#: Stop retrying other repeated Shorts failures after five attempts. Permission
#: failures remain retryable: verification may happen after the fifth attempt.
SHORTS_MAX_ATTEMPTS = 5

#: Permission failures can clear after channel verification; retry at most once
#: per week per receipt indefinitely, rather than on every monitor run.
THUMBNAIL_PERMISSION_COOLDOWN_HOURS = 7 * 24

#: Back off on uploadRateLimitExceeded and preserve the whole channel's quota.
THUMBNAIL_RATE_LIMIT_COOLDOWN_HOURS = 6


def _cooldown_active(meta: dict[str, Any], now: datetime | None = None) -> str | None:
    raw = str(meta.get("thumbnail_retry_after") or "").strip()
    if not raw:
        return None
    try:
        until = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    return raw if until > ref else None


def _is_thumbnail_rate_limited(status: Any) -> bool:
    low = str(status or "").lower()
    return "uploadratelimitexceeded" in low or "uploaded too many thumbnails" in low


def _is_permission_refusal(status: Any) -> bool:
    """Recognize a possible permission/eligibility refusal, not a quota error.

    A 403 does not prove phone verification is the cause: it can also mean
    missing OAuth scopes, the wrong account or a YouTube policy restriction.
    """
    low = str(status or "").lower()
    if _is_thumbnail_rate_limited(low) or any(
        term in low for term in ("quotaexceeded", "ratelimitexceeded", "dailylimitexceeded")
    ):
        return False
    return any(term in low for term in (
        "[forbidden]", "403", "insufficientpermissions", "insufficient permission",
        "doesn't have permissions", "does not have permission", "not authorized",
    ))


def _permission_retry_allowed(meta: dict[str, Any]) -> bool:
    return bool(meta.get("thumbnail_pending")) and _is_permission_refusal(meta.get("thumbnail_error"))


def _wait_for_retry(meta: dict[str, Any], retry_permission: bool) -> str | None:
    until = _cooldown_active(meta)
    if until and retry_permission and meta.get("thumbnail_retry_reason") == "permission":
        return None
    return until

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


def clear_frontmatter_field(path: Path, key: str) -> None:
    """Remove a top-level field from a receipt's frontmatter (idempotent).

    Used when a failure is repaired: a receipt that says `thumbnail_pending: false`
    beside a 403 sentence describes two different days at once, and the next reader
    cannot tell which one is true.
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not m:
        return
    metadata = re.sub(rf"(?m)^{re.escape(key)}\s*:.*\n?", "", m.group(1))
    path.write_text(f"---\n{metadata}\n---{m.group('tail')}", encoding="utf-8")


def stamp_frontmatter_field(path: Path, key: str, value: str, raw: bool = False) -> None:
    """Insert or update a top-level field in a Markdown receipt's YAML frontmatter.

    Values are JSON-quoted by default, which is exactly right for scalars and wrong
    for a list: `thumbnail_poster` must read as `["PSALM 91", ...]` in the receipt,
    not as a quoted blob of JSON, so lists pass `raw=True` with YAML flow syntax.
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not m:
        raise ValueError(f"{path}: missing YAML frontmatter")
    metadata = m.group(1)
    line = f"{key}: {value if raw else json.dumps(value)}"
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
    retry_permission: bool = False,
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
        if retry_permission and not _permission_retry_allowed(doc.meta):
            continue
        if not force and rev == THUMBNAIL_REVISION and not doc.meta.get("thumbnail_pending"):
            continue
        if not force:
            wait_until = _wait_for_retry(doc.meta, retry_permission)
            if wait_until:
                print(f"[thumb-sync] skip {path.name}: thumbnail retry cooldown until {wait_until}")
                continue
        pending.append((path, doc))
    return pending


def collect_pending_short_receipts(
    published_dir: Path = PUBLISHED_DIR,
    force: bool = False,
    channel_id: str | None = None,
    retry_permission: bool = False,
) -> list[tuple[Path, Any]]:
    """Return `(path, ScriptDoc)` for published Shorts whose poster is not confirmed.

    Shorts were excluded here by `fmt != "longform"`, which is the second half of
    the reason nine live Shorts carry an auto-grabbed frame: the release path never
    asked YouTube for a thumbnail, and the only repair pass that could have fixed
    it on a later run skipped them by format. thumbnails.set has supported Shorts
    since 2026-11-03, so a Short is now repairable exactly like a long-form video.
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
        if fmt != "short" or not vid:
            continue
        rev = str(doc.meta.get("thumbnail_revision", "") or "").strip()
        permission_pending = _permission_retry_allowed(doc.meta)
        if retry_permission and not permission_pending:
            continue
        if not force and rev == SHORTS_POSTER_REVISION and not doc.meta.get("thumbnail_pending"):
            continue
        try:
            attempts = int(doc.meta.get("thumbnail_attempts") or 0)
        except (TypeError, ValueError):
            attempts = 0
        # Permission refusals can clear after verification, even after five old
        # failures. Other persistent failures still stop at the existing cap.
        if (not force and attempts >= SHORTS_MAX_ATTEMPTS and not permission_pending
                and not _is_thumbnail_rate_limited(doc.meta.get("thumbnail_error"))):
            print(f"[thumb-sync] skip {path.name}: {attempts} failed Shorts thumbnail "
                  f"attempts (last: {str(doc.meta.get('thumbnail_error') or '')[:120]!r}); "
                  f"run with --force to retry")
            continue
        if not force:
            wait_until = _wait_for_retry(doc.meta, retry_permission)
            if wait_until:
                print(f"[thumb-sync] skip {path.name}: thumbnail retry cooldown until {wait_until}")
                continue
        pending.append((path, doc))
    return pending


def _shorts_poster_for(doc, out_path: Path, channel_id: str):
    """Rebuild a live Short's poster: receipt copy first, then its spec.

    Receipts from 2026-11-07 onward carry the authored lockup, so a repair never
    depends on the queue still holding the manifest. Older receipts fall back to
    the spec the slug names, which every published Short in this repo still has.
    """
    lines = doc.meta.get("thumbnail_poster")
    if isinstance(lines, str) and lines.strip().startswith("["):
        try:
            lines = json.loads(lines)
        except ValueError:
            lines = None
    if isinstance(lines, (list, tuple)) and len(lines) >= 2:
        return render_shorts_poster(
            out_path,
            lines=[str(x) for x in lines][:4],
            kicker=str(doc.meta.get("thumbnail_kicker") or "") or None,
            channel_id=channel_id,
            plate=str(doc.meta.get("thumbnail_plate") or "") or None,
        )
    report = poster_for_slug(str(doc.slug or doc.id or ""), out_path, channel_id=channel_id)
    if report is not None:
        return report
    from pipeline.shorts_poster import lines_from_title

    h1, h2, sub, tag = lines_from_title(str(doc.title or ""), "")
    return render_shorts_poster(out_path, lines=(h1, h2, sub, tag), channel_id=channel_id)


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
    try:
        creds.refresh(Request())
    except Exception as exc:
        if "invalid_scope" not in str(exc).lower():
            raise
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=None,
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
    shorts_only: bool = False,
    limit: int | None = None,
    retry_permission: bool = False,
    thumbnails_only: bool = False,
) -> list[dict[str, Any]]:
    """Render and apply cinema thumbnails (+ privacy/title hygiene) for live videos.

    Only the receipts belonging to `channel` (default: the run's CHANNEL_ID) are
    touched, and only that channel's OAuth token is used — a token can repair its
    own channel and nothing else.
    """
    profile = get_channel(channel or CONFIG.channel_id)
    pending = [] if shorts_only else collect_pending_receipts(
        published_dir=published_dir, force=force, channel_id=profile.id,
        retry_permission=retry_permission,
    )
    pending_shorts = collect_pending_short_receipts(
        published_dir=published_dir, force=force, channel_id=profile.id,
        retry_permission=retry_permission,
    )
    if limit is not None and limit >= 0:
        pending = pending[:limit]
        pending_shorts = pending_shorts[:limit]
    if not pending and not pending_shorts:
        print(f"[thumb-sync] {profile.id}: no eligible thumbnails in this pass "
              "(pending items may still be cooling down or blocked).")
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
    channel_rate_limited_until = ""
    for path, doc in pending:
        vid = str(doc.meta.get("youtube_video_id")).strip()
        doc_key = str(doc.id or doc.slug)
        if channel_rate_limited_until:
            stamp_frontmatter_field(path, "thumbnail_pending", True)
            stamp_frontmatter_field(path, "thumbnail_retry_after", channel_rate_limited_until)
            stamp_frontmatter_field(path, "thumbnail_retry_reason", "rate_limit")
            results.append({
                "id": doc_key,
                "video_id": vid,
                "thumbnail_status": f"deferred_rate_limit_until:{channel_rate_limited_until}",
                "privacy_updated": False,
                "title_updated": False,
            })
            continue
        hero = LIVE_HERO_OVERRIDES.get(doc_key) or str(doc.meta.get("thumb_text") or "").strip() or doc.title
        plate = curated_backdrop_for(doc_key, channel_id=profile.id)
        reports = generate_ctr_pack(
            out_root / doc_key,
            hero_override=hero,
            doc_key=doc_key,
            backdrop=plate,
            channel_id=profile.id,
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
                and not thumbnails_only
                and yt is not None
                and desired_priv == "public"
                and dur_sec >= 180
                and up_status == "processed"
                and live_priv in {"private", "unlisted"}
                # Private on purpose: YouTube is holding it for its publish
                # time. scripts/confirm_scheduled_publish.py owns that video
                # (and publishes it itself if YouTube is late).
                and not st.get("publishAt")
                and str(doc.meta.get("scheduled_publish")).strip().lower() != "true"
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
                and not thumbnails_only
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
                stamp_frontmatter_field(path, "thumbnail_pending", False)
                clear_frontmatter_field(path, "thumbnail_error")
                clear_frontmatter_field(path, "thumbnail_retry_after")
                clear_frontmatter_field(path, "thumbnail_retry_reason")
            else:
                status = thumb_setter(vid, primary.path)
                row["thumbnail_status"] = status
                if status == "ok":
                    # The refusal sentence describes a failure that no longer exists.
                    clear_frontmatter_field(path, "thumbnail_error")
                    clear_frontmatter_field(path, "thumbnail_retry_after")
                    clear_frontmatter_field(path, "thumbnail_retry_reason")
                    stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
                    stamp_frontmatter_field(path, "thumbnail_pending", False)
                elif "HttpError 404" in str(status):
                    clear_frontmatter_field(path, "thumbnail_retry_after")
                    clear_frontmatter_field(path, "thumbnail_retry_reason")
                    stamp_frontmatter_field(path, "youtube_status", "deleted_or_missing")
                    stamp_frontmatter_field(path, "thumbnail_revision", THUMBNAIL_REVISION)
                    stamp_frontmatter_field(path, "thumbnail_pending", False)
                else:
                    # Still not fixed. Say so, keep it queued for the next pass, and
                    # put the API's own words in the frontmatter — "no thumbnail"
                    # with no reason is what made this invisible for two videos.
                    stamp_frontmatter_field(path, "thumbnail_pending", True)
                    stamp_frontmatter_field(path, "thumbnail_error", str(status)[:900])
                    if _is_thumbnail_rate_limited(status):
                        retry_at = (
                            datetime.now(timezone.utc)
                            + timedelta(hours=THUMBNAIL_RATE_LIMIT_COOLDOWN_HOURS)
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        channel_rate_limited_until = retry_at
                        stamp_frontmatter_field(path, "thumbnail_retry_after", retry_at)
                        stamp_frontmatter_field(path, "thumbnail_retry_reason", "rate_limit")
                        print(f"::warning title=Thumbnail rate-limited "
                              f"({profile.id})::{vid} — backing off entire channel until {retry_at} "
                              f"to preserve daily YouTube API quota.")
                    elif _is_permission_refusal(status):
                        retry_at = (datetime.now(timezone.utc) + timedelta(
                            hours=THUMBNAIL_PERMISSION_COOLDOWN_HOURS
                        )).strftime("%Y-%m-%dT%H:%M:%SZ")
                        stamp_frontmatter_field(path, "thumbnail_retry_after", retry_at)
                        stamp_frontmatter_field(path, "thumbnail_retry_reason", "permission")
                        print(f"::warning title=Thumbnail permission refused ({profile.id})::"
                              f"{vid} — pending; retry after {retry_at}. Verify channel eligibility "
                              "and OAuth permissions; a 403 alone does not prove the cause.")
                    else:
                        clear_frontmatter_field(path, "thumbnail_retry_after")
                        clear_frontmatter_field(path, "thumbnail_retry_reason")
                        print(f"::warning title=Thumbnail still refused "
                              f"({profile.id})::{vid} — {status}. The receipt keeps "
                              f"thumbnail_pending: true; later monitor passes can retry "
                              f"it (50 quota units per attempt).")
        print(f"::notice title=Live thumbnail sync::{json.dumps(row)}")
        results.append(row)

    # ---- Shorts: the same contract, at 9:16 ------------------------------- #
    for path, doc in pending_shorts:
        vid = str(doc.meta.get("youtube_video_id", "")).strip()
        doc_key = str(doc.id or doc.slug)
        if channel_rate_limited_until:
            stamp_frontmatter_field(path, "thumbnail_pending", True)
            stamp_frontmatter_field(path, "thumbnail_retry_after", channel_rate_limited_until)
            stamp_frontmatter_field(path, "thumbnail_retry_reason", "rate_limit")
            results.append({
                "id": doc_key,
                "video_id": vid,
                "format": "short",
                "thumbnail_status": f"deferred_rate_limit_until:{channel_rate_limited_until}",
            })
            continue
        row: dict[str, Any] = {"id": doc_key, "video_id": vid, "format": "short",
                               "thumbnail_status": "dry_run" if dry_run else "pending"}
        poster = None
        try:
            poster = _shorts_poster_for(doc, out_root / "shorts" / doc_key / "poster.jpg",
                                        profile.id)
            row["poster"] = poster.as_dict()
            row["contrast"] = round(poster.contrast, 2)
            row["hero_px"] = poster.hero_px
        except PosterRefused as exc:
            row["thumbnail_status"] = f"poster_refused: {exc}"
            print(f"::warning title=Shorts poster refused ({profile.id})::{doc_key} — {exc}")
            if not dry_run:
                stamp_frontmatter_field(path, "thumbnail_pending", True)
                stamp_frontmatter_field(path, "thumbnail_error", str(exc)[:900])
            results.append(row)
            continue

        if not dry_run and poster is not None:
            status = apply_shorts_thumbnail(vid, poster.path, youtube=yt)
            row["thumbnail_status"] = status
            if status == "ok":
                stamp_frontmatter_field(path, "thumbnail_revision", SHORTS_POSTER_REVISION)
                stamp_frontmatter_field(path, "thumbnail_pending", False)
                stamp_frontmatter_field(path, "thumbnail_attempts", 0)
                clear_frontmatter_field(path, "thumbnail_error")
                clear_frontmatter_field(path, "thumbnail_retry_after")
                clear_frontmatter_field(path, "thumbnail_retry_reason")
                stamp_frontmatter_field(
                    path, "thumbnail_poster",
                    "[" + ", ".join(json.dumps(str(x)) for x in poster.lines) + "]",
                    raw=True)
                stamp_frontmatter_field(path, "thumbnail_kicker", poster.kicker)
                stamp_frontmatter_field(path, "thumbnail_plate", poster.plate)
            else:
                try:
                    seen = int(doc.meta.get("thumbnail_attempts") or 0)
                except (TypeError, ValueError):
                    seen = 0
                if _is_thumbnail_rate_limited(status):
                    retry_at = (
                        datetime.now(timezone.utc)
                        + timedelta(hours=THUMBNAIL_RATE_LIMIT_COOLDOWN_HOURS)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    channel_rate_limited_until = retry_at
                    stamp_frontmatter_field(path, "thumbnail_retry_after", retry_at)
                    stamp_frontmatter_field(path, "thumbnail_retry_reason", "rate_limit")
                elif _is_permission_refusal(status):
                    retry_at = (datetime.now(timezone.utc) + timedelta(
                        hours=THUMBNAIL_PERMISSION_COOLDOWN_HOURS
                    )).strftime("%Y-%m-%dT%H:%M:%SZ")
                    stamp_frontmatter_field(path, "thumbnail_retry_after", retry_at)
                    stamp_frontmatter_field(path, "thumbnail_retry_reason", "permission")
                    stamp_frontmatter_field(path, "thumbnail_attempts", seen + 1)
                else:
                    clear_frontmatter_field(path, "thumbnail_retry_after")
                    clear_frontmatter_field(path, "thumbnail_retry_reason")
                    stamp_frontmatter_field(path, "thumbnail_attempts", seen + 1)
                stamp_frontmatter_field(path, "thumbnail_pending", True)
                stamp_frontmatter_field(path, "thumbnail_error", str(status)[:900])
                print(f"::warning title=Shorts thumbnail not applied "
                      f"({profile.id})::{vid} — {status}. The receipt keeps "
                      f"thumbnail_pending: true; later eligible monitor passes may retry it "
                      f"(50 quota units per attempt).")
        print(f"::notice title=Shorts thumbnail sync::{json.dumps(row)}")
        results.append(row)

    return results


DEFAULT_CHANNEL_PASS_LIMIT = 4


def sync_all_channels(
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = DEFAULT_CHANNEL_PASS_LIMIT,
) -> dict[str, list[dict[str, Any]]]:
    """Repair every channel, each with its own credentials.

    One channel's failure must never silence another's repair — the pools are
    separate, so a 403 on one says nothing about the other.

    Live channels only: a registered channel with no credentials has no videos to
    repair, and reporting it as broken every three hours is the noise this repo
    keeps paying for.
    """
    from pipeline.channels import scheduled_channels

    results: dict[str, list[dict[str, Any]]] = {}
    for cid in sorted(scheduled_channels()):
        try:
            results[cid] = sync_published_thumbnails(
                force=force, dry_run=dry_run, channel=cid, limit=limit
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
    parser.add_argument("--retry-permission", action="store_true",
                        help="Retry only pending permission failures for one explicit channel")
    args = parser.parse_args(argv)
    dry = args.dry_run or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    if args.retry_permission:
        if not args.channel or args.channel not in CHANNELS or args.all_channels or args.force:
            parser.error("--retry-permission requires one exact --channel and cannot be combined with --all-channels or --force")
        if not dry and not _has_youtube_credentials(get_channel(args.channel)):
            print(f"[thumb-sync] {args.channel}: YouTube credentials are unavailable; nothing was changed.")
            return 1
        rows = sync_published_thumbnails(
            dry_run=dry, channel=args.channel, limit=DEFAULT_CHANNEL_PASS_LIMIT,
            retry_permission=True, thumbnails_only=True,
        )
        fixed = sum(1 for row in rows if row.get("thumbnail_status") == "ok")
        print(f"[thumb-sync] {args.channel}: {fixed}/{len(rows)} thumbnail(s) applied in this bounded pass. "
              "Other pending receipts may be awaiting later monitor passes or a rate-limit cooldown; "
              "inspect receipts and warnings for their current status.")
        return 0 if dry or all(row.get("thumbnail_status") == "ok" for row in rows) else 1
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
