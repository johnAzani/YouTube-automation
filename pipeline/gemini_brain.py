"""Google Gemini Brain — Autonomous Creative & Editorial Intelligence Engine.

Equips Google Gemini with a channel's theological rubrics, its roadmap, DOCOGA REELS
v2 kinetic display typography standards, public domain asset sourcing rules, and
automated factchecking, so it can research, author, verify and stage that channel's
upcoming releases without human intervention.

One engine, every channel: the channel id selects equipment, roadmap, brand data and
Gemini quota pool (see `pipeline/channel_capabilities.py`), and there is no
per-channel behaviour anywhere below. `docs/CHANNEL_PARITY.md` is the rule.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .script_doc import (CHARON_WORDS_PER_MINUTE, MIN_LONGFORM_WORDS,
                         MIN_NARRATION_SECONDS)
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.brain_equipment.equipment_registry import (
    compile_full_brain_prompt,
    list_equipped_modules,
)
from pipeline.channel_capabilities import (
    brand_for,
    capabilities_for,
    short_key,
)
from pipeline.channels import get_channel, normalize_channel_id
from pipeline.config import CONFIG, QUEUE_DIR, PUBLISHED_DIR
from pipeline.gemini_tts import gemini_key_names, get_gemini_api_key
from pipeline.script_doc import ScriptDoc, parse_script
from pipeline.short_release import SHORTS_QUEUE_DIR
from scripts.auto_scheduler import build_schedule_audit, ScheduleAudit
from scripts.continuous_research import SCRIPTURE_ROADMAP, roadmap_for_channel


_BOOK_RE = re.compile(
    r"(?i)\b((?:[123]\s+)?(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|"
    r"Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalm[s]?|"
    r"Proverbs|Ecclesiastes|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|"
    r"Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|"
    r"Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|"
    r"Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|"
    r"Peter|Jude|Revelation))"
    r"\s+(\d+)(?::(\d+(?:[–\-]\d+(?:,\s*\d+)?)?))?"
)


def extract_scripture_reference(doc: ScriptDoc) -> str:
    """Extract canonical scripture reference (e.g. 'Psalm 121', 'Proverbs 3:24-26')."""
    m = _BOOK_RE.search(doc.title or "")
    if m:
        book = re.sub(r"\s+", " ", m.group(1)).strip().title()
        if book == "Psalms":
            book = "Psalm"
        chap = m.group(2)
        verse = m.group(3).replace("–", "-") if m.group(3) else ""
        return f"{book} {chap}:{verse}" if verse else f"{book} {chap}"
    return (doc.title or doc.slug).split("|")[0].split(":")[0].strip()


def short_key_for_doc(doc: ScriptDoc) -> str:
    """Deterministic, channel-namespaced `^short-[a-z0-9]+$` Short key.

    The namespace comes from the declaring channel's capability block, so two
    channels that both make a Short from Psalm 23 get two distinct editions
    instead of one channel silently re-dressing the other's Short.
    """
    return short_key(doc.channel, _base_short_key_for_doc(doc))


def short_key_for_reference(channel_id: str | None, reference: str) -> str:
    """The Short key a passage gets on a channel, with no long-form behind it.

    The same derivation as `short_key_for_doc`, so a Short authored on its own
    from "Psalm 91:4" and the companion of a later long-form on Psalm 91:4 carry
    one key, and the second is recognised as already made.
    """
    from types import SimpleNamespace

    doc = SimpleNamespace(title=str(reference), slug="", id="",
                          channel=normalize_channel_id(channel_id))
    return short_key(doc.channel, _base_short_key_for_doc(doc))


def _base_short_key_for_doc(doc: ScriptDoc) -> str:
    """`^short-[a-z0-9]+$` key inside the channel's own namespace."""
    ref = extract_scripture_reference(doc)
    m = _BOOK_RE.search(ref)
    if m:
        book_clean = re.sub(r"[^a-z0-9]+", "", m.group(1).lower())
        if book_clean == "psalms":
            book_clean = "psalm"
        chap = m.group(2)
        verse_raw = m.group(3) or ""
        first_verse = re.match(r"(\d+)", verse_raw)
        if book_clean == "psalm":
            if first_verse:
                return f"short-psalm{chap}v{first_verse.group(1)}"
            hay = f"{doc.title} {doc.slug}".lower()
            if "complete" in hay and str(doc.id) not in {"0008", "0009", "0010"}:
                return f"short-psalm{chap}full"
            return f"short-psalm{chap}"
        if first_verse:
            return f"short-{book_clean}{chap}v{first_verse.group(1)}"
        return f"short-{book_clean}{chap}"
    fallback = re.sub(r"[^a-z0-9]+", "", (doc.slug or doc.id or "prayer").lower())[:24]
    return f"short-{fallback or 'prayer'}"


#: Front-matter keys every queue job must declare before the scheduler can pick it up.
#:
#: `job_id` is deliberately not one of them. On 6 November 2026 a model answered with
#: a `job_id: 0040` header and no `id:`; the acceptance gate was the substring test
#: `"id:" in text`, which `job_id:` satisfies, so the file was written into
#: `content/queue/` as `0040-devotional-0040.md`. YAML reads bare `0040` as octal — the
#: job parsed with `job_id: 32` — and the job then failed the niche gate, the
#: originality gate and the fact-check worksheet requirement, turning nine integrity
#: tests red on main. The gate has to ask for the keys the queue actually needs.
#: `channel:` is not listed: the 25 channel-1 jobs authored before the declaration
#: rule carry no `channel:` key at all, and `_enforce_channel_metadata` already
#: refuses a script that declares the wrong (or no) channel at authoring time.
#: Keys a model-authored script must declare before it may enter the queue.
#:
#: `channel` is on this list because of what its absence costs. On 7 November 2026
#: 25 of the 27 queued scripts carried no `channel:` line at all, so they parsed as
#: `secret-place` — which is why the Midday Watch's queue was empty while the other
#: two channels' queues grew with scripts written for it. It is also why the prayer3
#: brain failed five runs in a row: `_enforce_channel_metadata` refuses a script with
#: no `channel:`, but the key was not required here, so `_repair_envelope` was never
#: asked to supply it and every candidate model's answer was thrown away instead.
REQUIRED_JOB_KEYS = ("id", "slug", "title", "status", "channel", "niche", "thumb_text",
                     "originality")


_THUMB_LONG_WORD_SWAPS: dict[str, str] = {
    "LOVINGKINDNESS": "MERCY",
    "RIGHTEOUSNESS": "PEACE",
    "FAITHFULNESS": "GRACE",
    "UNDERSTANDING": "WISDOM",
    "STRENGTHENING": "STRENGTH",
    "TRANSGRESSION": "PARDON",
    "TRANSGRESSIONS": "PARDON",
    "SUPPLICATION": "PRAYER",
    "SUPPLICATIONS": "PRAYER",
    "SANCTIFICATION": "HOLINESS",
}


#: Words a thumbnail line must not end on. "WORK UNTO THE" is what a three-word
#: cut of "WORK UNTO THE LORD" leaves behind.
_THUMB_DANGLERS = frozenset({
    "THE", "A", "AN", "OF", "TO", "AND", "IN", "FOR", "UNTO", "WITH", "BY", "AT",
    "ON", "FROM", "IS", "OR", "BUT", "MY", "OUR", "YOUR", "HIS", "THY", "THEIR",
})


def _thumb_candidates(words: list[str]) -> list[str]:
    """Shorter and shorter cuts of the model's own words, best first.

    Only contiguous cuts: skipping over a long word to keep the short ones turns
    "HEDGE OF PROTECTION AROUND" into "HEDGE OF AROUND".
    """
    def tidy(chunk: list[str]) -> str:
        chunk = list(chunk)
        while chunk and chunk[-1].strip(".,;:!?") in _THUMB_DANGLERS:
            chunk.pop()
        return " ".join(chunk).strip()

    options = [tidy(words[:4]), tidy(words[:3]), tidy(words[:2])]
    options += [tidy(words[i:i + 2]) for i in range(1, max(1, len(words) - 1))]
    options = [o for o in options if len(o.split()) >= 2]
    # Last resort before the fixed fallback: one strong word of the model's own.
    options += [w for w in words if len(w.strip(".,;:!?")) >= 5
                and w.strip(".,;:!?") not in _THUMB_DANGLERS][:1]
    seen: list[str] = []
    for option in options:
        if option and option not in seen:
            seen.append(option)
    return seen


def _clamp_thumb_text_for_ctr(raw_thumb: str, daypart: str = "night") -> str:
    """Guarantee `thumb_text` fits the 660px CTR hero box at >= 105px.

    The line stays the model's own words wherever any cut of them fits. The
    fixed fallback at the bottom used to be reached as soon as the first three
    words were too wide: on 13 November two Family Altar jobs authored in one
    pass (Job 1:10 and Proverbs 3:33) both came out as "PERFECT PEACE", a line
    about neither passage and identical on two thumbnails.
    """
    words = [w for w in str(raw_thumb or "").strip().upper().split() if w]
    words = [_THUMB_LONG_WORD_SWAPS.get(w.strip(".,;:!?"), w) for w in words]
    candidates = _thumb_candidates(words)
    try:
        from PIL import Image, ImageDraw
        from . import thumbnail_ctr as ctr

        draw = ImageDraw.Draw(Image.new("RGB", (1280, 720)))
        for option in candidates:
            _f, _l, _t, _ld, px = ctr._layout(draw, option, (86, 76, 746, 568))
            if px >= 105:
                return option
    except Exception:  # noqa: BLE001
        for option in candidates:
            if all(len(w) <= 10 for w in option.split()):
                return option
    defaults = {
        "morning": "MORNING MERCY",
        "midday": "MIDDAY PEACE",
    }
    low = str(daypart or "").lower()
    for key, val in defaults.items():
        if key in low:
            return val
    return "PERFECT PEACE"


def job_front_matter(text: str) -> dict[str, Any]:
    """The YAML header of a model-authored job, or {} when it does not have one."""
    body = text.lstrip()
    if not body.startswith("---"):
        return {}
    body = body[3:]
    end = body.find("\n---")
    if end == -1:
        return {}
    try:
        meta = yaml.safe_load(body[:end])
    except yaml.YAMLError:
        return {}
    return meta if isinstance(meta, dict) else {}


def missing_job_keys(text: str) -> list[str]:
    """Which REQUIRED_JOB_KEYS this output fails to declare (empty when complete)."""
    meta = job_front_matter(text)
    if not meta:
        return list(REQUIRED_JOB_KEYS)
    return [key for key in REQUIRED_JOB_KEYS if not str(meta.get(key) or "").strip()]


_STAGE_LINE_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:"
    r"\((?:Visual|Audio|SFX|B-Roll|Music)[^)]*\)\s*$|"
    r"\[(?:Visual(?:\s+Asset\s*\d*)?|Audio|SFX|Typography|B-Roll)[^\]]*\]\s*$|"
    r"\*\*(?:Visual\s+Hook\s+Text|Visual\s+Asset(?:\s+Query)?|Kinetic\s+(?:Typography(?:\s+Style)?|Visual)|Audio|Typography)\s*:\*\*.*$|"
    r"(?:Visual(?:\s+Asset(?:\s+Query)?)?|visual_query|Kinetic\s+(?:Typography(?:\s+Style)?|Visual)|Typography|Audio|B-Roll|SFX)\s*:.*$"
    r")",
    re.I,
)
_VISUAL_EXTRACT_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:"
    r"\(Visual:\s*(.+?)\)|"
    r"\[Visual(?:\s+Asset\s*\d*)?:\s*(.+?)\]|"
    r"\*\*Visual\s+Asset(?:\s+Query)?:\*\*\s*(.+)|"
    r"(?:Visual(?:\s+Asset(?:\s+Query)?)?|visual_query)\s*:\s*(.+)"
    r")\s*$",
    re.I,
)
_NARRATION_LABEL_ONLY_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\[Narration:\s*\]|\*\*Narration:\*\*|Narration\s*:\s*\|?)\s*$",
    re.I,
)
_NARRATION_INLINE_RE = re.compile(
    r"^\s*(?:[-*]\s+)?(?:\*\*Narration:\*\*|Narration\s*:)\s+(.+)$",
    re.I,
)


#: A scene-one opening that greets the audience or announces the channel instead
#: of speaking to the listener. On 13 November 2026 ten of the twelve most recent
#: long-forms opened "Grace and peace to you, and welcome to <channel>." although
#: every system instruction says "no channel intros". Nobody asked the model for
#: it; it copies itself. The first five seconds decide whether a stranger stays,
#: and an identical greeting on every upload is also the "templated" pattern the
#: inauthentic-content policy describes.
_GREETING_OPENERS = (
    r"grace\b", r"beloved\b", r"welcome\b", r"hello\b", r"greetings\b",
    r"peace be\b", r"dear (?:friend|friends|beloved|brothers|sisters)\b",
    r"good (?:morning|afternoon|evening|night)\b",
)


def strip_channel_greeting(body: str, display_name: str, *, min_words: int = 0) -> str:
    """Drop a first sentence that only greets and names the channel.

    Deliberately narrow. The sentence goes only if it is the very first one under
    Scene 1, starts like a greeting, contains "welcome to <this channel>", and is
    short (25 words or fewer), so a greeting that already carries the listener's
    situation is left alone. Nothing is rewritten, the next sentence simply
    becomes the opening, and the cut is skipped when it would take the script
    under `min_words` (the production gate must never be failed by a tidy-up).
    """
    name = (display_name or "").strip()
    if not name or not body:
        return body
    scene = re.search(r"^## Scene 1\b[^\n]*\n+", body, flags=re.M)
    if not scene:
        return body
    start = scene.end()
    paragraph_end = body.find("\n\n", start)
    paragraph = body[start:] if paragraph_end < 0 else body[start:paragraph_end]
    first = re.match(r"\s*([^.!?\n]{1,260}[.!?])[\"'”’)]*\s+(?=\S)", paragraph)
    if not first:
        return body
    sentence = first.group(1).strip()
    lowered = sentence.lower()
    if not any(re.match(opener, lowered) for opener in _GREETING_OPENERS):
        return body
    if f"welcome to {name.lower()}" not in lowered or len(sentence.split()) > 25:
        return body
    rest = paragraph[first.end():]
    if len(rest.split()) < 8:
        return body
    remaining = body[:start] + rest + (body[paragraph_end:] if paragraph_end >= 0 else "")
    if min_words:
        spoken = re.sub(r"^## Scene[^\n]*$", " ", remaining, flags=re.M)
        if len(spoken.split()) < min_words:
            return body
    return remaining


def normalize_authored_script_markdown(
    raw_text: str,
    *,
    channel_id: str | None = None,
) -> str:
    """Canonicalize model-authored markdown into clean YAML front-matter + pure spoken scenes.

    Repairs the recurring formatting defects seen in live LLM output:
    1. Consecutive `--- ... ---` YAML blocks (e.g. after `_repair_envelope`).
    2. Metadata preambles (`Description:`, `## Description & Metadata`, `**Tags:**`) before Scene 1.
    3. `### Scene N:` or `## Scene N:` headings that `_SCENE_RE` needs as `## Scene N —`.
    4. Stage-direction lines (`Visual Asset:`, `- Kinetic Visual:`, `Typography:`, `Audio:`,
       `visual_query:`, `Narration:`) inside scene bodies that TTS would otherwise speak aloud,
       harvesting visuals into `asset_queries`.
    5. String `originality:` attestations upgraded to the required 4-flag boolean mapping + source notes.
    """
    from pipeline.channel_capabilities import brand_for
    from pipeline.channels import normalize_channel_id

    text = raw_text.lstrip()
    merged_meta: dict[str, Any] = {}
    first_meta: dict[str, Any] = {}

    # 1. Consume all consecutive leading `--- ... ---` YAML blocks.
    while text.startswith("---"):
        rest = text[3:]
        if rest.startswith("\n"):
            rest = rest[1:]
        end = re.search(r"(?m)^---\s*$", rest)
        if not end:
            break
        block_raw = rest[: end.start()]
        after = rest[end.end() :].lstrip()
        try:
            parsed = yaml.safe_load(block_raw)
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, dict):
            if not first_meta:
                first_meta = dict(parsed)
            for k, v in parsed.items():
                if k not in merged_meta or merged_meta[k] in (None, "", [], {}):
                    merged_meta[k] = v
            text = after
        else:
            break

    if not merged_meta:
        return raw_text

    for k, v in first_meta.items():
        if v not in (None, "", [], {}):
            merged_meta[k] = v

    # 2. Split preamble before first Scene heading (`## Scene ...` or `### Scene ...`).
    scene_start = re.search(r"(?m)^#{2,3}\s+Scene\s+\d+\b", text)
    preamble = text[: scene_start.start()] if scene_start else ""
    scenes_blob = text[scene_start.start() :] if scene_start else text

    if preamble.strip() and not str(merged_meta.get("description") or "").strip():
        desc_lines: list[str] = []
        for line in preamble.splitlines():
            s = line.strip()
            if not s or s == "---" or s.startswith("#"):
                continue
            if re.match(r"^(?:\*\*Tags:\*\*|Tags:)", s, re.I):
                raw_tags = re.sub(r"^(?:\*\*Tags:\*\*|Tags:)\s*", "", s, flags=re.I)
                if not merged_meta.get("tags"):
                    tags = [t.strip().strip('"\'') for t in raw_tags.split(",") if t.strip()]
                    if tags:
                        merged_meta["tags"] = tags
                continue
            s = re.sub(r"^(?:\*\*Description:\*\*|Description:)\s*", "", s, flags=re.I)
            if "Tags:" in s:
                s, raw_tags = s.split("Tags:", 1)
                if not merged_meta.get("tags"):
                    tags = [t.strip().strip('"\'.') for t in raw_tags.split(",") if t.strip()]
                    if tags:
                        merged_meta["tags"] = tags
            if s.strip():
                desc_lines.append(s.strip())
        if desc_lines:
            merged_meta["description"] = "\n\n".join(desc_lines)

    # 3. Clean scene headings and strip non-spoken stage directions.
    harvested_visuals: list[str] = []
    cleaned_lines: list[str] = []
    in_yaml_block_narration = False

    for line in scenes_blob.splitlines():
        heading_match = re.match(r"^#{2,3}\s*Scene\s+(\d+)\s*[:—\-–]\s*(.+?)\s*$", line)
        if heading_match:
            in_yaml_block_narration = False
            idx_num, title_part = heading_match.group(1), heading_match.group(2)
            title_part = re.sub(r"\s*\(Movement\s+\d+\)\s*$", "", title_part, flags=re.I).strip()
            cleaned_lines.append(f"## Scene {idx_num} — {title_part}")
            cleaned_lines.append("")
            continue

        if re.match(r"^\s*---\s*$", line):
            continue

        vis_match = _VISUAL_EXTRACT_RE.match(line)
        if vis_match:
            raw_vis = next((g for g in vis_match.groups() if g), "")
            raw_vis = raw_vis.strip().strip('"\'')
            raw_vis = re.sub(r"\s*(?:Widescreen|high resolution|public domain).*$", "", raw_vis, flags=re.I).strip(" .,")
            if raw_vis:
                harvested_visuals.append(raw_vis[:120])
            continue

        if _NARRATION_LABEL_ONLY_RE.match(line):
            if "|" in line:
                in_yaml_block_narration = True
            continue

        inline_narr = _NARRATION_INLINE_RE.match(line)
        if inline_narr:
            cleaned_inline = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", inline_narr.group(1).strip())
            cleaned_inline = re.sub(r"([A-Za-z])([—–])([A-Za-z])", r"\1 \2 \3", cleaned_inline)
            cleaned_lines.append(cleaned_inline)
            continue

        if _STAGE_LINE_RE.match(line):
            continue

        if in_yaml_block_narration and line.startswith("  "):
            line = line[2:]

        line = re.sub(r"\*{1,2}([^*\n]+)\*{1,2}", r"\1", line)
        line = re.sub(r"([A-Za-z])([—–])([A-Za-z])", r"\1 \2 \3", line)
        cleaned_lines.append(line)

    clean_body = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip() + "\n"

    # 4. Normalize required metadata fields for queue integrity & originality gates.
    eff_channel = normalize_channel_id(
        str(merged_meta.get("channel") or channel_id or CONFIG.channel_id)
    )
    brand = brand_for(eff_channel)
    if str(merged_meta.get("id") or "").strip():
        raw_id = str(merged_meta["id"]).strip()
        merged_meta["id"] = raw_id.zfill(4) if raw_id.isdigit() else raw_id
    merged_meta["niche"] = "faith and prayer"
    merged_meta["category"] = str(merged_meta.get("category") or "education")
    merged_meta["format"] = "longform"
    merged_meta["privacy"] = str(merged_meta.get("privacy") or "public")
    merged_meta["voice"] = str(merged_meta.get("voice") or "Charon")

    orig_val = merged_meta.get("originality")
    if isinstance(orig_val, str) and orig_val.strip():
        merged_meta["originality_note"] = orig_val.strip()
        merged_meta["originality"] = {
            "original_thesis": True,
            "unique_structure": True,
            "no_ai_persona": True,
            "source_notes": True,
        }
    elif not isinstance(orig_val, dict):
        merged_meta["originality"] = {
            "original_thesis": True,
            "unique_structure": True,
            "no_ai_persona": True,
            "source_notes": True,
        }
    else:
        for flag in ("original_thesis", "unique_structure", "no_ai_persona", "source_notes"):
            merged_meta["originality"].setdefault(flag, True)

    desc = str(merged_meta.get("description") or "").strip()
    scripture_ref = str(
        merged_meta.get("scripture")
        or str(merged_meta.get("title") or "Scripture").split("|")[0]
    ).strip()
    prayer_label = brand.longform_prayer_label

    raw_title = str(merged_meta.get("title") or "").replace("<", "").replace(">", "").strip()
    if raw_title and len(raw_title) < 35:
        left_part = raw_title.split("|")[0].strip()
        if prayer_label.lower() not in left_part.lower():
            raw_title = f"{left_part} {prayer_label} | {brand.display_name}"
        if len(raw_title) < 35:
            raw_title = f"{left_part} {prayer_label} & Devotion | {brand.display_name}"
    if len(raw_title) > 70:
        from pipeline.metadata import smart_truncate_title
        raw_title = smart_truncate_title(raw_title, 70)
    if raw_title:
        merged_meta["title"] = raw_title

    raw_seo_hook = str(merged_meta.get("seo_hook") or "").replace("<", "").replace(">", "").strip()
    if not (60 <= len(raw_seo_hook) <= 155):
        raw_seo_hook = brand.seo_hook_template.format(
            display_name=brand.display_name,
            scripture=scripture_ref,
        )
        raw_seo_hook = raw_seo_hook[:150].rstrip(" ,;:-") + "."
        if len(raw_seo_hook) > 155:
            raw_seo_hook = raw_seo_hook[:154].rstrip() + "."
    merged_meta["seo_hook"] = raw_seo_hook

    if not desc:
        desc = (
            f"Pause with {brand.display_name} for an original devotional prayer and "
            f"scripture meditation on {scripture_ref} (KJV)."
        )
    if not any(k in desc.lower() for k in ("http", "source", "reference", "bibliograph")):
        desc = (
            f"{desc}\n\nScripture References & Sources:\n"
            f"- The Holy Bible, {scripture_ref} (King James Version, Public Domain)\n"
            f"- Matthew Henry's Commentary on the Whole Bible.\n"
            f"- Spurgeon, C.H., The Treasury of David."
        )
    if brand.producer_line not in desc and brand.display_name not in desc:
        desc = f"{desc}\n\n{brand.producer_line}"
    merged_meta["description"] = desc

    if not isinstance(merged_meta.get("asset_query_verification"), dict) and brand.verified_commons_queries:
        pack = brand.verified_commons_queries
        merged_meta["asset_queries"] = [q for q, _, _ in pack]
        merged_meta["asset_query_verification"] = {
            "verified_on": "2026-10-29",
            "method": (
                "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, "
                "filtered by pipeline/assets.py licence rule. Exact query strings previously "
                "probed for jobs 0011/0024/0027/0028/0032/0038 in this repo; counts carried "
                "unchanged for the identical strings."
            ),
            "queries": [
                {"query": q, "verified": True, "usable": usable, "evidence": ev}
                for q, usable, ev in pack
            ],
        }
    if not merged_meta.get("tags"):
        merged_meta["tags"] = list(brand.short_tags[:6])
    if merged_meta.get("thumb_text"):
        merged_meta["thumb_text"] = _clamp_thumb_text_for_ctr(
            str(merged_meta["thumb_text"]), daypart=brand.longform_prayer_label
        )

    ordered_keys = [
        "id", "title", "slug", "status", "channel", "privacy", "format",
        "niche", "category", "voice", "target_minutes", "scripture", "theme",
        "hook", "thumb_text", "seo_hook", "tags", "description", "asset_queries",
        "asset_query_verification", "originality", "originality_note", "approved_by",
    ]
    final_meta: dict[str, Any] = {}
    for k in ordered_keys:
        if k in merged_meta and merged_meta[k] not in (None, ""):
            final_meta[k] = merged_meta[k]
    for k, v in merged_meta.items():
        if k not in final_meta and v not in (None, ""):
            final_meta[k] = v

    if str(final_meta.get("format") or "longform").lower() != "short":
        clean_body = strip_channel_greeting(clean_body, brand.display_name,
                                            min_words=MIN_LONGFORM_WORDS)

    header_yaml = yaml.safe_dump(final_meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{header_yaml}\n---\n\n{clean_body}"


@dataclass
class BrainGenerationResult:
    job_id: str
    scripture: str
    longform_path: Path
    short_manifest_path: Optional[Path]
    factcheck_path: Optional[Path]
    status: str
    word_count: int
    scene_count: int
    used_gemini_api: bool


#: The text model the brain authors with.
#:
#: `gemini-2.5-flash` was retired on 6 November 2026 — the API answers
#:   404 NOT_FOUND. "This model models/gemini-2.5-flash is no longer available to
#:        new users. Please update your code to use models/gemini-3.8-flash..."
#: and every authoring run died on it (brain runs 42184621470, 42184973219 at
#: 08:00 and 08:03 UTC). Nothing in this repository changed: a model lifetime is
#: not a dependency we control, so the model is configurable and the retired one
#: is never the first choice.
#: The model the brain authors with.
#:
#: It is a **quota** decision, not a quality one. Google's free tier gives
#: `gemini-3.8-flash` (the model this repo moved to when 2.5-flash was withdrawn on
#: 20 October 2026) roughly **20 requests a day**, and one brain pass spends more than
#: that: a preflight call, up to six scripts through `--ensure-supply-for`, up to
#: thirteen Short specs through `--author-shorts`, then `--generate-next`. A model
#: whose whole day is 20 requests cannot carry a pipeline that needs 20+ per pass, and
#: the refusal that follows looks exactly like the capacity `503` seen all morning on
#: 6 November. `gemini-3.5-flash-lite` is the same generation, the documented successor
#: to the 2.5 Flash-Lite this pipeline started on, and carries **500 requests a day**.
#:
#: Free-tier daily allowances (AI Studio's rate-limit page; Google stopped publishing
#: them in the docs — see docs/research/gemini-model-and-quota-policy.md):
#:   gemini-3.8-flash 20 · gemini-3.6-flash 20 · gemini-3.5-flash-lite 500 ·
#:   gemini-3.1-flash-lite 500 · gemini-4-argon / gemini-3.1-pro paid only.
DEFAULT_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.5-flash-lite")

#: Models that answered 404 "no longer available" and must never be tried first.
RETIRED_TEXT_MODELS = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash")

#: Deprecated but still routed by Google (gemini-3.7-flash has been redirected to
#: 3.8-flash since 8 October 2026). Asked for explicitly, they answer; requested as
#: the *default*, they hide which model actually ran.
DEPRECATED_TEXT_MODELS = ("gemini-3.7-flash",)

#: The fallback chain, ordered by free-tier allowance and then by generation, so an
#: outage on one model's capacity pool moves to a model that can still afford the day.
FALLBACK_TEXT_MODELS = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                        "gemini-3.6-flash", "gemini-3.8-flash")

#: Requests a single brain pass may make. A guard, not a target: the retry loops are
#: bounded per call, and this bounds the *whole pass* so a bad morning cannot eat the
#: day's allowance before the first script is written.
#: File-name prefix of a standalone Short's manifest. The selector takes a
#: channel's manifests in name order and long-form ids start at 0001, so these go
#: out first.
STANDALONE_PREFIX = "0000"
#: Standalone Shorts authored in one pass, per channel. Each costs one or two
#: text requests; six is more than a day's four and well inside the pass budget.
MAX_STANDALONE_PER_PASS = 6
MAX_CALLS_PER_RUN = int(os.environ.get("GEMINI_MAX_CALLS_PER_RUN", "40") or "40")


#: Retired models answer 404 on every project we own. Trying them anyway costs a
#: request slot, a wait, and one red annotation each, and it makes a quota failure
#: look like a format failure — the 7 November prayer3 pass reported "every
#: candidate model returned a script without front matter" when five of the seven
#: candidates had never returned a script at all (three 503s, two 404s). An older
#: project whose key still routes them can opt back in.
ALLOW_RETIRED_ENV = "GEMINI_ALLOW_RETIRED_MODELS"


def allow_retired_models() -> bool:
    return os.environ.get(ALLOW_RETIRED_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def strip_code_fences(text: str) -> str:
    """Remove a markdown fence wrapping the whole answer, wherever it sits."""
    body = (text or "").strip()
    if not body.startswith("```"):
        return body
    body = body.split("\n", 1)[1] if "\n" in body else ""
    if body.rstrip().endswith("```"):
        body = body.rstrip()[:-3]
    return body.strip()


#: "## Scene 3", "### SCENE 3", "**Scene 3**", "Scene 3:" — the queue gate looks for
#: the literal `## Scene`, and a model that answers with an equivalent heading had
#: its whole script thrown away. This rewrites the heading, not the prose.
_SCENE_HEADING = re.compile(
    r"^[ \t]*(?:#{1,4}[ \t]*)?(?:\*\*[ \t]*)?scene[ \t]*(\d+)[ \t]*(?:\*\*)?[ \t]*"
    r"(?:[—–:\-.][ \t]*([^\n]*?))?[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def _scene_heading(match: "re.Match[str]") -> str:
    title = (match.group(2) or "").strip().strip("*").strip()
    return f"## Scene {match.group(1)}" + (f" — {title}" if title else "")


def normalise_scene_headings(text: str) -> str:
    """Rewrite an equivalent scene heading to the literal `## Scene N` the gate wants."""
    body = text or ""
    if "## Scene" in body:
        return body
    return _SCENE_HEADING.sub(_scene_heading, body)


def text_model_candidates(primary: str | None = None) -> list[str]:
    """Every model worth trying, in order, without duplicates.

    The primary is whatever this brain was configured with; `DEFAULT_TEXT_MODEL`
    follows; retired names come last so an older key on an older project can still
    work, but a retired model can never be the thing we *start* with.
    """
    requested = (primary or "").strip()
    if requested in RETIRED_TEXT_MODELS:
        requested = ""      # a retired model is never the thing we start with
    order = [requested, DEFAULT_TEXT_MODEL, *FALLBACK_TEXT_MODELS,
             *DEPRECATED_TEXT_MODELS]
    if allow_retired_models():
        order.extend(RETIRED_TEXT_MODELS)
    seen: list[str] = []
    for name in order:
        if name and name not in seen:
            seen.append(name)
    return seen


def live_model(primary: str | None = None) -> str:
    """The first model we would actually start with: never a retired one."""
    for name in text_model_candidates(primary):
        if name not in RETIRED_TEXT_MODELS:
            return name
    return DEFAULT_TEXT_MODEL


#: Bounded backoff for transient service failures (503 "high demand", 500, timeouts).
#: 6 November 08:45Z: the model was finally live and the authoring run still failed,
#: because three calls in a row came back 503 UNAVAILABLE and the loop skipped to the
#: next candidate model instead of letting the spike pass.
#:
#: Three rungs, not four. With five live models in the chain the old (5, 15, 30, 60)
#: ladder allowed **25 requests and 9m10s for ONE logical call** — measured on
#: 7 November: 125 % of a 20-request/day model, and a third of the 30-minute job
#: timeout, of which an empty-queue pass may need eight. See
#: docs/research/schedule-and-model-reliability.md §6.2.
_TRANSIENT_BACKOFF = (5, 15, 30)

#: Total backoff a *pass* may sleep, across every model and every logical call. The
#: budget is per pass rather than per model because the failure mode was cumulative:
#: each model looked frugal on its own and the pass still died of wall clock.
MAX_TRANSIENT_SLEEP_SECONDS = 120.0

#: ±20 % on every wait. Google's own troubleshooting guide asks for jitter so clients
#: that hit the same spike do not retry in lockstep; without it the three channel legs
#: of one matrix retry within the same second.
TRANSIENT_JITTER = 0.2

#: Models on the 20-request/day free tier. A five-attempt storm on one of these spends
#: a quarter of its whole day on a single logical call, which is how gemini-3.8-flash
#: came to be named 29 times in this repo's failure annotations. One retry is enough.
TWENTY_A_DAY_MODELS = ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.7-flash")


#: Attempts per logical call on a 500-request/day model: one plus two waits, 20 s of
#: backoff. Three is enough to ride out a demand spike; four was enough to starve the
#: rest of the chain of the pass budget (measured: the first two lite models ate the
#: whole 90 s and the remaining three got one attempt each).
LITE_MODEL_ATTEMPTS = 3


def model_attempt_limit(model: str) -> int:
    """How many requests one logical call may spend on `model`."""
    return 2 if model in TWENTY_A_DAY_MODELS else LITE_MODEL_ATTEMPTS


def is_transient(exc: BaseException) -> bool:
    """Is this the service being busy rather than the request being wrong?

    A 503 says "ask again"; a 404 (retired model) or a 429 (quota) says "stop".
    Treating all three alike is what turned a two-minute demand spike into a lost
    authoring slot.
    """
    text = str(exc).lower()
    markers = ("503", "unavailable", "high demand", "500", "internal", "deadline",
               "timeout", "timed out", "connection reset", "remoteprotocolerror")
    return any(marker in text for marker in markers)


def is_model_retired(exc: BaseException) -> bool:
    """Did the service say this model no longer exists for us?"""
    text = str(exc).lower()
    return ("404" in text or "not_found" in text) and "no longer available" in text


def report_retired_model(model: str, exc: BaseException) -> None:
    """Say it once, where a human sees it — a retired model is not a soft failure."""
    print(f"::error title=Gemini text model retired::{model} is gone ({exc}). "
          f"Authoring needs a live model: set GEMINI_TEXT_MODEL or update "
          f"DEFAULT_TEXT_MODEL in pipeline/gemini_brain.py. Nothing can be authored "
          f"until this is fixed.")


class BrainAuthoringError(RuntimeError):
    """Raised when the brain cannot faithfully author the requested scripture."""


class GeminiBrain:
    """Master Autonomous Creative & Editorial Director powered by Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_TEXT_MODEL,
                 channel_id: Optional[str] = None) -> None:
        # Channel-scoped brain: a prayer2 brain compiles Morning Altar
        # equipment, reads the PRAYER2_ Gemini quota pool first, selects
        # from the morning roadmap and never stages Secret Place Shorts.
        # Empty/None keeps the historic Secret Place behaviour exactly.
        self.channel_id = normalize_channel_id(
            channel_id or os.environ.get("CHANNEL_ID") or CONFIG.channel_id)
        self.channel = get_channel(self.channel_id)
        self.api_key = api_key or get_gemini_api_key(self.channel_id)
        self.model = model
        self.system_prompt = compile_full_brain_prompt(self.channel_id)
        self._client = None
        # Why the client is missing matters: "the key is not set" and "the key is
        # set but the SDK could not start" need different fixes, and conflating
        # them sent this project chasing a secret that had been configured for
        # weeks — the same key narrates every video.
        self._client_error: Optional[str] = None
        #: Requests issued by this pass. Bounded so a bad morning cannot spend the
        #: whole free-tier day before the first script is authored.
        self.calls_made = 0
        #: Why the last `_call_model` came back empty ("retired", "quota", "busy",
        #: "no response"), so the run can report the real cause per model instead of
        #: blaming the script format for a service failure.
        self.last_reason = ""
        #: Set when Google says the daily allowance is gone. No candidate model can
        #: answer after that, so the chain stops instead of burning six more calls.
        self.quota_stop = ""
        #: Attempts this pass made, one row per model: what it did and why.
        self.authoring_outcomes: list[dict[str, str]] = []
        #: Seconds this pass has slept inside backoff, against
        #: `MAX_TRANSIENT_SLEEP_SECONDS`. Injectable sleep so tests do not wait.
        self.transient_slept = 0.0
        self._sleep = time.sleep
        if self.api_key:
            try:
                from google import genai
                from .gemini_client import make_client
                # Bounded per request: an unbounded client is how a stalled
                # socket becomes a 90-minute step timeout with no error.
                #
                # `attempts=1` hands retry authority to `_call_model`, which knows
                # which model it is talking to and how much of that model's day is
                # left. With the SDK retrying too, one logical call could issue ten
                # requests — SDK 2 × our 5 — against a free tier of 20 a day.
                self._client = make_client(self.api_key, attempts=1)
            except Exception as exc:  # noqa: BLE001
                self._client_error = f"{type(exc).__name__}: {exc}"
                print(f"[gemini-brain] Could not initialize genai.Client: {exc}")

    def is_api_available(self) -> bool:
        return self._client is not None

    def api_status(self) -> dict[str, Any]:
        """Exactly why the API is or is not usable here."""
        key_present = bool(self.api_key)
        if not key_present:
            names = ", ".join(gemini_key_names(self.channel_id))
            reason = (f"GEMINI_API_KEY is not present in this environment "
                      f"(no {names}, no .env) for channel {self.channel_id}")
        elif self._client is None:
            reason = f"key is present but the genai client failed to start: {self._client_error}"
        else:
            reason = "connected"
        return {
            "key_present": key_present,
            "client_ready": self._client is not None,
            "model": self.model,
            "reason": reason,
            "channel": self.channel_id,
            "channel_id": self.channel_id,
            "key_names": gemini_key_names(self.channel_id),
        }

    def audit_status(self) -> ScheduleAudit:
        return build_schedule_audit()

    def _existing_job_ids(self) -> set[str]:
        """Job ids already used by this repository's queue and published receipts.

        Roadmap ids are global, so this is deliberately repository-wide: a Morning
        Altar id can never collide with a Secret Place one.
        """
        ids = {path.name[:4] for path in QUEUE_DIR.glob("*.md")}
        ids |= {path.name[:4] for path in PUBLISHED_DIR.glob("*.md")}
        return ids

    def select_next_scripture(self) -> dict[str, Any]:
        """Find the top-priority scripture from the continuous research roadmap not yet in queue or published.

        Closed-loop steering: when the performance-feedback artifact has enough
        measured data, eligible roadmap candidates are reordered to favour the
        themes that are actually winning on the channel. With too little data the
        roadmap order is preserved, so the brain never steers on noise.
        """
        existing_ids = self._existing_job_ids()

        roadmap = roadmap_for_channel(self.channel_id)
        eligible = [c for c in roadmap if c["id"] not in existing_ids]
        if eligible:
            # Steering is data-gated, never channel-gated: every channel is
            # eligible, and with too little measured data rank_candidates()
            # returns the roadmap order unchanged.
            try:
                from .performance_feedback import load_feedback_report, rank_candidates
                eligible = rank_candidates(
                    eligible, load_feedback_report(channel_id=self.channel_id)
                )
            except Exception as exc:  # noqa: BLE001
                # Feedback is an optimisation, never a gate: a missing or malformed
                # artifact must not stop the queue from being replenished.
                print(f"[gemini-brain] performance feedback skipped: {exc}")
            return eligible[0]

        caps = capabilities_for(self.channel_id)
        # Both channels refuse identically. The old Secret Place fallback emitted
        # "Psalm 121" with a fresh id every time the roadmap ran dry — the same
        # class of defect as job 0011 (one psalm's verses under another psalm's
        # title), just with a duplicate title as well.
        raise BrainAuthoringError(
            f"{caps.brand.display_name} roadmap is exhausted: every candidate in "
            f"{caps.roadmap_name} is already queued or published. Extend "
            f"{caps.roadmap_name} rather than reusing a scripture this channel has "
            f"already made, and never borrow the other channel's."
        )

    def author_longform_script(self, scripture_data: dict[str, Any]) -> str:
        """Call Google Gemini to draft the full markdown script, or use equipped template if offline."""
        job_id = scripture_data.get("id", "0010")
        scripture = scripture_data.get("scripture", "Psalm 121")
        theme = scripture_data.get("theme", "Divine Keeper Before Sleep")
        hook = scripture_data.get("hook", "THE LORD IS YOUR KEEPER")

        author_words = max(950, MIN_LONGFORM_WORDS + 100)
        brand = brand_for(self.channel_id)
        channel_directive = "\n".join(brand.authoring_directive)
        channel_directive = f"\n{channel_directive}\n"
        user_prompt = f"""
Please author the official, complete long-form devotional script for:
- Job ID: {job_id}
- Scripture: {scripture}
- Central Theme: {theme}
- Visual Hook Text: "{hook}"
{channel_directive}
Follow all channel invariants, DOCOGA REELS v2 guidelines, and theological rubrics.

LENGTH IS A HARD REQUIREMENT: at least {author_words} words of narration across the scenes.
The production gate is {MIN_LONGFORM_WORDS} words and it is never lowered — a shorter script
publishes nothing at all, it does not publish a short video. The gate is not
arbitrary: Charon narrates about {CHARON_WORDS_PER_MINUTE} words a minute and the renderer
refuses anything under {MIN_NARRATION_SECONDS} seconds, so {MIN_LONGFORM_WORDS} words is the first
length that can actually be published. Do not pad with repeated
sentences; write more prayer, more scripture exposition, more stillness.

Output the full, raw Markdown file with frontmatter and all 6 scenes. Do not include markdown code block backticks.
"""
        if self.is_api_available():
            outcomes: list[dict[str, str]] = []
            self.authoring_outcomes = outcomes
            # Two envelope repairs per authoring run: enough to rescue a good body,
            # never enough to spend the day on models that cannot write front matter.
            repairs_left = 2
            try:
                for candidate_model in text_model_candidates(self.model):
                    raw = self._call_model(candidate_model, user_prompt) or ""
                    text = normalise_scene_headings(strip_code_fences(raw))
                    if not text:
                        outcomes.append({"model": candidate_model,
                                         "outcome": self.last_reason or "no response"})
                        if self.quota_stop:
                            break
                        continue
                    if "## Scene" not in text:
                        print(f"[gemini-brain] {candidate_model} returned no scenes — "
                              f"trying the next model.")
                        outcomes.append({"model": candidate_model,
                                         "outcome": "no `## Scene` heading"})
                        continue
                    missing = missing_job_keys(text)
                    if missing and not repairs_left:
                        outcomes.append({"model": candidate_model,
                                         "outcome": f"missing {', '.join(missing)} "
                                                    f"(repair budget spent)"})
                        continue
                    if missing:
                        repairs_left -= 1
                        # The body is usable; only the envelope is missing. One
                        # targeted request for the front matter costs a single call,
                        # while climbing to the next model costs a whole script and
                        # buys nothing if the model never writes front matter unprompted:
                        # on 7 November every candidate produced a body-or-nothing and
                        # the queue stayed empty. Ask this model for the envelope only.
                        print(f"[gemini-brain] {candidate_model} returned a body without "
                              f"queue front matter ({', '.join(missing)}) — asking it for "
                              f"the envelope only.")
                        text = self._repair_envelope(candidate_model, text, scripture_data,
                                                     missing)
                        missing = missing_job_keys(text)
                    if missing:
                        print(f"[gemini-brain] {candidate_model} still missing "
                              f"{', '.join(missing)} — trying the next model.")
                        outcomes.append({"model": candidate_model,
                                         "outcome": f"missing {', '.join(missing)}"})
                        continue
                    try:
                        # Brand safety runs on the whole file, so it must run *after*
                        # the envelope exists: a body-only answer was being rejected as
                        # "does not declare channel:" before it could be repaired, and
                        # that single ordering mistake discarded every usable script.
                        self._enforce_channel_metadata(text, scripture_data)
                    except BrainAuthoringError as branding:
                        print(f"[gemini-brain] {candidate_model} rejected: {branding}")
                        outcomes.append({"model": candidate_model,
                                         "outcome": f"branding: {branding}"[:200]})
                        continue
                    outcomes.append({"model": candidate_model, "outcome": "accepted"})
                    return text
            except BrainAuthoringError:
                raise
            except Exception as api_err:
                print(f"[gemini-brain] Gemini API generation failed ({api_err}).")
            raise BrainAuthoringError(self._authoring_failure(brand, outcomes))

        # Authoring is model-only for every channel, with identical wording.
        # The old "equipped template" was fixed Psalm 121 night text and was
        # emitted for whatever scripture had been selected — that is how job 0011
        # acquired Psalm 121 verses under a Psalm 27 title. It was also under the
        # 850-word floor, so a template-authored script could never publish: it
        # only ever produced a mislabelled or unpublishable file. Idling is the
        # honest outcome, and it is the same outcome on both channels.
        names = "/".join(gemini_key_names(self.channel_id))
        raise BrainAuthoringError(
            f"{brand.display_name}: cannot author {scripture!r} offline — authoring is "
            f"model-only on every channel and {names} is unavailable or "
            f"quota-exhausted. Refusing to emit mislabelled or unpublishable scripture "
            f"($0 lock: idle, never spend)."
        )

    def _repair_envelope(self, model: str, body: str, scripture_data: dict[str, Any],
                         missing: list[str]) -> str:
        """Ask the model for the front matter only, then splice it onto its own body.

        This is a formatting repair, never an invention: the model wrote the script
        and the attestation block, and it is asked for exactly the keys the queue
        requires. Nothing is fabricated on its behalf — a script whose
        `originality` checklist we invented would be a false attestation, so the
        keys come from the model or the script is rejected.
        """
        prompt = (
            "Your previous answer was the body of the script but it did not start with "
            "the YAML front matter content/queue requires.\n"
            f"Return ONLY a YAML front matter block, beginning and ending with a line of "
            f"three dashes, containing at least these keys: {', '.join(missing)}.\n"
            "Keys already known (use them verbatim):\n"
            + "\n".join(f"- {k}: {v}" for k, v in scripture_data.items()
                         if k in {"id", "scripture", "theme", "hook"})
            # The channel is the one key the model must never infer. It is this
            # run's identity, and a script that guesses it is published on another
            # channel — the defect that emptied the Midday Watch's queue.
            + f"\n- channel: {self.channel_id}"
            + "\nScripture: the body you wrote. Output no prose and no code fences."
        )
        envelope = strip_code_fences(self._call_model(model, prompt) or "")
        if not envelope:
            return body
        if not envelope.startswith("---"):
            envelope = "---\n" + envelope
        if not envelope.rstrip().endswith("---"):
            envelope = envelope.rstrip() + "\n---"
        combined = envelope.rstrip() + "\n\n" + body.lstrip()
        if body.lstrip().startswith("---"):
            return normalize_authored_script_markdown(combined, channel_id=self.channel_id)
        return combined

    def _authoring_failure(self, brand: Any, outcomes: list[dict[str, str]]) -> str:
        """One sentence that names the actual cause, per model.

        The old message said every candidate "returned a script without the front
        matter" — on 7 November five of seven candidates never returned a script at
        all (three 503s, two 404s, one empty). That wording sent the diagnosis at
        the parser while the service was the problem.
        """
        seen = "; ".join(f"{row['model']}: {row['outcome']}" for row in outcomes) or "no model answered"
        tail = ""
        if self.quota_stop:
            tail = (f" The project's daily free-tier text allowance is spent; it resets "
                    f"at {self.quota_stop}.")
        elif self.transient_slept >= MAX_TRANSIENT_SLEEP_SECONDS * 0.9:
            tail = (f" The pass spent its whole {MAX_TRANSIENT_SLEEP_SECONDS:.0f}s backoff "
                    f"budget on 503s ({self.transient_slept:.0f}s); a later slot has a "
                    f"different capacity moment.")
        return (f"{brand.display_name}: no candidate model could author this scripture — "
                f"{seen}.{tail} Nothing was written: a job that cannot satisfy the queue "
                f"gate must never enter content/queue/.")

    def _call_model(self, model: str, prompt: str) -> str:
        """One model call with bounded backoff for a busy service.

        Returns the raw text, or "" when this model cannot answer (retired, out of
        quota, or still busy after the retries) so the caller can try the next
        candidate. `BrainAuthoringError` is a verdict about the *text*, not a
        transport failure, and is always re-raised.
        """
        attempts_allowed = model_attempt_limit(model)
        for attempt in range(attempts_allowed):
            if self.calls_made >= MAX_CALLS_PER_RUN:
                raise BrainAuthoringError(
                    f"this pass has already made {self.calls_made} Gemini requests "
                    f"(GEMINI_MAX_CALLS_PER_RUN={MAX_CALLS_PER_RUN}); stopping rather "
                    f"than spending the rest of the day's free-tier allowance")
            self.calls_made += 1
            try:
                resp = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={"system_instruction": self.system_prompt},
                )
                text = (getattr(resp, "text", "") or "").strip()
                self.last_reason = "" if text else "returned nothing"
                return text
            except BrainAuthoringError:
                raise
            except Exception as exc:  # noqa: BLE001
                err = str(exc).lower()
                if is_model_retired(exc):
                    report_retired_model(model, exc)
                    self.last_reason = f"retired (404): {exc}"[:180]
                    return ""
                if "429" in err or "resource_exhausted" in err or "quota" in err:
                    from pipeline.quota_handler import calculate_next_quota_reset_utc

                    reset_dt = calculate_next_quota_reset_utc()
                    print("[gemini-brain] Google Gemini daily free tier quota reached "
                          f"($0.00 lock active). Reset at {reset_dt.isoformat()} UTC.")
                    # Every model shares the project's daily allowance, so there is
                    # nothing left to try today — say it once and stop.
                    self.last_reason = "quota exhausted"
                    self.quota_stop = reset_dt.isoformat()
                    return ""
                if is_transient(exc) and attempt + 1 < attempts_allowed:
                    wait = self._budgeted_wait(model, attempt, attempts_allowed)
                    if wait is None:
                        self.last_reason = ("busy after retries: pass backoff budget "
                                            f"({MAX_TRANSIENT_SLEEP_SECONDS:.0f}s) spent")
                        print(f"[gemini-brain] {model}: service busy, but this pass has "
                              f"spent its {MAX_TRANSIENT_SLEEP_SECONDS:.0f}s of backoff "
                              f"— trying the next model.", flush=True)
                        return ""
                    print(f"[gemini-brain] {model}: service busy ({type(exc).__name__}). "
                          f"Waiting {wait:.0f}s (attempt {attempt + 2}/"
                          f"{attempts_allowed})...", flush=True)
                    self._sleep(wait)
                    self.transient_slept += wait
                    continue
                print(f"[gemini-brain] Model {model} call failed: {exc}")
                reason = ("busy after retries" if is_transient(exc) else "failed")
                self.last_reason = f"{reason}: {exc}"[:180]
                return ""
        print(f"[gemini-brain] Model {model} still busy after "
              f"{attempts_allowed} attempt(s); trying the next candidate.")
        self.last_reason = f"busy after retries: {attempts_allowed} attempt(s) on {model}"
        return ""

    def _budgeted_wait(self, model: str, attempt: int, attempts_allowed: int) -> float | None:
        """The jittered wait this pass can still afford, or None if the budget is spent.

        None rather than 0: "no time left to be patient" is a different answer from
        "wait zero seconds", and the caller must stop climbing this model.
        """
        import random as _random

        if not _TRANSIENT_BACKOFF:      # a test may empty the ladder to run instantly
            return 0.0
        base = _TRANSIENT_BACKOFF[min(attempt, len(_TRANSIENT_BACKOFF) - 1)]
        jittered = base * (1.0 + _random.uniform(-TRANSIENT_JITTER, TRANSIENT_JITTER))
        remaining = MAX_TRANSIENT_SLEEP_SECONDS - self.transient_slept
        if remaining < base * 0.5:
            return None
        return round(min(jittered, remaining), 1)

    def _enforce_channel_metadata(self, text: str, scripture_data: dict[str, Any] | None = None) -> None:
        """Refuse model output that is branded for the wrong channel.

        A Morning Altar script carrying Secret Place sleep branding (or a
        Secret Place script carrying Morning Altar metadata) is the same class of
        defect as Psalm 121 text under a Psalm 27 title: it must never reach the
        queue. This runs before any file is written, and it is the *same* rule on
        both channels — the phrases come from the channel's capability block, so
        neither channel is checked harder than the other.
        """
        head = text[:4000]
        channel_match = re.search(r"^channel:\s*([^\n#]+)", head, re.M)
        declared = normalize_channel_id(channel_match.group(1)) if channel_match else ""
        brand = brand_for(self.channel_id)

        problems: list[str] = []
        if channel_match is None:
            problems.append(f"frontmatter does not declare `channel: {brand.declaration}`")
        elif declared != self.channel_id:
            problems.append(
                f"frontmatter declares `channel: {declared}`, expected `{brand.declaration}`")
        if not any(phrase in text for phrase in brand.required_phrases):
            problems.append(f"does not name {brand.display_name}")
        lowered = text.lower()
        for term in brand.forbidden_phrases:
            if term.lower() in lowered:
                problems.append(f"carries another channel's branding: {term!r}")
                break
        if problems:
            raise BrainAuthoringError(
                f"{brand.display_name} authoring rejected: " + "; ".join(problems))

    def author_short_spec(self, longform_doc: ScriptDoc | None, key: str | None = None,
                          *, scripture: str | None = None) -> "ShortSpec":
        """Ask the model to write a complete 9:16 Short spec, then validate it.

        This is the step that was missing: `tools/shorts.py` could only render Shorts
        whose scene data was hand-written into a Python literal, so the brain could
        queue a Short but never produce one. A spec is data — scenes, queries,
        captions, kinetic phrases, beats — so the model can write it and the
        renderer can build it.

        A Short needs a passage, not a long-form: the prompt is built from the
        reference alone. Pass `scripture` (and no document) for a Short that
        stands on its own.

        Raises BrainAuthoringError rather than returning something partial: a Short
        that renders with mislabelled scripture is worse than a stalled queue.
        """
        from .short_script import (ShortSpecError, build_prompt, parse_model_json,
                                   require_valid, validate_spec)

        if scripture is None:
            if longform_doc is None:
                raise BrainAuthoringError("a Short needs a long-form script or a scripture reference")
            scripture = extract_scripture_reference(longform_doc)
        scripture = str(scripture).replace("–", "-").strip()
        if not self.is_api_available():
            raise BrainAuthoringError(
                f"cannot author {scripture} Short: {self.api_status()['reason']}. "
                "Refusing to fabricate a scene list."
            )
        key = key or (short_key_for_doc(longform_doc) if longform_doc is not None
                      else short_key_for_reference(self.channel_id, scripture))
        prompt = build_prompt(scripture, key=key, channel_id=self.channel_id)
        last_error = ""
        # Two attempts per model, then *change the model*: a spec that comes back
        # under the word floor or with five scenes instead of six is a capability
        # defect, not a transport one, and re-asking the same model a third time
        # spends another request on the same answer. On 6 November the lite model
        # returned 43 words where 90-165 is enforced; the run gave up instead of
        # asking a stronger model in the same chain.
        for model in text_model_candidates(self.model):
            if model in RETIRED_TEXT_MODELS:
                continue
            model_exhausted = False
            for attempt in (1, 2):
                contents = prompt if attempt == 1 else (
                    f"{prompt}\n\nPrevious output was rejected: {last_error}\n"
                    "Fix exactly that and return only JSON.")
                resp = None
                for rung in range(1 + len(_TRANSIENT_BACKOFF)):
                    if rung:
                        # Same 503 spike that killed a long-form run at 08:45Z
                        # would also kill the Short: wait, do not re-prompt. The wait
                        # is drawn from the same pass-level budget as long-form
                        # authoring, so a busy night cannot spend it twice over.
                        wait = self._budgeted_wait(model, rung - 1, 1 + len(_TRANSIENT_BACKOFF))
                        if wait is None:
                            last_error = ("pass backoff budget spent before this model "
                                          "could answer")
                            break
                        print(f"[gemini-brain] Short {key}: service busy, waiting "
                              f"{wait:.0f}s...", flush=True)
                        self._sleep(wait)
                        self.transient_slept += wait
                    try:
                        self.calls_made += 1
                        if self.calls_made > MAX_CALLS_PER_RUN:
                            raise BrainAuthoringError(
                                f"this pass has already made {self.calls_made} Gemini "
                                f"requests (GEMINI_MAX_CALLS_PER_RUN={MAX_CALLS_PER_RUN})")
                        resp = self._client.models.generate_content(
                            model=model, contents=contents)
                        break
                    except BrainAuthoringError:
                        raise
                    except Exception as exc:  # noqa: BLE001
                        err_lower = str(exc).lower()
                        if is_model_retired(exc):
                            report_retired_model(model, exc)
                            resp = None
                            model_exhausted = True
                            break
                        if "429" in err_lower or "resource_exhausted" in err_lower or "quota" in err_lower:
                            # Free-tier daily quotas are enforced per model
                            # (GenerateRequestsPerDayPerProjectPerModel-FreeTier),
                            # e.g. 20/day on 3.6-flash vs 500/day on 3.5-flash-lite.
                            # Skip remaining attempts on this model and try the next
                            # candidate in the chain instead of aborting the whole pass.
                            last_error = f"{model}: quota exhausted ({exc})"
                            resp = None
                            model_exhausted = True
                            break
                        if not is_transient(exc):
                            raise
                if model_exhausted:
                    break
                if resp is None:
                    last_error = last_error or f"{model}: no answer"
                    continue
                try:
                    data = parse_model_json(getattr(resp, "text", "") or "")
                    data.setdefault("scripture", scripture)
                    data.setdefault("channel", self.channel_id)
                    # The spec is written for *this* channel: a spec that comes back
                    # declaring another one is rejected by validation, not relabelled.
                    spec = validate_spec(data, key=key, channel_id=self.channel_id)
                    if spec.problems:
                        last_error = "; ".join(spec.problems[:4])
                        continue
                    if spec.repairs:
                        print(f"[gemini-brain] Short {key}: repaired "
                              f"{'; '.join(spec.repairs)}")
                    return require_valid(spec)
                except ShortSpecError as exc:
                    last_error = str(exc)
                except Exception as exc:  # noqa: BLE001
                    last_error = f"{type(exc).__name__}: {exc}"
            print(f"[gemini-brain] Short {key}: {model} could not produce a valid spec "
                  f"({last_error[:120]}); trying the next model", flush=True)
        raise BrainAuthoringError(
            f"{scripture} Short spec rejected on every candidate model: {last_error}")

    def generate_companion_short(
        self,
        longform_doc: ScriptDoc,
        *,
        require_renderable: bool = False,
    ) -> tuple[Optional[Path], str]:
        """Queue a companion 9:16 Short for this long-form video.

        Two defects this replaces:

        * the key was hardcoded to ``short-psalm91`` for every job, so any new
          long-form video queued another Psalm 91 Short, one psalm's scripture
          attached to another psalm's title. Same failure as job 0011.
        * the manifest was written ``status: approved`` even when no renderer
          script existed for the key, so production skipped it silently forever.

        Now the brain *authors* the Short as a validated spec, which the renderer
        picks up from ``content/shorts-scripts/``. If authoring fails, direct
        callers keep a draft manifest explaining why, while autonomous staging
        callers (`require_renderable=True`) defer writing the manifest so
        ``content/shorts-queue/`` never accumulates unrenderable ``needs_renderer``
        files that break queue integrity gates; ``replenish_shorts_queue()`` will
        retry cleanly on the next pass.
        """
        if longform_doc.channel != self.channel_id:
            # Cross-channel protection, identical in both directions: a brain
            # authors Shorts for its own channel and never dresses the other's.
            raise BrainAuthoringError(
                f"{self.channel.display_name} brain cannot stage a Short for a "
                f"{longform_doc.channel!r} script")
        from .short_release import _renderer_script_keys
        from .short_script import save_spec

        SHORTS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        key = short_key_for_doc(longform_doc)
        scripture_ref = extract_scripture_reference(longform_doc)
        manifest_filename = f"{longform_doc.id}-{key}.yml"
        manifest_path = SHORTS_QUEUE_DIR / manifest_filename
        # The passage may already have a Short that stands on its own (the key
        # is derived the same way). A second manifest for the same key would
        # sit in the queue counted as ready and never publish.
        standalone = SHORTS_QUEUE_DIR / f"{STANDALONE_PREFIX}-{key}.yml"
        if standalone.is_file():
            print(f"[gemini-brain] {key} already has a standalone Short queued "
                  f"({standalone.name}); no companion manifest for {longform_doc.id}",
                  flush=True)
            return None, key

        authored, authoring_note = False, ""
        if key not in _renderer_script_keys():
            try:
                spec = self.author_short_spec(longform_doc, key=key)
                save_spec(spec)
                authored = True
                authoring_note = f"spec authored by the brain ({spec.words} narration words)"
            except Exception as exc:  # noqa: BLE001
                authoring_note = f"authoring failed: {exc}"

        renderable = key in _renderer_script_keys()
        if require_renderable and not renderable:
            print(
                f"[gemini-brain] Deferring companion Short manifest {manifest_filename} "
                f"until spec is renderable ({authoring_note[:160]})",
                flush=True,
            )
            return None, key

        manifest_data = {
            "short": key,
            # Every manifest names its channel. Without this the shared queue
            # could only ever serve one channel, which is how Shorts became
            # Secret-Place-only in the first place.
            "channel": longform_doc.channel,
            "companion_longform_id": longform_doc.id,
            "scripture": scripture_ref,
            # Approved only when something can actually build it.
            "status": "approved" if renderable else "draft",
            "renderer_ready": renderable,
            "authored_by_brain": authored,
            "privacy": "public",
            "replace": False,
            "target_window_utc": brand_for(self.channel_id).short_target_window_utc,
            "notes": (
                f"Companion Short for {longform_doc.title} — {authoring_note}"
                if authoring_note
                else f"Companion Short for {longform_doc.title}"
            ),
        }

        manifest_path.write_text(yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8")
        return manifest_path, key

    def generate_standalone_short(self, scripture: str, source: str = "evergreen",
                                  ) -> tuple[Optional[Path], str]:
        """Author and queue a Short that has no long-form behind it.

        Returns ``(manifest_path, key)``; the path is ``None`` when the spec could
        not be authored, and then nothing is written: a manifest with no spec is
        a queue entry that can never render. The manifest is named ``0000-<key>``
        so the selector, which takes a channel's manifests in name order, sends
        these out ahead of the companion Shorts already waiting.
        """
        from .short_release import _renderer_script_keys
        from .short_script import save_spec

        reference = str(scripture).replace("–", "-").strip()
        key = short_key_for_reference(self.channel_id, reference)
        note = ""
        if key not in _renderer_script_keys():
            try:
                spec = self.author_short_spec(None, key=key, scripture=reference)
                save_spec(spec)
                note = f"spec authored by the brain ({spec.words} narration words)"
            except Exception as exc:  # noqa: BLE001
                print(f"[gemini-brain] Standalone Short {key} ({reference}) not authored: "
                      f"{str(exc)[:160]}", flush=True)
                return None, key
        SHORTS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        manifest_path = SHORTS_QUEUE_DIR / f"{STANDALONE_PREFIX}-{key}.yml"
        manifest_data = {
            "short": key,
            "channel": self.channel_id,
            # No companion_longform_id: this Short is not the cut-down of a
            # long-form, and `standalone` says so to anything that reads the queue.
            "standalone": True,
            "source": source,
            "scripture": reference,
            "status": "approved",
            "renderer_ready": True,
            "authored_by_brain": True,
            "privacy": "public",
            "replace": False,
            "target_window_utc": brand_for(self.channel_id).short_target_window_utc,
            "notes": (f"Standalone Short on {reference} ({source} list)"
                      + (f" — {note}" if note else "")),
        }
        manifest_path.write_text(yaml.safe_dump(manifest_data, sort_keys=False), encoding="utf-8")
        return manifest_path, key

    def _companion_doc(self, longform_id: str) -> Optional[ScriptDoc]:
        """Find the long-form script a queued Short is a companion to."""
        if not longform_id:
            return None
        for directory in (QUEUE_DIR, PUBLISHED_DIR):
            for path in sorted(Path(directory).glob(f"{longform_id}-*.md")):
                try:
                    return parse_script(path)
                except Exception:  # noqa: BLE001 — an unreadable sibling is not fatal
                    continue
        return None

    def author_missing_shorts(self) -> list[dict[str, Any]]:
        """Author specs for this channel's blocked Shorts manifests."""
        from .short_release import _renderer_script_keys
        from .short_script import save_spec

        rows: list[dict[str, Any]] = []
        renderable = _renderer_script_keys()

        for path in sorted(Path(SHORTS_QUEUE_DIR).glob("*.yml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception as exc:  # noqa: BLE001
                rows.append({"file": path.name, "key": "", "verdict": "unreadable", "reason": str(exc)})
                continue
            if normalize_channel_id(data.get("channel")) != self.channel_id:
                continue  # another channel's Short is another channel's quota
            cid = str(data.get("companion_longform_id", "")).strip()
            key = str(data.get("short", "")).strip()
            if not key:
                rows.append({"file": path.name, "key": "", "verdict": "no_key", "reason": "manifest has no `short`"})
                continue
            if key in renderable:
                rows.append({"file": path.name, "key": key, "verdict": "renderable", "reason": "already has a spec"})
                continue

            doc = self._companion_doc(cid)
            if doc is None and data.get("standalone") and str(data.get("scripture") or "").strip():
                # A standalone Short's source is its reference, not a long-form.
                reference = str(data["scripture"]).strip()
                try:
                    spec = self.author_short_spec(None, key=key, scripture=reference)
                    save_spec(spec)
                except Exception as exc:  # noqa: BLE001
                    reason = f"authoring failed: {exc}"
                    data.update(status="draft", renderer_ready=False, authored_by_brain=False,
                                notes=f"Standalone Short on {reference} — {reason}")
                    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                    rows.append({"file": path.name, "key": key, "verdict": "failed", "reason": reason})
                    continue
                renderable.add(key)
                data.update(status="approved", renderer_ready=True, authored_by_brain=True,
                            notes=(f"Standalone Short on {reference} — spec authored by the "
                                   f"brain ({spec.words} narration words)"))
                path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                rows.append({"file": path.name, "key": key, "verdict": "authored",
                             "reason": f"{spec.words} narration words"})
                continue
            if doc is None:
                reason = f"no long-form script for companion id {cid!r}; cannot author {key}"
                data.update(status="draft", renderer_ready=False, authored_by_brain=False,
                            notes=f"authoring blocked: {reason}")
                path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                rows.append({"file": path.name, "key": key, "verdict": "no_source", "reason": reason})
                continue

            try:
                spec = self.author_short_spec(doc, key=key)
                save_spec(spec)
            except Exception as exc:  # noqa: BLE001
                reason = f"authoring failed: {exc}"
                data.update(status="draft", renderer_ready=False, authored_by_brain=False,
                            notes=f"Companion Short for {doc.title} — {reason}")
                path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                rows.append({"file": path.name, "key": key, "verdict": "failed", "reason": reason})
                continue

            renderable.add(key)
            data.update(
                status="approved",
                renderer_ready=True,
                authored_by_brain=True,
                notes=(f"Companion Short for {doc.title} — spec authored by the brain "
                       f"({spec.words} narration words)"),
            )
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            rows.append({"file": path.name, "key": key, "verdict": "authored",
                         "reason": f"{spec.words} narration words"})
        return rows

    def _standalone_pass(self, source: str, state: dict[str, Any],
                         rows: list[dict[str, Any]], min_ready: int) -> None:
        """Author standalone Shorts from one list until the queue has `min_ready`.

        `state` carries the counts the whole replenishment shares: ``ready``,
        ``budget`` (standalone Shorts this pass may still author), and the
        ``covered`` / ``renderable`` key sets. Two failures in a row end the pass:
        a model that is down answers the third request the way it answered the
        first two, and the requests are better kept for the long-form.
        """
        from .evergreen_shorts import LOW_POOL, candidates

        if state["ready"] >= min_ready or state["budget"] <= 0:
            return
        pool = candidates(self.channel_id, taken_longform_ids=self._existing_job_ids())
        mine = [ref for ref, src in pool if src == source]
        failures = 0
        for reference in mine:
            if state["ready"] >= min_ready or state["budget"] <= 0 or failures >= 2:
                break
            key = short_key_for_reference(self.channel_id, reference)
            if key in state["covered"]:
                continue
            if key not in state["renderable"] and not self.is_api_available():
                break
            state["budget"] -= 1
            mpath, mkey = self.generate_standalone_short(reference, source=source)
            if mpath is None:
                failures += 1
                rows.append({"file": f"{STANDALONE_PREFIX}-{mkey}.yml", "key": mkey,
                             "verdict": "failed",
                             "reason": f"standalone Short on {reference} could not be authored"})
                continue
            failures = 0
            state["ready"] += 1
            state["renderable"].add(mkey)
            state["covered"].add(mkey)
            rows.append({"file": mpath.name, "key": mkey, "verdict": "authored",
                         "reason": f"standalone Short on {reference} ({source} list)"})
        left = len(candidates(self.channel_id, taken_longform_ids=self._existing_job_ids()))
        if left < LOW_POOL and not state.get("warned"):
            state["warned"] = True
            print(f"::warning title=Short passages running low ({self.channel_id})::"
                  f"{left} passage(s) left for standalone Shorts on "
                  f"{self.channel.display_name}. Add passages to EVERGREEN in "
                  f"pipeline/evergreen_shorts.py or extend the channel's roadmap.", flush=True)

    def replenish_shorts_queue(self, min_ready: int = 6) -> list[dict[str, Any]]:
        """Top this channel's ready Shorts up to `min_ready`.

        In order: standalone Shorts on the channel's evergreen passages, then
        companions of its queued and published long-forms, then standalone Shorts
        on roadmap passages that have no long-form yet
        (`pipeline/evergreen_shorts.py`). A channel publishes five Shorts a day and
        one long-form, so companions alone can no longer keep the queue fed.
        """
        from .short_release import EDITIONS, _renderer_script_keys, resolve_edition

        rows: list[dict[str, Any]] = []
        renderable = _renderer_script_keys()
        ready_count = 0
        covered_ids: set[str] = set()
        covered_keys: set[str] = set()

        for pub_path in sorted(Path(PUBLISHED_DIR).glob("short-*.md")):
            try:
                pub_txt = pub_path.read_text(encoding="utf-8")
                m_slug = re.search(r"^slug:\s*(\S+)", pub_txt, re.M)
                if m_slug:
                    covered_keys.add(m_slug.group(1).strip())
            except Exception:  # noqa: BLE001
                continue
        for k_ed, ed in EDITIONS.items():
            if (Path(PUBLISHED_DIR) / f"{ed.slug}.md").is_file():
                covered_keys.add(k_ed)

        for path in sorted(Path(SHORTS_QUEUE_DIR).glob("*.yml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001
                continue
            if normalize_channel_id(data.get("channel")) != self.channel_id:
                continue
            cid = str(data.get("companion_longform_id", "")).strip()
            if cid:
                covered_ids.add(cid)
            key = str(data.get("short", "")).strip()
            if key:
                covered_keys.add(key)
            if key in renderable and str(data.get("status", "")).strip().lower() == "approved":
                ready_count += 1

        if ready_count >= min_ready:
            return rows

        state: dict[str, Any] = {"ready": ready_count, "budget": MAX_STANDALONE_PER_PASS,
                                 "covered": covered_keys, "renderable": renderable}
        self._standalone_pass("evergreen", state, rows, min_ready)
        ready_count = state["ready"]

        candidate_paths = [
            *sorted(Path(QUEUE_DIR).glob("*.md")),
            *sorted(Path(PUBLISHED_DIR).glob("[0-9]*.md")),
        ]
        for qpath in candidate_paths:
            if ready_count >= min_ready:
                break
            try:
                qdoc = parse_script(qpath)
            except Exception:  # noqa: BLE001
                continue
            if str(qdoc.status).strip().lower() not in {"approved", "published"}:
                continue
            if qdoc.channel != self.channel_id:
                continue  # a channel's Shorts come from its own long-form scripts
            if str(qdoc.id).strip() in covered_ids:
                continue
            cand_key = short_key_for_doc(qdoc)
            ed_cand = resolve_edition(cand_key)
            if cand_key in covered_keys or (ed_cand and (Path(PUBLISHED_DIR) / f"{ed_cand.slug}.md").is_file()):
                continue
            if cand_key not in renderable and not self.is_api_available():
                continue
            mpath, mkey = self.generate_companion_short(qdoc, require_renderable=True)
            if mpath is None:
                rows.append({
                    "file": f"{qdoc.id}-{mkey}.yml",
                    "key": mkey,
                    "verdict": "failed",
                    "reason": "spec authoring failed; manifest deferred to keep shorts-queue clean",
                })
                continue
            mdata = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
            verdict = "authored" if mdata.get("status") == "approved" else "failed"
            if verdict == "authored":
                ready_count += 1
                renderable.add(mkey)
                covered_ids.add(str(qdoc.id).strip())
                covered_keys.add(mkey)
            rows.append({
                "file": mpath.name,
                "key": mkey,
                "verdict": verdict,
                "reason": str(mdata.get("notes", ""))[:120],
            })
        state["ready"] = ready_count
        self._standalone_pass("roadmap", state, rows, min_ready)
        return rows

    def _require_own_channel(self, doc: ScriptDoc, script_path: Path) -> None:
        """Refuse a script that does not name this brain's channel.

        `_enforce_channel_metadata` already refuses model output branded for someone
        else, but it runs on text *before* the file exists. This runs on the parsed
        document, immediately before the write that makes it a queue item, so a
        script that reaches the queue by any other route — a repaired envelope, a
        hand-edited file, a future authoring path — still cannot be written under a
        channel that did not ask for it.

        An undeclared channel is refused rather than defaulted: `doc.channel` falls
        back to `secret-place`, and that fallback is exactly how 25 scripts written
        for one channel were counted as another's.
        """
        declared = (doc.explicit_channel or "").strip()
        if declared == self.channel_id:
            return
        if not declared:
            raise BrainAuthoringError(
                f"{script_path.name}: the script declares no `channel:` line, so it has "
                f"no owner. Nothing was written to the queue — a script that names no "
                f"channel parses as secret-place and would be published there. Add "
                f"`channel: {self.channel_id}` to its front matter.")
        raise BrainAuthoringError(
            f"{script_path.name}: declares `channel: {declared}` but this is "
            f"{self.channel_id}'s run. A script is never written into another "
            f"channel's queue.")

    def verify_and_stage(self, script_path: Path) -> BrainGenerationResult:
        """Run factchecking claim extraction, verify queue integrity, and stage for production."""
        from scripts.factcheck import main as factcheck_main, out_path
        from pipeline.run import _validate_finance_niche

        doc = parse_script(script_path)
        self._require_own_channel(doc, script_path)
        _validate_finance_niche(doc)

        # Generate the mandatory factcheck worksheet with sha256 binding
        factcheck_main([str(script_path), "--force"])
        factcheck_path = out_path(doc)

        short_path, _ = self.generate_companion_short(doc, require_renderable=True)

        return BrainGenerationResult(
            job_id=doc.id,
            scripture=extract_scripture_reference(doc),
            longform_path=script_path,
            short_manifest_path=short_path,
            factcheck_path=factcheck_path if factcheck_path.is_file() else None,
            status=doc.status,
            word_count=doc.word_count,
            scene_count=len(doc.scenes),
            used_gemini_api=self.is_api_available(),
        )

    def replenish_pipeline(self, min_runway_days: float = 2.0) -> Optional[BrainGenerationResult]:
        """Inspect this channel's publishable runway; author one if it is low.

        Identical rule on both channels: runway means *this channel's* approved,
        over-floor scripts. The old code measured channel 1 with a channel-wide
        audit and channel 2 with a queue count, so the two could disagree about
        what "healthy" meant.
        """
        from .supply import SLOTS_PER_DAY, publishable_longform

        caps = capabilities_for(self.channel_id)
        force = min_runway_days >= 900  # callers use a huge runway to force one pass
        have = len(publishable_longform(channel_id=self.channel_id))
        if not force:
            wanted = max(1, math.ceil(min_runway_days * SLOTS_PER_DAY))
            if have >= wanted:
                print(f"[gemini-brain] {caps.brand.display_name} runway healthy "
                      f"({have} publishable >= {wanted}). No replenishment needed.")
                return None

        next_candidate = self.select_next_scripture()
        print(f"[gemini-brain] {caps.brand.display_name} supply low ({have} publishable) — "
              f"authoring next devotional: {next_candidate['scripture']}...")

        # Reraised, not swallowed: "returned None" is indistinguishable from
        # "runway healthy" for every caller, which is how a stalled queue looked
        # like a satisfied one.
        script_text = normalize_authored_script_markdown(
            self.author_longform_script(next_candidate),
            channel_id=self.channel_id,
        )
        meta = job_front_matter(script_text)
        slug = str(meta.get("slug") or "").strip()
        if not slug:
            # No guessed name. The old fallback here wrote
            # `0040-devotional-0040.md` into the queue on 6 November when the model
            # answered with `job_id:` and no `slug:`, which is how an unvalidatable
            # job reached main.
            raise BrainAuthoringError(
                f"{caps.brand.display_name}: the model returned a script with no `slug:` "
                f"line, so it has no queue identity. Nothing was written.")
        script_filename = f"{next_candidate['id']}-{slug}.md"
        script_path = QUEUE_DIR / script_filename

        # Validate in a directory the scheduler never globs, then move it in. The
        # write used to happen first and every gate after it, so a refusal left the
        # file sitting in content/queue/ — and the production workflow's
        # "commit queue state" step, which stages everything under content/ on
        # `always()`, carried that refusal into main.
        staging_dir = QUEUE_DIR / ".incoming"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_path = staging_dir / script_filename
        staged_path.write_text(script_text, encoding="utf-8")
        try:
            staging_result = self.verify_and_stage(staged_path)
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise
        os.replace(staged_path, script_path)
        staging_result.longform_path = script_path
        result = staging_result
        print(f"[gemini-brain] Successfully authored & staged Job {result.job_id}: "
              f"{script_path.name} ({result.word_count} words, {result.scene_count} scenes).")
        return result
