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

### 1b. ⏱ Google Cloud project + OAuth production + YouTube API audit (lead time: days–weeks)
1. https://console.cloud.google.com → new project (e.g. `yt-automation-lab`).
2. Enable **YouTube Data API v3**.
3. OAuth consent screen: **External**. ⚠️ **The default "Testing" status expires refresh
   tokens every 7 days** — this is the #1 killer of unattended uploaders
   (DEEP_DIVE.md §1, Trap 1). Before minting any token you must move it to
   **In production**:
   - Fill branding: app name, support email, **homepage URL**, **privacy policy URL**
     (GitHub Pages/Notion is fine), and an **authorized domain** verified in Search
     Console.
   - Click **Publish app** (Testing → In production). Publishing ≠ verification — for a
     personal single-channel tool you click *"Advanced → Go to app (unsafe)"* once on
     your own consent screen. Long-lived tokens result.
4. Credentials → OAuth client ID → Desktop app → download JSON → save as
   `client_secret.json` locally (NEVER commit it).
5. Submit the **YouTube API Services Audit & Quota Extension form**
   (https://support.google.com/youtube/contact/yt_api_form). Required to lift the
   forced-private restriction on API uploads from unverified projects. Approval takes
   weeks — submit on day one.
6. Until it passes, the pipeline uploads **private** drafts and opens a "release ticket"
   GitHub Issue; you publish in YouTube Studio in ~2 clicks. This is fine — treat it as
   your mandatory human QC step.

## 2. Free API keys (10 minutes)

| Key | Where | Used for |
|---|---|---|
| `PEXELS_API_KEY` | https://www.pexels.com/api/ | stock video/photos |
| `PIXABAY_API_KEY` | https://pixabay.com/api/docs/ | stock fallback |

Both are free API tiers; Pexels/Pixabay can return both video and photos. Without keys, the renderer tries Openverse, Wikimedia Commons, Internet Archive, and NASA using explicit commercial-use/attribution filters. It requests clips first, then photos; if an automated job still finds no legal visual, it fails that scene rather than publishing a generic card. Existing authored documentaries keep their story-specific photo fallback.

## 3. Remaster the existing deep dives and Shorts (free GitHub Actions)

Open **Actions → Remaster documentary assets → Run workflow**, select branch
`arena/79365da2-youtube-automation` as the ref, choose `all` (or deep dives/Shorts) and leave
**Search free video first** enabled. The workflow uses optional Pexels/Pixabay secrets,
then keyless free providers, preserves the whole source frame, writes per-scene license
ledgers, and publishes updated demos to GitHub Pages. If a source API is unreachable,
the existing scene-specific photo remains; the local sandbox itself may not reach those
external domains.

## 4. Mint the YouTube refresh token (local, once)

```bash
pip install -r requirements.txt
python scripts/youtube_oauth.py --client-secret client_secret.json
```

Copy the printed `YOUTUBE_CLIENT_SECRET` and `YOUTUBE_REFRESH_TOKEN` values.

## 5. GitHub secrets

Repo → **Settings → Secrets and variables → Actions** → New repository secret:

| Secret | Value |
|---|---|
| `PEXELS_API_KEY` | from §2 |
| `PIXABAY_API_KEY` | from §2 |
| `YOUTUBE_CLIENT_SECRET` | from §3 (single-line JSON) |
| `YOUTUBE_REFRESH_TOKEN` | from §3 |
| `YOUTUBE_PLAYLIST_ID` | optional |
| `AUTO_PUBLISH` | `false` until the API audit passes; then `true` |

## 6. First production run

1. Write/approve a script in `content/queue/` (copy `0001-…md` as the template).
   Checklist: PLAN.md §4.4 — every `originality:` flag must be honestly true.
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
