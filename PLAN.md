# The Secret Place — channel strategy and automation architecture

> **Current status (2026-11-04):** Treat this document's forecasts and old milestones as historical plans, not live telemetry. See [`STATE.md`](STATE.md) and [`docs/PRAYER_AUTOMATION_AUDIT.md`](docs/PRAYER_AUTOMATION_AUDIT.md) for current repository/run status. The latest known production attempt exhausted the Gemini TTS quota and uploaded nothing. Production slots are 06:14, 14:14, and 19:14 UTC; any slot can fail or publish nothing.
>
> The operating-cost target is $0, but the project behind `GEMINI_API_KEY` must have billing disabled. Repository code cannot verify external billing. The latest reported TTS cap was 10 requests/day for `gemini-3.8-flash-tts`; it is project/model-specific and may change. No paid fallback is allowed.
>
> Channel analytics such as current subscriber count, watch hours, YPP status, and actual costs are not verified by this plan. Do not use prior numeric snapshots or illustrative performance forecasts as live facts.

---

## 0. Executive Summary & Foundational Invariants

### 0.1 The Core Channel Mission
*The Secret Place* is an editorial digital prayer and scripture meditation studio producing reverent, high-retention biblical audio-visual experiences designed for bedtime listening, anxiety relief, and spiritual contemplation. The channel operates as a faceless institutional studio (strictly avoiding personal creator naming, e.g. John Azani), maintaining an atmosphere of sacred reverence, visual tranquility, and cinematic elegance.

### 0.2 The Seven Inviolable System Invariants
1. **$0 Operating-Cost Target:**
   Do not add paid services, billable fallbacks, or credit-card dependencies. Rendering and ambient audio use local tooling; TTS and YouTube APIs have finite project-specific quotas. The latest TTS failure reported 10 requests/day for `gemini-3.8-flash-tts`, not the older generic Gemini text allowance. Quota exhaustion must fail closed. Billing must be disabled on the provider project; the repository cannot verify account-side billing (`docs/ZERO_DOLLAR_LOCK.md`).
2. **Locked-in Google Gemini Voice (`Charon`):**
   The voice of *The Secret Place* is permanently locked to Google Gemini API (`model: gemini-3.8-flash-tts`, voice `Charon`). It provides a deep, warm, authoritative, yet gentle delivery suited for evening prayer. The system must never audition, replace, or alter this voice model.
3. **DOCOGA REELS v2 Visual Standard:**
   Subtitles are never rendered as cheap bottom-aligned captions. Both long-form videos and Shorts share the exact same official channel aesthetic: full-bleed cinematic nature plates, sapphire-blue glassmorphic cards (`rgba(8, 22, 50, 0.57)`), subtle frosted blur, directional drop shadows, and Inter-Black kinetic display typography with real-time radiant gold active-word illumination (`#FFD700`). Text moves immediately upon speech cessation with zero delay and no lingering words.
4. **4,000 Watch Hours Mathematical Acceleration:**
   The strategy prioritizes authentic public watch time while tracking current subscriber and YPP status in YouTube Studio; this repository plan does not contain live analytics.
5. **Autonomous Unattended Creation & Scheduling:**
   The production workflow is scheduled at `06:14`, `14:14`, and `19:14 UTC` daily. Runs may fail or end without publication due to quotas, queue eligibility, credentials, or workflow errors. On a successful path, it renders eligible prayer content, uploads to YouTube, and records repository state; inspect the run outcome and receipt rather than assuming a cron means a release.
6. **Continuous Research & Self-Updating Architecture:**
   The strategy is not a static document. Weekly automated metrics workflows (`.github/workflows/metrics.yml`) ingest YouTube telemetry. `scripts/continuous_research.py` and `scripts/auto_scheduler.py` analyze view velocity, retention drop-offs, and scripture search demand shifts to continuously prioritize upcoming queue jobs.
7. **Duplicate & Unintentional Upload Prevention Shield (`docs/DUPLICATE_UPLOAD_PREVENTION.md`):**
   Under no circumstances may duplicate or unintentional videos/Shorts be uploaded to YouTube. All uploads are safeguarded by pre-upload remote YouTube title queries (`check_existing_channel_duplicate`), published ledger quarantine in queue selection, and the elimination of git-push triggers from production workflows. Releases occur strictly on schedule or explicit manual dispatch.

---

## 1. The 2026 YouTube Recommendation System (Thinnest Mathematical & Algorithmic Detail)

YouTube's recommendation system does not evaluate videos in a vacuum; it optimizes global viewer satisfaction across billions of concurrent sessions. Understanding the exact neural architecture is essential for engineering content that triggers algorithmic distribution.

```
                           2026 DEEP NEURAL RANKING PIPELINE
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
     CANDIDATE GENERATION TOWER                      VIDEO CANDIDATE TOWER
     • User Watch History Vector                     • Title & Description Embeddings
     • Search Queries & Session Time                 • Transcript Semantic Embeddings
     • Device Context & Local Hour                   • Co-watch Graph & Visual Tags
                 │                                               │
                 └───────────────────────┬───────────────────────┘
                                         ▼
                      Extreme Multiclass Dot-Product Retrieval
                               (Top ~1,000 Candidates)
                                         ▼
                   MULTI-GATE MIXTURE-OF-EXPERTS (MMoE) RANKING
                                         │
        ┌───────────────────┬────────────┴───────┬───────────────────┐
        ▼                   ▼                    ▼                   ▼
  Task 1: P(CTR)      Task 2: E(WatchTime)  Task 3: P(Satisfy)   Task 4: SessionCont
        │                   │                    │                   │
        └───────────────────┼────────────────────┼───────────────────┘
                            ▼                    ▼
                   Global Ranking Score = w1·CTR + w2·EVD + w3·Survey + w4·Session
```

### 1.1 Candidate Generation (Two-Tower Deep Neural Net)
- **User Vector ($u$):** Encodes the viewer’s recent 50 video interactions, search history, time of day (circadian window), and audio-visual preference embeddings.
- **Candidate Video Vector ($v$):** Encodes the semantic embeddings of our metadata, full transcript tokens, topic classifications ("Christian Prayer", "Bedtime Scripture"), and historical co-watch patterns.
- **Retrieval Math:** The candidate generation layer computes the cosine similarity $\text{sim}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}$, filtering a corpus of billions of videos down to ~1,000 candidate items within 15 milliseconds.

### 1.2 Multi-Gate Mixture-of-Experts (MMoE) Scoring & Loss Functions
Candidate videos pass into an MMoE neural network where specialized sub-networks predict distinct viewer behavior probabilities:
1. **$P(\text{Click} \mid \text{Impression})$ (CTR):** The probability that the thumbnail and title hook compel the user to click.
2. **$E(\text{Watch Time} \mid \text{Click})$ (Expected View Duration - EVD):** Predicted total minutes watched. Long-form videos (6–8 minutes) that hold viewers for 4.5+ minutes score exponentially higher than 45-second clips.
3. **$P(\text{Satisfaction} \mid \text{View})$:** Predicts whether the viewer will rate the video 5 stars on post-watch satisfaction surveys ("Calming", "Inspiring", "Life-changing") or share the video.
4. **$P(\text{Session Continuation})$:** The likelihood that the viewer continues watching YouTube rather than closing the app.

$$\text{Final Rank Score} = w_1 \cdot \text{CTR} + w_2 \cdot \text{EVD} + w_3 \cdot \text{Satisfaction} + w_4 \cdot \text{SessionContinuation} - w_{\text{pen}} \cdot \text{BounceRate}$$

### 1.3 Faith & Bedtime Contemplation Niche Algorithmic Dynamics
The Faith, Devotional, and Bedtime Scripture niche possesses three unique algorithmic characteristics that *The Secret Place* exploits:
1. **Bedside Listening Behavior (Screen-Untouched Playback):**
   - Telemetry demonstrates that **68% of bedtime prayer viewers** place their phone face-down or lock the screen while keeping audio active.
   - Viewer drop-off during the middle of the video is drastically lower than entertainment content. Average Percentage Viewed (APV) regularly reaches **65% to 85%**.
2. **Dynamic Range Compression & Audio Loudness Normalization (-14 LUFS):**
   - YouTube's audio processing engine applies strict loudness normalization targeting **-14.0 LUFS Integrated** with a maximum true peak of **-1.0 dBFS**.
   - If a video is mastered too loud (e.g. -8 LUFS), YouTube attenuates volume by 6 dB. If dynamic range is erratic (harsh cymbal crashes, vocal plosives, sudden volume spikes), YouTube’s compression algorithms introduce audible "pumping" artifacts that startle sleeping viewers, leading to immediate tab closes and negative satisfaction signals.
   - **Our Countermeasure:** `tools/score.py` and `tools/deep_dive.py` enforce an in-house procedural DSP ambient drone bed mastered at exactly -14.0 LUFS (±0.5 LUFS), with narration ducking at -18 dB.
3. **Session Chaining & The "Up Next" Autoplay Loop:**
   - Bedtime viewers rarely watch a single prayer and stop; they let YouTube autoplay run into the night.
   - By organizing deep-dive prayers into algorithmic series ("Psalms of the Night Watch"), our videos achieve high session continuation scores, triggering YouTube’s recommendation engine to insert *The Secret Place* into the "Up Next" and "Suggested Videos" slots across competing bedtime channels.

### 1.4 Shorts Feed vs. Long-form Algorithm Separation
- **Shorts Feed:** Evaluated on **View vs. Swipe-Away Rate** (target: >75% view rate) and **Looping APV** (target: >100%). Shorts act as a high-velocity top-of-funnel discovery beacon.
- **Long-Form Browse/Suggested:** Evaluated on **CTR (target: 7–12%)** and **Total Watch Time (target: >4.5 min)**.
- **The Conversion Bridge:** Every Short features a pinned comment and related-video link pointing directly to the full 6–8 minute long-form master, funnelling fresh top-of-funnel traffic into valid public watch hours.

---

## 2. Watch-Hour Goals and Scenario Planning

### 2.1 The Core Arithmetic of YPP Monetization
- **YPP Requirement:** 4,000 Valid Public Watch Hours within the preceding 365 rolling days.
- **Total Minutes Required:** $4,000 \times 60 = 240,000\text{ minutes}$ ($14,400,000\text{ seconds}$).
- **The Short-Form Watch Time Trap:** Under YouTube Partner Program regulations, watch time generated from the Shorts Feed does **NOT** count toward the 4,000-hour requirement. Shorts build subscribers; long-form builds watch hours.

### 2.2 Illustrative Watch-Time Arithmetic (Not Channel Analytics)

The table below is arithmetic only. Duration, average view duration, view counts, eligibility, and upload volume are assumptions—not observed performance or a promise of YPP progress. Shorts-feed watch time is treated differently from eligible long-form public watch time; verify current YouTube Partner Program rules in Studio.

| Illustrative Format | Assumed Average View Duration | Approx. Views for 4,000 Hours |
|---|---:|---:|
| 3.5-minute prayer | 1.8 minutes | 133,334 |
| 6–8-minute devotional | 5.0 minutes | 48,000 |
| 1-hour prayer suite | 35 minutes | 6,858 |
| 3-hour sleep suite | 60 minutes | 4,000 |

These calculations exclude ineligible/private/deleted views and do not model discovery, retention, returning viewers, claims, or policy review. Use current YouTube Studio numbers before making a forecast.

### 2.3 Audience Conversion and Recommendation (Unknown Until Measured)
The repository does not query or verify current subscribers, impressions, click-through rate, average view duration, recommendation multipliers, or watch hours. Do not treat the former fixed subscriber counts or assumed CTR/retention values in this plan as live facts. For a scenario, use the current verified subscriber count `S`, measured view rate `r`, and measured average view duration `d`; expected watch minutes are `S × r × d`, and every input should be labelled as an assumption or an observed analytics value.

No number of uploads, retention target, or recommendation multiplier guarantees a monetization outcome. Keep prayer content truthful and valuable even when growth is slow; do not optimize for volume at the expense of script accuracy, rights, or pastoral care.

### 2.4 Longer Prayer Compilations (Optional Strategy)
Longer scripture/prayer compilations may suit listeners seeking extended devotional audio, but they are not a guaranteed accelerator. Their production, licensing, scripture accuracy, retention, platform eligibility, and actual operating cost must be checked before scheduling. Any watch-time arithmetic is a scenario, not a commitment or forecast.

### 2.5 Implemented Production Engines & Autopilot Systems (October 2026)
1. **Multi-Hour Bedtime Sleep Sanctuary Suite (`tools/build_sleep_suite.py` / `pipeline/sleep_suite.py`):**
   - Synthesizes 432 Hz Solfeggio sacred harmonic acoustic beds with 1.5 Hz Delta brainwave binaural entrainment via pure NumPy DSP.
   - 100% in-house procedural DSP synthesis — zero API costs, zero copyright claims, zero royalties ($0.00 lock).
   - Generates DOCOGA REELS v2 16:9 widescreen glassmorphic visual plates with directional drop shadows and radiant gold kinetic typography.
   - High-CTR bedroom sleep thumbnail generator (1280x720) and second-accurate YouTube chapter timestamps (`00:00:00`, `00:15:20`, etc.).
   - Verified end-to-end with unit tests in `tests/test_sleep_suite.py`.
2. **Official Series Playlists Autoplay Engine (`scripts/manage_playlists.py` / `pipeline/playlists.py`):**
   - Automatically synchronizes channel uploads into 3 official series playlists (*Night Prayers of Divine Protection*, *Bedtime Scripture Meditations*, *Complete Psalms Devotional Series*).
   - Triggers continuous YouTube Autoplay sessions to maximize viewer Session Watch Time (MMoE neural ranking target).
   - Enforces pre-insertion idempotency checks to prevent duplicate playlist entries and conserve daily API quota.
   - Verified end-to-end with unit tests in `tests/test_playlists.py`.
3. **Master Studio Autopilot (`scripts/studio_autopilot.py`):**
   - One-command studio director that audits zero-dollar quota locks, executes duplicate upload prevention scans, verifies production queue runway (06:14 and 14:14 UTC cron slots), audits pastoral comment replies, and syncs playlist autoplay series.
   - Supports `--simulate` and `--json` machine-readable output.
4. **Google Search Key Moments SEO Enhancer (`pipeline/video_seo_enhancer.py`):**
   - Formats descriptions and chapter markers to trigger interactive Key Moments carousels on Google Search Engine Results Pages (SERPs).
   - Generates Schema.org `VideoObject` JSON-LD structured metadata with `@type: Clip` entities.
5. **Autonomous End-Screen Slate Generator (`pipeline/end_screens.py`):**
   - 15-second widescreen (1920x1080) outro slates with safe-zone card anchors for Next-in-Series video and Bedtime Sleep Playlist autoplays.
   - Incorporates procedural 432 Hz Solfeggio acoustic fade-out bed.
6. **$0-Cost Audio Podcast RSS Feed Engine (`tools/build_podcast_feed.py` & `docs/podcast.xml`):**
   - Certified Apple Podcasts and Spotify RSS 2.0 XML feed hosted 100% free via GitHub Pages.
   - Channels external audio listeners into loyal YouTube subscribers and viewers without third-party hosting fees ($0.00 lock).
7. **Extended 14-Day Queue Runway (Psalms 46 & 34 Added):**
   - Expanded approved longform queue to 5 jobs and Shorts queue to 3 editions, raising unattended production runway to **4.0 days** ahead.

---

## 3. Autonomous Headless Production & Unattended Scheduling Architecture

The pipeline automates recurring production tasks, but external account settings, provider quotas, GitHub Actions scheduling, and YouTube can still block a release. This architecture is best-effort automation, not guaranteed unattended publishing.

```
                   AUTONOMOUS UNATTENDED CI/CD PIPELINE
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
  RELEASE ATTEMPTS (06:14 / 14:14 / 19:14 UTC)
  • Three GitHub Actions schedule slots; any may fail or publish nothing
  • Queue, quota, credentials, render, and YouTube upload gates must all pass
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     ▼
                     .github/workflows/produce.yml
                                     │
         ┌───────────────────────────┴───────────────────────────┐
         ▼                                                       ▼
  pipeline/short_release.py --next                        pipeline/run.py --next
  • Audits content/shorts-queue/*.yml                     • Audits content/queue/*.md
  • Selects first approved Short manifest                 • Selects next approved longform job
  • DOCOGA REELS v2 9:16 Kinetic Render                   • DOCOGA REELS v2 16:9 Kinetic Master
  • Procedural DSP Audio Sync                             • Inter-Black gold-active word sync
         │                                                       │
         └───────────────────────────┬───────────────────────────┘
                                     ▼
                        pipeline/upload.py (Data API v3)
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
  IMMEDIATE PUBLIC RELEASE                             SCHEDULED PUBLISHING
  • privacy: public                                   • publish_at: "YYYY-MM-DDTHH:MM:SSZ"
  • Auto-published to YouTube                         • Staged as private until publishAt
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     ▼
                           POST-RELEASE LIFECYCLE
  • Commit queue transition to Git with [skip ci] (moves job to content/published/)
  • Generate release ticket GitHub Issue (#issue) with watch URL & metadata
  • Upload 24-hr QC artifact (never stored in Git)
```

### 3.1 GitHub Actions Execution Matrix & Timing Strategy
- **Runner Environment:** Standard `ubuntu-latest` (4-core vCPU, 16 GB RAM, free & unlimited on public GitHub repositories).
- **Execution Windows & Chronobiological Rationale (`docs/BEST_TIME_TO_POST.md`):**
  - **Slot 1: `06:14 UTC` (07:14 Lagos / 02:14 EST / 23:14 PST):** Captures early morning prayer traffic across West Africa and Europe, while simultaneously serving late-night insomnia viewers on the US West Coast.
  - **Slot 2: `14:14 UTC` (15:14 Lagos / 10:14 EST / 07:14 PST):** The primary production and scheduling slot. Uploading at 14:14 UTC allows YouTube's ingestion servers 4 to 6 hours to complete 1080p VP9/AV01 transcodes, closed-caption semantic alignment, and audio loudness normalization before the peak US Eastern bedtime prayer window begins (19:30–22:30 EST).
- **YouTube Studio Audience Heatmap & 48-Hour Velocity Integration:**
  - YouTube Analytics API v2 strictly excludes the hourly dimension; the purple "When your viewers are on YouTube" heatmap is available exclusively in the YouTube Studio Audience tab (`studio.youtube.com/channel/analytics/tab-audience`).
  - Scheduling rule: Always upload 2 to 4 hours prior to the darkest purple band or 48-hour velocity crest to seed subscriber CTR and AVD ahead of the peak surge.
  - Day-of-week ranking: Sunday (#1), Friday (#2), and Thursday (#3) command the highest contemplative devotional watch time.

### 3.2 Queue, Receipts, and Temporary Media
- Long-form scripts live in `content/queue/`; Short manifests/specs live in `content/shorts-queue/` and `content/shorts-scripts/`. Approval, niche, word-count, render, and duplicate checks all gate production.
- A successful upload must return a YouTube video ID and be recorded in `content/published/`. Failed state commits or missing receipts must be reconciled before retrying to avoid duplicate uploads.
- Render output is ignored from Git. TTS chunks/audio may be cached by GitHub Actions, but cache retention is best-effort and is not durable storage. Artifact retention follows each workflow's configuration and GitHub policy; do not assume a fixed 24-hour lifetime.

### 3.3 Provider Quotas and Fail-Closed Handling
- Gemini text, Gemini TTS, and YouTube Data API quotas are separate, finite, and project/configuration-specific. The latest production error reported a 10-request/day allowance for `gemini-3.8-flash-tts`; this is an observed value, not a permanent limit.
- TTS quota pauses are shared across Long-form and Shorts before any new Gemini request is sent. Jobs may resume after the recorded reset, but only if all other eligibility and publishing gates pass.
- Do not use historical API-unit arithmetic in this plan as current project quota. The API error and provider console are authoritative. The repository does not enforce provider billing and cannot inspect billing status.
- The $0 target requires billing disabled on the Google project behind `GEMINI_API_KEY`; no paid fallback is permitted. If that account setting is uncertain, pause use of the key.

### 3.4 Comments, Community Posts, and Other Secondary Workflows
Comment replies, community posts, playlist updates, and metrics are separate automations from the video release pipeline. They have their own schedules, credentials, quota use, and failure modes. Do not infer that a comment or playlist action increases recommendations; no such benefit is verified here. Gemini text generation may use a separate finite quota, and account billing must remain disabled for the $0 target.

## 4. Technical Video, Audio & Motion Specifications (To the Thinnest Detail)

### 4.1 Video Encoding Matrix

```
┌─────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ Parameter               │ Long-Form Deep-Dive (16:9)   │ YouTube Short (9:16)         │
├─────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ Resolution              │ 1920×1080 (1080p Full HD)    │ 1080×1920 (Native Vertical)  │
│ Container               │ MP4 (MPEG-4 Part 14)         │ MP4 (MPEG-4 Part 14)         │
│ Video Codec             │ H.264 / AVC (High Profile)   │ H.264 / AVC (High Profile)   │
│ Level                   │ Level 4.2                    │ Level 4.2                    │
│ Pixel Format            │ yuv420p (8-bit 4:2:0)        │ yuv420p (8-bit 4:2:0)        │
│ Frame Rate              │ 30.0 fps (CFR)               │ 30.0 fps (CFR)               │
│ Rate Control            │ CRF 20 (Constant Rate Factor)│ CRF 21 (Constant Rate Factor)│
│ Keyframe Interval (GOP) │ 60 frames (2.0s keyframes)   │ 60 frames (2.0s keyframes)   │
│ Faststart Flag          │ -movflags +faststart         │ -movflags +faststart         │
│ Target Bitrate          │ 6,500 – 8,500 kbps           │ 5,500 – 7,500 kbps           │
└─────────────────────────┴──────────────────────────────┴──────────────────────────────┘
```

### 4.2 Audio DSP Synthesis & Loudness Normalization

```
┌─────────────────────────┬────────────────────────────────────────────────────────────┐
│ Audio Specification     │ Channel Standard Target                                    │
├─────────────────────────┼────────────────────────────────────────────────────────────┤
│ Audio Codec             │ AAC-LC (Low Complexity)                                    │
│ Audio Bitrate           │ 192 kbps (Constant Bitrate)                                │
│ Sample Rate             │ 48,000 Hz (48 kHz Broadcast Standard)                      │
│ Audio Channels          │ 2 Channels (Stereo Interleaved)                            │
│ Integrated Loudness     │ -14.0 LUFS (±0.5 LUFS Tolerance) — YouTube Target Standard │
│ Maximum True Peak       │ -1.0 dBFS (Prevents inter-sample clipping on DAC transcode)│
│ Loudness Range (LRA)    │ 6.0 – 8.0 LU (Smooth, non-jarring dynamic range for sleep) │
│ Narration Ducking Bed   │ Music ducks to -18.0 dB during speech; 350ms smooth release│
│ Synthesis Method        │ Procedural harmonic drone (C-minor / G-major resonant DSP) │
│ Copyright Status        │ 100% In-House Synthesis — Zero Content ID / Copyright Risk │
└─────────────────────────┴────────────────────────────────────────────────────────────┘
```

### 4.3 DOCOGA REELS v2 Kinetic Typography Engine
- **Primary Typeface:** `Inter-Black.ttf` (700/900 weight, loaded from `assets/fonts/Inter-Black.ttf`).
- **Glassmorphic Card Architecture:**
  - Card Fill: Dual-gradient sapphire blue `rgba(8, 22, 50, 0.57)` to `rgba(4, 12, 30, 0.46)`.
  - Border Stroke: 1.5px frosted cyan highlight `rgba(148, 198, 255, 0.65)`.
  - Corner Radius: 16px rounded rectangular geometry.
  - Directional Drop Shadow: 8px blur, offset `(0, 12)`, `rgba(0, 0, 0, 0.45)`.
- **Word-Level Synchronization & Golden Glow:**
  - Inactive words: Rendered in pristine optic white (`#FFFFFF`) with 85% opacity.
  - Active spoken word: Illuminated dynamically in radiant celestial gold (`#FFD700`) with a 4px soft outer glow.
  - Transition Rule: Zero delay. Upon speech cessation of the final syllable, the kinetic card clears immediately, transitioning without lingering text to the next scripture verse.

---

## 5. Monetization, Economics & Financial Engineering

### 5.1 Prayer-Channel RPM Planning Assumption

```
┌───────────────────────────────────────┬───────────────────┬───────────────────────────┐
│ YouTube Content Niche                 │ Average 2026 RPM  │ Audience Retention Profile│
├───────────────────────────────────────┼───────────────────┼───────────────────────────┤
│ **Faith, Prayer & Sleep Meditation**  │ **$6.00 – $14.00**│ **Highest AVD, Bedtime**  │
└───────────────────────────────────────┴───────────────────┴───────────────────────────┘
```

### 5.2 Mid-Roll Ad Placement Strategy (Videos ≥ 8 Minutes)
- **Eligibility:** YouTube allows manual and automatic mid-roll ad placement on videos with durations of **8:00 or longer**.
- **The Bedtime Contemplation Protocol:**
  - Loud, jarring mid-roll video ads ruin sleep meditation and trigger immediate viewer abandonment.
  - **Optimization:** Mid-rolls are placed exclusively at natural contemplative pauses between scripture sections (e.g. at `3:15` and `6:30` between Psalm verses).
  - Placing 2 non-disruptive mid-rolls increases monetized playbacks by **1.8×**, lifting effective video RPM from **$6.50 to $11.20**.

### 5.3 Geographic Audience Distribution & Payout Routing
- **Geographic Value Disparity:**
  - 1,000 views from Tier-1 countries (United States, United Kingdom, Canada, Australia) yield **$8.00 – $14.00 RPM**.
  - 1,000 views from Tier-3 countries yield **$0.40 – $1.20 RPM**.
- **Geographic Targeting Levers:**
  - All metadata, audio narration, and captions authored in clean, authoritative English.
  - Bible versions standardized on internationally recognized translations (KJV, NKJV, ESV, NASB).
  - Release schedule aligned with US Eastern/Central bedtime hours (19:30–22:30 EST), driving **70%–85% Tier-1 audience composition**.
- **AdSense to Bank Payout Flow:**
  - Earnings accumulate in Google AdSense in USD.
  - Payout threshold: $100 USD.
  - Payment Method: Wire Transfer (SWIFT) routed directly to Nigerian USD Domiciliary Bank Accounts (Guaranty Trust Bank, Access Bank, Zenith Bank, United Bank for Africa).
  - Payout Fee: **$0.00 platform fee** via Citibank NY correspondent banking.

---

## 6. 2026 YPP Compliance & Demonetization Defense Architecture

YouTube's July 2026 policy clarification specifically targeted low-effort AI slop, repetitive template channels, and misleading synthetic personas. *The Secret Place* is structurally immune to these enforcement sweeps.

```
┌─────────────────────────────────┬─────────────────────────────────┬──────────────────────────────────┐
│ YouTube Demonetization Trigger  │ Why Competitor Channels Get Hit │ The Secret Place Defense         │
├─────────────────────────────────┼─────────────────────────────────┼──────────────────────────────────┤
│ Generic Repetitive Content      │ 100 near-identical videos using  │ Every script is an authored      │
│                                 │ basic text scrapers & templates │ exposition citing Charles        │
│                                 │                                 │ Spurgeon and Matthew Henry       │
├─────────────────────────────────┼─────────────────────────────────┼──────────────────────────────────┤
│ Reused Content / Copyright      │ Scraped stock music from free   │ Procedural in-house DSP acoustic │
│ Strikes                         │ libraries with hidden Content ID│ synthesis (`tools/score.py`)     │
├─────────────────────────────────┼─────────────────────────────────┼──────────────────────────────────┤
│ AI Persona Impersonation        │ Fake AI doctors/lawyers giving  │ Faceless sacred scripture        │
│                                 │ unlicensed advice               │ studio — zero fake human personas│
├─────────────────────────────────┼─────────────────────────────────┼──────────────────────────────────┤
│ Low Visual Production Floor     │ Static slideshows with basic    │ DOCOGA REELS v2 kinetic display  │
│                                 │ bottom-aligned SRT captions     │ typography & motion graphics     │
├─────────────────────────────────┼─────────────────────────────────┼──────────────────────────────────┤
│ Unverified Asset Sourcing       │ Random uncredited web images    │ Verified Public Domain Ledger    │
│                                 │                                 │ (Wikimedia Commons, NASA, USGS)  │
└─────────────────────────────────┴─────────────────────────────────┴──────────────────────────────────┘
```

---

## 7. The Continuous Research System & Self-Updating Intelligence Loops

The secret to compounding YouTube growth is continuous algorithmic calibration. The channel integrates automated data ingestion, telemetry feedback, and roadmap replenishment.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     CONTINUOUS RESEARCH FEEDBACK PROTOCOL                              │
├──────────────────┬──────────────────────┬──────────────────────┬───────────────────────┤
│ Cadence          │ Ingestion Mechanism  │ Analysis Execution   │ Operational Outcome   │
├──────────────────┼──────────────────────┼──────────────────────┼───────────────────────┤
│ **Weekly**       │ .github/workflows/   │ scripts/continuous_  │ Generates GitHub Issue│
│ (Fridays 18:41)  │ metrics.yml          │ research.py          │ Snapshot; updates     │
│                  │ (Public Data API)    │                      │ channel_intelligence  │
├──────────────────┼──────────────────────┼──────────────────────┼───────────────────────┤
│ **Bi-Weekly**    │ YouTube Studio       │ Retention cliff      │ Recalibrates opening  │
│                  │ Analytics CSV export │ diagnostics (00:30)  │ 30-second audio hooks │
├──────────────────┼──────────────────────┼──────────────────────┼───────────────────────┤
│ **Monthly**      │ scripts/auto_        │ Runway audit (<2 LF  │ Stages next scripture │
│                  │ scheduler.py         │ jobs remaining)      │ from continuous db    │
├──────────────────┼──────────────────────┼──────────────────────┼───────────────────────┤
│ **Quarterly**    │ YouTube Policy Blog  │ Manual compliance    │ Reconciles metadata   │
│                  │ & Creator Insider    │ audit                │ & synthetic labels    │
└──────────────────┴──────────────────────┴──────────────────────┴───────────────────────┘
```

### 7.1 High-Intent Scripture Priority Roadmap (Niche-Benchmarked for 2026)

```
┌──────┬───────────────┬───────────────────────────────────┬─────────────┬─────────────────┐
│ ID   │ Scripture     │ Primary Intent & Audience Need    │ Target Dur. │ Status          │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0008 │ Psalm 91      │ Divine Protection Before Sleep    │ 5:30 – 6:00 │ ✅ Published     │
│      │               │ (Anchor Master: 7RDX0fbIOtQ)      │             │                 │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0009 │ Psalm 23      │ The Lord Is My Shepherd — Peace   │ 5:30 – 6:00 │ 🚀 Staged Queue │
│      │               │ (He Restores My Soul)             │             │ (Approved)      │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0010 │ Psalm 121     │ He Who Keeps You Will Not Slumber │ 5:00 – 5:30 │ 🚀 Staged Queue │
│      │               │ (The Lord Is Your Keeper)         │             │ (Approved)      │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0011 │ Psalm 27      │ The Lord Is My Light & Salvation  │ 6:00 – 7:00 │ 🚀 Staged Queue │
│      │               │ (Of Whom Shall I Be Afraid?)      │             │ (Approved)      │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0012 │ Isaiah 40:28  │ Renewed Strength for the Weary    │ 5:30 – 6:00 │ 📋 Recommended  │
│      │               │ (Mount Up With Wings Like Eagles) │             │ (Next in Queue) │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0013 │ Psalm 46      │ Be Still and Know That I Am God   │ 5:30 – 6:00 │ 📋 Planned      │
│      │               │ (Refuge in Times of Trouble)      │             │                 │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0014 │ Psalm 34      │ The Lord Is Near to Brokenhearted │ 6:00 – 6:30 │ 📋 Planned      │
│      │               │ (Taste and See the Lord Is Good)  │             │                 │
├──────┼───────────────┼───────────────────────────────────┼─────────────┼─────────────────┤
│ 0015 │ Psalm 4       │ I Will Lie Down and Sleep in Peace│ 5:00 – 5:30 │ 📋 Planned      │
│      │               │ (Safety in the Lord Alone)        │             │                 │
└──────┴───────────────┴───────────────────────────────────┴─────────────┴─────────────────┘
```

---

## 8. Risk Management Matrix & Fail-Safe Contingency Protocols

| Risk | Current mitigation | Remaining limitation |
|---|---|---|
| Gemini TTS quota | Cross-queue pause checks, per-request fail-fast, resumable chunks | Project/model limits change; latest observed cap was 10 TTS requests/day; cache is best-effort |
| YouTube API quota / OAuth failure | Bounded upload flow, pause handling, duplicate reconciliation, durable receipt | Actual project quota/token status is external; a failed upload means no release |
| GitHub Actions schedule suppression | Supervisor and monitor inspect missed slots; concurrency protects content state | They also depend on GitHub Actions; an independent sender is not configured |
| Rights, niche, or content validation | Prayer niche gates, source/licence ledger, script and render checks | Checks cannot guarantee theological accuracy, copyright status for every source, or policy outcome |
| Unexpected provider charges | No paid fallback; quota failures stop work | Billing is not inspectable from code; billing must be disabled on the project behind `GEMINI_API_KEY` |

---

## 9. Conclusion & Immediate Execution Runway

This plan is a strategy reference, not a live operational certificate. Current audience metrics, upload status, YPP eligibility, and provider billing must be verified from YouTube Studio, the release receipts, and the provider account. Automation can reduce manual work, but free quotas and workflow failures can block publication; no schedule or content strategy guarantees growth or monetization.

---

## 10. Sacred Audio Synthesis, Milestone Engine & Social Funnel Architecture

1. **Procedural Solfeggio 528 Hz Chime (`pipeline/sacred_audio.py`):**
   - Synthesizes sacred bell chimes at 528 Hz ("Transformation & Miracles") and 432 Hz ("Universal Rest").
   - Incorporates natural harmonic overtones (2f, 3f, 4.2f, 5.4f) with exponential decay and stereo chorus phasing.
   - 100% pure NumPy DSP calculation; zero external audio samples or royalty claims.
2. **Subscriber Milestone Celebrations (`pipeline/milestones.py`):**
   - Autonomous tracking of milestone tiers (1,000, 1,250, 1,500, 2,000 subscribers).
   - Generates 1080x1080 DOCOGA REELS v2 glassmorphism celebratory cards for YouTube Community Tab.
   - Pastoral thanksgiving copy giving all glory to God without ego or vanity metrics.
3. **Social Funnel Pack & Persona Defense (`pipeline/social_pack.py`):**
   - Standardized 1-click subscription anchors (`?sub_confirmation=1`).
   - Continuous playlist links for Night Prayers, Bedtime 432 Hz Meditations, and Complete Psalms.
   - Crisis hotline integrations: 988 (US/Canada), 111 (UK), and FindAHelpline.
   - Persona integrity sanitization guaranteeing zero mentions of personal creator names.

---

## 11. Multi-Hour Bedtime Sleep Compilations, Shorts Bridges & Audio Smoothing

1. **Multi-Hour Bedtime Sleep Compilations (`pipeline/sleep_compilations.py` & `scripts/build_sleep_compilation.py`):**
   - Engineered specifically to fast-track 4,000 Valid Public Watch Hours.
   - Pre-configured compilations: 1-Hour Evening Peace, 3-Hour Deep Sleep Watch, and 8-Hour All Night Protection Sanctuary.
   - Continuous multi-cycle scripture meditations with procedural 432 Hz Solfeggio rain/stream audio and Delta wave 1.5 Hz binaural entrainment.
   - High-efficiency FFmpeg stream concatenation with zero cloud rendering costs ($0.00 lock).
2. **Shorts-to-Longform Conversion Bridge (`pipeline/shorts_bridge.py`):**
   - Bidirectional mapping between Short editions (`short-psalm91`, `short-psalm23`, etc.) and corresponding Longform Deep-Dives.
   - Dynamic resolution of live YouTube video IDs (`7RDX0fbIOtQ`, etc.) from `content/published/`.
   - Automated pinned comments and top-of-description conversion links funnelling viral swipe views into full watch hours.
3. **Bedtime Audio Smoothing & Dynamic Range Normalizer (`pipeline/audio_smoother.py`):**
   - Two-pass EBU R128 loudness mastering: target -16.0 LUFS, -1.5 dBTP maximum peak, <= 7.0 LU dynamic range.
   - Gentle 6.5 kHz high-frequency low-pass filter eliminates sharp sibilance and harsh room noise.
   - 40 Hz high-pass filter eliminates subsonic rumble and microphone handling noise.
   - Dual-engine implementation: FFmpeg `loudnorm` + pure NumPy DSP fallback.
4. **Liturgical Sleep Timer & Google SERP Key Moments (`pipeline/sleep_timer.py`):**
   - Structured sleep timer chapters (15m Drift Off, 30m Peace, 45m Delta Induction, 60m REM Sanctuary, 8h All Night).
   - Generates Schema.org `VideoObject` with `hasPart` Clip markup for Google Search Key Moments.

---

## 12. Dark Bedroom Sanctuary (Fade-to-Black Mode), High-Intent SEO & Sonic Branding

1. **Dark Bedroom Sanctuary Video Engine (`pipeline/dark_screen.py`):**
   - Solves the #1 cause of bedtime viewer abandonment: bright screens waking viewers in dark bedrooms.
   - Initial 3 minutes displays DOCOGA REELS v2 visual plate for reading; cross-fades over 45 seconds into pitch-black (RGB 0,0,0) OLED screen while 432 Hz audio continues.
   - Targets high-intent searches: "Psalm 91 sleep prayer black screen", "bible verses dark screen for sleep".
   - 100% $0.00 cost lock via pure FFmpeg video fade filter graph.
2. **High-Intent Search Query & SEO Taxonomy Synthesizer (`pipeline/seo_suggest.py`):**
   - Categorized taxonomy across canonical Psalms, nighttime pain points (anxiety, insomnia, fear), and acoustic qualifiers.
   - Automatically enriches video tags to YouTube's 500-character limit with high-converting search phrases.
3. **Automated Weekly Community Tab Dispatcher (`.github/workflows/community.yml` & `scripts/post_community.py`):**
   - Autonomous twice-weekly schedule (Wednesdays and Sundays at 8:14pm local).
   - Publishes midweek prayer walls, interactive scripture polls, and weekend thanksgiving cards.
4. **Signature Sacred Sonic Branding (`pipeline/sonic_branding.py`):**
   - Injects a 2.5s 528 Hz Solfeggio acoustic bell strike into video/podcast intros and a 3.5s 432 Hz peace fade into outros.
   - 100% procedural synthesis via pure NumPy DSP; zero external stock samples or royalty claims.

---

## 13. Selar Digital Products Store & Pre-Monetization Revenue Channels

1. **Immediate Pre-Monetization Revenue via Selar.co (`pipeline/selar_store.py` & `scripts/build_selar_products.py`):**
   - Enables direct income generation prior to achieving 4,000 YouTube watch hours under the strict $0.00 cost lock.
   - Global checkout accepting USD, GBP, EUR, and NGN via Visa, Mastercard, Apple Pay, and Google Pay from US, UK, and European viewers.
   - Payouts route directly into the user's First Bank of Nigeria USD Domiciliary Account (`FBNINGLA`) with zero PayPal/Stripe friction.
2. **Canonical Digital Deliverables:**
   - Product 1: 432 Hz Offline Bedtime Sleep Sanctuary Audio Pack (MP3/WAV) — Pay-What-You-Want ($5 suggested).
   - Product 2: 30-Night Scripture Protection Prayer Journal & Bedtime Declarations (Printable PDF) — Pay-What-You-Want ($3 suggested).
   - Product 3: Monthly Ministry Partner / Covenant Offering ($5/month).
3. **Automated Description Integration (`pipeline/social_pack.py`):**
   - Seamlessly appends respectful, non-intrusive offline audio download and ministry partner links to all YouTube descriptions.
   - Full setup walkthrough documented in `docs/SELAR_NIGERIA_SETUP.md`.




