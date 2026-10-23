#!/usr/bin/env python3
"""
MOTIONSTUDIO v4 — DocOga typography motion-design system (After-Effects-grade)
═══════════════════════════════════════════════════════════════════════════════
 1. CONTENT ANALYSIS    purpose/audience/tone/peaks/hierarchy declared first
 2. TYPOGRAPHY SOLVER   font-metric sizing, safe-width rejection, same-role
                        harmonization, line-break solving, vertical rhythm
                        chain, WCAG contrast verification. Calculates, never
                        guesses; rejects its own bad layouts.
 3. MOTION GRAMMAR      every animation bound to a reason:
                        hook→odometer roll · emphasis→cascade/slam+recoil ·
                        support→controlled rise · kicker→mask reveal ·
                        transition→flash | whip (momentum) | dissolve
                        (resolution) · conclusion→stillness · struck text
                        dims (color carries the verdict) · matter moves on
                        damped springs, the camera on clean cubics.
 4. SCHEDULER           reading-time-aware timing; auto-shift/retime/trim
 5. RENDER ENGINE       parallax camera (bg 0.35x content), motion blur as
                        ghost trails on every fast element, impact recoil +
                        shake, rolling odometer, breathing CTA. 30fps film
                        feel. Safe-zone locked.
 6. VIDEO QA ENGINE     typography (cut-off/size/contrast) · animation
                        (unscheduled motion, frame-diff vs event registry) ·
                        timing (pre-exit presence) · composition (safe areas,
                        pairwise collision, hierarchy) · consistency. Auto-
                        fixes and re-renders; refuses to encode if unfixable.
Run: python3 tools/motionstudio.py [reel1|reel2|all]

Env adapters vs the studio original (runtime portability only):
  · font discovery searches assets/fonts + system dirs (Inter .otf/.ttf)
  · encode() honors FFMPEG_BINARY when ffmpeg is not on PATH
"""
import os, sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageChops
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # shared ffmpeg resolution — see pipeline.assemble.ffmpeg_bin
try:
    from pipeline.assemble import ffmpeg_bin as _resolve_ffmpeg
except Exception:  # pragma: no cover - pipeline package unavailable
    def _resolve_ffmpeg():
        return os.environ.get('FFMPEG_BINARY') or 'ffmpeg'
FFMPEG = _resolve_ffmpeg()
OUT = os.path.join(ROOT, 'social')
W, H, FPS = 1080, 1920, 30
CX = W // 2
SAFE = dict(top=300, bottom=1240, left=80, right=1000)
SAFE_W = SAFE['right'] - SAFE['left']
EXIT, FLASH = 0.22, 0.09
TRANS_DUR = {'flash': FLASH, 'whip': 0.20, 'dissolve': 0.30}
REEL_CAP = 15.6

NAVY = (6, 26, 51)
NAVY2 = (12, 38, 70)
PANEL = (15, 61, 124)
WHITE, MUTED, FAINT = (255, 255, 255), (143, 168, 201), (96, 128, 170)
BLUE, YELLOW, RED, GREEN = (74, 140, 255), (255, 201, 60), (255, 90, 95), (46, 204, 107)

# ── font discovery (original: /usr/share/fonts/opentype/inter/Inter-{}.otf) ──
_FONT_DIRS = [os.path.join(ROOT, 'assets', 'fonts'), os.path.join(OUT, 'assets', 'fonts'),
              '/usr/share/fonts/opentype/inter', '/usr/share/fonts/truetype/inter']
_FALLBACK = {'Black': ['Black', 'ExtraBold', 'Bold'], 'ExtraBold': ['ExtraBold', 'Black'],
             'Bold': ['Bold', 'SemiBold'], 'SemiBold': ['SemiBold', 'Medium', 'Bold'],
             'Medium': ['Medium', 'Regular'], 'Regular': ['Regular', 'Light'],
             'Light': ['Light', 'Regular']}

def _font_path(w):
    for cand in _FALLBACK.get(w, [w]):
        for d in _FONT_DIRS:
            for ext in ('.otf', '.ttf'):
                p = os.path.join(d, f'Inter-{cand}{ext}')
                if os.path.exists(p):
                    return p
    raise FileNotFoundError(f'no Inter font file for weight {w!r} in {_FONT_DIRS}')

try:
    from PIL import features
    RAQM = features.check('raqm')
except Exception:
    RAQM = False

_fc = {}
def font(w, sz):
    key = (w, sz)
    if key not in _fc:
        if RAQM:
            _fc[key] = ImageFont.truetype(_font_path(w), sz, layout_engine=ImageFont.Layout.RAQM)
        else:
            _fc[key] = ImageFont.truetype(_font_path(w), sz)
    return _fc[key]

_scratch = ImageDraw.Draw(Image.new('RGB', (8, 8)))
def tw(text, w, sz):
    return _scratch.textbbox((0, 0), text, font=font(w, sz))[2]

# ═══════════════════════════════════ 1. CONTENT ══════════════════════════════
def Beat(kind, role, text='', **kw):
    b = dict(kind=kind, role=role, text=text, t0=None, exempt=False, why='', lines=None)
    b.update(kw)
    return b

REEL1 = dict(
    name='THE PRICE', out='reel-1-price.mp4',
    purpose='Hook non-followers on lawyer-price pain, resolve to free alternative',
    audience='Nigerian renters & young professionals, phone-first, sound-off',
    platform='Instagram Reels', tone='bold, direct, confident',
    peak='the red strike through ₦50,000 — number recoils, shakes, then dims',
    hierarchy='odometer prices > emphasis statements > support lines > kickers',
    scenes=[
        dict(id='A', role='hook', dur=3.3, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '₦50,000', target=50000, prefix='₦', size=210, y=620,
                 color=WHITE, count_dur=0.90, strike=RED, strike_hold=0.35, whose='theirs'),
            Beat('support', 'support', 'for one document.', size=58, y=885, color=MUTED),
        ]),
        dict(id='B', role='contrast', dur=2.9, punch=0.045, trans='flash', beats=[
            Beat('badge', 'emphasis', shape='cross', color=RED, cy=560, r=52),
            Beat('cascade', 'emphasis', 'TOO MUCH.', size=150, y=680, color=WHITE),
            Beat('kicker', 'kicker', 'THE LAWYER\u2019S PRICE', size=30, y=900, color=FAINT),
        ]),
        dict(id='C', role='reveal', dur=2.9, punch=0.020, trans='whip', beats=[
            Beat('badge', 'emphasis', shape='check', color=GREEN, cy=560, r=56, t0=0.02),
            Beat('cascade', 'emphasis', 'OR 2 MINUTES.', size=150, y=680, color=WHITE),
            Beat('kicker', 'kicker', 'ANY DOCUMENT \u00B7 ON YOUR PHONE', size=30, y=900, color=YELLOW),
        ]),
        dict(id='D', role='price', dur=2.9, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '₦2,000', target=2000, prefix='₦', size=262, y=590,
                 color=WHITE, count_dur=0.50, whose='ours'),
            Beat('kicker', 'kicker', '30 DAYS \u00B7 UNLIMITED', size=36, y=990, color=YELLOW),
        ]),
        dict(id='E', role='conclusion', dur=3.6, punch=0.0, trans='dissolve', beats=[
            Beat('wordpop', 'conclusion', 'FREE.', size=190, y=540, color=WHITE,
                 underline=YELLOW, rings=True),
            Beat('button', 'cta', 'docoga.com.ng', y=850),
            Beat('support', 'support', 'to start. No signup. No card.', size=46, y=1035, color=MUTED),
            Beat('kicker', 'kicker', 'YOUR DOCUMENTS. OUR PRIORITY.', size=24, y=1150,
                 color=FAINT, t0=1.72),
            Beat('kicker', 'kicker', 'FOLLOW @docoga.ng', size=24, y=1198, color=BLUE, t0=1.92),
        ]),
    ])

REEL2 = dict(
    name='EVERY DOCUMENT.', out='reel-2-documents.mp4',
    purpose='Show breadth — every document a Nigerian needs, one pass',
    audience='Nigerian renters & young professionals, phone-first, sound-off',
    platform='Instagram Reels', tone='fast, confident, organized',
    peak='7 icons landing one-by-one into the grid',
    hierarchy='headline > cycling document names > kickers',
    scenes=[
        dict(id='A', role='hook', dur=2.6, punch=0.050, trans='flash', beats=[
            Beat('cascade', 'hook', 'EVERY DOCUMENT.', size=132, y=420, color=WHITE),
            Beat('kicker', 'kicker', 'ONE PASS', size=30, y=660, color=BLUE),
        ]),
        dict(id='B', role='proof', dur=6.0, punch=0.020, trans='whip', beats=[
            Beat('headline', 'support', 'EVERY DOCUMENT.', size=96, y=400, color=WHITE, t0=0.02),
            Beat('icons', 'proof', '', exempt=True, why='visual element (grid cadence)'),
            Beat('cycler', 'emphasis', '', exempt=True, t0=2.84,
                 why='cadence element — rhythm is the message'),
        ]),
        dict(id='C', role='price', dur=2.8, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '₦2,000.', target=2000, prefix='₦', suffix='.', size=236,
                 y=560, color=WHITE, count_dur=0.50, whose='ours'),
            Beat('kicker', 'kicker', '30 DAYS \u00B7 ALL 9 DOCUMENTS', size=32, y=960, color=YELLOW),
        ]),
        dict(id='D', role='conclusion', dur=3.2, punch=0.0, trans='dissolve', beats=[
            Beat('wordpop', 'conclusion', 'FREE.', size=180, y=560, color=WHITE,
                 underline=YELLOW, rings=True),
            Beat('button', 'cta', 'docoga.com.ng', y=805),
            Beat('support', 'support', 'to start. No signup. No card.', size=42, y=950, color=MUTED),
            Beat('kicker', 'kicker', 'FOLLOW @docoga.ng', size=26, y=1155, color=BLUE),
        ]),
    ])

# ── channel reels: "The Canal That Broke a City" (Johnstown Flood, 1889) ──
REEL3 = dict(
    name='THE FLOOD', out='reel-3-flood.mp4',
    purpose='Hook history audience with the scale of the Johnstown Flood',
    audience='history & disaster-documentary fans, phone-first, sound-off',
    platform='YouTube Shorts / Instagram Reels', tone='grave, cinematic, factual',
    peak='the 2,209 count-up landing, yellow-underlined, then perfect stillness',
    hierarchy='fact odometers > verdict lines > support lines > kickers',
    scenes=[
        dict(id='A', role='hook', dur=3.2, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '2,209', target=2209, prefix='', size=250, y=580,
                 color=WHITE, count_dur=0.95, whose='ours'),
            Beat('support', 'support', 'one city. one night.', size=52, y=900, color=MUTED),
            Beat('kicker', 'kicker', 'JOHNSTOWN \u00B7 MAY 31, 1889', size=32, y=1010, color=YELLOW),
        ]),
        dict(id='B', role='contrast', dur=2.9, punch=0.045, trans='flash', beats=[
            Beat('badge', 'emphasis', shape='cross', color=RED, cy=540, r=52),
            Beat('cascade', 'emphasis', 'IT HELD FOR YEARS.', size=120, y=660, color=WHITE),
            Beat('kicker', 'kicker', 'A LAKE SAT ABOVE THE VALLEY', size=30, y=900, color=FAINT),
        ]),
        dict(id='C', role='reveal', dur=2.9, punch=0.020, trans='whip', beats=[
            Beat('cascade', 'emphasis', 'THEN IT DIDN\u2019T.', size=120, y=660, color=WHITE),
            Beat('kicker', 'kicker', 'THE WALL GAVE WAY', size=30, y=900, color=YELLOW),
        ]),
        dict(id='D', role='price', dur=2.9, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '20,000,000', target=20000000, prefix='', size=175, y=575,
                 color=WHITE, count_dur=0.85, whose='ours'),
            Beat('kicker', 'kicker', 'TONS OF WATER \u00B7 ONE RELEASED LAKE', size=32, y=975,
                 color=YELLOW),
        ]),
        dict(id='E', role='conclusion', dur=3.6, punch=0.0, trans='dissolve', beats=[
            Beat('wordpop', 'conclusion', 'REMEMBER.', size=180, y=540, color=WHITE,
                 underline=YELLOW, rings=True),
            Beat('button', 'cta', 'FULL STORY \u00B7 SUBSCRIBE', y=850),
            Beat('support', 'support', 'the courts held nobody responsible.', size=46, y=1035,
                 color=MUTED),
            Beat('kicker', 'kicker', 'THE CANAL THAT BROKE A CITY', size=24, y=1150,
                 color=FAINT, t0=1.72),
            Beat('kicker', 'kicker', 'FOLLOW FOR MORE HISTORY', size=24, y=1198, color=BLUE, t0=1.92),
        ]),
    ])

REEL4 = dict(
    name='THE SECRET', out='reel-4-secret.mp4',
    purpose='The dam\u2019s backstory — how a $2,000 lake was set up to fail',
    audience='history & disaster-documentary fans, phone-first, sound-off',
    platform='YouTube Shorts / Instagram Reels', tone='wry, ominous, factual',
    peak='the check badge landing on \u201cTHE FISH HAD TO STAY.\u201d — the irony that doomed a valley',
    hierarchy='fact odometers > verdict lines > support lines > kickers',
    scenes=[
        dict(id='A', role='hook', dur=3.0, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '$2,000', target=2000, prefix='$', size=240, y=580,
                 color=WHITE, count_dur=0.70, whose='ours'),
            Beat('support', 'support', 'a lake sat above the valley.', size=50, y=900, color=MUTED),
            Beat('kicker', 'kicker', 'THE PRICE OF A DAM', size=32, y=1010, color=YELLOW),
        ]),
        dict(id='B', role='contrast', dur=2.9, punch=0.045, trans='flash', beats=[
            Beat('badge', 'emphasis', shape='cross', color=RED, cy=540, r=52),
            Beat('cascade', 'emphasis', 'THE CANAL DIED.', size=120, y=660, color=WHITE),
            Beat('kicker', 'kicker', 'RAILROADS TOOK THE ROUTE', size=30, y=900, color=FAINT),
        ]),
        dict(id='C', role='reveal', dur=2.9, punch=0.020, trans='whip', beats=[
            Beat('badge', 'emphasis', shape='check', color=GREEN, cy=540, r=56, t0=0.02),
            Beat('cascade', 'emphasis', 'THE FISH HAD TO STAY.', size=120, y=660, color=WHITE),
            Beat('kicker', 'kicker', 'SO THEY SCREENED THE DRAIN', size=30, y=900, color=YELLOW),
        ]),
        dict(id='D', role='price', dur=2.9, punch=0.050, trans='flash', beats=[
            Beat('odometer', 'hook', '36', target=36, prefix='', size=262, y=575,
                 color=WHITE, count_dur=0.45, whose='ours'),
            Beat('kicker', 'kicker', 'FEET HIGH WHEN IT STRUCK', size=32, y=975, color=YELLOW),
        ]),
        dict(id='E', role='conclusion', dur=3.6, punch=0.0, trans='dissolve', beats=[
            Beat('wordpop', 'conclusion', 'GONE.', size=190, y=540, color=WHITE,
                 underline=YELLOW, rings=True),
            Beat('button', 'cta', 'FULL STORY \u00B7 SUBSCRIBE', y=850),
            Beat('support', 'support', 'the lake emptied in forty minutes.', size=46, y=1035,
                 color=MUTED),
            Beat('kicker', 'kicker', 'THE CANAL THAT BROKE A CITY', size=24, y=1150,
                 color=FAINT, t0=1.72),
            Beat('kicker', 'kicker', 'FOLLOW FOR MORE HISTORY', size=24, y=1198, color=BLUE, t0=1.92),
        ]),
    ])

DOCS = ['Tenancy Agreement', 'Rent Receipt', 'Notice to Quit', 'Invoice',
        'Employment Contract', 'Caution Fee', 'Demand Letter', 'Payslip', 'Warning Letter']
ICONS = ['icon-agreement', 'icon-receipt', 'icon-seal', 'icon-house',
         'icon-shield', 'icon-clock', 'icon-coin']

# ═════════════════════════════ 2. TYPOGRAPHY SOLVER ══════════════════════════
def weight_of(b):
    return {'cascade': 'Black', 'headline': 'Black', 'wordpop': 'Black',
            'kicker': 'SemiBold', 'support': 'Light', 'odometer': 'Black'}.get(b['kind'], 'Black')

def rel_lum(c):
    def ch(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])

BG_LUM = rel_lum(tuple(min(255, int(c * 1.15)) for c in NAVY))   # brightest bg region
def contrast_ratio(fg):
    return (rel_lum(fg) + 0.05) / (BG_LUM + 0.05)

def linebreak(text, w, sz):
    """balanced 2-line split at a word boundary"""
    words = text.split()
    best, bd = None, 1e9
    for i in range(1, len(words)):
        l1, l2 = ' '.join(words[:i]), ' '.join(words[i:])
        d = abs(tw(l1, w, sz) - tw(l2, w, sz))
        if d < bd:
            bd, best = d, [l1, l2]
    return best

def solve_sizes(reel):
    log = []
    for sc in reel['scenes']:
        for b in sc['beats']:
            if b['kind'] not in ('cascade', 'headline', 'wordpop', 'kicker', 'support', 'odometer') or not b['text']:
                continue
            want, s = b['size'], b['size']
            while s > 32 and tw(b['text'], weight_of(b), s) > SAFE_W:
                s -= 4
            if s <= 32 and tw(b['text'], weight_of(b), s) > SAFE_W and ' ' in b['text']:
                b['lines'] = linebreak(b['text'], weight_of(b), s)
                log.append(f"  LINEBREAK '{b['text'][:22]}' → 2 lines (could not fit one line ≥32px)")
                while s > 32 and max(tw(l, weight_of(b), s) for l in b['lines']) > SAFE_W:
                    s -= 4
            elif s != want:
                log.append(f"  REJECTED '{b['text'][:20]}' @ {want}px "
                           f"({tw(b['text'], weight_of(b), want)}px > {SAFE_W}px safe width) → {s}px")
            b['size'] = s
    cascades = [b for sc in reel['scenes'] for b in sc['beats'] if b['kind'] == 'cascade']
    if cascades:
        top = min(b['size'] for b in cascades)
        for b in cascades:
            if b['size'] != top:
                log.append(f"  HARMONIZE '{b['text'][:20]}' {b['size']}px → {top}px "
                           f"(same-role emphasis must share one size)")
                b['size'] = top
    return log

def contrast_report(reel):
    """WCAG check vs the BRIGHTEST background region (worst case)."""
    rows, worst = [], 99.0
    for sc in reel['scenes']:
        for b in sc['beats']:
            if b['kind'] in ('kicker', 'support', 'cascade', 'wordpop', 'headline', 'odometer') and b['text']:
                r = contrast_ratio(b['color'])
                need = 3.0 if b['size'] >= 24 else 4.5
                worst = min(worst, r / need)
                rows.append((b['text'][:18], b['color'], r, need, r >= need))
    return rows, worst

def solve_layout(reel):
    log = []
    for sc in reel['scenes']:
        chain = []
        for b in sc['beats']:
            k = b['kind']
            if k in ('cascade', 'headline', 'wordpop', 'odometer', 'support', 'kicker'):
                asc, desc = font(weight_of(b), b['size']).getmetrics()
                nl = len(b['lines']) if b['lines'] else 1
                chain.append([b['y'], b['y'] + nl * (asc + desc), b['text'][:14], b, 'y'])
            elif k == 'badge':
                chain.append([b['cy'] - b['r'], b['cy'] + b['r'], 'badge', b, 'cy'])
            elif k == 'button':
                chain.append([b['y'] - 8, b['y'] + 126, 'button', b, 'y'])
            elif k == 'icons':
                chain.append([535, 995, 'icon-grid', None, None])
            elif k == 'cycler':
                chain.append([1150, 1216, 'cycler', None, None])
        prev_y1 = SAFE['top']
        for box in chain:
            if box[3] is not None and box[0] < prev_y1 + 18:
                shift = prev_y1 + 18 - box[0]
                box[3][box[4]] += shift
                box[0] += shift
                box[1] += shift
                log.append(f"  RESPACE scene {sc['id']}: '{box[2]}' +{shift}px (min rhythm gap)")
            if box[1] > SAFE['bottom'] and box[3] is not None:
                over = box[1] - SAFE['bottom']
                box[3][box[4]] -= over
                box[0] -= over
                box[1] -= over
                log.append(f"  RESPACE scene {sc['id']}: '{box[2]}' -{over}px (safe bottom)")
            prev_y1 = max(prev_y1, box[1])
    return log

# ═══════════════════════════════ 3. MOTION GRAMMAR ═══════════════════════════
GRAMMAR = {
    'hook':        'odometer rolls up — mechanical counter, ghosted roll blur',
    'emphasis':    'per-char cascade on damped springs + slam strike: recoil, camera shake, ring',
    'strike':      'rejection of an EXTERNAL price only — never our own price; struck text dims',
    'own_price':   'our price is underlined in brand yellow — owned with confidence, never struck',
    'support':     'controlled whole-line rise — explanation never fights the headline',
    'kicker':      'mask-reveal wipe + tracking-in (18→6) — lands like a stamp',
    'proof':       'spin-settle grid, one element at a time — cadence, not chaos',
    'cta':         'rise + breathing scale + pulse — the only element allowed to loop',
    'conclusion':  'one word, double ring, underline sweep, then perfect stillness',
    'transition':  'flash = reset · whip = momentum into good news · dissolve = resolution',
    'physics':     'matter moves on damped springs; the camera moves on clean cubics',
    'blur':        'everything fast carries motion blur (ghost trails) — 30fps film feel',
}
ENTR = {'wordpop': 0.45, 'badge': 0.40, 'kicker': 0.35, 'support': 0.40,
        'button': 0.50, 'headline': 0.0}

def entrance_dur(b):
    k = b['kind']
    if k == 'odometer':
        return b['count_dur'] + 0.15
    if k == 'cascade':
        return 0.30 + 0.05 * (len(b['text']) - 1)
    if k == 'icons':
        return 0.30 + 0.42 * (len(ICONS) - 1) + 0.40
    if k == 'cycler':
        return 0.30
    return ENTR[k]

def reading_time(b):
    if b['exempt'] or not b['text']:
        return 0.0
    words = max(1, len(b['text'].replace('.', ' ').replace('\u00B7', ' ').split()))
    rt = 0.5 + words / 2.8
    cap = {'kicker': 1.00, 'support': 1.25, 'emphasis': 1.30, 'hook': 1.40,
           'conclusion': 1.10, 'cta': 0.0}.get(b['role'], 1.30)
    return min(cap, max(0.80, rt))

# ══════════════════════════════════ 4. SCHEDULER ═════════════════════════════
def schedule(reel):
    fixes = []
    for si, sc in enumerate(reel['scenes']):
        last = si == len(reel['scenes']) - 1
        t, prev_settle = 0.12, 0.0
        for b in sc['beats']:
            ent = entrance_dur(b)
            if b['t0'] is None:
                b['t0'] = round(t, 2)
            settle = max(b['t0'] + ent, TRANS_DUR[sc['trans']])
            rt = reading_time(b)
            if rt > 0:
                avail = (sc['dur'] - settle - 0.05) if last else (sc['dur'] - EXIT - settle)
                if avail < rt:
                    floor = max(0.10, prev_settle + 0.04)
                    new_t0 = round(max(floor, b['t0'] - (rt - avail)), 2)
                    if new_t0 < b['t0']:
                        fixes.append(f"  AUTO-FIX shift: scene {sc['id']} '{b['text'][:22]}' "
                                     f"t0 {b['t0']}→{new_t0}s (reading window {avail:.2f}s → needs {rt:.2f}s)")
                        b['t0'] = new_t0
                        settle = b['t0'] + ent
                        avail = (sc['dur'] - settle - 0.05) if last else (sc['dur'] - EXIT - settle)
                    if avail < rt:
                        add = round(rt - avail + 0.10, 2)
                        sc['dur'] = round(sc['dur'] + add, 2)
                        fixes.append(f"  AUTO-FIX retime: scene {sc['id']} +{add:.2f}s "
                                     f"('{b['text'][:22]}' could not shift earlier without crowding)")
            prev_settle = max(prev_settle, settle)
            t = max(t, settle + 0.12)
    total = round(sum(sc['dur'] for sc in reel['scenes']), 2)
    if total > REEL_CAP:
        for sc in reel['scenes']:
            if total <= REEL_CAP:
                break
            need = max(b['t0'] + entrance_dur(b) + max(reading_time(b), 0.8)
                       for b in sc['beats']) + (EXIT + 0.15 if sc is not reel['scenes'][-1] else 0.10)
            if sc['dur'] > need:
                take = round(min(sc['dur'] - need, total - REEL_CAP), 2)
                sc['dur'] = round(sc['dur'] - take, 2)
                total = round(total - take, 2)
                fixes.append(f"  AUTO-FIX trim: scene {sc['id']} -{take:.2f}s hold slack (reel cap {REEL_CAP}s)")
    reel['total'] = total
    return fixes

def events_of(reel):
    ev = []
    for si, sc in enumerate(reel['scenes']):
        off = sum(s['dur'] for s in reel['scenes'][:si])
        last = si == len(reel['scenes']) - 1
        if sc['trans'] == 'whip':
            ev.append((off, off + 0.24, 'whip-in'))
        elif sc['trans'] == 'dissolve':
            ev.append((off, off + 0.32, 'dissolve-in'))
        else:
            ev.append((off, off + FLASH + 0.02, 'cut/flash'))
        if sc['punch'] > 0:
            ev.append((off, off + 0.52, 'punch-in'))
        if not last:
            ev.append((off + sc['dur'] - EXIT, off + sc['dur'] + 0.03, 'accelerate-out'))
        for b in sc['beats']:
            t0, ent = off + b['t0'], entrance_dur(b)
            k = b['kind']
            if k == 'odometer':
                ev.append((t0 + 0.02, t0 + 0.03 + b['count_dur'] + 0.06, f"count {b['text']}"))
                if b.get('strike'):
                    s_at = b['t0'] + b['count_dur'] + b.get('strike_hold', 0.35)
                    b['strike_at_local'] = s_at
                    ev.append((off + s_at, off + s_at + 0.62, 'strike slam + recoil + ring + shake + dim'))
                elif b.get('whose') == 'ours':
                    u_at = t0 + b['count_dur'] + 0.25
                    ev.append((u_at, u_at + 0.45, 'own-price underline sweep'))
            elif k == 'cascade':
                ev.append((t0, t0 + 0.05 * (len(b['text']) - 1) + 0.56, 'cascade (springs)'))
            elif k in ('support', 'kicker', 'badge'):
                ev.append((t0, t0 + ent + 0.12, f'{k} in'))
            elif k == 'wordpop':
                ev.append((t0, t0 + ent + 0.60, 'wordpop + rings + underline'))
            elif k == 'button':
                ev.append((t0, t0 + ent + 0.08, 'button rise'))
                ev.append((t0, off + sc['dur'], 'button breathe/pulse'))
            elif k == 'icons':
                ev.append((t0, t0 + ent + 0.12, 'icon grid pops (springs)'))
            elif k == 'cycler':
                ev.append((t0, off + sc['dur'], 'name cycler cadence'))
    return ev

# ═══════════════════════════════ 5. RENDER ENGINE ════════════════════════════
def ease_cubic(p): return 1 - (1 - p) ** 3
def lerp_c(c1, c2, t): return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def spring(t, k=180.0, z=0.68):
    """analytic underdamped spring: 0→1 with natural overshoot/settle"""
    if t <= 0: return 0.0
    w = math.sqrt(k)
    wd = w * math.sqrt(max(1e-6, 1 - z * z))
    e = math.exp(-z * w * t)
    return 1 - e * (math.cos(wd * t) + (z * w / wd) * math.sin(wd * t))

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

def ctext(d, y, text, f, fill):
    w = _scratch.textbbox((0, 0), text, font=f)[2]
    d.text((CX - w // 2, y), text, font=f, fill=fill)
    return w

def ctracked(d, y, text, f, fill, tr=6):
    x = CX - (sum(_scratch.textlength(ch, font=f) + tr for ch in text) - tr) / 2
    for ch in text:
        if ch != ' ':
            d.text((x, y), ch, font=f, fill=fill)
        x += _scratch.textlength(ch, font=f) + tr

def badge(d, cx, cy, r, color, shape, pop=1.0):
    r = int(r * max(0.05, pop))
    if r < 4: return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    lw = max(8, int(r * 0.26))
    if shape == 'check':
        d.line([(cx - r * .45, cy + r * .02), (cx - r * .08, cy + r * .38),
                (cx + r * .5, cy - r * .32)], fill=WHITE, width=lw, joint='curve')
    else:
        d.line([(cx - r * .38, cy - r * .38), (cx + r * .38, cy + r * .38)], fill=WHITE, width=lw)
        d.line([(cx + r * .38, cy - r * .38), (cx - r * .38, cy + r * .38)], fill=WHITE, width=lw)

def ring(d, cx, cy, r, p, color):
    if p <= 0 or p >= 1: return
    rr = int(r + 130 * ease_cubic(p))
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
              outline=lerp_c(color, NAVY2, p), width=max(2, int(9 * (1 - p))))

def strike_mid(y, size):
    asc, _ = font('Black', size).getmetrics()
    return y + asc - round(0.363 * size)

def countup(lt, t0, t1, target):
    if lt < t0: return 0
    if lt >= t1: return target
    p = 1 - (1 - (lt - t0) / (t1 - t0)) ** 3
    step = max(1, target // 25)
    return int(min(target, round(target * p / step) * step))

def r_odometer(d, img, b, lt):
    t0 = b['t0']
    counting = lt < t0 + 0.03 + b['count_dur']
    v = countup(lt, t0 + 0.03, t0 + 0.03 + b['count_dur'], b['target'])
    txt = f"{b['prefix']}{v:,}{b.get('suffix', '')}"
    # impact recoil: scale bump decaying after the strike
    bump, col = 0.0, b['color']
    sp = lt - b['strike_at_local'] if b.get('strike') else -1.0
    if b.get('whose') == 'ours' and not b.get('strike') and lt > t0 + b['count_dur'] + 0.25:
        g = ease_cubic(min(1.0, (lt - t0 - b['count_dur'] - 0.25) / 0.35))
        w = tw(b['text'], 'Black', b['size'])
        asc_u, _ = font('Black', b['size']).getmetrics()
        uy = b['y'] + asc_u + 16
        d.rectangle([CX - w * 0.47, uy, CX - w * 0.47 + w * 0.94 * g, uy + 14], fill=YELLOW)
    if sp > 0:
        if sp < 0.22:
            bump = 0.06 * math.exp(-sp / 0.08)
        if sp > 0.12:                                   # struck = dead: dim to muted
            col = lerp_c(WHITE, MUTED, min(1.0, (sp - 0.12) / 0.35))
    sz = int(b['size'] * (1 + bump))
    f = font('Black', sz)
    ytop = b['y'] - int(b['size'] * bump * 0.36)
    if counting and lt > t0 + 0.05:
        vprev = countup(lt - 1.0 / FPS, t0 + 0.03, t0 + 0.03 + b['count_dur'], b['target'])
        if vprev != v:                                   # rolling-counter ghost
            tp = f"{b['prefix']}{vprev:,}{b.get('suffix', '')}"
            ctext(d, ytop - 16, tp, f, (*col, 90))
            ctext(d, ytop + 6, txt, f, (*col, 70))
    ctext(d, ytop, txt, f, col if lt > t0 + 0.04 else (*NAVY2, 255))
    if sp > 0:
        g = min(1.0, sp / 0.10)
        w = tw(b['text'], 'Black', b['size'])
        m = strike_mid(b['y'], b['size'])
        x0 = CX - w * 0.47
        tip = x0 + w * 0.94 * g
        d.rectangle([x0, m - 12, tip, m + 12], fill=b['strike'])
        if g < 1:                                        # horizontal slam blur
            d.rectangle([tip - 16, m - 10, tip, m + 10], fill=(*b['strike'], 80))
            d.rectangle([tip - 30, m - 8, tip - 16, m + 8], fill=(*b['strike'], 45))
            ring(d, tip, m, 30, sp / 0.55, b['strike'])

def r_cascade(d, img, b, lt):
    if lt < b['t0']: return
    f = font('Black', b['size'])
    lines = b['lines'] or [b['text']]
    asc, desc = f.getmetrics()
    lh = asc + desc + 8
    y = b['y']
    for line in lines:
        x = CX - sum(_scratch.textlength(ch, font=f) for ch in line) / 2
        for k, ch in enumerate(line):
            tl = lt - b['t0'] - k * 0.05
            if tl > 0 and ch != ' ':
                sp_now = spring(tl)
                sp_prev = spring(tl - 1.0 / FPS)
                y_now = y + 30 * (1 - sp_now)
                y_prev = y + 30 * (1 - sp_prev)
                col = lerp_c(NAVY2, b['color'], min(1, tl / 0.18))
                if abs(y_prev - y_now) > 2:              # motion-blur ghost trail
                    for gi in (1, 2):
                        gy = y_prev + (y_now - y_prev) * (gi / 2.6)
                        d.text((x, gy), ch, font=f, fill=(*col, int(85 * (1 - gi / 3))))
                d.text((x, y_now), ch, font=f, fill=col)
            x += _scratch.textlength(ch, font=f)
        y += lh

def r_support(d, img, b, lt):
    if lt < b['t0']: return
    p = min(1.0, (lt - b['t0']) / 0.40)
    yy = b['y'] + int(24 * (1 - ease_cubic(p)))
    col = lerp_c(NAVY2, b['color'], min(1, p * 1.6))
    for i, line in enumerate(b['lines'] or [b['text']]):
        ctext(d, yy + i * (font('Light', b['size']).getmetrics()[0] + 14), line,
              font('Light', b['size']), col)

def r_kicker(d, img, b, lt):
    """mask-reveal wipe + tracking-in"""
    if lt < b['t0']: return
    p = min(1.0, (lt - b['t0']) / 0.35)
    tr = int(18 - 12 * ease_cubic(p))
    col = lerp_c(NAVY2, b['color'], min(1.0, (lt - b['t0']) / 0.30))
    f = font('SemiBold', b['size'])
    TH = 200
    tmp = Image.new('RGBA', (W, TH), (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    ctracked(td, 80, b['text'], f, col, tr)
    fw = int(sum(_scratch.textlength(ch, font=f) + tr for ch in b['text']) - tr)
    rw = max(8, int(fw * ease_cubic(p)))
    tmp = tmp.crop((max(0, CX - rw // 2), 0, min(W, CX + rw // 2), TH))
    img.alpha_composite(tmp, (max(0, CX - rw // 2), b['y'] - 80))

def r_badge(d, img, b, lt):
    tl = lt - b['t0']
    if tl <= 0: return
    badge(d, CX, b['cy'], b['r'], b['color'], b['shape'], spring(tl, 170, 0.62))
    ring(d, CX, b['cy'], b['r'], min(1.0, tl / 0.40), b['color'])

def r_wordpop(d, img, b, lt):
    tl = lt - b['t0']
    if tl <= 0: return
    sc_now = 1 + 0.14 * (1 - spring(tl, 160, 0.60))
    sc_prev = 1 + 0.14 * (1 - spring(max(0.0, tl - 1.0 / FPS), 160, 0.60))
    col = b['color'] if tl > 0.05 else NAVY2
    if abs(sc_now - sc_prev) > 0.004:                    # scale-motion blur ghost
        ghost = font('Black', int(b['size'] * sc_prev))
        ctext(d, b['y'] + int(b['size'] * (sc_prev - sc_now) * 0.4), b['text'], ghost, (*col, 70))
    ctext(d, b['y'], b['text'], font('Black', int(b['size'] * sc_now)), col)
    if b.get('rings'):
        ring(d, CX, b['y'] + 100, 60, min(1.0, tl / 0.45), YELLOW)
        ring(d, CX, b['y'] + 100, 60, max(0.0, min(1.0, tl / 0.45) - 0.18), YELLOW)
    if b.get('underline') and tl > 0.45:
        g = ease_cubic(min(1.0, (tl - 0.45) / 0.35))
        wfree = tw(b['text'], 'Black', b['size']) * 0.92
        uy = b['y'] + int(font('Black', b['size']).getmetrics()[0] * 1.12)
        d.rectangle([CX - wfree / 2, uy, CX - wfree / 2 + wfree * g, uy + 12], fill=b['underline'])

def r_button(d, img, b, lt):
    p = min(1.0, max(0.0, (lt - b['t0']) / 0.50))
    if p <= 0: return
    yy = b['y'] + int(40 * (1 - spring(p * 0.50, 170, 0.70)))
    br = 0.5 + 0.5 * math.sin(2 * math.pi * (lt - b['t0']) / 1.1)   # breathing scale
    sc = 1 + 0.012 * br
    w2, h2 = int(640 * sc), int(118 * sc)
    d.rounded_rectangle([CX - w2 // 2 + 10, yy + 10, CX + w2 // 2 + 10, yy + h2 + 10],
                        54, fill=(*PANEL, 255))
    d.rounded_rectangle([CX - w2 // 2, yy, CX + w2 // 2, yy + h2], 54, fill=WHITE)
    fs = int(46 * sc)
    fb = font('Bold', fs)
    w = tw(b['text'], 'Bold', fs)
    d.text((CX - w // 2, yy + (h2 - fs) // 2 + 2), b['text'], font=fb, fill=(6, 26, 51))
    d.rounded_rectangle([CX - w2 // 2 - 9, yy - 8, CX + w2 // 2 + 9, yy + h2 + 8], 59,
                        outline=lerp_c((28, 88, 180), BLUE, br), width=5)

def r_headline(d, img, b, lt):
    ctext(d, b['y'], b['text'], font('Black', b['size']), b['color'])

_pos = {}
for _i, _n in enumerate(ICONS):
    _r, _c = divmod(_i, 4)
    _pos[_n] = (225 + _c * 215 + (107 if _r == 1 else 0), 640 + _r * 250)
ICON_IMGS = {n: Image.open(os.path.join(OUT, 'assets', n + '.png')).resize((210, 210), Image.LANCZOS)
             for n in ICONS}

def r_icons(d, img, b, lt):
    for k, name in enumerate(ICONS):
        tl = lt - b['t0'] - (0.30 + k * 0.42)
        if tl > 0:
            s = max(0.15, spring(tl, 140, 0.55))
            im2 = ICON_IMGS[name].resize((max(8, int(210 * s)), max(8, int(210 * s))), Image.LANCZOS)
            ang = 20 * max(0.0, 1 - tl * 1.5)
            if abs(ang) > 0.5:
                im2 = im2.rotate(ang, expand=True, resample=Image.BICUBIC)
            img.paste(im2, (_pos[name][0] - im2.width // 2, _pos[name][1] - im2.height // 2), im2)
            if tl < 0.40:
                ring(d, _pos[name][0], _pos[name][1], 60, tl / 0.40, BLUE)

def cycler_switches(dur):
    iv = np.linspace(0.48, 0.28, len(DOCS) - 1)
    sw, t = [2.84], 2.84
    for step in iv:
        t += float(step)
        sw.append(round(t, 2))
    return [s for s in sw if s < dur - 0.10]

def r_cycler(d, img, b, lt):
    sw = cycler_switches(b['_dur'])
    if not sw or lt < sw[0]: return
    k = max(i for i, s in enumerate(sw) if lt >= s)
    ctext(d, 1150, DOCS[k], font('SemiBold', 40), YELLOW)
    d.rectangle([CX - 230, 1210, CX + 230, 1215],
                fill=lerp_c(NAVY2, YELLOW, min(1.0, (lt - sw[k]) / 0.08)))

RENDER = {'odometer': r_odometer, 'cascade': r_cascade, 'support': r_support,
          'kicker': r_kicker, 'badge': r_badge, 'wordpop': r_wordpop,
          'button': r_button, 'headline': r_headline, 'icons': r_icons, 'cycler': r_cycler}

def zoom(img, s):
    if abs(s - 1.0) < 0.001: return img
    w2, h2 = int(W / s), int(H / s)
    x0, y0 = (W - w2) // 2, (H - h2) // 2
    return img.crop((x0, y0, x0 + w2, y0 + h2)).resize((W, H), Image.BICUBIC)

def apply_shake(img, lt, impacts):
    for ti in impacts:
        dt = lt - ti
        if 0 <= dt < 0.24:
            a = 1 - dt / 0.24
            return ImageChops.offset(img, int(6 * a * math.sin(46 * dt)), int(4 * a * math.cos(39 * dt)))
    return img

def render_reel(reel, tag):
    scenes = reel['scenes']
    n = int(round(reel['total'] * FPS))
    fd = f'/tmp/ms_{tag}'
    os.system('rm -rf ' + fd)
    os.makedirs(fd, exist_ok=True)
    bounds, t0 = [], 0.0
    for sc in scenes:
        bounds.append((t0, t0 + sc['dur']))
        t0 += sc['dur']
    for i in range(n):
        t = i / FPS
        si = max(k for k, (a, b) in enumerate(bounds) if a <= t)
        a, b = bounds[si]
        sc = scenes[si]
        last = si == len(scenes) - 1
        lt = min(t - a, sc['dur'])
        # ── content layer (RGBA) — matter, on springs
        content = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(content)
        impacts = [bb['strike_at_local'] for bb in sc['beats']
                   if bb['kind'] == 'odometer' and bb.get('strike') and 'strike_at_local' in bb]
        for beat in sc['beats']:
            beat['_dur'] = sc['dur']
            if lt >= beat['t0']:
                RENDER[beat['kind']](d, content, beat, lt)
        content = apply_shake(content, lt, impacts)      # camera shake hits matter, not bg
        # ── transition-in on the content layer
        if sc['trans'] == 'whip' and lt < 0.20:
            p = ease_cubic(lt / 0.20)
            dx = int(150 * (1 - p))
            layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            mask = content.split()[3]
            layer.paste(content, (dx, 0), mask)
            layer.paste(content, (int(dx * 0.6), 0), mask.point(lambda v: v * 110 // 255))
            layer.paste(content, (int(dx * 0.3), 0), mask.point(lambda v: v * 70 // 255))
            content = layer
        if sc['trans'] == 'dissolve' and lt < 0.30:
            p = lt / 0.30
            r, g, bl, al = content.split()
            content = Image.merge('RGBA', (r, g, bl, al.point(lambda v: int(v * p))))
        # ── camera: cubics; parallax bg at 0.35x
        s, fade_p = 1.0, 0.0
        if lt < 0.5 and sc['punch'] > 0:
            s = 1.0 + sc['punch'] * (1 - ease_cubic(lt / 0.5))
        if not last and lt > sc['dur'] - EXIT:
            p = (lt - (sc['dur'] - EXIT)) / EXIT
            s = 1.0 + 0.06 * ease_cubic(p)
            fade_p = ease_cubic(p)
        bg = zoom(BASE, 1.0 + 0.35 * (s - 1.0))
        cz = zoom(content, s)
        img = bg.copy()
        img.paste(cz, (0, 0), cz)
        if fade_p > 0:
            img = Image.blend(img, BASE, fade_p)
        if sc['trans'] == 'flash' and lt < FLASH:
            img = Image.blend(img, WHITE_IMG, 0.30 * (1 - lt / FLASH))
        img.save(f'{fd}/f_{i:04d}.png')
        if i % 120 == 0:
            print(f'  frame {i}/{n}', flush=True)
    return fd, n

def encode(fd, out, dur):
    cmd = [FFMPEG, '-y', '-framerate', str(FPS), '-i', fd + '/f_%04d.png',
           '-f', 'lavfi', '-t', f'{dur:.2f}', '-i', 'anullsrc=r=44100:cl=stereo',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
           '-vf', 'noise=alls=4:allf=t', '-x264-params', 'rc-lookahead=25',
           '-c:a', 'aac', '-b:a', '64k', '-shortest', '-movflags', '+faststart', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-500:])
        raise SystemExit('encode failed')
    print(f'  ✅ {out} {os.path.getsize(out)//1024} KB')

# ═══════════════════════════════ 6. VIDEO QA ENGINE ══════════════════════════
SETTLE_KINDS = ('odometer', 'cascade', 'support', 'kicker', 'wordpop', 'headline', 'badge', 'button')
READ_KINDS = ('odometer', 'cascade', 'support', 'kicker', 'wordpop', 'headline', 'button')
BOX_KINDS = ('odometer', 'cascade', 'support', 'kicker', 'wordpop', 'headline', 'badge', 'button')

def beat_box(b):
    if b['kind'] == 'badge':
        return (b['cy'] - b['r'], b['cy'] + b['r'])
    if b['kind'] == 'button':
        return (b['y'] - 8, b['y'] + 126)
    asc, desc = font(weight_of(b), b['size']).getmetrics()
    nl = len(b['lines']) if b['lines'] else 1
    return (b['y'], b['y'] + nl * (asc + desc))

def qa_reel(reel, fd, n):
    V = []
    scenes = reel['scenes']
    events = events_of(reel)

    def in_event(t):
        return any(a - 0.03 <= t <= b + 0.05 for a, b, _ in events)

    # — TYPOGRAPHY: cut-off at settle + size floor + contrast
    frames_seen = set()
    off = 0.0
    for sc in scenes:
        for b in sc['beats']:
            if b['kind'] in SETTLE_KINDS:
                s = off + max(b['t0'] + entrance_dur(b), TRANS_DUR[sc['trans']]) + 0.08
                idx = int(s * FPS)
                if idx not in frames_seen and 0 <= idx < n:
                    frames_seen.add(idx)
                    arr = np.asarray(Image.open(f'{fd}/f_{idx:04d}.png').convert('RGB')).astype(int)
                    mask = np.abs(arr - NAVY).sum(axis=2) > 60
                    ys, xs = np.nonzero(mask)
                    if len(ys) == 0:
                        V.append(('typography', f"scene {sc['id']}: NO content at settle of "
                                                f"'{b.get('text', b['kind'])[:18]}' [fix:check]"))
                    elif (xs.min() < SAFE['left'] - 2 or xs.max() > SAFE['right'] + 2 or
                          ys.min() < SAFE['top'] - 2 or ys.max() > SAFE['bottom'] + 2):
                        V.append(('typography', f"scene {sc['id']}: content outside safe zone at "
                                                f"'{b.get('text', b['kind'])[:18]}' settle "
                                                f"(x {xs.min()}-{xs.max()}, y {ys.min()}-{ys.max()}) [fix:resize]"))
            if b['text'] and b.get('size', 99) < 24:
                V.append(('typography', f"scene {sc['id']}: '{b['text'][:18]}' at {b['size']}px — "
                                        f"below 24px legibility floor [fix:resize]"))
            if b['text'] and b['kind'] in ('kicker', 'support', 'cascade', 'wordpop', 'headline', 'odometer'):
                r = contrast_ratio(b['color'])
                need = 3.0 if b['size'] >= 24 else 4.5
                if r < need:
                    V.append(('typography', f"scene {sc['id']}: '{b['text'][:18]}' contrast "
                                            f"{r:.1f}:1 < {need}:1 [fix:color]"))
        off += sc['dur']
    # — TIMING: text present at pre-exit (readable window is real)
    off = 0.0
    for sc in scenes:
        pre_t = off + sc['dur'] - (EXIT + 0.05 if sc is not scenes[-1] else 0.05)
        pre = int(pre_t * FPS)
        for b in sc['beats']:
            if b['kind'] not in READ_KINDS or b['exempt']:
                continue
            if b['t0'] + entrance_dur(b) > pre_t - off:
                continue
            if not (0 <= pre < n):
                continue
            arr = np.asarray(Image.open(f'{fd}/f_{pre:04d}.png').convert('RGB')).astype(int)
            y0, y1 = beat_box(b)
            reg = arr[max(0, y0 - 10):min(H, y1 + 10)]
            cols = [b.get('color', WHITE)]
            if b['kind'] == 'odometer':                       # struck → dimmed to MUTED
                cols.append(MUTED)
            strong = sum(int((np.abs(reg - c).sum(axis=2) < 120).sum()) for c in cols)
            if strong < 150:
                V.append(('timing', f"scene {sc['id']}: '{b['text'][:18]}' missing at pre-exit "
                                    f"({strong}px) — readable window not real [fix:retime]"))
        off += sc['dur']
    # — ANIMATION: motion only inside scheduled events
    prev = None
    for i in range(n):
        cur = np.asarray(Image.open(f'{fd}/f_{i:04d}.png').convert('RGB')).astype(np.int16)
        if prev is not None:
            changed = int((np.abs(cur - prev).max(axis=2) > 12).sum())
            if changed > 900 and not in_event(i / FPS):
                V.append(('animation', f'unscheduled motion at t={i / FPS:.2f}s ({changed}px changed)'))
        prev = cur
    # — COMPOSITION: pairwise co-visible collision + hierarchy
    for sc in scenes:
        live = [(beat_box(b), b) for b in sc['beats'] if b['kind'] in BOX_KINDS]
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                (ay0, ay1), ba = live[i]
                (by0, by1), bb = live[j]
                if ay0 < by1 - 6 and by0 < ay1 - 6:
                    V.append(('composition', f"scene {sc['id']}: '{ba.get('text', ba['kind'])[:14]}' and "
                                             f"'{bb.get('text', bb['kind'])[:14]}' boxes overlap "
                                             f"({ay0}-{ay1} vs {by0}-{by1}) [fix:respace]"))
        disp = [b['size'] for b in sc['beats'] if b['kind'] in ('cascade', 'wordpop', 'odometer')]
        kicks = [b['size'] for b in sc['beats'] if b['kind'] == 'kicker']
        if disp and kicks and min(kicks) >= min(disp):
            V.append(('composition', f"scene {sc['id']}: kicker ≥ display text (hierarchy broken)"))
    # — CONSISTENCY: one system across scenes
    for sc in scenes:
        for b in sc['beats']:
            if b['kind'] == 'odometer' and b.get('strike') and b.get('whose') == 'ours':
                V.append(('consistency', f"scene {sc['id']}: struck OUR OWN price '{b['text']}' — "
                                         f"strike means rejection; own price must be underlined [fix:unstrike]"))
    trans = {sc['trans'] for sc in scenes}
    if not trans <= {'flash', 'whip', 'dissolve'}:
        V.append(('consistency', f'unknown transition style in {trans}'))
    return V

def autofix(violations, reel):
    applied = []
    for cat, msg in violations:
        if '[fix:resize]' in msg or 'below 24px' in msg:
            sid = msg.split('scene ')[1][0]
            for sc in reel['scenes']:
                if sc['id'] == sid:
                    for b in sc['beats']:
                        if b['kind'] in ('cascade', 'wordpop', 'odometer') and b['size'] > 40:
                            b['size'] -= 16
                            applied.append(f"  AUTO-FIX resize: scene {sid} '{b['text'][:18]}' → {b['size']}px")
        elif '[fix:unstrike]' in msg:
            sid = msg.split('scene ')[1][0]
            for sc in reel['scenes']:
                if sc['id'] == sid:
                    for b in sc['beats']:
                        if b['kind'] == 'odometer' and b.get('strike'):
                            b['strike'] = None
                            b['whose'] = 'ours'
                            applied.append(f"  AUTO-FIX unstrike: scene {sid} '{b['text']}' → underline presentation")
        elif '[fix:respace]' in msg:
            sid = msg.split('scene ')[1][0]
            for sc in reel['scenes']:
                if sc['id'] == sid:
                    boxes = sorted([(beat_box(b), b) for b in sc['beats'] if b['kind'] in BOX_KINDS])
                    prev_y1 = SAFE['top']
                    for (y0, y1), b in boxes:
                        if y0 < prev_y1 + 18:
                            attr = 'cy' if b['kind'] == 'badge' else 'y'
                            shift = int(prev_y1 + 18 - y0)
                            b[attr] += shift
                            applied.append(f"  AUTO-FIX respace: scene {sid} '{b.get('text', b['kind'])[:16]}' +{shift}px")
                        prev_y1 = max(prev_y1, y1 + 18)
    return applied

# ════════════════════════════════════ PIPELINE ═══════════════════════════════
def build(reel, tag):
    bar = '=' * 62
    print(f'\n{bar}\nMOTIONSTUDIO v4 — {reel["name"]}  ({tag})\n{bar}')
    print('── 1. CONTENT ANALYSIS ──')
    for k in ('purpose', 'audience', 'platform', 'tone', 'peak', 'hierarchy'):
        print(f'  {k:11s} {reel[k]}')
    n_words = sum(len(b['text'].split()) for sc in reel['scenes'] for b in sc['beats'] if b['text'])
    for x in [y for sc in reel['scenes'] for y in sc['beats'] if y['exempt']]:
        print(f"  exemption   '{x['why']}'")
    print(f'  script      {n_words} words / {len(reel["scenes"])} scenes — every word must earn its frame')

    print('── 2. TYPOGRAPHY SOLVER ──')
    for line in solve_sizes(reel):
        print(line)
    for line in solve_layout(reel):
        print(line)
    rows, worst = contrast_report(reel)
    bad = [r for r in rows if not r[4]]
    for txt, col, r, need, _ in rows:
        flag = '✅' if r >= need else '❌'
        print(f'  contrast {flag} {txt:20s} {r:5.1f}:1 (needs {need}:1)')
    print(f'  layouts resolved: safe width {SAFE_W}px · band y{SAFE["top"]}-{SAFE["bottom"]} · '
          f'min contrast margin {worst:.2f}x')

    print('── 3+4. MOTION GRAMMAR + SCHEDULER ──')
    print(f'  grammar: {len(GRAMMAR)} rules; matter on springs, camera on cubics; blur on all fast motion')
    for f in schedule(reel):
        print(f)
    tl = ' · '.join(f"{sc['id']}({sc['role']},{sc['trans']}) {sc['dur']}s" for sc in reel['scenes'])
    print(f'  timeline: {tl} = {reel["total"]}s')
    n_ev = len(events_of(reel))
    print(f'  {n_ev} scheduled motion events registered (QA enforces these windows)')

    for attempt in range(3):
        print(f'── 5. RENDER (pass {attempt + 1}) ──')
        fd, n = render_reel(reel, tag)
        print('── 6. VIDEO QA ENGINE ──')
        V = qa_reel(reel, fd, n)
        for cat in ('typography', 'animation', 'timing', 'composition', 'consistency'):
            hits = [m for cc, m in V if cc == cat]
            print(f'  {cat:12s} ' + ('✅ PASS' if not hits else f'❌ {len(hits)} issue(s)'))
            for m in hits:
                print('      ' + m)
        if not V:
            print('  → 0 violations across all 5 categories. Encoding master.')
            encode(fd, os.path.join(OUT, reel['out']), reel['total'])
            return True
        applied = autofix(V, reel)
        if not applied:
            print('  → violations not auto-fixable — REFUSING to encode. Manual review required.')
            return False
        for a in applied:
            print(a)
        print('  → re-rendering with fixes…')
    return False

if __name__ == '__main__':
    args = sys.argv[1:]
    all_reels = {'reel1': (REEL1, 'r1'), 'reel2': (REEL2, 'r2'),
                 'reel3': (REEL3, 'r3'), 'reel4': (REEL4, 'r4')}
    sel = [a for a in args if a in all_reels or a == 'all'] or ['all']
    if 'all' in sel:
        sel = list(all_reels)
    ok = True
    for name in sel:
        reel, tag = all_reels[name]
        ok &= build(reel, tag)
    sys.exit(0 if ok else 1)
