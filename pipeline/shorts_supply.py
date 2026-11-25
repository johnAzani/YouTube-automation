"""How many more Shorts each channel can make, and from what.

Why this exists. On 25 November 2026 the daily CI was red because
``secret-place`` had one ready Short where the repository asks for two. The
failing test says so, but it says it days late and it says nothing about *why*.
Asked why, the answer was three separate shortages wearing one number:

* ``prayer2`` — **zero** standalone passages left (all fifteen evergreen ones
  used, nothing else free on the network) and no queue long-form still awaiting
  a companion Short, so it could not author another Short at all;
* ``prayer3`` — the same, exactly: no standalone passage and no companion left;
* ``prayer5`` — three companion Shorts left, no standalone passage.

A channel makes a Short from one of three things, in this order (see
``GeminiBrain.replenish_shorts_queue``): a seasonal Short for the day, a
companion Short for a queued long-form that has none, or a standalone Short on a
passage from ``EVERGREEN`` or the channel's own roadmap ahead of the long-form.
When all three are empty, the runway falls one video a day and nothing in the
pipeline stops it.

This module counts all three, per channel, and says which one is the binding
constraint. It writes a reading, not a fix: the fix is more scripture, and
inventing a passage is worse than reporting an empty pool.

    python -m pipeline.shorts_supply            # the table
    python -m pipeline.shorts_supply --json     # the same, as JSON
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "content" / "research" / "shorts_supply.json"
QUEUE_DIR = ROOT / "content" / "queue"
PUBLISHED_DIR = ROOT / "content" / "published"

#: How many ready Shorts a channel should hold. Matches
#: ``tests/test_multi_channel_resilience.py`` and ``supply.SHORTS_READY_TARGET``.
READY_FLOOR = 2


def _companion_left(channel_id: str) -> list[dict[str, str]]:
    """Queued long-forms on this channel that have no companion Short yet."""
    from pipeline.gemini_brain import short_key_for_doc
    from pipeline.script_doc import parse_script
    from pipeline.short_release import resolve_edition

    made: set[str] = set()
    covered: set[str] = set()
    try:
        import yaml
        for manifest in (ROOT / "content" / "shorts-queue").glob("*.yml"):
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            if str(data.get("channel") or "") != channel_id:
                continue
            if data.get("companion_longform_id"):
                covered.add(str(data["companion_longform_id"]).strip())
    except Exception:  # noqa: BLE001 — a reading must not crash on one bad manifest
        pass

    out = []
    for path in sorted(QUEUE_DIR.glob("*.md")):
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        if doc.channel != channel_id:
            continue
        if str(doc.status).strip().lower() not in {"approved", "published"}:
            continue
        if str(doc.id).strip() in covered or str(doc.id).strip() in made:
            continue
        edition = resolve_edition(short_key_for_doc(doc))
        if edition and (PUBLISHED_DIR / f"{edition.slug}.md").is_file():
            continue
        made.add(str(doc.id).strip())
        out.append({"id": str(doc.id).strip(), "title": str(doc.title)[:80]})
    return out


def measure(channel_id: str) -> dict[str, Any]:
    """The three ways a channel can make its next Short, counted."""
    from pipeline.evergreen_shorts import candidates
    from pipeline.gemini_brain import GeminiBrain
    from pipeline.short_release import count_ready_shorts

    brain = GeminiBrain(api_key="", channel_id=channel_id)
    standalone = [ref for ref, _source in
                  candidates(channel_id, taken_longform_ids=brain._existing_job_ids())]
    companions = _companion_left(channel_id)
    ready = count_ready_shorts(channel_id=channel_id)

    sources = len(standalone) + len(companions)
    if ready >= READY_FLOOR:
        verdict = "enough"
    elif sources:
        verdict = "can author"
    else:
        verdict = "dry"
    return {
        "channel": channel_id,
        "ready": ready,
        "standalone_passages": len(standalone),
        "standalone_examples": standalone[:5],
        "companion_longforms": len(companions),
        "sources": sources,
        "verdict": verdict,
        # The one to fix first, when there is one.
        "binding": (
            "enough ready Shorts" if verdict == "enough"
            else "no passage and no companion: this channel cannot make another Short"
            if verdict == "dry"
            else "authorable, and will be on the next pass"
        ),
    }


def _sentence(thin: list[str], dry: list[str]) -> str:
    """One sentence a person can act on, naming the binding constraint."""
    if not thin:
        return "Every channel holds at least %d ready Shorts." % READY_FLOOR
    parts = ["%s is below the floor of %d ready Shorts" % (", ".join(thin), READY_FLOOR)]
    if dry:
        verb = "cannot" if len(dry) == 1 else "cannot"
        parts.append("and %s %s make another Short at all: no standalone passage is "
                     "free and no queued long-form is waiting for its companion"
                     % (", ".join(dry), verb))
    else:
        parts.append("but it has passages to author from, so the next scheduled pass "
                     "fills it")
    return "; ".join(parts) + "."


def build_report(channels: list[str] | None = None) -> dict[str, Any]:
    from pipeline.channels import scheduled_channels

    names = list(scheduled_channels()) if channels is None else list(channels)
    rows = [measure(name) for name in names]
    dry = [r["channel"] for r in rows if r["verdict"] == "dry"]
    thin = [r["channel"] for r in rows if r["ready"] < READY_FLOOR]
    return {
        "schema": 1,
        "channels": rows,
        "ready_floor": READY_FLOOR,
        "under_floor": thin,
        "dry": dry,
        "total_sources": sum(r["sources"] for r in rows),
        "sentence": _sentence(thin, dry),
        "not_claimed": [
            "that more passages would produce more views. The supply reading says what "
            "can be authored, not what will be watched.",
        ],
        "cost_lock": "$0.00 / month (docs/ZERO_DOLLAR_LOCK.md)",
    }


def write_report(path: Path | None = None, report: dict[str, Any] | None = None) -> Path:
    out = REPORT_PATH if path is None else Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report if report is not None else build_report(),
                              indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        print(f'{"channel":14}{"ready":>7}{"passages":>10}{"companions":>12}  verdict')
        for row in report["channels"]:
            print(f'{row["channel"]:14}{row["ready"]:7}{row["standalone_passages"]:10}'
                  f'{row["companion_longforms"]:12}  {row["verdict"]}')
        print()
        print(report["sentence"])
    write_report(report=report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
