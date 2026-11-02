"""Expand approved prayer scripts to full length — additively, and never silently.

Why this exists
---------------
The production pipeline refuses any script under 650 words (`prayer_pipeline`
raises rather than ship a four-minute promise), so short scripts do not publish
bad videos — they publish *nothing*. Every approved job in the queue sits at
265-408 words, which is why the daily crons have had nothing to build.

The wrong fix is to lower the gate. The right fix is to lengthen the scripts.

What this tool guarantees
-------------------------
Expansion is **additive**. Every original line must still appear, verbatim and in
order, inside the expanded body. A model that rewrites, shortens or "improves"
existing scripture fails validation and the file is left untouched. That is the
one property that makes unattended rewriting safe here: the reviewed words are
still there, and the new words are reviewable on top of them.

It also refuses to write when:

* the result is still under the gate, or wildly over target,
* a scene heading was dropped, reordered or renamed,
* a sentence of 12+ words appears twice (padding by copy-paste),
* a creator name appears (brand invariant: zero personal names),
* the body quotes a psalm that contradicts the title — the defect that put
  Psalm 121 text under a Psalm 27 title in job 0011.

Usage
-----
    python -m tools.expand_scripts --list              # who is under the gate
    python -m tools.expand_scripts --dry-run           # report only
    python -m tools.expand_scripts --write             # requires a model provider
    python -m tools.expand_scripts --check             # scripture labels only

`--write` is deliberately refused for the offline template provider: padding is
not writing, and this tool exists to stop padding from reaching production.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "content" / "queue"

from pipeline.script_doc import MIN_LONGFORM_WORDS

MIN_WORDS = MIN_LONGFORM_WORDS   # the production gate; shared, not copied
TARGET_WORDS = 900       # a comfortable 5:30-6:00 at Charon's pace
MAX_WORDS = 1200
MIN_NEW_SENTENCE_WORDS = 12   # duplicate-detection window
BANNED_NAMES = ("azani", "john azani", "narrated by")

# Distinctive opening or refrain of each psalm this channel uses. A body that
# carries one psalm's fingerprint under another psalm's title is a template
# leak, not a cross-reference — see the 0011 incident.
PSALM_FINGERPRINTS = {
    23: ("the lord is my shepherd", "he maketh me to lie down in green pastures"),
    27: ("the lord is my light and my salvation", "whom shall i fear"),
    34: ("i will bless the lord at all times", "the angel of the lord encampeth"),
    46: ("god is our refuge and strength", "be still, and know that i am god"),
    91: ("he that dwelleth in the secret place", "thou shalt not be afraid for the terror by night"),
    121: ("i will lift up mine eyes unto the hills", "he that keepeth thee will not slumber",
          "the lord is thy keeper"),
}

SENTENCE_RE = re.compile(r"[^.!?]+[.!?]")


class ExpandError(RuntimeError):
    """Raised when an expansion must not be written."""


# --------------------------------------------------------------------------- #
# Reading jobs
# --------------------------------------------------------------------------- #
@dataclass
class Job:
    path: Path
    meta: dict
    body: str

    @property
    def job_id(self) -> str:
        return str(self.meta.get("id", self.path.name[:4]))

    @property
    def title(self) -> str:
        return str(self.meta.get("title", ""))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", "")).strip()

    @property
    def psalm(self) -> int | None:
        match = re.search(r"Psalm\s+(\d+)", self.title)
        return int(match.group(1)) if match else None

    @property
    def words(self) -> int:
        return len(self.body.split())

    def sections(self) -> list[tuple[str, list[str]]]:
        """[(heading, [paragraph, ...]), ...] preserving order."""
        out: list[tuple[str, list[str]]] = []
        heading = ""
        buf: list[str] = []
        for line in self.body.splitlines():
            if line.startswith("## "):
                if heading or any(p.strip() for p in buf):
                    out.append((heading, [p for p in buf if p.strip()]))
                heading, buf = line[3:].strip(), []
            elif line.strip():
                buf.append(line.strip())
        if heading or any(p.strip() for p in buf):
            out.append((heading, [p for p in buf if p.strip()]))
        return out


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        raise ExpandError("job file has no frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ExpandError("unterminated frontmatter")
    raw_meta, body = parts[1], parts[2]
    meta: dict = {}
    for line in raw_meta.splitlines():
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            meta[match.group(1)] = match.group(2).strip().strip('"')
    return meta, body.lstrip("\n")


def load_job(path: Path) -> Job:
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    return Job(path=path, meta=meta, body=body)


def under_gate(paths: list[Path] | None = None) -> list[Job]:
    jobs = []
    for path in paths or sorted(QUEUE_DIR.glob("*.md")):
        job = load_job(path)
        if job.status == "approved" and job.words < MIN_WORDS:
            jobs.append(job)
    return jobs


# --------------------------------------------------------------------------- #
# Checks
# --------------------------------------------------------------------------- #
def scripture_mismatch(job: Job, body: str | None = None) -> list[int]:
    """Psalms whose fingerprints appear in the body but not in the title.

    Only enforced when the title names a psalm. A devotional built on Matthew or
    Philippians may legitimately quote a psalm, so silence is the right answer
    there; a *Psalm 27* job carrying Psalm 121 text is a template leak.
    """
    text = (body if body is not None else job.body).lower()
    present = {n for n, prints in PSALM_FINGERPRINTS.items() if any(p in text for p in prints)}
    if job.psalm is None:
        return []
    return sorted(present - {job.psalm})


def duplicate_long_sentences(body: str, window: int = MIN_NEW_SENTENCE_WORDS) -> list[str]:
    seen: dict[str, int] = {}
    for sentence in SENTENCE_RE.findall(body):
        key = " ".join(sentence.lower().split())
        if len(key.split()) >= window:
            seen[key] = seen.get(key, 0) + 1
    return [s for s, n in seen.items() if n > 1]


def validate(original: Job, expanded: str, target: int = TARGET_WORDS) -> list[str]:
    """Return a list of failures. Empty list means the expansion may be written."""
    problems: list[str] = []
    words = len(expanded.split())
    if words < MIN_WORDS:
        problems.append(f"still {words} words, under the {MIN_WORDS} gate")
    if words > MAX_WORDS:
        problems.append(f"{words} words exceeds the {MAX_WORDS} ceiling")

    # additive only: every original line survives, verbatim, in order
    cursor = 0
    for line in original.body.splitlines():
        line = line.strip()
        if not line:
            continue
        found = expanded.find(line, cursor)
        if found < 0:
            problems.append(f"original line dropped or altered: {line[:70]!r}")
            continue
        cursor = found + len(line)

    # same scene headings, same order
    before = re.findall(r"^## .+$", original.body, re.M)
    after = re.findall(r"^## .+$", expanded, re.M)
    kept = [h for h in after if h in before]
    if kept != before:
        problems.append("scene headings were dropped or reordered")

    # the defect that put Psalm 121 text under a Psalm 27 title: never expand a
    # job whose scripture label is already wrong, and never introduce a new one
    if original.psalm is not None:
        leaked = scripture_mismatch(original, expanded)
        if leaked:
            own = scripture_mismatch(original)
            if own:
                problems.append(
                    f"job already quotes Psalm {own} under a Psalm {original.psalm} title — "
                    "re-author it before expanding, expansion cannot repair scripture"
                )
            else:
                problems.append(
                    f"expansion introduced Psalm {leaked} text into a Psalm {original.psalm} job")

    dupes = duplicate_long_sentences(expanded)
    if dupes:
        problems.append(f"{len(dupes)} sentence(s) repeated verbatim, first: {dupes[0][:70]!r}")

    lowered = expanded.lower()
    for name in BANNED_NAMES:
        if name in lowered:
            problems.append(f"creator name leaked: {name}")

    if "subscribe" in lowered and lowered.count("subscribe") > 1:
        problems.append("more than one subscribe call to action")
    return problems


# --------------------------------------------------------------------------- #
# Providers
# --------------------------------------------------------------------------- #
PROMPT = """You are extending a bedtime prayer script for a faceless scripture channel.

RULES THAT WILL BE ENFORCED BY CODE — a violation discards your output:
1. Every existing line must survive verbatim, in the same order. Do not rewrite,
   shorten, correct or "improve" any existing sentence.
2. Keep the existing scene headings exactly. You may add at most two new scenes,
   using the same "## Scene N — Title (Verses x–y)" pattern.
3. Add 2-4 sentences of new narration per existing scene, in the same voice:
   second person, calm, present tense, spoken aloud at bedtime.
4. Only quote scripture from {psalm_label}. Never quote another psalm.
5. No personal names. No "narrated by". One subscribe call to action only, and it
   must remain the final line of the script.
6. Do not pad. No sentence may repeat. Aim for about {target} words total.

TITLE: {title}
CURRENT WORD COUNT: {words}
TARGET WORD COUNT: {target}

CURRENT SCRIPT
--------------
{body}
--------------

Return only the expanded markdown body, with no commentary and no code fences."""


def gemini_provider(job: Job, target: int) -> str:
    """Live provider: same client and model the authoring brain already uses."""
    from pipeline.gemini_tts import get_gemini_api_key  # local import: offline tests

    key = get_gemini_api_key()
    if not key:
        raise ExpandError("GEMINI_API_KEY is not set; refusing to write")
    from google import genai

    client = genai.Client(api_key=key)
    prompt = PROMPT.format(
        psalm_label=f"Psalm {job.psalm}" if job.psalm else "the psalm named in the title",
        title=job.title, words=job.words, target=target, body=job.body,
    )
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise ExpandError("model returned nothing")
    return text


def template_provider(job: Job, target: int) -> str:
    """Offline stand-in used by tests and dry runs. Never published.

    It appends a breath-and-refrain paragraph to each scene, which is the shape of
    a real expansion without pretending to be writing.
    """
    sections = job.sections()
    out: list[str] = []
    for heading, paragraphs in sections:
        out.append(f"## {heading}")
        out.extend(paragraphs)
        out.append(
            "Take one slow breath here. Let the words you have just heard settle over you "
            "like a blanket, and let your shoulders drop away from your ears."
        )
    body = "\n\n".join(out) + "\n"
    while len(body.split()) < target:
        body = body.replace(
            "\n\n## ", "\n\nTake another slow breath. Nothing is required of you in this "
            "moment except to receive.\n\n## ", 1,
        )
        if body.count("Take another slow breath") > 6:
            break
    return body


PROVIDERS: dict[str, Callable[[Job, int], str]] = {
    "gemini": gemini_provider,
    "template": template_provider,
}


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
@dataclass
class Result:
    job_id: str
    path: Path
    before: int
    after: int = 0
    written: bool = False
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"job_id": self.job_id, "file": self.path.name, "before": self.before,
                "after": self.after, "written": self.written, "problems": self.problems}


def expand_job(job: Job, provider: str = "gemini", target: int = TARGET_WORDS,
               write: bool = False) -> Result:
    result = Result(job_id=job.job_id, path=job.path, before=job.words)
    fn = PROVIDERS.get(provider)
    if fn is None:
        result.problems.append(f"unknown provider {provider!r}")
        return result
    try:
        expanded = fn(job, target)
    except Exception as exc:  # provider faults must never corrupt a job file
        result.problems.append(f"provider error: {exc}")
        return result
    result.after = len(expanded.split())
    result.problems = validate(job, expanded, target)
    if result.problems or not write:
        return result
    header = job.path.read_text(encoding="utf-8").split("---", 2)
    job.path.write_text(f"---{header[1]}---\n\n{expanded.lstrip()}", encoding="utf-8")
    result.written = True
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Expand approved prayer scripts to full length.")
    parser.add_argument("--ids", default="", help="comma-separated job ids (blank = every job under the gate)")
    parser.add_argument("--provider", default="gemini", choices=sorted(PROVIDERS))
    parser.add_argument("--target", type=int, default=TARGET_WORDS)
    parser.add_argument("--write", action="store_true", help="write the expanded body back")
    parser.add_argument("--dry-run", action="store_true", help="report only (default)")
    parser.add_argument("--list", action="store_true", help="list jobs under the gate and exit")
    parser.add_argument("--check", action="store_true", help="scripture-label check only and exit")
    parser.add_argument("--diff", action="store_true", help="print a unified diff per job")
    args = parser.parse_args(argv)

    jobs = under_gate()
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        jobs = [j for j in jobs if j.job_id in wanted]
    if not jobs:
        print("no approved jobs under the gate")
        return 0

    if args.list or args.check:
        bad = 0
        for job in jobs:
            mismatch = scripture_mismatch(job)
            bad += bool(mismatch)
            flag = f"  WRONG PSALM: body quotes Psalm {mismatch}" if mismatch else ""
            print(f"{job.job_id}  {job.words:>4}w  {job.path.name}{flag}")
        print(f"\n{len(jobs)} under the gate, {bad} with a scripture-label defect")
        return 1 if args.check and bad else 0

    write = args.write and not args.dry_run
    if write and args.provider == "template":
        print("refusing --write with the template provider: padding is not writing")
        return 2

    results = [expand_job(job, args.provider, args.target, write) for job in jobs]
    for res in results:
        state = "WROTE" if res.written else ("skipped" if res.problems else "ready")
        print(f"{res.job_id}  {res.before:>4} -> {res.after:>4} words  {state}")
        for problem in res.problems:
            print(f"      ! {problem}")
        if args.diff and res.written:
            before = load_job(res.path).body
            print("".join(difflib.unified_diff(before.splitlines(True), before.splitlines(True))))
    print(json.dumps([r.as_dict() for r in results], indent=2))
    failed = [r for r in results if r.problems]
    return 1 if failed and write else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
