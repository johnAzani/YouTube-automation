# Seventh Channel Setup — The Provision Table (`prayer7`)

Status: **LIVE & PROVISIONED (`provisioned=True`) — all 5 `PRAYER7_*` GitHub Secrets connected and Day-1 launch queue (`0500`–`0503` + 4 Shorts) seeded.**
Every line of code, editorial & theological equipment, 30-scripture wisdom, open-doors & covenant provision roadmap (`0500`–`0529`),
Shorts namespacing (`short-provision…`), CTR thumbnail pack (`harvest` Royal Harvest Burgundy & Wheat-Gold grade),
Community Tab schedule, ES/PT localizations, bespoke brand artwork (`docs/media/provision-table-*.png`),
and isolated workflow readiness probes (`PRAYER7_READY`) are wired on `main`.

---

## Step 1 — Create the YouTube Channel & Upload Bespoke Branding
1. Sign into YouTube -> **Switch account -> View all channels -> Create a channel**:
   - **Name:** `The Provision Table`
   - **Handle:** `@TheProvisionTableDaily` *(if taken, share the exact handle you claim and we'll lock it in)*
2. Upload the 3 brand assets from `docs/media/` (see `docs/PROVISION_TABLE_BRANDING.md` for 1-click links & copy blocks):
   - **Picture:** `docs/media/provision-table-avatar.png` (`800 × 800` RGB)
   - **Banner image:** `docs/media/provision-table-banner.png` (`2560 × 1440` RGB, mobile-safe `1235 × 338`)
   - **Video watermark:** `docs/media/provision-table-watermark.png` (`150 × 150` RGBA transparent PNG) -> **Entire video**
3. Paste the **Description** (`<= 1,000` chars) and **Channel Keywords** from `docs/PROVISION_TABLE_BRANDING.md`.
4. Verify your phone number inside **YouTube Studio -> Settings -> Channel -> Feature eligibility -> Intermediate features** (unlocks custom thumbnails and videos over 15 minutes).

---

## Step 2 — Mint Isolated Google Cloud & Gemini Credentials (`$0.00/mo` Lock)
Create a **separate Google Cloud project** (e.g. `provision-table-automation`) so **The Provision Table** has its own independent **10,000 units/day** YouTube Data API v3 quota and Gemini free-tier pool:
1. Enable **YouTube Data API v3**.
2. On **Google Auth Platform -> Branding**, fill in:
   - App name: `Provision Table Automation`
   - Home page: `https://johnazani.github.io/YouTube-automation/app.html`
   - Privacy policy: `https://johnazani.github.io/YouTube-automation/privacy.html`
   - Terms of service: `https://johnazani.github.io/YouTube-automation/terms.html`
   - Authorized domain: `johnazani.github.io`
3. On **Audience**, click **Publish app** (`In production`) so the refresh token never expires after 7 days.
4. On **Clients**, create a **Web application** OAuth client with Authorized redirect URI `https://developers.google.com/oauthplayground`.
5. Exchange the 3 YouTube scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`) on OAuth Playground while selecting **The Provision Table** brand account, and generate a Gemini API key in **Google AI Studio** linked to that same new project.

---

## Step 3 — Save the 5 `PRAYER7_*` Repository Secrets in GitHub
Add under **Settings -> Secrets and variables -> Actions -> New repository secret**:
- `PRAYER7_GEMINI_API_KEY`
- `PRAYER7_YOUTUBE_CHANNEL_ID` *(from `youtube.com/account_advanced` while switched into The Provision Table)*
- `PRAYER7_YOUTUBE_CLIENT_ID`
- `PRAYER7_YOUTUBE_CLIENT_SECRET`
- `PRAYER7_YOUTUBE_REFRESH_TOKEN`

---

## Step 4 — Flip `provisioned=True` & Seed Launch Runway (`0500`–`0503`)
Once those 5 secrets are saved, reply **"Done"** (or send a screenshot) in chat and we will immediately seed the Day-1 `0500`–`0503` scripts + companion Shorts and flip `provisioned=True` on `"prayer7"` so **The Provision Table** goes live across all Nigeria Time (`WAT`) slots (**7:14 AM WAT**, **11:44 AM WAT** Short, **3:14 PM WAT**, **8:14 PM WAT**).
