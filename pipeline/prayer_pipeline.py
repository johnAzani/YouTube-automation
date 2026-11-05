"""Approved-style long-form production path (not yet enabled on main)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

from .config import CONFIG, OUTPUT_DIR, PUBLISHED_DIR
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
        backdrop = backdrop or curated_backdrop_for(doc.id or doc.slug)
        reports = generate_ctr_pack(out_dir / "thumbnails",
                                    hero_override=doc.meta.get("thumb_text"),
                                    doc_key=doc.id or doc.slug,
                                    backdrop=backdrop)
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

    Two API units, spent *before* a 25-minute render. On 2 November a video that was
    already live on the channel sat in the queue as `approved` because the commit
    that would have recorded it failed; without this check the next release slot
    would have re-rendered the whole thing from scratch and only then discovered the
    duplicate.
    """
    if getattr(CONFIG, "allow_duplicate_uploads", False):
        return None
    try:
        from googleapiclient.discovery import build

        from .upload import _credentials, check_existing_channel_duplicate

        youtube = build("youtube", "v3", credentials=_credentials(), cache_discovery=False)
        found = check_existing_channel_duplicate(youtube, doc.title, doc.slug)
        return str(found["id"]) if found else None
    except Exception as exc:  # noqa: BLE001 - never block a release on a pre-check
        print(f"[prayer] duplicate pre-check skipped: {exc!r}")
        return None


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
    print(f"[prayer] {doc.id} is already live as {existing}; recording it instead "
          f"of re-rendering")
    _mark_job_uploaded(path, doc, existing)
    job_dir = OUTPUT_DIR / doc.slug
    job_dir.mkdir(parents=True, exist_ok=True)
    _refresh_live_thumbnail(doc, existing, job_dir)
    result = {'id': doc.id, 'slug': doc.slug, 'video': None, 'thumbnail': None,
              'duration_seconds': None, 'tts_engine': 'none', 'dry_run': False,
              'video_id': existing, 'watch_url': f'https://youtu.be/{existing}',
              'privacy_status': 'already_published', 'uploaded': False}
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


def produce(path: Path, dry_run: bool, model_dir: Path) -> dict:
    """Run the approved rendering pipeline with hard safety checks.

    Alignment weights must already be local. This path never uses placeholder,
    alternate-model or non-Charon speech, or a legacy subtitle renderer.
    """
    from .run import _mark_job_uploaded, _open_release_ticket, _require_production_prerequisites
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
        published_record = PUBLISHED_DIR / Path(path).name
        if published_record.is_file():
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

        speech_key = _fingerprint(DELIVERY_RECIPE, DEFAULT_MODEL, "Charon", doc.full_narration)
        cached = _cached_json(out / 'narration.json', speech_key)
        if cached and audio.is_file():
            emit(f"reusing narration from the previous attempt ({cached.get('duration', 0):.0f}s)")
        else:
            with stage("speech synthesis", f"{doc.word_count} words, Charon"):
                synthesize_gemini_audio(doc.full_narration, audio, voice='Charon', model=DEFAULT_MODEL)
        duration = _probe_duration(audio)
        if duration is None or duration < MIN_NARRATION_SECONDS:
            raise RuntimeError(
                f'Actual Charon narration is {duration or 0:.0f}s; the channel needs '
                f'{MIN_NARRATION_SECONDS}s ({MIN_NARRATION_SECONDS // 60} minutes). '
                f'{doc.word_count} words is too short at Charon\'s pace — lengthen the script, '
                f'the floor is {MIN_LONGFORM_WORDS} words.')
        _write_json(out / 'narration.json', {'key': speech_key, 'duration': duration})

        align_key = _fingerprint("align-v1", speech_key, duration)
        cached_words = _cached_json(out / 'words.json', align_key)
        if cached_words and cached_words.get('words'):
            words = [tuple(w) for w in cached_words['words']]
            emit(f"reusing the previous word alignment ({len(words)} words)")
        else:
            with stage("speech alignment", f"{duration:.0f}s of audio"):
                words = align(audio, doc.full_narration, Path(model_dir))
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
        # Thumbnails come from the CTR pack, never from the card generator: it enforces
        # mobile legibility, contrast, safe zones and visibility against YouTube's
        # dark-mode page, and writes a report so the run page shows the numbers.
        # See docs/THUMBNAIL_RESEARCH.md.
        from .thumbnail_ctr import curated_backdrop_for, pick_backdrop

        with stage("thumbnail pack", "3 concepts"):
            thumb_reports = generate_ctr_pack(out / "thumbnails",
                                              hero_override=doc.meta.get("thumb_text"),
                                              doc_key=doc.id or doc.slug,
                                              backdrop=pick_backdrop(assets) or curated_backdrop_for(doc.id or doc.slug))
        for report in thumb_reports:
            mobile_preview(report.path, report.path.with_name(report.path.stem + "_mobile.png"))
        (out / "thumbnails" / "report.json").write_text(
            json.dumps([r.as_dict() for r in thumb_reports], indent=2), encoding="utf-8")
        thumbs = [r.path for r in thumb_reports]
        pack = write_metadata_pack(doc, durations, out)
        from .captions import write_srt_file
        srt_path = write_srt_file(out / 'captions.en.srt', words, doc.full_narration, duration=duration)
        result = {'id': doc.id, 'slug': doc.slug, 'video': str(final), 'thumbnail': str(thumbs[0]),
                  'captions': str(srt_path) if srt_path else '',
                  'duration_seconds': duration, 'tts_engine': 'gemini-api', 'dry_run': dry_run}
        if not dry_run:
            from .upload import upload
            with stage("upload", "YouTube"):
                up = upload(doc, final, thumbs[0], privacy=doc.meta.get('privacy'),
                            publish_at=doc.meta.get('publish_at'), description=pack.get('description'),
                            caption_path=srt_path, tags=pack.get('tags'))
            if not up.video_id:
                raise RuntimeError('YouTube returned no video ID; queue unchanged')
            # Persist the receipt before any nonessential notification.
            _mark_job_uploaded(path, doc, up.video_id)
            result.update(video_id=up.video_id, watch_url=up.watch_url,
                          privacy_status=up.privacy_status, uploaded=up.privacy_status != 'duplicate_prevented')
            if result['uploaded']:
                _open_release_ticket(doc, up.watch_url, up.privacy_status, up.video_id)
        (out / 'job_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    except (GeminiQuotaExceededError, QuotaExceededError) as exc:
        reset = getattr(exc, 'reset_utc', None)
        if not dry_run:
            pause_longform_job_on_quota(path, str(exc), reset)
        return {'job': doc.id, 'status': 'quota_paused', 'quota_reset_utc': reset.isoformat() if reset else None}
