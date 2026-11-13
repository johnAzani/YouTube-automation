"""Future prayer Shorts show all narration and use distinct, traceable footage."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image

from pipeline import assets, short_release
from pipeline.short_script import load_spec
from tools import shorts

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('key', ['short-gardenpsalm100v4', 'short-guidedproverbs3v5',
                                 'short-middaypsalm37v5', 'short-psalm91v11'])
def test_every_narration_word_is_shown_once_in_order(key):
    spec = load_spec(ROOT / 'content/shorts-scripts' / f'{key}.json')
    assert not spec.problems
    expected = [w for cap in spec.captions for w in cap[2].split()
                if short_release._clean_word_token(w)]
    timings = [[i * .4, i * .4 + .3, short_release._clean_word_token(w)]
               for i, w in enumerate(expected)]
    with mock.patch.dict(shorts.SCRIPTS, {key: spec.to_renderer()}):
        cards = shorts.build_kinetic_stream(key, timings, adur=len(timings) * .4 + 1)
    assert [w for card in cards for w in card['card_words']] == [w.upper() for w in expected]
    assert [t for card in cards for t in card['word_timings']] == [(w[0], w[1]) for w in timings]
    assert all(1 <= len(card['lines']) <= 3 for card in cards)
    assert all(a['disp_t1'] <= b['disp_t0'] for a, b in zip(cards, cards[1:]))
    assert cards[-1]['disp_t1'] >= timings[-1][1]
    bg = Image.new('RGB', (720, 1280), (20, 30, 40))
    for card in cards:
        assert shorts.kinetic_typography_layer(bg, [card], card['disp_t0'], is_prayer=True).size == (720, 1280)


def test_all_valid_authored_prayer_specs_show_the_full_script():
    from pipeline.short_script import load_authored
    for key, cfg in load_authored().items():
        expected = [w for cap in cfg['captions'] for w in cap[2].split()
                    if short_release._clean_word_token(w)]
        timing = [[i * .4, i * .4 + .3, short_release._clean_word_token(w)]
                  for i, w in enumerate(expected)]
        with mock.patch.dict(shorts.SCRIPTS, {key: cfg}):
            cards = shorts.build_kinetic_stream(key, timing, adur=len(timing) * .4 + 1)
        assert [word for card in cards for word in card['card_words']] == [w.upper() for w in expected], key
        assert all(len(card['lines']) <= 3 for card in cards), key


def test_mismatched_timings_refuse_to_show_wrong_words():
    cfg = {'captions': [[0, 1, 'A full prayer']], 'kinetic_phrases': []}
    with pytest.raises(ValueError, match='complete narration'):
        shorts._narration_kinetic_stream(cfg, [[0, .1, 'a'], [.1, .2, 'wrong']])


def test_aligned_timing_cache_is_bound_to_audio_text_and_data(tmp_path, monkeypatch):
    audio = tmp_path / 'short-test.mp3'
    audio.write_bytes(b'audio one')
    (tmp_path / 'output' / 'alignment-model').mkdir(parents=True)
    monkeypatch.setattr(short_release, 'REPO_ROOT', tmp_path)
    rows = [('A', 0, .2), ('prayer', .2, .8)]
    with mock.patch('pipeline.prayer_alignment.align', return_value=rows) as align:
        path = short_release._ensure_word_timings('short-test', audio, 'A prayer')
        short_release._ensure_word_timings('short-test', audio, 'A prayer')
        assert align.call_count == 1
        path.write_text('[]')
        short_release._ensure_word_timings('short-test', audio, 'A prayer')
        audio.write_bytes(b'different audio')
        short_release._ensure_word_timings('short-test', audio, 'A prayer')
        assert align.call_count == 3
    with mock.patch('pipeline.prayer_alignment.align', side_effect=RuntimeError('no model')):
        audio.write_bytes(b'another audio')
        with pytest.raises(RuntimeError, match='alignment unavailable'):
            short_release._ensure_word_timings('short-test', audio, 'A prayer')


def test_pexels_selects_other_candidates_when_a_source_is_excluded(tmp_path, monkeypatch):
    data = {'videos': [{'id': i, 'url': f'https://pexels.test/{i}',
                        'video_files': [{'link': f'https://media.test/{i}', 'width': 720, 'height': 1280}]}
                       for i in range(1, 5)]}
    monkeypatch.setattr(assets.CONFIG, 'pexels_api_key', 'test')
    monkeypatch.setattr(assets, '_http_get', lambda *a, **kw: SimpleNamespace(json=lambda: data))
    monkeypatch.setattr(assets, '_cache_path', lambda source, ident, ext: tmp_path / f'{ident}.{ext}')
    def download(url, dest):
        dest.write_bytes(url.encode()); return True
    monkeypatch.setattr(assets, '_download', download)
    first = assets._pexels('nature', True, 720, 1280, selection_seed='edition:0')
    second = assets._pexels('nature', True, 720, 1280, selection_seed='edition:1',
                            exclude_sources={assets._visual_source_id(first.origin_url)})
    assert first.origin_url != second.origin_url
    assert assets._pexels('nature', True, 720, 1280,
                          exclude_sources={assets._visual_source_id(v['url']) for v in data['videos']}) is None


def test_short_tries_a_different_keyed_result_after_bad_or_repeated_clip(tmp_path, monkeypatch):
    first_path, second_path = tmp_path / 'first.mp4', tmp_path / 'second.mp4'
    first_path.write_bytes(b'one'); second_path.write_bytes(b'two')
    first = assets.Asset(first_path, 'pexels', 'https://pexels.test/first', 'Pexels', 'video', width=720, height=1280)
    second = assets.Asset(second_path, 'pexels', 'https://pexels.test/second', 'Pexels', 'video', width=720, height=1280)
    def provider(q, video, w, h, *, exclude_sources, selection_seed):
        return second if assets._visual_source_id(first.origin_url) in exclude_sources else first
    monkeypatch.setattr(assets, '_pexels', provider)
    monkeypatch.setattr(shorts, '_is_vivid_video_clip', lambda path: path == second_path)
    result = shorts._acquire_short_asset('mountain', 1, tmp_path, selection_seed='edition:0')
    assert result.origin_url == second.origin_url


def test_footage_gate_rejects_one_clip_or_decode_fallback():
    one, two = 'sha256:' + '1' * 64, 'sha256:' + '2' * 64
    rows = [{'media': 'video', 'fallback': False, 'source_fingerprints': [one]},
            {'media': 'video', 'fallback': False, 'source_fingerprints': [one]},
            {'media': 'authored photo fallback', 'fallback': True, 'source_fingerprints': [two]}]
    assert short_release._verified_video_fingerprints(rows) == {one}
    rows[2].update(media='video', fallback=False)
    assert short_release._verified_video_fingerprints(rows) == {one, two}


def test_recent_receipts_are_channel_scoped_and_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(short_release, 'PUBLISHED_DIR', tmp_path)
    def receipt(name, channel, date, value):
        (tmp_path / name).write_text('---\nchannel: ' + channel + '\npublished_at: "' + date + '"\n'
                                     'short_visual_fingerprints: ' + json.dumps([value]) + '\n---\n\nReceipt.\n', encoding='utf-8')
    ids = ['url:' + str(i) * 64 for i in range(1, 6)]
    for i in range(4):
        receipt(f'{i}.md', 'prayer9', f'2026-11-0{i+1}T00:00:00Z', ids[i])
    receipt('other.md', 'prayer10', '2026-11-05T00:00:00Z', ids[4])
    assert short_release._recent_short_visuals('prayer9') == set(ids[1:4])
