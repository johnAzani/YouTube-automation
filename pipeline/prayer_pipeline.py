"""Approved-style long-form production path (not yet enabled on main)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

from .config import CONFIG, OUTPUT_DIR
from .script_doc import parse_script
from .originality import enforce
from .gemini_tts import DEFAULT_MODEL, get_gemini_api_key, synthesize_gemini_audio
from .prayer_alignment import align
from .prayer_visuals import render
from .tts import _probe_duration


def produce(path: Path, dry_run: bool, model_dir: Path) -> dict:
    """Run the approved rendering pipeline with hard safety checks.

    Alignment weights must already be local. This path never uses placeholder,
    alternate-model or non-Charon speech, or a legacy subtitle renderer.
    """
    from .run import _mark_job_uploaded, _open_release_ticket, _require_production_prerequisites
    from .assets import fetch_scene_assets
    from .metadata import write_metadata_pack
    from .thumbnail import generate_thumbnail_variants
    from .quota_handler import GeminiQuotaExceededError, QuotaExceededError, pause_longform_job_on_quota

    doc = parse_script(path)
    if doc.format != 'longform' or not any(term in str(doc.meta.get('niche', '')).lower() for term in ('faith', 'prayer', 'scripture', 'devotional')):
        raise RuntimeError('Only long-form prayer content is permitted')
    if doc.voice != 'Charon':
        raise RuntimeError('The permanent prayer voice is Charon')
    enforce(doc)
    _require_production_prerequisites(doc, dry_run, CONFIG.youtube_refresh_token,
                                      CONFIG.youtube_client_id, CONFIG.youtube_client_secret)
    if not get_gemini_api_key():
        raise RuntimeError('Gemini API key missing; refusing voice substitution')
    if not (Path(model_dir) / 'model.bin').is_file() or importlib.util.find_spec('faster_whisper') is None:
        raise RuntimeError('Offline speech alignment model is not installed')
    if not doc.scenes:
        raise RuntimeError('No prayer scenes in script')
    # Avoid consuming quota for scripts too short to plausibly reach five minutes.
    if doc.word_count < 650:
        raise RuntimeError(f'Prayer script has only {doc.word_count} words; expand it before full-length production')
    out = OUTPUT_DIR / doc.slug
    out.mkdir(parents=True, exist_ok=True)
    audio = out / 'narration.mp3'
    try:
        synthesize_gemini_audio(doc.full_narration, audio, voice='Charon', model=DEFAULT_MODEL)
        duration = _probe_duration(audio)
        if duration is None or duration < 300:
            raise RuntimeError('Actual Charon narration is shorter than five minutes')
        words = align(audio, doc.full_narration, Path(model_dir))
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
        for scene in doc.scenes:
            matches = fetch_scene_assets(scene.asset_query or scene.heading, scene.index,
                                         out / 'assets', target_width=1280, target_height=720,
                                         allow_generated=False)
            if not matches:
                raise RuntimeError(f'No licensed asset for scene {scene.index}')
            assets.append(matches[0].path)
        final = render(audio, list(zip(assets, durations)), words, duration,
                       out / f'{doc.slug}.mp4', timing_source='measured')
        thumbs = generate_thumbnail_variants(doc, assets[0], out)
        pack = write_metadata_pack(doc, durations, out)
        result = {'id': doc.id, 'slug': doc.slug, 'video': str(final), 'thumbnail': str(thumbs[0]),
                  'duration_seconds': duration, 'tts_engine': 'gemini-api', 'dry_run': dry_run}
        if not dry_run:
            from .upload import upload
            up = upload(doc, final, thumbs[0], privacy=doc.meta.get('privacy'),
                        publish_at=doc.meta.get('publish_at'), description=pack.get('description'))
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
