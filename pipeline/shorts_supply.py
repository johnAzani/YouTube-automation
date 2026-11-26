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

from datetime import datetime, timezone

import argparse
import json
import re
from pathlib import Path
from typing import Any

from pipeline.books import split_reference

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "content" / "research" / "shorts_supply.json"
QUEUE_DIR = ROOT / "content" / "queue"
PUBLISHED_DIR = ROOT / "content" / "published"

#: How many ready Shorts a channel should hold. Matches
#: ``tests/test_multi_channel_resilience.py`` and ``supply.SHORTS_READY_TARGET``.
READY_FLOOR = 2


def _manifest_field(path: Path, name: str) -> str:
    """One scalar field from a manifest, without a YAML parser.

    The daily growth job installs nothing, so this reading has to work with the
    standard library alone. These manifests are flat mappings of scalars written by
    ``yaml.safe_dump``; a line-wise read is enough, and a manifest that is not that
    shape simply contributes nothing.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines():
        if line.startswith(f"{name}:"):
            value = line.split(":", 1)[1].strip()
            return value.strip("'\"") 
    return ""


def _shorts_scripts() -> set[str]:
    """Keys a renderer can actually produce, read from the specs on disk."""
    return {path.stem for path in (ROOT / "content" / "shorts-scripts").glob("*.json")}


def _companion_left(channel_id: str) -> list[dict[str, str]]:
    """Queued long-forms on this channel that have no companion Short yet.

    A long-form whose Short already exists is not a source; that is the whole
    reason this count differs from the size of the queue directory.

    The key is derived here rather than by importing `gemini_brain`: this has to run
    with nothing installed, and the derivation is three lines of the same rules
    (`pipeline/gemini_brain.py: _base_short_key_for_doc`, which calls this one).
    """
    from pipeline.script_doc import parse_script

    specs = _shorts_scripts()
    covered: set[str] = set()
    for manifest in (ROOT / "content" / "shorts-queue").glob("*.yml"):
        if _manifest_field(manifest, "channel") != channel_id:
            continue
        covered.add(_manifest_field(manifest, "companion_longform_id"))

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
        doc_id = str(doc.id).strip()
        if not doc_id or doc_id in covered:
            continue
        key = short_key_from_parts(channel_id, str(doc.title or ""),
                                   slug=str(doc.slug or ""), doc_id=doc_id)
        if key in specs or (PUBLISHED_DIR / f"{key}.md").is_file():
            continue
        covered.add(doc_id)
        out.append({"id": doc_id, "title": str(doc.title)[:80]})
    return out


#: Keys the renderer has a script for, from `tools/shorts.py` (which imports without
#: third-party packages, unlike the rest of the release path).
def _renderable_keys() -> set[str]:
    try:
        from tools.shorts import SCRIPTS
        return {str(key) for key in SCRIPTS}
    except Exception:  # noqa: BLE001 — fall back to the generated specs only
        return set()


def _ready_count(channel_id: str) -> int:
    """Approved manifests for this channel whose spec exists and can render.

    The same verdict `short_release.count_ready_shorts` gives, computed without
    importing it: that module needs PyYAML, and the daily reading runs with no
    dependencies installed. The test suite asserts the two agree.
    """
    renderable = _renderable_keys() | _shorts_scripts()
    count = 0
    for manifest in (ROOT / "content" / "shorts-queue").glob("*.yml"):
        if _manifest_field(manifest, "channel") != channel_id:
            continue
        key = _manifest_field(manifest, "short") or _manifest_field(manifest, "edition")
        status = _manifest_field(manifest, "status").lower()
        if key in renderable and status == "approved":
            count += 1
    return count


def short_key_from_parts(channel_id: str, title: str, *, slug: str = "",
                         doc_id: str = "") -> str:
    """The Short key a channel's long-form on `title` gets.

    A dependency-free copy of `gemini_brain.short_key_for_doc` +
    `channel_capabilities.short_key`, because this module runs in the daily growth
    job, which installs nothing. `tests/test_shorts_supply.py` asserts the two
    derivations agree for every long-form in the queue, so the copy cannot drift
    silently — including its two special cases, a whole-psalm Short and a title
    with no reference in it at all.
    """
    from pipeline.channel_capabilities import short_key

    parts = split_reference(title)
    if parts is None:
        stem = re.sub(r"[^a-z0-9]+", "", str(slug or doc_id or "prayer").lower())[:24]
        return short_key(channel_id, f"short-{stem or 'prayer'}")
    book, chapter, verse = parts
    clean = re.sub(r"[^a-z0-9]+", "", book)
    if clean == "psalms":
        clean = "psalm"
    if clean == "psalm" and verse is None:
        # A whole-chapter Short only says so when the long-form calls itself
        # complete; `0008`-`0010` predate that convention (see gemini_brain).
        hay = f"{title} {slug}".lower()
        if "complete" in hay and str(doc_id) not in {"0008", "0009", "0010"}:
            return short_key(channel_id, f"short-psalm{chapter}full")
        return short_key(channel_id, f"short-psalm{chapter}")
    tail = f"v{verse}" if verse is not None else ""
    return short_key(channel_id, f"short-{clean}{chapter}{tail}")


def _used_ids() -> set[str]:
    """Roadmap ids already spent, repository-wide (ids are global)."""
    return ({p.name[:4] for p in QUEUE_DIR.glob("*.md")}
            | {p.name[:4] for p in PUBLISHED_DIR.glob("*.md")})


def measure(channel_id: str) -> dict[str, Any]:
    """The three ways a channel can make its next Short, counted."""
    from pipeline.evergreen_shorts import candidates

    standalone = [ref for ref, _source in candidates(channel_id, taken_longform_ids=_used_ids())]
    companions = _companion_left(channel_id)
    ready = _ready_count(channel_id)

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


def _is_are(names: list[str]) -> str:
    """`is` for one channel, `are` for several. Three channels read as `is` before."""
    return "is" if len(names) == 1 else "are"


def _sentence(thin: list[str], dry: list[str]) -> str:
    """One sentence a person can act on, naming the binding constraint."""
    if not thin:
        return "Every channel holds at least %d ready Shorts." % READY_FLOOR
    parts = ["%s %s below the floor of %d ready Shorts"
             % (", ".join(thin), _is_are(thin), READY_FLOOR)]
    if dry:
        # "cannot" is the same for one channel and for ten; the verb that has to
        # agree is the "is/are" above. The old code chose between two identical
        # strings here, so the branch could never change the output.
        parts.append("and %s cannot make another Short at all: no standalone passage "
                     "is free and no queued long-form is waiting for its companion"
                     % ", ".join(dry))
    elif len(thin) == 1:
        parts.append("but it has passages to author from, so the next scheduled "
                     "pass fills it")
    else:
        parts.append("but they have passages to author from, so the next scheduled "
                     "pass fills them")
    return "; ".join(parts) + "."


def build_report(channels: list[str] | None = None) -> dict[str, Any]:
    from pipeline.channels import scheduled_channels

    names = list(scheduled_channels()) if channels is None else list(channels)
    rows = [measure(name) for name in names]
    dry = [r["channel"] for r in rows if r["verdict"] == "dry"]
    thin = [r["channel"] for r in rows if r["ready"] < READY_FLOOR]
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
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
    parser.add_argument("--no-write", action="store_true",
                        help="print the reading and leave the committed file alone")
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
    if not args.no_write:
        write_report(report=report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
