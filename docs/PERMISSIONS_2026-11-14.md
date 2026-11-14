# Every permission the ten channels need, to grant once

14 November 2026. Measured against the live credentials of all ten channels by the read-only
probe in `.github/workflows/channel-credential-audit.yml` (run 43583052252, 09:58 UTC), and
read from Google's own pages (listed at the end).

## Summary

- **For everything the studio does today, no permission is missing.** All ten tokens upload,
  edit, caption, comment and manage playlists and the channel page.
- **Two scopes are missing on all ten tokens**, both for measurement: `yt-analytics.readonly`
  and `yt-analytics-monetary.readonly`. A new scope cannot be added to an existing token, so
  each channel needs **one more mint**. Minted with the seven scopes below, there is no
  eighth to come back for: that is every scope a creator's channel can grant.
- **The YouTube Analytics API is switched off in all ten Google Cloud projects.** A token
  with the right scopes would still be refused until it is enabled.
- **Five channels have not verified a phone number** (The Midnight Watch, The Family Altar,
  The Covenant Shield, The Praise Garden, The Guided Path). No token can grant that.
- **`PEXELS_API_KEY` is not set**, so Pexels footage is skipped.

## What the probe found, per channel

| Channel | Token scopes today | Analytics API in its project | Videos over 15 min | Country | Live |
|---|---|---|---|---|---|
| The Secret Place | force-ssl, readonly, upload | off | allowed | NG | on |
| The Morning Altar (prayer2) | force-ssl, readonly, upload | off | allowed | NG | off |
| The Midday Watch (prayer3) | force-ssl, readonly, upload | off | allowed | NG | off |
| The Midnight Watch (prayer4) | force-ssl, readonly, upload | off | **not verified** | **not set** | off |
| The Family Altar (prayer5) | youtube, force-ssl, upload | off | **not verified** | **not set** | off |
| The Healing Balm (prayer6) | youtube, force-ssl, upload | off | allowed | **not set** | off |
| The Provision Table (prayer7) | youtube, force-ssl, upload | off | allowed | **not set** | off |
| The Covenant Shield (prayer8) | youtube, force-ssl, upload | off | **not verified** | **not set** | off |
| The Praise Garden (prayer9) | force-ssl, readonly, upload | off | **not verified** | **not set** | off |
| The Guided Path (prayer10) | force-ssl, readonly, upload | off | **not verified** | **not set** | off |

- "Not verified" is YouTube's `longUploadsStatus: eligible`: the channel may upload over 15
  minutes and set custom thumbnails once its owner verifies a phone number.
- Ten different Cloud projects, so ten separate daily quotas (10,000 units and 100 uploads
  each).
- Google reported no end date on any of the ten refresh tokens. That is what a project "In
  production" looks like, but the Audience page itself cannot be read from here.
- The YouTube Reporting API refused on scope before it said whether it is enabled, so its
  state is unknown.
- Every channel: Gemini key valid, Pixabay key set, Pexels key not set, no playlist ID secret
  (optional, unused by nine channels).

## The grant, once per channel

Ten channels, ten Cloud projects, ten mints. The old token keeps working until the new one is
saved, so nothing stops in between.

### 1. Google Cloud (the channel's own project)

1. **APIs & Services → Library**: enable **YouTube Analytics API** and **YouTube Reporting
   API**. YouTube Data API v3 is already on.
2. **Google Auth Platform → Audience**: it must read **In production**. If it reads Testing,
   press **Publish app**. Verification is not needed for your own account.
3. **Google Auth Platform → Clients → the Web client**: the client ID is shown. The client
   secret is shown only when it is created. If it was not kept, press **Add secret** and copy
   the new one. Leave the old secret enabled: GitHub still uses it, and a client may have two.

### 2. OAuth Playground (`https://developers.google.com/oauthplayground`)

1. Gear icon: tick **Use your own OAuth credentials**, paste the client ID and secret, Access
   type **Offline**, Force prompt **Consent Screen**.
2. In **Input your own scopes** paste this one line:

   ```
   https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/yt-analytics.readonly https://www.googleapis.com/auth/yt-analytics-monetary.readonly https://www.googleapis.com/auth/youtube.channel-memberships.creator
   ```

3. **Authorize APIs**, and choose **the channel itself** in the account picker (the Brand
   Account, not the personal account beside it).
4. On Google's consent page tick **Select all**. Any box left unticked is a scope the token
   will not have.
5. **Exchange authorization code for tokens** and copy the **Refresh token**.

### 3. GitHub (Settings → Secrets and variables → Actions)

Replace the channel's refresh token secret with the new value. Nothing else changes.

| Channel | Secret to replace |
|---|---|
| The Secret Place | `YOUTUBE_REFRESH_TOKEN` |
| prayer2 … prayer10 | `PRAYER2_YOUTUBE_REFRESH_TOKEN` … `PRAYER10_YOUTUBE_REFRESH_TOKEN` |

Never paste a token or a client secret into chat, an issue or a file.

### What each scope is for

| Scope | Gives | Used now |
|---|---|---|
| `youtube` | channel page, playlists, home shelves, banner, watermark | yes |
| `youtube.force-ssl` | edit and delete videos, comments, captions | yes |
| `youtube.upload` | upload, thumbnails | yes |
| `youtube.readonly` | read | yes |
| `yt-analytics.readonly` | watch time, where viewers come from, how long they stay, bulk reports with thumbnail impressions and click rate | not yet |
| `yt-analytics-monetary.readonly` | revenue reports | once a channel earns |
| `youtube.channel-memberships.creator` | list paying members | once memberships exist |

Left out: `youtubepartner` and `youtubepartner-channel-audit`. They act for a YouTube Content
Manager (a network or label) and a channel cannot grant them.

## What only the owner can do in YouTube Studio

No token covers these. Each is once per channel.

1. **Verify a phone number** on prayer4, prayer5, prayer8, prayer9 and prayer10: Settings →
   Channel → Feature eligibility → Intermediate features. Until then custom thumbnails and
   videos over 15 minutes are refused.
2. **Advanced features** on all ten (same page): clickable links in descriptions, higher
   daily upload limits, applying for monetisation. The API does not report this state, so it
   was not measured.
3. **Country of residence** on prayer4 … prayer10: Settings → Channel → Basic info. The code
   never changes a channel's country.
4. **2-step verification** on each Google Account. The Partner Program requires it.
5. For The Secret Place when it applies: AdSense, and the updated Partner Program terms.

## Other keys

| Key | State | Needed |
|---|---|---|
| `GEMINI_API_KEY` (one per channel) | valid on all ten | yes |
| `PIXABAY_API_KEY` | set | yes |
| `PEXELS_API_KEY` | **not set** | optional; free at pexels.com/api; adds a second footage source |
| `…YOUTUBE_PLAYLIST_ID` | not set | no |

## What keeps a token alive

A refresh token has no expiry of its own. It stops working only if:

- the project's Audience is Testing (ends after 7 days);
- access is removed in the Google Account (Security → third-party access), or the OAuth
  client is deleted, or its only enabled secret is disabled;
- it goes unused for six months (these are used daily);
- more than 100 tokens are minted for one account on one client (the oldest dies silently).

A password change does not end it. Minting a new token does not end the old one.

## What no permission makes possible

- End screens, cards, thumbnail A/B tests, pinning a comment, community posts, the related
  video on a Short, applying to the Partner Program: Studio only, no API.
- Inviting someone under Studio → Settings → Permissions gives no API access.
- A service account cannot act as a channel.
- From this workspace: starting a workflow by hand and listing secret names are refused
  (HTTP 403) by the GitHub connection. The work-around in use is a push that triggers the
  workflow.

## After the grant

Nothing in the studio reads Analytics yet. `scripts/channel_analytics.py` exists but looks for
separate `ANALYTICS_*` secrets and was written to run privately. Still to build once the
tokens are in place: read Analytics from the channel's own token in the daily growth run,
start the Reporting job for thumbnail impressions (reports begin within 48 hours of the job
and are kept 60 days), and decide which figures go into this public repository.

Whether the Analytics API accepts `videoThumbnailImpressions` directly could not be tested:
the API is off in every project. The probe asks that question on its next run.

## Changed with this note

- `scripts/permission_probe.py`, run by the credential audit after its existing check: GET
  requests only, prints scopes and Google's refusal codes, no secret, no figures, never fails
  the job. `tests/test_permission_probe.py` holds the workflow copy equal to the file.
- `scripts/youtube_oauth.py --purpose full` (and `--print-scopes`).
- `docs/FOURTH_CHANNEL_SETUP.md` told the reader to leave the project in Testing; corrected.
  `docs/SETUP.md` names the two extra APIs and the full scope line.

## Sources (read 14 November 2026)

- `developers.google.com/identity/protocols/oauth2` — refresh token expiry, 100-token limit.
- `support.google.com/cloud/answer/15549945` — Testing and In production.
- `support.google.com/cloud/answer/15549257` — client secrets shown once, two secrets per
  client, unused clients deleted after six months.
- `developers.google.com/youtube/v3/guides/authentication` — Data API scopes.
- `developers.google.com/youtube/reporting/guides/authorization` and `…/reporting/v1/reports`
  — Analytics and Reporting scopes, reporting jobs.
- `developers.google.com/youtube/v3/determine_quota_cost` — quota.
- `support.google.com/youtube/answer/9890437` and `…/9891124` — feature access.
- `support.google.com/youtube/answer/12843009` — Partner Program changes from 1 February 2027.
