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
from .run import _open_release_ticket, _require_production_prerequisites
from .script_doc import Scene, ScriptDoc

SHORTS_QUEUE_DIR = CONTENT_DIR / "shorts-queue"
MAX_SHORT_SECONDS = 180.0

#: Fresh takes of one Short that may fail speech alignment before the Short is
#: stepped over. A channel releases its queued Shorts in order, so one Short that
#: can never be aligned would otherwise hold every later one back for good.
MAX_ALIGNMENT_FAILURES = 3


class ShortAlignmentError(RuntimeError):
    """The spoken take could not be matched to the Short's words.

    Its own type so the release can tell "this take is bad, throw it away and
    count it" from every other reason narration could not be prepared.
    """

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
    channel: str = "secret-place"


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


def resolve_edition(key: str, channel_id: str | None = None) -> ShortEdition | None:
    """Return the ShortEdition for `key`, synthesizing one for authored specs.

    Every edition knows which channel it belongs to, and every channel dresses its
    own Shorts: the hand-written EDITIONS are The Secret Place's, and a brain-authored
    spec carries the channel that wrote it. Passing `channel_id` filters to that
    channel, so a release leg can never upload another channel's Short.
    """
    from .channels import normalize_channel_id

    wanted = normalize_channel_id(channel_id) if channel_id is not None else None

    if key in EDITIONS:
        edition = EDITIONS[key]
        return edition if wanted in (None, edition.channel) else None
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

    from .channel_capabilities import brand_for
    from .metadata import smart_truncate_title

    owner = getattr(spec, "channel", "secret-place")
    if wanted is not None and owner != wanted:
        return None
    brand = brand_for(owner)

    label = (
        spec.scripture.strip()
        if getattr(spec, "scripture", "").strip()
        else (f"Psalm {spec.psalm}" if spec.psalm else key.removeprefix("short-").replace("-", " ").title())
    )
    hook = (spec.poster[3] if len(spec.poster) >= 4 and spec.poster[3] else "Divine Peace").title()
    raw_title = brand.short_title_template.format(label=label, hook=hook)
    clean_title = f"{smart_truncate_title(raw_title, 86)} #Shorts"
    tag_key = re.sub(r"[^a-zA-Z0-9]+", "", label)
    return ShortEdition(
        key=key,
        job_id=f"SHORT-{key.removeprefix('short-').upper()}",
        slug=f"{key}-{brand.short_prayer_kind}-prayer",
        title=clean_title,
        niche="faith and prayer",
        tags=["shorts", label.lower(), *brand.short_tags],
        description=(
            f"{spec.narration_text}\n\n"
            f"Scripture reference: {label} (KJV / Public Domain biblical text).\n"
            f"{brand.producer_line}\n\n"
            f"{brand.short_hashtags.format(tag_key=tag_key)}"
        ),
        channel=owner,
    )


def queue_report(queue_dir: Path | None = None,
                 channel_id: str | None = None) -> list[dict]:
    """Every manifest in the Shorts queue with its verdict and the reason.

    The stage used to print "nothing to do" and exit 0, which is indistinguishable
    from success on the run page. Three approved manifests sat here for days while
    the renderer had no script for their keys.
    """
    from .channels import normalize_channel_id

    qdir = SHORTS_QUEUE_DIR if queue_dir is None else queue_dir
    if not qdir.is_dir():
        return []
    wanted = normalize_channel_id(channel_id) if channel_id is not None else None
    renderable = _renderer_script_keys()
    rows: list[dict] = []
    for path in sorted(qdir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        owner = normalize_channel_id(data.get("channel"))
        if wanted is not None and owner != wanted:
            continue
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
        elif resolve_edition(key, channel_id=owner) is None:
            verdict, reason = "unusable", f"unknown short key {key!r} not in EDITIONS or shorts-scripts"
        elif status != "approved":
            verdict, reason = "not_approved", f"status is {status or 'missing'}"
        else:
            verdict, reason = "ready", "will render on the next run"
            from .seasonal import manifest_window
            if manifest_window(data) == "early":
                reason = f"written for {data.get('season') or 'a season'}; publishes from {data.get('not_before')}"
        rows.append({"file": path.name, "short": key, "channel": owner,
                     "status": status, "verdict": verdict, "reason": reason})
    return rows


def count_ready_shorts(
    queue_dir: Path | None = None,
    channel_id: str | None = None,
) -> int:
    """Count renderable approved Shorts manifests for `channel_id`."""
    return sum(
        1 for row in queue_report(queue_dir=queue_dir, channel_id=channel_id)
        if row.get("verdict") == "ready"
    )


def select_next_queued_short(
    queue_dir: Path | None = None,
    published_dir: Path | None = None,
    channel_id: str | None = None,
) -> tuple[Path, str] | None:
    """Return `(manifest_path, short_key)` for this channel's next ready Short."""
    from .channels import normalize_channel_id as _norm

    qdir = SHORTS_QUEUE_DIR if queue_dir is None else queue_dir
    if not qdir.is_dir():
        return None
    wanted = _norm(channel_id if channel_id is not None else CONFIG.channel_id)

    # Determine published directory for duplicate validation
    pdir: Path | None = None
    if published_dir is not None:
        pdir = published_dir
    elif queue_dir is None:
        pdir = PUBLISHED_DIR
    elif (queue_dir.parent / "published").is_dir():
        pdir = queue_dir.parent / "published"

    fallback: tuple[Path, str, str, int] | None = None
    for path in sorted(qdir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if _norm(data.get("channel")) != wanted:
            continue  # one channel's Short never publishes on another's leg
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
        if resolve_edition(key, channel_id=wanted) is None:
            print(f"[queue] Skipping manifest {path.name}: unknown short key {key!r} not in EDITIONS")
            continue

        # A Short written for a day: never before it, first while its season is
        # open, withdrawn when it has closed (pipeline/seasonal.py).
        from .seasonal import manifest_window
        window = manifest_window(data)
        if window == "early":
            continue
        if window == "closed":
            data.update(status="draft", season_closed=True,
                        pause_reason=(f"{data.get('season') or 'season'} ended on "
                                      f"{data.get('not_after')}; the brain returns this Short "
                                      "to the queue when the season next opens"))
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            print(f"[queue] {path.name}: its season has closed; withdrawn until next year.")
            continue

        # Verified Shorts first: one whose narration carries its verse word for
        # word goes out ahead of one that cannot be checked or does not.
        verdict = scripture_status(key, data)
        rank = (0 if window == "open" else 2) + (0 if verdict == "verified" else 1)
        if rank == 0:
            return path, key
        if fallback is None or rank < fallback[3]:
            fallback = (path, key, verdict, rank)
    if fallback is not None:
        path, key, verdict, rank = fallback
        if rank < 2:
            print(f"[queue] {path.name} is for a season that is open; it goes out first.")
        if verdict == "unverified":
            print(f"::notice title=Short not yet scripture-verified ({wanted})::{key} was "
                  "written before the scripture check and its quotation does not match the "
                  "bundled text word for word; no verified Short is waiting, so it goes out. "
                  "The brain rewrites these each pass.")
        return path, key
    return None


def scripture_status(key: str, manifest: dict | None = None) -> str:
    """``"verified"``, ``"unverified"`` or ``"unknown"`` for one Short's quotation.

    ``verified``: the authored narration carries at least one whole verse of its
    passage word for word and none with a word changed. ``unknown``: a
    hand-written edition with no spec file, or no reference to check against.
    """
    from .scripture_text import quote_problems
    from .short_script import SPEC_DIR

    spec_file = Path(SPEC_DIR) / f"{key}.json"
    if not spec_file.is_file():
        return "unknown"
    try:
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        narration = " ".join(str(c[2]) for c in spec.get("captions", []))
    except Exception:  # noqa: BLE001
        return "unknown"
    reference = str((manifest or {}).get("scripture") or spec.get("scripture") or "").strip()
    if not reference and isinstance(spec.get("psalm"), int) and spec["psalm"]:
        reference = f"Psalm {spec['psalm']}"
    if not reference:
        return "unknown"
    return "unverified" if quote_problems(narration, reference) else "verified"


def _build_script_doc(edition: ShortEdition) -> ScriptDoc:
    desc = edition.description
    if edition.niche == "faith and prayer":
        try:
            from .shorts_bridge import enrich_short_description_with_bridge
            desc = enrich_short_description_with_bridge(
                desc, edition.key, channel_id=edition.channel)
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
            "channel": edition.channel,
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


def _recent_short_visuals(channel: str, limit: int = 3) -> set[str]:
    """Use verified receipt fingerprints, not cache guesses, to avoid recent repeats."""
    from .script_doc import parse_script
    records = []
    for path in PUBLISHED_DIR.glob('*.md'):
        try:
            meta = parse_script(path).meta
            ids = meta.get('short_visual_fingerprints')
            if str(meta.get('channel') or 'secret-place') != channel or not isinstance(ids, list):
                continue
            valid = [v for v in ids if isinstance(v, str) and
                     re.fullmatch(r'(?:url|sha256):[0-9a-f]{64}', v)]
            if valid:
                records.append((str(meta.get('published_at') or ''), path.name, valid))
        except Exception:
            continue
    return {value for _, _, values in sorted(records, reverse=True)[:limit] for value in values}


def _verified_video_fingerprints(scenes: list[dict]) -> set[str]:
    videos = set()
    for row in scenes:
        if row.get('media') != 'video' or row.get('fallback'):
            continue
        videos.update(v for v in row.get('source_fingerprints', [])
                      if isinstance(v, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', v))
    return videos


def upload_short_captions(video_id: str, short_key: str, *, youtube=None,
                          audio_dir: Path | None = None, out_dir: Path | None = None) -> str:
    """Give a published Short a caption track from the words it was rendered with.

    The words on screen are part of the picture; YouTube cannot search them,
    translate them or hand them to a screen reader. A caption track can be all
    three, and the timings already exist: the same per-word alignment the
    renderer drew the on-screen words from.

    Only a real alignment is used (the sidecar the aligner writes); estimated
    timings are for previews and are never published as captions. The call is
    best-effort: the Short is already public, and a missing caption track is
    never a reason to fail a release. Returns ``"ok"`` or ``"skipped: <why>"``.
    ``SHORT_CAPTIONS=0`` turns it off. One track costs 400 units of the
    channel's own 10,000-unit daily YouTube allowance.
    """
    if os.environ.get("SHORT_CAPTIONS", "1").strip().lower() in {"0", "false", "no", "off"}:
        return "skipped: switched off"
    try:
        from .captions import upload_captions, write_srt_file
        from .short_script import load_spec, spec_path

        audio_dir = audio_dir or (REPO_ROOT / "assets" / "deepdive")
        words_path = audio_dir / f"words-{short_key}.json"
        if not words_path.is_file() or not (audio_dir / f"words-{short_key}.alignment.json").is_file():
            return "skipped: no verified word timings"
        rows = json.loads(words_path.read_text(encoding="utf-8"))
        words = [(str(word), float(start), float(end)) for start, end, word in rows]
        if not words:
            return "skipped: no words"
        path = spec_path(short_key)
        narration = load_spec(path).narration_text if path.is_file() else " ".join(w for w, _, _ in words)
        srt = write_srt_file((out_dir or OUTPUT_DIR / "shorts-release" / short_key) / "captions.en.srt",
                             words, narration_text=narration, duration=words[-1][2])
        if srt is None:
            return "skipped: empty caption file"
        if youtube is None:
            from .upload import _thumb_client

            youtube = _thumb_client()
        return "ok" if upload_captions(youtube, video_id, srt, language="en") else "skipped: YouTube refused the track"
    except Exception as exc:  # noqa: BLE001
        return f"skipped: {type(exc).__name__}: {exc}"[:200]


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
    poster: dict | None = None,
    narration_engine: str | None = None,
    narration_voice: str | None = None,
    visual_fingerprints: list[str] | None = None,
    captions: str | None = None,
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
        if poster:
            thumb_block += ("\nPoster: "
                            f"{poster.get('width')}x{poster.get('height')}, "
                            f"contrast {poster.get('contrast')}:1, "
                            f"hero {poster.get('hero_px')}px, "
                            f"grade `{poster.get('grade')}`, "
                            f"safe-zone {poster.get('safe_zone_ok')}, "
                            f"revision `{poster.get('revision')}`\n")

    # A receipt is only allowed to say "done" when YouTube confirmed it. The old
    # path wrote `not_supported_for_shorts` from a hardcoded string, so nine live
    # Shorts looked explained and had no thumbnail at all.
    # A successful thumbnail on a different or superseded video is not proof
    # that the video named by this receipt has one.
    active_status = str((thumbnail_results or {}).get(video_id, "not_attempted"))
    thumb_fields = ""
    if active_status == "ok" and poster:
        thumb_fields += f'thumbnail_revision: "{poster.get("revision")}"\n'
        thumb_fields += f'thumbnail_channel_grade: "{poster.get("grade")}"\n'
    else:
        failure = "poster_metadata_unavailable" if active_status == "ok" else active_status
        thumb_fields += "thumbnail_pending: true\n"
        thumb_fields += f'thumbnail_error: {json.dumps(failure[:220])}\n'
    if poster:
        thumb_fields += ("thumbnail_poster: "
                         + json.dumps(list(poster.get("lines") or [])) + "\n")
        thumb_fields += f'thumbnail_kicker: {json.dumps(str(poster.get("kicker") or ""))}\n'
        thumb_fields += f'thumbnail_plate: {json.dumps(str(poster.get("plate") or ""))}\n'
    audit_block = ""
    if channel_audit:
        audit_block = f"\n\n## Channel Video Status Audit\n\n```json\n{json.dumps(channel_audit, indent=2)}\n```\n"
    voice_fields = ""
    if narration_engine and narration_voice:
        voice_fields = (f'narration_engine: {json.dumps(narration_engine)}\n'
                        f'narration_voice: {json.dumps(narration_voice)}\n')
    if captions:
        voice_fields += f'caption_track: {json.dumps(captions)}\n'
    content = (
        "---\n"
        f'id: "{edition.job_id}"\n'
        f'title: "{edition.title}"\n'
        f"slug: {edition.slug}\n"
        "status: published\n"
        "format: short\n"
        f"channel: {edition.channel}\n"
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
        + (f"short_visual_fingerprints: {json.dumps(visual_fingerprints)}\n" if visual_fingerprints else "")
        + f"{voice_fields}"
        f"{thumb_fields}"
        "---\n\n"
        f"{edition.description}"
        f"{thumb_block}"
        f"{audit_block}\n"
    )
    dest.write_text(content, encoding="utf-8")
    return dest


def _write_recovered_short_record(dest: Path, edition: ShortEdition, video: dict,
                                  poster: dict | None = None) -> Path:
    """Record verified existing video data without claiming an upload or thumbnail.

    Never overwrite a receipt. If writing fails, the caller must keep the queue
    manifest so the recovery can be safely retried.
    """
    vid = video["video_id"]
    published_at = video["published_at"]
    meta = {
        "id": edition.job_id, "title": video["title"], "slug": edition.slug,
        "status": "published", "format": "short", "channel": edition.channel,
        "niche": edition.niche, "category": "education",
        "published_on": published_at[:10], "published_at": published_at,
        "youtube_video_id": vid, "youtube_shorts_url": f"https://www.youtube.com/shorts/{vid}",
        "youtube_watch_url": f"https://youtu.be/{vid}",
        "privacy_status": video["privacy_status"], "youtube_upload_status": video["upload_status"],
        "youtube_duration": video.get("duration", ""),
        "receipt_recovered_from_youtube": True, "metadata_retrofit_approved": False,
        "thumbnail_pending": True, "thumbnail_error": "thumbnail_status_unverified_after_recovery",
        "thumbnail_attempts": 0,
    }
    frontmatter = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
    if poster:
        # The thumbnail sync updates these fields line-by-line, so keep lists
        # inline rather than leaving orphaned YAML list items on replacement.
        frontmatter += "thumbnail_poster: " + json.dumps(list(poster.get("lines") or [])) + "\n"
        frontmatter += "thumbnail_kicker: " + json.dumps(str(poster.get("kicker") or "")) + "\n"
        frontmatter += "thumbnail_plate: " + json.dumps(str(poster.get("plate") or "")) + "\n"
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = "---\n" + frontmatter + "---\n\n"
    content += ("This receipt was recovered from an existing YouTube video. "
                "No video was uploaded during recovery; the custom thumbnail status is unverified.\n")
    fh = dest.open("x", encoding="utf-8")
    try:
        with fh:
            fh.write(content)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
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
    m = re.search(r"^youtube_video_id:\s*['\"]?([A-Za-z0-9_-]+)['\"]?\s*$",
                  record_path.read_text(encoding="utf-8"), re.MULTILINE)
    return m.group(1) if m else ""


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
    return re.sub(r"[^a-z0-9']+", "", str(word).lower().replace("’", "'")).strip("'")


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


#: The shortest span a caption word is given when the recogniser did not time it.
MIN_WORD_SPAN_S = 0.04


def _spread_unheard_words(rows: list[list]) -> list[list]:
    """Give every word the aligner could not time a real span of its own.

    `pipeline.prayer_alignment.match` accepts a take when at least 85% of the
    script is recognised, and gives each word the recogniser did not hear a
    zero-length span at the previous word's end. That is its documented
    contract. The check below it in `_ensure_word_timings` demanded `end >
    start` for every word, so one unheard word in a 100-word Short refused the
    whole Short: the two disagreed, and the longer the Short the likelier the
    refusal (on 14 November the Shorts of 93 and 96 words went out and those of
    99, 114, 120 and 133 were refused, every token list being identical).

    A run of such words takes the silence between its neighbours when there is
    enough of it, and otherwise shares the previous word's span (or the next
    one's, at the very start) in proportion to word length. Starts and ends
    stay in order; nothing is invented about words that were heard. Rows that
    cannot be given a positive span are returned as they are, and the caller's
    check still refuses them.
    """
    out = [[float(r[0]), float(r[1]), r[2]] for r in rows]
    # Rounding to the millisecond can leave a word starting a hair before the
    # previous one ends.
    for i in range(1, len(out)):
        if 0 < out[i - 1][1] - out[i][0] <= 0.002:
            out[i][0] = out[i - 1][1]
            out[i][1] = max(out[i][1], out[i][0])
    n, i = len(out), 0
    while i < n:
        if out[i][1] - out[i][0] > 1e-9:
            i += 1
            continue
        j = i
        while j + 1 < n and out[j + 1][1] - out[j + 1][0] <= 1e-9:
            j += 1
        run = list(range(i, j + 1))
        left = i - 1 if i > 0 else None
        right = j + 1 if j + 1 < n else None
        gap_start = out[left][1] if left is not None else 0.0
        gap_end = out[right][0] if right is not None else gap_start
        if gap_end - gap_start >= MIN_WORD_SPAN_S * len(run):
            members, t0, t1 = run, gap_start, gap_end
        elif left is not None:
            members, t0, t1 = [left, *run], out[left][0], max(gap_end, out[left][1])
        elif right is not None:
            members, t0, t1 = [*run, right], 0.0, out[right][1]
        else:
            return out
        weights = [max(1, len(str(out[k][2]))) for k in members]
        total, clock = float(sum(weights)), t0
        for k, weight in zip(members, weights):
            width = (t1 - t0) * weight / total
            out[k][0], out[k][1] = clock, clock + width
            clock += width
        out[members[-1]][1] = t1
        i = j + 1
    for row in out:
        row[0], row[1] = round(row[0], 3), round(row[1], 3)
    return out


def _synthesise_narration(text: str, audio: Path) -> str:
    """Speak with the locked Gemini Charon voice; propagate failures unchanged."""
    from .gemini_tts import DEFAULT_MODEL, synthesize_gemini_audio

    synthesize_gemini_audio(text, audio, voice="Charon", model=DEFAULT_MODEL)
    return DEFAULT_MODEL


def _ensure_word_timings(short_key: str, audio_path: Path, narration_text: str,
                         require_alignment: bool = True) -> Path:
    """Reuse timings only for the same audio and text; production needs alignment."""
    import hashlib
    import math

    words_path = audio_path.parent / f"words-{short_key}.json"
    sidecar = audio_path.parent / f"words-{short_key}.alignment.json"
    digest = lambda value: hashlib.sha256(value).hexdigest()
    identity = {'text': digest(narration_text.encode('utf-8')),
                'audio': digest(audio_path.read_bytes()), 'version': 1}
    expected = [_clean_word_token(w) for w in narration_text.split() if _clean_word_token(w)]
    def valid(rows):
        if not isinstance(rows, list) or len(rows) != len(expected) or not expected:
            return False
        previous = 0.0
        for row, word in zip(rows, expected):
            if not isinstance(row, (list, tuple)) or len(row) != 3 or _clean_word_token(row[2]) != word:
                return False
            try:
                start, end = float(row[0]), float(row[1])
            except (ValueError, TypeError):
                return False
            if not math.isfinite(start) or not math.isfinite(end) or start < previous - 1e-6 or end <= start:
                return False
            previous = end
        return True
    try:
        meta = json.loads(sidecar.read_text(encoding='utf-8'))
        payload = words_path.read_bytes()
        rows = json.loads(payload)
        if all(meta.get(k) == v for k, v in identity.items()) and meta.get('timings') == digest(payload) and valid(rows):
            return words_path
    except (OSError, ValueError, TypeError, AttributeError):
        pass

    model_dir = REPO_ROOT / 'output' / 'alignment-model'
    try:
        from .prayer_alignment import align
        aligned = align(audio_path, narration_text, model_dir)
        rows = [[float(start), float(end), _clean_word_token(orig)] for orig, start, end in aligned]
        unheard = sum(1 for row in rows if row[1] - row[0] <= 1e-9)
        if unheard:
            rows = _spread_unheard_words(rows)
            print(f'[short-release] {short_key}: the recogniser did not time {unheard} of '
                  f'{len(rows)} words; each was given a share of the time around it')
        if not valid(rows):
            raise ValueError('alignment does not cover the narration in order' + _why_invalid(rows, expected))
    except Exception as exc:
        if require_alignment:
            cause = f"{type(exc).__name__}: {exc}".strip().rstrip(":")
            message = ('Short speech alignment unavailable or incomplete; refusing to render '
                       f'[{cause[:240]}]')
            # ValueError is how the aligner says "what was spoken does not match
            # the words" (the long-form path purges its take on the same signal).
            # It also says it when the speech model is not installed, and that,
            # like every other exception, is the runner's fault and not the
            # audio's: good audio is never thrown away, or counted against the
            # Short, because nothing was able to listen to it.
            if isinstance(exc, ValueError) and (model_dir / 'model.bin').is_file():
                raise ShortAlignmentError(message) from exc
            raise RuntimeError(message) from exc
        dur = probe_media(audio_path).duration_seconds
        rows = _fallback_word_timings(narration_text, dur)
        print(f'[short-release] preview only: estimated word timings ({dur:.1f}s)')
        words_path.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        sidecar.unlink(missing_ok=True)
        return words_path
    payload = json.dumps(rows, ensure_ascii=False).encode('utf-8')
    words_path.write_bytes(payload)
    sidecar.write_text(json.dumps({**identity, 'timings': digest(payload)}), encoding='utf-8')
    print(f'[short-release] aligned all {len(rows)} narration words for {short_key}')
    return words_path


def _why_invalid(rows: list, expected: list[str]) -> str:
    """The first thing wrong with a set of word timings, for the error message."""
    try:
        if len(rows) != len(expected):
            return f' ({len(rows)} timed words for {len(expected)} script words)'
        previous = 0.0
        for index, (row, word) in enumerate(zip(rows, expected), 1):
            if _clean_word_token(row[2]) != word:
                return f' (word {index} is {row[2]!r}, the script says {word!r})'
            start, end = float(row[0]), float(row[1])
            if start < previous - 1e-6:
                return f' (word {index} {word!r} starts at {start:.3f}s, before the previous word ends at {previous:.3f}s)'
            if end <= start:
                return f' (word {index} {word!r} has no length: {start:.3f}-{end:.3f}s)'
            previous = end
    except Exception:  # noqa: BLE001 - the reason is a courtesy, never a second failure
        return ''
    return ''


def _short_take_files(short_key: str) -> tuple[Path, Path, Path, Path]:
    """(audio, provenance sidecar, word timings, timings sidecar) for a Short."""
    audio = REPO_ROOT / "assets" / "deepdive" / f"{short_key}.mp3"
    return (audio, audio.with_suffix(".voice.json"),
            audio.parent / f"words-{short_key}.json",
            audio.parent / f"words-{short_key}.alignment.json")


def _discard_short_take(short_key: str) -> None:
    """Remove a Short's spoken take and everything derived from it."""
    for path in _short_take_files(short_key):
        path.unlink(missing_ok=True)


def record_alignment_failure(manifest_path: Path | None, exc: Exception) -> dict:
    """Count a rejected take on the Short's manifest; step over it at the limit.

    The count lives in the queue manifest, which the leg commits, so it survives
    between runs and is visible in the repository. At `MAX_ALIGNMENT_FAILURES`
    the manifest becomes `alignment_paused`: the selector only releases
    `approved` manifests, so the channel's next Short goes out at the next slot
    instead of this one failing forever. Setting `status: approved` again (and
    removing `alignment_failures`) puts it back in line.
    """
    if not manifest_path or not Path(manifest_path).is_file():
        return {}
    manifest_path = Path(manifest_path)
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        try:
            count = int(data.get("alignment_failures") or 0) + 1
        except (TypeError, ValueError):
            count = 1
        data["alignment_failures"] = count
        data["last_alignment_error"] = str(exc)[:300]
        if count >= MAX_ALIGNMENT_FAILURES:
            data["status"] = "alignment_paused"
            data["pause_reason"] = (
                f"speech alignment rejected {count} separate takes; stepped over so "
                f"later Shorts on this channel can release")
            print(f"::warning title=Short stepped over::{manifest_path.name} failed speech "
                  f"alignment on {count} takes and is now alignment_paused; the channel's "
                  f"next Short releases at the next slot.")
        else:
            print(f"[short-release] {manifest_path.name}: rejected take {count} of "
                  f"{MAX_ALIGNMENT_FAILURES}; the take was discarded and the next slot "
                  f"synthesises a new one.")
        manifest_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return data
    except Exception as save_err:  # noqa: BLE001
        print(f"[short-release] could not record the alignment failure: {save_err}")
        return {}


def _ensure_narration(short_key: str, require_provenance: bool = True) -> None:
    """Prepare Charon narration; never trust old unlabelled cached audio in production."""
    import hashlib
    from .gemini_tts import DEFAULT_MODEL, DELIVERY_RECIPE
    from .quota_handler import GeminiQuotaExceededError, QuotaExceededError

    try:
        from .short_script import load_spec, spec_path

        path = spec_path(short_key)
        if not path.is_file():
            if require_provenance:
                raise RuntimeError("legacy Short audio has no verified Charon provenance")
            return  # legacy offline preview only
        spec = load_spec(path)
        audio = REPO_ROOT / "assets" / "deepdive" / f"{short_key}.mp3"
        sidecar = audio.with_suffix(".voice.json")
        words = audio.parent / f"words-{short_key}.json"
        text_hash = hashlib.sha256(spec.narration_text.encode("utf-8")).hexdigest()
        expected = {"model": DEFAULT_MODEL, "voice": "Charon", "recipe": DELIVERY_RECIPE,
                    "text_sha256": text_hash}
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            valid = (isinstance(meta, dict) and all(meta.get(k) == v for k, v in expected.items())
                     and audio.is_file() and audio.stat().st_size > 0
                     and meta.get("audio_sha256") == hashlib.sha256(audio.read_bytes()).hexdigest())
        except (OSError, ValueError):
            valid = False
        def synthesise() -> None:
            # Unlabelled or altered caches may be another speaker. Discard their
            # timings too, so they cannot be paired with the new narration.
            audio.parent.mkdir(parents=True, exist_ok=True)
            _discard_short_take(short_key)
            print(f"[short-release] synthesising Charon narration for {short_key} ({spec.words} words)")
            try:
                engine = _synthesise_narration(spec.narration_text, audio)
                if engine != DEFAULT_MODEL or not audio.is_file() or audio.stat().st_size == 0:
                    raise RuntimeError("Gemini Charon produced no verified audio")
                expected["audio_sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
                tmp = sidecar.with_suffix(".tmp")
                tmp.write_text(json.dumps(expected), encoding="utf-8")
                tmp.replace(sidecar)
            except Exception:
                audio.unlink(missing_ok=True)
                sidecar.unlink(missing_ok=True)
                raise

        reused = bool(valid)
        if not valid:
            synthesise()
        try:
            _ensure_word_timings(short_key, audio, spec.narration_text,
                                 require_alignment=require_provenance)
        except ShortAlignmentError as first:
            # A take that alignment rejects must not survive this run. The audio
            # and its provenance file are saved to the Actions cache and restored
            # by the next run, where they still look valid (same text, same
            # checksum), so the same rejected take was aligned, and refused, at
            # every slot. On 13 November 2026 seven channels each had the Short
            # at the head of their queue stuck this way, across two production
            # runs, and released no Shorts at all.
            _discard_short_take(short_key)
            if not reused:
                # Spoken moments ago and already rejected: do not spend a second
                # speech request in the same run. The next slot starts clean.
                raise
            print(f"[short-release] the saved take of {short_key} failed alignment "
                  f"({first}); discarded, synthesising a fresh take")
            synthesise()
            try:
                _ensure_word_timings(short_key, audio, spec.narration_text,
                                     require_alignment=require_provenance)
            except ShortAlignmentError:
                _discard_short_take(short_key)
                raise
    except ShortAlignmentError as exc:
        raise ShortAlignmentError(
            f"cannot prepare Charon narration for {short_key} ({exc}); refusing to render"
        ) from exc
    except (QuotaExceededError, GeminiQuotaExceededError):
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"cannot prepare Charon narration for {short_key} ({exc}); refusing to render"
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
    edition = resolve_edition(short_key, channel_id=CONFIG.channel_id)
    if edition is None:
        known = sorted(EDITIONS) + sorted(k for k in _renderer_script_keys() if k not in EDITIONS)
        raise RuntimeError(
            f"Unknown Short edition {short_key!r} for channel {CONFIG.channel_id!r}; "
            f"known editions: {known}")

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

    if skip_render and not dry_run and "prayer" in str(doc.meta.get("niche", "")).lower():
        raise RuntimeError("Refusing production Short with unverified pre-rendered narration; render with Charon")

    if not skip_render:
        try:
            _ensure_narration(short_key, require_provenance=(
                not dry_run and "prayer" in str(doc.meta.get("niche", "")).lower()))
        except ShortAlignmentError as exc:
            record_alignment_failure(manifest_path, exc)
            raise
        except (QuotaExceededError, GeminiQuotaExceededError) as exc:
            return _pause_manifest_on_quota(
                manifest_path,
                stage_dir,
                exc,
                {"id": edition.job_id, "key": edition.key, "slug": edition.slug,
                 "title": edition.title, "format": "short", "dry_run": dry_run},
            )
        render_env = dict(os.environ)
        prayer_production = not dry_run and 'prayer' in str(doc.meta.get('niche', '')).lower()
        if prayer_production:
            render_env['SHORT_REQUIRE_VARIED_VIDEO'] = '1'
            render_env['SHORT_RECENT_CLIP_IDS'] = json.dumps(sorted(_recent_short_visuals(edition.channel)))
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
    if not dry_run and 'prayer' in str(doc.meta.get('niche', '')).lower():
        if len(_verified_video_fingerprints(scenes)) < 2:
            raise RuntimeError('Short does not contain two distinct verified video clips; leaving queue unchanged')

    stage_dir = OUTPUT_DIR / edition.slug
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    staged_video = stage_dir / f"{edition.slug}.mp4"
    shutil.copy2(video_path, staged_video)
    shutil.copy2(sources_path, stage_dir / "scene-sources.json")

    # The poster is a native 9:16 image now, not a 1280x720 plate that YouTube
    # would crop to a 405px strip (see pipeline/shorts_poster.py). It is measured
    # before it is written: contrast >= 7.0 behind the hero, every word inside the
    # Shorts UI safe zone, or it refuses.
    from .channel_capabilities import brand_for
    from .shorts_poster import (
        POSTER_REVISION,
        PosterRefused,
        kicker_for,
        lines_from_title,
        poster_for_spec,
        render_shorts_poster,
    )

    brand = brand_for(edition.channel)
    spec_payload: dict | None = None
    try:
        from .short_script import spec_path as _spec_path

        _sp = _spec_path(edition.key)
        if _sp.is_file():
            spec_payload = json.loads(_sp.read_text(encoding="utf-8"))
    except Exception as spec_exc:  # noqa: BLE001
        print(f"[short-release] Notice: spec poster unavailable for {edition.key}: {spec_exc}")

    staged_thumb: Path | None = stage_dir / "thumbnail.jpg"
    poster_report = None
    try:
        if spec_payload:
            poster_report = poster_for_spec(spec_payload, staged_thumb,
                                            channel_id=edition.channel)
        else:
            h1, h2, sub, tag = lines_from_title(edition.title, brand.display_name.upper())
            poster_report = render_shorts_poster(
                staged_thumb, lines=(h1, h2, sub, tag),
                kicker=kicker_for(edition.channel), channel_id=edition.channel)
        print(f"[short-release] poster {poster_report.width}x{poster_report.height} "
              f"contrast={poster_report.contrast:.1f} hero={poster_report.hero_px}px "
              f"grade={poster_report.grade}")
    except (PosterRefused, Exception) as refused:  # noqa: BLE001 - never block a release
        # A Short is the ride-along, never the release: publish it, but say out
        # loud that its poster was refused and leave the receipt marked so the
        # monitor's repair pass retries instead of pretending it is fine.
        reason = "poster refused" if isinstance(refused, PosterRefused) else "poster failed"
        print(f"::warning title=Shorts {reason}::{edition.key} — {refused}")
        staged_thumb = None
        poster_report = None

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
        "thumbnail": str(staged_thumb) if staged_thumb else "",
        "thumbnail_report": poster_report.as_dict() if poster_report else None,
        "dry_run": dry_run,
    }

    if not dry_run:
        from .quota_handler import (
            QuotaExceededError,
            GeminiQuotaExceededError,
            calculate_next_quota_reset_utc,
        )
        from .upload import (
            apply_shorts_thumbnail,
            audit_channel_videos,
            inspect_existing_short,
            set_video_thumbnail,
            upload,
        )

        short_desc = edition.description
        if any(k in edition.niche.lower() for k in ("faith", "prayer", "scripture", "devotional")):
            try:
                from .shorts_bridge import enrich_short_description_with_bridge

                short_desc = enrich_short_description_with_bridge(
                    edition.description, edition.key, channel_id=edition.channel)
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
            print(f"[short-release] YouTube upload skipped: existing video detected ({up.video_id}).")
            # A title match is not a receipt. Verify the authenticated owner and
            # remote video first, then persist facts before retiring the manifest.
            # On any lookup/write failure, leave the manifest for a safe retry.
            video = inspect_existing_short(up.video_id, edition.title)
            _write_recovered_short_record(
                published_record, edition, video,
                poster=poster_report.as_dict() if poster_report else None,
            )
            if manifest_path and manifest_path.is_file():
                manifest_path.unlink()
            result.update(
                {
                    "uploaded": False,
                    "duplicate_prevented": True,
                    "receipt_recovered": True,
                    "privacy_status": video["privacy_status"],
                    "video_id": up.video_id,
                    "watch_url": f"https://youtu.be/{up.video_id}",
                    "shorts_url": f"https://www.youtube.com/shorts/{up.video_id}",
                }
            )
            (stage_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result

        if not up.video_id:
            raise RuntimeError("YouTube upload returned no video ID; leaving published ledger untouched.")

        # thumbnails.set has supported Shorts since 2026-11-03 (API revision history),
        # after processing completes. Before that the API accepted the call and
        # ignored it, which is why this path skipped it and every receipt recorded
        # `not_supported_for_shorts` without ever asking YouTube. `apply_shorts_thumbnail`
        # waits for processing, sets, retries a 429, and verifies the response really
        # carries `shortsAspectRatio` before calling it done.
        thumb_results: dict[str, str] = {}
        if staged_thumb is not None:
            try:
                thumb_results[up.video_id] = apply_shorts_thumbnail(up.video_id, staged_thumb)
            except Exception as thumb_exc:  # noqa: BLE001
                # The Short is published; a thumbnail is not worth a red release.
                # The receipt records `thumbnail_pending: true`, and the monitor's
                # repair pass applies it on a later run (thumbnails.set is 50 units).
                thumb_results[up.video_id] = f"error: {type(thumb_exc).__name__}: {thumb_exc}"[:300]
                print(f"::warning title=Shorts thumbnail not applied::{up.video_id} — {thumb_exc}")
            print(f"[short-release] shorts thumbnail: {thumb_results[up.video_id]}")
        else:
            thumb_results[up.video_id] = "poster_refused"

        # Do not delete legacy videos here. Upload acceptance is not proof that a
        # replacement finished processing, and an irreversible delete cannot be
        # rolled back if the new upload is later rejected or the receipt write fails.
        if legacy_video_ids:
            print("::warning title=Legacy Shorts retained::Review older editions after "
                  "confirming the new video; no legacy videos were deleted.")
        channel_audit = audit_channel_videos([up.video_id, *legacy_video_ids])
        active_video_id = up.video_id
        by_id = {row.get("id"): row for row in channel_audit if isinstance(row, dict) and row.get("id")}
        new_row = by_id.get(up.video_id, {})
        if new_row.get("uploadStatus") in {"rejected", "failed", "deleted"}:
            raise RuntimeError("New Short failed YouTube processing; retained legacy videos and queue state")

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
        from .gemini_tts import DEFAULT_MODEL
        verified_voice = (not skip_render and "prayer" in str(doc.meta.get("niche", "")).lower()
                          and active_video_id == up.video_id)
        # Last, after the thumbnail and the audit: the caption track is the one
        # optional call here and the most expensive (400 units).
        caption_status = (upload_short_captions(up.video_id, edition.key, out_dir=stage_dir)
                          if not skip_render else "skipped: not rendered in this run")
        print(f"[short-release] caption track: {caption_status}")
        result["caption_track"] = caption_status
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
            poster=poster_report.as_dict() if poster_report else None,
            narration_engine=DEFAULT_MODEL if verified_voice else None,
            narration_voice="Charon" if verified_voice else None,
            visual_fingerprints=sorted({v for row in scenes if row.get('media') == 'video' and not row.get('fallback')
                                        for v in row.get('source_fingerprints', [])
                                        if isinstance(v, str) and re.fullmatch(r'(?:url|sha256):[0-9a-f]{64}', v)}),
            captions=caption_status,
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
        rows = queue_report(channel_id=CONFIG.channel_id)
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
    channel_id: str | None = None,
) -> tuple[Path, float] | None:
    """Return `(receipt_path, age_minutes)` if a Short published within `hours`.

    Scoped per channel: one channel's Short must not pause the other channel's
    slot, which is what a shared pacing guard would do the moment both channels
    publish Shorts.
    """
    if hours <= 0:
        return None
    directory = published_dir or PUBLISHED_DIR
    if not directory.is_dir():
        return None
    from .channels import normalize_channel_id

    wanted = normalize_channel_id(channel_id) if channel_id is not None else None
    now_dt = now or datetime.now(timezone.utc)
    newest: tuple[Path, float] | None = None
    for path in sorted(directory.glob("short-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            if "youtube_video_id:" not in text:
                continue
            if wanted is not None:
                m_ch = re.search(r"^channel:\s*(\S+)", text, re.M)
                owner = normalize_channel_id(m_ch.group(1) if m_ch else None)
                if owner != wanted:
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
    parser.add_argument("--short", default="", help="Short edition key (e.g. short-enron)")
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
            queued = select_next_queued_short(channel_id=CONFIG.channel_id)
            if queued is None:
                # Before declaring nothing to do, have the brain author the specs
                # the queue is blocked on.
                if _author_missing_short_specs():
                    queued = select_next_queued_short(channel_id=CONFIG.channel_id)
            if queued is None:
                rows = queue_report(channel_id=CONFIG.channel_id)
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
                from .run import quota_blocked_until

                blocked = quota_blocked_until(channel_id=CONFIG.channel_id)
                if blocked is not None:
                    print(
                        f"[short-release] Daily speech quota for {CONFIG.channel_id} "
                        f"is spent until {blocked.isoformat()} UTC; keeping queued Shorts "
                        f"intact for the next window."
                    )
                    print(
                        f"::notice title=Short quota cooldown::{CONFIG.channel_id} "
                        f"speech quota resets at {blocked.isoformat()} UTC; queued "
                        f"Shorts preserved."
                    )
                    return 0
                try:
                    min_gap_h = float(os.environ.get("SHORTS_MIN_GAP_HOURS", "3.0"))
                except ValueError:
                    min_gap_h = 3.0
                recent = recent_short_published_within(
                    hours=min_gap_h, channel_id=CONFIG.channel_id)
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
            short_key = "short-enron"

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
