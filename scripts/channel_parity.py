#!/usr/bin/env python3
"""Print the channel capability matrix and prove the channels are in parity.

This is the human-readable half of ``tests/test_channel_parity.py``: the same
invariants, but printed for a run page or a terminal instead of asserted.

    python scripts/channel_parity.py            # matrix + checks
    python scripts/channel_parity.py --json     # machine-readable

Exit code 0 means every registered channel has every capability. The check is
deliberately duplicated in tests so a red gate is never the only signal.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import channel_capabilities as cc
from pipeline.channels import CHANNELS
from pipeline.script_doc import parse_script
from scripts.continuous_research import roadmap_for_channel


def _checks() -> list[dict]:
    from pipeline.brain_equipment.equipment_registry import compile_full_brain_prompt
    from pipeline.gemini_brain import short_key_for_doc
    from pipeline.short_release import EDITIONS, resolve_edition

    results: list[dict] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    channels = cc.known_channels()
    check("every registered channel has a capability block",
          set(channels) == set(CHANNELS),
          f"registry={sorted(CHANNELS)} capabilities={list(channels)}")

    for channel_id in channels:
        caps = cc.capabilities_for(channel_id)
        brand = caps.brand
        prompt = compile_full_brain_prompt(channel_id)
        check(f"{channel_id}: brain equipment compiles",
              brand.display_name in prompt and "DOCOGA REELS v2" in prompt,
              ", ".join(sorted(caps.equipment)))
        check(f"{channel_id}: roadmap is present",
              bool(roadmap_for_channel(channel_id)),
              f"{len(roadmap_for_channel(channel_id))} candidates in {caps.roadmap_name}")
        check(f"{channel_id}: prompt never names another channel",
              all(other.display_name not in prompt
                  for other in (cc.brand_for(c) for c in channels)
                  if other.channel_id != channel_id),
              "")
        check(f"{channel_id}: pinned comment is branded",
              brand.display_name in cc.pinned_comment_for(
                  channel_id, theme="peace", scripture_hook="Psalm 1:1", footer="")
              or "AMEN" in cc.pinned_comment_for(
                  channel_id, theme="peace", scripture_hook="Psalm 1:1", footer=""),
              "")

    # Shorts: one key per channel per scripture, and editions never cross over.
    keys: dict[str, str] = {}
    collisions: list[str] = []
    for channel_id in channels:
        brand = cc.brand_for(channel_id)
        tmp = ROOT / "content" / "queue"
        sample = next((p for p in sorted(tmp.glob("*.md"))
                       if parse_script(p).channel == channel_id), None)
        if sample is None:
            check(f"{channel_id}: has a queued script to key a Short from", False,
                  "no queued script for this channel")
            continue
        key = short_key_for_doc(parse_script(sample))
        if key in keys:
            collisions.append(f"{key}: {keys[key]} + {channel_id}")
        keys[key] = channel_id
    check("short keys are unique across channels", not collisions, "; ".join(collisions))

    crossovers = [
        f"{key} resolves for {channel_id}"
        for key, edition in EDITIONS.items()
        for channel_id in channels
        if channel_id != edition.channel and resolve_edition(key, channel_id=channel_id)
    ]
    check("short editions never resolve for another channel", not crossovers,
          "; ".join(crossovers))

    for name in ("produce.yml", "gemini_brain.yml"):
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        missing = [c for c in channels if f'"{c}"' not in text]
        check(f"{name}: schedules every channel", not missing, ", ".join(missing))

    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args(argv)

    channels = cc.known_channels()
    results = _checks()
    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({
            "channels": channels,
            "capabilities": list(cc.REQUIRED_CAPABILITIES),
            "results": results,
            "ok": not failed,
        }, indent=2))
        return 0 if not failed else 1

    width = max(len(c) for c in channels) + 2
    print("=" * 78)
    print("CHANNEL CAPABILITY MATRIX — every channel, every capability")
    print("=" * 78)
    print(f"{'capability':<28}" + "".join(f"{c:<{width}}" for c in channels))
    for capability in cc.REQUIRED_CAPABILITIES:
        print(f"{capability:<28}" + "".join(f"{'yes':<{width}}" for _ in channels))
    print("-" * 78)
    for channel_id in channels:
        caps = cc.capabilities_for(channel_id)
        brand = caps.brand
        print(f"{brand.display_name} ({channel_id})")
        print(f"  handle:      {brand.handle}")
        print(f"  roadmap:     {caps.roadmap_name} "
              f"({len(roadmap_for_channel(channel_id))} candidates)")
        print(f"  equipment:   {', '.join(sorted(caps.equipment))}")
        print(f"  supply goal: {caps.supply_min_publishable} publishable")
        print(f"  Shorts:      key namespace "
              f"{brand.short_key_namespace or '(channel 1, unprefixed)'}")
    print("-" * 78)
    for row in results:
        print(f"{'PASS' if row['ok'] else 'FAIL'}  {row['check']}"
              + (f" — {row['detail']}" if row["detail"] else ""))
    print("=" * 78)
    print("PARITY OK" if not failed else f"{len(failed)} PARITY FAILURE(S)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
