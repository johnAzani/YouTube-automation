# Second Channel Setup — Separate GCP Project per Channel ($0.00)

How **The Morning Altar** (`prayer2`) was added as a fully independent channel
on the same codebase as **The Secret Place** (`secret-place`), and how to
repeat the pattern for any future channel.

**Architecture decision:** separate Google Cloud project per channel.
Each channel therefore gets its *own*:

- YouTube Data API v3 quota pool (**10,000 units/day** — uploads can never
  starve the other channel, and there is no paid overage to fall into)
- Gemini free-tier pool (limits are enforced **per project**, not per key)
- OAuth client + refresh token (a token only ever authorizes the channel it
  was minted for)
- GitHub secret set, prefixed `PRAYER2_*`
- Compliance-audit status (a new project is unaudited → uploads are locked
  **private** until its audit passes; publish manually from Studio meanwhile)

Creating projects/keys is free. **Never enable billing and never use Vertex
AI** — with no billing attached, both APIs fail closed with quota errors
(`403 quotaExceeded` / `429 RESOURCE_EXHAUSTED`) instead of charging. The
pipeline already pauses and resumes at the midnight-Pacific reset
(`docs/ZERO_DOLLAR_LOCK.md`).

---

## 1. What already exists in this repo (done for you)

| Piece | Where |
|---|---|
| Channel registry (ids, handles, secret prefixes, privacy defaults) | `pipeline/channels.py` |
| Queue routing — a run only picks up its own channel's scripts | `channel:` frontmatter + `pipeline/run.py` (`select_jobs`, cross-channel refusal in `process()`) |
| Wrong-channel guard — aborts before upload if the token authorizes a different channel than `YOUTUBE_EXPECTED_CHANNEL_ID` | `pipeline/upload.py::verify_target_channel` |
| Channel-aware descriptions (Selar/store links stay on Channel 1 only) | `pipeline/metadata.py`, `pipeline/pinned_comments.py`, `pipeline/localize_metadata.py` |
| Channel selector (`secret-place` / `prayer2`) | Produce, Metrics, Comments, Set-thumbnail workflows |
| Brand kit + launch checklist | `docs/MORNING_ALTAR_BRANDING.md` |
| First (draft) Morning Altar script | `content/queue/0036-psalm-5-morning-prayer-begin-your-day.md` |

Scheduled (cron) runs always target `secret-place`. `prayer2` runs are
manual-dispatch only for now, and for `prayer2` the Produce workflow skips
the Secret Place queue-repair and authored-Shorts steps.

## 2. What only you can do (your Google account — ~30 minutes)

### 2a. Create the YouTube channel
1. Create the channel following `docs/MORNING_ALTAR_BRANDING.md` (name,
   handle, avatar/banner/watermark, About, keywords, 2-step verification).

### 2b. Create the separate Google Cloud project
1. Google Cloud Console → create project (e.g. `morning-altar-youtube`).
   **Do not link a billing account.** *(Done 2026-11-04: project
   "The Morning Altar" created and selected; Google Auth Platform
   configured — OAuth Overview reached, no OAuth client created yet.)*
2. Enable **YouTube Data API v3** (APIs & Services → Library → search
   "YouTube Data API v3" → Enable). Do this in the new project, not Channel
   1's — quota pools are per project.
3. Configure the Google Auth Platform (new console UI, left menu:
   Overview / Branding / Audience / Clients / Data Access):
   - **Overview → "Get started"** wizard: App name `The Morning Altar
     Automation`, pick your email as user-support email → Next → Audience:
     **External** → Next → Contact information: your email → Next →
     tick the Google API Services policy agreement → **Create**.
   - **Audience → "Publish app"** → Confirm. This moves the app from
     *Testing* to **In production**; in Testing, refresh tokens expire after
     7 days (`docs/SETUP.md` §1b). Unverified is fine for your own account —
     expect a warning screen later and click through only for your own app.
   - **Data Access → "Add or remove scopes" → "Manually add scopes"** →
     paste `https://www.googleapis.com/auth/youtube.upload` and
     `https://www.googleapis.com/auth/youtube.readonly` → "Add to table" →
     Update → Save.
   - **Clients → "Create client" → Web application**: name
     `Morning Altar YouTube Uploader` → Authorized redirect URIs →
     `https://developers.google.com/oauthplayground` → **Create**. Copy the
     client ID and client secret straight into the GitHub secrets in §2e —
     never into chat, issues or commits.

### 2c. Mint the Morning Altar refresh token
1. OAuth Playground → gear icon → use your **new** client ID/secret,
   **Server-side**, **Offline**, consent prompt.
2. Authorize scopes `youtube.upload` + `youtube.readonly` **while signed in
   as / selecting The Morning Altar channel** — this is the step that decides
   which channel the token uploads to. Picking your personal channel here is
   the #1 multi-channel mistake; `verify_target_channel` will catch it later
   if `PRAYER2_YOUTUBE_CHANNEL_ID` is set (step 2e).
3. Exchange the code and keep the refresh token private. **Never paste it
   into chat, issues, commits or workflow inputs.**

   **Troubleshooting — "Access blocked: The Morning Altar Automation has not
   completed the Google verification process" (seen 2026-11-04):** this is
   Google refusing authorization because the app is still in **Testing**
   and/or its **Branding** page is incomplete (`docs/DEEP_DIVE.md` Trap 1).
   Fix in this order, then re-run step 1:
   1. **Branding** page: app name + support email (from the wizard), plus
      Application home page `https://johnazani.github.io/YouTube-automation/app.html`
      and Privacy policy `https://johnazani.github.io/YouTube-automation/privacy.html`;
      add `johnazani.github.io` under authorized domains if the form asks.
   2. **Audience** page: Publishing status must be **In production** — use
      **Publish app** if it still says Testing. Publishing ≠ verification:
      an unverified production app still issues long-lived tokens; you just
      click *Advanced → Go to The Morning Altar Automation (unsafe)* once on
      your own consent screen.
   3. Do **not** settle for the Testing-mode shortcut (adding yourself as a
      test user also unblocks authorization, but those refresh tokens
      hard-expire after 7 days — the exact failure Trap 1 exists to avoid).

### 2d. Create the separate Gemini project + key
1. Google AI Studio → create a **new project** → create API key in it.
   (A second key inside Channel 1's project would share its free-tier pool —
   limits are per project, not per key.)
2. No billing, no Vertex AI. Free tier only; exhaustion returns 429 and the
   pipeline pauses until reset.

### 2e. Add the GitHub secrets (Settings → Secrets and variables → Actions)

*Status 2026-11-04: `PRAYER2_YOUTUBE_CLIENT_ID` and
`PRAYER2_YOUTUBE_CLIENT_SECRET` added. Still outstanding:
`PRAYER2_YOUTUBE_REFRESH_TOKEN` (§2c) and `PRAYER2_GEMINI_API_KEY` (§2d).*

| Secret | Value |
|---|---|
| `PRAYER2_YOUTUBE_CLIENT_ID` | Web OAuth client ID from the **new** GCP project |
| `PRAYER2_YOUTUBE_CLIENT_SECRET` | Raw client secret (**not** JSON) |
| `PRAYER2_YOUTUBE_REFRESH_TOKEN` | Token from 2c, minted for The Morning Altar |
| `PRAYER2_YOUTUBE_PLAYLIST_ID` | *(optional)* a Morning Altar playlist ID |
| `PRAYER2_GEMINI_API_KEY` | Key from 2d |
| `PRAYER2_YOUTUBE_CHANNEL_ID` | *(recommended, as a repository **Variable**)* the channel's `UC…` ID — Studio → Settings → Channel → Advanced. Activates the wrong-channel guard |

Shared, no need to duplicate: `PEXELS_API_KEY`, `PIXABAY_API_KEY`, GitHub
Actions minutes (public repo), ffmpeg, stock sources.

## 3. Run it

1. Review the queued draft (`content/queue/0036-…md`) aloud, verify every
   KJV quotation, set `human_rewrite: true` and `status: approved`.
   Scripts opt into this channel with `channel: prayer2` in frontmatter —
   scripts without a `channel:` line belong to The Secret Place and a
   `prayer2` run will skip (or, for an explicit `--job`, refuse) them.
2. Actions → **Produce video** → Run workflow → **channel: prayer2**,
   `dry_run` ticked (render-only rehearsal) → check the artifact.
3. Run again with `dry_run` unticked. The upload lands **private** (new
   project, unaudited). Open the release ticket / Studio and publish
   manually, exactly as Channel 1 started.
4. Metrics / Comments / Set-thumbnail also accept the same `channel`
   selector for manual runs. Community, growth-autopilot, monitor and the
   brain still operate on Channel 1 only until Morning Altar has its own
   data history.

## 4. Adding a third channel later

1. Add a profile in `pipeline/channels.py` (new prefix, e.g. `PRAYER3_`).
2. Repeat §2 with a **new** GCP project + Gemini project + token.
3. Add the `prayer3` option + secret mapping to the workflows that need it.
4. Tag its scripts `channel: prayer3`. Nothing else changes.
