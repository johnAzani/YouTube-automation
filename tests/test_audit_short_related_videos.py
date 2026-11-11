from pathlib import Path

from scripts.audit_short_related_videos import find_candidates


def receipt(root: Path, name: str, *, channel='prayer5', kind='longform',
            title='Joshua 24:15 Family Prayer', video='AAAAAAAAAAA',
            visibility='public', extra=''):
    (root / name).write_text(
        f'---\nid: TEST\ntitle: "{title}"\nslug: test\nchannel: {channel}\n'
        f'format: {kind}\nprivacy_status: {visibility}\nyoutube_video_id: "{video}"\n'
        f'{extra}---\n\nA prayer.\n', encoding='utf-8')


def test_same_channel_scripture_pair_only(tmp_path):
    receipt(tmp_path, 'short.md', kind='short', video='BBBBBBBBBBB')
    receipt(tmp_path, 'good.md')
    receipt(tmp_path, 'wrong-channel.md', channel='prayer6', video='CCCCCCCCCCC')
    receipt(tmp_path, 'wrong-scripture.md', title='Joshua 24:16 Family Prayer', video='DDDDDDDDDDD')
    pairs = find_candidates(tmp_path)
    assert len(pairs) == 1
    assert pairs[0]['channel'] == 'prayer5'
    assert pairs[0]['short']['video_id'] == 'BBBBBBBBBBB'
    assert [v['video_id'] for v in pairs[0]['longforms']] == ['AAAAAAAAAAA']
    assert not pairs[0]['ambiguous']


def test_excludes_unknown_private_conflicting_deleted_and_invalid_receipts(tmp_path):
    receipt(tmp_path, 'short.md', kind='short', video='BBBBBBBBBBB')
    receipt(tmp_path, 'private.md', visibility='private')
    receipt(tmp_path, 'unknown.md', visibility='', video='CCCCCCCCCCC')
    receipt(tmp_path, 'conflict.md', extra='privacy: private\n', video='DDDDDDDDDDD')
    receipt(tmp_path, 'deleted.md', extra='youtube_status: deleted_or_missing\n', video='EEEEEEEEEEE')
    receipt(tmp_path, 'rejected.md', extra='youtube_upload_status: rejected\n', video='FFFFFFFFFFF')
    receipt(tmp_path, 'invalid.md', video='bad')
    assert find_candidates(tmp_path) == []


def test_ambiguity_and_duplicate_receipts_are_not_hidden(tmp_path):
    receipt(tmp_path, 'short.md', kind='short', video='BBBBBBBBBBB')
    receipt(tmp_path, 'long-one.md')
    receipt(tmp_path, 'duplicate.md')
    receipt(tmp_path, 'long-two.md', video='CCCCCCCCCCC')
    pair = find_candidates(tmp_path)[0]
    assert pair['ambiguous']
    assert {v['video_id'] for v in pair['longforms']} == {'AAAAAAAAAAA', 'CCCCCCCCCCC'}


def test_generic_titles_and_same_video_are_not_matched(tmp_path):
    receipt(tmp_path, 'short.md', kind='short', title='A Family Prayer', video='BBBBBBBBBBB')
    receipt(tmp_path, 'long.md', title='A Family Prayer')
    assert find_candidates(tmp_path) == []
    receipt(tmp_path, 'short.md', kind='short', video='AAAAAAAAAAA')
    receipt(tmp_path, 'long.md')
    assert find_candidates(tmp_path) == []
