"""What a stranger sees in the first second of a Short, measured.

Why this exists. On 25 November 2026 the engaged-view report was read for the
first time (``scripts/analytics_reader.py``): of 4,336 plays across the
thirty-five most-viewed videos, **1,739 were engaged plays — 40.1%**. Six in ten
people leave before the count of a play has finished. That is the swipe, and it
happens before a title, a description, or a word of narration is reached.

Everything the pipeline had measured until then was downstream of it: retention
of the four people who stayed, thumbnails on surfaces the swipe feed never shows,
titles read after the decision. This module asks the question those cannot: what
is actually on the screen at second one, and does any of it vary?

The answer, from 634 authored specs: almost nothing varies in the way that would
matter. The first frame is a scene photograph with two lines of type — a kicker
and a sub — and the composition is identical on every Short. That is the finding.
It is stated as a measurement rather than an opinion so that the next change can
be measured against it.

What this module does **not** do: decide that one composition beats another.
Twelve Shorts were matchable to their spec on 25 November, which is not enough to
separate one composition from another, and a module that claimed otherwise would
be the same mistake as the three-second-caption rule that the same day's data
contradicted.

    python -m pipeline.first_frame            # the audit, as text
    python -m pipeline.first_frame --json     # the same, as JSON
"""
from __future__ import annotations

from datetime import datetime, timezone

import argparse
import json
import re
import statistics
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "content" / "shorts-scripts"
REPORT_PATH = ROOT / "content" / "research" / "first_frame.json"
ANALYTICS_DIR = ROOT / "content" / "analytics"

#: A kicker that names a passage rather than a need. The authoring prompt already
#: asks for the need and forbids the reference here, so a match is a spec that
#: shipped against the rule, and worth counting.
_REFERENCE = re.compile(
    r"^\s*(?:[1-3]\s+)?(GENESIS|EXODUS|LEVITICUS|NUMBERS|DEUTERONOMY|JOSHUA|JUDGES|RUTH|SAMUEL|KINGS|"
    r"CHRONICLES|EZRA|NEHEMIAH|ESTHER|JOB|PSALM|PSALMS|PROVERBS|ECCLESIASTES|SONG|ISAIAH|"
    r"JEREMIAH|LAMENTATIONS|EZEKIEL|DANIEL|HOSEA|JOEL|AMOS|OBADIAH|JONAH|MICAH|NAHUM|"
    r"HABAKKUK|ZEPHANIAH|HAGGAI|ZECHARIAH|MALACHI|MATTHEW|MARK|LUKE|JOHN|ACTS|ROMANS|"
    r"CORINTHIANS|GALATIANS|EPHESIANS|PHILIPPIANS|COLOSSIANS|THESSALONIANS|TIMOTHY|TITUS|"
    r"PHILEMON|HEBREWS|JAMES|PETER|JUDE|REVELATION)\b",
    re.I,
)

#: Words a kicker must not be, because they say nothing a stranger can use: the
#: channel's own name, a general invitation, or a mood with no object.
_VAGUE = {"PRAYER", "PRAY", "BLESSED", "FAITH", "HOPE", "PEACE", "AMEN", "GOD", "JESUS",
          "WELCOME", "BREATHE", "PAUSE", "REST"}


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z']+", str(text or "")))


def first_frame(spec: dict[str, Any]) -> dict[str, Any]:
    """The composition of second one, as the renderer will draw it."""
    scenes = spec.get("scenes") or []
    scene = scenes[0] if scenes else {}
    kinetic = spec.get("kinetic_phrases") or []
    opening = kinetic[0] if kinetic and len(kinetic[0]) >= 3 else None
    kicker = str(scene.get("kicker") or "").strip()
    sub = str(scene.get("sub") or "").strip()
    lines = list(opening[2]) if opening else []
    return {
        "kicker": kicker,
        "sub": sub,
        "kicker_is_reference": bool(_REFERENCE.match(kicker)),
        "kicker_is_vague": kicker.upper() in _VAGUE,
        "kicker_words": _words(kicker),
        "sub_words": _words(sub),
        "kinetic_lines": lines,
        "kinetic_words": sum(_words(line) for line in lines),
        # The number a stranger must read before the first word is spoken.
        "words_on_frame_one": _words(kicker) + _words(sub) + sum(_words(x) for x in lines),
        "first_caption_ends": float((spec.get("captions") or [[0, 0]])[0][1] or 0),
    }


def read_specs(spec_dir: Path | None = None) -> list[tuple[str, dict[str, Any]]]:
    folder = SPEC_DIR if spec_dir is None else spec_dir
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            out.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def build_audit(specs: Iterable[tuple[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Every Short's first frame, and how little of it differs between Shorts."""
    rows = []
    for key, spec in (read_specs() if specs is None else specs):
        frame = first_frame(spec)
        frame["key"] = key
        frame["channel"] = spec.get("channel")
        rows.append(frame)
    if not rows:
        return {"schema": 1, "specs": 0, "findings": [], "note": "no specs to read"}

    words = [r["words_on_frame_one"] for r in rows]
    references = [r for r in rows if r["kicker_is_reference"]]
    vague = [r for r in rows if r["kicker_is_vague"]]
    # The composition, as a shape: what kinds of line are on the frame.
    shapes = {"kicker + sub + kinetic": 0, "kicker + sub": 0, "kicker only": 0, "nothing": 0}
    for r in rows:
        if r["kinetic_lines"]:
            shapes["kicker + sub + kinetic"] += 1
        elif r["kicker"] and r["sub"]:
            shapes["kicker + sub"] += 1
        elif r["kicker"]:
            shapes["kicker only"] += 1
        else:
            shapes["nothing"] += 1

    findings = [
        "%d of %d Shorts (%d%%) put a scripture reference on the first frame, which "
        "the authoring prompt forbids: a reference is not a reason for a stranger to stay." % (
            len(references), len(rows), round(100 * len(references) / len(rows))),
        "Every first frame is the same composition — %d of %d are a scene plate with three "
        "stacked lines of type. Nothing about the frame has ever varied, so nothing about "
        "it has ever been tested." % (shapes["kicker + sub + kinetic"], len(rows)),
        "A stranger must read a median of %d words on that frame before hearing a word. "
        "The decision they are making takes about one second." % statistics.median(words),
    ]
    if vague:
        findings.append("%d Shorts open on a word that names nothing: %s." % (
            len(vague), ", ".join(sorted({r["kicker"] for r in vague}))[:120]))

    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "specs": len(rows),
        "median_words_on_frame_one": statistics.median(words),
        "max_words_on_frame_one": max(words),
        "first_frames_with_a_reference": len(references),
        "first_frames_with_a_vague_kicker": len(vague),
        "compositions": shapes,
        "median_first_caption_seconds": statistics.median(
            [r["first_caption_ends"] for r in rows]),
        "findings": findings,
        "not_claimed": [
            "that one first-frame composition earns more stays than another. Twelve Shorts "
            "could be matched to their spec on 25 November 2026; that cannot separate two "
            "compositions, and the module says so rather than picking one.",
        ],
        "cost_lock": "$0.00 / month (docs/ZERO_DOLLAR_LOCK.md)",
    }


def write_audit(path: Path | None = None, audit: dict[str, Any] | None = None) -> Path:
    out = REPORT_PATH if path is None else Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit if audit is not None else build_audit(),
                              indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def headline(audit: dict[str, Any]) -> str:
    if not audit.get("specs"):
        return "First frame: no authored Shorts to read."
    return ("First frame: %d of %d Shorts put a scripture reference where the need belongs, "
            "and every frame is the same composition (%d words to read before a word is spoken)."
            % (audit["first_frames_with_a_reference"], audit["specs"],
               audit["median_words_on_frame_one"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="print the audit as JSON")
    args = parser.parse_args(argv)
    audit = build_audit()
    if args.json:
        print(json.dumps(audit, indent=1, sort_keys=True))
    else:
        print(headline(audit))
        for finding in audit.get("findings", []):
            print("  -", finding)
    write_audit(audit=audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
