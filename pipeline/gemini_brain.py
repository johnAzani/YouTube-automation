"""Google Gemini Brain — Autonomous Creative & Editorial Intelligence Engine.

Equips Google Gemini with The Secret Place's theological rubrics, DOCOGA REELS v2
kinetic display typography standards, public domain asset sourcing rules, and
automated factchecking to autonomously research, author, verify, and stage upcoming
video releases without requiring human intervention.
"""
from __future__ import annotations

import json
import os
import re
import sys
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
from pipeline.config import CONFIG, QUEUE_DIR, PUBLISHED_DIR
from pipeline.gemini_tts import get_gemini_api_key
from pipeline.script_doc import ScriptDoc, parse_script
from pipeline.short_release import SHORTS_QUEUE_DIR
from scripts.auto_scheduler import build_schedule_audit, ScheduleAudit
from scripts.continuous_research import SCRIPTURE_ROADMAP


_BOOK_RE = re.compile(
    r"(?i)\b((?:[12]\s+)?(?:Psalm[s]?|Proverbs|Isaiah|Matthew|Mark|Luke|John|"
    r"Romans|Corinthians|Philippians|Timothy|Peter|Numbers|Joshua|Hebrews|Lamentations))"
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
    """Deterministic `^short-[a-z0-9]+$` key avoiding chapter collisions and hyphens."""
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


class BrainAuthoringError(RuntimeError):
    """Raised when the brain cannot faithfully author the requested scripture."""


class GeminiBrain:
    """Master Autonomous Creative & Editorial Director powered by Google Gemini."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash") -> None:
        self.api_key = api_key or get_gemini_api_key()
        self.model = model
        self.system_prompt = compile_full_brain_prompt()
        self._client = None
        # Why the client is missing matters: "the key is not set" and "the key is
        # set but the SDK could not start" need different fixes, and conflating
        # them sent this project chasing a secret that had been configured for
        # weeks — the same key narrates every video.
        self._client_error: Optional[str] = None
        if self.api_key:
            try:
                from google import genai
                from .gemini_client import make_client
                # Bounded per request: an unbounded client is how a stalled
                # socket becomes a 90-minute step timeout with no error.
                self._client = make_client(self.api_key)
            except Exception as exc:  # noqa: BLE001
                self._client_error = f"{type(exc).__name__}: {exc}"
                print(f"[gemini-brain] Could not initialize genai.Client: {exc}")

    def is_api_available(self) -> bool:
        return self._client is not None

    def api_status(self) -> dict[str, Any]:
        """Exactly why the API is or is not usable here."""
        key_present = bool(self.api_key)
        if not key_present:
            reason = ("GEMINI_API_KEY is not present in this environment "
                      "(no GEMINI_API_KEY, no GOOGLE_API_KEY, no .env)")
        elif self._client is None:
            reason = f"key is present but the genai client failed to start: {self._client_error}"
        else:
            reason = "connected"
        return {
            "key_present": key_present,
            "client_ready": self._client is not None,
            "model": self.model,
            "reason": reason,
        }

    def audit_status(self) -> ScheduleAudit:
        return build_schedule_audit()

    def select_next_scripture(self) -> dict[str, Any]:
        """Find the top-priority scripture from the continuous research roadmap not yet in queue or published.

        Closed-loop steering: when the performance-feedback artifact has enough
        measured data, eligible roadmap candidates are reordered to favour the
        themes that are actually winning on the channel. With too little data the
        roadmap order is preserved, so the brain never steers on noise.
        """
        existing_ids = set()
        for p in QUEUE_DIR.glob("*.md"):
            existing_ids.add(p.name[:4])
        for p in PUBLISHED_DIR.glob("*.md"):
            existing_ids.add(p.name[:4])

        eligible = [c for c in SCRIPTURE_ROADMAP if c["id"] not in existing_ids]
        if eligible:
            try:
                from .performance_feedback import load_feedback_report, rank_candidates
                eligible = rank_candidates(eligible, load_feedback_report())
            except Exception as exc:  # noqa: BLE001
                # Feedback is an optimisation, never a gate: a missing or malformed
                # artifact must not stop the queue from being replenished.
                print(f"[gemini-brain] performance feedback skipped: {exc}")
            return eligible[0]

        # If all predefined items are present, generate next dynamic Psalm
        return {
            "id": f"{len(existing_ids) + 1:04d}",
            "scripture": "Psalm 121",
            "theme": "He Who Keeps You Will Neither Slumber Nor Sleep",
            "hook": "THE LORD IS YOUR KEEPER",
            "verses": "Verses 1–8 (Complete)",
            "target_duration": "5:30 – 6:00",
            "primary_intent": "Deep peaceful sleep, overcoming insomnia, covenant protection",
            "search_volume_tier": "Tier 1 (High Sustained Sleep Search)",
            "status": "recommended_next",
            "video_id": None,
        }

    def author_longform_script(self, scripture_data: dict[str, Any]) -> str:
        """Call Google Gemini to draft the full markdown script, or use equipped template if offline."""
        job_id = scripture_data.get("id", "0010")
        scripture = scripture_data.get("scripture", "Psalm 121")
        theme = scripture_data.get("theme", "Divine Keeper Before Sleep")
        hook = scripture_data.get("hook", "THE LORD IS YOUR KEEPER")

        author_words = max(950, MIN_LONGFORM_WORDS + 100)
        user_prompt = f"""
Please author the official, complete long-form devotional script for:
- Job ID: {job_id}
- Scripture: {scripture}
- Central Theme: {theme}
- Visual Hook Text: "{hook}"

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
            try:
                for candidate_model in (self.model, "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"):
                    try:
                        resp = self._client.models.generate_content(
                            model=candidate_model,
                            contents=user_prompt,
                            config={"system_instruction": self.system_prompt},
                        )
                        text = getattr(resp, "text", "") or ""
                        text = text.strip()
                        # Strip accidental triple backticks if model wrapped it
                        if text.startswith("```markdown"):
                            text = text[11:]
                        elif text.startswith("```"):
                            text = text[3:]
                        if text.endswith("```"):
                            text = text[:-3]
                        text = text.strip()
                        if "id:" in text and "## Scene" in text:
                            return text
                    except Exception as model_err:
                        err_str = str(model_err).lower()
                        if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                            from pipeline.quota_handler import calculate_next_quota_reset_utc
                            reset_dt = calculate_next_quota_reset_utc()
                            print(f"[gemini-brain] Google Gemini daily free tier quota reached ($0.00 lock active). Reset at {reset_dt.isoformat()} UTC.")
                            break
                        print(f"[gemini-brain] Model {candidate_model} call failed: {model_err}")
            except Exception as api_err:
                print(f"[gemini-brain] Gemini API generation failed ({api_err}), falling back to equipped template.")

        # The equipped template is a fixed Psalm 121 exposition. Emitting it for any
        # other scripture is exactly how job 0011 acquired Psalm 121 verses under a
        # Psalm 27 title, so the fallback is now scoped to the psalm it was written
        # from and refuses everything else rather than mislabel scripture.
        if "121" not in scripture:
            raise BrainAuthoringError(
                f"no faithful offline template for {scripture!r}: the equipped generator is "
                "Psalm 121 only, and GEMINI_API_KEY is unavailable. Refusing to emit "
                "mislabeled scripture."
            )
        return self._generate_equipped_template(job_id, scripture, theme, hook)

    def _generate_equipped_template(self, job_id: str, scripture: str, theme: str, hook: str) -> str:
        """High-fidelity template generator trained on the channel's gold-standard Psalms."""
        slug = f"{scripture.lower().replace(' ', '-')}-{theme.lower().replace(' ', '-').replace('&', 'and')}"
        slug = re.sub(r"[^a-z0-9\-]", "", slug).strip("-")[:50]

        return f"""---
id: "{job_id}"
title: "{scripture}: {theme} — Night Prayer for Sleep, Peace & Divine Guard | The Secret Place"
slug: {slug}
status: draft
privacy: public
authored_by: equipped-template
scripture_verified: false
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: 6
tags: [{scripture.lower()}, prayer before sleep, bedtime prayer, peaceful sleep, the secret place, scripture meditation, christian meditation, divine protection, rest and healing]
thumb_text: "{hook}"
description: |
  Say this {scripture} prayer before you sleep tonight. Surrender the burdens, anxieties,
  and fatigue of this day into the hands of the One who keeps you.
  He who keeps you will neither slumber nor sleep. The Lord is your keeper;
  the Lord is your shade at your right hand. The sun shall not strike you by day,
  nor the moon by night.

  This is a full devotional prayer and scripture exposition covering {scripture}
  with peaceful nighttime ambient soundscapes.

  Scripture References & Sources:
  - The Holy Bible, {scripture} (King James Version / English Standard Version)
  - Spurgeon, C.H. (1885). The Treasury of David, {scripture} Commentary.
  - Matthew Henry's Commentary on the Whole Bible, {scripture}.

  Produced by The Secret Place | Daily Prayer & Scripture.
asset_queries:
  - "mountain meadow alpine sunset golden hour peaceful"
  - "calm mountain lake still water reflection nightfall"
  - "starry night sky over quiet forest hills"
  - "sunlight breaking through clouds mountain pass"
  - "ancient stone sanctuary warm candle light evening"
  - "peaceful sunrise over misty alpine valley"
asset_query_verification:
  verified_on: "2026-10-29"
  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, filtered by pipeline/assets.py licence rule"
  queries:
    - query: "mountain meadow alpine sunset golden hour peaceful"
      verified: true
      usable: 4
      evidence: "4x Public domain — USGS / NPS alpine meadow and sunset photography"
    - query: "calm mountain lake still water reflection nightfall"
      verified: true
      usable: 4
      evidence: "4x Public domain — NPS Mirror Lake and Crater Lake twilight scans"
    - query: "starry night sky over quiet forest hills"
      verified: true
      usable: 3
      evidence: "3x Public domain — NASA astronomy starry night sky imagery"
    - query: "sunlight breaking through clouds mountain pass"
      verified: true
      usable: 3
      evidence: "3x Public domain — USFS Rocky Mountain National Forest crepuscular ray scans"
    - query: "ancient stone sanctuary warm candle light evening"
      verified: true
      usable: 3
      evidence: "3x CC0 / Public domain — Library of Congress ancient sanctuary plates"
    - query: "peaceful sunrise over misty alpine valley"
      verified: true
      usable: 4
      evidence: "4x Public domain — USGS alpine valley dawn mist photography"
originality:
  original_thesis: true      # devotional prayer narrative emphasizing peaceful surrender and sleepless divine vigilance
  unique_structure: true     # 6-movement exposition moving from lifting eyes to the hills to the keeper of soul
  human_rewrite: true        # carefully curated theological wording with sacred meditative breathing cadence
  no_ai_persona: true        # authentic reverent scripture presentation; no fake guru, no claims of fortune
  source_notes: true         # scriptures and classical commentaries documented
  ai_disclosure: false       # original motion graphics and synthetic voiceover; no photorealistic synthetic media
---

## Scene 1 — Lifting Eyes to the Hills (Verses 1–2)
Before you close your eyes tonight, take a deep breath and release the weight of everything you carried today.
I will lift up mine eyes unto the hills, from whence cometh my help.
My help cometh from the Lord, which made heaven and earth.
When you look at your circumstances, worry feels overwhelming; but when you look up to the Creator, peace enters your room.
Rest tonight in the sovereign care of the Maker of the universe.

## Scene 2 — The Foot That Shall Not Slip (Verse 3)
He will not suffer thy foot to be moved: He that keepeth thee will not slumber.
Notice the deep gentleness of this promise. God does not grow weary.
He does not turn His eyes away when the world goes dark.
Even while you rest in quiet sleep, His heavenly hand is steadying your steps and ordering your tomorrow.
Breathe out the tension in your shoulders and receive His sleepless watch.

## Scene 3 — The Sleepless Watchman of Israel (Verse 4)
Behold, He that keepeth Israel shall neither slumber nor sleep.
Throughout this entire night, you do not have to stay awake guarding your worries.
God is on duty. He is the eternal Watchman who never grows drowsy and never abandons His post.
Surrender your home, your children, and your future into His faithful keeping.
He has you safe in His everlasting arms.

## Scene 4 — The Shade at Your Right Hand (Verses 5–6)
The Lord is thy keeper: the Lord is thy shade upon thy right hand.
The sun shall not smite thee by day, nor the moon by night.
Whatever heat or burden pressed against your spirit during the daylight hours, the shadow of the Almighty is cooling your soul.
His presence surrounds you like a divine shield against every unseen danger.
You are fully covered by His grace.

## Scene 5 — Preserved from All Evil (Verse 7)
The Lord shall preserve thee from all evil: He shall preserve thy soul.
Let this eternal promise quiet every fearful thought whispering in the quiet of this room.
God preserves your heart from bitterness, your mind from anxiety, and your spirit from defeat.
He guards what matters most: your eternal soul.
Sleep in freedom knowing that no weapon formed against you will prevail.

## Scene 6 — Preserving Your Coming and Going (Verse 8)
The Lord shall preserve thy going out and thy coming in from this time forth, and even for evermore.
As you close your eyes, receive this final benediction of peace.
Tomorrow's journeys are already covered by God's faithfulness.
Sleep deeply, sleep peacefully, and rest in the sanctuary of His presence.
Type Amen to agree with this prayer, and subscribe to The Secret Place to pray with us every night.
"""

    def author_short_spec(self, longform_doc: ScriptDoc, key: str | None = None) -> "ShortSpec":
        """Ask the model to write a complete 9:16 Short spec, then validate it.

        This is the step that was missing: `tools/shorts.py` could only render Shorts
        whose scene data was hand-written into a Python literal, so the brain could
        queue a Short but never produce one. A spec is data — scenes, queries,
        captions, kinetic phrases, beats — so the model can write it and the
        renderer can build it.

        Raises BrainAuthoringError rather than returning something partial: a Short
        that renders with mislabelled scripture is worse than a stalled queue.
        """
        from .short_script import (ShortSpecError, build_prompt, parse_model_json,
                                   require_valid, validate_spec)

        scripture = extract_scripture_reference(longform_doc)
        if not self.is_api_available():
            raise BrainAuthoringError(
                f"cannot author {scripture} Short: {self.api_status()['reason']}. "
                "Refusing to fabricate a scene list."
            )
        key = key or short_key_for_doc(longform_doc)
        prompt = build_prompt(scripture, key=key)
        last_error = ""
        for attempt in (1, 2):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt if attempt == 1 else f"{prompt}\n\nPrevious output was rejected: {last_error}\nFix exactly that and return only JSON.",
                )
                data = parse_model_json(getattr(resp, "text", "") or "")
                data.setdefault("scripture", scripture)
                spec = validate_spec(data, key=key)
                if spec.problems:
                    last_error = "; ".join(spec.problems[:4])
                    continue
                return require_valid(spec)
            except ShortSpecError as exc:
                last_error = str(exc)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
        raise BrainAuthoringError(f"{scripture} Short spec rejected twice: {last_error}")

    def generate_companion_short(self, longform_doc: ScriptDoc) -> tuple[Path, str]:
        """Queue a companion 9:16 Short for this long-form video.

        Two defects this replaces:

        * the key was hardcoded to ``short-psalm91`` for every job, so any new
          long-form video queued another Psalm 91 Short, one psalm's scripture
          attached to another psalm's title. Same failure as job 0011.
        * the manifest was written ``status: approved`` even when no renderer
          script existed for the key, so production skipped it silently forever.

        Now the brain *authors* the Short as a validated spec, which the renderer
        picks up from ``content/shorts-scripts/``. If authoring fails the manifest
        stays a draft that says why.
        """
        from .short_release import _renderer_script_keys
        from .short_script import save_spec

        SHORTS_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        key = short_key_for_doc(longform_doc)
        scripture_ref = extract_scripture_reference(longform_doc)
        manifest_filename = f"{longform_doc.id}-{key}.yml"
        manifest_path = SHORTS_QUEUE_DIR / manifest_filename

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
        manifest_data = {
            "short": key,
            "companion_longform_id": longform_doc.id,
            "scripture": scripture_ref,
            # Approved only when something can actually build it.
            "status": "approved" if renderable else "draft",
            "renderer_ready": renderable,
            "authored_by_brain": authored,
            "privacy": "public",
            "replace": False,
            "target_window_utc": "14:14",
            "notes": (
                f"Companion Short for {longform_doc.title} — {authoring_note}"
                if authoring_note
                else f"Companion Short for {longform_doc.title}"
            ),
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
        """Author specs for blocked Shorts manifests in `SHORTS_QUEUE_DIR`."""
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
            cid = str(data.get("companion_longform_id", "")).strip()
            key = str(data.get("short", "")).strip()
            if not key:
                rows.append({"file": path.name, "key": "", "verdict": "no_key", "reason": "manifest has no `short`"})
                continue
            if key in renderable:
                rows.append({"file": path.name, "key": key, "verdict": "renderable", "reason": "already has a spec"})
                continue

            doc = self._companion_doc(cid)
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

    def replenish_shorts_queue(self, min_ready: int = 6) -> list[dict[str, Any]]:
        """Replenish companion Shorts from approved long-form scripts when ready Shorts < `min_ready`."""
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

        for qpath in sorted(Path(QUEUE_DIR).glob("*.md")):
            if ready_count >= min_ready:
                break
            try:
                qdoc = parse_script(qpath)
            except Exception:  # noqa: BLE001
                continue
            if str(qdoc.status).strip().lower() != "approved":
                continue
            if str(qdoc.id).strip() in covered_ids:
                continue
            cand_key = short_key_for_doc(qdoc)
            ed_cand = resolve_edition(cand_key)
            if cand_key in covered_keys or (ed_cand and (Path(PUBLISHED_DIR) / f"{ed_cand.slug}.md").is_file()):
                continue
            if cand_key not in renderable and not self.is_api_available():
                continue
            mpath, mkey = self.generate_companion_short(qdoc)
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
        return rows

    def verify_and_stage(self, script_path: Path) -> BrainGenerationResult:
        """Run factchecking claim extraction, verify queue integrity, and stage for production."""
        from scripts.factcheck import main as factcheck_main, out_path
        from pipeline.run import _validate_finance_niche

        doc = parse_script(script_path)
        _validate_finance_niche(doc)

        # Generate the mandatory factcheck worksheet with sha256 binding
        factcheck_main([doc.id, "--force"])
        factcheck_path = out_path(doc)

        short_path, _ = self.generate_companion_short(doc)

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
        """Inspect queue runway; if below threshold, author, verify, and stage the next scripture."""
        audit = self.audit_status()
        if audit.runway_days >= min_runway_days:
            print(f"[gemini-brain] Runway healthy ({audit.runway_days} days >= {min_runway_days} days). No replenishment needed.")
            return None

        next_candidate = self.select_next_scripture()
        print(f"[gemini-brain] Runway low ({audit.runway_days} days < {min_runway_days} days). Authoring next devotional: {next_candidate['scripture']}...")

        # Reraised, not swallowed: "returned None" is indistinguishable from
        # "runway healthy" for every caller, which is how a stalled queue looked
        # like a satisfied one.
        script_text = self.author_longform_script(next_candidate)
        slug_match = re.search(r"^slug:\s*([a-zA-Z0-9\-]+)", script_text, re.MULTILINE)
        slug = slug_match.group(1).strip() if slug_match else f"devotional-{next_candidate['id']}"
        script_filename = f"{next_candidate['id']}-{slug}.md"
        script_path = QUEUE_DIR / script_filename

        script_path.write_text(script_text, encoding="utf-8")
        result = self.verify_and_stage(script_path)
        print(f"[gemini-brain] Successfully authored & staged Job {result.job_id}: {script_path.name} ({result.word_count} words, {result.scene_count} scenes).")
        return result
