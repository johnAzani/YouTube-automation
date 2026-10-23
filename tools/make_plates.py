#!/usr/bin/env python3
"""Generate rights-clean editorial plates for scenes with no licensed photo.

Why this exists
---------------
`image-search/LICENSES.yml` records that the `enron-corporation-headquarters-
houston-c-*.jpg`, courtroom, and scandal newspaper stills carry embedded Getty
Images metadata or unverified provenance. They were referenced by scene rows in
`tools/deep_dive.py` and `tools/shorts.py`, blocking clean monetization.

These plates are generated procedurally in the show's own blue-duotone palette,
deliberately *not* photographs of real buildings, newspapers, or individuals,
and carrying zero third-party inputs of any kind.

Provenance is provable rather than asserted, which is what makes them `cleared`
in the ledger where every downloaded still starts as `unverified`:

  * every byte is produced by this file from a fixed seed — no network, no source
    image, no font, no timestamp chunk;
  * generation is byte-reproducible, so the sha256 in the ledger pins exactly
    these pixels and `scripts/licence_ledger.py check` fails if they drift.

Run:  .venv/bin/python tools/make_plates.py
"""
from __future__ import annotations

import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "image-search")

W, H = 1280, 720

# The deep-dive palette (tools/deep_dive.py) so the plates cut together seamlessly.
SKY_TOP = (4, 14, 34)
SKY_HORIZON = (16, 44, 88)
BUILDING = (6, 19, 40)
BUILDING_EDGE = (24, 58, 104)
WINDOW_WARM = (255, 201, 60)
WINDOW_ICE = (170, 210, 248)
CRIMSON = (255, 86, 92)
EMERALD = (72, 232, 164)
HAZE = (58, 104, 168)

BASE_SEED = 20261023
SEED_STEP = 977

# Procedural editorial plates across all Enron deep-dive and Short scenes.
PLATES = [
    "houston-skyline-plate-1.png",
    "houston-skyline-plate-2.png",
    "houston-skyline-plate-3.png",
    "houston-skyline-plate-4.png",
    "houston-skyline-plate-5.png",
    "enron-market-board-plate-1.png",
    "enron-ledger-grid-plate-1.png",
    "enron-pipeline-corridor-plate-1.png",
    "enron-spe-network-plate-1.png",
    "enron-courtroom-columns-plate-1.png",
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


def _skyline_plate(rnd: random.Random) -> Image.Image:
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


def _market_board_plate(rnd: random.Random) -> Image.Image:
    """Trading floor ticker matrix and ascending price candles."""
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Subtle perspective grid across trading board
    for gx in range(80, W, 64):
        d.line([gx, 60, gx, H - 60], fill=(40, 88, 152, 42), width=1)
    for gy in range(84, H - 40, 48):
        d.line([60, gy, W - 60, gy], fill=(40, 88, 152, 42), width=1)

    # Background ticker cells
    for row in range(6):
        ry = 96 + row * 28
        x = 92
        while x < W - 140:
            cw = rnd.randint(28, 74)
            col = WINDOW_WARM if rnd.random() < 0.28 else WINDOW_ICE
            d.rectangle([x, ry, x + cw, ry + 8], fill=col + (rnd.randint(45, 115),))
            x += cw + rnd.randint(12, 26)

    # 22 rising/volatile candlestick bars peaking right of centre
    price = 0.22
    pts: list[tuple[int, int]] = []
    for idx in range(22):
        cx = 128 + idx * 48
        drift = 0.048 if idx < 17 else -0.055
        open_p = price
        close_p = max(0.14, min(0.90, open_p + drift + rnd.uniform(-0.028, 0.035)))
        high_p = min(0.95, max(open_p, close_p) + rnd.uniform(0.02, 0.07))
        low_p = max(0.08, min(open_p, close_p) - rnd.uniform(0.02, 0.06))
        price = close_p

        y_open = int(H * 0.78 - open_p * (H * 0.56))
        y_close = int(H * 0.78 - close_p * (H * 0.56))
        y_high = int(H * 0.78 - high_p * (H * 0.56))
        y_low = int(H * 0.78 - low_p * (H * 0.56))
        up = close_p >= open_p
        bar_col = EMERALD if (up and idx < 16) else (WINDOW_WARM if idx == 16 else CRIMSON)

        d.line([cx, y_high, cx, y_low], fill=bar_col + (215,), width=3)
        top_y, bot_y = min(y_open, y_close), max(y_open, y_close)
        d.rectangle([cx - 12, top_y, cx + 12, max(top_y + 6, bot_y)], fill=bar_col + (210,))
        pts.append((cx, y_close))

        # Volume bar along bottom band
        vh = rnd.randint(22, 86)
        d.rectangle([cx - 10, H - 56 - vh, cx + 10, H - 56], fill=WINDOW_ICE + (78,))

    d.line(pts, fill=WINDOW_WARM + (190,), width=3)
    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


def _ledger_grid_plate(rnd: random.Random) -> Image.Image:
    """Architectural accounting ledger columns with highlighted restatement rows."""
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Twin folio pages in deep navy glass
    for page_idx, px0 in enumerate((136, 664)):
        pw, py0, ph = 480, 76, 568
        d.rounded_rectangle(
            [px0, py0, px0 + pw, py0 + ph],
            radius=14,
            fill=(8, 24, 52, 232),
            outline=BUILDING_EDGE + (190,),
            width=2,
        )
        d.rectangle([px0 + 24, py0 + 24, px0 + pw - 24, py0 + 42], fill=WINDOW_WARM + (185,))
        for r in range(15):
            ry = py0 + 68 + r * 32
            flagged = (page_idx == 1 and r in (4, 8, 11)) or (page_idx == 0 and r == 9)
            if flagged:
                d.rectangle(
                    [px0 + 18, ry - 5, px0 + pw - 18, ry + 17],
                    fill=CRIMSON + (58,),
                    outline=CRIMSON + (165,),
                    width=1,
                )
            stub_w = rnd.randint(90, 190)
            stub_col = CRIMSON if flagged else WINDOW_ICE
            d.rectangle([px0 + 28, ry, px0 + 28 + stub_w, ry + 10], fill=stub_col + (165,))
            for col_i in range(3):
                cx0 = px0 + 252 + col_i * 68
                num_w = rnd.randint(28, 52)
                ncol = WINDOW_WARM if flagged else (140, 184, 232)
                d.rectangle([cx0 + (54 - num_w), ry, cx0 + 54, ry + 10], fill=ncol + (185,))

    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


def _pipeline_corridor_plate(rnd: random.Random) -> Image.Image:
    """Receding industrial transmission pipelines converging toward a dusk horizon."""
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    _stars(d, rnd)

    horizon_y = int(H * 0.44)
    vanish_x = int(W * 0.56)

    # Distant compressor silhouettes along the horizon
    for sx in range(120, W - 120, 118):
        sh = rnd.randint(34, 88)
        sw = rnd.randint(40, 82)
        d.rectangle([sx, horizon_y - sh, sx + sw, horizon_y], fill=BUILDING + (245,))
        d.line([sx, horizon_y - sh, sx + sw, horizon_y - sh], fill=BUILDING_EDGE + (210,), width=2)
        if rnd.random() < 0.45:
            d.ellipse([sx + sw // 2 - 3, horizon_y - sh - 12, sx + sw // 2 + 3, horizon_y - sh - 6],
                      fill=WINDOW_WARM + (225,))

    # Ground plane
    d.rectangle([0, horizon_y, W, H], fill=(5, 16, 36, 255))

    # Three converging steel transmission pipes with rim highlights
    for offset, spread in ((-250, -520), (0, -70), (240, 420)):
        p_near_l = vanish_x + spread - 58
        p_near_r = vanish_x + spread + 58
        p_far_l = vanish_x + offset // 8 - 8
        p_far_r = vanish_x + offset // 8 + 8
        d.polygon(
            [(p_far_l, horizon_y), (p_far_r, horizon_y), (p_near_r, H), (p_near_l, H)],
            fill=(14, 38, 76, 248),
        )
        d.line([(p_far_l, horizon_y), (p_near_l, H)], fill=WINDOW_ICE + (195,), width=3)
        d.line([(p_far_r, horizon_y), (p_near_r, H)], fill=BUILDING_EDGE + (220,), width=2)
        mid_near = (p_near_l * 2 + p_near_r) // 3
        mid_far = (p_far_l * 2 + p_far_r) // 3
        d.line([(mid_far, horizon_y), (mid_near, H)], fill=WINDOW_WARM + (95,), width=2)

    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


def _spe_network_plate(rnd: random.Random) -> Image.Image:
    """Central balance-sheet monolith wired to off-balance-sheet satellite vaults."""
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx, cy = W // 2, H // 2
    satellites: list[tuple[int, int, tuple[int, int, int]]] = []
    count = 9
    for idx in range(count):
        ang = (2.0 * math.pi * idx / count) - 0.35
        rad_x = 390 + rnd.randint(-28, 28)
        rad_y = 225 + rnd.randint(-20, 20)
        sx = int(cx + math.cos(ang) * rad_x)
        sy = int(cy + math.sin(ang) * rad_y)
        col = CRIMSON if idx % 3 == 0 else WINDOW_WARM
        satellites.append((sx, sy, col))

    # Conduits between central monolith and off-book vaults
    for sx, sy, col in satellites:
        d.line([(cx, cy), (sx, sy)], fill=col + (145,), width=3)
        mx, my = (cx + sx) // 2, (cy + sy) // 2
        d.ellipse([mx - 5, my - 5, mx + 5, my + 5], fill=col + (225,))

    for sx, sy, col in satellites:
        d.rounded_rectangle(
            [sx - 56, sy - 34, sx + 56, sy + 34],
            radius=10,
            fill=(8, 24, 52, 238),
            outline=col + (205,),
            width=2,
        )
        d.rectangle([sx - 38, sy - 12, sx + 38, sy - 3], fill=WINDOW_ICE + (175,))
        d.rectangle([sx - 38, sy + 7, sx + 18, sy + 15], fill=col + (195,))

    # Central corporate tower block
    d.rounded_rectangle(
        [cx - 104, cy - 86, cx + 104, cy + 86],
        radius=16,
        fill=(10, 30, 64, 248),
        outline=WINDOW_ICE + (225,),
        width=3,
    )
    for row in range(4):
        ry = cy - 54 + row * 28
        d.rectangle([cx - 72, ry, cx + 72, ry + 12], fill=WINDOW_WARM + (190 if row == 0 else 115,))

    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


def _courtroom_columns_plate(rnd: random.Random) -> Image.Image:
    """Neoclassical federal courthouse colonnade with diagonal shafts of light."""
    img = Image.new("RGBA", (W, H), SKY_TOP + (255,))
    _sky(img)

    # Soft diagonal light beams behind colonnade
    beams = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beams)
    for bx in (210, 520, 830):
        bd.polygon(
            [(bx, 0), (bx + 150, 0), (bx + 340, H), (bx + 130, H)],
            fill=(170, 210, 248, 36),
        )
    beams = beams.filter(ImageFilter.GaussianBlur(28))
    img.alpha_composite(beams)

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    # Entablature and stepped podium
    d.rectangle([60, 56, W - 60, 118], fill=(8, 24, 52, 248), outline=BUILDING_EDGE + (220,), width=2)
    d.line([60, 118, W - 60, 118], fill=WINDOW_WARM + (190,), width=3)
    for step in range(3):
        sy = H - 96 + step * 28
        inset = 54 - step * 18
        d.rectangle([inset, sy, W - inset, sy + 28], fill=(8, 22, 48, 250), outline=BUILDING_EDGE + (185,), width=2)

    # Six fluted columns with lit left edge
    for idx in range(6):
        cx = 166 + idx * 190
        cw = 74
        top_y, bot_y = 118, H - 96
        d.rectangle([cx - cw // 2 - 10, top_y, cx + cw // 2 + 10, top_y + 20],
                    fill=(14, 38, 76, 252), outline=WINDOW_ICE + (165,), width=2)
        d.rectangle([cx - cw // 2, top_y + 20, cx + cw // 2, bot_y - 18], fill=(9, 27, 58, 252))
        d.rectangle([cx - cw // 2, top_y + 20, cx - cw // 2 + 14, bot_y - 18], fill=WINDOW_ICE + (72,))
        for flute in range(-22, 28, 12):
            fx = cx + flute
            d.line([fx, top_y + 28, fx, bot_y - 24], fill=(4, 13, 30, 175), width=2)
        d.rectangle([cx - cw // 2 - 12, bot_y - 18, cx + cw // 2 + 12, bot_y],
                    fill=(14, 38, 76, 252), outline=WINDOW_ICE + (165,), width=2)

    # Subtle dust motes in light beams
    for _ in range(90):
        mx = rnd.randrange(120, W - 120)
        my = rnd.randrange(130, H - 110)
        d.point((mx, my), fill=WINDOW_WARM + (rnd.randint(45, 135),))

    img.alpha_composite(layer)
    _haze(img)
    _vignette(img)
    return img.convert("RGB")


_THEMED_BUILDERS = {
    5: _market_board_plate,
    6: _ledger_grid_plate,
    7: _pipeline_corridor_plate,
    8: _spe_network_plate,
    9: _courtroom_columns_plate,
}


def make_plate(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    delta = seed - BASE_SEED
    if delta >= 0 and delta % SEED_STEP == 0:
        idx = delta // SEED_STEP
        builder = _THEMED_BUILDERS.get(idx)
        if builder is not None:
            return builder(rnd)
    return _skyline_plate(rnd)


def ensure_plates() -> None:
    """Build missing plates only; never hide changed bytes from the ledger check."""
    os.makedirs(IMG, exist_ok=True)
    for i, name in enumerate(PLATES):
        out = os.path.join(IMG, name)
        if not os.path.exists(out):
            make_plate(seed=BASE_SEED + i * SEED_STEP).save(out, "PNG", optimize=True)


def main(argv: list[str] | None = None) -> int:
    _ = list(sys.argv[1:] if argv is None else argv)
    os.makedirs(IMG, exist_ok=True)
    for i, name in enumerate(PLATES):
        out = os.path.join(IMG, name)
        make_plate(seed=BASE_SEED + i * SEED_STEP).save(out, "PNG", optimize=True)
        print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")
    print("\nThese plates are generated, so they are `cleared` in the ledger — record")
    print("the licence and this file as their source before running licence_ledger.py check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
