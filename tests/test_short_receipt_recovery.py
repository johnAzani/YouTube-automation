"""Recover duplicate Shorts without re-uploading or inventing receipt facts."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from pipeline import short_release as release, upload
from pipeline.script_doc import parse_script
from scripts import sync_published_thumbnails as sync

VIDEO = "FNRQnoo_-cU"
TITLE = "Pray This Joshua 24:15 Family Prayer Over Your Home | Family Prayer #Shorts"


def client_for(**overrides):
    client = mock.MagicMock()
    client.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "UC_expected", "snippet": {"title": "Family"}}]}
    item = {"id": VIDEO, "snippet": {"channelId": "UC_expected", "title": TITLE,
            "publishedAt": "2026-11-11T12:03:29Z"},
            "status": {"privacyStatus": "public", "uploadStatus": "processed"},
            "contentDetails": {"duration": "PT54S"}}
    for key, fields in overrides.items():
        if isinstance(fields, dict):
            item[key].update(fields)
        else:
            item[key] = fields
    client.videos.return_value.list.return_value.execute.return_value = {"items": [item]}
    return client


def inspect_with(client):
    with mock.patch.object(upload.CONFIG, "expected_youtube_channel_id", "UC_expected"), \
         mock.patch.object(upload, "_credentials", return_value=mock.Mock()), \
         mock.patch("googleapiclient.discovery.build", return_value=client):
        return upload.inspect_existing_short(VIDEO, TITLE)


def test_inspection_checks_channel_video_title_and_public_status():
    client = client_for()
    info = inspect_with(client)
    assert info == {"video_id": VIDEO, "title": TITLE, "privacy_status": "public",
                    "upload_status": "processed", "published_at": "2026-11-11T12:03:29Z", "duration": "PT54S"}
    client.videos.return_value.insert.assert_not_called()
    client.videos.return_value.update.assert_not_called()
    client.thumbnails.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"snippet": {"channelId": "UC_other"}}, {"snippet": {"title": "Different prayer"}},
    {"snippet": {"publishedAt": ""}}, {"status": {"privacyStatus": ""}},
    {"status": {"uploadStatus": "rejected"}}, {"id": "not_the_id_"},
])
def test_inspection_fails_closed_on_unverified_data(changes):
    with pytest.raises(RuntimeError):
        inspect_with(client_for(**changes))


def test_inspection_fails_if_expected_channel_unconfigured_or_wrong():
    with mock.patch.object(upload.CONFIG, "expected_youtube_channel_id", ""):
        with pytest.raises(RuntimeError, match="expected channel ID"):
            upload.inspect_existing_short(VIDEO, TITLE)
    client = client_for()
    client.channels.return_value.list.return_value.execute.return_value = {"items": [{"id": "UC_other"}]}
    with pytest.raises(RuntimeError, match="Refusing to upload"):
        inspect_with(client)


def _edition():
    return release.ShortEdition(key="short-test", job_id="SHORT-TEST", slug="short-test-recovery",
                                title=TITLE, niche="faith and prayer", tags=[],
                                description="A prayer.", channel="prayer5")


def _video():
    return {"video_id": VIDEO, "title": TITLE, "privacy_status": "public",
            "upload_status": "processed", "published_at": "2026-11-11T12:03:29Z", "duration": "PT54S"}


def _prepare_run(tmp_path, monkeypatch, inspect_result):
    root = tmp_path
    (root / "social").mkdir()
    (root / "social/short-test.mp4").write_bytes(b"rendered")
    src = root / "output/short-stock/short-test"
    src.mkdir(parents=True)
    (src / "scene-sources.json").write_text('[{"scene":1}]')
    manifest = root / "queue.yml"
    manifest.write_text("short: short-test\nstatus: approved\n")
    monkeypatch.setattr(release, "REPO_ROOT", root)
    monkeypatch.setattr(release, "PUBLISHED_DIR", root / "published")
    monkeypatch.setattr(release, "OUTPUT_DIR", root / "output")
    monkeypatch.setattr(release, "resolve_edition", lambda *a, **kw: _edition())
    monkeypatch.setattr(release, "_require_production_prerequisites", lambda *a: None)
    monkeypatch.setattr(release, "verify_short_render", lambda *a: release.MediaProbe(True, True, 720, 1280, 54.0))
    monkeypatch.setattr(release.CONFIG, "channel_id", "prayer5")
    from pipeline import shorts_poster
    report = SimpleNamespace(width=1080, height=1920, contrast=10, hero_px=90, grade="test",
                             as_dict=lambda: {"lines": ["ONE", "TWO"], "kicker": "PRAYER", "plate": ""})
    monkeypatch.setattr(shorts_poster, "render_shorts_poster", lambda *a, **kw: report)
    monkeypatch.setattr(upload, "upload", mock.Mock(return_value=SimpleNamespace(
        privacy_status="duplicate_prevented", video_id=VIDEO)))
    monkeypatch.setattr(upload, "inspect_existing_short", mock.Mock(side_effect=inspect_result if isinstance(inspect_result, Exception) else None,
                                                                   return_value=inspect_result))
    thumbnail = mock.Mock()
    monkeypatch.setattr(upload, "apply_shorts_thumbnail", thumbnail)
    return manifest, root / "published/short-test-recovery.md", thumbnail


def test_duplicate_creates_truthful_receipt_then_removes_manifest(tmp_path, monkeypatch):
    manifest, path, thumbnail = _prepare_run(tmp_path, monkeypatch, _video())
    result = release.run_short_release("short-test", skip_render=True, manifest_path=manifest)
    assert result["duplicate_prevented"] and result["receipt_recovered"] and not result["uploaded"]
    assert not manifest.exists() and path.exists()
    meta = parse_script(path).meta
    assert meta["youtube_video_id"] == VIDEO and meta["published_at"] == '2026-11-11T12:03:29Z'
    assert meta["privacy_status"] == "public" and meta["thumbnail_pending"] is True
    assert meta["receipt_recovered_from_youtube"] is True and "thumbnail_revision" not in meta
    assert release._read_previous_video_id(path) == VIDEO
    assert [p for p, _ in sync.collect_pending_short_receipts(path.parent, channel_id="prayer5")] == [path]
    thumbnail.assert_not_called()
    sync.stamp_frontmatter_field(path, "thumbnail_poster", '["ONE", "TWO"]', raw=True)
    assert parse_script(path).meta['thumbnail_poster'] == ["ONE", "TWO"]


def test_duplicate_verification_failure_keeps_manifest_and_no_receipt(tmp_path, monkeypatch):
    manifest, path, thumbnail = _prepare_run(tmp_path, monkeypatch, RuntimeError("lookup failed"))
    with pytest.raises(RuntimeError, match="lookup failed"):
        release.run_short_release("short-test", skip_render=True, manifest_path=manifest)
    assert manifest.exists() and not path.exists()
    thumbnail.assert_not_called()


def test_duplicate_write_failure_keeps_manifest(tmp_path, monkeypatch):
    manifest, path, thumbnail = _prepare_run(tmp_path, monkeypatch, _video())
    monkeypatch.setattr(release, '_write_recovered_short_record', mock.Mock(side_effect=OSError('disk error')))
    with pytest.raises(OSError, match='disk error'):
        release.run_short_release('short-test', skip_render=True, manifest_path=manifest)
    assert manifest.exists() and not path.exists()
    thumbnail.assert_not_called()


def test_recovery_never_overwrites_existing_receipt(tmp_path):
    path = tmp_path / 'existing.md'
    path.write_text('keep me')
    with pytest.raises(FileExistsError):
        release._write_recovered_short_record(path, _edition(), _video())
    assert path.read_text() == 'keep me'


def test_real_recovered_receipt_keeps_verified_identity_without_reupload():
    path = Path(__file__).resolve().parents[1] / 'content/published/short-familyjoshua24v15-household-prayer.md'
    doc = parse_script(path)
    assert doc.meta['youtube_video_id'] == VIDEO and doc.meta['privacy_status'] == 'public'
    assert doc.meta['receipt_recovered_from_youtube'] is True
    assert doc.meta['published_at'] == '2026-11-11T12:03:29Z'
    # The thumbnail may be cooling down or eventually applied; its current state
    # is live operational data, not an invariant of the recovered receipt.
