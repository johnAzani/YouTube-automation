# GROWTH FEEDBACK LOOP — closing the loop, activating the dormant engines (2026-11-04)

**Scope:** a line-by-line audit of what the automation actually runs, the one growth
lever that was missing entirely, and the dormant-but-tested engines that were built
and never wired. Everything here is **fully automated** and **$0.00/month** — no paid
tier, no new secret, no manual gate. Where a lever genuinely cannot be automated
(YouTube has no public API for it), this document says so plainly instead of faking it.

**The honest frame:** nothing here *guarantees* results. What it guarantees is that the
channel stops publishing blind and starts compounding: every release is measured, the
next release is steered by what worked, finished videos chain into the next one, and
the search surface keeps widening — all without a human in the loop and without spend.

---

## 1. What the audit found (wired vs. dormant)

The repo has ~20 growth modules. Most were **built and unit-tested but never referenced
by any workflow** — dormant engines. The audit traced every module to the workflows that
call it.

### Already wired (before this change)
| Lever | Where it runs |
|---|---|
| es/pt metadata localization | `upload.py` → `localize_metadata` |
| English captions (long-form) | `upload.py` → `captions` |
| Single playlist insert (`CONFIG.playlist_id`) | `upload.py:299` |
| Pinned comment (AMEN + Selar links) | `upload.py` → `pinned_comments` |
| 3-concept thumbnail packs + chapters | `prayer_pipeline` → `thumbnail_ctr`/`thumbnail_studio` |
| Shorts bridge | `short_release` → `shorts_bridge` |
| Live thumbnail sync + metadata retrofit | `monitor.yml` |
| Scripture roadmap authoring + auto-scheduler | `gemini_brain.yml` |
| Weekly public metrics snapshot | `metrics.yml` → `metrics_snapshot` |

### Dormant (0 workflow references) — the gap
`studio_autopilot`, `manage_playlists`/`playlists`, `end_screens`, `dark_screen`,
`thumbnail_tester`, `seo_suggest`, `video_seo_enhancer`, `sonic_branding`,
`celebrate_milestone`/`milestones`, `build_sleep_compilation`/`sleep_compilations`,
`tools/build_podcast_feed`, `channel_analytics`/`view_analytics`.

### The one lever that was missing entirely
**There was no closed feedback loop.** `GeminiBrain.select_next_scripture()` walked a
*static* `SCRIPTURE_ROADMAP` in fixed order and never read which videos actually
performed. The brain authored blind. `metrics.yml` collected views/likes/comments every
week and threw them into a short-lived artifact that nothing ever read. The channel
could not double down on what worked. **This is the highest-leverage gap, and it is now
closed.**

---

## 2. What was built

### 2.1 Closed-loop performance feedback (the keystone)
- **`pipeline/performance_feedback.py`** + **`scripts/performance_feedback.py`**.
- Reads the public metrics snapshot (`content/metrics.csv`, produced by
  `metrics_snapshot`) + the published receipts, collapses to the latest reading per
  video, and scores each long-form video on two axes:
  - **Reach** — view velocity = `views / age_days`, gated to videos ≥ 3 days old (a video
    published this morning would otherwise show an absurd views/day from 3 views).
  - **Satisfaction** — engagement rate = `(likes + comments) / views`, gated to videos
    with ≥ 25 lifetime views (1 like on 2 views is 50% but meaningless).
  - Score = `0.5 · normalised_velocity + 0.5 · normalised_engagement`, normalised across
    the measured long-form cohort. **Shorts are a separate lane** (their discovery engine
    is different) and never steer long-form selection.
- Aggregates by **theme** (protection / peace-rest / stillness-refuge / light-courage /
  trust-surrender / anxiety-peace / blessing) using a scripture-first classifier. Scripture
  references match on a digit boundary so "Psalm 4" cannot accidentally match "Psalm 46".
- **Confidence gate:** fewer than 3 measured long-form videos → a neutral
  `insufficient_data` report; the brain keeps its roadmap order. It never steers on noise.
- Writes **`content/research/performance_feedback.json`** — **derived-only**: theme ranks,
  average scores, measured-video counts, and plain-language guidance. **No raw view counts,
  no video IDs, no per-video metrics table.** The raw snapshot stays an Actions artifact.
- **Fail-soft everywhere:** missing snapshot, malformed artifact, or too little data all
  degrade to "keep roadmap order", never block authoring.

### 2.2 The brain now reads the feedback
`GeminiBrain.select_next_scripture()` — the **sole choke point** both authoring paths use
(`supply.ensure_supply` and `scripts/gemini_brain.py`) — now ranks eligible roadmap
candidates through `rank_candidates()` in three bands:
1. themes scoring **at/above** the measured average → front (best first);
2. themes with **no** measured score → keep their roadmap place (middle);
3. themes scoring **below** the average → back (deprioritised).

With insufficient data the order is unchanged. A missing/corrupt artifact is caught and
logged, never fatal. Backward-compatible: the existing selection test still passes.

### 2.3 Growth autopilot workflow (activates the dormant engines)
**`.github/workflows/growth-autopilot.yml`** — daily **02:14 UTC = 03:14 Nigeria time**,
before the 03:14 UTC brain so the freshest feedback is committed before authoring reads it:
1. `metrics_snapshot` — public stats + **live subscriber count** (fail-soft);
2. `performance_feedback` — compute + write the derived artifact;
3. `manage_playlists` — **series-playlist autoplay sync** (session watch-time);
4. `celebrate_milestone` — renders the Community card + pastoral copy from the **live** count.

Each engine is fail-soft (`continue-on-error`); one failing never blocks the others. The
commit step copies the proven `monitor.yml` pattern — `git fetch` + `reset --mixed` (never
`pull --rebase`, which conflicted five times on the 2 Nov release), stages **only** the
derived feedback JSON, `[skip ci]`. Raw metrics + the milestone card upload as 30-day
artifacts, never committed. Uses the **same** `YOUTUBE_*` secrets already configured.

### 2.4 Series playlists — session watch-time (dormant → live)
`playlists.sync_all_series_playlists` groups published videos into autoplay series
(Night Prayers / Bedtime Sleep / Complete Psalms). Fully **idempotent**: it searches for an
existing playlist by title before creating, and skips a video already present. When a
viewer finishes one prayer, the next autoplays — the lever that multiplies watch-hours per
viewer and moves the 4,000-hour YPP goal. Cost after the first sync is near-zero (only new
videos are inserted, 50 units each).

### 2.5 Milestone celebration — live count (dormant → live)
`scripts/celebrate_milestone.py` no longer defaults to a hardcoded `1230`. With no `--subs`
it reads the live count from `content/channel-metrics.json` (written by the snapshot in the
same job) and **skips rather than guesses** if unavailable. Renders the 1080² card + copy
for the Community Tab. (Posting to the Community Tab itself is Studio-only — see §4.)

### 2.6 SEO tag enrichment (dormant → live)
`metadata.build_tags` now folds in the `seo_suggest` high-intent taxonomy — the pain-point
and search queries distressed/sleepless viewers actually type ("bible verses for sleeping",
"christian meditation for sleep", "bedtime prayer against fear"). Every candidate still
passes through `fit_youtube_tags`, which enforces the **500-char quote-aware budget, the
18-tag cap, and the 432 Hz gate** — so this is strictly additive and cannot break the tag
contract. Verified on a live queued script: 18 tags, cost 470, no "432".

### 2.7 Dynamic next-job recommendation
`scripts/continuous_research.py` hardcoded `next_job = SCRIPTURE_ROADMAP[1]` (Psalm 23 —
already published). It now reuses the brain's feedback-aware selection (lazy import to avoid
the circular dependency), so the intelligence briefing recommends a scripture that is
actually next, not a stale guess.

### 2.8 Privacy hardening
`content/metrics.csv` was **not** gitignored — raw API metrics could have been committed to
this public repo. It is now gitignored alongside `channel-metrics.json`. Only the derived,
aggregate feedback artifact is committed.

**Tests:** 25 new (feedback engine + brain-steering integration), 2 existing tests updated
to reflect the intentional behavior changes, and the scheduler-supervisor tests made robust
to new workflows (a `pad_history` helper so a newly-added cron never becomes an accidental
candidate). **Full suite: 734 passed + 1632 subtests, 0 failed.**

---

## 3. Research findings that shaped the design (2026)

### 3.1 The algorithm rewards satisfaction + session contribution, not raw watch time
2026 consensus: ranking weights **viewer satisfaction** (formalized ~May 2026) and
**session contribution** — does this video lead to more watching? Shorts and long-form rank
on **separate engines**. Repeat/return viewing is rewarded. This is exactly why the feedback
loop blends engagement (satisfaction) with reach, why playlists (session chains) matter, and
why Shorts are scored in a separate lane. CTR benchmark 5–10%; first-30s retention > 70%.
*(Secondary/blog sources: milx.app, weaveaura.studio, biolinky.co, yt-seo-architect.)*

### 3.2 Sleep/ambience grows on habit + session time, not virality
A well-positioned multi-hour mix can out-earn dozens of standard videos; 8–10h sleep formats
win; transitions must be smooth; "boring is the product." Hybrid sleep-paced narration + a
content niche builds a compounding evergreen catalog. Playlists by duration/purpose and
timestamps in descriptions help. **But** low-effort reused loops are a monetization risk
(§3.4) — which is why the ambient-only compilation is *not* auto-published (§5).
*(outlierkit.com Sep 2026, fluxnote.io Mar 2026, tunepocket.com Jul 2026.)*

### 3.3 What the APIs can and cannot measure
- **Analytics API v2** `dimensions=video` supports views, estimatedMinutesWatched,
  averageViewDuration, **averageViewPercentage**, subscribersGained, likes, comments, shares,
  and `annotationClickThroughRate` (end-screen/card CTR). `dimensions=insightTrafficSourceType`
  gives traffic sources.
- **Per-video impressions / thumbnail CTR are NOT available** via targeted Analytics queries —
  they are **bulk Reporting API only**. `impressions`/`impressionsCtr` are **channel-level only**
  (`ids=channel==MINE`, no dimensions); adding `dimensions=video` returns HTTP 400. So the
  feedback loop uses **public Data API view velocity + engagement as the proxy** and never
  fabricates a thumbnail CTR. `annotationClickThroughRate` is end-screen/card CTR, **not**
  thumbnail CTR.
- Analytics needs the `yt-analytics.readonly` scope, which the **upload token does not have**
  (it has `youtube.upload` + `youtube.readonly` + `force-ssl`). Enrichment would need a one-time
  `python scripts/youtube_oauth.py --purpose analytics` + `ANALYTICS_*` secrets. The loop is
  built to work **without** it (public metrics only) and could be enriched later, fail-soft.
*(developers.google.com/youtube/reporting, tarka.ai, benly.ai, ytdetective.com, Stack Overflow
48792678/49686802.)*

### 3.4 Monetization policy — why "more" is not always "better"
On 2025-07-15 "repetitious content" was renamed **inauthentic content**: mass-produced,
templated, interchangeable videos (incl. generic AI templates) are disallowed. A separate
**reused content** rule requires significant added value. Judged at the **channel** level;
reapply ~30–90 days. Disallowed examples: image slideshows / scrolling text with minimal
narrative, compilations with little narrative, near-duplicate re-uploads. This is the reason
the static-plate ambient compilation is deliberately **not** auto-published.
*(vidiq, lilachbullock, shapelessai, kompozy, outlierkit.)*

### 3.5 Watch-hours rules (the YPP gap)
Full YPP: **4,000 public watch hours / 365 days + 1,000 subs** (early tier 3,000h + 500).
**Shorts-feed watch time does NOT count** (Shorts path is 10M views/90d; early 3M). Private /
unlisted / deleted videos are excluded; only long-form > 60s counts. The channel is past the
subscriber gate (~1,230) — the gap is watch-hours, which is why playlists (session chains) and
making more of what works are the priority levers.
*(TubeBuddy, top4smm, smmnut.)*

### 3.6 Data API quota (the $0 lock is safe)
Free **10,000 general units/day**; since Jun 2026 `videos.insert` has its own bucket
(100/day, 1 unit). Costs: `playlistItems.insert` 50, `playlists.insert` 50, `videos.update` 50,
`thumbnails.set` 50, `commentThreads.insert` 50, `captions.insert` 400, `*.list` 1. Resets
midnight Pacific. The growth autopilot's daily footprint is tiny: ~12 `videos.list` units +
idempotent playlist inserts (near-zero after the first sync). Nowhere near any limit.
*(upload-post.com, postzen.dev, official playlistItems.insert doc.)*

---

## 4. What cannot be automated (honest limits — no public API)

These are **Studio-only**. The automation stages everything it can and never claims to have
posted what it cannot:
- **Community Tab posts** — no Data API endpoint. `community.yml` stages a READY pack; the
  milestone card is rendered + staged, not auto-posted.
- **End screens & cards** — no public API (Google issue tracker: "Won't Fix / Intended
  behavior"). Automatable substitute = burn a slate into the video + playlists + pinned comment.
- **Test & Compare (native thumbnail/title A/B)** — Studio-only. `thumbnail_tester` produces
  variants; the actual test is run in Studio.
- **Shorts related-video link** and the **podcast-playlist flag** — Studio-only.
- **Per-video thumbnail impressions/CTR** — bulk Reporting API only (§3.3).

The end-screen outro renderer (`end_screens.render_endscreen_video`) is also kept **off**: it
renders 1920×1080 while the main render is 1280×720, so concatenation would need a re-encode on
the hot render path — not worth the risk for a slate that playlists + pinned comment already cover.

---

## 5. What was deliberately NOT auto-published (and the safe path forward)

### 5.1 Multi-hour sleep compilations
`render_sleep_compilation_video` produces a **static sanctuary plate + a 432 Hz tone/rain bed
with no narration**. Two problems:
1. **Policy:** a static image + ambient tone for an hour is the "minimal narrative" pattern
   YouTube flags as inauthentic (§3.4). Auto-publishing it risks the whole channel's YPP review.
2. **Memory:** `synthesize_sleep_bed` allocates whole-duration float64 stereo arrays —
   ~2.5 GB at 1h, ~7.6 GB at 3h, ~20 GB at 8h, plus intermediates → OOM on a runner. The test
   suite only renders a 1.0s preview, so this is untested at length.

**Safe path forward (not done here):** chunked/streaming WAV synthesis (bounded memory) **and**
a real narration library to mix in (only one prayer MP3 is committed; produce narration MP3s are
CI artifacts, never persisted). Until both exist, compilations stay a manual/preview tool.

### 5.2 Podcast RSS auto-grow
A valid podcast feed needs **hosted per-episode audio enclosures**. `tools/build_podcast_feed.py`
currently points four static episodes at committed `assets/deepdive/*.mp3`. New prayer narration
MP3s are CI artifacts, never hosted, so regenerating the feed would emit broken enclosure URLs.
Auto-grow is blocked until there is $0 hosting for per-episode audio (or the MP3s are committed,
which conflicts with the keep-artifacts-out-of-git rule). Deprioritized rather than shipping a
broken feed. The existing test hard-asserts `len(items) == len(CANONICAL_EPISODES)`, so any
receipt-based generation must be an opt-in flag, never the default.

---

## 6. Cost & safety ledger

| Item | Cost | New secret? | Manual step? |
|---|---|---|---|
| Performance feedback loop | $0 (public Data API, already-collected stats) | No | No |
| Growth autopilot workflow | $0 (same upload token) | No | No |
| Series playlist sync | $0 (idempotent, ~0 units after first sync) | No | No |
| Milestone celebration | $0 (renders locally) | No | Card staged; Community post is Studio-only |
| SEO tag enrichment | $0 (local taxonomy) | No | No |
| Dynamic next-job | $0 | No | No |

**Invariants respected:** $0.00 hard lock (fail-closed on quota); voice locked to Gemini TTS
Charon free tier; DOCOGA REELS v2 sapphire visuals; persona "The Secret Place" only; Nigeria
time (WAT, UTC+1) everywhere; no manual review gate added to the website; raw API metrics never
committed to the public repo.

---

## 7. Sources (research log)
- developers.google.com/youtube/reporting — Reach reports are bulk Reporting API only.
- tarka.ai/playbook/fundamentals/youtube-analytics-api; benly.ai/learn/dimensions-metrics —
  Analytics v2 per-video metrics/dimensions; impressions channel-level only.
- ytdetective.com/blog/youtube-analytics-metrics-explained — CTR benchmark 2–10%; view-count
  change 2026-08-24; YPP uses engaged views.
- milx.app; weaveaura.studio; biolinky.co; yt-seo-architect — 2026 algorithm consensus
  (satisfaction, session contribution, separate Shorts/long-form engines).
- outlierkit.com/resources/youtube-music-channel-growth-strategy (Sep 2026); fluxnote.io
  meditation guide (Mar 2026); tunepocket.com (Jul 2026) — sleep/ambience growth mechanics.
- Stack Overflow 48792678 / 49686802; issuetracker 35166657 — end screens/cards have no public API.
- vidiq; lilachbullock; shapelessai; kompozy; outlierkit — inauthentic/reused content policy.
- TubeBuddy; top4smm; smmnut — watch-hours rules.
- upload-post.com; postzen.dev; official playlistItems.insert doc — Data API quota costs.

*All external claims are secondary/blog sources except the official Google API docs and issue
tracker; treat algorithm specifics as directional, not guarantees. Nothing here promises results.*
