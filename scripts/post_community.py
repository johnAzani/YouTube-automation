#!/usr/bin/env python3
"""CLI tool to manage and generate YouTube Community Tab Posts & Prayer Wall.

Generates:
  1. 1080x1080 square visual glassmorphic scripture cards.
  2. Weekly interactive scripture poll schedules.
  3. Nighttime prayer wall invitations.

Usage:
    python scripts/post_community.py --generate-weekly    # Generate 7-day schedule + image cards
    python scripts/post_community.py --preview            # Inspect the next scheduled community post
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.channel_capabilities import brand_for
from pipeline.channels import add_channel_arg, normalize_channel_id, scheduled_channels
from pipeline.community_posts import (
    community_schedule_for,
    export_weekly_community_manifest,
    publish_community_post,
    select_today_community_post,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube Community Tab Automation Engine")
    add_channel_arg(parser)
    parser.add_argument("--all-channels", action="store_true", help="Prepare today's community post for every scheduled channel")
    parser.add_argument("--generate-weekly", action="store_true", help="Generate 7-day community schedule and cards")
    parser.add_argument("--preview", action="store_true", help="Preview the current community post")
    parser.add_argument("--publish", action="store_true", help="Publish or stage today's community post")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run without live network calls")
    parser.add_argument("--out-dir", type=str, default="content/community", help="Output directory")

    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    targets = (
        list(scheduled_channels())
        if args.all_channels
        else [normalize_channel_id(args.channel)]
    )

    for channel_id in targets:
        brand = brand_for(channel_id)
        print("=" * 72)
        print(f"{brand.display_name.upper()} ({channel_id}) — YOUTUBE COMMUNITY TAB AUTOMATION ($0.00 COST LOCK)")
        print("=" * 72)

        if args.publish:
            post = select_today_community_post(channel_id=channel_id)
            res = publish_community_post(post, dry_run=args.dry_run, channel_id=channel_id)
            print(f"[+] Prepared: {res['post_id']} ({res['status']})")
            print(f"    Copy pack: {res['ready_pack']}")
            if res.get("card_path"):
                print(f"    Card:      {res['card_path']}")
            print(f"    Post at:   {res['composer']}")
            print("=" * 72)
            continue

        if args.generate_weekly or not args.preview:
            print(f"[*] Generating weekly liturgical community schedule in {out_dir}...")
            files = export_weekly_community_manifest(out_dir, channel_id=channel_id)
            print(f"    [+] Successfully generated {len(files)} files (manifests + cards):")
            for f in files:
                print(f"        • {f.name}")
            print("=" * 72)
            continue

        if args.preview:
            next_post = community_schedule_for(channel_id)[0]
            print(f"[*] Next Scheduled Community Post: {next_post.post_id} ({next_post.post_type})")
            print(f"    Title: {next_post.title}")
            print(f"    Body:\n{next_post.body_text}\n")
            if next_post.poll:
                print(f"    Poll Question: {next_post.poll.question}")
                for idx, opt in enumerate(next_post.poll.options, 1):
                    print(f"      [{idx}] {opt}")
            print("=" * 72)


if __name__ == "__main__":
    main()
