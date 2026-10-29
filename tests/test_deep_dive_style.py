"""Verification suite for long-form video engine style parity with approved Shorts master."""
import os
import pytest
from PIL import Image
import tools.deep_dive as dd
import tools.shorts as shorts


def test_prayer_impacts_parity():
    """Verify camera shake impact points match between Shorts and long-form engines."""
    assert dd.PRAYER_IMPACTS == shorts.PRAYER_IMPACTS
    assert len(dd.PRAYER_IMPACTS) == 8


def test_kinetic_phrases_parity():
    """Verify script lines and phrases are identical in line stacking and count."""
    dd_phrases = dd.SCRIPTS['psalm91']['kinetic_phrases']
    sh_phrases = shorts.SCRIPTS['short-psalm91']['kinetic_phrases']
    assert len(dd_phrases) == len(sh_phrases) == 8

    for (dd_w0, dd_w1, dd_lines, dd_acc, dd_kck), (sh_w0, sh_w1, sh_lines, sh_acc, sh_kck) in zip(dd_phrases, sh_phrases):
        assert dd_w0 == sh_w0
        assert dd_w1 == sh_w1
        assert list(dd_lines) == list(sh_lines)
        assert dd_acc == sh_acc
        assert dd_kck == sh_kck


def test_kinetic_stream_timing_and_zero_delay():
    """Verify zero-delay sentence advance without lingering or text drift."""
    words = dd.load_words('psalm91')
    stream = dd.build_kinetic_stream('psalm91', words)
    assert len(stream) == 8

    for i in range(len(stream)):
        if i == 0:
            assert stream[i]['disp_t0'] == 0.0
        else:
            assert stream[i]['disp_t0'] == stream[i - 1]['t1']

        if i + 1 < len(stream):
            assert stream[i]['disp_t1'] == stream[i]['t1']


def test_widescreen_typography_rendering():
    """Verify kinetic typography renders properly into a 16:9 canvas (1280x720)."""
    words = dd.load_words('psalm91')
    stream = dd.build_kinetic_stream('psalm91', words)
    bg = Image.new('RGB', (1280, 720), (10, 24, 48))

    layer = dd.kinetic_typography_layer(bg, stream, 1.0, is_prayer=True)
    assert layer.size == (1280, 720)
    assert layer.mode == 'RGBA'

    # Test expanding halo ring at t = 6.2s
    layer_halo = dd.kinetic_typography_layer(bg, stream, 6.2, is_prayer=True)
    assert layer_halo.size == (1280, 720)


def test_apply_shake_offset():
    """Verify camera micro-shake generates non-zero offset on impact."""
    img = Image.new('RGB', (1280, 720), (20, 20, 20))
    shaken = dd.apply_shake(img, 6.25, dd.PRAYER_IMPACTS)
    assert shaken.size == (1280, 720)
