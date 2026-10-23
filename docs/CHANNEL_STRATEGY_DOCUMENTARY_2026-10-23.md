> **SUPERSEDED — 23 October 2026.** The niche is decided in
> [`NICHE_DECISION_2026-10-23.md`](NICHE_DECISION_2026-10-23.md). One niche only:
> education-categorised money-collapse documentaries, 18–22 minutes, Tier-1 English.
> Every alternative discussed below is deleted. Keep this file for its evidence, not
> for its recommendations.

# Channel strategy: what your existing style actually is, and what to do with it

**Date:** 23 October 2026  
**Status:** decision memo for discussion. Supersedes the product recommendation in [`FINANCE_STRATEGY_DECISION_2026-10-23.md`](FINANCE_STRATEGY_DECISION_2026-10-23.md) after a style and competition audit. Nothing here authorizes publishing, spending, rebranding or approval changes.

**Your answers this memo is built on:** product income · US/UK/global English audience · 6–18 month horizon · keep the existing style.

---

## 1. The conflict I have to name first

You picked **product income**. I then audited your **existing style**, and the two do not fit the way I assumed.

Your channel is not a personal-finance explainer. It is a **financial-disaster documentary**:

| What the repo contains | Detail |
|---|---|
| Format | `format: longform`, `target_minutes: 9`, scene-by-scene narration |
| Voice | `en-US-ChristopherNeural` — a single consistent narrator |
| Visual method | Text plates, archival/stock imagery, captions, no face |
| Editorial stance | *"A money story, not money advice. No picks, no predictions — just the record."* |
| Current queue | Lehman (0003), LTCM (0004), Northern Rock (0005), Barings (0006) |
| Niche lock | `pipeline/run.py::_validate_finance_niche` hard-refuses anything outside finance/business |
| Research standard | A 6,028-word Lehman dossier with 22 sources and a 2,634-word claim audit |

That is a **documentary studio**, not a calculator channel. My earlier recommendation — attach a paid car-cost spreadsheet — assumed a different channel. A viewer who just watched Lehman die does not want to model their car payment. Those are two different audiences, and putting them on one channel would weaken both.

So the honest version of your choice is:

> **Keep the documentary style and make the product the research itself** — the dossier, the source pack, the extended case file.

That is a coherent product. It is also the only one that grows out of what the studio already makes.

---

## 2. Discovery one: your niche is being flooded right now, by channels that look exactly like you

I searched the four stories in your queue. What I found on Northern Rock is the most important thing in this memo.

**Northern Rock search results, 23 October 2026:**

| Channel | Video | Length | Views | Age | Tell |
|---|---|---:|---:|---|---|
| Scandal | Northern Rock: The Bank that Brought Back the Bank Run | 22:55 | **17K** | 10 months | — |
| GoneUnder | Northern Rock: The Bank Run That Shocked Britain | 8:09 | — | **58 days** | Description states *"This film uses AI-generated imagery for some scenes"* |
| Empire Archive | Northern Rock: £1 Billion Gone in 24 Hours | 10:58 | — | **71 days** | Hashtag-stuffed description; template chapters ("The Morning the Money Ran") |
| OpenLearn (OU) | The First Domino: Northern Rock | 5:09 | 26K | 15 years | — |
| patchy media | Newsnight report, 17 Sept 2007 | 25:09 | 2.9K | 9 years | — |

Two brand-new channels, 58 and 71 days old, are publishing AI-assisted Northern Rock documentaries **in the exact format this repo produces**. In the Greensill search, a channel called *Follow The Dots* had posted a 7:37 Greensill explainer **three hours earlier**. In the Nickel Squeeze search, *Tradonomics* — 73 days old — had a 14:33 version.

Three consequences:

1. **Demand is real.** People do not build channels for topics nobody watches.
2. **The format is commoditising fast.** The pipeline's output — narration over text plates and stock imagery — is now the cheap, default product in this niche.
3. **This is precisely what YouTube's July 2026 policy targets.** Template format, high upload cadence, synthetic narration, no visible human author. The January 2026 wave removed 16 channels with 35M combined subscribers and 4.7B lifetime views. A channel that looks like *Empire Archive* is one review away from demonetisation.

**So this is not a niche you can enter by being adequate.** Being adequate is now free and everywhere. You have to be visibly different within the first ten seconds.

---

## 3. Discovery two: your current slate is aimed at the most saturated stories in the niche

| Your script | What already exists | Views |
|---|---|---:|
| 0006 Barings / Nick Leeson | ColdFusion — *How a 28 Year Old Man Destroyed England's Oldest Bank* (22:53) | **4.2M** |
| 0006 Barings | BBC documentary reupload | 481K |
| 0006 Barings | Technically Money (14:56, 3 years old) | 17K |
| 0003 Lehman | Moconomy — *The Collapse of Lehman Brothers* (46:22) | **1.1M** |
| 0003 Lehman | Gravitas — *Inside Lehman Brothers* (full film) | 94K |
| 0003 Lehman | FRONTLINE — *Breaking the Bank* (54:19) | **1.8M** |
| 0004 LTCM | Hamish Hodder — *The Most Dangerous Hedge Fund in History* (28:47, 11 months) | **1.0M** |
| 0004 LTCM | The Capital Files (21:16, 12 months) | 512 |
| 0005 Northern Rock | Scandal (22:55, 10 months) | 17K |

Read that table carefully, because it contains both the opportunity and the warning.

- The **million-view versions belong to established brands** — ColdFusion, FRONTLINE, Hamish Hodder, Moconomy. They win on trust and production value, not on the story being unknown.
- The **new entrants on the same stories get 512 and 17K views.** The Capital Files made a 21-minute LTCM documentary twelve months ago and has 512 views. That is what "adequate" earns.
- **A 9-minute text-plate Barings video is a weaker version of a 4.2M-view video that already exists.** That is the single worst use of a ₦0 studio: competing head-on, on a famous story, against the best-produced version, with less production.

**This is the finding that should change the content plan.** Not the niche — the *story selection*.

---

## 4. Discovery three: length is the biggest lever you are not using

This is the most actionable number in the whole research set.

Documentary retention benchmarks (2026, multiple sources): 45–55% at 8–12 minutes, 35–45% at 15–30 minutes, 25–35% at 30–60 minutes. Using the midpoint of each band:

| Length | Retention | AVD | Views for 4,000 h | Views for 8,000 h | Hours from 12 videos × 5,000 views |
|---:|---:|---:|---:|---:|---:|
| 9 min (current) | 50% | 4.5 min | 53,333 | **106,667** | 4,500 |
| 12 min | 47.5% | 5.7 min | 42,105 | 84,211 | 5,700 |
| 15 min | 45% | 6.75 min | 35,556 | 71,111 | 6,750 |
| **18 min** | 42.5% | **7.65 min** | 31,373 | **62,745** | **7,650** |
| 20 min | 40% | 8.0 min | 30,000 | 60,000 | 8,000 |
| 30 min | 35% | 10.5 min | 22,857 | 45,714 | 10,500 |
| 45 min | 30% | 13.5 min | 17,778 | 35,556 | 13,500 |

Three things fall out of this:

**a) Going from 9 to 20 minutes cuts the views you need for monetization by 44%.** At 9 minutes you need 106,667 views to clear 8,000 hours. At 20 minutes you need 60,000.

**b) It is the difference between failing and passing on a realistic slate.** Twelve videos averaging 5,000 views each:

- At 9 minutes: **4,500 hours** — fails the 8,000-hour bar.
- At 18 minutes: **7,650 hours** — just short.
- At 20 minutes: **8,000 hours** — passes exactly.

At 9 minutes, twelve videos at 5,000 views each do **not** get you monetized. At 20 minutes, the same twelve videos do. That is the entire argument for longer documentaries, in one line.

**c) Every minute past eight adds mid-roll inventory.** The current 9-minute target clears the 8-minute threshold by one minute, which is the minimum, not the optimum.

**The caveat, stated plainly:** this arithmetic assumes retention holds. A 20-minute video that people abandon at minute three earns less than a tight 9-minute one. Length only pays when the material sustains it. That is a writing problem, not a runtime setting — and it is why the current scripts should be *expanded with substance*, not padded.

**The cost:** 20 minutes at this narration pace (~144 words per minute) is roughly **2,900 words** of script, versus 1,294 today. That is more than double the writing per video. The 6-hour-per-video pilot budget in the earlier plan is not realistic for this format; 9–10 hours is. I would rather raise the budget honestly than pretend.

---

## 5. What the comparables actually earn

| Channel | Subs | Videos | Total views | Recent velocity | Estimate |
|---|---:|---:|---:|---|---|
| ColdFusion | 5.25M | 587 | 578M | ~40K–1M/day | Ad estimates range **$6.3K to $11.9K/mo** across trackers — a 2× spread on the same channel |
| Modern MBA | 823K | 82 | 62.5M | ~1.08M / 28d | **~$6.8K/mo** ad estimate |
| MagnatesMedia | 1.86M | 255 | 194M | ~13K–30K/day | Founder says **>$1M from AdSense alone**, plus a **$997 course** and a paid community |
| Business Casual | 1.1M | 91 | 103M | **inactive ~3 years** | $4K–$20K/mo estimated |
| Wall Street Millennial | — | — | — | — | 17–22 min explainers, 129K–222K on individual videos |

Two lessons that matter more than the numbers:

**Lesson one: the closest format match quit.** Business Casual has 1.1M subscribers, 91 videos, and averages 1.1M views per video — better ratios than almost anyone. Its last upload was roughly three years ago. It also spent 2021–2022 suing YouTube and lost. A documentary channel can be excellent and still stop. Nobody publishes why, but the pattern is common: the format is expensive in attention, and there is no compounding without uploads.

**Lesson two: the money that scales is not ads.** MagnatesMedia's founder reports more than $1M from AdSense across 255 videos and seven years — impressive, but his *product* is a $997 course sold to people who want to build channels like his. That is the honest shape of the documentary business: **the audience pays for the method, not for the topic.**

Which brings us to your product.

---

## 6. The product truth for a documentary audience

Here is the uncomfortable arithmetic. A documentary audience is an **entertainment-and-education** audience. They came for a story. They are not shopping.

What actually converts:

| Product type | Evidence | Realistic timing |
|---|---|---|
| **Membership** (early access, extended cuts, source packs) | AIR Media-Tech: a documentary channel at ~450K subs earned ~**$10K/mo** vs a fitness channel at the same size earning ~**$1K/mo**; a smaller documentary channel took **78.7% of its $959.79** monthly revenue from memberships | After 10–20 videos and a recognisable method |
| **Research dossiers** (the case file behind each video) | No public benchmark exists. This is a hypothesis. | Immediately testable, small volume |
| **A course on the method** | MagnatesMedia's $997 course; claimed $135K/mo community (secondary source, unverified) | Only after you have succeeded publicly |
| **Sponsorship** | Finance CPM $30–$60; documentary/business sponsorships are the second leg | 10K+ subscribers |
| **Ads** | Education & Science median RPM **$10.22** — the highest measured niche, 4.4× the all-niche median of $2.30 | Needs volume |

**Membership math, at $5/month:**

| Members | Gross | YouTube (70%) | Patreon (~87%) |
|---:|---:|---:|---:|
| 200 | $1,000 | $700 | $870 |
| 400 | $2,000 | $1,400 | $1,740 |
| 1,000 | $5,000 | $3,500 | $4,350 |

At a typical 1% conversion, 200 members needs about 20,000 subscribers. That is a year-two outcome, not a month-three one.

**The conclusion I have to give you:** a documentary channel cannot sell a product before it has an audience, and it cannot build an audience faster than 12–24 months. If product income means "money in the first six months," this vehicle cannot deliver it. If it means "a second, higher-margin revenue line once the channel works," it can — and the dossier is the right product because it already exists in your repo.

---

## 7. The recommendation

Keep the style. Change the story selection, the length, and the product framing.

> **Build "case files" — mechanism documentaries reconstructed from primary documents, 18–22 minutes, where the paid product is the dossier behind the video.**

Call it whatever you like; the shape is:

**a) Mechanism over biography.** Do not retell famous collapses. Take stories where the *machinery* failed — the plumbing, the accounting, the collateral — and show how it broke. Barings has been told 4.2 million times; the mechanics of how one clerk's error account escaped detection for three years has not.

**b) Receipts on screen.** Every claim shows its document: the examiner's report page, the filing, the court order, the central bank statement. This is the one thing AI-slop channels cannot fake, and it is what your repo already does better than most — 22 sources and a claim audit for one video. **This is your defensibility.**

**c) 18–22 minutes.** Per the table above, this is worth roughly 40% of the views you would otherwise need.

**d) The product is the dossier.** Each video ships with a paid case file: the sources, the timeline, the numbers, the documents, the extended analysis. $9–$19 per file, or $7–$9/month for the archive. It is the research you are already doing, packaged. No new pipeline, no new business.

**e) One sentence of positioning:** *"Every number traced to the document."* It is a promise the competition cannot copy without doing the work.

### Why this beats the alternatives

| Option | Why not |
|---|---|
| Keep the current slate at 9 min | Direct competition with 1–4M-view versions of the same stories; 12 videos × 5,000 views fails the 8,000-hour bar |
| Switch to money-math explainers with a calculator | Abandons your style and your existing research pipeline |
| Chase viral collapses (SVB, FTX) | ColdFusion, WSJ and FRONTLINE already own those; new entrants get hundreds of views |
| Volume play with AI imagery | Exactly the pattern YouTube demonetised in January 2026 |
| Ads-only | At $10.22 RPM you need roughly 1M views/month for $10K; that is a team business |

### The three-story slate I would test

| # | Story | Why it passes the gate | Competition |
|---|---|---|---|
| 1 | **The Nickel Squeeze (LME, March 2022)** — the exchange cancelled $12bn of trades in a day | Pure mechanism: margin calls, off-exchange shorts, a market operator's power to press undo. Genuinely under-covered. | Patrick Boyle 222K (20:34); Coin Bureau 227K (23:15) |
| 2 | **The LDI gilt crisis (UK, September 2022)** — pension funds forced the Bank of England to buy bonds | The least-told systemic story of the decade. Perfect for a Tier-1 UK audience. | Almost nothing at explainer quality |
| 3 | **Greensill** — supply-chain finance, insurance and one man's access | Mechanism-rich, documents-rich, and the story is still resolving. | Wall Street Millennial 129K (17:38); ABC 45:08 901K; Patrick Boyle 222K (18:25) |

These are all "how the machine broke" stories. They fit the existing voice, they fit the existing research method, they are 18–22 minutes of real material, and none of them requires beating ColdFusion at his own game.

**And the fourth, kept because it is already written:** Barings — but reframed from "the rogue trader" (4.2M views elsewhere) to **"the account that nobody checked for three years."** Same research, different question, no head-on collision.

---

## 8. The realistic 12-month picture

| Month | What happens | Honest expectation |
|---|---|---|
| 1–2 | Build the first case file; expand to 18–22 min; publish | 100–1,000 views |
| 3–4 | Three videos; test the dossier as a paid product | 200–3,000 views/video; 0–20 dossier sales |
| 5–8 | Six videos; find the one story that travels | 1,000–20,000 views on a breakout |
| 9–12 | Ten to twelve videos; apply to YPP | 8,000 hours if average ≥5,000 views/video at 20 min |

**Revenue at the end of year one, if it works:** $100–$1,500/month, mostly from dossiers and the first sponsors, with ads a rounding error until well past 100,000 monthly views.

**Revenue at the end of year two, if it compounds:** $1,000–$6,000/month across ads, sponsors and membership.

**The failure mode is not "no demand."** It is stopping at video four, or producing twelve adequate videos that look like the 58-day-old AI channels.

---

## 9. What I need you to decide

1. **Do you accept 18–22 minutes per video**, knowing it roughly doubles the writing per video and raises the per-video budget from 6 to ~9 hours?
2. **Do you accept dropping the three famous stories** (Lehman, LTCM, Northern Rock) from the launch slate, or at least re-sequencing them behind the three mechanism stories?
3. **Do you want the dossier as the product**, or would you rather defer products entirely until the channel has 10,000 subscribers and simply build for ads and sponsors?
4. **Which is the first case file** — nickel, LDI, or Greensill?

I recommend: yes to 18–22 minutes · yes to re-sequencing · dossier yes but built *after* video one proves the research is readable · nickel first.

---

## 10. What would change this recommendation

- **If the first three videos average under 500 views**, the problem is not length or topic — it is packaging and hook. Stop producing and fix thumbnails and openings.
- **If retention at 20 minutes lands under 30%**, the writing cannot sustain length; drop to 12–14 minutes and accept the higher view requirement.
- **If nobody downloads a free sample of a dossier**, nobody will buy one. Kill the product line.
- **If YouTube flags the channel as inauthentic**, stop and audit. Do not reupload.
- **If a competitor with a real brand covers the same mechanism story**, pick a different mechanism. Never compete on the same story with less production.

---

## 11. Sources for this memo

Checked 23 October 2026.

1. AIR Media-Tech, *State of YouTube Monetization 2026* — 300 channels, 3,595 channel-months, May 2025–May 2026; median RPM $2.30; Education & Science $10.22; Business & Finance $2.01 (three channels); top 10% of channels take 58% of ad revenue. https://air.io/en/air-data-findings/youtube-monetization-statistics-2026
2. AIR Media-Tech, *Why Some Channels Earn 10x More* — two ~450K channels, fitness ~$1K/mo vs documentary ~$10K/mo; membership share 78.7% of $959.79. https://air.io/en/monetization/youtube-monetization-why-some-channels-earn-10x-more-with-the-same-subscriber-count
3. vidIQ, *YouTube Subscriber Benchmarks 2026* — 61.2M channels; 1,000 subs = 40.6%; 100K = 1.3%; median channel 508 subscribers. https://vidiq.com/research/youtube-subscriber-benchmarks-2026/
4. vidIQ, time to 1,000 subscribers — 9,414 channels created after 2023; median ~16 months; 68% needed >40 videos; 31% needed 150+. https://vidiq.com/blog/post/how-to-get-your-first-1000-youtube-subscribers/
5. vidIQ, channels at 1,000 subscribers — 89% under 5,000 monthly views. https://vidiq.com/blog/post/youtube-pay-1000-subscribers/
6. Tubefilter, 13 July 2026 — YouTube's inauthentic-content categories and the "will not be allowed to monetize" language. https://www.tubefilter.com/2026/07/13/youtube-inauthentic-content-monetization-policy-update/
7. TechCrunch, 20 July 2026 — three inauthentic categories; AI personas on finance; policy rolled out 16 July. https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/
8. AIR / press coverage, January 2026 enforcement wave — 16 channels, ~35M subscribers, ~4.7B views, ~$10M annual ad revenue. https://air.io/en/monetization/youtube-monetization-policy-changes-2026-a-complete-dated-timeline
9. Retention benchmarks — documentary 45–55% at 8–12 min; 35–45% at 15–30 min; 25–35% at 30–60 min. https://prepublish.ai/blog/youtube-retention-benchmarks-2026 and https://humbleandbrag.com/blog/youtube-audience-retention-benchmarks
10. OutlierKit, *How Money Works* — 1.8M subs, 324 videos, ~902.8K avg views. https://outlierkit.com/channel/howmoneyworks
11. OutlierKit, *Business Casual* — 1.1M subs, 91 videos, 102.9M views, last upload 1,097 days ago, $4K–$20K/mo estimate. https://outlierkit.com/channel/businesscasual
12. vidIQ, Modern MBA — 823K subs, 82 videos, 62.49M views, 1.08M in 28d, ~$6,769/mo estimate. https://vidiq.com/youtube-stats/channel/@modernmba/
13. Modern MBA site — self-reported ~20 min average view duration, 2M+ monthly viewers, 70% North America. https://modern-mba.com/ (channel-reported, not audited)
14. Social Blade, ColdFusion — 5.25M subs, 578M views, 587 videos. https://socialblade.com/youtube/handle/coldfusion
15. HypeAuditor, ColdFusion — $8,689–$11,903 estimated monthly income; vidIQ shows ~$6K/mo — a 2× divergence. https://hypeauditor.com/youtube/UC4QZ_LsYcvcq7qOsOhpAX4A/
16. Social Blade, MagnatesMedia — 1.86M subs, 194M views, 255 videos. https://socialblade.com/youtube/handle/magnatesmedia
17. MagnatesMedia founder page — ">$1,000,000 from YouTube AdSense alone"; $997 course. https://magnatesmedia.com/
18. Business Casual Holdings v. YouTube — dismissed with prejudice, 22 Nov 2022. https://www.courtlistener.com/docket/59847655/business-casual-holdings-llc-v-youtube-llc/
19. Patreon vs YouTube fee comparison, 2026 — YouTube 30% of memberships; Patreon 10% + processing. https://milx.app/en/trends/is-subscription-based-income-worth-it-the-case-of-youtube-memberships
20. Sponsorship CPM ranges — finance $30–$60 (OutlierKit), $40–$80 (SponsorRadar). https://outlierkit.com/resources/youtube-sponsorship-rates/ and https://sponsorradar.com/insights/youtube-sponsorship-rates-what-brands-should-pay
21. YouTube search result pages, 23 Oct 2026 — Northern Rock, Barings, Lehman, LTCM, SVB, Greensill, nickel. Snapshots, not exhaustive, not search-volume data.
22. Repo inspection — `content/queue/*.md` frontmatter, `docs/DEEP_DIVE.md`, `pipeline/config.py` (`words_per_second: 2.5`), `pipeline/run.py::_validate_finance_niche`, `content/research/0003-lehman-dossier.md`.

**Limits:** all revenue figures from trackers are modelled, not disclosed. Modern MBA's 20-minute AVD and MagnatesMedia's revenue claims are self-reported. Retention bands are industry aggregates, not YouTube-published data. The 1% membership conversion rate is a planning assumption. Search snapshots rank by relevance, not demand.
