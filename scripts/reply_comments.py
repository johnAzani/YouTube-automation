#!/usr/bin/env python3
"""Autonomous / Assisted YouTube Comment Reply CLI for The Secret Place.

Audits recent viewer comments, categorizes intent (Prayer Request, Amen,
Testimony, Inquiry, Scam), generates context-aware pastoral replies using
Google Gemini Brain, and safely publishes them via YouTube Data API v3 while
enforcing strict anti-spam, anti-shadowban, and $0.00 quota safety invariants.

Usage:
    python scripts/reply_comments.py --simulate            # Run simulation with 6 realistic viewer comments
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
    parser.add_argument("--simulate", action="store_true", help="Run simulated cohort of typical viewer comments to verify response logic")
    args = parser.parse_args()

    # Default to dry-run unless --apply is explicitly passed
    is_dry_run = not args.apply or args.dry_run

    print("\n" + "=" * 70)
    print("  THE SECRET PLACE — AUTONOMOUS COMMENT REPLY ENGINE")
    print(f"  Mode: {'SIMULATION / PREVIEW' if (args.simulate or is_dry_run) else 'LIVE PRODUCTION (Posting to YouTube)'}")
    print(f"  Batch Limit: {min(args.limit, 25)}")
    print("=" * 70 + "\n")

    youtube = None
    if not args.simulate and all((CONFIG.youtube_client_id, CONFIG.youtube_client_secret, CONFIG.youtube_refresh_token)):
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
    elif not args.simulate:
        print("[comments] Notice: Running in credential-free simulation / dry-run mode.")

    engine = CommentReplyEngine(
        youtube_service=youtube,
        gemini_api_key=CONFIG.gemini_api_key or os.environ.get("GEMINI_API_KEY", ""),
    )

    # 1. Fetch Candidate Comments (or generate simulation cohort)
    candidates = []
    if args.simulate:
        from pipeline.comment_replies import CommentItem
        print("[comments] Running simulation with 6 realistic viewer comments...")
        simulated_raw = [
            ("c_sim_1", "Grace Hopper", "Amen! Thank you Lord, I receive this peace over my family tonight"),
            ("c_sim_2", "Sarah Jenkins", "Please pray for my mother Mary who is undergoing cancer surgery tomorrow morning. I am so scared."),
            ("c_sim_3", "David Kim", "I have struggled with severe insomnia for two weeks, this was the only prayer that let me sleep deeply."),
            ("c_sim_4", "Mark Thompson", "Which Bible translation are you reading from in this video?"),
            ("c_sim_5", "WhatsAppBot", "Contact Prophet John on WhatsApp +1234567890 for instant miracle prayers!"),
            ("c_sim_6", "AnonymousSoul", "I feel so hopeless and broken tonight, I want to end my life"),
        ]
        for cid, author, text in simulated_raw:
            cat = classify_comment_intent(text)
            if cat == "SPAM_SCAM":
                print(f"[comments] 🛡️  SPAM SHIELD: Filtered malicious comment from '{author}' (silently skipped)")
                continue
            candidates.append(
                CommentItem(
                    comment_id=cid,
                    video_id=args.video_id or "7RDX0fbIOtQ",
                    author_name=author,
                    author_channel_id="UC_SIM_" + author.replace(" ", ""),
                    text=text,
                    published_at="2026-10-29T14:00:00Z",
                    category=cat,
                )
            )
    else:
        print(f"[comments] Fetching candidate comments (Video ID: {args.video_id or 'Channel-Wide Recent'})...")
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
