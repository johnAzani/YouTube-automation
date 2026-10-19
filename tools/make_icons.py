#!/usr/bin/env python3
"""Generates the 7 MotionStudio reel-grid icons into social/assets/ (210x210 RGBA)."""
import os
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'social', 'assets')
S = 210
NAVY = (6, 26, 51, 255)
PANEL = (15, 61, 124, 255)
BORDER = (74, 140, 255, 160)
WHITE = (255, 255, 255, 255)
YELLOW = (255, 201, 60, 255)
GREEN = (46, 204, 107, 255)

def base():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, S - 3, S - 3], radius=44, fill=PANEL, outline=BORDER, width=4)
    return img, d

def save(name, img):
    img.save(os.path.join(OUT, name + '.png'))
    print('  icon', name)

def icon_agreement():
    img, d = base()
    d.rounded_rectangle([52, 30, 158, 182], radius=12, fill=WHITE)
    d.polygon([(136, 30), (158, 52), (136, 52)], fill=PANEL)
    d.rectangle([136, 30, 158, 52], outline=PANEL)
    for y in (78, 102, 126):
        d.line([(68, y), (142, y)], fill=PANEL, width=9)
    d.line([(70, 156), (100, 150), (118, 162), (140, 152)], fill=YELLOW, width=8, joint='curve')
    return img

def icon_receipt():
    img, d = base()
    d.rounded_rectangle([58, 34, 152, 170], radius=10, fill=WHITE)
    pts = [(58, 170)]
    x = 58
    up = True
    while x < 152:
        pts.append((x + 9.4, 170 + (12 if up else 0)))
        up = not up
        x += 9.4
    pts.append((152, 170))
    d.polygon(pts, fill=PANEL)
    for y in (62, 88, 114):
        d.line([(72, y), (138, y)], fill=PANEL, width=8)
    d.ellipse([92, 132, 118, 158], outline=YELLOW, width=7)
    return img

def icon_seal():
    img, d = base()
    d.polygon([(86, 140), (105, 175), (124, 140), (124, 178), (86, 178)], fill=YELLOW)
    d.ellipse([53, 38, 157, 142], fill=WHITE)
    d.ellipse([67, 52, 143, 128], outline=PANEL, width=8)
    star = []
    import math
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = 30 if i % 2 == 0 else 13
        star.append((105 + r * math.cos(ang), 90 + r * math.sin(ang)))
    d.polygon(star, fill=PANEL)
    return img

def icon_house():
    img, d = base()
    d.polygon([(105, 32), (32, 96), (178, 96)], fill=WHITE)
    d.rounded_rectangle([52, 92, 158, 180], radius=8, fill=WHITE)
    d.rounded_rectangle([88, 118, 122, 180], radius=6, fill=PANEL)
    d.rounded_rectangle([62, 108, 84, 132], radius=4, fill=PANEL)
    d.rounded_rectangle([126, 108, 148, 132], radius=4, fill=PANEL)
    return img

def icon_shield():
    img, d = base()
    d.polygon([(105, 28), (172, 56), (172, 108), (105, 184), (38, 108), (38, 56)], fill=WHITE)
    d.line([(72, 102), (96, 130), (142, 72)], fill=GREEN, width=16, joint='curve')
    return img

def icon_clock():
    img, d = base()
    d.ellipse([42, 42, 168, 168], fill=WHITE)
    d.ellipse([56, 56, 154, 154], outline=PANEL, width=7)
    d.line([(105, 105), (105, 72)], fill=PANEL, width=10)
    d.line([(105, 105), (132, 118)], fill=PANEL, width=10)
    d.ellipse([99, 99, 111, 111], fill=YELLOW)
    for ang, (dx, dy) in {'top': (0, -1), 'bot': (0, 1), 'left': (-1, 0), 'right': (1, 0)}.items():
        d.line([(105 + dx * 52, 105 + dy * 52), (105 + dx * 60, 105 + dy * 60)], fill=PANEL, width=8)
    return img

def icon_coin():
    img, d = base()
    d.ellipse([42, 42, 168, 168], fill=WHITE)
    d.ellipse([56, 56, 154, 154], outline=YELLOW, width=8)
    # geometric naira sign: N with two horizontal strikes
    d.line([(82, 78), (82, 132)], fill=PANEL, width=11)
    d.line([(128, 78), (128, 132)], fill=PANEL, width=11)
    d.line([(82, 78), (128, 132)], fill=PANEL, width=11)
    d.line([(72, 92), (138, 92)], fill=PANEL, width=7)
    d.line([(72, 112), (138, 112)], fill=PANEL, width=7)
    return img

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    save('icon-agreement', icon_agreement())
    save('icon-receipt', icon_receipt())
    save('icon-seal', icon_seal())
    save('icon-house', icon_house())
    save('icon-shield', icon_shield())
    save('icon-clock', icon_clock())
    save('icon-coin', icon_coin())
