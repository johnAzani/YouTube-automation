# Sixth Channel Setup — The Healing Balm (`prayer6`)

Status: **REGISTERED (`provisioned=False`) — Ready for YouTube Channel Creation & `PRAYER6_*` Secrets.**
Every line of code, editorial & theological equipment, 30-scripture healing & restoration roadmap (`0400`–`0429`),
Shorts namespacing (`short-healing…`), CTR thumbnail pack (`balm` Gilead sapphire-and-alabaster grade),
Community Tab schedule, ES/PT localizations, and bespoke brand artwork (`docs/media/healing-balm-*.png`)
are wired into the repository in full parity with Channels 1–5.

Because `provisioned=False` until you save the 5 `PRAYER6_*` GitHub Secrets, **zero scheduled runs or watchdog alerts** will fire prematurely while you set up the YouTube channel.

---

## Step 1 — Create the YouTube Channel & Upload Bespoke Branding
1. Sign into YouTube -> **Switch account -> View all channels -> Create a channel**:
   - **Name:** `The Healing Balm`
   - **Handle:** `@TheHealingBalmDaily` *(if taken, share the exact handle you claim and we'll lock it in)*
2. Upload the 3 brand assets from `docs/media/` (see `docs/HEALING_BALM_BRANDING.md` for 1-click links & copy blocks):
   - **Picture:** `docs/media/healing-balm-avatar.png` (`800 × 800` RGB)
   - **Banner image:** `docs/media/healing-balm-banner.png` (`2560 × 1440` RGB, mobile-safe `1235 × 338`)
   - **Video watermark:** `docs/media/healing-balm-watermark.png` (`150 × 150` RGBA transparent PNG) -> **Entire video**
3. Paste the **Description** (`<= 1,000` chars) and **Channel Keywords** from `docs/HEALING_BALM_BRANDING.md`.
4. Verify your phone number inside **YouTube Studio -> Settings -> Channel -> Feature eligibility -> Intermediate features** (unlocks custom thumbnails and videos over 15 minutes).

---

## Step 2 — Mint Isolated Google Cloud & Gemini Credentials (`$0.00/mo` Lock)
Create a **separate Google Cloud project** (e.g. `healing-balm-automation`) so **The Healing Balm** has its own independent **10,000 units/day** YouTube Data API v3 quota and Gemini free-tier pool:
1. Enable **YouTube Data API v3**.
2. On **Google Auth Platform -> Branding**, fill in:
   - App name: `Healing Balm Automation`
   - Home page: `https://johnazani.github.io/YouTube-automation/app.html`
   - Privacy policy: `https://johnazani.github.io/YouTube-automation/privacy.html`
   - Terms of service: `https://johnazani.github.io/YouTube-automation/terms.html`
   - Authorized domain: `johnazani.github.io`
3. On **Audience**, click **Publish app** (`In production`) so the refresh token never expires after 7 days.
4. On **Clients**, create a **Web application** OAuth client with Authorized redirect URI `https://developers.google.com/oauthplayground`.
5. Exchange the 3 YouTube scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`) on OAuth Playground while selecting **The Healing Balm** brand account, and generate a Gemini API key in **Google AI Studio** linked to that same new project.

---

## Step 3 — Save the 5 `PRAYER6_*` Repository Secrets in GitHub
Add under **Settings -> Secrets and variables -> Actions -> New repository secret**:
- `PRAYER6_GEMINI_API_KEY`
- `PRAYER6_YOUTUBE_CHANNEL_ID` *(from `youtube.com/account_advanced` while switched into The Healing Balm)*
- `PRAYER6_YOUTUBE_CLIENT_ID`
- `PRAYER6_YOUTUBE_CLIENT_SECRET`
- `PRAYER6_YOUTUBE_REFRESH_TOKEN`

---

## Step 4 — Flip `provisioned=True` & Seed Launch Runway (`0400`–`0403`)
Once those 5 secrets are saved, reply **"Done"** in chat and we will immediately seed the Day-1 `0400`–`0403` scripts + companion Shorts and flip `provisioned=True` on `"prayer6"` so **The Healing Balm** goes live across all Nigeria Time (`WAT`) slots (**7:14 AM WAT**, **3:14 PM WAT**, **4:44 PM WAT** Short, **8:14 PM WAT**).
