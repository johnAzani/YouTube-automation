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
    r"(?i)\b((?:[12]\s+)?(?:Psalm[s]?|Proverbs|Isaiah|Matthew|Mark|Luke|John|"
    r"Romans|Corinthians|Philippians|Ephesians|Timothy|Peter|Numbers|Joshua|Hebrews|Lamentations))"
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
MAX_CALLS_PER_RUN = int(os.environ.get("GEMINI_MAX_CALLS_PER_RUN", "40") or "40")


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
             *DEPRECATED_TEXT_MODELS, *RETIRED_TEXT_MODELS]
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
_TRANSIENT_BACKOFF = (5, 15, 30, 60)


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
                eligible = rank_candidates(eligible, load_feedback_report())
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
            try:
                for candidate_model in text_model_candidates(self.model):
                    text = (self._call_model(candidate_model, user_prompt) or "").strip()
                    if not text:
                        continue
                    # Strip accidental triple backticks if model wrapped it
                    if text.startswith("```markdown"):
                        text = text[11:]
                    elif text.startswith("```"):
                        text = text[3:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                    if "id:" in text and "## Scene" in text:
                        self._enforce_channel_metadata(text, scripture_data)
                        return text
            except BrainAuthoringError:
                raise
            except Exception as api_err:
                print(f"[gemini-brain] Gemini API generation failed ({api_err}).")

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

    def _call_model(self, model: str, prompt: str) -> str:
        """One model call with bounded backoff for a busy service.

        Returns the raw text, or "" when this model cannot answer (retired, out of
        quota, or still busy after the retries) so the caller can try the next
        candidate. `BrainAuthoringError` is a verdict about the *text*, not a
        transport failure, and is always re-raised.
        """
        for attempt in range(1 + len(_TRANSIENT_BACKOFF)):
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
                return getattr(resp, "text", "") or ""
            except BrainAuthoringError:
                raise
            except Exception as exc:  # noqa: BLE001
                err = str(exc).lower()
                if is_model_retired(exc):
                    report_retired_model(model, exc)
                    return ""
                if "429" in err or "resource_exhausted" in err or "quota" in err:
                    from pipeline.quota_handler import calculate_next_quota_reset_utc

                    reset_dt = calculate_next_quota_reset_utc()
                    print("[gemini-brain] Google Gemini daily free tier quota reached "
                          f"($0.00 lock active). Reset at {reset_dt.isoformat()} UTC.")
                    return ""
                if is_transient(exc) and attempt < len(_TRANSIENT_BACKOFF):
                    wait = _TRANSIENT_BACKOFF[attempt]
                    print(f"[gemini-brain] {model}: service busy ({type(exc).__name__}). "
                          f"Waiting {wait}s (attempt {attempt + 2}/"
                          f"{1 + len(_TRANSIENT_BACKOFF)})...", flush=True)
                    time.sleep(wait)
                    continue
                print(f"[gemini-brain] Model {model} call failed: {exc}")
                return ""
        print(f"[gemini-brain] Model {model} still busy after "
              f"{len(_TRANSIENT_BACKOFF)} retries; trying the next candidate.")
        return ""

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
            for attempt in (1, 2):
                contents = prompt if attempt == 1 else (
                    f"{prompt}\n\nPrevious output was rejected: {last_error}\n"
                    "Fix exactly that and return only JSON.")
                resp = None
                for wait in (0, *_TRANSIENT_BACKOFF):
                    if wait:
                        # Same 503 spike that killed a long-form run at 08:45Z
                        # would also kill the Short: wait, do not re-prompt.
                        print(f"[gemini-brain] Short {key}: service busy, waiting {wait}s...",
                              flush=True)
                        time.sleep(wait)
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
                        if is_model_retired(exc):
                            report_retired_model(model, exc)
                            resp = None
                            break
                        if not is_transient(exc):
                            raise
                if resp is None:
                    last_error = f"{model}: no answer"
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
        """Replenish this channel's companion Shorts when ready Shorts < `min_ready`."""
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

        for qpath in sorted(Path(QUEUE_DIR).glob("*.md")):
            if ready_count >= min_ready:
                break
            try:
                qdoc = parse_script(qpath)
            except Exception:  # noqa: BLE001
                continue
            if str(qdoc.status).strip().lower() != "approved":
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
        script_text = self.author_longform_script(next_candidate)
        slug_match = re.search(r"^slug:\s*([a-zA-Z0-9\-]+)", script_text, re.MULTILINE)
        slug = slug_match.group(1).strip() if slug_match else f"devotional-{next_candidate['id']}"
        script_filename = f"{next_candidate['id']}-{slug}.md"
        script_path = QUEUE_DIR / script_filename

        script_path.write_text(script_text, encoding="utf-8")
        result = self.verify_and_stage(script_path)
        print(f"[gemini-brain] Successfully authored & staged Job {result.job_id}: "
              f"{script_path.name} ({result.word_count} words, {result.scene_count} scenes).")
        return result
