# Why the Shorts get few views — what the channel's own numbers say

24 November 2026. Written because "the views are too low" is true and useless on
its own. Every figure here is read from `content/analytics/` and
`content/research/`, from this repository's own channels. Nothing is a target
someone else reported.

## The state, measured

| | |
| :--- | ---: |
| Shorts published in 21 days, ten channels | **536** (25.5 a day) |
| Measured views per Short, network mean | **69** |
| Median views per Short, by channel | **10 to 182** |
| Shorts-feed share of all views, 28 days | **94%** (5,133 of 5,480) |
| Plays per video that were never widened past 50 impressions | **76 of 113** |

## 1. It is not a volume problem

The pipeline published 536 Shorts in three weeks without missing a slot. Adding
more output changes nothing, because the ceiling is not effort.

## 2. Each Short is auditioned in front of a few dozen people, then dropped

The feed gives a new Short a small test audience. If that sample does not look
promising, it stops. The median video in `secret-place.reach.json` was shown
**24 times**; 76 of 113 videos never passed 50 impressions. That is not
rejection — it is a failed audition.

The decision is made in **the first second or two**, before a title is read,
before a description exists. Which means every downstream improvement — better
tips, longer descriptions, clever hooks in the script — is fighting the wrong
battle.

## 3. The channel's identity tells the feed nothing

This is the strongest signal in the data, and it is uncomfortable.

Titles come from `short_title_template` in `pipeline/channel_capabilities.py`.
Ranked by measured views per Short:

| Channel | Median views | Fixed part of every title |
| :--- | ---: | :--- |
| prayer8 · Covenant Shield | **182** | Prayer for **Divine Protection** |
| prayer9 · Praise Garden | 90 | Prayer of **Thanksgiving** |
| prayer10 · Guided Path | 84 | Prayer for **God's Guidance** |
| prayer7 · Provision Table | 53 | Prayer for **Open Doors & Provision** |
| prayer4 · Midnight Watch | 52 | **Midnight Prayer** |
| prayer6 · Healing Balm | 34 | Healing Prayer for **Peace & Strength** |
| prayer5 · Family Altar | 31 | **Family Prayer Over Your Home** |
| secret-place · Secret Place | 25 | Prayer **Before You Sleep** |
| prayer2 · Morning Altar | 11 | Prayer **at Sunrise** |
| prayer3 · Midday Watch | 10 | Prayer **at Noon** |

The three highest-named needs — protection, gratitude, guidance — are all in the
top four. "At Sunrise" and "at Noon" name a *clock*, not a need, and they are the
two worst channels. Psalm 91 sits at the top of this channel's search terms; the
channel that names "Divine Protection" in every title is the one that gets 182
views a Short.

**What this does not prove:** that renaming a channel multiplies its views by
seven. Ten channels over three weeks, with unknown differences in account age and
history, cannot settle that. What it does show is that the phrase doing the work
is absent from exactly the channels doing worst, and that costs nothing to fix.

## 4. Retention does predict reach — but slowly

Across 35 measured videos on The Secret Place, average percentage viewed and
views correlate at **ρ = 0.46**. Split by retention:

| | Median views |
| :--- | ---: |
| Bottom third by percentage watched | **37** |
| Top third by percentage watched | **118** |
| Watched past the end (looped, ≥100%) | 114 (8 videos) |
| Not looped | 78 (27 videos) |

So keeping people does raise views. But the gap between "81% watched" and "63%
watched" moves a Short from ~37 to ~118 views — **3×, not 100×**. Retention
matters and is worth fixing. It will not, by itself, produce the audience you
want.

## 5. One belief in this repository is wrong, and the data says so

`pipeline/short_script.py` requires the first caption to end in about three
seconds, on the reasoning that the swipe happens then. Joined against the 22
Short receipts that can be matched to a spec:

| First caption ends | Views |
| :--- | ---: |
| 10s — John 14:1-3 | **238** (the highest) |
| 7s — Philippians 4:8 | 58 (the lowest) |
| 6–15s | 51 to 238 |

A 10-second opening out-performed a 7-second one by 4×, and the spread inside
the group is far larger than any trend across it. The rule was imposed on a
mechanism the repository could not measure, and the measurement available does
not support it. That is worth saying plainly rather than quietly keeping.

## 6. The measurement itself was hiding the Shorts

Until today, the per-video Analytics report was sorted by **watch time** and
capped at 50 rows. A three-hour long-form outranks every Short ever published, so
the report described **35 videos while 536 Shorts had gone out**: 28 of The
Secret Place's own 64 Shorts were missing from it, and the newest measured Short
was six days old. Every conclusion drawn about Shorts from that file was drawn
about an unrepresentative sample.

Fixed: the reader now asks a second time sorted by **views**, and requests
**engaged views** — the pre-2025 count of plays that lasted. Since 31 March 2025
`views` counts any play at all, so engaged views are the only stay-or-swipe
signal the API exposes. Studio's actual "viewed vs swiped away" is in no API;
this is a proxy, and the page says so.

## What to change, in order of leverage

1. **Name the need in the fixed title, not the clock.** `prayer3` "Prayer at Noon"
   → "Prayer for Strength at Noon". `prayer2` "at Sunrise" → "for a Fresh Start".
   This is the highest-leverage, lowest-risk change available, and it is
   currently untested rather than rejected.
2. **Keep the title formats that already work.** Protection, thanksgiving and
   guidance stay named exactly as they are.
3. **Read engaged views before touching the hooks.** The next Analytics read
   answers "did they stay or swipe" for the first time; changing the first three
   seconds before seeing it would be guessing again.
4. **Grant Analytics to the other nine channels.** `prayer2` at 11 views and
   `prayer8` at 182 look identical from here except for one number. That is the
   largest blind spot left, and it is the one thing that needs a person.

## What is not claimed

- Any view count, subscriber count, or date.
- That a title rewrite multiplies views. Directed evidence needs a before-and-after
  across weeks on the same channel.
- That retention is unimportant. It correlates; it is just not sufficient.

---

## Appendix — what changed in the code as a result

1. **`scripts/analytics_reader.py` asks for the Shorts.** A second per-video
   report sorted by `views`, plus `engagedViews` on both. A new section on the
   analytics page — *"What was started, and what was actually watched"* — reports
   the engaged share and says plainly that it is a proxy for Studio's
   "viewed vs swiped away".
2. **`prayer2` and `prayer3` titles name a need.** "Prayer at Sunrise" →
   "Prayer for Fresh Start at Sunrise"; "Prayer at Noon" → "Prayer for Strength
   at Noon". Every searchable word that was there before is still there.
3. **An overflowing title can no longer lose its promise.**
   `pipeline/short_release.py` used `label | hook` when a title passed the
   character limit — which kept the hook and dropped the phrase that names what
   the Short is for. It now keeps the template's words and shortens the hook;
   only if there is no room for any hook does the trailing flourish go, and the
   promise stays.
