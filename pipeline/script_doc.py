"""Parse a video job from a markdown file with YAML frontmatter.

Example file: content/queue/0001-the-canal-that-broke-a-city.md

---
id: "0001"
title: "..."
slug: the-canal-that-broke-a-city
status: draft            # draft | approved | published
format: longform         # longform | short
niche: history
voice: en-US-ChristopherNeural
target_minutes: 8
tags: [history, engineering, disasters]
thumb_text: "THE CANAL THAT BROKE A CITY"
asset_queries:
  - "old canal construction"
  - "flood city street"
originality:
  original_thesis: true
  unique_structure: true
  human_rewrite: true
  no_ai_persona: true
  source_notes: true
  ai_disclosure: false
---

## Scene 1 — The hook
Narration text...

## Scene 2 — ...
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - PyYAML is in requirements.txt
    yaml = None


@dataclass
class Scene:
    index: int
    heading: str
    narration: str
    asset_query: str = ""


@dataclass
class ScriptDoc:
    path: Path
    meta: dict
    scenes: list[Scene] = field(default_factory=list)

    # -- convenience accessors -------------------------------------------
    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.path.stem.split("-")[0]))

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.path.stem))

    @property
    def slug(self) -> str:
        return str(self.meta.get("slug", self.path.stem))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", "draft")).lower()

    @property
    def format(self) -> str:
        return str(self.meta.get("format", "longform")).lower()

    @property
    def voice(self) -> str:
        return str(self.meta.get("voice", ""))

    @property
    def full_narration(self) -> str:
        return "\n".join(s.narration for s in self.scenes).strip()

    @property
    def word_count(self) -> int:
        return len(self.full_narration.split())

    @property
    def description(self) -> str:
        return str(self.meta.get("description", "")).strip()

    @property
    def tags(self) -> list[str]:
        raw = self.meta.get("tags", [])
        return [str(t) for t in raw] if isinstance(raw, list) else []

    @property
    def thumb_text(self) -> str:
        return str(self.meta.get("thumb_text", self.title)).strip()


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.S)
_SCENE_RE = re.compile(r"^##\s+(?:Scene\s+(\d+)\s*[—\-–:]\s*)?(.+?)\s*$", re.M)


def parse_script(path: Path) -> ScriptDoc:
    text = Path(path).read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path}: missing YAML frontmatter delimited by ---")
    raw_meta, body = m.group(1), m.group(2)

    if yaml is not None:
        meta = yaml.safe_load(raw_meta) or {}
    else:  # minimal fallback: flat "key: value" lines
        meta = {}
        for line in raw_meta.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")

    # Split body into scenes on "## Scene N — Heading" (or plain "## Heading")
    splits = list(_SCENE_RE.finditer(body))
    scenes: list[Scene] = []
    if splits:
        for i, sm in enumerate(splits):
            start = sm.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(body)
            narration = body[start:end].strip()
            heading = sm.group(2).strip()
            idx = int(sm.group(1)) if sm.group(1) else i + 1
            scenes.append(Scene(index=idx, heading=heading, narration=narration))
    else:
        narration = body.strip()
        if narration:
            scenes.append(Scene(index=1, heading="Main", narration=narration))

    # Attach per-scene asset queries if provided
    queries = meta.get("asset_queries", []) or []
    if isinstance(queries, list):
        for i, sc in enumerate(scenes):
            if i < len(queries):
                sc.asset_query = str(queries[i])

    if not scenes:
        raise ValueError(f"{path}: no narration scenes found")
    return ScriptDoc(path=Path(path), meta=meta, scenes=scenes)
