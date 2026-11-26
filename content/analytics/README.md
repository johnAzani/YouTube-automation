# Where each channel stands (YouTube Analytics)

Written by `scripts/analytics_reader.py`. Do not edit: the next run rewrites it.
YouTube's figures run about two days behind. Revenue is never written here.

## Where the counted watch hours come from

Written by `pipeline/growth_score.py`; the detail is in `content/research/growth_score.json`. Hours watched in the Shorts feed do not count toward the Partner Program, so the doors below are the ones that do.

| Door | Hours, shared window |
| :--- | ---: |
| suggested | 55 |
| Shorts feed — does not count | 24.5 |
| yt search | 1 |
| home subs | 1.1 |
| other pages | 3.3 |
| playlist | 0 |
| notifications | 0.1 |
| ext url | 1.1 |
| direct unknown | 2 |
| channel page | 0.58 |
| sound pages | 0 |

**Counted: 56 hours (63.1% of all watch hours read).**

The threshold asks 58.5 hours a day for the 67 days left before it doubles; the channels run at 3.4 a day.

**Release length: 16 minutes.** the median view of a measured video is 16.3 minutes (across 8 videos); a release is not built longer than that

Night tail: `hold` — kept.

Long-form retention, median of videos with a reading: **10.5% watched**. A Short is excluded from this figure: a looping Short reports past 100%.

### Which thumbnail concept earns the click

Written by `pipeline/thumbnail_campaign.py`. The pack renders three concepts; a rotation puts a different one live on each release, so the click rate that follows can be compared across videos. A per-video Test & Compare is Studio-only: the Data API can neither open one nor read which variant won.

| Concept | Videos | Impressions | Click rate |
| :--- | ---: | ---: | ---: |
| hook | 2 | 0 | — (too few impressions) |
| quiet | 5 | 0 | — (too few impressions) |
| poster | 1 | 0 | — (too few impressions) |

### How long a release should be

A view is watched for a median of **16.3 minutes** across 8 measured videos. A release is not built longer than that, so length outside the prayer is time nobody spends.

The night tail is the problem: `16` — 91% of every published minute is never watched.

### What is actually reachable

Written by `pipeline/realistic_ceiling.py`. Every figure below is measured or is a documented level, never a promise.

| Lever | Hours a day |
| :--- | ---: |
| as it stands | 1.6 |
| click rate to 4% | 4.5 |
| watch time to 3 minutes and a 4% click rate | 4.5 |

The threshold asks 59.7 hours a day; the channels produce 1.558. With both format levers at their documented levels it would be 4.55. To reach the threshold at a 4% click rate and the measured watch time, YouTube would have to serve 5,497 impressions a day where it serves 418. Impressions are chosen by YouTube's recommendation system from how viewers respond, so that is the honest distance: it is reach, not metadata.

## Toward the Partner Program

| Channel | Subscribers (need 1,000) | Watch hours, 365 days (need 4,000) | Shorts views, 90 days (need 10,000,000) | Long-form hours a day, last 28 days (need 11) | Read |
| :--- | ---: | ---: | ---: | ---: | :--- |
| The Secret Place | 1,270 | 77.8 | 5,493 | 2.3 | 2026-11-26 |

Ads need the subscribers and either the watch hours or the Shorts views. Watch hours counted here are long-form and live only: time watched in the Shorts feed does not count. A year of the daily figure in the last column is what the 365-day total becomes. YouTube Studio's Earn page holds the official count.

Not granted Analytics access yet: The Morning Altar, The Midday Watch, The Midnight Watch, The Family Altar, The Healing Balm, The Provision Table, The Covenant Shield, The Praise Garden, The Guided Path.

## The Secret Place

Last 28 days (2026-10-29 to 2026-11-26): 5,543 views, 89.1 watch hours (63.4 long-form and live, 25.7 Shorts). Over 365 days: 77.8 hours long-form and live, 76.8 hours Shorts.

Where viewers came from, last 28 days:

| Source | Views | Watch hours |
| :--- | ---: | ---: |
| Shorts feed | 4,788 | 24 |
| YouTube search | 264 | 1 |
| Suggested videos | 223 | 55.5 |
| Home and subscriptions | 110 | 1.4 |
| Other YouTube pages | 57 | 3.3 |
| Channel page | 42 | 0.55 |
| Other sites and apps | 30 | 1.1 |
| Notifications | 11 | 0.1 |
| Direct or unknown | 7 | 2 |
| Playlists | 2 | 0 |
| Shorts sound pages | 1 | 0 |

What viewers typed into YouTube search to find this channel, last 90 days:

| Words typed | Views | Watch hours |
| :--- | ---: | ---: |
| psalm 91 | 8 | 0.02 |
| psalm 31 | 7 | 0.15 |
| grace for purpose night prayer today | 5 | 0.08 |
| psalm 27 explained | 4 | 0.05 |
| divine office night prayer for today | 2 | 0.02 |
| night prayer before going to bed | 2 | 0 |
| psalm 34 | 2 | 0 |
| psalm 42 | 2 | 0 |
| psalms 91 | 2 | 0 |
| psalmul 91 | 2 | 0 |
| 91 psalm | 1 | 0 |
| 91 psalm prayer | 1 | 0 |

13 other search(es) in YouTube's top 25 were not about prayer or scripture and are not listed.

Videos by watch time, 365 days (up to 50):

| Video | Watch hours | Views | Average watched |
| :--- | ---: | ---: | ---: |
| [When Exhaustion Weighs on Your Soul: Isaiah 40:28-31](https://youtu.be/XLXi986WZ_k) | 20.8 | 61 | 19:24 (10.6%) |
| [Bedtime Prayer for a Troubled Heart: John 14:27 / The Secret Place](https://youtu.be/uGkV42GvplM) | 10.6 | 49 | 13:32 (7.2%) |
| [Bedtime Prayer for Anxiety and Overthinking: Philippians 4:6-7](https://youtu.be/YsHGDAO8uRE) | 7.1 | 9 | 47:33 (25.4%) |
| [Night Prayer When Dread Keeps You Awake: 2 Timothy 1:7](https://youtu.be/IhL8prNsgaU) | 6.5 | 12 | 39:08 (21%) |
| [Bedtime Prayer When You Are Worn Out: Matthew 11:28-30](https://youtu.be/EmLY_qhrc7c) | 6.3 | 31 | 19:03 (10.2%) |
| [Night Prayer to Quiet a Racing Mind: Isaiah 26:3-4 / The Secret Place](https://youtu.be/t00bsmMtC-s) | 4.8 | 70 | 8:47 (4.7%) |
| [When the Night Feels Too Dark: Psalm 139:11-12 / The Secret Place](https://youtu.be/VPAFfGNkCGs) | 2.8 | 18 | 10:34 (5.7%) |
| [Say This Psalm 23 Prayer Before You Sleep / Divine Peace #Shorts](https://youtu.be/kLgHN57fb1w) | 2.1 | 260 | 1:17 (146%) |
| [Say This Psalm 27 Prayer Before You Sleep / Fear No Evil #Shorts](https://youtu.be/KkPAtMLoGf4) | 2 | 394 | 0:46 (75.4%) |
| [Say This Psalm 62:1-2 Prayer Before You Sleep / The Secret Place #Sho…](https://youtu.be/-kl7Qg8lQhk) | 1.9 | 111 | 3:34 (363%) |
| [Say This Psalm 16:7-8 Prayer Before You Sleep / Never Be Moved #Shorts](https://youtu.be/d0Et8L_6y1o) | 1.8 | 139 | 1:52 (191%) |
| [Night Prayer When You Feel Afraid: Isaiah 41:10 / The Secret Place](https://youtu.be/nBujp4zoTCk) | 1.6 | 37 | 4:42 (2.5%) |
| [Say This John 14:27 Prayer Before You Sleep / The Secret Place #Shorts](https://youtu.be/dmwIvRt6Ve8) | 1.5 | 177 | 1:04 (109%) |
| [Say This Psalm 42:8 Prayer Before You Sleep / He Is With You #Shorts](https://youtu.be/D4SsfbWpMK4) | 1.3 | 118 | 1:47 (238%) |
| [Say This John 14:1-3 Prayer Before You Sleep / Your Tired Soul #Shorts](https://youtu.be/SAA1fLyeNgo) | 0.97 | 239 | 0:32 (73.2%) |
| [Psalm 91:11-12 Night Prayer / Angels Guard Your Home & Sleep](https://youtu.be/dgvGl0EZyYE) | 0.92 | 25 | 2:30 (39.5%) |
| [Say This Psalm 56:3 Prayer Before You Sleep / The Secret Place #Shorts](https://youtu.be/uSsaVvsLsfU) | 0.9 | 194 | 0:32 (63.5%) |
| [Say This Psalm 91 Prayer Before You Sleep / Divine Protection #Shorts](https://youtu.be/SG69BbNlfRw) | 0.83 | 267 | 0:25 (64.9%) |
| [Say This Isaiah 30:15 Prayer Before You Sleep / Isaiah 30:15 #Shorts](https://youtu.be/57j_VQcPFlI) | 0.77 | 82 | 1:21 (150%) |
| [Say This Psalm 18:2 Prayer Before You Sleep / Safe Stronghold #Shorts](https://youtu.be/jhOlEJvNg-0) | 0.73 | 126 | 0:54 (98.8%) |
| [Say This Philippians 4:6-7 Prayer Before You Sleep / Tonight #Shorts](https://youtu.be/QHm6Z2sfpnc) | 0.67 | 115 | 0:45 (66%) |
| [Say This Psalm 4:4 Prayer Before You Sleep / Commune With Your Heart…](https://youtu.be/fsnBaSiXhHY) | 0.67 | 123 | 0:37 (69.5%) |
| [Say This Psalm 31:5 Prayer Before You Sleep / Redeemed In Peace #Shor…](https://youtu.be/nHTVsgHaLpE) | 0.58 | 98 | 0:44 (71.3%) |
| [Say This 1 Peter 5:7 Prayer Before You Sleep / 1 Peter 5:7 #Shorts](https://youtu.be/GQT7eKz9MAE) | 0.57 | 120 | 0:35 (81.3%) |
| [Say This Psalm 34 Prayer Before You Sleep / Angels Stand Watch #Shorts](https://youtu.be/fTYu1V5GHUE) | 0.53 | 129 | 0:49 (91.9%) |
| [Say This Psalm 37:7 Prayer Before You Sleep / The Secret Place #Shorts](https://youtu.be/5ekShDmycic) | 0.53 | 54 | 1:27 (129%) |
| [Say This Psalm 103:1-5 Prayer Before You Sleep / Night Prayer #Shorts](https://youtu.be/y1Vt4YVBLdQ) | 0.47 | 78 | 0:58 (100%) |
| [Say This Psalm 139:11-12 Prayer Before You Sleep / The Secret Place #…](https://youtu.be/avnYVdvDmkc) | 0.47 | 51 | 1:02 (99.6%) |
| [Bedtime Prayer to Let Go of Worry: 1 Peter 5:7 / The Secret Place](https://youtu.be/mzA1qTbk1Kc) | 0.45 | 6 | 4:05 (2.2%) |
| [Say This Isaiah 41:10 Prayer Before You Sleep / The Secret Place #Sho…](https://youtu.be/nZO6mwej0Is) | 0.42 | 69 | 0:42 (67.9%) |
| [Psalm 37:7 Bedtime Prayer / Rest in the Lord & Fret Not](https://youtu.be/sAyMduXhoeQ) | 0.4 | 8 | 3:27 (50.5%) |
| [Say This Matthew 28:20 Prayer Before You Sleep / Constant Presence #S…](https://youtu.be/T3HVq07iMzM) | 0.38 | 101 | 0:27 (49.7%) |
| [Say This Psalm 91:11-12 Prayer Before You Sleep / Angelic Night Guard…](https://youtu.be/dqKjQaJbU0c) | 0.38 | 151 | 0:23 (46.2%) |
| [Say This Psalm 139:7-10 Prayer Before You Sleep / The Secret Place #S…](https://youtu.be/6Y9d1w6Cvzg) | 0.37 | 175 | 0:24 (58.1%) |
| [Say This 2 Timothy 1:7 Prayer Before You Sleep / Mind #Shorts](https://youtu.be/XyFODtqpNkU) | 0.37 | 78 | 0:34 (69%) |
| [Say This Matthew 11:28-30 Prayer Before You Sleep / The Secret Place…](https://youtu.be/GBNCiP8UTS8) | 0.33 | 69 | 0:47 (81.3%) |

#### What was started, and what was actually watched

Of 4,496 plays across the 36 most-viewed videos, **1,773 were engaged views** — plays that lasted rather than started. That 39.4% is the nearest thing the Analytics API offers to YouTube Studio's "viewed vs swiped away"; Studio does not expose that figure to any API, so it is a proxy, not the number itself.

| Video | Views | Engaged | Average watched |
| :--- | ---: | ---: | ---: |
| [KkPAtMLoGf4](https://youtu.be/KkPAtMLoGf4) | 394 | 146 | 0:46 (75.4%) |
| [SG69BbNlfRw](https://youtu.be/SG69BbNlfRw) | 267 | 108 | 0:25 (64.9%) |
| [kLgHN57fb1w](https://youtu.be/kLgHN57fb1w) | 260 | 96 | 1:17 (146%) |
| [SAA1fLyeNgo](https://youtu.be/SAA1fLyeNgo) | 239 | 102 | 0:32 (73.2%) |
| [uSsaVvsLsfU](https://youtu.be/uSsaVvsLsfU) | 194 | 96 | 0:32 (63.5%) |
| [dmwIvRt6Ve8](https://youtu.be/dmwIvRt6Ve8) | 177 | 84 | 1:04 (109%) |
| [6Y9d1w6Cvzg](https://youtu.be/6Y9d1w6Cvzg) | 175 | 48 | 0:24 (58.1%) |
| [dqKjQaJbU0c](https://youtu.be/dqKjQaJbU0c) | 151 | 55 | 0:23 (46.2%) |
| [xkpfupurX-0](https://youtu.be/xkpfupurX-0) | 147 | 41 | 0:20 (42.4%) |
| [d0Et8L_6y1o](https://youtu.be/d0Et8L_6y1o) | 139 | 56 | 1:52 (191%) |
| [fTYu1V5GHUE](https://youtu.be/fTYu1V5GHUE) | 129 | 38 | 0:49 (91.9%) |
| [jhOlEJvNg-0](https://youtu.be/jhOlEJvNg-0) | 126 | 47 | 0:54 (98.8%) |
| [fsnBaSiXhHY](https://youtu.be/fsnBaSiXhHY) | 123 | 59 | 0:37 (69.5%) |
| [GQT7eKz9MAE](https://youtu.be/GQT7eKz9MAE) | 120 | 56 | 0:35 (81.3%) |
| [D4SsfbWpMK4](https://youtu.be/D4SsfbWpMK4) | 118 | 42 | 1:47 (238%) |

Thumbnails, 2026-10-15 to 2026-11-24 (37 days of YouTube's daily reach files): shown 16,081 times, clicked 211 times, a click rate of 1.3%.
A thumbnail is counted where YouTube shows one (search, home, suggested, the channel page). The Shorts feed shows none, so Shorts watched there are not in these figures.

Videos by times shown (up to 25):

| Video | Thumbnail shown | Clicks | Click rate |
| :--- | ---: | ---: | ---: |
| [Night Prayer to Quiet a Racing Mind: Isaiah 26:3-4 / The Secret Place](https://youtu.be/t00bsmMtC-s) | 1,858 | 19 | 1% |
| [Bedtime Prayer When You Are Worn Out: Matthew 11:28-30](https://youtu.be/EmLY_qhrc7c) | 1,793 | 14 | 0.78% |
| [When Exhaustion Weighs on Your Soul: Isaiah 40:28-31](https://youtu.be/XLXi986WZ_k) | 1,454 | 37 | 2.5% |
| [Bedtime Prayer for a Troubled Heart: John 14:27 / The Secret Place](https://youtu.be/uGkV42GvplM) | 1,418 | 36 | 2.5% |
| [When the Night Feels Too Dark: Psalm 139:11-12 / The Secret Place](https://youtu.be/VPAFfGNkCGs) | 1,352 | 10 | 0.74% |
| [Bedtime Prayer for Anxiety and Overthinking: Philippians 4:6-7](https://youtu.be/YsHGDAO8uRE) | 1,128 | 5 | 0.44% |
| [Night Prayer When You Feel Afraid: Isaiah 41:10 / The Secret Place](https://youtu.be/nBujp4zoTCk) | 1,103 | 18 | 1.6% |
| [Night Prayer When Dread Keeps You Awake: 2 Timothy 1:7](https://youtu.be/IhL8prNsgaU) | 856 | 5 | 0.58% |
| [Psalm 91:11-12 Night Prayer / Angels Guard Your Home & Sleep](https://youtu.be/dgvGl0EZyYE) | 581 | 18 | 3.1% |
| [Bedtime Prayer to Let Go of Worry: 1 Peter 5:7 / The Secret Place](https://youtu.be/mzA1qTbk1Kc) | 284 | 4 | 1.4% |
| [Psalm 37:7 Bedtime Prayer / Rest in the Lord & Fret Not](https://youtu.be/sAyMduXhoeQ) | 202 | 5 | 2.5% |
| [pbpPdG7_DQk](https://youtu.be/pbpPdG7_DQk) | 167 | 3 | 1.8% |
| [Zw0pjLM5hEI](https://youtu.be/Zw0pjLM5hEI) | 131 | 3 | 2.3% |
| [Psalm 91:5-6 Night Prayer / Deliverance From Terror by Night](https://youtu.be/rb6X37vQt7o) | 130 | 0 | 0% |
| [Say This Psalm 121 Prayer Before You Sleep / He Who Keeps You #Shorts](https://youtu.be/xkpfupurX-0) | 129 | 0 | 0% |
| [Say This Psalm 37:7 Prayer Before You Sleep / The Secret Place #Shorts](https://youtu.be/5ekShDmycic) | 125 | 0 | 0% |
| [Surrendering Every Heavy Burden: Psalm 31:5 / The Secret Place](https://youtu.be/r3nA7BgZpP4) | 123 | 1 | 0.81% |
| [Say This Matthew 6:34 Prayer Before You Sleep / The Secret Place #Sho…](https://youtu.be/EiF_FNNAhCU) | 109 | 1 | 0.92% |
| [Say This Psalm 91 Prayer Before You Sleep / Divine Protection #Shorts](https://youtu.be/SG69BbNlfRw) | 108 | 1 | 0.93% |
| [Say This Psalm 27 Prayer Before You Sleep / Fear No Evil #Shorts](https://youtu.be/KkPAtMLoGf4) | 104 | 0 | 0% |
| [Say This Psalm 34 Prayer Before You Sleep / Angels Stand Watch #Shorts](https://youtu.be/fTYu1V5GHUE) | 91 | 0 | 0% |
| [Say This Psalm 18:2 Prayer Before You Sleep / Safe Stronghold #Shorts](https://youtu.be/jhOlEJvNg-0) | 88 | 0 | 0% |
| [Bedtime Prayer for Sleep Without Fear: Proverbs 3:24-26](https://youtu.be/3xrS2BqNeWA) | 86 | 1 | 1.2% |
| [Night Prayer When You Lie Awake: Psalm 63:6-7 / The Secret Place](https://youtu.be/P2JDAtPkryI) | 85 | 2 | 2.4% |
| [Say This Psalm 91:11-12 Prayer Before You Sleep / Angelic Night Guard…](https://youtu.be/dqKjQaJbU0c) | 77 | 0 | 0% |

## What each channel is trying in its titles

A phrase comes from the words viewers typed into YouTube search, or from wording shared by the titles of the most-watched videos of the channel's kind. It is offered to the title writer and judged by the channel's own long prayers, each counted once at a few days old: kept when titles with it drew clearly more views a video, dropped when they drew clearly fewer (`pipeline/lessons.py`). No two channels try the same phrase.

| Channel | Phrase | Where it came from | Now | Long prayers with / without | Views with / without | Since |
| :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| The Morning Altar | day with god | titles of the most-watched videos of this kind | being tried | 1 / 5 | 21 / 15 | 2026-11-17 |
| The Morning Altar | morning worship | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 36 | 2026-11-17 |
| The Midday Watch | morning prayer | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 40 | 2026-11-17 |
| The Midday Watch | start your day | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 40 | 2026-11-17 |
| The Midday Watch | blessed morning | titles of the most-watched videos of this kind | being tried | 0 / 0 | 0 / 0 | 2026-11-24 |
| The Provision Table | financial breakthrough | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 41 | 2026-11-17 |
| The Provision Table | carry this scripture | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 41 | 2026-11-17 |
| The Provision Table | breakthrough comes | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 41 | 2026-11-17 |
| The Covenant Shield | holy spirit | titles of the most-watched videos of this kind | being tried | 0 / 0 | 0 / 0 | 2026-11-24 |
| The Praise Garden | thanksgiving worship | titles of the most-watched videos of this kind | being tried | 0 / 6 | 0 / 30 | 2026-11-17 |
| The Guided Path | prayer for peace | titles of the most-watched videos of this kind | being tried | 0 / 0 | 0 / 0 | 2026-11-24 |
