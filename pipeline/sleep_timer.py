"""Liturgical Sleep Timer & Google SERP Key Moments Engine.

Generates precise sleep timer intervals (e.g. 15-min drift, 30-min peace, 60-min delta rest),
chapter timestamps, and Schema.org structured metadata for Google Search Key Moments
under the permanent $0.00 / month cost lock.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SleepTimerInterval:
    minutes: int
    label: str
    phase: str
    scripture_focus: str


DEFAULT_SLEEP_TIMERS: list[SleepTimerInterval] = [
    SleepTimerInterval(15, "15 Min Sleep Drift", "Alpha-to-Theta Transition", "Psalm 91:4 (His Wings)"),
    SleepTimerInterval(30, "30 Min Deep Peace", "Light Non-REM Rest", "Psalm 23:2 (Still Waters)"),
    SleepTimerInterval(45, "45 Min Delta Induction", "Slow-Wave Sleep", "Psalm 121:4 (He Does Not Slumber)"),
    SleepTimerInterval(60, "60 Min REM Sanctuary", "Deep Restorative Sleep", "Psalm 4:8 (Sleep in Peace)"),
    SleepTimerInterval(120, "2 Hours Angelic Watch", "First Sleep Cycle Complete", "Psalm 34:7 (Angel Encamps)"),
    SleepTimerInterval(180, "3 Hours Night Watch", "Core Sleep Restoration", "Psalm 46:10 (Be Still & Know)"),
    SleepTimerInterval(480, "8 Hours All Night Sanctuary", "Full Overnight Rest", "Numbers 6:24-26 (The Benediction)"),
]


def generate_sleep_timer_chapters(total_duration_minutes: int = 60) -> list[dict[str, Any]]:
    """Generate sleep timer chapter markers up to the total duration."""
    results = [
        {
            "timestamp": "00:00",
            "seconds": 0,
            "title": "00:00 🕊️ Bedtime Sleep Sanctuary Opening & Stillness",
            "phase": "Centering in God's Presence",
        }
    ]

    for interval in DEFAULT_SLEEP_TIMERS:
        if interval.minutes < total_duration_minutes:
            hours = interval.minutes // 60
            mins = interval.minutes % 60
            if hours > 0:
                ts = f"{hours:02d}:{mins:02d}:00"
            else:
                ts = f"{mins:02d}:00"

            results.append({
                "timestamp": ts,
                "seconds": interval.minutes * 60,
                "title": f"{ts} 🌙 {interval.label} — {interval.scripture_focus}",
                "phase": interval.phase,
            })

    return results


def format_sleep_timer_description_block(total_duration_minutes: int = 60) -> str:
    """Format description timestamp block for YouTube and Google Key Moments."""
    chapters = generate_sleep_timer_chapters(total_duration_minutes)
    lines = ["⏱️ BEDTIME SLEEP TIMER & CHAPTERS:"]
    for c in chapters:
        lines.append(f"• {c['title']}")
    return "\n".join(lines)


def generate_sleep_schema_jsonld(
    title: str,
    description: str,
    video_id: str,
    duration_iso: str = "PT1H0M0S",
    upload_date: str = "2026-10-29",
    chapters: list[dict[str, Any]] | None = None,
) -> str:
    """Generate Schema.org VideoObject JSON-LD with hasPart clips for Google Search."""
    if chapters is None:
        chapters = generate_sleep_timer_chapters(60)

    has_parts = []
    for idx, c in enumerate(chapters):
        start_sec = c["seconds"]
        end_sec = chapters[idx + 1]["seconds"] if idx + 1 < len(chapters) else start_sec + 900
        has_parts.append({
            "@type": "Clip",
            "name": c["title"].split("—")[-1].strip() if "—" in c["title"] else c["title"],
            "startOffset": start_sec,
            "endOffset": end_sec,
            "url": f"https://www.youtube.com/watch?v={video_id}&t={start_sec}s",
        })

    data = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": title,
        "description": description[:300],
        "thumbnailUrl": [f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"],
        "uploadDate": upload_date,
        "duration": duration_iso,
        "embedUrl": f"https://www.youtube.com/embed/{video_id}",
        "hasPart": has_parts,
    }
    return json.dumps(data, indent=2)
