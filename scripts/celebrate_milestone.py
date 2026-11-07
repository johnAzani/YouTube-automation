#!/usr/bin/env python3
"""CLI script to check and celebrate subscriber milestones on the Community Tab.

Usage:
    python3 scripts/celebrate_milestone.py [--subs 1230] [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.milestones import (
    get_current_milestone_status,
    render_milestone_card,
)


def _live_subscriber_count(channel_id: str | None = None) -> int | None:
    """Read the freshest public subscriber count from the metrics snapshot.

    The growth autopilot runs metrics_snapshot first, which writes
    content/channel-metrics.json. Using that live number (instead of a hardcoded
    guess) keeps milestone celebrations honest. Returns None when unavailable.
    """
    import json

    candidates = (
        [REPO_ROOT / "content" / f"channel-metrics-{channel_id}.json"]
        if channel_id
        else []
    ) + [REPO_ROOT / "content" / "channel-metrics.json"]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if channel_id and data.get("channel_key") not in (None, channel_id):
                continue
            count = data.get("subscriber_count")
            return int(count) if count is not None else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return None


def main():
    from pipeline.channel_capabilities import brand_for
    from pipeline.channels import add_channel_arg, apply_channel_env
    from pipeline.config import CONFIG

    parser = argparse.ArgumentParser(description="Celebrate Subscriber Milestones autonomously.")
    add_channel_arg(parser)
    parser.add_argument("--subs", type=int, default=None,
                        help="Current subscriber count (default: read live from channel-metrics.json)")
    parser.add_argument("--dry-run", action="store_true", help="Render card without publishing")
    args = parser.parse_args()
    channel_id = apply_channel_env(args.channel)
    CONFIG.refresh()
    brand_title = brand_for(channel_id).display_name.upper()

    subs = args.subs
    if subs is None:
        subs = _live_subscriber_count(channel_id=args.channel)
        if subs is None:
            print("[milestone] No live subscriber count available; run metrics_snapshot first. "
                  "Skipping celebration rather than guessing.")
            return
        print(f"[milestone] Using live subscriber count from channel-metrics.json: {subs}")

    achieved, upcoming = get_current_milestone_status(current_subs=subs)

    print("==========================================================================")
    print(f"{brand_title} — SUBSCRIBER MILESTONE CELEBRATION ENGINE")
    print("==========================================================================")
    print(f"Current Subscriber Count: {subs}")

    if achieved:
        print(f"[+] Latest Milestone Achieved: {achieved.headline} ({achieved.subs_target} subs)")
        print(f"    Subheading: {achieved.subheading}")
        print(f"    Scripture:  {achieved.scripture_ref}")
        suffix = f"_{channel_id}" if args.channel else ""
        out_card = REPO_ROOT / "content" / "community" / f"milestone_{achieved.subs_target}{suffix}.png"
        render_milestone_card(achieved, out_path=out_card, channel_id=channel_id)
        print(f"[+] Celebratory Card Rendered: {out_card.relative_to(REPO_ROOT)}")
        print("\n--- Pastoral Community Tab Copy ---")
        print(achieved.pastoral_message)
        print("-----------------------------------")
    else:
        print("[*] No milestones achieved yet.")

    if upcoming:
        remaining = upcoming.subs_target - subs
        print(f"\n[*] Next Upcoming Milestone: {upcoming.headline} ({upcoming.subs_target} subs)")
        print(f"    Souls needed to reach next tier: {remaining}")

    print("==========================================================================")


if __name__ == "__main__":
    main()
