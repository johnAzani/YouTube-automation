"""Shorts-to-Longform Conversion Bridge Engine.

Funnels fast top-of-funnel YouTube Shorts viewers directly into full-length
Deep-Dive and Bedtime Sleep Sanctuary videos to accelerate valid public watch hours
toward the 4,000-hour YPP monetization bar under the permanent $0.00 cost lock.

Key Capabilities:
  1. Bidirectional mapping between Short editions and Longform Deep-Dive masters.
  2. Autonomous resolution of live YouTube video IDs from content/published/.
  3. High-converting pastoral pinned comments bridging viewers to the full prayer.
  4. Top-of-description conversion link injection before mobile truncation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import CONFIG, REPO_ROOT

PUBLISHED_DIR = REPO_ROOT / "content" / "published"
QUEUE_DIR = REPO_ROOT / "content" / "queue"

# Canonical Short -> Longform Mapping
# Maps Short edition keys and slugs to corresponding longform job IDs and titles
SHORT_LONGFORM_CATALOG: dict[str, dict[str, str]] = {
    "short-psalm91": {
        "longform_job_id": "0008",
        "longform_slug": "psalm-91-prayer-of-divine-protection",
        "scripture": "Psalm 91",
        "title": "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep",
        "fallback_video_id": "7RDX0fbIOtQ",
        "theme": "divine protection and angelic shelter",
    },
    "short-psalm23": {
        "longform_job_id": "0009",
        "longform_slug": "0009-psalm-23-the-lord-is-my-shepherd",
        "scripture": "Psalm 23",
        "title": "Psalm 23: The Lord Is My Shepherd — Night Prayer for Rest, Healing & Peace",
        "fallback_video_id": "",
        "theme": "divine rest, still waters, and soul restoration",
    },
    "short-psalm121": {
        "longform_job_id": "0010",
        "longform_slug": "0010-psalm-121-my-help-comes-from-the-lord",
        "scripture": "Psalm 121",
        "title": "Psalm 121: He Who Keeps You Will Not Slumber — Nighttime Sleep Prayer",
        "fallback_video_id": "",
        "theme": "unsleeping protection and peaceful sleep",
    },
    "short-psalm27": {
        "longform_job_id": "0011",
        "longform_slug": "0011-psalm-27-the-lord-is-my-light",
        "scripture": "Psalm 27",
        "title": "Psalm 27: The Lord Is My Light & Salvation — Prayer Against Night Fear",
        "fallback_video_id": "",
        "theme": "courage, light in darkness, and freedom from fear",
    },
    "short-psalm46": {
        "longform_job_id": "0013",
        "longform_slug": "0013-psalm-46-refuge-in-times-of-trouble",
        "scripture": "Psalm 46",
        "title": "Psalm 46: God Is Our Refuge and Strength — Be Still and Know",
        "fallback_video_id": "",
        "theme": "stillness in storms and God's sovereign shelter",
    },
    "short-psalm34": {
        "longform_job_id": "0014",
        "longform_slug": "0014-psalm-34-taste-and-see-the-lord-is-good",
        "scripture": "Psalm 34",
        "title": "Psalm 34: The Angel of the Lord Encamps Around You — Bedtime Prayer",
        "fallback_video_id": "",
        "theme": "angelic deliverance and healing for the brokenhearted",
    },
}

DEFAULT_PLAYLIST_FALLBACK = "https://www.youtube.com/playlist?list=PL_NIGHT_PRAYERS"


def resolve_short_key(key_or_title: str) -> str | None:
    """Normalize any short identifier, slug, or title to canonical short key."""
    s = (key_or_title or "").strip().lower()
    s_clean = s.replace("-", " ")
    for key in SHORT_LONGFORM_CATALOG:
        if key in s or key.replace("-", " ") in s_clean:
            return key
    if "psalm 91" in s_clean or "psalm91" in s:
        return "short-psalm91"
    if "psalm 23" in s_clean or "psalm23" in s:
        return "short-psalm23"
    if "psalm 121" in s_clean or "psalm121" in s:
        return "short-psalm121"
    if "psalm 27" in s_clean or "psalm27" in s:
        return "short-psalm27"
    if "psalm 46" in s_clean or "psalm46" in s:
        return "short-psalm46"
    if "psalm 34" in s_clean or "psalm34" in s:
        return "short-psalm34"
    return None


def resolve_longform_counterpart(short_key_or_title: str) -> dict[str, Any]:
    """Find the live or scheduled long-form video matching a Short."""
    short_key = resolve_short_key(short_key_or_title)
    if not short_key or short_key not in SHORT_LONGFORM_CATALOG:
        return {
            "found": False,
            "url": DEFAULT_PLAYLIST_FALLBACK,
            "title": "Night Prayers of Divine Protection",
            "is_live_video": False,
        }

    info = SHORT_LONGFORM_CATALOG[short_key]
    job_id = info["longform_job_id"]
    slug = info["longform_slug"]
    fallback_vid = info.get("fallback_video_id", "")

    # 1. Search published records in content/published/
    published_candidates = [
        PUBLISHED_DIR / f"{job_id}-{slug}.md",
        PUBLISHED_DIR / f"{slug}.md",
    ]
    for p in PUBLISHED_DIR.glob(f"*{job_id}*.md"):
        if p not in published_candidates:
            published_candidates.append(p)

    for cand in published_candidates:
        if cand.is_file():
            text = cand.read_text(encoding="utf-8")
            m = re.search(r"youtube_video_id:\s*[\"']?([A-Za-z0-9_-]{11})[\"']?", text)
            if m:
                vid = m.group(1)
                return {
                    "found": True,
                    "video_id": vid,
                    "url": f"https://youtu.be/{vid}",
                    "title": info["title"],
                    "scripture": info["scripture"],
                    "theme": info["theme"],
                    "is_live_video": True,
                }

    # 2. Check fallback video ID (e.g. 7RDX0fbIOtQ for Psalm 91)
    if fallback_vid:
        return {
            "found": True,
            "video_id": fallback_vid,
            "url": f"https://youtu.be/{fallback_vid}",
            "title": info["title"],
            "scripture": info["scripture"],
            "theme": info["theme"],
            "is_live_video": True,
        }

    # 3. Fallback to Series Playlist
    return {
        "found": True,
        "video_id": None,
        "url": DEFAULT_PLAYLIST_FALLBACK,
        "title": info["title"],
        "scripture": info["scripture"],
        "theme": info["theme"],
        "is_live_video": False,
    }


def generate_short_bridge_comment(short_key_or_title: str) -> str:
    """Generate high-converting pinned comment bridging Shorts viewers to full prayer."""
    counterpart = resolve_longform_counterpart(short_key_or_title)
    url = counterpart["url"]
    scripture = counterpart.get("scripture", "this Scripture")
    theme = counterpart.get("theme", "divine peace and angelic protection")

    comment = (
        f"🕊️ PRAY THE FULL NIGHTTIME SCRIPTURE MEDITATION:\n"
        f"Experience the complete 8-minute prayer and exposition of {scripture} before sleep:\n"
        f"👉 {url}\n\n"
        f"Rest under God's covenant of {theme} tonight. "
        f"Write 'AMEN' in faith and leave your prayer request below — we are interceding for your household! 🙏🕊️✨"
    )
    return comment.strip()


def enrich_short_description_with_bridge(description: str, short_key_or_title: str) -> str:
    """Inject prominent bridge link at the very top of Short description."""
    counterpart = resolve_longform_counterpart(short_key_or_title)
    url = counterpart["url"]
    scripture = counterpart.get("scripture", "Scripture")

    header = (
        f"🕊️ PRAY THE COMPLETE 8-MINUTE {scripture.upper()} MEDITATION: 👉 {url}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if url in description:
        return description  # Already enriched
    return header + description
