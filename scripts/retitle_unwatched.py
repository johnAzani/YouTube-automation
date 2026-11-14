#!/usr/bin/env python3
"""Give a channel's unwatched long-forms a need-first title. See pipeline/retitle.py.

Two steps, because the receipt must be edited on the tree it is committed on:

    python scripts/retitle_unwatched.py --channel prayer7 --ledger /tmp/retitles.json
        reads content/metrics.csv (the public snapshot this job just took),
        chooses at most two long-forms, asks the model for a title for each and
        writes the accepted ones to the ledger. Changes nothing else.

    python scripts/retitle_unwatched.py --apply-ledger /tmp/retitles.json
        stamps each ledger entry into its receipt and prints the paths changed.

The monitor's metadata sync then pushes each receipt's title to YouTube.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import retitle  # noqa: E402
from pipeline.channels import get_channel, normalize_channel_id  # noqa: E402
from pipeline.performance_feedback import load_metric_snapshots  # noqa: E402


def _model_asker(channel_id: str):
    """``ask(prompt) -> text`` on the channel's own free-tier text models, or ``None``."""
    from pipeline.gemini_brain import GeminiBrain, text_model_candidates

    brain = GeminiBrain(channel_id=channel_id)
    if not brain.is_api_available():
        return None

    def ask(prompt: str) -> str:
        for model in text_model_candidates(brain.model):
            answer = brain._call_model(model, prompt)
            if answer:
                return answer
        return ""

    return ask


def choose(channel_id: str, ledger: Path, *, ask=None, snapshots=None, today=None) -> list[dict]:
    channel_id = normalize_channel_id(channel_id)
    snapshots = load_metric_snapshots() if snapshots is None else snapshots
    ledger.write_text("[]", encoding="utf-8")
    if not snapshots:
        print("[retitle] no metrics snapshot in this run; nothing is changed without view counts")
        return []
    targets = retitle.find_targets(channel_id, snapshots, today=today)
    if not targets:
        print(f"[retitle] {channel_id}: no long-form is {retitle.MIN_AGE_DAYS}+ days old with "
              f"{retitle.MAX_VIEWS} views or fewer and its first title")
        return []
    ask = ask or _model_asker(channel_id)
    if ask is None:
        print(f"::notice title=Retitle skipped ({channel_id})::{len(targets)} unwatched "
              "long-form(s) are waiting for a new title; no text model is available in this run")
        return []
    name = get_channel(channel_id).display_name
    stamp = (today or datetime.now(timezone.utc).date()).isoformat()
    entries: list[dict] = []
    for target in targets:
        title, why = retitle.propose_title(target, name, ask)
        if title is None:
            print(f"::warning title=No new title ({channel_id})::{target.path.name}: {why[:200]}")
            continue
        entries.append({"file": str(target.path.relative_to(ROOT)) if target.path.is_relative_to(ROOT)
                        else str(target.path),
                        "video_id": target.video_id, "old_title": target.title,
                        "new_title": title, "date": stamp})
        print(f"::notice title=New title ({channel_id})::{target.video_id} "
              f"({target.views} views in {target.age_days} days): "
              f"'{target.title}' -> '{title}'")
    ledger.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def apply(ledger: Path, root: Path = ROOT) -> list[str]:
    try:
        entries = json.loads(ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    changed: list[str] = []
    for entry in entries:
        path = Path(entry["file"])
        path = path if path.is_absolute() else root / path
        outcome = retitle.apply_ledger_entry(path, entry)
        print(f"[retitle] {path.name}: {outcome}", file=sys.stderr)
        if outcome == "stamped":
            changed.append(entry["file"])
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--apply-ledger", type=Path)
    args = parser.parse_args(argv)
    if args.apply_ledger:
        for path in apply(args.apply_ledger):
            print(path)
        return 0
    if not (args.channel and args.ledger):
        parser.error("--channel and --ledger, or --apply-ledger")
    choose(args.channel, args.ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
