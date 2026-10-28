#!/usr/bin/env python3
"""
DOCOGA REELS v2 — kinetic-typography system, 100% code-rendered.
Camera: punch-in 4.5% / accelerate-out + fade, 90ms flash cuts, impact shake.
Type: odometer count-ups, per-char drop cascades, tracked-in kickers, slam strikes.
Specs: 1080x1920 · 30fps · H.264 crf20 · AAC silent · safe zones 270/660/65.
Run: python3 tools/make_reels.py [reel1|reel2|covers]
"""
import os, sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageChops
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, 'social')
W, H = 1080, 1920
FPS = 30
CX = W // 2
MAXW = 860

NAVY = (6, 26, 51)
NAVY2 = (12, 38, 70)          # fade-from color (≈ bg)
PANEL = (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60), (255, 90, 95), (46, 204, 113)

# Font discovery: supports Inter-Variable.ttf if present, with graceful fallback to assets/fonts/Inter-*.ttf
_FONT_DIRS = [
    os.path.join(ROOT, 'tools', 'fonts'),
    os.path.join(ROOT, 'assets', 'fonts'),
    os.path.join(OUT, 'assets', 'fonts'),
    '/usr/share/fonts/opentype/inter',
    '/usr/share/fonts/truetype/inter',
]
_FALLBACK_WEIGHTS = {
    'Black': ['Black', 'ExtraBold', 'Bold'],
    'ExtraBold': ['ExtraBold', 'Black', 'Bold'],
    'Bold': ['Bold', 'SemiBold'],
    'SemiBold': ['SemiBold', 'Medium', 'Bold'],
    'Medium': ['Medium', 'Regular'],
    'Regular': ['Regular', 'Light'],
    'Light': ['Light', 'Regular'],
}

try:
    from PIL import features
    RAQM = features.check('raqm')
except Exception:
    RAQM = False

_fc = {}
def _resolve_font_file(w):
    var_path = os.path.join(ROOT, 'tools', 'fonts', 'Inter-Variable.ttf')
    if os.path.exists(var_path):
        return var_path, True
    for cand in _FALLBACK_WEIGHTS.get(w, [w]):
        for d in _FONT_DIRS:
            for ext in ('.ttf', '.otf'):
                p = os.path.join(d, f'Inter-{cand}{ext}')
                if os.path.exists(p):
                    return p, False
    return 'DejaVuSans.ttf', False

def font(w, sz):
    key = (w, sz)
    if key not in _fc:
        path, is_var = _resolve_font_file(w)
        try:
            if RAQM:
                _f = ImageFont.truetype(path, sz, layout_engine=ImageFont.Layout.RAQM)
            else:
                _f = ImageFont.truetype(path, sz)
            if is_var:
                try: _f.set_variation_by_name(w)
                except Exception: pass
        except Exception:
            _f = ImageFont.load_default()
        _fc[key] = _f
    return _fc[key]

def fit(d, text, w, sz, max_w=MAXW):
    while sz > 30:
        f = font(w, sz)
        if d.textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        sz -= 4
    return font(w, sz)

def fit_size(d, text, w, sz, max_w=MAXW):
    while sz > 30 and d.textbbox((0, 0), text, font=font(w, sz))[2] > max_w:
        sz -= 4
    return sz

def ease_cubic(p): return 1 - (1 - p) ** 3
def ease_back(p, s=1.70158):
    p -= 1
    return p * p * ((s + 1) * p + s) + 1
def lerp_c(c1, c2, t): return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def ctext(d, cx, y, text, f, fill):
    w = d.textbbox((0, 0), text, font=f)[2]
    d.text((cx - w // 2, y), text, font=f, fill=fill)
    return w

def tracked_w(d, text, f, tr):
    return sum(d.textlength(ch, font=f) + tr for ch in text) - tr

def ctracked(d, cx, y, text, f, fill, tr=6):
    x = cx - tracked_w(d, text, f, tr) / 2
    for ch in text:
        if ch != ' ':
            d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tr

def badge(d, cx, cy, r, color, kind, pop=1.0):
    r = int(r * max(0.05, pop))
    if r < 4: return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    lw = max(8, int(r * 0.26))
    if kind == 'check':
        d.line([(cx - r * .45, cy + r * .02), (cx - r * .08, cy + r * .38),
                (cx + r * .5, cy - r * .32)], fill=WHITE, width=lw, joint='curve')
    else:
        d.line([(cx - r * .38, cy - r * .38), (cx + r * .38, cy + r * .38)], fill=WHITE, width=lw)
        d.line([(cx + r * .38, cy - r * .38), (cx - r * .38, cy + r * .38)], fill=WHITE, width=lw)

def ring(d, cx, cy, r, p, color):
    """expanding impact ring, p in 0..1"""
    if p <= 0 or p >= 1: return
    rr = int(r + 130 * ease_cubic(p))
    wdt = max(2, int(9 * (1 - p)))
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=lerp_c(color, NAVY2, p), width=wdt)

def ctext_drop(d, lt, t0, stag, text, f, y, fill, dy=30):
    """per-character drop-settle cascade"""
    if lt < t0: return
    x = CX - (sum(d.textlength(ch, font=f) for ch in text)) / 2
    for k, ch in enumerate(text):
        p = (lt - t0 - k * stag) / 0.30
        if p > 0:
            p = min(1.0, p)
            yy = y + int(dy * (1 - ease_back(p, 1.2)))
            col = lerp_c(NAVY2, fill, min(1, p * 1.7))
            if ch != ' ':
                d.text((x, yy), ch, font=f, fill=col)
        x += d.textlength(ch, font=f)

def kicker_in(d, lt, t0, y, text, sz, fill):
    """tracked-in kicker: letter-spacing 18→6 + fade"""
    if lt < t0: return
    p = min(1.0, (lt - t0) / 0.35)
    tr = int(18 - 12 * ease_cubic(p))
    col = lerp_c(NAVY2, fill, min(1.0, (lt - t0) / 0.30))
    ctracked(d, CX, y, text, font('SemiBold', sz), col, tr)

def countup(lt, t0, t1, target):
    if lt < t0: return 0
    if lt >= t1: return target
    p = 1 - (1 - (lt - t0) / (t1 - t0)) ** 3
    step = max(1, target // 25)
    return int(min(target, round(target * p / step) * step))

# ── filmic background: radial gradient + dot grid + vignette (precomputed) ──
def build_base():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - CX) / 620.0) ** 2 + ((yy - 760) / 760.0) ** 2)
    b = 1.0 + 0.15 * np.exp(-r ** 2 / 0.5) - 0.15 * (r / 1.9) ** 2.2
    b = np.clip(b, 0.83, 1.15)[..., None]
    arr = np.clip(np.array(NAVY, dtype=np.float32) * b, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    dot = tuple(min(255, c + 9) for c in NAVY)
    for gy in range(36, H, 72):
        for gx in range(36, W, 72):
            d.ellipse([gx - 2, gy - 2, gx + 2, gy + 2], fill=dot)
    return img

BASE = build_base()
WHITE_IMG = Image.new('RGB', (W, H), WHITE)

def zoom(img, s):
    if abs(s - 1.0) < 0.001: return img
    w2, h2 = int(W / s), int(H / s)
    x0, y0 = (W - w2) // 2, (H - h2) // 2
    return img.crop((x0, y0, x0 + w2, y0 + h2)).resize((W, H), Image.BICUBIC)

def envelope(img, lt, dur, is_last):
    if lt < 0.5:                                   # punch-in
        img = zoom(img, 1.045 - 0.045 * ease_cubic(lt / 0.5))
    if not is_last and lt > dur - 0.22:            # accelerate out + fade
        p = (lt - (dur - 0.22)) / 0.22
        img = zoom(img, 1.0 + 0.06 * ease_cubic(p))
        img = Image.blend(img, BASE, min(1.0, ease_cubic(p)))
    if lt < 0.09:                                  # flash cut
        img = Image.blend(img, WHITE_IMG, 0.30 * (1 - lt / 0.09))
    return img

def apply_shake(img, lt, impacts):
    for ti in impacts:
        dt = lt - ti
        if 0 <= dt < 0.24:
            a = 1 - dt / 0.24
            dx, dy = int(6 * a * math.sin(46 * dt)), int(4 * a * math.cos(39 * dt))
            return ImageChops.offset(img, dx, dy)
    return img

_skip_env = False  # scenes may set this to opt out of envelope (cover card)

def _get_ffmpeg_cmd():
    try:
        from pipeline.assemble import ffmpeg_bin
        return ffmpeg_bin()
    except Exception:
        return os.environ.get('FFMPEG_BINARY') or 'ffmpeg'

def render(reel_name, scenes, out, duration):
    os.makedirs('/tmp/rf_' + reel_name, exist_ok=True)
    n = int(duration * FPS)
    bounds, t0 = [], 0.0
    for dur, _ in scenes:
        bounds.append((t0, t0 + dur)); t0 += dur
    global _skip_env
    for i in range(n):
        t = i / FPS
        si = max(k for k, (a, b) in enumerate(bounds) if a <= t < b or (k == len(scenes) - 1 and t >= b))
        a, b = bounds[si]
        lt = min(t - a, scenes[si][0])
        img = BASE.copy()
        d = ImageDraw.Draw(img)
        _skip_env = False
        impacts = scenes[si][1](d, img, lt, scenes[si][0]) or []
        img = apply_shake(img, lt, impacts)
        if not _skip_env:
            img = envelope(img, lt, scenes[si][0], si == len(scenes) - 1)
        img.save(f'/tmp/rf_{reel_name}/f_{i:04d}.png')
        if i % 90 == 0: print(f'  frame {i}/{n}')
    encode(f'/tmp/rf_{reel_name}', out, duration)

def encode(frames_dir, out, dur):
    ff = _get_ffmpeg_cmd()
    cmd = [ff, '-y', '-framerate', str(FPS), '-i', os.path.join(frames_dir, 'f_%04d.png'),
           '-f', 'lavfi', '-t', f'{dur:.2f}', '-i', 'anullsrc=r=44100:cl=stereo',
           '-c:v', 'libx264', '-preset', 'veryfast', '-threads', '2', '-pix_fmt', 'yuv420p', '-crf', '20',
           '-vf', 'noise=alls=4:allf=t', '-x264-params', 'rc-lookahead=12',
           '-c:a', 'aac', '-b:a', '64k', '-shortest', '-movflags', '+faststart', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-600:]); raise SystemExit('encode failed')
    print('✅', out, f'{os.path.getsize(out)//1024} KB')

def strike_mid(y, size):
    asc, _ = font('Black', size).getmetrics()
    return y + asc - round(0.363 * size)

# ═══════════════════════════ REEL 1 — "THE PRICE" (15s) ═══════════════════════════

def s1a(d, img, lt, dur):
    """odometer ₦50,000 → red slam strike → sub drops"""
    v = countup(lt, 0.05, 0.95, 50000)
    txt = f'₦{v:,}'
    b1 = fit_size(d, '₦50,000', 'Black', 210)
    ctext(d, CX, 620, txt, font('Black', b1), WHITE if lt > 0.04 else NAVY2)
    w = d.textbbox((0, 0), '₦50,000', font=font('Black', b1))[2]
    if lt > 1.30:
        g = min(1.0, (lt - 1.30) / 0.10)            # 0.10s slam
        m1 = strike_mid(620, b1)
        x0 = CX - w * 0.47
        d.rectangle([x0, m1 - 12, x0 + w * 0.94 * g, m1 + 12], fill=RED)
        if g < 1:
            ring(d, x0 + w * 0.94 * g, m1, 30, (lt - 1.30) / 0.5, RED)
    ctext_drop(d, lt, 1.85, 0.045, 'for one document.', font('Light', 58), 850, MUTED)
    return [1.30]

def s1b(d, img, lt, dur):
    p = (lt - 0.10) / 0.35
    badge(d, CX, 560, 52, RED, 'cross', min(1.0, p))
    if p > 0: ring(d, CX, 560, 52, p, RED)
    ctext_drop(d, lt, 0.30, 0.05, 'TOO MUCH.', fit(d, 'TOO MUCH.', 'Black', 128), 680, WHITE)
    kicker_in(d, lt, 1.50, 900, 'THE LAWYER\u2019S PRICE', 30, FAINT)
    return []

def s1c(d, img, lt, dur):
    p = (lt - 0.10) / 0.35
    badge(d, CX, 560, 56, GREEN, 'check', min(1.0, p))
    if p > 0: ring(d, CX, 560, 56, p, GREEN)
    ctext_drop(d, lt, 0.30, 0.05, 'OR 2 MINUTES.', fit(d, 'OR 2 MINUTES.', 'Black', 118), 680, WHITE)
    kicker_in(d, lt, 1.50, 900, 'ANY DOCUMENT \u00B7 ON YOUR PHONE', 30, YELLOW)
    return []

def s1d(d, img, lt, dur):
    v = countup(lt, 0.05, 0.50, 2000)
    txt = f'₦{v:,}'
    b4 = fit_size(d, '₦2,000', 'Black', 250)
    ctext(d, CX, 590, txt, font('Black', b4), WHITE if lt > 0.04 else NAVY2)
    w = d.textbbox((0, 0), '₦2,000', font=font('Black', b4))[2]
    if lt > 0.75:
        g = min(1.0, (lt - 0.75) / 0.10)
        m4 = strike_mid(590, b4)
        x0 = CX - w * 0.45
        d.rectangle([x0, m4 - 12, x0 + w * 0.90 * g, m4 + 12], fill=YELLOW)
        if g < 1:
            ring(d, x0 + w * 0.90 * g, m4, 30, (lt - 0.75) / 0.5, YELLOW)
    kicker_in(d, lt, 1.35, 990, '30 DAYS \u00B7 UNLIMITED', 36, YELLOW)
    return [0.75]

def end_button(d, lt, t0, by):
    p = min(1.0, max(0.0, (lt - t0) / 0.5))
    if p <= 0: return
    yy = by + int(40 * (1 - ease_back(p)))
    d.rounded_rectangle([CX - 320 + 10, yy + 10, CX + 320 + 10, yy + 118 + 10], 54, fill=PANEL)
    d.rounded_rectangle([CX - 320, yy, CX + 320, yy + 118], 54, fill=WHITE)
    fb = font('Bold', 46)
    tw = d.textbbox((0, 0), 'docoga.com.ng', font=fb)[2]
    d.text((CX - tw // 2, yy + 34), 'docoga.com.ng', font=fb, fill=(6, 26, 51))
    b = 0.5 + 0.5 * math.sin(2 * math.pi * (lt - t0) / 1.1)     # pulse
    d.rounded_rectangle([CX - 329, yy - 8, CX + 329, yy + 126], 59,
                        outline=lerp_c((28, 88, 180), BLUE, b), width=5)

def s1e(d, img, lt, dur):
    p = min(1.0, max(0.0, (lt - 0.10) / 0.45))
    ctext(d, CX, 540, 'FREE.', font('Black', int(190 * (1.14 - 0.14 * (ease_back(p) if p < 1 else 1)))),
          WHITE if lt > 0.14 else NAVY2)
    if p > 0:
        ring(d, CX, 640, 60, p, YELLOW)
        ring(d, CX, 640, 60, max(0.0, p - 0.18), YELLOW)
    if lt > 0.55:                                               # underline sweep
        g = ease_cubic(min(1.0, (lt - 0.55) / 0.35))
        wfree = d.textbbox((0, 0), 'FREE.', font=font('Black', 190))[2] * 0.92
        d.rectangle([CX - wfree / 2, 800, CX - wfree / 2 + wfree * g, 812], fill=YELLOW)
    end_button(d, lt, 0.75, 850)
    if lt > 1.30:
        ctext(d, CX, 1030, 'No signup. No card.', font('Light', 46),
              lerp_c(NAVY2, MUTED, min(1, (lt - 1.30) / 0.35)))
    kicker_in(d, lt, 1.70, 1150, 'YOUR DOCUMENTS. OUR PRIORITY.', 24, FAINT)
    kicker_in(d, lt, 1.90, 1195, 'FOLLOW @docoga.ng', 24, BLUE)
    return []

REEL1 = [(3.2, s1a), (3.0, s1b), (3.0, s1c), (3.0, s1d), (2.8, s1e)]

# ═══════════════════════════ REEL 2 — "EVERY DOCUMENT." (13s) ═══════════════════════════

ICONS = ['icon-agreement', 'icon-receipt', 'icon-seal', 'icon-house',
         'icon-shield', 'icon-clock', 'icon-coin']
_pos = {}
for idx, name in enumerate(ICONS):
    r, c = divmod(idx, 4)
    x = 235 + c * 220 + (110 if r == 1 else 0)
    _pos[name] = (x, 640 + r * 250)
ICON_IMGS = {n: Image.open(os.path.join(OUT, 'assets', n + '.png')).resize((210, 210), Image.LANCZOS)
             for n in ICONS if os.path.exists(os.path.join(OUT, 'assets', n + '.png'))}
DOCS = ['Tenancy Agreement', 'Rent Receipt', 'Notice to Quit', 'Invoice',
        'Employment Contract', 'Caution Fee', 'Demand Letter', 'Payslip', 'Warning Letter']
SWITCH = [2.90, 3.28, 3.65, 4.01, 4.36, 4.70, 5.03, 5.35, 5.66]  # all 9 names, accelerating

def pop_icon(img, ic, cx, cy, p):
    if p <= 0: return
    s = max(0.15, ease_back(p, 1.4))
    ang = 20 * max(0.0, 1 - p * 1.5)
    im2 = ic.resize((max(8, int(210 * s)), max(8, int(210 * s))), Image.LANCZOS)
    if abs(ang) > 0.5:
        im2 = im2.rotate(ang, expand=True, resample=Image.BICUBIC)
    img.paste(im2, (cx - im2.width // 2, cy - im2.height // 2), im2)

def s2a(d, img, lt, dur):
    ctext_drop(d, lt, 0.10, 0.05, 'EVERY DOCUMENT.', fit(d, 'EVERY DOCUMENT.', 'Black', 110), 420, WHITE)
    kicker_in(d, lt, 1.30, 640, 'ONE PASS', 30, BLUE)
    return []

def s2b(d, img, lt, dur):
    ctext(d, CX, 400, 'EVERY DOCUMENT.', fit(d, 'EVERY DOCUMENT.', 'Black', 96), WHITE)
    for k, name in enumerate(ICONS):
        if name not in ICON_IMGS: continue
        p = (lt - (0.30 + k * 0.42)) / 0.40
        if p > 0:
            pop_icon(img, ICON_IMGS[name], _pos[name][0], _pos[name][1], min(1.0, p))
            if p < 1: ring(d, _pos[name][0], _pos[name][1], 60, p, BLUE)
    if lt > SWITCH[0]:
        k = max(i for i, s in enumerate(SWITCH) if lt >= s)
        ctext(d, CX, 1150, DOCS[k], font('SemiBold', 40), YELLOW)
        d.rectangle([CX - 230, 1210, CX + 230, 1215], fill=lerp_c(NAVY2, YELLOW, min(1.0, (lt - SWITCH[k]) / 0.08)))
    return []

def s2c(d, img, lt, dur):
    v = countup(lt, 0.05, 0.50, 2000)
    txt = f'₦{v:,}.'
    b = fit_size(d, '₦2,000.', 'Black', 200)
    ctext(d, CX, 560, txt, font('Black', b), WHITE if lt > 0.04 else NAVY2)
    w = d.textbbox((0, 0), '₦2,000.', font=font('Black', b))[2]
    if lt > 0.75:
        g = min(1.0, (lt - 0.75) / 0.10)
        m = strike_mid(560, b)
        x0 = CX - w * 0.45
        d.rectangle([x0, m - 12, x0 + w * 0.90 * g, m + 12], fill=YELLOW)
        if g < 1:
            ring(d, x0 + w * 0.90 * g, m, 30, (lt - 0.75) / 0.5, YELLOW)
    kicker_in(d, lt, 1.30, 960, '30 DAYS \u00B7 ALL 9 DOCUMENTS', 32, YELLOW)
    return [0.75]

def s2d(d, img, lt, dur):
    p = min(1.0, max(0.0, (lt - 0.10) / 0.45))
    ctext(d, CX, 560, 'FREE.', font('Black', int(180 * (1.14 - 0.14 * (ease_back(p) if p < 1 else 1)))),
          WHITE if lt > 0.14 else NAVY2)
    if p > 0:
        ring(d, CX, 660, 55, p, YELLOW)
        ring(d, CX, 660, 55, max(0.0, p - 0.18), YELLOW)
    end_button(d, lt, 0.60, 800)
    kicker_in(d, lt, 1.10, 1150, 'FOLLOW @docoga.ng', 26, BLUE)
    return []

REEL2 = [(2.6, s2a), (6.0, s2b), (2.4, s2c), (2.0, s2d)]

# ═══════════════════════════ covers (crop-safe: content inside y 420–1500) ═══════════════════════════

def cover1(d):
    b = fit_size(d, '₦2,000', 'Black', 240)
    ctext(d, CX, 590, '₦2,000', font('Black', b), WHITE)
    w = d.textbbox((0, 0), '₦2,000', font=font('Black', b))[2]
    asc_c, _ = font('Black', b).getmetrics()
    uy = 590 + asc_c + 16
    d.rectangle([CX - w * 0.47, uy, CX + w * 0.47, uy + 14], fill=YELLOW)
    ctracked(d, CX, 940, '30 DAYS \u00B7 UNLIMITED', font('SemiBold', 36), YELLOW, 6)
    ctracked(d, CX, 1180, 'DOCOGA', font('SemiBold', 30), BLUE, 9)

def cover2(img, d):
    ctext(d, CX, 420, 'EVERY DOCUMENT.', fit(d, 'EVERY DOCUMENT.', 'Black', 96), WHITE)
    for name in ICONS:
        if name not in ICON_IMGS: continue
        ic = ICON_IMGS[name]
        px, py = _pos[name]
        img.paste(ic, (px - 105, py - 105), ic)
    ctracked(d, CX, 1160, '9 DOCUMENTS \u00B7 ONE PASS', font('SemiBold', 32), YELLOW, 6)

def make_covers():
    img = BASE.copy(); d = ImageDraw.Draw(img)
    cover1(d); img.save(os.path.join(OUT, 'reel-1-cover.jpg'), quality=92)
    print('✅ reel-1-cover.jpg')
    img = BASE.copy(); d = ImageDraw.Draw(img)
    cover2(img, d); img.save(os.path.join(OUT, 'reel-2-cover.jpg'), quality=92)
    print('✅ reel-2-cover.jpg')

# ═══════════════════════════ REEL 3 — "CAUTION FEE" (38s, voiceover) ═══════════════════════════

def s3a(d, img, lt, dur):
    kicker_in(d, lt, 0.05, 430, 'YOUR LANDLORD IS HOLDING', 30, BLUE)
    ctext_drop(d, lt, 0.35, 0.045, 'YOUR CAUTION FEE.', fit(d, 'YOUR CAUTION FEE.', 'Black', 118), 590, WHITE)
    ctext_drop(d, lt, 2.3, 0.045, "here's what he hopes", font('Light', 54), 800, MUTED)
    ctext_drop(d, lt, 2.6, 0.045, 'you never find out.', font('Light', 54), 880, MUTED)
    return [0.35]

def s3b(d, img, lt, dur):
    p = min(1.0, max(0.0, (lt - 0.10) / 0.35))
    if 'icon-coin' in ICON_IMGS:
        pop_icon(img, ICON_IMGS['icon-coin'], CX, 500, p)
    if p > 0: ring(d, CX, 500, 105, p, YELLOW)
    ctext_drop(d, lt, 0.50, 0.05, 'A SECURITY DEPOSIT.', fit(d, 'A SECURITY DEPOSIT.', 'Black', 86), 700, WHITE)
    ctext_drop(d, lt, 1.8, 0.05, 'NOT A GIFT.', fit(d, 'NOT A GIFT.', 'Black', 112), 860, YELLOW)
    kicker_in(d, lt, 2.9, 1060, 'IT GOES BACK TO YOU AT MOVE-OUT', 28, FAINT)
    return [0.50, 1.8]

def s3c(d, img, lt, dur):
    p = min(1.0, max(0.0, (lt - 0.10) / 0.35))
    badge(d, CX, 480, 56, GREEN, 'check', min(1.0, p))
    if p > 0: ring(d, CX, 480, 56, p, GREEN)
    ctext_drop(d, lt, 0.45, 0.05, 'REFUNDABLE.', fit(d, 'REFUNDABLE.', 'Black', 150), 640, WHITE)
    ctext_drop(d, lt, 1.6, 0.05, 'every naira.', font('Light', 62), 870, MUTED)
    kicker_in(d, lt, 2.7, 1020, 'NO DAMAGE BEYOND NORMAL WEAR AND TEAR', 28, GREEN)
    ctext_drop(d, lt, 4.6, 0.05, "it's the standard legal position", font('Light', 40), 1140, FAINT)
    return [0.45]

def s3d(d, img, lt, dur):
    kicker_in(d, lt, 0.05, 430, 'SO WHY DO LANDLORDS KEEP IT?', 30, BLUE)
    ctext_drop(d, lt, 0.60, 0.05, 'NO EVIDENCE.', fit(d, 'NO EVIDENCE.', 'Black', 132), 600, RED)
    ctext_drop(d, lt, 1.9, 0.045, 'tenants arrive empty-handed.', font('Light', 50), 840, MUTED)
    return [0.60]

def s3e(d, img, lt, dur):
    kicker_in(d, lt, 0.05, 400, 'THE PLAY \u00b7 DAY ONE', 30, YELLOW)
    ctext_drop(d, lt, 0.35, 0.05, 'VIDEO EVERY ROOM.', fit(d, 'VIDEO EVERY ROOM.', 'Black', 100), 540, WHITE)
    for i, item in enumerate(['TAPS', 'WALLS', 'TOILETS']):
        ctext_drop(d, lt, 1.5 + i * 0.30, 0.04, item, font('SemiBold', 58), 760 + i * 95, BLUE)
    ctext_drop(d, lt, 3.6, 0.05, 'AND IN WRITING \u2014', font('Light', 50), 1120, WHITE)
    ctext_drop(d, lt, 4.3, 0.05, 'refund clause + deadline', font('SemiBold', 56), 1210, YELLOW)
    kicker_in(d, lt, 5.8, 1340, 'IF IT IS NOT WRITTEN, IT DOES NOT EXIST', 26, FAINT)
    return [0.35, 4.3]

def s3f(d, img, lt, dur):
    ctext(d, CX, 490, "IT'S YOUR MONEY.", fit(d, "IT'S YOUR MONEY.", 'Black', 118), WHITE if lt > 0.04 else NAVY2)
    ctext_drop(d, lt, 1.1, 0.045, 'just parked with him.', font('Light', 56), 690, MUTED)
    if lt > 0.8:
        g = ease_cubic(min(1.0, (lt - 0.8) / 0.35))
        wu = d.textbbox((0, 0), "IT'S YOUR MONEY.", font=font('Black', 118))[2] * 0.9
        d.rectangle([CX - wu / 2, 780, CX - wu / 2 + wu * g, 792], fill=YELLOW)
    end_button(d, lt, 1.9, 880)
    if lt > 2.7:
        ctext(d, CX, 1070, 'FREE to start. No signup. No card.', font('Light', 42),
              lerp_c(NAVY2, MUTED, min(1, (lt - 2.7) / 0.35)))
    kicker_in(d, lt, 3.1, 1160, 'YOUR DOCUMENTS. OUR PRIORITY.', 24, FAINT)
    kicker_in(d, lt, 3.3, 1205, 'FOLLOW @docoga.ng', 24, BLUE)
    return []

REEL3 = [(6.0, s3a), (5.0, s3b), (8.0, s3c), (5.5, s3d), (8.0, s3e), (5.5, s3f)]

# ═══════════════════════════ REEL 4 - "66 YEARS, 6 RIGHTS" v8 (ASR word-sync) ═══════════════════════════

import json as _json
from PIL import ImageEnhance as _IE
from PIL import Image as _PImage

def _load_w4():
    root = os.path.dirname(os.path.abspath(__file__))
    jf = os.path.join(root, '..', 'renders', 'r4-words.json')
    if os.path.exists(jf):
        return _json.load(open(jf))['segments']
    # Fallback mock segments if renders/r4-words.json does not exist
    return []

W4 = _load_w4()
COVER_T0 = 0.7  # v12 EMBEDDED-COVER LAW: cover card opens the video; display = speech + COVER_T0
for _s in W4:
    _s['start'] += COVER_T0
    _s['end'] += COVER_T0
    for _w in _s.get('words', []):
        _w['t'] += COVER_T0

VIS_LEAD = 0.07  # v9 WORD-LEVEL SYNC LAW: visual events land ON the spoken word

def _sw(i, wi=None):
    if i >= len(W4): return 0.0
    seg = W4[i]
    if wi is None:
        return seg['start']
    return seg['words'][wi]['t'] if wi < len(seg.get('words', [])) else seg['end']

def _wf(i, txt, occ=1):
    if i >= len(W4): return 0
    n = 0
    for j, w in enumerate(W4[i].get('words', [])):
        if w['w'] == txt:
            n += 1
            if n == occ:
                return j
    return 0

def _wt(*a):
    if not W4: return 0.0
    if len(a) == 1:
        t = _sw(a[0])
    elif isinstance(a[1], int):
        t = _sw(a[0], a[1])
    else:
        t = _sw(a[0], _wf(a[0], a[1], a[2] if len(a) > 2 else 1))
    return max(0.0, t - VIS_LEAD)

GRN = (0, 135, 81)

def _jit(lt, t0, amp=7):
    if lt - t0 < 0.07:
        return amp if int(lt * 30) % 2 == 0 else -amp
    return 0

_SPR = {}

def load_sprite(path, maxh=460, maxw=560):
    key = (path, maxh, maxw)
    if key in _SPR:
        return _SPR[key]
    if not os.path.exists(path):
        im = Image.new('RGBA', (maxw, maxh), (0, 0, 0, 0))
    else:
        im = _PImage.open(path)
    w, h = im.size
    sc = min(maxw / float(max(1, w)), maxh / float(max(1, h)))
    if sc < 1.0:
        im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))), _PImage.LANCZOS)
    _SPR[key] = im
    return _SPR[key]

def story_subject(d, img, lt, t0, path, accent_t, ph, s_path=None, s_t0=None, side=-1):
    ent = min(1.0, max(0.0, (lt - t0) / 0.35))
    if ent <= 0:
        return
    nud = ease_cubic(min(1.0, max(0.0, (lt - s_t0) / 0.35))) if s_t0 is not None else 0.0
    pcx = int(CX - side * 70 * nud)
    pcy = 420
    r1, r2 = 170, 205
    ringp = ease_cubic(min(1.0, (lt - t0) / 0.5))
    if ringp > 0:
        col1 = lerp_c(NAVY2, BLUE, 0.38)
        d.arc([pcx - r1, pcy - r1, pcx + r1, pcy + r1], -90, -90 + int(360 * ringp), fill=col1, width=2)
        if ringp > 0.4:
            col2 = lerp_c(NAVY2, BLUE, 0.20)
            d.ellipse([pcx - r2, pcy - r2, pcx + r2, pcy + r2], outline=col2, width=2)
    e = ease_back(ent)
    sc = 0.88 + 0.12 * e
    ap = 0.0
    if lt >= accent_t:
        q = (lt - accent_t) / 0.45
        if q <= 1.0:
            ap = 0.055 * math.sin(math.pi * q)
    sc *= (1.0 + ap)
    dy = 7.0 * math.sin(2 * math.pi * (lt + ph) / 3.1)
    dx = 4.0 * math.sin(2 * math.pi * (lt + 1.7 * ph) / 4.3)
    spr = load_sprite(path, 400, 430)
    w2, h2 = spr.size
    if abs(sc - 1.0) > 0.004:
        spr = spr.resize((max(1, int(w2 * sc)), max(1, int(h2 * sc))), _PImage.LANCZOS)
        w2, h2 = spr.size
    sw = int(w2 * 0.52)
    shy = int(pcy + h2 * 0.52 + 10 - dy * 0.6)
    d.ellipse([pcx - sw // 2, shy, pcx + sw // 2, shy + 30], fill=lerp_c(NAVY2, (0, 0, 0), 0.45))
    aa = int(255 * ease_cubic(ent))
    if aa < 255:
        s2 = spr.copy()
        s2.putalpha(s2.getchannel('A').point(lambda v: v * aa // 255))
        spr = s2
    img.paste(spr, (int(pcx + dx - w2 / 2), int(pcy + dy - h2 / 2)), spr)
    if s_path is not None and s_t0 is not None and lt >= s_t0:
        e2 = min(1.0, (lt - s_t0) / 0.35)
        sc2 = 0.85 + 0.15 * ease_back(e2)
        dy2 = 6.0 * math.sin(2 * math.pi * (lt + ph + 2.1) / 3.1)
        spr2 = load_sprite(s_path, 250, 320)
        w3, h3 = spr2.size
        if abs(sc2 - 1.0) > 0.004:
            spr2 = spr2.resize((max(1, int(w3 * sc2)), max(1, int(h3 * sc2))), _PImage.LANCZOS)
            w3, h3 = spr2.size
        scx = int(CX + side * 235)
        scy = 545
        sw3 = int(w3 * 0.55)
        shy3 = int(scy + h3 * 0.5 + 8 - dy2 * 0.5)
        d.ellipse([scx - sw3 // 2, shy3, scx + sw3 // 2, shy3 + 24], fill=lerp_c(NAVY2, (0, 0, 0), 0.40))
        aa2 = int(255 * ease_cubic(e2))
        if aa2 < 255:
            s3 = spr2.copy()
            s3.putalpha(s3.getchannel('A').point(lambda v: v * aa2 // 255))
            spr2 = s3
        img.paste(spr2, (int(scx - w3 / 2), int(scy + dy2 - h3 / 2)), spr2)
    if lt >= accent_t:
        q = (lt - accent_t) / 0.5
        if q <= 1.0:
            rr = r2 * (1.0 + 0.16 * q)
            d.ellipse([pcx - rr, pcy - rr, pcx + rr, pcy + rr], outline=lerp_c(YELLOW, NAVY2, q), width=5)

def sweep(d, lt, dur):
    W2 = CX * 2
    npass = 2 if dur > 4.5 else 1
    pd = dur / npass
    x = -700 + ((lt % pd) / pd) * (W2 + 1400)
    for i in range(0, 220, 11):
        a = 0.055 * (1.0 - abs(i - 110) / 110.0)
        if a <= 0.004:
            continue
        col = lerp_c(NAVY2, WHITE, a)
        xs = x + i
        d.polygon([(xs, 0), (xs + 11, 0), (xs + 11 - 150, 1920), (xs - 150, 1920)], fill=col)

def progress(d, lt, t0, k, total=6):
    W2 = CX * 2
    x0, x1, y = 60, W2 - 60, 112
    d.rectangle([x0, y, x1, y + 12], fill=lerp_c(NAVY2, WHITE, 0.10))
    p = ease_back(min(1.0, max(0.0, (lt - t0) / 0.35)))
    seg = (x1 - x0) / total
    d.rectangle([x0, y, x0 + seg * (k - 1) + seg * max(0.0, p), y + 12], fill=YELLOW)

def flagbar(d, lt, t0, y, wmax):
    p = ease_cubic(min(1.0, max(0.0, (lt - t0) / 0.5)))
    if p <= 0:
        return
    w = int(wmax * p)
    nseg = 26
    segw = w / float(nseg)
    x0 = CX - w / 2
    for i in range(nseg):
        off = 5.5 * math.sin(2 * math.pi * (i / float(nseg)) - 2 * math.pi * (lt / 1.3))
        xs = x0 + i * segw
        d.rectangle([xs, y + off, xs + segw + 1, y + 9 + off], fill=GRN)
        d.rectangle([xs, y + 9 + off, xs + segw + 1, y + 18 + off], fill=WHITE)
        d.rectangle([xs, y + 18 + off, xs + segw + 1, y + 27 + off], fill=GRN)

def tick(d, lt, t0, cx, cy, s, col):
    p = ease_cubic(min(1.0, max(0.0, (lt - t0) / 0.22)))
    if p <= 0:
        return
    e = s * p
    x1 = cx - s * 0.5
    x2 = x1 + e * 0.35
    y2 = cy + e * 0.35
    x3 = x2 + e * 0.6
    y3 = y2 - e * 0.7
    d.line([(x1, cy), (x2, y2)], fill=col, width=8)
    d.line([(x2, y2), (x3, y3)], fill=col, width=8)

def word_pop(d, lt, t0, x, y, txt, f, col, drop=18, punch=False, ul=None):
    if lt < t0:
        return
    p = min(1.0, (lt - t0) / 0.12)
    if punch and p < 1:
        sz = max(30, int(f.size * (1.26 - 0.26 * p)))
        fp = font('Black', sz)
        wp = d.textlength(txt, font=fp)
        xf = x + (d.textlength(txt, font=f) - wp) / 2 + _jit(lt, t0)
        c = col if p > 0.55 else lerp_c(NAVY2, col, p / 0.55)
        d.text((xf, y + int((1 - p) * drop)), txt, font=fp, fill=c)
    else:
        c = lerp_c(NAVY2, col, p) if p < 1 else col
        d.text((x, y + int((1 - p) * drop)), txt, font=f, fill=c)
    if ul is not None and lt > t0 + 0.10:
        g = ease_cubic(min(1.0, (lt - t0 - 0.10) / 0.18))
        if g > 0:
            ww = d.textlength(txt, font=f)
            d.rectangle([x, ul, x + ww * g, ul + 9], fill=YELLOW)

def year_counter(d, lt, t0, t1):
    if lt < t0 or lt > t1 + 0.4:
        return
    p = min(1.0, max(0.0, (lt - t0) / max(0.3, (t1 - t0))))
    yr = 1960 + int(66 * ease_cubic(p) + 0.0001)
    fA = font('Light', 56)
    fB = font('Black', 66)
    wa = d.textlength('1960', font=fA)
    war = d.textlength(' → ', font=fA)
    wb = d.textlength(str(yr), font=fB)
    x0 = CX - (wa + war + wb) / 2
    d.text((x0, 1000), '1960', font=fA, fill=MUTED)
    d.text((x0 + wa, 1004), ' → ', font=fA, fill=FAINT)
    d.text((x0 + wa + war, 990), str(yr), font=fB, fill=YELLOW if yr >= 2026 else WHITE)

def cut_flash(img, lt):
    if lt < 0.07:
        a = 1.0 + 0.15 * (1.0 - lt / 0.07)
        img.paste(_IE.Brightness(img).enhance(a), (0, 0))

_LCACHE = {}

def sync_line(d, t, y, words):
    key = tuple((w, s) for w, _, _, s, _p in words)
    if key not in _LCACHE:
        fs = [font('Black', s) for _, _, _, s, _p in words]
        ws = [d.textlength(w, font=f) for (w, _, _, _, _p), f in zip(words, fs)]
        gap = 28
        total = sum(ws) + gap * (len(ws) - 1)
        if total > 940:
            sc = 940.0 / total
            fs = [font('Black', max(40, int(s * sc))) for (_, _, _, s, _p) in words]
            ws = [d.textlength(w, font=f) for (w, _, _, _, _p), f in zip(words, fs)]
            total = sum(ws) + gap * (len(ws) - 1)
        x = CX - total / 2
        xs = []
        for wdt in ws:
            xs.append(x)
            x += wdt + gap
        _LCACHE[key] = (fs, xs)
    fs, xs = _LCACHE[key]
    for (txt, t0, col, sz, punch), f, x in zip(words, fs, xs):
        word_pop(d, t, t0, x, y, txt, f, col, punch=punch, ul=(y + 118) if punch else None)

def s4cover(d, img, lt, dur):
    global _skip_env
    _skip_env = True
    cov_path = 'renders/r4-cover.jpg'
    if os.path.exists(cov_path):
        plate = _PImage.open(cov_path).convert('RGB')
        p = min(1.0, lt / dur)
        sc = 1.0 - 0.015 * ease_cubic(p)
        if abs(sc - 1.0) > 0.002:
            w, h = plate.size
            plate = plate.resize((int(w * sc), int(h * sc)), _PImage.LANCZOS)
        img.paste(plate, ((W - plate.size[0]) // 2, (H - plate.size[1]) // 2))
    return []

# Run CLI
if __name__ == '__main__':
    SEG = sys.argv[1:] or ['covers']
    if 'reel1' in SEG:
        print('── REEL 1: THE PRICE (15s) ──')
        render('r1', REEL1, os.path.join(OUT, 'reel-1-price.mp4'), 15.0)
    if 'reel2' in SEG:
        print('── REEL 2: EVERY DOCUMENT (13s) ──')
        render('r2', REEL2, os.path.join(OUT, 'reel-2-documents.mp4'), 13.0)
    if 'reel3' in SEG:
        print('── REEL 3: CAUTION FEE (38s, voiceover) ──')
        render('r3', REEL3, os.path.join(OUT, 'reel-3-cautionfee.mp4'), 38.0)
    if 'covers' in SEG:
        make_covers()
    print('DONE')
