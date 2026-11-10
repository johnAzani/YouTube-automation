"""Channel capability matrix — every channel is a first-class citizen.

Why this module exists
----------------------
The automation was built for one channel and grew a second one channel at a
time, which is how "The Morning Altar has no Shorts / no brain" and "The Secret
Place has no per-channel queue row" happened in the first place: each capability
was a hardcoded ``if channel == "prayer2"`` somewhere in the pipeline. A branch
like that is invisible until the day the *other* channel needs it, and then it
silently does the wrong thing instead of failing.

So the rule is now structural rather than remembered:

    Every channel registered in ``pipeline.channels.CHANNELS`` has every
    capability in ``REQUIRED_CAPABILITIES``. There are no per-channel feature
    switches — a capability exists for all channels or for none.

This module is the **only** place that is allowed to know which channel is which.
It holds each channel's *data* (equipment files, roadmap, branding strings,
queue names), never per-channel behaviour: the pipeline reads these values and
runs one code path. ``tests/test_channel_parity.py`` fails the build if a
channel-specific literal reappears anywhere else, if a required capability datum
is missing, or if a workflow stops covering every channel.

Adding a channel
----------------
1. Add its profile to ``pipeline.channels.CHANNELS``.
2. Add its block here with every field below (the test lists what is missing).
3. Add its secrets mapping to each channel-scoped workflow.

Nothing else in the codebase should need to change — and the parity test will
tell you if it does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from pipeline.channels import normalize_channel_id

EQUIPMENT_DIR = Path(__file__).resolve().parent / "brain_equipment"

#: Equipment modules every channel must compile into its brain prompt.
REQUIRED_EQUIPMENT: tuple[str, ...] = (
    "system_instruction",
    "theological_rubric",
)

#: Capabilities every channel has, by construction. Keep this list honest: it is
#: what the parity test asserts, and what `scripts/channel_parity.py` prints.
REQUIRED_CAPABILITIES: tuple[str, ...] = (
    "brain_supply",          # unattended long-form authoring from its own roadmap
    "backlog_expansion",     # lengthening under-floor scripts under its own quota
    "factcheck_gate",        # worksheet + approval choke point before publishing
    "per_channel_queue_rows",# its own queue_health()/watchdog rows
    "scheduled_production",  # its own leg in the scheduled Produce workflow
    "companion_shorts",      # 9:16 Shorts queued, authored and published per channel
    "branded_authoring",     # refuses output branded for another channel
    "roadmap_queue",         # its own scripture roadmap with unique job ids
    "per_channel_quota",     # its own Gemini key pool (prefixed secret)
    "owner_idle_safety",     # free-tier exhaustion idles only that channel
)


@dataclass(frozen=True)
class Brand:
    """Everything channel-specific about *what the writing says*."""

    channel_id: str
    display_name: str
    handle: str
    declaration: str          # value of frontmatter `channel:`
    title_suffix: str
    producer_line: str
    closing_cta: str
    #: Brand strings that must appear in anything the brain authors
    required_phrases: tuple[str, ...]
    #: Brand strings from the *other* channel that must never appear
    forbidden_phrases: tuple[str, ...]
    #: Lines injected into the authoring prompt (identical mechanism per channel)
    authoring_directive: tuple[str, ...]
    #: Shorts dressing
    short_title_template: str   # .format(label=..., hook=...)
    short_channel_label: str    # how the Short prompt describes the channel
    short_prayer_kind: str      # "pre-sleep" / "sunrise"
    short_opening: str          # what the narration invites the viewer to do first
    short_imagery: str          # what the b-roll queries should describe
    subscribe_heading: str      # heading of the description's subscribe block
    short_target_window_utc: str  # slot a queued Short aims for
    short_tags: tuple[str, ...]
    short_hashtags: str
    short_end_card: str
    short_key_namespace: str    # "" for channel 1; keeps Short keys globally unique
    #: Comment replies (audited 2026-11-07). The reply engine used to be
    #: channel-blind: it hardcoded "the pastoral voice of The Secret Place" and
    #: replied as channel 1 on whatever credentials it was handed. Who answers,
    #: and the daypart that answer belongs to, are brand data like any other —
    #: declared once here instead of a second copy inside the reply engine.
    comment_persona: str        # "the pastoral prayer team at {display_name}"
    comment_farewell: str       # the daypart-correct closing line
    #: The ribbon line on a Short's 9:16 poster (2026-11-07). The poster used to
    #: hardcode "PRAYER BEFORE SLEEP" for every channel, so a sunrise Short wore
    #: the night channel's wording. `short_prayer_kind` still picks the colour
    #: grade (night / dawn / noon); this picks the words.
    shorts_poster_kicker: str
    #: Pinned comments. Both are .format() templates.
    longform_pinned_comment: str
    short_pinned_comment: str
    #: Long-form normalization data (title label, SEO hook template, verified Commons plates)
    longform_prayer_label: str = "Night Prayer"
    seo_hook_template: str = (
        "Rest tonight in {display_name} with {scripture} (KJV) "
        "and release every anxious thought into the Father's keeping before sleep."
    )
    verified_commons_queries: tuple[tuple[str, int, str], ...] = ()
    #: Per-channel closed-loop feedback artifact & series playlists (growth-autopilot)
    feedback_artifact_name: str = "performance_feedback.json"
    anchor_video: tuple[str, str, tuple[str, ...]] | None = None
    series_playlists: tuple[tuple[str, str, str, tuple[str, ...]], ...] = ()
    #: Per-channel Community Tab schedule (empty tuple -> canonical Secret Place schedule)
    community_posts: tuple[dict, ...] = ()
    #: Shorts-to-longform conversion bridge copy & fallback title
    short_bridge_theme: str = "peaceful rest and sovereign nighttime protection"
    short_fallback_title: str = "Night Prayers of Divine Protection"
    #: Subscriber milestone celebration copy (daypart-specific, zero cross-channel bleed)
    milestone_subheading_1250: str = "A SANCTUARY OF PEACE ACROSS THE NATIONS"
    milestone_subheading_1500: str = "UNBROKEN NIGHTTIME PRAYER WATCH"
    milestone_sanctuary_phrase: str = "before sleep"
    milestone_cadence_phrase: str = "every night"
    milestone_closing_blessing: str = "Peace be upon your home tonight."
    milestone_2000_closing: str = "your evening sanctuary of rest"
    #: Daypart-scoped SEO hashtags, fallback hooks, backend tag seeds, localizations & comments
    seo_fallback_hashtags: tuple[str, ...] = (
        "#NightPrayer", "#PrayerBeforeSleep", "#BedtimePrayer", "#TheSecretPlace",
    )
    seo_hook_ref_template: str = (
        "Pray this {ref} KJV night prayer before sleep for deep peace, "
        "quiet rest, and God's protection over your home tonight."
    )
    seo_hook_generic: str = (
        "Pray this KJV bedtime scripture prayer before you sleep for deep peace, "
        "freedom from anxiety, and God's watchful protection tonight."
    )
    seo_book_tag_suffixes: tuple[str, ...] = ("night prayer", "prayer for sleep")
    seo_tag_seeds: tuple[str, ...] = (
        "prayer before sleep",
        "night prayer for peace and protection",
        "bedtime prayer",
        "christian sleep prayer",
        "kjv scripture prayer",
        "the secret place prayer",
    )
    localized_title_es: str = "Oración de la Noche para Dormir en Paz | {channel_name}"
    localized_title_pt: str = "Oração da Noite para Dormir em Paz | {channel_name}"
    localized_ref_title_es: str = "{ref_es} Oración de la Noche para Dormir en Paz | {channel_name}"
    localized_ref_title_pt: str = "{ref_pt} Oração da Noite para Dormir em Paz | {channel_name}"
    localized_desc_lead_es: str = "Oración nocturna de protección divina y paz. Descansa bajo la sombra del Altísimo."
    localized_desc_lead_pt: str = "Oração poderosa da noite para proteção e paz espiritual. Descanse sob as asas de Deus."
    localized_invite_es: str = (
        "Escucha esta oración bíblica antes de dormir para recibir la paz profunda de Dios y protección sobre tu hogar."
    )
    localized_invite_pt: str = (
        "Ouça esta oração bíblica antes de dormir para receber a paz profunda de Deus e proteção sobre o seu lar."
    )
    default_comment_scripture_hook: str = (
        "Numbers 6:24-26 — 'The Lord bless you and keep you; the Lord make His face shine upon you and give you peace.'"
    )
    default_comment_theme: str = "sacred peace and restorative sleep"
    #: 16:9 long-form CTR thumbnail daypart grade & default Test & Compare hero copy
    ctr_grade: str = "night"
    ctr_hook_hero: str = "PRAY THIS TONIGHT"
    ctr_quiet_hero: str = "WHILE YOU SLEEP"


@dataclass(frozen=True)
class ChannelCapabilities:
    """The channel's data, in the shape the shared pipeline expects."""

    channel_id: str
    brand: Brand
    equipment: Mapping[str, str]   # module -> filename in brain_equipment/
    roadmap: str                   # roadmap namespace in scripts.continuous_research
    roadmap_name: str              # constant name, quoted in refusals
    legacy_queue_alias: str        # historic queue_health row name ("" if none)
    supply_min_publishable: int    # scheduled supply target


_SECRET_PLACE_COMMENT = (
    "🕊️ Beloved family, if you are listening to this tonight, write 'AMEN' in faith to claim "
    "God's promise of {theme} over your home, your children, and your mind.\n\n"
    "📖 {scripture_hook}\n\n"
    "Drop your prayer requests below — our pastoral editorial team reads and intercedes over "
    "every single name before this night closes. Rest in holy stillness tonight. You are not "
    "alone. 🙏✨{footer}"
)

_MORNING_ALTAR_COMMENT = (
    "🌅 Beloved family, if you are beginning this day with us, write 'AMEN' in faith to claim "
    "God's promise of {theme} over your home, your work, and your mind today.\n\n"
    "📖 {scripture_hook}\n\n"
    "Drop your prayer requests below — our pastoral editorial team reads and intercedes over "
    "every single name. Go into today covered, calm, and confident. You are not alone. 🙏✨{footer}"
)

_MIDDAY_WATCH_COMMENT = (
    "☀️ Beloved family, if you are pausing your day with us right now, write 'AMEN' in faith to "
    "claim God's promise of {theme} over your work, your home, and your mind this afternoon.\n\n"
    "📖 {scripture_hook}\n\n"
    "Drop your prayer request below — our pastoral editorial team reads and intercedes over "
    "every single name. Whatever this afternoon is asking of you, you are not carrying it "
    "alone. 🙏✨{footer}"
)

_MIDNIGHT_WATCH_COMMENT = (
    "🕯️ Beloved watchmen, if you are standing in prayer at this midnight hour, write 'AMEN' in "
    "faith to declare God's promise of {theme} over your household, your calling, and your season.\n\n"
    "📖 {scripture_hook}\n\n"
    "Leave your midnight prayer request below — our intercessory team stands on the watchtower "
    "over every petition. Like Paul and Silas at midnight, praise goes before your breakthrough. "
    "You are not standing alone. 🙏🔥{footer}"
)

_FAMILY_ALTAR_COMMENT = (
    "🏡 Beloved household of faith, if you are gathering your home and loved ones in prayer with "
    "us today, write 'AMEN' in faith to claim God's promise of {theme} over your family, your "
    "children, your marriage, and every room under your roof.\n\n"
    "📖 {scripture_hook}\n\n"
    "Share the first names or family needs you are lifting up below — our pastoral prayer team "
    "intercedes over every household represented here. As for me and my house, we will serve the "
    "LORD! 🙏🌿{footer}"
)

_BRANDS: dict[str, Brand] = {
    "secret-place": Brand(
        channel_id="secret-place",
        display_name="The Secret Place",
        handle="@TheSecretPlace",
        declaration="secret-place",
        title_suffix="| The Secret Place",
        producer_line="Produced by The Secret Place | Daily Prayer & Scripture.",
        closing_cta=(
            "Type Amen to agree with this prayer, and subscribe to The Secret Place "
            "to pray with us every night."
        ),
        required_phrases=("The Secret Place",),
        forbidden_phrases=(
            "The Morning Altar",
            "@TheMorningAltarDaily",
            "the morning altar",
            "begin every sunrise with us",
            "The Midday Watch",
            "@TheMiddayWatch",
            "noonday prayer",
            "The Midnight Watch",
            "@TheMidnightWatchDaily",
            "@TheMidnightWatch",
            "stand on the watchtower in midnight prayer",
            "The Family Altar",
            "@TheFamilyAltarDaily",
            "cover your home and family in daily prayer",
        ),
        authoring_directive=(
            "CHANNEL: The Secret Place (secret-place) - night prayer, never a morning devotional.",
            "Frontmatter MUST include exactly: channel: secret-place",
            "Title MUST end with: | The Secret Place",
            'Tags MUST include "the secret place" and "prayer before sleep"; never The Morning '
            'Altar, sunrise or morning-prayer branding.',
            "Description MUST credit: Produced by The Secret Place | Daily Prayer & Scripture.",
            "Scenes follow the night arc in the rubric and end with: "
            '"Type Amen to agree with this prayer, and subscribe to The Secret Place to pray '
            'with us every night."',
            "Asset queries MUST be night, candlelight, quiet-room or starfield scenes.",
        ),
        short_title_template="Say This {label} Prayer Before You Sleep | {hook}",
        subscribe_heading="🙏 PRAY WITH US EVERY NIGHT",
        short_target_window_utc="14:14",
        short_channel_label="a faceless bedtime-prayer channel called The Secret Place",
        short_prayer_kind="pre-sleep",
        short_opening="breathe",
        short_imagery="calm nature or candle",
        short_tags=(
            "night prayer",
            "bedtime prayer",
            "prayer of protection",
            "peaceful sleep",
            "the secret place",
        ),
        short_hashtags="#Shorts #{tag_key} #NightPrayer #BedtimePrayer #DailyScripture #TheSecretPlace",
        short_end_card="The Secret Place — prayers every day",
        short_key_namespace="",
        comment_persona="the pastoral prayer team at The Secret Place",
        comment_farewell="Rest in His peace tonight.",
        shorts_poster_kicker="PRAYER BEFORE SLEEP",
        longform_pinned_comment=_SECRET_PLACE_COMMENT,
        short_pinned_comment=(
            "🕊️ PRAY THE FULL NIGHTTIME SCRIPTURE MEDITATION:\n"
            "Tap the linked full-length prayer right above this title (or visit {handle}) "
            "to experience the complete prayer of {scripture}:\n"
            "👉 {url}\n\n"
            "📖 Our printable 30-Night Bedside Prayer Journal & voluntary ministry support links "
            "are clickable directly on our {handle} channel profile.\n\n"
            "Rest under God's covenant of {theme} tonight. "
            "Write 'AMEN' in faith and leave your prayer request below — we are interceding for "
            "your household! 🙏🕊️✨{footer}"
        ),
        longform_prayer_label="Night Prayer",
        seo_hook_template=(
            "Rest tonight in {display_name} with {scripture} (KJV) "
            "and release every anxious thought into the Father's keeping before sleep."
        ),
        verified_commons_queries=(
            ("starry night sky milky way mountains", 4, "4x Public domain — NPS / NASA dark sky reserve astrophotography"),
            ("peaceful night landscape moon over calm lake", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("calm mountain lake still water reflection nightfall", 4, "4x Public domain — NPS Mirror Lake and Crater Lake twilight scans"),
            ("ancient chapel interior candlelight peaceful sanctuary", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("still water perfect reflection moon night sky stars", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("star night sky over quiet countryside peaceful", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
        ),
        feedback_artifact_name="performance_feedback.json",
        anchor_video=(
            "7RDX0fbIOtQ",
            "Psalm 91: The Complete Prayer of Divine Protection Before You Sleep",
            ("psalm 91", "prayer of protection", "sleep prayer", "the secret place"),
        ),
        series_playlists=(
            (
                "night_prayers",
                "Night Prayers of Divine Protection — The Secret Place",
                "Say these powerful Psalm prayers before you sleep tonight. Let God's covenant of "
                "divine protection, peace, and angelic shelter surround your home, family, and mind from wall to wall.\n\n"
                "Featuring Psalm 91, Psalm 23, Psalm 121, and Psalm 27 with peaceful 432 Hz bedtime meditation soundscapes.\n\n"
                "Produced by The Secret Place | Daily Scripture & Bedtime Prayer.",
                ("psalm 91", "protection", "night prayer", "sleep prayer", "secret place"),
            ),
            (
                "bedtime_sleep",
                "Bedtime Scripture Meditations for Deep Sleep & Peace (432 Hz)",
                "Soothing scripture meditations, biblical sleep prayers, and calming nighttime scriptures "
                "designed to overcome insomnia, quiet racing thoughts, and guide you into deep, restorative rest.\n\n"
                "Featuring 432 Hz Solfeggio acoustic beds and sacred scripture.\n\n"
                "Produced by The Secret Place | Daily Scripture & Bedtime Prayer.",
                ("sleep", "bedtime", "rest", "peace", "432 hz", "meditation"),
            ),
            (
                "complete_psalms",
                "The Complete Psalms Devotional Series (Exposition & Prayer)",
                "Verse-by-verse devotional prayer and classical commentary across the Book of Psalms. "
                "Deep-dive into God's word with classical exposition, historical context, and contemplative evening prayer.\n\n"
                "Produced by The Secret Place | Daily Scripture & Bedtime Prayer.",
                ("psalm", "scripture", "exposition", "devotional"),
            ),
        ),
    ),
    "prayer2": Brand(
        channel_id="prayer2",
        display_name="The Morning Altar",
        handle="@TheMorningAltarDaily",
        declaration="prayer2",
        title_suffix="| The Morning Altar",
        producer_line="Produced by The Morning Altar | Daily Sunrise Prayer",
        closing_cta=(
            "Type Amen to agree with this prayer, and subscribe to The Morning Altar to begin "
            "every sunrise with us."
        ),
        required_phrases=("The Morning Altar",),
        forbidden_phrases=(
            "The Secret Place",
            "@TheSecretPlace",
            "the secret place",
            "before you sleep",
            "bedtime prayer",
            "prayer before sleep",
            "night prayer",
            "close your eyes tonight",
            "pray with us every night",
            "The Midday Watch",
            "@TheMiddayWatch",
            "noonday prayer",
            "The Midnight Watch",
            "@TheMidnightWatchDaily",
            "@TheMidnightWatch",
            "midnight watch",
            "The Family Altar",
            "@TheFamilyAltarDaily",
            "cover your home and family in daily prayer",
        ),
        authoring_directive=(
            "CHANNEL: The Morning Altar (prayer2) - sunrise, never bedtime.",
            "Frontmatter MUST include exactly: channel: prayer2",
            "Title MUST end with: | The Morning Altar",
            'Tags MUST include "morning prayer" and "the morning altar"; never "the secret '
            'place", sleep or bedtime terms.',
            "Description MUST credit: Produced by The Morning Altar | Daily Sunrise Prayer",
            'Scenes follow the sunrise arc in the rubric and end with: "Type Amen to agree with '
            'this prayer, and subscribe to The Morning Altar to begin every sunrise with us."',
            "Asset queries MUST be sunrise/dawn/morning-light scenes, never night or moonlight.",
        ),
        short_title_template="Say This {label} Prayer at Sunrise | {hook}",
        subscribe_heading="🙏 BEGIN EVERY MORNING IN PRAYER",
        short_target_window_utc="06:14",
        short_channel_label="a faceless sunrise-prayer channel called The Morning Altar",
        short_prayer_kind="sunrise",
        short_opening="greet the morning",
        short_imagery="dawn, sunrise light or open-window morning",
        short_tags=(
            "morning prayer",
            "sunrise prayer",
            "daily devotion",
            "the morning altar",
            "scripture meditation",
        ),
        short_hashtags="#Shorts #{tag_key} #MorningPrayer #SunrisePrayer #DailyDevotion #TheMorningAltar",
        short_end_card="The Morning Altar — begin every sunrise in prayer",
        short_key_namespace="morning",
        comment_persona="the morning prayer team at The Morning Altar",
        comment_farewell="Go into your day covered by His grace.",
        shorts_poster_kicker="BEGIN YOUR DAY IN PRAYER",
        longform_pinned_comment=_MORNING_ALTAR_COMMENT,
        short_pinned_comment=(
            "🌅 PRAY THE FULL SUNRISE SCRIPTURE MEDITATION:\n"
            "Tap the linked full-length prayer right above this title (or visit {handle}) "
            "to begin the complete morning prayer of {scripture}:\n"
            "👉 {url}\n\n"
            "Write 'AMEN' in faith and leave your prayer request below — we are interceding "
            "over your household before this day begins! Go into today covered, calm, and "
            "confident. 🙏🌅✨{footer}"
        ),
        longform_prayer_label="Morning Prayer",
        seo_hook_template=(
            "Begin this sunrise at {display_name} with {scripture} (KJV) "
            "and commit every step and decision of your day to the Lord in prayer."
        ),
        verified_commons_queries=(
            ("golden dawn light over misty landscape morning", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("sunrise dawn light over quiet valley morning serene", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("sunlight breaking through clouds mountain pass", 3, "3x Public domain — USFS Rocky Mountain National Forest crepuscular ray scans"),
            ("golden light rays over calm landscape morning dawn", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("peaceful sunrise over misty countryside morning", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("peaceful sunrise over misty alpine valley", 4, "4x Public domain — USGS alpine valley dawn mist photography"),
        ),
        feedback_artifact_name="performance_feedback_prayer2.json",
        anchor_video=None,
        series_playlists=(
            (
                "morning_prayers",
                "Morning Prayers to Begin Your Day — The Morning Altar",
                "Begin every sunrise at The Morning Altar with KJV scripture declarations and guided prayer "
                "for peace, protection, and God's presence over your household.\n\n"
                "Produced by The Morning Altar | Daily Sunrise Prayer.",
                ("morning prayer", "sunrise", "morning altar", "lamentations", "mark", "begin your day"),
            ),
            (
                "sunrise_guidance",
                "Sunrise Scripture Prayers for Wisdom, Favor & Work — The Morning Altar",
                "Commit your plans, decisions, and daily work to the Lord at daybreak with Proverbs and Psalms "
                "morning prayers.\n\n"
                "Produced by The Morning Altar | Daily Sunrise Prayer.",
                ("proverbs", "trust", "guidance", "mercy", "mercies", "work", "morning"),
            ),
            (
                "morning_psalms",
                "Morning Psalms & Daily Devotions (KJV) — The Morning Altar",
                "Verse-by-verse sunrise Psalm meditations and classical KJV morning prayers to anchor your heart before the day begins.\n\n"
                "Produced by The Morning Altar | Daily Sunrise Prayer.",
                ("psalm", "scripture", "devotion", "morning prayer"),
            ),
        ),
        community_posts=(
            {
                "post_id": "comm-prayer2-001-sunday-dawn",
                "post_type": "POLL",
                "title": "Where do you need God's fresh mercy at sunrise today?",
                "body_text": (
                    "It is of the Lord's mercies that we are not consumed, because his compassions fail not. "
                    "They are new every morning: great is thy faithfulness (Lamentations 3:22-23).\n\n"
                    "Before this new week gathers speed, commit your first thoughts at The Morning Altar. "
                    "Vote below and type 'AMEN' to agree in sunrise prayer! 🌅🙏"
                ),
                "poll": {
                    "question": "What are you placing on The Morning Altar this morning?",
                    "options": [
                        "Peace & protection over my household today",
                        "Wisdom & favor in my work and decisions",
                        "Strength, health & renewed joy at daybreak",
                        "Guidance for an open door this week",
                    ],
                    "context_scripture": "Lamentations 3:22-23",
                },
                "image_rel_path": "comm-prayer2-001-sunday-dawn.png",
                "target_utc": "06:00",
                "tags": ["#MorningPrayer", "#TheMorningAltar", "#Lamentations3", "#DailyDevotion"],
            },
            {
                "post_id": "comm-prayer2-002-midweek-altar",
                "post_type": "PRAYER_WALL",
                "title": "The Morning Altar Sunrise Prayer Wall: Share Today's Requests",
                "body_text": (
                    "My voice shalt thou hear in the morning, O Lord; in the morning will I direct my prayer unto thee, "
                    "and will look up (Psalm 5:3).\n\n"
                    "Beloved family, drop your morning prayer requests below before you step into today's work. "
                    "Our morning prayer team intercedes over every household named here. Write 'AMEN' in faith!"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer2-002-midweek-altar.png",
                "target_utc": "06:00",
                "tags": ["#MorningPrayerWall", "#Psalm5", "#TheMorningAltar", "#SunrisePrayer"],
            },
            {
                "post_id": "comm-prayer2-003-thursday-direction",
                "post_type": "POLL",
                "title": "Which morning scripture anchors your steps today?",
                "body_text": (
                    "Trust in the Lord with all thine heart; and lean not unto thine own understanding. "
                    "In all thy ways acknowledge him, and he shall direct thy paths (Proverbs 3:5-6).\n\n"
                    "Walk into today confident that the Father goes before you."
                ),
                "poll": {
                    "question": "Which morning promise are you standing on today?",
                    "options": [
                        "Proverbs 3:5-6 — He directs my paths",
                        "Psalm 143:8 — Lovingkindness in the morning",
                        "Psalm 90:14 — Satisfy us early with Thy mercy",
                        "Isaiah 40:31 — Renewed strength like eagles",
                    ],
                    "context_scripture": "Proverbs 3:5-6",
                },
                "image_rel_path": "comm-prayer2-003-thursday-direction.png",
                "target_utc": "06:00",
                "tags": ["#Proverbs3", "#MorningScripture", "#TheMorningAltar"],
            },
            {
                "post_id": "comm-prayer2-004-friday-joy",
                "post_type": "SCRIPTURE_DEVOTIONAL",
                "title": "Joy Cometh in the Morning: Step Into Today Unafraid",
                "body_text": (
                    "Weeping may endure for a night, but joy cometh in the morning (Psalm 30:5).\n\n"
                    "Whatever yesterday carried, a fresh dawn of God's favor has risen over your life today. "
                    "Type 'NEW MERCIES TODAY' in the comments if you receive His morning peace! 🌅✨"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer2-004-friday-joy.png",
                "target_utc": "06:00",
                "tags": ["#Psalm30", "#JoyInTheMorning", "#TheMorningAltar"],
            },
        ),
        short_bridge_theme="morning mercy, clear guidance, and daily covering",
        short_fallback_title="Morning Prayers to Begin Your Day — The Morning Altar",
        milestone_subheading_1250="A SUNRISE ALTAR ACROSS THE NATIONS",
        milestone_subheading_1500="UNBROKEN DAILY SUNRISE PRAYER",
        milestone_sanctuary_phrase="at daybreak",
        milestone_cadence_phrase="every sunrise",
        milestone_closing_blessing="Go into today covered by His grace.",
        milestone_2000_closing="your daily sunrise altar of prayer",
        seo_fallback_hashtags=(
            "#MorningPrayer", "#SunrisePrayer", "#DailyDevotion", "#TheMorningAltar",
        ),
        seo_hook_ref_template=(
            "Pray this {ref} KJV morning prayer at sunrise for daily guidance, "
            "fresh mercy, and God's covering over your steps today."
        ),
        seo_hook_generic=(
            "Pray this KJV sunrise scripture prayer to begin your day in God's "
            "presence, wisdom, and steadfast covering."
        ),
        seo_book_tag_suffixes=("morning prayer", "sunrise prayer"),
        seo_tag_seeds=(
            "morning prayer before work",
            "daily morning prayer",
            "sunrise scripture prayer",
            "prayer to start your day",
            "kjv morning devotion",
            "the morning altar prayer",
            "prayer for guidance and wisdom",
            "christian morning prayer",
        ),
        localized_title_es="Oración de la Mañana al Amanecer en Paz | {channel_name}",
        localized_title_pt="Oração da Manhã ao Amanhecer em Paz | {channel_name}",
        localized_ref_title_es="{ref_es} Oración de la Mañana para Empezar el Día | {channel_name}",
        localized_ref_title_pt="{ref_pt} Oração da Manhã para Começar o Dia | {channel_name}",
        localized_desc_lead_es="Oración matutina de sabiduría, gracia y cobertura divina para comenzar el día.",
        localized_desc_lead_pt="Oração matinal de sabedoria, graça e cobertura divina para começar o dia.",
        localized_invite_es=(
            "Escucha esta oración bíblica al amanecer para comenzar tu día con la sabiduría, gracia y cobertura de Dios."
        ),
        localized_invite_pt=(
            "Ouça esta oração bíblica ao amanhecer para começar o seu dia com a sabedoria, graça e cobertura de Deus."
        ),
        default_comment_scripture_hook=(
            "Psalm 5:3 — 'My voice shalt thou hear in the morning, O Lord; in the morning will I "
            "direct my prayer unto thee, and will look up.'"
        ),
        default_comment_theme="fresh morning mercy, clear guidance, and daily covering",
        ctr_grade="dawn",
        ctr_hook_hero="PRAY AT SUNRISE",
        ctr_quiet_hero="FIRST LIGHT PEACE",
    ),
    "prayer3": Brand(
        channel_id="prayer3",
        display_name="The Midday Watch",
        handle="@TheMiddayWatch",
        declaration="prayer3",
        title_suffix="| The Midday Watch",
        producer_line="Produced by The Midday Watch | Noonday Prayer & Scripture",
        closing_cta=(
            "Type Amen to agree with this prayer, and subscribe to The Midday Watch "
            "to pause and pray with us at noon."
        ),
        required_phrases=("The Midday Watch",),
        forbidden_phrases=(
            "The Secret Place",
            "@TheSecretPlace",
            "The Morning Altar",
            "@TheMorningAltarDaily",
            "before you sleep",
            "bedtime prayer",
            "prayer before sleep",
            "night prayer",
            "begin every sunrise with us",
            "sunrise prayer",
            "The Midnight Watch",
            "@TheMidnightWatchDaily",
            "@TheMidnightWatch",
            "midnight watch",
            "The Family Altar",
            "@TheFamilyAltarDaily",
            "cover your home and family in daily prayer",
        ),
        authoring_directive=(
            "CHANNEL: The Midday Watch (prayer3) - the middle of the day, never bedtime and "
            "never sunrise.",
            "Frontmatter MUST include exactly: channel: prayer3",
            "Title MUST end with: | The Midday Watch",
            'Tags MUST include "midday prayer" and "the midday watch"; never sunrise, sleep, '
            'bedtime or night-prayer terms.',
            "Description MUST credit: Produced by The Midday Watch | Noonday Prayer & Scripture",
            'Scenes follow the noonday arc in the rubric and end with: "Type Amen to agree with '
            'this prayer, and subscribe to The Midday Watch to pause and pray with us at noon."',
            "Asset queries MUST be midday light, a quiet desk, an open window at noon or "
            "high-sun landscape scenes - never candlelight, starfields or dawn.",
        ),
        short_title_template="Say This {label} Prayer at Noon | {hook}",
        subscribe_heading="🙏 PAUSE AND PRAY AT NOON",
        short_target_window_utc="12:14",
        short_channel_label="a faceless noonday-prayer channel called The Midday Watch",
        short_prayer_kind="midday",
        short_opening="pause what you are doing",
        short_imagery="midday light through a window, a quiet desk, high sun on open ground",
        short_tags=(
            "midday prayer",
            "noon prayer",
            "afternoon prayer",
            "the midday watch",
            "scripture meditation",
        ),
        short_hashtags="#Shorts #{tag_key} #MiddayPrayer #NoonPrayer #DailyDevotion #TheMiddayWatch",
        short_end_card="The Midday Watch — pause and pray at noon",
        short_key_namespace="midday",
        comment_persona="the midday prayer team at The Midday Watch",
        comment_farewell="Walk through this afternoon steady in His peace.",
        shorts_poster_kicker="PAUSE AND PRAY AT NOON",
        longform_pinned_comment=_MIDDAY_WATCH_COMMENT,
        short_pinned_comment=(
            "☀️ PRAY THE FULL NOONDAY SCRIPTURE MEDITATION:\n"
            "Tap the linked full-length prayer right above this title (or visit {handle}) "
            "to pray the complete midday prayer of {scripture}:\n"
            "👉 {url}\n\n"
            "Write 'AMEN' in faith and leave your prayer request below — we are interceding "
            "over your afternoon right now. Whatever the rest of this day holds, you are not "
            "carrying it alone. 🙏☀️✨{footer}"
        ),
        longform_prayer_label="Midday Prayer",
        seo_hook_template=(
            "Pause at noonday with {display_name} in {scripture} (KJV) "
            "and receive quiet strength, clarity, and peace for the hours ahead."
        ),
        verified_commons_queries=(
            ("sunlight breaking through clouds mountain pass", 3, "3x Public domain — USFS Rocky Mountain National Forest crepuscular ray scans"),
            ("divine light breaking through clouds over peaceful landscape", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("forest sunlight mist", 3, "3x Public domain — USFS forest crepuscular ray and mist photography"),
            ("peaceful mountain river calm water forest", 4, "4x Public domain — NPS mountain stream and river dawn scans"),
            ("golden light rays through clouds over mountain peak", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("sun rays breaking clouds mountains", 3, "3x Public domain — NOAA National Weather Service crepuscular ray mountain photography"),
        ),
        feedback_artifact_name="performance_feedback_prayer3.json",
        anchor_video=None,
        series_playlists=(
            (
                "midday_prayers",
                "Midday Prayers to Pause & Reset Your Day — The Midday Watch",
                "Step away from the noise at noon with KJV scripture meditations and steady prayer "
                "for peace, focus, and protection through the afternoon.\n\n"
                "Produced by The Midday Watch | Noonday Prayer & Scripture.",
                ("midday", "noon", "noonday", "midday watch", "pause"),
            ),
            (
                "afternoon_strength",
                "Noonday Prayers for Work, Clarity & Renewed Strength — The Midday Watch",
                "Commit the work of your hands to the Lord and receive renewed afternoon strength from Proverbs, Isaiah, and the Psalms.\n\n"
                "Produced by The Midday Watch | Noonday Prayer & Scripture.",
                ("proverbs", "isaiah", "strength", "work", "commit", "midday prayer"),
            ),
            (
                "midday_psalms",
                "Psalms at Noon (KJV Devotional Series) — The Midday Watch",
                "Verse-by-verse midday Psalm prayers and classical KJV reflections for stillness and courage in the middle of the day.\n\n"
                "Produced by The Midday Watch | Noonday Prayer & Scripture.",
                ("psalm", "scripture", "devotion", "noon prayer", "midday"),
            ),
        ),
        community_posts=(
            {
                "post_id": "comm-prayer3-001-sunday-noon",
                "post_type": "POLL",
                "title": "Pause at Noon: What do you need God to steady this afternoon?",
                "body_text": (
                    "Evening, and morning, and at noon, will I pray, and cry aloud: and he shall hear my voice (Psalm 55:17).\n\n"
                    "Step away from the rush for sixty seconds at The Midday Watch and reset your heart in Christ's peace. "
                    "Vote below and write 'AMEN' to agree in midday prayer! ☀️🙏"
                ),
                "poll": {
                    "question": "Where do you need the Lord's steady hand most this afternoon?",
                    "options": [
                        "Quiet focus & clarity in the middle of work",
                        "Renewed physical & emotional strength",
                        "Peace over an anxious conversation or decision",
                        "Protection & grace over my family today",
                    ],
                    "context_scripture": "Psalm 55:17",
                },
                "image_rel_path": "comm-prayer3-001-sunday-noon.png",
                "target_utc": "12:00",
                "tags": ["#MiddayPrayer", "#TheMiddayWatch", "#Psalm55", "#NoonPrayer"],
            },
            {
                "post_id": "comm-prayer3-002-midweek-watch",
                "post_type": "PRAYER_WALL",
                "title": "The Midday Watch Noonday Prayer Wall: Leave Your Afternoon Requests",
                "body_text": (
                    "Commit thy works unto the Lord, and thy thoughts shall be established (Proverbs 16:3).\n\n"
                    "Halfway through the day, lay down what has felt heavy since morning. Drop your midday prayer "
                    "request below — our midday prayer team is interceding right now. Type 'AMEN' in faith!"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer3-002-midweek-watch.png",
                "target_utc": "12:00",
                "tags": ["#NoondayPrayerWall", "#Proverbs16", "#TheMiddayWatch"],
            },
            {
                "post_id": "comm-prayer3-003-thursday-shield",
                "post_type": "POLL",
                "title": "Which noonday scripture resets your spirit in a busy week?",
                "body_text": (
                    "Thou wilt keep him in perfect peace, whose mind is stayed on thee: because he trusteth in thee (Isaiah 26:3).\n\n"
                    "Let God's word anchor the rest of your afternoon."
                ),
                "poll": {
                    "question": "Which scripture are you carrying through this afternoon?",
                    "options": [
                        "Psalm 55:17 — At noon will I pray",
                        "Isaiah 26:3 — Kept in perfect peace",
                        "Psalm 91:6 — Shielded at noonday",
                        "Philippians 4:6-7 — Peace that guards the heart",
                    ],
                    "context_scripture": "Isaiah 26:3",
                },
                "image_rel_path": "comm-prayer3-003-thursday-shield.png",
                "target_utc": "12:00",
                "tags": ["#Isaiah26", "#MiddayScripture", "#TheMiddayWatch"],
            },
            {
                "post_id": "comm-prayer3-004-friday-strength",
                "post_type": "SCRIPTURE_DEVOTIONAL",
                "title": "Finish the Day Steady: The Lord Is At Your Right Hand",
                "body_text": (
                    "The Lord is thy keeper: the Lord is thy shade upon thy right hand (Psalm 121:5).\n\n"
                    "Even in the heat of the afternoon, you do not walk unshielded. "
                    "Type 'STEADY IN HIS PEACE' below to claim renewed strength for the hours ahead! ☀️🛡️"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer3-004-friday-strength.png",
                "target_utc": "12:00",
                "tags": ["#Psalm121", "#AfternoonStrength", "#TheMiddayWatch"],
            },
        ),
        short_bridge_theme="noonday strength, quiet wisdom, and steadfast peace",
        short_fallback_title="Noonday Prayers for Strength & Clarity — The Midday Watch",
        milestone_subheading_1250="A NOONDAY REFUGE ACROSS THE NATIONS",
        milestone_subheading_1500="UNBROKEN NOONDAY PRAYER WATCH",
        milestone_sanctuary_phrase="at high noon",
        milestone_cadence_phrase="at noon",
        milestone_closing_blessing="Carry His quiet strength into the hours ahead.",
        milestone_2000_closing="your daily noonday sanctuary of prayer",
        seo_fallback_hashtags=(
            "#MiddayPrayer", "#NoonPrayer", "#DailyDevotion", "#TheMiddayWatch",
        ),
        seo_hook_ref_template=(
            "Pause at noonday with this {ref} KJV midday prayer for renewed strength, "
            "quiet clarity, and God's peace over the hours ahead."
        ),
        seo_hook_generic=(
            "Pause at noon with this KJV midday scripture prayer for quiet strength, "
            "clear wisdom, and steadfast peace through the afternoon."
        ),
        seo_book_tag_suffixes=("midday prayer", "noon prayer"),
        seo_tag_seeds=(
            "midday prayer for strength",
            "noonday scripture prayer",
            "afternoon prayer break",
            "prayer at noon",
            "kjv midday devotion",
            "the midday watch prayer",
            "prayer for clarity and peace",
            "christian midday prayer",
        ),
        localized_title_es="Oración del Mediodía para Fortaleza y Paz | {channel_name}",
        localized_title_pt="Oração do Meio-Dia para Força e Paz | {channel_name}",
        localized_ref_title_es="{ref_es} Oración del Mediodía para Fortaleza y Paz | {channel_name}",
        localized_ref_title_pt="{ref_pt} Oração do Meio-Dia para Força e Paz | {channel_name}",
        localized_desc_lead_es="Oración del mediodía para recibir fortaleza renovada, claridad y la paz de Dios.",
        localized_desc_lead_pt="Oração do meio-dia para receber força renovada, clareza e a paz de Deus.",
        localized_invite_es=(
            "Haz una pausa al mediodía con esta oración bíblica para recibir fortaleza renovada, claridad y la paz de Dios."
        ),
        localized_invite_pt=(
            "Faça uma pausa ao meio-dia com esta oração bíblica para receber força renovada, clareza e a paz de Deus."
        ),
        default_comment_scripture_hook=(
            "Psalm 55:17 — 'Evening, and morning, and at noon, will I pray, and cry aloud: and He shall hear my voice.'"
        ),
        default_comment_theme="renewed midday strength, quiet wisdom, and steadfast peace",
        ctr_grade="noon",
        ctr_hook_hero="PRAY AT NOON",
        ctr_quiet_hero="STAND FIRM TODAY",
    ),
    "prayer4": Brand(
        channel_id="prayer4",
        display_name="The Midnight Watch",
        handle="@TheMidnightWatchDaily",
        declaration="prayer4",
        title_suffix="| The Midnight Watch",
        producer_line="Produced by The Midnight Watch | Midnight Prayer & Breakthrough Scripture",
        closing_cta=(
            "Type Amen to agree with this prayer, and subscribe to The Midnight Watch "
            "to stand on the watchtower in midnight prayer."
        ),
        required_phrases=("The Midnight Watch",),
        forbidden_phrases=(
            "The Secret Place",
            "@TheSecretPlace",
            "The Morning Altar",
            "@TheMorningAltarDaily",
            "The Midday Watch",
            "@TheMiddayWatch",
            "before you sleep",
            "bedtime prayer",
            "prayer before sleep",
            "begin every sunrise with us",
            "sunrise prayer",
            "pause and pray with us at noon",
            "noonday prayer",
            "The Family Altar",
            "@TheFamilyAltarDaily",
            "cover your home and family in daily prayer",
        ),
        authoring_directive=(
            "CHANNEL: The Midnight Watch (prayer4) - wakeful 12:00 AM midnight watch & "
            "breakthrough intercession (Psalm 119:62 / Acts 16:25), never bedtime/sleep, "
            "never sunrise, and never midday.",
            "Frontmatter MUST include exactly: channel: prayer4",
            "Title MUST end with: | The Midnight Watch",
            'Tags MUST include "midnight prayer" and "the midnight watch"; never sunrise, '
            'midday, noonday, bedtime or sleep terms.',
            "Description MUST credit: Produced by The Midnight Watch | Midnight Prayer & Breakthrough Scripture",
            'Scenes follow the midnight watchtower arc in the rubric and end with: "Type Amen to '
            'agree with this prayer, and subscribe to The Midnight Watch to stand on the '
            'watchtower in midnight prayer."',
            "Asset queries MUST be midnight watchtower, deep starlit sky, aurora, stone fortress "
            "silhouette or lamp-lit vigil scenes - never sunrise, dawn or high noon.",
        ),
        short_title_template="Pray This {label} Midnight Prayer | {hook}",
        subscribe_heading="🕯️ STAND ON THE MIDNIGHT WATCH",
        short_target_window_utc="23:14",
        short_channel_label="a faceless midnight-breakthrough prayer channel called The Midnight Watch",
        short_prayer_kind="midnight",
        short_opening="rise in spirit at this midnight hour",
        short_imagery="midnight watchtower silhouette, deep starry heavens, lamp-lit sanctuary vigil",
        short_tags=(
            "midnight prayer",
            "midnight watch",
            "breakthrough prayer",
            "the midnight watch",
            "deliverance prayer",
        ),
        short_hashtags="#Shorts #{tag_key} #MidnightPrayer #MidnightWatch #BreakthroughPrayer #TheMidnightWatch",
        short_end_card="The Midnight Watch — stand in prayer at midnight",
        short_key_namespace="midnight",
        comment_persona="the midnight intercessory team at The Midnight Watch",
        comment_farewell="Stand firm on the watchtower — God hears at midnight.",
        shorts_poster_kicker="RISE AND PRAY AT MIDNIGHT",
        longform_pinned_comment=_MIDNIGHT_WATCH_COMMENT,
        short_pinned_comment=(
            "🕯️ PRAY THE COMPLETE MIDNIGHT WATCH INTERCESSION:\n"
            "Tap the linked full-length prayer right above this title (or visit {handle}) "
            "to stand in the full midnight prayer of {scripture}:\n"
            "👉 {url}\n\n"
            "Write 'AMEN' in faith and leave your midnight prayer request below — we are "
            "standing on the watchtower over your household right now. Like Paul and Silas at "
            "midnight, praise goes before your breakthrough! 🙏🕯️🔥{footer}"
        ),
        longform_prayer_label="Midnight Prayer",
        seo_hook_template=(
            "Rise at midnight with {display_name} in {scripture} (KJV) "
            "for breakthrough intercession, spiritual deliverance, and unshakeable faith."
        ),
        verified_commons_queries=(
            ("starry night sky milky way mountains", 4, "4x Public domain — NPS / NASA dark sky reserve astrophotography"),
            ("aurora borealis night sky mountains", 4, "4x Public domain — NASA / NOAA / NPS northern lights night-watch photography"),
            ("ancient chapel interior candlelight peaceful sanctuary", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("star night sky over quiet countryside peaceful", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("peaceful night landscape moon over calm lake", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("calm mountain lake still water reflection nightfall", 4, "4x Public domain — NPS Mirror Lake and Crater Lake twilight scans"),
        ),
        feedback_artifact_name="performance_feedback_prayer4.json",
        anchor_video=None,
        series_playlists=(
            (
                "midnight_watch_prayers",
                "Midnight Watch Prayers for Breakthrough & Deliverance — The Midnight Watch",
                "Rise at the twelfth hour like David (Psalm 119:62) and Paul & Silas (Acts 16:25) "
                "with KJV midnight intercession for household deliverance and breakthrough.\n\n"
                "Produced by The Midnight Watch | Midnight Prayer & Breakthrough Scripture.",
                ("midnight", "watchtower", "breakthrough", "midnight watch", "deliverance"),
            ),
            (
                "midnight_psalms",
                "Midnight Psalms of Victory & Protection (KJV) — The Midnight Watch",
                "Verse-by-verse midnight Psalm prayers and Spurgeon & Matthew Henry reflections "
                "for standing firm in the darkest watch.\n\n"
                "Produced by The Midnight Watch | Midnight Prayer & Breakthrough Scripture.",
                ("psalm", "fortress", "refuge", "victory", "midnight prayer"),
            ),
            (
                "watchman_intercession",
                "Standing on the Watchtower: Family & Destiny Intercession — The Midnight Watch",
                "Fervid KJV scripture prayers covering your home, children, calling, and coming season at the midnight gate.\n\n"
                "Produced by The Midnight Watch | Midnight Prayer & Breakthrough Scripture.",
                ("isaiah", "acts", "family", "household", "watchman", "intercession"),
            ),
        ),
        community_posts=(
            {
                "post_id": "comm-prayer4-001-sunday-midnight",
                "post_type": "POLL",
                "title": "The Midnight Gate: What are you standing in faith for at midnight?",
                "body_text": (
                    "At midnight I will rise to give thanks unto thee because of thy righteous judgments (Psalm 119:62).\n\n"
                    "Join watchmen around the world at The Midnight Watch as a new week opens. "
                    "Vote below and type 'AMEN' to seal your midnight petition! 🕯️🙏"
                ),
                "poll": {
                    "question": "Where are you believing God for midnight breakthrough right now?",
                    "options": [
                        "Breakthrough & open doors in a long-standing trial",
                        "Spiritual covering & deliverance over my household",
                        "Peace, clarity & strength in the darkest hour",
                        "Restoration of health, purpose & family unity",
                    ],
                    "context_scripture": "Psalm 119:62",
                },
                "image_rel_path": "comm-prayer4-001-sunday-midnight.png",
                "target_utc": "23:00",
                "tags": ["#MidnightPrayer", "#TheMidnightWatch", "#Psalm119", "#MidnightWatch"],
            },
            {
                "post_id": "comm-prayer4-002-midweek-watchtower",
                "post_type": "PRAYER_WALL",
                "title": "The Midnight Watchtower Prayer Wall: Leave Your Midnight Petitions",
                "body_text": (
                    "And at midnight Paul and Silas prayed, and sang praises unto God: and the prisoners heard them (Acts 16:25).\n\n"
                    "No chain outlasts midnight praise. Leave your prayer request below — our intercessory team is standing on the watchtower "
                    "with you tonight. Write 'AMEN' in faith!"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer4-002-midweek-watchtower.png",
                "target_utc": "23:00",
                "tags": ["#MidnightWatchtower", "#Acts16", "#TheMidnightWatch"],
            },
            {
                "post_id": "comm-prayer4-003-thursday-fortress",
                "post_type": "POLL",
                "title": "Which midnight scripture anchors your faith on the watchtower?",
                "body_text": (
                    "I have set watchmen upon thy walls, O Jerusalem, which shall never hold their peace day nor night (Isaiah 62:6).\n\n"
                    "Stand upon God's unfailing Word at the twelfth hour."
                ),
                "poll": {
                    "question": "Which midnight scripture are you declaring right now?",
                    "options": [
                        "Psalm 119:62 — At midnight I will rise to give thanks",
                        "Acts 16:25-26 — Midnight praise that looses bands",
                        "Isaiah 62:6 — Watchmen upon the walls",
                        "Zechariah 2:5 — A wall of fire round about",
                    ],
                    "context_scripture": "Isaiah 62:6",
                },
                "image_rel_path": "comm-prayer4-003-thursday-fortress.png",
                "target_utc": "23:00",
                "tags": ["#Isaiah62", "#MidnightScripture", "#TheMidnightWatch"],
            },
            {
                "post_id": "comm-prayer4-004-friday-victory",
                "post_type": "SCRIPTURE_DEVOTIONAL",
                "title": "Midnight Praise Goes Before Your Breakthrough",
                "body_text": (
                    "For the weapons of our warfare are not carnal, but mighty through God to the pulling down of strong holds (2 Corinthians 10:4).\n\n"
                    "Stand steady on the watchtower tonight. Type 'GOD HEARS AT MIDNIGHT' below in faith! 🕯️🔥"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer4-004-friday-victory.png",
                "target_utc": "23:00",
                "tags": ["#BreakthroughPrayer", "#MidnightPraise", "#TheMidnightWatch"],
            },
        ),
        short_bridge_theme="midnight breakthrough, household covering, and unshakeable faith",
        short_fallback_title="Midnight Watch Prayers for Breakthrough & Deliverance — The Midnight Watch",
        milestone_subheading_1250="A MIDNIGHT WATCHTOWER ACROSS THE NATIONS",
        milestone_subheading_1500="UNBROKEN MIDNIGHT INTERCESSION WATCH",
        milestone_sanctuary_phrase="at the midnight hour",
        milestone_cadence_phrase="every midnight",
        milestone_closing_blessing="Stand firm on the watchtower — God hears at midnight.",
        milestone_2000_closing="your midnight watchtower of prayer and breakthrough",
        seo_fallback_hashtags=(
            "#MidnightPrayer", "#MidnightWatch", "#BreakthroughPrayer", "#TheMidnightWatch",
        ),
        seo_hook_ref_template=(
            "Rise at midnight with this {ref} KJV midnight prayer for spiritual breakthrough, "
            "household deliverance, and steadfast faith on the watchtower."
        ),
        seo_hook_generic=(
            "Rise at the midnight hour with this KJV midnight watch prayer for breakthrough, "
            "deliverance, and God's covering over your household."
        ),
        seo_book_tag_suffixes=("midnight prayer", "midnight watch prayer"),
        seo_tag_seeds=(
            "midnight prayer for breakthrough",
            "midnight watch prayer",
            "12am midnight prayer kjv",
            "paul and silas midnight prayer",
            "kjv midnight intercession",
            "the midnight watch prayer",
            "midnight deliverance prayer",
            "christian midnight prayer",
        ),
        localized_title_es="Oración de Medianoche por Victoria y Liberación | {channel_name}",
        localized_title_pt="Oração da Meia-Noite por Vitória e Libertação | {channel_name}",
        localized_ref_title_es="{ref_es} Oración de Medianoche por Victoria y Liberación | {channel_name}",
        localized_ref_title_pt="{ref_pt} Oração da Meia-Noite por Vitória e Libertação | {channel_name}",
        localized_desc_lead_es="Oración de medianoche para intercesión, liberación espiritual y victoria en Cristo.",
        localized_desc_lead_pt="Oração da meia-noite para intercessão, libertação espiritual e vitória em Cristo.",
        localized_invite_es=(
            "Levántate a la medianoche con esta oración bíblica para clamar por liberación, fortaleza y victoria en Dios."
        ),
        localized_invite_pt=(
            "Levante-se à meia-noite com esta oração bíblica para clamar por libertação, força e vitória em Deus."
        ),
        default_comment_scripture_hook=(
            "Psalm 119:62 — 'At midnight I will rise to give thanks unto thee because of thy righteous judgments.'"
        ),
        default_comment_theme="midnight breakthrough, household deliverance, and unshakeable faith",
        ctr_grade="midnight",
        ctr_hook_hero="PRAY AT MIDNIGHT",
        ctr_quiet_hero="CHAINS MUST BREAK",
    ),
    "prayer5": Brand(
        channel_id="prayer5",
        display_name="The Family Altar",
        handle="@TheFamilyAltarDaily",
        declaration="prayer5",
        title_suffix="| The Family Altar",
        producer_line="Produced by The Family Altar | Daily Household & Family Prayer",
        closing_cta=(
            "Type Amen to agree with this prayer, and subscribe to The Family Altar "
            "to cover your home and family in daily prayer."
        ),
        required_phrases=("The Family Altar",),
        forbidden_phrases=(
            "The Secret Place",
            "@TheSecretPlace",
            "The Morning Altar",
            "@TheMorningAltarDaily",
            "The Midday Watch",
            "@TheMiddayWatch",
            "The Midnight Watch",
            "@TheMidnightWatchDaily",
            "before you sleep",
            "bedtime prayer",
            "prayer before sleep",
            "begin every sunrise with us",
            "pause and pray with us at noon",
            "stand on the watchtower in midnight prayer",
        ),
        authoring_directive=(
            "CHANNEL: The Family Altar (prayer5) - daily Christian household, marriage, "
            "children & covenant home prayer (Joshua 24:15 / Psalm 128:3), never sleep/bedtime, "
            "never sunrise-altar, never midday-watch, and never midnight-watch branding.",
            "Frontmatter MUST include exactly: channel: prayer5",
            "Title MUST end with: | The Family Altar",
            'Tags MUST include "family prayer" and "the family altar"; never sleep, bedtime, '
            'morning altar, midday watch, or midnight watch branding.',
            "Description MUST credit: Produced by The Family Altar | Daily Household & Family Prayer",
            'Scenes follow the covenant household arc in the rubric and end with: "Type Amen to '
            'agree with this prayer, and subscribe to The Family Altar to cover your home and '
            'family in daily prayer."',
            "Asset queries MUST be warm candlelit sanctuary, olive groves, peaceful homestead, "
            "quiet valley or calm countryside scenes.",
        ),
        short_title_template="Pray This {label} Family Prayer Over Your Home | {hook}",
        subscribe_heading="🏡 COVER YOUR HOME IN DAILY PRAYER",
        short_target_window_utc="17:14",
        short_channel_label="a faceless Christian family-and-household prayer channel called The Family Altar",
        short_prayer_kind="household",
        short_opening="gather your home and loved ones in faith",
        short_imagery="warm lamp-lit table with Bible, olive branches, peaceful countryside home",
        short_tags=(
            "family prayer",
            "prayer for my home",
            "prayer for children",
            "the family altar",
            "household blessing",
        ),
        short_hashtags="#Shorts #{tag_key} #FamilyPrayer #PrayerForMyHome #TheFamilyAltar #HouseholdBlessing",
        short_end_card="The Family Altar — cover your home in prayer",
        short_key_namespace="family",
        comment_persona="the pastoral family prayer team at The Family Altar",
        comment_farewell="May the peace of God dwell richly within your home.",
        shorts_poster_kicker="BLESS THIS HOME IN PRAYER",
        longform_pinned_comment=_FAMILY_ALTAR_COMMENT,
        short_pinned_comment=(
            "🏡 PRAY THE FULL HOUSEHOLD SCRIPTURE COVERING:\n"
            "Tap the linked full-length prayer right above this title (or visit {handle}) "
            "to pray the complete family blessing of {scripture} over your home:\n"
            "👉 {url}\n\n"
            "Write 'AMEN' in faith and share the family members you are lifting up below — "
            "as for me and my house, we will serve the LORD! 🙏🌿✨{footer}"
        ),
        longform_prayer_label="Family Prayer",
        seo_hook_template=(
            "Gather at {display_name} in {scripture} (KJV) "
            "to cover your home, marriage, children, and provision in daily prayer."
        ),
        verified_commons_queries=(
            ("ancient chapel interior candlelight peaceful sanctuary", 4, "4x Public domain — verified Wikimedia Commons / USGS / NPS / NASA imagery"),
            ("olive trees grove countryside landscape peaceful", 4, "4x Public domain — verified Wikimedia Commons / USDA / LoC agricultural & landscape scans"),
            ("golden meadow valley peaceful pastoral landscape", 4, "4x Public domain — NPS / USFS pastoral valley photography"),
            ("calm mountain lake still water reflection peaceful", 4, "4x Public domain — NPS Mirror Lake and Crater Lake scans"),
            ("sunbeams forest trees golden light peaceful", 4, "4x Public domain — USFS / NPS woodland light photography"),
            ("historic stone cottage homestead peaceful countryside", 4, "4x Public domain — NPS / Library of Congress historic homestead photography"),
        ),
        feedback_artifact_name="performance_feedback_prayer5.json",
        anchor_video=None,
        series_playlists=(
            (
                "household_blessing_prayers",
                "Prayers for Home, Peace & Household Protection (KJV) — The Family Altar",
                "Daily KJV scripture prayers anchored in Joshua 24:15 and Isaiah 32:18 to cover "
                "every room, threshold, and loved one under your roof in God's peace.\n\n"
                "Produced by The Family Altar | Daily Household & Family Prayer.",
                ("home", "house", "household", "peaceable habitation", "family prayer"),
            ),
            (
                "prayers_for_children_and_marriage",
                "Prayers Over Children, Marriage & Generations (KJV) — The Family Altar",
                "Verse-by-verse KJV family prayers from Psalm 128, Isaiah 54:13, and Proverbs "
                "covering your spouse, sons, daughters, and future generations.\n\n"
                "Produced by The Family Altar | Daily Household & Family Prayer.",
                ("children", "marriage", "spouse", "psalm 128", "generations"),
            ),
            (
                "family_provision_and_wisdom",
                "Prayers for Godly Provision, Wisdom & Stewardship — The Family Altar",
                "Reverent KJV scripture prayers with Charles Spurgeon & Matthew Henry reflections "
                "for daily bread, honest labour, and divine wisdom in the home.\n\n"
                "Produced by The Family Altar | Daily Household & Family Prayer.",
                ("provision", "wisdom", "philippians 4", "proverbs", "blessing"),
            ),
        ),
        community_posts=(
            {
                "post_id": "comm-prayer5-001-sunday-home",
                "post_type": "POLL",
                "title": "Sunday Family Altar: What are you praying over your household this week?",
                "body_text": (
                    "But as for me and my house, we will serve the LORD (Joshua 24:15).\n\n"
                    "As a new week opens over your roof, where are you asking the Lord to pour out His grace first? "
                    "Vote below and type 'AMEN' to cover your family in prayer! 🌿🙏"
                ),
                "poll": {
                    "question": "What are you lifting up on the Family Altar first this week?",
                    "options": [
                        "Peace & unity across every room of our home",
                        "Protection & wisdom over our children",
                        "Strength & tenderness in marriage & family",
                        "God's faithful provision & guidance ahead",
                    ],
                    "context_scripture": "Joshua 24:15",
                },
                "image_rel_path": "comm-prayer5-001-sunday-home.png",
                "target_utc": "17:00",
                "tags": ["#FamilyPrayer", "#TheFamilyAltar", "#Joshua2415", "#HouseholdBlessing"],
            },
            {
                "post_id": "comm-prayer5-002-midweek-children",
                "post_type": "PRAYER_WALL",
                "title": "The Family Altar Prayer Wall: Covering Our Children & Loved Ones",
                "body_text": (
                    "And all thy children shall be taught of the LORD; and great shall be the peace of thy children (Isaiah 54:13).\n\n"
                    "Leave the first name or relationship (son, daughter, spouse, parent) you are standing in faith for today — "
                    "our prayer team is lifting every family before the throne of grace. Write 'AMEN' in faith!"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer5-002-midweek-children.png",
                "target_utc": "17:00",
                "tags": ["#PrayerForChildren", "#Isaiah5413", "#TheFamilyAltar"],
            },
            {
                "post_id": "comm-prayer5-003-thursday-scripture",
                "post_type": "POLL",
                "title": "Which household scripture anchors your home today?",
                "body_text": (
                    "Except the LORD build the house, they labour in vain that build it (Psalm 127:1).\n\n"
                    "Stand upon God's unchanging promises over every room of your home."
                ),
                "poll": {
                    "question": "Which KJV household promise are you standing on right now?",
                    "options": [
                        "Joshua 24:15 — As for me and my house, we will serve the LORD",
                        "Psalm 128:3 — Olive plants round about thy table",
                        "Isaiah 32:18 — Dwell in a peaceable habitation",
                        "Numbers 6:24-26 — The LORD bless thee, and keep thee",
                    ],
                    "context_scripture": "Psalm 127:1",
                },
                "image_rel_path": "comm-prayer5-003-thursday-scripture.png",
                "target_utc": "17:00",
                "tags": ["#Psalm127", "#Psalm128", "#TheFamilyAltar"],
            },
            {
                "post_id": "comm-prayer5-004-friday-blessing",
                "post_type": "SCRIPTURE_DEVOTIONAL",
                "title": "Weekend Aaronic Blessing Over Every Household",
                "body_text": (
                    "The LORD bless thee, and keep thee: The LORD make his face shine upon thee, and be gracious unto thee (Numbers 6:24-25).\n\n"
                    "May the peace of Christ rest upon your table, your family, and your home all weekend long. Type 'BLESS THIS HOME' below in faith! 🏡🙏"
                ),
                "poll": None,
                "image_rel_path": "comm-prayer5-004-friday-blessing.png",
                "target_utc": "17:00",
                "tags": ["#Numbers6", "#HouseholdBlessing", "#TheFamilyAltar"],
            },
        ),
        short_bridge_theme="household peace, family covering, and God's faithful provision",
        short_fallback_title="Prayers for Home, Peace & Household Protection (KJV) — The Family Altar",
        milestone_subheading_1250="A COVENANT FAMILY ALTAR ACROSS THE NATIONS",
        milestone_subheading_1500="DAILY PRAYER OVER EVERY HOME & GENERATION",
        milestone_sanctuary_phrase="around the family altar",
        milestone_cadence_phrase="every day over your home",
        milestone_closing_blessing="May the peace of God dwell richly within your home.",
        milestone_2000_closing="your daily sanctuary of household and family prayer",
        seo_fallback_hashtags=(
            "#FamilyPrayer", "#PrayerForMyHome", "#HouseholdBlessing", "#TheFamilyAltar",
        ),
        seo_hook_ref_template=(
            "Gather around the Family Altar with this {ref} KJV family prayer for household peace, "
            "protection over your children, marriage unity, and God's faithful provision."
        ),
        seo_hook_generic=(
            "Gather around the Family Altar with this KJV household prayer for family peace, "
            "children's covering, marriage strength, and godly provision."
        ),
        seo_book_tag_suffixes=("family prayer", "prayer for my home"),
        seo_tag_seeds=(
            "prayer for my family and home",
            "family prayer kjv",
            "prayer for children protection",
            "joshua 24 15 family prayer",
            "household blessing prayer",
            "the family altar prayer",
            "christian marriage and family prayer",
            "psalm 128 family blessing",
        ),
        localized_title_es="Oración por la Familia, los Hijos y el Hogar | {channel_name}",
        localized_title_pt="Oração pela Família, Filhos e Lar | {channel_name}",
        localized_ref_title_es="{ref_es} Oración por la Familia y el Hogar | {channel_name}",
        localized_ref_title_pt="{ref_pt} Oração pela Família e pelo Lar | {channel_name}",
        localized_desc_lead_es="Oración bíblica diaria por la paz del hogar, los hijos, el matrimonio y la provisión de Dios.",
        localized_desc_lead_pt="Oração bíblica diária pela paz do lar, pelos filhos, pelo casamento e pela provisão de Deus.",
        localized_invite_es=(
            "Reúne tu hogar en oración con esta meditación bíblica para cubrir a tu familia, hijos y casa bajo la paz de Dios."
        ),
        localized_invite_pt=(
            "Reúna seu lar em oração com esta meditação bíblica para cobrir sua família, filhos e casa sob a paz de Deus."
        ),
        default_comment_scripture_hook=(
            "Joshua 24:15 — 'But as for me and my house, we will serve the LORD.'"
        ),
        default_comment_theme="household peace, family covering, and God's faithful provision",
        ctr_grade="hearth",
        ctr_hook_hero="BLESS THIS HOME",
        ctr_quiet_hero="COVER MY FAMILY",
    ),
}

_CAPABILITIES: dict[str, ChannelCapabilities] = {
    "secret-place": ChannelCapabilities(
        channel_id="secret-place",
        brand=_BRANDS["secret-place"],
        equipment={
            "system_instruction": "system_instruction.md",
            "theological_rubric": "theological_rubric.md",
        },
        roadmap="secret-place",
        roadmap_name="SCRIPTURE_ROADMAP",
        legacy_queue_alias="longform",
        supply_min_publishable=6,
    ),
    "prayer2": ChannelCapabilities(
        channel_id="prayer2",
        brand=_BRANDS["prayer2"],
        equipment={
            "system_instruction": "morning_system_instruction.md",
            "theological_rubric": "morning_theological_rubric.md",
        },
        roadmap="prayer2",
        roadmap_name="MORNING_ALTAR_ROADMAP",
        legacy_queue_alias="",
        supply_min_publishable=6,
    ),
    "prayer3": ChannelCapabilities(
        channel_id="prayer3",
        brand=_BRANDS["prayer3"],
        equipment={
            "system_instruction": "midday_system_instruction.md",
            "theological_rubric": "midday_theological_rubric.md",
        },
        roadmap="prayer3",
        roadmap_name="MIDDAY_WATCH_ROADMAP",
        legacy_queue_alias="",
        supply_min_publishable=6,
    ),
    "prayer4": ChannelCapabilities(
        channel_id="prayer4",
        brand=_BRANDS["prayer4"],
        equipment={
            "system_instruction": "midnight_system_instruction.md",
            "theological_rubric": "midnight_theological_rubric.md",
        },
        roadmap="prayer4",
        roadmap_name="MIDNIGHT_WATCH_ROADMAP",
        legacy_queue_alias="",
        supply_min_publishable=6,
    ),
    "prayer5": ChannelCapabilities(
        channel_id="prayer5",
        brand=_BRANDS["prayer5"],
        equipment={
            "system_instruction": "family_system_instruction.md",
            "theological_rubric": "family_theological_rubric.md",
        },
        roadmap="prayer5",
        roadmap_name="FAMILY_ALTAR_ROADMAP",
        legacy_queue_alias="",
        supply_min_publishable=6,
    ),
}


def capabilities_for(channel_id: str | None = None) -> ChannelCapabilities:
    """Capabilities for a channel, failing closed on anything unregistered."""
    cid = normalize_channel_id(channel_id)
    try:
        return _CAPABILITIES[cid]
    except KeyError:
        known = ", ".join(sorted(_CAPABILITIES))
        raise ValueError(
            f"No capability block for channel {cid!r}; every channel in "
            f"pipeline.channels.CHANNELS needs one here. Known: {known}"
        ) from None


def brand_for(channel_id: str | None = None) -> Brand:
    return capabilities_for(channel_id).brand


def known_channels() -> tuple[str, ...]:
    """Registered channels, in production order (channel 1 first).

    Fails closed: a channel added to ``pipeline.channels.CHANNELS`` without a
    capability block here is an error, not a channel that quietly gets less.
    """
    from pipeline.channels import CHANNELS

    missing = [cid for cid in CHANNELS if cid not in _CAPABILITIES]
    if missing:
        raise ValueError(
            "channels registered without capabilities: " + ", ".join(missing)
            + " — add them to pipeline/channel_capabilities.py"
        )
    return tuple(CHANNELS)


def equipment_path(channel_id: str | None = None, module: str = "system_instruction") -> Path:
    caps = capabilities_for(channel_id)
    try:
        return EQUIPMENT_DIR / caps.equipment[module]
    except KeyError:
        raise ValueError(
            f"channel {caps.channel_id!r} declares no {module!r} equipment; "
            f"declared: {', '.join(sorted(caps.equipment))}"
        ) from None


def equipment_text(channel_id: str | None = None, module: str = "system_instruction") -> str:
    path = equipment_path(channel_id, module)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else ""


def subscribe_heading_for(channel_id: str | None = None) -> str:
    return brand_for(channel_id).subscribe_heading


def short_key(channel_id: str | None, base_key: str) -> str:
    """Namespace a Short key so two channels can never share one edition.

    Channel 1 keeps its historic keys untouched (``short-psalm91v5``); every other
    channel prefixes its namespace (``short-morningpsalm143v8``) so the shared
    renderer/spec directory stays collision-free and a Short can never be dressed
    in the other channel's branding.
    """
    namespace = brand_for(channel_id).short_key_namespace
    if not namespace:
        return base_key
    stem = base_key.removeprefix("short-")
    return f"short-{namespace}{stem}"


def channel_for_short_key(key_or_title: str) -> str | None:
    """Infer the owning channel from a namespaced Short key or slug."""
    s = (key_or_title or "").strip().lower()
    if not s:
        return None
    for cid, brand in _BRANDS.items():
        ns = brand.short_key_namespace
        if ns and (s.startswith(f"short-{ns}") or f"-{ns}-" in s or f"short_{ns}" in s):
            return cid
    return None


def channel_for_display_name(channel_name: str | None) -> str | None:
    """Resolve a channel id from its display name or @handle."""
    raw = (channel_name or "").strip().lower()
    if not raw:
        return None
    for cid, brand in _BRANDS.items():
        if raw in {brand.display_name.lower(), brand.handle.lower(), cid}:
            return cid
    return None


def pinned_comment_for(channel_id: str | None, theme: str, scripture_hook: str,
                       footer: str = "") -> str:
    """The channel's long-form pinned comment, in that channel's voice."""
    return brand_for(channel_id).longform_pinned_comment.format(
        theme=theme, scripture_hook=scripture_hook, footer=footer)


def short_pinned_comment_for(channel_id: str | None, url: str, scripture: str,
                             theme: str, footer: str = "") -> str:
    """The channel's Short → long-form bridge comment."""
    brand = brand_for(channel_id)
    return brand.short_pinned_comment.format(
        url=url, scripture=scripture, theme=theme, handle=brand.handle, footer=footer)
