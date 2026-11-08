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


def ensure_playlist_exists(
    youtube: Any,
    spec: PlaylistSpec,
    dry_run: bool = False,
    *,
    existing_playlists: list[dict] | None = None,
) -> str | None:
    """Ensure a playlist exists, creating it if absent. Returns playlist_id."""
    if dry_run or not youtube:
        print(f"[playlist] [dry-run] Would ensure playlist exists: '{spec.title}'")
        return f"mock_pl_{spec.key}"

    # 1. Search existing channel playlists (cached across the sync pass when provided)
    existing = existing_playlists if existing_playlists is not None else get_channel_playlists(youtube)
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
        if pl_id and existing_playlists is not None:
            existing_playlists.append({"id": pl_id, "snippet": {"title": spec.title}})
        print(f"[playlist] Successfully created playlist '{spec.title}' with ID: {pl_id}")
        return pl_id
    except Exception as exc:
        print(f"[playlist] Error creating playlist '{spec.title}': {exc}")
        return None


def get_playlist_items(youtube: Any, playlist_id: str) -> list[dict[str, str]]:
    """Retrieve all items (item_id, video_id, title) in a playlist in one paginated pass."""
    if not youtube or not playlist_id or playlist_id.startswith("mock_"):
        return []

    items_out: list[dict[str, str]] = []
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
                snippet = item.get("snippet", {}) or {}
                vid = (
                    (snippet.get("resourceId", {}) or {}).get("videoId")
                    or (item.get("contentDetails", {}) or {}).get("videoId")
                )
                if vid:
                    items_out.append({
                        "item_id": str(item.get("id") or "").strip(),
                        "video_id": str(vid).strip(),
                        "title": str(snippet.get("title") or "").strip(),
                    })

            next_page = res.get("nextPageToken")
            if not next_page:
                break
    except Exception as exc:
        print(f"[playlist] Notice: error reading playlist items for {playlist_id}: {exc}")

    return items_out


def get_playlist_video_ids(youtube: Any, playlist_id: str) -> set[str]:
    """Get all video IDs already present in a playlist to enforce idempotency."""
    return {row["video_id"] for row in get_playlist_items(youtube, playlist_id) if row.get("video_id")}


def prune_shorts_from_playlist(
    youtube: Any,
    playlist_id: str,
    short_video_ids: set[str],
    *,
    dry_run: bool = False,
    playlist_items: list[dict[str, str]] | None = None,
) -> int:
    """Remove vertical #Shorts from a long-form Series Playlist so continuous autoplay never breaks."""
    items = list(playlist_items) if playlist_items is not None else get_playlist_items(youtube, playlist_id)
    pruned = 0
    for row in items:
        vid = row.get("video_id", "")
        title = row.get("title", "")
        item_id = row.get("item_id", "")
        is_short = (vid in short_video_ids) or ("#shorts" in title.lower())
        if not is_short:
            continue
        if dry_run or not youtube:
            print(f"[playlist] [dry-run] Would prune Short '{vid}' ({title}) from long-form playlist {playlist_id}")
            pruned += 1
            if playlist_items is not None and row in playlist_items:
                playlist_items.remove(row)
            continue
        if not item_id:
            continue
        try:
            youtube.playlistItems().delete(id=item_id).execute()
            pruned += 1
            if playlist_items is not None and row in playlist_items:
                playlist_items.remove(row)
            print(f"[playlist] Pruned Short '{vid}' (item {item_id}) from long-form playlist {playlist_id}")
        except Exception as exc:
            print(f"[playlist] Warning: could not prune Short '{vid}' from {playlist_id}: {exc}")
    return pruned


def add_video_to_playlist(
    youtube: Any,
    playlist_id: str,
    video_id: str,
    title: str = "",
    dry_run: bool = False,
    *,
    existing_video_ids: set[str] | None = None,
) -> bool:
    """Add a video to a playlist with strict idempotency (skips if already present)."""
    if dry_run or not youtube:
        print(f"[playlist] [dry-run] Would add video '{video_id}' ({title}) to playlist {playlist_id}")
        return True

    # Check if already present (reusing cached set when supplied by sync_all_series_playlists)
    existing_vids = existing_video_ids if existing_video_ids is not None else get_playlist_video_ids(youtube, playlist_id)
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
        if existing_video_ids is not None:
            existing_video_ids.add(video_id)
        print(f"[playlist] Successfully added video '{video_id}' to playlist {playlist_id}")
        return True
    except Exception as exc:
        print(f"[playlist] Error adding video '{video_id}' to playlist: {exc}")
        return False


def playlists_for_channel(channel_id: str | None = None) -> dict[str, PlaylistSpec]:
    """Return the official series playlists configured for `channel_id`."""
    from .channel_capabilities import brand_for
    from .channels import normalize_channel_id

    eff = normalize_channel_id(channel_id or CONFIG.channel_id)
    brand = brand_for(eff)
    if not brand.series_playlists:
        return dict(OFFICIAL_PLAYLISTS)
    return {
        key: PlaylistSpec(
            key=key,
            title=title,
            description=desc,
            privacy_status="public",
            matching_keywords=list(kws),
        )
        for key, title, desc, kws in brand.series_playlists
    }


def _is_short_receipt(pub_file: Path, doc: Any) -> bool:
    fmt = str(getattr(doc, "format", "") or doc.meta.get("format", "")).strip().lower()
    if fmt == "short" or pub_file.name.startswith("short-"):
        return True
    return "#shorts" in str(getattr(doc, "title", "") or "").lower()


def collect_published_short_video_ids(
    channel_id: str | None = None,
    *,
    published_dir: Path | None = None,
) -> set[str]:
    """Collect published Short YouTube video IDs scoped to `channel_id`."""
    from .channels import normalize_channel_id

    eff = normalize_channel_id(channel_id or CONFIG.channel_id)
    directory = published_dir or PUBLISHED_DIR
    short_ids: set[str] = set()
    if not directory.exists():
        return short_ids

    for pub_file in sorted(directory.glob("*.md")):
        try:
            doc = parse_script(pub_file)
            if doc.channel != eff:
                continue
            if not _is_short_receipt(pub_file, doc):
                continue
            vid = doc.meta.get("youtube_video_id") or doc.meta.get("video_id")
            if vid and str(vid).strip():
                short_ids.add(str(vid).strip())
        except Exception:
            continue
    return short_ids


def collect_published_videos(
    channel_id: str | None = None,
    *,
    include_shorts: bool = False,
    published_dir: Path | None = None,
) -> list[dict]:
    """Collect published long-form videos from content/published/ scoped to `channel_id`.

    Shorts (`format: short` / `#Shorts`) are excluded by default so continuous
    8-minute Series Playlist autoplay sessions are never broken by 45-second
    vertical clips (which also do not contribute Shorts-feed hours toward the
    4,000-hour long-form YPP threshold).
    """
    from .channel_capabilities import brand_for
    from .channels import normalize_channel_id

    eff = normalize_channel_id(channel_id or CONFIG.channel_id)
    brand = brand_for(eff)
    directory = published_dir or PUBLISHED_DIR
    videos: list[dict] = []
    anchor_id = ""
    if brand.anchor_video:
        anchor_id, anchor_title, anchor_tags = brand.anchor_video
        videos.append({
            "video_id": anchor_id,
            "title": anchor_title,
            "tags": list(anchor_tags),
            "niche": "faith and prayer",
        })

    if not directory.exists():
        return videos

    for pub_file in sorted(directory.glob("*.md")):
        try:
            doc = parse_script(pub_file)
            if doc.channel != eff:
                continue
            if str(doc.meta.get("youtube_status", "")).strip() == "deleted_or_missing":
                continue
            if not include_shorts and _is_short_receipt(pub_file, doc):
                continue
            vid = doc.meta.get("youtube_video_id") or doc.meta.get("video_id")
            if vid and str(vid).strip() != anchor_id:
                videos.append({
                    "video_id": str(vid).strip(),
                    "title": doc.title,
                    "tags": doc.tags or [],
                    "niche": doc.meta.get("niche", "faith and prayer"),
                })
        except Exception:
            continue

    return videos


def sync_all_series_playlists(
    youtube: Any = None,
    dry_run: bool = False,
    channel_id: str | None = None,
    *,
    published_dir: Path | None = None,
) -> dict:
    """Audit and sync all official channel playlists with published long-form videos."""
    from .channel_capabilities import brand_for
    from .channels import normalize_channel_id

    eff = normalize_channel_id(channel_id or CONFIG.channel_id)
    brand = brand_for(eff)
    playlists = playlists_for_channel(eff)
    videos = collect_published_videos(channel_id=eff, include_shorts=False, published_dir=published_dir)
    short_ids = collect_published_short_video_ids(channel_id=eff, published_dir=published_dir)
    sync_report: dict[str, Any] = {
        "channel": eff,
        "playlists_synced": 0,
        "videos_assigned": 0,
        "shorts_pruned": 0,
        "playlists": {},
    }

    print("=" * 72)
    print(f"{brand.display_name.upper()} ({eff}) — OFFICIAL SERIES PLAYLIST AUTOPLAY SYNC")
    print("=" * 72)
    print(f"[*] Found {len(videos)} published long-form video(s) to organize "
          f"(excluding {len(short_ids)} Short(s)).")

    # Fetch existing channel playlists once per channel sync (1 API unit instead of N)
    cached_playlists = get_channel_playlists(youtube) if (youtube and not dry_run) else None

    for key, spec in playlists.items():
        pl_id = ensure_playlist_exists(
            youtube,
            spec,
            dry_run=dry_run,
            existing_playlists=cached_playlists,
        )
        sync_report["playlists"][key] = {
            "title": spec.title,
            "id": pl_id,
            "videos": [],
            "shorts_pruned": 0,
        }
        if not pl_id:
            continue

        sync_report["playlists_synced"] += 1

        # Fetch playlist items once per playlist, prune any legacy #Shorts, and reuse ID set
        playlist_items = get_playlist_items(youtube, pl_id) if (youtube and not dry_run) else None
        if playlist_items is not None:
            pruned = prune_shorts_from_playlist(
                youtube,
                pl_id,
                short_ids,
                dry_run=dry_run,
                playlist_items=playlist_items,
            )
            sync_report["shorts_pruned"] += pruned
            sync_report["playlists"][key]["shorts_pruned"] = pruned
            cached_video_ids: set[str] | None = {
                row["video_id"] for row in playlist_items if row.get("video_id")
            }
        else:
            cached_video_ids = None

        # Match long-form videos to playlist based on keywords
        for v in videos:
            v_title_lower = v["title"].lower()
            v_tags_lower = [t.lower() for t in v.get("tags", [])]
            matches = False

            for kw in spec.matching_keywords:
                if kw in v_title_lower or any(kw in t for t in v_tags_lower):
                    matches = True
                    break

            if matches:
                added = add_video_to_playlist(
                    youtube,
                    pl_id,
                    v["video_id"],
                    title=v["title"],
                    dry_run=dry_run,
                    existing_video_ids=cached_video_ids,
                )
                if added:
                    sync_report["videos_assigned"] += 1
                    sync_report["playlists"][key]["videos"].append(v["video_id"])

    print("=" * 72)
    print(f"[+] Playlist sync complete: {sync_report['playlists_synced']} playlists checked, "
          f"{sync_report['videos_assigned']} long-form placements verified, "
          f"{sync_report['shorts_pruned']} Short(s) pruned.")
    print("=" * 72)
    return sync_report
