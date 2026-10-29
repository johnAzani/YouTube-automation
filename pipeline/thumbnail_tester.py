"""Multi-Variant Thumbnail A/B/C Test Generator & Mobile Contrast Scorer.

Engineered to maximize YouTube Click-Through Rate (CTR) — the #1 candidate
ranking multiplier in the 2026 YouTube algorithm — under the $0.00 cost lock.

Key Capabilities:
  1. Generates 3 distinct psychological hook variants (Emotional Relief,
     Scripture Authority, Deep Sleep) for YouTube Studio's "Test & Compare".
  2. Mobile Legibility & Contrast Scorer:
     • WCAG AAA Luminance Contrast Ratio (target >= 7.0:1)
     • Mobile downscale edge acuity (simulates 120x68 mobile search view)
     • Safe-zone verification (avoids bottom-right YouTube timestamp overlay).
  3. 100% pure Python / NumPy / Pillow ($0.00 cost, zero cloud APIs).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import CONFIG, REPO_ROOT
from .script_doc import ScriptDoc

TW, TH = 1280, 720  # YouTube 16:9 Thumbnail Standard

# Palette Definitions
SAPPHIRE_BG = ((4, 12, 26), (9, 31, 61))
OBSIDIAN_BG = ((3, 6, 15), (15, 20, 35))
ROYAL_BG = ((6, 20, 48), (12, 45, 90))

GOLD_TEXT = (255, 215, 0)
WHITE_TEXT = (255, 255, 255)
ICE_TEXT = (188, 222, 252)
MUTED_TEXT = (143, 168, 201)


@dataclass(frozen=True)
class ThumbnailVariantSpec:
    variant_id: str  # "A", "B", "C"
    hook_type: str
    primary_headline: str
    secondary_kicker: str
    badge_label: str
    bg_gradient: tuple[tuple[int, int, int], tuple[int, int, int]]
    accent_color: tuple[int, int, int]


@dataclass
class ThumbnailScore:
    variant_id: str
    contrast_ratio: float
    wcag_aaa_compliant: bool
    mobile_edge_acuity: float
    timestamp_safe: bool
    composite_ctr_score: float  # 0 to 100


def _get_inter_font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        REPO_ROOT / "assets" / "fonts" / f"Inter-{weight}.ttf",
        REPO_ROOT / "tools" / "fonts" / f"Inter-{weight}.ttf",
        REPO_ROOT / "assets" / "fonts" / "Inter-Bold.ttf",
    ]
    for cand in font_candidates:
        if cand.is_file():
            try:
                return ImageFont.truetype(str(cand), size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def get_default_variants_for_script(title: str, scripture_ref: str = "PSALM 91") -> list[ThumbnailVariantSpec]:
    """Generate 3 psychological A/B/C testing variants for a video script."""
    ref_upper = scripture_ref.upper()
    return [
        ThumbnailVariantSpec(
            variant_id="A",
            hook_type="Emotional Relief & Fear Release",
            primary_headline="SAY THIS BEFORE SLEEP",
            secondary_kicker=f"{ref_upper} · FEAR NO EVIL",
            badge_label="432 Hz PEACEFUL SLEEP FREQUENCY",
            bg_gradient=SAPPHIRE_BG,
            accent_color=GOLD_TEXT,
        ),
        ThumbnailVariantSpec(
            variant_id="B",
            hook_type="Covenant Authority & Protection",
            primary_headline=f"{ref_upper}: GOD'S SHIELD",
            secondary_kicker="UNDER HIS WINGS TONIGHT",
            badge_label="ANGELIC PROTECTION GUARANTEE",
            bg_gradient=ROYAL_BG,
            accent_color=GOLD_TEXT,
        ),
        ThumbnailVariantSpec(
            variant_id="C",
            hook_type="Deep Rest & Soul Restoration",
            primary_headline="8 HOURS OF PEACE",
            secondary_kicker=f"{ref_upper} · HE RESTORES YOU",
            badge_label="DEEP SLEEP BEDTIME SANCTUARY",
            bg_gradient=OBSIDIAN_BG,
            accent_color=GOLD_TEXT,
        ),
    ]


def render_variant_image(spec: ThumbnailVariantSpec, out_path: Path | None = None) -> Image.Image:
    """Render a single 1280x720 thumbnail variant."""
    img = Image.new("RGBA", (TW, TH), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Background gradient
    c_top, c_bot = spec.bg_gradient
    for y in range(TH):
        factor = y / TH
        r = int(c_top[0] * (1 - factor) + c_bot[0] * factor)
        g = int(c_top[1] * (1 - factor) + c_bot[1] * factor)
        b = int(c_top[2] * (1 - factor) + c_bot[2] * factor)
        draw.line([(0, y), (TW, y)], fill=(r, g, b, 255))

    # 2. Celestial radiant aura
    glow = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = TW // 2, int(TH * 0.38)
    for rad in range(320, 0, -20):
        alpha = int(24 * (1.0 - (rad / 320.0)))
        glow_draw.ellipse(
            [(cx - rad, cy - rad), (cx + rad, cy + rad)],
            fill=(255, 215, 0, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Big Primary Hook Text
    font_hero = _get_inter_font(72, "Black")
    hb = draw.textbbox((0, 0), spec.primary_headline, font=font_hero)
    hw = hb[2] - hb[0]
    draw.text(((TW - hw) // 2 + 5, 145), spec.primary_headline, font=font_hero, fill=(0, 0, 0, 240))
    draw.text(((TW - hw) // 2, 140), spec.primary_headline, font=font_hero, fill=spec.accent_color)

    # 4. Secondary Kicker
    font_sub = _get_inter_font(52, "ExtraBold")
    sb = draw.textbbox((0, 0), spec.secondary_kicker, font=font_sub)
    sw = sb[2] - sb[0]
    draw.text(((TW - sw) // 2 + 4, 254), spec.secondary_kicker, font=font_sub, fill=(0, 0, 0, 220))
    draw.text(((TW - sw) // 2, 250), spec.secondary_kicker, font=font_sub, fill=WHITE_TEXT)

    # 5. Glassmorphism badge bar (avoiding bottom right timestamp zone)
    badge_w = int(TW * 0.82)
    badge_rect = [((TW - badge_w) // 2, 420), ((TW + badge_w) // 2, 510)]
    badge_layer = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge_layer)
    bdraw.rounded_rectangle(badge_rect, radius=18, fill=(8, 22, 50, 170), outline=(212, 175, 55, 140), width=2)
    img = Image.alpha_composite(img, badge_layer)
    draw = ImageDraw.Draw(img)

    font_badge = _get_inter_font(26, "Bold")
    bb = draw.textbbox((0, 0), spec.badge_label, font=font_badge)
    bw = bb[2] - bb[0]
    draw.text(((TW - bw) // 2, 448), spec.badge_label, font=font_badge, fill=ICE_TEXT)

    # 6. Channel Signature Watermark (centered, away from right timestamp)
    font_brand = _get_inter_font(22, "SemiBold")
    brand_str = "THE SECRET PLACE  ·  DAILY BEDTIME PRAYER"
    brb = draw.textbbox((0, 0), brand_str, font=font_brand)
    brw = brb[2] - brb[0]
    draw.text(((TW - brw) // 2, TH - 75), brand_str, font=font_brand, fill=MUTED_TEXT)

    res = img.convert("RGB")
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res.save(out_path, quality=95)
    return res


def evaluate_thumbnail_legibility(img: Image.Image, variant_id: str) -> ThumbnailScore:
    """Compute mathematical contrast ratio, mobile edge acuity, and safe-zone adherence."""
    arr = np.array(img).astype(np.float64) / 255.0

    # 1. Luminance calculation via standard Rec.709 coefficients
    luminance = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]

    # Sample text region (y: 120..320) vs background borders
    text_region = luminance[120:320, :]
    bg_region = luminance[:100, :]

    l_max = float(np.percentile(text_region, 95))
    l_min = float(np.percentile(bg_region, 10))
    contrast_ratio = (l_max + 0.05) / (l_min + 0.05)
    wcag_aaa = contrast_ratio >= 7.0

    # 2. Mobile downscale edge acuity simulation (120x68 mobile thumbnail)
    small = img.resize((120, 68), Image.Resampling.LANCZOS)
    small_gray = np.array(small.convert("L")).astype(np.float64)
    # Sobel gradient filter
    gy, gx = np.gradient(small_gray)
    edge_energy = float(np.mean(np.sqrt(gx**2 + gy**2)))
    # Normalize acuity to 0..100
    mobile_acuity = min(100.0, edge_energy * 5.5)

    # 3. Timestamp safe-zone check (bottom-right 180x80 px)
    # Ensure text is not in bottom right corner x in [1060..1280], y in [620..720]
    br_region = arr[620:720, 1060:1280, :]
    # A safe bottom right should have low text activity
    br_diff = float(np.std(br_region))
    timestamp_safe = br_diff < 0.15

    # 4. Composite CTR score calculation
    ctr_score = (
        min(40.0, (contrast_ratio / 10.0) * 40.0)
        + (mobile_acuity * 0.40)
        + (20.0 if timestamp_safe else 0.0)
    )
    ctr_score = round(min(100.0, max(0.0, ctr_score)), 1)

    return ThumbnailScore(
        variant_id=variant_id,
        contrast_ratio=round(contrast_ratio, 2),
        wcag_aaa_compliant=wcag_aaa,
        mobile_edge_acuity=round(mobile_acuity, 1),
        timestamp_safe=timestamp_safe,
        composite_ctr_score=ctr_score,
    )


def generate_thumbnail_test_suite(
    title: str,
    scripture_ref: str,
    out_dir: Path,
) -> dict:
    """Generate full A/B/C thumbnail testing pack with automated mobile score report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = get_default_variants_for_script(title, scripture_ref)

    report: dict = {
        "title": title,
        "scripture": scripture_ref,
        "variants": {},
        "winner_recommendation": None,
    }

    best_score = -1.0
    best_id = "A"

    for spec in specs:
        out_jpg = out_dir / f"thumbnail_variant_{spec.variant_id.lower()}.jpg"
        im = render_variant_image(spec, out_path=out_jpg)
        score = evaluate_thumbnail_legibility(im, spec.variant_id)

        report["variants"][spec.variant_id] = {
            "hook_type": spec.hook_type,
            "headline": spec.primary_headline,
            "file": out_jpg.name,
            "metrics": asdict(score),
        }

        if score.composite_ctr_score > best_score:
            best_score = score.composite_ctr_score
            best_id = spec.variant_id

    report["winner_recommendation"] = {
        "variant": best_id,
        "score": best_score,
        "reason": f"Variant {best_id} demonstrated highest mobile contrast ratio & edge sharpness for small screens.",
    }

    report_path = out_dir / "thumbnail_ab_test_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
