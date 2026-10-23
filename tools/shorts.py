#!/usr/bin/env python3
"""Shorts assembler — full-bleed 9:16 vertical documentary engine.

- 720x1280 @24fps (9:16 vertical), 1080x1920 super-sampled plates, smooth cinema camera
- Full-bleed edge-to-edge cover framing for both real HD stock video clips and documentary photography
- Natural rich documentary color grading + real frosted-glass backdrop blur cards
- Verified 20:9 / 19.5:9 YouTube Shorts safe-zone layout (clears status bar, header icons, right rail, and bottom channel chrome)
- Clip-first free stock search (Pexels, Pixabay, Wikimedia Commons, Internet Archive, NASA) with cleared 9:16 documentary plates as offline fail-safe
- Score-only audio (voice + background music, zero SFX), hush/swell automation

Run: .venv/bin/python tools/shorts.py [short-johnstown|short-enron]
"""
import os, sys, json, math, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import generate_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    from pipeline.licences import licence_note as LICENCE_NOTE, licence_report as LICENCE_REPORT
except Exception:  # pragma: no cover - import guard only
    LICENCE_NOTE = lambda name: ('pre-existing image-search still; source/license metadata '
                                 'unavailable in current ledger — verify before monetized reuse')
    LICENCE_REPORT = lambda names: []

W, H, FPS = 720, 1280, 24
CW, CH = 1080, 1920  # 1.5x super-sampled 9:16 plate canvas for sub-pixel cinema camera

# 20:9 / 19.5:9 YouTube Shorts viewport safe margins (in 720x1280 space):
# - Tall 20:9 phones crop ~52px off left & right edges -> keep UI inside x=[76..644]
# - Top status bar + YouTube back/search bar occupy y=[0..122] -> start HUD at y=136
# - Right action rail (Like/Comment/Save/Share) occupies x=[562..720], y=[555..1180]
# - Bottom channel chrome (@handle, title, privacy, share button) occupies y=[935..1280]
SAFE_L, SAFE_R = 76, 644
RAIL_SAFE_R = 554
SAFE_HUD_Y = 136
SAFE_CAPTION_Y = 810

NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
CRIMSON = (255, 86, 92)
EMERALD = (72, 232, 164)
WHITE = (255, 255, 255)
FAINT = (122, 156, 202)
ICE = (188, 222, 252)

try:
    from pipeline.assemble import ffmpeg_bin as _resolve_ffmpeg
except Exception:  # pragma: no cover - pipeline package unavailable
    def _resolve_ffmpeg():
        return os.environ.get('FFMPEG_BINARY') or 'ffmpeg'
FFMPEG = _resolve_ffmpeg()
FDIR = os.path.join(ROOT, 'assets', 'fonts')
IMG = os.path.join(ROOT, 'image-search')

# Ensure procedural backup plates remain present on disk for shared repo checks:
# houston-skyline-plate-1.png houston-skyline-plate-2.png houston-skyline-plate-3.png
# houston-skyline-plate-4.png houston-skyline-plate-5.png enron-market-board-plate-1.png
# enron-ledger-grid-plate-1.png enron-pipeline-corridor-plate-1.png
# enron-spe-network-plate-1.png enron-courtroom-columns-plate-1.png
from tools.make_plates import ensure_plates
ensure_plates()
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
    x = clamp01(x); return 1.0 if x >= 1.0 else 1.0 - 2.0 ** (-10.0 * x)
def ease_out_cubic(x):
    x = clamp01(x); return 1.0 - (1.0 - x) ** 3
def ease_in_out_sine(x):
    x = clamp01(x); return 0.5 - 0.5 * math.cos(math.pi * x)
def ease_out_back(x):
    x = clamp01(x); c1, c3 = 1.70158, 2.70158; return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2

def duration(path):
    r = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if 'Duration:' in ln:
            hh, mm, rest = ln.split('Duration: ')[1].split(',')[0].strip().split(':')
            return int(hh)*3600 + int(mm)*60 + float(rest)
    raise SystemExit(f'no duration for {path}')

# ------------------------ signature sapphire-blue grade + full-bleed 9:16 plates ----
_GAMMA_LUT = [min(255, max(0, int(round(255.0 * ((i / 255.0) ** 0.84))))) for i in range(256)]


def _duotone_luts():
    shadow, mid, high = (10, 28, 70), (20, 70, 150), (190, 225, 255)
    lr, lg, lb = [], [], []
    for i in range(256):
        t = i / 255.0
        if t < 0.54:
            u = t / 0.54
            c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
        else:
            u = (t - 0.54) / 0.46
            c = [mid[k] + (high[k] - mid[k]) * (u ** 1.08) for k in range(3)]
        lr.append(int(c[0]))
        lg.append(int(c[1]))
        lb.append(int(c[2]))
    return lr, lg, lb


LUT_R, LUT_G, LUT_B = _duotone_luts()


def grade_blue(im, tint_warm=0.0, keep_crimson=False):
    """Signature sapphire-blue documentary grade over bright full-bleed real video/photos."""
    rgb = im.convert('RGB').point(_GAMMA_LUT * 3)
    lum = rgb.convert('L')
    duo = Image.merge('RGB', (lum.point(LUT_R), lum.point(LUT_G), lum.point(LUT_B)))
    out = Image.blend(rgb, duo, 0.80)
    if tint_warm > 0:
        warm = Image.merge('RGB', (
            lum.point(lambda v: min(255, int(v * 1.24))),
            lum.point(lambda v: int(v * 0.70)),
            lum.point(lambda v: int(v * 0.30)),
        ))
        out = Image.blend(out, warm, min(0.32, tint_warm))
    out = out.point(lambda v: max(0, min(255, int(128 + (v - 128) * 1.12))))
    if keep_crimson:
        # Preserve glowing red market-crash candlesticks over the deep sapphire-blue grade
        r_ch, g_ch, _b_ch = rgb.split()
        red_mask = Image.eval(
            Image.composite(r_ch, Image.new('L', rgb.size, 0), r_ch),
            lambda v: v,
        )
        from PIL import ImageChops
        diff = ImageChops.subtract(r_ch, g_ch)
        mask = diff.point(lambda d: 0 if d < 62 else min(235, int((d - 62) * 3.2)))
        out = Image.composite(rgb, out, mask.filter(ImageFilter.GaussianBlur(1.5)))
    return out


grade_cinema = grade_blue


def _build_edge_scrim():
    """Subtle deep-blue top/bottom gradient for HUD & YouTube chrome readability."""
    scrim = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    px = scrim.load()
    for y in range(H):
        if y < 185:
            u = 1.0 - (y / 185.0)
            a = int(88 * (u ** 1.4))
        elif y > 1000:
            u = (y - 1000) / float(H - 1000)
            a = int(136 * (u ** 1.35))
        else:
            a = 0
        if a > 0:
            for x in range(W):
                px[x, y] = (3, 10, 28, a)
    return scrim


EDGE_SCRIM = _build_edge_scrim()


def prep_plate(path, tint_warm=0.0):
    """Full-bleed 9:16 cover plate (1080x1920) graded in signature sapphire-blue."""
    raw = Image.open(path).convert('RGB')
    scale = max(CW / max(1, raw.width), CH / max(1, raw.height))
    sw = max(CW, int(round(raw.width * scale)))
    sh = max(CH, int(round(raw.height * scale)))
    resized = raw.resize((sw, sh), Image.Resampling.LANCZOS)
    x0 = max(0, (sw - CW) // 2)
    y0 = max(0, (sh - CH) // 2)
    cropped = resized.crop((x0, y0, x0 + CW, y0 + CH))
    sharpened = cropped.filter(ImageFilter.UnsharpMask(radius=1.0, percent=88, threshold=3))
    keep_red = 'crash-poster' in os.path.basename(str(path))
    return grade_blue(sharpened, tint_warm=tint_warm, keep_crimson=keep_red)

def video_plate_reader(path, skip_intro=1.5):
    """Stream full-bleed 9:16 RGB video frames in natural documentary color,
    skipping potential black film-leader frames at the very start of archival clips."""
    vf = (
        f'scale={CW}:{CH}:force_original_aspect_ratio=increase,'
        f'crop={CW}:{CH},setsar=1,'
        f'eq=contrast=1.08:brightness=0.04:saturation=1.12,'
        f'fps={FPS},format=rgb24'
    )
    ss_args = ['-ss', f'{skip_intro:.2f}'] if skip_intro > 0 else []
    cmd = (
        [FFMPEG, '-loglevel', 'error', '-stream_loop', '-1']
        + ss_args
        + ['-i', str(path), '-an', '-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1']
    )
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**7)


def _is_vivid_video_clip(path):
    """Reject dark film leaders, murky low-res clips, blank slides, or blown-out frames."""
    try:
        dur = duration(str(path))
    except BaseException:
        return False
    if dur < 2.2:
        return False
    sample_times = [min(dur * 0.25, 1.6), min(dur * 0.50, 3.2), min(dur * 0.75, 4.8)]
    for ts in sample_times:
        proc = subprocess.run(
            [
                FFMPEG, '-loglevel', 'error', '-ss', f'{ts:.2f}', '-i', str(path),
                '-frames:v', '1', '-vf', 'scale=96:170:force_original_aspect_ratio=increase,crop=96:170',
                '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1',
            ],
            check=False,
            capture_output=True,
        )
        raw = proc.stdout
        if len(raw) < 96 * 170 * 3:
            return False
        lum = [0.299 * raw[i] + 0.587 * raw[i + 1] + 0.114 * raw[i + 2] for i in range(0, len(raw), 3)]
        mean_l = sum(lum) / len(lum)
        var_l = sum((v - mean_l) ** 2 for v in lum) / len(lum)
        std_l = math.sqrt(var_l)
        dark_frac = sum(1 for v in lum if v < 24.0) / len(lum)
        if mean_l < 58.0 or mean_l > 215.0 or std_l < 26.0 or dark_frac > 0.45:
            print(f'[shorts] rejecting dark/flat video {os.path.basename(str(path))} at t={ts:.1f}s (mean={mean_l:.1f}, std={std_l:.1f}, dark={dark_frac:.0%})', flush=True)
            return False
    return True

def read_video_plate(proc):
    if not proc or proc.stdout is None:
        return None
    size = CW * CH * 3
    data = bytearray()
    while len(data) < size:
        chunk = proc.stdout.read(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return grade_blue(Image.frombytes('RGB', (CW, CH), bytes(data)))

def stop_video_plate(proc):
    if not proc:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
    if proc.stdout:
        try:
            proc.stdout.close()
        except OSError:
            pass

# --------------------------------------- sub-pixel smooth cinema camera ----
def camera_frame(plate, p, mode='push_in', focus=(0.5, 0.45), extra_zoom=1.0):
    p = clamp01(p)
    s = 0.65 * ease_in_out_sine(p) + 0.35 * p
    fx, fy = focus
    if mode == 'push_in':
        z = 1.0 + 0.10 * s; dx = (fx - 0.5) * 0.06 * s; dy = (fy - 0.5) * 0.05 * s
    elif mode == 'pull_out':
        z = 1.10 - 0.10 * s; dx = (fx - 0.5) * 0.05 * (1.0 - s); dy = (fy - 0.5) * 0.04 * (1.0 - s)
    elif mode == 'pan_right':
        z = 1.07 + 0.03 * s; dx = -0.032 + 0.064 * s; dy = (fy - 0.5) * 0.03 * s
    elif mode == 'pan_left':
        z = 1.07 + 0.03 * s; dx = 0.032 - 0.064 * s; dy = (fy - 0.5) * 0.03 * s
    elif mode == 'tilt_up':
        z = 1.06 + 0.04 * s; dx = (fx - 0.5) * 0.03 * s; dy = 0.032 - 0.064 * s
    else:
        z = 1.02 + 0.07 * s; dx = 0.012 * math.sin(p * math.pi); dy = -0.025 * s
    z *= extra_zoom
    dx += 0.0012 * math.sin(p * 6.1 + 1.3)
    dy += 0.0010 * math.sin(p * 4.3 + 2.7)
    z *= 1.0 + 0.002 * math.sin(p * 2.4 + 0.6)
    vw = CW / z
    vh = CH / z
    cx = CW * (0.5 + dx)
    cy = CH * (0.5 + dy)
    x0 = max(0.0, min(CW - vw, cx - vw * 0.5))
    y0 = max(0.0, min(CH - vh, cy - vh * 0.5))
    im = plate.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)
    return Image.alpha_composite(im.convert('RGBA'), EDGE_SCRIM).convert('RGB')

def optical_flare_transition(f_prev, f_curr, u):
    e = ease_in_out_sine(u)
    base = Image.blend(f_prev, f_curr, e)
    inten = math.sin(clamp01(u) * math.pi) ** 1.6
    if inten <= 0.02:
        return base
    flare = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(flare)
    cy = int(H * 0.46)
    band_h = int(85 * inten + 10)
    d.ellipse([-120, cy - band_h, W + 120, cy + band_h], fill=(185, 225, 255, int(64 * inten)))
    d.rectangle([0, cy - 2, W, cy + 2], fill=(255, 225, 130, int(82 * inten)))
    flare = flare.filter(ImageFilter.GaussianBlur(18))
    return Image.alpha_composite(base.convert('RGBA'), flare).convert('RGB')

# ------------------------------------ translucent frosted glass cards ----
GLASS_CACHE = {}
MASK_CACHE = {}

def _rounded_mask(w, h, radius):
    w, h = max(16, int(w)), max(16, int(h))
    key = (w, h, radius)
    if key not in MASK_CACHE:
        m = Image.new('L', (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        MASK_CACHE[key] = m
    return MASK_CACHE[key]

def glass_card(w, h, radius=16, top=(10, 30, 66), bot=(5, 16, 38), a_top=164, a_bot=138, border_col=(148, 198, 255, 165)):
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
    bd.rounded_rectangle([1, 1, w * S - 2, h * S - 2], radius=radius * S, outline=border_col, width=3)
    card = card.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(card)
    d.line([(radius, 1), (w - radius, 1)], fill=(225, 240, 255, 115), width=1)
    GLASS_CACHE[key] = card
    return card

def card_alpha(card, a):
    a = clamp01(a)
    if a >= 0.999:
        return card
    c = card.copy()
    c.putalpha(c.getchannel('A').point(lambda v: int(v * a)))
    return c

def paste_frosted(layer, bg_rgb, card, px, py, alpha=1.0, radius=16):
    """Apply real optical backdrop blur of live footage under translucent glass card."""
    a = clamp01(alpha)
    if a <= 0.02:
        return
    cw, ch = card.size
    x0 = max(0, min(W - 1, int(px)))
    y0 = max(0, min(H - 1, int(py)))
    x1 = max(x0 + 1, min(W, int(px) + cw))
    y1 = max(y0 + 1, min(H, int(py) + ch))
    if bg_rgb is not None and (x1 - x0) > 8 and (y1 - y0) > 8:
        patch = bg_rgb.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(7))
        rgba_patch = patch.convert('RGBA')
        sub_mask = _rounded_mask(cw, ch, radius).crop((x0 - int(px), y0 - int(py), x1 - int(px), y1 - int(py)))
        rgba_patch.putalpha(sub_mask.point(lambda v: int(v * 0.88 * a)))
        layer.alpha_composite(rgba_patch, (x0, y0))
    layer.alpha_composite(card_alpha(card, a), (int(px), int(py)))

# -------------------------------------------------------------- text engine ----
def tracked_width(d, text, font, tracking):
    if not text:
        return 0.0
    return sum(d.textlength(ch, font=font) + tracking for ch in text) - tracking

def draw_tracked(d, text, font, x, y, fill, tracking=2.5):
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill)
        x += d.textlength(ch, font=font) + tracking

def kinetic_line(layer, text, font, cx, y, t, t0, color=WHITE, tracking=2.6, stagger=0.04, dur=0.48, slide=24, bounce=False, out_a=1.0):
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

def fit_font(weight, sz, text, maxw, tracking=2.2):
    f = fnt(weight, sz)
    d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    while tracked_width(d, text, f, tracking) > maxw and sz > 12:
        sz = int(sz * 0.92)
        f = fnt(weight, sz)
    return f

# ------------------------------------------------ cold-open, poster & end overlays ----
def poster_lockup_overlay(layer, kicker, big1, big2, sub_pill, alpha=1.0):
    """High-CTR scroll-stopping poster typography sized across ~87% of the 720px width
    so that even on a 358x636 mobile YouTube Shorts channel grid tile every word pops."""
    a = clamp01(alpha)
    if a <= 0.02:
        return
    cx = W // 2
    fk = fit_font('ExtraBold', 33, kicker, W - 110)
    fl1 = fit_font('Black', 214, big1, W - 76)
    fl2 = fit_font('Black', 156, big2, W - 84)
    ft = fit_font('Black', 32, sub_pill, W - 120)

    # Focused center contrast glow behind lockup while full-bleed skyscraper & red chart stay bright
    halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([-20, 210, W + 20, 960], fill=(4, 10, 26, int(162 * a)))
    hd.ellipse([50, 310, W - 50, 860], fill=(235, 38, 52, int(48 * a)))
    halo = halo.filter(ImageFilter.GaussianBlur(46))
    layer.alpha_composite(halo)

    d = ImageDraw.Draw(layer)
    # 1. Crimson kicker ribbon
    kw = d.textlength(kicker, font=fk)
    bpw, bph = int(kw + 58), 64
    bx0, by0 = cx - bpw // 2, 290
    d.rounded_rectangle(
        [bx0, by0, bx0 + bpw, by0 + bph],
        radius=15,
        fill=(228, 34, 46, int(250 * a)),
        outline=(255, 226, 226, int(220 * a)),
        width=3,
    )
    d.text((cx - kw / 2, by0 + 11), kicker, font=fk, fill=WHITE + (int(255 * a),))

    # 2. Giant "$70B" + "FRAUD" display headlines spanning ~87% of frame width
    w1 = d.textlength(big1, font=fl1)
    w2 = d.textlength(big2, font=fl2)
    y1, y2 = 368, 594
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((cx - w1 / 2, y1 + 12), big1, font=fl1, fill=(0, 0, 0, int(240 * a)), stroke_width=14, stroke_fill=(0, 0, 0, int(240 * a)))
    sd.text((cx - w2 / 2, y2 + 10), big2, font=fl2, fill=(0, 0, 0, int(240 * a)), stroke_width=12, stroke_fill=(0, 0, 0, int(240 * a)))
    sh = sh.filter(ImageFilter.GaussianBlur(11))
    layer.alpha_composite(sh)

    d = ImageDraw.Draw(layer)
    d.text((cx - w1 / 2, y1), big1, font=fl1, fill=WHITE + (int(255 * a),), stroke_width=9, stroke_fill=(8, 16, 34, int(255 * a)))
    d.text((cx - w2 / 2, y2), big2, font=fl2, fill=YELLOW + (int(255 * a),), stroke_width=8, stroke_fill=(10, 18, 36, int(255 * a)))

    # 3. Bottom gold-rimmed punchline pill
    tw_sub = d.textlength(sub_pill, font=ft)
    tpw, tph = int(tw_sub + 60), 62
    tx0, ty0 = cx - tpw // 2, 790
    d.rounded_rectangle(
        [tx0, ty0, tx0 + tpw, ty0 + tph],
        radius=15,
        fill=(8, 20, 44, int(240 * a)),
        outline=YELLOW + (int(240 * a),),
        width=3,
    )
    d.text((cx - tw_sub / 2, ty0 + 11), sub_pill, font=ft, fill=WHITE + (int(255 * a),))


def cold_open_overlay(layer, bg_rgb, title_pair, t, dur=2.8, poster_spec=None):
    if t < 0 or t > dur:
        return
    in_e = ease_out_expo(clamp01((t + 0.08) / 0.24))
    out_a = 1.0 if t < dur - 0.45 else 1.0 - ease_in_out_sine((t - (dur - 0.45)) / 0.45)
    a = in_e * out_a
    if a <= 0.01:
        return
    if poster_spec:
        poster_lockup_overlay(layer, poster_spec[0], poster_spec[1], poster_spec[2], poster_spec[3], alpha=a)
        return
    t1, t2 = title_pair
    max_card_w = SAFE_R - SAFE_L - 16
    f1 = fit_font('Black', 34, t1, max_card_w - 56, 2.4)
    f2 = fit_font('SemiBold', 13, t2, max_card_w - 56, 2.8)
    d = ImageDraw.Draw(layer)
    w1 = tracked_width(d, t1, f1, 2.4)
    pw = int(min(max_card_w, max(w1 + 56, 420)))
    ph = 118
    px = W // 2 - pw // 2
    py = int(218 - (1.0 - in_e) * 20)
    paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=18, a_top=172, a_bot=144), px, py, a, radius=18)
    bw = int(104 * ease_out_back(clamp01((t - 0.10) / 0.5)))
    d.rectangle([W // 2 - bw // 2, py + 16, W // 2 + bw // 2, py + 20], fill=YELLOW + (int(240 * a),))
    kinetic_line(layer, t1, f1, W / 2, py + 28, t, 0.06, WHITE, 2.4, stagger=0.026, dur=0.42, slide=18, out_a=a)
    w2 = tracked_width(d, t2, f2, 2.8)
    sa = int(238 * clamp01((t - 0.32) / 0.42) * a)
    if sa > 0:
        draw_tracked(d, t2, f2, W / 2 - w2 / 2, py + 84, ICE + (sa,), 2.8)

def end_card_overlay(base_img, end_pair, t_local, T):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    e = ease_out_expo(clamp01(t_local / 0.45))
    dim = Image.new('RGBA', (W, H), (4, 14, 32, int(115 * e)))
    layer = Image.alpha_composite(layer, dim)
    t1, t2 = end_pair
    pw, ph = 520, 178
    px, py = (W - pw) // 2, 430
    paste_frosted(layer, base_img, glass_card(pw, ph, radius=20, a_top=192, a_bot=165, border_col=YELLOW + (195,)), px, py, e, radius=20)
    d = ImageDraw.Draw(layer)
    f1 = fnt('Black', 40)
    f2 = fit_font('SemiBold', 15, t2.upper(), pw - 56, 2.6)
    kinetic_line(layer, t1, f1, W / 2, py + 24, t_local, 0.05, YELLOW, 3.0, stagger=0.04, dur=0.42, slide=20, bounce=True, out_a=e)
    bw = int(144 * ease_out_back(clamp01((t_local - 0.22) / 0.45)))
    d.rectangle([W // 2 - bw // 2, py + 88, W // 2 + bw // 2, py + 92], fill=WHITE + (int(225 * e),))
    w2 = tracked_width(d, t2.upper(), f2, 2.6)
    sa = int(242 * clamp01((t_local - 0.28) / 0.42))
    if sa > 0:
        draw_tracked(d, t2.upper(), f2, W / 2 - w2 / 2, py + 112, ICE + (sa,), 2.6)
    return Image.alpha_composite(base_img.convert('RGBA'), layer).convert('RGB')

# ------------------------------ HUD + chapter badge + word ribbon (20:9 safe) ----
def hud_chapter_layer(bg_rgb, kicker, sub, idx, nscenes, t_scene, scene_dur, total_frac):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    in_e = ease_out_expo(clamp01(t_scene / 0.42))
    out_e = 1.0 if (scene_dur - t_scene) > 0.35 else clamp01((scene_dur - t_scene) / 0.35)
    a = in_e * out_e
    d = ImageDraw.Draw(layer)

    # Compact right-side progress pill strictly inside SAFE_R=644 (never clipped on 20:9 phones)
    pw_prog, ph_prog = 104, 28
    px_prog, py_prog = SAFE_R - pw_prog, SAFE_HUD_Y + 6
    paste_frosted(layer, bg_rgb, glass_card(pw_prog, ph_prog, radius=14, a_top=168, a_bot=142), px_prog, py_prog, 0.94, radius=14)
    fp = fnt('Bold', 10)
    pct = f'{int(clamp01(total_frac) * 100):d}%'
    d.text((px_prog + 10, py_prog + 8), 'DOC', font=fp, fill=ICE + (225,))
    d.rectangle([px_prog + 38, py_prog + 12, px_prog + 68, py_prog + 16], fill=(255, 255, 255, 55))
    fill_w = int(30 * clamp01(total_frac))
    if fill_w > 0:
        d.rectangle([px_prog + 38, py_prog + 12, px_prog + 38 + fill_w, py_prog + 16], fill=YELLOW + (245,))
    d.text((px_prog + 72, py_prog + 8), pct, font=fp, fill=WHITE + (240,))

    if a > 0.02:
        max_hud_w = px_prog - SAFE_L - 12  # 452px cleanly left of DOC pill
        fk = fit_font('Bold', 12, kicker, max_hud_w - 86, 1.2)
        fs = fit_font('Medium', 10, sub, max_hud_w - 86, 1.2) if sub else fnt('Medium', 10)
        fc = fnt('Black', 10)
        tag = f'{idx:02d}/{nscenes:02d}'
        wk = tracked_width(d, kicker, fk, 1.2)
        ws = tracked_width(d, sub, fs, 1.2) if sub else 0
        cw = int(min(max_hud_w, max(wk + 86, ws + 86, 220)))
        ch = 46 if sub else 34
        cx = int(SAFE_L - (1.0 - in_e) * 14)
        cy = SAFE_HUD_Y
        paste_frosted(layer, bg_rgb, glass_card(cw, ch, radius=12, a_top=172, a_bot=144), cx, cy, a, radius=12)
        d.rounded_rectangle([cx + 8, cy + 8, cx + 56, cy + 26], radius=6, fill=YELLOW + (int(242 * a),))
        wt = d.textlength(tag, font=fc)
        d.text((cx + 32 - wt / 2, cy + 10), tag, font=fc, fill=NAVY + (int(255 * a),))
        draw_tracked(d, kicker, fk, cx + 66, cy + 8, WHITE + (int(252 * a),), 1.2)
        if sub:
            draw_tracked(d, sub, fs, cx + 66, cy + 26, ICE + (int(228 * a),), 1.2)

    # Bottom progress bar inside safe width so full progress is visible
    d.rectangle([SAFE_L, H - 6, SAFE_R, H], fill=(255, 255, 255, 38))
    bx = SAFE_L + int((SAFE_R - SAFE_L) * clamp01(total_frac))
    if bx > SAFE_L:
        d.rectangle([SAFE_L, H - 6, bx, H], fill=YELLOW + (235,))
    return layer

def build_caption_stream(key, raw_words):
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

def caption_ribbon_layer(bg_rgb, stream, t):
    """Animated karaoke captions above @channel overlay & left of right-rail icons."""
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

    # Keep captions strictly inside [SAFE_L..RAIL_SAFE_R] = [76..554] (width <= 478px)
    # and y = SAFE_CAPTION_Y (810..885), well above @handle/title at y>=935!
    max_cap_w = RAIL_SAFE_R - SAFE_L
    cap_cx = (SAFE_L + RAIL_SAFE_R) / 2.0  # 315.0
    f = fnt('ExtraBold', 18)
    d = ImageDraw.Draw(layer)
    gap = 6.5
    words = active['words']

    # Wrap cleanly into 1 or 2 balanced lines if needed so font stays big & legible
    lines = []
    cur_line = []
    cur_w = 0.0
    for idx_w, (ws, we, w) in enumerate(words):
        ww = d.textlength(w.upper(), font=f)
        needed = ww if not cur_line else (gap + ww)
        if cur_line and (cur_w + needed) > (max_cap_w - 30):
            lines.append(cur_line)
            cur_line = [(idx_w, ws, we, w, ww)]
            cur_w = ww
        else:
            cur_line.append((idx_w, ws, we, w, ww))
            cur_w += needed
    if cur_line:
        lines.append(cur_line)

    if len(lines) > 2:
        f = fnt('ExtraBold', 15)
        lines, cur_line, cur_w = [], [], 0.0
        for idx_w, (ws, we, w) in enumerate(words):
            ww = d.textlength(w.upper(), font=f)
            needed = ww if not cur_line else (gap + ww)
            if cur_line and (cur_w + needed) > (max_cap_w - 28):
                lines.append(cur_line)
                cur_line = [(idx_w, ws, we, w, ww)]
                cur_w = ww
            else:
                cur_line.append((idx_w, ws, we, w, ww))
                cur_w += needed
        if cur_line:
            lines.append(cur_line)

    line_widths = [sum(it[4] for it in ln) + gap * max(0, len(ln) - 1) for ln in lines]
    pw = int(min(max_cap_w, max(line_widths) + 30))
    line_h = 26
    ph = 16 + line_h * len(lines)
    px = int(cap_cx - pw / 2.0)
    py = SAFE_CAPTION_Y - (len(lines) - 1) * 14
    paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=12, top=(6, 20, 46), bot=(3, 10, 26), a_top=192, a_bot=172), px, py, a, radius=12)

    cur_idx = 0
    for j, (ws, we, _) in enumerate(words):
        if t >= ws - 0.04:
            cur_idx = j

    for li, ln in enumerate(lines):
        lw = line_widths[li]
        x = cap_cx - lw / 2.0
        yy = py + 8 + li * line_h
        for idx_w, ws, we, w, ww in ln:
            txt = w.upper()
            if idx_w == cur_idx:
                pad_x = 6
                d.rounded_rectangle(
                    [x - pad_x, yy - 2, x + ww + pad_x, yy + line_h - 3],
                    radius=6,
                    fill=(255, 201, 60, int(238 * a)),
                )
                d.text((x, yy), txt, font=f, fill=NAVY + (int(255 * a),))
            elif idx_w < cur_idx:
                d.text((x, yy), txt, font=f, fill=WHITE + (int(248 * a),))
            else:
                d.text((x, yy), txt, font=f, fill=ICE + (int(180 * a),))
            x += ww + gap
    return layer

# ------------------------- contextual visual diagrams (viz_layer) — vertical ----
def viz_layer(bg_rgb, viz_kind, t_scene, scene_dur):
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
    vcx = 315  # centered cleanly left of right-rail icons (SAFE_L=76 .. RAIL_SAFE_R=554)

    if viz_kind == 'pressure_gauge':
        pw, ph, px, py = 360, 102, vcx - 180, 560
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        d.text((px + 16, py + 12), 'HYDROSTATIC DAM LOAD', font=f1, fill=ICE + (int(235 * a),))
        d.rectangle([px + 16, py + 34, px + pw - 16, py + 54], fill=(255, 255, 255, int(42 * a)))
        bw = int((pw - 32) * ease_out_expo(prog))
        col = CRIMSON if prog > 0.75 else YELLOW
        if bw > 2:
            d.rectangle([px + 16, py + 34, px + 16 + bw, py + 54], fill=col + (int(240 * a),))
        d.text((px + 16, py + 68), 'EARTHEN CREST: CRITICAL', font=f1, fill=col + (int(245 * a),))

    elif viz_kind == 'dam_anatomy':
        pw, ph, px, py = 400, 156, vcx - 200, 545
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        fh = fnt('Black', 12)
        fb = fnt('SemiBold', 11)
        d.text((px + 16, py + 12), 'FATAL MODIFICATIONS TO DAM', font=fh, fill=YELLOW + (int(245 * a),))
        items = [(0.08, '01  IRON SCREENS CLOG PIPES'), (0.32, '02  SPILLWAY CHOKED'), (0.56, '03  CREST LOWERED 3FT')]
        for idx, (thr, txt) in enumerate(items):
            ia = clamp01((prog - thr) / 0.25) * a
            if ia > 0.02:
                yy = py + 36 + idx * 36
                d.rounded_rectangle([px + 16, yy, px + pw - 16, yy + 28], radius=8, fill=(255, 86, 92, int(48 * ia)), outline=CRIMSON + (int(165 * ia),), width=1)
                d.text((px + 26, yy + 6), txt, font=fb, fill=WHITE + (int(245 * ia),))

    elif viz_kind == 'rain_rising':
        for r in range(22):
            rx = int(((r * 137 + t_scene * 420) % (W + 100)) - 50)
            ry = int(((r * 91 + t_scene * 780) % (H + 120)) - 60)
            d.line([(rx, ry), (rx - 10, ry + 32)], fill=(185, 220, 255, int(70 * a)), width=2)
        pw, ph, px, py = 340, 114, vcx - 170, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        d.text((px + 16, py + 12), 'RESERVOIR WATER LEVEL', font=f1, fill=ICE + (int(235 * a),))
        d.rectangle([px + 16, py + 36, px + pw - 16, py + 60], outline=ICE + (int(140 * a),), width=2)
        fill_w = int((pw - 36) * ease_out_cubic(prog))
        col = CRIMSON if prog > 0.8 else YELLOW
        d.rectangle([px + 18, py + 38, px + 18 + fill_w, py + 58], fill=col + (int(230 * a),))
        d.text((px + 16, py + 72), 'STATUS: OVERTOPPING CREST', font=f1, fill=CRIMSON + (int(245 * a),))

    elif viz_kind == 'valley_drop':
        pw, ph, px, py = 390, 128, vcx - 195, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('SemiBold', 10)
        d.text((px + 16, py + 10), '14-MILE VALLEY DROP', font=f1, fill=YELLOW + (int(245 * a),))
        pts = [(px + 22, py + 40), (px + 125, py + 60), (px + 235, py + 84), (px + 355, py + 94)]
        d.line(pts, fill=ICE + (int(165 * a),), width=3)
        wx = int(px + 22 + (355 - 22) * ease_in_out_sine(prog))
        wy = int(py + 40 + (94 - 40) * ease_in_out_sine(prog))
        d.ellipse([wx - 6, wy - 6, wx + 6, wy + 6], fill=YELLOW + (int(255 * a),))
        d.text((px + 16, py + 102), 'SOUTH FORK (3:10 PM)', font=f2, fill=ICE + (int(225 * a),))
        d.text((px + 220, py + 102), 'JOHNSTOWN (4:07 PM)', font=f2, fill=WHITE + (int(240 * a),))

    elif viz_kind == 'wave_scale':
        pw, ph, px, py = 360, 142, vcx - 180, 560
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('Bold', 10)
        d.text((px + 16, py + 10), 'FLOOD WAVE SCALE', font=f1, fill=YELLOW + (int(245 * a),))
        base_y = py + 118
        bars = [('LOCOMOTIVE', 14, ICE), ('HOUSE', 24, WHITE), ('FLOOD', 36, CRIMSON)]
        for idx, (lab, ft, col) in enumerate(bars):
            bx = px + 28 + idx * 108
            bh = int((ft / 36.0) * 68 * ease_out_expo(clamp01((prog - idx * 0.15) / 0.55)))
            d.rectangle([bx, base_y - bh, bx + 56, base_y], fill=col + (int(230 * a),))
            d.text((bx + 8, base_y - bh - 14), f'{ft} FT', font=f2, fill=WHITE + (int(240 * a),))
            d.text((bx, base_y + 5), lab, font=f2, fill=ICE + (int(215 * a),))

    elif viz_kind == 'mtm_ledger':
        pw, ph, px, py = 396, 122, vcx - 198, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('Black', 12)
        d.text((px + 16, py + 10), 'MARK-TO-MARKET ILLUSION', font=f1, fill=YELLOW + (int(245 * a),))
        for yr in range(10):
            bx = px + 16 + yr * 21
            d.rectangle([bx, py + 34, bx + 15, py + 70], fill=(120, 175, 240, int(190 * a)), outline=WHITE + (int(120 * a),))
        d.text((px + 16, py + 80), '10-YR PROJECTION', font=fnt('SemiBold', 10), fill=ICE + (int(225 * a),))
        if prog > 0.25:
            pa = clamp01((prog - 0.25) / 0.4) * a
            d.rounded_rectangle([px + 228, py + 30, px + 380, py + 78], radius=8, fill=(255, 201, 60, int(62 * pa)), outline=YELLOW + (int(235 * pa),), width=2)
            d.text((px + 240, py + 39), 'BOOKED DAY 1', font=f2, fill=YELLOW + (int(250 * pa),))
            d.text((px + 240, py + 56), 'AS PROFIT', font=fnt('Bold', 10), fill=WHITE + (int(245 * pa),))

    elif viz_kind == 'stock_boom':
        pw, ph, px, py = 380, 130, vcx - 190, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('Black', 17)
        d.text((px + 16, py + 10), 'NYSE: ENE · SHARE PRICE', font=f1, fill=ICE + (int(235 * a),))
        vals = [0.18, 0.24, 0.31, 0.42, 0.39, 0.55, 0.68, 0.79, 0.92, 1.00]
        n_pts = max(2, int(len(vals) * ease_out_cubic(prog)))
        pts = []
        for idx in range(n_pts):
            vx = px + 18 + idx * ((pw - 36) / (len(vals) - 1))
            vy = py + 104 - vals[idx] * 58
            pts.append((vx, vy))
        if len(pts) >= 2:
            d.line(pts, fill=EMERALD + (int(245 * a),), width=3)
            lx, ly = pts[-1]
            d.ellipse([lx - 6, ly - 6, lx + 6, ly + 6], fill=YELLOW + (int(255 * a),))
            cur_p = 18.0 + (90.75 - 18.0) * vals[n_pts - 1]
            d.text((px + pw - 92, py + 10), f'${cur_p:0.2f}', font=f2, fill=EMERALD + (int(250 * a),))

    elif viz_kind == 'shell_maze':
        pw, ph, px, py = 408, 122, vcx - 204, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('Black', 10)
        d.text((px + 14, py + 10), 'OFF-BALANCE-SHEET SHELL MAZE', font=f1, fill=YELLOW + (int(245 * a),))
        nodes = ['ENRON', 'LJM 1&2', 'RAPTOR', 'CHEWCO']
        for idx, nm in enumerate(nodes):
            na = clamp01((prog - idx * 0.16) / 0.3) * a
            if na > 0.02:
                nx = px + 14 + idx * 96
                ny = py + 34
                col = CRIMSON if idx > 0 else ICE
                d.rounded_rectangle([nx, ny, nx + 86, ny + 38], radius=8, fill=(20, 45, 90, int(195 * na)), outline=col + (int(220 * na),), width=2)
                d.text((nx + 8, ny + 12), nm, font=f2, fill=WHITE + (int(250 * na),))
        d.text((px + 14, py + 84), 'RESULT: $30B+ LOSSES HIDDEN', font=fnt('Bold', 11), fill=CRIMSON + (int(245 * a),))

    elif viz_kind == 'insider_split':
        pw, ph, px, py = 392, 124, vcx - 196, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        fb = fnt('Bold', 11)
        d.rounded_rectangle([px + 14, py + 12, px + pw - 14, py + 54], radius=8, fill=(72, 232, 164, int(38 * a)), outline=EMERALD + (int(180 * a),), width=2)
        d.text((px + 22, py + 16), 'MESSAGE TO STAFF:', font=fb, fill=EMERALD + (int(240 * a),))
        d.text((px + 22, py + 31), '"KEEP BUYING ENRON"', font=fnt('Black', 12), fill=WHITE + (int(250 * a),))
        if prog > 0.30:
            sa = clamp01((prog - 0.30) / 0.35) * a
            d.rounded_rectangle([px + 14, py + 62, px + pw - 14, py + 108], radius=8, fill=(255, 86, 92, int(48 * sa)), outline=CRIMSON + (int(210 * sa),), width=2)
            d.text((px + 22, py + 68), 'EXECUTIVES DID:', font=fb, fill=CRIMSON + (int(245 * sa),))
            d.text((px + 22, py + 84), 'CASHED OUT $1.1B', font=fnt('Black', 12), fill=YELLOW + (int(250 * sa),))

    elif viz_kind == 'stock_crash':
        pw, ph, px, py = 380, 130, vcx - 190, 565
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, a)
        f1 = fnt('Bold', 12)
        f2 = fnt('Black', 17)
        d.text((px + 16, py + 10), 'NYSE: ENE · COLLAPSE', font=f1, fill=ICE + (int(235 * a),))
        vals = [1.0, 0.88, 0.74, 0.58, 0.42, 0.28, 0.15, 0.06, 0.01, 0.003]
        n_pts = max(2, int(len(vals) * ease_out_cubic(prog)))
        pts = []
        for idx in range(n_pts):
            vx = px + 18 + idx * ((pw - 36) / (len(vals) - 1))
            vy = py + 104 - vals[idx] * 58
            pts.append((vx, vy))
        if len(pts) >= 2:
            d.line(pts, fill=CRIMSON + (int(250 * a),), width=3)
            lx, ly = pts[-1]
            d.ellipse([lx - 6, ly - 6, lx + 6, ly + 6], fill=CRIMSON + (int(255 * a),))
            cur_p = 90.75 * vals[n_pts - 1]
            d.text((px + pw - 92, py + 10), f'${cur_p:0.2f}', font=f2, fill=CRIMSON + (int(250 * a),))
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
    for i, b in enumerate(beats):
        natural_end = b['t1'] + b.get('hold', 2.4)
        if i + 1 < len(beats):
            latest_end = beats[i + 1]['t0'] - 0.64
            b['end_t'] = max(b['t0'] + 0.35, min(natural_end, latest_end))
        else:
            b['end_t'] = natural_end
    return beats

def resolve_scenes(key, words, total_dur):
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
    for idx in range(1, len(resolved)):
        if resolved[idx]['t0'] <= resolved[idx - 1]['t0']:
            raise SystemExit(
                f"scene order error in {key}: {resolved[idx]['kicker']!r} t0={resolved[idx]['t0']:.2f} "
                f"<= previous {resolved[idx - 1]['t0']:.2f} — list scenes in spoken order"
            )
    for idx in range(len(resolved)):
        resolved[idx]['t1'] = resolved[idx + 1]['t0'] if idx + 1 < len(resolved) else total_dur
    return resolved

# --------------------------------------------------- speech-synced beats ----
def build_music_plan(key, words, beats):
    hushes, swells = [], []
    for b in beats:
        if b.get('kind') == 'count':
            big = b.get('num', 0) >= 1000 or 'txt' in b
            if big:
                swells.append(b['t0'] + b.get('dur', 1.35))
        elif b.get('kind') in ('quote', 'date'):
            swells.append(b['t0'] + (0.3 if b['kind'] == 'date' else 0.0))
    for cue in SCRIPTS[key].get('sfx_cues', []):
        if 'hush' not in cue:
            continue
        h = dict(cue['hush'])
        hit = find_phrase(words, h['a'], h.get('occ', 0))
        if not hit:
            raise SystemExit(f"hush anchor not found: {h['a']!r}")
        hushes.append(dict(t=hit[0][0], dur=h.get('dur', 1.2), depth=h.get('depth', 0.85), lead=h.get('lead', 0.5)))
    return hushes, swells

# Hero beats sit cleanly in upper-middle safe frame (y=340..445), leaving center & lower viewport open for real video/photography
SLOT_MAP = {'C': (360, 392), 'TC': (360, 342), 'BC': (360, 442)}
SLOT_CYCLE = ['C', 'TC', 'C', 'BC', 'C']

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
    r = 34 + 74 * ease_out_expo(e)
    a = int(135 * (1.0 - e))
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

def beat_count(layer, bg_rgb, b, t, cx, cy):
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
    fnum = fnt('Black', 52 if b.get('big', True) else 44)
    fnote = fnt('Bold', 12)
    d = ImageDraw.Draw(layer)
    wnum = d.textlength(shown, font=fnum)
    label = b.get('label', '')
    wlab = tracked_width(d, label, fnote, 1.8) if label else 0
    panel_w = int(min(SAFE_R - SAFE_L - 20, max(wnum + 52, wlab + 52, 240)))
    panel_h = 118 if label else 90
    px = int(cx - panel_w / 2)
    py = int(cy - panel_h / 2 - (1.0 - out_a) * 16)
    paste_frosted(layer, bg_rgb, glass_card(panel_w, panel_h, radius=18), px, py, ea * out_a, radius=18)
    d.rectangle([px + 18, py + 11, px + 18 + int((panel_w - 36) * ease_out_expo(local)), py + 15], fill=YELLOW + (int(240 * ea * out_a),))
    im = Image.new('RGBA', (int(wnum) + 20, 74), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 4), shown, font=fnum, fill=WHITE + (255,))
    if abs(pop - 1.0) > 0.01:
        nw, nh = max(2, int(im.width * pop)), max(2, int(im.height * pop))
        im = im.resize((nw, nh), Image.BICUBIC)
    im.putalpha(im.getchannel('A').point(lambda v: int(v * ea * out_a)))
    layer.alpha_composite(im, (int(cx - im.width / 2), int(py + 16)))
    if label:
        la = clamp01((t - (t0 + 0.15)) / 0.42) * ea * out_a
        if la > 0.02:
            draw_tracked(d, label, fnote, cx - wlab / 2, py + panel_h - 24, ICE + (int(245 * la),), 1.8)
    _flash_ring(layer, t, t0 + dur * 0.85, cx, cy)

def beat_phrase(layer, bg_rgb, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.24)
    if ea * out_a <= 0.01:
        return
    disp = b['words']
    ts = _word_times(b, len(disp))
    max_w = SAFE_R - SAFE_L - 28  # <= 540px
    f = fnt('Black', 24)
    tr = 4.5
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(w, font=f) + tr for w in disp]
    total = sum(widths) - tr
    if total > max_w - 44:
        f = fnt('Black', 19)
        widths = [d.textlength(w, font=f) + tr for w in disp]
        total = sum(widths) - tr
    pw = int(min(max_w, total + 44))
    ph = 72
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 16)
    paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, ea * out_a, radius=14)
    x0 = cx - total / 2.0
    x = x0
    hi = b.get('hi', -1)
    for i, (w, wt) in enumerate(zip(disp, ts)):
        local = clamp01((t - (wt - 0.18)) / 0.38)
        if local > 0:
            e = ease_out_expo(local)
            a = int(255 * min(1.0, local * 1.9) * out_a)
            col = YELLOW if i == hi else WHITE
            yy = py + 18 + (1.0 - e) * 16
            d.text((x, yy), w, font=f, fill=col + (a,))
        x += widths[i]
    prog = clamp01((t - (b['t0'] - 0.08)) / max(0.35, b['t1'] - b['t0'] + 0.25))
    if prog > 0:
        uw = total * ease_out_expo(prog)
        d.rectangle([x0, py + ph - 14, x0 + uw, py + ph - 10], fill=YELLOW + (int(235 * ea * out_a),))

def beat_quote(layer, bg_rgb, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.30)
    if ea * out_a <= 0.01:
        return
    disp = b['words']
    ts = _word_times(b, len(disp))
    max_w = SAFE_R - SAFE_L - 20
    fq = fnt('Bold', 18 if len(disp) > 6 else 22)
    fmark = fnt('Black', 60)
    fat = fnt('SemiBold', 11)
    d = ImageDraw.Draw(layer)
    mid = (len(disp) + 1) // 2
    lines = [disp[:mid], disp[mid:]]
    lts = [ts[:mid], ts[mid:]]
    line_w = [sum(d.textlength(w, font=fq) + 6 for w in lw) - 6 for lw in lines if lw]
    pw = int(min(max_w, max(line_w) + 84))
    ph = 130 if len(lines) > 1 and lines[1] else 94
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 16)
    paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=18), px, py, ea * out_a, radius=18)
    ma = int(235 * ea * out_a)
    d.text((px + 12, py + 8), '\u201c', font=fnt('Black', 42), fill=YELLOW + (ma,))
    for li, (lw, lt) in enumerate(zip(lines, lts)):
        widths = [d.textlength(w, font=fq) + 6 for w in lw]
        total = sum(widths) - 6
        x = max(px + 42, cx - total / 2.0 + 14)
        y = py + 24 + li * 30
        for w, wt in zip(lw, lt):
            local = clamp01((t - (wt - 0.18)) / 0.42)
            if local > 0:
                e = ease_out_expo(local)
                a = int(255 * min(1.0, local * 1.9) * out_a)
                yy = y + (1.0 - e) * 12
                d.text((x, yy), w, font=fq, fill=WHITE + (a,))
            x += d.textlength(w, font=fq) + 6
    if b.get('attrib'):
        la = clamp01((t - (b['t0'] + 0.25)) / 0.48) * ea * out_a
        if la > 0.02:
            aw = tracked_width(d, b['attrib'], fat, 1.6)
            draw_tracked(d, b['attrib'], fat, cx - aw / 2, py + ph - 21, YELLOW + (int(240 * la),), 1.6)

def beat_date(layer, bg_rgb, b, t, cx, cy):
    ea, out_a = _beat_envelope(b, t, pre=0.24)
    if ea * out_a <= 0.01:
        return
    t0 = b['t0']
    fm = fnt('Black', 30)
    fs = fnt('Bold', 12)
    d = ImageDraw.Draw(layer)
    wm = tracked_width(d, b['main'], fm, 2.0)
    ws = tracked_width(d, b.get('sub', ''), fs, 2.2) if b.get('sub') else 0
    pw, ph = int(min(SAFE_R - SAFE_L - 24, max(wm, ws) + 50)), 84
    px = int(cx - pw / 2)
    py = int(cy - ph / 2 - (1.0 - out_a) * 16)
    paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=14), px, py, ea * out_a, radius=14)
    bl = int(13 * ea)
    ba = int(235 * ea * out_a)
    for bx, by, dx, dy in ((px + 6, py + 6, 1, 1), (px + pw - 7, py + 6, -1, 1), (px + 6, py + ph - 7, 1, -1), (px + pw - 7, py + ph - 7, -1, -1)):
        x_a, x_b = sorted([bx, bx + bl * dx])
        y_a, y_b = sorted([by, by + bl * dy])
        d.rectangle([x_a, by, x_b, by + 2], fill=YELLOW + (ba,))
        d.rectangle([bx, y_a, bx + 2, y_b], fill=YELLOW + (ba,))
    kinetic_line(layer, b['main'], fm, cx, py + 13, t, t0 - 0.18, WHITE, 2.0, stagger=0.03, dur=0.42, slide=14, out_a=ea * out_a)
    if b.get('sub'):
        la = clamp01((t - (t0 + 0.18)) / 0.42) * ea * out_a
        if la > 0.02:
            draw_tracked(d, b['sub'], fs, cx - ws / 2, py + 50, ICE + (int(240 * la),), 2.2)

BEAT_KINDS = {'count': beat_count, 'phrase': beat_phrase, 'quote': beat_quote, 'date': beat_date}

def tease_layer(bg_rgb, teases, t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    tcx = (SAFE_L + RAIL_SAFE_R) // 2
    max_tw = RAIL_SAFE_R - SAFE_L - 8
    for tr in teases:
        t0 = tr['t']
        if t < t0 or t > t0 + 2.8:
            continue
        ea = ease_out_expo(clamp01((t - t0) / 0.5))
        out_a = 1.0 - clamp01((t - (t0 + 2.2)) / 0.5)
        dy = (1 - ea) * -22
        ftag = fnt('Black', 11)
        ftxt = fit_font('Bold', 13, tr['text'], max_tw - 84, 1.2)
        d = ImageDraw.Draw(layer)
        wtag = tracked_width(d, 'AHEAD', ftag, 2.0)
        wtxt = tracked_width(d, tr['text'], ftxt, 1.2)
        pw = int(min(max_tw, wtag + wtxt + 48))
        ph = 34
        px = int(tcx - pw // 2)
        py = int(736 + dy)
        paste_frosted(layer, bg_rgb, glass_card(pw, ph, radius=10, a_top=178, a_bot=152), px, py, ea * out_a, radius=10)
        a = int(255 * out_a)
        d.rounded_rectangle([px + 8, py + 7, px + 18 + wtag, py + 27], radius=5, fill=YELLOW + (int(238 * ea * out_a),))
        d.text((px + 12, py + 9), 'AHEAD', font=ftag, fill=NAVY + (a,))
        draw_tracked(d, tr['text'], ftxt, px + 26 + wtag, py + 9, WHITE + (a,), 1.2)
    return layer

def beats_layer(bg_rgb, beats, t, expire_t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for i, b in enumerate(beats):
        if b['t0'] > expire_t:
            continue
        slot_key = b.get('slot', SLOT_CYCLE[i % len(SLOT_CYCLE)])
        cx, cy = SLOT_MAP[slot_key]
        BEAT_KINDS[b['kind']](layer, bg_rgb, b, t, cx, cy)
    return layer

# --------------------------------------------------------- ambient layer ----
DUST = [((i * 149.3) % W, (i * 83.7) % H, 0.15 + (i % 5) * 0.04, 3 + (i % 3) * 2) for i in range(12)]
def ambient_layer(t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x0, y0, sp, sz in DUST:
        x = int((x0 + t * sp * 22) % W)
        y = int((y0 - t * sp * 30) % H)
        d.ellipse([x, y, x + sz, y + sz], fill=(205, 230, 255, 22))
    return layer

# ------------------------------------------------------------------ scripts ----
SCRIPTS = {
    'short-johnstown': dict(
        title=('THE CANAL THAT BROKE A CITY', 'CONEMAUGH VALLEY · MAY 31, 1889'),
        end=('FOLLOW', 'Full documentaries + Shorts weekly'),
        out='short-johnstown.mp4',
        narration='short-johnstown.mp3',
        stock_queries=[
            'South Fork Dam Lake Conemaugh Pennsylvania reservoir archival',
            'historic Pennsylvania fishing hunting club lake 1880s',
            'dam spillway screens fish reservoir water',
            'heavy rain reservoir flood dam overflow',
            'historic dam failure flood valley Pennsylvania',
            'flood water train wreckage river debris',
            'historic flood rubble stone bridge fire aftermath',
            'Red Cross disaster relief volunteers historic Pennsylvania',
            'historic courtroom negligence civil liability trial',
        ],
        scenes=[
            dict(a='', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='MAY 31, 1889', sub='14 MILES ABOVE JOHNSTOWN', cam='push_in', focus=(0.5, 0.42)),
            dict(a='wealthy pittsburgh', img='south-fork-fishing-and-hunting-club-club-3.jpg', kicker='A FISHING CLUB PLAYGROUND', sub='SOUTH FORK CLUB', cam='push_in', focus=(0.5, 0.40)),
            dict(a='they filled the spillway', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='THE FATAL MODIFICATIONS', sub='SCREENS · CHOKED SPILLWAY · LOWERED CREST', cam='pan_left', focus=(0.5, 0.45), viz='dam_anatomy'),
            dict(a='six to eight inches', img='south-fork-dam-lake-conemaugh-johnstown--3.jpg', kicker='6–8 INCHES IN 24 HOURS', sub='NOWHERE LEFT TO GO', cam='pull_out', focus=(0.5, 0.42), viz='rain_rising'),
            dict(a='three ten in the often', img='south-fork-dam-lake-conemaugh-johnstown--4.jpg', kicker='3:10 PM · THE DAM FAILS', sub='20M TONS UNLEASHED', cam='push_in', focus=(0.52, 0.45), viz='valley_drop'),
            dict(a='twenty million pounds of water', img='johnstown-train-clean.jpg', kicker='36-FOOT WALL OF WATER', sub='HOMES · TRAINS · 10M LBS DEBRIS', cam='pan_right', focus=(0.52, 0.45), viz='wave_scale'),
            dict(a='the wreckage', img='johnstown-flood-1889-ruins-destruction-h-1.jpg', kicker='62 ACRES BURNED 3 DAYS', sub='THE STONE BRIDGE INFERNO', cam='push_in', focus=(0.48, 0.45), warm=0.18),
            dict(a='the club', img='south-fork-dam-lake-conemaugh-johnstown--1.jpg', kicker='2,209 LIVES LOST', sub='NEVER HELD RESPONSIBLE', cam='pull_out', focus=(0.5, 0.42)),
            dict(a='an act of god', img='south-fork-dam-lake-conemaugh-johnstown--2.jpg', kicker='COURT: "ACT OF GOD"', sub='DAMS FAIL BY DECISIONS', cam='push_in', focus=(0.5, 0.42)),
        ],
        teases=[
            dict(t=10.5, text='THE DAM BREAKS AT 3:10 PM'),
            dict(t=24.0, text='A 36-FOOT WALL OF WATER'),
            dict(t=34.0, text='THE VERDICT THAT NEVER CAME'),
        ],
        sfx_cues=[
            dict(hush=dict(a='twenty million pounds of water', lead=0.55, dur=1.2, depth=0.88)),
            dict(hush=dict(a='an act of god', lead=0.45, dur=1.3, depth=0.88)),
        ],
        beats=[
            dict(a='two thousand dollar', kind='count', num=2000, pre='$', label='BOUGHT FOR — PITTSBURGH BARONS', dur=1.2, slot='C'),
            dict(a='two thousand two hundred', kind='count', num=2209, label='PEOPLE KILLED', dur=1.3, big=True, slot='C'),
            dict(a='private fishing', kind='phrase', words=['PRIVATE', 'FISHING', 'LAKE'], hi=2, slot='TC'),
            dict(a='spillway', kind='phrase', words=['SPILLWAY', 'CHOKED'], hi=0, slot='C'),
            dict(a='drain pipes', kind='phrase', words=['SCREENS', 'ON', 'DRAIN', 'PIPES'], hi=0, slot='C'),
            dict(a='six to eight inches', kind='count', txt='6–8 IN', label='OF RAIN IN 24 HOURS', dur=1.0, slot='C'),
            dict(a='three ten in the often', kind='date', main='3:10 PM', sub='SOUTH FORK DAM FAILS', slot='C'),
            dict(a='twenty million pounds of water', kind='count', num=20, suf='M', label='TONS OF WATER UNLEASHED', dur=1.3, slot='C'),
            dict(a='wall fell to six', kind='count', txt='36 FT', label='WALL OF WATER', dur=1.0, slot='C'),
            dict(a='three days', kind='date', main='3 DAYS', sub='FIRES BURNED AT STONE BRIDGE', slot='C'),
            dict(a='five months', kind='date', main='5 MONTHS', sub='CLARA BARTON & RED CROSS', slot='C'),
            dict(a='an act of god', kind='quote', words=['AN', 'ACT', 'OF', 'GOD'], attrib='— COURT RULING · $0 LIABILITY', slot='C'),
            dict(a='fail by decisions', kind='phrase', words=['FAIL', 'BY', 'DECISIONS'], hi=2, slot='C'),
        ],
        captions=[
            (0, 16, 'In 1889, a $2,000 dam killed 2,209 people.'),
            (17, 24, 'Wealthy Pittsburgh industrialists bought the South Fork Dam'),
            (25, 31, 'just to keep a private fishing lake.'),
            (32, 39, 'They filled the spillway to widen the road,'),
            (40, 53, 'and covered the drain pipes with screens so the game fish could not escape.'),
            (54, 65, 'Then 6 to 8 inches of rain fell in 24 hours.'),
            (66, 77, 'And at 3:10 in the afternoon, the dam gave way.'),
            (78, 89, '20 million tons of water dropped 14 miles in under an hour —'),
            (90, 95, 'a wall 36 feet high.'),
            (96, 101, 'The wreckage burned for 3 days.'),
            (102, 108, 'Clara Barton stayed 5 months.'),
            (109, 114, 'And the club? Never held responsible.'),
            (115, 123, 'For the courts called it an act of God.'),
            (124, 130, 'But dams do not fail by accident.'),
            (131, 134, 'They fail by decisions.'),
        ],
    ),
    'short-enron': dict(
        title=('HOW ENRON DIED', 'HOUSTON, TEXAS · DEC 2, 2001'),
        poster=("WALL STREET'S LIE", '$70B', 'FRAUD', 'GONE IN 24 DAYS'),
        midpoint_poster_window=(23.6, 27.6),
        end=('FOLLOW', 'Money, Explained — new every week'),
        out='short-enron.mp4',
        narration='short-enron.mp3',
        # Live-CI verified documentary video & photography queries (Pexels/Pixabay portrait HD video + Wikimedia/Archive)
        stock_queries=[
            'financial district night city',
            'new york stock exchange trading floor',
            'financial district skyscraper manhattan',
            'newspaper headlines',
            'ledger accounting book',
            'steel mill factory',
            'financial district skyscraper manhattan',
            'bank run',
            'abandoned office room',
            'courtroom judge bench',
        ],
        scenes=[
            dict(a='', img='short-enron-broll-01.jpg', lock_plate=True, kicker='WINTER 2001 · HOUSTON', sub='MOST INNOVATIVE COMPANY UNRAVELS', cam='tilt_up', focus=(0.5, 0.45)),
            dict(a='ninety dollars', img='short-enron-broll-02.jpg', kicker='PEAK: $90.75 / SHARE', sub='NYSE: ENE · AUG 2000', cam='push_in', focus=(0.5, 0.45), viz='stock_boom'),
            dict(a='fortune my busy nostra', img='short-enron-broll-03.jpg', kicker='FORTUNE · 6 YEARS RUNNING', sub='"MOST INNOVATIVE COMPANY"', cam='pull_out', focus=(0.5, 0.45)),
            dict(a='is enron overpriced', img='short-enron-broll-04.jpg', kicker='MAR 2001 · BETHANY McLEAN', sub='"IS ENRON OVERPRICED?"', cam='pan_right', focus=(0.5, 0.48)),
            dict(a='the profits were fiction', img='short-enron-broll-05.jpg', kicker='CFO ANDREW FASTOW', sub='ARCHITECT OF THE ILLUSION', cam='push_in', focus=(0.48, 0.48)),
            dict(a='mom to market accounting', img='short-enron-broll-06.jpg', kicker='MARK-TO-MARKET', sub='10 YRS PROFIT BOOKED DAY ONE', cam='pan_left', focus=(0.5, 0.45), viz='mtm_ledger'),
            dict(a='off the books', img='short-enron-crash-poster.jpg', lock_plate=True, kicker='LJM · RAPTOR · CHEWCO', sub='$30B+ DEBT IN SHELL ENTITIES', cam='push_in', focus=(0.5, 0.45), viz='shell_maze'),
            dict(a='december second', img='short-enron-broll-08.jpg', lock_plate=True, kicker='DEC 2, 2001 · CHAPTER 11', sub='$63.4B RECORD CH. 11 AT FILING', cam='pull_out', focus=(0.5, 0.45), viz='stock_crash'),
            dict(a='twenty thousand employees', img='short-enron-broll-09.jpg', kicker='20,000 JOBS & PENSIONS GONE', sub='85,000 AT ANDERSEN DISSOLVED', cam='pan_right', focus=(0.52, 0.48)),
            dict(a='they called themselves', img='short-enron-broll-10.jpg', kicker='THE RECKONING', sub='FASTOW & SKILLING IMPRISONED', cam='push_in', focus=(0.48, 0.45)),
        ],
        teases=[
            dict(t=6.2, text='ONE QUESTION ENDS IT ALL'),
            dict(t=11.6, text='10 YRS PROFIT BOOKED DAY 1'),
            dict(t=22.0, text='DEC 2 — $63.4B CHAPTER 11'),
        ],
        sfx_cues=[
            dict(hush=dict(a='is enron overpriced', lead=0.50, dur=1.2, depth=0.88)),
            dict(hush=dict(a='december second', lead=0.55, dur=1.3, depth=0.90)),
            dict(hush=dict(a='the company cannot', lead=0.50, dur=1.4, depth=0.85)),
        ],
        beats=[
            dict(a='six years in a row', kind='phrase', words=['6', 'YEARS', 'IN', 'A', 'ROW'], hi=0, slot='C'),
            dict(a='ninety dollars', kind='count', num=90.75, dec=2, pre='$', label='PEAK SHARE PRICE', dur=1.0, slot='C'),
            dict(a='seventy billion dollars', kind='count', num=70, pre='$', suf='B', label='PEAK VALUATION', dur=1.2, slot='C'),
            dict(a='is enron overpriced', kind='quote', hold=3.0, words=['IS', 'ENRON', 'OVERPRICED?'], attrib='— BETHANY McLEAN, FORTUNE', slot='C'),
            dict(a='the profits were fiction', kind='phrase', words=['PROFITS', 'WERE', 'FICTION'], hi=2, slot='C'),
            dict(a='mom to market accounting', kind='phrase', words=['MARK-TO-MARKET'], hi=0, size=26, slot='C'),
            dict(a='off the books partnerships', kind='phrase', words=['OFF-BOOKS', 'PARTNERSHIPS'], hi=0, slot='C'),
            dict(a='december second', kind='date', main='DEC 2, 2001', sub='CHAPTER 11 FILED', slot='C'),
            dict(a='sixty three billion dollars', kind='count', num=63.4, pre='$', suf='B', dec=1, label='IN ASSETS WIPED OUT', dur=1.3, slot='C'),
            dict(a='twenty thousand employees', kind='count', num=20000, label='JOBS & PENSIONS GONE', dur=1.2, slot='C'),
            dict(a='eighty five thousand', kind='count', num=85000, label='AT ANDERSEN DISSOLVED', dur=1.2, slot='C'),
            dict(a='the smartest guys in the room', kind='quote', words=['SMARTEST', 'GUYS', 'IN', 'THE', 'ROOM'], attrib='— ENRON SLOGAN', slot='C'),
            dict(a='it is not making money', kind='quote', words=['IF', 'IT', 'CANNOT', 'EXPLAIN', 'IT,', 'IT\'S', 'NOT', 'MAKING', 'MONEY.'], attrib='— THE LESSON', slot='C'),
        ],
        captions=[
            (0, 11, "Enron was voted America's most innovative company, 6 years in a row."),
            (12, 15, 'Its stock hit $90.'),
            (16, 22, 'The market value passed $70 billion.'),
            (23, 29, 'Then Fortune magazine asked one question:'),
            (30, 32, 'Is Enron overpriced?'),
            (33, 36, 'The profits were fiction'),
            (37, 47, '— projected decades of earnings, booked the day the deal was signed.'),
            (48, 51, 'Mark-to-market accounting,'),
            (52, 57, 'hidden in off-the-books partnerships,'),
            (58, 63, 'run by the chief financial officer.'),
            (64, 73, 'On Dec 2, 2001, Enron filed for bankruptcy.'),
            (74, 79, '$63 billion in assets.'),
            (80, 88, '20,000 employees lost their jobs & pensions.'),
            (89, 96, 'Arthur Andersen — 85,000 people —'),
            (97, 99, 'dissolved overnight.'),
            (100, 108, 'They called themselves the smartest guys in the room.'),
            (109, 117, 'If a company cannot explain how it makes money,'),
            (118, 122, 'it is not making money.'),
            (123, 127, 'Follow for Money, Explained.'),
        ],
    ),
}

def _acquire_short_asset(query, scene_no, stock_dir):
    """Clip-first acquisition tailored for full-bleed 9:16 Shorts.

    Prefers real moving video clips across all providers (Pexels, Pixabay,
    Wikimedia Commons, Internet Archive, NASA) and high-res portrait stock photos
    (Pexels/Pixabay); avoids replacing crisp 9:16 documentary plates with tiny or
    white-background flat scan diagrams when a scene has no matching video clip.
    """
    from pipeline import assets as A
    from pipeline.config import CONFIG

    q = query.strip() or 'financial district skyline'
    video_fns = [
        ('Pexels video', lambda: A._pexels(q, True, W, H)),
        ('Pixabay video', lambda: A._pixabay(q, True, W, H)),
    ]
    photo_fns = [
        ('Pexels photo', lambda: A._pexels(q, False, W, H)),
        ('Pixabay photo', lambda: A._pixabay(q, False, W, H)),
    ]
    if CONFIG.enable_keyless_sources:
        video_fns += [
            ('Wikimedia video', lambda: A._wikimedia(q, True, W, H)),
            ('Internet Archive video', lambda: A._internet_archive(q, True, W, H)),
            ('NASA video', lambda: A._nasa(q, True, W, H)),
        ]
        photo_fns += [
            ('Wikimedia photo', lambda: A._wikimedia(q, False, W, H)),
            ('Openverse photo', lambda: A._openverse(q, False, W, H)),
        ]

    for name, fn in video_fns:
        try:
            got = fn()
        except Exception as exc:
            print(f'[shorts] {name} errored on scene {scene_no}: {exc!r}', flush=True)
            got = None
        if got:
            if got.width and got.height and min(got.width, got.height) < 540:
                print(f'[shorts] skipping low-res video {got.width}x{got.height} on scene {scene_no}', flush=True)
                continue
            if not _is_vivid_video_clip(got.path):
                continue
            got.query = q
            print(f'[shorts] scene {scene_no}: VIDEO from {got.source} ({got.width}x{got.height})', flush=True)
            return got

    # If keyed stock photo exists, or high-res keyless photograph (>=800px) exists:
    for name, fn in photo_fns:
        try:
            got = fn()
        except Exception as exc:
            print(f'[shorts] {name} errored on scene {scene_no}: {exc!r}', flush=True)
            got = None
        if got and (got.source in ('pexels', 'pixabay') or (got.width >= 900 and got.height >= 700)):
            # Verify downloaded photo is photographic (not flat white chart/page scan)
            try:
                sample = Image.open(got.path).convert('RGB').resize((64, 64))
                white_frac = sum(1 for r, g, b in sample.getdata() if r > 235 and g > 235 and b > 235) / 4096.0
                if white_frac > 0.35:
                    print(f'[shorts] skipping flat white scan {got.path.name} ({white_frac:.0%} white); keeping full-bleed documentary plate', flush=True)
                    continue
            except Exception:
                continue
            got.query = q
            print(f'[shorts] scene {scene_no}: PHOTO from {got.source} ({got.width}x{got.height})', flush=True)
            return got
    return None

# -------------------------------------------------------------------- main ----
def main(key):
    cfg = SCRIPTS[key]
    out = os.path.join(ROOT, 'social', cfg['out'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    nar_src = os.path.join(AUDIO, cfg['narration'])
    nar = os.path.join(AUDIO, f'narration-{key}.m4a')
    shutil.copy(nar_src, '/tmp/_short_in.mp3')
    cmd = [FFMPEG, '-y', '-i', '/tmp/_short_in.mp3', '-c:a', 'aac', '-b:a', '160k', nar]
    subprocess.run(cmd, check=True, capture_output=True)
    adur = duration(nar)
    total = adur + 1.6
    n = int(total * FPS)
    words = load_words(key)
    beats = resolve_beats(key, words)
    scenes = resolve_scenes(key, words, total)
    cap_stream = build_caption_stream(key, words)

    if os.environ.get('ENABLE_STOCK_BROLL', '1').strip().lower() not in ('0', 'false', 'no', 'off'):
        try:
            stock_dir = os.path.join(ROOT, 'output', 'short-stock', key)
            os.makedirs(stock_dir, exist_ok=True)
            for si, sc in enumerate(scenes):
                if sc.get('lock_plate'):
                    continue
                queries = cfg.get('stock_queries', [])
                query = queries[si] if si < len(queries) else sc.get('kicker', 'documentary b-roll')
                sc['stock_query'] = query
                asset = _acquire_short_asset(query, si + 1, stock_dir)
                if asset:
                    sc['media_path'] = str(asset.path)
                    sc['media_kind'] = asset.kind
                    sc['source'] = asset.source
                    sc['source_url'] = asset.origin_url
                    sc['license_note'] = asset.license_note
                    sc['source_size'] = (asset.width, asset.height)
        except Exception as exc:
            print(f'  stock sourcing unavailable; using cleared 9:16 documentary plates: {exc!r}')

    print(f'[{key}] narration={adur:.1f}s total={total:.1f}s ({n}f) scenes={len(scenes)} beats={len(beats)}')
    cuts = [sc['t0'] for sc in scenes]
    hushes, swells = build_music_plan(key, words, beats)
    generate_score(key, total, cuts, [], [], hushes, swell_hits=swells)

    plate_cache = {}
    for sc in scenes:
        source_path = sc.get('media_path') or os.path.join(IMG, sc['img'])
        pkey = (source_path, sc.get('warm', 0.0))
        if sc.get('media_kind') == 'video':
            fallback = os.path.join(IMG, sc['img'])
            if not os.path.exists(fallback):
                raise SystemExit(f'missing fallback image {fallback}')
            if fallback not in plate_cache:
                plate_cache[fallback] = prep_plate(fallback, sc.get('warm', 0.0))
            sc['fallback_plate'] = plate_cache[fallback]
            sc['plate'] = None
            print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | VIDEO {sc.get('source')} {sc.get('source_size')} | {os.path.basename(source_path)}")
        else:
            if not os.path.exists(source_path):
                raise SystemExit(f'missing image {source_path}')
            if pkey not in plate_cache:
                plate_cache[pkey] = prep_plate(source_path, sc.get('warm', 0.0))
            sc['plate'] = plate_cache[pkey]
            label = (f"{sc.get('source')} {sc.get('source_size')}" if sc.get('media_path') else sc['img'])
            print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | PHOTO {label}")

    for _line in LICENCE_REPORT(sorted({sc['img'] for sc in scenes if not sc.get('media_path')})):
        print(_line)

    music = os.path.join(AUDIO, f'music-{key}.wav')
    proc = subprocess.Popen(
        [
            FFMPEG, '-y',
            '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
            '-i', nar, '-i', music,
            '-filter_complex', '[2:a]volume=0.58[m];[1:a]aformat=channel_layouts=stereo,volume=1.0[v];[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]',
            '-map', '0:v', '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-maxrate', '2600k', '-bufsize', '5200k',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
            out,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    FADE = 0.42
    nscenes = len(scenes)
    expire_t = adur - 0.5
    active_video_scene = -1
    video_proc = None

    for i in range(n):
        t = i / FPS
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

        if sc.get('media_kind') == 'video':
            if active_video_scene != k:
                stop_video_plate(video_proc)
                try:
                    video_proc = video_plate_reader(sc['media_path'])
                    active_video_scene = k
                except Exception as exc:
                    video_proc = None
                    active_video_scene = -1
                    print(f'  video decode fallback: {exc!r}')
            source = read_video_plate(video_proc) if video_proc else None
            if source is None:
                source = sc['fallback_plate']
                sc['media_kind'] = 'image'
                sc['used_fallback'] = True
                stop_video_plate(video_proc)
                video_proc = None
                active_video_scene = -1
        else:
            stop_video_plate(video_proc)
            video_proc = None
            active_video_scene = -1
            source = sc['plate']

        sc['last_source'] = source
        extra_z = 1.0 + 0.015 * (1.0 - ease_out_cubic(clamp01(pos / FADE))) if (k > 0 and pos < FADE) else 1.0
        frame = camera_frame(source, p, sc.get('cam', 'push_in'), sc.get('focus', (0.5, 0.45)), extra_zoom=extra_z)
        if k > 0 and pos < FADE:
            prev = scenes[k - 1]
            u = pos / FADE
            prev_z = 1.0 + 0.010 * ease_in_out_sine(u)
            prev_plate = prev.get('last_source', prev.get('plate'))
            f_prev = camera_frame(prev_plate, 1.0, prev.get('cam', 'push_in'), prev.get('focus', (0.5, 0.45)), extra_zoom=prev_z)
            frame = optical_flare_transition(f_prev, frame, u)

        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov.alpha_composite(ambient_layer(t))
        mp_win = cfg.get('midpoint_poster_window')
        poster_spec = cfg.get('poster')
        in_mid_poster = bool(mp_win and poster_spec and (mp_win[0] <= t <= mp_win[1]))
        in_open_poster = bool(poster_spec and t < 2.8)
        if not in_open_poster and not in_mid_poster:
            ov.alpha_composite(viz_layer(frame, sc.get('viz'), pos, sc_dur))
            ov.alpha_composite(beats_layer(frame, beats, t, expire_t))
            ov.alpha_composite(tease_layer(frame, cfg.get('teases', []), t))
        if t < 2.8:
            cold_open_overlay(ov, frame, cfg['title'], t, dur=2.8, poster_spec=poster_spec)
        elif in_mid_poster:
            mw0, mw1 = mp_win
            ma_in = ease_out_expo(clamp01((t - mw0) / 0.28))
            ma_out = 1.0 if t < mw1 - 0.32 else 1.0 - ease_in_out_sine((t - (mw1 - 0.32)) / 0.32)
            poster_lockup_overlay(ov, poster_spec[0], poster_spec[1], poster_spec[2], poster_spec[3], alpha=ma_in * ma_out)
        if not in_open_poster and not in_mid_poster:
            ov.alpha_composite(hud_chapter_layer(frame, sc['kicker'], sc.get('sub', ''), k + 1, nscenes, pos, sc_dur, t / total))
            ov.alpha_composite(caption_ribbon_layer(frame, cap_stream, t))
        frame = Image.alpha_composite(frame.convert('RGBA'), ov).convert('RGB')
        if t >= adur - 0.4:
            frame = end_card_overlay(frame, cfg['end'], t - (adur - 0.4), total - (adur - 0.4))
        proc.stdin.write(frame.tobytes())
        if i % 360 == 0:
            print(f'  frame {i}/{n}', flush=True)

    stop_video_plate(video_proc)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit('encode failed')

    report = []
    for si, sc in enumerate(scenes):
        report.append(dict(
            scene=si + 1,
            query=(cfg.get('stock_queries') or [''] * len(scenes))[si],
            media=('authored photo fallback' if not sc.get('media_path') or sc.get('used_fallback') else sc.get('media_kind')),
            provider=sc.get('source', 'existing story archive'),
            source_url=sc.get('source_url', ''),
            license=(sc.get('license_note') if sc.get('media_path') else LICENCE_NOTE(sc.get('img', ''))),
            dimensions=sc.get('source_size', None),
            fallback=(not bool(sc.get('media_path')) or bool(sc.get('used_fallback', False))),
            file=sc.get('media_path', sc.get('img', '')),
        ))
    report_dir = os.path.join(ROOT, 'output', 'short-stock', key)
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, 'scene-sources.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print('source log', os.path.join(report_dir, 'scene-sources.json'))
    print('done', out, os.path.getsize(out) // 1024, 'KB')

if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'short-johnstown'
    if arg not in SCRIPTS:
        raise SystemExit(f'unknown script {arg!r} — choose from {sorted(SCRIPTS)}')
    main(arg)
