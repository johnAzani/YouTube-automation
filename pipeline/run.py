"""Pipeline orchestrator.

Usage:
  python -m pipeline.run --dry-run --job content/queue/0001-....md
  python -m pipeline.run --job content/queue/0001-....md          # render + upload
  python -m pipeline.run --dry-run --all                          # all approved jobs
  python -m pipeline.run --next                                   # next approved, render + upload

Stages: originality gate -> TTS -> assets -> assemble -> thumbnail -> upload
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import CONFIG, OUTPUT_DIR, QUEUE_DIR, PUBLISHED_DIR
from .originality import enforce, OriginalityError
from .script_doc import ScriptDoc, parse_script


def _log(msg: str) -> None:
    print(f"[run] {msg}", flush=True)


def select_jobs(all_flag: bool, job_path: str | None, next_flag: bool) -> list[Path]:
    if job_path:
        return [Path(job_path)]
    jobs = sorted(QUEUE_DIR.glob("*.md"))
    approved: list[Path] = []
    for j in jobs:
        try:
            doc = parse_script(j)
        except Exception as exc:  # noqa: BLE001
            _log(f"skip {j.name}: parse error {exc}")
            continue
        if doc.status == "approved":
            approved.append(j)
        elif all_flag:
            _log(f"skip {j.name}: status={doc.status} (only 'approved' jobs are built)")
    if next_flag:
        return approved[:1]
    return approved


def process(path: Path, dry_run: bool) -> dict:
    doc = parse_script(path)
    _log(f"job {doc.id} «{doc.title}» format={doc.format} words={doc.word_count}")

    # ---- 1. originality gate ------------------------------------------
    try:
        enforce(doc)
    except OriginalityError:
        if dry_run and doc.status != "approved":
            _log("originality gate would block this job — continuing dry-run anyway (status != approved)")
        else:
            raise

    out_dir = OUTPUT_DIR / doc.slug
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Shorts render vertical (9:16). Long-form stays landscape.
    if doc.format == "short":
        CONFIG.width = int(os.environ.get("SHORT_WIDTH", "1080"))
        CONFIG.height = int(os.environ.get("SHORT_HEIGHT", "1920"))
    else:
        CONFIG.width = int(os.environ.get("VIDEO_WIDTH", "1280"))
        CONFIG.height = int(os.environ.get("VIDEO_HEIGHT", "720"))

    # ---- 2. narration -------------------------------------------------
    from .tts import synthesize

    voice = doc.voice or CONFIG.voice
    narration = synthesize(doc.full_narration, out_dir, voice=voice)
    _log(f"tts engine={narration.engine} duration={narration.duration_seconds:.1f}s")

    # ---- 3. assets ----------------------------------------------------
    from .assets import fetch_scene_assets

    scene_assets: list[list[Path]] = []
    for scene in doc.scenes:
        query = scene.asset_query or scene.heading
        assets = fetch_scene_assets(query, scene.index, out_dir / "assets")
        scene_assets.append([a.path for a in assets])
        _log(f"  scene {scene.index:02d} «{scene.heading[:40]}» -> {len(assets)} asset(s)")

    # ---- 4. assemble --------------------------------------------------
    from .assemble import assemble, scene_durations_from_words

    durations = scene_durations_from_words(doc, narration.duration_seconds)
    final = assemble(doc, scene_assets, narration.audio_path, narration.srt_path, out_dir, durations)
    _log(f"rendered {final} ({final.stat().st_size / 1e6:.1f} MB)")

    # ---- 5. thumbnail (+ A/B variants for Studio Test & Compare) -------
    from .thumbnail import generate_thumbnail_variants

    bg = scene_assets[0][0] if scene_assets and scene_assets[0] else None
    thumbs = generate_thumbnail_variants(doc, bg, out_dir)
    thumb = thumbs[0]
    _log(f"thumbnail {thumb.name} + {len(thumbs) - 1} A/B variants")

    # ---- 5b. SEO metadata pack (chapters, description, tags) ----------
    from .metadata import write_metadata_pack

    pack = write_metadata_pack(doc, durations, out_dir)
    _log(f"metadata pack: {len(pack['chapters'])} chapters, "
         f"title {pack['title_report']['length']} chars "
         f"({'ok' if pack['title_report']['visible_mobile'] else 'LONG for mobile'})")

    result = {
        "id": doc.id,
        "slug": doc.slug,
        "title": doc.title,
        "video": str(final),
        "thumbnail": str(thumb),
        "thumbnail_variants": [str(t) for t in thumbs],
        "srt": str(narration.srt_path),
        "duration_seconds": narration.duration_seconds,
        "tts_engine": narration.engine,
        "metadata": pack,
        "dry_run": dry_run,
    }

    # ---- 5c. auto-Shorts (opt-in via MAKE_SHORTS=1) -------------------
    if os.environ.get("MAKE_SHORTS", "").lower() in {"1", "true", "yes"}:
        from .shorts import cut_shorts

        shorts = cut_shorts(doc, final, narration.srt_path, durations,
                            out_dir / "shorts", count=int(os.environ.get("SHORTS_COUNT", "2")))
        result["shorts"] = [str(s) for s in shorts]
        _log(f"cut {len(shorts)} Short(s)")

    # ---- 6. upload ----------------------------------------------------
    if not dry_run:
        if not CONFIG.youtube_refresh_token or not CONFIG.youtube_client_secret:
            _log("no YouTube credentials in env — skipping upload (render kept in output/)")
            result["uploaded"] = False
        else:
            from .upload import upload

            up = upload(doc, final, thumb, description=pack.get("description"))
            result.update({
                "uploaded": True,
                "video_id": up.video_id,
                "watch_url": up.watch_url,
                "privacy_status": up.privacy_status,
            })
            _log(f"uploaded {up.watch_url} (privacy={up.privacy_status})")
            _open_release_ticket(doc, up.watch_url, up.privacy_status)

        # move job file to published/ and stamp it
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        doc.meta["status"] = "published"
        doc.meta["published_on"] = stamp
        dest = PUBLISHED_DIR / path.name
        PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), dest)
        _log(f"job file moved to {dest}")

    (out_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    # GitHub Actions job summary (renders nicely on the run page)
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"### 🎬 {doc.title}\n\n")
            f.write(f"- slug: `{doc.slug}`\n- duration: {narration.duration_seconds:.0f}s\n")
            f.write(f"- tts: {narration.engine}\n- video: `{final.name}`\n")
            if result.get("watch_url"):
                f.write(f"- watch: {result['watch_url']}\n")
            f.write("\n> ⚠️ Human QC required before publish: thumbnail, title, intro hook (first 30s), "
                    "captions, and the originality checklist signature.\n")
    return result


def _open_release_ticket(doc: ScriptDoc, url: str, privacy: str) -> None:
    """Best-effort GitHub release ticket so a human publishes in 2 clicks."""
    import os
    import subprocess

    if not os.environ.get("GITHUB_ACTIONS"):
        return
    title = f"Release ticket: {doc.title}"
    body = (
        f"Video rendered and uploaded.\n\n"
        f"- Watch/Studio link: {url}\n- Current privacy: `{privacy}`\n\n"
        f"### Human publish checklist\n"
        f"- [ ] Thumbnail reviewed/replaced (CTR lever #1)\n"
        f"- [ ] Title tuned for search + curiosity\n"
        f"- [ ] First 30 seconds hook reviewed\n"
        f"- [ ] Captions spot-checked\n"
        f"- [ ] Description sources present\n"
        f"- [ ] **Publish / schedule in YouTube Studio**\n"
    )
    try:
        subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            check=False, capture_output=True, text=True,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"release ticket creation skipped: {exc!r}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="YouTube automation pipeline")
    p.add_argument("--job", help="path to a specific script markdown file")
    p.add_argument("--all", action="store_true", help="process every approved job")
    p.add_argument("--next", action="store_true", help="process the next approved job")
    p.add_argument("--dry-run", action="store_true", help="render only; never upload")
    args = p.parse_args(argv)

    dry = args.dry_run or CONFIG.dry_run or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    CONFIG.dry_run = dry
    CONFIG.ensure_dirs()

    paths = select_jobs(args.all, args.job, args.next)
    if not paths:
        _log("nothing to do — no approved jobs in content/queue/")
        return 0

    results = []
    for path in paths:
        try:
            results.append(process(path, dry))
        except Exception as exc:  # noqa: BLE001
            _log(f"FAILED {path}: {exc}")
            return 1

    _log(f"done: {len(results)} job(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
