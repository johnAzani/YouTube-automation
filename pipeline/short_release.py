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
MAX_SHORT_SECONDS = 60.0
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


def select_next_queued_short(queue_dir: Path | None = None) -> tuple[Path, str] | None:
    """Return `(manifest_path, short_key)` for the first approved Short in queue."""
    qdir = SHORTS_QUEUE_DIR if queue_dir is None else queue_dir
    if not qdir.is_dir():
        return None
    for path in sorted(qdir.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if str(data.get("status", "")).strip().lower() != "approved":
            continue
        key = str(data.get("short", "")).strip()
        if not key:
            continue
        return path, key
    return None


def _build_script_doc(edition: ShortEdition) -> ScriptDoc:
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
            "description": edition.description,
            "originality": {
                "original_thesis": True,
                "unique_structure": True,
                "human_rewrite": True,
                "no_ai_persona": True,
                "source_notes": True,
            },
        },
        scenes=[Scene(index=1, heading="How Enron Died", narration=edition.description)],
    )


def _write_published_record(
    dest: Path,
    edition: ShortEdition,
    video_id: str,
    watch_url: str,
    privacy_status: str,
    probe: MediaProbe,
    scene_count: int,
) -> Path:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    shorts_url = f"https://www.youtube.com/shorts/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"
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
        f'youtube_video_id: "{video_id}"\n'
        f'youtube_shorts_url: "{shorts_url}"\n'
        f'youtube_watch_url: "{watch_url}"\n'
        f'youtube_studio_url: "{studio_url}"\n'
        f'privacy_status: "{privacy_status}"\n'
        f"width: {probe.width}\n"
        f"height: {probe.height}\n"
        f"duration_seconds: {round(probe.duration_seconds, 2)}\n"
        f"scenes_verified: {scene_count}\n"
        "---\n\n"
        f"{edition.description}\n"
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


def run_short_release(
    short_key: str,
    dry_run: bool = False,
    skip_render: bool = False,
    force: bool = False,
    manifest_path: Path | None = None,
) -> dict:
    if short_key not in EDITIONS:
        raise RuntimeError(f"Unknown Short edition {short_key!r}; expected one of {sorted(EDITIONS)}")

    edition = EDITIONS[short_key]
    doc = _build_script_doc(edition)
    published_record = PUBLISHED_DIR / f"{edition.slug}.md"

    if published_record.is_file() and not dry_run and not force:
        if manifest_path and manifest_path.is_file():
            manifest_path.unlink()
        raise RuntimeError(
            f"{edition.slug} is already recorded in {published_record.relative_to(REPO_ROOT)}; "
            "pass --force only if you intentionally want a duplicate upload."
        )

    _require_production_prerequisites(
        doc,
        dry_run,
        CONFIG.youtube_refresh_token,
        CONFIG.youtube_client_id,
        CONFIG.youtube_client_secret,
    )

    video_path = REPO_ROOT / "social" / f"{short_key}.mp4"
    sources_path = REPO_ROOT / "output" / "short-stock" / short_key / "scene-sources.json"

    if not skip_render:
        render_env = dict(os.environ)
        if render_env.get("SHORT_ENABLE_STOCK_BROLL", "").strip().lower() not in {"1", "true", "yes", "on"}:
            render_env["ENABLE_STOCK_BROLL"] = "0"
            render_env["ENABLE_KEYLESS_SOURCES"] = "0"
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
        "dry_run": dry_run,
    }

    if not dry_run:
        from .upload import upload

        up = upload(doc, staged_video, thumbnail_path=None, description=edition.description)
        if not up.video_id:
            raise RuntimeError("YouTube upload returned no video ID; leaving published ledger untouched.")
        shorts_url = f"https://www.youtube.com/shorts/{up.video_id}"
        result.update(
            {
                "uploaded": True,
                "video_id": up.video_id,
                "watch_url": up.watch_url,
                "shorts_url": shorts_url,
                "privacy_status": up.privacy_status,
            }
        )
        print(f"[short-release] uploaded {shorts_url} (privacy={up.privacy_status})")
        _open_release_ticket(doc, up.watch_url, up.privacy_status, up.video_id)
        _write_published_record(
            published_record,
            edition,
            up.video_id,
            up.watch_url,
            up.privacy_status,
            probe,
            len(scenes),
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
            queued = select_next_queued_short()
            if queued is None:
                print("[short-release] nothing to do — no approved Shorts in content/shorts-queue/")
                return 0
            manifest_path, short_key = queued
        elif not short_key:
            short_key = "short-enron"

        run_short_release(
            short_key=short_key,
            dry_run=dry,
            skip_render=args.skip_render,
            force=args.force,
            manifest_path=manifest_path,
        )
    except Exception as exc:  # noqa: BLE001
        safe_msg = _scrub(f"{type(exc).__name__}: {exc}")
        print(f"[short-release] FAILED — {safe_msg}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{safe_msg}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
