# Eighth Channel Setup — The Covenant Shield (`prayer8`)

Status: **Registered (`provisioned=False`); four long-form scripts and companion Shorts are drafts awaiting review.** The owner has shown the five secret names in GitHub. A [read-only diagnostic](https://github.com/johnAzani/YouTube-automation/actions/runs/43005673639) successfully refreshed OAuth, matched the authorized account to the configured Channel ID, and listed Gemini models. This does not independently confirm that the configured ID is the intended Studio channel, or verify generation, TTS, quota, or billing.
Every line of code, editorial & theological equipment, 30-scripture divine protection, safe-keeping & strong-tower roadmap (`0600`–`0629`),
Shorts namespacing (`short-shield…`), CTR thumbnail pack (`fortress` Imperial Tabernacle Purple & Burnished Shield-Gold grade),
Community Tab schedule, ES/PT localizations, bespoke brand artwork (`docs/media/covenant-shield-*.png`),
and isolated workflow readiness probes (`PRAYER8_READY`) are wired on `main`.

---

## Step 1 — Create the YouTube Channel & Upload Bespoke Branding
1. Sign into YouTube -> **Switch account -> View all channels -> Create a channel**:
   - **Name:** `The Covenant Shield`
   - **Handle:** `@TheCovenantShieldDaily` *(if taken, share the exact handle you claim and we'll lock it in)*
2. Upload the 3 brand assets from `docs/media/` (see `docs/COVENANT_SHIELD_BRANDING.md` for 1-click links & copy blocks):
   - **Picture:** `docs/media/covenant-shield-avatar.png` (`800 × 800` RGB)
   - **Banner image:** `docs/media/covenant-shield-banner.png` (`2560 × 1440` RGB, mobile-safe `1235 × 338`)
   - **Video watermark:** `docs/media/covenant-shield-watermark.png` (`150 × 150` RGBA transparent PNG) -> **Entire video**
3. Paste the **Description** (`<= 1,000` chars) and **Channel Keywords** from `docs/COVENANT_SHIELD_BRANDING.md`.
4. Verify your phone number inside **YouTube Studio -> Settings -> Channel -> Feature eligibility -> Intermediate features** (unlocks custom thumbnails and videos over 15 minutes).

---

## Step 2 — Mint Isolated Google Cloud & Gemini Credentials (`$0.00/mo` Lock)
Create a **separate Google Cloud project** (e.g. `covenant-shield-automation`) so **The Covenant Shield** has its own independent **10,000 units/day** YouTube Data API v3 quota and Gemini free-tier pool:
1. Enable **YouTube Data API v3**.
2. On **Google Auth Platform -> Branding**, fill in:
   - App name: `Covenant Shield Automation`
   - Home page: `https://johnazani.github.io/YouTube-automation/app.html`
   - Privacy policy: `https://johnazani.github.io/YouTube-automation/privacy.html`
   - Terms of service: `https://johnazani.github.io/YouTube-automation/terms.html`
   - Authorized domain: `johnazani.github.io`
3. On **Audience**, click **Publish app** (`In production`) so the refresh token never expires after 7 days.
4. On **Clients**, create a **Web application** OAuth client with Authorized redirect URI `https://developers.google.com/oauthplayground`.
5. Exchange the 3 YouTube scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`) on OAuth Playground while selecting **The Covenant Shield** brand account, and generate a Gemini API key in **Google AI Studio** linked to that same new project.

---

## Step 3 — Save the 5 Isolated GitHub Repository Secrets
In **GitHub -> Settings -> Secrets and variables -> Actions -> New repository secret**, add:

| Secret Name | Value |
|---|---|
| `PRAYER8_GEMINI_API_KEY` | Free-tier Gemini API key from the new Google Cloud project |
| `PRAYER8_YOUTUBE_CHANNEL_ID` | Channel ID starting with `UC...` (**YouTube Studio -> Settings -> Channel -> Advanced settings**) |
| `PRAYER8_YOUTUBE_CLIENT_ID` | OAuth 2.0 Web Client ID for `covenant-shield-automation` |
| `PRAYER8_YOUTUBE_CLIENT_SECRET` | OAuth 2.0 Web Client Secret for `covenant-shield-automation` |
| `PRAYER8_YOUTUBE_REFRESH_TOKEN` | Refresh token authorized as `@TheCovenantShieldDaily` |

---

## Step 4 — Activate Live Daily Publishing
Review the four drafts `0600`–`0603` in `content/queue/`, using the matching `content/factcheck/` worksheets, and the four companion Shorts in `content/shorts-scripts/` and `content/shorts-queue/`. The worksheets are generated checklists, not fact verification. Confirm in YouTube Studio that the channel ID configured in GitHub belongs to the intended channel; the diagnostic only proves the configured ID matches the OAuth account. After human review and approval, mark the content approved, flip `provisioned=True`, and only then run the debut. TTS and publishing must still be validated through production execution.

**Important:** the current `produce.yml` schedule independently selects `prayer8` when its refresh-token secret is present; `provisioned=False` is not a global off switch. Review scheduled Actions as well as channel settings before relying on this status to pause publishing.
