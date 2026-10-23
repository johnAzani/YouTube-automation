# Setup guide — from zero to first upload (all free)

Everything here is ₦0. Follow in order; items marked ⏱ have lead time, so start them first.

## 0. Prerequisites
- A Google account (new/brand account recommended for the channel)
- This repo **public** (Settings → General → Danger zone isn't involved — just create it
  public from the start. Public = free unlimited GitHub Actions minutes.)
- Read **[docs/DEEP_DIVE.md](DEEP_DIVE.md) §1** — three traps (OAuth 7-day token expiry,
  GitHub's 60-day schedule auto-disable, unaudited-API private lock) silently kill
  projects like this. This repo ships mitigations for all three; just don't undo them.

## 1. ⏱ Day 0 — start the slow things

### 1a. YouTube channel
1. Create a brand account channel for the niche chosen in PLAN.md §2.
2. Name/handle/avatar/banner (Canva free is fine). Note: the banner is branding, not art —
   clarity beats decoration.
3. In YouTube Studio: enable 2-step verification + custom thumbnails (Settings → Channel).

### 1b. Google Cloud + YouTube OAuth (phone-friendly; no local computer required)
1. In Google Cloud, create a project and enable **YouTube Data API v3**.
2. Configure Google Auth Platform for an **External** audience. For an unattended token,
   the app must be **In production**: Google says refresh tokens for non-basic scopes in
   **Testing** expire after 7 days. Keep the app unverified if it is only for your own
   account; expect Google's unverified-app warning and follow the consent screen. Do not
   authorize an app you do not recognize.
3. This repository's Pages site has a dedicated app overview and privacy policy:
   `https://johnazani.github.io/YouTube-automation/app.html` and
   `https://johnazani.github.io/YouTube-automation/privacy.html`. Put those links into
   Branding and add `johnazani.github.io` as an authorized domain. **Caveat:** Google
   requires verified domain ownership for app verification and may reject shared
   `github.io` hosting. If Google blocks the domain or publishing, a domain you control
   will be needed for a verified production app; do not claim to own GitHub's domain.
4. Create a **Web application** OAuth client and add this exact authorized redirect URI:
   `https://developers.google.com/oauthplayground`. Leave JavaScript origins blank. The
   local `scripts/youtube_oauth.py` flow is for a computer running a callback server; it
   is not the phone/GitHub path.
5. On <https://developers.google.com/oauthplayground/>, use your own client ID and secret,
   choose **Server-side**, **Offline**, and consent prompting, then authorize the scopes
   `https://www.googleapis.com/auth/youtube.upload` and
   `https://www.googleapis.com/auth/youtube.readonly`. Exchange the code and keep the
   refresh token private.
6. In GitHub repository Settings → Secrets and variables → Actions, create three
   separate secrets: `YOUTUBE_CLIENT_ID` (the Web client ID), `YOUTUBE_CLIENT_SECRET`
   (the raw Web client secret—not JSON), and `YOUTUBE_REFRESH_TOKEN` (the refresh token).
   Never commit or paste these values into issues, workflow inputs, or chat.
7. The workflow defaults to private uploads. Keep `AUTO_PUBLISH` unset/false until you
   deliberately choose a different visibility policy. The default YouTube API quota is
   enough for this repo's one-video-per-run schedule; a quota audit is not an OAuth
   setup prerequisite.

## 2. Free API keys (10 minutes)

| Key | Where | Used for |
|---|---|---|
| `PEXELS_API_KEY` | https://www.pexels.com/api/ | stock video/photos |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ | stock fallback |

Both are free API tiers; Pexels/Pixabay can return both video and photos. Without keys, the renderer tries Openverse, Wikimedia Commons, Internet Archive, and NASA using explicit commercial-use/attribution filters. It requests clips first, then photos; if an automated job still finds no legal visual, it fails that scene rather than publishing a generic card. Existing authored documentaries keep their story-specific photo fallback.

## 3. Remaster the existing deep dives and Shorts (free GitHub Actions)

After this workflow is present on the repository's default branch, open
**Actions → Remaster documentary assets → Run workflow**, select the branch you want the
refreshed demos published to, choose `all` (or deep dives/Shorts) and leave
**Search free video first** enabled. The workflow pushes its results back to whichever
branch it was dispatched from (it used to be pinned to a single Arena session branch and
refused to run anywhere else — fixed 2026-10-20). The workflow uses optional Pexels/Pixabay secrets,
then keyless free providers, preserves the whole source frame, writes per-scene license
ledgers, and publishes updated demos to GitHub Pages. If a source API is unreachable,
the existing scene-specific photo remains; the local sandbox itself may not reach those
external domains.

## 4. Mint the YouTube refresh token (OAuth Playground)

Use the phone-friendly Google OAuth Playground procedure in §1b. This repository's
`youtube_oauth.py` utility uses a local callback server and therefore requires a computer;
it is not needed when minting through OAuth Playground.

## 5. GitHub secrets

Repo → **Settings → Secrets and variables → Actions** → New repository secret:

| Secret | Value |
|---|---|
| `PEXELS_API_KEY` | from §2 |
| `PIXABAY_API_KEY` | from §2 |
| `YOUTUBE_CLIENT_ID` | Web OAuth client ID from Google Cloud |
| `YOUTUBE_CLIENT_SECRET` | raw Web OAuth client secret from Google Cloud (not JSON) |
| `YOUTUBE_REFRESH_TOKEN` | from §4 |
| `YOUTUBE_PLAYLIST_ID` | optional |
| `AUTO_PUBLISH` | `false` until the API audit passes; then `true` |

## 6. First production run

1. Write/approve a script in `content/queue/` (copy `content/queue/0003-how-lehman-brothers-died.md`
   — the required frontmatter shape is documented in `pipeline/script_doc.py`'s docstring).
   Checklist: PLAN.md §4.4 — every `originality:` flag must be honestly true
   (`human_rewrite` stays `false` until *you* have verified the facts and rewritten the
   narration; the originality gate blocks the run until then).

   **Shortcut for the fact-check:** `python scripts/factcheck.py 0003` writes
   `content/factcheck/0003-….md` — every claim in the script pulled out as a checkbox, next
   to the job's own declared sources, with a blank for the source you confirmed it against.
   It verifies nothing and pre-ticks nothing; it just saves you the hour of extraction. Tick
   the boxes, rewrite as you go, then flip the two flags **in the script file**. Re-running
   without `--force` will not clobber a worksheet you have already filled in.
2. Actions → **Produce video** → Run workflow (or wait for the 06:14/14:14 UTC cron).
3. Check the run summary + the `render-*` artifact (QC it: hook, pacing, captions).
4. A **release ticket** Issue appears → open the Studio link → replace thumbnail/title
   if needed → **Publish** (or schedule).
5. The workflow commits `content/queue/*.md` → `content/published/` automatically.

## 7. Day-to-day operations (the human part — 45–60 min/day)

- **Scripts** (the moat): 3 long-form/week + 5 Shorts/week. LLMs help research; you own
  the thesis, structure and line edits. If you didn't rewrite it, don't publish it.
- **Thumbnails/titles** (the CTR lever): always hand-tune before publish.
- **Comments/community**: reply to everything in month 1–2.
- **Weekly metrics review** (Studio): CTR ≥ 4%, avg view duration ≥ 40%. Kill formats
  that miss; double down on what works.

## 8. Monetization checklist (PLAN.md §5, §7)

- [ ] 500 subs + 3 uploads/90d + 3,000 hrs → apply for fan-funding tier (earliest money)
- [ ] 1,000 subs + 4,000 watch hrs → apply for full YPP **before 1 Feb 2027**
      (thresholds double to 8,000 hrs / 20M Shorts views after that date)
- [ ] AdSense for YouTube account → payment to Nigerian domiciliary account
      (GTB / Access / Zenith / UBA / First Bank — SWIFT wire)
- [ ] First affiliate links in descriptions (month 6+)

## Troubleshooting

| Symptom | Fix |
|---|---|
| Upload comes out private despite `public` | Expected for unaudited GCP projects — §1b; or set `AUTO_PUBLISH=true` after audit |
| `edge-tts` fails in CI | Microsoft can throttle unofficial endpoints — pipeline auto-falls back to placeholder audio; retry, or swap in Piper (local, free) |
| ffmpeg caption burn fails | Runner lacks libass — captions ship as a separate `.srt`; upload it as a YouTube caption track |
| Cron didn't fire on time | GitHub cron is best-effort (delays under load) — run manually via workflow_dispatch |
| 403 `quotaExceeded` on upload | Uploads are a separate 100/day bucket; `thumbnails.set` costs 50 units of the shared 10k pool — rare at our volume |


## Private channel Analytics

See [ANALYTICS.md](ANALYTICS.md) for report coverage, separate read-only consent,
private storage rules and explicit access gaps. Public-video snapshot success is
not proof of private Analytics or revenue access.
