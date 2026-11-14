"""Every upload carries a French title and description beside the Spanish and Portuguese ones."""
from __future__ import annotations

import re

import pytest

from pipeline import localize_metadata as lm
from pipeline import scripture_text
from pipeline.channels import get_channel, scheduled_channels

DESCRIPTION = "A quiet prayer on the passage.\n\n#prayer #scripture"


def _localize(channel_id: str, title: str) -> dict:
    return lm.build_metadata_localizations(title, DESCRIPTION, "faith and prayer",
                                           channel_name=get_channel(channel_id).display_name,
                                           channel_id=channel_id)


@pytest.mark.parametrize("channel_id", scheduled_channels())
def test_every_channel_has_french_beside_spanish_and_portuguese(channel_id):
    name = get_channel(channel_id).display_name
    locs = _localize(channel_id, f"Prayer When the Night Is Long: Psalm 30:5 | {name}")
    assert set(locs) == {"es", "pt", "fr"}
    french = locs["fr"]
    assert french["title"].startswith("Psaume 30:5 Prière")
    assert french["title"].endswith(f"| {name}")
    assert len(french["title"]) <= 95
    assert len(french["description"].encode("utf-8")) <= 4900
    assert DESCRIPTION in french["description"], "the English description follows the French lines"
    assert lm._SPOKEN_IN_ENGLISH_FR in french["description"], "a French viewer is told the prayer is in English"
    assert "{" not in french["title"] + french["description"]


@pytest.mark.parametrize("channel_id", scheduled_channels())
def test_a_title_with_no_passage_still_gets_a_french_title(channel_id):
    name = get_channel(channel_id).display_name
    french = _localize(channel_id, f"A Quiet Prayer for Today | {name}")["fr"]
    assert french["title"].startswith("Prière") and french["title"].endswith(f"| {name}")


def test_every_book_of_the_bible_has_a_french_name():
    books = set(scripture_text._bible())
    # The Song of Solomon is on no channel's list and the title pattern does not read it.
    missing = books - set(lm._BOOKS_FR) - {"song of solomon"}
    assert not missing, f"no French name for {sorted(missing)}"


@pytest.mark.parametrize("english, french", [
    ("Night Prayer: 2 Timothy 1:7 | The Secret Place", "2 Timothée 1:7"),
    ("Believing God for Your Family: Acts 16:31-34 | The Family Altar", "Actes 16:31-34"),
    ("Isaiah 40:31 Midday Prayer", "Ésaïe 40:31"),
    ("Psalm 121 Night Prayer", "Psaume 121"),
    ("Strength for Today: 1 John 4:18", "1 Jean 4:18"),
    ("Morning Mercies: Lamentations 3:22–23", "Lamentations 3:22-23"),
    ("A prayer with no passage", ""),
])
def test_references_are_named_in_french(english, french):
    assert lm.french_reference(english) == french


def test_no_french_line_promises_an_outcome():
    for channel_id, texts in lm._FRENCH.items():
        for text in texts:
            lowered = text.lower()
            for word in ("miracle", "garanti", "immédiat", "instantan", "guérira", "vous guérit"):
                assert word not in lowered, f"{channel_id}: '{word}' in {text!r}"
            assert not re.search(r"[!?]", text), f"{channel_id}: {text!r}"


def test_only_the_channel_with_a_store_links_to_it():
    secret = _localize("secret-place", "Psalm 91 Night Prayer | The Secret Place")["fr"]["description"]
    morning = _localize("prayer2", "Psalm 5 Morning Prayer | The Morning Altar")["fr"]["description"]
    assert ("selar" in secret.lower()) == bool(lm.SELAR_JOURNAL_URL)
    assert "selar" not in morning.lower()


def test_a_finance_video_gets_no_prayer_text_in_any_language():
    assert lm.build_metadata_localizations("Rates Explained", DESCRIPTION, "finance") == {}
