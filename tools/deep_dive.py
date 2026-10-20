#!/usr/bin/env python3
"""Deep-dive assembler v4: speech-driven documentary motion engine.

Upgrades over v3:
1. Speech-locked visual scene cuts: every archival plate cuts in at the exact
   spoken word timestamp where that topic begins (13 scenes in Johnstown,
   16 scenes in Enron — a new visual cut every 5-8s).
2. Aspect-correct 2304x1296 super-sampled plates + true sub-pixel floating-point
   camera rig (Image.EXTENT + BICUBIC with S-curve easing) — zero integer
   stepping, zero stretched portrait photos, plus whip-zoom + optical flare cuts.
3. Contextual visual diagrams (viz_layer): live stock charts ($90.75 boom &
   $0.26 crash), LJM/Raptor/Chewco shell-maze diagram, Mark-to-Market ledger,
   South Fork Dam failure anatomy, 36-ft wave scale, 14-mile valley profile.
4. Strict non-overlapping speech-synced hero beats + live word-by-word broadcast
   caption ribbon at lower-center that highlights every spoken word in real time.

Run: .venv/bin/python tools/deep_dive.py [johnstown|enron]
"""
import os, sys, json, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import generate_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1280, 720, 24
CW, CH = 1920, 1080  # 1.5x super-sampled plate canvas for sub-pixel camera

NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
CRIMSON = (255, 86, 92)
EMERALD = (72, 232, 164)
WHITE = (255, 255, 255)
FAINT = (122, 156, 202)
ICE = (170, 210, 248)

FFMPEG = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
FDIR = os.path.join(ROOT, 'assets', 'fonts')
IMG = os.path.join(ROOT, 'image-search')
AUDIO = os.path.join(ROOT, 'assets', 'deepdive')

FONT_CACHE = {}

def fnt(w, sz):
    k = (w, int(sz))
    if k not in FONT_CACHE:
        FONT_CACHE[k] = ImageFont.truetype(os.path.join(FDIR, f'Inter-{w}.ttf'), int(sz))
    return FONT_CACHE[k]

# ---------------------------------------------------------------- easing ----
def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))

def ease_out_expo(x):
    x = clamp01(x)
    return 1.0 if x >= 1.0 else 1.0 - 2.0 ** (-10.0 * x)

def ease_out_cubic(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3

def ease_in_out_sine(x):
    x = clamp01(x)
    return 0.5 - 0.5 * math.cos(math.pi * x)

def ease_out_back(x):
    x = clamp01(x)
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2

def duration(path):
    r = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if 'Duration:' in ln:
            hh, mm, rest = ln.split('Duration: ')[1].split(',')[0].strip().split(':')
            return int(hh) * 3600 + int(mm) * 60 + float(rest)
    raise SystemExit(f'no duration for {path}')

# -------------------------------------- blue grade + aspect-correct plate ----
def _duotone_luts():
    shadow, mid, high = (3, 11, 32), (14, 52, 114), (176, 214, 250)
    lr, lg, lb = [], [], []
    for i in range(256):
        t = i / 255.0
        if t < 0.55:
            u = t / 0.55
            c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
        else:
            u = (t - 0.55) / 0.45
            c = [mid[k] + (high[k] - mid[k]) * (u ** 1.12) for k in range(3)]
        lr.append(int(c[0])); lg.append(int(c[1])); lb.append(int(c[2]))
    return lr, lg, lb

LUT_R, LUT_G, LUT_B = _duotone_luts()

def grade_blue(im, tint_warm=0.0):
    """Cinematic blue-duotone grade, with optional warm highlight ember tint."""
    rgb = im.convert('RGB')
    lum = rgb.convert('L')
    duo = Image.merge('RGB', (lum.point(LUT_R), lum.point(LUT_G), lum.point(LUT_B)))
    out = Image.blend(rgb, duo, 0.82)
    if tint_warm > 0:
        warm = Image.merge('RGB', (
            lum.point(lambda v: min(255, int(v * 1.25))),
            lum.point(lambda v: int(v * 0.68)),
            lum.point(lambda v: int(v * 0.28)),
        ))
        out = Image.blend(out, warm, tint_warm)
    return out.point(lambda v: max(0, min(255, int(128 + (v - 128) * 1.14))))

def vignette():
    v = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.22, -H * 0.30, W * 1.22, H * 1.30], fill=255)
    return v.filter(ImageFilter.GaussianBlur(115))

VIG = vignette()
VIG_DARK = Image.new('RGB', (W, H), (2, 7, 20))

def prep_plate(path, focus_side=0.0, tint_warm=0.0):
    """Build an aspect-correct 2304x1296 super-sampled cinema plate.

    - Landscape photos (>= 1.28 aspect): cover-fit without stretching, sharpen,
      and blue-grade.
    - Portrait/square archival photos (< 1.28 aspect): build a blurred, darkened
      16:9 backdrop and mount the crisp unstretched archival plate with a subtle
      glass border, shifted slightly to `focus_side` (-1 left, 0 center, +1 right)
      so callout graphics sit cleanly on the opposite side.
    """
    raw = Image.open(path).convert('RGB')
    aspect = raw.width / max(1.0, float(raw.height))
    target_aspect = CW / float(CH)

    if aspect >= 1.28:
        if aspect > target_aspect:
            nh = CH
            nw = int(round(CH * aspect))
        else:
            nw = CW
            nh = int(round(CW / aspect))
        scaled = raw.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - CW) // 2
        y0 = int((nh - CH) * 0.38)  # favor upper-middle (faces/horizons)
        canvas = scaled.crop((x0, y0, x0 + CW, y0 + CH))
        canvas = canvas.filter(ImageFilter.UnsharpMask(radius=1.5, percent=115, threshold=2))
        return grade_blue(canvas, tint_warm=tint_warm)
    else:
        # Blurred 16:9 ambient backdrop
        bg = raw.resize((CW, CH), Image.BICUBIC).filter(ImageFilter.GaussianBlur(48))
        bg = grade_blue(bg, tint_warm=tint_warm).point(lambda v: int(v * 0.42))
        # Fit sharp photo inside 86% of canvas height
        fh = int(CH * 0.86)
        fw = int(round(fh * aspect))
        fg = raw.resize((fw, fh), Image.LANCZOS)
        fg = fg.filter(ImageFilter.UnsharpMask(radius=1.4, percent=115, threshold=2))
        fg = grade_blue(fg, tint_warm=tint_warm)
        cx = int(CW * (0.5 + 0.17 * focus_side))
        cy = CH // 2
        px, py = cx - fw // 2, cy - fh // 2
        # Soft frame glow
        d = ImageDraw.Draw(bg)
        d.rounded_rectangle([px - 4, py - 4, px + fw + 4, py + fh + 4],
                            radius=14, outline=(120, 180, 245), width=3)
        bg.paste(fg, (px, py))
        return bg

# --------------------------------------- sub-pixel smooth camera movement ----
def camera_frame(plate, p, mode='push_in', focus=(0.5, 0.48), extra_zoom=1.0):
    """True sub-pixel floating-point camera rig using Image.EXTENT + BICUBIC.

    Smooth cosine S-curve blended with linear momentum so camera never freezes
    and never integer-steps.
    """
    p = clamp01(p)
    s = 0.65 * ease_in_out_sine(p) + 0.35 * p
    fx, fy = focus

    if mode == 'push_in':
        z = 1.04 + 0.14 * s
        dx = (fx - 0.5) * 0.12 * s
        dy = (fy - 0.5) * 0.10 * s
    elif mode == 'pull_out':
        z = 1.18 - 0.14 * s
        dx = (fx - 0.5) * 0.10 * (1.0 - s)
        dy = (fy - 0.5) * 0.08 * (1.0 - s)
    elif mode == 'pan_right':
        z = 1.12 + 0.05 * s
        dx = -0.055 + 0.11 * s
        dy = (fy - 0.5) * 0.06 * s
    elif mode == 'pan_left':
        z = 1.12 + 0.05 * s
        dx = 0.055 - 0.11 * s
        dy = (fy - 0.5) * 0.06 * s
    elif mode == 'tilt_up':
        z = 1.12 + 0.06 * s
        dx = (fx - 0.5) * 0.06 * s
        dy = 0.045 - 0.09 * s
    else:  # 'drift_in'
        z = 1.06 + 0.11 * s
        dx = 0.03 * math.sin(p * math.pi)
        dy = -0.02 * s

    z *= extra_zoom
    vw = CW / z
    vh = CH / z
    cx = CW * (0.5 + dx)
    cy = CH * (0.5 + dy)
    x0 = max(0.0, min(CW - vw, cx - vw * 0.5))
    y0 = max(0.0, min(CH - vh, cy - vh * 0.5))
    im = plate.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)
    return Image.composite(im, VIG_DARK, VIG)

def optical_flare_transition(f_prev, f_curr, u):
    """Smooth whip-zoom cross-dissolve with anamorphic horizontal lens flare."""
    e = ease_in_out_sine(u)
    base = Image.blend(f_prev, f_curr, e)
    # Peak flare intensity at midpoint u=0.5
    inten = math.sin(clamp01(u) * math.pi) ** 1.6
    if inten <= 0.02:
        return base
    flare = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(flare)
    cy = int(H * 0.5)
    band_h = int(95 * inten + 12)
    a_core = int(72 * inten)
    d.ellipse([-120, cy - band_h, W + 120, cy + band_h], fill=(165, 215, 255, a_core))
    d.rectangle([0, cy - 3, W, cy + 3], fill=(255, 225, 130, int(90 * inten)))
    flare = flare.filter(ImageFilter.GaussianBlur(18))
    return Image.alpha_composite(base.convert('RGBA'), flare).convert('RGB')

# ------------------------------------------------------------- glass cards ----
GLASS_CACHE = {}

def glass_card(w, h, radius=18, top=(12, 42, 92), bot=(5, 20, 52),
               a_top=222, a_bot=188, border_col=(126, 184, 255, 165)):
    w, h = max(16, int(w)), max(16, int(h))
    key = (w, h, radius, top, bot, a_top, a_bot, border_col)
    if key in GLASS_CACHE:
        return GLASS_CACHE[key]
    S = 2
    mask = Image.new('L', (w * S, h * S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * S - 1, h * S - 1], radius=radius * S, fill=255)
    grad = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(h * S):
        u = y / max(1, h * S - 1)
        col = tuple(int(top[k] + (bot[k] - top[k]) * u) for k in range(3))
        gd.line([(0, y), (w * S, y)], fill=col + (int(a_top + (a_bot - a_top) * u),))
    card = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0))
    card.paste(grad, (0, 0), mask)
    bd = ImageDraw.Draw(card)
    bd.rounded_rectangle([1, 1, w * S - 2, h * S - 2], radius=radius * S,
                         outline=border_col, width=3)
    card = card.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(card)
    d.line([(radius, 1), (w - radius, 1)], fill=(210, 234, 255, 110), width=1)
    GLASS_CACHE[key] = card
    return card

def card_alpha(card, a):
    a = clamp01(a)
    if a >= 0.999:
        return card
    c = card.copy()
    c.putalpha(c.getchannel('A').point(lambda v: int(v * a)))
    return c

# -------------------------------------------------------------- text engine ----
def tracked_width(d, text, font, tracking):
    if not text:
        return 0.0
    return sum(d.textlength(ch, font=font) + tracking for ch in text) - tracking

def draw_tracked(d, text, font, x, y, fill, tracking=3.0):
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking

def kinetic_line(layer, text, font, cx, y, t, t0, color=WHITE, tracking=3.0,
                 stagger=0.04, dur=0.48, slide=32, bounce=False, out_a=1.0):
    """Per-letter stagger: fade + slide with motion smear."""
    if out_a <= 0.01:
        return
    d = ImageDraw.Draw(layer)
    w = tracked_width(d, text, font, tracking)
    x = cx - w / 2.0
    for i, ch in enumerate(text):
        local = clamp01((t - t0 - i * stagger) / dur)
        if local <= 0:
            x += d.textlength(ch, font=font) + tracking
            continue
        e = ease_out_back(local) if bounce else ease_out_expo(local)
        a = int(255 * min(1.0, local * 1.9) * out_a)
        yy = y + (1.0 - e) * slide
        if local < 0.96:
            d.text((x, yy + (1.0 - e) * slide * 0.45), ch, font=font, fill=color + (a // 3,))
        d.text((x, yy), ch, font=font, fill=color + (a,))
        x += d.textlength(ch, font=font) + tracking

def fit_font(weight, sz, text, maxw, tracking=2.5):
    f = fnt(weight, sz)
    d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    while tracked_width(d, text, f, tracking) > maxw and sz > 20:
        sz = int(sz * 0.92)
        f = fnt(weight, sz)
    return f

# ------------------------------------------------ cold-open & end overlays ----
def cold_open_overlay(layer, title_pair, t, dur=4.3):
    """Sleek translucent cold-open documentary banner over the opening shot."""
    if t < 0 or t > dur:
        return
    in_e = ease_out_expo(clamp01(t / 0.55))
    out_a = 1.0 if t < dur - 0.55 else 1.0 - ease_in_out_sine((t - (dur - 0.55)) / 0.55)
    a = in_e * out_a
    if a <= 0.01:
        return
    t1, t2 = title_pair
    f1 = fit_font('Black', 62, t1, W - 260, 3.0)
    f2 = fnt('SemiBold', 22)
    d = ImageDraw.Draw(layer)
    w1 = tracked_width(d, t1, f1, 3.0)
    pw = int(min(W - 140, max(w1 + 120, 620)))
    ph = 168
    px = W // 2 - pw // 2
    py = int(205 - (1.0 - in_e) * 28)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=22, a_top=225, a_bot=195), a), (px, py))
    # Top yellow documentary tag bar
    bw = int(160 * ease_out_back(clamp01((t - 0.10) / 0.5)))
    d.rectangle([W // 2 - bw // 2, py + 22, W // 2 + bw // 2, py + 27],
                fill=YELLOW + (int(240 * a),))
    kinetic_line(layer, t1, f1, W / 2, py + 40, t, 0.06, WHITE, 3.0,
                 stagger=0.028, dur=0.42, slide=24, out_a=a)
    w2 = tracked_width(d, t2, f2, 4.5)
    sa = int(235 * clamp01((t - 0.35) / 0.45) * a)
    if sa > 0:
        draw_tracked(d, t2, f2, W / 2 - w2 / 2, py + 122, ICE + (sa,), 4.5)

def end_card_overlay(base_img, end_pair, t_local, T):
    """Final subscribe CTA overlay over the closing shot."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    e = ease_out_expo(clamp01(t_local / 0.5))
    # Darken background slightly so CTA pops
    dim = Image.new('RGBA', (W, H), (3, 12, 28, int(165 * e)))
    layer = Image.alpha_composite(layer, dim)
    t1, t2 = end_pair
    pw, ph = 820, 230
    px, py = (W - pw) // 2, (H - ph) // 2 - 10
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=26, a_top=235, a_bot=205,
                                                border_col=YELLOW + (190,)), e), (px, py))
    d = ImageDraw.Draw(layer)
    f1 = fnt('Black', 68)
    f2 = fit_font('SemiBold', 24, t2.upper(), pw - 90, 3.5)
    kinetic_line(layer, t1, f1, W / 2, py + 34, t_local, 0.05, YELLOW, 4.0,
                 stagger=0.04, dur=0.45, slide=28, bounce=True, out_a=e)
    bw = int(220 * ease_out_back(clamp01((t_local - 0.25) / 0.5)))
    d.rectangle([W // 2 - bw // 2, py + 128, W // 2 + bw // 2, py + 133],
                fill=WHITE + (int(220 * e),))
    w2 = tracked_width(d, t2.upper(), f2, 3.5)
    sa = int(240 * clamp01((t_local - 0.30) / 0.45))
    if sa > 0:
        draw_tracked(d, t2.upper(), f2, W / 2 - w2 / 2, py + 154, ICE + (sa,), 3.5)
    return Image.alpha_composite(base_img.convert('RGBA'), layer).convert('RGB')

# -------------------------------------- HUD + chapter badge + word ribbon ----
def hud_chapter_layer(kicker, sub, idx, nscenes, t_scene, scene_dur, total_frac):
    """Top-left chapter badge + top-right retention progress indicator."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    in_e = ease_out_expo(clamp01(t_scene / 0.45))
    out_e = 1.0 if (scene_dur - t_scene) > 0.35 else clamp01((scene_dur - t_scene) / 0.35)
    a = in_e * out_e
    if a > 0.02:
        fk = fnt('Bold', 20)
        fs = fnt('Medium', 14)
        fc = fnt('Black', 14)
        d = ImageDraw.Draw(layer)
        tag = f'CH {idx:02d}/{nscenes:02d}'
        wk = tracked_width(d, kicker, fk, 1.8)
        ws = tracked_width(d, sub, fs, 2.0) if sub else 0
        cw = int(max(wk + 120, ws + 120))
        ch = 64 if sub else 46
        cx, cy = int(36 - (1.0 - in_e) * 32), 28
        layer.alpha_composite(card_alpha(glass_card(cw, ch, radius=14, a_top=210, a_bot=175), a), (cx, cy))
        # Yellow chapter pill
        d.rounded_rectangle([cx + 12, cy + 12, cx + 92, cy + 34], radius=6,
                            fill=YELLOW + (int(240 * a),))
        wt = d.textlength(tag, font=fc)
        d.text((cx + 52 - wt / 2, cy + 15), tag, font=fc, fill=NAVY + (int(255 * a),))
        draw_tracked(d, kicker, fk, cx + 104, cy + 11, WHITE + (int(250 * a),), 1.8)
        if sub:
            draw_tracked(d, sub, fs, cx + 104, cy + 39, ICE + (int(215 * a),), 2.0)

    # Top-right documentary progress pill + bottom edge bar
    d = ImageDraw.Draw(layer)
    pw, ph = 158, 36
    px, py = W - pw - 36, 28
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18, a_top=195, a_bot=160), 0.92), (px, py))
    fp = fnt('Bold', 14)
    pct = f'{int(clamp01(total_frac) * 100):3d}%'
    d.text((px + 16, py + 9), 'DOC', font=fp, fill=ICE + (210,))
    d.rectangle([px + 56, py + 15, px + 112, py + 21], fill=(255, 255, 255, 45))
    fill_w = int(56 * clamp01(total_frac))
    if fill_w > 0:
        d.rectangle([px + 56, py + 15, px + 56 + fill_w, py + 21], fill=YELLOW + (240,))
    d.text((px + 118, py + 9), pct, font=fp, fill=WHITE + (235,))

    # Full-width thin bottom progress bar
    d.rectangle([0, H - 5, W, H], fill=(255, 255, 255, 32))
    bx = int(W * clamp01(total_frac))
    if bx > 0:
        d.rectangle([0, H - 5, bx, H], fill=YELLOW + (235,))
    return layer

def build_caption_stream(key, raw_words):
    """Map verbatim clean script clauses onto exact pocketsphinx word timestamps."""
    clauses = SCRIPTS[key]['captions']
    stream = []
    for i0, i1, text in clauses:
        seg = raw_words[i0:i1 + 1]
        t_start, t_end = seg[0][0], seg[-1][1]
        cwords = text.split()
        n = len(cwords)
        if n == len(seg):
            w_entries = [(seg[j][0], seg[j][1], cwords[j]) for j in range(n)]
        else:
            # Interpolate proportional to character length over exact segment window
            weights = [max(2, len(w)) for w in cwords]
            tot_w = float(sum(weights))
            cur = t_start
            w_entries = []
            for w, wt in zip(cwords, weights):
                dt = (t_end - t_start) * (wt / tot_w)
                w_entries.append((cur, cur + dt, w))
                cur += dt
        stream.append(dict(t0=t_start, t1=t_end, words=w_entries))
    return stream

def caption_ribbon_layer(stream, t):
    """Live broadcast word-sync caption ribbon at lower-center (y=636)."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    active = None
    for c in stream:
        if c['t0'] - 0.12 <= t <= c['t1'] + 0.18:
            active = c
            break
    if not active:
        return layer

    in_a = clamp01((t - (active['t0'] - 0.12)) / 0.16)
    out_a = clamp01(((active['t1'] + 0.18) - t) / 0.18)
    a = min(in_a, out_a)
    if a <= 0.02:
        return layer

    f = fnt('ExtraBold', 27)
    d = ImageDraw.Draw(layer)
    gap = 11.0
    words = active['words']
    widths = [d.textlength(w.upper(), font=f) for _, _, w in words]
    total_w = sum(widths) + gap * max(0, len(words) - 1)
    if total_w > W - 160:
        f = fnt('ExtraBold', 23)
        widths = [d.textlength(w.upper(), font=f) for _, _, w in words]
        total_w = sum(widths) + gap * max(0, len(words) - 1)

    pw = int(total_w + 56)
    ph = 54
    px = W // 2 - pw // 2
    py = H - 76
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=16, top=(6, 22, 52), bot=(3, 12, 30),
                                                a_top=232, a_bot=215), a), (px, py))

    # Find currently spoken word index
    cur_idx = 0
    for j, (ws, we, _) in enumerate(words):
        if t >= ws - 0.04:
            cur_idx = j

    x = W / 2.0 - total_w / 2.0
    for j, ((ws, we, w), ww) in enumerate(zip(words, widths)):
        txt = w.upper()
        if j == cur_idx:
            # Active word highlight pill + yellow text
            pad_x = 7
            d.rounded_rectangle([x - pad_x, py + 8, x + ww + pad_x, py + ph - 8],
                                radius=8, fill=(255, 201, 60, int(48 * a)),
                                outline=(255, 201, 60, int(145 * a)), width=1)
            d.text((x, py + 11), txt, font=f, fill=YELLOW + (int(255 * a),))
        elif j < cur_idx:
            d.text((x, py + 12), txt, font=f, fill=WHITE + (int(240 * a),))
        else:
            d.text((x, py + 12), txt, font=f, fill=ICE + (int(155 * a),))
        x += ww + gap
    return layer

# ------------------------- contextual visual diagrams (viz_layer) -----------
def viz_layer(viz_kind, t_scene, scene_dur):
    """Contextual visual infographic over the image explaining the spoken concept."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if not viz_kind:
        return layer
    in_e = ease_out_expo(clamp01((t_scene - 0.15) / 0.5))
    out_a = 1.0 if (scene_dur - t_scene) > 0.45 else clamp01((scene_dur - t_scene) / 0.45)
    a = in_e * out_a
    if a <= 0.02:
        return layer
    prog = clamp01((t_scene - 0.15) / 1.65)
    d = ImageDraw.Draw(layer)

    if viz_kind == 'pressure_gauge':
        # Hydrostatic dam load meter on left side
        pw, ph, px, py = 330, 130, 44, 468
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=16), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Black', 24)
        d.text((px + 18, py + 14), 'HYDROSTATIC DAM LOAD', font=f1, fill=ICE + (int(230 * a),))
        d.rectangle([px + 18, py + 48, px + pw - 18, py + 72], fill=(255, 255, 255, int(38 * a)))
        bw = int((pw - 36) * ease_out_expo(prog))
        col = CRIMSON if prog > 0.75 else YELLOW
        if bw > 2:
            d.rectangle([px + 18, py + 48, px + 18 + bw, py + 72], fill=col + (int(240 * a),))
        d.text((px + 18, py + 84), 'EARTHEN CREST: CRITICAL', font=f1, fill=col + (int(245 * a),))

    elif viz_kind == 'dam_anatomy':
        # 3 fatal club modifications checklist on left
        pw, ph, px, py = 468, 210, 44, 390
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        fh = fnt('Black', 18)
        fb = fnt('SemiBold', 17)
        d.text((px + 20, py + 16), 'FATAL MODIFICATIONS TO DAM', font=fh, fill=YELLOW + (int(245 * a),))
        items = [
            (0.08, '01  IRON FISH SCREENS CLOG DRAIN PIPES'),
            (0.32, '02  SPILLWAY CHOKED WITH DEBRIS'),
            (0.56, '03  CREST LOWERED 3 FT FOR CARRIAGE ROAD'),
        ]
        for idx, (thr, txt) in enumerate(items):
            ia = clamp01((prog - thr) / 0.25) * a
            if ia > 0.02:
                yy = py + 56 + idx * 46
                d.rounded_rectangle([px + 20, yy, px + pw - 20, yy + 36], radius=8,
                                    fill=(255, 86, 92, int(45 * ia)),
                                    outline=CRIMSON + (int(160 * ia),), width=1)
                d.text((px + 32, yy + 7), txt, font=fb, fill=WHITE + (int(245 * ia),))

    elif viz_kind == 'rain_rising':
        # Animated rain streaks across frame + rising reservoir level bar
        for r in range(34):
            rx = int(((r * 97 + t_scene * 420) % (W + 120)) - 60)
            ry = int(((r * 61 + t_scene * 780) % (H + 120)) - 60)
            d.line([(rx, ry), (rx - 14, ry + 42)], fill=(185, 220, 255, int(70 * a)), width=2)
        pw, ph, px, py = 310, 150, 44, 448
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=16), a), (px, py))
        f1 = fnt('Bold', 16)
        d.text((px + 18, py + 14), 'RESERVOIR WATER LEVEL', font=f1, fill=ICE + (int(235 * a),))
        d.rectangle([px + 18, py + 48, px + pw - 18, py + 82], outline=ICE + (int(140 * a),), width=2)
        fill_w = int((pw - 40) * ease_out_cubic(prog))
        col = CRIMSON if prog > 0.8 else YELLOW
        d.rectangle([px + 20, py + 50, px + 20 + fill_w, py + 80], fill=col + (int(230 * a),))
        d.text((px + 18, py + 98), 'STATUS: OVERTOPPING CREST', font=f1, fill=CRIMSON + (int(245 * a),))

    elif viz_kind == 'valley_drop':
        # 14-mile elevation drop profile from Lake Conemaugh to Johnstown
        pw, ph, px, py = 460, 165, 44, 435
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('SemiBold', 14)
        d.text((px + 20, py + 14), '14-MILE CONEMAUGH VALLEY DROP', font=f1, fill=YELLOW + (int(245 * a),))
        pts = [(px + 34, py + 58), (px + 160, py + 82), (px + 290, py + 112), (px + 420, py + 126)]
        d.line(pts, fill=ICE + (int(160 * a),), width=3)
        # Moving wave front along path
        wx = int(px + 34 + (420 - 34) * ease_in_out_sine(prog))
        wy = int(py + 58 + (126 - 58) * ease_in_out_sine(prog))
        d.ellipse([wx - 8, wy - 8, wx + 8, wy + 8], fill=YELLOW + (int(255 * a),))
        d.text((px + 24, py + 134), 'SOUTH FORK DAM (3:10 PM)', font=f2, fill=ICE + (int(220 * a),))
        d.text((px + 275, py + 134), 'JOHNSTOWN (4:07 PM)', font=f2, fill=WHITE + (int(240 * a),))

    elif viz_kind == 'wave_scale':
        # 36-foot wave height comparison bars on left
        pw, ph, px, py = 360, 190, 44, 410
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Bold', 14)
        d.text((px + 20, py + 14), 'FLOOD WAVE HEIGHT SCALE', font=f1, fill=YELLOW + (int(245 * a),))
        base_y = py + 152
        bars = [('LOCOMOTIVE', 14, ICE), ('2-STORY HOUSE', 24, WHITE), ('FLOOD WALL', 36, CRIMSON)]
        for idx, (lab, ft, col) in enumerate(bars):
            bx = px + 34 + idx * 108
            bh = int((ft / 36.0) * 92 * ease_out_expo(clamp01((prog - idx * 0.15) / 0.55)))
            d.rectangle([bx, base_y - bh, bx + 64, base_y], fill=col + (int(230 * a),))
            d.text((bx + 6, base_y - bh - 20), f'{ft} FT', font=f2, fill=WHITE + (int(240 * a),))
            d.text((bx - 4, base_y + 8), lab[:10], font=f2, fill=ICE + (int(210 * a),))

    elif viz_kind == 'mtm_ledger':
        # Mark-to-market accounting diagram: 10-yr projected profits -> Day 1
        pw, ph, px, py = 460, 175, 44, 425
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Black', 18)
        d.text((px + 20, py + 14), 'MARK-TO-MARKET ILLUSION', font=f1, fill=YELLOW + (int(245 * a),))
        for yr in range(10):
            bx = px + 22 + yr * 24
            d.rectangle([bx, py + 54, bx + 18, py + 104],
                        fill=(120, 175, 240, int(185 * a)), outline=WHITE + (int(120 * a),))
        d.text((px + 22, py + 114), '10-YR UNEARNED PROJECTION', font=fnt('SemiBold', 14), fill=ICE + (int(220 * a),))
        if prog > 0.25:
            pa = clamp01((prog - 0.25) / 0.4) * a
            d.rounded_rectangle([px + 280, py + 48, px + 440, py + 118], radius=10,
                                fill=(255, 201, 60, int(55 * pa)), outline=YELLOW + (int(230 * pa),), width=2)
            d.text((px + 296, py + 60), 'BOOKED DAY 1', font=f2, fill=YELLOW + (int(250 * pa),))
            d.text((px + 296, py + 86), 'AS REAL PROFIT', font=fnt('Bold', 15), fill=WHITE + (int(245 * pa),))

    elif viz_kind == 'stock_boom':
        # Live climbing Enron stock chart ($18 -> $90.75)
        pw, ph, px, py = 440, 185, 44, 415
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Black', 24)
        d.text((px + 20, py + 14), 'NYSE: ENE · SHARE PRICE', font=f1, fill=ICE + (int(235 * a),))
        vals = [0.18, 0.24, 0.31, 0.42, 0.39, 0.55, 0.68, 0.79, 0.92, 1.00]
        n_pts = max(2, int(len(vals) * ease_out_cubic(prog)))
        pts = []
        for idx in range(n_pts):
            vx = px + 26 + idx * ((pw - 56) / (len(vals) - 1))
            vy = py + 150 - vals[idx] * 92
            pts.append((vx, vy))
        if len(pts) >= 2:
            d.line(pts, fill=EMERALD + (int(245 * a),), width=4)
            lx, ly = pts[-1]
            d.ellipse([lx - 7, ly - 7, lx + 7, ly + 7], fill=YELLOW + (int(255 * a),))
            cur_p = 18.0 + (90.75 - 18.0) * vals[n_pts - 1]
            d.text((px + pw - 125, py + 12), f'${cur_p:0.2f}', font=f2, fill=EMERALD + (int(250 * a),))

    elif viz_kind == 'shell_maze':
        # Off-books shell partnership flow diagram
        pw, ph, px, py = 480, 180, 44, 420
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Black', 17)
        d.text((px + 20, py + 14), 'OFF-BALANCE-SHEET SHELL MAZE', font=f1, fill=YELLOW + (int(245 * a),))
        nodes = ['ENRON', 'LJM 1 & 2', 'RAPTOR', 'CHEWCO']
        for idx, nm in enumerate(nodes):
            na = clamp01((prog - idx * 0.16) / 0.3) * a
            if na > 0.02:
                nx = px + 20 + idx * 112
                ny = py + 54
                col = CRIMSON if idx > 0 else ICE
                d.rounded_rectangle([nx, ny, nx + 98, ny + 52], radius=10,
                                    fill=(20, 45, 90, int(220 * na)), outline=col + (int(220 * na),), width=2)
                d.text((nx + 10, ny + 16), nm, font=f2, fill=WHITE + (int(250 * na),))
        d.text((px + 20, py + 128), 'RESULT: $30B+ IN LOSSES HIDDEN FROM INVESTORS',
               font=fnt('Bold', 15), fill=CRIMSON + (int(245 * a),))

    elif viz_kind == 'insider_split':
        # Told employees BUY vs Insiders SOLD $1.1B
        pw, ph, px, py = 460, 165, 44, 435
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        fb = fnt('Bold', 16)
        d.rounded_rectangle([px + 18, py + 18, px + pw - 18, py + 76], radius=10,
                            fill=(72, 232, 164, int(36 * a)), outline=EMERALD + (int(180 * a),), width=2)
        d.text((px + 30, py + 26), 'MESSAGE TO STAFF:', font=fb, fill=EMERALD + (int(240 * a),))
        d.text((px + 30, py + 48), '“KEEP BUYING ENRON STOCK”', font=fnt('Black', 18), fill=WHITE + (int(250 * a),))
        if prog > 0.30:
            sa = clamp01((prog - 0.30) / 0.35) * a
            d.rounded_rectangle([px + 18, py + 88, px + pw - 18, py + 148], radius=10,
                                fill=(255, 86, 92, int(48 * sa)), outline=CRIMSON + (int(210 * sa),), width=2)
            d.text((px + 30, py + 96), 'WHAT EXECUTIVES ACTUALLY DID:', font=fb, fill=CRIMSON + (int(245 * sa),))
            d.text((px + 30, py + 118), 'CASHED OUT $1.1 BILLION IN SHARES', font=fnt('Black', 18), fill=YELLOW + (int(250 * sa),))

    elif viz_kind == 'stock_crash':
        # Live crashing Enron stock chart ($90.75 -> $0.26)
        pw, ph, px, py = 430, 185, 44, 415
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), a), (px, py))
        f1, f2 = fnt('Bold', 16), fnt('Black', 24)
        d.text((px + 20, py + 14), 'NYSE: ENE · COLLAPSE (2001)', font=f1, fill=ICE + (int(235 * a),))
        vals = [1.0, 0.88, 0.74, 0.58, 0.42, 0.28, 0.15, 0.06, 0.01, 0.003]
        n_pts = max(2, int(len(vals) * ease_out_cubic(prog)))
        pts = []
        for idx in range(n_pts):
            vx = px + 26 + idx * ((pw - 56) / (len(vals) - 1))
            vy = py + 152 - vals[idx] * 94
            pts.append((vx, vy))
        if len(pts) >= 2:
            d.line(pts, fill=CRIMSON + (int(250 * a),), width=4)
            lx, ly = pts[-1]
            d.ellipse([lx - 7, ly - 7, lx + 7, ly + 7], fill=CRIMSON + (int(255 * a),))
            cur_p = 90.75 * vals[n_pts - 1]
            d.text((px + pw - 130, py + 12), f'${cur_p:0.2f}', font=f2, fill=CRIMSON + (int(250 * a),))

    return layer

# ---------------------------------------------------------- word sync ----
def load_words(key):
    path = os.path.join(AUDIO, f'words-{key}.json')
    return json.load(open(path))

def find_phrase(words, phrase, occ=0):
    ws = phrase.split()
    hits = []
    for i in range(len(words) - len(ws) + 1):
        if [words[i + j][2] for j in range(len(ws))] == ws:
            hits.append(words[i:i + len(ws)])
    return hits[occ] if len(hits) > occ else None

def resolve_beats(key, words):
    """Map each beat's anchor phrase to its spoken word times & enforce non-overlap."""
    beats = []
    for b in SCRIPTS[key]['beats']:
        hit = find_phrase(words, b['a'], b.get('occ', 0))
        if not hit:
            raise SystemExit(f'beat anchor not found in words-{key}.json: {b["a"]!r}')
        b2 = dict(b)
        b2['t0'] = hit[0][0]
        b2['t1'] = hit[-1][1]
        b2['wtimes'] = [w[0] for w in hit]
        beats.append(b2)
    beats.sort(key=lambda b: b['t0'])
    # Clamp each beat's end_t so two hero cards NEVER overlap on screen
    for i, b in enumerate(beats):
        natural_end = b['t1'] + b.get('hold', 2.4)
        if i + 1 < len(beats):
            # Next beat pre-enters at next['t0'] - 0.30, and current fades out over 0.32s
            latest_end = beats[i + 1]['t0'] - 0.64
            b['end_t'] = max(b['t0'] + 0.35, min(natural_end, latest_end))
        else:
            b['end_t'] = natural_end
    return beats

def resolve_scenes(key, words, total_dur):
    """Resolve each scene's spoken anchor phrase into [t0, t1] intervals."""
    raw_scenes = SCRIPTS[key]['scenes']
    resolved = []
    for idx, sc in enumerate(raw_scenes):
        sc2 = dict(sc)
        if idx == 0 or not sc.get('a'):
            sc2['t0'] = 0.0
        else:
            hit = find_phrase(words, sc['a'], sc.get('occ', 0))
            if not hit:
                raise SystemExit(f'scene anchor not found in words-{key}.json: {sc["a"]!r}')
            sc2['t0'] = max(0.0, hit[0][0] - 0.15)
        resolved.append(sc2)
    for idx in range(len(resolved)):
        resolved[idx]['t1'] = resolved[idx + 1]['t0'] if idx + 1 < len(resolved) else total_dur
    return resolved

# --------------------------------------------------- speech-synced beats ----
def build_sfx_plan(key, words, beats):
    """Resolve the semantic sfx cue sheet (SCRIPTS[key]['sfx_cues']) to timings.

    Every effect is placed by spoken-word anchor — sound follows the story.
    Returns (events, beds, hushes) for score.generate_score()."""
    events, beds, hushes = [], [], []
    pan_flip = 1
    # subtle panned whooshes on hero-beat entrances only
    for b in beats:
        p = 0.32 * pan_flip
        pan_flip *= -1
        events.append(dict(kind='whoosh', t=max(0.0, b['t0'] - 0.22),
                           amp=0.15 if b.get('kind') == 'phrase' else 0.21, pan=p))
        if b.get('kind') == 'count':
            big = b.get('num', 0) >= 1000 or 'txt' in b
            if big:
                events.append(dict(kind='riser', t=max(0.0, b['t0'] - 1.15), amp=0.30, pan=0.0))
            events.append(dict(kind='boom', t=b['t0'] + b.get('dur', 1.35),
                               amp=0.32 if big else 0.15, pan=0.0))
    for cue in SCRIPTS[key].get('sfx_cues', []):
        if 'hush' in cue:
            h = dict(cue['hush'])
            hit = find_phrase(words, h['a'], h.get('occ', 0))
            if not hit:
                raise SystemExit(f"hush anchor not found: {h['a']!r}")
            hushes.append(dict(t=hit[0][0], dur=h.get('dur', 1.2),
                               depth=h.get('depth', 0.85), lead=h.get('lead', 0.5)))
            continue
        hit = find_phrase(words, cue['a'], cue.get('occ', 0)) if cue.get('a') else None
        if cue.get('a') and not hit:
            raise SystemExit(f"sfx cue anchor not found: {cue['a']!r}")
        t0 = (hit[0][0] if hit else 0.0) + cue.get('delay', 0.0)
        if 'until' in cue:
            h2 = find_phrase(words, cue['until'], cue.get('uocc', 0))
            if not h2:
                raise SystemExit(f"sfx until-anchor not found: {cue['until']!r}")
            beds.append(dict(kind=cue['sfx'], t0=t0, t1=h2[-1][1] + cue.get('until_pad', 1.0),
                             amp=cue.get('amp', 0.1)))
        else:
            events.append(dict(kind=cue['sfx'], t=t0, amp=cue.get('amp', 0.5),
                               pan=cue.get('pan', 0.0)))
    events.sort(key=lambda e: e['t'])
    return events, beds, hushes

SLOT_MAP = {
    'R': (895, 295),
    'TR': (895, 215),
    'BR': (895, 385),
    'L': (385, 285),
    'C': (640, 295),
}
SLOT_CYCLE = ['R', 'TR', 'C', 'BR', 'R']

def _word_times(b, n):
    if n == len(b['wtimes']):
        return list(b['wtimes'])
    if n <= 1:
        return [b['t0']] * n
    span = max(0.25, b['t1'] - b['t0'])
    return [b['t0'] + span * i / (n - 1) for i in range(n)]

def _flash_ring(layer, t, t0, cx, cy):
    dt = t - t0
    if dt < 0 or dt > 0.48:
        return
    e = clamp01(dt / 0.48)
    r = 44 + 100 * ease_out_expo(e)
    a = int(145 * (1.0 - e))
    if a <= 2:
        return
    ring = Image.new('L', (int(r * 2) + 8, int(r * 2) + 8), 0)
    ImageDraw.Draw(ring).ellipse([0, 0, ring.width - 1, ring.height - 1], fill=a)
    ImageDraw.Draw(ring).ellipse([10, 10, ring.width - 11, ring.height - 11], fill=0)
    ring = ring.filter(ImageFilter.GaussianBlur(2))
    col = Image.new('RGBA', ring.size, YELLOW + (255,))
    col.putalpha(ring)
    layer.alpha_composite(col, (int(cx - ring.width / 2), int(cy - ring.height / 2)))

def _beat_envelope(b, t, pre=0.22, fade_out=0.32):
    t0, end_t = b['t0'], b['end_t']
    if t < t0 - pre or t > end_t + fade_out:
        return 0.0, 0.0
    ea = ease_out_expo(clamp01((t - (t0 - pre)) / 0.36))
    out_a = 1.0 if t <= end_t else 1.0 - ease_in_out_sine((t - end_t) / fade_out)
    return ea, out_a

def beat_count(layer, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t)
    if ea * out_a <= 0.01:
        return
    t0 = b['t0']
    dur = min(b.get('dur', 1.25), max(0.45, b['end_t'] - t0))
    local = clamp01((t - t0) / dur)
    if 'txt' in b:
        shown = b['txt']
        pop = 0.92 + 0.08 * ease_out_back(clamp01((t - (t0 - 0.1)) / 0.38))
    else:
        val = b.get('num', 0) * ease_out_expo(local)
        shown = f"{b.get('pre', '')}{val:,.{b.get('dec', 0)}f}{b.get('suf', '')}"
        pop = 0.92 + 0.08 * ease_out_back(clamp01((t - (t0 - 0.1)) / 0.35))

    fnum = fnt('Black', 92 if b.get('big', True) else 72)
    fnote = fnt('Bold', 21)
    d = ImageDraw.Draw(layer)
    wnum = d.textlength(shown, font=fnum)
    label = b.get('label', '')
    wlab = tracked_width(d, label, fnote, 3.0) if label else 0
    panel_w = int(max(wnum + 88, wlab + 88, 320))
    panel_h = 192 if label else 148
    px = int(cx - panel_w / 2)
    py = int(cy - panel_h / 2 - (1.0 - out_a) * 18)

    layer.alpha_composite(card_alpha(glass_card(panel_w, panel_h, radius=22), ea * out_a), (px, py))
    # Top accent bar + progress meter inside card
    d.rectangle([px + 28, py + 16, px + 28 + int((panel_w - 56) * ease_out_expo(local)), py + 21],
                fill=YELLOW + (int(240 * ea * out_a),))

    im = Image.new('RGBA', (int(wnum) + 28, 122), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((14, 6), shown, font=fnum, fill=WHITE + (255,))
    if abs(pop - 1.0) > 0.01:
        nw, nh = max(2, int(im.width * pop)), max(2, int(im.height * pop))
        im = im.resize((nw, nh), Image.BICUBIC)
    im.putalpha(im.getchannel('A').point(lambda v: int(v * ea * out_a)))
    layer.alpha_composite(im, (int(cx - im.width / 2), int(py + 26)))

    if label:
        la = clamp01((t - (t0 + 0.15)) / 0.42) * ea * out_a
        if la > 0.02:
            draw_tracked(d, label, fnote, cx - wlab / 2, py + panel_h - 44,
                         ICE + (int(245 * la),), 3.0)
    _flash_ring(layer, t, t0 + dur * 0.85, cx, cy)

def beat_phrase(layer, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.24)
    if ea * out_a <= 0.01:
        return
    t0, t1 = b['t0'], b['t1']
    disp = b['words']
    ts = _word_times(b, len(disp))
    f = fnt('Black', b.get('size', 40))
    tr = 6.0
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(w, font=f) + tr for w in disp]
    total = sum(widths) - tr
    if total > 560:
        f = fnt('Black', 32)
        widths = [d.textlength(w, font=f) + tr for w in disp]
        total = sum(widths) - tr

    pw = int(total + 76)
    ph = 114
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 18)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), ea * out_a), (px, py))

    x0 = cx - total / 2.0
    x = x0
    top_y = py + 24
    hi = b.get('hi', -1)
    for i, (w, wt) in enumerate(zip(disp, ts)):
        local = clamp01((t - (wt - 0.18)) / 0.38)
        if local > 0:
            e = ease_out_expo(local)
            a = int(255 * min(1.0, local * 1.9) * out_a)
            col = YELLOW if i == hi else WHITE
            yy = top_y + (1.0 - e) * 24
            d.text((x, yy), w, font=f, fill=col + (a,))
        x += widths[i]

    prog = clamp01((t - (t0 - 0.08)) / max(0.35, t1 - t0 + 0.25))
    if prog > 0:
        uw = total * ease_out_expo(prog)
        d.rectangle([x0, py + ph - 22, x0 + uw, py + ph - 17],
                    fill=YELLOW + (int(235 * ea * out_a),))

def beat_quote(layer, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.30)
    if ea * out_a <= 0.01:
        return
    t0, t1 = b['t0'], b['t1']
    disp = b['words']
    ts = _word_times(b, len(disp))
    fq = fnt('Bold', 34 if len(disp) > 6 else 40)
    fmark = fnt('Black', 110)
    fat = fnt('SemiBold', 18)
    d = ImageDraw.Draw(layer)

    mid = (len(disp) + 1) // 2
    lines = [disp[:mid], disp[mid:]]
    lts = [ts[:mid], ts[mid:]]
    line_w = [sum(d.textlength(w, font=fq) + 9 for w in lw) - 9 for lw in lines if lw]
    pw = int(min(W - 140, max(line_w) + 160))
    ph = 205 if len(lines) > 1 and lines[1] else 150
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 18)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=22), ea * out_a), (px, py))

    ma = int(240 * ea * out_a)
    d.text((px + 22, py + 12), '\u201c', font=fmark, fill=YELLOW + (ma,))
    for li, (lw, lt) in enumerate(zip(lines, lts)):
        widths = [d.textlength(w, font=fq) + 9 for w in lw]
        total = sum(widths) - 9
        x = cx - total / 2.0 + 18
        y = py + 36 + li * 48
        for i, (w, wt) in enumerate(zip(lw, lt)):
            local = clamp01((t - (wt - 0.18)) / 0.42)
            if local > 0:
                e = ease_out_expo(local)
                a = int(255 * min(1.0, local * 1.9) * out_a)
                yy = y + (1.0 - e) * 20
                d.text((x, yy), w, font=fq, fill=WHITE + (a,))
            x += widths[i]

    if b.get('attrib'):
        la = clamp01((t - (t0 + 0.25)) / 0.48) * ea * out_a
        if la > 0.02:
            aw = tracked_width(d, b['attrib'], fat, 2.2)
            draw_tracked(d, b['attrib'], fat, cx - aw / 2, py + ph - 36,
                         YELLOW + (int(240 * la),), 2.2)

def beat_date(layer, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.24)
    if ea * out_a <= 0.01:
        return
    t0 = b['t0']
    fm = fnt('Black', 46)
    fs = fnt('Bold', 19)
    d = ImageDraw.Draw(layer)
    wm = tracked_width(d, b['main'], fm, 2.8)
    ws = tracked_width(d, b.get('sub', ''), fs, 3.0) if b.get('sub') else 0
    pw, ph = int(max(wm, ws) + 86), 132
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 18)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), ea * out_a), (px, py))

    # Yellow corner brackets
    bl = int(22 * ea)
    ba = int(235 * ea * out_a)
    for bx, by, dx, dy in ((px + 8, py + 8, 1, 1), (px + pw - 9, py + 8, -1, 1),
                           (px + 8, py + ph - 9, 1, -1), (px + pw - 9, py + ph - 9, -1, -1)):
        x_a, x_b = sorted([bx, bx + bl * dx])
        y_a, y_b = sorted([by, by + bl * dy])
        d.rectangle([x_a, by, x_b, by + 3], fill=YELLOW + (ba,))
        d.rectangle([bx, y_a, bx + 3, y_b], fill=YELLOW + (ba,))

    kinetic_line(layer, b['main'], fm, cx, py + 22, t, t0 - 0.18, WHITE, 2.8,
                 stagger=0.03, dur=0.42, slide=22, out_a=ea * out_a)
    if b.get('sub'):
        la = clamp01((t - (t0 + 0.18)) / 0.42) * ea * out_a
        if la > 0.02:
            draw_tracked(d, b['sub'], fs, cx - ws / 2, py + 84,
                         ICE + (int(240 * la),), 3.0)

def beat_tease(layer, b, t, cx, cy):
    """Retention device: 'AHEAD — …' chip, top-center, slides in and out."""
    t0 = b['t0']
    if t < t0 or t > t0 + 3.0:
        return
    ea = ease_out_expo(clamp01((t - t0) / 0.5))
    out_a = 1.0 - clamp01((t - (t0 + 2.3)) / 0.5)
    dy = (1 - ea) * -46
    ftag = fnt('Bold', 19)
    ftxt = fnt('SemiBold', 30)
    d = ImageDraw.Draw(layer)
    wtag = tracked_width(d, 'AHEAD', ftag, 4.0)
    wtxt = tracked_width(d, b['text'], ftxt, 2.5)
    pw = int(wtag + wtxt + 86)
    ph = 64
    px = int(W / 2 - pw / 2)
    py = int(52 + dy)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=14), ea * out_a), (px, py))
    a = int(255 * out_a)
    d.text((px + 28, py + 21), 'AHEAD', font=ftag, fill=YELLOW + (a,))
    d.text((px + 28 + wtag + 26, py + 15), b['text'], font=ftxt, fill=WHITE + (a,))

BEAT_KINDS = {'count': beat_count, 'phrase': beat_phrase, 'quote': beat_quote,
              'date': beat_date, 'tease': beat_tease}

def beats_layer(beats, t, expire_t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for i, b in enumerate(beats):
        if b['t0'] > expire_t:
            continue
        slot_key = b.get('slot', SLOT_CYCLE[i % len(SLOT_CYCLE)])
        cx, cy = SLOT_MAP[slot_key]
        BEAT_KINDS[b['kind']](layer, b, t, cx, cy)
    return layer

# --------------------------------------------------------- ambient layer ----
DUST = [((i * 149.3) % W, (i * 83.7) % H, 0.15 + (i % 5) * 0.04, 4 + (i % 3) * 2)
        for i in range(18)]

def ambient_layer(t):
    """Subtle floating dust particles & soft cinema light sweep."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x0, y0, sp, sz in DUST:
        x = int((x0 + t * sp * 22) % W)
        y = int((y0 - t * sp * 30) % H)
        d.ellipse([x, y, x + sz, y + sz], fill=(175, 215, 255, 28))
    return layer

# ------------------------------------------------------------------ scripts ----
SCRIPTS = {
    'johnstown': dict(
        title=('THE CANAL THAT BROKE A CITY', 'CONEMAUGH VALLEY, PA \u00B7 MAY 31, 1889'),
        end=('SUBSCRIBE', 'Full-length historical documentaries \u00B7 new episodes weekly'),
        voices=('voice1.mp3', 'voice2.mp3', 'voice3.mp3'),
        out='deep-dive-johnstown.mp4',
        scenes=[
            dict(a='', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg',
                 kicker='LAKE CONEMAUGH \u00B7 MAY 31, 1889',
                 sub='14 MILES ABOVE JOHNSTOWN, PENNSYLVANIA',
                 cam='push_in', focus=(0.52, 0.48)),
            dict(a='artificial lake is rising', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg',
                 kicker='20,000,000 TONS OF FORCE',
                 sub='HELD BACK BY AN AGING EARTHEN EMBANKMENT',
                 cam='pan_right', focus=(0.60, 0.55), viz='pressure_gauge'),
            dict(a='story of the johnstown flood', img='south-fork-fishing-and-hunting-club-club-3.jpg',
                 kicker='A FISHING CLUB\u2019S PLAYGROUND',
                 sub='SOUTH FORK FISHING AND HUNTING CLUB',
                 cam='push_in', focus=(0.50, 0.45)),
            dict(a='built in eighteen fifty two', img='pennsylvania-main-line-canal-1850s-histo-2.jpg',
                 kicker='BUILT IN 1852 FOR A CANAL',
                 sub='MADE OBSOLETE BY THE PENNSYLVANIA RAILROAD',
                 cam='pan_left', focus=(0.48, 0.48)),
            dict(a='sold for just two thousand', img='south-fork-fishing-and-hunting-club-club-1.jpg',
                 kicker='BOUGHT FOR $2,000 IN 1879',
                 sub='PRIVATE MOUNTAIN RETREAT OF PITTSBURGH BARONS',
                 cam='push_in', focus=(0.50, 0.48)),
            dict(a='discharge pipes were fitted', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg',
                 kicker='THE FATAL MODIFICATIONS',
                 sub='CULVERT SCREENS \u00B7 CHOKED SPILLWAY \u00B7 LOWERED CREST',
                 cam='pan_left', focus=(0.45, 0.52), viz='dam_anatomy'),
            dict(a='six to eight inches', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg',
                 kicker='6\u20138 INCHES OF RAIN IN 24 HOURS',
                 sub='THE RESERVOIR HAS NOWHERE LEFT TO GO',
                 cam='pull_out', focus=(0.50, 0.45), viz='rain_rising'),
            dict(a='three in the often', img='south-fork-dam-lake-conemaugh-johnstown--4.jpg',
                 kicker='3:10 PM \u00B7 THE SOUTH FORK DAM FAILS',
                 sub='20 MILLION TONS DROP 14 MILES IN 57 MINUTES',
                 cam='push_in', focus=(0.58, 0.52), viz='valley_drop'),
            dict(a='thirty six feet high', img='johnstown-train-clean.jpg',
                 kicker='A 36-FOOT WALL OF WATER',
                 sub='33 LOCOMOTIVES & 10M LBS OF DEBRIS SWEPT AWAY',
                 cam='pan_right', focus=(0.55, 0.50), viz='wave_scale'),
            dict(a='fires burned across', img='johnstown-flood-1889-ruins-destruction-h-1.jpg',
                 kicker='THE STONE BRIDGE INFERNO',
                 sub='62 ACRES OF WRECKAGE BURNED FOR THREE DAYS',
                 cam='push_in', focus=(0.45, 0.52), warm=0.22),
            dict(a='two thousand two hundred', img='south-fork-dam-lake-conemaugh-johnstown--1.jpg',
                 kicker='2,209 LIVES LOST',
                 sub='ENTIRE FAMILIES LOST \u00B7 HUNDREDS NEVER IDENTIFIED',
                 cam='pull_out', focus=(0.50, 0.46)),
            dict(a='claro boston', img='south-fork-dam-lake-conemaugh-johnstown--2.jpg',
                 kicker='CLARA BARTON & THE RED CROSS',
                 sub='FIRST MAJOR PEACETIME DISASTER RELIEF \u00B7 5 MONTHS',
                 cam='pan_left', focus=(0.50, 0.50)),
            dict(a='never held responsible', img='johnstown-flood-1889-ruins-destruction-h-3.jpg',
                 kicker='THE VERDICT: \u201cAN ACT OF GOD\u201d',
                 sub='ZERO LIABILITY FOR THE SOUTH FORK CLUB MEMBERS',
                 cam='push_in', focus=(0.50, 0.45), focus_side=-0.5),
        ],
        sfx_cues=[
            dict(sfx='water', a=None, until='six to eight inches', amp=0.10),
            dict(sfx='rumble', a='six to eight inches', delay=1.3, amp=0.30),
            dict(sfx='rain', a='six to eight inches', until='twenty million pounds of water',
                 amp=0.13, until_pad=0.4),
            dict(hush=dict(a='twenty million pounds of water', lead=0.55, dur=1.15, depth=0.85)),
            dict(sfx='crash', a='twenty million pounds of water', delay=0.05, amp=0.72),
            dict(sfx='subdrop', a='twenty million pounds of water', delay=0.05, amp=0.68),
            dict(sfx='water_rush', a='twenty million pounds of water', until='fires burned across',
                 amp=0.16),
            dict(sfx='crash', a='thirty six feet high', delay=0.12, amp=0.42),
            dict(sfx='thud', a='ten million pounds of debris', delay=0.18, amp=0.42),
            dict(sfx='fire', a='fires burned across', until='claro boston', amp=0.13),
            dict(hush=dict(a='two thousand two hundred', lead=0.45, dur=1.35, depth=0.90)),
            dict(sfx='thud', a='two thousand two hundred', delay=0.42, amp=0.5),
            dict(sfx='shimmer', a='five months', delay=0.10, amp=0.22, pan=0.25),
            dict(sfx='boom', a='act of god', delay=0.05, amp=0.46),
        ],
        beats=[
            dict(a='twenty million pounds of force', kind='count', num=20, suf='M',
                 label='TONS OF FORCE BEHIND THE DAM', dur=1.4, slot='R'),
            dict(a='into a weapon', kind='phrase', words=['INTO', 'A', 'WEAPON'], hi=2, slot='C'),
            dict(a='eighteen fifty two', kind='date', main='1852',
                 sub='BUILT FOR THE PA MAIN LINE CANAL', slot='R'),
            dict(a='two thousand dollars', kind='count', num=2000, pre='$',
                 label='PAID BY PITTSBURGH INDUSTRIALISTS', dur=1.3, slot='R'),
            dict(a='game fish', kind='phrase', words=['BLOCKED', 'FOR', 'GAME', 'FISH'], hi=2, slot='R'),
            dict(a='crest was lowered', kind='phrase',
                 words=['CREST', 'LOWERED', 'FOR', 'A', 'ROAD'], hi=1, slot='R'),
            dict(a='six to eight inches', kind='count', txt='6\u20138 IN',
                 label='OF RAIN IN 24 HOURS', dur=1.0, slot='R'),
            dict(a='twenty million pounds of water', kind='count', num=20, suf='M',
                 label='TONS OF WATER UNLEASHED', dur=1.4, slot='R'),
            dict(a='thirty six feet high', kind='count', txt='36 FT',
                 label='WALL OF WATER & TIMBER', dur=1.0, slot='R'),
            dict(a='ten million pounds of debris', kind='count', num=10, suf='M',
                 label='POUNDS OF CRUSHING DEBRIS', dur=1.2, slot='R'),
            dict(a='sixty two acres', kind='count', num=62,
                 label='ACRES BURNED FOR 3 DAYS', dur=1.0, slot='R'),
            dict(a='two thousand two hundred', kind='count', num=2209,
                 label='PEOPLE KILLED IN JOHNSTOWN', dur=1.6, big=True, slot='C'),
            dict(a='five months', kind='date', main='5 MONTHS',
                 sub='CLARA BARTON & AMERICAN RED CROSS', slot='R'),
            dict(a='act of god', kind='quote', words=['AN', 'ACT', 'OF', 'GOD'],
                 attrib='\u2014 COURT RULING \u00B7 $0 PAID BY THE CLUB', slot='R'),
            dict(a='fail by decisions', kind='phrase',
                 words=['DAMS', 'FAIL', 'BY', 'DECISIONS'], hi=3, slot='C'),
        ],
        captions=[
            (0, 12, 'May 31st, 1889 \u2014 above the valley of Conemaugh,'),
            (13, 22, 'an artificial lake is rising: 20 million tons of force'),
            (23, 38, 'held back by an earthen dam rotting in plain sight.'),
            (39, 46, 'This is the story of the Johnstown Flood,'),
            (47, 60, 'and the decisions that turned a club into a weapon.'),
            (61, 70, 'The South Fork Dam was built in 1852'),
            (71, 82, 'to feed a canal the railroad soon made obsolete \u2014'),
            (83, 95, 'sold for $2,000 to wealthy Pittsburgh industrialists'),
            (96, 103, 'who wanted a private lake in the mountains.'),
            (104, 109, 'Their so-called improvements made everything worse.'),
            (110, 124, 'Drain pipes were screened so game fish couldn\u2019t escape.'),
            (125, 139, 'The spillway choked; the crest lowered to widen the road.'),
            (140, 151, 'When 6 to 8 inches of rain fell in 24 hours,'),
            (152, 158, 'the lake had nowhere left to go.'),
            (159, 171, 'At 3:10 in the afternoon, the South Fork Dam gave way.'),
            (172, 182, '20 million tons of water dropped 14 miles down the valley,'),
            (183, 193, 'reaching Johnstown in under an hour.'),
            (194, 201, 'A wall of water 36 feet high'),
            (202, 213, 'carried locomotives, houses, and 10M lbs of debris.'),
            (214, 230, 'Where water stopped, fires burned 62 acres for 3 days.'),
            (231, 244, '2,209 people were dead \u2014 many never identified.'),
            (245, 256, 'Clara Barton and the Red Cross stayed five months.'),
            (257, 270, 'The club was never held liable: called an Act of God.'),
            (271, 280, 'Dams don\u2019t fail by accident \u2014 they fail by decisions.'),
            (281, 293, 'Subscribe \u2014 the full story of the canal is coming.'),
        ],
    ),
    'enron': dict(
        title=('HOW ENRON DIED', 'HOUSTON, TEXAS \u00B7 DECEMBER 2, 2001'),
        end=('SUBSCRIBE', 'Money, Explained \u2014 investigative financial documentaries'),
        voices=('enron1.mp3', 'enron2.mp3', 'enron3.mp3'),
        out='deep-dive-enron.mp4',
        scenes=[
            dict(a='', img='enron-corporation-headquarters-houston-c-4.jpg',
                 kicker='WINTER 2001 \u00B7 HOUSTON, TEXAS',
                 sub='AMERICA\u2019S MOST INNOVATIVE COMPANY UNRAVELS',
                 cam='tilt_up', focus=(0.50, 0.45)),
            dict(a='enron and energy trading', img='enron-corporation-headquarters-houston-c-3.jpg',
                 kicker='AN EMPIRE BUILT ON PAPER',
                 sub='1400 SMITH STREET \u00B7 ENRON CORP HEADQUARTERS',
                 cam='push_in', focus=(0.50, 0.45), focus_side=-0.45),
            dict(a='humble gas pipeline', img='natural-gas-pipeline-construction-texas--1.jpg',
                 kicker='1985 \u00B7 THE PIPELINE ORIGINS',
                 sub='STARTED AS A HUMBLE TEXAS GAS TRANSMISSION FIRM',
                 cam='pan_right', focus=(0.52, 0.52)),
            dict(a='jeff skilling arrived', img='enron-corporation-headquarters-houston-c-5.jpg',
                 kicker='JEFF SKILLING\u2019S IDEA',
                 sub='\u201cSTOP OWNING THINGS \u2014 START TRADING THEM\u201d',
                 cam='push_in', focus=(0.52, 0.48)),
            dict(a='mom to market accounting', img='enron-corporation-headquarters-houston-c-5.jpg',
                 kicker='MARK-TO-MARKET ACCOUNTING',
                 sub='10 YEARS OF FUTURE PROFIT BOOKED ON DAY ONE',
                 cam='pan_left', focus=(0.45, 0.50), viz='mtm_ledger'),
            dict(a='ninety dollars', img='enron-bankruptcy-newspaper-headline-2001-3.jpg',
                 kicker='PEAK VALUATION: $70 BILLION',
                 sub='NYSE: ENE SOARS PAST $90 A SHARE IN AUGUST 2000',
                 cam='push_in', focus=(0.52, 0.46), viz='stock_boom'),
            dict(a='fortune magazine named', img='enron-corporation-headquarters-houston-c-4.jpg',
                 kicker='FORTUNE\u2019S DARLING \u00B7 6 YEARS RUNNING',
                 sub='NAMED \u201cMOST INNOVATIVE COMPANY\u201d 1996\u20132001',
                 cam='pull_out', focus=(0.50, 0.45)),
            dict(a='profits were fiction', img='andrew-fastow-enron-cfo-trial-photo-2.jpg',
                 kicker='CFO ANDREW FASTOW',
                 sub='ARCHITECT OF THE OFF-BALANCE-SHEET ILLUSION',
                 cam='push_in', focus=(0.46, 0.42)),
            dict(a='show partnerships', img='enron-bankruptcy-newspaper-headline-2001-1.jpg',
                 kicker='LJM \u00B7 RAPTOR \u00B7 CHEWCO',
                 sub='A MAZE OF SHELL ENTITIES HIDING $30B+ IN DEBT',
                 cam='push_in', focus=(0.50, 0.48), focus_side=0.48, viz='shell_maze'),
            dict(a='fortune report about', img='enron-corporation-headquarters-houston-c-3.jpg',
                 kicker='MARCH 2001 \u00B7 BETHANY McLEAN',
                 sub='FORTUNE ASKS ONE QUESTION: \u201cIS ENRON OVERPRICED?\u201d',
                 cam='pan_right', focus=(0.50, 0.45), focus_side=-0.45),
            dict(a='shredding documents', img='andrew-fastow-enron-cfo-trial-photo-1.jpg',
                 kicker='ARTHUR ANDERSEN DESTROYS EVIDENCE',
                 sub='AUDITORS SHRED TONNES OF ENRON WORKPAPERS',
                 cam='push_in', focus=(0.48, 0.42), focus_side=-0.45),
            dict(a='august two thousand', img='enron-scandal-2001-newspaper-headlines-f-5.jpg',
                 kicker='AUGUST 14, 2001 \u00B7 SKILLING QUITS',
                 sub='CEO RESIGNS AFTER JUST SIX MONTHS AT THE HELM',
                 cam='push_in', focus=(0.48, 0.42)),
            dict(a='telling employees to buy', img='enron-scandal-2001-newspaper-headlines-f-1.jpg',
                 kicker='THE INSIDER BETRAYAL',
                 sub='KEN LAY URGES STAFF TO BUY WHILE EXECUTIVES SELL',
                 cam='push_in', focus=(0.48, 0.42), focus_side=0.48, viz='insider_split'),
            dict(a='december second two thousand', img='enron-corporation-headquarters-houston-c-2.jpg',
                 kicker='DECEMBER 2, 2001 \u00B7 CHAPTER 11',
                 sub='$63.4 BILLION IN ASSETS \u2014 LARGEST U.S. BANKRUPTCY',
                 cam='pull_out', focus=(0.48, 0.50), viz='stock_crash'),
            dict(a='twenty thousand employees', img='enron-corporation-headquarters-houston-c-1.jpg',
                 kicker='20,000 JOBS & PENSIONS WIPED OUT',
                 sub='ARTHUR ANDERSEN (85,000 STAFF) COLLAPSES TOO',
                 cam='pan_right', focus=(0.52, 0.48)),
            dict(a='skilling went to prison', img='jeff-skilling-ken-lay-enron-trial-courtr-2.jpg',
                 kicker='THE RECKONING IN FEDERAL COURT',
                 sub='FASTOW & SKILLING IMPRISONED \u00B7 LAY CONVICTED',
                 cam='push_in', focus=(0.48, 0.42)),
        ],
        sfx_cues=[
            dict(sfx='city', a=None, until='mom to market accounting', amp=0.08),
            dict(sfx='ticker', a='mom to market accounting', until='ninety dollars', amp=0.07),
            dict(sfx='shimmer', a='ninety dollars', delay=1.15, amp=0.20, pan=-0.25),
            dict(sfx='shimmer', a='seventy billion dollars', delay=1.70, amp=0.28, pan=0.25),
            dict(sfx='unease', a='profits were fiction', until='enron overpriced', amp=0.12),
            dict(sfx='paper', a='fast the bills', until='hide billions in debt', amp=0.09),
            dict(hush=dict(a='enron overpriced', lead=0.50, dur=1.20, depth=0.88)),
            dict(sfx='thud', a='enron overpriced', delay=0.22, amp=0.38),
            dict(sfx='shredder', a='shredding documents', until='august two thousand', amp=0.13),
            dict(sfx='whoosh_down', a='skilling resigned', delay=0.05, amp=0.42, pan=-0.30),
            dict(hush=dict(a='december second two thousand', lead=0.55, dur=1.50, depth=0.90)),
            dict(sfx='boom', a='december second two thousand', delay=0.30, amp=0.72),
            dict(sfx='subdrop', a='december second two thousand', delay=0.30, amp=0.68),
            dict(sfx='crash', a='sixty three billion dollars', delay=2.05, amp=0.46),
            dict(sfx='thud', a='twenty thousand employees', delay=1.85, amp=0.42),
            dict(sfx='thud', a='eighty five thousand people', delay=1.85, amp=0.42),
            dict(sfx='thud', a='skilling went to prison', delay=0.15, amp=0.38),
            dict(sfx='thud', a='died before sentencing', delay=0.15, amp=0.34),
            dict(hush=dict(a='a company cannot explain how it makes money it is not making money',
                           lead=0.50, dur=1.40, depth=0.85)),
            dict(sfx='shimmer', a='a company cannot explain how it makes money it is not making money',
                 delay=2.30, amp=0.24, pan=0.20),
        ],
        beats=[
            dict(a='smartest guys in the room', kind='quote',
                 words=['SMARTEST', 'GUYS', 'IN', 'THE', 'ROOM'],
                 attrib='\u2014 ENRON\u2019S OWN SLOGAN', slot='R'),
            dict(a='humble gas pipeline', kind='phrase',
                 words=['HUMBLE', 'GAS', 'PIPELINE'], hi=2, slot='R'),
            dict(a='jeff skilling arrived', kind='date', main='JEFF SKILLING',
                 sub='STOP OWNING \u00B7 START TRADING', slot='R'),
            dict(a='mom to market accounting', kind='phrase',
                 words=['MARK-TO-MARKET', 'ACCOUNTING'], hi=0, size=36, slot='R'),
            dict(a='ninety dollars', kind='count', num=90.75, dec=2, pre='$',
                 label='PEAK SHARE PRICE (AUG 2000)', dur=1.0, slot='R'),
            dict(a='seventy billion dollars', kind='count', num=70, pre='$', suf='B',
                 label='PEAK MARKET VALUATION', dur=1.4, slot='R'),
            dict(a='six years in a row', kind='phrase',
                 words=['6', 'YEARS', 'IN', 'A', 'ROW'], hi=0, slot='C'),
            dict(a='profits were fiction', kind='phrase',
                 words=['THE', 'PROFITS', 'WERE', 'FICTION'], hi=3, slot='R'),
            dict(a='fast the bills', kind='date', main='ANDREW FASTOW',
                 sub='CHIEF FINANCIAL OFFICER', slot='R'),
            dict(a='j m wrapped up', kind='phrase',
                 words=['LJM', '\u00B7', 'RAPTOR', '\u00B7', 'CHEWCO'], hi=0, slot='R'),
            dict(a='hide billions in debt', kind='phrase',
                 words=['HIDING', 'BILLIONS', 'IN', 'DEBT'], hi=1, slot='R'),
            dict(a='enron overpriced', kind='quote', hold=3.6,
                 words=['IS', 'ENRON', 'OVERPRICED?'],
                 attrib='\u2014 BETHANY McLEAN, FORTUNE (MAR 2001)', slot='R'),
            dict(a='shredding documents', kind='phrase',
                 words=['SHREDDING', 'DOCUMENTS'], hi=0, slot='R'),
            dict(a='august two thousand', kind='date', main='AUGUST 2001',
                 sub='SKILLING QUITS AFTER 6 MONTHS', slot='R'),
            dict(a='while he sold', kind='phrase',
                 words=['SOLD', 'WHILE', 'STAFF', 'BOUGHT'], hi=0, slot='L'),
            dict(a='fake all alone', kind='phrase',
                 words=['FAKE', 'ALL', 'ALONG'], hi=0, slot='L'),
            dict(a='december second two thousand', kind='date', main='DEC 2, 2001',
                 sub='CHAPTER 11 BANKRUPTCY FILED', slot='R'),
            dict(a='sixty three billion dollars', kind='count', num=63.4, pre='$',
                 suf='B', dec=1, label='IN ASSETS \u2014 LARGEST U.S. FILING', dur=1.5, slot='R'),
            dict(a='twenty thousand employees', kind='count', num=20000,
                 label='ENRON EMPLOYEES LAID OFF', dur=1.4, slot='R'),
            dict(a='their pensions', kind='phrase',
                 words=['$2.1B', 'IN', 'PENSIONS', 'GONE'], hi=0, slot='R'),
            dict(a='eighty five thousand people', kind='count', num=85000,
                 label='ARTHUR ANDERSEN STAFF DISSOLVED', dur=1.4, slot='R'),
            dict(a='skilling went to prison', kind='phrase',
                 words=['SKILLING:', '24-YEAR', 'SENTENCE'], hi=1, slot='R'),
            dict(a='died before sentencing', kind='phrase',
                 words=['CONVICTED', 'ON', '10', 'COUNTS'], hi=0, slot='R'),
            dict(a='smartest guys in the room', occ=1, kind='phrase',
                 words=['THE', 'SMARTEST', 'GUYS', 'IN', 'THE', 'ROOM'], hi=1, size=34, slot='C'),
            dict(a='a company cannot explain how it makes money it is not making money',
                 kind='quote',
                 words=['IF', 'IT', 'CANNOT', 'EXPLAIN', 'HOW', 'IT', 'MAKES',
                        'MONEY,', 'IT\u2019S', 'NOT', 'MAKING', 'MONEY.'],
                 attrib='\u2014 THE LESSON THAT OUTLIVED ENRON', slot='C'),
        ],
        captions=[
            (0, 11, 'In the winter of 2001, America\u2019s most innovative company'),
            (12, 19, 'was revealed to be its greatest fraud.'),
            (20, 27, 'Enron: an energy trading empire built on paper,'),
            (28, 35, 'run by the smartest guys in the room.'),
            (36, 45, 'It began as a humble gas pipeline company in Houston.'),
            (46, 52, 'Then Jeff Skilling arrived with an idea:'),
            (53, 59, 'stop owning things and start trading them.'),
            (60, 69, 'Mark-to-market accounting booked a decade of profits'),
            (70, 76, 'on the very day a deal was signed.'),
            (77, 82, 'The stock soared past $90 a share.'),
            (83, 89, 'The market value passed $70 billion.'),
            (90, 106, 'Fortune named Enron Most Innovative 6 years in a row.'),
            (107, 119, 'But the profits were fiction \u2014 off the books, CFO Andrew Fastow'),
            (120, 136, 'built shell partnerships \u2014 LJM, Raptor, Chewco \u2014 hiding debt.'),
            (137, 151, 'When Bethany McLean asked: \u201cIs Enron Overpriced?\u201d'),
            (152, 158, 'the house of cards began to shake.'),
            (159, 175, 'Auditors at Arthur Andersen shredded documents instead.'),
            (176, 191, 'In August 2001, Skilling resigned after six months as CEO.'),
            (192, 203, 'Ken Lay told employees to buy the stock while he sold.'),
            (204, 215, 'In November, Enron admitted the profits were fake all along.'),
            (216, 225, 'On December 2nd, 2001, Enron filed for bankruptcy \u2014'),
            (226, 239, '$63.4 billion in assets, the largest in U.S. history.'),
            (240, 250, '20,000 employees lost their jobs and their pensions.'),
            (251, 260, 'Arthur Andersen, 85,000 people strong, dissolved.'),
            (261, 270, 'Andrew Fastow and Jeff Skilling went to prison.'),
            (271, 278, 'Ken Lay was convicted and died before sentencing.'),
            (279, 287, 'They called themselves the smartest guys in the room.'),
            (288, 302, 'The lesson: if a company cannot explain how it makes money,'),
            (303, 312, 'it is not making money. Subscribe \u2014 this is Money, Explained.'),
        ],
    ),
}

# -------------------------------------------------------------------- main ----
def main(key):
    cfg = SCRIPTS[key]
    out = os.path.join(ROOT, 'social', cfg['out'])
    v = [os.path.join(AUDIO, n) for n in cfg['voices']]
    nar = os.path.join(AUDIO, f'narration-{key}.m4a')
    cmd = [FFMPEG, '-y', '-i', v[0], '-i', v[1], '-i', v[2],
           '-filter_complex', 'concat=n=3:v=0:a=1', '-c:a', 'aac', '-b:a', '160k', nar]
    subprocess.run(cmd, check=True, capture_output=True)
    adur = duration(nar)
    total = adur + 2.2
    n = int(total * FPS)

    words = load_words(key)
    beats = resolve_beats(key, words)
    scenes = resolve_scenes(key, words, total)
    cap_stream = build_caption_stream(key, words)
    print(f'[{key}] narration={adur:.1f}s total={total:.1f}s ({n}f) scenes={len(scenes)} beats={len(beats)}')

    # ---- sound design: semantic cue sheet keyed to spoken words ----
    cuts = [sc['t0'] for sc in scenes]
    events, beds, hushes = build_sfx_plan(key, words, beats)
    generate_score(key, total, cuts, events, beds, hushes)

    # Pre-prep unique plates once
    plate_cache = {}
    for sc in scenes:
        pkey = (sc['img'], sc.get('focus_side', 0.0), sc.get('warm', 0.0))
        if pkey not in plate_cache:
            p_path = os.path.join(IMG, sc['img'])
            if not os.path.exists(p_path):
                raise SystemExit(f'missing image {p_path}')
            plate_cache[pkey] = prep_plate(p_path, sc.get('focus_side', 0.0), sc.get('warm', 0.0))
        sc['plate'] = plate_cache[pkey]
        print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | {sc['kicker']:34s} | {sc['img']}")

    music = os.path.join(AUDIO, f'music-{key}.wav')
    sfx = os.path.join(AUDIO, f'sfx-{key}.wav')
    proc = subprocess.Popen(
        [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
         '-r', str(FPS), '-i', '-', '-i', nar, '-i', music, '-i', sfx,
         '-filter_complex',
         '[2:a]volume=0.55[m];[1:a]aformat=channel_layouts=stereo,volume=1.0[v];'
         '[3:a]volume=0.95[s];[m][v][s]amix=inputs=3:duration=longest:normalize=0,'
         'alimiter=limit=0.95[a]',
         '-map', '0:v', '-map', '[a]',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
         '-maxrate', '1800k', '-bufsize', '3600k', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    FADE = 0.42
    nscenes = len(scenes)
    expire_t = adur - 0.5
    for i in range(n):
        t = i / FPS
        # Find active scene index
        k = 0
        for idx, sc in enumerate(scenes):
            if t >= sc['t0']:
                k = idx
            else:
                break
        sc = scenes[k]
        sc_dur = max(0.5, sc['t1'] - sc['t0'])
        pos = t - sc['t0']
        p = clamp01(pos / sc_dur)

        # Whip-zoom settle on cut-in
        extra_z = 1.0 + 0.055 * (1.0 - ease_out_cubic(clamp01(pos / FADE))) if (k > 0 and pos < FADE) else 1.0
        frame = camera_frame(sc['plate'], p, sc.get('cam', 'push_in'),
                             sc.get('focus', (0.5, 0.48)), extra_zoom=extra_z)

        if k > 0 and pos < FADE:
            prev = scenes[k - 1]
            u = pos / FADE
            prev_z = 1.0 + 0.045 * ease_in_out_sine(u)
            f_prev = camera_frame(prev['plate'], 1.0, prev.get('cam', 'push_in'),
                                  prev.get('focus', (0.5, 0.48)), extra_zoom=prev_z)
            frame = optical_flare_transition(f_prev, frame, u)

        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov.alpha_composite(ambient_layer(t))
        ov.alpha_composite(viz_layer(sc.get('viz'), pos, sc_dur))
        ov.alpha_composite(beats_layer(beats, t, expire_t))
        if t < 4.3:
            cold_open_overlay(ov, cfg['title'], t, dur=4.3)
        ov.alpha_composite(hud_chapter_layer(sc['kicker'], sc.get('sub', ''),
                                             k + 1, nscenes, pos, sc_dur, t / total))
        ov.alpha_composite(caption_ribbon_layer(cap_stream, t))

        frame = Image.alpha_composite(frame.convert('RGBA'), ov).convert('RGB')
        if t >= adur - 0.4:
            frame = end_card_overlay(frame, cfg['end'], t - (adur - 0.4), total - (adur - 0.4))

        proc.stdin.write(frame.tobytes())
        if i % 360 == 0:
            print(f'  frame {i}/{n}', flush=True)

    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit('encode failed')
    print('done', out, os.path.getsize(out) // 1024, 'KB')

if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'johnstown'
    if arg not in SCRIPTS:
        raise SystemExit(f'unknown script {arg!r} \u2014 choose from {sorted(SCRIPTS)}')
    main(arg)
