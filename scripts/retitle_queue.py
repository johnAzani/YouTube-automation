#!/usr/bin/env python3
"""Retitle queued prayers the variety gate would refuse. See pipeline/queue_titles.py.

Two steps, because a queued script is bound to its fact-check worksheet and both
must be edited on the tree they will be committed on:

    python scripts/retitle_queue.py --channel prayer10 --ledger /tmp/queue-titles.json
        finds the channel's queued long-forms whose titles fail the variety gate
        today, asks the model for a replacement for each, and writes the accepted
        ones to the ledger. Changes nothing else.

    python scripts/retitle_queue.py --channel prayer10 --ledger /tmp/queue-titles.json \
        --proposals proposals.json
        the same, with the words supplied by a person: a JSON object of
        ``{"job id": "new title"}``. Every one of them is still refused by
        ``retitle.title_problems`` and the leave-one-out variety check, so a
        proposals file is a convenience, never a way past the gate.

    python scripts/retitle_queue.py --apply-ledger /tmp/queue-titles.json
        re-checks every entry against the titles now on disk, stamps the new ones
        into their scripts, rebuilds the worksheet each changed script is bound
        to, and prints the paths that changed (script and worksheet).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline import lessons, queue_titles, retitle, title_variety  # noqa: E402
from pipeline.channels import get_channel, normalize_channel_id  # noqa: E402


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


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def choose(channel_id: str, ledger: Path, *, ask=None, proposals: Path | None = None,
           today: datetime | None = None, published_dir: Path | None = None,
           queue_dir: Path | None = None) -> list[dict]:
    """Audit one channel's queued titles and write the accepted replacements."""
    channel_id = normalize_channel_id(channel_id)
    failures = queue_titles.failing(channel_id, published_dir=published_dir,
                                    queue_dir=queue_dir)
    if not failures:
        print(f"[queue-titles] {channel_id}: no queued title fails the variety gate today")
        ledger.write_text("[]", encoding="utf-8")
        return []

    words_supplied: dict[str, str] = {}
    if proposals is not None:
        try:
            words_supplied = {str(k): str(v) for k, v in
                              json.loads(proposals.read_text(encoding="utf-8")).items()}
        except (OSError, json.JSONDecodeError) as exc:
            print(f"::warning title=Proposals unreadable ({channel_id})::{exc}")
            ledger.write_text("[]", encoding="utf-8")
            return []

    ask = ask or _model_asker(channel_id)
    if ask is None and not words_supplied:
        print(f"::notice title=Queue titles skipped ({channel_id})::{len(failures)} queued "
              "title(s) read like the ones beside them; no text model is available in this run")
        ledger.write_text("[]", encoding="utf-8")
        return []

    name = get_channel(channel_id).display_name
    stamp = (today or datetime.now(timezone.utc)).date().isoformat()
    entries: list[dict] = []
    for queued in failures:
        target = queue_titles.target_for(queued)
        # Judged without itself, and against the titles as they will read once
        # this one is replaced (earlier entries in this run are already on disk
        # by apply time and re-checked there).
        variety = queue_titles.variety_without(queued.title, channel_id,
                                               published_dir=published_dir,
                                               queue_dir=queue_dir)
        if queued.job_id in words_supplied:
            title, why = _checked(words_supplied[queued.job_id], queued, name, variety)
        else:
            title, why = retitle.propose_title(
                target, name, ask, variety=variety, draft=True,
                words=lessons.block_for(channel_id))
        if title is None:
            print(f"::warning title=No new title ({channel_id})::{queued.path.name}: {why[:200]}")
            continue
        entries.append({"file": _relative(queued.path), "job_id": queued.job_id,
                        "old_title": queued.title, "new_title": title,
                        "reference": queued.reference,
                        "problems": list(queued.problems), "date": stamp})
        print(f"::notice title=New queued title ({channel_id})::{queued.job_id}: "
              f"'{queued.title}' -> '{title}'")
    ledger.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return entries


def _checked(title: str, queued, channel_name: str, variety) -> tuple[str | None, str]:
    """A person's title goes through the same checks a model's does."""
    problems = retitle.title_problems(title, queued.reference, channel_name,
                                      queued.title, variety)
    if problems:
        return None, "; ".join(problems[:3])
    return " ".join(title.split()), ""


def apply(ledger: Path, root: Path = ROOT, *, today: datetime | None = None,
          published_dir: Path | None = None,
          queue_dir: Path | None = None) -> list[str]:
    """Stamp each ledger entry and rebuild the worksheet it is bound to.

    The reference is taken from the script on disk, not from the ledger: the
    entry is only a record of what was accepted, and the file is the truth. An
    entry whose title no longer matches, or whose reference is no longer in the
    title, is refused and left alone.
    """
    from pipeline.gemini_brain import extract_scripture_reference
    from pipeline.script_doc import parse_script
    from pipeline.scripture_text import exists as scripture_exists

    try:
        entries = json.loads(ledger.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    changed: list[str] = []
    for entry in entries:
        path = Path(entry["file"])
        path = path if path.is_absolute() else root / path
        if not path.is_file():
            print(f"[queue-titles] {path.name}: queued script not found", file=sys.stderr)
            continue
        try:
            doc = parse_script(path)
        except Exception as exc:  # noqa: BLE001
            print(f"[queue-titles] {path.name}: unreadable ({exc})", file=sys.stderr)
            continue
        if " ".join(str(doc.title).split()) != " ".join(str(entry["old_title"]).split()):
            print(f"[queue-titles] {path.name}: title changed since the new one was written",
                  file=sys.stderr)
            continue
        reference = extract_scripture_reference(doc)
        if (not reference or not scripture_exists(reference)
                or reference.lower() not in str(doc.title).lower().replace("–", "-")):
            print(f"[queue-titles] {path.name}: the title keeps no passage this can preserve",
                  file=sys.stderr)
            continue
        channel = normalize_channel_id(doc.channel)
        name = get_channel(channel).display_name
        variety = queue_titles.variety_without(entry["old_title"], channel,
                                               published_dir=published_dir,
                                               queue_dir=queue_dir)
        problems = retitle.title_problems(entry["new_title"], reference, name,
                                          entry["old_title"], variety)
        if problems:
            print(f"[queue-titles] {path.name}: refused on re-check: {'; '.join(problems[:3])}",
                  file=sys.stderr)
            continue
        outcome = queue_titles.apply(path, entry["new_title"], today=today)
        print(f"[queue-titles] {path.name}: {outcome}", file=sys.stderr)
        if outcome != "stamped":
            continue
        changed.append(entry["file"])
        worksheet = queue_titles.refresh_worksheet(path)
        if worksheet is not None:
            changed.append(_relative(worksheet))
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--proposals", type=Path,
                        help='JSON {"job id": "new title"} supplied by a person')
    parser.add_argument("--apply-ledger", type=Path)
    args = parser.parse_args(argv)
    if args.apply_ledger:
        for path in apply(args.apply_ledger):
            print(path)
        return 0
    if not (args.channel and args.ledger):
        parser.error("--channel and --ledger, or --apply-ledger")
    choose(args.channel, args.ledger, proposals=args.proposals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
