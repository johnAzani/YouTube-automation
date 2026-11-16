# Protection and revenue: what the rules say and where the channels stand (16 November 2026)

Read this with `AGENTS.md` (the standing order this research serves) and
`docs/MONETISATION_RESEARCH_2026-11-14.md` (the earlier note, written when
YouTube's own pages could not be reached from the build machine; this time
they were read directly).

Times are Nigeria time unless marked UTC.

## 1. The short version

1. **The largest risk is not a refused monetisation review. It is losing every
   channel at once.** YouTube's spam policy covers "coordinated networks of
   channels" and ends channels for AI-made videos produced in volume with small
   changes. A termination is of the owner, and takes the related channels too.
   Ten channels, one voice, one layout, one program and 66 uploads a day is the
   shape that policy describes.
2. **The first payment is far away on the present path.** On 16 November The
   Secret Place had **16 of the 4,000 watch hours** that count. Shorts bring
   98% of its views and none of those hours count. From 1 February 2027 the
   bar for new applicants is 8,000.
3. **Each channel has its own Google Cloud project, set up to give each its own
   quota.** YouTube's developer policy says one program gets exactly one
   project. This is the owner's to decide and fix; the program cannot.
4. Two things were fixed in the program today, and one measure was added so
   the drift is seen daily (section 6).

## 2. What YouTube's own pages say

Quotations are from the pages named, read on 16 November 2026.

### 2.1 Monetisation policy (support.google.com/youtube/answer/1311392)

- Content must be original and "not mass-produced, generic, repetitive, or manipulative".
- A reviewer looks at the main theme, the most viewed videos, the newest
  videos, where most watch time comes from, the titles, thumbnails and
  descriptions, and the About section. The channel is judged as a whole.
- Refused: content that "looks like it was made with a template", where
  "content feels interchangeable from video to video"; "image slideshows or
  scrolling text with minimal or no narrative, commentary, or educational
  value"; AI content from generic templates that gives "the impression of mass
  production".
- Allowed: the same intro and outro when the bulk of each video differs; a
  series in which each video has its own focus. "If you use automated tools or
  templates to help create your content, the final product must still
  demonstrate your creative vision".
- Reused content, refused: "Content that exclusively features readings of other
  materials you did not originally create". A prayer here quotes scripture and
  then prays in its own words; a video that only read the Bible aloud would
  fall under this line.
- AI personas, refused: a channel using an AI persona that "presents itself as
  a human expert providing advice" on "health, legal issues, finances, or
  politics", for example "An AI 'doctor' providing medical diagnoses, health
  advice, or wellness remedies". **The Healing Balm and The Provision Table
  pray about health and money. They must stay prayer and never become advice.**
  The Shorts writer is told to promise no healing; no check reads a prayer
  for financial or medical advice. That is an open item (section 8).

### 2.2 Spam policy (support.google.com/youtube/answer/2801973)

- It applies to videos, comments, links, posts, thumbnails "and coordinated
  networks of channels".
- "Automated or synthetic mass-production": "using automated tools or AI to
  churn out high volumes of similar content with minimal changes". The example
  given: "Channels that use the exact same background music and repetitive AI
  generated imagery across many videos, with each video reading out an
  AI-generated script."
- Also named: many low-effort repetitive polls; identical or similar comments
  across many videos; content made only to send viewers off YouTube. Asking
  viewers to like, comment or subscribe is allowed.
- Consequence: monetisation suspended, or the channel or account ended.
  Labelling a video as AI-made "is not a free pass".

### 2.3 What a termination reaches

From YouTube's public statement of November 2025 as reported by ppc.land and
two other secondary sources (the primary page was not read): a termination
applies to the person. YouTube looks for and ends the person's other channels,
and the person may not use or open another. One appeal. Channels are tied
together by Google account, AdSense account, recovery phone, device and
network, and similar metadata.

### 2.4 Partner Programme (answers 72851, 12843009 and 7101720)

- Today: 1,000 subscribers and either 4,000 qualified watch hours in 12 months
  or 10 million qualified Shorts views in 90 days.
- "any qualified watch hours from Shorts views in the Shorts Feed won't count
  towards the 4,000".
- From 1 February 2027, for new applicants: 8,000 hours or 20 million Shorts
  views. Channels already in are not affected.
- Earlier tier, unchanged: 500 subscribers and either 3,000 hours or 3 million
  Shorts views opens fan funding, Creator Partnerships and Shopping.
- Nigeria is on the list of countries where the Partner Programme is available.
- Also needed: no active strike, 2-step verification, advanced features, one
  AdSense account.
- Review is "typically in about 1 month". After a refusal: appeal within 21
  days, or apply again after 30 days; after a second refusal, 90 days.
- From 1 February 2027 a channel stays active with any one of: 1,000 hours in
  365 days; 1 million Shorts views in 90 days; 2 long-forms or 5 Shorts every
  90 days. Earning from the Shorts pool then needs 10 million Shorts views
  every 90 days.

### 2.5 Developer policy and quota (developers.google.com/youtube)

- Policy III.D.1.c: "you must create exactly one (1) API Project for that API
  Client".
- Quota page, last updated 12 November 2026: each project gets "100
  `search.list` calls, 100 `videos.insert` calls, and 10,000 units per day
  combined for all other endpoints". Setting a thumbnail, adding a comment,
  editing a video or adding to a playlist costs 50 units each.
- Secondary sources (not YouTube's text): several projects used to act as one
  and get round quota have had API access restricted, and more quota comes
  only through YouTube's audit and quota extension form.

### 2.6 AI disclosure

Secondary sources reading YouTube's page: disclosure is required for content
that is altered or synthetic and looks real. A text-to-speech narration over
original material does not require it, and disclosure does not reduce reach or
earnings. The program sends `containsSyntheticMedia: false` unless a script
says otherwise (`pipeline/upload.py`). The primary page was not read today.

## 3. Where the channels stand against those rules (measured)

Measured from the repository on 16 November 2026.

| What the rules describe | What was found |
|---|---|
| High volume | Uploads across all ten channels per UTC day: 30 (11 Nov), 41, 43, 54, **66** (15 Nov). About one long-form and five or six Shorts per channel per day. |
| Titles from a template | 188 published Shorts had 18 title shapes once the reference is removed. On each channel almost every title is the same sentence around a different reference. The few words after the bar were the channel's own name, the reference again, one word, or a cut-off line on **187 of the 260** Shorts written. |
| Long-form titles | 179 long-forms, 131 shapes. The older channels' shapes repeat ("<reference> Morning Prayer \| The Morning Altar", 15 times). |
| The same words in every video | Not found. Of 11,116 long-form sentences, 104 appear in more than one video, and those are the closing invitation and Bible verses. Median share of a Short's four-word phrases found in any other Short: 9%. |
| The same words across channels | Not found. No prayer sentence other than scripture is spoken on two channels. |
| Same voice, same music method, same layout on all ten | True, by design (`STATE.md` §1 locks the voice and the visual system). |
| One program, several Cloud projects | The setup notes (`docs/SECOND_CHANNEL_SETUP.md` and the later ones) create a separate Google Cloud project per channel, and say why: each gets its "own YouTube Data API v3 quota pool". How the owner's projects are actually set up cannot be read from here. |

What this means, said plainly: the words are original and differ video to
video, which is the strongest point in the channels' favour. The packaging
(titles, voice, layout, volume, ten channels at once) is what looks mass-made.
Nobody outside YouTube knows where its line is. The honest reading is that the
network is exposed, that more volume raises the exposure, and that the cheap
fixes are in the packaging.

## 4. Where the money stands (measured)

From YouTube Analytics for The Secret Place (`content/analytics/secret-place.json`,
written 7:53am on 16 November; figures run about two days behind). It is the
only channel that has granted Analytics access.

| | |
|---|---|
| Subscribers | 1,250 (needs 1,000) |
| Watch hours that count, 365 days | **16.03** (needs 4,000) |
| Shorts watch hours, 365 days (do not count) | 65.82 |
| Shorts views, 90 days | 3,107 (the Shorts route needs 10,000,000) |
| Views, last 28 days | 3,109, of which 3,042 Shorts and 67 long-form |
| Long-form watch hours a day, last 28 days | 0.05 |

- To reach 4,000 by 31 January 2027 the channel would need about 52 counted
  hours a day. It gets 0.05. **That date will not be met on the present path.**
  After it, the bar is 8,000 hours.
- The limit is not how many videos are made. It is that almost nobody watches
  the long-forms: 67 views in 28 days. Shorts get the views and their time
  does not count.
- The three-hour night version began on 14 November. The figures stop at 13
  November, so whether it earns hours is not yet known. It will show in this
  file from about 17 November.
- What a prayer channel earns per 1,000 views once monetised: published
  estimates range from $0.80 to $18 and contradict each other. None is used
  here. The channel's own figure, after monetisation, is the only real one.
- Money available before the Partner Programme: the Selar links in The Secret
  Place's descriptions. Their clicks and sales are not visible to the program.

## 5. What follows from it

In order of weight.

1. **Do not add volume.** More Shorts add no counted hours and add exposure.
2. **Make each video look like its own piece**: titles first (done today for
   Shorts), then long-form titles, thumbnails, and the fixed opening.
3. **Put the effort where hours come from**: getting a viewer from a Short to
   the long-form prayer on the same passage, and long-forms that are found in
   search.
4. **Keep prayer as prayer** on the health and money channels.
5. **The owner's decisions** (section 7).

## 6. What was changed on 16 November

- **A Short's title now says something of its own.** The words after the bar
  were always the last poster line. They are now the first line that is not
  the channel's name, the reference again, the kind of prayer the title
  already names, a single word, or a cut-off line; and one that keeps the
  whole title inside the length limit is preferred, so it is not cut off at
  the bar. On the 260 Shorts written so far, 187 get a different, fuller
  title and none loses its hook. Example: "Say This Psalm 108:2 Prayer at
  Sunrise | The Morning Altar" becomes "... | Awaken The Dawn". Titles such as
  "Receive God'S Peace" (a capital after the apostrophe) are also corrected.
  Only Shorts published from now on are affected; live titles are not edited.
  The upload's duplicate check finds a video by its title, so it now looks
  for the old title as well as the new one.
- **A Short may not speak in another channel's words.** The check that
  long-form prayers had was never applied to Shorts. The Family Altar
  published one that prayed "every bedtime prayer" (The Secret Place's
  wording) and the daily test run on `main` failed for it at 7:51am today.
  The writer is now told which words are not its own, and a Short that uses
  them is refused and written again. The one published Short is recorded by
  name; no waiting Short carries such wording.
- **A daily measure** (`scripts/channel_protection.py`, a step in the health
  check): uploads per channel per day, recent Short titles that say nothing of
  their own, titles used twice, and prayer sentences shared across channels.
  It reports and warns; it does not stop publishing. Today's reading: 113 of
  the 155 most recent Short titles say nothing of their own. That figure
  should fall over about four days as new Shorts replace them. If it does not,
  the fix did not work.

## 7. What only the owner can decide or do

1. **The Cloud projects.** One program with a project per channel is against
   the developer policy as written. The clean position is one project for the
   program and a request for more quota through YouTube's audit form. One
   project's default allowance (100 uploads a day; 10,000 other units) covers
   today's 66 uploads but probably not the thumbnails, pinned comments and
   edits that go with them (about 50 units each). This needs the owner's
   Google account and a decision; nothing was changed.
2. **How many channels, and how many uploads a day.** Fewer, more distinct
   channels are safer than ten alike. The program publishes what the schedule
   asks; the schedule is the owner's choice.
3. Phone verification on The Midnight Watch, The Family Altar, The Covenant
   Shield, The Praise Garden and The Guided Path (122 videos wait for their
   thumbnail; without one, the videos look more alike, not less).
4. Analytics permission on the nine channels that have not given it.
5. 2-step verification and an AdSense account, before any application.

## 8. Not known, or not done

- Where YouTube's line is. No number is published for volume or sameness.
- Whether the new titles raise views. Nothing has been published with them yet.
- Whether the three-hour night version earns counted hours.
- The spam policy's second half, the developer policy beyond section III.D,
  the AI disclosure page, the advertiser-friendly guidelines and the country
  list for the 500-subscriber tier were not read today.
- Whether using a free Gemini project per channel is within Google's terms.
  Secondary sources say several projects made to multiply free limits are not;
  the terms page read today (first part) does not mention it.
- No check reads a prayer for medical or financial advice.
- Long-form titles and thumbnails were measured, not changed.

## 9. How to undo today's changes

- Titles: in `pipeline/short_release.py`, make `title_hook` return
  `(last_line or "Divine Peace").title()` straight after `last_line` is set.
- Wording check: remove the `foreign_wording` block in
  `GeminiBrain.author_short_spec`.
- Daily measure: remove the step "Measure how alike the channels look" from
  `.github/workflows/automation-health.yml`.

## 10. Long-prayer titles (added later on 16 November)

Measured at 07:45 UTC over 123 published and 64 queued long prayers.

| Channel | Published titles still in the old form | Need-first titles (published and queued) | Of those, opening with "When" |
|---|---|---|---|
| The Secret Place | 13 | 12 | 2 |
| The Morning Altar | 19 | 11 | 5 |
| The Midday Watch | 10 | 13 | 5 |
| The Midnight Watch | 11 | 9 | 3 |
| The Family Altar | 8 | 8 | 0 |
| The Healing Balm | 7 | 9 | 3 |
| The Provision Table | 8 | 9 | 1 |
| The Covenant Shield | 5 | 9 | 1 |
| The Praise Garden | 4 | 8 | 3 |
| The Guided Path | 3 | 9 | 7 |

- The old form ("Psalm 143:8 Morning Prayer | The Morning Altar") opens with the passage and differs from its neighbours only by the passage. 88 published titles still carry it. `pipeline/retitle.py` replaces it on videos at least seven days old with two views or fewer, two a channel a day; 8 had been replaced by this reading.
- Of the 99 need-first titles, 30 open with "When". Seven of the eight retitled videos do.
- One need is worded identically on two channels ("When You Don't Know What to Do", The Morning Altar and The Midday Watch) and two more pairs differ by one word.
- Twenty passages are prayed on more than one channel. That is not a fault in itself (each channel prays it for its own hour), but it is where two titles are most likely to come out alike.

What was changed: `pipeline/title_variety.py` and its use by the retitler, the author and the daily measure (see `CHANGELOG.md`, same date). The marks in it (a third of the last fifteen titles; six tenths of the meaningful words) are this repository's, chosen from the readings above. YouTube publishes no number.

To undo: revert the commit. Nothing on YouTube was written by it. Titles it helps write afterwards are ordinary titles and stay.

Not known: whether varied titles bring more long-prayer views. YouTube search brought 145 of The Secret Place's 3,109 views in 28 days, so the words a title leads with matter, but that is one channel and one month.

