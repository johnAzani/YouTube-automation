"""Set up each channel's page: search keywords, a trailer for visitors, home-page shelves.

Before 14 November 2026 nothing in the studio touched a channel's page. A new
visitor to The Family Altar found a default page with no keywords for search,
no video offered to them, and the uploads in one row.

Three things are set, each only where the page has nothing of its own:

* **Keywords** (``brandingSettings.channel.keywords``): the channel's search
  phrases from its brand. Left alone when any keywords are already there.
* **Trailer for people who are not subscribed**
  (``brandingSettings.channel.unsubscribedTrailer``): the channel's most watched
  long-form in the latest public snapshot. Left alone when any trailer is set.
* **Home-page shelves** (``channelSections``): "popular uploads", then one shelf
  per series playlist of the channel that has videos in it. A shelf that exists
  is never moved, changed or removed; missing ones are added after the existing
  ones, up to YouTube's limit of ten.

What the code will not do: change a channel's name, description, country,
language, banner or picture; delete or reorder a shelf; touch anything a person
set by hand.

``channels.update`` replaces the whole ``brandingSettings`` part: every setting
left out of the request is erased. ``plan`` therefore starts from the settings
YouTube returned and changes only the two fields above, and ``apply`` refuses to
write a request that has lost the channel's title.

Cost: three one-unit reads a day; each write is 50 units and happens once.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

MAX_SECTIONS = 10
MAX_KEYWORD_CHARS = 450
MAX_PLAYLIST_SHELVES = 3


@dataclass
class Plan:
    """What ``apply`` will send. Empty lists and ``None`` mean nothing to do."""
    branding: dict | None = None
    sections: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.branding is None and not self.sections


def keyword_string(phrases: tuple[str, ...] | list[str]) -> str:
    """YouTube's keyword format: space-separated, a phrase of several words in double quotes."""
    out: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        clean = " ".join(str(phrase).replace('"', "").split())
        if not clean or clean.lower() in seen:
            continue
        token = f'"{clean}"' if " " in clean else clean
        if len(" ".join(out + [token])) > MAX_KEYWORD_CHARS:
            break
        seen.add(clean.lower())
        out.append(token)
    return " ".join(out)


def choose_trailer(longforms: list[dict]) -> str:
    """The most watched long-form; the newest when none has been watched. ``""`` when there is none.

    ``longforms``: ``{"video_id", "views", "published"}`` for this channel's public long-forms.
    """
    usable = [row for row in longforms if row.get("video_id")]
    if not usable:
        return ""
    best = max(usable, key=lambda row: (int(row.get("views") or 0), str(row.get("published") or "")))
    return str(best["video_id"])


def plan(channel: dict, sections: list[dict], *, keywords: tuple[str, ...] | list[str],
         longforms: list[dict], playlists: list[dict]) -> Plan:
    """Work out what the page lacks. Pure: no API call.

    ``channel``: the ``channels.list(part="brandingSettings")`` item.
    ``sections``: ``channelSections.list(part="snippet,contentDetails")`` items.
    ``playlists``: ``{"id", "items"}`` for the channel's series playlists, in shelf order.
    """
    result = Plan()
    settings = copy.deepcopy((channel.get("brandingSettings") or {}))
    page = settings.setdefault("channel", {})
    changed = False

    if str(page.get("keywords") or "").strip():
        result.notes.append("keywords: already set, left alone")
    else:
        wanted = keyword_string(keywords)
        if wanted:
            page["keywords"] = wanted
            changed = True
            result.notes.append(f"keywords: set ({len(wanted)} characters)")

    own_videos = {str(row.get("video_id")) for row in longforms if row.get("video_id")}
    current_trailer = str(page.get("unsubscribedTrailer") or "").strip()
    if current_trailer:
        result.notes.append("trailer: already set, left alone")
    else:
        trailer = choose_trailer(longforms)
        if trailer:
            page["unsubscribedTrailer"] = trailer
            changed = True
            result.notes.append(f"trailer: {trailer}")
        else:
            result.notes.append("trailer: no public long-form to offer yet")

    if changed:
        result.branding = settings

    kinds = {str((row.get("snippet") or {}).get("type") or "") for row in sections}
    shelved = {pid for row in sections
               for pid in ((row.get("contentDetails") or {}).get("playlists") or [])}
    room = MAX_SECTIONS - len(sections)
    position = max([int((row.get("snippet") or {}).get("position") or 0) for row in sections],
                   default=-1) + 1
    wanted_sections: list[dict] = []
    if "popularUploads" not in kinds and own_videos:
        wanted_sections.append({"snippet": {"type": "popularUploads"}})
    for playlist in playlists[:MAX_PLAYLIST_SHELVES]:
        pid = str(playlist.get("id") or "")
        if pid and pid not in shelved and int(playlist.get("items") or 0) > 0:
            wanted_sections.append({"snippet": {"type": "singlePlaylist"},
                                    "contentDetails": {"playlists": [pid]}})
    for body in wanted_sections[:max(0, room)]:
        body["snippet"]["position"] = position
        position += 1
        result.sections.append(body)
    if len(wanted_sections) > max(0, room):
        result.notes.append("shelves: the page is at YouTube's limit of ten; some were not added")
    result.notes.append(f"shelves: {len(result.sections)} to add, {len(sections)} already there")
    return result


def apply(youtube: Any, channel: dict, changes: Plan) -> list[str]:
    """Send the plan. Each write stands alone: one refusal does not stop the others."""
    done: list[str] = []
    if changes.branding is not None:
        before = ((channel.get("brandingSettings") or {}).get("channel") or {})
        after = changes.branding.get("channel") or {}
        lost = [key for key in ("title", "description", "country", "defaultLanguage")
                if before.get(key) and after.get(key) != before.get(key)]
        if lost or not channel.get("id"):
            done.append(f"branding NOT written: the request would change {lost or 'an unknown channel'}")
        else:
            try:
                youtube.channels().update(
                    part="brandingSettings",
                    body={"id": channel["id"], "brandingSettings": changes.branding},
                ).execute()
                done.append("branding written")
            except Exception as exc:  # noqa: BLE001
                done.append(f"branding refused: {str(exc)[:160]}")
    for body in changes.sections:
        label = body["snippet"]["type"]
        try:
            youtube.channelSections().insert(part="snippet,contentDetails", body=body).execute()
            done.append(f"shelf added: {label}")
        except Exception as exc:  # noqa: BLE001
            done.append(f"shelf refused ({label}): {str(exc)[:160]}")
    return done


def read_page(youtube: Any) -> tuple[dict, list[dict]]:
    """The authenticated channel's branding settings and its home-page shelves."""
    channels = youtube.channels().list(part="brandingSettings", mine=True).execute().get("items") or []
    if not channels:
        raise RuntimeError("YouTube returned no channel for these credentials")
    channel = channels[0]
    sections = (youtube.channelSections()
                .list(part="snippet,contentDetails", channelId=channel["id"]).execute().get("items") or [])
    return channel, sections
