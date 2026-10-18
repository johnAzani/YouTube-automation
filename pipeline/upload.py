"""YouTube upload via Data API v3 (free — 1 unit from the 100/day uploads bucket).

Visibility policy (PLAN.md §3.4):
  * Unaudited GCP projects have historically been forced to `private` on
    videos.insert. So the default is `private` + a GitHub "release ticket"
    (Issue) that a human uses to publish in ~2 clicks.
  * Once the project passes the YouTube API Services compliance audit, set
    AUTO_PUBLISH=true to go straight to `public` (or schedule with publishAt).

Credentials come from secrets (never from git):
  YOUTUBE_CLIENT_SECRET   — OAuth client secret JSON (string)
  YOUTUBE_REFRESH_TOKEN   — minted once via scripts/youtube_oauth.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


@dataclass
class UploadResult:
    video_id: str
    privacy_status: str
    watch_url: str
    auto_published: bool


def _credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google.oauth2.service_account import Credentials as SACredentials  # noqa: F401
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401

    info = json.loads(CONFIG.youtube_client_secret)
    if "installed" not in info and "web" not in info:
        raise RuntimeError("YOUTUBE_CLIENT_SECRET must be an OAuth client secret JSON")
    client_id = info["installed"]["client_id"] if "installed" in info else info["web"]["client_id"]
    client_secret = info["installed"]["client_secret"] if "installed" in info else info["web"]["client_secret"]

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
    parts = [doc.description or doc.title]
    parts.append("")
    parts.append("—")
    parts.append("Research notes & sources are listed above. Produced with an open,")
    parts.append("human-edited documentary pipeline (scripts reviewed by a human editor).")
    tags = " ".join(f"#{t.replace(' ', '')}" for t in doc.tags[:8])
    if tags:
        parts.append("")
        parts.append(tags)
    return "\n".join(parts)[:4900]


def upload(
    doc: ScriptDoc,
    video_path: Path,
    thumbnail_path: Path | None = None,
    privacy: str | None = None,
    publish_at: str | None = None,
) -> UploadResult:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    privacy = privacy or (CONFIG.default_privacy)
    if CONFIG.auto_publish and privacy == "private":
        privacy = "public"

    body = {
        "snippet": {
            "title": doc.title[:95],
            "description": build_description(doc),
            "tags": (doc.tags + CONFIG.tags_extra)[:20],
            "categoryId": "27" if doc.meta.get("category", "") == "education" else "27",
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
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[upload] {int(status.progress() * 100)}%")

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
