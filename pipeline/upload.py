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
from typing import Any

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
    # What actually happened to the custom thumbnail: "ok" (YouTube accepted
    # it), "failed: <reason>" (YouTube refused it), "missing_file" (nothing to
    # send), "by_design_short" (Shorts get no custom thumbnail), "not_requested".
    # It used to be invisible: the `thumbnails.set` call sat in a bare except
    # that printed one line into a step log nobody reads, so two Morning Altar
    # videos went live with YouTube's auto-picked frame while every receipt
    # claimed a `ctr-v3-cinema` thumbnail. Report it, stamp it, retry it.
    thumbnail_status: str = "not_requested"


from pipeline.quota_handler import (
    QuotaExceededError,
    GeminiQuotaExceededError,
    calculate_next_quota_reset_utc,
)


def _api_error_text(exc: Exception) -> str:
    """The API's own sentence, not a 300-character HTTPError repr.

    `set_video_thumbnail` used to store `str(exc)[:220]`, which for the two
    Morning Altar videos cut the message at "The thumbnail can't be set for the
    specified video. The re" — the useful half gone, so the reason could not be
    acted on. googleapiclient carries the parsed error body on `.content`.
    """
    import json as _json

    content = getattr(exc, "content", None)
    if content:
        try:
            raw = content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else str(content)
            payload = _json.loads(raw)
            message = str(payload.get("error", {}).get("message") or "").strip()
            reason = ""
            errors = payload.get("error", {}).get("errors") or []
            if errors and isinstance(errors[0], dict):
                reason = str(errors[0].get("reason") or "").strip()
            if message:
                return f"{message} [{reason}]" if reason else message
        except Exception:  # noqa: BLE001
            pass
    return str(exc)


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
    """Unified description builder delegating to `pipeline.metadata.build_description`."""
    from .metadata import build_description as _meta_build_description

    return _meta_build_description(doc)


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


def verify_target_channel(youtube) -> dict:
    """Confirm the refresh token authorizes the channel this run targets.

    A refresh token silently uploads to whichever channel was selected during
    OAuth consent. When ``YOUTUBE_EXPECTED_CHANNEL_ID`` is set, abort *before*
    any upload if the token belongs to a different channel — the fail-closed
    guard against pasting Channel 1's token into Channel 2's secrets.
    Returns the authorized channel's ``{id, title}``.
    """
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(
            "YouTube returned no channel for these credentials (mine=True). "
            "Re-mint the refresh token while signed into the target channel."
        )
    channel = items[0]
    actual_id = channel.get("id", "")
    title = (channel.get("snippet") or {}).get("title", "")
    expected = CONFIG.expected_youtube_channel_id.strip()
    if expected and actual_id != expected:
        raise RuntimeError(
            f"Refusing to upload: credentials authorize channel {actual_id} "
            f"({title!r}) but this run expects {expected} "
            f"(CHANNEL_ID={CONFIG.channel_id}). The refresh token was minted "
            "for the wrong channel — re-mint it for the target channel."
        )
    print(f"[upload] target channel verified: {title} ({actual_id}) "
          f"for CHANNEL_ID={CONFIG.channel_id}")
    return {"id": actual_id, "title": title}


def upload(
    doc: ScriptDoc,
    video_path: Path,
    thumbnail_path: Path | None = None,
    privacy: str | None = None,
    publish_at: str | None = None,
    description: str | None = None,
    caption_path: Path | None = None,
    tags: list[str] | None = None,
) -> UploadResult:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from .metadata import (
        build_tags,
        fit_youtube_tags,
        is_faith_doc,
        smart_truncate_title,
        truncate_utf8_bytes,
    )
    from .social_pack import (
        SELAR_JOURNAL_URL,
        SELAR_STORE_URL,
        build_sanctuary_resource_block,
    )

    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    safe_title = smart_truncate_title(doc.title, 95)
    faith = is_faith_doc(doc)
    is_short = (
        getattr(doc, "format", "") == "short"
        or str(doc.meta.get("format", "")).lower() == "short"
        or "#shorts" in safe_title.lower()
    )

    # --- DUPLICATE UPLOAD SAFETY SHIELD ----------------------------------
    if not CONFIG.allow_duplicate_uploads:
        existing = check_existing_channel_duplicate(
            youtube, safe_title, getattr(doc, "slug", None)
        ) or (
            check_existing_channel_duplicate(youtube, doc.title, getattr(doc, "slug", None))
            if doc.title != safe_title
            else None
        )
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

    raw_desc = description or build_description(doc)
    from .channels import get_channel

    if (
        faith
        and get_channel(CONFIG.channel_id).include_sanctuary_links
        and SELAR_JOURNAL_URL
        and (SELAR_JOURNAL_URL not in raw_desc or SELAR_STORE_URL not in raw_desc)
    ):
        raw_desc = raw_desc.rstrip() + "\n\n" + build_sanctuary_resource_block(include_store_links=True)
    full_desc = truncate_utf8_bytes(raw_desc, max_bytes=4900)

    allow_432 = "432" in safe_title.lower() or "dark_screen" in (getattr(doc, "slug", "") or "").lower()
    safe_tags = fit_youtube_tags(
        tags if tags is not None else build_tags(doc),
        CONFIG.tags_extra,
        max_chars=490,
        allow_432hz=allow_432,
    )
    category_id = str(doc.meta.get("category_id") or ("22" if faith else "27"))
    niche_str = getattr(doc, "niche", "") or str(doc.meta.get("niche", "faith and prayer" if faith else "education"))

    body = {
        "snippet": {
            "title": safe_title,
            "description": full_desc,
            "tags": safe_tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": bool(doc.meta.get("contains_synthetic_media", False)),
            "embeddable": True,
            "publicStatsViewable": True,
        },
    }
    if publish_at and privacy == "private":
        body["status"]["publishAt"] = publish_at

    # --- MULTI-LANGUAGE LOCALIZATION (SPANISH & PORTUGUESE $0.00 LOCK) ---
    insert_parts = "snippet,status"
    try:
        from .localize_metadata import build_metadata_localizations
        channel_profile = get_channel(CONFIG.channel_id)
        locs = build_metadata_localizations(
            safe_title,
            full_desc,
            niche_str,
            channel_name=CONFIG.channel_name or channel_profile.display_name,
        )
        if locs:
            body["localizations"] = locs
            insert_parts = "snippet,status,localizations"
    except Exception as exc:
        print(f"[upload] Notice: localization build skipped: {exc}")

    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    request = youtube.videos().insert(part=insert_parts, body=body, media_body=media)

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
    thumbnail_status = "not_requested"

    if thumbnail_path and thumbnail_path.exists() and not is_short:
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
            ).execute()
            thumbnail_status = "ok"
            print(f"[upload] custom thumbnail applied to {video_id}")
        except Exception as exc:  # noqa: BLE001
            thumbnail_status = f"failed: {_api_error_text(exc)}"
            print(f"[upload] thumbnail set FAILED (50 units/day; channel "
                  f"{CONFIG.channel_id}): {exc!r}")
            # Loud on purpose. A custom thumbnail needs a channel that YouTube
            # has unlocked for the feature (phone verification) and an OAuth
            # token carrying youtube.force-ssl; a silent failure here is
            # exactly how two published videos ended up with no thumbnail.
            print(f"::error title=YouTube refused the custom thumbnail "
                  f"({CONFIG.channel_id})::video {video_id} published, thumbnail "
                  f"NOT applied — {_api_error_text(exc)}. Check custom-thumbnail "
                  f"eligibility on the channel (phone verification), the "
                  f"youtube.force-ssl scope on the refresh token, and today's "
                  f"quota. The receipt records it as pending, so the monitor "
                  f"retries it instead of pretending it worked.")
    elif is_short:
        thumbnail_status = "by_design_short"
    else:
        thumbnail_status = "missing_file"
        print(f"[upload] no thumbnail file to apply for {video_id}")

    if caption_path and caption_path.is_file() and not is_short:
        try:
            from .captions import upload_captions

            upload_captions(youtube, video_id, caption_path, language="en")
        except Exception as exc:  # noqa: BLE001
            print(f"[upload] caption upload skipped: {exc!r}")

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

    # --- FIRST-HOUR PASTORAL PINNED COMMENT ---
    try:
        from .pinned_comments import generate_pastoral_pinned_comment, post_pastoral_pinned_comment
        pinned_text = generate_pastoral_pinned_comment(doc)
        post_pastoral_pinned_comment(youtube, video_id, pinned_text, dry_run=False)
    except Exception as exc:
        print(f"[upload] Notice: pastoral pinned comment skipped: {exc}")

    return UploadResult(
        video_id=video_id,
        privacy_status=stored_privacy,
        watch_url=f"https://youtu.be/{video_id}",
        auto_published=stored_privacy == "public",
        thumbnail_status=thumbnail_status,
    )


def update_live_video_metadata(
    video_id: str,
    *,
    new_title: str | None = None,
    new_description: str | None = None,
    new_tags: list[str] | None = None,
    localizations: dict | None = None,
    youtube=None,
) -> dict:
    """Safely update an already-published video's metadata without wiping omitted snippet fields.

    Per YouTube Data API v3 `videos.update` rules, calling `videos.update(part='snippet')`
    deletes any omitted property (`tags`, `categoryId`, `defaultLanguage`, `defaultAudioLanguage`).
    This helper always fetches `videos.list(part='snippet,localizations')` first (1 unit) and
    mutates the returned snippet in place before calling `videos.update` (50 units).
    """
    from .metadata import fit_youtube_tags, smart_truncate_title, truncate_utf8_bytes

    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id is required")

    if youtube is None:
        from googleapiclient.discovery import build

        creds = _credentials()
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    listed = youtube.videos().list(part="snippet,localizations", id=vid).execute()
    items = listed.get("items", [])
    if not items:
        raise RuntimeError(f"Video {vid} not found on channel")

    current = items[0]
    snippet = dict(current.get("snippet", {}))
    locs = dict(current.get("localizations", {}) or {})

    if new_title is not None:
        snippet["title"] = smart_truncate_title(new_title, 95)
    if new_description is not None:
        snippet["description"] = truncate_utf8_bytes(new_description, max_bytes=4900)
    if new_tags is not None:
        snippet["tags"] = fit_youtube_tags(new_tags, max_chars=490)

    snippet.setdefault("categoryId", "22")
    snippet["defaultLanguage"] = snippet.get("defaultLanguage") or "en"
    snippet["defaultAudioLanguage"] = snippet.get("defaultAudioLanguage") or "en"

    if localizations is not None:
        locs.update(localizations)

    parts = "snippet,localizations" if locs else "snippet"
    payload = {"id": vid, "snippet": snippet}
    if locs:
        payload["localizations"] = locs

    return youtube.videos().update(part=parts, body=payload).execute()


def diagnose_thumbnail_refusal(video_id: str, youtube: Any = None) -> dict[str, Any]:
    """Name *why* YouTube refused a thumbnail, instead of quoting the 403.

    The refusal sentence is the same for every cause — "The request might not be
    properly authorized" — so a receipt that stores only that sentence cannot be
    acted on. This asks the API the three questions that separate the causes:

    * does the authenticated account own the video at all (`channel_id` vs
      `auth_channel_id`)? A token for the wrong channel of a brand account fails
      here, and it is indistinguishable from a verification problem in the message;
    * is the video finished processing (`upload_status`)? thumbnails.set is refused
      on a video that is still `uploaded`;
    * has the channel been verified for custom thumbnails (`long_uploads_status`)?

    Returns `{}` when the lookup itself fails: a diagnostic must never turn one
    failure into two.
    """
    vid = (video_id or "").strip()
    if not vid:
        return {}
    try:
        if youtube is None:
            from googleapiclient.discovery import build

            youtube = build("youtube", "v3", credentials=_credentials(),
                            cache_discovery=False)
        mine = youtube.channels().list(part="id,snippet,status", mine=True).execute()
        auth_channel = ((mine.get("items") or [{}])[0])
        video = youtube.videos().list(part="snippet,status", id=vid).execute()
        item = (video.get("items") or [{}])[0]
        return {
            "auth_channel_id": auth_channel.get("id", ""),
            "auth_channel_title": (auth_channel.get("snippet") or {}).get("title", ""),
            "long_uploads_status": (auth_channel.get("status") or {}).get(
                "longUploadsStatus", ""),
            "video_channel_id": (item.get("snippet") or {}).get("channelId", ""),
            "video_channel_title": (item.get("snippet") or {}).get("channelTitle", ""),
            "video_privacy": (item.get("status") or {}).get("privacyStatus", ""),
            "upload_status": (item.get("status") or {}).get("uploadStatus", ""),
            "same_channel": (auth_channel.get("id", "") ==
                             (item.get("snippet") or {}).get("channelId", "")),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[upload] thumbnail diagnosis for {vid} unavailable: {exc}")
        return {}


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
        msg = f"{type(exc).__name__}: {_api_error_text(exc)}"
        diagnosis = diagnose_thumbnail_refusal(vid)
        if diagnosis:
            msg += (" | " + "; ".join(f"{k}={v}" for k, v in diagnosis.items()))
        print(f"[upload] set_video_thumbnail({vid}) failed: {msg}")
        return msg[:900]


#: thumbnails.set has supported Shorts only since 2026-11-03, and the docs attach
#: a condition the old code could not have honoured: call it "only after the video
#: has finished processing (when processingDetails.processingStatus is
#: succeeded). If called before video processing is complete, the custom thumbnail
#: might not be applied to the Short." "Might not be applied" is the silent failure
#: this codebase refuses to accept, so we wait for the status and then verify.
SHORTS_THUMBNAIL_WAIT_SECONDS = 600
SHORTS_THUMBNAIL_POLL_SECONDS = 15
THUMBNAIL_VERIFY_ATTEMPTS = 3


def _thumb_client(youtube: Any = None) -> Any:
    if youtube is not None:
        return youtube
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_credentials(), cache_discovery=False)


def wait_for_processing(video_id: str, *, youtube: Any = None,
                        timeout_seconds: int = SHORTS_THUMBNAIL_WAIT_SECONDS,
                        poll_seconds: int = SHORTS_THUMBNAIL_POLL_SECONDS,
                        sleep: Any = None) -> str:
    """Block until `processingStatus` is `succeeded`. Returns the last status seen."""
    import time as _time

    sleep = sleep or _time.sleep
    client = _thumb_client(youtube)
    waited = 0
    status = ""
    while True:
        try:
            resp = client.videos().list(part="status,processingDetails", id=video_id).execute()
            item = (resp.get("items") or [{}])[0]
            status = str((item.get("processingDetails") or {}).get("processingStatus") or "")
            if not status:
                status = str((item.get("status") or {}).get("uploadStatus") or "")
        except Exception as exc:  # noqa: BLE001
            print(f"[upload] could not read processing status of {video_id}: {exc}")
            return "unknown"
        if status in {"succeeded", "failed", "terminated", "processed"}:
            return "succeeded" if status == "processed" else status
        if not status:
            # No status at all means the gate cannot be evaluated. Waiting ten
            # minutes on a field that is not coming is how a run hangs; say so.
            return "unknown"
        if waited >= timeout_seconds:
            return status or "timeout"
        sleep(poll_seconds)
        waited += poll_seconds


def _upload_rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "uploadratelimitexceeded" in msg or "429" in msg or "too many" in msg


def verify_shorts_thumbnail(video_id: str, *, youtube: Any = None,
                            attempts: int = THUMBNAIL_VERIFY_ATTEMPTS,
                            sleep: Any = None) -> dict[str, Any]:
    """Ask YouTube whether the Short really carries a custom 9:16 thumbnail.

    The thumbnails resource defines `shortsAspectRatio` as "the Shorts aspect ratio
    (9:16) version of the thumbnail image ... available for YouTube Shorts that
    have a custom thumbnail set". Its presence is the only programmatic proof, and
    the bundled discovery document predates the field (google-api-python-client
    2.201.0), so this reads the raw response keys.
    """
    import time as _time

    sleep = sleep or _time.sleep
    client = _thumb_client(youtube)
    seen: dict[str, Any] = {}
    for attempt in range(max(1, attempts)):
        try:
            resp = client.videos().list(part="snippet", id=video_id).execute()
            item = (resp.get("items") or [{}])[0]
            thumbs = ((item.get("snippet") or {}).get("thumbnails") or {})
            seen = {"has_shorts_aspect": "shortsAspectRatio" in thumbs,
                    "keys": sorted(thumbs)}
        except Exception as exc:  # noqa: BLE001
            return {"has_shorts_aspect": None, "error": str(exc)[:200]}
        if seen.get("has_shorts_aspect"):
            return seen
        if attempt + 1 < attempts:
            sleep(5)
    return seen


def apply_shorts_thumbnail(
    video_id: str,
    thumbnail_path: Path,
    *,
    youtube: Any = None,
    wait_seconds: int = SHORTS_THUMBNAIL_WAIT_SECONDS,
    poll_seconds: int = SHORTS_THUMBNAIL_POLL_SECONDS,
    sleep: Any = None,
) -> str:
    """Set a Short's custom thumbnail and prove it landed. Returns a status string.

    Order matters and is the whole point: wait for processing, set, retry a 429,
    then verify `shortsAspectRatio` exists. A Short that is published with an
    unverified thumbnail is a Short whose channel page shows a random frame — the
    state every Short was in until 2026-11-07.
    """
    from googleapiclient.http import MediaFileUpload

    vid = (video_id or "").strip()
    if not vid or not Path(thumbnail_path).is_file():
        return "skipped"
    client = _thumb_client(youtube)

    status = wait_for_processing(vid, youtube=client, timeout_seconds=wait_seconds,
                                 poll_seconds=poll_seconds, sleep=sleep)
    if status != "succeeded":
        print(f"[upload] {vid}: processing status {status!r}; deferring the thumbnail")
        return f"deferred_processing_{status or 'unknown'}"

    last_error = ""
    for attempt in range(3):
        try:
            client.thumbnails().set(
                videoId=vid,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
            ).execute()
            print(f"[upload] set custom Shorts thumbnail on {vid}")
            break
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {_api_error_text(exc)}"
            if _upload_rate_limited(exc) and attempt < 2:
                import time as _time

                (sleep or _time.sleep)(20 * (attempt + 1))
                continue
            print(f"[upload] shorts thumbnail set({vid}) failed: {last_error}")
            diagnosis = diagnose_thumbnail_refusal(vid, youtube=client)
            if diagnosis:
                last_error += " | " + "; ".join(f"{k}={v}" for k, v in diagnosis.items())
            return last_error[:900]
    else:
        return last_error[:900]

    check = verify_shorts_thumbnail(vid, youtube=client, sleep=sleep)
    if check.get("has_shorts_aspect"):
        return "ok"
    return f"unverified: thumbnails={','.join(check.get('keys') or []) or 'none'}"


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

