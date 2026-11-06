#!/usr/bin/env python3
"""Google Gemini Brain CLI & Automation Runner.

Runs the autonomous brain of whichever channel ``--channel`` selects (default
``secret-place``): scripture research, longform devotional authoring, factchecking,
Shorts authoring and queue replenishment, with that channel's own equipment,
roadmap, branding and Gemini quota pool. Both channels run this identical code.

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
from pipeline import gemini_brain as gemini_brain_module
from pipeline.gemini_brain import BrainAuthoringError, GeminiBrain


def cmd_audit(brain: GeminiBrain) -> int:
    audit = brain.audit_status()
    print(f"Channel:            {brain.channel_id} ({brain.channel.display_name})")
    equipped = list_equipped_modules()
    status = brain.api_status()
    if status["client_ready"]:
        api_status = "ONLINE (google.genai connected)"
    elif status["key_present"]:
        api_status = f"KEY PRESENT, CLIENT FAILED — {status['reason']}"
    else:
        api_status = f"NO KEY HERE — {status['reason']}"

    print("=" * 76)
    print(f"{brain.channel.display_name.upper()} — GOOGLE GEMINI AUTONOMOUS BRAIN AUDIT")
    print("=" * 76)
    # Supply is measured for *this* brain's channel; the equity figures come from
    # the metrics snapshot, which currently only has Channel 1 history, so they are
    # labelled rather than presented as this channel's numbers.
    from pipeline.short_release import queue_report
    from pipeline.supply import publishable_longform

    publishable = len(publishable_longform(channel_id=brain.channel_id))
    shorts_ready = sum(1 for row in queue_report(channel_id=brain.channel_id)
                       if row["verdict"] == "ready")
    print(f"Brain Model:        {brain.model}")
    print(f"Gemini API Status:  {api_status}")
    print(f"Channel Equity:     {audit.subscribers:,} Subscribers "
          f"(metrics snapshot — Channel 1 history only)")
    print(f"Watch Hours Target: {audit.watch_hours_target:,} Public Hours")
    print(f"Queue Runway:       {publishable} publishable long-form + "
          f"{shorts_ready} renderable Short(s) for {brain.channel.display_name}")
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


def cmd_equip(channel_id: str | None = None) -> int:
    from pipeline.channel_capabilities import capabilities_for

    equipped = list_equipped_modules()
    display = capabilities_for(channel_id).brand.display_name
    print("=" * 76)
    print(f"{display.upper()} — ACTIVE GEMINI BRAIN EQUIPMENT REGISTRY")
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


def cmd_ensure_supply_for_channel(channel_id: str, max_expansions: int = 3,
                                  target: int = 900,
                                  min_publishable: int | None = None,
                                  min_runway: float | None = None) -> int:
    """Run the supply loop for one named channel with its own brain/quota.

    This is the Morning Altar entry point: it builds a channel-scoped brain
    (PRAYER2_ Gemini pool, morning roadmap/branding, no Short staging) and
    counts only that channel's publishable queue. Fail-safe: an exhausted
    free tier or rejected script reports blocked and returns non-zero for
    the scheduled workflow, or an idle notice for the Produce repair pass —
    it never spends money and never approves defective work.
    """
    from pipeline.gemini_brain import GeminiBrain as _Brain
    brain = _Brain(channel_id=channel_id)
    if min_runway is not None:
        wanted = max(1, int(min_runway * 3 + 0.999))
        return cmd_ensure_supply(brain, max_expansions, target,
                                 min_publishable=wanted)
    return cmd_ensure_supply(brain, max_expansions, target,
                             min_publishable=min_publishable)


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
                             min_publishable=wanted,
                             channel_id=getattr(brain, "channel_id", None))


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


#: Models the probe asks about: every candidate the code can choose, in the order it
#: would choose them. Keeping this list next to the probe means the answer to "what
#: can we actually use today?" is one CI run away.
PROBE_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash",
                "gemini-3.8-flash", "gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts")


def cmd_probe_models(brain: GeminiBrain, generate: bool = False) -> int:
    """Ask the API, per model, whether it exists *and* whether it answers.

    `models.get` costs no generation quota and settles existence, but on 6 November
    every one of those models existed while `gemini-3.8-flash` answered `503` for
    three and a half hours. Existence is not service. With `generate`, one request of
    one token per model measures service — six requests in total, once per push, on
    models that are otherwise idle.

    Prints a table and one annotation per model, so the verdict is readable in the
    run summary without downloading anything.
    """
    if brain._client is None:
        print(f"::error title=Gemini probe::no client — {brain.api_status()['reason']}")
        return 1
    ok = 0
    for name in PROBE_MODELS:
        meta, serves, detail = "", "", ""
        try:
            info = brain._client.models.get(model=name)
            meta = (f"in={getattr(info, 'input_token_limit', '?')} "
                    f"out={getattr(info, 'output_token_limit', '?')}")
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}"
            print(f"::error title=Gemini probe::{name} — metadata unavailable — {detail}")
            print(f"[probe] {name:28} MISSING  {detail[:120]}")
            continue
        if generate:
            try:
                brain._client.models.generate_content(
                    model=name,
                    contents="Reply with the single word: ready",
                    config={"max_output_tokens": 1},
                )
                serves = "SERVING"
                ok += 1
            except Exception as exc:  # noqa: BLE001
                serves = "REFUSED"
                detail = f"{type(exc).__name__}: {exc}"
        print(f"[probe] {name:28} {serves or 'exists':8} {meta} {detail[:100]}")
        level = "notice" if (serves in {"SERVING", ""}) and not detail else "warning"
        if serves == "REFUSED":
            level = "warning"
        print(f"::{level} title=Gemini probe::{name} — {serves or 'metadata only'} "
              f"({meta}){' — ' + detail[:160] if detail else ''}")
    if generate and not ok:
        print("::error title=Gemini probe::no probed model answered a one-token request")
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
        # The same bounded retry the authoring calls use. This single call gates the
        # entire brain run, and on 6 November it was the *only* call that failed:
        # three runs in a row (09:16Z, 09:22Z, 09:24Z) died here on a 503 "high
        # demand" before any authoring code ran, so the backoff added to the
        # authoring path never got a chance to work.
        text = (brain._call_model(brain.model, "Reply with the single word: ready") or "").strip()
        if not text:
            print(f"::error title=Gemini service unavailable::{brain.model} did not answer "
                  f"after {1 + len(gemini_brain_module._TRANSIENT_BACKOFF)} attempts "
                  f"(503 UNAVAILABLE — upstream capacity, not this code). The next "
                  f"dispatch authorises nothing until Gemini answers.")
            return 1
        print(f"[preflight] live call:    {text[:60]}")
        return 0
    except Exception as exc:  # noqa: BLE001
        where = "GitHub Actions" if in_ci else "this machine"
        print(f"::error title=Gemini call failed ({where})::{type(exc).__name__}: {exc}")
        return 1


def cmd_ensure_supply(brain: GeminiBrain, max_expansions: int, target: int,
                      min_publishable: int | None = None,
                      channel_id: str | None = None) -> int:
    """Lengthen the backlog, author if still empty, verify — one unattended loop."""
    from pipeline.supply import SLOTS_PER_DAY, ensure_supply

    if min_publishable is None:
        min_publishable = SLOTS_PER_DAY
    report = ensure_supply(brain, limit=max_expansions, target=target,
                           min_publishable=min_publishable,
                           channel_id=channel_id or getattr(brain, "channel_id", None))
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
    parser.add_argument("--probe-models", dest="probe_models", action="store_true",
                        help="Ask the API which candidate models exist and, with "
                             "--probe-generate, which of them actually answer")
    parser.add_argument("--probe-generate", dest="probe_generate", action="store_true",
                        help="Spend one one-token request per probed model to measure service")
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
    parser.add_argument("--channel", default=None,
                        help="Channel to work on (default: CHANNEL_ID, else secret-place). "
                             "Every channel runs the same code path.")
    parser.add_argument("--ensure-supply-for", dest="ensure_supply_for", default=None,
                        help="Run the supply loop for this channel id with a channel-scoped brain")

    args = parser.parse_args(argv)
    if args.ensure_supply_for:
        return cmd_ensure_supply_for_channel(
            args.ensure_supply_for, max_expansions=args.max_expansions,
            target=args.target, min_publishable=args.min_publishable)
    brain = GeminiBrain(channel_id=args.channel) if args.channel else GeminiBrain()

    if args.equip:
        return cmd_equip(brain.channel_id)
    if args.generate_next:
        return cmd_generate_next(brain)
    if args.probe_models:
        return cmd_probe_models(brain, generate=args.probe_generate)
    if args.preflight:
        return cmd_preflight(brain)
    if args.ensure_supply:
        return cmd_ensure_supply(brain, args.max_expansions, args.target,
                                 args.min_publishable,
                                 channel_id=args.channel)
    if args.author_shorts:
        # Every channel authors its own Shorts; the queue manifests name their
        # channel, so one leg can never dress the other channel's Short.
        return cmd_author_shorts(brain)
    if args.auto_replenish:
        return cmd_auto_replenish(brain, args.min_runway)

    return cmd_audit(brain)


if __name__ == "__main__":
    sys.exit(main())
