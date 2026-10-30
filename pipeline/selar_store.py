"""Selar Digital Store & Off-Platform Monetization Engine.

Enables immediate, $0-cost revenue generation for Nigerian & international creators
via Selar.co before reaching YouTube's 4,000 public watch hours AdSense threshold.

Capabilities:
  1. Automated authoring of digital products (30-Night Scripture Protection Prayer Journal PDF/MD,
     Offline 432 Hz Bedtime Audio Packs).
  2. Multi-currency checkout support (USD, GBP, EUR, NGN) depositing directly into
     the user's First Bank USD Domiciliary Account or local bank account.
  3. 1080x1080 DOCOGA REELS v2 sapphire glassmorphism product mockup cover generation.
  4. Non-intrusive social pack integration with zero commercial slang or pressure.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from PIL import Image, ImageDraw, ImageFont

from .config import CONFIG, REPO_ROOT

DEFAULT_SELAR_STORE_URL = os.environ.get("SELAR_STORE_URL", "https://selar.com/showlove/thesecretplace")
PRODUCTS_DIR = REPO_ROOT / "content" / "products"

# Visual Theme Constants (DOCOGA REELS v2 Standard)
BG_TOP = (4, 12, 26)          # #040c1a Deep Midnight Blue
BG_BOTTOM = (9, 31, 61)       # #091f3d Deep Royal Sapphire
CARD_FILL = (8, 22, 50, 180)  # Frosted Glass
CARD_BORDER = (212, 175, 55, 150)  # Sacred Gold
GOLD_TEXT = (255, 215, 0)
WHITE_TEXT = (255, 255, 255)
MUTED_TEXT = (143, 168, 201)
ICE_TEXT = (188, 222, 252)


@dataclass(frozen=True)
class SelarProduct:
    product_id: str
    title: str
    subtitle: str
    price_usd: float
    is_pay_what_you_want: bool
    suggested_usd: float
    category: str
    description: str
    features: list[str]
    cover_image_name: str


CANONICAL_SELAR_PRODUCTS: list[SelarProduct] = [
    SelarProduct(
        product_id="prod-001-offline-audio-sanctuary",
        title="432 Hz Offline Bedtime Sleep Sanctuary Audio Pack",
        subtitle="Ad-Free Night Prayers · Full HD WAV & MP3 · Airplane Mode Ready",
        price_usd=0.0,
        is_pay_what_you_want=True,
        suggested_usd=5.0,
        category="Digital Audio Download",
        description=(
            "Rest tonight without Wi-Fi, battery drain, screen glare, or mid-roll advertisements. "
            "This official offline audio pack features all canonical night prayers from The Secret Place "
            "(Psalms 91, 23, 121, 27, 46, and 34) mastered at 432 Hz Solfeggio frequency with "
            "1.5 Hz Delta brainwave entrainment for uninterrupted, restorative sleep.\n\n"
            "Included Files:\n"
            "• High-Definition 320kbps MP3s + Studio Master WAVs\n"
            "• 1-Hour Continuous Bedtime Peace Session\n"
            "• 3-Hour Continuous Night Watch Meditation\n"
            "• Complete Bedtime Scripture Printable Companion Guide"
        ),
        features=[
            "100% Ad-Free Listening",
            "Listen in Airplane Mode with Screen Turned Off",
            "Mastered in 432 Hz Sacred Solfeggio Tuning",
            "EBU R128 Loudness Optimized (-16 LUFS Sleep Standard)",
            "Lifetime Download Access & Instant Delivery",
        ],
        cover_image_name="cover_offline_audio_pack.png",
    ),
    SelarProduct(
        product_id="prod-002-prayer-journal-pdf",
        title="30-Night Scripture Protection Prayer Journal & Bedtime Declarations",
        subtitle="Printable PDF Guide · Scripture Liturgies · Evening Declarations",
        price_usd=0.0,
        is_pay_what_you_want=True,
        suggested_usd=3.0,
        category="Digital PDF Book & Printable",
        description=(
            "Anchor your home under God's covenant of protection every evening. "
            "The 30-Night Scripture Protection Prayer Journal is a reverent, printable bedside companion "
            "designed to accompany your nightly prayer watch. Each evening features a focal Psalm, "
            "written biblical commentary from The Secret Place, declarations of peace, and space "
            "for personal gratitude before sleep."
        ),
        features=[
            "30 Complete Nightly Scripture Devotionals",
            "Angelic Protection & Covenant Declarations",
            "Printable Bedside Format (A4 & US Letter PDF)",
            "Mobile-Friendly Reading Format for Tablets & Phones",
            "Pay-What-You-Want ($0 Free Access for All Believers)",
        ],
        cover_image_name="cover_prayer_journal.png",
    ),
    SelarProduct(
        product_id="prod-003-ministry-covenant-partner",
        title="The Secret Place Ministry Partner / Covenant Offering",
        subtitle="Support Our Global Mission to Keep Scripture Prayers Free Forever",
        price_usd=5.0,
        is_pay_what_you_want=True,
        suggested_usd=10.0,
        category="Community Membership / Offering",
        description=(
            "Support the daily production and global broadcast of peaceful scripture meditations. "
            "Your monthly covenant offering helps us keep nighttime prayers free, ad-free, and accessible "
            "to millions of believers, hospital patients, and seekers worldwide who suffer from "
            "insomnia, fear, and nighttime anxiety."
        ),
        features=[
            "Partner in Ministry Outreach Across 120+ Nations",
            "Monthly Digital Prayer Letter & Scripture Wallpaper Pack",
            "Special Community Prayer Wall Commemoration",
            "Cancel or Adjust Giving at Any Time",
        ],
        cover_image_name="cover_ministry_partner.png",
    ),
]


def _get_inter_font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    cand_paths = [
        REPO_ROOT / "assets" / "fonts" / f"Inter-{weight}.ttf",
        REPO_ROOT / "tools" / "fonts" / f"Inter-{weight}.ttf",
        REPO_ROOT / "assets" / "fonts" / "Inter-Bold.ttf",
    ]
    for c in cand_paths:
        if c.is_file():
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def render_selar_product_cover(product: SelarProduct, out_path: Path | None = None) -> Image.Image:
    """Render a 1080x1080 high-conversion DOCOGA REELS v2 product mockup cover for Selar."""
    W, H = 1080, 1080
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Midnight Sapphire Gradient
    for y in range(H):
        factor = y / H
        r = int(BG_TOP[0] * (1 - factor) + BG_BOTTOM[0] * factor)
        g = int(BG_TOP[1] * (1 - factor) + BG_BOTTOM[1] * factor)
        b = int(BG_TOP[2] * (1 - factor) + BG_BOTTOM[2] * factor)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # 2. Celestial Golden Halo
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    cx, cy = W // 2, int(H * 0.36)
    for rad in range(350, 0, -20):
        alpha = int(24 * (1.0 - (rad / 350.0)))
        gdraw.ellipse([(cx - rad, cy - rad), (cx + rad, cy + rad)], fill=(255, 215, 0, alpha))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Frosted Glassmorphic Center Card
    margin = 80
    card_rect = [(margin, 120), (W - margin, H - 120)]
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card)
    cdraw.rounded_rectangle(card_rect, radius=24, fill=CARD_FILL, outline=CARD_BORDER, width=2)
    img = Image.alpha_composite(img, card)
    draw = ImageDraw.Draw(img)

    # 4. Kicker Badge
    font_badge = _get_inter_font(22, "SemiBold")
    badge = "THE SECRET PLACE  ·  OFFICIAL DIGITAL SANCTUARY"
    bb = draw.textbbox((0, 0), badge, font=font_badge)
    draw.text(((W - (bb[2] - bb[0])) // 2, 170), badge, font=font_badge, fill=MUTED_TEXT)

    # 5. Product Title (Multi-line centered)
    font_title = _get_inter_font(46, "Black")
    words = product.title.split()
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        line_str = " ".join(cur)
        if draw.textbbox((0, 0), line_str, font=font_title)[2] > (W - margin * 2 - 80):
            cur.pop()
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))

    start_y = 260
    for idx, l in enumerate(lines[:3]):
        tb = draw.textbbox((0, 0), l, font=font_title)
        tw = tb[2] - tb[0]
        y_pos = start_y + (idx * 56)
        draw.text(((W - tw) // 2 + 2, y_pos + 2), l, font=font_title, fill=(0, 0, 0, 200))
        draw.text(((W - tw) // 2, y_pos), l, font=font_title, fill=GOLD_TEXT)

    # 6. Subtitle
    font_sub = _get_inter_font(24, "Medium")
    sub_lines = [product.subtitle]
    if len(product.subtitle) > 45:
        parts = product.subtitle.split("·")
        sub_lines = [p.strip() for p in parts]

    cur_sub_y = start_y + (len(lines[:3]) * 56) + 30
    for sl in sub_lines[:2]:
        sb = draw.textbbox((0, 0), sl, font=font_sub)
        draw.text(((W - (sb[2] - sb[0])) // 2, cur_sub_y), sl, font=font_sub, fill=WHITE_TEXT)
        cur_sub_y += 34

    # 7. Features Box
    feat_top = max(cur_sub_y + 35, 540)
    feat_rect = [(margin + 40, feat_top), (W - margin - 40, feat_top + 220)]
    draw.rounded_rectangle(feat_rect, radius=16, fill=(10, 30, 60, 220), outline=(212, 175, 55, 100), width=1)

    font_feat = _get_inter_font(22, "SemiBold")
    for f_idx, feat in enumerate(product.features[:4]):
        fy = feat_top + 25 + (f_idx * 46)
        draw.text((margin + 70, fy), f"✓  {feat}", font=font_feat, fill=ICE_TEXT)

    # 8. Pricing & Access Badge
    font_price = _get_inter_font(26, "Bold")
    price_text = f"PAY WHAT YOU WANT  ·  SUGGESTED ${product.suggested_usd:.2f} USD" if product.is_pay_what_you_want else f"${product.price_usd:.2f} USD"
    pb = draw.textbbox((0, 0), price_text, font=font_price)
    draw.text(((W - (pb[2] - pb[0])) // 2, H - 200), price_text, font=font_price, fill=GOLD_TEXT)

    # 9. Direct Payout Note
    font_note = _get_inter_font(18, "Regular")
    note = "INSTANT EMAIL DELIVERY  ·  SECURE GLOBAL PAYMENT (USD / GBP / EUR / NGN)"
    nb = draw.textbbox((0, 0), note, font=font_note)
    draw.text(((W - (nb[2] - nb[0])) // 2, H - 155), note, font=font_note, fill=MUTED_TEXT)

    res = img.convert("RGB")
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res.save(out_path, quality=95)
    return res


def export_selar_product_manifests(out_dir: Path = PRODUCTS_DIR) -> list[Path]:
    """Generate all product listing manifests and visual covers in content/products/."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    for prod in CANONICAL_SELAR_PRODUCTS:
        # 1. Render Cover Card
        cover_path = out_dir / prod.cover_image_name
        render_selar_product_cover(prod, out_path=cover_path)
        generated.append(cover_path)

        # 2. Write Product Listing Spec
        spec_path = out_dir / f"{prod.product_id}.json"
        manifest_data = {
            "product_id": prod.product_id,
            "title": prod.title,
            "subtitle": prod.subtitle,
            "category": prod.category,
            "price_usd": prod.price_usd,
            "is_pay_what_you_want": prod.is_pay_what_you_want,
            "suggested_price_usd": prod.suggested_usd,
            "cover_image": prod.cover_image_name,
            "features": prod.features,
            "description": prod.description,
            "selar_payout_target": "First Bank of Nigeria USD Domiciliary Account (FBNINGLA)",
            "store_url_placeholder": f"{DEFAULT_SELAR_STORE_URL}/{prod.product_id}",
        }
        spec_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        generated.append(spec_path)

    return generated
