#!/usr/bin/env python3
"""Audit and clean up unintentional duplicate Shorts / Reels on YouTube.

Groups channel videos by normalized title, identifies the best-performing
anchor upload to keep public, and safely sets accidental duplicates to private
or deletes them so the channel feed remains clean and professional.

Usage:
    python scripts/cleanup_duplicate_shorts.py --audit           # Inspect duplicates safely
    python scripts/cleanup_duplicate_shorts.py --make-private    # Remove duplicates from public feed
    python scripts/cleanup_duplicate_shorts.py --delete          # Permanently delete duplicate uploads
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.config import CONFIG
from pipeline.upload import _credentials, _normalize_title


def audit_channel_shorts(youtube) -> list[dict]:
    """Retrieve recent uploads and filter for Shorts/Reels."""
    ch_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = ch_resp.get("items", [])
    if not items:
        print("[cleanup] No channel found for authenticated credentials.")
        return []

    uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    pl_resp = youtube.playlistItems().list(
        part="snippet",
        playlistId=uploads_pl,
        maxResults=50,
    ).execute()

    video_ids = [
        item["snippet"]["resourceId"]["videoId"]
        for item in pl_resp.get("items", [])
        if item.get("snippet", {}).get("resourceId", {}).get("videoId")
    ]

    if not video_ids:
        return []

    v_resp = youtube.videos().list(
        part="snippet,contentDetails,status,statistics",
        id=",".join(video_ids),
    ).execute()

    shorts = []
    for v in v_resp.get("items", []):
        vid = v["id"]
        snip = v.get("snippet", {})
        stat = v.get("statistics", {})
        status = v.get("status", {})
        cd = v.get("contentDetails", {})
        duration = cd.get("duration", "")
        title = snip.get("title", "")

        # Detect Short: duration PT..S under 61s, or #Shorts in title/description
        is_short = (
            "PT" in duration and "M" not in duration
            or "#short" in title.lower()
            or "#shorts" in snip.get("description", "").lower()
        )
        if is_short:
            views = int(stat.get("viewCount", 0))
            shorts.append({
                "id": vid,
                "title": title,
                "normalized_title": _normalize_title(title),
                "published_at": snip.get("publishedAt", ""),
                "views": views,
                "privacy": status.get("privacyStatus", ""),
                "duration": duration,
            })
    return shorts


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean up unintentional duplicate YouTube Shorts")
    parser.add_argument("--audit", action="store_true", default=True, help="Scan and display duplicate groups (read-only)")
    parser.add_argument("--make-private", action="store_true", help="Set duplicate videos to private (removes from public tab)")
    parser.add_argument("--delete", action="store_true", help="Permanently delete duplicate uploads from YouTube")
    args = parser.parse_args()

    print("\n" + "=" * 75)
    print("  THE SECRET PLACE — YOUTUBE SHORTS DUPLICATE AUDITOR & CLEANUP")
    print("=" * 75 + "\n")

    if not all((CONFIG.youtube_client_id, CONFIG.youtube_client_secret, CONFIG.youtube_refresh_token)):
        print("[cleanup] Missing YouTube credentials. Set YOUTUBE_* environment variables to run.")
        return 1

    try:
        from googleapiclient.discovery import build
        creds = _credentials()
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        print(f"[cleanup] Authentication failed: {exc}")
        return 1

    print("[cleanup] Fetching recent channel uploads...")
    shorts = audit_channel_shorts(youtube)
    if not shorts:
        print("[cleanup] No Shorts found on the channel.")
        return 0

    # Group by normalized title
    groups = defaultdict(list)
    for s in shorts:
        groups[s["normalized_title"]].append(s)

    duplicates_found = False
    for norm_title, items in groups.items():
        if len(items) <= 1:
            continue

        duplicates_found = True
        print(f"\n⚠️  DUPLICATE GROUP DETECTED ({len(items)} uploads of the same Reel):")
        print(f"   Normalized Title: \"{norm_title}\"\n")

        # Sort by views descending (keep highest-viewed as master)
        sorted_items = sorted(items, key=lambda x: (x["views"], x["published_at"]), reverse=True)
        master = sorted_items[0]
        duplicates = sorted_items[1:]

        print(f"   👑 MASTER VIDEO (KEEP PUBLIC):")
        print(f"      ID: {master['id']} | Published: {master['published_at']} | Views: {master['views']} | Privacy: {master['privacy']}")
        print(f"      URL: https://youtube.com/shorts/{master['id']}\n")

        print(f"   🗑️  DUPLICATE UPLOADS ({len(duplicates)} accidental copies):")
        for idx, dup in enumerate(duplicates, 1):
            print(f"      [{idx}] ID: {dup['id']} | Published: {dup['published_at']} | Views: {dup['views']} | Privacy: {dup['privacy']}")
            print(f"          URL: https://youtube.com/shorts/{dup['id']}")

            if args.make_private:
                try:
                    youtube.videos().update(
                        part="status",
                        body={
                            "id": dup["id"],
                            "status": {"privacyStatus": "private"},
                        },
                    ).execute()
                    print(f"          ✅ Set to PRIVATE (removed from public Shorts tab).")
                except Exception as exc:
                    print(f"          ❌ Failed to set private: {exc}")

            elif args.delete:
                try:
                    youtube.videos().delete(id=dup["id"]).execute()
                    print(f"          ✅ DELETED from YouTube.")
                except Exception as exc:
                    print(f"          ❌ Failed to delete: {exc}")

    if not duplicates_found:
        print("\n✅ Zero duplicate Shorts detected! Every Reel on your channel is unique.")
    elif not args.make_private and not args.delete:
        print("\n" + "=" * 75)
        print("💡 NEXT STEPS TO CLEAN UP YOUR SHORTS TAB:")
        print("   To automatically hide all duplicate uploads from your public channel tab:")
        print("   python scripts/cleanup_duplicate_shorts.py --make-private")
        print("=" * 75 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
