# What actually decides whether a Short is watched (17 November 2026)

YouTube does not rank a Short on how many times it is uploaded. The Help page
for Shorts search and discovery (read 17 November 2026) says the system looks
at, in order: whether a viewer **chose to view** rather than swipe, then
**average view duration** and **average % viewed**, then whether they enjoyed
it (likes, post-watch surveys).

Source: [Search & discovery tips — Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts).

This file records what was measured on *these* channels, what the prompt was
teaching the model to copy, and what changed. It does not claim a Short will
go viral. A breakout cannot be scheduled.

## 1. Where the views actually are

`content/analytics/secret-place.json`, generated 17 November 2026:

| | Figure |
|---|---|
| Subscribers | 1,260 (need 1,000) |
| Long-form watch hours, 365 days | 16.3 (need 4,000) |
| Shorts views, 90 days | 3,557 (need 10,000,000) |
| Last 28 days, Shorts feed | 3,229 of 3,575 views |
| Last 28 days, long-form hours | 1.78 |

Shorts views do not count toward the Partner Programme. They are still where
strangers are: 90% of the last 28 days' views arrived in the Shorts feed.
The other nine channels have not been granted Analytics; the 14 November
public-count snapshot (`docs/GROWTH_EVIDENCE_2026-11-14.md`) put Shorts at
97% of network views.

Search demand on this channel, 90 days, is the psalm by name (`psalm 91`,
`psalm 31`, `psalm 27 explained`) and bedtime language (`deep sleep prayers`,
`night prayer before going to bed`). Those terms produced 8, 7, 4, 2 and 2
views. Search is not the engine. The feed is.

## 2. The Shorts that held people

The same Analytics file ranks videos by watch hours. The four that looped
(average % viewed at or above 100) are all Shorts:

| Video | Views | Average % viewed | Watch hours |
|---|---:|---:|---:|
| Psalm 23 Short (`kLgHN57fb1w`) | 258 | 145% | 2.08 |
| Psalm 16:7-8 Short (`d0Et8L_6y1o`) | 140 | 191% | 1.77 |
| John 14:27 Short (`dmwIvRt6Ve8`) | 178 | 110% | 1.53 |
| Psalm 37:7 Short (`5ekShDmycic`) | 52 | 129% | 0.53 |

Psalm 27 has the most views (393) at 76% viewed. Psalm 121 has 147 views at
42%. Views without a loop do not produce the same hours. Four videos is not
a law; it is the only loop signal this channel has.

## 3. What the 353 authored specs actually do

Counted 17 November 2026 over every file in `content/shorts-scripts/`:

| | Count |
|---|---|
| Specs | 353 |
| First caption ends after second 3 | **353 of 353** (median 8s, mean 8.5s) |
| First caption longer than 8s | 98 |
| First caption words, median | 15 |
| Openings of more than 16 words | 46 |
| Last caption speaks "subscribe" | **193 of 353** |
| Last caption starts "type amen and subscribe" | 24 |
| Opening first-three-words "if you are" | **36** |
| "take a deep" / "rise in spirit" / "welcome" | 8 / 8 / 8 |
| First and last sentence share a content word | 74 of 353 (21%) |

The model was not ignoring the prompt. The prompt's own JSON example was
`[[0, 8, "First narrration line."]]`, and the hard rules said the prayer
"ends with a single subscribe invitation." Caption 1 is the swipe window;
the example taught an eight-second first line. The end card already says
SUBSCRIBE; speaking it is a closer, which is a reason to swipe as the clip
restarts.

A new template has already formed: 36 Shorts open "If you are…". That is
the same defect as "Gather your home…" on 13 November, with different words.

## 4. What changed

Applies to Shorts **written from now on**. Queued specs keep loading: the
new checks live in `authoring_defects()`, which `validate_spec` does not
call, so an eight-second first caption already in the queue still renders.

- The JSON example in `pipeline/short_script.py` starts `[0, 3, …]`.
- Caption 1 is asked for 3–8 words ending by second 3.
- Worn first-three-word skeletons are named and refused at authoring
  (`if you are`, `take a deep`, `rise in spirit`, `gather your home`,
  `close your eyes`, `bring every weary`, `welcome`).
- Spoken "subscribe" / "follow" / "type amen" in the last caption is
  refused at authoring. The end card is unchanged.
- A three-word first caption ("Can't sleep tonight?") is a valid line.

The figure this expects to move is **average % viewed** on new Shorts, read
from `content/analytics/` (The Secret Place only, about two days behind).
A loop looks like 100% or more, as on the four videos in section 2.

## 4b. The first picture was a citation

A Short autoplays. Many viewers have not turned the sound up in the first
second. The renderer already paints kinetic type at full opacity on frame 0
(`tools/shorts.py`, "DOCOGA REELS v2 EMBEDDED-COVER LAW"). The HUD card in
the top-left fades in over 0.42s, so by the time the swipe window is decided
it is readable.

Counted on the same 353 specs:

| | Count |
|---|---|
| Scene-1 kicker is a book+chapter (`PSALM 23:1`, `PROVERBS 16:3`, `1 PETER 5:7`) | **285 of 353** |
| Scene-1 kicker is the channel's name | 4 |
| Scene-1 kicker is a need (`GOD IS NEAR`, `A MOMENT OF PEACE`) | 64 |
| First kinetic phrase is need-language, not a verse | 353 of 353 |
| First kinetic phrase ends after second 3 | **353 of 353** (median 8s, 11 words) |

The scene example in the prompt was `"kicker": "PSALM NN:1"`. That is what
the HUD copied. A stranger scrolling past ten channels that all open on a
reference is looking at a template; YouTube's monetisation review looks for
the same thing.

Changed with the spoken hook, still only for Shorts written from now on:

- Scene 1 kicker must name the need (2–4 words), not the verse and not the
  channel. The verse stays on later scenes and on kinetic attribution.
- The first on-screen phrase must end by second 3 and stay within 8 words,
  matching caption 1.
- The JSON example is now `"kicker": "STILL HERE"`.

The HUD fade-in at t=0 was **not** removed. Making it visible on frame 0
while 285 queued specs still say `PSALM NN:1` would put a citation on the
first frame of videos already waiting to render.

## 5. Unproven

- That a three-second first caption raises "% who chose to view". Studio
  has that metric; `content/analytics/` does not.
- That dropping the spoken subscribe raises loops. The four looping Shorts
  are too few to split by last line, and this repository does not store
  their narration.
- That naming worn skeletons stops a new one forming. The model may pick
  another three-word start and repeat it.
- That a need on the HUD instead of a citation raises "% who chose to view".
  The first kinetic phrase was already need-language; the HUD is smaller and
  arrives 0.42s later.

## 6. Owner-only

- Phone verification on the seven channels that still cannot set a custom
  thumbnail. Until then YouTube picks a frame.
- Sleep-length long-forms on The Secret Place, which is the only format in
  this niche that turns a small audience into counted watch hours.
- Nothing here raises how many videos a channel publishes in a day.

## Next step

Read `average_view_percent` on Shorts published after this change. Today's
looping four sit at 110–191%; the median of the rest on that list is under
70%. One Short above 100% is the first sign the loop is working.
