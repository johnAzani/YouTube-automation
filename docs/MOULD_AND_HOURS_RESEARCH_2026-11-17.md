# One mould, and the hours that are not there

17 November 2026. Times are Nigeria time (WAT, UTC+1) unless marked UTC.

This is a reading, not a plan. Everything below was read from this repository's own
files on 17 November 2026, and each figure names the file it came from. Nothing here
is an estimate where a record exists.

## The short answer

- **The ten channels are one shape.** 237 of the 237 Short titles published so far
  begin with the same two words — "Pray This" (130) or "Say This" (107) — and every
  channel's Shorts are built on exactly one frame, with only the passage swapped.
  The two words are set in code, per channel, in
  `pipeline/channel_capabilities.py` (`Brand.short_title_template`), and nothing has
  ever measured them.
- **The long prayers are one length.** All 133 published long-forms are authored to
  six minutes, from one number in one prompt
  (`pipeline/gemini_brain.py`: `author_words = max(950, …)`).
- **The funnel does not carry anyone yet.** 124 of 238 published Shorts link to a
  real prayer; the other 114 link to a playlists page, because their channel has no
  long-form on that passage. The only traffic figure that could show the bridge
  working — "Suggested videos" on The Secret Place — is 32 views in 28 days.
- **The hours are not there, and the date cannot be met.** The Secret Place has
  **16.33 counted hours of 4,000** in the last 365 days, and **1.78 hours in the last
  28 days**. Reaching 4,000 by 31 January 2027 needs **53 hours a day**; the
  channel is doing **0.064**.
- **The night tail's first reading is negative.** The one three-hour video the
  analytics cover was shown **730 times** — more than any other video on the
  channel — and returned **9 views, 99 seconds each, 0.18 watch hours**. A
  six-minute prayer on the same channel earned 0.10 to 0.88 hours. Three hours
  bought nothing. One video is not a finding; it is the first reading of the bet the
  research of 14 November named.

## 1. What was measured

### 1.1 The mould, on three axes

**Titles.** `scripts/channel_protection.py` now reports, per channel, how many of its
most recent Short titles are built on one frame — everything before the bar, less
the passage. The reading:

| Channel | Recent Short titles | On the channel's one frame | Frames it has | The frame |
|---|---:|---:|---:|---|
| The Secret Place | 20 | 20 of 20 | 1 | `Say This {passage} Prayer Before You Sleep` |
| The Morning Altar | 20 | 20 of 20 | 1 | `Say This {passage} Prayer at Sunrise` |
| The Midday Watch | 20 | 20 of 20 | 1 | `Say This {passage} Prayer at Noon` |
| The Midnight Watch | 20 | 20 of 20 | 1 | `Pray This {passage} Midnight Prayer` |
| The Family Altar | 19 | 19 of 19 | 1 | `Pray This {passage} Family Prayer Over Your Home` |
| The Healing Balm | 20 | 20 of 20 | 1 | `Pray This {passage} Healing Prayer for Peace & Strength` |
| The Provision Table | 20 | 20 of 20 | 1 | `Pray This {passage} Prayer for Open Doors & Provision` |
| The Covenant Shield | 16 | 16 of 16 | 1 | `Pray This {passage} Prayer for Divine Protection` |
| The Praise Garden | 16 | 16 of 16 | 1 | `Pray This {passage} Prayer of Thanksgiving` |
| The Guided Path | 14 | 14 of 14 | 1 | `Pray This {passage} Prayer for God's Guidance` |

Across the network: **237 of 237 published faith Short titles open with two words
another channel also uses**, and the whole network uses **2 openings in all**.

The hook after the bar was fixed on 16 November so that it says something of its own
(`pipeline/short_release.title_hook`). The words before the bar were not touched:
they come from one template per channel, and a channel has never had a second one.

**Length.** Every long-form job in the repository, counted by `target_minutes`:

| | Jobs | Six minutes | Other |
|---|---:|---:|---|
| Published, all ten channels | 133 | **133** | 0 |
| Waiting in the queue (faith) | 59 | 58 | one at 7 |
| Waiting in the queue (finance, another niche) | 5 | 0 | four at 9, one at 21 |

The length is not a content decision anybody made per video: `gemini_brain` asks for
"at least 950 words", and Charon narrates about 165 words a minute
(`pipeline/script_doc.py`), so every prayer lands at about 5:45–6:00.

**Openings.** The narration's first sentence was the subject of the 13 November fix
(`pipeline/short_script.recent_openings`), which shows the writer the eight worn
openings and asks it not to use them. It worked: the channels now have 16 to 37
distinct three-word openings each. It is advice, not a gate, and the worn lines are
still the most common on three channels:

| Channel | Shorts read | Distinct openings | Most-used opening | Uses |
|---|---:|---:|---|---:|
| The Secret Place | 47 | 29 | "Take a deep breath…" | 8 (17%) |
| The Midnight Watch | 35 | 24 | "Rise in spirit this midnight hour…" | 8 (23%) |
| The Family Altar | 25 | 17 | "Gather your home and loved ones in faith…" | 6 (24%) |

The last two are the exact stock lines the 13 November docstring names as the ones
the fix existed to remove. They are still there, on the same channels, 24 Shorts
later.

### 1.2 The funnel: where a Short sends the viewer

Every faith Short's description opens with a link to the full prayer
(`pipeline/shorts_bridge.enrich_short_description_with_bridge`). What that link
points at, read from all 238 published Short receipts:

| The link goes to | Shorts | Share |
|---|---:|---:|
| A live long-form on the same passage, same channel | 124 | 52% |
| A queued long-form on the same passage | 7 | 3% |
| The channel's playlists page, because there is no long-form on that passage | 107 | 45% |

The 45% is not a bug in the link: the bridge looks for a long-form on the Short's
own passage and there is none. The Shorts pray passages the channel has never made a
long prayer of. Two published long-forms are also gone from YouTube
(`youtube_status: deleted_or_missing`: job 0009 Psalm 23 on The Secret Place, job
0210 Ruth 3:8-11 on The Midnight Watch), which takes two more Shorts' worth of
targets with them.

Whether any of this matters is measurable on one channel only, and the figure is
small: The Secret Place's 28 days of traffic (`content/analytics/secret-place.json`):

| Where the view came from | Views | Watch hours |
|---|---:|---:|
| The Shorts feed | 3,229 | 16.22 |
| YouTube search | 162 | 0.58 |
| Other YouTube pages | 48 | 0.20 |
| The channel page | 41 | 0.47 |
| Other sites and apps | 34 | 0.37 |
| Suggested videos | 32 | 1.27 |
| Home and subscriptions | 20 | 0.05 |
| Notifications | 7 | 0.08 |
| Direct or unknown | 2 | 0.00 |

A Short viewer who goes on to the full prayer arrives as "Suggested videos", "the
channel page" or "other YouTube pages": **73 views and 1.7 hours in 28 days**. The
bridge is not carrying anyone yet. That is a statement about traffic, not about the
link: the link is in the description of every one of those Shorts and only YouTube
Studio's click data would say whether it was followed.

### 1.3 The hours

The Secret Place is the only channel past 1,000 subscribers (1,260), and it is the
only channel with Analytics access — the other nine are not readable at all, so no
distance-to-threshold figure exists for them.

| Figure | Reading | Where |
|---|---:|---|
| Subscribers (need 1,000) | 1,260 | `content/analytics/README.md` |
| Public watch hours, 365 days (need 4,000) | **16.33** | same |
| of which Shorts | 67.32 (does not count) | same |
| Long-form and live hours, last 28 days | **1.78** | same |
| Long-form views, last 28 days | **83** | same |
| Shorts views, last 28 days | 3,492 | same |
| Shown in search, home, suggested or the channel page, 27 days | 3,565 impressions, 50 clicks (1.4%) | `content/analytics/secret-place.reach.json` |

Three readings follow, and they are the whole of the revenue problem:

1. **A long-form view is worth 0.0214 hours** (77 seconds). A Shorts view is worth
   0.005 hours (18 seconds) and counts for nothing.
2. **The channel gets about 4.6 long-form views per long-form published** (83 views
   across 18 published long prayers in 28 days). It publishes one long prayer and five
   Shorts a day (`scripts/channel_protection.py`: 1 + 5 yesterday, 2 + 5 on The Guided
   Path), and its long prayers take about three views a day between them.
3. **11 hours a day is the rate 4,000 hours a year requires.** 11 ÷ 0.0214 is
   **514 long-form views a day**. The channel does about three. That is 170 times
   more, and no amount of writing, titling or scheduling moves a figure by 170 times
   on its own.

### 1.4 The night tail's first reading

`pipeline/night_tail.py` (built 14 November) turns The Secret Place's nightly
long-form into a three-hour video: the six-minute prayer, then the same video's own
pictures dimmed and the studio's own score, repeated behind it. Three have published:

| Job | Published | Length | Shown | Clicks | Views | Average watched | Watch hours |
|---|---|---:|---:|---:|---:|---:|---:|
| 0024 Psalm 139:11-12 | 14 Nov | 186 min | **730** | 7 (0.96%) | 9 | **1:39 (0.9%)** | **0.18** |
| 0025 Proverbs 3:24-26 | 15 Nov | 186 min | — | — | — | — | — |
| 0026 Isaiah 26:3-4 | 16 Nov | 188 min | — | — | — | — | — |

0024 was shown 730 times in the one day the reach files cover it — 20% of every
impression the channel received in 27 days, from one video, in one day. It returned
0.18 watch hours. The channel's six-minute long prayers returned between 0.10 and
0.88 hours each on the same basis, from a tenth as many impressions.

What that says, stated as narrowly as the evidence allows: **the extra length did not
hold anybody.** Viewers left at 99 seconds, which is the same place they leave a
six-minute devotional. 0025 and 0026 have no reading yet (YouTube's figures run about
two days behind). Three videos, one measured, is not a finding — but it is the first
reading of the bet, and the document that made the bet said the first week of watch
time was the test.

## 2. The arithmetic, if the threshold is the goal

- **31 January 2027** is the last day to apply at 4,000 hours; from 1 February 2027
  a channel still outside needs 8,000 (`AGENTS.md`, checked 16 November).
- 3,984 hours remain in 75 days: **53 hours a day**.
- At 0.0214 hours a long-form view, that is **about 2,500 long-form views a day**,
  against about three today.
- At the current rate of 0.064 hours a day, 4,000 hours is **about 170 years** away.

So: **the date cannot be met, and saying otherwise would be a lie.** What is left is
the rate, not the date. Two things can change the rate by the order of magnitude the
arithmetic needs, and only two:

1. **Many more long-form views**, which is a distribution problem — the channel is
   shown 132 times a day in total.
2. **Many more hours per view**, which is what a night-length video is for. It
   multiplies the numerator instead of the denominator: one viewer who leaves it
   playing for three hours is worth 3.0 hours, where one full six-minute view is
   0.1. To reach 53 hours a day that way needs **about 18 viewers a day** to leave it
   playing. The first one published got 9 viewers and none of them stayed.

Nothing in this repository can make someone stay. What it can do is stop claiming a
length that is not the length, which is the next section.

## 3. What was changed today

**The measure.** `scripts/channel_protection.py` has a new section, "Short titles
built on one frame", with the four columns in §1.1, and a line for the network's
openings. It is a reading and it can fail nothing. The figure it reports — 20 of 20,
one frame, on ten channels — is the thing that should move first, because a title is
the cheapest thing here to change and the only part of a video a reviewer reads for
every upload.

**The length in the description.** Every faith Short's description opened
"🕊️ PRAY THE COMPLETE **8-MINUTE** … MEDITATION" — one fixed sentence, on all ten
channels, pointing at six-minute videos and at three that run three hours. The
number was true when long-forms were nine minutes long and no record was ever read to
check it. `pipeline/shorts_bridge.py` now reads the length from the linked video's
own receipt: `duration_seconds` when the render recorded it, otherwise
`target_minutes`, otherwise no number at all. Re-read against the 238 published
Shorts: **121 now say six minutes, 3 say three hours, 107 say no number, 7 point at a
queued long-form.** No live description was edited; the retrofit script applies the
same function when it next rewrites one.

**A measure that was reading the wrong passage.** `scripts/channel_protection.py`
found a title's scripture reference with a pattern that accepted any capitalised word
before a number. It read "Say This **1 Peter** 5:7 Prayer Before You Sleep" as the
passage "This 1", and it did so on **19 published Short titles** — every title naming
a numbered book (1 Peter, 2 Samuel, 1 Corinthians, 3 John, 1 Thessalonians, …). Every
comparison between a title's hook and its own passage was made against the wrong
words. It now uses `gemini_brain._BOOK_RE`, the repository's one list of book names,
which `evergreen_shorts.reference_parts` already reads. The first table in the report
is unchanged by the fix — those 19 titles are older than the 20 most recent on their
channels — but the next numbered-book Short to publish will be measured correctly.

**What that figure is expected to move, and where it is read.** The frame column in
`python -m scripts.channel_protection` (and in the run summary the daily health check
writes). Today: 100% on ten channels, 237 of 237 sharing an opening. The change that
would move it is not in this pull request, because it rewrites the title of every
Short on ten channels and nobody can see what YouTube does with it from here.

## 4. What is not known

- **Whether a different frame brings more or fewer views.** No title here has been
  tested against another. The one comparison that exists — "Say This" Shorts had a
  median 77 views against 23 for "Pray This" — is confounded by channel age and
  subscriber count, as the 14 November research says itself.
- **Whether the 114 playlist links cost anything.** The bridge's own traffic is 73
  views in 28 days; the difference between a playlist page and a prayer has never
  been tested.
- **Whether the night tail works.** One measured video. Two more published since.
  The next reading is the honest one, and it needs a week.
- **What the other nine channels are doing.** They have no Analytics access, so
  their watch hours, impressions and click rates are unknown. Every revenue figure in
  this document is The Secret Place's alone.
- **How YouTube's reviewers read this.** YouTube publishes no threshold for
  "templated"; the marks this repository uses are its own, and they are stated as
  such wherever they appear.

## 5. What only the owner can do

1. **Decide what a Short's title should be.** Four frames per channel is a week's
   work and a writing decision; whether the channel keeps saying "Prayer at Sunrise"
   is the owner's call about what the channel is, not a program's. What the program
   can do is what it now does: report the share, and refuse nothing.
2. **Decide the night tail.** Keep publishing three-hour prayers on the strength of
   one negative reading, or pause it (`NIGHT_TAIL_MINUTES=0`) until the second and
   third readings are in. Both are defensible; the repository should not decide it
   quietly.
3. **Grant Analytics access to the other nine channels.** Without it, nine of the ten
   channels have never had a distance-to-threshold figure, and the five that need
   phone verification before they can carry a custom thumbnail cannot be measured at
   all.
4. **Set the target.** If the Partner Programme by January is no longer the goal, say
   so plainly and the arithmetic in §2 becomes a rate to improve rather than a date
   that will be missed. If it still is the goal, the only lever with the right order
   of magnitude is viewers who leave a night-length video playing, and that is a
   format decision, not a scheduling one.

## 6. What was read for this document, and what was not

Read: every published and queued job in `content/`; both analytics files;
`scripts/channel_protection.py`, `pipeline/shorts_bridge.py`,
`pipeline/short_release.py`, `pipeline/short_script.py`,
`pipeline/gemini_brain.py`, `pipeline/script_doc.py`,
`pipeline/channel_capabilities.py`, `pipeline/night_tail.py`,
`pipeline/evergreen_shorts.py`; `docs/MONETISATION_RESEARCH_2026-11-14.md`,
`docs/PROTECTION_AND_REVENUE_RESEARCH_2026-11-16.md`, `AGENTS.md`.

Not read: YouTube's own policy pages and help pages. They could not be reached from
the machine that wrote this — only GitHub and the package registries answer — so the
policy language quoted here ("feels interchangeable from video to video", the
inauthentic-content rule) is carried over from the repository's own reading of 16
November and has not been re-verified today. The thresholds (4,000 hours, 8,000 from
1 February 2027) are likewise carried over and should be re-checked against YouTube's
own page before any date is promised to anyone.
