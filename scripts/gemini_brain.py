#!/usr/bin/env python3
"""Google Gemini Brain CLI & Automation Runner.

Enables Google Gemini to act as the autonomous brain of The Secret Place, performing
scripture research, longform devotional authoring, factchecking, and queue replenishment.

Usage:
    python scripts/gemini_brain.py --audit            # Audit brain equipment, API status, and runway
    python scripts/gemini_brain.py --equip            # Display equipped modules and rubrics
    python scripts/gemini_brain.py --generate-next    # Author and stage the next scripture release
    python scripts/gemini_brain.py --auto-replenish   # Replenish queue if runway < 2.0 days
    python scripts/gemini_brain.py --author-shorts    # Author specs for Shorts with no renderer
    python scripts/gemini_brain.py --ensure-supply    # Make the long-form queue publishable
    python scripts/gemini_brain.py --preflight        # Can this runner reach Gemini at all?
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.brain_equipment.equipment_registry import list_equipped_modules
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain


def cmd_audit(brain: GeminiBrain) -> int:
    audit = brain.audit_status()
    equipped = list_equipped_modules()
    status = brain.api_status()
    if status["client_ready"]:
        api_status = "ONLINE (google.genai connected)"
    elif status["key_present"]:
        api_status = f"KEY PRESENT, CLIENT FAILED — {status['reason']}"
    else:
        api_status = f"NO KEY HERE — {status['reason']}"

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
    try:
        res = brain.replenish_pipeline(min_runway_days=999.0)  # force generation
    except BrainAuthoringError as exc:
        print(f"[gemini-brain] Refusing to author: {exc}")
        print("::error title=Brain cannot author::see the reason above")
        return 1
    if res:
        print(f"[gemini-brain] Successfully authored & staged Job {res.job_id}:")
        print(f"  - Longform:   {res.longform_path}")
        print(f"  - Short:      {res.short_manifest_path}")
        print(f"  - Factcheck:  {res.factcheck_path}")
        print(f"  - Stats:      {res.word_count} words across {res.scene_count} scenes")
        return 0
    return 1


def cmd_auto_replenish(brain: GeminiBrain, min_days: float) -> int:
    """The scheduled brain pass: keep `min_days` of runway publishable.

    Goes through the same supply loop as `--ensure-supply` rather than calling
    `replenish_pipeline` directly, because authoring alone was how a queue grew to
    twenty-one approved scripts that no run could publish.
    """
    # Days of runway -> scripts to keep publishable. This read "two release slots
    # per day" while produce.yml fires three (06:14, 14:14, 19:14), so a nightly
    # pass aimed at one publishable script left the evening slot with nothing.
    from pipeline.supply import SLOTS_PER_DAY

    wanted = max(1, math.ceil(min_days * SLOTS_PER_DAY))
    return cmd_ensure_supply(brain, max_expansions=SLOTS_PER_DAY, target=900,
                             min_publishable=wanted)


def cmd_author_shorts(brain: GeminiBrain) -> int:
    """Author the scene spec for every queued Short that cannot render yet, and replenish Shorts runway."""
    rows = brain.author_missing_shorts()
    rows.extend(brain.replenish_shorts_queue(min_ready=6))
    if not rows:
        print("[gemini-brain] Shorts queue is empty. Nothing to author.")
        return 0
    for row in rows:
        print(f"[gemini-brain]   {row['file']}: {row['verdict']} — {row['reason']}")
    authored = [r for r in rows if r["verdict"] == "authored"]
    failed = [r for r in rows if r["verdict"] in {"failed", "no_source", "unreadable", "no_key"}]
    print(f"[gemini-brain] Authored {len(authored)} Short spec(s); {len(failed)} still blocked.")
    if failed and not authored and any(r["verdict"] == "failed" for r in failed):
        # A brain that cannot author is a real fault; a missing source is not.
        return 1
    return 0


def cmd_preflight(brain: GeminiBrain) -> int:
    """Prove the runner can reach Gemini before anything depends on it.

    A wrong answer here is expensive: the key has been configured since week one
    and narrates every video, while the authoring path reported "GEMINI_API_KEY
    unavailable" because the client had failed to start for an unrelated reason.
    """
    status = brain.api_status()
    print(f"[preflight] key present:  {status['key_present']}")
    print(f"[preflight] client ready: {status['client_ready']}")
    print(f"[preflight] model:        {status['model']}")
    print(f"[preflight] reason:       {status['reason']}")
    in_ci = bool(os.environ.get("GITHUB_ACTIONS"))
    if not status["client_ready"]:
        print(f"::error title=Gemini unreachable::{status['reason']}")
        return 1
    try:
        resp = brain._client.models.generate_content(
            model=brain.model, contents="Reply with the single word: ready")
        text = (getattr(resp, "text", "") or "").strip()
        print(f"[preflight] live call:    {text[:60] or '(empty response)'}")
        return 0
    except Exception as exc:  # noqa: BLE001
        where = "GitHub Actions" if in_ci else "this machine"
        print(f"::error title=Gemini call failed ({where})::{type(exc).__name__}: {exc}")
        return 1


def cmd_ensure_supply(brain: GeminiBrain, max_expansions: int, target: int,
                      min_publishable: int | None = None) -> int:
    """Lengthen the backlog, author if still empty, verify — one unattended loop."""
    from pipeline.supply import SLOTS_PER_DAY, ensure_supply

    if min_publishable is None:
        min_publishable = SLOTS_PER_DAY
    report = ensure_supply(brain, limit=max_expansions, target=target,
                           min_publishable=min_publishable)
    for row in report.expanded:
        state = "WROTE" if row.get("written") else "skipped"
        print(f"[brain] expand {row['job_id']}: {row['before']} -> {row['after']} words {state}")
        for problem in row.get("problems", []):
            print(f"[brain]   ! {problem}")
    for row in report.authored_all:
        print(f"[brain] author: {row.get('job_id', '?')} -> {row.get('words', '?')} words "
              f"({row.get('reason', row.get('status', 'ok'))})")
    print(f"[brain] supply: {report.summary()}")
    for reason in report.blocked:
        print(f"[brain] blocked: {reason}")

    if report.ok:
        return 0
    print("::error title=Long-form supply empty::nothing in content/queue can publish")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Google Gemini Brain Automation CLI")
    parser.add_argument("--audit", action="store_true", help="Audit brain equipment and queue runway")
    parser.add_argument("--equip", action="store_true", help="List equipped brain knowledge modules")
    parser.add_argument("--generate-next", action="store_true", help="Generate and stage the next scripture release")
    parser.add_argument("--auto-replenish", action="store_true", help="Replenish queue if runway < threshold")
    parser.add_argument("--preflight", action="store_true",
                        help="Check the key and make one live model call, then exit")
    parser.add_argument("--ensure-supply", action="store_true",
                        help="Lengthen the backlog and author a script if the queue is empty")
    parser.add_argument("--min-publishable", type=int, default=1,
                        help="Leave at least this many publishable scripts behind")
    parser.add_argument("--max-expansions", type=int, default=3,
                        help="Model calls this run may spend lengthening old scripts")
    parser.add_argument("--target", type=int, default=900, help="Target word count when expanding")
    parser.add_argument("--author-shorts", action="store_true",
                        help="Author scene specs for queued Shorts that have no renderer")
    parser.add_argument("--min-runway", type=float, default=2.0, help="Minimum runway days threshold (default: 2.0)")

    args = parser.parse_args(argv)
    brain = GeminiBrain()

    if args.equip:
        return cmd_equip()
    if args.generate_next:
        return cmd_generate_next(brain)
    if args.preflight:
        return cmd_preflight(brain)
    if args.ensure_supply:
        return cmd_ensure_supply(brain, args.max_expansions, args.target,
                                 args.min_publishable)
    if args.author_shorts:
        return cmd_author_shorts(brain)
    if args.auto_replenish:
        return cmd_auto_replenish(brain, args.min_runway)

    return cmd_audit(brain)


if __name__ == "__main__":
    sys.exit(main())
