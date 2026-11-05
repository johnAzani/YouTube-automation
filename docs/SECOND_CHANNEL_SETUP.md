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
| First Morning Altar script | `content/published/0036-psalm-5-morning-prayer-begin-your-day.md` (uploaded `_vp27ZYPYaY`, public; the corrected-video history is in the §2e status note) |

Scheduled (cron) Produce runs serve **both** channels (owner decision,
2026-11-05): each slot runs The Secret Place and then The Morning Altar,
sequentially, and `prayer2` uploads are **public with auto-publish**, on the
same terms as `secret-place`. A manual Produce dispatch still produces only
the channel selected. For `prayer2` the Produce workflow runs a
channel-scoped queue-repair pass (Secret Place Shorts stay Secret Place
only). The Morning Altar brain now owns Morning Altar script supply
unattended: `gemini_brain.yml` replenishes both channels (each with its
own Gemini quota pool), so a scheduled `prayer2` leg normally finds an
approved `channel: prayer2` script in `content/queue/`. If free-tier
capacity is exhausted, the leg still idles with a "Morning Altar queue
empty" notice instead of failing the slot or spending money ($0 lock).

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
     paste all three scope URLs (one per line) → "Add to table" → Update →
     Save:
     - `https://www.googleapis.com/auth/youtube.upload`
     - `https://www.googleapis.com/auth/youtube.readonly`
     - `https://www.googleapis.com/auth/youtube.force-ssl`

     All three are required: the pipeline's credential object
     (`pipeline/upload.py` `SCOPES`) always requests upload + readonly +
     force-ssl, and Google rejects a refresh token whose granted scopes
     don't cover the requested set (`invalid_scope`). force-ssl is also
     what the comments workflows use.
   - **Clients → "Create client" → Web application**: name
     `Morning Altar YouTube Uploader` → Authorized redirect URIs →
     `https://developers.google.com/oauthplayground` → **Create**. Copy the
     client ID and client secret straight into the GitHub secrets in §2e —
     never into chat, issues or commits.

### 2c. Mint the Morning Altar refresh token
1. OAuth Playground → gear icon → use your **new** client ID/secret,
   **Server-side**, **Offline**, consent prompt.
2. Authorize scopes `youtube.upload` + `youtube.readonly` +
   `youtube.force-ssl` **while signed in
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

   **Troubleshooting — "the stored refresh token cannot be exchanged for
   the scopes this script needs" (seen 2026-11-04, metrics run #25):** the
   token was minted with only upload + readonly, but every pipeline script
   requests upload + readonly + **force-ssl**. Scopes are frozen into the
   refresh token at mint time, so the fix has two halves: (a) add
   `youtube.force-ssl` under **Data Access** (step 3 above), then (b)
   re-authorize in OAuth Playground with all three scopes ticked and
   replace the `PRAYER2_YOUTUBE_REFRESH_TOKEN` secret with the new token.
   Re-minting alone (without the Data Access change) just reproduces the
   same two-scope token.

   **Troubleshooting — "YouTube Data API v3 has not been used in project
   … before or it is disabled" (seen 2026-11-04, metrics run #27):** the
   token now exchanges fine (this error is *progress* past the scope
   problem), but the API itself was never switched on in the new project.
   Enabling an API is per project, so Channel 1's enabled state does not
   carry over. Fix: in the Morning Altar project open APIs & Services →
   Library (or the link in the error message), Enable **YouTube Data
   API v3**, wait a few minutes for it to propagate, then re-run. No
   secret or scope changes are needed.

### 2d. Create the separate Gemini project + key
1. Google AI Studio → create a **new project** → create API key in it.
   (A second key inside Channel 1's project would share its free-tier pool —
   limits are per project, not per key.)
2. No billing, no Vertex AI. Free tier only; exhaustion returns 429 and the
   pipeline pauses until reset.

### 2e. Add the GitHub secrets (Settings → Secrets and variables → Actions)

*Status 2026-11-04 (COMPLETE): **The Morning Altar is live end-to-end.**
Data API enabled → metrics run #28 succeeded (1 subscriber, 0 public
videos). Script 0036 (Psalm 5) approved under owner authorization,
dry-run render succeeded (run 41887937132), and the first video was
uploaded **private** on 2026-11-04: `oS7f32WDj_Y` (7:57) — receipt in
`content/published/0036-*.md`. **That upload is defective and must
never be published:** its `tts-v2` narration speaks the read-aloud
contract aloud. Job 0036 was deliberately re-queued (PR #254) and the
replacement (run 41958248221, `R8mVvedhYVw`, supposedly `tts-v3`) **is
also defective** — it still reads instruction-shaped text aloud. Deep
diagnosis found two evidence-backed causes: (1) the workflow restores
`_gemini_chunks_*` across runs while the per-chunk reuse hash keyed
only on `voice:model:chunk-text`, so defective-era chunk audio could
be silently reused; (2) PR #253 carried style in
`GenerateContentConfig.system_instruction`, a channel Google's
official Gemini 3.8 TTS migration guide does not document — for 3.8
models, text is a verbatim transcript and style belongs in
`speech_metadata.style`. The next fix removes `system_instruction`
from every TTS request, moves style to `speech_metadata.style` /
the interactions `speech_metadata` annotation, versions every cache
key by the delivery recipe (`tts-v4-speech-metadata-style`), and bumps
the Actions chunk-cache key. That fix shipped as `tts-v4` (PR #256) and
is **proven on real audio**: corrected upload `_vp27ZYPYaY` from run
`42010285242` (2026-11-05, 7:46) was owner-verified to begin with the
prayer itself, made **public**, and both defective uploads were deleted
in Studio. The run still concluded *failure* — a monitor snapshot
(`d5a74af`, 47 seconds after PR #264 merged) resurrected the retired
receipt, so the run uploaded and then could not write its own receipt;
the repo receipt was reconciled with the live video ID afterwards, and
`produce()` now fails fast (PR #267) when a published record already
exists. The same tts-v4 was then re-proven on channel 1: the corrected
Psalm 27 replacement `BFlkzRVMf8o` (run `42033981791`, 2026-11-05)
uploaded **private** to The Secret Place, wrote its own receipt
cleanly, and was owner-verified. The owner has since flipped
`BFlkzRVMf8o` **public** in Studio and deleted the defective
`7ll7w1hYf7o` there (owner-completed 2026-11-05); the published
receipt in `content/published/0011-*.md` now records `privacy: public`
for that video. Remaining owner actions: watermark + channel
keywords via desktop Studio only. Earlier: run #25's
two-scope token was fixed (three scopes saved in Data Access, token
re-minted, secret replaced — run #27 got past the credential exchange,
then hit `accessNotConfigured` until the API was enabled). Earlier:
`PRAYER2_YOUTUBE_CLIENT_ID` and
`PRAYER2_YOUTUBE_CLIENT_SECRET` added; Data Access scopes
(`youtube.upload`, `youtube.readonly`) saved; Branding saved (app home /
privacy / terms pages + `johnazani.github.io` authorized domain; logo
deliberately left empty so verification is not triggered); Audience
published — Publishing status **In production**, External, OAuth user cap
1/100 (the "requires verification" banner is expected; verification is
intentionally not submitted, same as Channel 1); `PRAYER2_YOUTUBE_REFRESH_TOKEN`
minted in OAuth Playground and added to GitHub secrets (owner screenshot
2026-11-04) and since replaced with a three-scope token; `PRAYER2_GEMINI_API_KEY` also added (§2d); `PRAYER2_YOUTUBE_CHANNEL_ID` stored as a Secret (workflows accept Variables or Secrets). **PR #243 merged to `main` 2026-11-04** — run channel-2 workflows from `main`.*

| Secret | Value |
|---|---|
| `PRAYER2_YOUTUBE_CLIENT_ID` | Web OAuth client ID from the **new** GCP project |
| `PRAYER2_YOUTUBE_CLIENT_SECRET` | Raw client secret (**not** JSON) |
| `PRAYER2_YOUTUBE_REFRESH_TOKEN` | Token from 2c, minted for The Morning Altar |
| `PRAYER2_YOUTUBE_PLAYLIST_ID` | *(optional)* a Morning Altar playlist ID |
| `PRAYER2_GEMINI_API_KEY` | Key from 2d |
| `PRAYER2_YOUTUBE_CHANNEL_ID` | *(recommended; repository **Variable** or Secret — workflows accept either)* the channel's `UC…` ID — Studio → Settings → Channel → Advanced, or youtube.com/account_advanced while switched to the channel. Activates the wrong-channel guard |

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
3. Run again with `dry_run` unticked, or simply queue an approved script:
   since 2026-11-05 the scheduled slots (07:14 / 15:14 / 20:14 Lagos)
   produce The Morning Altar right after The Secret Place, uploading
   **public with auto-publish**. Note YouTube can still clamp uploads from
   an unaudited API project to private server-side; check the release
   ticket's recorded privacy after the first scheduled upload. The
   Morning Altar brain keeps the queue stocked unattended (Morning Altar
   roadmap, sunrise branding, `PRAYER2_` Gemini pool, no companion
   Shorts); if free-tier capacity is exhausted, an empty queue means the
   slot idles (watch for the "Morning Altar queue empty" notice) rather
   than failing or spending money.
4. Metrics / Comments / Set-thumbnail also accept the same `channel`
   selector for manual runs. Community, growth-autopilot and monitor
   still operate on Channel 1 only until Morning Altar has its own data
   history; the brain now replenishes **both** channels, and the
   scheduler supervisor's dropped-slot recovery dispatches both Produce
   channels.

## 4. Adding a third channel later

1. Add a profile in `pipeline/channels.py` (new prefix, e.g. `PRAYER3_`).
2. Repeat §2 with a **new** GCP project + Gemini project + token.
3. Add the `prayer3` option + secret mapping to the workflows that need it.
4. Tag its scripts `channel: prayer3`. Nothing else changes.
