"""Equipment Registry for Google Gemini Brain.

Loads system instructions, theological rubrics, DOCOGA REELS v2 kinetic typography rules,
and gold-standard exemplars to equip Google Gemini with the complete creative, algorithmic,
and technical standards of The Secret Place.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EQUIPMENT_DIR = Path(__file__).resolve().parent


def load_equipment_text(filename: str) -> str:
    path = EQUIPMENT_DIR / filename
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _is_morning_altar(channel_id: str | None) -> bool:
    value = str(channel_id or "").strip().lower().replace("_", "-")
    return value in {"prayer2", "morning-altar", "the-morning-altar", "channel2"}


def get_system_instruction(channel_id: str | None = None) -> str:
    if _is_morning_altar(channel_id):
        return load_equipment_text("morning_system_instruction.md")
    return load_equipment_text("system_instruction.md")


def get_theological_rubric(channel_id: str | None = None) -> str:
    if _is_morning_altar(channel_id):
        return load_equipment_text("morning_theological_rubric.md")
    return load_equipment_text("theological_rubric.md")


def get_docoga_reels_rules() -> str:
    return load_equipment_text("docoga_reels_rules.md")


def compile_full_brain_prompt(channel_id: str | None = None) -> str:
    """Combine all active equipment modules into a unified master system directive.

    Channel-aware: ``prayer2`` (The Morning Altar) compiles the sunrise
    system instruction and morning rubric; every other/empty id keeps the
    original Secret Place night equipment exactly as before.
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


def list_equipped_modules() -> dict[str, Any]:
    """Return status and file sizes of all active equipment modules."""
    files = sorted(EQUIPMENT_DIR.glob("*.*"))
    return {
        f.name: {
            "size_bytes": f.stat().st_size,
            "is_loaded": True,
        }
        for f in files
        if f.suffix in (".md", ".json", ".py") and f.name != "__pycache__"
    }
