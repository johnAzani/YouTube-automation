"""Channel registry — one automation codebase, several YouTube channels.

Each channel keeps its **own** Google Cloud project, YouTube Data API quota
pool (10,000 units/day), Gemini free-tier pool, OAuth client and refresh
token. Channels never share credentials: a token minted for one channel
uploads to that channel only, so credentials are selected per channel and
never mixed.

Secret naming convention (GitHub Actions secrets):

  Channel 1 (``secret-place``) keeps the original unprefixed names
  (``YOUTUBE_CLIENT_ID`` ...) so existing production runs are untouched.
  Every later channel uses its ``secret_prefix``::

      PRAYER2_YOUTUBE_CLIENT_ID
      PRAYER2_YOUTUBE_CLIENT_SECRET
      PRAYER2_YOUTUBE_REFRESH_TOKEN
      PRAYER2_YOUTUBE_PLAYLIST_ID      (optional)
      PRAYER2_GEMINI_API_KEY
      PRAYER2_AUTO_PUBLISH             (optional; prayer2 stays private)

Workflows map the selected channel's secrets onto the canonical env names
(``YOUTUBE_CLIENT_ID`` etc.) before any pipeline code runs, so the pipeline
itself always reads one consistent set of variables. ``CHANNEL_ID`` records
which channel a run belongs to and drives queue routing: a script declares
its channel in frontmatter (``channel: prayer2``; absent = ``secret-place``)
and a run only ever picks up its own channel's scripts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_CHANNEL_ID = "secret-place"


@dataclass(frozen=True)
class ChannelProfile:
    id: str
    display_name: str
    handle: str
    secret_prefix: str  # "" for channel 1, e.g. "PRAYER2_" afterwards
    default_privacy: str
    auto_publish: bool
    include_sanctuary_links: bool  # Selar/store links belong to channel 1 only

    def secret_name(self, base: str) -> str:
        return f"{self.secret_prefix}{base}"

    def secret_names(self) -> dict[str, str]:
        return {
            "client_id": self.secret_name("YOUTUBE_CLIENT_ID"),
            "client_secret": self.secret_name("YOUTUBE_CLIENT_SECRET"),
            "refresh_token": self.secret_name("YOUTUBE_REFRESH_TOKEN"),
            "playlist_id": self.secret_name("YOUTUBE_PLAYLIST_ID"),
            "gemini_api_key": self.secret_name("GEMINI_API_KEY"),
        }


CHANNELS: dict[str, ChannelProfile] = {
    "secret-place": ChannelProfile(
        id="secret-place",
        display_name="The Secret Place",
        handle="@TheSecretPlace",
        secret_prefix="",
        default_privacy="public",
        auto_publish=True,
        include_sanctuary_links=True,
    ),
    "prayer2": ChannelProfile(
        id="prayer2",
        display_name="The Morning Altar",
        handle="@MorningAltarPrayer",
        secret_prefix="PRAYER2_",
        # New GCP projects are unaudited, so API uploads are private-locked
        # until the compliance audit passes. Private drafts by design.
        default_privacy="private",
        auto_publish=False,
        include_sanctuary_links=False,
    ),
}

# Friendly aliases accepted in frontmatter / workflow inputs.
_ALIASES = {
    "secret_place": "secret-place",
    "the-secret-place": "secret-place",
    "channel1": "secret-place",
    "morning-altar": "prayer2",
    "the-morning-altar": "prayer2",
    "channel2": "prayer2",
}


def normalize_channel_id(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if not value:
        return DEFAULT_CHANNEL_ID
    return _ALIASES.get(value, value)


def get_channel(channel_id: str | None = None) -> ChannelProfile:
    """Resolve a channel profile, failing closed on unknown ids."""
    cid = normalize_channel_id(channel_id or os.environ.get("CHANNEL_ID"))
    try:
        return CHANNELS[cid]
    except KeyError:
        known = ", ".join(sorted(CHANNELS))
        raise ValueError(f"Unknown CHANNEL_ID {cid!r}; known channels: {known}") from None


def channel_for_doc(meta: dict | None) -> str:
    """The channel a script belongs to (frontmatter `channel:`, default ch.1)."""
    return normalize_channel_id((meta or {}).get("channel"))
