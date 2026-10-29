"""Subscriber Milestone Celebration & Community Gratitude Engine.

Monitors channel subscriber milestones (e.g. 1,000, 1,250, 1,500, 2,000, 5,000),
generates 1080x1080 celebratory Community Tab visual cards, and drafts
pastoral thanksgiving devotionals under the $0.00 cost lock.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .config import CONFIG, REPO_ROOT

CW, CH = 1080, 1080

BG_TOP = (4, 12, 26)          # #040c1a Deep Midnight Blue
BG_BOTTOM = (9, 31, 61)       # #091f3d Deep Royal Sapphire
CARD_FILL = (8, 22, 50, 175)  # rgba(8, 22, 50, 0.68) Frosted Glass
CARD_BORDER = (212, 175, 55, 140)  # Sacred Gold
GOLD_TEXT = (255, 215, 0)
WHITE_TEXT = (255, 255, 255)
MUTED_TEXT = (143, 168, 201)
ICE_TEXT = (188, 222, 252)


@dataclass(frozen=True)
class MilestoneTier:
    subs_target: int
    headline: str
    subheading: str
    scripture_ref: str
    pastoral_message: str


# Canonical Milestone Levels
MILESTONE_TIERS: list[MilestoneTier] = [
    MilestoneTier(
        subs_target=1000,
        headline="1,000 SOULS IN PRAYER",
        subheading="TO GOD BE THE GLORY · YPP MILESTONE REACHED",
        scripture_ref="Psalm 103:1-2",
        pastoral_message=(
            "Beloved prayer family, our hearts overflow with gratitude to God. "
            "Over 1,000 believers from across the nations have gathered into The Secret Place "
            "to seek God's presence, protection, and peace before sleep.\n\n"
            "'Bless the Lord, O my soul, and forget not all His benefits.' (Psalm 103:2)\n\n"
            "Thank you for praying with us every night. Let us know in the comments what nation "
            "you are praying from tonight! Type 'AMEN' and give glory to God! 🙏🕊️✨"
        ),
    ),
    MilestoneTier(
        subs_target=1250,
        headline="1,250 BELIEVERS UNITED",
        subheading="A SANCTUARY OF PEACE ACROSS THE NATIONS",
        scripture_ref="Psalm 34:3",
        pastoral_message=(
            "Over 1,250 souls now abide under the shadow of the Almighty together every night. "
            "'Oh, magnify the Lord with me, and let us exalt His name together.' (Psalm 34:3)\n\n"
            "Drop your prayer requests below — we are interceding over every household represented here. "
            "Peace be upon your home tonight."
        ),
    ),
    MilestoneTier(
        subs_target=1500,
        headline="1,500 STRONG IN FAITH",
        subheading="UNBROKEN NIGHTTIME PRAYER WATCH",
        scripture_ref="Psalm 91:1-2",
        pastoral_message=(
            "1,500 believers standing firm in God's covenant of protection. "
            "He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty.\n\n"
            "Write 'AMEN' to claim His peace over your family tonight!"
        ),
    ),
    MilestoneTier(
        subs_target=2000,
        headline="2,000 SOULS IN COVENANT",
        subheading="MULTITUDES RESTING IN HIS PRESENCE",
        scripture_ref="Psalm 121:1-2",
        pastoral_message=(
            "2,000 faithful praying hearts! Our help comes from the Lord, Maker of heaven and earth. "
            "Thank you for making The Secret Place your evening sanctuary of rest."
        ),
    ),
]


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


def get_current_milestone_status(current_subs: int = 1230) -> tuple[MilestoneTier | None, MilestoneTier | None]:
    """Return (latest_achieved_tier, next_upcoming_tier)."""
    achieved = None
    upcoming = None

    for tier in MILESTONE_TIERS:
        if current_subs >= tier.subs_target:
            achieved = tier
        elif upcoming is None:
            upcoming = tier

    return achieved, upcoming


def render_milestone_card(tier: MilestoneTier, out_path: Path | None = None) -> Image.Image:
    """Render a 1080x1080 celebratory Community Tab card."""
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Midnight sapphire vertical gradient
    for y in range(CH):
        factor = y / CH
        r = int(BG_TOP[0] * (1 - factor) + BG_BOTTOM[0] * factor)
        g = int(BG_TOP[1] * (1 - factor) + BG_BOTTOM[1] * factor)
        b = int(BG_TOP[2] * (1 - factor) + BG_BOTTOM[2] * factor)
        draw.line([(0, y), (CW, y)], fill=(r, g, b, 255))

    # 2. Celestial golden radiant aura
    glow = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = CW // 2, int(CH * 0.35)
    for rad in range(360, 0, -20):
        alpha = int(26 * (1.0 - (rad / 360.0)))
        glow_draw.ellipse(
            [(cx - rad, cy - rad), (cx + rad, cy + rad)],
            fill=(255, 215, 0, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Frosted glassmorphism card
    margin_x = int(CW * 0.08)
    card_rect = [(margin_x, int(CH * 0.12)), (CW - margin_x, int(CH * 0.88))]
    card_layer = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(card_rect, radius=24, fill=CARD_FILL, outline=CARD_BORDER, width=3)
    img = Image.alpha_composite(img, card_layer)
    draw = ImageDraw.Draw(img)

    # 4. Top Header Badge
    font_badge = _get_inter_font(22, "SemiBold")
    badge_text = "THE SECRET PLACE  ·  COMMUNITY MILESTONE CELEBRATION"
    bb = draw.textbbox((0, 0), badge_text, font=font_badge)
    draw.text(((CW - (bb[2] - bb[0])) // 2, int(CH * 0.17)), badge_text, font=font_badge, fill=MUTED_TEXT)

    # 5. Main Headline
    font_hero = _get_inter_font(56, "Black")
    hb = draw.textbbox((0, 0), tier.headline, font=font_hero)
    hw = hb[2] - hb[0]
    draw.text(((CW - hw) // 2 + 3, int(CH * 0.28) + 3), tier.headline, font=font_hero, fill=(0, 0, 0, 220))
    draw.text(((CW - hw) // 2, int(CH * 0.28)), tier.headline, font=font_hero, fill=GOLD_TEXT)

    # 6. Subheading
    font_sub = _get_inter_font(26, "ExtraBold")
    sb = draw.textbbox((0, 0), tier.subheading, font=font_sub)
    draw.text(((CW - (sb[2] - sb[0])) // 2, int(CH * 0.38)), tier.subheading, font=font_sub, fill=WHITE_TEXT)

    # 7. Scripture Badge Box
    sc_rect = [(margin_x + 50, int(CH * 0.46)), (CW - margin_x - 50, int(CH * 0.54))]
    draw.rounded_rectangle(sc_rect, radius=14, fill=(12, 38, 70, 220), outline=GOLD_TEXT, width=1)
    font_sc = _get_inter_font(24, "Bold")
    sc_msg = f"📖  {tier.scripture_ref.upper()}"
    sc_b = draw.textbbox((0, 0), sc_msg, font=font_sc)
    draw.text(((CW - (sc_b[2] - sc_b[0])) // 2, int(CH * 0.485)), sc_msg, font=font_sc, fill=GOLD_TEXT)

    # 8. Message Excerpt
    font_msg = _get_inter_font(28, "Medium")
    msg_lines = [
        "Thank you to every believer who prays with us each night.",
        "May God's divine peace and holy angels surround your home.",
        "Write 'AMEN' below to claim His covenant tonight!",
    ]
    for idx, l in enumerate(msg_lines):
        mb = draw.textbbox((0, 0), l, font=font_msg)
        draw.text(((CW - (mb[2] - mb[0])) // 2, int(CH * 0.60) + (idx * 48)), l, font=font_msg, fill=ICE_TEXT)

    # 9. Footer
    font_foot = _get_inter_font(22, "SemiBold")
    foot_text = "TO GOD BE ALL THE GLORY  ·  THE SECRET PLACE"
    fb = draw.textbbox((0, 0), foot_text, font=font_foot)
    draw.text(((CW - (fb[2] - fb[0])) // 2, int(CH * 0.82)), foot_text, font=font_foot, fill=GOLD_TEXT)

    res = img.convert("RGB")
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res.save(out_path, quality=95)
    return res
