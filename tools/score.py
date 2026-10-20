#!/usr/bin/env python3
"""Procedural score + cinematic sound design for deep-dive clips. numpy -> WAV.

Sound design philosophy: every effect is placed by SEMANTIC CUE (word-anchored),
not mechanically. Rain arrives with the storm; the breach gets a sub-drop crash
and a rushing-water bed; fire crackle takes over the wreckage act; the shredder
runs under the document-destruction line; money moments shimmer, collapses boom.
Emotional HUSH windows duck the score before the heaviest spoken lines so the
words land in near-silence. Stereo placement (panned whooshes, wide ambience),
FFT reverb tails on impacts, and sidechain-style ducking of the music bed.

Usage (via tools/deep_dive.py):
    generate_score(key, total, cuts, events, beds, hushes)
"""
import os, sys, wave, math
import numpy as np

SR = 44100
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'assets', 'deepdive')

# ------------------------------------------------------------- dsp helpers ----
def _fft_shape(x, cutoff, order=2.0):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X *= 1.0 / (1.0 + (f / max(1.0, cutoff)) ** order)
    return np.fft.irfft(X, n)

def _fft_hp(x, cutoff, order=2.0):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X *= 1.0 - 1.0 / (1.0 + (f / max(1.0, cutoff)) ** order)
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

def _reverb(x, decay=1.05, mix=0.32, seed=17):
    """FFT convolution with a synthetic exponential-noise impulse."""
    if mix <= 0:
        return x
    ln = int(decay * SR)
    rng = np.random.default_rng(seed)
    ir = rng.normal(0, 1, ln) * np.exp(-np.arange(ln) / SR * (5.0 / decay))
    ir = _fft_shape(ir, 4200, 1.2)
    ir /= np.abs(ir).max() + 1e-9
    n = 1
    while n < len(x) + ln:
        n *= 2
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(ir, n), n)[:len(x)]
    wet /= np.abs(wet).max() + 1e-9
    return (1 - mix) * x + mix * wet * (np.abs(x).max() + 1e-9)

def _write_wav(path, left, right):
    stereo = np.stack([left, right], axis=1)
    stereo = np.clip(stereo, -1.0, 1.0)
    data = (stereo * 32767).astype('<i2').tobytes()
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data)
    print('wrote', os.path.basename(path), f'{len(left)/SR:.1f}s')

def _pan(x, pan):
    """pan -1..1 -> (left, right) gains via equal power."""
    p = np.clip(pan, -1, 1)
    return x * math.sqrt((1 - p) / 2) * 1.414, x * math.sqrt((1 + p) / 2) * 1.414

# ------------------------------------------------------------------- music ----
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

def _music_bed(total, cuts, big_hits):
    n = int(total * SR)
    t = np.arange(n) / SR
    padL = _pad_bed(total, 0.9992, 11)
    padR = _pad_bed(total, 1.0008, 23)
    sub = (np.sin(2 * np.pi * 55.0 * t) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t))
           + 0.45 * np.sin(2 * np.pi * 82.41 * t))
    heart = np.zeros(n)
    thump_n = int(0.32 * SR)
    tt = np.arange(thump_n) / SR
    thump = (np.sin(2 * np.pi * 56 * tt) * np.exp(-tt * 13)
             + 0.55 * np.sin(2 * np.pi * 41 * tt) * np.exp(-tt * 9))
    for k in np.arange(0.9, total - 0.4, 1.18):
        s = int(k * SR)
        heart[s:s + thump_n] += thump[:n - s]
    rng = np.random.default_rng(5)
    wind = _fft_shape(rng.normal(0, 1, n), 320, 1.4)
    wind *= 0.45 + 0.30 * np.sin(2 * np.pi * 0.07 * t + 1.2)

    swell = np.full(n, 0.32)
    for c in list(cuts[1:-1]) + list(big_hits):
        a0, a1 = int(max(0.0, c - 1.6) * SR), int(min(total, c + 2.6) * SR)
        if a1 <= a0:
            continue
        w = np.linspace(0, 1, a1 - a0)
        shape = np.where(w < 0.38, w / 0.38, 1.0 - (w - 0.38) / 0.62) ** 1.2
        swell[a0:a1] = np.maximum(swell[a0:a1], 0.32 + 0.50 * shape)
    fin = int(max(0.0, total - 10.0) * SR)
    swell[fin:] = np.maximum(swell[fin:], np.linspace(0.34, 0.92, n - fin))

    center = 0.42 * sub + 0.20 * heart + 0.16 * wind
    left = (0.40 * padL + center) * swell
    right = (0.40 * padR + center) * swell
    return left, right

# --------------------------------------------------------------------- hits ----
def _whoosh(amp, pan=0.0, pan_sweep=0.55):
    n = int(0.55 * SR)
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, n)
    tt = np.arange(n) / SR
    hi = _fft_shape(x, 3800, 1.2) * np.exp(-tt * 9)
    lo = _fft_shape(x, 700, 1.4) * np.exp(-tt * 4.5)
    mono = (hi * 0.7 + lo * 0.9) * amp
    # pan sweeps across the stereo field for movement
    L = np.zeros(n); R = np.zeros(n)
    steps = 10
    for i in range(steps):
        s0, s1 = int(i * n / steps), int((i + 1) * n / steps)
        p = pan - pan_sweep + 2 * pan_sweep * (i / max(1, steps - 1))
        l, r = _pan(mono[s0:s1], p)
        L[s0:s1], R[s0:s1] = l, r
    return L, R

def _swish(amp, pan=0.0):
    n = int(0.34 * SR)
    rng = np.random.default_rng(4)
    x = rng.normal(0, 1, n)
    tt = np.arange(n) / SR
    mono = _fft_shape(x * np.exp(-tt * 11), 2600, 1.1) * amp * 1.4
    return _pan(mono, pan)

def _whoosh_down(amp, pan=0.0):
    n = int(0.8 * SR)
    tt = np.arange(n) / SR
    f = 900 * np.exp(-tt * 2.8) + 90
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 3.2) * 0.5
    rng = np.random.default_rng(21)
    noise = _fft_shape(rng.normal(0, 1, n), 1800, 1.3) * np.exp(-tt * 4.0)
    return _pan((tone + noise * 0.8) * amp, pan)

def _boom(amp, pan=0.0):
    n = int(1.15 * SR)
    tt = np.arange(n) / SR
    f = 58 * np.exp(-tt * 3.2) + 27
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 4.2)
    click = np.zeros(n)
    nc = int(0.012 * SR)
    rng = np.random.default_rng(6)
    click[:nc] = rng.normal(0, 1, nc) * np.exp(-np.arange(nc) / SR * 300)
    mono = _reverb(body + 0.18 * _fft_shape(click, 2200, 1.3), decay=1.2, mix=0.28) * amp
    return _pan(mono, pan)

def _subdrop(amp, pan=0.0):
    n = int(1.6 * SR)
    tt = np.arange(n) / SR
    f = 48 * np.exp(-tt * 1.6) + 22
    mono = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 1.9) * amp
    return _pan(mono, pan)

def _crash(amp, pan=0.0):
    """Impact + debris grains + reverb tail — the breach / the collapse."""
    n = int(2.2 * SR)
    rng = np.random.default_rng(7)
    tt = np.arange(n) / SR
    impact = _fft_shape(rng.normal(0, 1, n), 2600, 1.1) * np.exp(-tt * 9) * 0.9
    sub = np.sin(2 * np.pi * np.cumsum(42 * np.exp(-tt * 2.2) + 24) / SR) * np.exp(-tt * 3.2)
    debris = np.zeros(n)
    for _ in range(14):
        g = int(rng.uniform(0.03, 1.1) * SR)
        gl = int(rng.uniform(0.02, 0.09) * SR)
        if g + gl < n:
            debris[g:g + gl] += rng.normal(0, 1, gl) * np.exp(-np.arange(gl) / SR * 40) * rng.uniform(0.2, 0.6)
    mono = _reverb(impact + 0.8 * sub + 0.55 * _fft_shape(debris, 3200, 1.2),
                   decay=1.5, mix=0.36) * amp
    return _pan(mono, pan)

def _thud(amp, pan=0.0):
    """Soft distant drum — somber beats (jobs lost, prison, verdicts)."""
    n = int(0.9 * SR)
    tt = np.arange(n) / SR
    f = 70 * np.exp(-tt * 5.0) + 42
    mono = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 5.5)
    mono = _reverb(mono, decay=1.1, mix=0.35) * amp
    return _pan(mono, pan)

def _shimmer(amp, pan=0.0):
    """Bright bell stack — money rising, human warmth."""
    n = int(1.4 * SR)
    tt = np.arange(n) / SR
    x = np.zeros(n)
    for f, a, d in ((1318.5, 1.0, 3.2), (1975.5, 0.55, 4.0), (2637.0, 0.3, 5.0), (880.0, 0.4, 2.6)):
        x += a * np.sin(2 * np.pi * f * tt) * np.exp(-tt * d)
    mono = _reverb(x * 0.22, decay=1.3, mix=0.4) * amp
    return _pan(mono, pan)

def _riser(amp, pan=0.0, dur=1.15):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(8)
    noise = _fft_shape(rng.normal(0, 1, n), 1400, 1.2) * (tt / dur) ** 2
    f = 190 * (700 / 190) ** (tt / dur)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * (tt / dur) ** 2.4
    mono = (0.8 * noise + 0.5 * tone) * amp * (0.98 ** 0)  # ends crisply at the hit
    return _pan(mono, pan)

def _rumble(amp, pan=0.0, dur=2.8):
    n = int(dur * SR)
    tt = np.arange(n) / SR
    rng = np.random.default_rng(9)
    x = _fft_shape(rng.normal(0, 1, n), 90, 1.8)
    env = np.sin(np.pi * np.clip(tt / dur, 0, 1)) ** 1.3
    return _pan(x * env * amp * 2.2, pan)

# ------------------------------------------------------------- ambience beds ----
def _bed(kind, n, amp, seed):
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    if kind == 'rain':
        x = _fft_hp(rng.normal(0, 1, n), 1800, 1.1)
        x *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.9 * t + 1)  # gusts
    elif kind == 'fire':
        brown = np.cumsum(rng.normal(0, 1, n))
        brown = _fft_shape(brown / (np.abs(brown).max() + 1e-9), 700, 1.4)
        crackle = np.zeros(n)
        for _ in range(int(n / SR * 22)):
            g = int(rng.uniform(0, n - 2000))
            gl = int(rng.uniform(60, 420))
            crackle[g:g + gl] += rng.normal(0, 1, gl) * np.exp(-np.arange(gl) / SR * 55) * rng.uniform(0.3, 1.0)
        x = brown * 0.8 + _fft_hp(crackle, 900, 1.1) * 0.7
    elif kind == 'water':
        x = _fft_shape(rng.normal(0, 1, n), 900, 1.3)
        x *= 0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 0.13 * t))
    elif kind == 'water_rush':
        x = _fft_shape(rng.normal(0, 1, n), 1500, 1.1)
        x *= 0.8 + 0.2 * np.sin(2 * np.pi * 0.35 * t + 2)
    elif kind == 'city':
        x = _fft_shape(rng.normal(0, 1, n), 240, 1.5)
        x += 0.25 * np.sin(2 * np.pi * 58 * t) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.11 * t))
    elif kind == 'ticker':
        x = np.zeros(n)
        step = int(0.135 * SR)
        for g in range(0, n - 300, step):
            if rng.uniform() < 0.72:
                gl = int(rng.uniform(30, 90))
                x[g:g + gl] += rng.normal(0, 1, gl) * np.exp(-np.arange(gl) / SR * 120) * rng.uniform(0.25, 0.8)
        x = _fft_hp(x, 900, 1.2)
    elif kind == 'paper':
        x = np.zeros(n)
        for _ in range(int(n / SR * 7)):
            g = int(rng.uniform(0, n - 9000))
            gl = int(rng.uniform(2000, 8000))
            x[g:g + gl] += rng.normal(0, 1, gl) * np.sin(np.pi * np.arange(gl) / gl) ** 2 * rng.uniform(0.2, 0.55)
        x = _fft_shape(x, 2600, 1.2)
    elif kind == 'shredder':
        chop = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 16 * t))
        x = _fft_hp(rng.normal(0, 1, n), 700, 1.0) * chop * (0.85 + 0.15 * np.sin(2 * np.pi * 0.7 * t))
    elif kind == 'unease':
        x = (np.sin(2 * np.pi * 110 * t) + np.sin(2 * np.pi * 111.3 * t) * 0.9
             + np.sin(2 * np.pi * 116.5 * t) * 0.5)
        x = _fft_shape(x * 0.33, 500, 1.4)
    else:
        return np.zeros(n), np.zeros(n)
    x = x / (np.abs(x).max() + 1e-9) * amp
    # wide stereo: light decorrelation
    return x, np.roll(x, int(0.012 * SR))

# ----------------------------------------------------------------- assembly ----
HIT_KINDS = {
    'whoosh': _whoosh, 'swish': _swish, 'boom': _boom, 'subdrop': _subdrop,
    'crash': _crash, 'thud': _thud, 'shimmer': _shimmer, 'riser': _riser,
    'rumble': _rumble, 'whoosh_down': _whoosh_down,
}

def generate_score(key, total, cuts, events, beds=None, hushes=None, swell_hits=None,
                   out_dir=OUT):
    """Build music-{key}.wav (+ sfx-{key}.wav only when effects are requested).

    events: [{kind, t, amp, pan?}]        discrete hits (unused in music-only mode)
    beds:   [{kind, t0, t1, amp}]         ambience windows (unused in music-only mode)
    hushes: [{t, dur, depth, lead?}]      score-ducking moments (already offset)
    swell_hits: [t, ...]                  extra score swell crests (count landings)
    """
    beds = beds or []
    hushes = hushes or []
    events = events or []
    n = int(total * SR)
    print(f'score[{key}]: {total:.1f}s  hits={len(events)}  beds={len(beds)}  hushes={len(hushes)}')

    # ---- music with hush + swell automation ----
    big = list(swell_hits or []) + [e['t'] for e in events if e['kind'] in ('boom', 'crash', 'subdrop')]
    m_L, m_R = _music_bed(total, cuts, big)
    duck = np.ones(n)
    for h in hushes:
        lead = h.get('lead', 0.5)
        t0, t1 = max(0.0, h['t'] - lead), min(total, h['t'] + h['dur'])
        t2 = min(total, t1 + 0.85)
        i0, i1, i2 = int(t0 * SR), int(t1 * SR), int(t2 * SR)
        if i1 <= i0:
            continue
        duck[i0:i1] = np.minimum(duck[i0:i1], np.linspace(1.0, 1.0 - h['depth'], i1 - i0))
        if i2 > i1:
            duck[i1:i2] = np.minimum(duck[i1:i2], np.linspace(1.0 - h['depth'], 1.0, i2 - i1))
    m_L *= duck
    m_R *= duck
    peak = max(np.abs(m_L).max(), np.abs(m_R).max(), 1e-9)
    m_L, m_R = m_L / peak * 0.30, m_R / peak * 0.30

    _write_wav(os.path.join(out_dir, f'music-{key}.wav'), m_L, m_R)

    if not events and not beds:
        print(f'score[{key}]: music-only (no sound effects by design)')
        return

    # ---- optional sfx stem (only when effects are explicitly requested) ----
    s_L, s_R = np.zeros(n), np.zeros(n)
    for ev in events:
        kind = ev['kind']
        fn = HIT_KINDS.get(kind)
        if not fn:
            continue
        amp = ev.get('amp', 0.5)
        pan = ev.get('pan', 0.0)
        if kind in ('whoosh', 'swish', 'whoosh_down', 'boom', 'subdrop', 'crash',
                    'thud', 'shimmer', 'riser', 'rumble'):
            out = fn(amp, pan)
        L, R = out
        s0 = int(max(0.0, ev['t']) * SR)
        ln = min(len(L), n - s0)
        if ln > 0:
            s_L[s0:s0 + ln] += L[:ln]
            s_R[s0:s0 + ln] += R[:ln]
    for b in beds:
        i0, i1 = int(max(0.0, b['t0']) * SR), int(min(total, b['t1']) * SR)
        if i1 <= i0:
            continue
        L, R = _bed(b['kind'], i1 - i0, b.get('amp', 0.1), seed=hash(b['kind']) % 9999)
        fade = min(int(1.1 * SR), (i1 - i0) // 2)
        env = np.ones(i1 - i0)
        env[:fade] = np.linspace(0, 1, fade) ** 1.4
        env[-fade:] = np.linspace(1, 0, fade) ** 1.4
        s_L[i0:i1] += L * env
        s_R[i0:i1] += R * env

    # sidechain: big impacts duck the music a touch more
    imp = np.abs(s_L + s_R)
    imp = _fft_shape(imp, 2.2, 1.0)
    imp /= imp.max() + 1e-9
    m_L *= 1.0 - 0.30 * imp
    m_R *= 1.0 - 0.30 * imp

    peak = max(np.abs(s_L).max(), np.abs(s_R).max(), 1e-9)
    s_L, s_R = s_L / peak * 0.46, s_R / peak * 0.46

    _write_wav(os.path.join(out_dir, f'music-{key}.wav'), m_L, m_R)
    _write_wav(os.path.join(out_dir, f'sfx-{key}.wav'), s_L, s_R)

if __name__ == '__main__':
    generate_score('smoke', 14.0, [2.0, 7.0, 12.0],
                   [dict(kind='whoosh', t=1.2, amp=0.4, pan=-0.4),
                    dict(kind='crash', t=5.0, amp=0.75),
                    dict(kind='subdrop', t=5.0, amp=0.7),
                    dict(kind='thud', t=9.5, amp=0.5),
                    dict(kind='shimmer', t=11.0, amp=0.25, pan=0.3)],
                   beds=[dict(kind='rain', t0=1.0, t1=6.0, amp=0.12),
                         dict(kind='fire', t0=7.0, t1=13.5, amp=0.12)],
                   hushes=[dict(t=5.0, dur=1.2, depth=0.85, lead=0.5)])
