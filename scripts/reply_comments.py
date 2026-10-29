#!/usr/bin/env python3
"""Autonomous / Assisted YouTube Comment Reply CLI for The Secret Place.

Audits recent viewer comments, categorizes intent (Prayer Request, Amen,
Testimony, Inquiry, Scam), generates context-aware pastoral replies using
Google Gemini Brain, and safely publishes them via YouTube Data API v3 while
enforcing strict anti-spam, anti-shadowban, and $0.00 quota safety invariants.

Usage:
    python scripts/reply_comments.py --dry-run             # Inspect candidate replies without posting
    python scripts/reply_comments.py --video-id 7RDX0fbIOtQ --limit 10
    python scripts/reply_comments.py --apply --limit 15    # Post approved pastoral replies
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.comment_replies import (
    CommentReplyEngine,
    classify_comment_intent,
    generate_reply_with_gemini,
)
from pipeline.config import CONFIG
from pipeline.quota_handler import GeminiQuotaExceededError, QuotaExceededError
from pipeline.upload import _credentials


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous / Assisted YouTube Comment Reply System")
    parser.add_argument("--video-id", help="Target specific YouTube video ID (e.g. 7RDX0fbIOtQ)")
    parser.add_argument("--limit", type=int, default=10, help="Max comments to process (default: 10, max: 25)")
    parser.add_argument("--dry-run", action="store_true", help="Draft replies with Gemini without posting to YouTube")
    parser.add_argument("--apply", action="store_true", help="Post drafted replies to YouTube")
    args = parser.parse_args()

    # Default to dry-run unless --apply is explicitly passed
    is_dry_run = not args.apply or args.dry_run

    print("\n" + "=" * 70)
    print("  THE SECRET PLACE — AUTONOMOUS COMMENT REPLY ENGINE")
    print(f"  Mode: {'DRY RUN (Preview Only)' if is_dry_run else 'LIVE PRODUCTION (Posting to YouTube)'}")
    print(f"  Batch Limit: {min(args.limit, 25)}")
    print("=" * 70 + "\n")

    youtube = None
    if all((CONFIG.youtube_client_id, CONFIG.youtube_client_secret, CONFIG.youtube_refresh_token)):
        try:
            from googleapiclient.discovery import build
            creds = _credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            print("[comments] YouTube Data API v3 authenticated successfully.")
        except Exception as exc:
            print(f"[comments] Could not authenticate with YouTube: {exc}")
            if not is_dry_run:
                print("[comments] Cannot run in live --apply mode without valid YouTube credentials.")
                return 1
    else:
        print("[comments] Notice: Running in credential-free simulation / dry-run mode.")

    engine = CommentReplyEngine(
        youtube_service=youtube,
        gemini_api_key=CONFIG.gemini_api_key or os.environ.get("GEMINI_API_KEY", ""),
    )

    # 1. Fetch Candidate Comments
    print(f"[comments] Fetching candidate comments (Video ID: {args.video_id or 'Channel-Wide Recent'})...")
    candidates = []
    try:
        candidates = engine.fetch_candidate_comments(
            video_id=args.video_id,
            max_results=min(args.limit, 25),
        )
    except QuotaExceededError as qe:
        print(f"[comments] YouTube Quota Exceeded: {qe}")
        return 0

    if not candidates:
        print("[comments] No unresponded candidate comments found.")
        print(f"[comments] Total comments logged in deduplication ledger: {len(engine.replied_log)}")
        return 0

    print(f"[comments] Found {len(candidates)} comments requiring pastoral response:\n")

    # 2. Process & Reply
    replied_count = 0
    for idx, c in enumerate(candidates, 1):
        print(f"[{idx}/{len(candidates)}] Comment from '{c.author_name}' ({c.category}):")
        print(f"  Text: \"{c.text}\"")

        reply_text = generate_reply_with_gemini(c, api_key=engine.gemini_api_key)
        print(f"  Drafted Reply: \"{reply_text}\"")

        try:
            success = engine.post_reply(c, reply_text, dry_run=is_dry_run)
            if success:
                replied_count += 1
        except QuotaExceededError as qe:
            print(f"[comments] YouTube Quota limit reached during reply batch: {qe}")
            break

        print("-" * 70)

    print(f"\n[comments] Completed batch. Successfully processed {replied_count} replies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
