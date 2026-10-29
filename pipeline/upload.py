"""YouTube upload via Data API v3 (free — 1 unit from the 100/day uploads bucket).

Visibility policy (PLAN.md §3.4):
  * Unaudited GCP projects have historically been forced to `private` on
    videos.insert. So the default is `private` + a GitHub "release ticket"
    (Issue) that a human uses to publish in ~2 clicks.
  * Once the project passes the YouTube API Services compliance audit, set
    AUTO_PUBLISH=true to go straight to `public` (or schedule with publishAt).

Credentials come from secrets (never from git):
  YOUTUBE_CLIENT_ID       — the Web OAuth client ID
  YOUTUBE_CLIENT_SECRET   — the raw Web OAuth client secret (not JSON)
  YOUTUBE_REFRESH_TOKEN   — minted once via OAuth Playground or scripts/youtube_oauth.py
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


@dataclass
class UploadResult:
    video_id: str
    privacy_status: str
    watch_url: str
    auto_published: bool


from pipeline.quota_handler import (
    QuotaExceededError,
    GeminiQuotaExceededError,
    calculate_next_quota_reset_utc,
)


def _client_credentials(client_id: str, client_secret: str) -> tuple[str, str]:
    """Validate the separate raw Web client ID and secret values."""
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    if not client_id or not client_secret:
        raise RuntimeError("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET as separate secrets.")
    if client_secret.startswith("{"):
        raise RuntimeError(
            "YOUTUBE_CLIENT_SECRET must be the raw OAuth client secret, not JSON. "
            "Store the client ID separately as YOUTUBE_CLIENT_ID."
        )
    return client_id, client_secret


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as SACredentials  # noqa: F401
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401

    client_id, client_secret = _client_credentials(
        CONFIG.youtube_client_id,
        CONFIG.youtube_client_secret,
    )

    creds = Credentials(
        token=None,
        refresh_token=CONFIG.youtube_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def build_description(doc: ScriptDoc) -> str:
    niche = getattr(doc, "niche", "") or str(doc.meta.get("niche", ""))
    slug = getattr(doc, "slug", "")
    is_prayer = any(k in niche.lower() or k in slug.lower() for k in ("faith", "prayer", "scripture", "devotional", "psalm"))
    parts = [doc.description or doc.title]
    parts.append("")
    parts.append("—")
    if is_prayer:
        parts.append("Scripture & Devotional Commentary: Original editorial production by The Secret Place.")
        parts.append("Production Disclosure: Audio narration and visual motion design were created or enhanced")
        parts.append("using Google Gemini AI and studio DSP synthesizers under human editorial direction.")
    else:
        parts.append("Research notes & sources are listed above. Produced with an open,")
        parts.append("human-edited documentary pipeline (scripts reviewed by a human editor).")
    tags = " ".join(f"#{t.replace(' ', '')}" for t in doc.tags[:8])
    if tags:
        parts.append("")
        parts.append(tags)
    return "\n".join(parts)[:4900]


def _normalize_title(title: str) -> str:
    """Normalize video title for duplicate detection by stripping hashtags, punctuation, and extra whitespace."""
    import re
    # Remove hashtag suffixes (e.g. #Shorts, #shorts, #Psalm91)
    cleaned = re.sub(r"#\w+", "", title)
    # Remove punctuation characters
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    # Lowercase and collapse consecutive whitespace
    return " ".join(cleaned.lower().split())


def check_existing_channel_duplicate(youtube, title: str, slug: str | None = None) -> dict | None:
    """Check if a video with an identical or near-identical title already exists on the channel.

    Returns existing video metadata if found, or None.
    Uses only 2 YouTube Data API quota units (channels.list + playlistItems.list).
    """
    try:
        ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
        items = ch_resp.get("items", [])
        if not items:
            return None
        uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Check recent 50 channel uploads
        pl_resp = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_pl,
            maxResults=50,
        ).execute()

        target_norm = _normalize_title(title)

        for p_item in pl_resp.get("items", []):
            snip = p_item.get("snippet", {})
            remote_title = snip.get("title", "")
            remote_id = snip.get("resourceId", {}).get("videoId", "")
            if not remote_id:
                continue

            # Exact title match
            if remote_title.strip() == title.strip():
                return {"id": remote_id, "title": remote_title, "match": "exact"}

            # Normalized title match (ignoring case, punctuation, and hashtag variations)
            if target_norm and _normalize_title(remote_title) == target_norm:
                return {"id": remote_id, "title": remote_title, "match": "normalized"}

        return None
    except Exception as exc:
        print(f"[upload] Notice: duplicate check query skipped: {exc}")
        return None


def upload(
    doc: ScriptDoc,
    video_path: Path,
    thumbnail_path: Path | None = None,
    privacy: str | None = None,
    publish_at: str | None = None,
    description: str | None = None,
) -> UploadResult:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    # --- DUPLICATE UPLOAD SAFETY SHIELD ----------------------------------
    if not CONFIG.allow_duplicate_uploads:
        existing = check_existing_channel_duplicate(youtube, doc.title, getattr(doc, "slug", None))
        if existing:
            print("\n" + "=" * 70)
            print("🛑 [upload] DUPLICATE SHIELD: PREVENTED UNINTENTIONAL / ACCIDENTAL UPLOAD")
            print(f"   A video with matching title already exists on your YouTube channel!")
            print(f"   Existing Video ID: {existing['id']}")
            print(f"   Existing Title:    \"{existing['title']}\"")
            print(f"   Match Type:        {existing['match']}")
            print(f"   Action:            Aborting upload to prevent duplicate reels on channel.")
            print(f"   To override (not recommended), set ALLOW_DUPLICATE_UPLOADS=true.")
            print("=" * 70 + "\n")
            return UploadResult(
                video_id=existing["id"],
                privacy_status="duplicate_prevented",
                watch_url=f"https://youtu.be/{existing['id']}",
                auto_published=False,
            )

    privacy = privacy or doc.meta.get("privacy") or (CONFIG.default_privacy)
    publish_at = publish_at or doc.meta.get("publish_at")

    if publish_at:
        privacy = "private"
    elif CONFIG.auto_publish and privacy == "private":
        privacy = "public"

    body = {
        "snippet": {
            "title": doc.title[:95],
            "description": (description or build_description(doc))[:4900],
            "tags": (doc.tags + CONFIG.tags_extra)[:20],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"[upload] {int(status.progress() * 100)}%")
    except Exception as exc:
        err_msg = str(exc)
        if "quotaExceeded" in err_msg or "uploadLimitExceeded" in err_msg:
            reset_dt = calculate_next_quota_reset_utc()
            iso_reset = reset_dt.isoformat().replace("+00:00", "Z")
            raise QuotaExceededError(
                f"YouTube daily API upload quota exceeded (10,000 units limit). Pausing until midnight PT reset ({iso_reset}).",
                reset_time_utc=reset_dt,
            ) from exc
        raise

    video_id = response["id"]
    stored_privacy = response.get("status", {}).get("privacyStatus", privacy)

    if thumbnail_path and thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()
        except Exception as exc:  # noqa: BLE001
            print(f"[upload] thumbnail set failed (quota is 50 units/day): {exc!r}")

    if CONFIG.playlist_id:
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": CONFIG.playlist_id,
                        "resourceId": {"kind": "youtube#video", "videoId": video_id},
                    }
                },
            ).execute()
        except Exception as exc:  # noqa: BLE001
            print(f"[upload] playlist insert failed: {exc!r}")

    return UploadResult(
        video_id=video_id,
        privacy_status=stored_privacy,
        watch_url=f"https://youtu.be/{video_id}",
        auto_published=stored_privacy == "public",
    )


def set_video_thumbnail(video_id: str, thumbnail_path: Path) -> str:
    """Apply a custom thumbnail to an existing YouTube video ID and return 'ok' or error string."""
    vid = (video_id or "").strip()
    if not vid or not thumbnail_path.is_file():
        return "skipped"
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = _credentials()
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        youtube.thumbnails().set(
            videoId=vid,
            media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
        ).execute()
        print(f"[upload] set custom thumbnail on {vid}")
        return "ok"
    except Exception as exc:  # noqa: BLE001
        msg = f"{type(exc).__name__}: {exc}"
        print(f"[upload] set_video_thumbnail({vid}) failed: {msg}")
        return msg[:220]


def audit_channel_videos(extra_video_ids: list[str] | None = None) -> list[dict]:
    """Return status/thumbnail metadata for recent channel uploads plus any explicit video IDs."""
    try:
        from googleapiclient.discovery import build

        creds = _credentials()
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        ids: list[str] = [v.strip() for v in (extra_video_ids or []) if v and v.strip()]

        ch_resp = youtube.channels().list(part="snippet,contentDetails", mine=True).execute()
        for ch in ch_resp.get("items", []):
            uploads_pl = ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", "")
            if uploads_pl:
                pl_resp = (
                    youtube.playlistItems()
                    .list(part="contentDetails", playlistId=uploads_pl, maxResults=15)
                    .execute()
                )
                for item in pl_resp.get("items", []):
                    vid = item.get("contentDetails", {}).get("videoId", "")
                    if vid and vid not in ids:
                        ids.append(vid)

        seen: list[str] = []
        for vid in ids:
            if vid and vid not in seen:
                seen.append(vid)
        if not seen:
            return []

        v_resp = (
            youtube.videos()
            .list(part="snippet,status,contentDetails", id=",".join(seen[:25]))
            .execute()
        )
        rows: list[dict] = []
        for item in v_resp.get("items", []):
            st = item.get("status", {})
            sn = item.get("snippet", {})
            cd = item.get("contentDetails", {})
            thumbs = sn.get("thumbnails", {})
            rows.append(
                {
                    "id": item.get("id", ""),
                    "title": sn.get("title", ""),
                    "publishedAt": sn.get("publishedAt", ""),
                    "uploadStatus": st.get("uploadStatus", ""),
                    "privacyStatus": st.get("privacyStatus", ""),
                    "rejectionReason": st.get("rejectionReason", ""),
                    "failureReason": st.get("failureReason", ""),
                    "duration": cd.get("duration", ""),
                    "thumbMaxres": bool(thumbs.get("maxres") or thumbs.get("standard")),
                }
            )
        return rows
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"[:240]}]


def delete_video(video_id: str) -> bool:
    """Best-effort delete of a superseded private YouTube upload if scope allows."""
    vid = (video_id or "").strip()
    if not vid:
        return False
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        client_id, client_secret = _client_credentials(
            CONFIG.youtube_client_id,
            CONFIG.youtube_client_secret,
        )
        creds = Credentials(
            token=None,
            refresh_token=CONFIG.youtube_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        youtube.videos().delete(id=vid).execute()
        print(f"[upload] deleted superseded video {vid}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[upload] keeping prior video {vid} (delete skipped/not permitted): {exc!r}")
        return False

