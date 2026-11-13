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


def get_viewer_first_standard() -> str:
    """Titles, openings and retention rules shared by every channel.

    One file for all ten channels on purpose: packaging is not a matter of
    daypart, and a rule that lived in ten system instructions would drift.
    """
    return load_equipment_text("viewer_first_standard.md")


def front_matter_skeleton(channel_id: str | None = None) -> str:
    """The literal front-matter block every authored script must open with.

    The prompt used to state this in prose alone — *"Frontmatter must declare
    `channel: <id>`"* — and nothing else. A census of the queue on 7 November 2026
    says what that costs: `id`, `slug`, `title`, `status`, `format`, `niche`,
    `voice` and `target_minutes` were present in all 27 scripts, and `channel` in
    two. The model was not careless; it was never shown the shape, and the one key
    it had to invent from a sentence is the one it dropped.

    So the block is shown, with the run's own channel filled in. Nothing here is
    invented on the model's behalf at authoring time: this is a template in a
    prompt, and the keys it asks for are the keys `missing_job_keys` requires and
    `_require_own_channel` checks.
    """
    from pipeline.channels import normalize_channel_id
    from pipeline.config import CONFIG

    # No channel id is named here: the default comes from configuration, so this
    # module stays free of channel-specific branches (tests/test_channel_parity.py).
    channel = normalize_channel_id(channel_id or CONFIG.channel_id)
    return f"""## REQUIRED FILE FORMAT — the front matter, exactly

Every script opens with this block, and these key names are machine-read. Two are
load-bearing: a script without `channel:` is published to the wrong channel, and a
script without `slug:` has no queue identity and is discarded. Copy the block and
fill in the values; do not rename, reorder or omit a key.

---
id: '<the 4-digit id you were assigned>'
title: "<the listener's need or the promise, in plain words>: <scripture reference> | <this channel's display name> (35-70 chars; see VIEWER-FIRST STANDARD)"
slug: <kebab-case-slug-of-the-title>
status: approved
channel: {channel}
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
thumb_text: "<2 TO 4 UPPERCASE WORDS THAT COMPLETE THE TITLE, NOT REPEAT IT>"
seo_hook: "<one 75-140 char sentence: who this prayer is for, what it asks God for, and the KJV reference>"
description: |
  <2-3 sentence devotional summary quoting the KJV passage>

  Scripture References & Sources:
  - The Holy Bible (King James Version, Public Domain)
  - Matthew Henry's Commentary on the Whole Bible.
tags:
  - "<channel name lowercase>"
  - "<scripture reference lowercase>"
originality:
  original_thesis: true
  unique_structure: true
  no_ai_persona: true
  source_notes: true
---

After the closing `---`, write ONLY `## Scene 1 — <Title>`, `## Scene 2 — <Title>`, etc.,
followed immediately by pure spoken prayer narration prose. NEVER write stage-direction
prefixes (`Visual Asset:`, `Visual:`, `Kinetic Visual:`, `Typography:`, `Audio:`,
`Narration:`, `visual_query:`) or a second `---` YAML block inside the body — every word
under `## Scene N` is spoken aloud by TTS.
"""


def compile_full_brain_prompt(channel_id: str | None = None) -> str:
    """Combine the channel's equipment modules into one master directive.

    Same modules, same order, for every channel — only the files differ, and
    which files belong to which channel is declared once in
    `pipeline.channel_capabilities`.
    """
    parts = [
        get_system_instruction(channel_id),
        "---",
        front_matter_skeleton(channel_id),
        "---",
        "## THEOLOGICAL EXEGESIS & SCRIPTURE STANDARDS",
        get_theological_rubric(channel_id),
        "---",
        "## DOCOGA REELS v2 KINETIC TYPOGRAPHY & VISUAL ASSET STANDARDS",
        get_docoga_reels_rules(),
        "---",
        # Last on purpose: where an older line about titles or openings
        # disagrees, the most recent instruction is the one the model follows.
        "## VIEWER-FIRST STANDARD: TITLE, OPENING AND RETENTION (ALL CHANNELS)",
        get_viewer_first_standard(),
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
