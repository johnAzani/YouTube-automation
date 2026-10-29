#!/usr/bin/env python3
"""CLI script to build Multi-Hour Bedtime Sleep Compilations under the $0.00 cost lock.

Usage:
    python3 scripts/build_sleep_compilation.py --tier 1hour --preview
    python3 scripts/build_sleep_compilation.py --tier 3hour --generate-queue-job
    python3 scripts/build_sleep_compilation.py --tier 8hour --thumbnail-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.sleep_compilations import (
    COMPILATION_TIERS,
    build_compilation_queue_manifest,
    calculate_compilation_chapters,
    render_sleep_compilation_video,
)
from pipeline.sleep_suite import render_sleep_thumbnail


def main():
    parser = argparse.ArgumentParser(description="Multi-Hour Bedtime Sleep Compilation Generator ($0.00 Lock)")
    parser.add_argument("--tier", choices=["1hour", "3hour", "8hour"], default="1hour", help="Compilation duration tier")
    parser.add_argument("--preview", action="store_true", help="Generate a fast 30-second preview clip")
    parser.add_argument("--render-video", action="store_true", help="Render video clip")
    parser.add_argument("--output-dir", type=str, default="output/compilations", help="Output directory")
    parser.add_argument("--generate-queue-job", action="store_true", help="Write queue manifest to content/queue/")
    parser.add_argument("--thumbnail-only", action="store_true", help="Generate only the 16:9 bedroom sleep thumbnail")
    parser.add_argument("--job-id", type=str, default=None, help="Custom job ID for queue manifest")

    args = parser.parse_args()
    tier = COMPILATION_TIERS[args.tier]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("==========================================================================")
    print("THE SECRET PLACE — MULTI-HOUR BEDTIME SLEEP COMPILATION ENGINE")
    print(f"Tier:            {args.tier.upper()} ({tier.target_hours} Hours Target)")
    print(f"Title:           {tier.title}")
    print(f"Cost Invariant:  $0.00 / month forever (In-house DSP + DOCOGA REELS v2)")
    print("==========================================================================")

    # 1. Render Thumbnail
    thumb_path = out_dir / f"thumbnail_{args.tier}.jpg"
    print(f"[*] Rendering 16:9 High-CTR Bedroom Sleep Thumbnail...")
    render_sleep_thumbnail(
        hook_title=tier.thumb_title,
        scripture_subtitle=tier.thumb_subtitle,
        sub_badge="432 Hz SLEEP FREQUENCY · UNDER HIS WINGS",
        out_path=thumb_path,
    )
    print(f"[+] Saved thumbnail: {thumb_path}")

    if args.thumbnail_only:
        print("[+] Thumbnail-only run complete.")
        return

    # 2. Queue Manifest Generation
    if args.generate_queue_job:
        manifest_path = build_compilation_queue_manifest(tier_id=args.tier, job_id=args.job_id)
        print(f"[+] Generated approved queue manifest: {manifest_path.relative_to(REPO_ROOT)}")

    # 3. Chapters
    total_seconds = 30.0 if args.preview else (tier.target_hours * 3600.0)
    chapters = calculate_compilation_chapters(total_seconds)
    print("\nTIMESTAMPS & CHAPTERS:")
    for c in chapters[:8]:
        print(f"  {c['timestamp']} — {c['title']} ({c['duration']:.1f}s)")
    if len(chapters) > 8:
        print(f"  ... and {len(chapters) - 8} additional chapters.")

    # 4. Video Assembly (only if requested via --preview or --render-video)
    if args.preview or args.render_video:
        dur_sec = 30.0 if args.preview else min(300.0, total_seconds)
        video_path = out_dir / f"sleep_compilation_{args.tier}_{int(dur_sec)}s.mp4"
        print(f"\n[*] Rendering compilation video to {video_path} ({dur_sec:.1f}s)...")
        render_sleep_compilation_video(video_path, duration_seconds=dur_sec, tier_id=args.tier, preview=args.preview)
        print(f"[+] Render complete! Size: {video_path.stat().st_size / 1e6:.2f} MB")
    print("==========================================================================")


if __name__ == "__main__":
    main()
