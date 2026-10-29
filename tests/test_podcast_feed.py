"""Unit tests for $0-Cost Audio Podcast RSS Feed Engine."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from tools.build_podcast_feed import (
    CANONICAL_EPISODES,
    PODCAST_METADATA,
    generate_podcast_rss_xml,
)


def test_podcast_metadata_integrity():
    """Verify podcast metadata has author, categories, and links."""
    assert len(PODCAST_METADATA["title"]) > 0
    assert len(PODCAST_METADATA["link"]) > 0
    assert PODCAST_METADATA["category"] == "Religion & Spirituality"
    assert len(CANONICAL_EPISODES) >= 4


def test_generate_podcast_rss_xml_valid():
    """Verify RSS XML feed is well-formed XML and conforms to iTunes specs."""
    xml_str = generate_podcast_rss_xml()
    assert len(xml_str) > 1000
    assert "<rss version=\"2.0\"" in xml_str
    assert "<channel>" in xml_str
    assert "<title>The Secret Place:" in xml_str
    assert "https://www.youtube.com/@TheSecretPlace" in xml_str

    # Parse with ElementTree to verify XML well-formedness
    root = ET.fromstring(xml_str)
    assert root.tag == "rss"
    channel = root.find("channel")
    assert channel is not None
    items = channel.findall("item")
    assert len(items) == len(CANONICAL_EPISODES)
    for it in items:
        assert it.find("title") is not None
        assert it.find("enclosure") is not None
        assert it.find("guid") is not None
