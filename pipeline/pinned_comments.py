"""Autonomous Pinned Comment & First-Hour Engagement Engine.

Generates and inserts high-conversion pastoral top-level comments immediately upon
video upload to trigger First-Hour Engagement Velocity ($V_{1hr}$), driving
algorithmic distribution in YouTube's recommendation engine while surfacing
clickable bedside Selar sanctuary resources on Long-Form videos.

Cost & Safety Invariants:
  • $0.00 / month hard cost lock (consumes 50 YouTube Data API units per upload).
  • Zero mentions of personal creator names; speaks exclusively as The Secret Place.
  • Anti-spam compliant; encourages faith declarations ("AMEN") and prayer requests.
"""
from __future__ import annotations

import re
from typing import Any

from .config import CONFIG
from .script_doc import ScriptDoc
from .social_pack import SELAR_JOURNAL_URL, SELAR_STORE_URL, sanitize_persona_integrity

_DAYTIME_COMMENT_HOOKS: list[tuple[str, str, str]] = [
    (
        "proverbs 3:5",
        "Proverbs 3:5-6 — 'Trust in the LORD with all thine heart; and lean not unto thine own understanding. In all thy ways acknowledge Him, and He shall direct thy paths.'",
        "divine direction, clear wisdom, and ordered steps",
    ),
    (
        "psalm 91:6",
        "Psalm 91:5-6 — 'Thou shalt not be afraid... nor for the destruction that wasteth at noonday.'",
        "sovereign covering and steadfast protection",
    ),
    (
        "psalm 91:2",
        "Psalm 91:2 — 'I will say of the LORD, He is my refuge and my fortress: my God; in Him will I trust.'",
        "unshakable refuge and covenant protection",
    ),
    (
        "psalm 37:5",
        "Psalm 37:5 — 'Commit thy way unto the LORD; trust also in Him; and He shall bring it to pass.'",
        "quiet confidence and faithful guidance",
    ),
    (
        "psalm 5",
        "Psalm 5:3 — 'My voice shalt thou hear in the morning, O LORD; in the morning will I direct my prayer unto thee, and will look up.'",
        "fresh morning mercy and attentive grace",
    ),
    (
        "psalm 143",
        "Psalm 143:8 — 'Cause me to hear thy lovingkindness in the morning; for in thee do I trust: cause me to know the way wherein I should walk.'",
        "unfailing lovingkindness and clear daily direction",
    ),
    (
        "lamentations 3",
        "Lamentations 3:22-23 — 'It is of the LORD's mercies that we are not consumed, because His compassions fail not. They are new every morning: great is thy faithfulness.'",
        "brand-new morning mercies and great faithfulness",
    ),
    (
        "mark 1",
        "Mark 1:35 — 'And in the morning, rising up a great while before day, He went out, and departed into a solitary place, and there prayed.'",
        "sacred communion and quiet strength from the Father",
    ),
    (
        "psalm 55",
        "Psalm 55:17 — 'Evening, and morning, and at noon, will I pray, and cry aloud: and He shall hear my voice.'",
        "unbroken communion and answered prayer",
    ),
    (
        "proverbs 16",
        "Proverbs 16:3 — 'Commit thy works unto the LORD, and thy thoughts shall be established.'",
        "established thoughts, clarity, and blessed work",
    ),
    (
        "isaiah 40",
        "Isaiah 40:31 — 'But they that wait upon the LORD shall renew their strength; they shall mount up with wings as eagles.'",
        "renewed strength and unwearying endurance",
    ),
    (
        "psalm 118",
        "Psalm 118:24 — 'This is the day which the LORD hath made; we will rejoice and be glad in it.'",
        "joy, gladness, and sovereign favor",
    ),
    (
        "psalm 90",
        "Psalm 90:14, 17 — 'O satisfy us early with thy mercy... and establish thou the work of our hands upon us.'",
        "early mercy and God's favor establishing the work of your hands",
    ),
    (
        "psalm 19",
        "Psalm 19:14 — 'Let the words of my mouth, and the meditation of my heart, be acceptable in thy sight, O LORD, my strength, and my redeemer.'",
        "pure words, guarded thoughts, and redeeming strength",
    ),
    (
        "psalm 25",
        "Psalm 25:4-5 — 'Shew me thy ways, O LORD; teach me thy paths. Lead me in thy truth, and teach me.'",
        "truthful guidance and steady direction",
    ),
    (
        "joshua 1",
        "Joshua 1:9 — 'Be strong and of a good courage; be not afraid, neither be thou dismayed: for the LORD thy God is with thee whithersoever thou goest.'",
        "courage, strength, and God's abiding presence",
    ),
]

_SCRIPTURE_COMMENT_HOOKS: list[tuple[str, str, str]] = [
    (
        "psalm 91",
        "Psalm 91:4 — 'He shall cover you with His feathers, and under His wings you shall take refuge; His truth shall be your shield and buckler.'",
        "divine protection and angelic shelter",
    ),
    (
        "psalm 23",
        "Psalm 23:1-2 — 'The Lord is my shepherd; I shall not want. He makes me to lie down in green pastures; He leads me beside the still waters.'",
        "divine rest, healing, and peace",
    ),
    (
        "psalm 121",
        "Psalm 121:3-4 — 'He that keepeth thee will not slumber. Behold, He that keepeth Israel shall neither slumber nor sleep.'",
        "unsleeping protection and peaceful sleep",
    ),
    (
        "psalm 27",
        "Psalm 27:1 — 'The Lord is my light and my salvation; whom shall I fear? The Lord is the strength of my life; of whom shall I be afraid?'",
        "courage and freedom from nighttime anxiety",
    ),
    (
        "psalm 46",
        "Psalm 46:1, 10 — 'God is our refuge and strength, a very present help in trouble... Be still, and know that I am God.'",
        "holy stillness and unshakable refuge",
    ),
    (
        "psalm 34",
        "Psalm 34:7 — 'The angel of the LORD encampeth round about them that fear Him, and delivereth them.'",
        "angelic guard and deliverance over your household",
    ),
    (
        "psalm 4",
        "Psalm 4:8 — 'I will both lay me down in peace, and sleep: for thou, LORD, only makest me dwell in safety.'",
        "deep safety and untroubled rest",
    ),
    (
        "psalm 3",
        "Psalm 3:5 — 'I laid me down and slept; I awaked; for the LORD sustained me.'",
        "sustaining peace through every watch of the night",
    ),
    (
        "psalm 16",
        "Psalm 16:7-8 — 'I will bless the LORD, who hath given me counsel... because He is at my right hand, I shall not be moved.'",
        "gentle night counsel and steady confidence",
    ),
    (
        "psalm 18",
        "Psalm 18:2 — 'The LORD is my rock, and my fortress, and my deliverer; my God, my strength, in whom I will trust.'",
        "unbreakable strength and shelter",
    ),
    (
        "psalm 31",
        "Psalm 31:5 — 'Into thine hand I commit my spirit: thou hast redeemed me, O LORD God of truth.'",
        "peaceful surrender into the Father's hands",
    ),
    (
        "psalm 37",
        "Psalm 37:7 — 'Rest in the LORD, and wait patiently for Him: fret not thyself.'",
        "quiet contentment and freedom from fretting",
    ),
    (
        "psalm 63",
        "Psalm 63:6-7 — 'When I remember thee upon my bed, and meditate on thee in the night watches... in the shadow of thy wings will I rejoice.'",
        "joyful rest beneath the shadow of His wings",
    ),
    (
        "psalm 139",
        "Psalm 139:11-12 — 'Yea, the darkness hideth not from thee; but the night shineth as the day.'",
        "God's luminous presence in the deepest night",
    ),
    (
        "proverbs 3",
        "Proverbs 3:24 — 'When thou liest down, thou shalt not be afraid: yea, thou shalt lie down, and thy sleep shall be sweet.'",
        "sweet, fearless sleep tonight",
    ),
    (
        "isaiah 26",
        "Isaiah 26:3 — 'Thou wilt keep him in perfect peace, whose mind is stayed on thee: because he trusteth in thee.'",
        "perfect peace over your mind and thoughts",
    ),
    (
        "isaiah 41",
        "Isaiah 41:10 — 'Fear thou not; for I am with thee: be not dismayed; for I am thy God: I will strengthen thee.'",
        "strength, courage, and God's right hand upholding you",
    ),
    (
        "matthew 11",
        "Matthew 11:28 — 'Come unto me, all ye that labour and are heavy laden, and I will give you rest.'",
        "deep soul rest from every heavy burden",
    ),
    (
        "john 14",
        "John 14:27 — 'Peace I leave with you, my peace I give unto you... Let not your heart be troubled, neither let it be afraid.'",
        "Christ's untroubled peace over your heart",
    ),
    (
        "philippians 4",
        "Philippians 4:7 — 'And the peace of God, which passeth all understanding, shall keep your hearts and minds through Christ Jesus.'",
        "God's garrison of peace guarding your heart and mind",
    ),
    (
        "2 timothy 1",
        "2 Timothy 1:7 — 'For God hath not given us the spirit of fear; but of power, and of love, and of a sound mind.'",
        "power, love, and a quiet, sound mind",
    ),
    (
        "1 peter 5",
        "1 Peter 5:7 — 'Casting all your care upon Him; for He careth for you.'",
        "complete release of every anxious care",
    ),
    (
        "numbers 6",
        "Numbers 6:24-26 — 'The LORD bless thee, and keep thee: the LORD make His face shine upon thee, and give thee peace.'",
        "the Father's priestly blessing and keeping peace",
    ),
]


def generate_pastoral_pinned_comment(doc: ScriptDoc) -> str:
    """Generate an authoritative, comforting pastoral comment for the video.

    - For Shorts: builds a Short-to-Longform & Channel-Bio bridge comment.
    - For Long-Form Faith videos: includes KJV promise, 'AMEN' & prayer-request
      invitation, and both live clickable Selar sanctuary links.
    """
    niche = (getattr(doc, "niche", "") or str(doc.meta.get("niche", ""))).lower()
    if any(k in niche for k in ("finance", "business", "economics", "corporate")):
        return ""

    title_lower = (doc.title or "").lower()
    is_short = (
        getattr(doc, "format", "") == "short"
        or doc.meta.get("format") == "short"
        or "#shorts" in title_lower
        or (getattr(doc, "slug", "") and "short-" in getattr(doc, "slug", ""))
    )

    if is_short:
        try:
            from .shorts_bridge import generate_short_bridge_comment

            short_key = getattr(doc, "slug", "") or doc.title
            return sanitize_persona_integrity(generate_short_bridge_comment(
                short_key, channel_id=doc.explicit_channel or CONFIG.channel_id))
        except Exception:
            pass

    from .channel_capabilities import brand_for, pinned_comment_for
    from .channels import DEFAULT_CHANNEL_ID, get_channel, normalize_channel_id

    channel_id = normalize_channel_id(doc.explicit_channel or CONFIG.channel_id)
    brand = brand_for(channel_id)
    scripture_hook = brand.default_comment_scripture_hook
    theme = brand.default_comment_theme

    hook_table = (
        [*_SCRIPTURE_COMMENT_HOOKS, *_DAYTIME_COMMENT_HOOKS]
        if channel_id == DEFAULT_CHANNEL_ID
        else [*_DAYTIME_COMMENT_HOOKS, *_SCRIPTURE_COMMENT_HOOKS]
    )
    for key, verse_text, verse_theme in hook_table:
        if re.search(rf"\b{re.escape(key)}(?!\d)", title_lower):
            if channel_id != DEFAULT_CHANNEL_ID and any(
                w in (verse_text + " " + verse_theme).lower()
                for w in ("sleep", "slumber", "night", "tonight", "bed", "liest down")
            ):
                continue
            scripture_hook = verse_text
            theme = verse_theme
            break

    sanctuary_links = get_channel(channel_id).include_sanctuary_links
    selar_lines: list[str] = []
    if sanctuary_links and SELAR_JOURNAL_URL:
        selar_lines.append(f"📖 Printable 30-Night Bedside Prayer Journal: {SELAR_JOURNAL_URL}")
    if sanctuary_links and SELAR_STORE_URL:
        selar_lines.append(f"🤍 Voluntary Ministry Support: {SELAR_STORE_URL}")
    selar_footer = ("\n\n" + "\n".join(selar_lines)) if selar_lines else ""

    # One template per channel, declared in the capability matrix: neither channel
    # gets a bespoke code path (which is how The Morning Altar inherited a night
    # comment in the first place).
    comment = pinned_comment_for(
        channel_id, theme=theme, scripture_hook=scripture_hook, footer=selar_footer)
    return sanitize_persona_integrity(comment.strip())


def post_pastoral_pinned_comment(
    youtube: Any,
    video_id: str,
    comment_text: str,
    dry_run: bool = False,
) -> str | None:
    """Insert a top-level owner comment on the newly uploaded video."""
    if not comment_text or not comment_text.strip():
        return None
    if dry_run or not youtube:
        print(f"[pinned-comment] [dry-run] Would post pinned comment on video '{video_id}':")
        print(f"  \"{comment_text[:120]}...\"")
        return f"mock_comment_{video_id}"

    try:
        req = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": sanitize_persona_integrity(comment_text),
                        }
                    },
                }
            },
        )
        res = req.execute()
        comment_id = res.get("id")
        print(f"[pinned-comment] Successfully posted pastoral comment on video '{video_id}' (ID: {comment_id})")
        return comment_id
    except Exception as exc:
        print(f"[pinned-comment] Notice: error posting pinned comment: {exc}")
        return None
