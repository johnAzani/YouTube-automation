"""Long-form recovery must verify remote facts before retiring the queue job."""
from pathlib import Path
from unittest import mock

import pytest

from pipeline import prayer_pipeline, run, upload
from pipeline.script_doc import parse_script

VIDEO = 'FNRQnoo_-cU'
TITLE = 'Psalm 46 Prayer'


def _youtube(privacy='private', upload_status='processed', channel='UC_expected'):
    youtube = mock.MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {
        'items': [{'id': 'UC_expected', 'snippet': {'title': 'Test'}}]}
    youtube.videos.return_value.list.return_value.execute.return_value = {'items': [{
        'id': VIDEO,
        'snippet': {'channelId': channel, 'title': TITLE, 'publishedAt': '2026-11-01T11:42:00Z'},
        'status': {'privacyStatus': privacy, 'uploadStatus': upload_status},
        'contentDetails': {'duration': 'PT5M30S'},
    }]}
    return youtube


def _inspect(youtube):
    with mock.patch.object(upload.CONFIG, 'expected_youtube_channel_id', 'UC_expected'), \
         mock.patch.object(upload, '_credentials', return_value=object()), \
         mock.patch('googleapiclient.discovery.build', return_value=youtube):
        return upload.inspect_existing_longform(VIDEO, TITLE)


def test_longform_inspection_reads_actual_remote_facts_without_mutating():
    youtube = _youtube()
    info = _inspect(youtube)
    assert info['privacy_status'] == 'private'
    assert info['published_at'] == '2026-11-01T11:42:00Z'
    assert info['upload_status'] == 'processed'
    youtube.videos.return_value.insert.assert_not_called()
    youtube.videos.return_value.update.assert_not_called()
    youtube.thumbnails.assert_not_called()


@pytest.mark.parametrize('client', [
    _youtube(channel='UC_other'), _youtube(upload_status='rejected'),
    _youtube(privacy=''),
])
def test_longform_inspection_rejects_unverified_video(client):
    with pytest.raises(RuntimeError):
        _inspect(client)


def _job(tmp_path):
    path = tmp_path / '0013-x.md'
    path.write_text('---\nid: "0013"\nslug: psalm-46\nstatus: approved\n'
                    'format: longform\nniche: faith and prayer\ntitle: Psalm 46 Prayer\n'
                    'privacy: public\nnarration_voice: Charon\n'
                    'thumbnail_revision: old\nmetadata_revision: stale\n---\n\n'
                    '## Scene 1 — One\nA prayer.\n', encoding='utf-8')
    return path


def test_recovery_records_remote_privacy_time_without_unverified_claims(tmp_path, monkeypatch):
    path = _job(tmp_path)
    published = tmp_path / 'published'
    info = _inspect(_youtube())
    monkeypatch.setattr(run, 'PUBLISHED_DIR', published)
    monkeypatch.setattr(prayer_pipeline, 'OUTPUT_DIR', tmp_path / 'output')
    monkeypatch.setattr(prayer_pipeline, 'already_published', lambda doc: VIDEO)
    monkeypatch.setattr(upload, 'inspect_existing_longform', lambda *a: info)
    monkeypatch.setattr(prayer_pipeline, '_refresh_live_thumbnail', lambda *a: None)
    result = prayer_pipeline.record_if_live(path)
    assert result['privacy_status'] == 'already_published'
    assert result['youtube_privacy_status'] == 'private'
    assert not path.exists()
    meta = parse_script(published / path.name).meta
    assert meta['youtube_video_id'] == VIDEO
    assert meta['published_at'] == '2026-11-01T11:42:00Z'
    assert meta['published_on'] == '2026-11-01'
    assert meta['privacy'] == meta['privacy_status'] == 'private'
    assert meta['receipt_recovered_from_youtube'] is True
    assert meta['metadata_retrofit_approved'] is False
    assert meta['thumbnail_pending'] is True
    for key in ('narration_engine', 'narration_voice', 'thumbnail_revision', 'metadata_revision'):
        assert key not in meta


def test_unverified_recovery_leaves_queue_and_does_not_touch_thumbnail(tmp_path, monkeypatch):
    path = _job(tmp_path)
    original = path.read_text()
    monkeypatch.setattr(run, 'PUBLISHED_DIR', tmp_path / 'published')
    monkeypatch.setattr(prayer_pipeline, 'already_published', lambda doc: VIDEO)
    monkeypatch.setattr(upload, 'inspect_existing_longform', mock.Mock(side_effect=RuntimeError('lookup failed')))
    thumb = mock.Mock()
    monkeypatch.setattr(prayer_pipeline, '_refresh_live_thumbnail', thumb)
    with pytest.raises(RuntimeError, match='lookup failed'):
        prayer_pipeline.record_if_live(path)
    assert path.read_text() == original
    assert not (tmp_path / 'published').exists()
    thumb.assert_not_called()


def test_recovery_refuses_bad_timestamp_before_modifying_queue(tmp_path, monkeypatch):
    path = _job(tmp_path)
    original = path.read_text()
    monkeypatch.setattr(run, 'PUBLISHED_DIR', tmp_path / 'published')
    info = {'video_id': VIDEO, 'privacy_status': 'public', 'upload_status': 'processed',
            'published_at': '2026-11-01'}
    with pytest.raises(RuntimeError, match='timestamp'):
        run._mark_job_uploaded(path, parse_script(path), VIDEO, recovered_video=info)
    assert path.read_text() == original
