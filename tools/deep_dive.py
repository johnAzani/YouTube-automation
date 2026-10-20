#!/usr/bin/env python3
"""Deep-dive assembler v3: archival photos + narration -> 16:9 documentary clip.

Cinematic blue-duotone grade ("blue card" filter), glass card overlays, kinetic
type, AND speech-synced motion graphics: count-up stats, word-by-word phrase
reveals, quote cards and date chips that land exactly on the spoken words
(pocketsphinx word timings in assets/deepdive/words-*.json). Ambient layer:
parallax background words, dust motes, light-leak sweeps.

Config-driven: add a SCRIPTS entry + narration clips + image-search plates.

Run: .venv/bin/python tools/deep_dive.py [johnstown|enron]
"""
import os, sys, json, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1280, 720, 24
NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
WHITE = (255, 255, 255)
FAINT = (122, 156, 202)
ICE = (170, 210, 248)

FFMPEG = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
FDIR = os.path.join(ROOT, 'assets', 'fonts')
IMG = os.path.join(ROOT, 'image-search')
AUDIO = os.path.join(ROOT, 'assets', 'deepdive')

# ---------------------------------------------------------------- easing ----
def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

def ease_out_expo(x):
    x = clamp01(x)
    return 1.0 if x >= 1 else 1.0 - 2.0 ** (-10.0 * x)

def ease_out_back(x):
    x = clamp01(x)
    c1, c3 = 1.70158, 2.70158
    return 1.0 + c3 * (x - 1.0) ** 3 + c1 * (x - 1.0) ** 2

def fnt(w, sz):
    return ImageFont.truetype(os.path.join(FDIR, f'Inter-{w}.ttf'), sz)

def duration(path):
    r = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if 'Duration:' in ln:
            hh, mm, rest = ln.split('Duration: ')[1].split(',')[0].strip().split(':')
            return int(hh) * 3600 + int(mm) * 60 + float(rest)
    raise SystemExit(f'no duration for {path}')

# ------------------------------------------------------- blue grade + vign ----
def _duotone_luts():
    shadow, mid, high = (3, 11, 32), (15, 55, 118), (172, 210, 248)
    lr, lg, lb = [], [], []
    for i in range(256):
        t = i / 255.0
        if t < 0.55:
            u = t / 0.55
            c = [shadow[k] + (mid[k] - shadow[k]) * u for k in range(3)]
        else:
            u = (t - 0.55) / 0.45
            c = [mid[k] + (high[k] - mid[k]) * (u ** 1.15) for k in range(3)]
        lr.append(int(c[0])); lg.append(int(c[1])); lb.append(int(c[2]))
    return lr, lg, lb

LUT_R, LUT_G, LUT_B = _duotone_luts()

def grade_blue(im):
    """Cinematic blue-duotone 'filter' — shadows to navy, highlights to ice."""
    lum = im.convert('L')
    duo = Image.merge('RGB', (lum.point(LUT_R), lum.point(LUT_G), lum.point(LUT_B)))
    out = Image.blend(im.convert('RGB'), duo, 0.85)
    return out.point(lambda v: max(0, min(255, int(128 + (v - 128) * 1.12))))

def vignette():
    v = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    return v.filter(ImageFilter.GaussianBlur(120))

VIG = vignette()

def ken_burns(plate, p, zoom_in):
    """plate: pre-graded full-size image. Returns WxH RGB frame."""
    im = plate
    z = (1.0 + 0.14 * p) if zoom_in else (1.14 - 0.14 * p)
    cw, ch = int(im.width / z), int(im.height / z)
    drift = (p - 0.5) * 0.10 * (im.width - cw)
    x = int((im.width - cw) / 2 + drift)
    y = int((im.height - ch) / 2 + (p - 0.5) * 0.06 * (im.height - ch))
    im = im.crop((x, y, x + cw, y + ch)).resize((W, H), Image.LANCZOS)
    base = Image.new('RGB', (W, H), NAVY)
    base.paste(im)
    return Image.composite(base, Image.new('RGB', (W, H), (2, 8, 22)), VIG)

# ------------------------------------------------------------- glass cards ----
GLASS_CACHE = {}

def glass_card(w, h, radius=18, top=(16, 54, 112), bot=(8, 30, 78), a_top=205, a_bot=140):
    key = (w, h, radius, top, bot, a_top, a_bot)
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
                         outline=(126, 184, 255, 150), width=3)
    card = card.resize((w, h), Image.LANCZOS)
    d = ImageDraw.Draw(card)
    d.line([(radius, 1), (w - radius, 1)], fill=(196, 224, 255, 95), width=1)
    GLASS_CACHE[key] = card
    return card

def card_alpha(card, a):
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

def kinetic_line(layer, text, font, cx, y, t, t0, color=WHITE, tracking=3.0,
                 stagger=0.05, dur=0.55, slide=38, bounce=False):
    """Per-letter stagger: fade + slide with motion smear (AE-style)."""
    d = ImageDraw.Draw(layer)
    w = tracked_width(d, text, font, tracking)
    x = cx - w / 2
    for i, ch in enumerate(text):
        local = clamp01((t - t0 - i * stagger) / dur)
        if local <= 0:
            x += d.textlength(ch, font=font) + tracking
            continue
        e = ease_out_back(local) if bounce else ease_out_expo(local)
        a = int(255 * min(1.0, local * 1.8))
        yy = y + (1 - e) * slide
        if local < 0.99:  # motion smear ghosts
            for gy, ga in ((yy + (1 - e) * slide * 0.55, a // 3),
                           (yy + (1 - e) * slide * 0.28, (2 * a) // 5)):
                d.text((x, gy), ch, font=font, fill=color + (ga,))
        d.text((x, yy), ch, font=font, fill=color + (a,))
        x += d.textlength(ch, font=font) + tracking

def tracking_line(layer, text, font, cx, y, t, t0, color=ICE,
                  track_from=16.0, track_to=5.0, dur=0.7):
    """Subtitle: letter-spacing collapses as it fades in."""
    local = clamp01((t - t0) / dur)
    if local <= 0:
        return
    e = ease_out_expo(local)
    tr = track_from + (track_to - track_from) * e
    d = ImageDraw.Draw(layer)
    w = tracked_width(d, text, font, tr)
    a = int(255 * min(1.0, local * 2.2))
    x = cx - w / 2
    for ch in text:
        d.text((x, y), ch, font=font, fill=color + (a,))
        x += d.textlength(ch, font=font) + tr

def bar_wipe(layer, cx, y, w0, h, t, t0, dur=0.5, color=YELLOW):
    local = clamp01((t - t0) / dur)
    if local <= 0:
        return
    e = ease_out_back(local)
    w = max(2.0, w0 * e)
    d = ImageDraw.Draw(layer)
    d.rectangle([cx - w / 2, y, cx + w / 2, y + h], fill=color + (255,))

def shine_sweep(layer, t, t0, period=3.2, dur=1.0, band=240):
    """Moving light sweep through whatever is already drawn on the layer."""
    dt = t - t0
    if dt < 0:
        return layer
    ph = dt % period
    if ph >= dur:
        return layer
    x = -band * 2 + (W + band * 4) * (ph / dur)
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).rectangle([x - band / 2, 0, x + band / 2, H], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(70))
    alpha = ImageChops.multiply(m, layer.getchannel('A')).point(lambda v: int(v * 0.5))
    sh = Image.new('RGBA', (W, H), (215, 235, 255, 0))
    sh.putalpha(alpha)
    return Image.alpha_composite(layer, sh)

def fade_shift(layer, ex, dy=-22.0):
    """Global exit: fade out while drifting up."""
    a = layer.getchannel('A').point(lambda v: int(v * (1.0 - clamp01(ex))))
    layer.putalpha(a)
    dyi = int(dy * clamp01(ex))
    if dyi:
        out = Image.new('RGBA', layer.size, (0, 0, 0, 0))
        out.paste(layer, (0, dyi))
        return out
    return layer

# ------------------------------------------------- animated card background ----
def _glow_sprite(size, peak):
    g = Image.new('L', (size, size), 0)
    ImageDraw.Draw(g).ellipse([0, 0, size - 1, size - 1], fill=peak)
    return g.filter(ImageFilter.GaussianBlur(size // 4))

GLOW = _glow_sprite(520, 70)

def _bg_base():
    img = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        u = y / (H - 1)
        d.line([(0, y), (W, y)], fill=(int(5 + 7 * u), int(20 + 16 * u), int(50 + 34 * u)))
    return img

BG_BASE = _bg_base()

def _streaks():
    s = Image.new('L', (W * 2, H), 0)
    d = ImageDraw.Draw(s)
    d.polygon([(300, -80), (430, -80), (980, H + 80), (820, H + 80)], fill=46)
    d.polygon([(1250, -80), (1330, -80), (1750, H + 80), (1650, H + 80)], fill=32)
    d.polygon([(1900, -80), (2020, -80), (2500, H + 80), (2360, H + 80)], fill=24)
    return s.filter(ImageFilter.GaussianBlur(60))

STREAKS = _streaks()

def card_background(t):
    img = BG_BASE.copy()
    for i, (spd, rad, col, al) in enumerate((
            (0.35, 620, (40, 110, 210), 0.34),
            (0.22, 520, (20, 70, 160), 0.30),
            (0.45, 420, (70, 150, 235), 0.22))):
        x = int(W * (0.18 + 0.32 * i) + math.sin(t * spd + i * 2.1) * 150) - rad // 2
        y = int(H * 0.40 + math.cos(t * spd * 0.8 + i * 1.3) * 90) - rad // 2
        gl = GLOW.resize((rad, rad), Image.BILINEAR).point(lambda v: int(v * al))
        img.paste(col, (x, y), gl)
    off = int((t * 26) % W)
    st = STREAKS.crop((off, 0, off + W, H))
    img.paste((120, 175, 240), (0, 0), st)
    return Image.composite(img, Image.new('RGB', (W, H), (3, 12, 30)), VIG)

# ---------------------------------------------------------- title / end cards ----
def fit_font(weight, sz, text, maxw):
    f = fnt(weight, sz)
    d = ImageDraw.Draw(Image.new('RGB', (8, 8)))
    while tracked_width(d, text, f, 2.0) > maxw and sz > 24:
        sz = int(sz * 0.94)
        f = fnt(weight, sz)
    return f

def card_frame(t1, t2, t, T, bounce_head=False):
    img = card_background(t)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    f1 = fit_font('Black', 80, t1, W - 200)
    f2 = fit_font('SemiBold', 28, t2, W - 180)
    d0 = ImageDraw.Draw(layer)
    w1 = tracked_width(d0, t1, f1, 3.0)

    # glass panel grows behind the title block
    panel_w, panel_h = int(min(W - 120, w1 + 150)), 250
    pw = int(panel_w * ease_out_expo(clamp01((t - 0.02) / 0.55)))
    if pw > 20:
        panel = glass_card(panel_w, panel_h, radius=26)
        x0 = (panel_w - pw) // 2
        layer.alpha_composite(card_alpha(panel.crop((x0, 0, x0 + pw, panel_h)),
                                         clamp01((t - 0.02) / 0.35)),
                              (W // 2 - pw // 2, 228))

    kinetic_line(layer, t1, f1, W / 2, 262, t, 0.12, WHITE, 3.0,
                 stagger=0.05, dur=0.55, slide=42, bounce=bounce_head)
    bar_wipe(layer, W / 2, 384, max(180.0, w1 * 0.55), 12, t, 1.35, 0.5)
    tracking_line(layer, t2, f2, W / 2, 424, t, 1.5, ICE, 16.0, 5.0, 0.7)
    layer = shine_sweep(layer, t, 2.4)
    if t > T - 0.55:
        layer = fade_shift(layer, (t - (T - 0.55)) / 0.55)
    return Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')

def title_card_frame(t, T):
    return card_frame(SCRIPT_TITLE[0], SCRIPT_TITLE[1], t, T, bounce_head=False)

def end_card_frame(t, T):
    return card_frame(SCRIPT_END[0], SCRIPT_END[1], t, T, bounce_head=True)

# --------------------------------------------------------------- kicker ----
KICKER_TEXT_CACHE = {}

def kicker_layer(text, idx, nscenes, t_in, t_out):
    """Blue glass chip + yellow bar + wiped text + chapter counter."""
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    if t_in < 0:
        return layer
    e = ease_out_expo(clamp01(t_in / 0.5))
    a = clamp01(t_in / 0.3)
    x_off = (1 - e) * -64
    if t_out < 0.35:
        q = clamp01(t_out / 0.35)
        x_off += (1 - q) * -48
        a *= q
    if a <= 0.01:
        return layer
    a = int(255 * a)

    f = fnt('SemiBold', 26)
    if text not in KICKER_TEXT_CACHE:
        tmp = Image.new('RGBA', (W, 80), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((0, 8), text, font=f, fill=WHITE + (255,))
        KICKER_TEXT_CACHE[text] = tmp.crop((0, 0, int(tmp.getbbox()[2]) + 6, 52))
    txt = KICKER_TEXT_CACHE[text]
    tw = txt.width

    pad, bh = 22, 58
    cw, chh = tw + pad * 2 + 18, bh
    cx, cy = 48 + x_off, H - 118
    card = card_alpha(glass_card(cw, chh, radius=14), a / 255.0)
    layer.alpha_composite(card, (int(cx), int(cy)))

    d = ImageDraw.Draw(layer)
    bar_h = 30 * e
    d.rectangle([cx + 16, cy + (bh - bar_h) / 2, cx + 21, cy + (bh + bar_h) / 2],
                fill=YELLOW + (a,))
    reveal = max(1, int(tw * ease_out_expo(clamp01(t_in / 0.7))))
    txa = txt.copy()
    txa.putalpha(txa.getchannel('A').point(lambda v: int(v * a / 255)))
    layer.alpha_composite(txa.crop((0, 0, reveal, txa.height)),
                          (int(cx + pad + 16), int(cy + (bh - txt.height) / 2 - 4)))
    fc = fnt('Medium', 18)
    ca = int(255 * clamp01((t_in - 0.25) / 0.4) * (a / 255))
    if ca > 0:
        d.text((cx + pad + 18, cy - 30), f'{idx:02d} / {nscenes:02d}', font=fc,
               fill=ICE + (ca,))
    return layer

def progress_bar(layer, frac, a=210):
    d = ImageDraw.Draw(layer)
    d.rectangle([0, H - 5, W, H], fill=(255, 255, 255, 26))
    x = int(W * clamp01(frac))
    if x > 0:
        d.rectangle([0, H - 5, x, H], fill=ICE + (a,))

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

def resolve_beats(key):
    """Map each beat's anchor phrase to its spoken word times."""
    words = load_words(key)
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
    return beats

# --------------------------------------------------- speech-synced beats ----
SLOTS = [(938, 165), (330, 175), (640, 255), (925, 445), (345, 445)]

def _word_times(b, n):
    """n display words over the anchor's word times (equal count -> 1:1)."""
    if n == len(b['wtimes']):
        return list(b['wtimes'])
    if n <= 1:
        return [b['t0']] * n
    span = b['t1'] - b['t0']
    return [b['t0'] + span * i / (n - 1) for i in range(n)]

def _flash_ring(layer, t, t0, cx, cy):
    dt = t - t0
    if dt < 0 or dt > 0.5:
        return
    e = clamp01(dt / 0.5)
    r = 46 + 105 * ease_out_expo(e)
    a = int(150 * (1 - e))
    if a <= 2:
        return
    ring = Image.new('L', (int(r * 2) + 8, int(r * 2) + 8), 0)
    ImageDraw.Draw(ring).ellipse([0, 0, ring.width - 1, ring.height - 1], fill=a)
    ImageDraw.Draw(ring).ellipse([10, 10, ring.width - 11, ring.height - 11], fill=0)
    ring = ring.filter(ImageFilter.GaussianBlur(2))
    col = Image.new('RGBA', ring.size, ICE + (255,))
    col.putalpha(ring)
    layer.alpha_composite(col, (int(cx - ring.width / 2), int(cy - ring.height / 2)))

def beat_count(layer, b, t, cx, cy):
    dur = b.get('dur', 1.35)
    t0, t1 = b['t0'], b['t1']
    ext = b.get('hold', 3.0)
    if t < t0 - 0.25 or t > t1 + ext + 0.6:
        return
    out_a = 1.0
    if t > t1 + ext:
        out_a = 1.0 - clamp01((t - t1 - ext) / 0.55)
    ea = ease_out_expo(clamp01((t - (t0 - 0.25)) / 0.4))
    # count-up value
    local = clamp01((t - t0) / dur)
    if 'txt' in b:
        shown = b['txt'] if local > 0.25 else ''
        pop = ease_out_back(clamp01((t - t0) / 0.4))
    else:
        val = b.get('num', 0) * ease_out_expo(local)
        shown = f"{b.get('pre', '')}{val:,.{b.get('dec', 0)}f}{b.get('suf', '')}"
        pop = 0.9 + 0.1 * ease_out_back(clamp01((t - t0) / 0.35))
    fnum = fnt('Black', 104 if b.get('big', True) else 76)
    fnote = fnt('SemiBold', 24)
    d = ImageDraw.Draw(layer)
    wnum = d.textlength(shown, font=fnum) if shown else 0
    wlab = tracked_width(d, b.get('label', ''), fnote, 3.5) if b.get('label') else 0
    panel_w = int(max(wnum, wlab) + 96)
    panel_h = 196 if b.get('label') else 150
    px = int(cx - panel_w / 2)
    py = int(cy - panel_h / 2)
    pw = int(panel_w * ease_out_expo(clamp01((t - (t0 - 0.25)) / 0.45)))
    if pw > 16:
        x0 = (panel_w - pw) // 2
        layer.alpha_composite(card_alpha(glass_card(panel_w, panel_h, radius=22), ea * out_a),
                              (px + x0, py))
    if shown:
        if abs(pop - 1.0) > 0.01:
            im = Image.new('RGBA', (int(wnum) + 24, 130), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((12, 6), shown, font=fnum, fill=WHITE + (255,))
            nw = max(2, int(im.width * pop))
            nh = max(2, int(im.height * pop))
            im = im.resize((nw, nh), Image.LANCZOS)
            im.putalpha(im.getchannel('A').point(lambda v: int(v * out_a)))
            layer.alpha_composite(im, (int(cx - nw / 2), int(cy - nh / 2 - 14)))
        else:
            im = Image.new('RGBA', (int(wnum) + 24, 130), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((12, 6), shown, font=fnum, fill=WHITE + (255,))
            im.putalpha(im.getchannel('A').point(lambda v: int(v * out_a)))
            layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2 - 14)))
    if b.get('label'):
        la = clamp01((t - (t0 + 0.45)) / 0.5)
        if la > 0:
            lw = int(wlab * ease_out_expo(la))
            im = Image.new('RGBA', (int(wlab) + 8, 40), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((4, 4), b['label'], font=fnote, fill=ICE + (int(255 * out_a),))
            layer.alpha_composite(im.crop((0, 0, max(1, lw), im.height)),
                                  (int(cx - wlab / 2), int(cy + 38)))
    _flash_ring(layer, t, t0 + dur, cx, cy)

def beat_phrase(layer, b, t, cx, cy):
    t0, t1 = b['t0'], b['t1']
    ext = b.get('hold', 2.3)
    if t < t0 - 0.3 or t > t1 + ext + 0.6:
        return
    out_a = 1.0
    if t > t1 + ext:
        out_a = 1.0 - clamp01((t - t1 - ext) / 0.55)
    disp = b['words']
    ts = _word_times(b, len(disp))
    f = fnt('Black', 46 if b.get('size', 46) >= 46 else 38)
    tr = 7.0
    d = ImageDraw.Draw(layer)
    widths = [d.textlength(w, font=f) + tr for w in disp]
    total = sum(widths) - tr
    x0 = cx - total / 2
    x = x0
    top_y = cy - 30
    hi = b.get('hi', -1)
    for i, (w, wt) in enumerate(zip(disp, ts)):
        local = clamp01((t - (wt - 0.22)) / 0.45)
        if local > 0:
            e = ease_out_expo(local)
            a = int(255 * min(1.0, local * 1.9) * out_a)
            col = YELLOW if i == hi else WHITE
            yy = top_y + (1 - e) * 30
            if local < 0.99:
                d.text((x, yy + (1 - e) * 16), w, font=f, fill=col + (a // 3,))
            d.text((x, yy), w, font=f, fill=col + (a,))
        x += widths[i]
    # underline rule draws across the phrase as the words land
    prog = clamp01((t - (t0 - 0.1)) / max(0.4, t1 - t0 + 0.35))
    if prog > 0:
        uw = total * ease_out_expo(prog)
        d.rectangle([x0, cy + 34, x0 + uw, cy + 39], fill=YELLOW + (int(210 * out_a),))

def beat_quote(layer, b, t, cx, cy):
    t0, t1 = b['t0'], b['t1']
    ext = b.get('hold', 2.8)
    if t < t0 - 0.4 or t > t1 + ext + 0.6:
        return
    out_a = 1.0
    if t > t1 + ext:
        out_a = 1.0 - clamp01((t - t1 - ext) / 0.55)
    disp = b['words']
    ts = _word_times(b, len(disp))
    fq = fnt('Light', 46)
    fmark = fnt('Black', 130)
    fat = fnt('Medium', 22)
    d = ImageDraw.Draw(layer)
    ea = ease_out_expo(clamp01((t - (t0 - 0.4)) / 0.5))
    # split into two balanced lines and measure
    mid = (len(disp) + 1) // 2
    lines = [disp[:mid], disp[mid:]]
    lts = [ts[:mid], ts[mid:]]
    line_w = [sum(d.textlength(w, font=fq) + 8 for w in lw) - 8 for lw in lines]
    pw = int(max(line_w) + 190)
    ph = 210 if len(lines) > 1 and lines[1] else 150
    px, py = int(cx - pw / 2), int(cy - ph / 2 - 10)
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=22), ea * out_a), (px, py))
    # bold yellow quote mark
    ma = int(235 * ea * out_a)
    d.text((px + 26, py + 18), '\u201c', font=fmark, fill=YELLOW + (ma,))
    for li, (lw, lt) in enumerate(zip(lines, lts)):
        widths = [d.textlength(w, font=fq) + 8 for w in lw]
        total = sum(widths) - 8
        x = cx - total / 2 + 22
        y = py + 46 + li * 56
        for i, (w, wt) in enumerate(zip(lw, lt)):
            local = clamp01((t - (wt - 0.22)) / 0.5)
            if local > 0:
                e = ease_out_expo(local)
                a = int(255 * min(1.0, local * 1.8) * out_a)
                yy = y + (1 - e) * 22
                if local < 0.99:
                    d.text((x, yy + (1 - e) * 12), w, font=fq, fill=WHITE + (a // 3,))
                d.text((x, yy), w, font=fq, fill=WHITE + (a,))
            x += widths[i]
    # accent bar grows under the panel
    bar_e = ease_out_back(clamp01((t - (t0 - 0.1)) / 0.6))
    bw = 130 * bar_e
    d.rectangle([cx - bw / 2, py + ph + 14, cx + bw / 2, py + ph + 19],
                fill=YELLOW + (int(220 * out_a),))
    if b.get('attrib'):
        la = clamp01((t - (t1 - 0.15)) / 0.6)
        if la > 0:
            aw = tracked_width(d, b['attrib'], fat, 2.5)
            aa = int(235 * ease_out_expo(la) * out_a)
            x = cx - aw / 2 + (1 - ease_out_expo(la)) * 30
            for ch in b['attrib']:
                d.text((x, py + ph + 32), ch, font=fat, fill=ICE + (aa,))
                x += d.textlength(ch, font=fat) + 2.5

def beat_date(layer, b, t, cx, cy):
    t0, t1 = b['t0'], b['t1']
    ext = b.get('hold', 2.6)
    if t < t0 - 0.3 or t > t1 + ext + 0.6:
        return
    out_a = 1.0
    if t > t1 + ext:
        out_a = 1.0 - clamp01((t - t1 - ext) / 0.55)
    fm = fnt('Black', 52)
    fs = fnt('SemiBold', 21)
    d = ImageDraw.Draw(layer)
    wm = tracked_width(d, b['main'], fm, 3.0)
    ws = tracked_width(d, b.get('sub', ''), fs, 3.5) if b.get('sub') else 0
    pw, ph = int(max(wm, ws) + 90), 132
    px, py = int(cx - pw / 2), int(cy - ph / 2)
    ea = ease_out_expo(clamp01((t - (t0 - 0.3)) / 0.4))
    layer.alpha_composite(card_alpha(glass_card(pw, ph, radius=18), ea * out_a), (px, py))
    # corner brackets grow out of the chip corners
    bl = int(26 * ea)
    ba = int(220 * out_a)
    for bx, by, dx, dy in ((px + 8, py + 8, 1, 1), (px + pw - 9, py + 8, -1, 1),
                           (px + 8, py + ph - 9, 1, -1), (px + pw - 9, py + ph - 9, -1, -1)):
        d.rectangle([bx, by, bx + bl * dx if dx > 0 else bx + 3, by + 3 if dy > 0 else by + 3],
                    fill=YELLOW + (ba,))
        d.rectangle([bx, by, bx + 3 if dx > 0 else bx + 3, by + bl * dy if dy > 0 else by + 3],
                    fill=YELLOW + (ba,))
    kinetic_line(layer, b['main'], fm, cx, cy - 46, t, t0 - 0.22, WHITE, 3.0,
                 stagger=0.035, dur=0.5, slide=26)
    if b.get('sub'):
        la = clamp01((t - (t0 + 0.28)) / 0.5)
        if la > 0:
            sw = ws * ease_out_expo(la)
            im = Image.new('RGBA', (int(ws) + 8, 36), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((4, 2), b['sub'], font=fs, fill=ICE + (int(255 * out_a),))
            layer.alpha_composite(im.crop((0, 0, max(1, int(sw)), im.height)),
                                  (int(cx - ws / 2), int(cy + 6)))

BEAT_KINDS = {'count': beat_count, 'phrase': beat_phrase, 'quote': beat_quote, 'date': beat_date}

def beats_layer(beats, t, expire_t):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for i, b in enumerate(beats):
        if b['t0'] > expire_t:
            continue
        cx, cy = SLOTS[i % len(SLOTS)]
        BEAT_KINDS[b['kind']](layer, b, t, cx, cy)
    return layer

# --------------------------------------------------------- ambient layer ----
DUST = [( (i * 149.3) % W, (i * 83.7) % H, 0.16 + (i % 5) * 0.05, 4 + (i % 4) * 2, i * 1.7 )
        for i in range(26)]
DUST_SPR = _glow_sprite(28, 120)
BGWORD_CACHE = {}

def _bg_word(word):
    if word not in BGWORD_CACHE:
        f = fnt('Black', 170)
        tmp = Image.new('RGBA', (2200, 260), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((20, 10), word, font=f, fill=ICE + (255,))
        tmp = tmp.crop(tmp.getbbox())
        BGWORD_CACHE[word] = tmp.filter(ImageFilter.GaussianBlur(7))
    return BGWORD_CACHE[word]

def ambient_layer(scene_idx, t, bgwords):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    # parallax background words, drifting slowly against the Ken Burns move
    for i in range(2):
        w = bgwords[(scene_idx * 2 + i) % len(bgwords)]
        spr = _bg_word(w)
        x = int(W / 2 - spr.width / 2 + math.sin(t * 0.05 + scene_idx * 1.3 + i * 2.2) * 130)
        y = int(70 + i * 330 + math.cos(t * 0.04 + i * 1.9) * 40)
        s2 = spr.copy()
        s2.putalpha(s2.getchannel('A').point(lambda v: int(v * 0.13)))
        layer.alpha_composite(s2, (x, y))
    # dust motes drifting up
    for x0, y0, sp, sz, ph in DUST:
        x = int((x0 + t * sp * 22) % (W + 60)) - 30
        y = int((y0 - t * sp * 34) % (H + 60)) - 30
        dim = 0.10 + 0.05 * (sz % 3)
        spr = DUST_SPR if sz <= 5 else GLOW.resize((sz * 6, sz * 6), Image.BILINEAR)
        if spr.mode == 'L':
            s2 = Image.new('RGBA', spr.size, ICE + (255,))
            s2.putalpha(spr.point(lambda v: int(v * dim)))
        else:
            s2 = spr.copy()
            s2.putalpha(s2.getchannel('A').point(lambda v: int(v * dim)))
        layer.alpha_composite(s2, (x, y))
    # soft light-leak sweep across the frame
    off = int((t * 14) % (W * 2))
    st = STREAKS.crop((off, 0, off + W, H))
    st = st.point(lambda v: v // 5)
    leak = Image.new('RGBA', (W, H), (140, 190, 250, 0))
    leak.putalpha(st)
    return Image.alpha_composite(layer, leak)

# ------------------------------------------------------------------ scripts ----
SCRIPTS = {
    'johnstown': dict(
        title=('THE CANAL THAT BROKE A CITY', 'A DEEP DIVE \u00B7 MAY 31, 1889'),
        end=('SUBSCRIBE', 'the full story of the canal that broke a city'),
        voices=('voice1.mp3', 'voice2.mp3', 'voice3.mp3'),
        out='deep-dive-johnstown.mp4',
        bgwords=['CONEMAUGH', '1889', 'JOHNSTOWN', 'DEBRIS', 'VERDICT', 'FLOOD'],
        beats=[
            dict(a='twenty million pounds of force', kind='count', num=20, suf='M',
                 label='TONS OF FORCE HELD BACK', dur=1.6),
            dict(a='into a weapon', kind='phrase', words=['INTO', 'A', 'WEAPON'], hi=2),
            dict(a='eighteen fifty two', kind='date', main='1852', sub='THE SOUTH FORK DAM IS BUILT'),
            dict(a='two thousand dollars', kind='count', num=2000, pre='$',
                 label='THE CLUB PAID FOR THE LAKE', dur=1.4),
            dict(a='game fish', kind='phrase', words=['GAME', 'FISH'], hi=1),
            dict(a='crest was lowered', kind='phrase', words=['THE', 'CREST', 'WAS', 'LOWERED'], hi=1),
            dict(a='six to eight inches', kind='count', txt='6\u20138 IN',
                 label='OF RAIN IN 24 HOURS', dur=1.1),
            dict(a='twenty million pounds of water', kind='count', num=20, suf='M',
                 label='TONS OF WATER RELEASED', dur=1.7),
            dict(a='thirty six feet high', kind='count', txt='36 FT',
                 label='THE WALL OF WATER', dur=1.1),
            dict(a='ten million pounds of debris', kind='count', num=10, suf='M',
                 label='POUNDS OF DEBRIS', dur=1.4),
            dict(a='sixty two acres', kind='count', num=62,
                 label='ACRES BURNED', dur=1.0),
            dict(a='three days', kind='phrase', words=['THREE', 'DAYS'], hi=0),
            dict(a='two thousand two hundred', kind='count', num=2209,
                 label='DEAD', dur=1.7, big=True),
            dict(a='five months', kind='count', txt='5 MONTHS',
                 label='CLARA BARTON\u2019S RED CROSS STAYED', dur=1.0),
            dict(a='act of god', kind='quote', words=['AN', 'ACT', 'OF', 'GOD'],
                 attrib='\u2014 THE VERDICT THAT NEVER CAME'),
            dict(a='fail by decisions', kind='phrase',
                 words=['THEY', 'FAIL', 'BY', 'DECISIONS'], hi=3),
        ],
        scenes=[
            ('south-fork-dam-lake-conemaugh-johnstown--3.jpg', 'THE LAKE ABOVE THE VALLEY'),
            ('south-fork-dam-lake-conemaugh-johnstown--5.png', 'BUILT FOR A CANAL THAT DIED'),
            ('south-fork-dam-lake-conemaugh-johnstown--4.jpg', 'THE DAM GIVES WAY'),
            ('johnstown-flood-1889-ruins-destruction-h-1.jpg', 'THE STONE BRIDGE'),
            ('johnstown-flood-1889-ruins-destruction-h-2.jpg', 'A CITY OF DEBRIS'),
            ('johnstown-flood-1889-ruins-destruction-h-4.jpg', 'THREE DAYS OF FIRE'),
            ('south-fork-dam-lake-conemaugh-johnstown--1.jpg', 'THE SURVIVORS'),
            ('south-fork-dam-lake-conemaugh-johnstown--2.jpg', 'THE VERDICT NEVER CAME'),
        ]),
    'enron': dict(
        title=('HOW ENRON DIED', 'A DEEP DIVE \u00B7 DECEMBER 2, 2001'),
        end=('SUBSCRIBE', 'money, explained \u2014 the fall of the smartest guys in the room'),
        voices=('enron1.mp3', 'enron2.mp3', 'enron3.mp3'),
        out='deep-dive-enron.mp4',
        bgwords=['ENRON', '2001', 'HOUSTON', 'BANKRUPTCY', 'FRAUD', 'TRIAL'],
        beats=[
            dict(a='smartest guys in the room', kind='quote',
                 words=['SMARTEST', 'GUYS', 'IN', 'THE', 'ROOM'],
                 attrib='\u2014 ENRON\u2019S OWN SLOGAN'),
            dict(a='humble gas pipeline', kind='phrase',
                 words=['HUMBLE', 'GAS', 'PIPELINE'], hi=2),
            dict(a='jeff skilling arrived', kind='date', main='JEFF SKILLING',
                 sub='ARRIVES WITH AN IDEA'),
            dict(a='mom to market accounting', kind='phrase',
                 words=['MARK-TO-MARKET', 'ACCOUNTING'], hi=0, size=38),
            dict(a='ninety dollars', kind='count', num=90, pre='$',
                 label='A SHARE AT ITS PEAK', dur=1.1),
            dict(a='seventy billion dollars', kind='count', num=70, pre='$', suf='B',
                 label='MARKET VALUE', dur=1.6),
            dict(a='six years in a row', kind='phrase',
                 words=['SIX', 'YEARS', 'IN', 'A', 'ROW'], hi=0),
            dict(a='profits were fiction', kind='phrase',
                 words=['THE', 'PROFITS', 'WERE', 'FICTION'], hi=3),
            dict(a='off the books', kind='phrase', words=['OFF', 'THE', 'BOOKS'], hi=0),
            dict(a='fast the bills', kind='date', main='ANDREW FASTOW',
                 sub='THE CFO HIDING THE DEBT'),
            dict(a='j m wrapped up', kind='phrase',
                 words=['LJM', '\u00B7', 'RAPTOR', '\u00B7', 'CHEWCO'], hi=0),
            dict(a='hide billions in debt', kind='phrase',
                 words=['HIDING', 'BILLIONS', 'IN', 'DEBT'], hi=1),
            dict(a='enron overpriced', kind='quote',
                 words=['IS', 'ENRON', 'OVERPRICED?'],
                 attrib='\u2014 BETHANY McLEAN, FORTUNE, MAR 2001'),
            dict(a='house of cards', kind='phrase',
                 words=['HOUSE', 'OF', 'CARDS'], hi=1),
            dict(a='shredding documents', kind='phrase',
                 words=['SHREDDING', 'DOCUMENTS'], hi=0),
            dict(a='august two thousand', kind='date', main='AUGUST 2001',
                 sub='THE CEO QUITS'),
            dict(a='skilling resigned', kind='phrase',
                 words=['SKILLING', 'RESIGNS'], hi=1),
            dict(a='fake all alone', kind='phrase',
                 words=['FAKE', 'ALL', 'ALONG'], hi=0),
            dict(a='december second two thousand', kind='date', main='DEC 2, 2001',
                 sub='CHAPTER 11 \u00B7 ENRON COLLAPSES'),
            dict(a='sixty three billion dollars', kind='count', num=63.4, pre='$',
                 suf='B', dec=1, label='IN ASSETS \u2014 LARGEST U.S. BANKRUPTCY', dur=1.8),
            dict(a='filing in american history', kind='phrase',
                 words=['FILING', 'IN', 'AMERICAN', 'HISTORY'], hi=3),
            dict(a='twenty thousand employees', kind='count', num=20000,
                 label='JOBS GONE', dur=1.7),
            dict(a='their pensions', kind='phrase',
                 words=['THEIR', 'PENSIONS'], hi=1),
            dict(a='eighty five thousand people', kind='count', num=85000,
                 label='ANDERSEN STAFF \u2014 DISSOLVED', dur=1.8),
            dict(a='skilling went to prison', kind='phrase',
                 words=['SKILLING', 'WENT', 'TO', 'PRISON'], hi=3),
            dict(a='died before sentencing', kind='phrase',
                 words=['DIED', 'BEFORE', 'SENTENCING'], hi=0),
            dict(a='smartest guys in the room', occ=1, kind='phrase',
                 words=['THE', 'SMARTEST', 'GUYS', 'IN', 'THE', 'ROOM'], hi=1, size=38),
            dict(a='a company cannot explain how it makes money it is not making money',
                 kind='quote',
                 words=['A', 'COMPANY', 'CANNOT', 'EXPLAIN', 'HOW', 'IT', 'MAKES',
                        'MONEY', 'IT\u2019S', 'NOT', 'MAKING', 'MONEY'],
                 attrib='\u2014 THE LESSON THAT OUTLIVED ENRON'),
        ],
        scenes=[
            ('enron-corporation-headquarters-houston-c-3.jpg', 'THE EMPIRE IN HOUSTON'),
            ('enron-corporation-headquarters-houston-c-5.jpg', 'THE TRADING MACHINE'),
            ('enron-corporation-headquarters-houston-c-2.jpg', 'SEVENTY BILLION DOLLARS'),
            ('enron-corporation-headquarters-houston-c-4.jpg', 'THE OFF-BOOKS MAZE'),
            ('jeff-skilling-ken-lay-enron-trial-courtr-1.jpg', '\u201cIS ENRON OVERPRICED?\u201d'),
            ('jeff-skilling-ken-lay-enron-trial-courtr-2.jpg', 'THE RESIGNATION'),
            ('jeff-skilling-ken-lay-enron-trial-courtr-3.jpg', 'GUILTY'),
            ('enron-corporation-headquarters-houston-c-1.jpg', 'THE PENSIONS'),
        ]),
}

SCRIPT_TITLE = ('', '')
SCRIPT_END = ('', '')

# -------------------------------------------------------------------- main ----
def main(key):
    global SCRIPT_TITLE, SCRIPT_END
    cfg = SCRIPTS[key]
    SCRIPT_TITLE, SCRIPT_END = cfg['title'], cfg['end']
    out = os.path.join(ROOT, 'social', cfg['out'])
    # 1. concat narration
    v = [os.path.join(AUDIO, n) for n in cfg['voices']]
    nar = os.path.join(AUDIO, f'narration-{key}.m4a')
    cmd = [FFMPEG, '-y', '-i', v[0], '-i', v[1], '-i', v[2],
           '-filter_complex', 'concat=n=3:v=0:a=1', '-c:a', 'aac', '-b:a', '160k', nar]
    subprocess.run(cmd, check=True, capture_output=True)
    adur = duration(nar)
    print(f'narration {adur:.1f}s')

    beats = resolve_beats(key)
    print(f'{len(beats)} speech-synced beats, first at {beats[0]["t0"]:.2f}s')

    TITLE, END = 5.0, 3.2
    ph0, ph1 = TITLE, adur + 0.6
    scenes = cfg['scenes']
    per = (ph1 - ph0) / len(scenes)
    total = ph1 + END
    n = int(total * FPS)
    print(f'video {total:.1f}s = {n} frames')

    srcs = [os.path.join(IMG, f) for f, _ in scenes]
    plates = []
    for s in srcs:
        if not os.path.exists(s):
            raise SystemExit(f'missing image {s}')
        im = Image.open(s)
        print(' ', os.path.basename(s), im.size)
        plates.append(grade_blue(im))
    print('blue-graded', len(plates), 'plates')

    proc = subprocess.Popen(
        [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
         '-r', str(FPS), '-i', '-', '-i', nar,
         '-map', '0:v', '-map', '1:a',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    FADE = 0.45
    nscenes = len(scenes)
    expire_t = ph1 - 0.2
    for i in range(n):
        t = i / FPS
        if t < TITLE:
            frame = title_card_frame(t, TITLE)
        elif t < ph1:
            k = min(int((t - ph0) // per), nscenes - 1)
            p = (t - ph0 - k * per) / per
            frame = ken_burns(plates[k], p, zoom_in=(k % 2 == 0))
            pos = t - ph0 - k * per
            ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            ov.alpha_composite(ambient_layer(k, t, cfg['bgwords']))
            ov.alpha_composite(beats_layer(beats, t, expire_t))
            ov.alpha_composite(kicker_layer(scenes[k][1], k + 1, nscenes,
                                            pos - 0.12, per - pos - 0.30))
            progress_bar(ov, t / total)
            frame = Image.alpha_composite(frame.convert('RGBA'), ov).convert('RGB')
            # crossfade from the previous plate
            if k > 0 and pos < FADE:
                f1 = ken_burns(plates[k - 1], 1.0, zoom_in=((k - 1) % 2 == 0))
                frame = Image.blend(f1, frame, pos / FADE)
        else:
            frame = end_card_frame(t - ph1, END)
            ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            progress_bar(ov, t / total)
            frame = Image.alpha_composite(frame.convert('RGBA'), ov).convert('RGB')

        # fade from title into first photo
        if t >= TITLE - FADE and t < TITLE:
            f2 = ken_burns(plates[0], 0.0, True)
            frame = Image.blend(frame, f2, (t - (TITLE - FADE)) / FADE)
        proc.stdin.write(frame.tobytes())
        if i % 240 == 0:
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
