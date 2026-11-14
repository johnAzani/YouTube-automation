"""Approved-style long-form production path (not yet enabled on main)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

from .config import CONFIG, OUTPUT_DIR
from .script_doc import MIN_LONGFORM_WORDS, MIN_NARRATION_SECONDS, parse_script
from .originality import enforce
from .progress import Heartbeat, emit, stage
from .gemini_client import Deadline, stage_budget_seconds
from .gemini_tts import DEFAULT_MODEL, get_gemini_api_key, synthesize_gemini_audio
from .prayer_alignment import align
from .prayer_visuals import render
from .tts import _probe_duration


def _refresh_live_thumbnail(doc, video_id: str, out_dir: Path) -> str | None:
    """Put this script's own thumbnail on a video that is already live.

    A video published by a run that died before recording itself went out wearing
    whatever frame the pack rendered then — and because the pack ignored the
    script's `thumb_text`, that frame was the same fixed one on every release.
    Re-rendering here repairs the picture on the channel at the same time as the
    receipt. Failure is logged and swallowed: the receipt matters more.
    """
    try:
        from .assets import fetch_scene_assets
        from .thumbnail_ctr import curated_backdrop_for, generate_ctr_pack, pick_backdrop
        from .upload import set_video_thumbnail

        backdrop = None
        if doc.scenes:
            scene = doc.scenes[0]
            matches = fetch_scene_assets(scene.asset_query or scene.heading, scene.index,
                                         out_dir / "assets", count=1,
                                         target_width=1280, target_height=720,
                                         allow_generated=False)
            backdrop = pick_backdrop([m.path for m in matches])
        backdrop = backdrop or curated_backdrop_for(doc.id or doc.slug, channel_id=doc.channel)
        reports = generate_ctr_pack(out_dir / "thumbnails",
                                    hero_override=doc.meta.get("thumb_text"),
                                    doc_key=doc.id or doc.slug,
                                    backdrop=backdrop,
                                    channel_id=doc.channel)
        if not reports:
            return None
        status = set_video_thumbnail(video_id, reports[0].path)
        print(f"[prayer] refreshed the thumbnail on {video_id}: {status}")
        return status
    except Exception as exc:  # noqa: BLE001 - a picture is never worth a failed run
        print(f"[prayer] could not refresh the thumbnail on {video_id}: {exc!r}")
        return None


def already_published(doc) -> str | None:
    """The existing video id if this exact title is already on the channel.

    The bounded playlist scan happens *before* synthesis and rendering. If the
    channel cannot be checked, do not spend speech quota on a take that cannot be
    safely uploaded; the caller leaves the job in the queue.
    """
    if getattr(CONFIG, "allow_duplicate_uploads", False):
        return None
    try:
        from googleapiclient.discovery import build

        from .metadata import smart_truncate_title
        from .upload import _credentials, check_existing_channel_duplicate

        youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
        safe_title = smart_truncate_title(doc.title, 95)
        found = check_existing_channel_duplicate(
            youtube, safe_title, doc.slug,
            additional_titles=(doc.title,) if safe_title != doc.title else (),
        )
        return str(found["id"]) if found else None
    except Exception as exc:
        raise RuntimeError("Cannot verify duplicate status before narration; leaving queue unchanged") from exc


def record_if_live(path: Path, doc=None) -> dict | None:
    """If this title is already on the channel, record it here and return the result.

    The receipt — the move to `content/published/` with the real video id — is the
    only thing that stops the next slot re-uploading the same video, so recovering a
    lost one is a *release-critical* job, not bookkeeping. It is also fast when the
    video is live and expensive when it is not: on 2 November this check decided to
    render, so a repair and a 45-minute render shared one 90-minute step and the
    step timed out twice. Callers that only want the repair pass `render=False`.
    """
    from .run import _mark_job_uploaded

    doc = doc or parse_script(path)
    existing = already_published(doc)
    if not existing:
        return None
    # A title match is not proof of ownership, privacy or publication time.
    # Keep the queue job intact unless YouTube confirms those facts.
    from .upload import inspect_existing_longform
    video = inspect_existing_longform(existing, doc.title)
    print(f"[prayer] {doc.id} matches an existing video {existing}; recording "
          f"verified remote facts instead of re-rendering")
    _mark_job_uploaded(path, doc, existing, recovered_video=video)
    job_dir = OUTPUT_DIR / doc.slug
    job_dir.mkdir(parents=True, exist_ok=True)
    _refresh_live_thumbnail(doc, existing, job_dir)
    result = {'id': doc.id, 'slug': doc.slug, 'video': None, 'thumbnail': None,
              'duration_seconds': None, 'tts_engine': 'none', 'dry_run': False,
              'video_id': existing, 'watch_url': f'https://youtu.be/{existing}',
              'privacy_status': 'already_published', 'youtube_privacy_status': video['privacy_status'],
              'uploaded': False}
    (job_dir / 'job_result.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    return result


def _fingerprint(*parts) -> str:
    import hashlib

    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:32]


def _cached_json(path: Path, key: str):
    """Return the cached payload when its fingerprint matches, else None."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if payload.get("key") == key else None


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _narrate(doc, audio: Path) -> str:
    """Use the locked Gemini Charon voice; never substitute another speaker."""
    synthesize_gemini_audio(doc.full_narration, audio, voice='Charon', model=DEFAULT_MODEL)
    return DEFAULT_MODEL


def _purge_corrupted_speech_artifacts(out_dir: Path) -> None:
    """Remove poisoned narration and cached TTS chunks after speech alignment rejects audio."""
    import shutil

    for name in ("narration.mp3", "narration.json", "words.json"):
        (out_dir / name).unlink(missing_ok=True)
    for chunk_dir in out_dir.glob("_gemini_chunks_*"):
        if chunk_dir.is_dir():
            shutil.rmtree(chunk_dir, ignore_errors=True)
        else:
            chunk_dir.unlink(missing_ok=True)


def _add_night_tail(doc, final: Path, assets, duration: float) -> dict | None:
    """Lengthen the bedtime channel's prayer for the night; ``None`` when it does not apply."""
    from . import night_tail

    channel_id = doc.explicit_channel or CONFIG.channel_id
    minutes = night_tail.configured_minutes(channel_id)
    if not minutes:
        return None
    try:
        from .channels import get_channel
        from .upload import _thumb_client

        allowed, why = night_tail.long_uploads_allowed(_thumb_client())
        if not allowed:
            print(f"::warning title=Night tail skipped ({channel_id})::{why}")
            return None
        with stage("night tail", f"{minutes} min in all"):
            info = night_tail.extend(final, assets, prayer_seconds=duration, total_minutes=minutes,
                                     channel_name=get_channel(channel_id).display_name)
    except Exception as exc:  # noqa: BLE001 - the prayer is published either way
        print(f"::warning title=Night tail skipped ({channel_id})::{str(exc)[:300]}")
        return None
    if info:
        print(f"[night-tail] {channel_id}: {duration / 60:.1f} min of prayer, then "
              f"{info['units']} x {info['unit_seconds'] / 60:.0f} min of rest = "
              f"{info['total_seconds'] / 3600:.2f} h, {info['megabytes']} MB, "
              f"built in {info['build_seconds']:.0f}s")
    return info


def produce(path: Path, dry_run: bool, model_dir: Path) -> dict:
    """Run the approved rendering pipeline with hard safety checks.

    Alignment weights must already be local. This path never uses placeholder,
    alternate-model or non-Charon speech, or a legacy subtitle renderer.
    """
    from .run import _existing_published_path, _mark_job_uploaded, _open_release_ticket, _require_production_prerequisites
    from .assets import fetch_scene_assets
    from .metadata import write_metadata_pack
    from .thumbnail_studio import mobile_preview
    from .thumbnail_ctr import generate_ctr_pack
    from .quota_handler import GeminiQuotaExceededError, QuotaExceededError, pause_longform_job_on_quota

    doc = parse_script(path)
    if doc.format != 'longform' or not any(term in str(doc.meta.get('niche', '')).lower() for term in ('faith', 'prayer', 'scripture', 'devotional')):
        raise RuntimeError('Only long-form prayer content is permitted')
    if doc.voice != 'Charon':
        raise RuntimeError('The permanent prayer voice is Charon')
    enforce(doc)
    _require_production_prerequisites(doc, dry_run, CONFIG.youtube_refresh_token,
                                      CONFIG.youtube_client_id, CONFIG.youtube_client_secret)
    if not dry_run:
        # A published record for this exact job file means the video was
        # already released (or a stale record is impersonating one). Rendering
        # anyway uploads a duplicate and only fails afterwards, when the
        # receipt move refuses to overwrite the record — on 5 November 2026
        # job 0036 rendered for 52 minutes and uploaded before discovering a
        # stale record that a monitor snapshot had resurrected after its
        # retirement was merged. Fail here instead: a deliberate replacement
        # must retire the record first, and a lost receipt is recovered by
        # record_if_live below (which only runs when no record exists).
        published_record = _existing_published_path(path)
        if published_record:
            raise RuntimeError(
                f'Published record {published_record} already exists for job '
                f'{doc.id}; refusing to render or upload a duplicate. If this '
                'is a deliberate replacement, retire the record first (the '
                'replacement run will write a fresh one).'
            )
        recorded = record_if_live(path, doc)
        if recorded:
            return recorded

    if not get_gemini_api_key():
        raise RuntimeError('Gemini API key missing; refusing voice substitution')
    if not (Path(model_dir) / 'model.bin').is_file() or importlib.util.find_spec('faster_whisper') is None:
        raise RuntimeError('Offline speech alignment model is not installed')
    if not doc.scenes:
        raise RuntimeError('No prayer scenes in script')
    # Avoid consuming quota for scripts too short to plausibly reach five minutes.
    if doc.word_count < MIN_LONGFORM_WORDS:
        raise RuntimeError(f'Prayer script has only {doc.word_count} words; expand it before full-length production')
    out = OUTPUT_DIR / doc.slug
    out.mkdir(parents=True, exist_ok=True)
    audio = out / 'narration.mp3'
    try:
        # Speech is the expensive, deterministic step: on a retry the same script
        # text must not be paid for again in minutes and free-tier quota. The
        # sidecar records which text produced this file, so an edited script still
        # re-synthesises and an unchanged one is reused.
        # The fingerprint prefix is the delivery recipe version. v1/v2/v3
        # audio must never be reused — the recipe (what else reached the
        # model, and how) is what made those takes defective.
        from .gemini_tts import DELIVERY_RECIPE

        import hashlib

        speech_key = _fingerprint(DELIVERY_RECIPE, DEFAULT_MODEL, "Charon", doc.full_narration)
        cached = _cached_json(out / 'narration.json', speech_key)
        cached_ok = (cached and cached.get('engine') == DEFAULT_MODEL and
                     cached.get('voice') == 'Charon' and audio.is_file() and
                     cached.get('audio_sha256') == hashlib.sha256(audio.read_bytes()).hexdigest())
        if cached_ok:
            emit(f"reusing narration from the previous attempt ({cached.get('duration', 0):.0f}s)")
            engine = DEFAULT_MODEL
        else:
            # Even unchanged text may be spoken at different timings on a new take.
            # Never reuse an alignment produced for the previous audio file.
            (out / 'words.json').unlink(missing_ok=True)
            (out / 'narration.json').unlink(missing_ok=True)
            with stage("speech synthesis", f"{doc.word_count} words, Charon"):
                engine = _narrate(doc, audio)
        if engine != DEFAULT_MODEL:
            raise RuntimeError(f'Refusing narration engine {engine!r}; Gemini Charon is required')
        duration = _probe_duration(audio)
        if duration is None or duration < MIN_NARRATION_SECONDS:
            speaker = "Charon" if engine == DEFAULT_MODEL else engine
            raise RuntimeError(
                f'Actual {speaker} narration is {duration or 0:.0f}s; the channel needs '
                f'{MIN_NARRATION_SECONDS}s ({MIN_NARRATION_SECONDS // 60} minutes). '
                f'{doc.word_count} words is too short at {speaker}\'s pace — lengthen the script, '
                f'the floor is {MIN_LONGFORM_WORDS} words.')
        _write_json(out / 'narration.json',
                    {'key': speech_key, 'duration': duration, 'engine': engine,
                     'voice': 'Charon', 'audio_sha256': hashlib.sha256(audio.read_bytes()).hexdigest()})

        align_key = _fingerprint("align-v1", speech_key, duration)
        cached_words = _cached_json(out / 'words.json', align_key)
        if cached_words and cached_words.get('words'):
            words = [tuple(w) for w in cached_words['words']]
            emit(f"reusing the previous word alignment ({len(words)} words)")
        else:
            try:
                with stage("speech alignment", f"{duration:.0f}s of audio"):
                    words = align(audio, doc.full_narration, Path(model_dir))
            except ValueError:
                # Never publish a take whose spoken words failed alignment. Remove
                # the cached chunks so a later retry cannot reuse poisoned audio.
                _purge_corrupted_speech_artifacts(out)
                raise
            _write_json(out / 'words.json', {'key': align_key, 'words': [list(w) for w in words]})
        boundaries = [0.0]
        count = 0
        for scene in doc.scenes[:-1]:
            count += len(scene.narration.split())
            if count <= 0 or count >= len(words):
                raise RuntimeError('Scene boundary does not match aligned speech')
            boundaries.append(words[count - 1][2])
        boundaries.append(duration)
        durations = [b - a for a, b in zip(boundaries, boundaries[1:])]
        if any(d <= 0 for d in durations):
            raise RuntimeError('Invalid scene duration')
        assets = []
        # A budget for the whole asset stage, not just per provider call. Eight
        # scenes x (search + download + licence scan) is normally a few minutes;
        # if a provider is throttling us it can be an hour of quiet retries, which
        # is one of the two places the 90-minute release step went on 2 November.
        # Fail at a named scene instead of at the step's cap.
        asset_budget = Deadline(stage_budget_seconds(1200), "asset fetch")
        for scene in doc.scenes:
            asset_budget.check(f"scene {scene.index}/{len(doc.scenes)}")
            with stage("asset fetch", f"scene {scene.index}/{len(doc.scenes)}"):
                # count=1 on purpose: this path renders exactly matches[0], so asking
                # for CONFIG.clips_per_scene (2) doubled both the provider searches
                # and the downloads for a second clip that was thrown away.
                matches = fetch_scene_assets(scene.asset_query or scene.heading, scene.index,
                                             out / 'assets', count=1,
                                             target_width=1280, target_height=720,
                                             allow_generated=False)
            if not matches:
                raise RuntimeError(f'No licensed asset for scene {scene.index}')
            assets.append(matches[0].path)
        with stage("encode", f"{duration / 60:.1f} min, {len(doc.scenes)} scenes"):
            heartbeat = Heartbeat("encode", int(duration * 24))
            final = render(audio, list(zip(assets, durations)), words, duration,
                           out / f'{doc.slug}.mp4', timing_source='measured',
                           progress=heartbeat.tick)
        # The bedtime channel's prayer is followed by hours of quiet music, so one
        # listener through the night is hours of watch time (pipeline/night_tail.py).
        # The prayer file is never changed; a failure there publishes it as before.
        night = None if dry_run else _add_night_tail(doc, final, assets, duration)
        if night:
            final = Path(night['video'])
        # Thumbnails come from the CTR pack, never from the card generator: it enforces
        # mobile legibility, contrast, safe zones and visibility against YouTube's
        # dark-mode page, and writes a report so the run page shows the numbers.
        # See docs/THUMBNAIL_RESEARCH.md.
        from .thumbnail_ctr import curated_backdrop_for, pick_backdrop

        with stage("thumbnail pack", "3 concepts"):
            thumb_reports = generate_ctr_pack(out / "thumbnails",
                                              hero_override=doc.meta.get("thumb_text"),
                                              doc_key=doc.id or doc.slug,
                                              backdrop=pick_backdrop(assets) or curated_backdrop_for(doc.id or doc.slug, channel_id=doc.channel),
                                              channel_id=doc.channel)
        for report in thumb_reports:
            mobile_preview(report.path, report.path.with_name(report.path.stem + "_mobile.png"))
        (out / "thumbnails" / "report.json").write_text(
            json.dumps([r.as_dict() for r in thumb_reports], indent=2), encoding="utf-8")
        thumbs = [r.path for r in thumb_reports]
        pack = write_metadata_pack(doc, durations, out)
        if night:
            from .night_tail import describe as describe_night

            pack = describe_night(pack, prayer_seconds=duration,
                                  total_seconds=night['total_seconds'])
        from .captions import write_srt_file
        srt_path = write_srt_file(out / 'captions.en.srt', words, doc.full_narration, duration=duration)
        result = {'id': doc.id, 'slug': doc.slug, 'video': str(final), 'thumbnail': str(thumbs[0]),
                  'captions': str(srt_path) if srt_path else '',
                  'duration_seconds': duration, 'tts_engine': engine, 'dry_run': dry_run}
        if night:
            result.update(duration_seconds=night['total_seconds'], prayer_seconds=duration,
                          night_tail=night)
        if not dry_run:
            from .upload import upload
            with stage("upload", "YouTube"):
                up = upload(doc, final, thumbs[0], privacy=doc.meta.get('privacy'),
                            publish_at=doc.meta.get('publish_at'), description=pack.get('description'),
                            caption_path=srt_path, tags=pack.get('tags'))
            if not up.video_id:
                raise RuntimeError('YouTube returned no video ID; queue unchanged')
            # Persist the receipt before any nonessential notification.
            # A duplicate-prevented upload points to an existing video. The take
            # rendered here did not produce it, so do not invent its voice or claim
            # that this attempt applied a thumbnail.
            is_new_upload = up.privacy_status != 'duplicate_prevented'
            recovered_video = None
            if not is_new_upload:
                from .upload import inspect_existing_longform
                recovered_video = inspect_existing_longform(up.video_id, doc.title)
            _mark_job_uploaded(path, doc, up.video_id,
                               getattr(up, 'thumbnail_status', 'not_requested') if is_new_upload else 'not_requested',
                               narration_engine=engine if is_new_upload else None,
                               narration_voice='Charon' if is_new_upload else None,
                               recovered_video=recovered_video,
                               scheduled_for=(getattr(up, 'scheduled_for', '') or None) if is_new_upload else None,
                               pinned_comment=getattr(up, 'pinned_comment', None) if is_new_upload else None)
            result.update(video_id=up.video_id, watch_url=up.watch_url,
                          privacy_status=up.privacy_status, uploaded=up.privacy_status != 'duplicate_prevented')
            if is_new_upload and getattr(up, 'scheduled_for', ''):
                result['scheduled_for'] = up.scheduled_for
            if result['uploaded']:
                _open_release_ticket(doc, up.watch_url, up.privacy_status, up.video_id)
        (out / 'job_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    except (GeminiQuotaExceededError, QuotaExceededError) as exc:
        reset = getattr(exc, 'reset_utc', None)
        if not dry_run:
            pause_longform_job_on_quota(path, str(exc), reset)
        return {'job': doc.id, 'status': 'quota_paused', 'quota_reset_utc': reset.isoformat() if reset else None}
