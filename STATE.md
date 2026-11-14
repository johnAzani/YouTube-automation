# 🕊️ The Secret Place — Master Project State & Living Memory Ledger
**Document Status:** Permanent Single Source of Truth (`STATE.md`)  
**Channel Identity:** *The Secret Place* (`@TheSecretPlace`)  
**Production Studio:** Autonomous ₦0 / $0 Faith & Scripture Production Lab on GitHub Actions  
**Last Synchronized:** 2026-11-03 (Nigeria time, WAT / UTC+1 — all human-facing times in this document are Nigeria time, see §7)  
**Primary Banking Rail:** First Bank of Nigeria (FBN) USD Domiciliary Account (`FBNINGLA`)

---

## ⚠️ CRITICAL NOTICE FOR ANY FUTURE AI SESSION OR AGENT
> **DO NOT TREAT THIS CONVERSATION AS A BLANK SLATE.**  
> Everything in this document has already been built, tested, and verified.
> - **DO NOT** re-ask the user if they have YouTube secrets or credentials (they are ALREADY configured and verified).
> - **DO NOT** attempt to change, audition, or suggest new voices (Google Gemini TTS `Charon` is permanently locked).
> - **DO NOT** re-ask how to monetize or set up Selar (both the Show Love hub and Product #2 are ALREADY live).
> - **DO NOT** use or mention personal creator names (`John Azani` or `Azani John`); the channel is exclusively *The Secret Place*.
> - **DO NOT** add manual review gates to the website dashboard; uploads happen directly to YouTube on schedule.
> - **DO NOT** tell the owner a time in UTC. He thinks in Nigeria time (WAT, UTC+1, Africa/Lagos — Abuja). Give him the Nigerian wall clock with a plain day: "tonight at 8:14pm", "tomorrow morning at 4:14am", "Friday 7:41pm". Never "03:14 UTC", never a bare cron string. The cron expressions in `.github/workflows/` stay in UTC — they must, GitHub has no other clock — but every time a human has to read one, it gets translated first. The full translation table is in §7.

---

## 1. Permanent System Invariants ($0.00 Hard Cost Lock)

1. **$0.00 / Month Hard Cost Lock:** Under no circumstances may any pipeline component require or transition to a paid subscription, billable cloud tier, or credit card charge. If external rate limits or free quotas are reached, jobs fail closed (pause and wait for next reset).
2. **Permanent Voice Standard:** Google Gemini API TTS (`model: gemini-3.8-flash-tts`, `voice: Charon`) locked at free tier.
3. **Visual Theme Standard:** Signature DOCOGA REELS v2 sapphire glassmorphic visual system with directional drop shadows, Inter typography, radiant gold active-word illumination, and full-bleed 16:9 widescreen long-form and 9:16 vertical Shorts plates.
4. **Persona & Attributions:** Strictly *The Secret Place* editorial team. Zero mentions of personal creator names in scripts, descriptions, metadata, or audio.
5. **Website Function:** The website (`docs/index.html` / GitHub Pages) is exclusively an **analytics display and asset download dashboard**. There is NO manual review gate on the website; releases are published directly to YouTube.

---

## 2. Completed Milestones (100% Done & Verified)

### A. YouTube Credentials & Upload Automation (ALREADY ACTIVE)
* **Status:** Verified and functional. Videos have already been uploaded previously.
* **Stored in GitHub Secrets:**
  * `YOUTUBE_CLIENT_ID` (OAuth 2.0 Web Client ID)
  * `YOUTUBE_CLIENT_SECRET` (OAuth 2.0 Client Secret)
  * `YOUTUBE_REFRESH_TOKEN` (Minted OAuth refresh token with upload & SSL scopes)
  * `GEMINI_API_KEY` (Free Google AI Studio key)
  * `AUTO_PUBLISH=true` (Releases publish directly as public)
* **Release Schedule (`.github/workflows/produce.yml`):**
  * `06:14 UTC` (**7:14am Nigeria time** — morning scripture devotional)
  * `14:14 UTC` (**3:14pm Nigeria time** — US transatlantic afternoon priming)
  * `20:14 UTC` (**9:14pm Nigeria time** — nighttime bedtime prayer surge)

### B. Nigerian Banking & Monetization Architecture (ALREADY ACTIVE)
* **Target Bank:** First Bank of Nigeria (FBN).
* **Account Type:** USD Domiciliary Account (SWIFT: `FBNINGLA`).
* **AdSense Rail:** Direct international SWIFT wire transfers from Google Ireland/US into First Bank USD account with zero middleman or currency conversion loss.
* **Selar.co Store Integration:** Fully operational with global card/Apple Pay checkout in USD, GBP, EUR, and NGN settling directly into First Bank:
  1. **Voluntary Ministry Offering / Show Love Hub:** **LIVE** at  
     👉 **[https://selar.com/showlove/thesecretplace](https://selar.com/showlove/thesecretplace)**
  2. **Product #2 (30-Night Scripture Protection Prayer Journal PDF):** **LIVE** at  
     👉 **[https://selar.com/i000qy7g39](https://selar.com/i000qy7g39)** (Discounted: ~~₦5,000~~ $\rightarrow$ **₦3,000** / $3.00 USD)
* **Automated Release Descriptions (`pipeline/social_pack.py`):** Automatically appends both live links into every future video description:
  ```text
  📥 OFFLINE BEDTIME PRAYER SANCTUARY:
  • 30-Night Scripture Protection Prayer Journal: https://selar.com/i000qy7g39
  • Partner in Prayer & Voluntary Ministry Support: https://selar.com/showlove/thesecretplace
  ```

### C. Digital Product Deliverables
* **30-Night Prayer Journal PDF (`content/products/30_night_prayer_journal.pdf`):** Complete 34-page printable companion featuring:
  * Page 1: Midnight Sapphire & Gold framing cover plate.
  * Page 2: Pastoral Introduction & The 4-Step Bedtime Sanctuary Ritual.
  * Pages 3–32: 30 Dedicated Nightly Devotionals, Spoken Authority Declarations, Guided Prayers, and Ruled Bedside Writing Lines for Cares & Daily Mercies.
  * Page 33: Bedside Emergency Scripture Shield for Panic, Insomnia, Bad Dreams, and Grief.
  * Page 34: The Priestly Benediction (Numbers 6:24-26) and partner invitation.
* **Direct 1-Tap Dashboard Downloads (`docs/index.html`):** The admin dashboard allows 1-tap browser downloads of:
  * `products/30_night_prayer_journal.pdf` (PDF)
  * `products/the-secret-place-selar-products-pack.zip` (Complete bundle with covers + JSON listings + PDF)
  * `products/cover_prayer_journal.png` (1080×1080 cover)
  * `products/cover_offline_audio_pack.png` (1080×1080 cover)

### D. Algorithmic Guardrails & Safety Shields
* **Duplicate Prevention Shield:** `pipeline/upload.py` queries channel titles before upload; unlinks matching queue manifests to prevent duplicate reels.
* **Pastoral Comment Engine (`.github/workflows/comments.yml`):** Autonomous responder locked at 20 replies/day (1,000 YouTube Data API units / 10% daily budget), zero duplicate replies, crisis helpline auto-escalation (988 US/CA, 111 UK), crypto scammer auto-silencing.
* **Community Tab Autopilot (`.github/workflows/community.yml`):** Scheduled Wednesday & Sunday prayer polls and thanksgiving cards at 8:14pm local.
* **Unified Shorts & Long-Form Background Music Lock (`tools/score.py`, `pipeline/prayer_visuals.py`):** Every long-form prayer video now synthesizes and mixes the exact same reverent stereo Shorts background music score (`tools/score.py::generate_score` — stereo-detuned `Am–F–C–G–Am–Dm–F–E` pad bed cycled at ~7.0s per chord, 55/82.4 Hz sub foundation, soft heartbeat pulse, ambient breath, scene-cut swells, `"Amen"` hush, and `volume=0.58` stereo `amix` + `alimiter=0.95`).
* **Dark Bedroom Sanctuary (`pipeline/dark_screen.py`):** 3 minutes of DOCOGA REELS v2 glassmorphism cross-fading over 45 seconds into pure OLED pitch black (`RGB 0,0,0`) while unbroken 432 Hz audio plays all night.

---

## 3. Current Queue & Script Inventory

### Approved & Ready for Production in `content/queue/` (22 full-length prayers ≥ 850 spoken words + 4 Shorts):
1. `0011-psalm-27-the-lord-is-my-light-and-my-salvation--fe.md` (Approved, 967 spoken words — re-authored with authentic KJV Psalm 27)
2. `0014-psalm-34-the-angel-of-the-lord-encampeth.md` (Approved, 922 spoken words)
3. `0015-psalm-91-5-6-deliverance-from-terror-by-night.md` (Approved, 882 spoken words)
4. `0016-psalm-91-11-12-angelic-guardians-bed.md` (Approved, 885 spoken words)
5. `0017-psalm-4-8-in-peace-i-will-lie-down-and-sleep.md` (Approved, 888 spoken words — unpaused after false burst `429`)
6. `0019-psalm-16-7-8-counsel-in-the-night-seasons.md` (Approved, 958 spoken words)
7. `0020-psalm-18-2-my-rock-my-fortress-my-deliverer.md` (Approved, 902 spoken words)
8. `0021-psalm-31-1-5-committing-my-spirit-to-his-hand.md` (Approved, 1,123 spoken words)
9. `0022-psalm-37-3-4-7-rest-in-the-lord-wait-patiently.md` (Approved, 900 spoken words)
10. `0023-psalm-63-5-7-remembering-god-upon-my-bed.md` (Approved, 892 spoken words)
11. `0024-psalm-139-11-12-darkness-is-as-light-to-him.md` (Approved, 888 spoken words)
12. `0025-proverbs-3-24-26-when-you-lie-down-sleep-is-sweet.md` (Approved, 918 spoken words)
13. `0026-isaiah-26-3-4-kept-in-perfect-peace.md` (Approved, 1,029 spoken words)
14. `0027-isaiah-41-10-upholding-you-with-his-right-hand.md` (Approved, 883 spoken words)
15. `0028-matthew-11-28-30-rest-for-the-weary-soul.md` (Approved, 853 spoken words)
16. `0029-john-14-27-my-peace-i-give-unto-you.md` (Approved, 1,075 spoken words)
17. `0030-philippians-4-6-7-the-peace-that-guards-heart-and-mind.md` (Approved, 895 spoken words)
18. `0031-2-timothy-1-7-power-love-and-a-sound-mind.md` (Approved, 876 spoken words)
19. `0032-1-peter-5-6-7-casting-all-your-care-upon-him.md` (Approved, 875 spoken words)
20. `0033-numbers-6-24-26-the-priestly-benediction-of-peace.md` (Approved, 855 spoken words)
21. `0034-psalm-91-complete-night-prayer-of-divine-protection.md` (Approved, 975 spoken words — full 16-verse KJV Psalm 91 sleep sanctuary)
22. `0035-psalm-23-complete-night-prayer-restore-my-soul.md` (Approved, 995 spoken words — full 6-verse KJV Psalm 23 sleep sanctuary)

### Armed Brain-Authored Shorts in `content/shorts-queue/` + `content/shorts-scripts/` (9 Ready):
* `short-psalm34`, `short-psalm91v5`, `short-psalm91v11`, `short-psalm4v8`, `short-psalm16v7`, `short-psalm18v2`, `short-psalm31v5`, `short-proverbs3v24`, `short-isaiah26v3` — all 9 validated (`90–165` words, bold 2–3 line DOCOGA REELS v2 kinetic cards, exact KJV text, local `words-{key}.json` alignment), paced at `>= 3.0 hours` between automatic Short releases, and replenished autonomously by `gemini_brain.yml` whenever ready Shorts drop below `6`.

### Published Video Records in `content/published/`:
* `0008-psalm-91-prayer-of-divine-protection.md` (`7RDX0fbIOtQ` — Psalm 91 Brief Blessing, `ctr-v3-cinema` thumbnail synced, auto-retrofitted with Selar links)
* `0009-psalm-23-the-lord-is-my-shepherd.md` (`JZv67RNPCEI` — deleted remotely on YouTube; replaced in queue by full-length `0035`)
* `0010-psalm-121-he-who-keeps-you-will-neither-slumber-no.md` (`6M6oV8MxD9s` — Psalm 121, `ctr-v3-cinema` thumbnail synced, title & Selar metadata auto-retrofitted)
* `0013-psalm-46-god-is-our-refuge-and-strength.md` (`1g8TXHD0Xks` — Psalm 46, `ctr-v3-cinema` thumbnail synced, auto-retrofitted with Selar links)
* `0018-psalm-3-3-5-the-shield-that-lifts-my-head.md` (`vs2xt72CgcI` — Psalm 3:3-5, `ctr-v3-cinema` thumbnail synced, auto-retrofitted with Selar links)
* `short-0006-psalm-46-god-is-our-refuge.md` (`mjr36vC_PtM` / `short-psalm46`, published Tuesday 3 November 2026 at 9:09pm Nigeria time)
* `short-0005-psalm-27-the-lord-is-my-light.md` (`KkPAtMLoGf4` / `short-psalm27`, published Tuesday 3 November 2026 at 7:58pm Nigeria time)
* `short-0004-psalm-121-he-who-keeps-you.md` (`xkpfupurX-0` / `short-psalm121`, published Tuesday 3 November 2026 at 7:43pm Nigeria time)
* `short-0003-psalm-23-the-lord-is-my-shepherd.md` (`kLgHN57fb1w` / `short-psalm23`, published Tuesday 3 November 2026 at 3:14pm Nigeria time)
* `short-0002-psalm-91-prayer-of-protection.md` (`SG69BbNlfRw` / `short-psalm91`)
* `short-0001-enron-70b-fraud.md` (`DLEWL6dm5lo` / legacy)

### 2026-11-03 Autonomous Hardening Summary (Tuesday 3 November, Nigeria time):
* **Metadata Perfection, Selar Integration & Live Channel Retrofit (`PR #230` + Autopilot Lock):** Wired both live Selar links (`https://selar.com/i000qy7g39` & `https://selar.com/showlove/thesecretplace`) across Line 2 watch-page fold, sanctuary resource blocks, pastoral owner comments, faith Shorts bridges, and Spanish/Portuguese localizations; upgraded all 22 queued prayer titles (`55–62` chars), `seo_hook` snippets, quote-aware `<= 500`-char tags, verified `.srt` closed captions, `BT.709` + `48 kHz` AAC + sRGB ICC profiles, and idempotent `metadata_revision: "selar-seo-v1"` live-channel sync inside `monitor.yml`.
* **Quota-Aware Pacing & Autonomous Shorts Runway:** Added `SHORTS_MIN_GAP_HOURS` (`3.0h`) pacing guard on automatic Short releases, quota-cooldown recognition across `produce.yml`, `scheduler_supervisor.py`, and `automation_monitor.py` (eliminating supervisor retry storms and false stall alerts after daily uploads), non-Psalm/verse-aware `short_key_for_doc()` (`^short-[a-z0-9]+$`), and automatic companion Short replenishment in `author_missing_shorts()`.
* **Brain-Authored Shorts Engine Completed End-to-End:** `pipeline/short_release.py` now generates `assets/deepdive/words-{key}.json` via local CPU `faster-whisper` (with deterministic proportional fallback), dynamically synthesizes `ShortEdition` metadata for any future brain-authored Short spec, pauses cleanly on daily quota exhaustion, and uses `short-prayer-cover-poster.jpg` for all prayer Shorts; `tools/shorts.py` renders all prayer Shorts with full DOCOGA REELS v2 kinetic typography, sequential word-aligned captions, punctuation-tolerant anchor matching, and clean procedural-plate source manifests.
* **TTS Burst Resilience & Quota Gating:** `pipeline/gemini_tts.py` distinguishes 3-RPM burst `429`s from daily free-tier exhaustion across both `interactions.create` and `models.generate_content`, checks single-chunk audio against truncation, and caches chunks with `.sha256` verification (`save-always: true` in `produce.yml`); `pipeline/run.py` enforces `quota_blocked_until()` before starting subsequent queue jobs and skips manual release-ticket issues on `privacy: public` uploads.
* **Hermetic Crisis/Comment Guards & Watchdog Self-Healing:** `scripts/reply_comments.py` and `tests/test_comments_end_to_end.py` never escalate simulated/dry-run/test comments to GitHub issues; `monitor.yml` granted `contents: write`; `gemini_brain.yml` aligned on `concurrency: group: content-state`; `pipeline_watchdog.py` sweeps synthetic `c4`/`c_sim_6` issues and superseded public release tickets automatically in CI.

### Factcheck Worksheets in `content/factcheck/`:
* 19 worksheets generated for queue scripts `0015`–`0033` via `scripts/factcheck.py`
* All worksheets are empty checkboxes awaiting human review (standing rule: only a human may set `human_rewrite: true`)

### Automation Status & Investigation Log (October 30, 2026):

**Friday 30 October 2026 — Real workflow run on `main` (NOT dry run):**

* **06:14 UTC slot (7:14 AM WAT):** Passed — no video published.
* **14:14 UTC slot (3:14 PM WAT):** Passed — no video published.
* **19:14 UTC slot (8:14 PM WAT):** Upcoming — next scheduled release.
* **Manual workflow_dispatch run (#42/43) on `main`:** Rendered `0009` (Psalm 23) successfully but workflow reported failure due to `short_release --next` crash.

**Real Run #42/43 Details:**
* ✅ **Gemini TTS (Charon voice)** — 182.9s narration synthesized successfully
* ✅ **Pixabay API key** — working, downloaded assets (3840x2160, 1920x1080)
* ✅ **Video rendered** — `psalm-23-the-lord-is-my-shepherd.mp4` (240 MB)
* ✅ **Metadata pack** — 6 chapters, 93-char title
* ❌ **short_release --next crashed** — `unknown script 'short-psalm23'` — a shorts-queue manifest referenced a short key not in EDITIONS
* ❓ **YouTube upload** — unconfirmed; workflow failed at short_release before reaching upload confirmation

**Fixes Applied:**
* **PR #104 merged to main** — exit-code capture fix (pipeline.run failures no longer masked by short_release) + broadened asset queries for `0009`.
* **PR #105 merged to main** — `short_release --next` now skips manifests with unknown short keys instead of crashing. If no valid short manifest exists, exits 0 and lets `pipeline.run --next` proceed.
* **`PIXABAY_API_KEY` added** to GitHub repository secrets — stock asset source now available.
* **`PEXELS_API_KEY` still missing** — Pexels API key issuance is paused (pexels.com/api/ shows "New API key issuance is currently paused"). Recommended to add when available.
* **Asset queries broadened** in `content/queue/0009-psalm-23-the-lord-is-my-shepherd.md` to terms more likely to return Wikimedia Commons / US government public domain results.
* **`originality` checklist block added** to `0009` frontmatter (required by originality gate).

**Repository Secrets (as of Oct 30, 2026):**
| Secret | Last Updated | Status |
|--------|-------------|--------|
| `GEMINI_API_KEY` | 4 days ago | ✓ Present |
| `PIXABAY_API_KEY` | 10 minutes ago | ✓ Present |
| `YOUTUBE_CLIENT_ID` | last week | ✓ Present |
| `YOUTUBE_CLIENT_SECRET` | last week | ✓ Present |
| `YOUTUBE_REFRESH_TOKEN` | last week | ✓ Present |
| `PEXELS_API_KEY` | — | ✗ Missing (issuance paused at Pexels) |

**Next Approved Job:**
* `0009-psalm-23-the-lord-is-my-shepherd.md` — `status: approved`, `privacy: public`, `format: longform`, `voice: Charon`. Will render via TTS + assets + assemble path on the next successful produce.yml run.

---

## 4. Active Roadmap (What to Do Next)

1. **List Product #1 on Selar (432 Hz Offline Bedtime Audio Sanctuary) — READY FOR LISTING (October 30, 2026):**
   * Audio files generated and packaged (all $0.00 procedural DSP):
     * `content/products/audio/432hz-bedtime-peace-1hour.mp3` (144 MB, 320kbps, 60 min) — under Selar's 750 MB per-file limit ✓
     * `content/products/audio/432hz-night-watch-3hour.mp3` (432 MB, 320kbps, 180 min) — under Selar's 750 MB per-file limit ✓
     * `content/products/audio/companion-guide-bedtime-scripture.pdf` (5 KB printable)
   * Upload individual MP3 files to Selar one at a time (each under 750 MB limit)
   * Manifest: `content/products/prod-001-offline-audio-sanctuary.json` (updated with real file specs)
   * Cover: `content/products/cover_offline_audio_pack.png` (1080x1080, DOCOGA REELS v2)
   * **Next step:** Upload MP3 files individually to Selar.co — see copy-paste instructions below in §5.
   * **⚠️ Selar Constraint:** Max file size per downloadable file is 750 MB. All MP3s are individually under this limit. ZIP was 497 MB but could not be pushed to GitHub (100 MB file limit).
2. **Expand the Nightly Prayer Queue to 30 Continuous Nights — COMPLETE (October 30, 2026):**
   * All 24 queue scripts (IDs `0009`–`0033`) authored, factcheck worksheets generated, and all 217 tests passing.
   * Guarantees a full 30-day automated release runway at `19:14 UTC` / `06:14 UTC` / `14:14 UTC`.
3. **Closed-Loop Growth Engine — COMPLETE (November 4, 2026):**
   * The brain no longer authors blind. `pipeline/performance_feedback.py` scores every published long-form video on reach (view velocity) + satisfaction (engagement), aggregates by theme, and writes the derived-only `content/research/performance_feedback.json`. `GeminiBrain.select_next_scripture()` now favours the themes that are actually winning (confidence-gated; falls back to roadmap order on too little data).
   * `.github/workflows/growth-autopilot.yml` runs daily at 3:14am Nigeria time: metrics snapshot → feedback → series-playlist autoplay sync (session watch-time) → live-count milestone celebration. Every engine fail-soft; only the derived feedback is committed.
   * SEO tag enrichment (`seo_suggest` high-intent taxonomy) wired into `build_tags`; `continuous_research` next-job is now dynamic, not the stale hardcoded Psalm 23.
   * Full research + honest API limits: `docs/GROWTH_FEEDBACK_LOOP_2026-11-04.md`.
4. **Assemble 1-Hour & 3-Hour Dark Screen Sleep Compilations — DEFERRED (policy + memory):**
   * The current compilation is a static plate + ambient tone bed with **no narration** — the "minimal narrative" pattern YouTube's inauthentic-content policy flags, and `synthesize_sleep_bed` would OOM at multi-hour lengths. **Not auto-published.** Safe path forward: chunked/streaming audio synthesis + a real narration library first. See `docs/GROWTH_FEEDBACK_LOOP_2026-11-04.md` §5.
5. **Monitor YouTube Analytics Telemetry:**
   * Track subscriber velocity and watch hours via the daily growth-autopilot snapshot + weekly `metrics.yml`. Per-video thumbnail CTR/impressions are **not** available via targeted Analytics queries (bulk Reporting API only); the loop uses public view velocity + engagement as the proxy and never fabricates CTR. Optional Analytics enrichment (retention/APV) needs a one-time `--purpose analytics` OAuth token; the loop works without it.

---

## 5. Selar Listing Instructions — Product #1 (Copy-Paste Ready)

**Product:** 432 Hz Offline Bedtime Sleep Sanctuary Audio Pack  
**ZIP file:** `content/432hz-offline-bedtime-sanctuary-pack.zip` (~497 MB — under Selar's 750 MB limit)  
**Cover image:** `content/products/cover_offline_audio_pack.png` (1080x1080)  
**Manifest:** `content/products/prod-001-offline-audio-sanctuary.json`

### Step-by-Step on Selar.co:

1. **Log in** to your Selar.co dashboard (the same account used for Product #2).

2. **Tap "Add Product" → "Digital Product"** (top-left card, same flow as Product #2).

3. **Fill the form with these exact values:**

   | Field | Value |
   |-------|-------|
   | Product Name | `432 Hz Offline Bedtime Sleep Sanctuary Audio Pack` |
   | Sale Price | `$0.00` (Pay-What-You-Want) |
   | Suggested Price | `$5.00 USD` |
   | Category | `Digital Audio Download` |
   | Product Type | `Digital Product` (top-left card) |

4. **Description (copy-paste):**

   ```
   Rest tonight without Wi-Fi, battery drain, screen glare, or mid-roll advertisements.
   This official offline audio pack features all canonical night prayers from The Secret Place
   (Psalms 91, 23, 121, 27, 46, and 34) mastered at 432 Hz Solfeggio frequency with
   1.5 Hz Delta brainwave entrainment for uninterrupted, restorative sleep.

   Included Files:
   • High-Definition 320kbps MP3s + Studio Master WAVs
   • 1-Hour Continuous Bedtime Peace Session
   • 3-Hour Continuous Night Watch Meditation
   • Complete Bedtime Scripture Printable Companion Guide

   Scripture References & Sources:
   - The Holy Bible, Psalms 91, 23, 121, 27, 46, 34 (King James Version / Public Domain)
   - Produced by The Secret Place | Daily Prayer & Scripture.
   ```

5. **Upload the ZIP file:** `432hz-offline-bedtime-sanctuary-pack.zip` (2.97 GB)

6. **Upload the cover image:** `cover_offline_audio_pack.png` (1080x1080, already rendered in DOCOGA REELS v2 sapphire glassmorphism)

7. **Set payout to:** First Bank of Nigeria USD Domiciliary Account (SWIFT: `FBNINGLA`)

8. **Tap "Create Product"** — the product goes live immediately.

9. **After listing:** Update `store_url` in `prod-001-offline-audio-sanctuary.json` with the live Selar URL, and add the link to `docs/index.html` dashboard header alongside Product #2.

---

## 6. Permanent System Invariants ($0.00 Hard Cost Lock)

1. **$0.00 / Month Hard Cost Lock:** Under no circumstances may any pipeline component require or transition to a paid subscription, billable cloud tier, or credit card charge. If external rate limits or free quotas are reached, jobs fail closed (pause and wait for next reset).
2. **Permanent Voice Standard:** Google Gemini API TTS (`model: gemini-3.8-flash-tts`, `voice: Charon`) locked at free tier.
3. **Visual Theme Standard:** Signature DOCOGA REELS v2 sapphire glassmorphic visual system with directional drop shadows, Inter typography, radiant gold active-word illumination, and full-bleed 16:9 widescreen long-form and 9:16 vertical Shorts plates.
4. **Persona & Attributions:** Strictly *The Secret Place* editorial team. Zero mentions of personal creator names in scripts, descriptions, metadata, or audio.
5. **Website Function:** The website (`docs/index.html` / GitHub Pages) is exclusively an **analytics display and asset download dashboard**. There is NO manual review gate on the website; releases are published directly to YouTube.


### 31 October 2026 — OAuth and publication recovery

The user reauthorized YouTube using their own OAuth client and updated the three GitHub Actions YouTube credentials. Manual production run #47 uploaded Psalm 23 as public video `JZv67RNPCEI` and posted its pastoral comment, confirming the upload credentials worked. The overall run failed because the Shorts renderer has no `short-psalm23` script; its publication-record commit step was skipped, so the uploaded long-form job remained in the queue on main. This branch reconciles that receipt and adjusts the workflow to commit content changes even when the render step fails, and skips queued Shorts unsupported by the renderer. These changes require merging before they protect production. The video duration reported by the workflow was 190 seconds, below the requested 5–8+ minute long-form target. Do not rerun until the record is reconciled.


### Visual-style correction — pending deployment

The user rejected the montage/subtitle style used in public Psalm 23 video `JZv67RNPCEI` and requested its permanent deletion. YouTube credentials are not available in this workspace; deletion must be performed in YouTube Studio by the channel owner. The approved visual reference is `tools/shorts.py` `short-psalm91`: sapphire glassmorphism, Inter, gold active-word illumination, full-bleed plates, sentence-level synchronized kinetic text. Voice remains Gemini Charon; long-form must be 16:9 and at least 5 minutes. The existing generic queue renderer does not meet this standard; this branch fails closed for all `pipeline.run` jobs, including dry runs, instead of uploading the rejected style. This is a temporary production pause, not a completed long-form adaptation. The existing Psalm 91 master is only about 40 seconds and cannot satisfy the full-length requirement. The owner should disable the Produce video workflow until the fix is deployed; attempting to disable it via GitHub API returned 403. The branch needs merging to affect production.

### Approved widescreen style — 31 October 2026

The owner watched the GitHub Pages preview and explicitly confirmed: “Exactly that is it lock it in.” The permanent visual reference is `docs/media/approved-style-preview.mp4` (SHA-256 `69c55e855ed3a9a8ec1ffa79663489d7370eaaf636158c1ae853fe2c11d9f156`), based on `tools/shorts.py` `short-psalm91`. Requirements and limitations are documented in `docs/APPROVED_VISUAL_STYLE.md`, and a regression test protects the preview from silent replacement. PR #109's legacy-renderer production block and PR #110's preview are already on main; prior notes saying those fixes still need merging are historical. The nine-second preview is not a completed long-form renderer. Long-form production stays paused until the approved style, measured speech sync, and at least five minutes of real Gemini Charon narration are implemented and verified. Whether the owner deleted YouTube video `JZv67RNPCEI` has not been confirmed.

### Approved renderer work — current branch (not live)

Rebuilt the previously uncommitted widescreen work on this active branch: `pipeline/prayer_visuals.py` renders full-bleed scenes with the approved Shorts typography, glass HUD, color grade and camera motion; `pipeline/prayer_alignment.py` aligns narration with a preinstalled offline faster-whisper model, rejecting mismatches and uncertain timing; `pipeline/prayer_draft.py` builds an offline draft from existing Charon narration and scene assets. The encoder and scene timing have local tests, including a five-minute synthetic silent render; that does not verify real Charon speech or synchronization. Portrait style defaults are regression-tested. The user-approved reference remains unchanged. The queue's live style lock remains active, and none of this new work is wired to the upload pipeline or deployed. The necessary offline model and real full-length Gemini narration are not available in this workspace; GitHub secrets cannot be retrieved here. The next queued Psalm 121 script is roughly 408 words and may not meet the five-minute minimum. No new video has been published. An initial full suite passed 227 tests and 1,089 subtests after fixing two stale scheduler expectations; an additional five-minute synthetic render test subsequently passed.

### Production integration work — pending real alignment verification

This branch now includes `pipeline/prayer_pipeline.py`, a new end-to-end approved-style production path with Gemini Charon narration, a local measured-word alignment prerequisite, full-bleed scene rendering, duration enforcement, upload and publication receipt handling. This new path is not yet connected to `pipeline.run.process` on main; the legacy-style lock remains active. The first queued Psalm 121 script has 408 words, below the new full-length preflight threshold of 650, and needs substantive expansion without falsely claiming human revision. The Gemini TTS implementation on this branch no longer falls back to alternate models and handles quota errors from the interactions API. Tests use mocks for upload/Gemini and synthetic sound for encoder tests; they are not proof of a real full-length Charon video.

A new secret-free GitHub Actions diagnostic (`prayer-alignment-check.yml`) runs the local speech model on the existing Psalm 91 recording, comparing its timestamps against the stored reference including segment 3. The model download occurs in temporary GitHub runner storage. At the time of writing the diagnostic has not yet run; its result and actual timing accuracy remain unverified. This diagnostic does not upload or unlock publishing. GitHub Actions credentials and a real Gemini request are unavailable in the sandbox, and an unverified assumption that an API key cannot incur billing is not a $0.00 guarantee.

### 31 October 2026 — Wiring approved style into automation (branch, not yet deployed)

The approved prayer renderer is now connected to `pipeline.run.process` on this branch, with no legacy-renderer fallback. The production workflow provisions a local CPU alignment model and checks the existing Psalm 91 recording before proceeding. The next script, Psalm 121 (`0010`), was expanded to 884 words; its actual Charon duration is not yet measured, and its fact-check worksheet was regenerated but not independently checked. The new text is recorded truthfully as `human_rewrite: false`. Because the owner requires autonomous publication without a manual approval gate, the originality checker no longer treats that flag as mandatory; its substantive/source checks remain. These flags are assertions, not proof of factual accuracy or originality.

The branch's separate GitHub alignment diagnostic downloaded the local model and aligned the real existing Psalm 91 recording. A permissive confidence diagnostic measured a worst difference of approximately 0.400 seconds across the reference and 0.200 seconds in segment 3. A later diagnostic using the actual confidence floor reported the same numbers but failed at the floating-point 0.400-second boundary; an epsilon correction has been made and needs a new run. This comparison is not proof of exact word-level sync for other voices or scripts. Local tests passed 231 tests and 1,110 subtests; upload/TTS tests use mocks. No live full-length render or upload has been verified. Gemini API keys are unavailable locally; the API's free tier is not an enforceable zero-dollar cap if the project has paid billing enabled, which has not been independently verified. Keep the branch unmerged until real synchronization and the zero-cost constraint can be assured. The actual production on main remains blocked and no new YouTube upload has occurred.

The real-recording alignment diagnostic subsequently passed at a 0.400-second maximum tolerance (worst discrepancy 0.400 seconds; segment 3 discrepancy 0.200 seconds). This demonstrates a bounded match to the existing reference, not exact word-to-word synchronization or accuracy on the new narration. The branch's GitHub CI also exposed that its test runner installed no pytest despite importing pytest-based tests; the workflow now explicitly installs and runs pytest. The branch is still not merged: an actual full-length Gemini render, verified free-only billing, and YouTube publication remain outstanding.

### Upload request — current blocker

The owner explicitly requested that the real approved-style video be uploaded. PR #112 remains a draft and is not on `main`; the new full-length Charon path has not been exercised end to end with real credentials and no new video has been uploaded. The branch's public-recording alignment diagnostic passed against the existing reference at a 0.4-second tolerance (segment 3: 0.2 seconds); this does not guarantee exact synchronization for the new narration. The CI unit-test job passed, but the network-dependent general pipeline dry-run failed, and the offline renderer job was still running at the last check. GitHub Actions secrets cannot be read using this integration (403). In particular, no evidence is available here that the Google project associated with `GEMINI_API_KEY` has billing disabled; a Gemini API key and a quota response do not enforce the owner's $0 hard limit if paid billing is active. No paid API call or automatic publication should be attempted on an unverified billing project. The owner can verify the project billing state in Google Cloud Console without sharing credentials.

On checking directly in the sandbox, no Gemini API key, Google application credentials, or Google project identifier was present; the installed GitHub integration also returned HTTP 403 for the repository secrets list. Google AI Studio has no supported connector in this session. Consequently the Gemini project's billing state cannot be independently verified from here. The public GitHub Actions unit-test job succeeded, but the real long-form video has not been uploaded and PR #112 remains a draft.

### In-depth cost and release research — 31 October 2026

- Google's Gemini pricing page lists Standard `gemini-3.8-flash-tts` input and output as free on the free tier, with separately priced paid-tier usage. A free-capable model is not proof that the deployed API key's project is free. Official pricing: https://ai.google.dev/gemini-api/docs/pricing .
- Google says API keys inherit their parent project's billing status; the Projects page displays billing tier, and disabling billing on a project returns it to the free tier. A paid-project balance reaching zero does not automatically downgrade to free. Official billing documentation: https://ai.google.dev/gemini-api/docs/billing . Actual Gemini project ID, billing status, and real paid/free tier remain UNKNOWN here; no Google project auth or API key is available in the sandbox.
- A 429 can reflect minute, daily, token or paid-tier spend limits; it is not proof of free billing. Free daily RPD resets at midnight Pacific local time, not permanently 08:00 UTC: https://ai.google.dev/gemini-api/docs/rate-limits . `pipeline/quota_handler.py` currently hard-codes 08:00 UTC and inaccurately states 1,500 RPD / 15 RPM as universal. This is a research finding; it has not yet been fixed. On 1 November 2026 Pacific midnight is 08:00 in Lagos; from 2 November it is 09:00 in Lagos because daylight saving changes.
- Google Cloud's billing status API `projects.getBillingInfo` returns `billingEnabled` and requires an authenticated principal with `resourcemanager.projects.get`; matching a secret API key to its owning project can require `apikeys.keys.lookup`. Neither the secret key nor access to a Google Cloud identity is available here. References: https://docs.cloud.google.com/billing/docs/access-control ; https://docs.cloud.google.com/api-keys/docs/reference/rest/v2/keys/lookupKey . A successful `models.list` does not prove billing tier or inference eligibility: https://ai.google.dev/gemini-api/docs/troubleshooting .
- Alert-only budgets do not enforce a hard stop; spend caps may exist for supported services but availability, zero-threshold behavior, reporting delay and scope need separate verification. Unlinking billing may stop other project services and doesn't erase already accrued costs: https://docs.cloud.google.com/billing/docs/how-to/budgets ; https://docs.cloud.google.com/billing/docs/how-to/modify-project . Do not change billing without owner approval.
- The repository is public, so standard GitHub-hosted runners are free for compute, but artifact/cache storage policies have separate allowances. GitHub API returned 40 unexpired artifacts totalling 8,022,777,290 bytes at investigation time (including repeated ~599 MB GitHub Pages artifacts). Account-wide plan, accrued storage and actual charges were not accessible; this is a risk to investigate, not evidence of a charge. Example: scheduled blocked production still generated `render-41229855644` (~534 MB), because its artifact step captures `output/` including cached assets. Avoid purging artifacts without authorization. Reference: https://docs.github.com/en/billing/concepts/product-billing/github-actions .
- The latest scheduled production run started Saturday 31 October at 7:31pm Lagos time and failed; GitHub annotations show the legacy-style block stopped long-form `0010`, and the unsupported Short manifests were skipped. No video upload is shown in that run: https://github.com/johnAzani/YouTube-automation/actions/runs/41229855644 . Main still blocks long-form; draft PR #112 is not merged. The approved video preview is `docs/media/approved-style-preview.mp4`; actual full-length Charon output and upload are unverified.
- The research also found outdated quota assertions in the repo: current Google documentation describes `videos.insert` as a separate upload quota bucket, not the historic 1,600-unit statement. https://developers.google.com/youtube/v3/docs/videos/insert . This does not establish this project's actual quota.

### Read-only GitHub secret diagnostic

The user confirmed the Gemini key is stored in GitHub Secrets and authorized finding information through it. Added `.github/workflows/gemini-key-diagnostic.yml`, which runs only on the session branch, passes the secret to a no-checkout step, and requests only metadata for the required TTS model. It prints neither the key nor the response and attempts no speech generation or upload. Its result can confirm secret presence and model-metadata accessibility only; neither result establishes the key's project or billing tier. Actual result is pending the workflow run.

Diagnostic result: GitHub Actions run https://github.com/johnAzani/YouTube-automation/actions/runs/41246316711 reported `GEMINI_API_KEY` present and requested `gemini-3.8-flash-tts` model metadata accessible. The response body and key were not exposed. No speech generation or upload occurred. This does not establish free-tier eligibility, identify the parent project, or verify billing. The separate Google Cloud authenticated permissions described above are still required for the proposed billing preflight. Result recorded from sanitized GitHub check annotations; the raw Actions log endpoint was inaccessible from this sandbox.

### User-confirmed free tier and quota reset correction

The user confirmed that the Gemini project is on the free tier. Treat this as the user's current account information, not as an independently verified billing API result or a permanent guard against later billing changes. The GitHub secret/model metadata diagnostic above remains valid; no inference or upload has been performed.

Updated `calculate_next_quota_reset_utc` to calculate midnight in `America/Los_Angeles` with daylight-saving transitions rather than assuming 08:00 UTC. Added summer, autumn/spring DST transition, exact-midnight and naive-time tests. Removed inaccurate claims that quota handling alone enforces the $0 lock and that one fixed Gemini quota applies universally. Targeted quota tests: 13 passed. Full local suite: 236 passed, 1,110 subtests. Remaining: autonomous billing/project check, actual live Charon synthesis and alignment verification, compliant final render and upload. This correction is on the session branch, not main; no live production was triggered.

### Branch cleanup and PR #112 readiness review — 31 October 2026

All 61 stale remote `arena/*` branches were deleted from `origin`; `main` is
untouched at `1813451`. PR #112's branch was kept because it is the only
unmerged work, and its tip is additionally preserved as the tag
`archive-pr112-approved-prayer-visual-pipeline` (`e7c6c42`).

PR #112 was reviewed offline and **not merged**. Verified: 236 tests pass on its
tip; the widescreen renderer runs for real (1280×720 H.264/AAC, sapphire grade,
frosted HUD, Inter display type, gold active-word illumination) at 202 ms/frame
on a 2-core sandbox (4.85× realtime, i.e. ~12–15 min for a 6-minute master on a
4-core runner); `full_narration` matches the concatenated scene narrations for
all 28 queue scripts. Unverified: live Gemini `gemini-3.8-flash-tts`/Charon
synthesis under the new no-fallback policy, the `faster-whisper` alignment model
and tolerance check, licensed asset fetch, and a full-length render plus upload.
A dry run could not be started from this session — `gh workflow run` returns
`HTTP 403` because the GitHub integration has no `actions:write`.

**Blocking finding:** the queue is not a 30-night long-form runway.
`python scripts/audit_runway.py` reports 22 of 28 scripts below the 650-word
(≈4.2 min) floor enforced by `pipeline/prayer_pipeline.py`; the short ones are
227–408 words (1.5–2.7 min). Of the 6 that clear the floor, 0003–0007 are
`draft`, so **only 0010 is publishable: 1 job, 5.7 minutes**. Merging #112 today
would publish 0010 on the next cron and then fail closed on the length gate
three times a day. Full review, recommendations and the exact dry-run to run:
`docs/WIDESCREEN_PIPELINE_READINESS.md`.

### CI dependency fix + long-form upload runbook — 1 November 2026

The required `Unit tests + doctor` job was failing on every branch, including
`main`, before running a single assertion: seven modules under `tests/` import
`pytest` at module scope while the workflow installs only `requirements.txt` and
runs `python -m unittest discover -s tests`. Adding `pytest>=8.0` to
`requirements.txt` fixes collection without touching the workflow files (PR #112
edits the same step, so this avoids a conflict). `tests/test_auto_scheduler.py`
also stopped hardcoding job `0009`/"Psalm 23" — it failed forever once 0009 was
published — and now derives both expectations from `content/queue/`.

`docs/LONG_FORM_UPLOAD_RUNBOOK.md` documents the only currently working path to
publish a long-form video in the approved style: dispatch `Produce video` on the
PR #112 branch (dry run first, then the real upload), then merge #112 so the
published receipt and renderer land on `main` together. Nothing in style can be
uploaded from `main` until #112 merges, because `main`'s renderer still fails
closed by design.

Also note for whoever merges #112: after `0010` publishes, the next approved job
is `0011` at 408 words, which the renderer refuses, so the cron goes red one run
later. Approving `0003`–`0007` (already 1,055–3,175 words, sitting at
`status: draft`) restores roughly six full-length uploads.

### Verified end-to-end dry render, and the alignment fixes it exposed — 1 November 2026

The owner could not select the PR #112 branch in the Actions "Use workflow from"
dropdown (runs #43–#51 all executed on `main` and died on the legacy-renderer
guard), so a push-triggered workflow (`.github/workflows/preview-render.yml`) was
added. It checks out #112's ref itself and renders with `DRY_RUN=1` — it can
never publish.

**Run https://github.com/johnAzani/YouTube-automation/actions/runs/41280103404 is
the first successful end-to-end long-form run.** It produced real Gemini
`gemini-3.8-flash-tts` Charon narration for job 0010 (5:04 of audio), passed the
local `faster-whisper` alignment and the Psalm 91 tolerance check (max difference
0.400 s, segment 3 0.200 s), and rendered the full master plus metadata. Nothing
was uploaded.

Reaching that point required three fixes to #112's own code, each found by a real
run rather than by reading it:

1. `pipeline/prayer_alignment.py` demanded exactly one recogniser token per
   script word. Run 1 aborted on a zero-length word (`start == end` at word 183),
   run 2 on `word count differs: 883 vs 884; mismatches=[(['for', 'evermore'],
   ['forevermore'])]`, run 3 on a correctly transcribed word with probability
   0.117. The module now tolerates zero-length words, maps script words onto the
   recognised tokens, and only applies the confidence floor where the text did
   not match. It still fails closed if the narration says something else
   (`Peace.` narrated as `Rest.`), on non-monotonic, negative or non-finite
   timings, and on unknown models/audio.
2. `pipeline/prayer_visuals.py` rejected zero-length spans (`end <= start`) even
   though the typography only compares timestamps.
3. `tests/test_auto_scheduler.py` hardcoded published jobs; #112's own rewrite
   replaced it during the merge.

`tests/test_prayer_alignment.py` pins every case above (159 tests pass). The
renderer from #112 is now merged onto this branch together with these fixes and
`scripts/audit_runway.py`, so merging this branch puts a working approved-style
renderer on `main` — after which `produce.yml` can be dispatched from `main`
itself, which is the only branch the mobile app offers.

Still true after this: the queue's renderable runway is one job (0010).

### Job 0010 published — first long-form upload in the approved renderer, 1 November 2026

`Produce video` #52 (run 41287229366, `main` @ `c75a8ec`, manually dispatched,
22m48s, exit 0) published **Psalm 121 → https://www.youtube.com/watch?v=6M6oV8MxD9s**:

- public, 05:22, category Education, chapters in the description, full transcript present;
- real Gemini `gemini-3.8-flash-tts` Charon narration + `faster-whisper` alignment
  (the run passed the Psalm 91 tolerance check, max 0.400 s);
- pastoral comment posted (`[pinned-comment] … 6M6oV8MxD9s`);
- `content/published/0010-…md` carries `youtube_video_id: 6M6oV8MxD9s`,
  `published_on: 2026-11-01`; the queue file was moved and committed; release ticket created;
- QC artifact `render-41287229366` (1.11 GB, retained 1 day).

**Style defect found in that run's log:** every scene used a Pixabay stock *clip*,
including `2160x3840` portrait ones, because `fetch_scene_assets` accepted the first
result from any provider regardless of aspect. A 9:16 clip centre-cropped into a
16:9 master keeps only a narrow band, so the published plate is not the full-bleed
frame the approved style calls for. Fixed: `ASPECT_TOLERANCE` (0.55) now refuses a
source that is too far from the render aspect and keeps searching; 3:2 and 21:9
sources still pass, 9:16 into 16:9 does not, 9:16 into 9:16 still does, and a scene
falls back to the best rejected candidate rather than aborting. Four tests in
`tests/test_asset_sourcing.py` pin it.

`produce.yml` now also extracts three frames from every master into
`output/style-frames/` and uploads them as `style-frames-<run-id>` (14 days), so the
look can be checked in seconds instead of downloading the full QC artifact.

Next approved job is `0011` at 408 words: the 650-word gate will fail closed on the
next cron, so no further upload happens until `0003`–`0007` (1,055–3,175 words,
`status: draft`) are approved or the short scripts are expanded.

### Thumbnail system rebuilt to measured CTR constraints — 1 November 2026

The owner asked for the thumbnail to be reworked in depth after approving the
video itself. Research is recorded in `docs/THUMBNAIL_RESEARCH.md` with sources;
the short version is that a thumbnail is read at 120–168 px on a phone, so it
survives on one focal subject, ≤5 very large words and ≥7:1 contrast — and the
previous generator had none of those guarantees.

Published Psalm 121 thumbnail, measured: five text elements (kicker, hero,
rule, subtitle, tag), no focal art, ~40% of the frame empty, hero at 82 px,
hard-coded strings reading "PSALM 91" and "16 VERSES" on a Psalm 121 video, and
no validation at all. Legible ink (bright type + art that survives downscale):
**5.6% of the frame**.

New `pipeline/thumbnail_studio.py` paints its own focal art (moon over still
water / starfield / dawn), sets the hero at a computed 96–260 px with ≤5 words
and ≤3 lines, measures text-vs-background contrast and adds a feathered local
scrim if it is under 7:1, keeps all content inside a 1280×720 safe box clear of
the bottom-right duration badge, applies filmic grade + grain + unsharp, and
returns a report (hero px, words, lines, contrast, safe-zone and badge checks,
file size). Three genuinely different concepts ship for Test & Compare, which
picks by watch-time share across up to three thumbnails.

Result for `THE LORD IS YOUR KEEPER`: hero 134 px, contrast 11.5:1, 121 KiB,
safe zones clear, legible ink **14.4%** (2.6× the old frame). Committed frames
and 168 px mobile previews: `docs/media/thumbnails/`.

Wiring: `prayer_pipeline.produce` now renders the studio pack into
`output/thumbnails/` with `report.json` and mobile previews; the workflow
`.github/workflows/set-thumbnail.yml` renders the pack for any published job and,
with `dry_run` unticked, applies it to a live video via `thumbnails.set` (50
units) — which is how the already-published `6M6oV8MxD9s` gets its new
thumbnail. 13 tests pin the constraints (`tests/test_thumbnail_studio.py`).

### CTR pack — the thumbnail that has to win a dark-mode feed — 1 November 2026

Measuring the studio frames against the surfaces they appear on found three
defects that legibility rules cannot see:

1. **The frame dissolved into the app.** YouTube's dark-mode page is #0F0F0F
   (luma 15); the studio vignette crushed its corners to about #02050E. A
   thumbnail darker than the page has no visible edge. The live frame measured
   border luma 24 with **13% of border pixels at or below the page colour**.
2. **The focal mass was too small.** The moon is this channel's only "face". The
   breakout data puts a tight chin-to-brow crop (≥40% of frame height) at 7.6%
   CTR against 4.3% for a small subject; the studio moon was 29% of height.
3. **The copy restated the title.** The published title already reads "…Will
   Neither Slumber Nor Sleep — Night Prayer for Sleep…", so "THE LORD IS YOUR
   KEEPER" and "HE NEVER SLEEPS" were redundant. That was an error in the earlier
   recommendation.

`pipeline/thumbnail_ctr.py` now paints three concepts with a print floor so no
pixel sits at the page grey (`EDGE_LUMA_MIN = 26`), a moon at 37–44% of frame
height with a bleeding halo, and a **lone house with two lit windows** as the
human anchor a face would otherwise provide. Copy is chosen to add what the title
cannot: an imperative ("PRAY THIS TONIGHT"), an inverted subject ("WHILE YOU
SLEEP"), or no words at all (28% of breakout thumbnails carry none).

Measured: border luma 24 → 33, dark-border share 13% → 0.4%, hero 130–135 px,
contrast 9.1–11.8:1, 90–112 KiB. Decision sheet:
`docs/media/thumbnails/ctr-decision.png`. 21 tests in `tests/test_thumbnail_ctr.py`
pin the dark-feed, focal-mass, word-budget and no-title-repetition rules; full
suite 198 passing. The workflow now offers `hook | quiet | poster` alongside the
studio variants.

### Supply side: script expansion + the 0011 root cause — 1 November 2026

The daily crons were publishing nothing, and it was not a plumbing fault. Every
approved job in the queue was 265–408 words against a hard 650-word gate, so
`produce` failed closed three times a day. 0010 shipped only because it was
written at 951 words.

`tools/expand_scripts.py` is the missing supply-side step. It expands approved
scripts to ~900 words **additively**: every original line must reappear verbatim
and in order, scene headings must keep their positions, and the run is refused
if the result is still under the gate, over 1200 words, carries a repeated
12-word sentence (padding), leaks a creator name, or quotes a psalm that
contradicts the title. The template provider cannot be used with `--write` —
padding is not writing, and the tool exists to stop padding reaching production.
`.github/workflows/expand-scripts.yml` runs it with Gemini, `dry_run` defaulting
to true.

**Root cause of job 0011** (Psalm 121 verses under a Psalm 27 title): the offline
fallback in `pipeline/gemini_brain.py` is a fixed Psalm 121 exposition, emitted
for *whatever* scripture was requested whenever the API was unavailable — and it
stamped `status: approved`, so it went straight into the publishing cron. Now the
fallback refuses anything that is not Psalm 121 (`BrainAuthoringError`, handled
as "refusing to author" rather than a crash) and template output is
`status: draft` with `scripture_verified: false`.

19 new tests in `tests/test_expand_scripts.py`, 2 in `tests/test_gemini_brain.py`;
full suite **219 passing**.

### Community posts: honest, and visible — 1 November 2026

Asked whether the Community Tab workflow works unattended, the answer was no on
two independent counts, and the check added here also caught a third.

1. **It had never run.** `Autonomous Community Tab Automation` was created on
   main on 30 October and by 21:34 UTC on Sunday 1 November — two and a half hours
   after its own Sun/Wed 19:14 window, with the 19:14 comment cron having fired at
   19:42 — it had **zero runs**. A workflow that never starts never fails, which
   is why this was invisible.
2. **It could not have posted anyway.** `pipeline/community_posts.py` never
   called an API; `publish_community_post` returned `status: "published"` after
   rendering a PNG. And `scripts/post_community.py` passed
   `dry_run=args.dry_run or True`, which is always `True`, so `--publish` was a
   no-op even before that.
3. **It cannot be fixed by wiring.** The YouTube Data API v3 has no endpoint for
   creating Community posts. Publishing happens only inside YouTube Studio, or via
   its native scheduler.

So the workflow is now honest: it writes `content/community/<id>-READY.md` with the
exact body, poll options and card path, uploads it as an artifact, and the run page
says *"YouTube has no API for Community posts — open Studio → Create → Post"*.
Status is `ready_for_manual_post`, never `published`. The card paths now match what
the manifest actually writes (`comm-00N-*.png`, not the never-created
`card_comm_00N.png`).

`scripts/automation_health.py` + `.github/workflows/automation-health.yml` (daily
20:14 UTC) audit every scheduled workflow against its own cron cadence and flag
`NEVER RAN` / `OVERDUE`. On its first run it reported:

```
comments.yml        daily     ok          2026-11-01 19:42 UTC
community.yml       every 7d  NEVER RAN   no run recorded
expand-scripts.yml  daily     NEVER RAN   no run recorded
```

18 new tests (15 health, 3 community honesty), written with `unittest` after the
pytest-style first draft was found to be collected by *nothing* in CI. Full suite
**237 passing**.

### Shorts are half automated — and the queue no longer pretends otherwise

Asked whether Shorts run unattended, the answer is no, and three separate things
were hiding it:

1. **A Short needs a hand-authored scene script.** `tools/shorts.py` holds a
   `SCRIPTS` dict with per-Short scene definitions (1668 lines: plates, camera
   moves, on-screen kickers, narration timing). There is no generator for those.
   The renderer knows three keys — `short-enron`, `short-johnstown`,
   `short-psalm91` — while `EDITIONS` defines seven. Every approved manifest in the
   queue pointed at a key with no script, so `select_next_queued_short()` returned
   `None`, the stage printed "nothing to do", and exited 0. Green run, no video.
2. **The brain hardcoded the key.** `generate_companion_short` wrote
   `short: short-psalm91` and `status: approved` for *every* long-form job — a
   second Psalm 91 Short queued against any new psalm, and the same
   mislabelled-scripture class of bug as job 0011.
3. **It spent quota on a guaranteed failure.** The Shorts path called
   `set_video_thumbnail` on every upload. YouTube rejects custom thumbnails on
   Shorts, so that was 50 units burned per Short for nothing.

Fixed: the brain derives the key from the psalm, writes `renderer_ready`, and only
marks `approved` when a scene script exists — otherwise `draft` with the reason.
`queue_report()` explains every manifest's verdict and the stage emits a
`Shorts stalled` warning naming the missing script. `set_video_thumbnail` is no
longer called on the Shorts path. The three approved-but-unrenderable manifests
(0009/0013/0014) were downgraded to `draft` with `approved_note` and
`renderer_ready: false`, so the queue stops claiming they will publish.

`auto_scheduler.audit_shorts_queue` now reports those rows as `blocked` and counts
only renderable ones as approved, so the runway can no longer be inflated by
unbuildable work; `audit_longform_queue` likewise requires the word floor. Running
`automation_health` now prints, daily:

```
queue: longform  ready=0  approved and above the word floor
queue: shorts    ready=0  5 manifest(s) waiting on a scene script in tools/shorts.py
```

16 new tests in `tests/test_short_release_queue.py` plus queue-health and scheduler
guards; full suite **253 passing**.

### The brain now authors Shorts — a Short is data, not code

The previous entry's first bullet was an excuse, not a fact: it said a Short needs a
hand-authored scene script and "there is no generator for those". The renderer was
always data-driven — `stock_queries`, `scenes`, `captions`, `kinetic_phrases`,
`beats` — so the only thing making a Short a code change was that the data lived
inside a Python literal. Data can be generated, so the brain generates it.

`pipeline/short_script.py` is the authoring contract. The brain returns JSON, and
`validate_spec` rejects it unless it is safe to render:

* 6–10 scenes, exactly one stock query per scene, camera move in the whitelist,
  focus fractions in 0–1, kicker ≤ 22 and sub ≤ 34 characters (9:16 safe area);
* captions non-overlapping, 90–165 narration words, 30–180 seconds;
* one kinetic phrase per caption with matching start/end seconds;
* every `beats[].a` anchor present verbatim in the narration;
* no creator names or "narrated by";
* **no cross-psalm quotation** — the spec may quote only its own psalm, checked
  against per-psalm fingerprints (23/27/34/46/91/121). This is the job-0011 bug
  class, refused by machine instead of by review.

A valid spec is written to `content/shorts-scripts/<key>.json`, which
`tools/shorts.py` merges into `SCRIPTS` at import and which `_renderer_script_keys()`
unions with the literal keys. From there the path is fully automatic: the release
stage TTS-synthesises the narration from the captions with the standing `Charon`
voice (`_ensure_narration`), renders, verifies, uploads. No human authoring step
exists anywhere in it.

Two entry points, both unattended:

1. `pipeline.short_release --next` — before printing "nothing to do" it asks the
   brain to author the specs the queue is blocked on, then re-selects.
2. `scripts/gemini_brain.py --author-shorts` — a step in `gemini_brain.yml` that
   backfills every `needs_renderer` manifest and commits `content/shorts-scripts/`.

Failure is loud and non-fabricating: if the model returns something invalid twice,
or the API key is absent, the manifest stays `draft` with `authoring failed: …` in
its notes and the queue keeps reporting itself stalled. A Short that renders with
mislabelled scripture is worse than an empty queue.

Current state of the five blocked manifests (0009/0010/0011/0013/0014) is `draft`,
`renderer_ready: false`, `authored_by_brain: false` — locally the API key is absent,
so authoring refuses. In Actions, where `GEMINI_API_KEY` is a secret, the next
brain or production run authors all five. 28 new tests; full suite **281 passing**.

---

## 7. The schedule, in Nigeria time

GitHub Actions cron is UTC and always will be. Nigeria is UTC+1 all year — no
daylight saving — so Nigerian time is the cron hour **plus one**, with the same
minutes. Every time below is Abuja/Lagos wall clock.

| When it runs (Nigeria) | What happens | cron (UTC) |
|---|---|---|
| **3:14am, daily** | **Growth autopilot**: snapshots public metrics, computes the closed-loop performance feedback the brain reads, syncs series playlists (session watch-time), celebrates the live subscriber milestone | `14 2 * * *` |
| **4:14am, daily** | **The brain**: lengthens short scripts, authors a new long-form if the queue lacks runway, authors Short specs for anything blocked — now steered by the performance feedback | `14 3 * * *` |
| **4:23am, Monday** | Keepalive self-heal | `23 3 * * 1` |
| **7:14am, daily** | Production slot 1 — a Short on every channel; the long-form of The Morning Altar and The Praise Garden | `14 6 * * *` |
| **8:14am, daily** | Comment replies | `14 7 * * *` |
| **11:14am, daily** | Production slot 2 — a Short on every channel; the long-form of The Provision Table and The Guided Path | `14 10 * * *` |
| **3:14pm, daily** | Production slot 3 — a Short on every channel; the long-form of The Midday Watch and The Family Altar | `14 14 * * *` |
| **4:14pm, daily** | Comment replies | `14 15 * * *` |
| **7:41pm, Friday** | Weekly metrics pull | `41 18 * * 5` |
| **8:14pm, daily** | Production slot 4 — a Short on every channel; the long-form of The Secret Place and The Healing Balm | `14 19 * * *` |
| **12:14am, daily** | Production slot 5 — a Short on every channel; the long-form of The Midnight Watch and The Covenant Shield | `14 23 * * *` |
| **8:14pm, daily** | Comment replies | `14 19 * * *` |
| **8:14pm, Sunday and Wednesday** | Community post is prepared (manual post — the API has no endpoint) | `14 19 * * 0,3` |
| **9:14pm, daily** | Health check, then the watchdog files or closes its stall issue | `14 20 * * *` |

**Since 14 November 2026 each channel publishes one long-form and five Shorts a
day** (it was three and three; the Shorts are what is watched). Every production
slot repairs the queue first, then publishes a Short on every channel, and each
channel's long-form goes out at its own slot. Shorts no longer need a long-form
behind them. The decision, the passage lists and the way back are in
`docs/SHORTS_FIRST_MIX_2026-11-14.md`.

The expansion pass no longer has a cron of its own: it runs inside the brain at
4:14am **and** at the top of every production run, so a missed or late cron is
repaired by the next release instead of becoming an empty evening.

So the next chance for everything to move is **tomorrow morning at 4:14am**, and
the first production run after that is **7:14am**.

Run anything early by hand from the Actions tab ("Run workflow"); nothing here
needs you to wait for a slot.

### The brain owns long-form too, and the pipeline reports itself

The owner's requirement: *"even when I don't ping you everything is working — the
brain is working like you 100 percent."* That was not true, and the reasons were
all of the same kind: stages that succeed while doing nothing.

**What the audit found (2 November):**

- `expand-scripts.yml` — the pass that lengthens short scripts — had **never run**.
  Its cron was registered, its YAML was valid, the Actions page was green, and it
  had zero executions.
- It would not have worked if it had run. `gemini_provider` imported
  `get_gemini_api_key` from `pipeline.config`, where that function does not exist.
  Every script would have died on `ImportError` and been reported "skipped".
- So 21 approved scripts sat in `content/queue/` at 227–397 words against a
  650-word floor. Production ran three times a day, found nothing publishable,
  printed a friendly notice and **exited 0**. Green all day, no video.
- The brain made it worse: runway counted "approved" scripts regardless of length,
  so it kept authoring *more* 250-word scripts, and its authoring prompt never
  asked for length at all.
- `replenish_pipeline` swallowed authoring failures and returned `None`, which is
  indistinguishable from "runway healthy" at every call site.

**What now exists — `pipeline/supply.py`**, one loop, in the right order:

1. lengthen every approved script under the floor (validated: additive, no padding,
   no creator names, no wrong-psalm text, never lowers the gate),
2. if fewer than `min_publishable` remain, author a new long-form — the prompt now
   requires 900 words, and the script is expanded in the same run if it lands short,
3. approve it only after it clears the floor, passes the scripture-label check, and
   has its factcheck worksheet,
4. report exactly what happened, or fail loudly naming the reason.

`ensure_supply` is called by `gemini_brain.py --ensure-supply`, by
`--auto-replenish` (one code path now), and at the **top of every production run**,
so a delayed or skipped brain cron is repaired by the next release slot. The
`expand-scripts.yml` cron is gone — expansion is part of the loop, not a separate
job with an ordering dependency.

**And it reports itself.** `scripts/pipeline_watchdog.py` keeps exactly one issue
open while the pipeline is unhealthy — empty long-form queue, nothing renderable in
Shorts, no upload in three days, a scheduled workflow that never ran — and closes
it on the first fully healthy check. It runs at the end of every production run and
in the nightly health check. An issue is an email; the owner no longer has to ask.

Current honest state, which the watchdog reproduces exactly:

```
BLOCKING: long-form queue — nothing in content/queue/ is approved and over the 650-word floor.
warning : shorts queue    — 5 manifests with no scene spec yet
warning : workflows      — expand-scripts.yml / automation-health.yml: never ran
```

The gate was **not** lowered to make this green. 23 new tests in
`tests/test_supply.py`; full suite **304 passing**.

### Correction: the key was never missing

The last two entries kept printing "GEMINI_API_KEY unavailable" from this sandbox and
let it read as a pipeline fault. It never was one. The key has been configured since
week one; it narrates every video, and `google-genai` is in `requirements.txt`, so
Actions has both the secret and the SDK. **Voiceover working is proof the key works.**

Why the brain still authored nothing for days, with a working key:

`replenish_pipeline` asked `audit_status().runway_days`, and runway counted every
`status: approved` script regardless of length. Twenty-one approved scripts at
227–397 words read as ~10 days of runway, so the brain answered "healthy, no
replenishment needed" and exited 0 — every single day. It was never blocked on
credentials; it was told by its own queue that there was nothing to do. (The
word-floor requirement in runway accounting landed yesterday; runway is now `0.0`.)

What changed so this cannot be misdiagnosed again:

- `GeminiBrain.api_status()` distinguishes **no key present** from **key present but
  the client failed to start**, and carries the underlying exception.
- Authoring errors quote that reason instead of the blanket "key unavailable".
- `scripts/gemini_brain.py --preflight` proves the runner can make one live model
  call, and runs as the first step of `gemini_brain.yml`. A key that is present but
  broken now fails loudly with the real error instead of degrading into "offline".
- `pipeline_watchdog.py` reports `brain api: <reason>` on every check, and treats an
  unreachable brain as fatal **in CI** (non-fatal on a laptop with no key).

Note on the watchdog: a missing key is only fatal where the workflow *declares* it
holds one (`EXPECT_BRAIN_API: "1"`, set in `automation-health.yml` and `produce.yml`,
both of which now forward the secret). The unit-test job and any runner without it
report the fact as context instead. Inferring fatality from `GITHUB_ACTIONS` alone
filed a false alarm from every CI job — caught by CI, fixed, and pinned by a test.

### Reply automation: it was never fetching anything

Asked to make comment replies work end to end. They didn't, and the reason was one
wrong parameter name.

`fetch_candidate_comments` built its channel-wide listing with
`allForChannelId`. That is not a parameter of `commentThreads.list` — the real one
is `allThreadsRelatedToChannelId` — so googleapiclient raised
`TypeError: Got an unexpected keyword argument allForChannelId` before any request
was made. The broad `except Exception` caught it, printed a line, and returned an
empty list. The CLI then printed "No unresponded candidate comments found" and
**exited 0**.

The workflow passes no `--video-id`, so all three daily pulses took that path:
three runs a day, zero comments listed, zero replies, green every time. Verified
locally against the real discovery client: the old name raises `TypeError`, the new
one builds a valid URI.

Also fixed:

- **A broken fetch is now an error.** `CommentFetchError` propagates to exit 1 with
  an `::error` annotation, so "the API rejected the call" can never again read like
  "nobody commented today".
- **403 no longer means quota.** A disabled comment section, a missing
  `youtube.force-ssl` scope, and an exhausted daily quota are three different
  things; only the last one pauses.
- **Crisis comments are held, not answered in public.** A hotline reply posted under
  someone's self-harm disclosure labels them in front of every other viewer. The
  comment is recorded (`CRISIS_ESCALATED`) with a draft reply and filed as a
  `viewer-crisis` issue for a personal answer. `--reply-to-crisis` opts back in.
- **The prompt's rules are now enforced on the model's output**: no links, handles,
  phone numbers, money solicitation, or creator names, whatever the model returns.
- **The ledger is committed** (`content/comments/replied.json`, seeded `{}`) with a
  rebase before push, and committed even when the batch fails partway — otherwise
  the next pulse answers the same person twice.

18 new end-to-end tests drive the real CLI against a fake Data API: fetch → classify
→ draft → insert → ledger, dedupe on the second run, skip already-answered threads,
refuse scams, hold crises, and exit non-zero when every insert fails. Full suite
**343 tests, 436 with pytest**.

### Standing rule: monitor every automation, not the one being asked about

Three rounds of "is X working?" produced the same answer three times. Each check
was triggered by the owner, and each one found a green workflow doing nothing. So
the rule is now standing, and it is enforced by code rather than by memory:

> **Every automation is checked continuously — every three hours — for whether it
> ran, whether it succeeded, and whether the run changed anything. Faults are
> corrected on sight, before the owner notices.**

`scripts/automation_monitor.py` is the check. For every scheduled workflow:

| verdict | meaning | severity |
|---|---|---|
| `OK` | ran inside its cron window, last run succeeded | — |
| `NEW` | added recently; its first window has not closed | warning |
| `UNTESTED FIX` | last run failed, but the workflow changed afterwards | warning |
| `FAILING` | last run failed with nothing changed since | **blocking** |
| `OVERDUE` | last run older than its own cadence + grace | **blocking** |
| `NEVER RAN` | registered, green on the Actions page, never executed | **blocking** |
| `FLAKY` | 2+ failures in the last 5 runs | warning |

It also records **outcomes**, because a successful run is not evidence of work: the
last upload, the size of the long-form queue, the number of authored Short specs,
and the number of replies actually recorded in `content/comments/replied.json`.

`.github/workflows/monitor.yml` runs it every three hours at :23 past, with the
Gemini key, `EXPECT_BRAIN_API=1`, and issue permission. `pipeline_watchdog.py`
consumes its findings, keeps one issue open while anything is wrong and closes it
on the first fully healthy check. The snapshot is committed to
`content/monitor/status.json` so a recurring fault is dated instead of rediscovered.

First run of the monitor, on real history:

```
monitor.yml            NEVER RAN      never         0
automation-health.yml  NEW            never         0   added today, first window open
metrics.yml            UNTESTED FIX   10-30 22:37   6   failed before its last edit
comments.yml           OK             11-01 22:49  11
community.yml          OK             11-01 22:50   1
gemini_brain.yml       OK             11-01 10:25   3
keepalive.yml          OK             10-26 09:08   1
produce.yml            OK             11-01 22:47  20
```

Two of those were real findings the old health check could not see. `metrics.yml`
had been failing weekly since 30 October with `invalid_scope: Bad Request` — the
stored refresh token could not be exchanged for the scopes the script requests.
That arrived as a bare stack trace, which reads as broken analytics code; it now
prints the scopes it wanted and the exact command to re-mint the token. (The upload
token was re-minted on 31 October, after that failure, so the next Friday run should
pass — the monitor keeps calling it an untested fix until it does.)

20 new tests pin the verdicts, including the two that matter most: an empty run
history must never report healthy, and a failure that predates the last edit is
"untested", not "fixed". Full suite **456 with pytest**.

---

## Knowing when a workflow was edited, and when it last ran

The owner's next question was blunt and correct: *"you should know the last time it
was edited and the last time it ran — this gives you a better understanding of what
is happening."* The first monitor reported edit and run times, and both were wrong
in ways that mattered.

**"Last edited" was lying.** This clone is a single squashed commit — `git rev-list
--count HEAD` returns 1 — so `git log -1 -- <path>` returned the tip commit for
*every* workflow. Everything looked edited minutes ago, which quietly downgraded
real failures from FAILING to "untested fix". The monitor now reads the edit date
from `gh api repos/<slug>/commits?path=.github/workflows/<file>&per_page=1` and
returns `None` rather than guessing when the local history is too shallow to date a
file. The real dates: `produce`/`gemini_brain`/`automation-health` 2 Nov 06:56 WAT,
`comments` 07:23 WAT, `community`/`metrics`/`keepalive` 05:58 WAT.

**Missed slots were invisible.** A workflow whose schedule simply did not fire has
no failed run to find, so run history alone says it is fine. `prev_occurrence()`
now expands the cron and a new blocking verdict, `MISSED SLOT`, fires when the most
recent slot is more than three hours old (`SLOT_GRACE`) and no run followed it. The
grace is measured *after* the slot — the first version compared against
`slot - grace` and raised a false alarm on a scheduler that was 31 minutes late.

That change found the thing the old audit could not: on the morning of 2 November
the brain's 04:14 WAT slot, keepalive's 04:23 slot and produce's 07:14 slot all
came and went with no run at all. Nothing uploaded, and every workflow was green.

## The supervisor, because a dropped schedule cannot report itself

The monitor can *say* a slot was dropped; it cannot make the work happen, and it
cannot run if it was the dropped workflow. `scripts/scheduler_supervisor.py` runs
every fifteen minutes, compares each workflow's most recent scheduled slot against
its last run, and dispatches whatever was missed with `workflow_dispatch`. Rails:
a slot is dispatched only once (the slot key is kept in
`content/monitor/dispatched.json`), at most three per pass, never for the
supervising workflows themselves, only between 90 minutes and six hours after the
slot. The 90-minute floor matters — at 45 minutes it would race a merely late
scheduler, and for `produce.yml` a duplicate run means a duplicate upload.

14 new tests cover the supervisor, and the monitor's stamps are now WAT throughout
(`all times WAT` in the table, no bare UTC anywhere), because the owner reads WAT.

Full suite: **481 with pytest**.

---

## The morning it all said green and published nothing — 2 November 2026

The owner's message was three words and a screenshot: *"I have not seen it on
YouTube"*, with the channel showing Psalm 121 from the day before and nothing
newer. Every workflow had a green tick. This is the full chain, because each link
looked healthy on its own.

**1. The scheduler dropped the slots.** Brain 04:14, keepalive 04:23 and produce
07:14 WAT produced no runs at all. `scheduler_supervisor.py` dispatched all three
at 08:59 WAT (see the section above). Keepalive succeeded. The other two did not —
which is how the next four faults surfaced.

**2. The two length gates disagreed.** Production refused scripts under
`MIN_LONGFORM_WORDS = 650`; the renderer separately refused narration under 300
seconds. Charon narrates ~165 words a minute (job 0010: 884 words → 5:22), so 650
words is **3.9 minutes** — the word gate admitted scripts that could never render,
and each attempt paid for a full TTS call before failing with *"Actual Charon
narration is shorter than five minutes"*. The floor is now **derived**:
`required_words(300) + 25 = 850`, with `CHARON_WORDS_PER_MINUTE` and
`MIN_NARRATION_SECONDS` shared by the gate, the renderer and the brain prompt so
they cannot drift apart again.

**3. The expansion instruction contradicted itself.** The prompt said "add 2-4
sentences per existing scene" *and* "aim for 900 words". For a 280-word script
with five scenes, maximum compliance is ~400 words. A rule-following model
returned output that was valid, additive, in the right psalm — and permanently
under the gate, so `validate` refused it and nothing was written. Night after
night. The prompt now states the shortfall in words (`need`, `per_scene`,
`min_words`, `max_words`) so the arithmetic is possible.

**4. Progress was thrown away every time.** Because a short-but-safe expansion was
discarded, each run restarted from the same 280-word file. `expand_job` now
converges: an attempt that violates *only* the floor is written back — it is
additive, unrepeated and un-leaked, so keeping it is honest progress — and the
next attempt starts from the longer body. Rule violations are still never written
(`validate(..., require_floor=False)` is the discriminator), and an overshoot asks
again with a smaller target instead of abandoning the script.

**5. "Nothing to publish" was not an error.** `pipeline/run.py` printed a friendly
notice and `return 0`, on the stated theory that a red cron would train everyone to
ignore the dashboard. That is exactly why three slots a day could pass with no
upload. It now exits **2** with `empty_reason()`, which names the worst script and
how many words it is short: *"21 approved script(s) are under the 850-word floor —
0029 needs 623 more words — and the expansion pass did not bring any of them over
it"*.

**6. Approval did not mean publishable.** `supply.set_status` is the single choke
point for approval, so the rule lives there: a long-form script under the floor
cannot be marked `approved` by any caller. The 21 stragglers predate the guard;
the monitor now reports them as a blocking outcome (`publishable runway 0 of 21`)
instead of a note.

**7. The queue state could be lost, and losing it is dangerous.** The supervisor's
ledger commit landed between production's checkout and its `git push`, so the
`published/` move was rejected and discarded. That is not cosmetic: the move is
what stops the next run uploading the same video again. Production and the
supervisor now share one `content-state` concurrency group, and the commit step
rebases and retries five times, failing loudly if it still cannot land.

**8. The monitor measured the wrong thing twice.** "Last upload" used file mtime,
which a fresh CI checkout stamps with the checkout time — it reported "0.1h ago"
on a channel that had published the day before. It now reads `published_on` from
the published frontmatter. And it never looked at uploads at all, so a successful
production run that published nothing read as `OK`; there are now two blocking
outcomes for that: `publishable runway` and `produce published nothing`.

19 new tests in `tests/test_supply_never_stalls.py` pin each link, including the
one that matters most: a provider that under-delivers on every single call still
reaches the floor and stops there. Full suite: **508 with pytest**.

**And a dispatched slot that fails is retried.** `MAX_ATTEMPTS_PER_SLOT = 2`. On 2
November the 07:14 produce slot was dispatched at 08:59 and the run then failed;
treating the slot as settled would have left the channel with no video until the
next day. The ledger records attempts, `_failed_dispatches` finds entries whose run
finished badly after the dispatch, and a successful dispatch is never repeated.
Live check at 09:10 WAT: brain and produce retried, keepalive skipped because
*"its dispatched run succeeded"*.

## The renderer refused the scripts the expansion wrote

The re-dispatched production run at 10:19 WAT got further than any run since
Friday: the repair step **succeeded** (the queue finally had something over the
floor), the script rendered, and then `prayer_visuals.sentence_stream` raised
*"Sentence is too long for the widescreen layout"* and the whole upload died.

That limit was fine while every script was 250 words of short sentences. The
moment a script was correctly expanded, the model wrote real prayer sentences —
*"Father, when the day has left us feeling small, remind us that the hills are not
higher than Your compassion…"* — which need eight or nine 30-character lines, and
the layout drew at most six. A long sentence was never an error; it is two cards.
The stream now wraps and paginates, splitting each sentence's word timings across
the cards it occupies, so narration and subtitles stay in lockstep. Two tests pin
it: a 40-word prayer sentence must paginate rather than raise, and every card must
fit six lines of thirty characters.

Same run, second lesson: `produce.yml` merged the Short and long-form exit codes
with `max`, so a Short that could not render reported the *release* as failed. The
long-form upload is the release now — it decides the exit code, and a Short fault
is a `::warning` naming the code.

**The expansion invalidated every worksheet it touched.** Worksheets are bound to
the script by sha256 and `tests/test_queue_integrity` refuses an approved job whose
worksheet does not match — correctly. The first five lengthened scripts therefore
turned 118 subtests red, which is the suite doing its job. `expand_job` now
regenerates the worksheet on every write (`refresh_worksheet`), so a lengthened
script and its worksheet always move together.

**The brain's Shorts named photos that do not exist.** The authored spec for
`short-psalm23` claims `image-search/short-psalm23-scene-01.jpg`; nothing creates
that file, so `tools/shorts.py` exited 1 with `missing image` while the manifest
said the Short was ready — the same shape of lie one layer down. A missing photo is
a missing asset, not a reason to publish nothing: `synthetic_plate()` draws the
channel's sapphire plate with the scene kicker, the source log records
`authored photo fallback`, and the render continues.

**Riding CI, because CI is the only trigger that always fires.** At 10:01 on 2
November the dry-run CI started within seconds of the push while the supervisor's
own `push` trigger, its 10:00 slot and its 10:15 slot all produced nothing. The
supervisor now also runs on `workflow_run` completion of *"Dry-run pipeline (CI
proof)"* and *"pages build and deployment"* — the two workflows that start on every
push and every pull request — so every CI run is another chance to notice a slot
that never fired.

**The monitor itself had never run.** On 2 November `monitor.yml`'s 06:23, 09:23 and
12:23 UTC slots produced *no runs at all* — the one job built to notice a stall was
stalled, which is the most embarrassing possible version of the same bug. The brain
did eventually run at 11:02, nearly eight hours after its 03:14 slot, so the
scheduler is queueing runs unpredictably rather than dropping them cleanly.
`monitor.yml` and `automation-health.yml` now also trigger on push to main and on
`workflow_run` completion of production/CI/supervisor, and the monitor shares the
`content-state` concurrency group because it commits into `content/` as well.

**A slow render and a wedged render looked identical.** Step 8 was one opaque
"Render and upload target edition" holding both the Short and the release: no log
line, no summary, no timeout of its own until the job's 120-minute cap. On 2
November a run that was simply working cost the owner half an hour of watching it.
The stages are now two steps — *Render the Short (9:16)* (30 min, `continue-on-error`)
and *Render and upload the long-form edition* (90 min, the release) — each writing
its own section of the run summary, so a stall fails at a named step and a working
render shows which stage it is in.

**The watchdog could not report a stale publish either.** `last_publish` looked for
`published_at` / `uploaded_at` / `date` / `publish_at`; the publisher writes
`published_on`. Every receipt therefore fell through to the file's mtime, and a CI
checkout stamps every file with the checkout time — so the watchdog read "last
publish 0d ago" on a channel that had not published since the previous day. It is
the third instance of the same defect (the monitor read mtime too) and the most
damaging, because this is the job that decides whether to file the issue. It now
dates from `published_on`, reports an undated receipt as *undated* rather than as
fresh, and says "recency unknown" instead of "no receipt exists".

**The 10:48 run published a video and then lost the record.** Its annotations say
the long-form stage exited 0 — *"long-form published, the Short stage exited 1"* —
so Psalm 46 went up on the channel. Then the commit step failed **five times in a
row**: it retried `git pull --rebase --autostash origin main`, hit the same content
conflict on every attempt, and gave up. The repo therefore still lists 0013 as
`approved` in `content/queue/`, and the only thing standing between that and a
duplicate upload is `upload.check_existing_channel_duplicate`, which queries the
channel's last 50 uploads by title.

Two fixes: the commit step no longer rebases. It re-points HEAD at the current
main, stages the `content/` working tree on top, and commits — nothing to conflict
on, so a retry can only be about main having moved, not about the same merge
failing forever. And the Short failure itself: `tools/shorts.py` still had one
`SystemExit` for a scene whose stock asset is a **video** while the scene names a
photo that does not exist. That path now falls back to the same sapphire plate, so
a missing image cannot take down a render again.

**The duplicate is now caught before the render, not after it.** With 0013 live but
still in the queue, the 3:14pm slot would have spent 25 minutes re-rendering a
finished video and only then had the upload shield say "already there".
`prayer_pipeline.already_published()` asks the channel first — two API units, before
any Gemini or alignment work — and if the title is live it records the receipt and
moves the job to `published/` with the real video id instead of rendering. It fails
soft: any error in the pre-check and the release proceeds as normal.

**Recording a duplicate must not cost the slot.** With the pre-check in place, the
3:14pm run would have found 0013 live, filed it, and exited — a day with no new
video and a green tick, which is the failure this whole afternoon was about. When
`--next` records an already-live job it now selects again and renders the next
eligible script, stopping at the first real publish. Two tests: it moves on after a
duplicate, and it stops after one real release rather than draining the queue.

---

## The brain stopped publishing blind — 4 November 2026 (Wednesday, Nigeria time)

The deep audit asked one question of every growth module: *which workflow actually calls
you?* Most of the answers were "none." Roughly twenty growth modules were built and
unit-tested and then left dormant — series playlists, milestones, the SEO taxonomy, the
sleep-compilation renderer, the podcast feed. And the one lever that mattered most was not
dormant, it was **absent**: there was no feedback loop. `select_next_scripture()` walked a
static roadmap in fixed order; `metrics.yml` collected views/likes/comments every week and
dropped them into an artifact nothing read. The channel could not double down on what
worked. It published blind.

**The loop is now closed.** `pipeline/performance_feedback.py` reads the public snapshot plus
the published receipts, takes the latest reading per video, and scores each long-form on
reach (views/day, gated to ≥3 days old) and satisfaction ((likes+comments)/views, gated to
≥25 views), blended 50/50 and normalised across the measured cohort. Shorts are a separate
lane — their discovery engine is different and they must not steer long-form. It aggregates
by theme and writes `content/research/performance_feedback.json`: **derived only** — theme
ranks, average scores, guidance. No raw counts, no video IDs. The raw snapshot stays an
Actions artifact, and `content/metrics.csv` is now gitignored (it was not before — raw API
metrics could have landed in this public repo).

**The brain reads it at the one choke point both authoring paths share.** Eligible roadmap
candidates are ranked in three bands: themes at/above the measured average go first, unmeasured
themes keep their roadmap place, below-average themes go last. Fewer than three measured
videos → a neutral report and the roadmap order is preserved; it never steers on noise. A
missing or corrupt artifact is caught and logged, never fatal. The confidence gate and the
fail-soft path are both tested.

**The dormant engines are wired.** `.github/workflows/growth-autopilot.yml` runs daily at
3:14am Nigeria time (02:14 UTC, before the brain): snapshot → feedback → series-playlist
autoplay sync → live-count milestone celebration. Playlist sync is idempotent (searches by
title before creating, skips videos already present), so after the first sync it costs almost
nothing and chains finished prayers into the next one — session watch-time, the lever that
moves the 4,000-hour goal. `celebrate_milestone.py` no longer guesses 1230; it reads the live
count from the snapshot and skips rather than fabricates. The commit step copies monitor.yml's
fetch + reset --mixed pattern (never pull --rebase, which conflicted five times on 2 Nov) and
stages only the derived feedback. Every engine is fail-soft; one failing never blocks the rest.

**Two smaller fixes.** `build_tags` now folds in the `seo_suggest` high-intent taxonomy — the
queries sleepless viewers actually type — and every candidate still passes `fit_youtube_tags`,
so the 500-char budget, 18-tag cap and 432 gate are untouched (verified: 18 tags, cost 470, no
432). And `continuous_research` no longer hardcodes the already-published Psalm 23 as the next
job; it reuses the brain's feedback-aware selection.

**What was deliberately not done, and why.** The multi-hour sleep compilation is a static
plate + ambient tone with no narration — the "minimal narrative" pattern the inauthentic-content
policy flags, and `synthesize_sleep_bed` would OOM at length (whole-duration float64 arrays).
It is not auto-published; the safe path is chunked synthesis + a real narration library first.
The podcast feed cannot auto-grow without hosted per-episode audio (narration MP3s are CI
artifacts, never hosted). Community posts, Test & Compare, end-screen/card elements, the Shorts
related-video link and the podcast flag are all Studio-only — no public API — so the automation
stages what it can and never claims to have posted what it cannot. Per-video thumbnail CTR is
bulk Reporting API only; the loop uses public velocity + engagement as the proxy and never
fabricates a CTR. Full detail and sources: `docs/GROWTH_FEEDBACK_LOOP_2026-11-04.md`.

**Cost: $0.00.** Only the free Data API and the already-configured upload token; no new secret,
no paid tier, no manual gate. Tests: 25 new (feedback + brain-steering integration), the two
tests that pinned the old stale behavior updated to the new correct behavior, and the
scheduler-supervisor tests made robust to new workflows. **Full suite: 734 passed + 1632
subtests, 0 failed.** Nothing here guarantees results; it guarantees the channel stops
publishing blind and starts compounding.
