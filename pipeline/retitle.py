"""A new title for a long-form nobody has watched.

Measured on 13 November 2026: 35 of 95 long-forms had no views at all and the
median had one (docs/GROWTH_EVIDENCE_2026-11-14.md). Most carry the older title
form, "Psalm 23:5 Provision Prayer | The Provision Table", which names the
passage and the channel and not the reason a person would search for it. Since
14 November queued long-forms lead with the need ("Prayer Before a Big
Decision: Proverbs 15:22 | The Guided Path"); the ones already published kept
the titles they went out with.

This module decides which published long-forms get a new title and checks the
title a model proposes. It does not write to YouTube. The new title is stamped
into the video's receipt with ``metadata_revision`` reset; the monitor's
existing metadata sync (``scripts/retrofit_published_metadata.py``, every three
hours) pushes the receipt's title, description, tags and translations to the
live video. One write path to YouTube, not two.

Rules:

* long-forms only; a Short's title is not the reason it is or is not watched;
* at least ``MIN_AGE_DAYS`` old and at most ``MAX_VIEWS`` views in the latest
  public snapshot: a video with an audience keeps the title that found it;
* once per video, ever (``retitled_at`` in the receipt);
* at most ``MAX_PER_RUN`` per channel per day (a title change costs about 50
  units of YouTube quota when the monitor pushes it);
* the scripture reference stays in the title, word for word.

Whether a new title brings views is not known. The first retitled videos are the
test; ``title_before`` in each receipt keeps what it was.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

MIN_AGE_DAYS = 7
MAX_VIEWS = 2
MAX_PER_RUN = 2
MIN_TITLE_CHARS = 35
MAX_TITLE_CHARS = 70
PENDING_REVISION = "retitle-pending"

#: Words a prayer title does not use: a promised outcome, or bait.
BANNED = (
    "guaranteed", "instantly", "instant", "miracle", "miracles", "secret", "shocking",
    "must watch", "don't skip", "do not skip", "100%", "powerful", "most powerful",
    "breakthrough tonight", "will heal", "cures", "cure", "you won't believe", "viral",
)


@dataclass
class Target:
    path: Path
    video_id: str
    title: str
    reference: str
    channel: str
    views: int
    age_days: int
    context: str = ""


def _published(meta: dict) -> date | None:
    for key in ("published_at", "published_on"):
        value = str(meta.get(key) or "").strip()
        if not value:
            continue
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                continue
    return None


def _pinned_title_ids() -> set[str]:
    try:
        from scripts.retrofit_published_metadata import TITLE_FIXES
        return set(TITLE_FIXES)
    except Exception:  # noqa: BLE001
        return set()


def latest_views(snapshots: list[dict]) -> dict[str, int]:
    """``{video_id: views}`` from each video's most recent snapshot row that has a view count."""
    latest: dict[str, tuple[str, int]] = {}
    for row in snapshots:
        vid = str(row.get("video_id") or "")
        views = row.get("views")
        if not vid or views in (None, ""):
            continue
        stamp = str(row.get("snapshot_date") or "")
        if vid not in latest or stamp >= latest[vid][0]:
            latest[vid] = (stamp, int(views))
    return {vid: views for vid, (_, views) in latest.items()}


def find_targets(channel_id: str, snapshots: list[dict], *, published_dir: Path | None = None,
                 today: date | None = None, limit: int = MAX_PER_RUN) -> list[Target]:
    """This channel's long-forms that are old enough, unwatched and never retitled: oldest first."""
    from .channels import channel_for_doc, normalize_channel_id
    from .config import PUBLISHED_DIR
    from .gemini_brain import extract_scripture_reference
    from .script_doc import parse_script
    from .scripture_text import exists as scripture_exists

    wanted = normalize_channel_id(channel_id)
    today = today or datetime.now(timezone.utc).date()
    views = latest_views(snapshots)
    found: list[Target] = []
    for path in sorted(Path(published_dir or PUBLISHED_DIR).glob("*.md")):
        if path.name.startswith("short-"):
            continue
        try:
            doc = parse_script(path)
        except Exception:  # noqa: BLE001
            continue
        meta = doc.meta
        if doc.format == "short" or normalize_channel_id(channel_for_doc(meta)) != wanted:
            continue
        if "faith" not in str(meta.get("niche") or "").lower():
            continue
        video_id = str(meta.get("youtube_video_id") or "").strip()
        if not video_id or video_id not in views:
            continue  # no public reading for it: nothing is known, nothing is changed
        if meta.get("retitled_at") or meta.get("receipt_recovered_from_youtube"):
            continue
        if str(doc.id) in _pinned_title_ids():
            continue  # the metadata sync holds a fixed title for this video
        if str(meta.get("youtube_status") or "") == "deleted_or_missing":
            continue
        published = _published(meta)
        if published is None:
            continue
        age = (today - published).days
        if age < MIN_AGE_DAYS or views[video_id] > MAX_VIEWS:
            continue
        reference = extract_scripture_reference(doc)
        if (not reference or not scripture_exists(reference)
                or reference.lower() not in str(doc.title).lower().replace("–", "-")):
            continue  # the title names no passage we can keep
        context = " ".join(str(meta.get(key) or "") for key in ("seo_hook", "thumb_text")).strip()
        found.append(Target(path, video_id, str(doc.title), reference, wanted,
                            views[video_id], age, context[:400]))
    found.sort(key=lambda target: -target.age_days)
    return found[:limit]


def title_problems(title: str, reference: str, channel_name: str, old_title: str) -> list[str]:
    """Why a proposed title is refused; empty when it may be used."""
    problems: list[str] = []
    text = " ".join(str(title or "").replace("–", "-").split())
    if text != str(title or ""):
        problems.append("title has stray whitespace or a dash that is not a hyphen")
    if not MIN_TITLE_CHARS <= len(text) <= MAX_TITLE_CHARS:
        problems.append(f"title is {len(text)} characters; it must be "
                        f"{MIN_TITLE_CHARS}-{MAX_TITLE_CHARS}")
    form = re.fullmatch(
        rf"(?P<need>[^:|]+): {re.escape(reference)}(?: \| {re.escape(channel_name)})?", text)
    if not form:
        problems.append(f"title must read '<need or promise>: {reference}' with an optional "
                        f"' | {channel_name}' after it")
        return problems
    need = form.group("need").strip()
    if len(need.split()) < 3:
        problems.append("the part before the colon must say the need in at least three words")
    if re.search(r"\d", need):
        problems.append("the need must not contain digits")
    if re.search(r"[!?#*\"]", need):
        problems.append("no exclamation marks, question marks, hashtags or quotation marks")
    if any(len(word) > 3 and word.isupper() for word in need.split()):
        problems.append("no words in capitals")
    lowered = f" {need.lower()} "
    for banned in BANNED:
        if f" {banned} " in lowered or (" " in banned and banned in lowered):
            problems.append(f"'{banned}' is not used in a prayer title")
    if text.lower() == " ".join(str(old_title or "").split()).lower():
        problems.append("the new title is the old title")
    return problems


def build_prompt(target: Target, channel_name: str, rejected: str = "") -> str:
    examples = (
        "Night Prayer When Dread Keeps You Awake: 2 Timothy 1:7",
        "Prayer Before a Big Decision: Proverbs 15:22 | The Guided Path",
        "Believing God for Your Family: Acts 16:31-34 | The Family Altar",
        "Midday Prayer for Strength at Work: Colossians 3:23-24",
    )
    return (
        f"A prayer video on the YouTube channel \"{channel_name}\" has had almost no views "
        f"under this title:\n  {target.title}\n\n"
        f"It is a narrated prayer on {target.reference}."
        + (f" What it is about: {target.context}\n" if target.context else "\n")
        + "\nWrite ONE new title that leads with the need or the moment a person would be in "
        "when they search for this prayer, in the plain words they would type.\n\n"
        f"The title must read exactly:  <need or promise>: {target.reference}\n"
        f"and may end with:  | {channel_name}\n"
        f"- {MIN_TITLE_CHARS} to {MAX_TITLE_CHARS} characters in all. Leave the channel name "
        "off if it does not fit.\n"
        "- The need is three words or more, in Title Case, with no digits, no capitals for "
        "emphasis, no question or exclamation marks.\n"
        "- Honest: no promised outcome, no 'miracle', 'powerful', 'guaranteed' or 'secret'.\n"
        f"- Keep the reference exactly as written: {target.reference}\n\n"
        "Titles in this form on the same channels:\n"
        + "".join(f"  {example}\n" for example in examples)
        + (f"\nYour last answer was refused: {rejected}\n" if rejected else "")
        + "\nReturn the title alone on one line, with nothing before or after it."
    )


def propose_title(target: Target, channel_name: str, ask: Callable[[str], str],
                  attempts: int = 2) -> tuple[str | None, str]:
    """Ask for a title until one passes: ``(title, "")`` or ``(None, why)``."""
    rejected = ""
    for _ in range(attempts):
        try:
            answer = ask(build_prompt(target, channel_name, rejected)) or ""
        except Exception as exc:  # noqa: BLE001
            return None, f"model unavailable: {str(exc)[:120]}"
        lines = [line.strip().strip("`\"'") for line in answer.splitlines() if line.strip()]
        if not lines:
            rejected = "no title was returned"
            continue
        title = " ".join(lines[0].replace("–", "-").split())
        problems = title_problems(title, target.reference, channel_name, target.title)
        if not problems:
            return title, ""
        rejected = "; ".join(problems[:3])
    return None, rejected or "no usable title"


def apply_ledger_entry(path: Path, entry: dict) -> str:
    """Stamp one new title into its receipt: ``"stamped"`` or the reason it was left alone.

    The receipt is re-read here, from the tree it will be committed on, and is
    left untouched when its title is no longer the one the new title was written
    for, or when the edit would not read back as the new title.
    """
    from scripts.sync_published_thumbnails import stamp_frontmatter_field

    from .script_doc import parse_script

    if not path.is_file():
        return "receipt not found"
    original = path.read_text(encoding="utf-8")
    try:
        doc = parse_script(path)
    except Exception as exc:  # noqa: BLE001
        return f"unreadable receipt: {exc}"
    if doc.meta.get("retitled_at"):
        return "already retitled"
    if " ".join(str(doc.title).split()) != " ".join(str(entry["old_title"]).split()):
        return "title changed since the new one was written"
    try:
        stamp_frontmatter_field(path, "title", entry["new_title"])
        stamp_frontmatter_field(path, "title_before", entry["old_title"])
        stamp_frontmatter_field(path, "retitled_at", entry["date"])
        stamp_frontmatter_field(path, "retitle_reason",
                                f"unwatched after {MIN_AGE_DAYS} days or more")
        stamp_frontmatter_field(path, "metadata_revision", PENDING_REVISION)
        check = parse_script(path)
        if str(check.title) != entry["new_title"] or check.meta.get("title_before") != entry["old_title"]:
            raise ValueError("the edited receipt does not read back as the new title")
    except Exception as exc:  # noqa: BLE001
        path.write_text(original, encoding="utf-8")
        return f"not stamped: {exc}"
    return "stamped"
