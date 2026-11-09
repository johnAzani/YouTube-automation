# Fourth Channel Setup — The Midnight Watch (`prayer4`)

Status: **registered, not yet live (`provisioned=False`).** Every line of code,
equipment, 30-scripture roadmap (`0200`–`0229`), Shorts namespacing (`short-midnight…`),
CTR thumbnail pack (`midnight` grade), Community Tab schedule, ES/PT localizations,
brand artwork (`docs/media/midnight-watch-*.png`), and GitHub Actions workflow probes
are wired into `main` in full parity with the three live channels.

The channel is a **midnight breakthrough & watchman prayer** channel anchored in
**Psalm 119:62** (*"At midnight I will rise to give thanks unto thee because of thy
righteous judgments"*) and **Acts 16:25–26** (*"And at midnight Paul and Silas prayed,
and sang praises unto God... and every one's bands were loosed"*):

* **The Secret Place (`secret-place`)** owns bedtime rest and peaceful sleep.
* **The Morning Altar (`prayer2`)** owns the sunrise consecration.
* **The Midday Watch (`prayer3`)** owns noonday strength for work and afternoon trials.
* **The Midnight Watch (`prayer4`)** owns the **12:00 AM watchtower** — wakeful
  midnight thanksgiving, household deliverance, and persevering intercession.

---

## 1. What is already built and tested

| Piece | Where |
|---|---|
| Channel profile (`prayer4`), secret prefix `PRAYER4_`, aliases (`midnight`, `midnight-watch`, `the-midnight-watch`, `channel4`), `provisioned=False` | `pipeline/channels.py` |
| Brand block — title suffix, producer line, closing CTA, mutual `forbidden_phrases` across all four channels, Shorts dressing, pinned comments, playlists, Community posts, ES/PT localizations, CTR hero pack | `pipeline/channel_capabilities.py` |
| Dedicated equipment: `midnight_system_instruction.md`, `midnight_theological_rubric.md` | `pipeline/brain_equipment/` |
| Dedicated 30-scripture KJV roadmap, job IDs **`0200`–`0229`** (globally unique) | `scripts/continuous_research.py` |
| Midnight visual color science (royal indigo + watchtower gold) for 9:16 Shorts & 16:9 CTR packs | `pipeline/shorts_poster.py`, `pipeline/thumbnail_ctr.py` |
| Ready-to-upload YouTube Studio artwork (`avatar`, `banner`, `watermark`, `thumbnail-template`, `brand-sheet`) | `docs/media/midnight-watch-*.png` (`tools/make_channel_brand_assets.py`) |
| Secret mapping + `PRAYER4_READY` runtime probes in `produce.yml`, `gemini_brain.yml`, `comments.yml`, `metrics.yml`, `growth-autopilot.yml`, `community.yml`, `monitor.yml`, `set-thumbnail.yml` | `.github/workflows/` |
| Parity & fourth-channel test suites | `tests/test_channel_parity.py`, `tests/test_fourth_channel.py` |

While `provisioned=False` and `PRAYER4_*` secrets are unset:
* `scheduled_channels()` excludes `prayer4`, so `scheduler-supervisor.yml` and
  `monitor.yml` stay 100% green and never raise false starvation alarms.
* `produce.yml`, `gemini_brain.yml`, and `comments.yml` emit a clean informational
  notice (`prayer4 waits for credentials`) and skip the `prayer4` matrix leg cleanly.

---

## 2. How to make `prayer4` live (~25 minutes, $0.00 free tier)

Always create a **separate Google Cloud project** for `prayer4`. YouTube's 10,000-unit
daily quota and Gemini's free-tier RPD limits are enforced **per Google Cloud project**,
so isolating `prayer4` protects the three live channels' quotas.

### Step A — Create the YouTube channel & upload the brand art
1. Create the YouTube Brand Account channel **The Midnight Watch** (`@TheMidnightWatch`).
2. In **YouTube Studio -> Customization -> Branding**, upload from `docs/media/`:
   * **Picture:** `midnight-watch-avatar.png` (`800 x 800`)
   * **Banner image:** `midnight-watch-banner.png` (`2560 x 1440`, mobile-safe `1235 x 338`)
   * **Video watermark (Entire video):** `midnight-watch-watermark.png` (`150 x 150` RGBA)
3. Verify phone number in **YouTube Studio -> Settings -> Channel -> Feature eligibility -> Intermediate features** (required for custom 16:9 thumbnails and >15m uploads).

### Step B — Create a dedicated Google Cloud project (No billing account)
1. Create a new project (e.g. `midnight-watch-youtube`) — **do not attach billing** (`$0.00` lock).
2. Enable **YouTube Data API v3**.
3. Configure OAuth consent screen (**External** -> Testing -> add the channel's Google email as a test user) and create a **Desktop app** OAuth client.
4. Run locally to mint the refresh token while selecting **The Midnight Watch** Brand Account:
   ```bash
   python tools/youtube_auth.py --client-secrets path/to/client_secret.json
   ```
5. Create a free-tier **Gemini API key** in Google AI Studio tied to a separate project.

### Step C — Save the GitHub Repository Secrets
In **GitHub -> Settings -> Secrets and variables -> Actions**, add:

| Secret / Variable | Value |
|---|---|
| `PRAYER4_YOUTUBE_CLIENT_ID` | OAuth Desktop client ID from Step B |
| `PRAYER4_YOUTUBE_CLIENT_SECRET` | OAuth Desktop client secret from Step B |
| `PRAYER4_YOUTUBE_REFRESH_TOKEN` | Refresh token from `tools/youtube_auth.py` |
| `PRAYER4_GEMINI_API_KEY` | Free-tier AI Studio key for `prayer4` |
| `PRAYER4_YOUTUBE_CHANNEL_ID` *(optional var/secret)* | `UC...` channel ID (hard identity lock against cross-channel uploads) |
| `PRAYER4_YOUTUBE_PLAYLIST_ID` *(optional)* | Default `PL...` playlist ID |

### Step D — Flip `provisioned=True`
Once those secrets are saved:
1. Change `provisioned=False` -> `provisioned=True` on `"prayer4"` in `pipeline/channels.py`.
2. At **4:14 AM WAT** (`gemini_brain.yml`), Gemini Brain will automatically author the initial queue (`0200` Psalm 119:62 onward + Shorts `short-midnight*`), and `produce.yml` will automatically include `prayer4` on the **7:14 AM, 3:14 PM, and 8:14 PM WAT** daily release cadence!
