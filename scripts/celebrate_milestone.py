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


def main():
    parser = argparse.ArgumentParser(description="Celebrate Subscriber Milestones autonomously.")
    parser.add_argument("--subs", type=int, default=1230, help="Current channel subscriber count")
    parser.add_argument("--dry-run", action="store_true", help="Render card without publishing")
    args = parser.parse_args()

    achieved, upcoming = get_current_milestone_status(current_subs=args.subs)

    print("==========================================================================")
    print("THE SECRET PLACE — SUBSCRIBER MILESTONE CELEBRATION ENGINE")
    print("==========================================================================")
    print(f"Current Subscriber Count: {args.subs}")

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
        remaining = upcoming.subs_target - args.subs
        print(f"\n[*] Next Upcoming Milestone: {upcoming.headline} ({upcoming.subs_target} subs)")
        print(f"    Souls needed to reach next tier: {remaining}")

    print("==========================================================================")


if __name__ == "__main__":
    main()
