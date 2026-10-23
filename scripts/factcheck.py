#!/usr/bin/env python3
"""Generate a fact-check worksheet for a queued script.

Why
---
`pipeline/originality.py` blocks every job whose `human_rewrite` is `false`, and the standing
rule in this repo is that a machine never flips that flag: a human has to verify the facts,
rewrite the narration in their own words, and only then approve. That is the difference
between a monetizable channel and a terminated one (PLAN.md §4.4).

The problem is that the human half is slow. Reading a 900-word script, pulling out every
checkable claim, and then finding which of six sources settles each one is an hour of
mechanical work before the actual judgement starts.

This script does the mechanical part and nothing else. It extracts candidate claims and
prints them as a checklist next to the job's own declared sources. **It verifies nothing and
asserts nothing about whether any claim is true** — an empty checkbox is the correct output.
A human fills them in.

Extraction is deliberately dumb and deterministic: a sentence is a candidate claim if it
contains a number word ("two thousand and eight", "thirty-one dollars" — the narration
spells numbers out for TTS), a month name, or a mid-sentence proper noun. Dumb is right
here: a missed claim is a checkbox the human adds, whereas a clever extractor that silently
decides what matters would hide claims behind a model's judgement.

Output goes to `content/factcheck/`, never `content/queue/` — that directory is globbed by
`pipeline/run.py::select_jobs`, `scripts/doctor.py`, the queue-integrity tests and
`dry-run.yml`, so a stray `.md` there would be treated as a renderable job.

Usage
-----
    python scripts/factcheck.py                  # every queued job missing a worksheet
    python scripts/factcheck.py 0003             # one job, by id
    python scripts/factcheck.py --all --force    # regenerate everything, overwriting
    python scripts/factcheck.py 0003 --stdout    # preview, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.script_doc import parse_script  # noqa: E402

QUEUE_DIR = ROOT / "content" / "queue"
OUT_DIR = ROOT / "content" / "factcheck"

# The narration spells numbers out so edge-tts reads them correctly, so digit-matching
# finds almost nothing. These are the tokens that make a sentence a numeric claim.
NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety", "hundred", "thousand", "million", "billion", "trillion",
}
MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"}
# Units that turn a bare number into something a viewer will hold you to.
UNIT_WORDS = {"dollar", "dollars", "percent", "cent", "cents", "pound", "pounds",
              "year", "years", "month", "months", "day", "days", "week", "weeks"}

# A sentence this long with no figure/date/name is still surfaced as a reading prompt.
# Short connective sentences ("The cash came back.") are not worth a line of their own.
MIN_UNFLAGGED_WORDS = 10

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def _sentences(narration: str) -> list[str]:
    return [re.sub(r"\s+", " ", s).strip() for s in _SENTENCE_RE.split(narration.strip())
            if s.strip()]


def _tokens(sentence: str) -> list[str]:
    return _WORD_RE.findall(sentence)


def _is_capitalised(word: str) -> bool:
    return word[:1].isupper() and word[1:].islower() or (word.isupper() and len(word) > 1)


def classify(sentence: str) -> tuple[bool, list[str]]:
    """Return (is_claim, reasons). Reasons name *why* the sentence was pulled, so a human
    scanning the worksheet knows what to look at."""
    words = [w.lower() for w in _tokens(sentence)]
    reasons: list[str] = []

    numbers = [w for w in words if w in NUMBER_WORDS]
    if numbers:
        # "one" alone is usually an article ("a single weekend"), not a figure. Only flag
        # it when a unit or a bigger magnitude sits next to it.
        meaningful = [w for w in numbers if w != "one"]
        if meaningful or any(u in words for u in UNIT_WORDS):
            reasons.append("figure")
    if any(w in MONTHS for w in words):
        reasons.append("date")
    if any(u in words for u in UNIT_WORDS) and "figure" not in reasons:
        reasons.append("quantity")

    raw = _tokens(sentence)
    # Proper nouns: a named entity is a claim about the world. Consecutive capitals are one
    # name, so "Wall Street" surfaces as itself rather than "Wall, Street". A lone capital
    # at index 0 is ambiguous — that is just sentence grammar — but two capitals at index 0
    # is almost certainly a name ("Lehman Brothers"), so those are kept.
    names: list[str] = []
    run: list[str] = []
    run_start = 0
    for i, w in enumerate(raw):
        if _is_capitalised(w) and w.lower() not in MONTHS:
            if not run:
                run_start = i
            run.append(w)
            continue
        if run:
            if not (run_start == 0 and len(run) == 1):
                names.append(" ".join(run))
            run = []
    if run and not (run_start == 0 and len(run) == 1):
        names.append(" ".join(run))
    # Drop a trailing possessive and de-duplicate while preserving order.
    # (Not rstrip("'s") — that strips a character set and would mangle "Brothers".)
    names = [n[:-2] if n.endswith("'s") else n for n in dict.fromkeys(names)]
    if names:
        reasons.append("named: " + ", ".join(names[:4]))

    return bool(reasons), reasons


def _sources(doc) -> list[str]:
    """Pull the source list out of the job's own description."""
    out = []
    for line in doc.description.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and len(stripped) > 6:
            out.append(stripped[2:].strip())
    return out


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(doc, path: Path) -> str:
    claims = []
    for scene in doc.scenes:
        picked, also_read = [], []
        for sentence in _sentences(scene.narration):
            ok, reasons = classify(sentence)
            if ok:
                picked.append((sentence, reasons))
            elif len(sentence.split()) >= MIN_UNFLAGGED_WORDS:
                # A sentence with no figure, date or proper noun can still be a load-bearing
                # claim ("a repo is in substance a secured loan"). Listing only the flagged
                # ones would let a human tick every box and miss those, so the rest are
                # surfaced as a reading prompt rather than dropped.
                also_read.append(sentence)
        claims.append((scene, picked, also_read))

    total = sum(len(p) for _, p, _ in claims)
    extra = sum(len(a) for _, _, a in claims)
    sources = _sources(doc)
    L: list[str] = []
    A = L.append

    A(f"# Fact-check worksheet — job {doc.id}: {doc.title}")
    A("")
    A(f"> Generated by `scripts/factcheck.py` from "
      f"`content/queue/{path.name}`")
    A(f"> Source sha256: `{_sha(path)}`")
    A(">")
    A("> **This file verifies nothing.** The extraction is mechanical: every sentence with a")
    A("> number, a date, or a named entity is listed as a candidate claim. Whether any of them")
    A("> is true is for you to decide. An unticked box is the correct starting state.")
    A(">")
    A("> If the script changes, this worksheet is stale — regenerate with")
    A(f"> `python scripts/factcheck.py {doc.id} --force` and re-check anything you had already")
    A("> signed off. Your ticks are not preserved, because a claim that moved is a claim that")
    A("> needs re-reading.")
    A("")
    A("## How to use this")
    A("")
    A("1. Work scene by scene. Tick `[x]` only when you have confirmed the claim against a")
    A("   source you would be happy to cite on screen.")
    A("2. Mark `[?]` for anything you cannot confirm, then either soften the narration or cut")
    A("   the claim. \"Probably right\" is not a tick.")
    A("3. Rewrite the narration in your own words as you go — do not do a separate pass.")
    A("4. When every box is ticked or resolved, flip `human_rewrite: true` and")
    A("   `status: approved` **in the script file**, not here. `pipeline/originality.py`")
    A("   reads the script, and `tests/test_queue_integrity.py` refuses an approved job")
    A("   whose `human_rewrite` is still false.")
    A("")
    A("## Declared sources")
    A("")
    if sources:
        A("From this job's `description`. Read the primary documents first — a secondary")
        A("account repeating a number is not a source for that number.")
        A("")
        for s in sources:
            A(f"- [ ] {s}")
    else:
        A("_This job's `description` declares no sources._ Add them to the script before")
        A("fact-checking — `originality.source_notes` is set to true, so the gate expects")
        A("source links in the description.")
    A("")
    A(f"## Candidate claims ({total} flagged + {extra} also-read across {len(doc.scenes)} scenes)")
    A("")
    for scene, picked, also_read in claims:
        A(f"### Scene {scene.index} — {scene.heading}")
        A("")
        if not picked and not also_read:
            A("_No candidate claim detected in this scene. Still read it._")
            A("")
            continue
        for sentence, reasons in picked:
            A(f"- [ ] {sentence}")
            A(f"      _why flagged: {'; '.join(reasons)}_ → source: ____________")
        if also_read:
            A("")
            A(f"_Also read — no figure, date or name detected, so these were not auto-flagged._")
            A(f"_Some of them are still claims; tick one if you want to check it._")
            for sentence in also_read:
                A(f"- {sentence}")
        A("")
    A("## Sign-off")
    A("")
    A("- [ ] Every claim above is ticked or resolved")
    A("- [ ] Narration rewritten in my own words")
    A("- [ ] Sources in `description` are the ones I actually used")
    A("- [ ] `human_rewrite: true` set in the script")
    A("- [ ] `status: approved` set in the script")
    A("")
    A(f"Checked by: ____________  Date: ____________")
    A("")
    return "\n".join(L)


def queued_jobs() -> list[Path]:
    return sorted(p for p in QUEUE_DIR.glob("*.md") if p.stem.lower() != "readme")


def out_path(doc) -> Path:
    return OUT_DIR / f"{doc.id}-{doc.slug}.md"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate fact-check worksheets for queued scripts.")
    ap.add_argument("job", nargs="?", help="job id (e.g. 0003); default: all queued jobs")
    ap.add_argument("--all", action="store_true", help="every queued job, not just missing ones")
    ap.add_argument("--force", action="store_true", help="overwrite an existing worksheet")
    ap.add_argument("--stdout", action="store_true", help="print instead of writing")
    args = ap.parse_args(argv)

    jobs = queued_jobs()
    if args.job:
        jobs = [p for p in jobs if p.stem.startswith(args.job)]
        if not jobs:
            print(f"no queued job matching {args.job!r} in {QUEUE_DIR.relative_to(ROOT)}")
            return 1

    written = skipped = 0
    for path in jobs:
        try:
            doc = parse_script(path)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {path.name}: will not parse ({exc})")
            continue
        text = build(doc, path)
        if args.stdout:
            print(text)
            continue
        dest = out_path(doc)
        if dest.exists() and not args.force and not args.all:
            print(f"  = {dest.relative_to(ROOT)} already exists (use --force to regenerate)")
            skipped += 1
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        n_claims = text.count("- [ ] ")
        print(f"  + {dest.relative_to(ROOT)} — {n_claims} checkboxes")
        written += 1

    if args.stdout:
        return 0
    print(f"factcheck: {written} written, {skipped} left alone")
    if written:
        print("  ⚠ these worksheets verify nothing. The claims are yours to check, and only a")
        print("    human may set human_rewrite: true / status: approved in the script file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
