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

### A. Voiceover & Audio Narration ($0.00)
1. **Google Gemini API (`gemini-3.8-flash-tts` / `gemini-2.5-flash-tts`)**:
   * Operates strictly within Google AI Studio's **Free Tier**.
   * Free limits: **15 Requests Per Minute (RPM)**, **1,500 Requests Per Day (RPD)**, **1,000,000 Tokens Per Minute (TPM)**.
   * **Lock Enforcement**: The code in `pipeline/gemini_tts.py` catches HTTP 429 (`RESOURCE_EXHAUSTED`) and applies exponential backoff or pauses the queue job with `quota_paused`. It never calls paid GCP Vertex AI endpoints.
2. **Microsoft Edge-TTS (`edge-tts`)**:
   * Uses Microsoft Edge's public read-aloud neural voice service (`en-US-DavisNeural`, `en-US-ChristopherNeural`).
   * 100% free with no account or credit card required.

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
