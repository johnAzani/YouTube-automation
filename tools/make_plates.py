#!/usr/bin/env python3
"""Generate rights-clean skyline plates for scenes with no licensed photo.

Why this exists
---------------
`image-search/LICENSES.yml` records that all five `enron-corporation-headquarters-
houston-c-*.jpg` stills carry embedded Getty Images rights metadata. They were
referenced by scene rows in `tools/deep_dive.py` and `tools/shorts.py`, so
the Enron deep dive and the Enron Short could not be monetized — and nothing
stopped a human from uploading them anyway, because the only signal was a warning
printed above 1,200 frames of render output.

There is no licensed Houston skyline in the pool to swap in (verified: the 35
non-encumbered files are Fastow/courtroom/newspaper/Johnstown/pipeline images and
nothing else). So these plates are generated instead: an abstract night skyline in
the show's own blue-duotone palette, deliberately *not* a depiction of the real
Enron Center and carrying no third-party content of any kind.

Provenance is provable rather than asserted, which is what makes them `cleared` in
the ledger where every downloaded still starts as `unverified`:

  * every byte is produced by this file from a fixed seed — no network, no source
    image, no font, no timestamp chunk;
  * generation is byte-reproducible, so the sha256 in the ledger pins exactly
    these pixels and `scripts/licence_ledger.py check` fails if they drift.

Run:  .venv/bin/python tools/make_plates.py
"""
from __future__ import annotations

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "image-search")

W, H = 1280, 720

# The deep-dive palette (tools/deep_dive.py) so the plates cut together with the
# authored stills instead of looking pasted in.
SKY_TOP = (4, 14, 34)
SKY_HORIZON = (16, 44, 88)
BUILDING = (6, 19, 40)
BUILDING_EDGE = (24, 58, 104)
WINDOW_WARM = (255, 201, 60)
WINDOW_ICE = (170, 210, 248)
HAZE = (58, 104, 168)

# One plate per encumbered Houston HQ still it replaces.
PLATES = [
    "houston-skyline-plate-1.png",
    "houston-skyline-plate-2.png",
    "houston-skyline-plate-3.png",
    "houston-skyline-plate-4.png",
    "houston-skyline-plate-5.png",
]


def _sky(img: Image.Image) -> None:
    """Vertical gradient plus a star field."""
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        # Ease so the brightening bunches near the horizon, like city light spill.
        e = t ** 1.7
        r = int(SKY_TOP[0] + (SKY_HORIZON[0] - SKY_TOP[0]) * e)
        g = int(SKY_TOP[1] + (SKY_HORIZON[1] - SKY_TOP[1]) * e)
        b = int(SKY_TOP[2] + (SKY_HORIZON[2] - SKY_TOP[2]) * e)
        for x in range(W):
            px[x, y] = (r, g, b)


def _stars(d: ImageDraw.ImageDraw, rnd: random.Random) -> None:
    for _ in range(150):
        x = rnd.randrange(W)
        y = rnd.randrange(int(H * 0.55))
        a = rnd.randint(40, 150)
        d.point((x, y), fill=(200, 220, 255, a))


def _building(d: ImageDraw.ImageDraw, rnd: random.Random,
              x: int, w: int, top: int, beacon: bool = False) -> None:
    d.rectangle([x, top, x + w, H], fill=BUILDING + (255,))
    d.line([x, top, x + w, top], fill=BUILDING_EDGE + (255,), width=2)
    # Window grid: mostly dark, a sparse warm/ice scatter so it reads at night.
    step_x, step_y = 14, 20
    for wy in range(top + 12, H - 8, step_y):
        for wx in range(x + 6, x + w - 6, step_x):
            roll = rnd.random()
            if roll < 0.13:
                d.rectangle([wx, wy, wx + 5, wy + 7], fill=WINDOW_WARM + (rnd.randint(120, 235),))
            elif roll < 0.18:
                d.rectangle([wx, wy, wx + 5, wy + 7], fill=WINDOW_ICE + (rnd.randint(70, 150),))
    if beacon:
        bx = x + w // 2
        d.line([bx, top - 26, bx, top], fill=BUILDING_EDGE + (255,), width=3)
        d.ellipse([bx - 4, top - 34, bx + 4, top - 26], fill=(255, 92, 96, 235))


def _haze(img: Image.Image) -> None:
    """Light-pollution band sitting on the horizon."""
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    bd.rectangle([0, int(H * 0.62), W, H], fill=HAZE + (58,))
    band = band.filter(ImageFilter.GaussianBlur(46))
    img.alpha_composite(band)


def _vignette(img: Image.Image) -> None:
    v = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(v)
    d.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(120))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade.putalpha(v.point(lambda p: 255 - int(p * 0.55)))
    img.alpha_composite(shade)


def make_plate(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    _stars(d, rnd)

    # Back row: distant, low, dimmer. Then a front row that overlaps it.
    x = -20
    while x < W + 40:
        w = rnd.randint(46, 104)
        top = rnd.randint(int(H * 0.46), int(H * 0.60))
        _building(d, rnd, x, w, top)
        x += w + rnd.randint(4, 16)

    x = -30
    while x < W + 40:
        w = rnd.randint(64, 148)
        top = rnd.randint(int(H * 0.30), int(H * 0.52))
        _building(d, rnd, x, w, top, beacon=rnd.random() < 0.18)
        x += w + rnd.randint(10, 30)

    # One clearly dominant tower per plate, placed off-centre for a camera move.
    tw = rnd.randint(96, 132)
    tx = int(W * rnd.uniform(0.24, 0.66))
    _building(d, rnd, tx, tw, int(H * 0.14), beacon=True)

    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


def ensure_plates() -> None:
    """Build missing plates only; never hide changed bytes from the ledger check."""
    os.makedirs(IMG, exist_ok=True)
    for i, name in enumerate(PLATES):
        out = os.path.join(IMG, name)
        if not os.path.exists(out):
            make_plate(seed=20261023 + i * 977).save(out, "PNG", optimize=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    os.makedirs(IMG, exist_ok=True)
    for i, name in enumerate(PLATES):
        out = os.path.join(IMG, name)
        make_plate(seed=20261023 + i * 977).save(out, "PNG", optimize=True)
        print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")
    print("\nThese plates are generated, so they are `cleared` in the ledger — record")
    print("the licence and this file as their source before running licence_ledger.py check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
