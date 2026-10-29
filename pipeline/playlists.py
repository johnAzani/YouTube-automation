"""Official Series Playlist Management & Autoplay Engine for The Secret Place.

Organizes long-form and bedtime content into official YouTube Series Playlists
to maximize viewer Session Watch Time and continuous autoplays, directly
accelerating YPP 4,000 Watch Hours qualification.

Quota Economics ($0.00 Lock):
  • playlists.list: 1 unit
  • playlists.insert: 50 units (only run once per playlist)
  • playlistItems.list: 1 unit
  • playlistItems.insert: 50 units (only when adding new video)
  Total daily quota usage: <150 units out of 10,000 units/day free allowance.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import CONFIG, PUBLISHED_DIR
from .script_doc import parse_script


@dataclass(frozen=True)
class PlaylistSpec:
    key: str
    title: str
    description: str
    privacy_status: str = "public"
    matching_keywords: list[str] = field(default_factory=list)


# Official Channel Series Playlists
OFFICIAL_PLAYLISTS: dict[str, PlaylistSpec] = {
    "night_prayers": PlaylistSpec(
        key="night_prayers",
        title="Night Prayers of Divine Protection — The Secret Place",
        description=(
            "Say these powerful Psalm prayers before you sleep tonight. Let God's covenant of "
            "divine protection, peace, and angelic shelter surround your home, family, and mind from wall to wall.\n\n"
            "Featuring Psalm 91, Psalm 23, Psalm 121, and Psalm 27 with peaceful 432 Hz bedtime meditation soundscapes.\n\n"
            "Produced by The Secret Place | Daily Scripture & Bedtime Prayer."
        ),
        privacy_status="public",
        matching_keywords=["psalm 91", "protection", "night prayer", "sleep prayer", "secret place"],
    ),
    "bedtime_sleep": PlaylistSpec(
        key="bedtime_sleep",
        title="Bedtime Scripture Meditations for Deep Sleep & Peace (432 Hz)",
        description=(
            "Soothing scripture meditations, biblical sleep prayers, and calming nighttime scriptures "
            "designed to overcome insomnia, quiet racing thoughts, and guide you into deep, restorative rest.\n\n"
            "Featuring 432 Hz Solfeggio acoustic beds and sacred scripture.\n\n"
            "Produced by The Secret Place | Daily Scripture & Bedtime Prayer."
        ),
        privacy_status="public",
        matching_keywords=["sleep", "bedtime", "rest", "peace", "432 hz", "meditation"],
    ),
    "complete_psalms": PlaylistSpec(
        key="complete_psalms",
        title="The Complete Psalms Devotional Series (Exposition & Prayer)",
        description=(
            "Verse-by-verse devotional prayer and classical commentary across the Book of Psalms. "
            "Deep-dive into God's word with classical exposition, historical context, and contemplative evening prayer.\n\n"
            "Produced by The Secret Place | Daily Scripture & Bedtime Prayer."
        ),
        privacy_status="public",
        matching_keywords=["psalm", "scripture", "exposition", "devotional"],
    ),
}


def get_channel_playlists(youtube: Any) -> list[dict]:
    """Retrieve existing channel playlists."""
    try:
        req = youtube.playlists().list(
            part="snippet,status",
            mine=True,
            maxResults=50,
        )
        res = req.execute()
        return res.get("items", [])
    except Exception as exc:
        print(f"[playlist] Error fetching channel playlists: {exc}")
        return []


def ensure_playlist_exists(youtube: Any, spec: PlaylistSpec, dry_run: bool = False) -> str | None:
    """Ensure a playlist exists, creating it if absent. Returns playlist_id."""
    if dry_run or not youtube:
        print(f"[playlist] [dry-run] Would ensure playlist exists: '{spec.title}'")
        return f"mock_pl_{spec.key}"

    # 1. Search existing channel playlists
    existing = get_channel_playlists(youtube)
    for pl in existing:
        snippet = pl.get("snippet", {})
        if snippet.get("title", "").strip().lower() == spec.title.strip().lower():
            pl_id = pl.get("id")
            print(f"[playlist] Found existing playlist: '{spec.title}' (ID: {pl_id})")
            return pl_id

    # 2. Create playlist if absent
    print(f"[playlist] Creating new official playlist: '{spec.title}'...")
    try:
        req = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": spec.title,
                    "description": spec.description,
                    "defaultLanguage": "en",
                },
                "status": {
                    "privacyStatus": spec.privacy_status,
                },
            },
        )
        res = req.execute()
        pl_id = res.get("id")
        print(f"[playlist] Successfully created playlist '{spec.title}' with ID: {pl_id}")
        return pl_id
    except Exception as exc:
        print(f"[playlist] Error creating playlist '{spec.title}': {exc}")
        return None


def get_playlist_video_ids(youtube: Any, playlist_id: str) -> set[str]:
    """Get all video IDs already present in a playlist to enforce idempotency."""
    if not youtube or not playlist_id or playlist_id.startswith("mock_"):
        return set()

    video_ids: set[str] = set()
    try:
        next_page = None
        while True:
            req = youtube.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page,
            )
            res = req.execute()
            for item in res.get("items", []):
                snippet = item.get("snippet", {})
                vid = snippet.get("resourceId", {}).get("videoId")
                if vid:
                    video_ids.add(vid)

            next_page = res.get("nextPageToken")
            if not next_page:
                break
    except Exception as exc:
        print(f"[playlist] Notice: error reading playlist items for {playlist_id}: {exc}")

    return video_ids


def add_video_to_playlist(
    youtube: Any,
    playlist_id: str,
    video_id: str,
    title: str = "",
    dry_run: bool = False,
) -> bool:
    """Add a video to a playlist with strict idempotency (skips if already present)."""
    if dry_run or not youtube:
        print(f"[playlist] [dry-run] Would add video '{video_id}' ({title}) to playlist {playlist_id}")
        return True

    # Check if already present
    existing_vids = get_playlist_video_ids(youtube, playlist_id)
    if video_id in existing_vids:
        print(f"[playlist] Video '{video_id}' already present in playlist {playlist_id}. Skipping (idempotent).")
        return True

    print(f"[playlist] Adding video '{video_id}' to playlist {playlist_id}...")
    try:
        req = youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {
                        "kind": "youtube#video",
                        "videoId": video_id,
                    },
                },
            },
        )
        req.execute()
        print(f"[playlist] Successfully added video '{video_id}' to playlist {playlist_id}")
        return True
    except Exception as exc:
        print(f"[playlist] Error adding video '{video_id}' to playlist: {exc}")
        return False


def collect_published_videos() -> list[dict]:
    """Collect published videos from content/published/."""
    videos = []
    # Always include live anchor video
    videos.append({
        "video_id": "7RDX0fbIOtQ",
        "title": "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep",
        "tags": ["psalm 91", "prayer of protection", "sleep prayer", "the secret place"],
        "niche": "faith and prayer",
    })

    if not PUBLISHED_DIR.exists():
        return videos

    for pub_file in sorted(PUBLISHED_DIR.glob("*.md")):
        try:
            doc = parse_script(pub_file)
            vid = doc.meta.get("youtube_video_id") or doc.meta.get("video_id")
            if vid and vid != "7RDX0fbIOtQ":
                videos.append({
                    "video_id": str(vid).strip(),
                    "title": doc.title,
                    "tags": doc.tags or [],
                    "niche": doc.meta.get("niche", "faith and prayer"),
                })
        except Exception:
            continue

    return videos


def sync_all_series_playlists(youtube: Any = None, dry_run: bool = False) -> dict:
    """Audit and sync all official channel playlists with published videos."""
    videos = collect_published_videos()
    sync_report: dict[str, Any] = {
        "playlists_synced": 0,
        "videos_assigned": 0,
        "playlists": {},
    }

    print("=" * 72)
    print("THE SECRET PLACE — OFFICIAL SERIES PLAYLIST AUTOPLAY SYNC")
    print("=" * 72)
    print(f"[*] Found {len(videos)} published channel video(s) to organize.")

    for key, spec in OFFICIAL_PLAYLISTS.items():
        pl_id = ensure_playlist_exists(youtube, spec, dry_run=dry_run)
        sync_report["playlists"][key] = {
            "title": spec.title,
            "id": pl_id,
            "videos": [],
        }
        if not pl_id:
            continue

        sync_report["playlists_synced"] += 1

        # Match videos to playlist based on keywords
        for v in videos:
            v_title_lower = v["title"].lower()
            v_tags_lower = [t.lower() for t in v.get("tags", [])]
            matches = False

            for kw in spec.matching_keywords:
                if kw in v_title_lower or any(kw in t for t in v_tags_lower):
                    matches = True
                    break

            if matches:
                added = add_video_to_playlist(youtube, pl_id, v["video_id"], title=v["title"], dry_run=dry_run)
                if added:
                    sync_report["videos_assigned"] += 1
                    sync_report["playlists"][key]["videos"].append(v["video_id"])

    print("=" * 72)
    print(f"[+] Playlist sync complete: {sync_report['playlists_synced']} playlists checked, "
          f"{sync_report['videos_assigned']} video placements verified.")
    print("=" * 72)
    return sync_report
