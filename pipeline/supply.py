"""Keep the long-form queue publishable, without a person in the loop.

The brain could already *author* a script, and `tools/expand_scripts.py` could
already lengthen one, but they were separate crons in separate workflows with an
ordering dependency nobody enforced:

* 02:14 UTC expansion, 03:14 UTC brain, 06:14 UTC production. If the expansion
  run was delayed or skipped, production had nothing runnable — and it printed a
  cheerful notice and exited 0, so nothing looked broken.
* The brain counted runway as "approved scripts", including the 100–350 word ones
  it could not publish. So it kept *adding* more of them: twenty-one approved
  scripts in `content/queue/` and not one over the word floor.
* Every new script was authored short, and nothing ever lengthened it.

This module is the missing loop, in one place and in the right order:

    1. lengthen approved scripts that are under the floor,
    2. if the queue still has nothing publishable, author a new one,
    3. verify the result is actually publishable,
    4. say plainly what happened.

The word floor is never lowered — see `MIN_LONGFORM_WORDS`. Every write goes
through `tools.expand_scripts.validate`, which refuses to rewrite, reorder or
drop a single reviewed line, refuses padding, refuses creator names, and refuses
to expand a script whose body quotes the wrong psalm.

Callers: the brain cron (`scripts/gemini_brain.py --ensure-supply`) and the
production workflow, so a missed brain run is repaired by the next release slot
instead of becoming an empty evening.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent

# How many model calls one run may spend lengthening the backlog. The free tier
# is shared with authoring, and a run that spends its whole budget on old scripts
# cannot author the new one the queue actually needs.
MAX_EXPANSIONS_PER_RUN = 3
# When nothing is publishable there is no reason to be frugal: every release slot
# that runs against an empty queue is a wasted slot, and each job converges over
# up to `MAX_ATTEMPTS` model calls, so an empty queue spends more calls per job.
MAX_EXPANSIONS_WHEN_EMPTY = 5
MAX_MODEL_CALLS_PER_RUN = 10
MAX_AUTHORS_PER_RUN = 2
EXPANSION_TARGET_WORDS = 900

# The release slots in .github/workflows/produce.yml: 06:14, 14:14 and 19:14 UTC.
# Supply is measured against this, not against "scripts", because the queue is
# consumed three times a day and a target of one leaves the 7:14pm slot empty.
SLOTS_PER_DAY = 3


@dataclass
class SupplyReport:
    publishable_before: int = 0
    expanded: list[dict[str, Any]] = field(default_factory=list)
    authored: Any = None
    authored_all: list[dict[str, Any]] = field(default_factory=list)
    publishable_after: int = 0
    wanted: int = 1
    blocked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the queue can publish without anyone touching it."""
        return self.publishable_after > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "publishable_before": self.publishable_before,
            "wanted": self.wanted,
            "publishable_after": self.publishable_after,
            "expanded": self.expanded,
            "authored": self.authored,
            "blocked": self.blocked,
            "ok": self.ok,
        }

    def summary(self) -> str:
        bits = [f"{self.publishable_before} publishable before"]
        if self.expanded:
            wrote = [e for e in self.expanded if e.get("written")]
            bits.append(f"{len(wrote)}/{len(self.expanded)} script(s) lengthened")
        if self.authored:
            bits.append(f"authored {self.authored.get('job_id')}")
        bits.append(f"{self.publishable_after} publishable after")
        return "; ".join(bits)


def publishable_longform(queue_dir: Path | None = None) -> list[Path]:
    """Approved scripts that are actually over the word floor.

    Uses the production selector, so this can never disagree with what the
    publisher will pick up.
    """
    from .run import select_jobs

    if queue_dir is not None:  # tests: a scratch queue
        from .script_doc import MIN_LONGFORM_WORDS, parse_script

        out: list[Path] = []
        for path in sorted(Path(queue_dir).glob("*.md")):
            try:
                doc = parse_script(path)
            except Exception:  # noqa: BLE001
                continue
            if str(doc.status).strip().lower() == "approved" and doc.word_count >= MIN_LONGFORM_WORDS:
                out.append(path)
        return out
    return select_jobs(all_flag=False, job_path=None, next_flag=False) or []


def under_gate_jobs(queue_dir: Path | None = None):
    from tools.expand_scripts import under_gate

    if queue_dir is None:
        return under_gate()
    return under_gate(sorted(Path(queue_dir).glob("*.md")))


def expand_backlog(limit: int = MAX_EXPANSIONS_PER_RUN, target: int = EXPANSION_TARGET_WORDS,
                   queue_dir: Path | None = None, write: bool = True) -> list[dict[str, Any]]:
    """Lengthen up to `limit` approved-but-short scripts. Returns one row each.

    A provider that cannot write (no key, quota, model refusal) is reported per
    script and writes nothing; it never falls back to padding.
    """
    from tools.expand_scripts import expand_job

    rows: list[dict[str, Any]] = []
    calls = 0
    for job in under_gate_jobs(queue_dir)[:limit]:
        if calls >= MAX_MODEL_CALLS_PER_RUN:
            break
        result = expand_job(job, provider="gemini", target=target, write=write)
        calls += getattr(result, "attempts", 1)
        row = result.as_dict()
        row["file"] = Path(row.get("file", job.path.name)).name
        rows.append(row)
    return rows


def set_status(path: Path, status: str, approved_by: str = "") -> None:
    """Rewrite only the frontmatter `status:` line, leaving every word intact.

    This is the single choke point for approval in the whole codebase, so the rule
    that approval means publishable lives here: a long-form script under the word
    floor cannot be marked approved by any caller, brain or human or test. The 21
    short scripts that sat approved for weeks are why this guard exists.
    """
    import re

    from .script_doc import MIN_LONGFORM_WORDS, parse_script

    if status == "approved":
        doc = parse_script(Path(path))
        if doc.format == "longform" and doc.word_count < MIN_LONGFORM_WORDS:
            raise ValueError(
                f"{Path(path).name}: {doc.word_count} words cannot be approved — the "
                f"long-form floor is {MIN_LONGFORM_WORDS}. Approved must mean publishable."
            )

    text = Path(path).read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError(f"{path}: no frontmatter to edit")
    head, rest = match.group(1), text[match.end():]

    lines = head.splitlines()
    replaced = False
    for i, line in enumerate(lines):
        if re.match(r"^status\s*:", line):
            comment = f"  #{line.split('#', 1)[1]}" if "#" in line else ""
            lines[i] = f"status: {status}{comment}"
            replaced = True
    if not replaced:
        lines.append(f"status: {status}")
    if approved_by:
        lines = [ln for ln in lines if not ln.startswith("approved_by:")]
        lines.append(f"approved_by: {approved_by}")
    Path(path).write_text("---\n" + "\n".join(lines) + "\n---\n" + rest, encoding="utf-8")


def author_new(brain, expand_target: int = EXPANSION_TARGET_WORDS) -> dict[str, Any]:
    """Author, lengthen if needed, verify, and stage one new long-form job."""
    from .gemini_brain import BrainAuthoringError

    try:
        result = brain.replenish_pipeline(min_runway_days=999.0)  # force one authoring pass
    except BrainAuthoringError as exc:
        return {"ok": False, "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    if result is None:
        return {"ok": False, "reason": "brain returned no script"}

    row: dict[str, Any] = {
        "ok": True,
        "job_id": result.job_id,
        "longform_path": str(result.longform_path),
        "words": result.word_count,
        "short_manifest": str(result.short_manifest_path) if result.short_manifest_path else None,
    }

    # A freshly authored script that lands under the floor is not publishable;
    # lengthen it in the same run rather than leaving it for tomorrow's cron.
    from .script_doc import MIN_LONGFORM_WORDS, parse_script
    from tools.expand_scripts import expand_job, load_job

    doc = parse_script(result.longform_path)
    if doc.word_count < MIN_LONGFORM_WORDS:
        job = load_job(result.longform_path)
        res = expand_job(job, provider="gemini", target=expand_target, write=True)
        row["expansion"] = res.as_dict()
        if res.written:
            row["words"] = res.after
        doc = parse_script(result.longform_path)

    row["words"] = doc.word_count
    if doc.word_count < MIN_LONGFORM_WORDS:
        row["ok"] = False
        row["reason"] = (f"authored {doc.word_count} words; still under the "
                         f"{MIN_LONGFORM_WORDS}-word floor and expansion could not fix it")
        return row

    # Scripture label is checked by machine before anything is approved: a Psalm 27
    # job carrying Psalm 121 text is the defect that shipped once already.
    from tools.expand_scripts import load_job, scripture_mismatch

    leaked = scripture_mismatch(load_job(result.longform_path))
    if leaked:
        row["ok"] = False
        names = ", ".join(f"Psalm {n}" for n in leaked)
        row["reason"] = (f"body quotes {names} under a "
                         f"{doc.title.split(':')[0]} title; refused")
        return row

    # The editorial gate is real, it is just no longer a human queue: the brain
    # approves only a script that cleared the floor, the scripture check, and the
    # factcheck worksheet `verify_and_stage` wrote. A human can still downgrade it.
    if str(doc.status).strip().lower() != "approved":
        set_status(result.longform_path, "approved", approved_by="brain")
        doc = parse_script(result.longform_path)
        row["approved_by_brain"] = True

    row["publishable"] = doc.word_count >= MIN_LONGFORM_WORDS
    row["words"] = doc.word_count
    row["status"] = doc.status
    return row


def ensure_supply(brain, limit: int = MAX_EXPANSIONS_PER_RUN,
                  target: int = EXPANSION_TARGET_WORDS,
                  queue_dir: Path | None = None, write: bool = True,
                  min_publishable: int = 1,
                  max_authors: int = MAX_AUTHORS_PER_RUN) -> SupplyReport:
    """The whole loop: lengthen the backlog, author what is still missing, verify.

    `min_publishable` is how much runway to leave behind: 1 means "tomorrow can
    publish", 2 means "tomorrow and the day after". Authoring stops at that count
    so a healthy queue spends nothing.
    """
    report = SupplyReport()
    report.wanted = min_publishable
    report.publishable_before = len(publishable_longform(queue_dir))

    # Lengthening is the only way the under-floor backlog ever becomes publishable,
    # and it was capped at three per run no matter how far behind the queue was:
    # the backlog could not close while production was spending three schedules a
    # day. Spend enough model calls to close the gap, still within one run's budget.
    shortfall = max(0, min_publishable - report.publishable_before)
    limit = max(limit, min(shortfall, MAX_EXPANSIONS_WHEN_EMPTY))
    if report.publishable_before == 0:
        limit = max(limit, MAX_EXPANSIONS_WHEN_EMPTY)
    report.expanded = expand_backlog(limit=limit, target=target, queue_dir=queue_dir, write=write)
    for row in report.expanded:
        if row.get("problems"):
            report.blocked.append(f"{row['job_id']}: {row['problems'][0]}")

    report.publishable_after = len(publishable_longform(queue_dir))

    authored: list[dict[str, Any]] = []
    for _ in range(max(0, max_authors)):
        if report.publishable_after >= min_publishable or brain is None:
            break
        row = author_new(brain, expand_target=target)
        authored.append(row)
        if not row.get("ok"):
            report.blocked.append(f"authoring: {row.get('reason')}")
            break
        report.publishable_after = len(publishable_longform(queue_dir))

    report.authored = authored[0] if len(authored) == 1 else (authored or None)
    report.authored_all = authored

    if report.publishable_after == 0 and not report.blocked:
        report.blocked.append(
            "no approved script is over the word floor and nothing could be authored"
        )
    return report
