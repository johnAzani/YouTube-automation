#!/usr/bin/env python3
"""Google Gemini Brain CLI & Automation Runner.

Enables Google Gemini to act as the autonomous brain of The Secret Place, performing
scripture research, longform devotional authoring, factchecking, and queue replenishment.

Usage:
    python scripts/gemini_brain.py --audit            # Audit brain equipment, API status, and runway
    python scripts/gemini_brain.py --equip            # Display equipped modules and rubrics
    python scripts/gemini_brain.py --generate-next    # Author and stage the next scripture release
    python scripts/gemini_brain.py --auto-replenish   # Replenish queue if runway < 2.0 days
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.brain_equipment.equipment_registry import list_equipped_modules
from pipeline.gemini_brain import GeminiBrain


def cmd_audit(brain: GeminiBrain) -> int:
    audit = brain.audit_status()
    equipped = list_equipped_modules()
    api_status = "ONLINE (google.genai connected)" if brain.is_api_available() else "STANDBY / OFFLINE (equipped templates active)"

    print("=" * 76)
    print("THE SECRET PLACE — GOOGLE GEMINI AUTONOMOUS BRAIN AUDIT")
    print("=" * 76)
    print(f"Brain Model:        {brain.model}")
    print(f"Gemini API Status:  {api_status}")
    print(f"Channel Equity:     {audit.subscribers:,} Subscribers")
    print(f"Watch Hours Target: {audit.watch_hours_target:,} Public Hours")
    print(f"Queue Runway:       {audit.runway_days} Days ({audit.longform_approved_count} LF + {audit.shorts_approved_count} Shorts approved)")
    print("-" * 76)
    print("EQUIPPED BRAIN MODULES:")
    for mod_name, meta in equipped.items():
        print(f"  • {mod_name:<30} ({meta['size_bytes']:,} bytes)")
    print("-" * 76)
    cand = brain.select_next_scripture()
    print("NEXT RECOMMENDED SCRIPTURE:")
    print(f"  • Job ID:     {cand['id']}")
    print(f"  • Scripture:  {cand['scripture']}")
    print(f"  • Theme:      {cand['theme']}")
    print(f"  • Hook:       \"{cand['hook']}\"")
    print("=" * 76)
    return 0


def cmd_equip() -> int:
    equipped = list_equipped_modules()
    print("=" * 76)
    print("THE SECRET PLACE — ACTIVE GEMINI BRAIN EQUIPMENT REGISTRY")
    print("=" * 76)
    for mod_name, meta in equipped.items():
        print(f"MODULE: {mod_name} ({meta['size_bytes']} bytes)")
    print("=" * 76)
    return 0


def cmd_generate_next(brain: GeminiBrain) -> int:
    cand = brain.select_next_scripture()
    print(f"[gemini-brain] Authoring next scripture: {cand['scripture']} (Job {cand['id']})...")
    res = brain.replenish_pipeline(min_runway_days=999.0)  # force generation
    if res:
        print(f"[gemini-brain] Successfully authored & staged Job {res.job_id}:")
        print(f"  - Longform:   {res.longform_path}")
        print(f"  - Short:      {res.short_manifest_path}")
        print(f"  - Factcheck:  {res.factcheck_path}")
        print(f"  - Stats:      {res.word_count} words across {res.scene_count} scenes")
        return 0
    return 1


def cmd_auto_replenish(brain: GeminiBrain, min_days: float) -> int:
    res = brain.replenish_pipeline(min_runway_days=min_days)
    if res:
        print(f"[gemini-brain] Queue replenished with Job {res.job_id} ({res.scripture}).")
        return 0
    print("[gemini-brain] Queue is already well-stocked. No replenishment performed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Google Gemini Brain Automation CLI")
    parser.add_argument("--audit", action="store_true", help="Audit brain equipment and queue runway")
    parser.add_argument("--equip", action="store_true", help="List equipped brain knowledge modules")
    parser.add_argument("--generate-next", action="store_true", help="Generate and stage the next scripture release")
    parser.add_argument("--auto-replenish", action="store_true", help="Replenish queue if runway < threshold")
    parser.add_argument("--min-runway", type=float, default=2.0, help="Minimum runway days threshold (default: 2.0)")

    args = parser.parse_args(argv)
    brain = GeminiBrain()

    if args.equip:
        return cmd_equip()
    if args.generate_next:
        return cmd_generate_next(brain)
    if args.auto_replenish:
        return cmd_auto_replenish(brain, args.min_runway)

    return cmd_audit(brain)


if __name__ == "__main__":
    sys.exit(main())
