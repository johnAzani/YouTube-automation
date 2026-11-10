# Fifth Channel Setup — The Family Altar (`prayer5`)

Status: **LIVE (`provisioned=True` as of 2026-11-10).**
Every line of code, editorial & theological equipment, 30-scripture household roadmap (`0300`–`0329`),
Shorts namespacing (`short-family…`), CTR thumbnail pack (`hearth` covenant emerald-and-gold grade),
Community Tab schedule, ES/PT localizations, bespoke brand artwork (`docs/media/family-altar-*.png`),
all 5 `PRAYER5_*` GitHub Secrets, and initial Day-1 launch scripts (`0300`–`0303`) are live on `main`.

---

## Step 1 — Create the YouTube Channel & Upload Bespoke Branding
1. Sign into YouTube on your account -> **Create a channel**:
   - **Name:** `The Family Altar`
   - **Handle:** `@TheFamilyAltarDaily` *(if taken, tell us the exact handle you claim and we'll lock it in)*
2. Upload the 3 brand assets from `docs/media/` (see `docs/FAMILY_ALTAR_BRANDING.md` for 1-click links & copy blocks):
   - **Picture:** `docs/media/family-altar-avatar.png` (`800 × 800` RGB)
   - **Banner image:** `docs/media/family-altar-banner.png` (`2560 × 1440` RGB, mobile-safe `1235 × 338`)
   - **Video watermark:** `docs/media/family-altar-watermark.png` (`150 × 150` RGBA transparent PNG) -> **Entire video**
3. Paste the **Description** and **Channel Keywords** from `docs/FAMILY_ALTAR_BRANDING.md`.
4. Verify your phone number inside **YouTube Studio -> Settings -> Channel -> Feature eligibility -> Intermediate features** (unlocks custom thumbnails and videos over 15 minutes).

---

## Step 2 — Mint Isolated Google Cloud & Gemini Credentials (`$0.00/mo` Lock)
Create a **separate Google Cloud project** (e.g. `family-altar-automation`) so **The Family Altar** has its own independent **10,000 units/day** YouTube Data API v3 quota and Gemini free-tier pool:
1. Enable **YouTube Data API v3**.
2. On **Google Auth Platform -> Branding**, fill in:
   - App name: `Family Altar Automation`
   - Home page: `https://johnazani.github.io/YouTube-automation/app.html`
   - Privacy policy: `https://johnazani.github.io/YouTube-automation/privacy.html`
   - Terms of service: `https://johnazani.github.io/YouTube-automation/terms.html`
   - Authorized domain: `johnazani.github.io`
3. On **Audience**, click **Publish app** (`In production`) so the refresh token never expires after 7 days.
4. On **Clients**, create a **Web application** OAuth client with Authorized redirect URI `https://developers.google.com/oauthplayground`.
5. Exchange the 3 YouTube scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`) on OAuth Playground while selecting **The Family Altar** brand account, and generate a Gemini API key in **Google AI Studio** linked to that same new project.

---

## Step 3 — Save the 5 `PRAYER5_*` Repository Secrets in GitHub
Add under **Settings -> Secrets and variables -> Actions -> New repository secret**:
- `PRAYER5_GEMINI_API_KEY`
- `PRAYER5_YOUTUBE_CHANNEL_ID` *(from `youtube.com/account_advanced` while switched into The Family Altar)*
- `PRAYER5_YOUTUBE_CLIENT_ID`
- `PRAYER5_YOUTUBE_CLIENT_SECRET`
- `PRAYER5_YOUTUBE_REFRESH_TOKEN`

---

## Step 4 — Flip `provisioned=True` & Seed Launch Runway
Once those 5 secrets are saved, flip `provisioned=True` on `"prayer5"` in `pipeline/channels.py` and seed the Day-1 `0300`–`0303` scripts so **The Family Altar** begins publishing immediately on all Nigeria Time (`WAT`) release slots.
