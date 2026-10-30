"""Social Funnel Pack & Standard Description Engine.

Standardizes video descriptions across all releases with 1-click subscription
links, official playlist links, podcast RSS references, scripture citations,
and crisis support info under the strict $0.00 cost lock.
"""
from __future__ import annotations

import os
import re

CHANNEL_HANDLE = "@TheSecretPlace"
SUBSCRIBE_URL = "https://www.youtube.com/@TheSecretPlace?sub_confirmation=1"
PODCAST_URL = "https://johnazani.github.io/YouTube-automation/podcast.xml"
SELAR_STORE_URL = os.environ.get("SELAR_STORE_URL", "https://selar.com/showlove/thesecretplace")
SELAR_JOURNAL_URL = os.environ.get("SELAR_JOURNAL_URL", "https://selar.com/i000qy7g39")

# Official Playlists
PLAYLIST_LINKS = {
    "Night Prayers": "https://www.youtube.com/playlist?list=PL_NIGHT_PRAYERS",
    "Bedtime Scripture Meditations (432 Hz)": "https://www.youtube.com/playlist?list=PL_BEDTIME_SLEEP",
    "Complete Psalms Devotional Series": "https://www.youtube.com/playlist?list=PL_COMPLETE_PSALMS",
}


def build_standardized_description_footer(
    scripture_source: str = "The Holy Bible (King James Version / English Standard Version, Public Domain)",
    include_store_links: bool = True,
) -> str:
    """Build the official social funnel footer appended to all YouTube descriptions."""
    store_block = ""
    if include_store_links and SELAR_STORE_URL:
        journal_line = f"• 30-Night Scripture Protection Prayer Journal: {SELAR_JOURNAL_URL}\n" if SELAR_JOURNAL_URL else ""
        store_block = (
            f"\n📥 OFFLINE BEDTIME PRAYER SANCTUARY (AD-FREE AUDIO & PRINTABLES):\n"
            f"{journal_line}"
            f"• Partner in Prayer & Voluntary Ministry Support: {SELAR_STORE_URL}\n"
        )

    footer = (
        f"\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕊️ JOIN OUR DAILY PRAYER COMMUNITY\n"
        f"Subscribe for nightly prayers and biblical peace: {SUBSCRIBE_URL}\n\n"
        f"🎧 OFFICIAL SERIES PLAYLISTS (CONTINUOUS AUTOPLAY):\n"
        f"• Night Prayers of Protection: {PLAYLIST_LINKS['Night Prayers']}\n"
        f"• Bedtime Sleep Meditations (432 Hz): {PLAYLIST_LINKS['Bedtime Scripture Meditations (432 Hz)']}\n"
        f"• Complete Psalms Expositions: {PLAYLIST_LINKS['Complete Psalms Devotional Series']}\n\n"
        f"🎙️ AUDIO PODCAST (APPLE / SPOTIFY):\n"
        f"Listen free to our nighttime audio stream: {PODCAST_URL}\n"
        f"{store_block}\n"
        f"📖 SCRIPTURE & ATTRIBUTION:\n"
        f"{scripture_source}\n"
        f"Produced by The Secret Place | Daily Scripture & Evening Prayer Sanctuary.\n\n"
        f"❤️ CRISIS & PASTORAL SUPPORT:\n"
        f"If you are experiencing despair or overwhelming emotional pain, please know you are loved.\n"
        f"• US & Canada: Call or text 988 (Suicide & Crisis Lifeline)\n"
        f"• United Kingdom: Call 111 (NHS Mental Health Services)\n"
        f"• International: https://findahelpline.com\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"#TheSecretPlace #NightPrayer #BedtimePrayer #PeacefulSleep #ChristianMeditation"
    )
    return footer


def sanitize_persona_integrity(text: str) -> str:
    """Ensure zero personal creator names appear in metadata or comments."""
    cleaned = re.sub(r"\bJohn\s+Azani\b", "The Secret Place", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAzani\s+John\b", "The Secret Place", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAzani\b", "The Secret Place", cleaned, flags=re.IGNORECASE)
    return cleaned
