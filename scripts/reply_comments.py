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
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.comment_replies import (
    CommentFetchError,
    CommentReplyEngine,
    classify_comment_intent,
    generate_reply_with_gemini,
)
from pipeline.config import CONFIG
from pipeline.quota_handler import GeminiQuotaExceededError, QuotaExceededError
from pipeline.upload import _credentials


def _summary(rows: dict) -> None:
    """Print a machine-readable line and write the GitHub step summary."""
    print("[comments] result: " + json.dumps(rows))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("### 💬 Comment replies\n\n")
            for key, value in rows.items():
                fh.write(f"- {key}: `{value}`\n")
            fh.write("\n")
    except Exception:  # noqa: BLE001 — a summary is never worth failing a run
        pass


def _crisis_body(held: list[dict]) -> str:
    body = [
        "A viewer disclosed distress in a comment. The reply automation held it "
        "instead of posting publicly — a hotline reply under someone's self-harm "
        "disclosure labels them in front of every other viewer.",
        "",
        "Please reply personally when you can.",
        "",
    ]
    for row in held:
        body += [
            f"### {row['author']}",
            f"- comment: `{row['comment_id']}` on video `{row['video_id']}`",
            f"- they wrote: \"{row['text'][:400]}\"",
            f"- suggested reply (unposted): {row['draft']}",
            "",
        ]
    return "\n".join(body)


def unreported(known_text: str, held: list[dict]) -> list[dict]:
    """The held comments nobody has been told about yet.

    The comment job runs on a schedule, so an unresolved disclosure was filed as a
    brand-new issue every time it ran: #206, #207 and #209 were the same viewer.
    Three issues for one person is how a real escalation gets lost in noise. A
    comment already named in an open issue is already reported; anything new is
    appended to that same issue rather than opening another.
    """
    return [row for row in held if str(row["comment_id"]) not in known_text]


def _gh(*args: str):
    import subprocess
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=False)


def _escalate_crisis(held: list[dict]) -> str:
    """Record held disclosures once, and say where. Returns what happened."""
    text = _crisis_body(held)
    print(text)
    if not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        return "not filed (no token)"
    _gh("label", "create", "viewer-crisis", "--color", "b60205",
        "--description", "A viewer disclosed distress; needs a personal reply")

    import json as _json
    listing = _gh("issue", "list", "--label", "viewer-crisis", "--state", "open",
                  "--json", "number", "--limit", "5")
    numbers = []
    if listing.returncode == 0 and listing.stdout.strip():
        try:
            numbers = [row["number"] for row in _json.loads(listing.stdout)]
        except (ValueError, KeyError, TypeError):
            numbers = []

    if numbers:
        number = str(numbers[0])
        detail = _gh("issue", "view", number, "--json", "body,comments")
        known = detail.stdout if detail.returncode == 0 else ""
        fresh = unreported(known, held)
        if not fresh:
            print(f"[replies] the held disclosure is already reported in issue #{number}")
            return f"already reported in #{number}"
        _gh("issue", "comment", number, "--body", _crisis_body(fresh))
        return f"added {len(fresh)} new comment(s) to #{number}"

    created = _gh("issue", "create", "--title",
                  f"Viewer in distress — {len(held)} comment(s) need a personal reply",
                  "--label", "viewer-crisis", "--body", text)
    return created.stdout.strip() if created.returncode == 0 else "could not file an issue"


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous / Assisted YouTube Comment Reply System")
    parser.add_argument("--video-id", help="Target specific YouTube video ID (e.g. 7RDX0fbIOtQ)")
    parser.add_argument("--limit", type=int, default=10, help="Max comments to process (default: 10, max: 25)")
    parser.add_argument("--dry-run", action="store_true", help="Draft replies with Gemini without posting to YouTube")
    parser.add_argument("--apply", action="store_true", help="Post drafted replies to YouTube")
    parser.add_argument("--simulate", action="store_true", help="Run simulated cohort of typical viewer comments to verify response logic")
    parser.add_argument("--reply-to-crisis", action="store_true",
                        help="Also post the public lifeline reply on crisis comments "
                             "(default: hold them for a human reply)")
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
            # Not an error: the free tier resets. Say when, and exit green so the
            # dashboard does not cry wolf every night at the quota boundary.
            print(f"[comments] YouTube quota reached — resuming after {qe}")
            _summary({"mode": "quota_paused", "reason": str(qe)})
            return 0
        except CommentFetchError as fe:
            # This is the fault that used to hide: the old code printed the error
            # and returned an empty list, so "the API call was invalid" read exactly
            # like "nobody commented today".
            print(f"[comments] FAILED — {fe}", file=sys.stderr)
            print(f"::error title=Comment fetch failed::{fe}")
            _summary({"mode": "fetch_failed", "reason": str(fe)})
            return 1

    if not candidates:
        print("[comments] No unresponded candidate comments found.")
        print(f"[comments] Total comments logged in deduplication ledger: {len(engine.replied_log)}")
        _summary({"mode": "idle", "candidates": 0, "posted": 0,
                  "ledger": len(engine.replied_log)})
        return 0

    print(f"[comments] Found {len(candidates)} comments requiring pastoral response:\n")

    # 2. Process & Reply
    replied_count = 0
    failures: list[str] = []
    held: list[dict] = []
    for idx, c in enumerate(candidates, 1):
        print(f"[{idx}/{len(candidates)}] Comment from '{c.author_name}' ({c.category}):")
        print(f"  Text: \"{c.text}\"")

        reply_text = generate_reply_with_gemini(c, api_key=engine.gemini_api_key)
        print(f"  Drafted Reply: \"{reply_text}\"")

        if c.category == "CRISIS_DISTRESS":
            held.append({"comment_id": c.comment_id, "author": c.author_name,
                         "video_id": c.video_id, "text": c.text, "draft": reply_text})

        try:
            success = engine.post_reply(c, reply_text, dry_run=is_dry_run,
                                        allow_crisis=args.reply_to_crisis)
            if success:
                replied_count += 1
            elif c.category != "CRISIS_DISTRESS":
                failures.append(c.comment_id)
        except QuotaExceededError as qe:
            print(f"[comments] YouTube quota reached during the batch: {qe}")
            break

        print("-" * 70)

    attempted = len(candidates) - len(held)
    print(f"\n[comments] Completed batch: {replied_count} posted, "
          f"{len(failures)} failed, {len(held)} held for a human, out of {len(candidates)}.")
    _summary({"mode": "dry_run" if is_dry_run else "live",
              "candidates": len(candidates), "posted": replied_count,
              "failed": len(failures), "held_for_human": len(held),
              "ledger": len(engine.replied_log),
              "target": args.video_id or "all channel videos"})
    if held:
        _escalate_crisis(held)
    if attempted and not replied_count and failures:
        print("::error title=No reply was posted::every insert failed — see the log above")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
