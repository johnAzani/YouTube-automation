# Uploading a Long-Form Video to YouTube: Technical, Operational & Algorithmic Master Guide

**Document Version:** 1.0 (Master Ingestion & Publishing Architecture)  
**Date:** October 29, 2026  
**Channel Identity:** *The Secret Place* (`@TheSecretPlace`) — Faceless Devotional & Faith Documentary Studio  
**Primary Long-Form Master Asset:** `docs/media/deep-dive-psalm91.mp4` (1280×720 FHD Master, 16:9 Widescreen)  
**Primary Long-Form Thumbnail:** `docs/media/psalm-91-longform-thumbnail.jpg` (1280×720 High-CTR Studio Plate)  
**Automation Codebase:** `pipeline/upload.py`, `tools/deep_dive.py`, `tools/score.py`

---

## 1. Executive Summary: Why Long-Form Video is Channel Equity

While YouTube Shorts drive rapid subscriber discovery, **Long-Form Videos (16:9 Widescreen)** constitute the core equity, brand reputation, and monetization foundation of a YouTube channel:
1. **The 4,000 Watch Hours Engine:** Meeting the primary YouTube Partner Program (YPP) milestone requires 4,000 valid public watch hours. A single 10-to-15 minute contemplative prayer video with 30,000 views at a 65% completion rate generates over **3,250 watch hours**.
2. **Premium AdSense Economics (RPM):** Long-form videos allow mid-roll ad insertions (on videos $\ge 8\text{ minutes}$), multiplying revenue per viewer by 2.5x to 4x compared to non-midroll videos. Devotional content targeting Tier 1 markets (US, UK, CA, AU) commands **$8.00 to $16.00 CPM** and **$4.50 to $9.50 RPM**.
3. **Evergreen Search & Recommendation Life Cycle:** Long-form videos remain active in YouTube search and suggested feeds for 3 to 7+ years, generating steady compound viewership long after publication.

To maximize reach and prevent demonetization, this guide documents the **thinnest technical and operational details** for uploading long-form videos both **programmatically via the YouTube Data API v3** and **manually via the YouTube Studio web dashboard**.

---

## 2. YouTube Account Verification & Feature Tiers: The 15-Minute Gate

Before a channel can successfully publish long-form content, it must unlock YouTube's feature verification tiers. Uploading a video longer than 15 minutes to an unverified channel results in an immediate upload rejection error (`uploadLimitExceeded: Video is too long`).

```
                              YOUTUBE FEATURE TIERS
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        ▼                               ▼                               ▼
     TIER 1                          TIER 2                          TIER 3
  STANDARD FEATURES           INTERMEDIATE FEATURES             ADVANCED FEATURES
  • Videos up to 15 min       • Videos OVER 15 minutes         • >10 daily uploads
  • Auto-generated thumbs       (up to 12 hrs / 256 GB)        • Clickable links in desc
  • Standard upload limits    • Custom thumbnail upload        • Pin comments
  • Instant upon creation     • Live streaming unlocked        • Content ID appeals
                              • Phone SMS/Call verification    • Video ID / History
```

### 2.1 The Three Feature Tiers Explained

| Feature Tier | Duration & File Limit | Custom Thumbnails? | Requirements / Verification Method | Impact on Long-Form Publishing |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Standard Features** | Max 15 minutes; Max 2 GB | **NO** (Only 3 auto-picked frames) | Default on any new Google account | **INSUFFICIENT:** Blocks long-form documentaries and custom high-CTR thumbnails. |
| **Tier 2: Intermediate Features** | **Up to 12 Hours or 256 GB** | **YES** (`thumbnails.set` enabled) | One-time Phone Number SMS or Voice OTP verification in YouTube Studio Settings | **MANDATORY:** Unlocks videos $> 15\text{ minutes}$ and custom 16:9 studio thumbnails. |
| **Tier 3: Advanced Features** | Unlimited daily upload volume | **YES** | Video verification (1-min smartphone selfie), Valid Government ID, or 2 months channel history | Unlocks external hyperlinks in descriptions, pinned comments, and Content ID appeals. |

### 2.2 How to Verify Intermediate Features (One-Time Setup)
1. Log into **YouTube Studio** (`studio.youtube.com`).
2. Navigate to **Settings** (gear icon in lower-left sidebar) $\rightarrow$ **Channel** $\rightarrow$ **Feature eligibility**.
3. Locate **Intermediate features** and click **Verify phone number**.
4. Select country, enter mobile number, and submit the 6-digit SMS verification code. Status updates instantly to **Enabled**.

---

## 3. Video & Audio Encoding Specifications: Bit-by-Bit Ingestion Standards

Uploading unoptimized video leads to multi-hour transcode delays, color banding, washed-out blacks, and volume throttling. To guarantee pristine playback across mobile, 4K Smart TVs, and desktop monitors, videos must adhere to YouTube's exact ingestion matrix.

### 3.1 Container & Video Stream Specifications

```
┌────────────────────────────────────────────────────────────────────────┐
│                     MASTER VIDEO ENCODING MATRIX                       │
├───────────────────────┬────────────────────────────────────────────────┤
│ Container             │ MP4 (MPEG-4 Part 14) or MOV                    │
│ Header Atom           │ FastStart Enabled (`-movflags +faststart`)     │
│ Video Codec           │ H.264 (AVC) or ProRes 422 HQ                   │
│ Profile / Level       │ High Profile, Level 4.2 / 5.1                  │
│ Color Space           │ Rec. 709 (BT.709), Standard YUV 4:2:0          │
│ Pixel Aspect Ratio    │ 1:1 (Square Pixels)                            │
│ Frame Rate            │ 24.0 fps (Cinematic standard), Constant FPS    │
│ GOP Structure         │ Closed GOP; Keyframe every 12 frames (0.5 sec) │
│ Target Bitrate (1080p)│ 10,000 – 12,000 kbps (VBR 2-pass or CRF 18-20) │
│ Target Bitrate (1440p)│ 16,000 – 24,000 kbps (Forces VP9 transcode)    │
│ Target Bitrate (4K)   │ 35,000 – 45,000 kbps                           │
└───────────────────────┴────────────────────────────────────────────────┘
```

#### Why FastStart (`-movflags +faststart`) is Essential
By default, standard video encoders place the `moov` atom (the index table containing chunk offsets and duration metadata) at the very end of the file.
- **The Problem:** YouTube’s ingestion servers cannot begin processing or validating the video until the entire file has uploaded.
- **The Solution:** Passing `-movflags +faststart` shifts the `moov` atom to the very beginning of the MP4 file. YouTube's servers start decoding, generating proxy streams, and running copyright checks simultaneously while remaining bytes are uploading.

#### The 1440p Transcode Hack
YouTube uses three distinct video codecs for viewer playback:
1. **AVC1 (H.264):** Assigned by default to standard 1080p uploads on small/new channels. It exhibits visible artifacting in dark gradients and fine text.
2. **VP9 (`vp09`):** Higher efficiency codec assigned to popular videos and videos with resolutions $\ge 1440\text{p}$.
3. **AV1 (`av01`):** Next-generation compression offering maximum sharpness at minimal bitrates.
- **Pro Producer Technique:** Rendering long-form prayer documentaries at **2560×1440 (1440p QHD)** forces YouTube’s ingestion pipeline to allocate **VP9 / AV1** transcoding immediately upon upload, ensuring crystal-clear sapphire typography even when viewers watch at 1080p.

---

### 3.2 Audio Standards: The -14 LUFS Loudness Penalty

```
┌────────────────────────────────────────────────────────────────────────┐
│                     MASTER AUDIO ENCODING MATRIX                       │
├───────────────────────┬────────────────────────────────────────────────┤
│ Audio Codec           │ AAC-LC (Advanced Audio Coding Low Complexity)  │
│ Channels              │ Stereo (2.0) or 5.1 Surround                   │
│ Sample Rate           │ 48,000 Hz (48 kHz)                             │
│ Audio Bitrate         │ 384 kbps (Stereo) / 512 kbps (5.1)             │
│ Target Loudness       │ -14.0 LUFS Integrated (±1.0 LUFS)               │
│ Maximum True Peak     │ -1.0 dBTP (Decibels True Peak)                 │
│ Loudness Range (LRA)  │ 9 to 12 LU (Comfortable dynamic range)         │
└───────────────────────┴────────────────────────────────────────────────┘
```

#### Understanding YouTube's Loudness Normalization
YouTube applies automated loudness normalization to prevent sudden volume spikes across videos:
- **If your audio is too loud (-10 LUFS):** YouTube's player turns down your audio volume slider by 4.0 dB (visible in *Stats for Nerds* as `Normalized 63% (content loudness +4.0dB)`). This introduces digital gain reduction and squashes dynamic punch.
- **If your audio is too quiet (-22 LUFS):** YouTube **DOES NOT** turn up the volume! Viewers on mobile phones will struggle to hear the prayer, assume poor production quality, and swipe away.
- **The Gold Standard:** Master voiceover and procedural music to exactly **-14.0 LUFS integrated** with **-1.0 dBTP true peak**.

#### FFmpeg Production Loudness Command
```bash
ffmpeg -i input_master.wav -af "loudnorm=I=-14:LRA=11:TP=-1.0" -c:a aac -b:a 384k -ar 48000 output_normalized.m4a
```

---

## 4. YouTube Data API v3 Programmatic Upload Protocol

For automated production pipelines, uploading is handled programmatically via the **YouTube Data API v3**. Because video files are large binary payloads, YouTube does not permit standard single-part POST requests for production video files.

### 4.1 The Resumable Upload Protocol (`uploadType=resumable`)
The resumable upload protocol executes in three distinct phases:

```
                       RESUMABLE UPLOAD PROTOCOL
                                   │
                                   ▼
                   PHASE 1: METADATA HANDSHAKE
      POST /upload/youtube/v3/videos?uploadType=resumable
      • Sends snippet (title, desc, tags) and status (privacy)
      • Headers: X-Upload-Content-Length, X-Upload-Content-Type
      • Server returns: 200 OK + Location: {upload_session_uri}
                                   │
                                   ▼
                   PHASE 2: CHUNKED DATA TRANSFER
      PUT {upload_session_uri}
      • Sends video binary in 8 MiB (8,388,608 bytes) chunks
      • Headers: Content-Range: bytes 0-8388607/52428800
      • Server returns: 308 Resume Incomplete after each chunk
      • Server returns: 200/201 Created on final chunk
                                   │
                                   ▼
                   PHASE 3: NETWORK FAULT RECOVERY
      If socket disconnects during transmission:
      • Send empty PUT with Content-Range: bytes */{total_bytes}
      • Server returns 308 + Range: bytes=0-{last_received_byte}
      • Pipeline resumes from last_received_byte + 1
```

### 4.2 API Quota Allocation & Daily Budgeting

YouTube Data API projects are assigned a default daily quota of **10,000 units**:

| API Call / Operation | Quota Cost per Call | Description |
| :--- | :--- | :--- |
| `videos.insert` | **1,600 units** | Uploading the video binary and metadata payload. |
| `thumbnails.set` | **50 units** | Uploading and attaching a custom 16:9 thumbnail. |
| `playlistItems.insert` | **50 units** | Adding the uploaded video to a curated channel playlist. |
| `videos.update` | **50 units** | Updating title, description, or category post-upload. |
| `videos.list` / `channels.list` | **1 unit** | Querying video status, upload processing state, or channel details. |

#### Maximum Upload Capacity per Rolling 24 Hours
- Total cost per complete video package:
  $$\text{Cost} = 1600\ (\text{video}) + 50\ (\text{thumbnail}) + 50\ (\text{playlist}) = 1,700\text{ units}$$
- Maximum uploads per day:
  $$\lfloor 10,000 / 1,700 \rfloor = \mathbf{5\text{ complete long-form uploads per day}}$$
- **Quota Reset Window:** Daily quota resets at **midnight Pacific Time (08:00 UTC)**.
- **Quota Exceeded Error Handling:** When quota runs out, the API returns HTTP 403 `quotaExceeded`. The codebase in `pipeline/upload.py` intercepts this error, computes the exact seconds remaining until 08:00 UTC, and safely pauses production.

---

### 4.3 OAuth 2.0 Security Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        OAUTH 2.0 TOKEN FLOW                            │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Developer Console: Create "OAuth Client ID" (Type: Web / Desktop)  │
│ 2. Scopes: `https://www.googleapis.com/auth/youtube.upload`           │
│           `https://www.googleapis.com/auth/youtube.readonly`          │
│ 3. One-Time Minting: User authorizes channel access in browser         │
│ 4. Google Auth Server returns:                                         │
│    • Short-lived Access Token (Expires in 3,600 seconds)               │
│    • Long-lived Refresh Token (Stored securely in GitHub Secrets)      │
│ 5. Pipeline execution: Refresh token exchanged automatically for       │
│    ephemeral Bearer token on every upload run                          │
└────────────────────────────────────────────────────────────────────────┘
```

#### Why Service Accounts Cannot Directly Upload to YouTube
A common developer pitfall is attempting to use a Google Cloud Service Account (`@project.iam.gserviceaccount.com`). Service accounts do not own YouTube channels and cannot upload to consumer or brand accounts without enterprise Google Workspace / CMS domain delegation. Long-form automated pipelines **must use User OAuth 2.0 credentials with a refresh token**.

---

## 5. YouTube Studio High-Touch Manual Upload Workflow

For flagship documentary releases, uploading manually through the **YouTube Studio Dashboard** (`studio.youtube.com`) ensures meticulous control over metadata, ad suitability self-certification, and 1080p transcode completion.

### Step 1: Initiating File Upload
1. Open [studio.youtube.com](https://studio.youtube.com).
2. Click **Create** (top-right camera icon) $\rightarrow$ **Upload videos**.
3. Drag and drop the master file (`deep-dive-psalm91.mp4`).
4. While the file uploads in the background, complete the 4 workflow tabs: **Details**, **Video elements**, **Checks**, and **Visibility**.

---

### Step 2: Details & Metadata Optimization (The 5 Pillars)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE 5 METADATA PILLARS                          │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Title: Front-loaded emotional hook + scripture reference            │
│ 2. Description: 3-tier structure (hook, timestamps, transparency)      │
│ 3. Thumbnail: 16:9 native plate with duration safe-zone cleared        │
│ 4. Playlists: Added to auto-play thematic sleep & prayer series        │
│ 5. Audience: Marked "Not Made for Kids" (COPPA compliance)             │
└────────────────────────────────────────────────────────────────────────┘
```

#### Pillar 1: High-CTR Title Engineering (Max 100 Characters)
- **Mobile Cut-Off Rule:** On smartphones, titles truncate after **55 to 65 characters**. Essential keywords and emotional hooks must appear in the first 50 characters.
- **Proven Faith & Prayer Formula:**
  `[Emotional Hook / Urgent Promise] | [Scripture Passage] ([Context / Meditation])`
- **Recommended Titles for Psalm 91 Master:**
  - *Option A:* `PRAY THIS BEFORE YOU SLEEP | Psalm 91 Prayer of Divine Protection (Sleep Meditation)` (88 chars)
  - *Option B:* `NO EVIL SHALL BEFALL YOU | Psalm 91 Night Prayer for Peace & Healing` (71 chars)
  - *Option C:* `PSALM 91: PRAYER BEFORE SLEEP | Rest Under His Wings Tonight` (60 chars)

---

#### Pillar 2: Description Architecture (The 3-Zone Blueprint)

```text
[ZONE 1: THE ABOVE-THE-FOLD HOOK — FIRST 150 CHARACTERS]
Before you sleep tonight, pray Psalm 91 over your life, your home, and your family. Experience the deep peace of God and rest under the shadow of the Almighty.

[ZONE 2: CLICKABLE INTERACTIVE CHAPTERS / TIMESTAMPS]
00:00 — Introduction: The Secret Place of the Most High
02:15 — Psalm 91:1–2: He Is My Refuge and Fortress
05:30 — Deliverance From the Snare and Peril
08:45 — Under His Wings: Divine Shield of Truth
12:10 — Psalm 91:10: No Evil Shall Befall You
15:40 — Angelic Protection Over All Your Ways
19:15 — The Promise of Salvation and Long Life
22:00 — Closing Night Prayer & Peaceful Sleep Blessing

[ZONE 3: THEOLOGICAL CONTEXT, SCRIPTURE TEXT & TRANSPARENCY]
📖 Scripture Reference: Psalm 91 (KJV / WEB)
🕊️ Channel Mission: The Secret Place is a sacred digital sanctuary providing daily Christian prayer, bedtime scripture meditation, and biblical encouragement.

🙏 PRAYER FOCUS TONIGHT:
If you are carrying anxiety, fear, or spiritual heaviness, play this meditation as you rest. Claim God's promise that no weapon formed against you shall prosper.

🔔 Subscribe to join our prayer family: https://youtube.com/@TheSecretPlace?sub_confirmation=1
💬 Leave your prayer requests in the comments below so our community can agree with you in prayer.

—
Production Transparency & Editorial Disclosure:
Scripture commentary, narrative structure, and devotional synthesis authored by The Secret Place editorial studio. Visual motion graphics and acoustic harmonic soundscapes created using in-house procedural DSP and digital motion design tools under human editorial direction.
#Psalm91 #NightPrayer #ChristianMeditation #PrayerBeforeSleep #TheSecretPlace
```

#### The Rules of YouTube Chapter Timestamps
To activate automated chapter divisions on the video timeline:
1. The first timestamp **MUST begin at `00:00` or `0:00`**.
2. There must be at least **3 distinct chapters** listed in ascending chronological order.
3. Each chapter must be at least **10 seconds in duration**.
4. Each line must follow the format `mm:ss - Chapter Title` or `hh:mm:ss - Chapter Title`.

---

#### Pillar 3: Thumbnail Upload
- Click **Upload thumbnail**.
- Select `docs/media/psalm-91-longform-thumbnail.jpg` (Native 16:9, 1280×720, under 2 MB).
- **Safe Zone Verification:** Confirm that no headline text enters the lower-right $280\times 120\text{px}$ quadrant, ensuring the black YouTube duration stamp does not obscure words.

#### Pillar 4: Playlist Assignment
- Click **Playlists** $\rightarrow$ select or create *"Prayers of Protection & Peace"*.
- Creating thematic series increases **Session Watch Time** by up to 240% as YouTube automatically queues subsequent videos.

#### Pillar 5: Audience Declaration (COPPA Compliance)
- Select: **No, it's not made for kids**.
- *Warning:* Selecting "Yes, it's made for kids" disables personalized ads, disables comments, removes notification bells, and reduces RPM by up to 80%.

---

### Step 3: Video Elements (End Screens & Cards)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   STANDARD END SCREEN LAYOUT (LAST 20s)                │
├───────────────────────────────────┬────────────────────────────────────┤
│ [VIDEO: BEST FOR VIEWER]          │ [PLAYLIST: PSALM MEDITATIONS]      │
│ (Dynamic AI recommendation)       │ (Keeps viewer in channel ecosystem)│
│                                   │                                    │
│                 [SUBSCRIBE: CHANNEL WATERMARK]                         │
│                 (Circular channel avatar badge)                        │
└───────────────────────────────────┴────────────────────────────────────┘
```

1. **Subtitles / Closed Captions:**
   - Click **Add** $\rightarrow$ **Upload file** $\rightarrow$ select formatted `.srt` or `.vtt` file.
   - *Algorithmic Impact:* YouTube indexes every word in uploaded caption files for Google & YouTube search queries.
2. **End Screens (Active during final 20 seconds):**
   - Click **Add** $\rightarrow$ Choose template:
     - 1 Video element: Set to *"Best for viewer"*.
     - 1 Playlist element: Set to *"Night Prayers & Devotionals"*.
     - 1 Subscribe element: Displays channel avatar.
3. **Cards (Info Cards):**
   - Add up to 5 interactive teaser cards placed at natural viewer retention drop-off inflection points (e.g. at minute 5:30 linking to related morning prayer).

---

### Step 4: Verification Checks & Self-Certification

1. **Copyright Check:** YouTube runs an automated Content ID scan against its audio and video database. Because our score is procedurally synthesized via Python (`tools/score.py`) and our plates are ledger-cleared (`image-search/LICENSES.yml`), the check will display a clean green checkmark: *"No issues found."*
2. **Ad Suitability (Monetization Self-Certification):**
   - Answer the 10 standard brand safety questions (Inappropriate language, Adult content, Violence, Shocking content, etc.).
   - Faith, scripture, and peaceful meditation receive a flawless rating, qualifying for the **unrestricted Green Dollar Icon**.

---

### Step 5: Visibility & The "Unlisted Staging" Strategy

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE "UNLISTED STAGING" TIMELINE                      │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ T = 0 Hours       │ T + 2 to 4 Hours  │ T + 4 Hours                    │
├───────────────────┼───────────────────┼────────────────────────────────┤
│ Upload as         │ • SD Transcode ✅  │ Set to PUBLIC                  │
│ UNLISTED          │ • 1080p HD ✅     │ • Algorithmic push begins      │
│                   │ • Content ID ✅   │ • Early viewers see crisp 1080p│
│                   │ • Green Icon ✅   │ • Max retention velocity       │
└───────────────────┴───────────────────┴────────────────────────────────┘
```

#### The Rookie Mistake: Publishing Immediately
When an upload reaches 100%, YouTube has only finished encoding the low-resolution **360p Standard Definition (SD)** stream.
- If you publish immediately, your most dedicated subscribers who click the notification in the first 10 minutes will see a pixelated 360p video.
- Many assume poor production quality and bounce within 15 seconds, dragging down your Average View Duration (AVD) and permanently crippling the video's algorithmic trajectory.

#### The Professional Publishing Procedure
1. Set visibility to **Unlisted** (or schedule for 4 hours in advance).
2. Wait until YouTube Studio displays: *"Checks complete. HD processing finished."*
3. Verify that the **Green Dollar Icon** is confirmed.
4. Switch visibility to **Public** at your target audience's peak browsing hour.

---

## 6. Algorithmic Velocity: The First 48 Hours

The first 48 hours determine whether YouTube's recommendation engine expands a video from subscriber notifications to the broader **Suggested Videos** and **Browse Features (Home)** feeds.

```
                          RECOMMENDATION FLYWHEEL
                                     │
                                     ▼
                      PHASE 1: CANDIDATE GENERATION
         • Algorithm filters millions of videos down to hundreds
         • Triggered by title keywords, tags, and category embeddings
                                     │
                                     ▼
                        PHASE 2: CANDIDATE RANKING
         • Scored by: Predicted CTR × Predicted Watch Time
                                     │
                                     ▼
                       PHASE 3: AUDIENCE EXPANSION
         • If CTR > 8% and APV > 55% across early viewers:
         • Algorithm tests video on broader Lookalike Audiences
```

### 6.1 The Pinned Comment Community Flywheel
Immediately upon setting the video to Public:
1. Post a thoughtful, open-ended devotional reflection in the comments:
   > *"Heavenly Father, we invite Your peace into every home watching this video tonight. Where in your life do you need God's divine shield? Leave your prayer request below so our community can pray with you."*
2. Click the three dots $\rightarrow$ **Pin comment**.
3. **The 60-Minute Engagement Sprint:** Respond to the first 20 to 30 comments with a heart and a short personalized reply. This sends notification pings back to viewers, inviting them to re-enter the video discussion and accelerating comment velocity.

---

## 7. Master Production & Upload Checklist: "The Secret Place"

Follow this checklist before releasing `deep-dive-psalm91.mp4`:

### Phase 1: File & Asset Verification
- [x] **Video Render:** `docs/media/deep-dive-psalm91.mp4` verified at 1280×720 (16:9), 24fps, H.264 High Profile, with FastStart atom.
- [x] **Audio Master:** Integrated loudness verified at **-14.0 LUFS (±1.0)** with **-1.0 dBTP true peak**.
- [x] **Thumbnail Master:** `docs/media/psalm-91-longform-thumbnail.jpg` verified at 1280×720 (16:9), under 2 MB, duration safe-zone cleared.
- [x] **Licensing Ledger:** All scenes confirmed `status: cleared` in `image-search/LICENSES.yml` (`tests/test_licence_ledger.py` passes 100%).
- [x] **Content ID Clearance:** Background score verified as 100% procedural DSP synthesis (`tools/score.py`); zero external stock samples.

### Phase 2: Metadata Staging
- [x] **Title Locked:** `PRAY THIS BEFORE YOU SLEEP | Psalm 91 Prayer of Divine Protection (Sleep Meditation)` (88 chars).
- [x] **Description Prepared:** 3-zone structure containing above-the-fold hook, 8 formatted chapter timestamps starting at `00:00`, scripture text, and transparency disclosure footer.
- [x] **Category:** Set to **Education (27)** or **People & Blogs / Inspiration**.
- [x] **COPPA Status:** Declared **Not Made for Kids**.

### Phase 3: Ingestion & Release
- [ ] **Staging Upload:** Upload file as **Unlisted**.
- [ ] **Transcode Inspection:** Confirm 1080p HD processing badge in YouTube Studio.
- [ ] **Copyright Check:** Confirm *"Checks complete. No issues found."*
- [ ] **Monetization Self-Certification:** Submit ad suitability form; confirm Green Dollar Icon.
- [ ] **Video Elements:** Attach End Screen (Best for viewer + Psalm playlist + Subscribe) and pin interactive Card.
- [ ] **Public Launch:** Switch visibility to **Public** at optimal evening meditation hour (7:00 PM EST).
- [ ] **Community Engagement:** Post and pin community prayer question; reply to initial viewer comments within 60 minutes.
