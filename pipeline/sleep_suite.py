"""Multi-Hour Bedtime Sleep Sanctuary Engine for The Secret Place.

Engineered specifically to accelerate YouTube Partner Program (YPP) watch hours
toward the 4,000-hour threshold at strict $0.00 / month cost lock.

Combines:
  1. Multi-movement biblical scripture liturgies (Psalms 91, 23, 121, 27 + Benediction).
  2. Procedural 432 Hz Solfeggio tuning + Delta brainwave binaural entrainment (1.5 Hz)
     with low-pass filtered acoustic rain/stream beds synthesized via pure numpy DSP.
  3. DOCOGA REELS v2 widescreen 16:9 sapphire-blue glassmorphic visual sanctuary plates
     with directional drop shadows and radiant gold kinetic typography.
  4. Precise timestamped chapter markers and high-intent bedtime search metadata.
"""
from __future__ import annotations

import math
import os
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .assemble import ffmpeg_bin
from .config import CONFIG, QUEUE_DIR, REPO_ROOT

SAMPLE_RATE = 44100
DEFAULT_SOLFEGGIO_HZ = 432.0
DELTA_ENTRAINMENT_HZ = 1.5  # 1.5 Hz delta wave entrainment for deep restorative sleep

# Official Color Palette (DOCOGA REELS v2 Widescreen Standard)
BG_TOP = (4, 12, 26)          # #040c1a Deep Midnight Blue
BG_BOTTOM = (9, 31, 61)       # #091f3d Deep Royal Sapphire
CARD_FILL = (8, 22, 50, 160)  # rgba(8, 22, 50, 0.63) Frosted Glass
CARD_BORDER = (212, 175, 55, 120)  # Subtle Sacred Gold
GOLD_ACCENT = (255, 215, 0)   # Radiant Gold #FFD700
WHITE_TEXT = (255, 255, 255)  # Crisp White
ICE_TEXT = (188, 222, 252)    # Soft Ice Blue
MUTED_TEXT = (143, 168, 201)  # Slate Muted Blue
SHADOW_COLOR = (0, 0, 0, 180) # Directional Drop Shadow


@dataclass(frozen=True)
class SleepVerse:
    verse_ref: str
    text: str
    key_words: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SleepMovement:
    movement_num: int
    scripture: str
    title: str
    theme: str
    verses: list[SleepVerse]
    ambient_focus: str
    relative_weight: float = 1.0


# Canonical Biblical Liturgies for Bedtime Sleep Sanctuary
MOVEMENTS: list[SleepMovement] = [
    SleepMovement(
        movement_num=1,
        scripture="Psalm 91",
        title="The Shield of Divine Protection",
        theme="Surrendering fear, resting under the shadow of the Almighty, angelic watch.",
        ambient_focus="432 Hz Solfeggio & Gentle Night Rain",
        relative_weight=1.2,
        verses=[
            SleepVerse(
                verse_ref="Psalm 91:1-2",
                text="He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty. I will say of the Lord, He is my refuge and my fortress: my God; in Him will I trust.",
                key_words=["SECRET PLACE", "MOST HIGH", "SHADOW", "ALMIGHTY", "REFUGE", "FORTRESS", "TRUST"],
            ),
            SleepVerse(
                verse_ref="Psalm 91:4-5",
                text="He shall cover you with His feathers, and under His wings you shall take refuge; His truth shall be your shield and buckler. You shall not be afraid of the terror by night, nor of the arrow that flies by day.",
                key_words=["FEATHERS", "WINGS", "REFUGE", "SHIELD", "NOT BE AFRAID", "TERROR BY NIGHT"],
            ),
            SleepVerse(
                verse_ref="Psalm 91:11-12",
                text="For He shall give His angels charge over you, to keep you in all your ways. In their hands they shall bear you up, lest you dash your foot against a stone.",
                key_words=["ANGELS CHARGE", "KEEP YOU", "BEAR YOU UP"],
            ),
            SleepVerse(
                verse_ref="Psalm 91:15-16",
                text="He shall call upon Me, and I will answer him; I will be with him in trouble; I will deliver him and honor him. With long life I will satisfy him, and show him My salvation.",
                key_words=["ANSWER HIM", "DELIVER HIM", "LONG LIFE", "SALVATION"],
            ),
        ],
    ),
    SleepMovement(
        movement_num=2,
        scripture="Psalm 23",
        title="The Good Shepherd & Still Waters of Rest",
        theme="Overcoming weariness, quiet pasture, restored soul, fearless peace.",
        ambient_focus="432 Hz Harmonic Drone & Calming Stream Waters",
        relative_weight=1.0,
        verses=[
            SleepVerse(
                verse_ref="Psalm 23:1-2",
                text="The Lord is my shepherd; I shall not want. He makes me to lie down in green pastures; He leads me beside the still waters.",
                key_words=["SHEPHERD", "NOT WANT", "GREEN PASTURES", "STILL WATERS"],
            ),
            SleepVerse(
                verse_ref="Psalm 23:3-4",
                text="He restores my soul; He leads me in the paths of righteousness for His name's sake. Yea, though I walk through the valley of the shadow of death, I will fear no evil; for You are with me; Your rod and Your staff, they comfort me.",
                key_words=["RESTORES MY SOUL", "FEAR NO EVIL", "YOU ARE WITH ME", "COMFORT ME"],
            ),
            SleepVerse(
                verse_ref="Psalm 23:5-6",
                text="You prepare a table before me in the presence of my enemies; You anoint my head with oil; my cup runs over. Surely goodness and mercy shall follow me all the days of my life; and I will dwell in the house of the Lord forever.",
                key_words=["ANOINT MY HEAD", "CUP RUNS OVER", "GOODNESS AND MERCY", "DWELL FOREVER"],
            ),
        ],
    ),
    SleepMovement(
        movement_num=3,
        scripture="Psalm 121",
        title="The Keeper Who Neither Slumbers Nor Sleeps",
        theme="Unsleeping watchfulness, help from the Creator, shade from daytime heat and night gloom.",
        ambient_focus="432 Hz Sub-Bass & Sacred Resonant Chimes",
        relative_weight=1.0,
        verses=[
            SleepVerse(
                verse_ref="Psalm 121:1-3",
                text="I will lift up mine eyes unto the hills, from whence cometh my help. My help cometh from the Lord, which made heaven and earth. He will not suffer thy foot to be moved: He that keepeth thee will not slumber.",
                key_words=["HELP COMETH", "MADE HEAVEN AND EARTH", "WILL NOT SLUMBER"],
            ),
            SleepVerse(
                verse_ref="Psalm 121:4-6",
                text="Behold, He that keepeth Israel shall neither slumber nor sleep. The Lord is thy keeper: the Lord is thy shade upon thy right hand. The sun shall not smite thee by day, nor the moon by night.",
                key_words=["NEITHER SLUMBER NOR SLEEP", "THY KEEPER", "THY SHADE"],
            ),
            SleepVerse(
                verse_ref="Psalm 121:7-8",
                text="The Lord shall preserve thee from all evil: He shall preserve thy soul. The Lord shall preserve thy going out and thy coming in from this time forth, and even for evermore.",
                key_words=["PRESERVE THEE", "PRESERVE THY SOUL", "FOR EVERMORE"],
            ),
        ],
    ),
    SleepMovement(
        movement_num=4,
        scripture="Psalm 27",
        title="The Secret Pavilion & Deliverance From Fear",
        theme="Holy confidence, light piercing the darkness, safe in His temple.",
        ambient_focus="432 Hz Ethereal Celestial Pad",
        relative_weight=1.0,
        verses=[
            SleepVerse(
                verse_ref="Psalm 27:1-3",
                text="The Lord is my light and my salvation; whom shall I fear? The Lord is the strength of my life; of whom shall I be afraid? Though an host should encamp against me, my heart shall not fear.",
                key_words=["LIGHT AND SALVATION", "WHOM SHALL I FEAR", "STRENGTH OF MY LIFE", "HEART SHALL NOT FEAR"],
            ),
            SleepVerse(
                verse_ref="Psalm 27:5, 14",
                text="For in the time of trouble He shall hide me in His pavilion: in the secret place of His tabernacle shall He hide me; He shall set me up upon a rock. Wait on the Lord: be of good courage, and He shall strengthen thine heart.",
                key_words=["HIDE ME", "PAVILION", "SECRET PLACE", "UPON A ROCK", "BE OF GOOD COURAGE", "STRENGTHEN THINE HEART"],
            ),
        ],
    ),
    SleepMovement(
        movement_num=5,
        scripture="Night Benediction",
        title="Sacred Nighttime Blessing & Peaceful Sleep",
        theme="Release of anxiety, sacred stillness, peaceful breathing into the night.",
        ambient_focus="432 Hz Deep Delta Drift & Sacred Stillness",
        relative_weight=0.8,
        verses=[
            SleepVerse(
                verse_ref="Numbers 6:24-26 / Philippians 4:7",
                text="The Lord bless you and keep you; the Lord make His face shine upon you, and be gracious unto you; the Lord lift up His countenance upon you, and give you peace. And the peace of God, which surpasses all understanding, will guard your hearts and minds.",
                key_words=["BLESS YOU AND KEEP YOU", "FACE SHINE UPON YOU", "GIVE YOU PEACE", "PEACE OF GOD", "GUARD YOUR HEARTS"],
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Procedural 432 Hz DSP Sleep Audio Synthesis ($0.00 Cost Lock)
# ---------------------------------------------------------------------------

def _fft_shape(x: np.ndarray, cutoff: float, order: float = 2.0, sr: int = SAMPLE_RATE) -> np.ndarray:
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    X *= 1.0 / (1.0 + (f / max(1.0, cutoff)) ** order)
    return np.fft.irfft(X, n)


def synthesize_sleep_bed(
    duration_seconds: float,
    solfeggio_freq: float = DEFAULT_SOLFEGGIO_HZ,
    binaural_hz: float = DELTA_ENTRAINMENT_HZ,
    sample_rate: int = SAMPLE_RATE,
    out_path: str | Path | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesize continuous 432 Hz Solfeggio ambient bed with delta brainwave entrainment.

    100% pure numpy DSP, zero cloud costs, zero royalty claims, zero Content ID issues.
    """
    total_samples = int(duration_seconds * sample_rate)
    if total_samples <= 0:
        raise ValueError("duration_seconds must be positive")

    t = np.arange(total_samples, dtype=np.float64) / sample_rate

    # 1. Harmonic Pythagorean / Solfeggio Drone centered around 432 Hz
    # Fundamental notes: D2 (72Hz), A2 (108Hz), D3 (144Hz), A3 (216Hz), D4 (288Hz), A4 (432Hz)
    harmonics = [
        (54.0, 0.40),    # Sub-bass root drone
        (108.0, 0.35),   # Deep warmth octave
        (216.0, 0.25),   # Sacred 432 sub-harmonic
        (324.0, 0.15),   # Gentle fifth
        (432.0, 0.30),   # Solfeggio fundamental
        (648.0, 0.08),   # Celestial harmonic
    ]

    left = np.zeros(total_samples, dtype=np.float64)
    right = np.zeros(total_samples, dtype=np.float64)

    # Subtle slow amplitude swell (0.05 Hz = 20-second breathing cycle)
    breathing_swell = 0.85 + 0.15 * np.sin(2 * np.pi * 0.05 * t)

    for freq, amp in harmonics:
        # Binaural detuning: Left = freq - binaural/2, Right = freq + binaural/2
        f_left = freq - (binaural_hz / 2.0)
        f_right = freq + (binaural_hz / 2.0)

        # Gentle chorus detuning for natural acoustic dispersion
        left += amp * np.sin(2 * np.pi * f_left * t) * breathing_swell
        right += amp * np.sin(2 * np.pi * f_right * t) * breathing_swell

    # 2. Calming Distant Rain / Gentle Water Stream Noise
    # Generates white noise and shapes it via low-pass FFT to sound like distant soothing rain
    rng = np.random.default_rng(seed=432)
    noise = rng.normal(0, 1.0, total_samples)
    rain_bed = _fft_shape(noise, cutoff=420.0, order=2.5, sr=sample_rate)
    # Slow natural ebb and flow
    rain_mod = 0.6 + 0.4 * np.sin(2 * np.pi * 0.03 * t + 1.2)
    rain_stereo_l = rain_bed * rain_mod * 0.18
    # Decorrelate right channel slightly
    rain_noise_r = rng.normal(0, 1.0, total_samples)
    rain_bed_r = _fft_shape(rain_noise_r, cutoff=420.0, order=2.5, sr=sample_rate)
    rain_stereo_r = rain_bed_r * (0.6 + 0.4 * np.cos(2 * np.pi * 0.03 * t)) * 0.18

    left += rain_stereo_l
    right += rain_stereo_r

    # 3. Smooth Fade-in and Fade-out (5.0 seconds each)
    fade_len = min(int(5.0 * sample_rate), total_samples // 4)
    if fade_len > 0:
        fade_in = np.linspace(0.0, 1.0, fade_len)
        fade_out = np.linspace(1.0, 0.0, fade_len)
        left[:fade_len] *= fade_in
        right[:fade_len] *= fade_in
        left[-fade_len:] *= fade_out
        right[-fade_len:] *= fade_out

    # 4. Mastered Broadcast Normalization (-14 LUFS equivalent peak headroom)
    max_val = max(float(np.abs(left).max()), float(np.abs(right).max()))
    if max_val > 1e-6:
        # Scale to -1.5 dB peak (0.84)
        target_peak = 0.84
        left = (left / max_val) * target_peak
        right = (right / max_val) * target_peak

    # 5. Export WAV if output path provided
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        stereo = np.stack([left, right], axis=1)
        stereo = np.clip(stereo, -1.0, 1.0)
        i16_data = (stereo * 32767).astype("<i2").tobytes()
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(i16_data)

    return left, right


# ---------------------------------------------------------------------------
# Visual Sanctuary Plate Rendering (DOCOGA REELS v2 Standard)
# ---------------------------------------------------------------------------

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


def render_sanctuary_plate(
    movement: SleepMovement,
    verse_idx: int = 0,
    width: int = 1920,
    height: int = 1080,
) -> Image.Image:
    """Render a 16:9 widescreen sanctuary plate with sapphire glassmorphism & typography."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Subtle Midnight Sapphire Vertical Gradient
    for y in range(height):
        factor = y / height
        r = int(BG_TOP[0] * (1 - factor) + BG_BOTTOM[0] * factor)
        g = int(BG_TOP[1] * (1 - factor) + BG_BOTTOM[1] * factor)
        b = int(BG_TOP[2] * (1 - factor) + BG_BOTTOM[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Golden Ambient Glow in upper center
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.28)
    for rad in range(350, 0, -25):
        alpha = int(18 * (1.0 - (rad / 350.0)))
        glow_draw.ellipse(
            [(cx - rad, cy - rad), (cx + rad, cy + rad)],
            fill=(255, 215, 0, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Frosted Glassmorphism Card
    card_margin_x = int(width * 0.12)
    card_top = int(height * 0.14)
    card_bottom = int(height * 0.86)
    card_rect = [(card_margin_x, card_top), (width - card_margin_x, card_bottom)]

    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(card_rect, radius=24, fill=CARD_FILL, outline=CARD_BORDER, width=2)
    img = Image.alpha_composite(img, card_layer)
    draw = ImageDraw.Draw(img)

    # 4. Sacred Header Badges
    font_badge = _get_inter_font(22, "SemiBold")
    header_text = "THE SECRET PLACE  ·  BEDTIME SLEEP SANCTUARY  ·  432 Hz"
    bbox_h = draw.textbbox((0, 0), header_text, font=font_badge)
    hw = bbox_h[2] - bbox_h[0]
    draw.text(((width - hw) // 2, card_top + 36), header_text, font=font_badge, fill=MUTED_TEXT)

    # 5. Scripture Movement Title
    font_title = _get_inter_font(44, "Black")
    title_text = f"{movement.scripture.upper()}  —  {movement.title.upper()}"
    bbox_t = draw.textbbox((0, 0), title_text, font=font_title)
    tw = bbox_t[2] - bbox_t[0]
    # Directional drop shadow
    draw.text(((width - tw) // 2 + 3, card_top + 83), title_text, font=font_title, fill=(0, 0, 0, 200))
    draw.text(((width - tw) // 2, card_top + 80), title_text, font=font_title, fill=GOLD_ACCENT)

    # 6. Current Verse Body & Gold Keyword Illuminations
    if movement.verses:
        v_idx = verse_idx % len(movement.verses)
        verse = movement.verses[v_idx]
    else:
        verse = SleepVerse(
            verse_ref=movement.scripture,
            text="Peace I leave with you, My peace I give unto you.",
            key_words=["PEACE"],
        )

    font_ref = _get_inter_font(26, "Bold")
    bbox_r = draw.textbbox((0, 0), verse.verse_ref, font=font_ref)
    rw = bbox_r[2] - bbox_r[0]
    draw.text(((width - rw) // 2, card_top + 160), verse.verse_ref, font=font_ref, fill=ICE_TEXT)

    # Word wrapping body text
    font_body = _get_inter_font(34, "Medium")
    words = verse.text.split()
    lines: list[list[str]] = []
    curr_line: list[str] = []
    max_line_width = int(width * 0.70)

    for word in words:
        test_line = " ".join(curr_line + [word])
        bbox_l = draw.textbbox((0, 0), test_line, font=font_body)
        if (bbox_l[2] - bbox_l[0]) <= max_line_width:
            curr_line.append(word)
        else:
            if curr_line:
                lines.append(curr_line)
            curr_line = [word]
    if curr_line:
        lines.append(curr_line)

    # Render lines with highlighted gold words
    start_y = card_top + 230
    line_spacing = 54
    key_words_clean = {k.strip().upper() for k in verse.key_words}

    for l_idx, line_words in enumerate(lines[:7]):
        # Calculate full line width
        line_str = " ".join(line_words)
        bbox_line = draw.textbbox((0, 0), line_str, font=font_body)
        line_w = bbox_line[2] - bbox_line[0]
        cur_x = (width - line_w) // 2
        line_y = start_y + (l_idx * line_spacing)

        for w_idx, w_text in enumerate(line_words):
            clean_token = "".join(c for c in w_text if c.isalnum()).upper()
            is_gold = clean_token in key_words_clean
            color = GOLD_ACCENT if is_gold else WHITE_TEXT

            # Draw word shadow + text
            w_disp = w_text + (" " if w_idx < len(line_words) - 1 else "")
            draw.text((cur_x + 2, line_y + 2), w_disp, font=font_body, fill=(0, 0, 0, 180))
            draw.text((cur_x, line_y), w_disp, font=font_body, fill=color)

            wb = draw.textbbox((0, 0), w_disp, font=font_body)
            cur_x += wb[2] - wb[0]

    # 7. Bottom Frequency & Sanctuary Indicator
    font_foot = _get_inter_font(20, "Regular")
    foot_text = f"AMBIENT BED: {movement.ambient_focus.upper()}  ·  DELTA WAVE 1.5 Hz  ·  REST UNDER HIS SHADOW"
    bbox_f = draw.textbbox((0, 0), foot_text, font=font_foot)
    fw = bbox_f[2] - bbox_f[0]
    draw.text(((width - fw) // 2, card_bottom - 45), foot_text, font=font_foot, fill=MUTED_TEXT)

    return img.convert("RGB")


def render_sleep_thumbnail(
    hook_title: str = "8 HOURS OF PEACE",
    scripture_subtitle: str = "PSALM 91, 23 & 121",
    sub_badge: str = "432 Hz SLEEP FREQUENCY · UNDER HIS WINGS",
    width: int = 1280,
    height: int = 720,
    out_path: str | Path | None = None,
) -> Image.Image:
    """Render high-contrast, scroll-stopping 16:9 bedroom sleep thumbnail."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # Midnight sapphire gradient
    for y in range(height):
        factor = y / height
        r = int(BG_TOP[0] * (1 - factor) + BG_BOTTOM[0] * factor)
        g = int(BG_TOP[1] * (1 - factor) + BG_BOTTOM[1] * factor)
        b = int(BG_TOP[2] * (1 - factor) + BG_BOTTOM[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Golden celestial halo
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.40)
    for rad in range(320, 0, -20):
        alpha = int(25 * (1.0 - (rad / 320.0)))
        glow_draw.ellipse(
            [(cx - rad, cy - rad), (cx + rad, cy + rad)],
            fill=(255, 215, 0, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # Big primary hook
    font_hook = _get_inter_font(72, "Black")
    bbox_h = draw.textbbox((0, 0), hook_title, font=font_hook)
    hw = bbox_h[2] - bbox_h[0]
    # Heavy directional drop shadow
    draw.text(((width - hw) // 2 + 5, 145), hook_title, font=font_hook, fill=(0, 0, 0, 230))
    draw.text(((width - hw) // 2, 140), hook_title, font=font_hook, fill=GOLD_ACCENT)

    # Scripture subtitle in crisp white
    font_sub = _get_inter_font(52, "ExtraBold")
    bbox_s = draw.textbbox((0, 0), scripture_subtitle, font=font_sub)
    sw = bbox_s[2] - bbox_s[0]
    draw.text(((width - sw) // 2 + 4, 254), scripture_subtitle, font=font_sub, fill=(0, 0, 0, 220))
    draw.text(((width - sw) // 2, 250), scripture_subtitle, font=font_sub, fill=WHITE_TEXT)

    # Glassmorphism badge bar at bottom
    badge_w = int(width * 0.85)
    badge_rect = [((width - badge_w) // 2, 420), ((width + badge_w) // 2, 510)]
    badge_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge_layer)
    bdraw.rounded_rectangle(badge_rect, radius=18, fill=CARD_FILL, outline=CARD_BORDER, width=2)
    img = Image.alpha_composite(img, badge_layer)
    draw = ImageDraw.Draw(img)

    font_badge = _get_inter_font(26, "Bold")
    bbox_b = draw.textbbox((0, 0), sub_badge, font=font_badge)
    bw = bbox_b[2] - bbox_b[0]
    draw.text(((width - bw) // 2, 448), sub_badge, font=font_badge, fill=ICE_TEXT)

    # Channel signature watermark
    font_brand = _get_inter_font(22, "SemiBold")
    brand_text = "THE SECRET PLACE  ·  DAILY BEDTIME PRAYER"
    bbox_br = draw.textbbox((0, 0), brand_text, font=font_brand)
    brw = bbox_br[2] - bbox_br[0]
    draw.text(((width - brw) // 2, height - 70), brand_text, font=font_brand, fill=MUTED_TEXT)

    res = img.convert("RGB")
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res.save(out_path, quality=95)
    return res


# ---------------------------------------------------------------------------
# YouTube Chapter Markers & Queue Manifest Generation
# ---------------------------------------------------------------------------

def generate_chapter_timestamps(
    movements: Sequence[SleepMovement],
    total_duration_seconds: float,
) -> list[dict]:
    """Generate precise second-accurate YouTube chapter markers."""
    total_weight = sum(m.relative_weight for m in movements)
    chapters = []
    current_sec = 0.0

    for m in movements:
        dur = (m.relative_weight / total_weight) * total_duration_seconds
        hours = int(current_sec // 3600)
        minutes = int((current_sec % 3600) // 60)
        seconds = int(current_sec % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"

        chapters.append({
            "movement": m.movement_num,
            "title": f"{m.scripture} — {m.title}",
            "timestamp": time_str,
            "seconds": round(current_sec, 2),
            "duration": round(dur, 2),
        })
        current_sec += dur

    return chapters


def build_sleep_suite_manifest(
    job_id: str = "0012",
    target_hours: float = 1.0,
    out_dir: Path | None = None,
) -> Path:
    """Generate approved markdown queue script for the Bedtime Sleep Sanctuary."""
    total_seconds = target_hours * 3600.0
    total_minutes = int(target_hours * 60)
    chapters = generate_chapter_timestamps(MOVEMENTS, total_seconds)

    chapters_formatted = "\n".join(
        f"  {c['timestamp']} {c['title']}" for c in chapters
    )

    content = f"""---
id: "{job_id}"
title: "PSALM 91, 23 & 121: The Complete Night Prayer for Peaceful Sleep & Divine Protection ({total_minutes} Mins 432 Hz)"
slug: "psalm-sleep-sanctuary-{total_minutes}min"
status: approved
privacy: public
format: longform
niche: faith and prayer
category: education
voice: Charon
target_minutes: {total_minutes}
tags:
  - psalm 91 sleep prayer
  - psalm 23 deep sleep
  - psalm 121 night prayer
  - bedtime scripture meditation
  - 432 hz sleep music
  - the secret place
  - peaceful sleep prayer
  - prayer for anxiety relief
  - christian sleep meditation
thumb_text: "8 HOURS OF PEACE"
description: |
  Listen to this soothing scripture meditation before you close your eyes tonight.
  Let God's covenant of divine protection, peaceful rest, and unslumbering watch
  surround your home, family, and thoughts.

  Movements & Chapters:
{chapters_formatted}

  Audio Engineering:
  - 432 Hz Pythagorean sacred Solfeggio frequency
  - Delta brainwave binaural entrainment (1.5 Hz) for rapid restorative sleep
  - Procedural acoustic rain and calm stream soundscapes

  Scripture References & Sources:
  - The Holy Bible, Psalms 91, 23, 121, 27 (KJV / NKJV Public Domain text)
  - Spurgeon, C.H. (1885). The Treasury of David.

  Produced by The Secret Place | Daily Scripture & Bedtime Prayer.
asset_queries:
  - "calm mountain lake sunset water reflection"
  - "milky way galaxy starry night sky"
  - "candle burning dark room"
  - "sunlight through forest trees mountain mist"
---

## Movement 1 — Psalm 91: The Fortress of the Most High
He who dwells in the secret place of the Most High shall abide under the shadow of the Almighty.
I will say of the Lord, He is my refuge and my fortress: my God; in Him will I trust.
He shall cover you with His feathers, and under His wings you shall take refuge.
You shall not be afraid of the terror by night, nor of the arrow that flies by day.
For He shall give His angels charge over you, to keep you in all your ways.

## Movement 2 — Psalm 23: The Good Shepherd & Still Waters
The Lord is my shepherd; I shall not want.
He makes me to lie down in green pastures; He leads me beside the still waters.
He restores my soul. He leads me in paths of righteousness for His name's sake.
Yea, though I walk through the valley of the shadow of death, I will fear no evil; for You are with me.
Your rod and Your staff, they comfort me.
Surely goodness and mercy shall follow me all the days of my life.

## Movement 3 — Psalm 121: The Keeper Who Never Slumbers
I will lift up mine eyes unto the hills, from whence cometh my help.
My help cometh from the Lord, which made heaven and earth.
He that keepeth thee will not slumber. Behold, He that keepeth Israel shall neither slumber nor sleep.
The Lord is thy keeper; the Lord is thy shade upon thy right hand.
The Lord shall preserve thy soul; He shall preserve thy going out and coming in for evermore.

## Movement 4 — Psalm 27: The Secret Pavilion
The Lord is my light and my salvation; whom shall I fear?
The Lord is the strength of my life; of whom shall I be afraid?
For in the time of trouble He shall hide me in His pavilion.
In the secret place of His tabernacle shall He hide me; He shall set me up upon a rock.
Wait on the Lord; be of good courage, and He shall strengthen thine heart.

## Movement 5 — Sacred Nighttime Benediction
The Lord bless you and keep you.
The Lord make His face shine upon you, and be gracious unto you.
The Lord lift up His countenance upon you, and give you peace.
Sleep tonight in holy peace, under the shadow of the Almighty.
"""
    target_dir = out_dir or QUEUE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / f"{job_id}-psalm-sleep-sanctuary-{total_minutes}min.md"
    manifest_path.write_text(content.strip() + "\n", encoding="utf-8")
    return manifest_path


# ---------------------------------------------------------------------------
# Video Rendering Pipeline via FFmpeg ($0.00 Cost Lock)
# ---------------------------------------------------------------------------

def render_sleep_suite_video(
    output_mp4: Path,
    duration_seconds: float = 30.0,
    preview: bool = False,
) -> Path:
    """Render the Sleep Sanctuary video combining 432 Hz DSP audio and glassmorphic plates."""
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    temp_audio = output_mp4.parent / f"{output_mp4.stem}_audio.wav"
    temp_plate = output_mp4.parent / f"{output_mp4.stem}_plate.png"

    try:
        # 1. Synthesize procedural 432 Hz audio bed
        synthesize_sleep_bed(
            duration_seconds=duration_seconds,
            out_path=temp_audio,
        )

        # 2. Render primary sanctuary plate
        plate_img = render_sanctuary_plate(MOVEMENTS[0], verse_idx=0, width=1920, height=1080)
        plate_img.save(temp_plate)

        # 3. Assemble via ffmpeg
        ffmpeg = ffmpeg_bin()
        cmd = [
            ffmpeg,
            "-y",
            "-loop", "1",
            "-i", str(temp_plate),
            "-i", str(temp_audio),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-t", f"{duration_seconds:.2f}",
            str(output_mp4),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {proc.stderr[-800:]}")

        return output_mp4
    finally:
        # Cleanup temporary scratch files
        if temp_audio.exists():
            temp_audio.unlink(missing_ok=True)
        if temp_plate.exists():
            temp_plate.unlink(missing_ok=True)
