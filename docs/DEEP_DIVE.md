# Deep Dive — the thin details that make or break a ₦0 YouTube automation

Companion to [PLAN.md](../PLAN.md). PLAN.md is the strategy; this file is the engineering
and operations fine print, gathered from primary sources (GitHub Docs, Google/YouTube
docs) and 2026 industry data. Read §1 before you write a single line of config — those
three traps silently kill most GitHub-Actions YouTube projects.

---

## 1. The three traps that silently kill automation projects

### Trap 1 — Google OAuth "Testing" mode expires your refresh token every 7 days

This is the #1 reason unattended YouTube uploaders die in week two.

- An OAuth consent screen left in **Testing** (the default) issues refresh tokens that
  **hard-expire after 7 days**, regardless of usage. Your workflow uploads fine for a
  week, then dies with `invalid_grant` on a Saturday morning.
- Source: Google's own help text — *"Authorizations by a test user will expire seven days
  from the time of consent. If your OAuth client requests an offline access type and
  receives a refresh token, that token will also expire."*
- **The fix (in this exact order, once):**
  1. OAuth consent screen → fill **branding**: app name, support email, **homepage URL**,
     **privacy policy URL** (a GitHub Pages or Notion page is fine), and an **authorized
     domain** you verified via Search Console (GitHub Pages domain works).
  2. Click **Publish app** (moves status Testing → **In production**). Publishing ≠
     verification; an unverified production app still issues long-lived tokens — you just
     click *"Advanced → Go to [app] (unsafe)"* once on your own account's consent screen.
  3. **Only then** run `scripts/youtube_oauth.py` to mint the refresh token, and store it
     in the `YOUTUBE_REFRESH_TOKEN` secret.
- In-production tokens then last indefinitely (they can still expire after **6 months of
  non-use** — irrelevant here since the pipeline refreshes daily).
- Note: `youtube.upload` is a *sensitive* scope. Full Google verification is only needed
  for apps serving many users. For a single-channel personal tool, the unverified
  production path above is the standard approach.

### Trap 2 — GitHub disables scheduled workflows after 60 days of repo inactivity

- **In a public repository, `schedule:` workflows are auto-disabled when there is no
  repository activity for 60 days.** (GitHub Docs, "Disabling and enabling a workflow".)
  Disabling is near-silent: the cron just stops firing. In a repo where cron *is* the
  product, this is fatal.
- Crucial subtlety (confirmed by multiple 2026 incident reports): **only pushes to the
  default branch reliably reset the timer.** Workflow runs, issues, and even API
  `PUT /actions/workflows/{id}/enable` calls have been observed *not* to reset it in
  some cases. API re-enable *does* un-disable a workflow that already died.
- **Belt-and-braces mitigation — shipped in this repo as `.github/workflows/keepalive.yml`:**
  runs monthly (and every produce run), (a) commits a timestamp file (resets the
  activity clock), and (b) calls the enable API on every scheduled workflow (self-heals
  if anything got disabled). Keep it as the one workflow you never delete.
- Also note: cron events only fire from the **default branch**, and are best-effort
  (GitHub documents delays under load; independent measurements show ~64% slot
  reliability at 15-minute intervals with ~7 min median delay — fine for 2×/day
  content, useless for SLAs).

### Trap 3 — API uploads from unaudited GCP projects are forced private

- Since 28 Jul 2020, `videos.insert` from unverified projects has been restricted to
  `private` (docs around this have fluctuated in Oct 2026 — plan for both worlds).
- Fix: submit the **YouTube API Services Audit & Quota Extension form** on day one;
  until it passes, the pipeline's private-upload + human-publish flow is not a
  workaround, it is the designed QC step.

---

## 2. The economics in thin detail

### 2.1 Audience geography is the #1 revenue lever (bigger than niche)

2026 CPM/RPM data (multiple trackers, ranges vary by methodology):

| Audience country | Typical long-form RPM | vs US |
|---|---|---|
| United States | **$8–$18** (finance up to $25–30) | 1× |
| United Kingdom / Canada / Australia | $6–$14 | 0.7–0.9× |
| South Africa | $1–$4 | 0.2–0.4× |
| **Nigeria** | **$0.30–$2** (often $0.50–1) | **0.05–0.15×** |
| India / Indonesia / Brazil | $0.30–$1.50 | 0.05–0.15× |

Implications (these are strategy decisions, not footnotes):

1. **Produce in English for a US/UK/CA/AU audience.** Neutral US/UK narration voice
   (`en-US-ChristopherNeural`, `en-GB-RyanNeural`), global-perspective topics, US
   spelling in metadata. The same 100K views are worth **10–20× more** depending on
   who watches. This is how a small channel outsells a big one.
2. **Publish on a US afternoon schedule** (UTC 15:00–21:00 catches US morning/afternoon
   and EU evening). Data-backed best slots: weekdays 12–4 PM, Friday best day;
   Shorts 7–11 AM (audience-local).
3. If a video unexpectedly pops in a low-RPM region: don't chase it — algorithm
   diversification across geographies is normal.

### 2.2 Revenue scenario model (ads only, one channel, history/science niche, $5–8 RPM)

| Scenario | Month 6 | Month 12 | Month 24 | What it assumes |
|---|---|---|---|---|
| Bear (most common outcome) | $0 | $50–150 | $300–800 | Slow traction, 1–2 videos pop late |
| Base (good execution) | $0–100 | $400–1,000 | $1,500–4,000 | Steady 3×/week, CTR ≥ 4%, AVD ≥ 45% |
| Moon (one breakout + consistency) | $200–1,000 | $2,000–8,000 | $8,000–30,000 | 1–2 videos >1M views, format-market fit |

Cross-checks from public 2026 data: well-executed faceless channels typically cross YPP
in **6–12 months**; first payouts $50–500; $1K–$5K/mo by months 12–18; a documented
median-ish case earned **$895 total in two years** with inconsistent posting (the
realistic outcome of "post when it feels like it"). The Forbes-featured outlier hit YPP
in 45 days. The honest takeaway: **variance is enormous, volume of quality output is the
only controllable.**

### 2.3 What "millions per month" actually requires

```
$1,000,000/month at $10 RPM  =  100,000,000 monetized views/month
$1,000,000/month at $25 RPM  =   40,000,000 monetized views/month
```
That is MrBeast territory (top ~50 channels on Earth). The compounding path that actually
gets there — if it ever does — looks like:
Year 1: one channel → $500–2K/mo · Year 2: $2–10K/mo + first sponsorships ·
Year 3: portfolio of 2–5 channels + products ($10–50K/mo) · Year 4+: media brand.
Plan for the middle; treat the tail as tail. The ₦0 infrastructure is what makes years
1–2 survivable.

### 2.4 Revenue stack — exact mechanics

| Stream | When | Mechanics (2026) |
|---|---|---|
| Watch-page ads | YPP full tier | Creators keep **55%** of ad revenue (45% YouTube). RPM ≈ 0.4–0.5× CPM. |
| Shorts ads | YPP full tier | Shared revenue pool, ~45% after music costs; **RPM $0.03–0.10** — growth tool, not income. |
| YouTube Premium | YPP full tier | Pro-rata watch-time share; ~10–15% of ad income for US-heavy audiences. |
| Super Thanks / Memberships | Expanded YPP (500 subs) | Small ($5–50/mo early) but real proof-of-revenue. |
| **Mid-roll ads** | 8+ min videos | Our 8–12 min target exists for this. |
| Sponsorships | ~10K+ views/video | Market rate ≈ **$15–30 CPM per integration** (e.g. 50K views × $20 = ~$1K per dedicated mention). |
| Affiliate links | From month 3–6 | Amazon Associates (free), software programs (20–40% recurring), finance ($50–200/signup — only in non-advisory framing). |
| Digital product | From ~month 9 | PDF research packs / courses; Gumroad free tier. |

### 2.5 Getting the money to Nigeria (AdSense)

- YPP is open to Nigeria; AdSense for YouTube pays by **wire transfer to a domiciliary
  (USD) account** — GTBank, Access, Zenith, UBA, First Bank all work (SWIFT code needed).
- **Payment threshold:** $100 (or local-currency equivalent) before any payout; payments
  process ~21st–26th of the month following accrual.
- **Tax:** complete the AdSense **W-8BEN** (or W-8BEN-E) online form (foreign status —
  Nigeria has no US tax treaty, so expect standard withholding on US-sourced income;
  consult a local accountant for FIRS obligations). This is free to do; just don't skip
  it or payments are blocked.
- Payoneer is a common alternative via AdSense in some regions; wire is simplest.

---

## 3. Growth mechanics — the numbers we grade every video against

### 3.1 Benchmarks (2026 aggregated data)

| Metric | Healthy | Good | Excellent | Action if below |
|---|---|---|---|---|
| Impressions CTR (long-form) | 4–6% | 7%+ | 10%+ | New thumbnail first, title second (half of all channels sit at 2–10%) |
| Avg % viewed (6–10 min) | 40–50% | 55–60% | 65%+ | Fix the first 30 s hook; check drop-off graph at 0:30 |
| Avg % viewed (10–15 min) | 35–45% | 50%+ | — | Consider cutting to 8–9 min |
| Shorts APV (< 30 s) | 65%+ | 80%+ | 90%+ | Rewritten hook / faster cuts |
| Shorts APV (30–60 s) | 45–50% | 65%+ | 80%+ | Target 22–45 s band |
| Subs per 1,000 views (long-form) | 2–5 | 6–10 | 10+ | Clearer channel promise / series branding |

### 3.2 Shorts strategy details (the sub engine)

- **Sweet spot 22–45 s** (50–60 s Shorts pull ~22× the views of <10 s ones; sub-15 s
  collapsed in 2026 reach tests — too short to clear absolute watch-time gates).
- Algorithm's rough push gates: ~65% AVD for <30 s, ~50% for 30–60 s. Below the bar,
  distribution stops — don't "rescue" a dead Short, make a new one.
- 2026 Metricool study (800K videos): Shorts views per post **+127% YoY**, but average
  watch time **−67%** (0.26 min) — the feed rewards high-turnover, mid-length clips.
- Cadence: 4–7 Shorts/week, cut from long-forms (a "clip pipeline" job is on the roadmap;
  manual cutting is fine in month 1). Post Shorts in the 7–11 AM window of the target
  audience (US), long-form at 12–4 PM (Friday strongest).

### 3.3 Format rotation (anti-template discipline)

Rotate at least 4 format shapes across any 10 videos so no channel-level template
emerges (this is both an algorithmic freshness lever AND the inauthentic-content shield):

1. Timeline narrative (chronological deep-dive)
2. Mystery/reveal ("What the records show")
3. Comparison/counterfactual ("What if X had failed")
4. Listicle-with-thesis (ranked, argued — not a slideshow)
5. Explainer of a mechanism (how a thing works)

---

## 4. The 12-week countdown to the 1 Feb 2027 threshold change

Today: **18 Oct 2026**. New applicants after **1 Feb 2027** need 8,000 watch hours /
20M Shorts views (double). Channels already in YPP keep the old bar. Everything below
is backwards-planned from submitting the application **by 15 Jan 2027** (buffer for
review).

| Week | Dates (2026–27) | Content target | Growth target | Ops |
|---|---|---|---|---|
| W1 | Oct 18–24 | Scripts 1–6 written + approved | — | Setup week: channel, GCP+audit form, keys, secrets, keepalive live |
| W2–4 | Oct 25–Nov 14 | 3 LF + 5 Shorts/wk (9 LF total) | 100–300 subs | Learn: first CTR/AVD data; iterate hooks weekly |
| W5–8 | Nov 15–Dec 12 | 3 LF + 7 Shorts/wk (12 LF) | 300–700 subs, ~1,000 hrs | Double down on best format; kill worst |
| W9–11 | Dec 13–Jan 2 | 3 LF + 7 Shorts/wk | 700–1,000 subs, ~3,000 hrs | Apply fan-funding tier at 500 subs |
| W12 | Jan 3–15 | 3 LF + 7 Shorts/wk | **1,000 subs + 4,000 hrs** | **Submit full YPP application by Jan 15** |
| Buffer | Jan 16–31 | Keep posting | — | Application review + AdSense/W-8BEN setup |

If the target slips: **still apply before Feb 1 with whatever qualifies later** — you
keep the 4,000-hour bar for the application window you entered. The single worst outcome
is missing the date and applying into the 8,000-hour regime.

4,000 watch hours sanity math: 40 long-forms × 8 min × 7.5 average views each = 400
hours… no: **each view of an 8-min video at 50% AVD = 4 watch-minutes**, so 4,000 hours
= 60,000 such views total. Spread over 30–40 videos that is **1,500–2,000 average views
per video** — one moderately successful video (~100K views) covers the entire bar, which
is why library-building + Shorts amplification from week 1 matters more than perfection.

---

## 5. Operating SOP (the human's 45–60 min/day)

### Daily
- [ ] 20–30 min: script work (research → draft → rewrite). Two scripts/week minimum buffer.
- [ ] 10 min: approve queue items (run originality checklist honestly), check overnight run artifacts.
- [ ] 10 min: publish QC on any release ticket (thumbnail swap, title tune, publish/schedule).
- [ ] 5 min: reply to every comment (months 1–2; then top comments).

### Weekly (30 min, e.g. Friday)
- [ ] Metrics: CTR, AVD%, subs, watch hrs vs the §3.1 table. Note the week's best/worst.
- [ ] Format-rotation check on the next 3 scripts.
- [ ] One improvement shipped to the pipeline or the format (a/b title pattern, new b-roll source, etc.).

### Monthly (60 min)
- [ ] Retro: watch-hour pace vs the §4 table. If behind by >20%, raise Shorts volume or change topic-selection criteria — not output volume of the same thing.
- [ ] Verify keepalive workflow ran (§1 Trap 2).
- [ ] Verify OAuth token still refreshing (a failed upload is the alarm — see pipeline logs).
- [ ] Check `credits.json` accumulates; spot-check licences.

---

## 6. Toolchain alternatives (all still ₦0 unless noted)

| Need | Primary (shipped) | Free alternatives | Paid upgrade path (later) |
|---|---|---|---|
| TTS | `edge-tts` (Edge neural, no key) | Piper (fully local, offline), gTTS | ElevenLabs (~$5–22/mo) |
| Stock video | Pexels (free key) | Pixabay, Coverr, Openverse | Storyblocks |
| Stock images | Pexels/Pixabay | Wikimedia Commons, NASA, Internet Archive | — |
| Music | none (default) | YouTube Audio Library, Pixabay Music (CC0), local CC0 files via `MUSIC_DIR` | Artlist/Epidemic |
| Assembly | ffmpeg (runners) | — | Descript/Runway (not needed) |
| Script research | Human + free LLM tiers (Gemini, etc.) | Wikipedia/primary sources (better anyway) | — |
| Thumbnails | ffmpeg plate (draft) | Canva free (human polish) | Photoshop |
| Scheduling | GitHub Actions cron | — | — |
| Metrics | YouTube Studio (free) | `yt-dlp` metadata scrapes | vidIQ/TubeBuddy ($0–8/mo) |

Every paid tool is a *convenience* purchase after revenue exists — nothing in the
critical path needs money.

---

## 7. Licensing & compliance matrix

| Asset | Licence | Commercial use | Attribution | Notes |
|---|---|---|---|---|
| Pexels photos/videos | Pexels License | ✅ | Not required | No "identifiable people in bad light" etc. — review clips |
| Pixabay media | Pixabay Content License | ✅ | Not required | No standalone redistribution |
| Wikimedia Commons | CC-BY / CC-BY-SA / PD (per file) | ✅ | **Required for CC-BY** | `credits.json` logs the licence; add to description when CC-BY |
| NASA media | Public domain | ✅ | Requested (not required) | "NASA" logo use restricted — fine in narration context |
| edge-tts audio | Unofficial MS endpoint | ⚠️ gray | — | Fine for starting; swap to Piper/ElevenLabs if commercial risk matters to you |
| YouTube Audio Library | YouTube license | ✅ | Not required | Only usable in YouTube videos — fine here |
| AI disclosure | YouTube policy | — | — | Required only for *realistic synthetic media* (e.g. photoreal fake footage); synthetic narration over real archives typically doesn't trigger it — set `ai_disclosure` truthfully per video |

Never use: unlicensed movie/documentary clips, other creators' footage ("reused
content" policy), scraped text read verbatim ("inauthentic content" policy).

---

## 8. Scaling playbook (after channel #1 earns)

1. **$1K/mo milestone:** systematize the SOP → outsource nothing yet; the pipeline is
   already the intern. Bank the template: this repo becomes the production OS.
2. **Channel #2** (month 9–15): same infra, `CONTENT_DIR` per channel, separate YouTube
   secrets. Target a *different* niche/format so no cross-channel template pattern.
3. **Sponsorship readiness** at ~50K+ views/video: media kit (one page), rate card at
   $20 CPM, inbox standard pitch.
4. **Portfolio math:** 3 channels × $3K/mo is both more achievable and more robust than
   1 × $10K/mo — different algorithms, different risks (a single demonetization event
   cannot zero the business).
5. Reinvest first profits: still ₦0 infra; money goes into thumbnail tools, better TTS,
   or paid research databases — never into paid view schemes (policy termination risk).

---

## 9. Sources (fine-print research log, 18 Oct 2026)

- GitHub Docs — scheduled workflow 60-day auto-disable:
  https://docs.github.com/actions/managing-workflow-runs/disabling-and-enabling-a-workflow ·
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- Keepalive patterns (push resets the timer; API enable self-heals):
  https://github.com/orgs/community/discussions/147369 · multiple 2026 incident write-ups
  (camptocamp/docker-postgres#28, kasenteoh/nous#256)
- Google OAuth Testing-mode 7-day refresh-token expiry (official):
  https://support.google.com/cloud/answer/15549945 · Google API "invalid_grant" docs:
  https://developers.google.com/google-ads/api/docs/get-started/common-errors
- YouTube Data API unverified-project private lock & audit:
  https://developers.google.com/youtube/v3/docs/videos/insert ·
  https://support.google.com/youtube/answer/7300965 ·
  https://developers.google.com/youtube/data/revision_history
- CPM/RPM by country 2026: https://milx.app/en/cases/in-what-countries-cpm-are-the-highest ·
  https://theloops.live/tools/earnings-by-country ·
  https://youseo.app/youtube-rpm-by-country · https://creaticalc.com/blog/youtube-cpm-rates-by-country
- CTR/retention/Shorts benchmarks 2026:
  https://www.dataslayer.ai/blog/youtube-algorithm-2025-how-to-get-your-videos-recommended ·
  https://humbleandbrag.com/blog/youtube-audience-retention-benchmarks ·
  https://metricool.com/youtube-shorts-algorithm/ ·
  https://www.socialync.io/blog/youtube-shorts-algorithm-2026 ·
  https://postfa.st/blog/best-time-to-post-on-youtube
- Faceless channel timelines/earnings 2026:
  https://fluxnote.io/blog/how-much-faceless-youtube-channel-earns-2026 ·
  https://frameloop.ai/blog/faceless-youtube-statistics-2026 ·
  https://faceless.my/blog/is-faceless-youtube-channel-worth-it/ ·
  https://www.forbes.com/sites/jodiecook/2026/09/25/how-to-build-a-faceless-youtube-channel-that-pays-10000-a-month/
- Nigeria AdSense payout & YPP:
  https://guidescafe.ng/step-by-step-guide-to-set-up-youtube-monetization-in-nigeria-including-tax-implications-and-compliance/
