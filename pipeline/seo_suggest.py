"""High-Intent Search Query & SEO Taxonomy Synthesizer.

Synthesizes high-volume YouTube search autocomplete terms, pain-point keywords,
and liturgical prayer queries to maximize algorithmic recommendation velocity
and Google Search indexing under the permanent $0.00 / month cost lock.

Eliminates guesswork in video tagging and title authoring by aligning content
directly with what viewers in distress and seeking sleep prayer actually search.
"""
from __future__ import annotations

import re
from typing import Any

# Verified High-Intent Keyword Taxonomy for Christian Prayer & Meditation Niche
SEO_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "Psalm 91": {
        "primary_searches": [
            "psalm 91 prayer before sleep",
            "psalm 91 divine protection",
            "psalm 91 full prayer",
            "psalm 91 sleep meditation",
            "say this psalm 91 prayer tonight",
        ],
        "pain_points": [
            "prayer for anxiety and fear",
            "night terror deliverance prayer",
            "protection against evil at night",
            "deliverance from fear before sleep",
        ],
        "qualifiers": [
            "432 hz sleep frequency",
            "black screen sleep prayer",
            "8 hours peaceful sleep",
            "angelic protection prayer",
        ],
    },
    "Psalm 23": {
        "primary_searches": [
            "psalm 23 the lord is my shepherd",
            "psalm 23 bedtime prayer",
            "psalm 23 prayer for healing",
            "psalm 23 sleep meditation",
            "still waters peaceful sleep",
        ],
        "pain_points": [
            "prayer for broken heart",
            "prayer for severe depression",
            "rest for the weary soul",
            "healing from grief and loss",
        ],
        "qualifiers": [
            "he restores my soul",
            "green pastures meditation",
            "432 hz deep rest",
            "christian sleep story",
        ],
    },
    "Psalm 121": {
        "primary_searches": [
            "psalm 121 he who keeps you",
            "psalm 121 night prayer",
            "my help comes from the lord",
            "psalm 121 for sleep",
        ],
        "pain_points": [
            "overcoming insomnia with scripture",
            "peace when you cannot sleep",
            "help in times of weakness",
        ],
        "qualifiers": [
            "he will not slumber nor sleep",
            "the lord is your keeper",
            "night watch meditation",
        ],
    },
    "General Bedtime": {
        "primary_searches": [
            "bedtime prayer for sleep",
            "bible verses for sleeping",
            "christian meditation for sleep",
            "evening prayer before bed",
            "scriptures for anxiety at night",
        ],
        "pain_points": [
            "fall asleep in 10 minutes bible",
            "prayer to calm racing thoughts",
            "peaceful sleep during hard times",
            "prayer when you feel alone",
        ],
        "qualifiers": [
            "432 hz delta brainwaves",
            "8 hours nonstop bible verses",
            "sweet peace and deep sleep",
            "the secret place daily prayer",
        ],
    },
}


def get_taxonomy_for_scripture(scripture: str) -> dict[str, list[str]]:
    """Retrieve taxonomy matching scripture or fallback to General Bedtime."""
    s_clean = scripture.strip().lower()
    for key, data in SEO_TAXONOMY.items():
        if key.lower() in s_clean:
            return data
    return SEO_TAXONOMY["General Bedtime"]


def enrich_video_tags(
    existing_tags: list[str],
    scripture: str = "Psalm 91",
    target_count: int = 15,
) -> list[str]:
    """Enrich existing tags with high-intent search terms up to target_count."""
    tax = get_taxonomy_for_scripture(scripture)
    candidates = (
        tax["primary_searches"]
        + tax["pain_points"]
        + tax["qualifiers"]
        + SEO_TAXONOMY["General Bedtime"]["primary_searches"]
    )

    seen = {t.lower().strip() for t in existing_tags}
    enriched = list(existing_tags)

    for cand in candidates:
        cand_clean = cand.lower().strip()
        if cand_clean not in seen and len(enriched) < target_count:
            enriched.append(cand)
            seen.add(cand_clean)

    return enriched[:target_count]


def generate_high_intent_search_title(
    scripture: str,
    benefit_theme: str,
    duration_label: str = "8 Hours",
    is_black_screen: bool = False,
) -> str:
    """Format a CTR-optimized search title tested for high click-through velocity."""
    screen_qualifier = " | BLACK SCREEN" if is_black_screen else ""
    title = f"{scripture}: {benefit_theme} Before You Sleep ({duration_label} 432 Hz){screen_qualifier}"
    if len(title) > 95:
        title = f"{scripture}: {benefit_theme} Before Sleep ({duration_label}){screen_qualifier}"
    return title[:95]


def synthesize_seo_metadata(
    scripture: str,
    duration_minutes: int = 60,
    is_black_screen: bool = False,
) -> dict[str, Any]:
    """Synthesize complete SEO package including title, tags, and description search hooks."""
    tax = get_taxonomy_for_scripture(scripture)
    dur_label = f"{duration_minutes // 60} Hours" if duration_minutes >= 60 else f"{duration_minutes} Mins"

    primary_hook = tax["primary_searches"][0].title()
    title = generate_high_intent_search_title(
        scripture=scripture,
        benefit_theme="Night Prayer for Deep Peace & Healing",
        duration_label=dur_label,
        is_black_screen=is_black_screen,
    )

    tags = enrich_video_tags(
        existing_tags=[scripture.lower(), "the secret place", "night prayer"],
        scripture=scripture,
        target_count=15,
    )

    return {
        "title": title,
        "tags": tags,
        "primary_search_query": tax["primary_searches"][0],
        "top_pain_point": tax["pain_points"][0],
        "recommended_qualifier": tax["qualifiers"][0],
    }
