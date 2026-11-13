"""Generate ``docs/network-state.json`` for the GitHub Pages 3-channel dashboard.

Reads canonical state from ``content/published/``, ``content/queue/``,
``content/shorts-queue/``, ``content/monitor/status.json``, and per-channel
``content/research/<feedback_artifact_name>`` using ``pipeline.channels`` and
``pipeline.channel_capabilities`` (zero hardcoded channel IDs).

Includes a material-change write guard so volatile timestamps and relative age
strings (``"last success 0.2h ago"``) never trigger empty Git commits.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from pipeline.channel_capabilities import capabilities_for, known_channels
from pipeline.channels import CHANNELS, DEFAULT_CHANNEL_ID, normalize_channel_id

REPO = Path(__file__).resolve().parents[1]
_AGE_DRIFT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:s|sec|m|min|h|hr|d|day)s?\s+ago\b", re.IGNORECASE)


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:  # noqa: BLE001
        meta = {}
    return (meta if isinstance(meta, dict) else {}), parts[2]


def _word_count(body: str) -> int:
    lines = [
        ln.strip()
        for ln in body.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    return len(" ".join(lines).split())


def _clean_tagline(producer_line: str, display_name: str) -> str:
    cleaned = producer_line.strip().rstrip(".")
    if "|" in cleaned:
        return cleaned.split("|", 1)[1].strip()
    prefix = f"Produced by {display_name}"
    if cleaned.startswith(prefix):
        cleaned = cleaned[len(prefix) :].lstrip(" —-|:")
    return cleaned or display_name


def _duration_label(fmt: str, meta: dict[str, Any], body: str) -> str:
    dur_sec = meta.get("duration_seconds")
    if isinstance(dur_sec, (int, float)) and dur_sec > 0:
        sec = int(round(float(dur_sec)))
        return f"{sec}s" if sec < 90 else f"{sec // 60}m {sec % 60:02d}s"
    if fmt == "short":
        return "<60s"
    words = _word_count(body)
    if words > 0:
        mins = max(1, round(words / 145))
        return f"~{mins} min"
    target = meta.get("target_minutes")
    if isinstance(target, (int, float)) and target > 0:
        return f"~{int(target)} min"
    return "Long-form"


def _load_published(repo_root: Path) -> list[dict[str, Any]]:
    pub_dir = repo_root / "content" / "published"
    if not pub_dir.is_dir():
        return []
    videos: list[dict[str, Any]] = []
    for md in sorted(pub_dir.glob("*.md")):
        try:
            raw = md.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _split_frontmatter(raw)
        if not meta:
            continue
        ch_id = normalize_channel_id(meta.get("channel") or DEFAULT_CHANNEL_ID)
        profile = CHANNELS.get(ch_id) or CHANNELS[DEFAULT_CHANNEL_ID]
        fmt_raw = str(meta.get("format") or "").strip().lower()
        is_short = fmt_raw == "short" or md.name.startswith("short-")
        fmt = "short" if is_short else "longform"
        vid = str(meta.get("youtube_video_id") or "").strip()
        privacy = str(
            meta.get("privacy") or meta.get("privacy_status") or profile.default_privacy
        ).strip().lower()
        if meta.get("scheduled_publish") is True:
            # Uploaded private with a publish time: `published_at` is when it
            # goes public, and until then the link opens a private video.
            privacy = "scheduled"
        published_at = str(meta.get("published_at") or "").strip()
        published_on = str(meta.get("published_on") or "").strip()
        if not published_on and len(published_at) >= 10:
            published_on = published_at[:10]
        watch_url = str(meta.get("youtube_watch_url") or "").strip() or (
            f"https://youtu.be/{vid}" if vid else ""
        )
        shorts_url = str(meta.get("youtube_shorts_url") or "").strip() or (
            f"https://www.youtube.com/shorts/{vid}" if (vid and is_short) else ""
        )
        studio_url = str(meta.get("youtube_studio_url") or "").strip() or (
            f"https://studio.youtube.com/video/{vid}/edit" if vid else ""
        )
        thumb_url = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""
        poster_lines = meta.get("thumbnail_poster")
        thumb_text = str(meta.get("thumb_text") or "").strip()
        if not thumb_text and isinstance(poster_lines, list) and poster_lines:
            thumb_text = " · ".join(str(x) for x in poster_lines[:2] if x)
        videos.append(
            {
                "id": str(meta.get("id") or md.stem).strip(),
                "slug": str(meta.get("slug") or md.stem).strip(),
                "file": md.name,
                "title": str(meta.get("title") or md.stem).strip(),
                "channel": ch_id,
                "channel_name": profile.display_name,
                "channel_handle": profile.handle,
                "format": fmt,
                "niche": str(meta.get("niche") or "faith and prayer").strip(),
                "privacy": privacy,
                "published_on": published_on,
                "published_at": published_at,
                "youtube_video_id": vid,
                "watch_url": shorts_url if is_short and shorts_url else watch_url,
                "youtu_be_url": watch_url,
                "shorts_url": shorts_url,
                "studio_url": studio_url,
                "thumb_url": thumb_url,
                "thumb_text": thumb_text,
                "thumbnail_pending": meta.get("thumbnail_pending") is True,
                "duration_label": _duration_label(fmt, meta, body),
                "words": _word_count(body),
            }
        )
    videos.sort(
        key=lambda item: (
            item["published_at"] or (item["published_on"] + "T00:00:00Z" if item["published_on"] else ""),
            item["id"],
        ),
        reverse=True,
    )
    return videos


def _load_longform_queue(repo_root: Path) -> list[dict[str, Any]]:
    q_dir = repo_root / "content" / "queue"
    if not q_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for md in sorted(q_dir.glob("*.md")):
        try:
            raw = md.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _split_frontmatter(raw)
        if not meta:
            continue
        ch_id = normalize_channel_id(meta.get("channel") or DEFAULT_CHANNEL_ID)
        profile = CHANNELS.get(ch_id) or CHANNELS[DEFAULT_CHANNEL_ID]
        niche = str(meta.get("niche") or "").strip().lower()
        status = str(meta.get("status") or "draft").strip().lower()
        rows.append(
            {
                "id": str(meta.get("id") or md.stem[:4]).strip(),
                "slug": str(meta.get("slug") or md.stem).strip(),
                "file": md.name,
                "title": str(meta.get("title") or md.stem).strip(),
                "channel": ch_id,
                "channel_name": profile.display_name,
                "status": status,
                "niche": niche,
                "publishable": status in {"approved", "quota_paused"} and "faith" in niche,
                "target_minutes": int(meta.get("target_minutes") or 6),
                "words": _word_count(body),
            }
        )
    return rows


def _load_shorts_queue(repo_root: Path) -> list[dict[str, Any]]:
    sq_dir = repo_root / "content" / "shorts-queue"
    if not sq_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for yml in sorted(sq_dir.glob("*.yml")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue
        ch_id = normalize_channel_id(data.get("channel") or DEFAULT_CHANNEL_ID)
        profile = CHANNELS.get(ch_id) or CHANNELS[DEFAULT_CHANNEL_ID]
        status = str(data.get("status") or "draft").strip().lower()
        target = data.get("target_window_utc")
        # YAML 1.1 interprets an unquoted 18:44 as the integer 1124. Never
        # display that number as a time or guess an invalid value.
        if not isinstance(target, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", target):
            target = ""
        rows.append(
            {
                "short": str(data.get("short") or yml.stem).strip(),
                "file": yml.name,
                "companion_longform_id": str(data.get("companion_longform_id") or "").strip(),
                "scripture": str(data.get("scripture") or "").strip(),
                "channel": ch_id,
                "channel_name": profile.display_name,
                "status": status,
                "publishable": status in {"approved", "quota_paused"} and bool(data.get("renderer_ready", True)),
                "target_window_utc": target,
            }
        )
    return rows


def _load_feedback(repo_root: Path, artifact_name: str) -> dict[str, Any]:
    path = repo_root / "content" / "research" / artifact_name
    if not path.is_file():
        return {"available": False, "measured_longform_videos": 0, "top_themes": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"available": False, "measured_longform_videos": 0, "top_themes": []}
    themes = data.get("themes") if isinstance(data.get("themes"), list) else []
    top_themes = [
        {
            "theme": str(t.get("theme") or ""),
            "videos": int(t.get("videos") or 0),
            "top_scripture": str(t.get("top_scripture") or ""),
        }
        for t in themes[:3]
        if isinstance(t, dict)
    ]
    return {
        "available": True,
        "as_of": str(data.get("as_of") or ""),
        "measured_longform_videos": int(data.get("measured_longform_videos") or 0),
        "total_longform_videos": int(data.get("total_longform_videos") or 0),
        "top_themes": top_themes,
    }


def _load_automations(repo_root: Path) -> tuple[bool, list[dict[str, Any]], str]:
    status_path = repo_root / "content" / "monitor" / "status.json"
    if not status_path.is_file():
        return False, [], ""
    try:
        raw = json.loads(status_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return False, [], ""
    except Exception:  # noqa: BLE001
        return False, [], ""
    healthy = raw.get("healthy") is True
    items: list[dict[str, Any]] = []
    for row in raw.get("automations") or []:
        if not isinstance(row, dict):
            continue
        items.append(
            {
                "workflow": str(row.get("workflow") or ""),
                "name": str(row.get("name") or row.get("workflow") or ""),
                "verdict": str(row.get("verdict") or "OK"),
                "severity": str(row.get("severity") or "ok"),
                "detail": str(row.get("detail") or ""),
                "last_conclusion": str(row.get("last_conclusion") or ""),
                "last_run": str(row.get("last_run") or ""),
                "last_success": str(row.get("last_success") or ""),
                "runs_14d": int(row.get("runs_14d") or 0),
                "missed_slots": int(row.get("missed_slots") or 0),
                "failures_5": int(row.get("failures_5") or 0),
                "effect": str(row.get("effect") or ""),
            }
        )
    return healthy, items, str(raw.get("generated_at") or "")


def build_network_state(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or REPO
    videos = _load_published(root)
    lf_queue = _load_longform_queue(root)
    sh_queue = _load_shorts_queue(root)
    healthy, automations, monitor_generated_at = _load_automations(root)

    channels_out: list[dict[str, Any]] = []
    for ch_id in known_channels():
        profile = CHANNELS[ch_id]
        caps = capabilities_for(ch_id)
        brand = caps.brand
        ch_videos = [v for v in videos if v["channel"] == ch_id]
        ch_lf_pub = [v for v in ch_videos if v["format"] == "longform"]
        ch_sh_pub = [v for v in ch_videos if v["format"] == "short"]
        ch_public = [v for v in ch_videos if v["privacy"] == "public"]
        ch_lf_q_ready = [q for q in lf_queue if q["channel"] == ch_id and q["publishable"]]
        ch_lf_q_other = [q for q in lf_queue if q["channel"] == ch_id and not q["publishable"]]
        ch_sh_q_ready = [s for s in sh_queue if s["channel"] == ch_id and s["publishable"]]
        latest = ch_videos[0] if ch_videos else None
        next_lf = ch_lf_q_ready[0] if ch_lf_q_ready else None
        next_sh = ch_sh_q_ready[0] if ch_sh_q_ready else None

        channels_out.append(
            {
                "id": ch_id,
                "display_name": profile.display_name,
                "handle": profile.handle,
                "prayer_label": brand.longform_prayer_label,
                "daypart": brand.short_prayer_kind,
                "tagline": _clean_tagline(brand.producer_line, profile.display_name),
                "target_window_utc": brand.short_target_window_utc,
                "poster_kicker": brand.shorts_poster_kicker,
                "provisioned": profile.provisioned,
                "auto_publish": profile.auto_publish,
                "default_privacy": profile.default_privacy,
                "supply_target": caps.supply_min_publishable,
                "counts": {
                    "published_total": len(ch_videos),
                    "published_longform": len(ch_lf_pub),
                    "published_shorts": len(ch_sh_pub),
                    "thumbnail_pending": sum(1 for video in ch_videos if video["thumbnail_pending"]),
                    "public_total": len(ch_public),
                    "queued_longform": len(ch_lf_q_ready),
                    "queued_other": len(ch_lf_q_other),
                    "queued_shorts": len(ch_sh_q_ready),
                },
                "latest_video": (
                    {
                        "id": latest["id"],
                        "title": latest["title"],
                        "format": latest["format"],
                        "youtube_video_id": latest["youtube_video_id"],
                        "watch_url": latest["watch_url"],
                        "published_on": latest["published_on"],
                        "published_at": latest["published_at"],
                    }
                    if latest
                    else None
                ),
                "next_queued_longform": (
                    {
                        "id": next_lf["id"],
                        "title": next_lf["title"],
                        "words": next_lf["words"],
                        "status": next_lf["status"],
                    }
                    if next_lf
                    else None
                ),
                "next_queued_short": (
                    {
                        "short": next_sh["short"],
                        "scripture": next_sh["scripture"],
                        "target_window_utc": next_sh["target_window_utc"],
                        "status": next_sh["status"],
                    }
                    if next_sh
                    else None
                ),
                "feedback": _load_feedback(root, brand.feedback_artifact_name),
            }
        )

    pub_lf_total = sum(1 for v in videos if v["format"] == "longform")
    pub_sh_total = sum(1 for v in videos if v["format"] == "short")
    public_total = sum(1 for v in videos if v["privacy"] == "public")
    q_lf_ready = [q for q in lf_queue if q["publishable"]]
    q_sh_ready = [s for s in sh_queue if s["publishable"]]
    auto_ok = sum(1 for a in automations if a["severity"] == "ok")

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "monitor_generated_at": monitor_generated_at,
        "cost_lock": {
            "monthly_cost_usd": 0.0,
            "paid_tiers": 0,
            "channels_provisioned": sum(1 for c in channels_out if c["provisioned"]),
            "channels_total": len(channels_out),
        },
        "totals": {
            "published_total": len(videos),
            "published_longform": pub_lf_total,
            "published_shorts": pub_sh_total,
            "public_total": public_total,
            "queued_longform": len(q_lf_ready),
            "queued_shorts": len(q_sh_ready),
            "automations_ok": auto_ok,
            "automations_total": len(automations),
            "network_healthy": healthy,
        },
        "channels": channels_out,
        "videos": videos,
        "queues": {
            "longform": q_lf_ready,
            "shorts": q_sh_ready,
        },
        "automations": automations,
    }


def material_fingerprint(payload: dict[str, Any]) -> str:
    """Canonical JSON excluding volatile timestamps and relative age-drift text."""
    clone = copy.deepcopy(payload)
    clone.pop("generated_at", None)
    for item in clone.get("automations") or []:
        if isinstance(item, dict) and isinstance(item.get("detail"), str):
            item["detail"] = _AGE_DRIFT_RE.sub("<age>", item["detail"])
    return json.dumps(clone, sort_keys=True, ensure_ascii=True)


def write_network_state(
    out_path: Path | None = None,
    *,
    repo_root: Path | None = None,
    force: bool = False,
) -> bool:
    """Write ``docs/network-state.json`` only if material state changed. Returns True if written."""
    root = repo_root or REPO
    target = out_path or (root / "docs" / "network-state.json")
    new_payload = build_network_state(root)
    if not force and target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and (
                material_fingerprint(existing) == material_fingerprint(new_payload)
            ):
                return False
        except Exception:  # noqa: BLE001
            pass
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(new_payload, indent=2) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    out_path = args.out or (args.repo_root / "docs" / "network-state.json")
    wrote = write_network_state(out_path, repo_root=args.repo_root, force=args.force)
    status = "updated" if wrote else "unchanged (material state identical)"
    print(f"[dashboard] {out_path}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
