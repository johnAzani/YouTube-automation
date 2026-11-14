# What the numbers say (14 November 2026)

Source: the public counts in the ten "Channel Analytics Snapshot" issues of
13 November, 11:51pm to 11:57pm UTC (#414 to #423). Views, likes and comments
only; watch time and click-through rate are not available to the automation.

## 1. The numbers

| Channel | Subscribers | Long videos | Views on long videos | Shorts | Views on Shorts | Share of views from Shorts |
|---|---|---|---|---|---|---|
| The Secret Place | 1,250 | 14 | 55 | 23 | 2,676 | 98% |
| The Morning Altar | 31 | 22 | 98 | 24 | 1,973 | 95% |
| The Midday Watch | 10 | 14 | 39 | 15 | 1,198 | 97% |
| The Midnight Watch | 13 | 10 | 7 | 9 | 688 | 99% |
| The Family Altar | 0 | 8 | 20 | 5 | 187 | 90% |
| The Healing Balm | 2 | 7 | 1 | 5 | 101 | 99% |
| The Provision Table | 3 | 8 | 19 | 6 | 342 | 95% |
| The Covenant Shield | 0 | 5 | 15 | 2 | 7 | 32% |
| The Praise Garden | 2 | 4 | 4 | 1 | 292 | 99% |
| The Guided Path | 0 | 3 | 3 | 1 | 49 | 94% |
| **All ten** | | **95** | **261** | **91** | **7,513** | **97%** |

- Long videos: 2.7 views each on average, median 1, best 20. 35 of the 95 have
  no views at all. 7 likes in total.
- Shorts: 83 views each on average, median 65, best 393. 8.8% of views leave a
  like, which is high.
- 11 Shorts have 5 views or fewer; 8 of those are on The Family Altar, The
  Healing Balm and The Covenant Shield, all three launched on 11 November.

## 2. What they say

1. **Shorts are where people are.** The same scriptures, the same voice, the
   same day: the Short is watched about 30 times more than the long video. A
   long video costs two to four speech requests and 30 to 80 minutes of
   rendering; a Short costs one request and a few minutes.
2. **Well-known passages travel further.** The best Shorts are Psalm 27 (393),
   Psalm 100:4 (292, in under a day, on a channel with two subscribers),
   Psalm 91 (266), Psalm 23 (258), Numbers 6:24-26 (208), Isaiah 54:17 (188 in
   a few hours). The best long videos are Psalm 91:11-12, Psalm 121:7-8 and
   Psalm 46.
3. **Every channel's Shorts open with one sentence skeleton.** All five Family
   Altar Shorts begin "Gather your home and loved ones in faith..."; the
   Midnight Watch ones "Rise in spirit at this midnight hour..."; the Healing
   Balm ones "Bring every weary burden...". The prompt supplied that line, so
   the model used it. The numbers cannot say how much this costs: the same
   skeleton drew 104 and 82 views on some days and 0 on others. The one Short
   that opened on the listener's own moment ("Before you ask God for anything
   today...") drew 292 views in under a day on a channel with two subscribers,
   which is one video, not a pattern. The reason to change it is that the first
   seconds decide whether a Short is watched or swiped, and that ten channels
   each repeating one opening line is the templated pattern YouTube's
   monetisation review looks for.
4. **Shorter Shorts did somewhat better.** Among Shorts at least two days old:
   90 to 99 words, median 114 views (10 Shorts); 100 to 114 words, 70 (22);
   115 to 129 words, 56 (20). Few videos and mixed channels, so a nudge, not a
   rule.
5. **Three new channels had a dead day.** The Family Altar and The Healing
   Balm each published three Shorts on 12 November, their second day; those six
   drew 0 to 4 views. Their Shorts on the day before and the day after drew 41
   to 104. The cause is not known.

## 3. What changed today

- **41 queued long videos retitled** to lead with the need, in the words a
  person would search ("Morning Prayer for Guidance and Direction: Psalm
  25:4-5" instead of "Psalm 25:4-5 Morning Prayer | The Morning Altar"). The
  scripture reference stays in every title; Short keys, slugs and references
  are unchanged. 13 thumbnail lines that were cut mid-phrase or duplicated the
  title were replaced with whole lines ("LEAD ME IN" is now "SHOW ME THY
  WAYS"). These are the uploads of roughly the next two days on all channels.
- **Shorts are asked for their own first sentence** (`pipeline/short_script.py`).
  The channel's stock invitation is given to the model as mood, not as line
  one; the model is shown the openings the channel has already used and told
  not to start that way; the first sentence is at most 16 words and names the
  listener's moment. No greeting, no channel name, no "don't scroll".
- **Shorts are asked to be about 105 words** (95 to 118) instead of 120. The
  validator's limits (90 to 165) are unchanged, so nothing that passed before
  is rejected now.

Applies to Shorts written from now on. The 47 Shorts already queued keep their
openings; they are spoken-word specs bound to captions and timings, and editing
them by hand risks a Short that fails to render and blocks its channel's queue.

## 4. Monetisation: where this stands

What YouTube requires, per channel: 1,000 subscribers, and either 4,000 hours
watched on long videos in 12 months or 10 million Shorts views in 90 days.

| | Needed per channel | Now |
|---|---|---|
| Subscribers | 1,000 | One channel has 1,250. The other nine have 0 to 31. |
| Hours on long videos | 4,000 | 261 views across all ten channels. If every one of them had watched a whole video, about 35 hours in total. |
| Shorts views | 10,000,000 in 90 days | 7,513 across all ten channels since launch. |

Ten channels monetised within a month is not reachable from these numbers. The
gap is a factor of several hundred to several thousand, and no change to
titles, sound or schedule closes a gap that size in four weeks. Saying
otherwise would be dishonest.

What is realistic to aim for:

- **The Secret Place** already has the subscribers. It needs watch hours. Its
  long videos are six to eight minutes and are watched once or twice each. The
  only format in this niche that produces hours from a small audience is the
  sleep-length video (one hour or more, played while falling asleep), and the
  channel's subject is exactly that. It is not built; see section 5.
- **The other nine** need subscribers first, and Shorts are the only thing
  bringing strangers to them. More and better Shorts is the route.
- A breakout (a Short or a long video that reaches tens of thousands) is what
  changes the picture, and it cannot be scheduled. What can be done is to make
  more well-aimed attempts where the audience already is, and to learn from
  each one.

## 5. Decisions waiting on the owner

1. **Change the mix. Decided and built the same day** (the owner handed the
   decision over): one long video and five Shorts a day per channel, the same
   six uploads as before, with Shorts written on their own. See
   `docs/SHORTS_FIRST_MIX_2026-11-14.md`.
2. **Sleep-length videos on The Secret Place.** One a week, an hour long, made
   from the channel's own published night prayers with music between them.
   Needs the spoken audio of each prayer to be kept (today it survives only
   in a short-lived build cache) and a light renderer, since the normal one would take about
   six hours for a one-hour video.
3. **Phone verification.** Seven channels still cannot set a custom thumbnail
   (The Midnight Watch, The Family Altar, The Healing Balm, The Provision
   Table, The Covenant Shield, The Praise Garden, The Guided Path). Each needs
   youtube.com/verify once. Until then their videos show a frame YouTube picks.

## 6. Not known

- Whether the retitled long videos draw more views. The first of them publish
  on 14 November; the next snapshot issues will show it.
- Why six Shorts on two new channels drew almost nothing on 12 November
  (section 2, point 5).
- Whether a Short's own opening sentence raises its views. Shorts written from
  today will show it.
- Watch time, how far people watch, and click-through rate, for any video.
