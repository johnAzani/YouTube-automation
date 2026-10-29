# Google Search Key Moments, End-Screen Autoplay & $0 Podcast RSS Engine
## Multi-Platform Discovery, Session Watch Time & External Funnel ($0.00 / Month Hard Cost Lock)

> **Channel:** *The Secret Place* (`@TheSecretPlace`)  
> **Audience:** **1,230 Subscribers** (YPP 1,000 Threshold Surpassed)  
> **Primary Milestone:** **4,000 Valid Public Watch Hours**  
> **Financial Governance:** Strict, fail-closed **$0.00 / month cost lock** (`docs/ZERO_DOLLAR_LOCK.md`). Zero cloud infrastructure bills, zero paid APIs.

---

## 1. Google Search "Key Moments" Video SEO Enhancer (`pipeline/video_seo_enhancer.py`)

Over 40% of nighttime prayer searches originate directly from Google Search (`"psalm 91 prayer for sleep"`, `"psalm 23 bedtime meditation"`). Google Search displays YouTube videos with interactive **Key Moments** clip carousels directly on the Search Engine Results Page (SERP).

### Specifications & Formatting:
1. **First Timestamp:** Must begin at `00:00`.
2. **Ascending Order:** All timestamps strictly ascend with at least 10 seconds per clip.
3. **Intent-Targeted Naming:** Chapters are structured with search keywords (*"Opening Prayer & Scripture"*, *"Divine Protection Covenant"*, *"Angelic Army Guard"*, *"Sacred Night Benediction"*).
4. **Schema.org VideoObject JSON-LD:** Generates structured JSON-LD with `@type: Clip` entities for search engine crawler indexing.

---

## 2. Autonomous End-Screen Outro Slate & Card Autoplay Engine (`pipeline/end_screens.py`)

When a viewer finishes watching Psalm 91 or Psalm 23, if there is no End Screen pointing to the next video or Series Playlist, YouTube auto-recommends a competitor's video. 

### Visual Architecture (DOCOGA REELS v2 16:9 Widescreen):
- **Duration:** 15.0 seconds.
- **Canvas:** $1920 \times 1080$ Full HD.
- **Backdrop:** Midnight sapphire vertical gradient (`#040c1a` to `#091f3d`) with golden celestial halo.
- **Card Anchors (YouTube Studio End-Screen Safe Areas):**
  - **Left Card Slot (`x=140, y=340, w=760, h=428`):** *Watch Next in Series* (e.g. Psalm 23 or Psalm 121).
  - **Right Card Slot (`x=1020, y=340, w=760, h=428`):** *Continuous Sleep Playlist (432 Hz)*.
  - **Center Avatar Ring (`cx=960, cy=173, r=65`):** *Subscribe to The Secret Place*.
- **Audio:** Continuous 432 Hz Solfeggio acoustic bed with gentle fade-out via pure NumPy DSP.

---

## 3. $0-Cost Audio Podcast RSS Feed Engine (`tools/build_podcast_feed.py` & `docs/podcast.xml`)

Bedtime listeners frequently listen to ambient scripture audio on Apple Podcasts, Spotify, and Amazon Music.

### Zero-Dollar Infrastructure:
- **Hosting:** 100% free via GitHub Pages at `https://johnazani.github.io/YouTube-automation/podcast.xml`.
- **Zero Third-Party Fees:** Completely replaces $20/month podcast host subscriptions (Libsyn, Podbean).
- **Format:** Fully certified iTunes / Apple Podcasts / Spotify RSS 2.0 XML with `<itunes:category>`, `<enclosure>`, and high-resolution artwork.
- **Traffic Funnel:** Every episode description links directly back to the YouTube video, channeling external podcast listeners into loyal YouTube subscribers and video viewers!

---

## 4. Extended 14-Day Queue Expansion

To guarantee headless, unattended production, the queue has been expanded with four foundational Psalm expositions:
- **Job 0013 (Psalm 46):** *God Is Our Refuge & Strength — Be Still & Know | The Secret Place*
- **Job 0014 (Psalm 34):** *The Angel of the Lord Encamps Round About You — Bedtime Prayer | The Secret Place*
- Companion vertical Shorts: `short-psalm46` and `short-psalm34` in `content/shorts-queue/`.
- Verified asset queries and factcheck worksheets generated in `content/factcheck/`.

---

## 5. Verification Commands

```bash
# Generate the certified podcast RSS feed:
python tools/build_podcast_feed.py

# Verify all 183 automated tests:
PYTHONPATH=. pytest

# Run the unified Studio Autopilot health check:
python scripts/studio_autopilot.py
```
