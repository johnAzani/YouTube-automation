#!/usr/bin/env python3
"""Deep-dive assembler: archival photos + narration -> 16:9 documentary clip.

Ken Burns on stills, chapter kickers, title/end cards, voice muxed via ffmpeg.
Config-driven: add a SCRIPTS entry + narration clips + image-search plates.

Run: .venv/bin/python tools/deep_dive.py [johnstown|enron]
"""
import os, sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1280, 720, 24
NAVY = (6, 26, 51)
YELLOW = (255, 201, 60)
WHITE = (255, 255, 255)
FAINT = (96, 128, 170)

FFMPEG = os.environ.get('FFMPEG_BINARY', 'ffmpeg')
FDIR = os.path.join(ROOT, 'assets', 'fonts')
IMG = os.path.join(ROOT, 'image-search')
AUDIO = os.path.join(ROOT, 'assets', 'deepdive')

def fnt(w, sz):
    return ImageFont.truetype(os.path.join(FDIR, f'Inter-{w}.ttf'), sz)

def duration(path):
    r = subprocess.run([FFMPEG, '-i', path], capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if 'Duration:' in ln:
            hh, mm, rest = ln.split('Duration: ')[1].split(',')[0].strip().split(':')
            return int(hh) * 3600 + int(mm) * 60 + float(rest)
    raise SystemExit(f'no duration for {path}')

def vignette():
    v = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    return v.filter(ImageFilter.GaussianBlur(120))

VIG = vignette()

def ken_burns(path, p, zoom_in):
    im = Image.open(path).convert('RGB')
    z = (1.0 + 0.14 * p) if zoom_in else (1.14 - 0.14 * p)
    cw, ch = int(im.width / z), int(im.height / z)
    drift = (p - 0.5) * 0.10 * (im.width - cw)
    x = int((im.width - cw) / 2 + drift)
    y = int((im.height - ch) / 2 + (p - 0.5) * 0.06 * (im.height - ch))
    im = im.crop((x, y, x + cw, y + ch)).resize((W, H), Image.LANCZOS)
    base = Image.new('RGB', (W, H), NAVY)
    base.paste(im)
    base = Image.composite(base, Image.new('RGB', (W, H), (2, 8, 18)), VIG)
    return base

def kicker(img, text):
    d = ImageDraw.Draw(img)
    f = fnt('SemiBold', 26)
    d.rectangle([40, H - 88, 46, H - 48], fill=YELLOW)
    x = 62
    for ch in text:
        d.text((x, H - 84), ch, font=f, fill=WHITE)
        x += d.textlength(ch, font=f) + 5

def title_card(t1, t2):
    img = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(img)
    f1, f2 = fnt('Black', 78), fnt('SemiBold', 30)
    w = d.textlength(t1, font=f1)
    while w > W - 120:
        f1 = fnt('Black', int(f1.size * 0.94))
        w = d.textlength(t1, font=f1)
    d.text(((W - w) / 2, 268), t1, font=f1, fill=WHITE)
    d.rectangle([(W - w * 0.55) / 2, 386, (W + w * 0.55) / 2, 398], fill=YELLOW)
    w2 = d.textlength(t2, font=f2)
    d.text(((W - w2) / 2, 430), t2, font=f2, fill=FAINT)
    return img

def end_card(t1, t2):
    img = Image.new('RGB', (W, H), NAVY)
    d = ImageDraw.Draw(img)
    f1, f2 = fnt('Black', 84), fnt('Light', 30)
    w = d.textlength(t1, font=f1)
    d.text(((W - w) / 2, 276), t1, font=f1, fill=WHITE)
    d.rectangle([(W - 260) / 2, 392, (W + 260) / 2, 404], fill=YELLOW)
    w2 = d.textlength(t2, font=f2)
    while w2 > W - 160:
        f2 = fnt('Light', int(f2.size * 0.94))
        w2 = d.textlength(t2, font=f2)
    d.text(((W - w2) / 2, 444), t2, font=f2, fill=FAINT)
    return img

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

def main(key):
    cfg = SCRIPTS[key]
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

    title, endc = title_card(*cfg['title']), end_card(*cfg['end'])
    srcs = [os.path.join(IMG, f) for f, _ in scenes]
    for s in srcs:
        if not os.path.exists(s):
            raise SystemExit(f'missing image {s}')
        print(' ', os.path.basename(s), Image.open(s).size)

    proc = subprocess.Popen(
        [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
         '-r', str(FPS), '-i', '-', '-i', nar,
         '-map', '0:v', '-map', '1:a',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    FADE = 0.45
    for i in range(n):
        t = i / FPS
        if t < TITLE:
            frame = title
        elif t < ph1:
            k = int((t - ph0) // per)
            k = min(k, len(scenes) - 1)
            p = (t - ph0 - k * per) / per
            frame = ken_burns(srcs[k], p, zoom_in=(k % 2 == 0))
            kicker(frame, scenes[k][1])
        else:
            frame = endc
        # fade from title into first photo and between photos
        if t >= TITLE - FADE and t < TITLE:
            f2 = ken_burns(srcs[0], 0.0, True)
            a = (t - (TITLE - FADE)) / FADE
            frame = Image.blend(frame, f2, a)
        elif t >= TITLE and t < ph1:
            k = int((t - ph0) // per)
            k = min(k, len(scenes) - 1)
            pos = t - ph0 - k * per
            if k > 0 and pos < FADE:
                f2 = frame
                f1 = ken_burns(srcs[k - 1], 1.0, zoom_in=((k - 1) % 2 == 0))
                frame = Image.blend(f1, f2, pos / FADE)
                kicker(frame, scenes[k][1])
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
        raise SystemExit(f'unknown script {arg!r} — choose from {sorted(SCRIPTS)}')
    main(arg)
