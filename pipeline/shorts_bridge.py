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
        "fallback_video_id": "6M6oV8MxD9s",
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
        "fallback_video_id": "1g8TXHD0Xks",
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

DEFAULT_PLAYLIST_FALLBACK = "https://www.youtube.com/@SecretPlaceSanctuary/playlists"

#: The length fields a long-form's own receipt records, in the order that tells
#: the truth about the finished video: `duration_seconds` is what the render
#: actually produced (a night-tail prayer is 3 hours, not 6 minutes), and
#: `target_minutes` is what the script was authored to.
_LENGTH_FIELDS = re.compile(
    r"^duration_seconds:\s*([0-9.]+)\s*$|^target_minutes:\s*([0-9]+)\s*$", re.M)


def minutes_on_record(path: Path) -> int | None:
    """How long the video in this receipt is, in whole minutes, if it says.

    Every Short's description used to open "PRAY THE COMPLETE 8-MINUTE <PASSAGE>
    MEDITATION" — a fixed sentence, on all ten channels, pointing at videos that
    are authored to six minutes and at three on The Secret Place that run three
    hours (`pipeline/night_tail.py`). The number was true once, when long-forms
    were nine minutes long, and no record was ever read to check it.

    Read, not assumed: the video's own receipt decides. ``None`` when the
    receipt records neither length, so a caller says what it does know instead
    of inventing a number.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    seconds = minutes = None
    for match in _LENGTH_FIELDS.finditer(head.split("\n---", 1)[0]):
        if match.group(1):
            try:
                seconds = float(match.group(1))
            except ValueError:
                seconds = None
        elif match.group(2):
            try:
                minutes = int(match.group(2))
            except ValueError:
                minutes = None
    if seconds and seconds >= 60:
        return int(round(seconds / 60))
    return minutes or seconds or None


def length_phrase(minutes: int | None) -> str:
    """``6`` -> ``"6-MINUTE "``, ``180`` -> ``"3-HOUR "``, unknown -> ``""``.

    A trailing space, so the phrase can be dropped straight into the sentence.
    Whole hours are said in hours: "PRAY THE COMPLETE 3-HOUR PSALM 91 ..." is
    what a night-tail video is, and "180-MINUTE" is not how anyone says it.
    """
    if not minutes:
        return ""
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes // 60}-HOUR "
    if minutes >= 120:
        return f"{round(minutes / 60)}-HOUR "
    return f"{int(minutes)}-MINUTE "


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


def playlist_fallback_for_channel(channel_id: str | None = None) -> str:
    """Official playlists tab URL for `channel_id` (never leaks another channel's handle)."""
    from .channels import get_channel

    handle = get_channel(channel_id).handle
    return f"https://www.youtube.com/{handle}/playlists"


_SHORT_SLUG_SUFFIX_RE = re.compile(
    r"-(?:sunrise|morning|midday|noonday|afternoon|night|pre-sleep|bedtime)-prayer$"
)


def _normalize_short_lookup_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s.startswith("short-"):
        s = _SHORT_SLUG_SUFFIX_RE.sub("", s)
    return s


def _dynamic_counterpart_from_repo(
    short_key_or_title: str,
    channel_id: str | None = None,
) -> dict[str, Any] | None:
    """Resolve any brain-authored Short key against published or queued long-form docs."""
    needle = (short_key_or_title or "").strip().lower()
    if not needle:
        return None
    needle_key = _normalize_short_lookup_key(needle)
    try:
        from .channel_capabilities import brand_for, channel_for_short_key
        from .channels import normalize_channel_id
        from .gemini_brain import extract_scripture_reference, short_key_for_doc
        from .script_doc import parse_script
    except Exception:  # noqa: BLE001
        return None

    inferred_cid = (
        normalize_channel_id(channel_id)
        if channel_id
        else channel_for_short_key(short_key_or_title)
    )

    pub_docs = []
    for p in sorted(PUBLISHED_DIR.glob("*.md")):
        if p.name.startswith("short-"):
            continue
        try:
            doc = parse_script(p)
        except Exception:  # noqa: BLE001
            continue
        if inferred_cid and doc.channel != inferred_cid:
            continue
        if str(doc.meta.get("youtube_status", "")).strip() == "deleted_or_missing":
            continue
        vid = str(doc.meta.get("youtube_video_id", "")).strip()
        if not vid:
            continue
        pub_docs.append((doc, vid, extract_scripture_reference(doc)))

    # Pass 1: exact Short-key match on published long-form receipts
    for doc, vid, ref in pub_docs:
        if short_key_for_doc(doc) in {needle, needle_key}:
            return {
                "found": True,
                "channel": doc.channel,
                "video_id": vid,
                "url": f"https://youtu.be/{vid}",
                "title": doc.title,
                "scripture": ref,
                "theme": brand_for(doc.channel).short_bridge_theme,
                "is_live_video": True,
                # What this video actually runs for, from its own receipt.
                "minutes": minutes_on_record(doc.path),
            }

    # Pass 2: scripture-title substring match on published long-form receipts
    for doc, vid, ref in pub_docs:
        if ref and ref.lower() in needle:
            return {
                "found": True,
                "channel": doc.channel,
                "video_id": vid,
                "url": f"https://youtu.be/{vid}",
                "title": doc.title,
                "scripture": ref,
                "theme": brand_for(doc.channel).short_bridge_theme,
                "is_live_video": True,
                # What this video actually runs for, from its own receipt.
                "minutes": minutes_on_record(doc.path),
            }

    queue_docs = []
    for p in sorted(QUEUE_DIR.glob("*.md")):
        try:
            doc = parse_script(p)
        except Exception:  # noqa: BLE001
            continue
        if inferred_cid and doc.channel != inferred_cid:
            continue
        queue_docs.append((doc, extract_scripture_reference(doc)))

    for exact_only in (True, False):
        for doc, ref in queue_docs:
            matched = (
                short_key_for_doc(doc) in {needle, needle_key}
                if exact_only
                else bool(ref and ref.lower() in needle)
            )
            if matched:
                return {
                    "found": True,
                    "channel": doc.channel,
                    "video_id": None,
                    "url": playlist_fallback_for_channel(doc.channel),
                    "title": doc.title,
                    "scripture": ref,
                    "theme": brand_for(doc.channel).short_bridge_theme,
                    "is_live_video": False,
                    # Not uploaded yet: the length is the length it is authored to.
                    "minutes": minutes_on_record(doc.path),
                }
    return None


def resolve_longform_counterpart(
    short_key_or_title: str,
    channel_id: str | None = None,
) -> dict[str, Any]:
    """Find the live or scheduled long-form video matching a Short."""
    from .channel_capabilities import brand_for, channel_for_short_key
    from .channels import DEFAULT_CHANNEL_ID, normalize_channel_id

    inferred_cid = (
        normalize_channel_id(channel_id)
        if channel_id
        else channel_for_short_key(short_key_or_title)
    )

    dyn = _dynamic_counterpart_from_repo(short_key_or_title, channel_id=inferred_cid)
    if dyn is not None:
        return dyn

    eff_cid = inferred_cid or DEFAULT_CHANNEL_ID
    brand = brand_for(eff_cid)
    fallback_url = playlist_fallback_for_channel(eff_cid)

    # SHORT_LONGFORM_CATALOG holds only the primary channel's historic Psalm masters;
    # non-default channels never inherit another channel's video IDs or handles.
    if eff_cid != DEFAULT_CHANNEL_ID:
        return {
            "found": False,
            "channel": eff_cid,
            "url": fallback_url,
            "title": brand.short_fallback_title,
            "theme": brand.short_bridge_theme,
            "is_live_video": False,
            "minutes": None,
        }

    short_key = resolve_short_key(short_key_or_title)
    if not short_key or short_key not in SHORT_LONGFORM_CATALOG:
        return {
            "found": False,
            "channel": eff_cid,
            "url": fallback_url,
            "title": brand.short_fallback_title,
            "theme": brand.short_bridge_theme,
            "is_live_video": False,
            "minutes": None,
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
            if "deleted_or_missing" in text:
                continue
            m = re.search(r"youtube_video_id:\s*[\"']?([A-Za-z0-9_-]{11})[\"']?", text)
            if m:
                vid = m.group(1)
                return {
                    "found": True,
                    "channel": eff_cid,
                    "video_id": vid,
                    "url": f"https://youtu.be/{vid}",
                    "title": info["title"],
                    "scripture": info["scripture"],
                    "theme": info["theme"],
                    "is_live_video": True,
                    "minutes": minutes_on_record(cand),
                }

    # 2. Check fallback video ID (e.g. 7RDX0fbIOtQ for Psalm 91)
    if fallback_vid:
        return {
            "found": True,
            "channel": eff_cid,
            "video_id": fallback_vid,
            "url": f"https://youtu.be/{fallback_vid}",
            "title": info["title"],
            "scripture": info["scripture"],
            "theme": info["theme"],
            "is_live_video": True,
            # The catalog names the video; only a receipt knows its length.
            "minutes": None,
        }

    # 3. Fallback to Series Playlist
    return {
        "found": True,
        "channel": eff_cid,
        "video_id": None,
        "url": fallback_url,
        "title": info["title"],
        "scripture": info["scripture"],
        "theme": info["theme"],
        "is_live_video": False,
        "minutes": None,
    }


def generate_short_bridge_comment(short_key_or_title: str,
                                  channel_id: str | None = None) -> str:
    """Bridge a Short's viewers to the full prayer, in that channel's voice.

    The comment used to be hardcoded to The Secret Place's handle and night
    language, which would have mislabelled every Morning Altar Short. Branding now
    comes from the channel's capability block, and the store/journal footer only
    appears on channels that actually own that funnel.
    """
    from .channel_capabilities import short_pinned_comment_for
    from .channels import normalize_channel_id

    counterpart = resolve_longform_counterpart(short_key_or_title, channel_id=channel_id)
    url = counterpart["url"]
    scripture = counterpart.get("scripture") or "this Scripture"
    owner = normalize_channel_id(channel_id or counterpart.get("channel"))
    theme = counterpart.get("theme") or "divine peace and protection"

    return short_pinned_comment_for(owner, url=url, scripture=scripture,
                                    theme=theme, footer="").strip()


def enrich_short_description_with_bridge(description: str, short_key_or_title: str,
                                        channel_id: str | None = None) -> str:
    """Put the full-prayer link (and, where it exists, the store) in a Short's description.

    Faith Shorts earn their long-form watch time through this link, so every channel
    gets the header. The Selar/journal block belongs to the channel that owns that
    funnel and is therefore capability-driven, not hardcoded.
    """
    from .channels import get_channel, normalize_channel_id
    from .social_pack import SELAR_JOURNAL_URL, SELAR_STORE_URL

    counterpart = resolve_longform_counterpart(short_key_or_title, channel_id=channel_id)
    url = counterpart["url"]
    scripture = counterpart.get("scripture") or "Scripture"
    owner = normalize_channel_id(channel_id or counterpart.get("channel"))

    # The length is the linked video's own, read from its receipt. This sentence
    # said "8-MINUTE" on all ten channels for every Short, whatever the video
    # ran: the long-forms are authored to six minutes, and The Secret Place's
    # night-tail prayers are three hours. With no receipt to read, the sentence
    # says what it does know.
    length = length_phrase(counterpart.get("minutes"))
    header = (
        f"🕊️ PRAY THE COMPLETE {length}{scripture.upper()} MEDITATION: 👉 {url}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    out = description if (url in description) else (header + description)

    if not get_channel(owner).include_sanctuary_links:
        return out
    if SELAR_JOURNAL_URL and SELAR_JOURNAL_URL not in out:
        handle = get_channel(owner).handle
        selar_block = (
            f"\n\n🕊️ BEDTIME PRAYER SANCTUARY (Also in {handle} bio):\n"
            f"• 30-Night Scripture Protection Prayer Journal (PDF): {SELAR_JOURNAL_URL}\n"
            f"• Partner in Prayer & Voluntary Ministry Support: {SELAR_STORE_URL}"
        )
        # Insert before trailing hashtag line if present so hashtags stay at the bottom
        lines = out.rstrip().splitlines()
        if lines and lines[-1].lstrip().startswith("#"):
            hashtag_line = lines.pop()
            out = "\n".join(lines).rstrip() + selar_block + "\n\n" + hashtag_line
        else:
            out = out.rstrip() + selar_block
    return out
