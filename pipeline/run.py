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
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import CONFIG, OUTPUT_DIR, QUEUE_DIR, PUBLISHED_DIR, REPO_ROOT
from .originality import enforce, OriginalityError
from .script_doc import ScriptDoc, parse_script


def _log(msg: str) -> None:
    print(f"[run] {msg}", flush=True)


def _require_production_prerequisites(
    doc: ScriptDoc,
    dry_run: bool,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> None:
    """Fail closed before rendering when a production upload cannot be completed."""
    if dry_run:
        return
    if doc.status != "approved":
        raise RuntimeError(
            f"Refusing production run for job {doc.id}: status={doc.status!r}; "
            "set status to 'approved' only after human review."
        )
    missing = []
    if not refresh_token:
        missing.append("YOUTUBE_REFRESH_TOKEN")
    if not client_id:
        missing.append("YOUTUBE_CLIENT_ID")
    if not client_secret:
        missing.append("YOUTUBE_CLIENT_SECRET")
    if missing:
        raise RuntimeError(
            "Refusing production run because required YouTube credential(s) are missing: "
            + ", ".join(missing)
            + ". Use --dry-run to render without uploading; the queue job will remain unchanged."
        )


def _require_real_narration(engine: str, dry_run: bool) -> None:
    """Placeholder audio is useful for offline renders, but never publishable."""
    if not dry_run and engine not in ("edge-tts", "gemini-api"):
        raise RuntimeError(
            f"Refusing production upload: narration engine is {engine!r} (placeholder audio). "
            "Fix the TTS failure and rerun; placeholder audio must not be published."
        )


def _mark_job_uploaded(path: Path, doc: ScriptDoc, video_id: str) -> Path:
    """Move and stamp a queue job only after YouTube confirms an uploaded video ID."""
    if not video_id:
        raise RuntimeError("YouTube returned no video ID; leaving the queue job untouched.")
    dest = PUBLISHED_DIR / path.name
    if dest.exists():
        raise RuntimeError(f"Published record already exists at {dest}; leaving the queue job untouched.")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = path.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not frontmatter:
        raise RuntimeError(f"Cannot stamp {path}: missing YAML frontmatter; leaving the queue job untouched.")
    metadata = frontmatter.group(1)
    metadata, replacements = re.subn(r"(?m)^status\s*:.*$", "status: published", metadata, count=1)
    if not replacements:
        raise RuntimeError(f"Cannot stamp {path}: missing top-level status; leaving the queue job untouched.")
    for key, value in (("published_on", stamp), ("youtube_video_id", video_id)):
        line = f"{key}: {json.dumps(value)}"
        pattern = rf"(?m)^{re.escape(key)}\s*:.*$"
        if re.search(pattern, metadata):
            metadata = re.sub(pattern, line, metadata, count=1)
        else:
            metadata += f"\n{line}"

    updated = f"---\n{metadata}\n---{frontmatter.group('tail')}"
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(updated, encoding="utf-8")
    temp_path.replace(path)

    doc.meta["status"] = "published"
    doc.meta["published_on"] = stamp
    doc.meta["youtube_video_id"] = video_id
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), dest)
    _log(f"job file moved to {dest}")
    return dest


def _validate_finance_niche(doc: ScriptDoc) -> None:
    """Keep every automated channel upload inside approved channel niches."""
    niche = str(doc.meta.get("niche", "")).strip().lower()
    allowed = ("finance", "financial", "business", "markets", "economics", "faith", "prayer", "scripture", "devotional")
    if not any(term in niche for term in allowed):
        raise RuntimeError(
            f"Refusing out-of-niche job {doc.id}: niche={niche or '(missing)'!r}. "
            "This channel publishes finance, business, markets, or economics only."
        )


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
    _validate_finance_niche(doc)
    _log(f"job {doc.id} «{doc.title}» format={doc.format} words={doc.word_count}")

    # ---- 1. originality gate ------------------------------------------
    try:
        enforce(doc)
    except OriginalityError:
        if dry_run and doc.status != "approved":
            _log("originality gate would block this job — continuing dry-run anyway (status != approved)")
        else:
            raise

    _require_production_prerequisites(
        doc,
        dry_run,
        CONFIG.youtube_refresh_token,
        CONFIG.youtube_client_id,
        CONFIG.youtube_client_secret,
    )

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

    # ---- 2. narration & render path ----------------------------------
    authored_master = REPO_ROOT / "docs" / "media" / "deep-dive-psalm91.mp4"
    if not authored_master.is_file():
        authored_master = REPO_ROOT / "social" / "deep-dive-psalm91.mp4"
    is_authored_prayer = (doc.id == "0008" or "psalm-91" in doc.slug) and authored_master.is_file()

    if is_authored_prayer:
        _log(f"found authored DOCOGA REELS v2 master: {authored_master.name}")
        final = out_dir / f"{doc.slug}.mp4"
        shutil.copy2(authored_master, final)
        _log(f"using authored DOCOGA REELS v2 widescreen master {final} ({final.stat().st_size / 1e6:.1f} MB)")

        authored_thumb = REPO_ROOT / "docs" / "media" / "psalm-91-longform-thumbnail.jpg"
        thumb = out_dir / "thumbnail.jpg"
        if authored_thumb.is_file():
            shutil.copy2(authored_thumb, thumb)
            thumbs = [thumb]
            _log(f"using authored 16:9 widescreen thumbnail {thumb.name}")
        else:
            from .thumbnail import generate_thumbnail_variants
            thumbs = generate_thumbnail_variants(doc, None, out_dir)
            thumb = thumbs[0]

        durations = [6.2, 5.4, 4.7, 3.7, 4.4, 4.1, 4.2, 6.85]
        from .metadata import write_metadata_pack
        pack = write_metadata_pack(doc, durations, out_dir)
        _log(f"metadata pack: {len(pack['chapters'])} chapters, "
             f"title {pack['title_report']['length']} chars "
             f"({'ok' if pack['title_report']['visible_mobile'] else 'LONG for mobile'})")

        narration_dur = 39.55
        narration_engine = "gemini-3.8-flash-tts"
        srt_path_str = ""
    else:
        from .tts import synthesize

        voice = doc.voice or CONFIG.voice
        narration = synthesize(doc.full_narration, out_dir, voice=voice)
        _log(f"tts engine={narration.engine} duration={narration.duration_seconds:.1f}s")
        _require_real_narration(narration.engine, dry_run)

        # ---- 3. assets ----------------------------------------------------
        from .assets import fetch_scene_assets, attempts_summary

        scene_assets: list[list[Path]] = []
        for scene in doc.scenes:
            query = scene.asset_query or scene.heading
            assets = fetch_scene_assets(query, scene.index, out_dir / "assets", allow_generated=False)
            if not assets:
                raise RuntimeError(
                    f"Scene {scene.index} has no licensed, downloadable video or photo for {query!r}; "
                    "refusing to substitute a generic title card. Add a usable free image/video or revise the query."
                    + attempts_summary(scene.index, out_dir / "assets")
                )
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

        narration_dur = narration.duration_seconds
        narration_engine = narration.engine
        srt_path_str = str(narration.srt_path)

    result = {
        "id": doc.id,
        "slug": doc.slug,
        "title": doc.title,
        "video": str(final),
        "thumbnail": str(thumb),
        "thumbnail_variants": [str(t) for t in thumbs],
        "srt": srt_path_str,
        "duration_seconds": narration_dur,
        "tts_engine": narration_engine,
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
        from .upload import upload

        upload_thumb = None if doc.format == "short" else thumb
        up = upload(doc, final, upload_thumb, description=pack.get("description"))
        if not up.video_id:
            raise RuntimeError("YouTube upload returned no video ID; leaving the queue job untouched.")
        result.update({
            "uploaded": True,
            "video_id": up.video_id,
            "watch_url": up.watch_url,
            "privacy_status": up.privacy_status,
        })
        _log(f"uploaded {up.watch_url} (privacy={up.privacy_status})")
        _open_release_ticket(doc, up.watch_url, up.privacy_status, up.video_id)

        # A queue transition is allowed only after a confirmed upload.
        _mark_job_uploaded(path, doc, up.video_id)

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


def _open_release_ticket(doc: ScriptDoc, url: str, privacy: str, video_id: str = "") -> None:
    """Best-effort GitHub release ticket so a human publishes in 2 clicks."""
    import os
    import subprocess

    if not os.environ.get("GITHUB_ACTIONS"):
        return
    title = f"Release ticket: {doc.title}"
    studio = f"https://studio.youtube.com/video/{video_id}/edit" if video_id else ""
    shorts_url = (
        f"https://www.youtube.com/shorts/{video_id}"
        if video_id and getattr(doc, "format", "") == "short"
        else ""
    )
    body = (
        f"Video rendered and uploaded.\n\n"
        f"- Watch link: {url}\n"
        + (f"- Shorts link: {shorts_url}\n" if shorts_url else "")
        + (f"- Studio editor: {studio}\n" if studio else "")
        + f"- Current privacy: `{privacy}`\n\n"
        f"### Human publish checklist\n"
        f"- [ ] Thumbnail reviewed/replaced (CTR lever #1)\n"
        f"- [ ] Title tuned for search + curiosity\n"
        f"- [ ] First 30 seconds hook reviewed\n"
        f"- [ ] Captions spot-checked\n"
        f"- [ ] Description sources present\n"
        f"- [ ] **Publish / schedule in YouTube Studio**\n"
    )
    env = {**os.environ}
    if not env.get("GH_TOKEN") and env.get("GITHUB_TOKEN"):
        env["GH_TOKEN"] = env["GITHUB_TOKEN"]
    try:
        proc = subprocess.run(
            ["gh", "issue", "create", "--title", title, "--body", body],
            check=False, capture_output=True, text=True, env=env,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"release ticket creation skipped: {exc!r}")
        return
    if proc.returncode != 0:
        # Never fail the upload over a ticket, but never hide it either —
        # before this, a missing GH_TOKEN made gh fail completely silently.
        _log(f"release ticket creation failed (exit {proc.returncode}): "
             f"{(proc.stderr or proc.stdout or '').strip()[:300]}")
    else:
        _log(f"release ticket created: {(proc.stdout or '').strip()[:200]}")


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
            import traceback
            tb = traceback.format_exc()
            clean_exc = str(exc).replace("\n", " ")
            print(f"::error file={path}::{clean_exc}", flush=True)
            summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
            if summary_path:
                with open(summary_path, "a", encoding="utf-8") as f:
                    f.write(f"### ❌ FAILED `{path.name}`\n\n```\n{exc}\n\n{tb}\n```\n")
            return 1

    _log(f"done: {len(results)} job(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
