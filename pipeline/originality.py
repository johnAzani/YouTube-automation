"""Originality gate — the demonetization insurance policy.

YouTube's "inauthentic content" policy (Jul 2025 rename, Jul 2026 clarification)
demonetizes generic/template/mass-produced video. Reviewers judge the channel's
overall pattern. This module refuses to build any job whose frontmatter does not
check substantive originality and source-note flags. Human rewriting is recorded
when present, but is not a publishing gate for this autonomous studio. These
checks cannot verify originality or factual accuracy on their own.
"""
from __future__ import annotations

from .script_doc import ScriptDoc

REQUIRED_FLAGS = (
    "original_thesis",
    "unique_structure",
    "no_ai_persona",
    "source_notes",
)

FORBIDDEN_PERSONA_PATTERNS = (
    r"\bas a (?:doctor|physician|lawyer|attorney|financial advisor|financial planner)\b",
    r"\bi am a (?:doctor|physician|lawyer|attorney|financial advisor|certified)\b",
    r"\bmy (?:patients|clients|firm)\b",
)


class OriginalityError(RuntimeError):
    pass


def check(doc: ScriptDoc) -> list[str]:
    """Return a list of violations; empty list means the job may proceed."""
    problems: list[str] = []
    flags = doc.meta.get("originality")

    if not isinstance(flags, dict):
        problems.append("frontmatter is missing the 'originality' checklist block (PLAN.md §4.4)")
        return problems

    for flag in REQUIRED_FLAGS:
        if flags.get(flag) is not True:
            problems.append(f"originality.{flag} must be explicitly set to true")

    import re

    body = doc.full_narration.lower()
    for pattern in FORBIDDEN_PERSONA_PATTERNS:
        if re.search(pattern, body):
            problems.append(
                f"script matches a forbidden AI-persona/sensitive-advice pattern: {pattern!r} "
                "(YouTube demonetizes AI personas posing as experts on health/finance/legal topics)"
            )

    if doc.word_count < 60:
        problems.append(f"script is too thin ({doc.word_count} words) — add real substance")

    # Description must carry sources (checklist asserts it; we double-check text)
    if flags.get("source_notes") and not any(k in doc.description.lower() for k in ("http", "source", "reference", "bibliograph")):
        problems.append("originality.source_notes is true but description has no source links/text")

    return problems


def enforce(doc: ScriptDoc) -> None:
    problems = check(doc)
    if problems:
        bullet = "\n".join(f"  ✗ {p}" for p in problems)
        raise OriginalityError(
            f"Originality gate blocked job {doc.id} ({doc.slug}):\n{bullet}\n"
            "Fix the script and checklist in the markdown file, then re-run."
        )
