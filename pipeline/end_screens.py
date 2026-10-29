"""Autonomous End-Screen Slate Generator & Autoplay Chaining Engine.

Renders high-retention 15-second 16:9 widescreen Full HD (1920x1080) End-Screen
Outro Slates with safe-zone card anchors for YouTube Studio's interactive elements,
locking viewers into consecutive autoplay sessions ($0.00 cost lock).

Coordinates tailored for YouTube Studio End-Screen Element Grid:
  • Left Video Card:   x=140, y=280, w=740, h=416 (Next In Series)
  • Right Playlist Card: x=1040, y=280, w=740, h=416 (Bedtime Sleep Playlist)
  • Center Channel Sub: cx=960, cy=180, r=80 (Subscribe Watermark)
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from .assemble import ffmpeg_bin
from .config import CONFIG, REPO_ROOT
from .sleep_suite import synthesize_sleep_bed

W, H = 1920, 1080
OUTRO_SECONDS = 15.0

BG_TOP = (4, 12, 26)          # #040c1a Deep Midnight Blue
BG_BOTTOM = (9, 31, 61)       # #091f3d Deep Royal Sapphire
CARD_FILL = (8, 22, 50, 160)  # Frosted Glass
CARD_BORDER = (212, 175, 55, 140)  # Sacred Gold
GOLD_TEXT = (255, 215, 0)
WHITE_TEXT = (255, 255, 255)
MUTED_TEXT = (143, 168, 201)
ICE_TEXT = (188, 222, 252)


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


def render_endscreen_plate(
    next_video_title: str = "PSALM 23 · THE LORD IS MY SHEPHERD",
    playlist_title: str = "BEDTIME SCRIPTURE MEDITATIONS (432 Hz)",
    channel_name: str = "THE SECRET PLACE",
    width: int = W,
    height: int = H,
    out_path: Path | None = None,
) -> Image.Image:
    """Render a 1920x1080 widescreen end-screen card plate with element placeholders."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    # 1. Midnight sapphire vertical gradient
    for y in range(height):
        factor = y / height
        r = int(BG_TOP[0] * (1 - factor) + BG_BOTTOM[0] * factor)
        g = int(BG_TOP[1] * (1 - factor) + BG_BOTTOM[1] * factor)
        b = int(BG_TOP[2] * (1 - factor) + BG_BOTTOM[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Celestial golden halo
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = width // 2, int(height * 0.25)
    for rad in range(350, 0, -25):
        alpha = int(22 * (1.0 - (rad / 350.0)))
        glow_draw.ellipse(
            [(cx - rad, cy - rad), (cx + rad, cy + rad)],
            fill=(255, 215, 0, alpha),
        )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)

    # 3. Channel Subscribe Center Ring & Badge
    sub_cy = int(height * 0.16)
    sub_r = 65
    draw.ellipse(
        [(cx - sub_r, sub_cy - sub_r), (cx + sub_r, sub_cy + sub_r)],
        fill=(12, 38, 70, 220),
        outline=GOLD_TEXT,
        width=3,
    )
    font_sub_btn = _get_inter_font(26, "Black")
    draw.text((cx - 46, sub_cy - 16), "PRAY", font=font_sub_btn, fill=GOLD_TEXT)

    font_brand = _get_inter_font(28, "Black")
    bb = draw.textbbox((0, 0), channel_name, font=font_brand)
    bw = bb[2] - bb[0]
    draw.text(((width - bw) // 2, sub_cy + sub_r + 16), channel_name, font=font_brand, fill=WHITE_TEXT)

    font_sub_tag = _get_inter_font(20, "Medium")
    st_text = "CLICK TO SUBSCRIBE & JOIN OUR DAILY PRAYER SANCTUARY"
    sb = draw.textbbox((0, 0), st_text, font=font_sub_tag)
    draw.text(((width - (sb[2] - sb[0])) // 2, sub_cy + sub_r + 52), st_text, font=font_sub_tag, fill=MUTED_TEXT)

    # 4. Left Video Card Placeholder (YouTube End Screen Safe Area)
    left_x = 140
    card_y = 340
    card_w = 760
    card_h = 428

    left_rect = [(left_x, card_y), (left_x + card_w, card_y + card_h)]
    card_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card_layer)
    cdraw.rounded_rectangle(left_rect, radius=20, fill=CARD_FILL, outline=CARD_BORDER, width=2)
    img = Image.alpha_composite(img, card_layer)
    draw = ImageDraw.Draw(img)

    font_header = _get_inter_font(24, "Bold")
    draw.text((left_x + 36, card_y + 30), "▶  WATCH NEXT IN DEVOTIONAL SERIES", font=font_header, fill=GOLD_TEXT)

    font_title = _get_inter_font(32, "Black")
    draw.text((left_x + 36, card_y + 75), next_video_title, font=font_title, fill=WHITE_TEXT)

    font_hint = _get_inter_font(22, "Regular")
    draw.text((left_x + 36, card_y + card_h - 45), "Surrender the night into His presence · Next Prayer", font=font_hint, fill=ICE_TEXT)

    # 5. Right Playlist Card Placeholder (Continuous Autoplay Area)
    right_x = 1020
    right_rect = [(right_x, card_y), (right_x + card_w, card_y + card_h)]
    card_layer2 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw2 = ImageDraw.Draw(card_layer2)
    cdraw2.rounded_rectangle(right_rect, radius=20, fill=CARD_FILL, outline=CARD_BORDER, width=2)
    img = Image.alpha_composite(img, card_layer2)
    draw = ImageDraw.Draw(img)

    draw.text((right_x + 36, card_y + 30), "🔁  CONTINUOUS SLEEP PLAYLIST", font=font_header, fill=GOLD_TEXT)
    draw.text((right_x + 36, card_y + 75), playlist_title, font=font_title, fill=WHITE_TEXT)
    draw.text((right_x + 36, card_y + card_h - 45), "Overnight 432 Hz Solfeggio & Calming Rain Autoplay", font=font_hint, fill=ICE_TEXT)

    # 6. Bottom Sacred Benediction Footer
    font_foot = _get_inter_font(22, "SemiBold")
    foot_text = "PEACE I LEAVE WITH YOU · MY PEACE I GIVE UNTO YOU · JOHN 14:27"
    fb = draw.textbbox((0, 0), foot_text, font=font_foot)
    draw.text(((width - (fb[2] - fb[0])) // 2, height - 90), foot_text, font=font_foot, fill=GOLD_TEXT)

    res = img.convert("RGB")
    if out_path:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res.save(out_path, quality=95)
    return res


def render_endscreen_video(
    output_mp4: Path,
    duration_seconds: float = OUTRO_SECONDS,
    next_video_title: str = "PSALM 23 · THE LORD IS MY SHEPHERD",
    playlist_title: str = "BEDTIME SCRIPTURE MEDITATIONS (432 Hz)",
) -> Path:
    """Render the 15-second MP4 end-screen outro with 432 Hz ambient audio fade-out."""
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    temp_audio = output_mp4.parent / f"{output_mp4.stem}_audio.wav"
    temp_plate = output_mp4.parent / f"{output_mp4.stem}_plate.png"

    try:
        # 1. Synthesize 432 Hz ambient outro audio bed
        synthesize_sleep_bed(
            duration_seconds=duration_seconds,
            out_path=temp_audio,
        )

        # 2. Render visual card plate
        plate_img = render_endscreen_plate(
            next_video_title=next_video_title,
            playlist_title=playlist_title,
            width=W,
            height=H,
            out_path=temp_plate,
        )

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
            raise RuntimeError(f"FFmpeg render of end-screen failed: {proc.stderr[-800:]}")

        return output_mp4
    finally:
        if temp_audio.exists():
            temp_audio.unlink(missing_ok=True)
        if temp_plate.exists():
            temp_plate.unlink(missing_ok=True)
