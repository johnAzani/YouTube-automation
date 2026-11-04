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


def _live_subscriber_count() -> int | None:
    """Read the freshest public subscriber count from the metrics snapshot.

    The growth autopilot runs metrics_snapshot first, which writes
    content/channel-metrics.json. Using that live number (instead of a hardcoded
    guess) keeps milestone celebrations honest. Returns None when unavailable.
    """
    import json

    path = REPO_ROOT / "content" / "channel-metrics.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        count = data.get("subscriber_count")
        return int(count) if count is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Celebrate Subscriber Milestones autonomously.")
    parser.add_argument("--subs", type=int, default=None,
                        help="Current subscriber count (default: read live from channel-metrics.json)")
    parser.add_argument("--dry-run", action="store_true", help="Render card without publishing")
    args = parser.parse_args()

    subs = args.subs
    if subs is None:
        subs = _live_subscriber_count()
        if subs is None:
            print("[milestone] No live subscriber count available; run metrics_snapshot first. "
                  "Skipping celebration rather than guessing.")
            return
        print(f"[milestone] Using live subscriber count from channel-metrics.json: {subs}")

    achieved, upcoming = get_current_milestone_status(current_subs=subs)

    print("==========================================================================")
    print("THE SECRET PLACE — SUBSCRIBER MILESTONE CELEBRATION ENGINE")
    print("==========================================================================")
    print(f"Current Subscriber Count: {subs}")

    if achieved:
        print(f"[+] Latest Milestone Achieved: {achieved.headline} ({achieved.subs_target} subs)")
        print(f"    Subheading: {achieved.subheading}")
        print(f"    Scripture:  {achieved.scripture_ref}")
        out_card = REPO_ROOT / "content" / "community" / f"milestone_{achieved.subs_target}.png"
        render_milestone_card(achieved, out_path=out_card)
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
