"""Move a queued Short's citation off its first frame, once, and record it.

Why this exists. The first-frame audit (`pipeline/first_frame.py`) found 26 of the
53 Shorts waiting in the queue open on a scripture citation — a reference where
the prompt requires the need. The authoring guard (`short_script.authoring_defects`)
now refuses new ones, so the count can only fall if the queued ones are fixed, and
re-authoring a spec means paying a model to rewrite words that were already fine.
The words were not the problem. One line was in the wrong place.

The repair is deliberately narrow, and it refuses more often than it acts:

* it only moves a kicker that **is** a citation (``VERSE_KICKER_RE``);
* the replacement is text the spec already contains — the scene's own ``sub``, or
  failing that the first line of its kinetic phrase, never a generated phrase;
* the replacement must fit the renderer's kicker width and must not itself be a
  citation or the channel's name;
* the citation is not deleted. It moves to the scene that reads the verse, which
  is where the audit says it belongs, and the first frame keeps its own words.

When no existing line qualifies, the spec is left exactly as it is and reported as
``no need line to promote`` rather than given an invented one. That distinction is
the whole point: a repair that writes new copy is authoring, and this module is not
allowed to author.

    python -m pipeline.first_frame_repair              # what it would change
    python -m pipeline.first_frame_repair --write      # do it
    python -m pipeline.first_frame_repair --json       # the report
"""
from __future__ import annotations

from datetime import datetime, timezone

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "content" / "shorts-scripts"
QUEUE_DIR = ROOT / "content" / "shorts-queue"
REPORT_PATH = ROOT / "content" / "research" / "first_frame_repair.json"

#: The field a repair leaves behind, so a spec that was changed says so.
REPAIR_FIELD = "first_frame_repair"


def _queued_keys() -> set[str]:
    """Short keys with a manifest in the queue, read without a YAML parser.

    The growth job installs nothing, so this reads the one field it needs.
    """
    keys: set[str] = set()
    for path in QUEUE_DIR.glob("*.yml"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("short:"):
                keys.add(line.split(":", 1)[1].strip().strip("\"'"))
                break
    return keys


def _usable(line: str, kicker: str) -> bool:
    """Whether an existing line can stand in as the first frame's kicker."""
    from pipeline.short_script import (CHANNEL_KICKER_RE, MAX_KICKER_CHARS,
                                       VERSE_KICKER_RE)

    text = " ".join(str(line or "").split()).strip().upper()
    if not text or text == kicker.upper():
        return False
    if len(text) > MAX_KICKER_CHARS:
        return False
    if VERSE_KICKER_RE.search(text) or CHANNEL_KICKER_RE.search(text):
        return False
    # A fragment that ends on a joining word reads as a truncated sentence on a
    # frame nobody gets a second look at.
    if text.split()[-1].lower() in {"and", "or", "the", "a", "of", "to", "your", "in", "at"}:
        return False
    return True


def plan(spec: dict[str, Any]) -> dict[str, Any]:
    """What this repair would do to one spec, without touching it."""
    from pipeline.first_frame import first_frame
    from pipeline.short_script import VERSE_KICKER_RE

    frame = first_frame(spec)
    if not frame["kicker_is_reference"]:
        return {"action": "none", "reason": "the first frame already names a need"}
    scene = (spec.get("scenes") or [{}])[0]
    kicker = str(scene.get("kicker") or "").strip()
    sub = str(scene.get("sub") or "").strip()
    lines = ((spec.get("kinetic_phrases") or [[None, None, []]])[0][2] or [])
    for source, candidate in (("sub", sub), ("kinetic", str(lines[0]) if lines else "")):
        if _usable(candidate, kicker):
            return {
                "action": "promote",
                "from": source,
                "old_kicker": kicker,
                "new_kicker": " ".join(candidate.split()).upper(),
                "citation_to": _citation_target(spec, kicker),
            }
    return {"action": "keep", "reason": "no need line to promote", "old_kicker": kicker}


def _citation_target(spec: dict[str, Any], kicker: str) -> int | None:
    """The scene index the citation moves to: the one that speaks the verse.

    The first scene after the opening whose narration mentions the book, else the
    scene the citation was already on (its own, index 0, when nothing matches) so a
    repair never moves a citation somewhere it does not belong.
    """
    from pipeline.books import split_reference
    from pipeline.short_script import _norm

    parts = split_reference(kicker)
    if parts is None:
        return None
    book = parts[0].split()[-1]
    scenes = spec.get("scenes") or []
    for index, scene in enumerate(scenes[1:], start=1):
        if book in _norm(scene.get("a", "")).lower():
            return index
    return None


def apply(spec: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    """Return the repaired spec. Never mutates the argument."""
    if decision.get("action") != "promote":
        return spec
    from pipeline.short_script import VERSE_KICKER_RE

    copy = json.loads(json.dumps(spec))
    old = decision["old_kicker"]
    new = decision["new_kicker"]
    scene = copy["scenes"][0]
    scene["kicker"] = new
    # Keep the citation, on the scene that reads the verse.
    target = decision.get("citation_to")
    if isinstance(target, int) and 0 < target < len(copy["scenes"]):
        destination = copy["scenes"][target]
        if not VERSE_KICKER_RE.search(str(destination.get("kicker") or "")):
            destination["kicker"] = old.upper()
    copy[REPAIR_FIELD] = {
        "moved": old.upper(),
        "to": new,
        "why": ("the first frame must name the need; the citation belongs on the "
                "scene that reads the verse (pipeline/first_frame.py)"),
    }
    return copy


def _published_keys() -> set[str]:
    """Short keys whose frame is already on YouTube.

    A receipt's slug is ``<key>-<human title suffix>`` (``short-morningpsalm86v11-
    sunrise-prayer``), so the key is the receipt's stem with the spec's own name as
    a prefix. Matching on the stem alone finds nothing, which would silently make
    every published Short look repairable.
    """
    keys: set[str] = set()
    specs = sorted((path.stem for path in SPEC_DIR.glob("*.json")), key=len, reverse=True)
    for path in (ROOT / "content" / "published").glob("short-*.md"):
        stem = path.stem
        match = next((spec for spec in specs
                      if stem == spec or stem.startswith(spec + "-")), None)
        if match:
            keys.add(match)
    return keys


def audit(write: bool = False, spec_dir: Path | None = None,
          include_published: bool = False) -> dict[str, Any]:
    """Cite-first specs, and the ones worth rewriting.

    Only a spec whose Short has not been published is rewritten by default. The
    published archive is the **control**: 456 Shorts already open on a citation,
    and if they were rewritten too there would be nothing left to compare a
    need-first frame against. Rewriting them would delete the experiment it is
    supposed to serve.
    """
    folder = SPEC_DIR if spec_dir is None else Path(spec_dir)
    queued = _queued_keys()
    published = set() if include_published else _published_keys()
    rows: list[dict[str, Any]] = []
    changed = 0
    for path in sorted(folder.glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        decision = plan(spec)
        if decision["action"] == "none":
            continue
        already_live = path.stem in published
        row = {"key": path.stem, "queued": path.stem in queued,
               "published": already_live, **decision}
        if already_live and decision["action"] == "promote":
            # Kept as the control, not for lack of a repair.
            row["action"] = "control"
            row["reason"] = ("already published; kept as the citation-first control "
                             "the need-first frames are compared against")
        rows.append(row)
        if decision["action"] == "promote" and not already_live and write:
            repaired = apply(spec, decision)
            path.write_text(json.dumps(repaired, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            changed += 1
    promoted = [row for row in rows if row["action"] == "promote"]
    kept = [row for row in rows if row["action"] == "keep"]
    control = [row for row in rows if row["action"] == "control"]
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "written": write,
        "specs_examined": len(list(folder.glob("*.json"))),
        "citation_frames": len(rows),
        "promotable": len(promoted),
        "no_need_line": len(kept),
        "citation_first_control": len(control),
        "queued_promotable": sum(1 for row in promoted if row["queued"]),
        "changed": changed,
        "rows": rows,
        "not_claimed": [
            "that a repaired frame keeps more people. This moves an already-written "
            "line to where the rule says it belongs; whether that helps is the next "
            "reading's question, and one composition still cannot be compared "
            "against another until the repaired Shorts are published and watched.",
        ],
        "cost_lock": "$0.00 / month (docs/ZERO_DOLLAR_LOCK.md)",
    }


def write_report(report: dict[str, Any], path: Path | None = None) -> Path:
    out = REPORT_PATH if path is None else Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--write", action="store_true", help="rewrite the specs")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = audit(write=args.write)
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        print(f"{report['citation_frames']} specs open on a citation; "
              f"{report['promotable']} can move a need line up "
              f"({report['queued_promotable']} of them queued); "
              f"{report['no_need_line']} have no line to promote and are left alone.")
        if report["written"]:
            print(f"rewrote {report['changed']} spec(s).")
        for row in report["rows"]:
            if row["action"] == "promote":
                print(f"  {row['key']}: {row['old_kicker']} -> {row['new_kicker']}"
                      f"  (from {row['from']})")
    write_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
