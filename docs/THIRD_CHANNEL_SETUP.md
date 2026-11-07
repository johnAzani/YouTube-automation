# Third Channel Setup — The Midday Watch (`prayer3`)

Status: **registered, not live.** Every line of code the channel needs is in `main`
and held to the same standard as the two channels that already publish. What is
missing is not code — it is one Google Cloud project, one OAuth refresh token, one
Gemini key, and a single one-word change to make it live.

The channel is a **prayer** channel for the middle of the day — Psalm 55:17,
"Evening, and morning, and at noon, will I pray". The Secret Place owns the night,
The Morning Altar owns the sunrise, The Midday Watch owns the hours that carry
weight: work, patience, integrity, and strength for the afternoon.

---

## 1. What is already done (merged, tested)

| Piece | Where |
|---|---|
| Channel profile, secret prefix `PRAYER3_`, aliases (`midday`, `noonday`, `channel3`) | `pipeline/channels.py` |
| Brand block — title suffix, producer line, closing CTA, required/forbidden phrases, authoring directive, Shorts dressing, pinned comments | `pipeline/channel_capabilities.py` |
| The other two brands now **forbid** this one, and it forbids both of them | same file |
| Its own equipment: `midday_system_instruction.md`, `midday_theological_rubric.md` | `pipeline/brain_equipment/` |
| Its own roadmap, job ids **0045–0052** (globally unique) | `scripts/continuous_research.py` |
| Shorts namespacing (`short-midday…`) so no Short can collide or be cross-dressed | `short_key_namespace="midday"` |
| Secret mapping in `produce.yml`, `gemini_brain.yml`, `comments.yml`, `metrics.yml` + manual-dispatch options | `.github/workflows/` |
| Readiness gate — see §4 | `produce.yml` / `gemini_brain.yml` plan steps |
| Parity tests: capabilities, brand, equipment, roadmap, Shorts, workflows | `tests/test_channel_parity.py`, `tests/test_third_channel.py` |

Nothing else in the pipeline changed: one code path, one capability matrix, no
`if channel == …` anywhere.

## 2. Registered vs live — the distinction that keeps the alarm honest

`pipeline/channels.py` marks the channel `provisioned=False`. That flag is read in
exactly three places and nowhere else:

* `scheduled_channels()` — the list the **scheduler supervisor** dispatches;
* `scripts/automation_health.queue_health()` — the per-channel rows the monitor and
  watchdog read;
* `produce.yml` / `gemini_brain.yml` also probe `secrets.PRAYER3_*` at runtime, so an
  early flip still cannot upload with borrowed credentials.

Why: a channel with no credentials has no supply problem — it has no work by
design. Scheduling it three times a day would produce three failing legs and a
permanently amber watchdog, which is exactly the "red that everyone learns to
ignore" this repository has been burned by.

## 3. What only you can do (~30 minutes, all free-tier)

Everything below uses **separate** projects. Free-tier Gemini limits and the
10,000-unit/day YouTube quota are enforced **per project**, not per key or per
channel, so sharing them would starve the two channels that are publishing.

### 3a. Create the YouTube channel
1. Create **The Midday Watch** (`@TheMiddayWatch`) — name, banner, description,
   links. Public uploads from an unaudited API project may be clamped to private
   until Google's audit completes; the pipeline records the privacy YouTube
   actually returns, so this is visible, not guessed.

### 3b. Create a separate Google Cloud project
1. New project, e.g. `midday-watch-youtube`. **Do not link a billing account.**
2. Enable **YouTube Data API v3** — in *this* project, not channel 1's or 2's;
   the 10,000-unit daily quota is pooled per project.
3. Google Auth Platform (left menu: Overview / Branding / Audience / Clients /
   Data Access) → **Get started** wizard:
   - App name `The Midday Watch Automation` (distinct from the other two, so the
     consent screen says which channel you are authorising), user-support email
     = yours;
   - Audience: **External**;
   - Contact information: your email; tick the API Services policy → **Create**.
4. **Audience → Publish app → Confirm.** Do this *before* minting the token. A
   consent screen left in **Testing** issues refresh tokens that hard-expire after
   **7 days** (`docs/DEEP_DIVE.md` trap 1) — the pipeline uploads all week, then
   dies with `invalid_grant`. Unverified *In production* is fine for your own
   account: you click *Advanced → Go to … (unsafe)* once, on your own app.
5. **Data Access → Add or remove scopes → Manually add scopes**, all three, one
   per line — the pipeline always requests this exact set and Google rejects a
   token whose grants do not cover it (`invalid_scope`):
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.readonly`
   - `https://www.googleapis.com/auth/youtube.force-ssl`
6. **Clients → Create client → Web application**, name
   `Midday Watch YouTube Uploader`, authorised redirect URI
   `https://developers.google.com/oauthplayground` → Create. Copy the client ID
   and secret straight into the GitHub secrets in §3e — never into chat, an
   issue or a commit.
   *(A **Desktop** client plus `python scripts/youtube_oauth.py` is the
   equivalent local route; it listens on `localhost:8765`, so it needs a
   computer, not a phone. The two live channels were minted through the
   Playground — both routes work, this one has the track record.)*

### 3c. Mint the refresh token
OAuth Playground → gear icon → *use your own OAuth credentials* → paste the new
client ID/secret → **Server-side**, **Offline**, consent prompt → authorize the
three scopes **while signed in as The Midday Watch** (this is what decides which
channel the token can publish to) → exchange → **refresh token**.

Never paste a token into an issue, a commit, this file, or chat.

### 3d. Create the separate Gemini project
Google AI Studio → new project → create API key in it. Free tier only, no billing.

### 3e. Add six repository secrets (Settings → Secrets and variables → Actions)

| Secret | Value |
|---|---|
| `PRAYER3_YOUTUBE_CLIENT_ID` | from §3b |
| `PRAYER3_YOUTUBE_CLIENT_SECRET` | from §3b |
| `PRAYER3_YOUTUBE_REFRESH_TOKEN` | from §3c |
| `PRAYER3_GEMINI_API_KEY` | from §3d |
| `PRAYER3_YOUTUBE_CHANNEL_ID` | the channel's `UC…` id — the wrong-token guard; without it a mis-mapped token could upload to the wrong channel |
| `PRAYER3_YOUTUBE_PLAYLIST_ID` | optional |

### Before the first upload — the one code change
Flip one word in `pipeline/channels.py`:

```python
    provisioned=False,   #  →  provisioned=True,
```

and push. That is the whole switch. Nothing else has to be remembered, and the
parity tests fail if the flip is made without the secrets being referenced.

## 4. What happens the moment it is live

* The supervisor dispatches it in the same three slots as the others — 06:14,
  14:14, 19:14 UTC — checking for that channel's own receipt.
* The monitor gains `longform:prayer3` and `shorts:prayer3` rows; the watchdog
  reports an empty queue for it the same way it does for the others.
* The 03:14 brain pass authors its first script from roadmap id **0045**
  (Psalm 55:17), and its companion Short.
* Comments, metrics and community accept `channel: prayer3`.

## 5. First three days — what to watch

1. The first authored job in `content/queue/` should carry `channel: prayer3`,
  `thumb_text`, `niche`, `originality`, and six scenes. If the brain returns
   anything else it now refuses to write it and climbs to the next model.
2. The first Short key should read `short-midday…`.
3. Confirm the upload landed on `@TheMiddayWatch` and not on a neighbour — that is
   what `PRAYER3_YOUTUBE_CHANNEL_ID` exists to prevent.
