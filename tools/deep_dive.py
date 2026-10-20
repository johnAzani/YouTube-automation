#!/usr/bin/env python3
"""Deep-dive assembler v2: archival photos + narration -> 16:9 documentary clip.

Cinematic blue-duotone grade on every plate ("blue card" filter), glass card
overlays, kinetic type: per-letter stagger with motion smear, ease-out-expo
wipes, overshoot bars, moving light sweeps, chapter kickers, title/end cards,
Ken Burns moves, narration muxed via ffmpeg.

Config-driven: add a SCRIPTS entry + narration clips + image-search plates.

Run: .venv/bin/python tools/deep_dive.py [johnstown|enron]
"""
import os, sys, math, subprocess
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
    # yellow accent bar grows out of the chip
    bar_h = 30 * e
    d.rectangle([cx + 16, cy + (bh - bar_h) / 2, cx + 21, cy + (bh + bar_h) / 2],
                fill=YELLOW + (a,))
    # text wipe reveal (left -> right)
    reveal = max(1, int(tw * ease_out_expo(clamp01(t_in / 0.7))))
    txa = txt.copy()
    txa.putalpha(txa.getchannel('A').point(lambda v: int(v * a / 255)))
    layer.alpha_composite(txa.crop((0, 0, reveal, txa.height)),
                          (int(cx + pad + 16), int(cy + (bh - txt.height) / 2 - 4)))
    # chapter counter, fades in slightly later
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

# ------------------------------------------------------------------ scripts ----
SCRIPTS = {
    'johnstown': dict(
        title=('THE CANAL THAT BROKE A CITY', 'A DEEP DIVE \u00B7 MAY 31, 1889'),
        end=('SUBSCRIBE', 'the full story of the canal that broke a city'),
        voices=('voice1.mp3', 'voice2.mp3', 'voice3.mp3'),
        out='deep-dive-johnstown.mp4',
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
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    FADE = 0.45
    nscenes = len(scenes)
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
