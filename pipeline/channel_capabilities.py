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
    "📖 Psalm 5:3 — 'My voice shalt thou hear in the morning, O Lord; in the morning will I "
    "direct my prayer unto thee, and will look up.'\n\n"
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
