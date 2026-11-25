# The first frame, and the passage supply

25 November 2026. Two questions asked on the same day, both answered by counting.

## 1. Why does the feed stop after a few dozen impressions?

The engaged-view report, read for the first time on 25 November, answers part of
it:

| | |
| :--- | ---: |
| Plays across the 35 most-viewed videos | **4,336** |
| **Engaged** plays — those that lasted | **1,739 = 40.1%** |
| Median engaged share per video | **40.3%** |
| Median average percentage viewed | **68.1%** |

**Six in ten plays end almost immediately.** That is the swipe, and it is decided
before the narration is heard.

And it is a *different* problem from retention. Engaged share and average
percentage viewed correlate at **ρ = −0.09**; engaged share and views at
**ρ = −0.19**. The people who stay watch most of it; the ones who leave are not
leaving because the middle dragged. Treating the two as one lever — which this
repository had been doing — measures the wrong half.

## 2. What is on the first frame

`pipeline/first_frame.py` reads all 634 authored Short specs and reports what the
renderer will actually draw in second one:

| | |
| :--- | ---: |
| Shorts that put a **scripture reference** on the first frame | **456 of 639 (71%)** |
| Distinct first-frame compositions | **1** |
| Words a stranger must read before hearing a word (median) | **15** |
| Median time the first caption ends | **8s** |

Two findings, one of them embarrassing:

- **The authoring prompt forbids a citation on the first frame** — "its kicker is
  the need in 2-4 words… never the scripture reference". Seven in ten specs
  shipped with one anyway. `short_script.authoring_defects` already rejects it for
  *new* authoring, and caught 418 of the 420 it could see; the ones it missed were
  spelled out ("HOSEA SIX ONE", "NEHEMIAH TWO FOUR"). That guard now recognises
  spelled-out numbers. The counter in `pipeline/first_frame.py` was wrong in the
  other direction: it did not recognise numbered books, so it missed every
  "1 PETER 5:7", "2 TIMOTHY 1:7" and "1 JOHN 4:18" — 456 is the corrected count.

**Five Shorts now exist in the other composition.** `pipeline/passage_short.py`
writes a spec from the passage itself, with the need on scene one and the citation
arriving with the verse on scene two. It exists so a channel never runs dry when
no model is available, and the five it wrote for `prayer2` are what makes the
comparison possible at all — one composition against another, on the same
channel, in the same month.
- **Every first frame is the same composition.** A photograph, a kicker, a sub,
  and three stacked lines of kinetic type — 634 out of 634. Nothing about the
  frame has ever varied, so nothing about it has ever been tested. That is why
  the swipe rate sits at one number for every channel.

**What this does not claim:** which composition keeps more people. Only twelve
Shorts could be matched to their spec on 25 November, and twelve cannot separate
one design from another. The module writes that limit into its own report rather
than recommending a change it cannot support — the same mistake as the
three-second-caption rule, which the same day's data contradicted (238 views from
a 10-second opening, 58 from a 7-second one).

## 3. Why the Shorts runway keeps running dry

The daily CI went red because `secret-place` held one ready Short where the
repository asks for two. One number; three different causes.
`pipeline/shorts_supply.py` counts all three ways a channel can make its next
Short — a seasonal Short, a companion Short for a queued long-form, or a
standalone Short from a passage — per channel:

| channel | ready | standalone passages | companion long-forms |
| :--- | ---: | ---: | ---: |
| prayer2 | **0** | 11 | 0 |
| prayer3 | 3 | 0 | 0 |
| prayer5 | 8 | 0 | 0 |
| secret-place | 2 | 0 | 0 |
| … | | | |

`prayer2` had **zero** of both on 25 November and could not have authored another
Short at all. It does now: the passages that were still unclaimed anywhere on the
network were added to its evergreen list and to its roadmap (rows 0973–0980), and
its roadmap headroom went from 7 unqueued scriptures to 15.

**The uncomfortable finding:** for every channel, every roadmap passage already
has a Short. The network is not short of schedule — it has consumed its
scripture. Six channels had an empty standalone pool before this change. Adding
passages helps, but the supply of *unclaimed* passages is the real constraint on
how long this can continue at five Shorts a channel a day, and it should be
planned for rather than discovered by a red test.

## What changed

- `pipeline/first_frame.py` — the audit above, written to
  `content/research/first_frame.json`, in the daily growth job.
- `pipeline/shorts_supply.py` — the per-channel supply reading in
  `content/research/shorts_supply.json`, daily.
- `pipeline/passage_short.py` — writes a spec from a passage, need first, verse
  second. Five written for `prayer2`; marked `authored_by: passage-template` so
  they are never mistaken for a model's prose.
- `pipeline/short_script.py` — the first-frame citation guard now catches
  spelled-out numbers; specs now record who authored them.
- `prayer2`: eight roadmap rows and twelve evergreen passages, chosen only after
  checking every list on the network, the seasonal tables included.
