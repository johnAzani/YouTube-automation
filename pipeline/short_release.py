"""Production release path for authored 9:16 YouTube Shorts (`tools/shorts.py`).

Enforces fail-closed pre-flight and post-render gates before calling
`pipeline.upload.upload()`:

  1. Non-dry-run runs require all three YouTube OAuth secrets up front.
  2. Duplicate uploads are blocked unless `--force` is passed.
  3. Every rendered scene must trace either to a licensed stock acquisition or
     to a `status: cleared` entry in `image-search/LICENSES.yml` (zero Getty,
     corrupt, unrecorded, or unverified fallback stills).
  4. The encoded MP4 must carry both `video` and `audio` streams, strict
     vertical dimensions (`height > width`), and duration within `(15s, 60s]`.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import yaml

from .assemble import ffmpeg_bin
from .config import CONFIG, CONTENT_DIR, OUTPUT_DIR, PUBLISHED_DIR, REPO_ROOT
from .licences import load_ledger, uncleared_stills, unsafe_stills
from .run import _open_release_ticket, _require_production_prerequisites, _validate_channel_niche
from .script_doc import Scene, ScriptDoc

SHORTS_QUEUE_DIR = CONTENT_DIR / "shorts-queue"
MAX_SHORT_SECONDS = 180.0
MIN_SHORT_SECONDS = 15.0


@dataclass(frozen=True)
class ShortEdition:
    key: str
    job_id: str
    slug: str
    title: str
    niche: str
    tags: list[str]
    description: str


EDITIONS: dict[str, ShortEdition] = {
    "short-enron": ShortEdition(
        key="short-enron",
        job_id="SHORT-0001",
        slug="short-0001-how-enron-died",
        title="How Enron Faked $70 Billion in Plain Sight #Shorts",
        niche="finance and business",
        tags=[
            "shorts",
            "enron",
            "accounting scandal",
            "mark to market",
            "financial history",
            "corporate collapse",
            "business documentary",
        ],
        description=(
            "Enron hit $90.75 a share and a ~$70B valuation before one question — "
            "\"Is Enron Overpriced?\" — exposed mark-to-market accounting and off-balance-sheet "
            "partnerships hiding billions in debt.\n\n"
            "On December 2, 2001, Enron filed for Chapter 11 bankruptcy with $63.4B in "
            "reported assets.\n\n"
            "A money story, not money advice. No picks, no predictions — just the record.\n\n"
            "Primary & archival sources:\n"
            "- McLean, Bethany (2001). \"Is Enron Overpriced?\" Fortune, March 5, 2001.\n"
            "- Powers, William C., Jr. et al. (2002). Report of Investigation by the Special "
            "Investigative Committee of the Board of Directors of Enron Corp., Feb 1, 2002.\n"
            "- In re Enron Corp., Case No. 01-16034 (AJG), U.S. Bankruptcy Court, S.D.N.Y., "
            "Voluntary Petition (Dec 2, 2001).\n"
            "- Enron Corp. Form 10-K & Form 8-K filings, U.S. Securities and Exchange Commission.\n\n"
            "#Shorts #Enron #FinancialHistory #Accounting #Documentary"
        ),
    ),
    "short-psalm91": ShortEdition(
        key="short-psalm91",
        job_id="SHORT-0002",
        slug="short-0002-psalm-91-prayer-of-protection",
        title="Say This Psalm 91 Prayer Before You Sleep | Divine Protection #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 91",
            "night prayer",
            "prayer of protection",
            "bedtime prayer",
            "daily scripture",
            "christian encouragement",
            "peaceful sleep",
        ],
        description=(
            "He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty.\n\n"
            "Rest tonight under God's divine shield. When fear whispers in the dark, remember that His faithfulness "
            "is your shield and buckler. No evil shall befall you, nor shall any plague come near your dwelling.\n\n"
            "Scripture reference: Psalm 91 (NKJV / Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm91 #NightPrayer #PrayerOfProtection #BedtimePrayer #DailyScripture #TheSecretPlace"
        ),
    ),
    "short-psalm23": ShortEdition(
        key="short-psalm23",
        job_id="SHORT-0003",
        slug="short-0003-psalm-23-the-lord-is-my-shepherd",
        title="Say This Psalm 23 Prayer Before You Sleep | Divine Peace #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 23",
            "the lord is my shepherd",
            "night prayer",
            "prayer of peace",
            "bedtime prayer",
            "daily scripture",
            "christian encouragement",
            "peaceful sleep",
        ],
        description=(
            "The Lord is my shepherd; I shall not want. He makes me to lie down in green pastures.\n\n"
            "Rest tonight under God's gentle shepherding. When worry troubles your mind, remember that He restores "
            "your soul and leads you beside still waters. Even in the valley of shadows, you shall fear no evil.\n\n"
            "Scripture reference: Psalm 23 (NKJV / Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm23 #TheLordIsMyShepherd #NightPrayer #BedtimePrayer #DailyScripture #TheSecretPlace"
        ),
    ),
    "short-psalm121": ShortEdition(
        key="short-psalm121",
        job_id="SHORT-0004",
        slug="short-0004-psalm-121-he-who-keeps-you",
        title="Say This Psalm 121 Prayer Before You Sleep | He Who Keeps You #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 121",
            "he who keeps you",
            "night prayer",
            "prayer of protection",
            "bedtime prayer",
            "daily scripture",
            "christian encouragement",
            "peaceful sleep",
        ],
        description=(
            "I will lift up mine eyes unto the hills, from whence cometh my help. "
            "My help cometh from the Lord, which made heaven and earth.\n\n"
            "Rest peacefully tonight knowing that He who keeps you will neither slumber nor sleep. "
            "The Lord is your keeper and your shade upon your right hand.\n\n"
            "Scripture reference: Psalm 121 (KJV / NKJV Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm121 #HeWhoKeepsYou #NightPrayer #BedtimePrayer #DailyScripture #TheSecretPlace"
        ),
    ),
    "short-psalm27": ShortEdition(
        key="short-psalm27",
        job_id="SHORT-0005",
        slug="short-0005-psalm-27-the-lord-is-my-light",
        title="Say This Psalm 27 Prayer Before You Sleep | Fear No Evil #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 27",
            "the lord is my light",
            "night prayer",
            "fear no evil",
            "bedtime prayer",
            "daily scripture",
            "christian encouragement",
            "peaceful sleep",
        ],
        description=(
            "The Lord is my light and my salvation; whom shall I fear? "
            "The Lord is the strength of my life; of whom shall I be afraid?\n\n"
            "Surrender all nighttime anxiety into His presence. In the time of trouble "
            "He will hide you in His pavilion and set your feet upon a rock.\n\n"
            "Scripture reference: Psalm 27 (KJV / NKJV Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm27 #TheLordIsMyLight #FearNoEvil #NightPrayer #BedtimePrayer #TheSecretPlace"
        ),
    ),
    "short-psalm46": ShortEdition(
        key="short-psalm46",
        job_id="SHORT-0006",
        slug="short-0006-psalm-46-god-is-our-refuge",
        title="Say This Psalm 46 Prayer Before You Sleep | Be Still & Know #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 46",
            "be still and know",
            "god is our refuge",
            "night prayer",
            "peaceful sleep",
            "daily scripture",
            "the secret place",
        ],
        description=(
            "God is our refuge and strength, a very present help in trouble. "
            "Therefore we will not fear, though the earth be removed.\n\n"
            "Be still, and know that He is God. Rest tonight under His divine fortress.\n\n"
            "Scripture reference: Psalm 46 (KJV / NKJV Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm46 #BeStillAndKnow #NightPrayer #BedtimePrayer #TheSecretPlace"
        ),
    ),
    "short-psalm34": ShortEdition(
        key="short-psalm34",
        job_id="SHORT-0007",
        slug="short-0007-psalm-34-angel-of-the-lord",
        title="Say This Psalm 34 Prayer Before You Sleep | Angels Stand Watch #Shorts",
        niche="faith and prayer",
        tags=[
            "shorts",
            "psalm 34",
            "angel of the lord",
            "night prayer",
            "prayer of protection",
            "bedtime prayer",
            "daily scripture",
            "the secret place",
        ],
        description=(
            "The angel of the Lord encamps all around those who fear Him, and delivers them. "
            "Oh, taste and see that the Lord is good; blessed is the man who trusts in Him!\n\n"
            "Rest tonight under the guard of heavenly messengers.\n\n"
            "Scripture reference: Psalm 34 (KJV / NKJV Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            "#Shorts #Psalm34 #AngelOfTheLord #NightPrayer #BedtimePrayer #TheSecretPlace"
        ),
    ),
}


@dataclass(frozen=True)
class MediaProbe:
    has_video: bool
    has_audio: bool
    width: int
    height: int
    duration_seconds: float


def probe_media(video_path: Path) -> MediaProbe:
    """Inspect container streams and dimensions via `ffmpeg -hide_banner -i`."""
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise RuntimeError(f"Short video missing or empty: {video_path}")

    proc = subprocess.run(
        [ffmpeg_bin(), "-hide_banner", "-i", str(video_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    banner = f"{proc.stdout}\n{proc.stderr}"

    dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", banner)
    if not dur_match:
        raise RuntimeError(f"Could not read duration from {video_path.name}")
    duration_s = (
        int(dur_match.group(1)) * 3600
        + int(dur_match.group(2)) * 60
        + float(dur_match.group(3))
    )

    has_video = False
    has_audio = False
    width = 0
    height = 0
    for line in banner.splitlines():
        if "Stream #" not in line:
            continue
        if " Video:" in line:
            has_video = True
            dim_match = re.search(r"\b(\d{2,5})x(\d{2,5})\b", line)
            if dim_match:
                width = int(dim_match.group(1))
                height = int(dim_match.group(2))
        elif " Audio:" in line:
            has_audio = True

    return MediaProbe(
        has_video=has_video,
        has_audio=has_audio,
        width=width,
        height=height,
        duration_seconds=duration_s,
    )


def verify_short_render(
    video_path: Path,
    sources_json_path: Path,
    ledger: dict[str, dict] | None = None,
) -> MediaProbe:
    """Fail closed if media streams, aspect ratio, duration, or licences fail."""
    probe = probe_media(video_path)
    if not probe.has_video:
        raise RuntimeError(f"{video_path.name} has no video stream.")
    if not probe.has_audio:
        raise RuntimeError(f"{video_path.name} has no audio stream.")
    if probe.width <= 0 or probe.height <= 0 or probe.height <= probe.width:
        raise RuntimeError(
            f"{video_path.name} must be vertical (height > width) for YouTube Shorts; "
            f"got {probe.width}x{probe.height}."
        )
    if not (MIN_SHORT_SECONDS <= probe.duration_seconds <= MAX_SHORT_SECONDS):
        raise RuntimeError(
            f"{video_path.name} duration {probe.duration_seconds:.1f}s outside "
            f"[{MIN_SHORT_SECONDS:.0f}s, {MAX_SHORT_SECONDS:.0f}s] Shorts bounds."
        )

    if not sources_json_path.is_file():
        raise RuntimeError(f"Scene source ledger missing: {sources_json_path}")
    rows = json.loads(sources_json_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"Scene source ledger is empty: {sources_json_path}")

    fallback_files: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if row.get("fallback") or row.get("provider") == "existing story archive":
            fname = Path(str(row.get("file") or "")).name
            if not fname:
                raise RuntimeError(f"Scene {idx} used fallback with no recorded filename.")
            fallback_files.append(fname)
        else:
            lic = str(row.get("license") or "").strip().lower()
            if not lic or "encumbered" in lic or "unverified" in lic:
                raise RuntimeError(f"Scene {idx} has non-cleared licence note: {row.get('license')!r}")

    if fallback_files:
        active_ledger = load_ledger(use_cache=False) if ledger is None else ledger
        bad_unsafe = unsafe_stills(fallback_files, active_ledger)
        bad_uncleared = uncleared_stills(fallback_files, active_ledger)
        if bad_unsafe or bad_uncleared:
            details = ", ".join(f"{n} [{s}]" for n, s in (bad_unsafe or bad_uncleared))
            raise RuntimeError(
                f"Refusing to upload Short with uncleared fallback still(s): {details}"
            )

    return probe


def _renderer_script_keys() -> set[str]:
    """Hand-written SCRIPTS keys plus every validated authored spec.

    Read by AST so the heavy rendering dependencies are never imported here, then
    unioned with `content/shorts-scripts/*.json` — which is how the brain's Shorts
    become renderable without a code change.
    """
    tree = ast.parse((REPO_ROOT / "tools" / "shorts.py").read_text(encoding="utf-8"))
    keys: set[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SCRIPTS" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                keys = {k.value for k in node.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    if keys is None:
        raise RuntimeError("Cannot determine supported Shorts renderer scripts")
    from .short_script import authored_keys
    return keys | authored_keys()


def resolve_edition(key: str) -> ShortEdition | None:
    """Return the ShortEdition for `key`, synthesizing one for brain-authored specs."""
    if key in EDITIONS:
        return EDITIONS[key]
    try:
        from .short_script import load_spec, spec_path

        path = spec_path(key)
        if not path.is_file():
            return None
        spec = load_spec(path)
        if spec.problems:
            return None
    except Exception:  # noqa: BLE001
        return None

    from .metadata import smart_truncate_title

    label = (
        spec.scripture.strip()
        if getattr(spec, "scripture", "").strip()
        else (f"Psalm {spec.psalm}" if spec.psalm else key.removeprefix("short-").replace("-", " ").title())
    )
    hook = (spec.poster[3] if len(spec.poster) >= 4 and spec.poster[3] else "Divine Peace").title()
    raw_title = f"Say This {label} Prayer Before You Sleep | {hook}"
    clean_title = f"{smart_truncate_title(raw_title, 86)} #Shorts"
    tag_key = re.sub(r"[^a-zA-Z0-9]+", "", label)
    return ShortEdition(
        key=key,
        job_id=f"SHORT-{key.removeprefix('short-').upper()}",
        slug=f"{key}-night-prayer",
        title=clean_title,
        niche="faith and prayer",
        tags=[
            "shorts",
            label.lower(),
            "night prayer",
            "bedtime prayer",
            "prayer of protection",
            "daily scripture",
            "peaceful sleep",
            "the secret place",
        ],
        description=(
            f"{spec.narration_text}\n\n"
            f"Scripture reference: {label} (KJV / Public Domain biblical text).\n"
            "Produced by The Secret Place | Daily Prayer & Scripture.\n\n"
            f"#Shorts #{tag_key} #NightPrayer #BedtimePrayer #DailyScripture #TheSecretPlace"
        ),
    )


def queue_report(queue_dir: Path | None = None) -> list[dict]:
    """Every manifest in the Shorts queue with its verdict and the reason.

    The stage used to print "nothing to do" and exit 0, which is indistinguishable
    from success on the run page. Three approved manifests sat here for days while
    the renderer had no script for their keys.
    """
    qdir = SHORTS_QUEUE_DIR if queue_dir is None else queue_dir
    if not qdir.is_dir():
        return []
    renderable = _renderer_script_keys()
    rows: list[dict] = []
    for path in sorted(qdir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        key = str(data.get("short") or data.get("edition") or "").strip()
        status = str(data.get("status", "")).strip().lower()
        brain_queued = bool(data.get("scripture") or data.get("authored_by_brain"))
        if key not in EDITIONS and key not in renderable and not brain_queued:
            verdict, reason = "unusable", f"unknown short key {key!r} not in EDITIONS"
        elif key not in renderable:
            verdict, reason = (
                "needs_renderer",
                f"no scene script {key!r} in content/shorts-scripts/ or tools/shorts.py",
            )
        elif resolve_edition(key) is None:
            verdict, reason = "unusable", f"unknown short key {key!r} not in EDITIONS or shorts-scripts"
        elif status != "approved":
            verdict, reason = "not_approved", f"status is {status or 'missing'}"
        else:
            verdict, reason = "ready", "will render on the next run"
        rows.append({"file": path.name, "short": key, "status": status,
                     "verdict": verdict, "reason": reason})
    return rows


def select_next_queued_short(
    queue_dir: Path | None = None,
    published_dir: Path | None = None,
) -> tuple[Path, str] | None:
    """Return `(manifest_path, short_key)` for the first approved or quota-resumed Short in queue."""
    qdir = SHORTS_QUEUE_DIR if queue_dir is None else queue_dir
    if not qdir.is_dir():
        return None

    # Determine published directory for duplicate validation
    pdir: Path | None = None
    if published_dir is not None:
        pdir = published_dir
    elif queue_dir is None:
        pdir = PUBLISHED_DIR
    elif (queue_dir.parent / "published").is_dir():
        pdir = queue_dir.parent / "published"

    for path in sorted(qdir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_status = str(data.get("status", "")).strip().lower()

        # Check if job was paused due to daily quota exhaustion
        if raw_status == "quota_paused":
            reset_at_str = data.get("quota_reset_utc")
            if reset_at_str:
                from datetime import datetime, timezone
                try:
                    reset_at = datetime.fromisoformat(reset_at_str)
                    now_utc = datetime.now(timezone.utc)
                    if now_utc >= reset_at:
                        print(f"[queue] Quota reset time passed ({reset_at_str}). Auto-unpausing {path.name}...")
                        data["status"] = "approved"
                        raw_status = "approved"
                        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                    else:
                        print(f"[queue] {path.name} is paused until daily quota resets at {reset_at_str} UTC.")
                        continue
                except Exception as parse_err:
                    print(f"[queue] Warning: could not parse quota_reset_utc: {parse_err}")
                    continue

        is_approved = (
            raw_status == "approved"
            or bool(data.get("approved"))
        )
        if not is_approved:
            continue
        key = str(data.get("short") or data.get("edition") or "").strip()
        if not key:
            continue

        # --- DUPLICATE SHORT SHIELD: Verify not already in published directory ---
        if pdir is not None and pdir.is_dir():
            published_candidates = [
                pdir / f"{key}.md",
                pdir / f"{path.stem}.md",
            ]
            ed_cand = resolve_edition(key)
            if ed_cand is not None:
                published_candidates.append(pdir / f"{ed_cand.slug}.md")

            is_already_published = False
            for p_cand in published_candidates:
                if p_cand.is_file():
                    p_text = p_cand.read_text(encoding="utf-8")
                    if "youtube_video_id:" in p_text or "status: published" in p_text:
                        is_already_published = True
                        print(
                            f"[queue] 🛑 DUPLICATE BLOCKED: Short '{key}' ({path.name}) is already published in "
                            f"{p_cand.name}. Unlinking duplicate queue manifest to prevent accidental upload."
                        )
                        path.unlink()
                        break

            if is_already_published:
                continue

        if key not in _renderer_script_keys():
            print(f"[queue] Skipping manifest {path.name}: renderer has no script for {key!r}")
            continue

        # Skip manifests referencing short keys that aren't valid EDITIONS or authored specs
        if resolve_edition(key) is None:
            print(f"[queue] Skipping manifest {path.name}: unknown short key {key!r} not in EDITIONS")
            continue

        return path, key
    return None


def _build_script_doc(edition: ShortEdition) -> ScriptDoc:
    desc = edition.description
    if edition.niche == "faith and prayer":
        try:
            from .shorts_bridge import enrich_short_description_with_bridge
            desc = enrich_short_description_with_bridge(desc, edition.key)
        except Exception:
            pass

    return ScriptDoc(
        path=PUBLISHED_DIR / f"{edition.slug}.md",
        meta={
            "id": edition.job_id,
            "title": edition.title,
            "slug": edition.slug,
            "status": "approved",
            "format": "short",
            "niche": edition.niche,
            "category": "education",
            "tags": list(edition.tags),
            "description": desc,
            "originality": {
                "original_thesis": True,
                "unique_structure": True,
                "human_rewrite": True,
                "no_ai_persona": True,
                "source_notes": True,
            },
        },
        scenes=[Scene(index=1, heading=edition.title, narration=desc)],
    )


def _write_published_record(
    dest: Path,
    edition: ShortEdition,
    video_id: str,
    watch_url: str,
    privacy_status: str,
    probe: MediaProbe,
    scene_count: int,
    thumbnail_results: dict[str, str] | None = None,
    channel_audit: list[dict] | None = None,
) -> Path:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    stamp_precise = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"
    thumb_block = ""
    if thumbnail_results:
        lines = "\n".join(f"- `{vid}`: `{status}`" for vid, status in thumbnail_results.items())
        thumb_block = f"\n\n## Custom Thumbnail Apply Results\n\n{lines}\n"
    audit_block = ""
    if channel_audit:
        audit_block = f"\n\n## Channel Video Status Audit\n\n```json\n{json.dumps(channel_audit, indent=2)}\n```\n"
    content = (
        "---\n"
        f'id: "{edition.job_id}"\n'
        f'title: "{edition.title}"\n'
        f"slug: {edition.slug}\n"
        "status: published\n"
        "format: short\n"
        f"niche: {edition.niche}\n"
        "category: education\n"
        f'published_on: "{today}"\n'
        f'published_at: "{stamp_precise}"\n'
        f'youtube_video_id: "{video_id}"\n'
        f'youtube_shorts_url: "{shorts_url}"\n'
        f'youtube_watch_url: "{watch_url}"\n'
        f'youtube_studio_url: "{studio_url}"\n'
        f'privacy_status: "{privacy_status}"\n'
        'metadata_revision: "selar-seo-v1"\n'
        f"width: {probe.width}\n"
        f"height: {probe.height}\n"
        f"duration_seconds: {round(probe.duration_seconds, 2)}\n"
        f"scenes_verified: {scene_count}\n"
        "---\n\n"
        f"{edition.description}"
        f"{thumb_block}"
        f"{audit_block}\n"
    )
    dest.write_text(content, encoding="utf-8")
    return dest


def _scrub(text: str) -> str:
    cleaned = text
    for secret in (
        CONFIG.youtube_client_id,
        CONFIG.youtube_client_secret,
        CONFIG.youtube_refresh_token,
        CONFIG.pexels_api_key,
        CONFIG.pixabay_api_key,
    ):
        if secret and len(secret) >= 4:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def _read_previous_video_id(record_path: Path) -> str:
    if not record_path.is_file():
        return ""
    m = re.search(r'^youtube_video_id:\s*"([^"]+)"', record_path.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1).strip() if m else ""


def _close_superseded_tickets(title: str, new_shorts_url: str) -> None:
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        return
    try:
        proc = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--limit", "10", "--json", "number,title"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            return
        for row in json.loads(proc.stdout or "[]"):
            if row.get("title") == f"Release ticket: {title}":
                subprocess.run(
                    [
                        "gh",
                        "issue",
                        "close",
                        str(row["number"]),
                        "--comment",
                        f"Superseded by full-bleed B-roll replacement Short upload: {new_shorts_url}",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
    except Exception:  # noqa: BLE001
        pass


def _clean_word_token(word: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", word.lower()).strip("'")


def _fallback_word_timings(narration_text: str, duration_s: float) -> list[list]:
    """Deterministic monotonic word timings when faster-whisper weights are absent."""
    tokens = [_clean_word_token(w) for w in narration_text.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return [[0.0, round(max(0.5, duration_s), 2), "amen"]]
    usable_dur = max(1.0, float(duration_s) - 0.15)
    weights = [max(2, len(t)) for t in tokens]
    total_w = float(sum(weights))
    cursor = 0.0
    out: list[list] = []
    for tok, wt in zip(tokens, weights):
        dt = usable_dur * (wt / total_w)
        t0 = round(cursor, 2)
        t1 = round(min(usable_dur, cursor + max(0.04, dt - 0.01)), 2)
        if t1 <= t0:
            t1 = round(t0 + 0.04, 2)
        out.append([t0, t1, tok])
        cursor += dt
    return out


def _ensure_word_timings(short_key: str, audio_path: Path, narration_text: str) -> Path:
    """Generate `assets/deepdive/words-{short_key}.json` (`[[t0, t1, word], ...]`).

    Uses the preinstalled local faster-whisper CPU model (`output/alignment-model`)
    at $0.00 when available, falling back to character-weighted monotonic timing
    over the probed narration duration so `tools/shorts.py` never crashes on a
    missing word-alignment file.
    """
    words_path = audio_path.parent / f"words-{short_key}.json"
    if words_path.is_file() and words_path.stat().st_size > 10:
        return words_path

    model_dir = REPO_ROOT / "output" / "alignment-model"
    rows: list[list] = []
    if (model_dir / "model.bin").is_file():
        try:
            from .prayer_alignment import align

            aligned = align(audio_path, narration_text, model_dir)
            for orig, start_s, end_s in aligned:
                tok = _clean_word_token(orig) or orig.lower()
                t0 = round(float(start_s), 2)
                t1 = round(max(float(start_s) + 0.03, float(end_s)), 2)
                rows.append([t0, t1, tok])
            print(f"[short-release] aligned {len(rows)} words via faster-whisper for {short_key}")
        except Exception as exc:  # noqa: BLE001
            print(f"[short-release] faster-whisper alignment fallback for {short_key}: {exc}")
            rows = []

    if not rows:
        dur = probe_media(audio_path).duration_seconds
        rows = _fallback_word_timings(narration_text, dur)
        print(f"[short-release] generated {len(rows)} proportional word timings ({dur:.1f}s) for {short_key}")

    words_path.parent.mkdir(parents=True, exist_ok=True)
    words_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return words_path


def _ensure_narration(short_key: str) -> None:
    """Make sure an authored Short has audio and word timings before rendering.

    A brain-authored Short ships as a spec: captions only, no MP3. The same Charon
    voice that narrates the long-form reads the captions here, and local word
    alignment writes `words-{short_key}.json` so `tools/shorts.py` can render with
    zero human steps and $0.00 cost.
    """
    from .quota_handler import GeminiQuotaExceededError, QuotaExceededError

    try:
        from .short_script import load_spec, spec_path

        path = spec_path(short_key)
        if not path.is_file():
            return  # hand-written SCRIPTS entry: its audio & words JSON are committed
        spec = load_spec(path)
        audio = REPO_ROOT / "assets" / "deepdive" / f"{short_key}.mp3"
        if not audio.is_file():
            from .gemini_tts import synthesize_gemini_audio

            audio.parent.mkdir(parents=True, exist_ok=True)
            print(f"[short-release] synthesising narration for {short_key} ({spec.words} words)")
            synthesize_gemini_audio(spec.narration_text, audio, voice="Charon")
        _ensure_word_timings(short_key, audio, spec.narration_text)
    except (QuotaExceededError, GeminiQuotaExceededError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"cannot prepare narration for {short_key} ({exc}); refusing to render a silent Short"
        ) from exc


def _pause_manifest_on_quota(
    manifest_path: Path | None,
    stage_dir: Path,
    exc: Exception,
    base_result: dict,
) -> dict:
    from .quota_handler import GeminiQuotaExceededError, calculate_next_quota_reset_utc

    reset_utc = getattr(exc, "reset_utc", None) or calculate_next_quota_reset_utc()
    reset_iso = reset_utc.isoformat()
    is_gemini = isinstance(exc, GeminiQuotaExceededError)
    pause_label = "Gemini API" if is_gemini else "YouTube API"
    print(f"[short-release] Daily {pause_label} limit reached ($0.00 lock): {exc}. Pausing job until {reset_iso}...")
    if manifest_path and manifest_path.is_file():
        try:
            qdata = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            qdata["status"] = "quota_paused"
            qdata["quota_reset_utc"] = reset_iso
            qdata["pause_reason"] = (
                "gemini_api_daily_quota_exhausted" if is_gemini else "youtube_api_daily_quota_exhausted"
            )
            manifest_path.write_text(yaml.safe_dump(qdata, sort_keys=False), encoding="utf-8")
            print(f"[short-release] Manifest {manifest_path.name} marked as quota_paused.")
        except Exception as save_err:
            print(f"[short-release] Failed to update queue manifest: {save_err}")
    stage_dir.mkdir(parents=True, exist_ok=True)
    result = {
        **base_result,
        "uploaded": False,
        "paused": True,
        "status": "quota_paused",
        "pause_reason": "quota_exceeded",
        "quota_reset_utc": reset_iso,
    }
    (stage_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_short_release(
    short_key: str,
    dry_run: bool = False,
    skip_render: bool = False,
    force: bool = False,
    manifest_path: Path | None = None,
) -> dict:
    edition = resolve_edition(short_key)
    if edition is None:
        raise RuntimeError(f"Unknown Short edition {short_key!r}; expected one of {sorted(EDITIONS)}")

    doc = _build_script_doc(edition)
    published_record = PUBLISHED_DIR / f"{edition.slug}.md"
    stage_dir = OUTPUT_DIR / edition.slug

    legacy_video_ids: list[str] = []
    desired_privacy: str | None = None
    desired_publish_at: str | None = None
    if manifest_path and manifest_path.is_file():
        mdata = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        # Only explicit force/force_reupload flag overrides duplicate protection
        if bool(mdata.get("force")) or bool(mdata.get("force_reupload")):
            force = True
        if mdata.get("privacy"):
            desired_privacy = str(mdata.get("privacy")).strip().lower()
        if mdata.get("publish_at"):
            desired_publish_at = str(mdata.get("publish_at")).strip()
        for vid in mdata.get("legacy_video_ids") or []:
            if isinstance(vid, str) and vid.strip():
                legacy_video_ids.append(vid.strip())

    previous_video_id = _read_previous_video_id(published_record)
    if previous_video_id and previous_video_id not in legacy_video_ids:
        legacy_video_ids.append(previous_video_id)

    if published_record.is_file() and not dry_run and not force:
        if manifest_path and manifest_path.is_file():
            manifest_path.unlink()
        print(f"[short-release] 🛑 DUPLICATE PREVENTED: {edition.slug} is already recorded in {published_record.relative_to(REPO_ROOT)}. Skipping upload.")
        print(f"::notice title=Short already published::`{edition.slug}` is recorded as "
              f"{previous_video_id or 'unknown'}; nothing was uploaded.")
        return {
            "uploaded": False,
            "duplicate_prevented": True,
            "video_id": previous_video_id,
            "message": f"Already published as {previous_video_id}",
        }

    if not dry_run:
        _validate_channel_niche(doc)

    _require_production_prerequisites(
        doc,
        dry_run,
        CONFIG.youtube_refresh_token,
        CONFIG.youtube_client_id,
        CONFIG.youtube_client_secret,
    )

    video_path = REPO_ROOT / "social" / f"{short_key}.mp4"
    sources_path = REPO_ROOT / "output" / "short-stock" / short_key / "scene-sources.json"

    from .quota_handler import GeminiQuotaExceededError, QuotaExceededError

    if not skip_render:
        try:
            _ensure_narration(short_key)
        except (QuotaExceededError, GeminiQuotaExceededError) as exc:
            return _pause_manifest_on_quota(
                manifest_path,
                stage_dir,
                exc,
                {"id": edition.job_id, "key": edition.key, "slug": edition.slug,
                 "title": edition.title, "format": "short", "dry_run": dry_run},
            )
        render_env = dict(os.environ)
        if render_env.get("SHORT_DISABLE_STOCK_BROLL", "").strip().lower() in {"1", "true", "yes", "on"}:
            render_env["ENABLE_STOCK_BROLL"] = "0"
            render_env["ENABLE_KEYLESS_SOURCES"] = "0"
        else:
            render_env["ENABLE_STOCK_BROLL"] = "1"
            render_env["ENABLE_KEYLESS_SOURCES"] = "1"
        cmd = [sys.executable, str(REPO_ROOT / "tools" / "shorts.py"), short_key]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=render_env, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"tools/shorts.py {short_key} failed with exit code {proc.returncode}")

    probe = verify_short_render(video_path, sources_path)
    scenes = json.loads(sources_path.read_text(encoding="utf-8"))

    stage_dir = OUTPUT_DIR / edition.slug
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged_video = stage_dir / f"{edition.slug}.mp4"
    shutil.copy2(video_path, staged_video)
    shutil.copy2(sources_path, stage_dir / "scene-sources.json")

    from .thumbnail import generate_short_scroll_stopper_thumbnail

    if edition.niche == "faith and prayer" or "psalm" in edition.key or "prayer" in edition.key:
        hero_bg = REPO_ROOT / "image-search" / "short-prayer-cover-poster.jpg"
        kicker, line1, line2, tag = "PRAYER BEFORE SLEEP", "PSALM", "91", "DIVINE PROTECTION"
        if edition.key != "short-psalm91":
            m_book = re.search(
                r"(?i)\b((?:1|2)\s*(?:Timothy|Peter|Corinthians|John)|Psalm|Proverbs|Isaiah|Matthew|John|Philippians|Numbers|Romans)\s*(\d+)",
                f"{edition.title} {edition.key}",
            )
            if m_book:
                line1 = re.sub(r"\s+", " ", m_book.group(1)).strip().upper()
                line2 = m_book.group(2)
            else:
                m_num = re.search(r"psalm\s*(\d+)", f"{edition.key} {edition.title}", re.I)
                line2 = m_num.group(1) if m_num else "PEACE"
            try:
                from .short_script import load_spec, spec_path

                sp = spec_path(edition.key)
                if sp.is_file():
                    spec_obj = load_spec(sp)
                    if len(spec_obj.poster) >= 4:
                        kicker = spec_obj.poster[0][:28]
                        tag = spec_obj.poster[3][:28]
            except Exception:  # noqa: BLE001
                tag = "DIVINE PEACE"
        staged_thumb = generate_short_scroll_stopper_thumbnail(
            bg_path=hero_bg,
            out_path=stage_dir / "thumbnail.jpg",
            kicker=kicker,
            line1=line1,
            line2=line2,
            tag=tag,
        )
    else:
        hero_bg = REPO_ROOT / "image-search" / "short-enron-thumb-hero.jpg"
        if not hero_bg.is_file():
            hero_bg = REPO_ROOT / "image-search" / "short-enron-crash-poster.jpg"
        staged_thumb = generate_short_scroll_stopper_thumbnail(
            bg_path=hero_bg,
            out_path=stage_dir / "thumbnail.jpg",
        )

    result: dict = {
        "id": edition.job_id,
        "key": edition.key,
        "slug": edition.slug,
        "title": edition.title,
        "format": "short",
        "width": probe.width,
        "height": probe.height,
        "duration_seconds": round(probe.duration_seconds, 2),
        "scenes_verified": len(scenes),
        "video": str(staged_video),
        "thumbnail": str(staged_thumb),
        "dry_run": dry_run,
    }

    if not dry_run:
        from .quota_handler import (
            QuotaExceededError,
            GeminiQuotaExceededError,
            calculate_next_quota_reset_utc,
        )
        from .upload import (
            audit_channel_videos,
            delete_video,
            set_video_thumbnail,
            upload,
        )

        short_desc = edition.description
        if any(k in edition.niche.lower() for k in ("faith", "prayer", "scripture", "devotional")):
            try:
                from .shorts_bridge import enrich_short_description_with_bridge

                short_desc = enrich_short_description_with_bridge(edition.description, edition.key)
            except Exception as bridge_exc:  # noqa: BLE001
                print(f"[short-release] Notice: short bridge enrichment skipped: {bridge_exc}")

        try:
            up = upload(doc, staged_video, thumbnail_path=None, description=short_desc, privacy=desired_privacy, publish_at=desired_publish_at)
        except (QuotaExceededError, GeminiQuotaExceededError) as exc:
            reset_utc = getattr(exc, "reset_utc", None) or calculate_next_quota_reset_utc()
            reset_iso = reset_utc.isoformat()
            pause_label = "Gemini API" if isinstance(exc, GeminiQuotaExceededError) else "YouTube API"
            print(f"[short-release] Daily {pause_label} limit reached ($0.00 lock): {exc}. Pausing job until {reset_iso}...")
            if manifest_path and manifest_path.is_file():
                try:
                    qdata = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                    qdata["status"] = "quota_paused"
                    qdata["quota_reset_utc"] = reset_iso
                    qdata["pause_reason"] = "gemini_api_daily_quota_exceeded" if isinstance(exc, GeminiQuotaExceededError) else "youtube_api_daily_quota_exceeded"
                    manifest_path.write_text(yaml.safe_dump(qdata, sort_keys=False), encoding="utf-8")
                    print(f"[short-release] Manifest {manifest_path.name} marked as quota_paused.")
                except Exception as save_err:
                    print(f"[short-release] Failed to update queue manifest: {save_err}")
            result.update(
                {
                    "uploaded": False,
                    "paused": True,
                    "pause_reason": "quota_exceeded",
                    "quota_reset_utc": reset_iso,
                }
            )
            (stage_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

        if up.privacy_status == "duplicate_prevented":
            print(f"[short-release] YouTube upload skipped: duplicate video already live ({up.video_id}).")
            if manifest_path and manifest_path.is_file():
                manifest_path.unlink()
            result.update(
                {
                    "uploaded": False,
                    "duplicate_prevented": True,
                    "video_id": up.video_id,
                    "watch_url": f"https://youtu.be/{up.video_id}",
                    "shorts_url": f"https://www.youtube.com/shorts/{up.video_id}",
                }
            )
            (stage_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

        if not up.video_id:
            raise RuntimeError("YouTube upload returned no video ID; leaving published ledger untouched.")

        # Shorts cannot take custom thumbnails: thumbnails.set fails for them, and
        # the call still costs quota. Record it instead of paying for a known failure.
        thumb_results: dict[str, str] = {up.video_id: "not_supported_for_shorts"}
        print("[short-release] skipping thumbnails.set: YouTube rejects custom thumbnails on Shorts")

        # Ensure every unlocked legacy Short on the channel stops carrying the old frame
        for old_vid in legacy_video_ids:
            if old_vid and old_vid != up.video_id:
                thumb_results[old_vid] = "not_supported_for_shorts"
                delete_video(old_vid)

        channel_audit = audit_channel_videos([up.video_id, *legacy_video_ids])
        active_video_id = up.video_id
        by_id = {row.get("id"): row for row in channel_audit if isinstance(row, dict) and row.get("id")}
        new_row = by_id.get(up.video_id, {})
        if new_row.get("uploadStatus") == "rejected":
            for cand_id in legacy_video_ids:
                cand_row = by_id.get(cand_id, {})
                if cand_row.get("uploadStatus") in {"processed", "uploaded"}:
                    active_video_id = cand_id
                    break

        active_watch_url = f"https://youtu.be/{active_video_id}"
        shorts_url = f"https://www.youtube.com/shorts/{active_video_id}"
        _close_superseded_tickets(edition.title, shorts_url)
        result.update(
            {
                "uploaded": True,
                "video_id": active_video_id,
                "uploaded_video_id": up.video_id,
                "watch_url": active_watch_url,
                "shorts_url": shorts_url,
                "privacy_status": up.privacy_status,
                "thumbnail_results": thumb_results,
                "channel_audit": channel_audit,
            }
        )
        print(f"[short-release] active short {shorts_url} (uploaded={up.video_id}, privacy={up.privacy_status})")
        _open_release_ticket(doc, active_watch_url, up.privacy_status, active_video_id)
        _write_published_record(
            published_record,
            edition,
            active_video_id,
            active_watch_url,
            up.privacy_status,
            probe,
            len(scenes),
            thumbnail_results=thumb_results,
            channel_audit=channel_audit,
        )
        if manifest_path and manifest_path.is_file():
            manifest_path.unlink()

    (stage_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_env:
        with open(summary_env, "a", encoding="utf-8") as fh:
            fh.write(f"### 🎬 {edition.title}\n\n")
            fh.write(f"- edition: `{edition.key}` (`{probe.width}x{probe.height}`, {probe.duration_seconds:.1f}s)\n")
            fh.write(f"- cleared scenes verified: `{len(scenes)}/{len(scenes)}`\n")
            if result.get("shorts_url"):
                fh.write(f"- shorts link: {result['shorts_url']}\n")
                fh.write(f"- watch link: {result['watch_url']}\n")
                fh.write(f"- privacy: `{result['privacy_status']}`\n")
    return result


def _author_missing_short_specs() -> list[dict]:
    """Let the brain write the scene specs the queue is waiting on.

    A Short is data, so this is not a human step: the brain authors the spec,
    validation rejects anything implausible, and the manifest flips to approved
    only once a renderer exists. If the brain cannot author, nothing is fabricated
    and the queue keeps reporting itself as stalled.
    """
    try:
        rows = queue_report()
    except Exception as exc:  # noqa: BLE001
        print(f"[short-release] cannot inspect queue for authoring: {exc}")
        return []
    if not any(r["verdict"] == "needs_renderer" for r in rows):
        return []
    try:
        from .gemini_brain import GeminiBrain
        authored = GeminiBrain().author_missing_shorts()
    except Exception as exc:  # noqa: BLE001
        print(f"[short-release] brain could not author missing Shorts: {exc}")
        return []
    for row in authored:
        print(f"[short-release] authoring {row['file']}: {row['verdict']} — {row['reason']}")
    return authored


def recent_short_published_within(
    hours: float = 3.0,
    published_dir: Path | None = None,
    now: datetime | None = None,
) -> tuple[Path, float] | None:
    """Return `(receipt_path, age_minutes)` if a Short published within `hours`."""
    if hours <= 0:
        return None
    directory = published_dir or PUBLISHED_DIR
    if not directory.is_dir():
        return None
    now_dt = now or datetime.now(timezone.utc)
    newest: tuple[Path, float] | None = None
    for path in sorted(directory.glob("short-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if "youtube_video_id:" not in text:
                continue
            m = re.search(r'^published_at:\s*"?([^"\n]+)"?', text, re.M)
            if not m:
                continue
            when = datetime.fromisoformat(m.group(1).strip().replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            continue
        age_sec = (now_dt - when).total_seconds()
        if 0 <= age_sec < hours * 3600.0:
            age_min = age_sec / 60.0
            if newest is None or age_min < newest[1]:
                newest = (path, age_min)
    return newest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render, verify, and upload an authored YouTube Short")
    parser.add_argument("--short", default="", help="Short edition key (e.g. short-psalm91)")
    parser.add_argument("--next", action="store_true", help="Process next approved Short in content/shorts-queue/")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    dry = (
        args.dry_run
        or CONFIG.dry_run
        or os.environ.get("DRY_RUN", "").strip().lower() in {"1", "true", "yes"}
    )
    CONFIG.ensure_dirs()
    try:
        manifest_path: Path | None = None
        short_key = args.short.strip()
        if args.next and not short_key:
            queued = select_next_queued_short()
            if queued is None:
                # Before declaring nothing to do, have the brain author the specs
                # the queue is blocked on.
                if _author_missing_short_specs():
                    queued = select_next_queued_short()
            if queued is None:
                rows = queue_report()
                ready = [r for r in rows if r["verdict"] == "ready"]
                blocked = [r for r in rows if r["verdict"] in {"needs_renderer", "unusable", "not_approved"}]
                print("[short-release] nothing to do — no Short in the queue can render right now.")
                for row in rows:
                    print(f"[short-release]   {row['file']}: {row['verdict']} — {row['reason']}")
                if blocked and os.environ.get("GITHUB_ACTIONS"):
                    print(f"::warning title=Shorts stalled::{len(blocked)} manifest(s) waiting, "
                          f"0 ready. A Short needs a scene script: authored by the brain into "
                          f"content/shorts-scripts/, or hand-written in tools/shorts.py.")
                if ready:
                    print(f"::error title=Shorts selection bug::{len(ready)} ready manifest(s) were not selected")
                    return 1
                return 0
            if not dry and not args.force and os.environ.get("GITHUB_ACTIONS"):
                try:
                    min_gap_h = float(os.environ.get("SHORTS_MIN_GAP_HOURS", "3.0"))
                except ValueError:
                    min_gap_h = 3.0
                recent = recent_short_published_within(hours=min_gap_h)
                if recent is not None:
                    rec_path, age_min = recent
                    print(
                        f"[short-release] Pacing guard: {rec_path.name} published {age_min:.0f}m ago "
                        f"(< {min_gap_h:.1f}h slot spacing); keeping queued Shorts paced for the next window."
                    )
                    print(
                        f"::notice title=Short pacing cooldown::Latest Short ({rec_path.name}) "
                        f"published {age_min:.0f}m ago; preserving queue for the next scheduled slot."
                    )
                    return 0
            manifest_path, short_key = queued
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::notice title=Short selected::`{short_key}` from "
                      f"{manifest_path.name if manifest_path else 'the built-in editions'}")
        elif not short_key:
            short_key = "short-psalm91"

        outcome = run_short_release(
            short_key=short_key,
            dry_run=dry,
            skip_render=args.skip_render,
            force=args.force,
            manifest_path=manifest_path,
        ) or {}

        # A returned dict is not a success. This is the same defect as the
        # long-form release: a quota pause returns quietly, `main` returns 0, and
        # the step is green with nothing uploaded. Say which happened.
        if outcome.get("paused"):
            print(f"::error title=Short did not upload::Gemini/YouTube quota is "
                  f"exhausted; `{short_key}` is paused until "
                  f"{outcome.get('quota_reset_utc')} and nothing was uploaded.", flush=True)
            return 3
        if outcome.get("uploaded"):
            print(f"::notice title=Short published::{(outcome.get('shorts_url') or outcome.get('watch_url') or '')}",
                  flush=True)
        elif outcome.get("duplicate_prevented"):
            print(f"::notice title=Short already live::`{short_key}` recorded as "
                  f"{outcome.get('video_id') or 'unknown'}; nothing re-uploaded.", flush=True)
        elif dry:
            print(f"::notice title=Short rendered only::`{short_key}` rendered under "
                  f"DRY_RUN; nothing uploaded.", flush=True)
        else:
            print(f"::notice title=Short finished with no upload::`{short_key}` — see the "
                  f"step summary for the reason.", flush=True)
    except Exception as exc:  # noqa: BLE001
        safe_msg = _scrub(f"{type(exc).__name__}: {exc}")
        print(f"[short-release] FAILED — {safe_msg}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{safe_msg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
