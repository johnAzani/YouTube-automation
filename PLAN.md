# YouTube Automation Master Plan — ₦0 Budget, GitHub Actions Powered

> **Planning update — 2026-10-23:** The newer
> [finance niche research](docs/FINANCE_NICHE_RESEARCH_2026-10-23.md) supersedes
> income expectations as decision assumptions: this plan's earnings/milestone dates,
> per-niche rates and exact deadline/application interpretations are not guarantees
> or verified channel forecasts. Measure actual channel data, time and costs first.
> Start with a capped pilot; do not spend or rush uploads to meet an income promise.

**Status:** living document · **Started:** 2026-10-18 · **Branch:** `main`
*(moved off the session branch `arena/79365da2-youtube-automation` on 2026-10-20 — see MAINTENANCE.md)*

---

## 0. TL;DR (read this first)

1. **Yes, GitHub Actions works — better than you think.** A **public** repo gets **free, unlimited**
   standard runners (4-core Linux, 16 GB RAM). That is your entire compute bill: **₦0 / $0**. ffmpeg
   rendering, TTS, stock-footage fetching and even YouTube uploads can all run inside scheduled
   workflows. This repo is the studio.
2. **"Millions of dollars monthly" is not a plan — it is a lottery ticket.** The math is in §5:
   $1M/month at a realistic $10 RPM needs **~100 million monetized views per month** (MrBeast-class).
   What *is* plannable: **$0 → first AdSense dollar in ~4–8 months → $1K–$10K/mo in 12–24 months**,
   then scale with a channel portfolio + affiliates + products. We will build for the plan, not the
   lottery.
3. **There is a hard deadline: 1 Feb 2027.** YouTube is doubling YPP entry requirements for new
   applicants (4,000 → **8,000** watch hours / 10M → **20M** Shorts views). If we apply *before*
   that date, the old bar applies. Today is **18 Oct 2026** — we have **~3.5 months** to get
   1,000 subs + 4,000 watch hours and submit the YPP application. Every schedule in this plan is
   built around that cliff.
4. **The real risk is not tooling — it is demonetization.** YouTube's "inauthentic content" policy
   (the old "repetitious content" rule, renamed 15 Jul 2025, clarified 16 Jul 2026) explicitly
   targets mass-produced/template AI video. In January 2026 YouTube terminated 16 channels
   (~35M subscribers, ~4.7B lifetime views) in one sweep. **Our automation must produce the grunt
   work (research packs, narration, assembly, upload) while a human owns the creative (angle,
   script, structure, final approval).** That is the difference between a monetizable channel and
   a terminated one — and it is also what makes the content actually good.
5. **Stack (all free):** GitHub Actions (public repo) · Python · ffmpeg · `edge-tts`
   (neural voices, no API key) · Pexels + Pixabay + Openverse/Wikimedia/NASA (stock visuals) ·
   YouTube Data API (free — 100 uploads/day since Jun 2026) · Gemini free tier (optional research
   assistant). Total: **$0.00/month**.

---

## 1. Honest expectations (the part most "YouTube automation" content skips)

### 1.1 What the income distribution actually looks like

| Milestone | Monthly ad revenue | What it takes |
|---|---|---|
| Months 1–3 | $0 | Pre-monetization. Library building. Typical video: 50–500 views. |
| Months 3–8 | $0 → first payout | YPP approval (1,000 subs + 4,000 hrs **before 1 Feb 2027**), then AdSense ≥ $100 threshold |
| Months 6–12 | $100 – $1,000 | 30K–100K monthly views at $3–8 RPM |
| Year 2 (solid channel) | $1,000 – $10,000 | 100K–500K monthly views, improving retention/CTR |
| Year 2–3 (portfolio) | $10,000 – $50,000 | 2–5 channels + affiliates + digital products |
| "Millions per month" | $1,000,000+ | ~100M+ monetized views/mo. Top ~50 channels on Earth. Not a first-year outcome. |

Sources: 2026 niche RPM data — finance $10–25 RPM, education/history $3–8, entertainment $1–4,
Shorts $0.03–0.10 per 1,000 views (see §7 Sources).

### 1.2 Why most "faceless automation" channels die (and how we won't)

The July 2026 policy clarification names **three categories YouTube will not monetize**:

1. **Generic, repetitive, template-based content** — near-identical videos, slideshows, the same
   script structure re-rendered with different nouns, TTS reading scraped text verbatim.
2. **Off-putting / emotionally manipulative content** — staged distress, shock-stitching.
3. **AI personas on sensitive topics** — fake AI "doctors", "financial advisors", "lawyers".

Reviewers judge the **whole channel's pattern**, not one video. Enforcement ladder: warning →
90-day demonetization → permanent removal. **Our countermeasure is structural** (§4.4):
human-written scripts with original theses, format rotation, no AI expert personas, a mandatory
pre-publish originality checklist, and modest volume (≤1 long-form/day, quality floor first).

---

## 2. Strategy

### 2.1 Niche selection (do this once, properly)

Constraints: faceless-friendly, **not** an "AI persona on sensitive topics" trap, RPM worth the
effort, evergreen search demand, producible from open-licence footage.

| Candidate | RPM (2026) | Policy risk | Footage availability | Verdict |
|---|---|---|---|---|
| History / documentary explainers | $4–8 | Low | Excellent (Wikimedia, archives, maps) | ✅ **Primary recommendation** |
| Science & technology culture | $6–11 | Low | Excellent (NASA public domain, labs, space) | ✅ Great alternative |
| Business case studies / how companies work | $8–15 | Medium (finance adjacency — keep it *documentary*, never *advice*) | Good | ✅ Highest RPM if kept non-advisory |
| Motivation / book summaries | $3–8 | Low | Good | ⚠️ Saturated, low retention ceiling |
| Scary stories TTS / sleep music / kids | $0.40–2.50 | High (slop + COPPA) | — | ❌ RPM trap — avoid |

**Pick one channel theme and one format family.** Full research: **docs/FINANCE.md** (finance-niche
deep dive, Oct 2026 — RPM data, policy minefield, affiliate/sponsor math). Recommended lane:
**money & business documentaries** — this same documentary craft aimed at finance/business subjects
("Why Enron Died", "The $6B Wirecard Fraud", "The Canal That Broke a City") — finance-grade RPM
($8–25 US audience; affiliates $50–500/referral; sponsor CPM $40–200) with documentary safety:
**no AI personas, no advice**, evergreen archives, human-approved scripts. History/tech explainers
remain the format family and the safe floor. Hard dates: **YPP application by Jan 15, 2027**
(new-applicant thresholds double Feb 1, 2027); file AdSense **W-8BEN** before first payment.

### 2.2 Format mix (feeds both growth and watch hours)

- **Long-form (8–12 min), 3×/week** — the watch-hour and RPM engine. This is what pays.
- **Shorts (30–59 s), 5–7×/week** — cut from the long-forms. The subscriber engine. Shorts views
  do **not** count toward the 4,000-hour bar, but they drive subs that convert to long-form views.
- **Thumbnails + titles are a human job** (highest-leverage CTR decision on the platform; the
  pipeline generates a *draft* thumbnail, the human swaps/edits before publish).

### 2.3 Revenue stack beyond ads (from month 6)

1. **Affiliate links** in descriptions (books, tools — Amazon Associates is free; finance/B2B
   programs pay $50–200/sale).
2. **Digital product** once audience exists (PDF deep-dives, research packs — Gumroad free tier).
2b. **Auto-dubbed languages** from month 2 — YouTube auto-dubbing (27 languages) opened to all
   creators 4 Feb 2026 and is free; it expands non-US reach at ₦0 (GROWTH.md §8).
3. **Second channel** once channel #1 is systematized and proven.
4. Ad revenue stays the floor, not the ceiling.

---

## 3. The ₦0 infrastructure — why GitHub Actions is the right call

### 3.1 Verified limits & prices (Oct 2026)

| Item | Value | Notes |
|---|---|---|
| Standard runners, **public** repos | **Free & unlimited** | ubuntu-latest = **4-core / 16 GB** on public repos (2-core/8 GB on private) |
| Private repos free quota | 2,000 min/mo, 500 MB artifacts | Only relevant if the repo goes private — don't |
| Job timeout | 6 h per job | A 10-min 1080p render is nothing |
| Concurrency (Free plan) | 20 jobs | Matrix rendering is possible if we ever need it |
| Artifact storage | 500 MB (shared w/ Packages) | **Never store videos in git** — see §3.3 |
| Cache | 10 GB per repo | Perfect for pip + stock-asset cache |
| Cron reliability | Best-effort (jobs can delay 15–30+ min under load) | Fine for content, not for SLAs |
| YouTube Data API upload | 1 unit from a **100 uploads/day** bucket (since 1 Jun 2026; was 1,600 units pre-Dec 2025) | Way more than we need |
| YouTube API cost | $0 (quota-based, no paid tier) | |
| Pexels API | Free, ~200 req/h | Commercial use OK, no attribution required |
| Pixabay API | Free, ~100 req/min | Commercial use OK |
| `edge-tts` | Free, no key (unofficial Microsoft Edge neural voices) | Have a fallback voice path — see risks §6 |
| ffmpeg | Preinstalled on ubuntu runners (`apt-get install -y ffmpeg` as insurance) | |

### 3.2 Architecture

```
                 ┌────────────────────────────────────────────────┐
                 │  GitHub repo (PUBLIC = free unlimited CI)      │
                 │                                                │
  human writes → │  content/queue/*.md  ──(status: approved)──┐   │
  & approves     │                                            ▼   │
                 │            .github/workflows/produce.yml       │
                 │            (cron 06:14 & 14:14 UTC + manual)   │
                 │                     │                          │
                 │        ┌────────────┼─────────────┐            │
                 │        ▼            ▼             ▼            │
                 │   pipeline/tts  pipeline/assets  pipeline/…    │
                 │   (edge-tts +   (Pexels/Pixabay/  (ffmpeg      │
                 │    word timing)  Wikimedia/NASA)   assemble)   │
                 │        └────────────┼─────────────┘            │
                 │                     ▼                          │
                 │        pipeline/upload.py → YouTube (draft)    │
                 │                     │                          │
                 │        GitHub Issue "release ticket" + artifact│
                 └─────────────────────┼──────────────────────────┘
                                       ▼
                        human clicks Publish in YouTube Studio
                        (or auto-publish after API audit passes)
```

### 3.3 Storage discipline (critical)

- **Git stores text only:** scripts, metadata, configs, code. Target repo size < 5 MB.
- Rendered videos live **≤ 24 h as Actions artifacts** (short `retention-days`) purely for QC,
  then die. The video itself goes straight to YouTube.
- Stock footage is fetched per-run and cached via `actions/cache` (10 GB free), never committed.

### 3.4 YouTube API audit — the one real setup delay

Since 28 Jul 2020, uploads from **unverified** GCP projects have been forced to `private`.
(Docs around this have fluctuated in Oct 2026 — some pages now say the restriction is lifted —
so we plan for both worlds:)

1. **Day 1:** create the GCP project, enable YouTube Data API, OAuth consent, submit the
   **YouTube API Services Audit & Quota Extension form**. Approval can take weeks.
2. **Until audit passes:** `upload.py` uploads as `private` and opens a **release ticket**
   (GitHub Issue with the Studio link); the human flips it to public/scheduled — 2 clicks.
3. **After audit passes:** set `AUTO_PUBLISH=true` and the pipeline goes end-to-end.

---

## 4. The pipeline (this repo)

### 4.1 Job lifecycle

```
idea (human) → draft script (human+LLM assist) → status: approved (human gate)
   → GH Actions: research-pack → TTS → visuals → assemble → thumbnail → metadata
   → upload to YouTube (private draft) → release ticket → human publishes
   → status: published + performance log
```

### 4.2 Code map

| Path | Role |
|---|---|
| `pipeline/run.py` | Orchestrator CLI: `--dry-run`, `--job <script.md>`, `--all` |
| `pipeline/script_doc.py` | Parses `content/queue/*.md` (YAML frontmatter + scene-by-scene body) |
| `pipeline/tts.py` | `edge-tts` neural narration with word boundaries → SRT captions; offline placeholder fallback |
| `pipeline/assets.py` | Pexels → Pixabay → Openverse/Wikimedia/NASA → generated title cards |
| `pipeline/assemble.py` | ffmpeg: clip montage under narration, Ken-Burns stills, caption burn (optional), audio duck |
| `pipeline/thumbnail.py` | Branded draft thumbnail (still + title plate) |
| `pipeline/upload.py` | YouTube resumable upload, thumbnail set, visibility policy, release ticket |
| `pipeline/originality.py` | The originality checklist engine (§4.4) — refuses to run on non-compliant scripts |
| `.github/workflows/produce.yml` | Scheduled production + manual dispatch |
| `.github/workflows/dry-run.yml` | CI proof on every push (no secrets needed) |

### 4.3 Script format (the human creative layer)

One markdown file per video in `content/queue/`, YAML frontmatter (title, niche, voice, status,
asset queries) + scene sections. **The body is written by a human** (LLM may draft; the human
rewrites the thesis, structure, and every scene's point of view). Example lives at
`content/queue/0001-the-canal-that-broke-a-city.md`.

### 4.4 Originality gate (our demonetization insurance)

`pipeline/originality.py` blocks the build unless the frontmatter checklist asserts:

- [ ] `original_thesis` — the video argues something specific, not a rehash of the top 10 results
- [ ] `unique_structure` — scene outline differs from the channel's last 5 videos (format rotation)
- [ ] `human_rewrite` — script was human-edited, not pasted from an LLM
- [ ] `no_ai_persona` — no fake expert on health/finance/legal/politics
- [ ] `source_notes` — at least 2 real sources cited in the description
- [ ] `ai_disclosure` — set truthfully if synthetic media is realistic enough to require it

Volume cap: **max 1 long-form + 2 Shorts per day** — enough for the Feb 2027 deadline, not enough
to look like a content farm.

---

## 5. The money math

### 5.1 Views needed (ad revenue only)

```
monthly_revenue = (monetized_views / 1000) × RPM
```

| Monthly monetized views | @ $4 RPM (history) | @ $8 (science/tech) | @ $15 (business cases) |
|---|---|---|---|
| 10,000 | $40 | $80 | $150 |
| 100,000 | $400 | $800 | $1,500 |
| 500,000 | $2,000 | $4,000 | $7,500 |
| 1,000,000 | $4,000 | $8,000 | $15,000 |
| 100,000,000 | $400,000 | $800,000 | $1,500,000 |

The "millions per month" row is the last one. That is the entire top of YouTube. Plan on the
middle rows and scale toward them; treat the last row as a tail outcome, not a target.

### 5.2 Path to the 1 Feb 2027 gate (the real "fast monetization" plan)

4,000 watch hours = 240,000 minutes. At an 8-minute average video:

- 30 long-forms × 8 min × **166 avg views each** = 4,000 hrs. Trivially achievable **if** even one
  video pops; grinding if every video gets <100 views. Hence: quality floor + Shorts feeding subs.
- Conservative scenario: month 3–5 to thresholds → apply for YPP **no later than mid-Jan 2027**.
- 500-sub fan-funding tier unlocks earlier (~month 2–3) — Super Thanks/merch money is small but
  it's the first proof of revenue before the ad gate.

### 5.3 Costs — the whole bill

| Line | Cost |
|---|---|
| GitHub Actions (public repo) | $0 |
| edge-tts / ffmpeg / Python | $0 |
| Pexels + Pixabay + Wikimedia + NASA | $0 |
| YouTube Data API | $0 |
| Gemini API free tier (optional research) | $0 |
| Google account / YouTube channel | $0 |
| **Total to start and run** | **₦0 / $0** |

Everything monetization pays for — AdSense account, wire to a Nigerian domiciliary account (GTB,
Access, Zenith, UBA, First Bank all supported via SWIFT) — also costs nothing to set up.

---

## 6. Risks & mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Demonetization under "inauthentic content" | **Critical** | Originality gate (§4.4), human scripts, format rotation, modest volume, no AI personas |
| YPP threshold doubling 1 Feb 2027 | **High** | Hard deadline: apply before Feb 2027; schedule is built backwards from it |
| OAuth "Testing" mode kills upload token every 7 days | **High** | Consent screen published to **In production** before minting the refresh token (DEEP_DIVE §1) |
| GitHub auto-disables cron after 60 days idle | **High** | `keepalive.yml`: monthly heartbeat commit + weekly workflow re-enable |
| `edge-tts` is an unofficial service (can break) | Medium | Fallback chain in `tts.py`; swap-in points for Piper (local, free) or paid TTS later |
| YouTube API audit delays public auto-publish | Medium | Private-upload + 2-click human publish until audit passes (§3.4) |
| Low-RPM audience (Nigeria-heavy) collapsing revenue | Medium | Produce in English for US/UK/CA/AU; US-afternoon publish slots (DEEP_DIVE §2.1) |
| Stock footage licence complaints | Medium | Only Pexels/Pixabay/Wikimedia/NASA/Internet Archive; licence logged per clip |
| Cron jitter in Actions | Low | 2 runs/day, idempotent queue, `concurrency` group to prevent overlap |
| Runner disk limits on big renders | Low | 720p proxies for drafts; 1080p final; artifacts deleted at 1 day |
| Single channel failure | Medium | The playbook transfers; spin channel #2 from the same infra after channel #1 hits $1K/mo |
| Reused-content strikes from "similar" ideas | Medium | `originality.py` duplicate-thesis check + human review of search results before scripting |

---

## 7. 90-day operating plan

### Phase 0 — Days 1–7 (setup week)
- [ ] Create channel (brand account), niche locked, banner/logo (Canva free), handle secured
- [ ] GCP project + OAuth + **submit YouTube API audit form** (starts the clock — §3.4)
- [ ] Pexels + Pixabay API keys → GitHub secrets
- [ ] Push this repo public (free Actions), enable workflows
- [ ] Write & approve scripts 0001–0006 (2 weeks of long-form) + 10 Shorts scripts
- [ ] Human-pass every video through the originality checklist before `status: approved`

### Phase 1 — Days 8–30 (launch & iterate)
- [ ] 3 long-form/week + 5 Shorts/week, published at fixed UTC slots (audience: skew US/EU for RPM)
- [ ] Human: thumbnail + title A/B judgment per video (the single biggest CTR lever)
- [ ] Weekly review of CTR (>4% target), avg view duration (>40% target), and iterate hooks
- [ ] Community tab + replies to every comment (algorithm + loyalty)

### Phase 2 — Days 31–60 (growth sprint)
- [ ] Double down on the best-performing format (kill what flops — data, not hope)
- [ ] Shorts volume to 1/day (clips from proven long-forms)
- [ ] Apply for YPP fan-funding tier at 500 subs (first money can land here)
- [ ] SEO pass: search-driven titles for evergreen queries in the niche

### Phase 3 — Days 61–90 (monetization gate)
- [ ] Hit **1,000 subs + 4,000 watch hours → apply for full YPP before 1 Feb 2027**
- [ ] Link AdSense (Nigerian domiciliary account ready for wire payments)
- [ ] Add first affiliate links to descriptions
- [ ] Retro: pipeline runbook → `docs/PLAYBOOK.md`; prep channel #2 concept

### KPIs we run the business on
| KPI | Target (day 90) |
|---|---|
| Long-form published | ≥ 30 |
| Subscribers | ≥ 1,000 |
| Watch hours (365d) | ≥ 4,000 |
| Avg CTR | ≥ 4% |
| Avg view duration | ≥ 40% |
| YPP application submitted | before 1 Feb 2027 |
| Cost incurred | ₦0 |

---

## 8. Sources & further reading (research log, Oct 2026)

**Fine print companions: [docs/DEEP_DIVE.md](docs/DEEP_DIVE.md)** — OAuth 7-day token trap,
GitHub's 60-day schedule auto-disable, audience-geography economics (a US view is worth
10–20× a Nigerian view), CTR/retention benchmarks, the 12-week countdown to the
1 Feb 2027 threshold change, and the Nigeria AdSense payout mechanics — and
**[docs/GROWTH.md](docs/GROWTH.md)** — the 2026 ranking model (satisfaction surveys +
session contribution), the 48-hour ritual, packaging science with the Test & Compare SOP,
the exact metadata limits, the idea-validation rubric, and the free auto-dubbing lever
(opened to all creators 4 Feb 2026).

1. YouTube channel monetization policies (official) — inauthentic content:
   https://support.google.com/youtube/answer/1311392
2. TechCrunch — "YouTube clarifies policies around AI slop and upsetting videos" (16 Jul 2026):
   https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/
3. YouTube Partner Program eligibility (official):
   https://support.google.com/youtube/answer/72851
4. YPP threshold doubling, effective 1 Feb 2027 (announced 10 Aug 2026):
   https://www.digitalmusicnews.com/2026/08/10/youtube-doubles-eligibility-requirements-partner-program/
5. Jan 2026 enforcement wave (16 channels, ~35M subs terminated):
   https://ytgrowth.io/blog/youtube-ai-policy
6. GitHub Docs — Actions limits & billing (free unlimited on public repos):
   https://docs.github.com/en/actions/reference/limits ·
   https://docs.github.com/en/billing/concepts/product-billing/github-actions
7. YouTube Data API quota calculator & revision history (100 uploads/day bucket since 1 Jun 2026):
   https://developers.google.com/youtube/data/determine_quota_cost ·
   https://developers.google.com/youtube/data/revision_history
8. videos.insert & the unverified-project private lock / audit:
   https://developers.google.com/youtube/v3/docs/videos/insert ·
   https://support.google.com/youtube/answer/7300965
9. 2026 faceless-niche RPM data:
   https://fluxnote.io/guides/faceless-channel-niche-profitability-2026 ·
   https://outlierkit.com/resources/faceless-youtube-channels/ ·
   https://youtubeniches.com/blog/best-faceless-youtube-niches-2026
10. Free TTS landscape 2026 (edge-tts etc.):
    https://freeapihub.com/blog/best-free-text-to-speech-apis
11. YouTube monetization in Nigeria (AdSense payout paths):
    https://guidescafe.ng/step-by-step-guide-to-set-up-youtube-monetization-in-nigeria-including-tax-implications-and-compliance/
12. Pexels API (free, commercial use): https://www.pexels.com/api/ · Pixabay API:
    https://pixabay.com/service/about/api/

---

*This plan is deliberately honest about odds and rules. The way to "millions" runs through years of
compounding: first a channel that earns $1K/mo, then $10K/mo, then a portfolio. The ₦0 GitHub
Actions studio removes every excuse for not starting today.*
