# Architectural Guarantee: $0.00 / Month Permanent Free-Tier Lock

***

## 1. Executive Commitment

**The Secret Place** YouTube automation and editorial production pipeline is permanently and architecturally locked at **$0.00 / month**. Under no circumstances will any component require, incur, or transition to a paid subscription, credit card charge, or billable cloud tier.

If any external API quota limit is reached, the system **fails closed**: jobs pause automatically and resume only after free quotas refresh. It will never fall back to a paid tier.

---

## 2. Subsystem-by-Subsystem Zero-Cost Audit

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PERMANENT $0.00 ZERO-COST PIPELINE                   │
├─────────────────────────┬──────────────────────┬───────────────────────┤
│ Subsystem               │ Free Tier Limit      │ Fail-Closed Mechanism │
├─────────────────────────┼──────────────────────┼───────────────────────┤
│ Google Gemini Voice TTS │ 15 RPM / 1,500 RPD   │ Automatic 429 backoff │
│ Microsoft Edge Voice    │ Free Neural Stream   │ Paragraph chunking    │
│ Visual Plates & B-Roll  │ Public Domain / CC0  │ SHA-256 Ledger gate   │
│ Audio DSP Soundscapes   │ 100% Procedural DSP  │ SciPy/NumPy synthesis │
│ Cloud Compute & CI/CD   │ Free GitHub Runners  │ Public repo unlimited │
│ YouTube Data API v3     │ 10,000 units / day   │ Daily quota pause     │
│ Hosting & Review Portal │ Free GitHub Pages    │ Static build delivery │
└─────────────────────────┴──────────────────────┴───────────────────────┤
│ TOTAL MONTHLY COST      │ $0.00 / month FOREVER│ ZERO FINANCIAL RISK   │
└─────────────────────────┴──────────────────────┴───────────────────────┘
```

---

## 3. Subsystem Breakdown

### A. Google Gemini Brain & Voiceover Synthesis ($0.00 Hard Lock)
1. **Google Gemini Free Tier Invariant**:
   * Operates strictly within Google AI Studio's **Free Tier** ($0.00 / month forever).
   * Free limits: **15 Requests Per Minute (RPM)**, **1,500 Requests Per Day (RPD)**, **1,000,000 Tokens Per Minute (TPM)**.
   * Under no circumstances will any call transition to Vertex AI billable tiers, pay-as-you-go billing accounts, or credit card charges.
2. **Locked-in Daily Quota Reset & Auto-Continuation**:
   * Google's daily free tier quota resets daily at **midnight Pacific Time** (08:00 UTC PST / 07:00 UTC PDT).
   * If the daily quota finishes (HTTP 429 / `RESOURCE_EXHAUSTED`), `pipeline/quota_handler.py` catches `GeminiQuotaExceededError`, calculates the exact next reset timestamp (`calculate_next_quota_reset_utc()`), and safely marks the queue job as `status: quota_paused` with `quota_reset_utc: <ISO 8601>`.
   * **Seamless Auto-Resume**: The production cron runs twice daily (`06:14 UTC` and `14:14 UTC`). When `now_utc >= quota_reset_utc`, `select_jobs` in `pipeline/run.py` and `select_next_queued_short` in `pipeline/short_release.py` automatically detect that the quota has refreshed, unpause the job to `status: approved`, and seamlessly continue rendering and uploading with the permanent `Charon` voice at **$0.00**.
   * **Voice Integrity Invariant**: The pipeline never falls back to an unapproved voice when Gemini quota finishes. It fails closed, pauses, and resumes with the official Google voice (`Charon`) at the next reset.
3. **Microsoft Edge-TTS (`edge-tts`)**:
   * Secondary zero-cost fallback for dev rendering; 100% free with no credit card required.

### B. Procedural Ambient Soundscapes ($0.00)
* Soundscapes, score beds, and harmonic prayer drones are synthesized in mathematical code via `tools/score.py` using **SciPy** and **NumPy** DSP sine/harmonic wave generators.
* Zero commercial music licenses, zero royalty payments, and 0.00% Content ID copyright claims.

### C. Visual Plates & Stock Media ($0.00)
* All visual assets are sourced strictly from verified **Public Domain** and **CC0 Creative Commons** archives:
  * United States Geological Survey (USGS) landscape archives.
  * National Oceanic and Atmospheric Administration (NOAA) cloud and ray photography.
  * National Park Service (NPS) alpine lake scans.
  * NASA Astronomy Picture of the Day (APOD) and European Southern Observatory (ESO) night sky archives.
  * Metropolitan Museum of Art Open Access collection.
  * Wikimedia Commons and Library of Congress public domain scans.
* **Fail-Closed Gate**: `pipeline/licences.py` inspects SHA-256 hashes against `image-search/LICENSES.yml`. Any unverified or proprietary still (e.g. Getty Images) causes the build to fail immediately.

### D. Cloud Video Assembly & Ingestion Compute ($0.00)
* GitHub Actions provides **unlimited free compute minutes** for public repositories on standard `ubuntu-latest` 4-core runners.
* Video assembly runs FFmpeg locally inside the runner; zero third-party video-rendering cloud SaaS fees.

### E. YouTube Data API v3 ($0.00)
* YouTube provides every Google Cloud project with a default **10,000 units/day free quota**.
* Standard `videos.insert` upload consumes 1,600 units. The pipeline uploads 1–2 videos per day ($\sim 3,200$ units), remaining well within the free limit.
* `pipeline/upload.py` monitors quota errors (`QuotaExceededError`) and pauses jobs until 08:00 UTC (midnight Pacific) without incurring overage fees.

### F. Hosting & Preview Portal ($0.00)
* The showcase review portal (`https://johnazani.github.io/YouTube-automation/`) is hosted for free on **GitHub Pages**.

---

## 4. Operational Invariant

> **Rule:** No PR or dependency may introduce a paid SaaS subscription, billing account requirement, or external credit card integration. The channel will remain 100% free to operate indefinitely.
