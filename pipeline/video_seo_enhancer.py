"""Google Search Key Moments & Video SEO Enhancer.

Optimizes YouTube video descriptions and chapter timestamps to trigger
Google Search Engine Results Page (SERP) 'Key Moments' carousels, driving
organic search traffic directly into The Secret Place videos under the $0.00 lock.

Google Key Moments Specifications:
  1. The first chapter must start at 00:00 (or 0:00).
  2. At least three timestamps in ascending order.
  3. Minimum duration of 10 seconds per chapter clip.
  4. Timestamp format must be [H:]MM:SS followed by a descriptive title.
  5. Schema.org VideoObject JSON-LD generation for web dashboard & GitHub Pages.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class KeyMoment:
    seconds: float
    timestamp: str  # "00:00", "01:15", etc.
    label: str
    search_query_focus: str


def format_seconds_to_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    sec_int = int(seconds)
    hours = sec_int // 3600
    minutes = (sec_int % 3600) // 60
    secs = sec_int % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timestamp_to_seconds(timestamp: str) -> float:
    """Parse HH:MM:SS or MM:SS into total seconds."""
    parts = [int(p) for p in timestamp.strip().split(":")]
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    elif len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    elif len(parts) == 1:
        return float(parts[0])
    return 0.0


def validate_key_moments(chapters: Sequence[dict]) -> tuple[bool, list[str]]:
    """Validate that chapter markers adhere to Google Search Key Moments specifications."""
    issues = []
    if len(chapters) < 3:
        issues.append(f"Google Key Moments requires at least 3 chapters; found {len(chapters)}.")

    if not chapters:
        return False, issues

    # 1. First timestamp must be 00:00
    first_stamp = chapters[0].get("timestamp", "").strip()
    if first_stamp not in ["0:00", "00:00", "00:00:00", "0:00:00"]:
        issues.append(f"First chapter must begin at 00:00; found '{first_stamp}'.")

    # 2. Ascending order and minimum duration
    prev_sec = 0.0
    for idx, c in enumerate(chapters):
        t_str = c.get("timestamp", "")
        sec = c.get("seconds", parse_timestamp_to_seconds(t_str))
        if idx > 0 and sec <= prev_sec:
            issues.append(f"Chapter '{c.get('title')}' ({t_str}) is not strictly in ascending order.")
        if idx > 0 and (sec - prev_sec) < 10.0:
            issues.append(f"Chapter '{c.get('title')}' is shorter than Google's 10-second minimum clip requirement.")
        prev_sec = sec

    return len(issues) == 0, issues


def build_serp_key_moments(
    raw_chapters: Sequence[dict],
    target_search_keywords: Sequence[str] | None = None,
) -> list[KeyMoment]:
    """Enhance raw chapter markers with high-intent Google Search keywords."""
    moments = []
    for idx, c in enumerate(raw_chapters):
        t_str = c.get("timestamp", format_seconds_to_timestamp(c.get("seconds", 0.0)))
        sec = float(c.get("seconds", parse_timestamp_to_seconds(t_str)))
        title = c.get("title", f"Movement {idx+1}")

        # Clean title for SERP clarity
        clean_title = re.sub(r"^[0-9]+[\.\-]\s*", "", title).strip()
        search_focus = target_search_keywords[idx % len(target_search_keywords)] if target_search_keywords else clean_title

        moments.append(
            KeyMoment(
                seconds=sec,
                timestamp=t_str,
                label=clean_title,
                search_query_focus=search_focus,
            )
        )
    return moments


def enhance_description_with_key_moments(
    base_description: str,
    key_moments: Sequence[KeyMoment],
    channel_name: str = "The Secret Place",
) -> str:
    """Format description with Google Search Key Moments block."""
    valid, issues = validate_key_moments([{"timestamp": m.timestamp, "seconds": m.seconds, "title": m.label} for m in key_moments])

    chapters_formatted = "\n".join(
        f"{m.timestamp} {m.label}" for m in key_moments
    )

    serp_block = (
        f"\n\nTIMESTAMPS & KEY MOMENTS:\n"
        f"{chapters_formatted}\n\n"
        f"Listen every night to {channel_name} for peaceful scripture meditations, "
        f"bedtime prayers, and divine protection over your home."
    )

    # Avoid duplicating timestamps if already present
    if "TIMESTAMPS" in base_description or "CHAPTERS" in base_description:
        return base_description

    return (base_description.strip() + serp_block).strip()


def generate_video_schema_json_ld(
    title: str,
    description: str,
    video_id: str,
    upload_date_iso: str,
    duration_iso: str,
    thumbnail_url: str,
    key_moments: Sequence[KeyMoment],
) -> dict:
    """Generate Schema.org VideoObject JSON-LD with Clip entities for Google SERP."""
    clips = []
    for idx, m in enumerate(key_moments):
        end_sec = key_moments[idx + 1].seconds if idx + 1 < len(key_moments) else m.seconds + 60.0
        clips.append({
            "@type": "Clip",
            "name": m.label,
            "startOffset": int(m.seconds),
            "endOffset": int(end_sec),
            "url": f"https://www.youtube.com/watch?v={video_id}&t={int(m.seconds)}s",
        })

    schema = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": title,
        "description": description[:1000],
        "thumbnailUrl": [thumbnail_url],
        "uploadDate": upload_date_iso,
        "duration": duration_iso,
        "contentUrl": f"https://www.youtube.com/watch?v={video_id}",
        "embedUrl": f"https://www.youtube.com/embed/{video_id}",
        "hasPart": clips,
    }
    return schema
