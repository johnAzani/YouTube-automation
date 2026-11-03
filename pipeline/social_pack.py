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
PODCAST_URL = os.environ.get("PODCAST_URL", "https://www.youtube.com/@TheSecretPlace/podcasts")
SELAR_STORE_URL = os.environ.get("SELAR_STORE_URL", "https://selar.com/showlove/thesecretplace")
SELAR_JOURNAL_URL = os.environ.get("SELAR_JOURNAL_URL", "https://selar.com/i000qy7g39")

# Official Series & Flagship Sanctuary Links (real live URLs; env-overridable once playlist IDs are minted)
PLAYLIST_LINKS = {
    "Night Prayers": os.environ.get("YT_PLAYLIST_NIGHT_PRAYERS", "https://youtu.be/7RDX0fbIOtQ"),
    "Bedtime Scripture Meditations": os.environ.get("YT_PLAYLIST_BEDTIME_SLEEP", "https://youtu.be/6M6oV8MxD9s"),
    "Bedtime Scripture Meditations (432 Hz)": os.environ.get("YT_PLAYLIST_BEDTIME_SLEEP", "https://youtu.be/6M6oV8MxD9s"),
    "Complete Psalms Devotional Series": os.environ.get("YT_PLAYLIST_COMPLETE_PSALMS", "https://youtu.be/1g8TXHD0Xks"),
}


def build_above_fold_selar_line() -> str:
    """Single quiet pastoral resource line placed right at the watch-page fold (Line 2)."""
    if not SELAR_JOURNAL_URL:
        return ""
    return f"📖 30-Night Bedside Prayer Journal: {SELAR_JOURNAL_URL}"


def build_sanctuary_resource_block(
    scripture_source: str = "The Holy Bible (King James Version, Public Domain)",
    include_store_links: bool = True,
    include_crisis_support: bool = True,
) -> str:
    """Clean, reverent Sanctuary Resource & Session Continuation block for descriptions."""
    lines: list[str] = []
    if include_store_links and (SELAR_JOURNAL_URL or SELAR_STORE_URL):
        lines.append("🕊️ OFFLINE BEDTIME PRAYER SANCTUARY")
        if SELAR_JOURNAL_URL:
            lines.append(
                f"• 30-Night Scripture Protection Prayer Journal (Printable PDF): {SELAR_JOURNAL_URL}"
            )
        if SELAR_STORE_URL:
            lines.append(
                f"• Partner in Prayer & Voluntary Ministry Support: {SELAR_STORE_URL}"
            )
        lines.append("")

    lines.extend(
        [
            "🙏 CONTINUE PRAYING THROUGH THE NIGHT",
            f"• Psalm 91 Night Prayer of Protection: {PLAYLIST_LINKS['Night Prayers']}",
            f"• Psalm 121 Unsleeping Watch Prayer: {PLAYLIST_LINKS['Bedtime Scripture Meditations']}",
            f"• Subscribe to The Secret Place: {SUBSCRIBE_URL}",
            "",
        ]
    )

    if include_crisis_support:
        lines.extend(
            [
                "❤️ PASTORAL & CRISIS CARE",
                "If tonight feels heavy or overwhelming, please know you are deeply loved and never alone.",
                "• US & Canada: Call or text 988 | UK: Call 111 | International: https://findahelpline.com",
                "",
            ]
        )

    lines.extend(
        [
            f"Scripture & Devotional Attribution: {scripture_source}.",
            "Curated by The Secret Place editorial team with reverent narration and nighttime sanctuary score.",
        ]
    )
    return "\n".join(lines).strip()


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
        f"• Bedtime Sleep Meditations: {PLAYLIST_LINKS['Bedtime Scripture Meditations']}\n"
        f"• Complete Psalms Expositions: {PLAYLIST_LINKS['Complete Psalms Devotional Series']}\n\n"
        f"🎙️ AUDIO PODCAST:\n"
        f"Listen free to our nighttime audio sanctuary: {PODCAST_URL}\n"
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
    """Ensure zero personal creator names or handles appear in metadata or comments."""
    cleaned = re.sub(
        r"https?://johnazani\.github\.io/[^\s)]*",
        "https://www.youtube.com/@TheSecretPlace/podcasts",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bJohn\s+Azani\b", "The Secret Place", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAzani\s+John\b", "The Secret Place", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bjohnazani\b", "TheSecretPlace", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bAzani\b", "The Secret Place", cleaned, flags=re.IGNORECASE)
    return cleaned
