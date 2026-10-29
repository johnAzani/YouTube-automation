# YouTube Channel Analytics: Master Access, Operations & Coverage Guide

**Channel Identity:** *The Secret Place* (`@TheSecretPlace`) — Sacred Scripture, Devotional Prayer & Bedtime Contemplation  
**Live Public Release:** Video ID `7RDX0fbIOtQ` — *Psalm 91: Night Prayer of Divine Protection*  
**Codebase Collectors:** `scripts/metrics_snapshot.py`, `scripts/channel_analytics.py`, `scripts/view_analytics.py`  
**Automated CI/CD Workflow:** `.github/workflows/metrics.yml`

---

## 1. Executive Summary: The Analytics Hierarchy

To get access to **all** analytics, it is critical to understand the technical boundary between **YouTube Studio Web / Mobile** and the **YouTube Analytics API v2**:

```
                               YOUTUBE ANALYTICS HIERARCHY
                                            │
        ┌───────────────────────────────────┴───────────────────────────────────┐
        ▼                                                                       ▼
   TIER 1: YOUTUBE STUDIO CONSOLE                                  TIER 2: PROGRAMMATIC APIS
   (Direct Web & Mobile Dashboard)                              (Automated Data & CI/CD Pipelines)
   • 100% of all platform metrics                               • Scalable JSON reports & CSV tracking
   • Live real-time 48h & 60m velocity                          • Data API v3: Public views, likes, subs
   • Thumbnail Impressions & CTR (Exclusive!)                   • Analytics API v2: Daily, traffic, countries
   • Audience retention curves (Second-by-second)               • Safe offline archival & automated runs
   • Returning vs New viewers & demographics                    • Privacy-isolated (mode 0600, gitignored)
```

> **Crucial Platform Rule:** YouTube's backend **DOES NOT expose Thumbnail Impressions or Impressions Click-Through Rate (CTR) through the YouTube Analytics API v2**. These two vital distribution metrics are strictly reserved for the **YouTube Studio Web / Mobile UI** and manual Studio CSV exports.

---

## 2. Direct Live Access via YouTube Studio

The fastest and most complete way to view 100% of all real-time metrics, impressions, CTR, and retention curves is directly inside YouTube Studio.

### 2.1 Direct URLs for "The Secret Place" & Video `7RDX0fbIOtQ`

| Analytics Destination | Direct YouTube Studio URL | Key Metrics Displayed |
| :--- | :--- | :--- |
| **Entire Channel Analytics** | [studio.youtube.com/channel/analytics](https://studio.youtube.com) | Channel views, total watch hours, subscriber velocity, top videos. |
| **Video `7RDX0fbIOtQ` Overview** | [studio.youtube.com/video/7RDX0fbIOtQ/analytics](https://studio.youtube.com/video/7RDX0fbIOtQ/analytics) | Live real-time 48-hr & 60-min views, watch time, subscriber delta. |
| **Reach & Distribution (CTR)** | [studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-reach](https://studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-reach) | **Impressions**, **Impressions CTR**, traffic sources (Browse, Suggested, Search). |
| **Engagement & Retention** | [studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-engagement](https://studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-engagement) | **Average View Duration (AVD)**, **Audience Retention Curve** (dips, spikes). |
| **Audience Demographics** | [studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-audience](https://studio.youtube.com/video/7RDX0fbIOtQ/analytics/tab-audience) | Returning vs New viewers, top countries (US, UK, CA), age & gender. |
| **Video Editor & Captions** | [studio.youtube.com/video/7RDX0fbIOtQ/edit](https://studio.youtube.com/video/7RDX0fbIOtQ/edit) | End screens, cards, chapters, closed captions, and tags. |

### 2.2 The 4 Core Analytics Tabs in Studio Explained

```
┌────────────────────────────────────────────────────────────────────────┐
│                      THE 4 STUDIO ANALYTICS TABS                       │
├───────────────────┬────────────────────────────────────────────────────┤
│ 1. OVERVIEW       │ Real-time view bar chart (last 48 hours & 60 min)  │
│                   │ Total public watch hours towards 4,000 YPP goal    │
│                   │ Subscriber count change driven by this upload      │
├───────────────────┼────────────────────────────────────────────────────┤
│ 2. CONTENT/REACH  │ IMPRESSIONS: Total times thumbnail was served      │
│                   │ IMPRESSIONS CTR: % of viewers who clicked          │
│                   │ TRAFFIC SOURCES: Browse, Suggested, Search, Shorts │
│                   │ TOP SEARCH TERMS: Exact phrases viewers typed      │
├───────────────────┼────────────────────────────────────────────────────┤
│ 3. ENGAGEMENT     │ AVERAGE VIEW DURATION (AVD): e.g. 2m 45s           │
│                   │ AVERAGE PERCENTAGE VIEWED (APV): e.g. 68%          │
│                   │ RETENTION CURVE: Graph from 00:00 to video end     │
├───────────────────┼────────────────────────────────────────────────────┤
│ 4. AUDIENCE       │ RETURNING VS NEW: Core loyalty indicator           │
│                   │ "WHEN YOUR VIEWERS ARE ON YOUTUBE": Purple heatmap │
│                   │ SUBSCRIBER WATCH TIME: % subscribed vs unsubscribed│
│                   │ GEOGRAPHY: Tier-1 US/UK/CA viewer concentrations   │
└───────────────────┴────────────────────────────────────────────────────┘
```

### 2.3 Identifying Optimal Publishing Times in the Audience Tab
Under the **Audience** tab (`studio.youtube.com/channel/analytics/tab-audience`), locate the 7-day $\times$ 24-hour purple chart **"When your viewers are on YouTube"**.
- The darkest purple cells indicate peak viewer activity (typically 20:00–23:00 local viewer time in the faith/prayer niche).
- **Algorithmic Rule:** Schedule automated long-form uploads **3 to 4 hours before** the darkest purple block begins (14:14 UTC / 10:14 AM EST) to allow full 1080p VP9 transcoding and caption indexing before peak traffic arrives.
- For complete chronobiological and timezone analysis, see [docs/BEST_TIME_TO_POST.md](BEST_TIME_TO_POST.md).


---

## 3. Platform Boundary: API Coverage vs Studio Exclusives

To avoid false assumptions about what code can collect, this matrix documents exact field availability:

| Metric Category | Specific Metrics | YouTube Studio Web | Programmatic API Path | Known Boundary / Caveat |
| :--- | :--- | :---: | :---: | :--- |
| **Public Video Counts** | Views, Likes, Comments | ✅ Yes | `scripts/metrics_snapshot.py` | Top 50 public videos; unlisted/private excluded. |
| **Subscribers** | Current total subscriber count | ✅ Yes | `scripts/metrics_snapshot.py` | YouTube rounds public count to 3 significant figures. |
| **Daily Channel Totals** | Daily views, watch minutes, AVD, sub gains/losses | ✅ Yes | `scripts/channel_analytics.py` (`daily`) | Requires `yt-analytics.readonly` OAuth scope. |
| **Video Breakdown** | Per-video views, watch time, AVD, APV | ✅ Yes | `scripts/channel_analytics.py` (`videos`) | Paginated safely; excludes unreleased drafts. |
| **Traffic Sources** | Traffic breakdown by source type | ✅ Yes | `scripts/channel_analytics.py` (`traffic_sources`) | Categories (Browse, Suggested, Search); not individual URLs. |
| **Geographies** | Country breakdown by views & watch time | ✅ Yes | `scripts/channel_analytics.py` (`countries`) | Small countries under threshold withheld by Google. |
| **Device Types** | Mobile, TV, Desktop, Tablet, Console | ✅ Yes | `scripts/channel_analytics.py` (`devices`) | High accuracy across mobile and smart TV apps. |
| **Audience Demographics** | Age groups, Gender breakdown | ✅ Yes | `scripts/channel_analytics.py` (`demographics`) | Minimum view threshold required before Google populates. |
| **Audience Retention** | Second-by-second watch ratio curve | ✅ Yes | `scripts/channel_analytics.py` (`--retention-video`) | Per-video query (`elapsedVideoTimeRatio`). |
| **Best Time to Post** | **"When your viewers are on YouTube" Hourly Heatmap** | ✅ **YES** | ❌ **API BLOCKED** | **Studio Exclusive:** API v2 only supports daily dimension (`day`), not hourly. See `docs/BEST_TIME_TO_POST.md` for our empirical lead-time schedule. |
| **Estimated Revenue** | Estimated ad revenue, playback RPM | ✅ Yes | `scripts/channel_analytics.py` (`--revenue`) | Requires `yt-analytics-monetary.readonly`; estimated, not AdSense payout. |
| **Impressions & CTR** | **Thumbnail Impressions & Click-Through Rate** | ✅ **YES** | ❌ **API BLOCKED** | **Studio Exclusive:** YouTube API v2 does not expose CTR. Export via Studio CSV if needed. |
| **New vs Returning** | Unique & returning viewer counts | ✅ **YES** | ❌ **API BLOCKED** | Studio Exclusive: Audience cohort graph in Studio. |
| **Copyright & Checks** | Content ID claims, strikes, ad suitability | ✅ **YES** | ❌ **API BLOCKED** | Studio Exclusive: Checked on video details tab. |

---

## 4. Automated Public Metrics Snapshot (Zero-Setup CI/CD)

The repository includes a fully automated public metrics collector running on **GitHub Actions** (`.github/workflows/metrics.yml`).

### 4.1 How It Works
1. Runs automatically every **Friday at 18:41 UTC** (end of week snapshot).
2. Uses the existing YouTube Data API credentials (`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`).
3. Queries channel statistics and up to 50 public videos.
4. Generates a rolling 30-day snapshot in `content/metrics.csv` and `content/channel-metrics.json`.
5. Uploads a 30-day zip artifact to the GitHub Actions run summary.

### 4.2 Triggering It On-Demand in GitHub Actions
1. Go to your repository on GitHub: `https://github.com/johnAzani/YouTube-automation`.
2. Click the **Actions** tab.
3. In the left sidebar, click **Weekly metrics snapshot**.
4. Click **Run workflow** $\rightarrow$ select branch `main` $\rightarrow$ click green **Run workflow** button.
5. In ~25 seconds, the run completes and generates the artifact.

### 4.3 Running It Locally
```bash
python scripts/metrics_snapshot.py
```
Outputs:
- `content/channel-metrics.json`: Public subscriber count and channel metadata.
- `content/metrics.csv`: Snapshot of views, likes, and comments across all public uploads.

---

## 5. Private YouTube Analytics API v2 Collector

For deep private reports (daily performance, traffic sources, geography, devices, retention curves, and revenue), use `scripts/channel_analytics.py`.

### 5.1 One-Time Setup Instructions

#### Step 1: Enable YouTube Analytics API in Google Cloud
1. Open [Google Cloud Console](https://console.cloud.google.com).
2. Select your YouTube automation project.
3. Navigate to **APIs & Services** $\rightarrow$ **Library**.
4. Search for **YouTube Analytics API** and click **Enable**.

#### Step 2: Mint a Read-Only Analytics OAuth Token
Run the local minting tool on your computer (never run in public CI):
```bash
python scripts/youtube_oauth.py --client-secret client_secret.json --purpose analytics
```
*(If you want revenue estimates as well, use `--purpose analytics-revenue`).*
A browser window opens asking you to authorize read-only analytics access for your YouTube channel.

The script prints:
- `ANALYTICS_CLIENT_ID`
- `ANALYTICS_CLIENT_SECRET`
- `ANALYTICS_REFRESH_TOKEN`

#### Step 3: Export Credentials in Your Environment
```bash
export ANALYTICS_CLIENT_ID="your-client-id"
export ANALYTICS_CLIENT_SECRET="your-client-secret"
export ANALYTICS_REFRESH_TOKEN="your-refresh-token"
```

#### Step 4: Run the Analytics Collector
```bash
# Standard 28-day channel report:
python scripts/channel_analytics.py --start 2026-10-01 --end 2026-10-28

# Deep retention curve for public video 7RDX0fbIOtQ:
python scripts/channel_analytics.py --start 2026-10-01 --end 2026-10-28 --retention-video 7RDX0fbIOtQ

# Include revenue estimates:
python scripts/channel_analytics.py --start 2026-10-01 --end 2026-10-28 --revenue
```

#### Step 5: View the Formatted Report
To display the collected data in clean ASCII tables:
```bash
python scripts/view_analytics.py
```

Outputs formatted tables for:
- Daily Performance (views, watch minutes, AVD, subscriber gains/losses)
- Top Videos ranked by watch time
- Traffic Source percentages
- Top Geographies and audience countries
- Device Distribution (Mobile vs TV vs Desktop)
- Second-by-second Audience Retention curve

---

## 6. Interpreting Devotional & Prayer Channel Benchmarks

When evaluating analytics for *The Secret Place*, use these proven niche benchmarks:

```
┌────────────────────────────────────────────────────────────────────────┐
│                  FAITH & PRAYER BENCHMARK SCORECARD                    │
├─────────────────────────┬───────────────────┬──────────────────────────┤
│ Metric                  │ Target Benchmark  │ Optimization Action      │
├─────────────────────────┼───────────────────┼──────────────────────────┤
│ Impressions CTR         │ 7.0% – 12.0%      │ High CTR = Urgent hook;  │
│ (Thumbnail + Title)     │                   │ Low CTR (<5%) = Rework   │
│                         │                   │ thumbnail text/contrast  │
├─────────────────────────┼───────────────────┼──────────────────────────┤
│ Average View Duration   │ >55% (Long-form)  │ High AVD triggers browse │
│ (APV / Retention)       │ >75% (Shorts)     │ recommendations          │
├─────────────────────────┼───────────────────┼──────────────────────────┤
│ Retention at 00:30      │ >70% of viewers   │ Hook must establish      │
│ (The 30-Second Cliff)   │ still watching    │ holy stillness quickly   │
├─────────────────────────┼───────────────────┼──────────────────────────┤
│ Primary Traffic Source  │ Browse / Suggested│ Healthy evergreen sign;  │
│ (After First 72 Hours)  │ (Combined >60%)   │ YouTube is promoting it  │
├─────────────────────────┼───────────────────┼──────────────────────────┤
│ Audience Geography      │ US / UK / CA / AU │ Maximizes premium Tier-1 │
│                         │ (>65% of views)   │ RPM ($6.00 – $14.00)     │
└─────────────────────────┴───────────────────┴──────────────────────────┘
```

---

## 7. Security, Privacy & $0.00 Cost Guarantee

1. **Zero Cost Invariant ($0.00):** Both YouTube Data API v3 and YouTube Analytics API v2 are **100% free** under Google Cloud's standard developer tier. No billing account or credit card is ever required.
2. **Privacy Isolation:** Private analytics reports generated by `scripts/channel_analytics.py` are saved strictly under gitignored `output/private-analytics/report.json` with POSIX permissions `0600` (read/write only by owner). They are never committed to git, uploaded to public CI, or exposed in logs.
3. **Read-Only Scope:** The analytics OAuth token is strictly read-only (`yt-analytics.readonly`). It carries zero upload or edit permissions, protecting channel integrity.
