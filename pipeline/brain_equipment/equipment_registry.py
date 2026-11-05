"""Equipment Registry for Google Gemini Brain.

Loads system instructions, theological rubrics, DOCOGA REELS v2 kinetic typography rules,
and gold-standard exemplars to equip Google Gemini with the creative, algorithmic and
technical standards of the channel it is authoring for.

Channel identity is *data*: which files a channel compiles lives in
`pipeline.channel_capabilities`, so a new channel is a registry entry, not a new
`if` statement in here. Every channel compiles the same three modules — its own
system instruction and theological rubric, plus the shared DOCOGA REELS v2 rules.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.channel_capabilities import equipment_text

EQUIPMENT_DIR = Path(__file__).resolve().parent


def load_equipment_text(filename: str) -> str:
    path = EQUIPMENT_DIR / filename
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def get_system_instruction(channel_id: str | None = None) -> str:
    return equipment_text(channel_id, "system_instruction")


def get_theological_rubric(channel_id: str | None = None) -> str:
    return equipment_text(channel_id, "theological_rubric")


def get_docoga_reels_rules() -> str:
    return load_equipment_text("docoga_reels_rules.md")


def compile_full_brain_prompt(channel_id: str | None = None) -> str:
    """Combine the channel's equipment modules into one master directive.

    Same modules, same order, for every channel — only the files differ, and
    which files belong to which channel is declared once in
    `pipeline.channel_capabilities`.
    """
    parts = [
        get_system_instruction(channel_id),
        "---",
        "## THEOLOGICAL EXEGESIS & SCRIPTURE STANDARDS",
        get_theological_rubric(channel_id),
        "---",
        "## DOCOGA REELS v2 KINETIC TYPOGRAPHY & VISUAL ASSET STANDARDS",
        get_docoga_reels_rules(),
    ]
    return "\n\n".join(filter(None, parts))


# Short alias used by channel-scoped callers.
def compile_brain_prompt(channel_id: str | None = None) -> str:
    return compile_full_brain_prompt(channel_id)


def list_equipped_modules(channel_id: str | None = None) -> dict[str, Any]:
    """Return status and file sizes of all equipment modules on disk.

    `channel_id` is accepted for symmetry with the rest of the registry and is
    echoed in ``scripts/gemini_brain.py --audit``; the on-disk listing is shared
    so an audit shows every module installed for the repository.
    """
    files = sorted(EQUIPMENT_DIR.glob("*.*"))
    return {
        f.name: {
            "size_bytes": f.stat().st_size,
            "is_loaded": True,
        }
        for f in files
        if f.suffix in (".md", ".json", ".py") and f.name != "__pycache__"
    }
