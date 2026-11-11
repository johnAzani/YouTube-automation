"""A recovery note must never be sent to a live video as its description."""
from pathlib import Path
from unittest import mock

import pytest

from pipeline import short_release
from pipeline.script_doc import parse_script
from scripts import retrofit_published_metadata as retrofit
from scripts import sync_published_thumbnails as thumbnails


@pytest.fixture
def receipt(tmp_path):
    path = tmp_path / 'short-recovered.md'
    path.write_text('''---
id: SHORT-TEST
title: Family Prayer #Shorts
slug: short-family-test
status: published
format: short
channel: prayer5
niche: faith and prayer
youtube_video_id: FNRQnoo_-cU
receipt_recovered_from_youtube: true
thumbnail_pending: true
---

This receipt was recovered from an existing YouTube video. No video was uploaded during recovery; the custom thumbnail status is unverified.
''')
    return path


@pytest.mark.parametrize('only_pending', [True, False])
def test_recovery_metadata_is_held_even_on_force(receipt, only_pending):
    updater = mock.Mock()
    before = receipt.read_text()
    assert retrofit.collect_published_faith_targets(receipt.parent, only_pending=only_pending) == []
    assert retrofit.sync_published_metadata(published_dir=receipt.parent, only_pending=only_pending, updater=updater) == []
    updater.assert_not_called()
    assert receipt.read_text() == before
    assert 'metadata_revision' not in parse_script(receipt).meta
    assert [p for p, _ in thumbnails.collect_pending_short_receipts(receipt.parent, channel_id='prayer5')] == [receipt]


def test_approval_alone_does_not_publish_the_recovery_note(receipt):
    text = receipt.read_text().replace('thumbnail_pending: true', 'thumbnail_pending: true\nmetadata_retrofit_approved: true')
    receipt.write_text(text)
    assert retrofit.collect_published_faith_targets(receipt.parent, only_pending=False) == []


def test_explicit_approval_and_reviewed_description_allow_sync(receipt):
    text = receipt.read_text().replace('thumbnail_pending: true', 'thumbnail_pending: true\nmetadata_retrofit_approved: true')
    receipt.write_text(text.replace('This receipt was recovered from an existing YouTube video. No video was uploaded during recovery; the custom thumbnail status is unverified.', 'A reviewed family prayer description.'))
    targets = retrofit.collect_published_faith_targets(receipt.parent, only_pending=True)
    assert len(targets) == 1 and 'reviewed family prayer' in targets[0]['description']


def test_fresh_recovered_receipt_records_the_explicit_hold(tmp_path):
    edition = short_release.ShortEdition('short-test', 'SHORT-TEST', 'short-test', 'Family Prayer #Shorts',
                                         'faith and prayer', [], 'Prayer.', 'prayer5')
    video = {'video_id': 'FNRQnoo_-cU', 'title': edition.title, 'privacy_status': 'public',
             'upload_status': 'processed', 'published_at': '2026-11-11T12:03:29Z', 'duration': 'PT54S'}
    path = short_release._write_recovered_short_record(tmp_path / 'short-test.md', edition, video)
    meta = parse_script(path).meta
    assert meta['metadata_retrofit_approved'] is False and 'metadata_revision' not in meta
    assert retrofit.collect_published_faith_targets(tmp_path, only_pending=False) == []


def test_live_recovered_receipt_is_held_without_false_revision_changes():
    path = Path(__file__).resolve().parents[1] / 'content/published/short-familyjoshua24v15-household-prayer.md'
    assert all(t['video_id'] != 'FNRQnoo_-cU' for t in retrofit.collect_published_faith_targets(path.parent, only_pending=False))
