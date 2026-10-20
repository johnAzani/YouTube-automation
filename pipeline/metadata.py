"""SEO metadata pack: chapters, description, tags, title variants.

2026 spec (docs/GROWTH.md §5):
  * title 100 chars hard / ~55–65 visible — keyword in first 5 words
  * description 5,000 chars; first 150–157 = "money zone"
  * chapters: start 0:00, ≥3, ≥10 s each, 1 per 1–2 min, keyword-named
  * tags 500 chars total (low weight) · hashtags 3–5 (16+ → ALL ignored)

Everything here is a DRAFT for human review — the human owns the final title
(the single highest-leverage decision). Chapter timestamps are exact: they
come from the render's scene durations.
"""
from __future__ import annotations

import json
from pathlib import Path

from .script_doc import ScriptDoc


def chapters_from_scenes(doc: ScriptDoc, scene_durations: list[float]) -> list[tuple[str, str]]:
    """Return [(mm:ss, chapter_name), ...] — first chapter always at 0:00."""
    out: list[tuple[str, str]] = []
    t = 0.0
    for scene, dur in zip(doc.scenes, scene_durations):
        m, s = divmod(int(t), 60)
        h, m = divmod(m, 60)
        stamp = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        name = scene.heading.strip()
        if len(name) > 60:
            name = name[:57] + "..."
        out.append((stamp, name))
        t += dur
    return out


def format_chapters(chapters: list[tuple[str, str]]) -> str:
    return "\n".join(f"{stamp} {name}" for stamp, name in chapters)


def build_description(doc: ScriptDoc, scene_durations: list[float] | None = None,
                      extra_links: str = "") -> str:
    """Full SEO description. First 150–157 chars are the search snippet — the
    frontmatter `seo_hook` (or first sentence) goes there."""
    hook = str(doc.meta.get("seo_hook", "")).strip() or doc.title
    body = doc.description or ""

    parts = [
        hook[:155],                       # money zone
        "",
        body.strip()[:1200] if body else "",
    ]
    if scene_durations:
        chapters = format_chapters(chapters_from_scenes(doc, scene_durations))
        parts += ["", "CHAPTERS", chapters]
    if extra_links:
        parts += ["", extra_links]
    tags = " ".join(f"#{t.replace(' ', '')}" for t in doc.tags[:3])
    parts += ["", tags or "#documentary"]
    return "\n".join(p for p in parts if p is not None)[:4900]


def build_tags(doc: ScriptDoc) -> list[str]:
    seen: list[str] = []
    for t in doc.tags:
        t = t.strip().lower()
        if t and t not in seen:
            seen.append(t)
    return seen[:15]


def title_report(doc: ScriptDoc) -> dict:
    """Validate the human's title against the visibility spec + A/B variants."""
    title = doc.title
    variants_raw = doc.meta.get("title_variants", []) or []
    variants = [title] + [str(v) for v in variants_raw]
    return {
        "chosen_title": title,
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
    pack = {
        "title": doc.title,
        "title_report": title_report(doc),
        "description": build_description(doc, scene_durations),
        "tags": build_tags(doc),
        "chapters": [{"time": s, "name": n} for s, n in chapters],
        "hashtags": [f"#{t.replace(' ', '')}" for t in doc.tags[:3]] or ["#documentary"],
        "publish_hint": "Schedule 2–4h before your audience peak (Analytics → Audience). "
                        "Pinned comment + community post + end screen within the first hour. "
                        "Do not change title/thumbnail in the first 24h.",
    }
    (out_dir / "metadata.json").write_text(json.dumps(pack, indent=2), encoding="utf-8")

    md = [
        f"# Metadata pack — {doc.title}",
        "",
        "## Title (human decision — spec: 55–65 visible chars, keyword first 5 words)",
        f"`{doc.title}` ({len(doc.title)} chars)",
    ]
    md += [f"- ⚠ {w}" for w in pack["title_report"]["warnings"]]
    if len(pack["title_report"]["ab_variants"]) > 1:
        md += ["", "### A/B variants for Studio Test & Compare",
               *[f"- {v}" for v in pack["title_report"]["ab_variants"]]]
    md += [
        "", "## Description (copy into Studio)", "", "```", pack["description"], "```",
        "", "## Tags (500 char budget)", ", ".join(pack["tags"]),
        "", "## Chapters", format_chapters(chapters),
        "", "## Publish ritual", pack["publish_hint"],
    ]
    (out_dir / "metadata.md").write_text("\n".join(md), encoding="utf-8")
    return pack
