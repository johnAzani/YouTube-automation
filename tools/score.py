#!/usr/bin/env python3
"""Procedural score + sound design for deep-dive clips. Pure numpy -> WAV.

Music: cinematic minor-key pad (FFT-softened harmonics), sub drone, heartbeat
pulse, wind bed, with swells at scene cuts and a finale lift. SFX: whooshes on
motion-graphics entrances, risers before stats, booms on count-up landings,
scene swishes, low rumbles for disaster beats.

Run standalone or via tools/deep_dive.py which calls generate_score().

Usage: .venv/bin/python tools/score.py <key> <total_seconds>
"""
import os, sys, wave, math
import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'deepdive')

# ------------------------------------------------------------- dsp helpers ----
def _fft_shape(x, cutoff, order=2.0):
    """Gentle spectral rolloff above cutoff (order=2 => 12 dB/oct feel)."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X *= 1.0 / (1.0 + (f / max(1.0, cutoff)) ** order)
    return np.fft.irfft(X, n)

def _env_adsr(n, a, r):
    if n <= 0:
        return np.zeros(0)
    e = np.ones(n)
    na = min(int(a * SR), max(0, n - 1))
    nr = min(int(r * SR), max(0, n - na))
    if na > 0:
        e[:na] = np.linspace(0, 1, na) ** 1.5
    if nr > 0:
        e[n - nr:] = np.linspace(1, 0, nr) ** 1.6
    return e

def _tone(freq, n, detune=1.0, seed=0):
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for h, a in ((1, 1.0), (2, 0.30), (3, 0.13), (4, 0.06), (5, 0.03)):
        x += a * np.sin(2 * np.pi * freq * h * detune * t + rng.uniform(0, 6.28))
    return x

def _write_wav(path, left, right):
    stereo = np.stack([left, right], axis=1)
    stereo = np.clip(stereo, -1.0, 1.0)
    data = (stereo * 32767).astype('<i2').tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
    print('wrote', path, f'{len(left)/SR:.1f}s')

# ------------------------------------------------------------------- music ----
# minor-key progression: Am  F  C  G  Am  Dm  F  E  (8 segments over the clip)
PROG = [
    (220.00, 261.63, 329.63),   # Am
    (174.61, 220.00, 261.63),   # F
    (130.81, 164.81, 196.00),   # C  (low)
    (196.00, 246.94, 293.66),   # G
    (220.00, 261.63, 329.63),   # Am
    (146.83, 174.61, 220.00),   # Dm
    (174.61, 220.00, 261.63),   # F
    (164.81, 196.00, 246.94),   # E  (dominant -> loops home)
]

def _pad_bed(total, detune, seed):
    n = int(total * SR)
    out = np.zeros(n)
    seg = total / len(PROG)
    for i, chord in enumerate(PROG):
        t0 = i * seg
        s0, ln = int(t0 * SR), int((seg + 1.2) * SR)
        ln = min(ln, n - s0)
        if ln <= 0:
            continue
        v = np.zeros(ln)
        for j, f in enumerate(chord):
            v += _tone(f, ln, detune=detune * (1 + 0.0009 * (j - 1)), seed=seed + i * 7 + j) / 3
        v *= _env_adsr(ln, 1.6, 1.4)
        out[s0:s0 + ln] += v
    return _fft_shape(out, 1300, 1.8)

def _music_bed(total, cuts, big_beats):
    n = int(total * SR)
    t = np.arange(n) / SR
    padL = _pad_bed(total, 0.9992, 11)
    padR = _pad_bed(total, 1.0008, 23)
    # sub drone with slow LFO
    sub = (np.sin(2 * np.pi * 55.0 * t) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t))
           + 0.45 * np.sin(2 * np.pi * 82.41 * t))
    # heartbeat pulse
    heart = np.zeros(n)
    thump_n = int(0.32 * SR)
    tt = np.arange(thump_n) / SR
    thump = (np.sin(2 * np.pi * 56 * tt) * np.exp(-tt * 13)
             + 0.55 * np.sin(2 * np.pi * 41 * tt) * np.exp(-tt * 9))
    for k in np.arange(0.9, total - 0.4, 1.18):
        s = int(k * SR)
        heart[s:s + thump_n] += thump[:n - s]
    # wind bed
    rng = np.random.default_rng(5)
    wind = _fft_shape(rng.normal(0, 1, n), 320, 1.4)
    wind *= 0.45 + 0.30 * np.sin(2 * np.pi * 0.07 * t + 1.2)

    swell = np.full(n, 0.30)
    for c in list(cuts[1:-1]) + list(big_beats):
        # lift before, crest at the moment, ease out after
        a0, a1 = int(max(0, (c - 1.6)) * SR), int(min(total, c + 2.6) * SR)
        if a1 <= a0:
            continue
        w = np.linspace(0, 1, a1 - a0)
        shape = np.where(w < 0.38, w / 0.38, 1.0 - (w - 0.38) / 0.62) ** 1.2
        swell[a0:a1] = np.maximum(swell[a0:a1], 0.30 + 0.52 * shape)
    fin = int(max(0, total - 10.0) * SR)
    swell[fin:] = np.maximum(swell[fin:], np.linspace(0.32, 0.92, n - fin))

    center = 0.42 * sub + 0.20 * heart + 0.16 * wind
    left = (0.40 * padL + center) * swell
    right = (0.40 * padR + center) * swell
    peak = max(np.abs(left).max(), np.abs(right).max(), 1e-9)
    return left / peak * 0.30, right / peak * 0.30

# --------------------------------------------------------------------- sfx ----
def _whoosh(amp):
    n = int(0.55 * SR)
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, n)
    tt = np.arange(n) / SR
    hi = _fft_shape(x, 3800, 1.2) * np.exp(-tt * 9)
    lo = _fft_shape(x, 700, 1.4) * np.exp(-tt * 4.5)
    return (hi * 0.7 + lo * 0.9) * amp

def _swish(amp):
    n = int(0.34 * SR)
    rng = np.random.default_rng(4)
    x = rng.normal(0, 1, n)
    tt = np.arange(n) / SR
    return _fft_shape(x * np.exp(-tt * 11), 2600, 1.1) * amp * 1.4

def _boom(amp):
    n = int(1.0 * SR)
    tt = np.arange(n) / SR
    f = 58 * np.exp(-tt * 3.2) + 27
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-tt * 4.2)
    click = np.zeros(n)
    nc = int(0.012 * SR)
    rng = np.random.default_rng(6)
    click[:nc] = rng.normal(0, 1, nc) * np.exp(-np.arange(nc) / SR * 300)
    return (body + 0.22 * _fft_shape(click, 2200, 1.3)) * amp

def _riser(amp, dur=1.15):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(8)
    noise = _fft_shape(rng.normal(0, 1, n), 1400, 1.2) * (tt / dur) ** 2
    f = 190 * (700 / 190) ** (tt / dur)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / dur) ** 2.4
    return (0.8 * noise + 0.5 * tone) * amp

def _rumble(amp, dur=2.8):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(9)
    x = _fft_shape(rng.normal(0, 1, n), 90, 1.8)
    env = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.3
    return x * env * amp * 2.2

def _sfx_bed(total, events):
    n = int(total * SR)
    bed = np.zeros(n)
    for ev in events:
        kind, t, amp = ev['kind'], ev['t'], ev.get('amp', 0.5)
        if kind == 'whoosh':
            buf = _whoosh(amp)
        elif kind == 'swish':
            buf = _swish(amp)
        elif kind == 'boom':
            buf = _boom(amp)
        elif kind == 'riser':
            buf = _riser(amp)
        elif kind == 'rumble':
            buf = _rumble(amp)
        else:
            continue
        s = int(max(0.0, t) * SR)
        ln = min(len(buf), n - s)
        if ln > 0:
            bed[s:s + ln] += buf[:ln]
    peak = np.abs(bed).max() or 1.0
    return bed / peak * 0.42

# ----------------------------------------------------------------- public ----
def generate_score(key, total, cuts, events, out_dir=OUT):
    print(f'score: {key} {total:.1f}s, {len(events)} sfx events')
    big = [e['t'] for e in events if e['kind'] in ('boom', 'rumble')]
    left, right = _music_bed(total, cuts, big)
    _write_wav(os.path.join(out_dir, f'music-{key}.wav'), left, right)
    sfx = _sfx_bed(total, events)
    _write_wav(os.path.join(out_dir, f'sfx-{key}.wav'), sfx, sfx)

if __name__ == '__main__':
    key = sys.argv[1] if len(sys.argv) > 1 else 'johnstown'
    total = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
    generate_score(key, total, [5, total * 0.3, total * 0.6, total], [
        dict(kind='whoosh', t=3.0, amp=0.5), dict(kind='boom', t=8.0, amp=0.6),
        dict(kind='riser', t=14.0, amp=0.5), dict(kind='swish', t=20.0, amp=0.5),
        dict(kind='rumble', t=26.0, amp=0.5)])
