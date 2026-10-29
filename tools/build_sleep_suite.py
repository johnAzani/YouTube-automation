#!/usr/bin/env python3
"""CLI Tool to generate the Multi-Hour Bedtime Sleep Sanctuary Suite.

Generates:
  1. Procedural 432 Hz Solfeggio & Delta brainwave audio beds.
  2. DOCOGA REELS v2 16:9 widescreen glassmorphic visual plates.
  3. High-CTR YouTube bedroom sleep thumbnails.
  4. Production queue markdown job for autonomous scheduling.
  5. High-efficiency MP4 video renders.

Usage:
    python tools/build_sleep_suite.py --preview                     # 30-second rapid test render
    python tools/build_sleep_suite.py --duration 60 --generate-queue-job # 1-Hour Suite + Queue Job
    python tools/build_sleep_suite.py --thumbnail-only              # High-contrast YouTube thumbnail
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.sleep_suite import (
    MOVEMENTS,
    build_sleep_suite_manifest,
    generate_chapter_timestamps,
    render_sanctuary_plate,
    render_sleep_suite_video,
    render_sleep_thumbnail,
    synthesize_sleep_bed,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Hour Bedtime Sleep Sanctuary Engine")
    parser.add_argument("--duration", type=int, default=60, help="Target duration in minutes (default 60)")
    parser.add_argument("--preview", action="store_true", help="Generate a fast 30s preview clip")
    parser.add_argument("--output-dir", type=str, default="output/sleep_sanctuary", help="Output directory")
    parser.add_argument("--generate-queue-job", action="store_true", help="Write queue manifest to content/queue/")
    parser.add_argument("--thumbnail-only", action="store_true", help="Generate only the YouTube thumbnail")
    parser.add_argument("--plate-only", action="store_true", help="Render only the visual plate images")
    parser.add_argument("--audio-only", action="store_true", help="Generate only the procedural 432 Hz WAV bed")

    args = parser.parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("THE SECRET PLACE — BEDTIME SLEEP SANCTUARY ENGINE ($0.00 COST LOCK)")
    print("=" * 72)

    # 1. Thumbnail generation
    thumb_path = out_dir / "thumbnail.jpg"
    print(f"[*] Rendering 16:9 High-CTR Bedroom Sleep Thumbnail...")
    render_sleep_thumbnail(
        hook_title="8 HOURS OF PEACE",
        scripture_subtitle="PSALM 91, 23 & 121",
        sub_badge="432 Hz SLEEP FREQUENCY · UNDER HIS WINGS",
        out_path=thumb_path,
    )
    print(f"    [+] Saved thumbnail: {thumb_path}")

    if args.thumbnail_only:
        print("[*] Completed thumbnail-only run.")
        return

    # 2. Plate generation
    if args.plate_only:
        print(f"[*] Rendering sanctuary plates for {len(MOVEMENTS)} movements...")
        for m in MOVEMENTS:
            p_img = render_sanctuary_plate(m, verse_idx=0, width=1920, height=1080)
            p_path = out_dir / f"plate_movement_{m.movement_num}_{m.scripture.lower().replace(' ', '_')}.png"
            p_img.save(p_path)
            print(f"    [+] Saved plate: {p_path.name}")
        return

    # 3. Queue Manifest Generation
    if args.generate_queue_job:
        target_hrs = 0.5 if args.preview else (args.duration / 60.0)
        job_id = "0012"
        manifest_path = build_sleep_suite_manifest(job_id=job_id, target_hours=target_hrs)
        print(f"[*] Generated approved queue manifest: {manifest_path}")

    # 4. Audio / Video Rendering
    dur_sec = 30.0 if args.preview else float(args.duration * 60)
    print(f"[*] Target duration: {dur_sec:.1f}s ({dur_sec / 60:.1f} minutes)")

    if args.audio_only:
        audio_path = out_dir / f"sleep_bed_{int(dur_sec)}s_432hz.wav"
        print(f"[*] Synthesizing procedural 432 Hz Solfeggio audio bed...")
        synthesize_sleep_bed(duration_seconds=dur_sec, out_path=audio_path)
        print(f"    [+] Saved WAV: {audio_path} ({audio_path.stat().st_size / 1e6:.2f} MB)")
        return

    video_path = out_dir / f"sleep_sanctuary_{int(dur_sec)}s.mp4"
    print(f"[*] Rendering final video to {video_path}...")
    render_sleep_suite_video(video_path, duration_seconds=dur_sec, preview=args.preview)
    print(f"    [+] Complete! Final MP4 size: {video_path.stat().st_size / 1e6:.2f} MB")

    # Chapter summary
    chapters = generate_chapter_timestamps(MOVEMENTS, dur_sec)
    print("\nTIMESTAMPS & CHAPTERS:")
    for c in chapters:
        print(f"  {c['timestamp']} — {c['title']} ({c['duration']:.1f}s)")
    print("=" * 72)


if __name__ == "__main__":
    main()
