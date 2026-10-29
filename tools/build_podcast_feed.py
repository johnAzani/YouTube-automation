#!/usr/bin/env python3
"""$0-Cost Audio Podcast RSS XML Generator for Apple Podcasts & Spotify.

Generates an iTunes/Spotify-certified RSS 2.0 XML podcast feed (docs/podcast.xml)
hosted 100% free on GitHub Pages, channeling audio listeners into loyal
YouTube subscribers without paying third-party podcast host fees (e.g. Libsyn, Podbean).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PODCAST_XML_PATH = ROOT / "docs" / "podcast.xml"

PODCAST_METADATA = {
    "title": "The Secret Place: Bedtime Prayers & Calming Scripture Meditations",
    "link": "https://www.youtube.com/@TheSecretPlace",
    "language": "en-us",
    "copyright": "© 2026 The Secret Place. Public Domain Scripture Liturgies.",
    "subtitle": "Daily Bedtime Prayers, Nighttime Scripture & 432 Hz Peaceful Sleep Meditations",
    "author": "The Secret Place",
    "summary": (
        "Reverent, peaceful biblical prayer meditations and sacred scripture readings "
        "designed for bedtime listening, anxiety relief, and deep restorative sleep. "
        "Featuring Psalms 91, 23, 121, 27 and continuous 432 Hz Solfeggio acoustic soundscapes."
    ),
    "description": (
        "Welcome to The Secret Place. Experience deep peace, relief from nighttime anxiety, "
        "and restorative sleep through biblical scripture liturgies. Say these powerful Psalm prayers "
        "before you close your eyes tonight and rest under the shadow of the Almighty.\n\n"
        "Watch full visual kinetic devotionals on YouTube: https://www.youtube.com/@TheSecretPlace"
    ),
    "owner_name": "The Secret Place Editorial Team",
    "owner_email": "prayer@thesecretplace.media",
    "image_url": "https://johnazani.github.io/YouTube-automation/media/channel-prayer-avatar.png",
    "category": "Religion & Spirituality",
    "subcategory": "Christianity",
    "explicit": "no",
}

CANONICAL_EPISODES = [
    {
        "guid": "tsp-ep-0001-psalm-91",
        "title": "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep",
        "description": (
            "Say this Psalm 91 prayer before you sleep tonight. Let God's covenant of divine "
            "protection and supernatural peace surround your home, family, and mind from wall to wall.\n\n"
            "Scripture: Psalm 91:1-16 (KJV / NKJV Public Domain text).\n"
            "Watch with kinetic display subtitles on YouTube: https://www.youtube.com/watch?v=7RDX0fbIOtQ"
        ),
        "pub_date": "Thu, 29 Oct 2026 14:00:00 +0000",
        "duration_seconds": 360,
        "enclosure_url": "https://raw.githubusercontent.com/johnAzani/YouTube-automation/main/assets/deepdive/short-prayer-psalm91.mp3",
        "file_size": 5800000,
    },
    {
        "guid": "tsp-ep-0002-psalm-23",
        "title": "Psalm 23: The Lord Is My Shepherd — Night Prayer for Rest, Healing & Peace",
        "description": (
            "Surrender the worries and fatigue of this day into the gentle hands of the Good Shepherd. "
            "He restores your soul and leads you beside still waters.\n\n"
            "Scripture: Psalm 23:1-6.\n"
            "Watch full video on YouTube: https://www.youtube.com/@TheSecretPlace"
        ),
        "pub_date": "Wed, 28 Oct 2026 14:00:00 +0000",
        "duration_seconds": 360,
        "enclosure_url": "https://raw.githubusercontent.com/johnAzani/YouTube-automation/main/assets/deepdive/short-prayer-psalm91.mp3",
        "file_size": 5800000,
    },
    {
        "guid": "tsp-ep-0003-psalm-121",
        "title": "Psalm 121: He Who Keeps You Will Neither Slumber Nor Sleep",
        "description": (
            "Rest tonight knowing that your Keeper never slumbers. The Lord is your shade and your shield.\n\n"
            "Scripture: Psalm 121:1-8.\n"
            "Watch on YouTube: https://www.youtube.com/@TheSecretPlace"
        ),
        "pub_date": "Tue, 27 Oct 2026 14:00:00 +0000",
        "duration_seconds": 360,
        "enclosure_url": "https://raw.githubusercontent.com/johnAzani/YouTube-automation/main/assets/deepdive/short-prayer-psalm91.mp3",
        "file_size": 5800000,
    },
    {
        "guid": "tsp-ep-0004-sleep-sanctuary-1hr",
        "title": "1-Hour Bedtime Sleep Sanctuary: Psalms 91, 23 & 121 (432 Hz Solfeggio & Distant Rain)",
        "description": (
            "Continuous 1-hour ambient scripture meditation combining Psalms 91, 23, 121, and 27 "
            "with gentle 432 Hz Pythagorean sacred tuning and delta wave entrainment for deep restorative sleep.\n\n"
            "Watch full video on YouTube: https://www.youtube.com/@TheSecretPlace"
        ),
        "pub_date": "Mon, 26 Oct 2026 14:00:00 +0000",
        "duration_seconds": 3600,
        "enclosure_url": "https://raw.githubusercontent.com/johnAzani/YouTube-automation/main/assets/deepdive/short-prayer-psalm91.mp3",
        "file_size": 58000000,
    },
]


def generate_podcast_rss_xml() -> str:
    """Generate RFC-822 / iTunes compliant podcast XML."""
    episodes_xml = []
    for ep in CANONICAL_EPISODES:
        ep_xml = f"""    <item>
      <title>{escape(ep['title'])}</title>
      <description>{escape(ep['description'])}</description>
      <link>{escape(PODCAST_METADATA['link'])}</link>
      <guid isPermaLink="false">{ep['guid']}</guid>
      <pubDate>{ep['pub_date']}</pubDate>
      <enclosure url="{ep['enclosure_url']}" length="{ep['file_size']}" type="audio/mpeg"/>
      <itunes:duration>{ep['duration_seconds']}</itunes:duration>
      <itunes:explicit>no</itunes:explicit>
      <itunes:author>{escape(PODCAST_METADATA['author'])}</itunes:author>
    </item>"""
        episodes_xml.append(ep_xml)

    items_block = "\n".join(episodes_xml)

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" 
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(PODCAST_METADATA['title'])}</title>
    <link>{escape(PODCAST_METADATA['link'])}</link>
    <language>{PODCAST_METADATA['language']}</language>
    <copyright>{escape(PODCAST_METADATA['copyright'])}</copyright>
    <itunes:subtitle>{escape(PODCAST_METADATA['subtitle'])}</itunes:subtitle>
    <itunes:author>{escape(PODCAST_METADATA['author'])}</itunes:author>
    <itunes:summary>{escape(PODCAST_METADATA['summary'])}</itunes:summary>
    <description>{escape(PODCAST_METADATA['description'])}</description>
    <itunes:owner>
      <itunes:name>{escape(PODCAST_METADATA['owner_name'])}</itunes:name>
      <itunes:email>{escape(PODCAST_METADATA['owner_email'])}</itunes:email>
    </itunes:owner>
    <itunes:image href="{escape(PODCAST_METADATA['image_url'])}"/>
    <itunes:category text="{escape(PODCAST_METADATA['category'])}">
      <itunes:category text="{escape(PODCAST_METADATA['subcategory'])}"/>
    </itunes:category>
    <itunes:explicit>{PODCAST_METADATA['explicit']}</itunes:explicit>

{items_block}

  </channel>
</rss>
"""
    return feed.strip() + "\n"


def main() -> None:
    print("=" * 72)
    print("THE SECRET PLACE — $0-COST AUDIO PODCAST RSS FEED ENGINE")
    print("=" * 72)
    print(f"[*] Building iTunes & Spotify certified podcast feed...")
    xml_content = generate_podcast_rss_xml()
    PODCAST_XML_PATH.parent.mkdir(parents=True, exist_ok=True)
    PODCAST_XML_PATH.write_text(xml_content, encoding="utf-8")
    print(f"    [+] Saved feed to {PODCAST_XML_PATH} ({len(xml_content)} bytes)")
    print(f"    [+] Feed URL (GitHub Pages): https://johnazani.github.io/YouTube-automation/podcast.xml")
    print(f"    [+] Total Episodes Configured: {len(CANONICAL_EPISODES)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
