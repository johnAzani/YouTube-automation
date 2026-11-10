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
    #: True once this channel's Google credentials (refresh token + Gemini key)
    #: exist in the repository. "Registered" and "live" are different things: a
    #: channel with no credentials is fully capable in code but must not be
    #: handed three production slots a day that cannot authenticate, nor have its
    #: empty queues reported as a supply failure. Scheduled work, queue rows and
    #: supervisor dispatches all follow this one flag.
    provisioned: bool = True

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
        handle="@TheMorningAltarDaily",
        secret_prefix="PRAYER2_",
        # Owner decision, 2026-11-05: The Morning Altar publishes on the
        # same terms as The Secret Place — scheduled Produce runs include
        # it and uploads are public with auto-publish. YouTube may still
        # clamp an upload from an unaudited API project to private; the
        # pipeline records the privacy YouTube actually returns.
        default_privacy="public",
        auto_publish=True,
        include_sanctuary_links=False,
    ),
    "prayer3": ChannelProfile(
        id="prayer3",
        display_name="The Midday Watch",
        handle="@TheMiddayWatch",
        secret_prefix="PRAYER3_",
        # Owner decision, 2026-11-06: the third channel is a prayer channel and
        # publishes on the same terms as the other two — public uploads, three
        # legs a day. Provisioned 2026-11-07 (see the note below).
        default_privacy="public",
        auto_publish=True,
        include_sanctuary_links=False,
        # Live 2026-11-07. The owner's own Google Cloud project `The Midday Watch`
        # exists, its three scopes are registered, and PRAYER3_YOUTUBE_CLIENT_ID,
        # _CLIENT_SECRET and _REFRESH_TOKEN are in the repository secrets — the
        # refresh token was minted while signed in as @TheMiddayWatch.
        #
        # Flipped on its own, deliberately: produce.yml already schedules the
        # channel the moment that refresh token exists (the readiness probe reads
        # the secret, not this flag), so leaving the flag False would have had the
        # channel *running* while `scheduled_channels()` kept it out of the health
        # monitor and the supervisor — work happening where nothing was watching.
        # One flag, one meaning: registered + credentialed = scheduled + watched.
        provisioned=True,
    ),
    "prayer4": ChannelProfile(
        id="prayer4",
        display_name="The Midnight Watch",
        handle="@TheMidnightWatchDaily",
        secret_prefix="PRAYER4_",
        # Owner decision, 2026-11-09: fourth prayer channel dedicated to the
        # 12:00 AM midnight watch & breakthrough intercession (Psalm 119:62 /
        # Acts 16:25). Provisioned 2026-11-10 once @TheMidnightWatchDaily's
        # dedicated Google Cloud OAuth client, refresh token, and Gemini API
        # key (PRAYER4_*) were saved in GitHub Secrets.
        default_privacy="public",
        auto_publish=True,
        include_sanctuary_links=False,
        provisioned=True,
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
    "midday": "prayer3",
    "noonday": "prayer3",
    "the-midday-watch": "prayer3",
    "channel3": "prayer3",
    "midnight": "prayer4",
    "midnight-watch": "prayer4",
    "the-midnight-watch": "prayer4",
    "channel4": "prayer4",
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


def scheduled_channels() -> tuple[str, ...]:
    """Channels that are live: registered *and* provisioned with credentials.

    Everything that spends schedule, quota or alarm on a channel reads this;
    everything that describes what a channel is *capable* of reads
    ``CHANNELS``/``known_channels()``. The distinction exists so adding a
    channel cannot make the monitor and the supervisor complain about work that
    the owner has deliberately not provisioned yet.
    """
    return tuple(cid for cid, profile in CHANNELS.items() if profile.provisioned)


def channel_for_doc(meta: dict | None) -> str:
    """The channel a script belongs to (frontmatter `channel:`, default ch.1)."""
    return normalize_channel_id((meta or {}).get("channel"))


def add_channel_arg(parser) -> None:
    """Attach a standard `--channel` CLI option to an `ArgumentParser`."""
    parser.add_argument(
        "--channel",
        default=None,
        help="Target channel id (secret-place, prayer2, prayer3; defaults to CHANNEL_ID or secret-place)",
    )


def apply_channel_env(channel_id: str | None = None) -> str:
    """Resolve `channel_id` and map its prefixed secrets onto canonical env vars."""
    prev_raw = (os.environ.get("CHANNEL_ID") or "").strip()
    prev_cid = normalize_channel_id(prev_raw) if prev_raw else ""
    explicit = channel_id or prev_raw
    cid = normalize_channel_id(explicit)
    if explicit:
        already_scoped = bool(prev_raw) and prev_cid == cid
        os.environ["CHANNEL_ID"] = cid
        profile = get_channel(cid)
        if profile.secret_prefix:
            mapping = {
                "YOUTUBE_CLIENT_ID": profile.secret_name("YOUTUBE_CLIENT_ID"),
                "YOUTUBE_CLIENT_SECRET": profile.secret_name("YOUTUBE_CLIENT_SECRET"),
                "YOUTUBE_REFRESH_TOKEN": profile.secret_name("YOUTUBE_REFRESH_TOKEN"),
                "YOUTUBE_PLAYLIST_ID": profile.secret_name("YOUTUBE_PLAYLIST_ID"),
                "GEMINI_API_KEY": profile.secret_name("GEMINI_API_KEY"),
            }
            for canonical, prefixed in mapping.items():
                if prefixed in os.environ and os.environ[prefixed]:
                    os.environ[canonical] = os.environ[prefixed]
                elif prefixed not in os.environ and not already_scoped:
                    # Only clear inherited canonical vars when switching from an
                    # unscoped/other channel; preserve vars already mapped for `cid`
                    # by the workflow job `env:` block.
                    os.environ.pop(canonical, None)
    return cid

