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
from .script_doc import MIN_LONGFORM_WORDS, ScriptDoc, parse_script
from .thumbnail_ctr import THUMBNAIL_REVISION


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


def _quarantine_tts_blocked_job(path: Path, reason: str) -> None:
    """Mark a queue script `status: tts_blocked` so it cannot poison subsequent slots."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    fm = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not fm:
        return
    meta = fm.group(1)
    meta, n = re.subn(r"(?m)^status\s*:.*$", "status: tts_blocked", meta, count=1)
    if not n:
        meta = "status: tts_blocked\n" + meta
    clean_reason = re.sub(r"\s+", " ", str(reason)).strip()[:220]
    line = f"tts_blocked_reason: {json.dumps(clean_reason)}"
    if re.search(r"(?m)^tts_blocked_reason\s*:.*$", meta):
        meta = re.sub(r"(?m)^tts_blocked_reason\s*:.*$", line, meta, count=1)
    else:
        meta += f"\n{line}"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(f"---\n{meta}\n---{fm.group('tail')}", encoding="utf-8")
    tmp.replace(path)


def _require_real_narration(engine: str, dry_run: bool) -> None:
    """Placeholder audio is useful for offline renders, but never publishable."""
    if not dry_run and engine not in ("edge-tts", "gemini-api"):
        raise RuntimeError(
            f"Refusing production upload: narration engine is {engine!r} (placeholder audio). "
            "Fix the TTS failure and rerun; placeholder audio must not be published."
        )


def _mark_job_uploaded(
    path: Path,
    doc: ScriptDoc,
    video_id: str,
    thumbnail_status: str = "not_requested",
) -> Path:
    """Move and stamp a queue job only after YouTube confirms an uploaded video ID.

    ``thumbnail_status`` is what YouTube actually did with the custom thumbnail
    (see ``UploadResult``). The receipt only claims ``thumbnail_revision`` when
    the thumbnail really landed; otherwise it records ``thumbnail_pending`` plus
    the reason, which is what makes ``scripts/sync_published_thumbnails.py``
    retry the video on the next monitor pass. It used to be stamped
    unconditionally, so a refused thumbnail looked finished forever — that is
    why the two Morning Altar videos had none and nothing said so.
    """
    thumb_ok = str(thumbnail_status).strip().lower() == "ok"
    thumb_note = "" if thumb_ok else str(thumbnail_status or "not_requested").strip()[:220]
    if not video_id:
        raise RuntimeError("YouTube returned no video ID; leaving the queue job untouched.")
    dest = PUBLISHED_DIR / path.name
    if dest.exists():
        raise RuntimeError(f"Published record already exists at {dest}; leaving the queue job untouched.")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d")
    # The full instant as well as the date. `published_on` alone is a date, so every
    # reader has to assume midnight and a video uploaded three hours ago reads as
    # "20h ago" — which is how a healthy channel looks stale and an alarm stops
    # meaning anything.
    stamp_precise = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    text = path.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---(?P<tail>\s*\n.*|\Z)", text, re.S)
    if not frontmatter:
        raise RuntimeError(f"Cannot stamp {path}: missing YAML frontmatter; leaving the queue job untouched.")
    metadata = frontmatter.group(1)
    metadata, replacements = re.subn(r"(?m)^status\s*:.*$", "status: published", metadata, count=1)
    if not replacements:
        raise RuntimeError(f"Cannot stamp {path}: missing top-level status; leaving the queue job untouched.")
    stamped = [("published_on", stamp), ("published_at", stamp_precise),
               ("youtube_video_id", video_id), ("metadata_revision", "selar-seo-v1")]
    if thumb_ok:
        stamped.append(("thumbnail_revision", THUMBNAIL_REVISION))
    else:
        # Honest state: the repair pass in the monitor is what fixes this, so
        # leave a marker it can see rather than a revision it can trust.
        stamped.append(("thumbnail_pending", True))
        stamped.append(("thumbnail_error", thumb_note))
    for key, value in stamped:
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
    doc.meta["published_at"] = stamp_precise
    doc.meta["youtube_video_id"] = video_id
    if thumb_ok:
        doc.meta["thumbnail_revision"] = THUMBNAIL_REVISION
    else:
        doc.meta["thumbnail_pending"] = True
        doc.meta["thumbnail_error"] = thumb_note
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


def resolve_job_path(job_arg: str) -> Path:
    """Resolve a --job argument to a queue file.

    Accepts a full path, a bare filename, or a bare job id / filename
    prefix ("0036"). The Actions form once received "0036" verbatim, the
    pipeline looked for a file literally named `content/queue/0036`, and
    the run died in two minutes (Produce video #89) — an id is how a
    human naturally names a job, so resolve it instead of demanding the
    full filename. Ambiguous or unknown selectors fail with the list of
    real files rather than a bare FileNotFoundError.
    """
    arg = (job_arg or "").strip()
    if not arg:
        raise ValueError("--job requires a path, filename, or job id")
    candidate = Path(arg)
    if candidate.is_file():
        return candidate
    in_queue = QUEUE_DIR / candidate.name
    if in_queue.is_file():
        return in_queue
    matches = sorted(QUEUE_DIR.glob(f"{candidate.name}*.md"))
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(p.name for p in sorted(QUEUE_DIR.glob("*.md"))) or "(queue is empty)"
    if matches:
        names = ", ".join(p.name for p in matches)
        raise ValueError(f"--job {arg!r} is ambiguous: {names}. Available: {available}")
    raise ValueError(f"--job {arg!r} matches no file in content/queue/. Available: {available}")


def select_jobs(all_flag: bool, job_path: str | None, next_flag: bool) -> list[Path]:
    if job_path:
        return [resolve_job_path(job_path)]
    from .channels import normalize_channel_id

    target_channel = normalize_channel_id(CONFIG.channel_id)
    jobs = sorted(QUEUE_DIR.glob("*.md"))
    approved: list[Path] = []
    for j in jobs:
        try:
            doc = parse_script(j)
        except Exception as exc:  # noqa: BLE001
            _log(f"skip {j.name}: parse error {exc}")
            continue

        # Channel routing: a run only picks up its own channel's scripts.
        # Without this, selecting PRAYER2 credentials would upload The Secret
        # Place's next approved script to The Morning Altar (or vice versa).
        if doc.channel != target_channel:
            _log(f"skip {j.name}: channel={doc.channel} (this run targets {target_channel})")
            continue

        raw_status = str(doc.status).strip().lower()
        if raw_status == "quota_paused":
            from pipeline.quota_handler import is_quota_pause_expired, unpause_longform_job
            reset_at_str = doc.meta.get("quota_reset_utc", "")
            if is_quota_pause_expired(reset_at_str):
                _log(f"Quota reset time passed ({reset_at_str}). Auto-unpausing {j.name}...")
                unpause_longform_job(j)
                approved.append(j)
            else:
                _log(f"{j.name} is paused until daily quota resets at {reset_at_str} UTC.")
            continue

        if raw_status == "approved":
            # --- DUPLICATE SAFETY SHIELD: verify not already in content/published/ ---
            published_candidate = PUBLISHED_DIR / j.name
            if published_candidate.is_file():
                try:
                    pub_doc = parse_script(published_candidate)
                    if pub_doc.status == "published" and pub_doc.meta.get("youtube_video_id"):
                        _log(f"🛑 DUPLICATE BLOCKED: {j.name} is already published as {pub_doc.meta.get('youtube_video_id')}. Skipping queue.")
                        continue
                except Exception:
                    pass
            # A long-form prayer under the word floor cannot build, and picking it
            # would fail every cron forever — one bad row must never block the rest.
            # The brain's supply loop lengthens it (every production run and the
            # 4:14am brain pass), then it becomes eligible.
            fmt = str(getattr(doc, "format", "") or doc.meta.get("format", "")).lower()
            if fmt == "longform" and doc.word_count < MIN_LONGFORM_WORDS:
                _log(f"⏳ {j.name} is {doc.word_count} words, under the {MIN_LONGFORM_WORDS} floor; "
                     f"waiting for the brain to lengthen it.")
                continue
            approved.append(j)
        elif all_flag:
            _log(f"skip {j.name}: status={doc.status} (only 'approved' jobs are built)")
    if next_flag:
        return approved[:1]
    return approved


def process(path: Path, dry_run: bool) -> dict:
    """Use only the approved prayer renderer; never fall back to the old style."""
    from .channels import normalize_channel_id
    from .prayer_pipeline import produce

    # Explicit --job runs bypass select_jobs, so enforce routing here too:
    # never render/upload a script under the wrong channel's credentials.
    # (Only when the file exists — a missing path is produce()'s error to raise.)
    if not Path(path).is_file():
        model = Path(os.environ.get("PRAYER_ALIGNMENT_MODEL", OUTPUT_DIR / "alignment-model"))
        return produce(path, dry_run, model)
    doc = parse_script(path)
    target_channel = normalize_channel_id(CONFIG.channel_id)
    if doc.channel != target_channel:
        raise RuntimeError(
            f"Refusing cross-channel run for job {doc.id}: script channel={doc.channel!r} "
            f"but this run targets {target_channel!r} (CHANNEL_ID). "
            "Select the matching channel so its own GCP quota and token are used."
        )
    model = Path(os.environ.get("PRAYER_ALIGNMENT_MODEL", OUTPUT_DIR / "alignment-model"))
    return produce(path, dry_run, model)


def _disabled_legacy_process(path: Path, dry_run: bool) -> dict:
    """Retained for migration only; never call from production."""
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
        from .quota_handler import GeminiQuotaExceededError, QuotaExceededError, pause_longform_job_on_quota

        voice = doc.voice or CONFIG.voice
        try:
            narration = synthesize(doc.full_narration, out_dir, voice=voice)
        except (GeminiQuotaExceededError, QuotaExceededError) as q_exc:
            reset_dt = getattr(q_exc, "reset_utc", None)
            reset_iso = reset_dt.isoformat() if reset_dt else "08:00:00Z"
            _log(f"Daily quota reached: {q_exc}. Pausing job {path.name} until {reset_iso} UTC ($0.00 lock active)...")
            pause_longform_job_on_quota(path, str(q_exc), reset_dt)
            return {
                "job": doc.id,
                "status": "quota_paused",
                "quota_reset_utc": reset_iso,
                "error": str(q_exc),
            }
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
        raise RuntimeError("Legacy montage renderer is prohibited by the visual style lock")
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
        privacy_val = doc.meta.get("privacy")
        publish_at_val = doc.meta.get("publish_at")
        try:
            up = upload(doc, final, upload_thumb, privacy=privacy_val, publish_at=publish_at_val, description=pack.get("description"))
        except (QuotaExceededError, GeminiQuotaExceededError) as q_exc:
            reset_dt = getattr(q_exc, "reset_utc", None) or calculate_next_quota_reset_utc()
            reset_iso = reset_dt.isoformat()
            _log(f"Daily quota reached: {q_exc}. Pausing job {path.name} until {reset_iso} UTC ($0.00 lock active)...")
            pause_longform_job_on_quota(path, str(q_exc), reset_dt)
            return {
                "job": doc.id,
                "status": "quota_paused",
                "quota_reset_utc": reset_iso,
                "error": str(q_exc),
            }
        if up.privacy_status == "duplicate_prevented":
            _log(f"YouTube upload skipped: video already live on channel ({up.video_id}).")
            result.update({
                "uploaded": False,
                "duplicate_prevented": True,
                "video_id": up.video_id,
                "watch_url": f"https://youtu.be/{up.video_id}",
                "privacy_status": up.privacy_status,
                "thumbnail_status": up.thumbnail_status,
            })
            _mark_job_uploaded(path, doc, up.video_id, up.thumbnail_status)
            (out_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            return result
        if not up.video_id:
            raise RuntimeError("YouTube upload returned no video ID; leaving the queue job untouched.")
        result.update({
            "uploaded": True,
            "video_id": up.video_id,
            "watch_url": up.watch_url,
            "privacy_status": up.privacy_status,
            "thumbnail_status": up.thumbnail_status,
        })
        _log(f"uploaded {up.watch_url} (privacy={up.privacy_status}, "
             f"thumbnail={up.thumbnail_status})")
        _open_release_ticket(doc, up.watch_url, up.privacy_status, up.video_id)

        # A queue transition is allowed only after a confirmed upload.
        _mark_job_uploaded(path, doc, up.video_id, up.thumbnail_status)

    (out_dir / "job_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    # GitHub Actions job summary (renders nicely on the run page)
    summary_path = Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(f"### 🎬 {doc.title}\n\n")
            f.write(f"- slug: `{doc.slug}`\n- duration: {narration_dur:.0f}s\n")
            f.write(f"- tts: {narration_engine}\n- video: `{final.name}`\n")
            if result.get("watch_url"):
                f.write(f"- watch: {result['watch_url']}\n")
            if result.get("thumbnail_status"):
                # A published video with no custom thumbnail is a silent CTR
                # loss; say it on the run page instead of only in a log line.
                f.write(f"- thumbnail: `{result['thumbnail_status']}`\n")
            f.write("\n> ⚠️ Human QC required before publish: thumbnail, title, intro hook (first 30s), "
                    "captions, and the originality checklist signature.\n")
    return result


def _open_release_ticket(doc: ScriptDoc, url: str, privacy: str, video_id: str = "") -> None:
    """Best-effort GitHub release ticket so a human publishes in 2 clicks."""
    import os
    import subprocess

    if not os.environ.get("GITHUB_ACTIONS"):
        return
    if str(privacy or "").strip().lower() in {"public", "already_published", "duplicate_prevented"}:
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
    if video_id and PUBLISHED_DIR.is_dir():
        for rec in PUBLISHED_DIR.glob("*.md"):
            try:
                text = rec.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if (
                (f'youtube_video_id: "{video_id}"' in text or f"youtube_video_id: {video_id}" in text)
                and "release_ticket_opened: true" in text
            ):
                _log(f"release ticket skipped: already opened for {video_id} ({rec.name})")
                return
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
        if video_id and PUBLISHED_DIR.is_dir():
            for rec in PUBLISHED_DIR.glob("*.md"):
                try:
                    text = rec.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if f'youtube_video_id: "{video_id}"' in text or f"youtube_video_id: {video_id}" in text:
                    if "release_ticket_opened:" not in text and text.startswith("---\n"):
                        rec.write_text(
                            text.replace("---\n", "---\nrelease_ticket_opened: true\n", 1),
                            encoding="utf-8",
                        )
                    break


def quota_blocked_until(
    now: datetime | None = None,
    channel_id: str | None = None,
) -> datetime | None:
    """The latest quota-pause reset still in the future for *this* channel.

    Each scheduled channel has its own Google Cloud project and free-tier TTS
    allowance. A paused job on one channel must never hold back another
    channel's release slot.
    """
    import yaml

    from .channels import normalize_channel_id
    from .quota_handler import is_quota_pause_expired

    now = now or datetime.now(timezone.utc)
    wanted = normalize_channel_id(channel_id if channel_id is not None else CONFIG.channel_id)
    latest: datetime | None = None

    def _record(raw_reset: str) -> None:
        nonlocal latest
        raw = str(raw_reset or "").strip()
        if not raw or is_quota_pause_expired(raw):
            return
        try:
            when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when > now and (latest is None or when > latest):
            latest = when

    for path in sorted(QUEUE_DIR.glob("*.md")):
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        if doc.channel != wanted:
            continue
        if str(doc.status).strip().lower() != "quota_paused":
            continue
        _record(str(doc.meta.get("quota_reset_utc") or ""))

    shorts_dir = QUEUE_DIR.parent / "shorts-queue"
    if shorts_dir.is_dir():
        for path in sorted(shorts_dir.glob("*.yml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:  # noqa: BLE001
                continue
            if normalize_channel_id(data.get("channel")) != wanted:
                continue
            if str(data.get("status") or "").strip().lower() != "quota_paused":
                continue
            _record(str(data.get("quota_reset_utc") or ""))

    return latest


def empty_reason(channel_id: str | None = None) -> str:
    """Why nothing could be published on this channel, in one sentence."""
    from .channels import normalize_channel_id
    from .script_doc import MIN_LONGFORM_WORDS, parse_script

    wanted = normalize_channel_id(channel_id if channel_id is not None else CONFIG.channel_id)
    queue = sorted(QUEUE_DIR.glob("*.md"))
    approved, short, missing = 0, [], 0
    for path in queue:
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        if doc.channel != wanted:
            continue
        if doc.status != "approved":
            missing += 1
            continue
        approved += 1
        if doc.word_count < MIN_LONGFORM_WORDS:
            short.append((path.name, doc.word_count))
    if approved and short:
        worst = min(short, key=lambda row: row[1])
        need = MIN_LONGFORM_WORDS - worst[1]
        return (f"{len(short)} approved script(s) are under the {MIN_LONGFORM_WORDS}-word "
                f"floor — {worst[0]} needs {need} more words — and the expansion pass "
                f"did not bring any of them over it")
    if not approved:
        return (f"no approved long-form script in content/queue ({missing} draft(s)); "
                f"the brain has not supplied one")
    return "the queue has scripts but none is eligible"


def record_published_jobs() -> int:
    """Write the receipt for every approved job that is already live on the channel.

    Its own entry point so a workflow can give it its own step and its own timeout.
    When this work ran inside the render step, a repair plus a render shared one
    90-minute budget and both runs on 2 November timed out with a video live and
    unrecorded.
    """
    from .prayer_pipeline import record_if_live

    recorded, checked = [], 0
    for path in select_jobs(False, None, False) or []:
        checked += 1
        try:
            result = record_if_live(path)
        except Exception as exc:  # noqa: BLE001 - a repair must never block a release
            _log(f"could not check {path.name}: {exc!r}")
            continue
        if result:
            recorded.append((path.name, result["video_id"]))

    for name, video_id in recorded:
        print(f"[run] recorded {name} -> {video_id}")
    _log(f"recorded {len(recorded)} already-live job(s) of {checked} checked")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Receipts written: {len(recorded)} of {checked} checked\n\n")
            for name, video_id in recorded:
                f.write(f"- `{name}` → https://youtu.be/{video_id}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="YouTube automation pipeline")
    p.add_argument("--job", help="path to a specific script markdown file")
    p.add_argument("--all", action="store_true", help="process every approved job")
    p.add_argument("--next", action="store_true", help="process the next approved job")
    p.add_argument("--dry-run", action="store_true", help="render only; never upload")
    p.add_argument("--record-published", action="store_true",
                   help="record jobs whose video is already live, then exit; never render")
    args = p.parse_args(argv)

    dry = args.dry_run or CONFIG.dry_run or os.environ.get("DRY_RUN", "").lower() in {"1", "true", "yes"}
    CONFIG.dry_run = dry
    CONFIG.ensure_dirs()

    if args.record_published:
        return record_published_jobs()

    paths = select_jobs(args.all, args.job, args.next)
    if not dry and not args.job:
        # Quota first: while any long-form pause is still live, starting the NEXT
        # approved script in the queue spends tomorrow's 10 requests/day allowance
        # instead of letting the paused script finish after reset.
        blocked = quota_blocked_until()
        if blocked is not None:
            print(f"::error title=Release did not publish::Gemini's free-tier TTS "
                  f"allowance (10 requests/day) is spent until "
                  f"{blocked.isoformat()} UTC. The next slot after that will publish; "
                  f"nothing was uploaded and nothing was wasted today.", flush=True)
            return 3
    if not paths:
        blocked = quota_blocked_until()
        if blocked is not None:
            print(f"::error title=Release did not publish::Gemini's free-tier TTS "
                  f"allowance (10 requests/day) is spent until "
                  f"{blocked.isoformat()} UTC. The next slot after that will publish; "
                  f"nothing was uploaded and nothing was wasted today.", flush=True)
            return 3
        # This used to `return 0` with a friendly notice, on the theory that a red
        # cron every three hours would train everyone to ignore the dashboard. In
        # practice it meant three production runs a day exited green while the
        # channel published nothing for days on end, and the only person who
        # noticed was the owner. An empty release slot is the fault, so it is
        # reported as one, with the arithmetic that explains it.
        why = empty_reason()
        _log(f"nothing publishable: {why}")
        print(f"::error title=Nothing publishable::{why}", flush=True)
        return 2

    results = []
    tried: set[Path] = set()
    remaining = list(paths)
    while remaining:
        path = remaining.pop(0)
        tried.add(path)
        try:
            result = process(path, dry)
            results.append(result)
        except Exception as exc:  # noqa: BLE001
            from .gemini_tts import is_content_blocked_error

            if not dry and args.next and is_content_blocked_error(exc):
                _quarantine_tts_blocked_job(path, str(exc))
                clean_exc = str(exc).replace("\n", " ")[:240]
                _log(f"quarantined TTS-blocked script {path.name}: {clean_exc}")
                print(
                    f"::warning file={path},title=Quarantined TTS-blocked script::"
                    f"{path.name} triggered Gemini TTS content filter ({clean_exc}); "
                    f"marked status=tts_blocked and advancing to next eligible script.",
                    flush=True,
                )
                if not remaining:
                    remaining = [
                        p for p in (select_jobs(False, None, False) or [])
                        if p not in tried
                    ]
                if remaining:
                    continue
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

        # A quota pause is NOT a release. `produce()` returns this dict instead of
        # raising, and every caller treated a returned dict as success — so on
        # 3 November the 07:27 release paused 0017 for exhausted Gemini quota,
        # uploaded nothing, wrote no receipt, and the run finished GREEN. Three
        # slots a day can do that while the channel publishes nothing, which is
        # exactly the report the owner keeps having to make himself.
        if result.get("status") == "quota_paused":
            reset = result.get("quota_reset_utc") or "an unknown time"
            _log(f"quota paused: {path.name} will publish after {reset}")
            print(f"::error title=Release did not publish::Gemini quota is exhausted; "
                  f"{path.name} is paused until {reset} UTC and nothing was uploaded. "
                  f"The $0.00 free tier allows a limited number of videos per day.",
                  flush=True)
            return 3

        # A job whose video is already on the channel is bookkeeping, not a release:
        # recording it must not consume the whole slot. Keep going until something is
        # actually published (or the eligible jobs run out).
        if not (args.next and result.get("privacy_status") == "already_published"):
            break
        _log(f"{path.name} was already live; moving on to the next eligible job")
        if not remaining:
            remaining = [p for p in (select_jobs(False, None, False) or [])
                         if p not in tried]

    # The outcome, in one line, as an annotation. A run page is behind a sign-in and
    # the log archive is unreachable from automation; an annotation is readable by
    # both, and it means "green" always comes with a sentence saying what went out.
    for result in results:
        if result.get("uploaded"):
            print(f"::notice title=Published::{(result.get('video_id') or '?')} — "
                  f"{result.get('watch_url') or ''} ({result.get('duration_seconds') or 0:.0f}s)")
        elif result.get("privacy_status") == "already_published":
            print(f"::notice title=Already live::id {result.get('id')} was already on the "
                  f"channel as {result.get('video_id')}; recorded, not re-uploaded.")
        elif result.get("dry_run"):
            print(f"::notice title=Rendered only::`{result.get('slug')}` rendered under "
                  f"DRY_RUN; nothing uploaded.")
        else:
            print(f"::notice title=Release finished with no upload::"
                  f"{json.dumps({k: result.get(k) for k in ('id', 'slug', 'status')})}")
    _log(f"done: {len(results)} job(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
