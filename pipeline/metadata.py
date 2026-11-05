"""SEO metadata pack: chapters, description, Selar sanctuary links, tags, title guards.

2026 YouTube & Google Video SEO spec:
  * title: 100 chars hard limit / ~55–68 visible — primary keyword in first 5 words,
    smart word-boundary guard (zero mid-word truncation, zero '<'/'>' characters).
  * description: 5,000 UTF-8 bytes hard limit;
      - Line 1 (chars 1–150): pure natural-language search snippet (`seo_hook`)
      - Line 2 (watch-page fold): quiet bedside Prayer Journal Selar link (`selar.com/i000qy7g39`)
      - Body: unwrapped prose paragraphs + scripture references
      - CHAPTERS: starts at `00:00`, >=3 chapters, >=10s per chapter (including final chapter)
      - Sanctuary Resources: both live Selar URLs (`selar.com/i000qy7g39` &
        `selar.com/showlove/thesecretplace`), companion prayers, subscribe, pastoral care
  * tags: <=500 serialized chars using YouTube's implicit-quote rule for multi-word tags
  * hashtags: 3–5 CamelCase hashtags in description (#Shorts first for Shorts)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .config import CONFIG
from .script_doc import ScriptDoc
from .social_pack import (
    SELAR_JOURNAL_URL,
    SELAR_STORE_URL,
    SUBSCRIBE_URL,
    build_above_fold_selar_line,
    build_sanctuary_resource_block,
    sanitize_persona_integrity,
)

_TRAILING_DANGLERS = {
    "&", "and", "or", "for", "of", "with", "to", "in", "on", "at", "by", "from", "the", "a", "an",
}

_SCRIPTURE_RE = re.compile(
    r"\b((?:[123]\s+)?(?:Psalm|Psalms|Proverbs|Isaiah|Matthew|Mark|Luke|John|"
    r"Romans|Philippians|Timothy|Peter|Numbers|Jude|Hebrews|Corinthians|Ephesians)"
    r"\s+\d+(?::\d+(?:[-–]\d+)?)?)\b",
    re.IGNORECASE,
)


def is_faith_doc(doc: ScriptDoc) -> bool:
    """Return True when the document belongs to the faith / scripture / prayer sanctuary."""
    niche = (getattr(doc, "niche", "") or str(doc.meta.get("niche", ""))).lower()
    slug = (getattr(doc, "slug", "") or "").lower()
    title = (doc.title or "").lower()
    if any(k in niche for k in ("finance", "business", "economics", "corporate")):
        return False
    return any(
        k in niche or k in slug or k in title
        for k in ("faith", "prayer", "scripture", "devotional", "psalm", "proverbs", "isaiah", "gospel", "bible")
    )


def sanitize_youtube_text(text: str) -> str:
    """Remove angle brackets (forbidden by YouTube Data API v3) and enforce persona integrity."""
    if not text:
        return ""
    cleaned = text.replace("<", "‹").replace(">", "›")
    cleaned = cleaned.replace("‹", "").replace("›", "")
    return sanitize_persona_integrity(cleaned)


def truncate_utf8_bytes(text: str, max_bytes: int = 4900) -> str:
    """Truncate text cleanly on a line or word boundary so UTF-8 byte length <= max_bytes."""
    cleaned = sanitize_youtube_text(text).strip()
    raw = cleaned.encode("utf-8")
    if len(raw) <= max_bytes:
        return cleaned

    clipped = raw[:max_bytes].decode("utf-8", errors="ignore")
    last_nl = clipped.rfind("\n")
    if last_nl >= int(len(clipped) * 0.75):
        return clipped[:last_nl].rstrip()
    last_space = clipped.rfind(" ")
    if last_space > 0:
        return clipped[:last_space].rstrip(" ,;:-—|")
    return clipped.rstrip()


def smart_truncate_title(title: str, limit: int = 95) -> str:
    """Truncate a YouTube title without ever chopping mid-word or leaving dangling '&'/'and'."""
    cleaned = " ".join(sanitize_youtube_text(title).split())
    if len(cleaned) <= limit:
        return cleaned

    # 1. Strip redundant trailing channel suffix first if present
    for sep in (" | The Secret Place", " — The Secret Place", " - The Secret Place"):
        if cleaned.endswith(sep) and len(cleaned) - len(sep) >= 30:
            trimmed = cleaned[: -len(sep)].rstrip()
            if len(trimmed) <= limit:
                return trimmed
            cleaned = trimmed

    # 2. Prefer a clean structural separator within [40..limit]
    window = cleaned[: limit + 1]
    for sep in (" | ", " — ", " - "):
        idx = window.rfind(sep)
        if idx >= 40:
            candidate = window[:idx].rstrip()
            if candidate:
                return candidate

    # 3. Word-boundary cut + strip trailing conjunctions / punctuation
    cut = window.rfind(" ")
    candidate = window[:cut] if cut > 20 else cleaned[:limit]
    words = candidate.rstrip(" ,;:-—|&").split()
    while len(words) > 4 and words[-1].lower().strip(".,;:-—|") in _TRAILING_DANGLERS:
        words.pop()
    return " ".join(words).rstrip(" ,;:-—|&")


def _clean_chapter_heading(heading: str, max_len: int = 68) -> str:
    """Convert internal script scene headings into clean viewer-facing chapter titles."""
    label = sanitize_youtube_text(heading or "").strip()
    # Remove trailing internal notes like "(Verse 1)", "(Verses 2–3 Synthesis)", "(Verse 8a)"
    label = re.sub(
        r"\s*\((?:Verse|Verses)\s+[^)]*(?:Synthesis)?\)\s*$",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip()
    label = re.sub(r"^\d+[\.\)]\s*", "", label).strip()
    if not label:
        label = "Scripture Prayer"
    if len(label) <= max_len:
        return label
    cut = label[: max_len + 1].rfind(" ")
    shortened = label[:cut] if cut > 20 else label[: max_len - 1]
    return shortened.rstrip(" ,;:-—|(&")


def _format_stamp(seconds: float) -> str:
    total = max(0, int(seconds))
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def chapters_from_scenes(doc: ScriptDoc, scene_durations: list[float]) -> list[tuple[str, str]]:
    """Return [(00:00, chapter_name), ...] obeying YouTube's >=10s & 00:00 start rules."""
    if not doc.scenes or not scene_durations:
        return []

    paired = [
        (_clean_chapter_heading(scene.heading), max(0.0, float(dur)))
        for scene, dur in zip(doc.scenes, scene_durations)
    ]
    if not paired:
        return []

    # Merge any sub-10s segment so YouTube never invalidates the entire chapter list
    merged: list[list[object]] = []
    for name, dur in paired:
        if not merged:
            merged.append([name, dur])
        elif float(merged[-1][1]) < 10.0:
            merged[-1][1] = float(merged[-1][1]) + dur
        else:
            merged.append([name, dur])

    if len(merged) > 1 and float(merged[-1][1]) < 10.0:
        merged[-2][1] = float(merged[-2][1]) + float(merged[-1][1])
        merged.pop()

    out: list[tuple[str, str]] = []
    t = 0.0
    for idx, (name, dur) in enumerate(merged):
        stamp = "00:00" if idx == 0 else _format_stamp(t)
        out.append((stamp, str(name)))
        t += float(dur)
    return out


def format_chapters(chapters: list[tuple[str, str]]) -> str:
    return "\n".join(f"{stamp} {name}" for stamp, name in chapters)


def _to_camel_hashtag(raw_tag: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\s_]", " ", raw_tag or "").strip()
    if not cleaned:
        return ""
    parts = [p for p in re.split(r"[\s_]+", cleaned) if p]
    if not parts:
        return ""
    token = "".join(p[:1].upper() + p[1:] for p in parts)
    return f"#{token}" if token else ""


def _hashtags_for_doc(doc: ScriptDoc) -> list[str]:
    faith = is_faith_doc(doc)
    seen_lower: set[str] = set()
    result: list[str] = []

    def _add(ht: str) -> None:
        if not ht or not ht.startswith("#") or len(ht) < 3 or len(ht) > 23:
            return
        low = ht.lower()
        if low not in seen_lower:
            seen_lower.add(low)
            result.append(ht)

    if doc.format == "short":
        _add("#Shorts")

    if faith:
        m = _SCRIPTURE_RE.search(doc.title or "")
        if m:
            book_chap = " ".join(m.group(1).replace(":", " ").replace("–", " ").replace("-", " ").split()[:2])
            _add(_to_camel_hashtag(book_chap))

    for t in doc.tags:
        t_clean = t.strip()
        if not t_clean or t_clean.lower() == "shorts" or len(t_clean.split()) > 3:
            continue
        if "432" in t_clean.lower() and "432" not in (doc.title or "").lower():
            continue
        _add(_to_camel_hashtag(t_clean))
        if len(result) >= 4:
            break

    if faith:
        for fallback in ("#NightPrayer", "#PrayerBeforeSleep", "#BedtimePrayer", "#TheSecretPlace"):
            if len(result) >= 5:
                break
            _add(fallback)
    elif not result:
        _add("#Documentary")

    return result[:5]


def _unwrap_prose_paragraphs(text: str) -> str:
    """Unwrap YAML single line-breaks inside prose paragraphs while preserving lists & headers."""
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text.strip())
    rendered_blocks: list[str] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # Preserve blocks that contain bullet lists, numbered lists, or colon headers
        if any(
            ln.startswith(("-", "•", "*", "00:", "0:", "1.", "2.", "3."))
            or ln.endswith(":")
            for ln in lines
        ):
            rendered_blocks.append("\n".join(lines))
        else:
            rendered_blocks.append(" ".join(lines))
    return "\n\n".join(rendered_blocks)


def _synthesize_seo_hook(doc: ScriptDoc) -> str:
    explicit = " ".join(str(doc.meta.get("seo_hook", "")).split()).strip()
    if explicit:
        return sanitize_youtube_text(explicit)[:155]

    if is_faith_doc(doc):
        m = _SCRIPTURE_RE.search(doc.title or "")
        if m:
            ref = m.group(1)
            return (
                f"Pray this {ref} KJV night prayer before sleep for deep peace, "
                f"quiet rest, and God's protection over your home tonight."
            )[:155]
        return (
            "Pray this KJV bedtime scripture prayer before you sleep for deep peace, "
            "freedom from anxiety, and God's watchful protection tonight."
        )[:155]

    return smart_truncate_title(doc.title, 150)


def build_description(
    doc: ScriptDoc,
    scene_durations: list[float] | None = None,
    extra_links: str = "",
) -> str:
    """Build complete SEO + Selar description within YouTube's 5,000 UTF-8 byte cap."""
    faith = is_faith_doc(doc)
    is_short = doc.format == "short"
    hook = _synthesize_seo_hook(doc)
    body = _unwrap_prose_paragraphs(doc.description or "")

    # Selar/store links are The Secret Place's funnel. Other channels (e.g.
    # The Morning Altar) must not inherit them — see pipeline/channels.py.
    from .channels import get_channel

    # The script's own channel wins over the ambient CONFIG channel: a
    # Morning Altar script must never inherit Selar links just because it
    # was rendered while CONFIG pointed at The Secret Place (and vice versa).
    doc_channel = get_channel(doc.explicit_channel or CONFIG.channel_id)
    sanctuary_links = faith and doc_channel.include_sanctuary_links

    #Zone 1: Search Snippet (Line 1) + Watch-Page Fold Selar Journal Link (Line 2)
    zone1_lines = [hook]
    if sanctuary_links and not is_short:
        fold_selar = build_above_fold_selar_line()
        if fold_selar and (SELAR_JOURNAL_URL not in body) and (SELAR_JOURNAL_URL not in extra_links):
            zone1_lines.append(fold_selar)

    parts: list[str] = ["\n".join(zone1_lines)]

    # Zone 2: Unique Devotional / Documentary Prose & Citations
    if body and body.strip() != hook.strip():
        parts.extend(["", body[:1800]])

    # Zone 3: Exact Timestamped Chapters (Long-Form with >=3 valid >=10s chapters)
    if scene_durations and not is_short:
        chapters = chapters_from_scenes(doc, scene_durations)
        if len(chapters) >= 3:
            parts.extend(["", "CHAPTERS", format_chapters(chapters)])

    # Zone 4: Sanctuary Resources (Both Live Selar Links + Internal Session Web + Pastoral Care)
    if extra_links:
        parts.extend(["", extra_links.strip()])
    elif sanctuary_links:
        already_has_both_selar = (
            (not SELAR_JOURNAL_URL or SELAR_JOURNAL_URL in body)
            and (not SELAR_STORE_URL or SELAR_STORE_URL in body)
        )
        if not already_has_both_selar:
            if is_short:
                short_resources = [
                    "🕊️ BEDTIME PRAYER SANCTUARY",
                    f"• 30-Night Bedside Prayer Journal (PDF): {SELAR_JOURNAL_URL}",
                    f"• Partner in Prayer & Voluntary Support: {SELAR_STORE_URL}",
                    f"• Subscribe to The Secret Place: {SUBSCRIBE_URL}",
                ]
                parts.extend(["", "\n".join(short_resources)])
            else:
                parts.extend(["", build_sanctuary_resource_block(include_store_links=True)])
    elif faith:
        # A channel without its own resource funnel yet (e.g. The Morning
        # Altar at launch): invite subscription to *this* channel only —
        # never borrow The Secret Place's Selar/store links.
        from .channel_capabilities import subscribe_heading_for

        profile = doc_channel
        profile_subscribe_heading = subscribe_heading_for(profile.id)
        if profile.id == CONFIG.channel_id:
            channel_name = CONFIG.channel_name or profile.display_name
            channel_handle = CONFIG.channel_handle or profile.handle
        else:
            channel_name = profile.display_name
            channel_handle = profile.handle
        parts.extend(
            [
                "",
                "\n".join(
                    [
                        profile_subscribe_heading,
                        f"• Subscribe to {channel_name}: "
                        f"https://www.youtube.com/{channel_handle}?sub_confirmation=1",
                        "",
                        "Scripture & Devotional Attribution: The Holy Bible "
                        "(King James Version, Public Domain).",
                        f"Curated by the {channel_name} editorial team.",
                    ]
                ),
            ]
        )
    elif not is_short:
        parts.extend(
            [
                "",
                "Research notes & primary sources are listed above. Produced with a human-edited documentary pipeline.",
            ]
        )

    # Zone 5: 3–5 Focused CamelCase Hashtags
    hashtags = " ".join(_hashtags_for_doc(doc))
    if hashtags:
        parts.extend(["", hashtags])

    assembled = "\n".join(p for p in parts if p is not None)
    return truncate_utf8_bytes(assembled, max_bytes=4900)


def serialized_youtube_tag_cost(tags: list[str]) -> int:
    """Exact YouTube Data API v3 tag character count (multi-word tags get implicit quotes)."""
    if not tags:
        return 0
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(0, len(tags) - 1)


def fit_youtube_tags(
    candidates: list[str],
    extra_tags: list[str] | None = None,
    max_chars: int = 490,
    allow_432hz: bool = False,
) -> list[str]:
    """Pack clean tags without ever exceeding YouTube's 500-char quote-aware tag limit."""
    chosen: list[str] = []
    seen: set[str] = set()
    pool = list(candidates or []) + list(extra_tags or [])

    for raw in pool:
        tag = " ".join(sanitize_youtube_text(str(raw)).lstrip("#").lower().split())
        if not tag or len(tag) > 65:
            continue
        if not allow_432hz and "432" in tag:
            continue
        if tag in seen:
            continue
        trial = [*chosen, tag]
        if serialized_youtube_tag_cost(trial) > max_chars:
            continue
        seen.add(tag)
        chosen.append(tag)
        if len(chosen) >= 18:
            break
    return chosen


def build_tags(doc: ScriptDoc) -> list[str]:
    """Generate scripture-aware, high-intent backend tags within the 500-char API budget.

    The dormant high-intent search taxonomy (``seo_suggest``) is now wired in: after
    the scripture-specific and brand seeds, it contributes the pain-point and search
    queries viewers actually type (insomnia, anxiety, spiritual warfare, …). Every
    candidate still passes through ``fit_youtube_tags``, which enforces the 500-char
    quote-aware budget, the 18-tag cap, and the 432 Hz gate — so this is additive and
    can never break the tag contract.
    """
    allow_432 = "432" in (doc.title or "").lower() or "dark_screen" in (doc.slug or "").lower()
    seeds: list[str] = []
    scripture_ref = ""

    if is_faith_doc(doc):
        m = _SCRIPTURE_RE.search(doc.title or "")
        if m:
            ref_raw = " ".join(m.group(1).lower().replace(":", " ").replace("–", " ").replace("-", " ").split())
            book_chap = " ".join(ref_raw.split()[:2])
            scripture_ref = book_chap
            seeds.extend(
                [
                    f"{book_chap} night prayer",
                    f"{book_chap} prayer for sleep",
                    book_chap,
                ]
            )
            if ref_raw != book_chap:
                seeds.insert(0, f"{ref_raw} prayer")

    seeds.extend(doc.tags or [])

    if is_faith_doc(doc):
        seeds.extend(
            [
                "prayer before sleep",
                "night prayer for peace and protection",
                "bedtime prayer",
                "christian sleep prayer",
                "kjv scripture prayer",
                "the secret place prayer",
            ]
        )
        # High-intent search taxonomy: what distressed / sleepless viewers actually
        # type. fit_youtube_tags drops any 432 Hz qualifier unless this is a 432 video.
        try:
            from .seo_suggest import get_taxonomy_for_scripture

            tax = get_taxonomy_for_scripture(scripture_ref or "General Bedtime")
            seeds.extend(tax.get("primary_searches", []))
            seeds.extend(tax.get("pain_points", []))
            seeds.extend(tax.get("qualifiers", []))
        except Exception:  # noqa: BLE001
            # SEO enrichment is an optimisation, never a gate.
            pass

    return fit_youtube_tags(seeds, max_chars=490, allow_432hz=allow_432)


def title_report(doc: ScriptDoc) -> dict:
    """Validate the title against mobile/search visibility windows + A/B variants."""
    title = smart_truncate_title(doc.title, 95)
    variants_raw = doc.meta.get("title_variants", []) or []
    variants = [title] + [smart_truncate_title(str(v), 95) for v in variants_raw]
    return {
        "chosen_title": title,
        "raw_title_length": len(doc.title),
        "length": len(title),
        "visible_mobile": len(title) <= 55,
        "visible_desktop": len(title) <= 70,
        "warnings": (
            (["title exceeds 55 chars — hook may be cut on mobile"] if len(title) > 55 else [])
            + (["title exceeds 70 chars — will truncate in search"] if len(title) > 70 else [])
        ),
        "ab_variants": variants[:3],
        "note": "Feed variants into Studio → A/B test titles & thumbnails (winner = watch-time share, not CTR)",
    }


def write_metadata_pack(doc: ScriptDoc, scene_durations: list[float], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters = chapters_from_scenes(doc, scene_durations)
    safe_title = smart_truncate_title(doc.title, 95)
    pack = {
        "title": safe_title,
        "title_report": title_report(doc),
        "description": build_description(doc, scene_durations),
        "tags": build_tags(doc),
        "chapters": [{"time": s, "name": n} for s, n in chapters],
        "hashtags": _hashtags_for_doc(doc),
        "selar_journal_url": SELAR_JOURNAL_URL if is_faith_doc(doc) else "",
        "selar_store_url": SELAR_STORE_URL if is_faith_doc(doc) else "",
        "publish_hint": "Schedule 2–4h before your audience peak (Analytics → Audience). "
                        "Pinned comment + community post + end screen within the first hour. "
                        "Do not change title/thumbnail in the first 24h.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")

    md = [
        f"# Metadata pack — {safe_title}",
        "",
        "## Title (spec: 55–68 visible chars, keyword first 5 words)",
        f"`{safe_title}` ({len(safe_title)} chars)",
    ]
    md += [f"- ⚠ {w}" for w in pack["title_report"]["warnings"]]
    if len(pack["title_report"]["ab_variants"]) > 1:
        md += [
            "",
            "### A/B variants for Studio Test & Compare",
            *[f"- {v}" for v in pack["title_report"]["ab_variants"]],
        ]
    md += [
        "", "## Description (copy into Studio)", "", "```", pack["description"], "```",
        "", f"## Tags ({serialized_youtube_tag_cost(pack['tags'])}/500 serialized chars)", ", ".join(pack["tags"]),
        "", "## Chapters", format_chapters(chapters),
        "", "## Publish ritual", pack["publish_hint"],
    ]
    (out_dir / "metadata.md").write_text("\n".join(md), encoding="utf-8")
    return pack
