#!/usr/bin/env python3
"""Prayer-first 16:9 long-form renderer for The Secret Place.

Renders approved scripture/devotional scenes with measured narration timing,
licensed or existing prayer visuals, local FFmpeg encoding, and prayer-specific
word-synchronised captions.

Run: .venv/bin/python tools/deep_dive.py psalm91
"""
import os, sys, json, math, subprocess, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import generate_score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,ROOT)  # shared free-stock acquisition adapters
# Authored-still licence ledger. Falls back to the old blanket string if the pipeline
# package is unavailable, so a bookkeeping module can never break a render.
try:
    from pipeline.licences import licence_note as LICENCE_NOTE, licence_report as LICENCE_REPORT
except Exception:  # pragma: no cover - import guard only
    LICENCE_NOTE = lambda name: ('pre-existing image-search still; source/license metadata '
                                 'unavailable in current ledger — verify before monetized reuse')
    LICENCE_REPORT = lambda names: []
W, H, FPS = 1280, 720, 24
CW, CH = 1920, 1080  # 1.5x super-sampled plate canvas for sub-pixel camera

NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
CRIMSON = (255, 86, 92)
EMERALD = (72, 232, 164)
WHITE = (255, 255, 255)
FAINT = (122, 156, 202)
ICE = (170, 210, 248)

# ffmpeg resolution: same precedence as pipeline.assemble.ffmpeg_bin() —
# FFMPEG_BINARY (when it actually resolves) > PATH > the imageio-ffmpeg static
# build pinned in requirements.txt. This line used to be
# `os.environ.get('FFMPEG_BINARY', 'ffmpeg')`, which hard-failed on any machine
# with no system ffmpeg even though a static build was already installed, and
# which honoured a bare `FFMPEG_BINARY=ffmpeg` (remaster.yml) that resolves to
# nothing at all.
try:
    from pipeline.assemble import ffmpeg_bin as _resolve_ffmpeg
except Exception:  # pragma: no cover - pipeline package unavailable
    def _resolve_ffmpeg():
        return os.environ.get('FFMPEG_BINARY') or 'ffmpeg'
FFMPEG = _resolve_ffmpeg()
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

def apply_shake(img, t, impacts):
    """DOCOGA REELS v2: Damped high-frequency camera micro-shake on impacts."""
    for ti in impacts:
        dt = t - ti
        if 0.0 <= dt < 0.22:
            a = 1.0 - dt / 0.22
            dx = int(4.5 * a * math.sin(46.0 * dt))
            dy = int(3.0 * a * math.cos(39.0 * dt))
            return ImageChops.offset(img, dx, dy)
    return img

PRAYER_IMPACTS = [0.0, 6.23, 13.41, 20.03, 24.17, 28.49, 32.42, 35.49]

SACRED_KICKERS = [
    'DIVINE PROTECTION COVENANT',
    'PSALM 91 : 1',
    'PSALM 91 : 10',
    'PRAYER FOR STILLNESS',
    'ANGELIC PROTECTION',
    'DIVINE PEACE',
    'EXODUS 14 : 14',
    'THE SECRET PLACE',
]

WHITE_IMG = Image.new('RGB', (W, H), (255, 255, 255))

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

def prep_plate(path, focus_side=0.0, tint_warm=0.0, mode='matte'):
    """Aspect-safe 16:9 plate: preserve the full source, never crop/stretch it.
    When mode='fill' (used for full-bleed widescreen prayer plates), scales to cover (CW, CH)."""
    raw = Image.open(path).convert('RGB')
    if mode == 'fill':
        scale = max(CW / max(1, raw.width), CH / max(1, raw.height))
        rw, rh = int(round(raw.width * scale)), int(round(raw.height * scale))
        raw = raw.resize((rw, rh), Image.Resampling.LANCZOS)
        x = (CW - rw) // 2
        y = (CH - rh) // 2
        canvas = Image.new('RGB', (CW, CH), (4, 12, 29))
        canvas.paste(raw, (x, y))
        fg = grade_blue(canvas.filter(ImageFilter.UnsharpMask(radius=1.25, percent=100, threshold=3)), tint_warm=tint_warm)
        return fg
    fit=min((CW*.86)/max(1,raw.width),(CH*.86)/max(1,raw.height))
    raw=raw.resize((max(1,int(round(raw.width*fit))),max(1,int(round(raw.height*fit)))),Image.Resampling.LANCZOS)
    avg=raw.resize((1,1),Image.Resampling.BILINEAR).getpixel((0,0))
    glow_col=(min(30,int(avg[0]*.12)),min(52,int(avg[1]*.18)),min(92,int(avg[2]*.24)))
    canvas=Image.new('RGB',(CW,CH),(4,12,29)); glow=Image.new('RGB',(CW,CH),(0,0,0)); d=ImageDraw.Draw(glow)
    d.ellipse((CW*.04,CH*.08,CW*.96,CH*.92),fill=glow_col)
    canvas=Image.blend(canvas,glow.filter(ImageFilter.GaussianBlur(120)),0.82)
    fg=grade_blue(raw.filter(ImageFilter.UnsharpMask(radius=1.25,percent=100,threshold=3)),tint_warm=tint_warm)
    cx=int(CW*(0.5+0.035*focus_side)); cy=CH//2; x=cx-fg.width//2; y=cy-fg.height//2
    shade=Image.new('RGBA',(CW,CH),(0,0,0,0)); sd=ImageDraw.Draw(shade)
    sd.rectangle((x-5,y-5,x+fg.width+5,y+fg.height+5),fill=(0,0,0,150),outline=(120,180,245,150),width=3)
    canvas=Image.alpha_composite(canvas.convert('RGBA'),shade.filter(ImageFilter.GaussianBlur(9))).convert('RGB')
    canvas.paste(fg,(x,y))
    return canvas


def video_plate_reader(path):
    iw,ih=int(CW*.86),int(CH*.86)
    vf=f'scale={iw}:{ih}:force_original_aspect_ratio=decrease,setsar=1,pad={CW}:{CH}:(ow-iw)/2:(oh-ih)/2:color=0x061a33,fps={FPS},format=rgb24'
    return subprocess.Popen([FFMPEG,'-loglevel','error','-stream_loop','-1','-i',str(path),'-an','-vf',vf,'-f','rawvideo','-pix_fmt','rgb24','pipe:1'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=10**7)


def read_video_plate(proc):
    if not proc or proc.stdout is None:return None
    size=CW*CH*3; data=bytearray()
    while len(data)<size:
        part=proc.stdout.read(size-len(data))
        if not part:return None
        data.extend(part)
    return grade_blue(Image.frombytes('RGB',(CW,CH),bytes(data)))


def stop_video_plate(proc):
    if not proc:return
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:proc.kill(); proc.wait(timeout=2)
    if proc.stdout:
        try:proc.stdout.close()
        except OSError:pass

# --------------------------------------- sub-pixel smooth camera movement ----
def camera_frame(plate, p, mode='push_in', focus=(0.5, 0.48), extra_zoom=1.0):
    """True sub-pixel floating-point camera rig using Image.EXTENT + BICUBIC.

    Smooth cosine S-curve blended with linear momentum so camera never freezes
    and never integer-steps.
    """
    p = clamp01(p)
    s = 0.65 * ease_in_out_sine(p) + 0.35 * p
    fx, fy = focus

    # Restrained sub-pixel moves stay within the source-safe matte; no source edge is lost.
    if mode == 'push_in':
        z=1.0+0.045*s; dx=(fx-0.5)*0.035*s; dy=(fy-0.5)*0.025*s
    elif mode == 'pull_out':
        z=1.045-0.045*s; dx=(fx-0.5)*0.03*(1.0-s); dy=(fy-0.5)*0.02*(1.0-s)
    elif mode == 'pan_right':
        z=1.025+0.015*s; dx=-0.0125+0.025*s; dy=(fy-0.5)*0.02*s
    elif mode == 'pan_left':
        z=1.025+0.015*s; dx=0.0125-0.025*s; dy=(fy-0.5)*0.02*s
    elif mode == 'tilt_up':
        z=1.025+0.015*s; dx=(fx-0.5)*0.02*s; dy=0.01-0.02*s
    else:
        z=1.005+0.035*s; dx=0.006*math.sin(p*math.pi); dy=-0.012*s
    z *= extra_zoom
    dx += 0.00035*math.sin(p*6.1+1.3)
    dy += 0.0003*math.sin(p*4.3+2.7)
    z *= 1.0+0.001*math.sin(p*2.4+0.6)
    vw = CW / z
    vh = CH / z
    cx = CW * (0.5 + dx)
    cy = CH * (0.5 + dy)
    x0 = max(0.0, min(CW - vw, cx - vw * 0.5))
    y0 = max(0.0, min(CH - vh, cy - vh * 0.5))
    im = plate.transform((W, H), Image.EXTENT, (x0, y0, x0 + vw, y0 + vh), Image.BICUBIC)
    return Image.composite(im, VIG_DARK, VIG)

def optical_flare_transition(f_prev, f_curr, u, is_prayer=False):
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
    flare_glow = (255, 235, 170, int(68 * inten)) if is_prayer else (165, 215, 255, int(72 * inten))
    flare_core = (255, 248, 220, int(95 * inten)) if is_prayer else (255, 225, 130, int(90 * inten))
    d.ellipse([-120, cy - band_h, W + 120, cy + band_h], fill=flare_glow)
    d.rectangle([0, cy - 3, W, cy + 3], fill=flare_core)
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

PHRASE_FONT_CACHE = {}
def fit_phrase_font(lines, base_sz=44, max_safe=960, tracking=1.8):
    sz = base_sz
    f = fnt('Black', sz)
    d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    while sz > 22:
        overflow = False
        for line in lines:
            if not line:
                continue
            words_l = line.split()
            w_words = [sum(d.textlength(ch, font=f) + tracking for ch in w) - tracking for w in words_l]
            space_w = d.textlength(' ', font=f) + tracking
            line_w = sum(w_words) + space_w * (len(words_l) - 1)
            if line_w > max_safe:
                overflow = True
                break
        if not overflow:
            break
        sz -= 2
        f = fnt('Black', sz)
    return sz, f

def get_phrase_font(lines, base_sz=44, max_safe=960, tracking=1.8):
    key = (tuple(lines), base_sz, max_safe, tracking)
    if key not in PHRASE_FONT_CACHE:
        PHRASE_FONT_CACHE[key] = fit_phrase_font(lines, base_sz, max_safe, tracking)
    return PHRASE_FONT_CACHE[key]

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
def hud_chapter_layer(kicker, sub, idx, nscenes, t_scene, scene_dur, total_frac, is_prayer=False):
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
        border_col = (235, 198, 92, 175) if is_prayer else (126, 184, 255, 165)
        layer.alpha_composite(card_alpha(glass_card(cw, ch, radius=14, a_top=210, a_bot=175, border_col=border_col), a), (cx, cy))
        pill_fill = (218, 165, 32, int(240 * a)) if is_prayer else YELLOW + (int(240 * a),)
        pill_txt_fill = (10, 24, 48, int(255 * a)) if is_prayer else NAVY + (int(255 * a),)
        d.rounded_rectangle([cx + 12, cy + 12, cx + 92, cy + 34], radius=6, fill=pill_fill)
        wt = d.textlength(tag, font=fc)
        d.text((cx + 52 - wt / 2, cy + 15), tag, font=fc, fill=pill_txt_fill)
        draw_tracked(d, kicker, fk, cx + 104, cy + 11, WHITE + (int(250 * a),), 1.8)
        if sub:
            draw_tracked(d, sub, fs, cx + 104, cy + 39, (220, 238, 255) if is_prayer else ICE + (215,), 2.0)

    # Top-right progress pill + bottom edge bar
    d = ImageDraw.Draw(layer)
    pw, ph = 158, 36
    px, py = W - pw - 36, 28
    border_col_r = (235, 198, 92, 175) if is_prayer else (126, 184, 255, 165)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18, a_top=195, a_bot=160, border_col=border_col_r), 0.92), (px, py))
    fp = fnt('Bold', 14)
    pct = f'{int(clamp01(total_frac) * 100):3d}%'
    pill_label = 'PRAYER' if is_prayer else 'DOC'
    d.text((px + 16, py + 9), pill_label, font=fp, fill=(255, 235, 180) if is_prayer else ICE + (210,))
    bar_x0 = px + 74 if is_prayer else px + 56
    bar_w = 38 if is_prayer else 56
    d.rectangle([bar_x0, py + 15, bar_x0 + bar_w, py + 21], fill=(255, 255, 255, 45))
    fill_w = int(bar_w * clamp01(total_frac))
    if fill_w > 0:
        d.rectangle([bar_x0, py + 15, bar_x0 + fill_w, py + 21], fill=(255, 218, 64) if is_prayer else YELLOW + (240,))
    d.text((px + 118, py + 9), pct, font=fp, fill=WHITE + (235,))

    # Full-width thin bottom progress bar
    d.rectangle([0, H - 5, W, H], fill=(255, 255, 255, 32))
    bx = int(W * clamp01(total_frac))
    if bx > 0:
        d.rectangle([0, H - 5, bx, H], fill=(255, 218, 64) if is_prayer else YELLOW + (235,))
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
    ph = 56
    px = W // 2 - pw // 2
    py = H - 78
    gc = glass_card(pw, ph, radius=16, top=(6, 22, 52), bot=(3, 12, 30), a_top=232, a_bot=215, border_col=(235, 198, 92, 185))
    layer.alpha_composite(card_alpha(gc, a), (px, py))

    # Find currently spoken word index
    cur_idx = 0
    for j, (ws, we, _) in enumerate(words):
        if t >= ws - 0.04:
            cur_idx = j

    x = W / 2.0 - total_w / 2.0
    for j, ((ws, we, w), ww) in enumerate(zip(words, widths)):
        txt = w.upper()
        is_active = (j == cur_idx)
        is_spoken = (j < cur_idx)

        # Directional contact drop shadow
        shadow_a = int(220 * a) if (is_active or is_spoken) else int(100 * a)
        d.text((x, py + 14), txt, font=f, fill=(0, 0, 0, shadow_a))

        if is_active:
            # Active word golden glow aura + highlight pill
            pad_x = 8
            d.rounded_rectangle([x - pad_x, py + 7, x + ww + pad_x, py + ph - 7],
                                radius=8, fill=(255, 201, 60, int(52 * a)),
                                outline=(255, 218, 64, int(185 * a)), width=2)
            # Ambient luminous bloom
            for gx, gy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                d.text((x + gx, py + 11 + gy), txt, font=f, fill=(255, 215, 40, int(140 * a)))
            d.text((x, py + 11), txt, font=f, fill=(255, 222, 60, int(255 * a)))
        elif is_spoken:
            d.text((x, py + 12), txt, font=f, fill=WHITE + (int(250 * a),))
        else:
            d.text((x, py + 12), txt, font=f, fill=(215, 235, 255, int(130 * a)))
        x += ww + gap
    return layer

SACRED_KICKERS = [
    'DIVINE PROTECTION COVENANT',
    'PSALM 91 : 1',
    'PSALM 91 : 10',
    'PRAYER FOR STILLNESS',
    'ANGELIC PROTECTION',
    'DIVINE PEACE',
    'EXODUS 14 : 14',
    'THE SECRET PLACE',
]

def align_card_words_to_speech(card_words, seg_words, default_t0, default_t1):
    """Word-to-word chronological alignment within the sentence segment."""
    import re
    def _clean(w):
        w = w.lower().replace('&', 'and')
        return re.sub(r'[^a-z0-9]', '', w)

    aligned = []
    seg_idx = 0
    for cw in card_words:
        cw_clean = _clean(cw)
        found = False
        for si in range(seg_idx, len(seg_words)):
            sw = _clean(seg_words[si][2])
            if cw_clean == sw or (cw_clean == '91' and 'ninety' in sw) or (cw_clean in sw and len(cw_clean) >= 3):
                t0 = seg_words[si][0]
                t1 = seg_words[si][1]
                if cw_clean == '91' and si + 1 < len(seg_words) and 'one' in _clean(seg_words[si+1][2]):
                    t1 = seg_words[si+1][1]
                    seg_idx = si + 2
                else:
                    seg_idx = si + 1
                aligned.append((t0, t1))
                found = True
                break
        if not found:
            prev_t = aligned[-1][1] if aligned else default_t0
            aligned.append((prev_t, prev_t + 0.35))
    return aligned

def build_kinetic_stream(key, raw_words):
    phrases_def = SCRIPTS[key].get('kinetic_phrases')
    if not phrases_def:
        return []
    stream = []
    for idx, entry in enumerate(phrases_def):
        if len(entry) == 5 and isinstance(entry[2], (list, tuple)):
            w0, w1, lines_list, acc, kck = entry
            lines = list(lines_list)
            l1 = lines[0] if len(lines) > 0 else ''
            l2 = lines[1] if len(lines) > 1 else ''
        elif len(entry) == 4 and isinstance(entry[2], (list, tuple)):
            w0, w1, lines_list, acc = entry
            lines = list(lines_list)
            l1 = lines[0] if len(lines) > 0 else ''
            l2 = lines[1] if len(lines) > 1 else ''
            kck = SACRED_KICKERS[idx] if idx < len(SACRED_KICKERS) else 'COVENANT OF PEACE'
        elif len(entry) == 6:
            w0, w1, l1, l2, acc, kck = entry
            lines = [l for l in (l1, l2) if l]
        else:
            w0, w1, l1, l2, acc = entry
            lines = [l for l in (l1, l2) if l]
            kck = SACRED_KICKERS[idx] if idx < len(SACRED_KICKERS) else 'COVENANT OF PEACE'
        seg = raw_words[w0:w1 + 1]
        t_start = seg[0][0]
        t_end = seg[-1][1]
        all_cwords = [w for l in lines for w in l.split()]
        word_timings = align_card_words_to_speech(all_cwords, seg, t_start, t_end)
        stream.append(dict(
            t0=t_start,
            t1=t_end,
            lines=lines,
            line1=l1,
            line2=l2,
            accent_words=acc,
            kicker=kck,
            words=seg,
            card_words=all_cwords,
            word_timings=word_timings,
        ))

    # Sentence-level display windows: advance immediately to next sentence when speech finishes;
    # zero delay, zero lingering on old text that the voice has already passed
    for i in range(len(stream)):
        if i == 0:
            stream[i]['disp_t0'] = 0.0
        else:
            stream[i]['disp_t0'] = stream[i - 1]['t1']

    for i in range(len(stream)):
        if i + 1 < len(stream):
            stream[i]['disp_t1'] = stream[i]['t1']
        else:
            stream[i]['disp_t1'] = 39.55
    return stream

def kinetic_typography_layer(bg_rgb, stream, t, is_prayer=False):
    """Rock-solid After Effects-style kinetic typography motion text design:
    zero scale-pulse wobble, microsecond-aligned to what is being spoken,
    infused with DOCOGA REELS v2 tracked kickers, gold underline sweeps, and expanding sacred rings,
    adapted for 16:9 widescreen format."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if not stream:
        return layer

    active = None
    item_idx = 0
    for idx, item in enumerate(stream):
        if item['disp_t0'] <= t < item['disp_t1']:
            active = item
            item_idx = idx
            break
    if not active:
        return layer

    t0 = active['disp_t0']
    t1 = active['disp_t1']
    dt = t - t0
    alpha = 1.0

    cy = 380  # Vertically centered in 1280x720 widescreen frame
    lines = active.get('lines') or [l for l in [active.get('line1'), active.get('line2')] if l]
    base_sz = 38 if len(lines) >= 5 else (42 if len(lines) == 4 else (48 if len(lines) == 3 else 54))
    max_safe = 960  # Widescreen safe width leaving 160px on each side
    tr = 1.8
    f_size, f = get_phrase_font(lines, base_sz=base_sz, max_safe=max_safe, tracking=tr)

    line_h = int(f_size * 1.25)
    total_h = len(lines) * line_h
    y_start = cy - total_h / 2.0

    # DOCOGA REELS v2: Expanding sacred halo ring on key spiritual declarations
    if is_prayer and item_idx in (1, 2, 4, 6, 7):
        if dt < 0.60:
            p_ring = clamp01(dt / 0.60)
            rr = int(80 + 200 * ease_out_cubic(p_ring))
            wdt = max(2, int(6 * (1.0 - p_ring)))
            ring_a = int(140 * (1.0 - p_ring) * alpha)
            if ring_a > 0:
                rd = ImageDraw.Draw(layer)
                rd.ellipse([W // 2 - rr, cy - rr, W // 2 + rr, cy + rr], outline=(255, 218, 64, ring_a), width=wdt)

    GOLD = (255, 218, 64)
    WHITE = (255, 255, 255)

    y_pad_top = 44
    text_canvas = Image.new('RGBA', (W, total_h + 160), (0, 0, 0, 0))
    td = ImageDraw.Draw(text_canvas)

    # DOCOGA REELS v2: Tracked-in kicker header above the main typography lines
    kicker_txt = active.get('kicker', '')
    if kicker_txt and is_prayer:
        if t == 0.0:
            kp = 1.0
            ktr = 4
            ka = 1.0
        else:
            kp = clamp01(dt / 0.32)
            ktr = int(14 - 10 * ease_out_cubic(kp))  # collapses 14 -> 4px
            ka = ease_out_cubic(clamp01(dt / 0.24)) * alpha
        fk = fnt('SemiBold', 15)
        kw = sum(td.textlength(ch, font=fk) + ktr for ch in kicker_txt) - ktr
        kx = (W - kw) / 2.0
        ky = 14

        # Directional contact shadow for kicker
        cur_x = kx
        for ch in kicker_txt:
            td.text((cur_x, ky + 2), ch, font=fk, fill=(0, 0, 0, int(185 * ka)))
            cur_x += td.textlength(ch, font=fk) + ktr

        # Celestial amber/gold tracked kicker
        kicker_col = (255, 228, 130)
        cur_x = kx
        for ch in kicker_txt:
            td.text((cur_x, ky), ch, font=fk, fill=kicker_col + (int(245 * ka),))
            cur_x += td.textlength(ch, font=fk) + ktr

    line_ws = []
    w_idx = 0
    word_timings = active.get('word_timings', [])
    for li, line in enumerate(lines):
        words = line.split()
        w_words = [sum(td.textlength(ch, font=f) + tr for ch in w) - tr for w in words]
        space_w = td.textlength(' ', font=f) + tr
        line_w = sum(w_words) + space_w * (len(words) - 1)
        line_ws.append(line_w)
        x = (W - line_w) / 2.0
        y = y_pad_top + li * line_h

        for w, ww in zip(words, w_words):
            w_t0, w_t1 = word_timings[w_idx] if w_idx < len(word_timings) else (0.0, 999.0)
            w_idx += 1

            # Word-level sync states within sentence segment:
            # Word illuminates in radiant gold the exact instant spoken (w_t0 <= t < w_t1).
            # Settles into crisp solid white the exact instant finished (t >= w_t1).
            # Zero delay, zero lagging behind what the voice has already passed.
            is_spoken = (t >= w_t1)
            is_active = (w_t0 <= t < w_t1)
            is_upcoming = (t < w_t0)

            is_accent = any(aw in w for aw in active.get('accent_words', []))

            if is_active:
                col = (255, 222, 60, int(255 * alpha))          # Blazing active gold
                glow_col = (255, 215, 40, int(195 * alpha))     # Intense luminous aura
                shadow_a = int(245 * alpha)
                y_off = -2                                       # Dynamic physical lift pop
            elif is_spoken:
                col = (255, 218, 64, int(255 * alpha)) if is_accent else (255, 255, 255, int(255 * alpha))
                glow_col = (255, 215, 60, int(50 * alpha)) if is_accent else (220, 240, 255, int(40 * alpha))
                shadow_a = int(210 * alpha)
                y_off = 0
            else:  # is_upcoming
                col = (215, 235, 255, int(120 * alpha))         # Soft translucent white
                glow_col = None
                shadow_a = int(90 * alpha)
                y_off = 0

            # Directional contact drop shadow (3 passes for 3D depth)
            for sx, sy, sa in [(0, 3, shadow_a), (0, 6, int(shadow_a * 0.75)), (0, 11, int(shadow_a * 0.50))]:
                cur_x = x
                for ch in w:
                    td.text((cur_x + sx, y + y_off + sy), ch, font=f, fill=(0, 0, 0, sa))
                    cur_x += td.textlength(ch, font=f) + tr

            # Active/accent ambient luminous glow around display characters
            if glow_col:
                cur_x = x
                passes = [(-2, 0), (2, 0), (0, -2), (0, 2)] if is_active else [(-1, 0), (1, 0), (0, -1), (0, 1)]
                for ch in w:
                    for gx, gy in passes:
                        td.text((cur_x + gx, y + y_off + gy), ch, font=f, fill=glow_col)
                    cur_x += td.textlength(ch, font=f) + tr

            # Main word typography
            cur_x = x
            for ch in w:
                td.text((cur_x, y + y_off), ch, font=f, fill=col)
                cur_x += td.textlength(ch, font=f) + tr
            x += ww + space_w

    # DOCOGA REELS v2: Kinetic Gold Underline Sweep beneath bottom line
    if (dt > 0.08 or t == 0.0) and is_prayer and line_ws:
        g = 1.0 if t == 0.0 else ease_out_cubic(clamp01((dt - 0.08) / 0.28))
        target_w = min(line_ws[-1] * 0.92, 540)
        ul_w = target_w * g
        ul_x0 = (W - target_w) / 2.0
        ul_y = y_pad_top + total_h + 8

        # Amber glow backing
        td.rounded_rectangle([ul_x0 - 2, ul_y - 2, ul_x0 + ul_w + 2, ul_y + 5], radius=3, fill=(255, 200, 40, int(85 * alpha)))
        # Pure gold bar
        td.rounded_rectangle([ul_x0, ul_y, ul_x0 + ul_w, ul_y + 3], radius=2, fill=(255, 222, 70, int(245 * alpha)))

    # Ambient deep shadow bloom
    ambient = text_canvas.split()[3].filter(ImageFilter.GaussianBlur(14))
    ambient_layer_img = Image.new('RGBA', text_canvas.size, (0, 0, 0, 0))
    ambient_layer_img.paste((0, 0, 0, int(195 * alpha)), (0, 0), mask=ambient)

    combined = Image.alpha_composite(ambient_layer_img, text_canvas)
    layer.alpha_composite(combined, (0, int(y_start - y_pad_top)))

    return layer

# ---------------------------------------------------------- word sync ----
def load_words(key):
    words_key = SCRIPTS.get(key, {}).get('words', key)
    path = os.path.join(AUDIO, f'words-{words_key}.json')
    if not os.path.exists(path):
        alt = os.path.join(AUDIO, f'words-short-{words_key}.json')
        if os.path.exists(alt):
            path = alt
        else:
            raise SystemExit(f'missing {path}')
    return json.load(open(path, 'r', encoding='utf-8'))

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
def build_music_plan(key, words, beats):
    """Music automation only — score swells + emotional hushes.

    Per the creative brief there are NO sound effects in the mix: the audio bed
    is narration + score. Hushes (from the cue sheet) duck the score before the
    heaviest spoken lines; swells lift it at count-up landings and quotes.
    Returns (hushes, swell_hits)."""
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
        hushes.append(dict(t=hit[0][0], dur=h.get('dur', 1.2),
                           depth=h.get('depth', 0.85), lead=h.get('lead', 0.5)))
    return hushes, swells

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

def tease_layer(teases, t):
    """Retention open-loops: 'AHEAD — …' pill above the caption ribbon."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for tr in teases:
        t0 = tr['t']
        if t < t0 or t > t0 + 2.9:
            continue
        ea = ease_out_expo(clamp01((t - t0) / 0.5))
        out_a = 1.0 - clamp01((t - (t0 + 2.25)) / 0.5)
        dy = (1 - ea) * -36
        ftag = fnt('Black', 16)
        ftxt = fnt('Bold', 21)
        d = ImageDraw.Draw(layer)
        wtag = tracked_width(d, 'AHEAD', ftag, 3.0)
        wtxt = tracked_width(d, tr['text'], ftxt, 1.8)
        pw = int(wtag + wtxt + 88)
        ph = 48
        px = W // 2 - pw // 2
        py = int(556 + dy)
        layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=12), ea * out_a), (px, py))
        a = int(255 * out_a)
        d.rounded_rectangle([px + 14, py + 11, px + 30 + wtag, py + 37], radius=6,
                            fill=YELLOW + (int(235 * ea * out_a),))
        d.text((px + 22, py + 14), 'AHEAD', font=ftag, fill=NAVY + (a,))
        d.text((px + 48 + wtag, py + 12), tr['text'], font=ftxt, fill=WHITE + (a,))
    return layer

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
    'psalm91': dict(
        title=('THE SECRET PLACE', 'PSALM 91 \u00B7 PRAYER OF DIVINE PROTECTION'),
        end=('SUBSCRIBE', 'The Secret Place \u2014 daily prayer and scripture'),
        narration='short-prayer-psalm91.mp3',
        words='psalm91',
        out='deep-dive-psalm91.mp4',
        stock_queries=[
            'calm mountain lake sunset water reflection',
            'sun rays breaking clouds mountains',
            'ancient castle mountain starry night',
            'candle burning dark room night prayer',
            'milky way galaxy starry night sky',
            'candle burning dark room night prayer',
            'golden sunrise lake mist morning',
            'calm mountain lake sunset water reflection',
        ],
        scenes=[
            dict(a='', img='long-prayer-scene-01.jpg', kicker='PSALM 91:1', sub='NIGHT PROTECTION PRAYER', cam='tilt_up', focus=(0.5, 0.45)),
            dict(a='he who dwells', img='long-prayer-scene-02.jpg', kicker='HE WHO DWELLS', sub='IN THE SECRET PLACE', cam='push_in', focus=(0.5, 0.45)),
            dict(a='no evil shall', img='long-prayer-scene-05.jpg', kicker='PSALM 91:10', sub='NO EVIL SHALL BEFALL YOU', cam='push_in', focus=(0.5, 0.42)),
            dict(a='heavenly father', img='long-prayer-scene-03.jpg', kicker='PRAYER FOR PEACE', sub='QUIET EVERY ANXIOUS THOUGHT', cam='pan_right', focus=(0.5, 0.48)),
            dict(a='send your angels', img='long-prayer-scene-06.jpg', kicker='ANGELIC PROTECTION', sub='GUARD THIS HOME', cam='pull_out', focus=(0.48, 0.48)),
            dict(a='let your divine peace', img='long-prayer-scene-03.jpg', kicker='DIVINE PEACE', sub='FILL THIS ROOM WALL TO WALL', cam='tilt_up', focus=(0.5, 0.50)),
            dict(a='sleep in peace', img='long-prayer-scene-04.jpg', kicker='REST IN GOD', sub='HE FIGHTS YOUR BATTLES', cam='pan_left', focus=(0.5, 0.45)),
            dict(a='receive this protection', img='long-prayer-scene-01.jpg', kicker='DIVINE SHIELD', sub='TYPE AMEN & SUBSCRIBE', cam='push_in', focus=(0.5, 0.45)),
        ],
        teases=[],
        sfx_cues=[
            dict(hush=dict(a='he who dwells', lead=0.35, dur=1.0, depth=0.85)),
            dict(hush=dict(a='heavenly father', lead=0.35, dur=1.0, depth=0.85)),
            dict(hush=dict(a='sleep in peace', lead=0.35, dur=1.0, depth=0.85)),
        ],
        beats=[
            dict(a='secret place', kind='quote', words=['SECRET', 'PLACE', 'OF', 'THE', 'MOST', 'HIGH'], attrib='\u2014 PSALM 91:1', slot='C'),
            dict(a='under the shadow', kind='phrase', words=['UNDER', 'HIS', 'SHADOW'], hi=0, slot='C'),
            dict(a='no evil shall', kind='quote', words=['NO', 'EVIL', 'SHALL', 'BEFALL', 'YOU'], attrib='\u2014 PSALM 91:10', slot='C'),
            dict(a='guard this home', kind='phrase', words=['ANGELS', 'GUARD', 'YOUR', 'HOME'], hi=0, slot='C'),
            dict(a='divine peace', kind='phrase', words=['DIVINE', 'PEACE', 'IN', 'THIS', 'ROOM'], hi=0, slot='C'),
            dict(a='god is fighting', kind='phrase', words=['GOD', 'FIGHTS', 'YOUR', 'BATTLES'], hi=0, slot='C'),
            dict(a='type amen', kind='phrase', words=['TYPE', 'AMEN', 'FOR', 'PROTECTION'], hi=1, slot='C'),
        ],
        captions=[
            (0, 19, 'Before you close your eyes tonight, take a deep breath, and place your home and family under Psalm 91.'),
            (20, 38, 'He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty.'),
            (39, 51, 'No evil shall befall you, nor shall any plague come near your dwelling.'),
            (52, 58, 'Heavenly Father, quiet every anxious thought tonight.'),
            (59, 69, 'Send your angels to guard this home, wash away every fear,'),
            (70, 81, 'and let your divine peace fill this room from wall to wall.'),
            (82, 92, 'Sleep in peace tonight, knowing that God is fighting your battles.'),
            (93, 107, 'If you receive this protection, type Amen, and subscribe to pray with us every day.'),
        ],
        kinetic_phrases=[
            (0, 19, [
                'BEFORE YOU CLOSE',
                'YOUR EYES TONIGHT',
                'TAKE A DEEP BREATH',
                'AND PLACE YOUR HOME & FAMILY',
                'UNDER PSALM 91',
            ], ['CLOSE', 'EYES', 'TONIGHT', 'BREATH', 'PSALM', '91'], 'DIVINE PROTECTION COVENANT'),
            (20, 38, [
                'HE WHO DWELLS',
                'IN THE SECRET PLACE',
                'OF THE MOST HIGH',
                'SHALL ABIDE UNDER THE SHADOW',
                'OF THE ALMIGHTY',
            ], ['DWELLS', 'SECRET', 'PLACE', 'MOST', 'HIGH', 'SHADOW', 'ALMIGHTY'], 'PSALM 91 : 1'),
            (39, 51, [
                'NO EVIL SHALL BEFALL YOU',
                'NOR SHALL ANY PLAGUE',
                'COME NEAR YOUR DWELLING',
            ], ['NO', 'EVIL', 'BEFALL', 'PLAGUE', 'DWELLING'], 'PSALM 91 : 10'),
            (52, 58, [
                'HEAVENLY FATHER',
                'QUIET EVERY ANXIOUS',
                'THOUGHT TONIGHT',
            ], ['HEAVENLY', 'FATHER', 'QUIET', 'ANXIOUS', 'TONIGHT'], 'PRAYER FOR STILLNESS'),
            (59, 69, [
                'SEND YOUR ANGELS',
                'TO GUARD THIS HOME',
                'WASH AWAY EVERY FEAR',
            ], ['ANGELS', 'GUARD', 'HOME', 'WASH', 'FEAR'], 'ANGELIC PROTECTION'),
            (70, 81, [
                'AND LET YOUR DIVINE PEACE',
                'FILL THIS ROOM',
                'FROM WALL TO WALL',
            ], ['DIVINE', 'PEACE', 'ROOM', 'WALL'], 'DIVINE PEACE'),
            (82, 92, [
                'SLEEP IN PEACE TONIGHT',
                'KNOWING THAT GOD',
                'IS FIGHTING YOUR BATTLES',
            ], ['PEACE', 'GOD', 'FIGHTING', 'BATTLES'], 'EXODUS 14 : 14'),
            (93, 107, [
                'IF YOU RECEIVE THIS PROTECTION',
                'TYPE AMEN AND SUBSCRIBE',
                'TO PRAY WITH US EVERY DAY',
            ], ['PROTECTION', 'TYPE', 'AMEN', 'SUBSCRIBE', 'PRAY'], 'THE SECRET PLACE'),
        ],
    ),
}

# -------------------------------------------------------------------- main ----
def main(key):
    cfg = SCRIPTS[key]
    out = os.path.join(ROOT, 'social', cfg['out'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    is_prayer = (key in ('psalm91', 'short-psalm91') or 'prayer' in key)
    if 'narration' in cfg:
        nar_src = os.path.join(AUDIO, cfg['narration'])
        nar = os.path.join(AUDIO, f'narration-{key}.m4a')
        shutil.copy(nar_src, '/tmp/_deep_in.mp3')
        cmd = [FFMPEG, '-y', '-i', '/tmp/_deep_in.mp3', '-c:a', 'aac', '-b:a', '160k', nar]
        subprocess.run(cmd, check=True, capture_output=True)
    else:
        v = [os.path.join(AUDIO, n) for n in cfg['voices']]
        nar = os.path.join(AUDIO, f'narration-{key}.m4a')
        if len(v) == 1:
            cmd = [FFMPEG, '-y', '-i', v[0], '-c:a', 'aac', '-b:a', '160k', nar]
        else:
            cmd = [FFMPEG, '-y']
            for vf in v:
                cmd += ['-i', vf]
            cmd += ['-filter_complex', f'concat=n={len(v)}:v=0:a=1', '-c:a', 'aac', '-b:a', '160k', nar]
        subprocess.run(cmd, check=True, capture_output=True)
    adur = duration(nar)
    total = adur + (1.6 if is_prayer else 2.2)
    n = int(total * FPS)

    words = load_words(key)
    beats = resolve_beats(key, words)
    scenes = resolve_scenes(key, words, total)
    cap_stream = build_caption_stream(key, words)
    kinetic_stream = build_kinetic_stream(key, words)
    for sc in scenes:
        stem=os.path.splitext(os.path.basename(sc['img']))[0]
        stem=__import__('re').sub(r'-{1,2}\d+$','',stem).replace('-',' ')
        sc['stock_query']=f'{stem} documentary archival'
    if os.environ.get('ENABLE_STOCK_BROLL','1').strip().lower() not in ('0','false','no','off'):
        try:
            from pipeline.assets import fetch_scene_assets
            stock_dir=os.path.join(ROOT,'output','deep-stock',key); found_by_query={}
            for si,sc in enumerate(scenes):
                query=sc['stock_query']
                if query not in found_by_query:
                    found_by_query[query]=fetch_scene_assets(query,si,stock_dir,count=1,target_width=W,target_height=H,allow_generated=False)
                found=found_by_query[query]
                if found:
                    asset=found[0]; sc['media_path']=str(asset.path); sc['media_kind']=asset.kind
                    sc['source']=asset.source; sc['source_url']=asset.origin_url; sc['license_note']=asset.license_note
                    sc['source_size']=(asset.width,asset.height); sc['stock_query']=query
        except Exception as exc:
            print(f'  stock sourcing unavailable; using authored story stills: {exc!r}')
    print(f'[{key}] narration={adur:.1f}s total={total:.1f}s ({n}f) scenes={len(scenes)} beats={len(beats)}')

    # ---- music automation: score swells + emotional hushes (no sound effects) ----
    cuts = [sc['t0'] for sc in scenes]
    hushes, swells = build_music_plan(key, words, beats)
    generate_score(key, total, cuts, [], [], hushes, swell_hits=swells)

    # Every scene keeps a real story-specific archive photo as decode/API fallback.
    plate_cache = {}
    plate_mode = 'fill' if is_prayer else 'matte'
    for sc in scenes:
        archive_path=os.path.join(IMG,sc['img'])
        if sc.get('media_kind')=='video':
            pkey=(archive_path,sc.get('focus_side',0.0),sc.get('warm',0.0),plate_mode)
            if pkey not in plate_cache:
                if not os.path.exists(archive_path):raise SystemExit(f'missing image {archive_path}')
                plate_cache[pkey]=prep_plate(archive_path,sc.get('focus_side',0.0),sc.get('warm',0.0),mode=plate_mode)
            sc['fallback_plate']=plate_cache[pkey]; sc['plate']=None
            label=f"VIDEO {sc.get('source')} {sc.get('source_size')}"
        else:
            p_path=sc.get('media_path') or archive_path
            pkey=(p_path,sc.get('focus_side',0.0),sc.get('warm',0.0),plate_mode)
            if pkey not in plate_cache:
                if not os.path.exists(p_path):raise SystemExit(f'missing image {p_path}')
                plate_cache[pkey]=prep_plate(p_path,sc.get('focus_side',0.0),sc.get('warm',0.0),mode=plate_mode)
            sc['plate']=plate_cache[pkey]
            label=f"PHOTO {sc.get('source')} {sc.get('source_size')}" if sc.get('media_path') else sc['img']
        print(f"  scene {sc['t0']:5.1f}-{sc['t1']:5.1f}s | {sc['kicker']:34s} | {label}")

    # Surface licence problems while the operator is still watching, not only in the JSON.
    for _line in LICENCE_REPORT(sorted({sc['img'] for sc in scenes if not sc.get('media_path')})):
        print(_line)

    music = os.path.join(AUDIO, f'music-{key}.wav')
    proc = subprocess.Popen(
        [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
         '-r', str(FPS), '-i', '-', '-i', nar, '-i', music,
         '-filter_complex',
         '[2:a]volume=0.62[m];[1:a]aformat=channel_layouts=stereo,volume=1.0[v];'
         '[m][v]amix=inputs=2:duration=longest:normalize=0,alimiter=limit=0.95[a]',
         '-map', '0:v', '-map', '[a]',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
         '-maxrate', '1800k', '-bufsize', '3600k', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    FADE = 0.42
    nscenes = len(scenes)
    expire_t = adur - 0.5
    active_video_scene=-1; video_proc=None
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

        if sc.get('media_kind')=='video':
            if active_video_scene!=k:
                stop_video_plate(video_proc)
                try:video_proc=video_plate_reader(sc['media_path']); active_video_scene=k
                except Exception as exc:video_proc=None; active_video_scene=-1; print(f'  video decode fallback: {exc!r}')
            source=read_video_plate(video_proc) if video_proc else None
            if source is None:
                source=sc['fallback_plate']; sc['media_kind']='image'; sc['used_fallback']=True
                stop_video_plate(video_proc); video_proc=None; active_video_scene=-1
        else:
            stop_video_plate(video_proc); video_proc=None; active_video_scene=-1; source=sc['plate']
        sc['last_source']=source
        # Camera easing
        punch_z = (1.0 + 0.035 * (1.0 - ease_out_cubic(clamp01(pos / 0.45)))) if is_prayer else 1.0
        accel_z = (1.0 + 0.020 * ease_out_cubic(clamp01((pos - (sc_dur - 0.20)) / 0.20))) if (is_prayer and pos > sc_dur - 0.20) else 1.0
        extra_z = 1.0 + 0.012 * (1.0 - ease_out_cubic(clamp01(pos / FADE))) if (k > 0 and pos < FADE) else 1.0
        frame = camera_frame(source, p, sc.get('cam', 'push_in'),
                             sc.get('focus', (0.5, 0.48)), extra_zoom=extra_z * punch_z * accel_z)

        if k > 0 and pos < FADE:
            prev = scenes[k - 1]
            u = pos / FADE
            prev_z = 1.0 + 0.008 * ease_in_out_sine(u)
            prev_source=prev.get('last_source',prev.get('plate'))
            f_prev = camera_frame(prev_source, 1.0, prev.get('cam', 'push_in'),
                                  prev.get('focus', (0.5, 0.48)), extra_zoom=prev_z)
            frame = optical_flare_transition(f_prev, frame, u, is_prayer=is_prayer)

        if is_prayer and k > 0 and pos < 0.07:
            frame = Image.blend(frame, WHITE_IMG, 0.16 * (1.0 - pos / 0.07))

        if is_prayer:
            frame = apply_shake(frame, t, PRAYER_IMPACTS)

        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ov.alpha_composite(ambient_layer(t))
        if not is_prayer:
            ov.alpha_composite(beats_layer(beats, t, expire_t))
            ov.alpha_composite(tease_layer(cfg.get('teases', []), t))
        if t < 4.3 and not is_prayer:
            cold_open_overlay(ov, cfg['title'], t, dur=4.3)
        ov.alpha_composite(hud_chapter_layer(sc['kicker'], sc.get('sub', ''),
                                             k + 1, nscenes, pos, sc_dur, t / total, is_prayer=is_prayer))
        if is_prayer and kinetic_stream:
            ov.alpha_composite(kinetic_typography_layer(frame, kinetic_stream, t, is_prayer=is_prayer))
        else:
            ov.alpha_composite(caption_ribbon_layer(cap_stream, t))

        frame = Image.alpha_composite(frame.convert('RGBA'), ov).convert('RGB')
        end_start = (kinetic_stream[-1]['disp_t1'] if (is_prayer and kinetic_stream) else adur - 0.4)
        if t >= end_start:
            frame = end_card_overlay(frame, cfg['end'], t - end_start, total - end_start)

        proc.stdin.write(frame.tobytes())
        if i % 360 == 0:
            print(f'  frame {i}/{n}', flush=True)

    stop_video_plate(video_proc)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit('encode failed')
    report=[]
    for si,sc in enumerate(scenes):
        report.append(dict(scene=si+1,query=sc.get('stock_query',''),media=('authored photo fallback' if not sc.get('media_path') or sc.get('used_fallback') else sc.get('media_kind')),
            provider=sc.get('source','existing story archive'),source_url=sc.get('source_url',''),
            # Authored stills now report their real ledger status instead of one blanket
            # "metadata unavailable" string: 10 of the 49 carry embedded Getty rights
            # metadata and 3 more an "All Rights Reserved" photographer copyright.
            license=(sc.get('license_note') if sc.get('media_path') else LICENCE_NOTE(sc.get('img',''))),
            dimensions=sc.get('source_size',None),fallback=(not bool(sc.get('media_path')) or bool(sc.get('used_fallback',False))),file=sc.get('media_path',sc.get('img',''))))
    report_dir=os.path.join(ROOT,'output','deep-stock',key); os.makedirs(report_dir,exist_ok=True)
    with open(os.path.join(report_dir,'scene-sources.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2,ensure_ascii=False)
    print('source log',os.path.join(report_dir,'scene-sources.json'))
    print('done', out, os.path.getsize(out) // 1024, 'KB')

if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else 'psalm91'
    if arg not in SCRIPTS:
        raise SystemExit(f'unknown script {arg!r} \u2014 choose from {sorted(SCRIPTS)}')
    main(arg)
