# The slot is when the work starts

17 November 2026. Times are UTC unless marked WAT (Nigeria, UTC+1).

Seventh reading of the day, one layer out from the picture and the sound: **the
clock.** Every published video carries the instant it went public, and every
channel has a slot it was made for. This is the distance between the two,
counted over the receipts rather than assumed from the crons.

## The short answer

- **A slot is the moment work becomes due, not the moment a video appears.**
  `scripts/produce_plan.py` says so in its own docstring, and the arithmetic of
  the pipeline enforces it: the cron fires at the slot, the render then starts,
  and with `PUBLISH_LEAD_MINUTES = 0` the upload is public the instant it
  finishes.
- **Measured over the newest 40 long-forms** (14 November 04:53 → 17 November
  07:37): each went public a **median 108 minutes after its own slot**; **none
  within an hour**; 8 of the 36 delivered after their slot took **more than three
  hours**, 3 more than six. The p90 is 380 minutes.
- **The floor is the render, not the cron.** The thirteen fastest of those 36
  landed 70–95 minutes after their slot and nothing has ever beaten 70 in the
  current mix. That is the pipeline's own length: render, encode, upload.
- **The one video ever published on its slot minute is the one that was
  scheduled.** The Healing Balm, 13 November: uploaded 17:32:45, public
  19:14:00 — to the second. It is the only receipt that carries `uploaded_at`,
  and the only long-form whose offset from its own slot is 0.
- **Two channels share a slot, and they publish seconds apart.** On 17 November
  The Morning Altar and The Praise Garden went public **2 seconds apart**
  (07:37:51 and 07:37:49); on 14 November two others were 11 seconds apart. Of
  the 373 receipts in the corpus, **243 (65%) have another channel's video within
  ten minutes**.
- **Reported, not changed.** The switch that would put a video on its slot
  minute exists, is tested, and is off. Turning it on is not one line: it moves
  five crons, ten slot values, and every time a human is told.
- **The figure is now printed daily.** The monitor's `publish instant` line reads
  it from the receipts, so a change to the schedule shows up the next morning
  instead of being assumed.

## 1. What a slot is, in the code

| Piece | Where | What it says |
|---|---|---|
| The slots | `.github/workflows/produce.yml:20-24` | five crons, `14 6`, `14 10`, `14 14`, `14 19`, `14 23` — 06:14 … 23:14 |
| Which channel's long-form, which slot | `scripts/produce_plan.py:68` `LONGFORM_SLOT_UTC` | two channels to a slot, ten channels over five |
| What a slot means | `scripts/produce_plan.py` (`slot_owes_longform`) | "the moment work for a release becomes due" |
| When it goes public | `scripts/produce_plan.py:51` `PUBLISH_LEAD_MINUTES` | `0` — "every upload is public the moment it finishes" |
| The safe way to land on the minute | `pipeline/publish_schedule.py` | finish early, upload private with `publishAt`, let YouTube publish |

The receipt keeps the distinction honest: `published_at` is the **public** time
even for a scheduled upload (`pipeline/run.py` — "the receipt is then dated with
the moment the video goes PUBLIC, because that is what every reader of
`published_at` means by it"), with `uploaded_at` and `scheduled_publish` beside
it. So every offset below is the real one, not an upload time.

## 2. What the receipts say

**The newest 40 long-forms** (the sample the daily monitor prints). Thirty-six
were delivered after their own slot; four were made at a different slot (see
§4) and are counted apart.

| Reading | Value |
|---|---|
| Median, after its own slot | **108 min** |
| p25 / p75 / p90 | 86 / 156 / 380 min |
| Worst | **619 min** (The Healing Balm, 14 November) |
| Within 30 min | **0 of 36** |
| Within 60 min | **0 of 36** |
| Within 2 h | 20 of 36 |
| Within 3 h | 28 of 36 |
| 70–95 min (the fast group) | **13** |
| 95–180 min | 14 |
| over 3 h | 8 |

By slot, over the same sample:

| Slot (UTC) | WAT | Long-forms | Median delay |
|---|---|---|---|
| 06:14 | 7:14am | 8 | **89 min** |
| 10:14 | 11:14am | 6 | 144 min |
| 14:14 | 3:14pm | 6 | 108 min |
| 19:14 | 8:14pm | 8 | 101 min |
| 23:14 | 12:14am | 8 | **169 min** |

The 06:14 slot is the healthiest and the 23:14 the worst — the overnight run is
the one that has to start on time for the small hours to work, and it is the one
that drifts most.

Measured across the whole corpus instead (132 long-forms, 3–17 November), the
distance from each video to the nearest of the five crons — not to its own slot,
so catch-up legs are not penalised:

| Within | Long-forms |
|---|---|
| 15 min of a cron | 10 of 132 (8%) |
| 30 min | 20 (15%) |
| 60 min | 40 (30%) |
| 120 min | 115 (87%) |

Median distance to the nearest slot: **84 minutes**.

## 3. The floor is the render

Nothing in the current mix has appeared sooner than **70 minutes** after its
slot, and thirteen of the 36 sit between 70 and 95 — a tight cluster, which is
what a fixed-length job looks like, not what an unreliable scheduler looks like.
A settled cron plus a 70-minute render produces a 70-minute delay every time.

The repo has measured the two halves before, over 47 runs and 96 channel legs on
8–13 November (`docs/SCHEDULED_PUBLISHING_2026-11-13.md`): GitHub started the
scheduled run **34 to 423 minutes** after the slot, median 218, and one
channel's render and upload took a median 44 minutes (p90 77, longest 128). The
parallel lanes brought the render half down; they cannot move the start. With
the render at about 70 minutes and the lead off, the shortest possible gap is the
render, and everything else is lateness stacked on top.

The one video that beat it is the one that did not need to wait:

| The Healing Balm, 13 November | |
|---|---|
| uploaded | `2026-11-13T17:32:45Z` (6:32pm WAT) |
| public | `2026-11-13T19:14:00Z` (8:14pm WAT) — **on the minute** |
| offset from its slot | **0.0 min** |

Its receipt is the only one in `content/published/` carrying `uploaded_at`, and
`scheduled_publish` now reads `false` because the video has since gone live and
`scripts/confirm_scheduled_publish.py` clears the flag. It is also the only
long-form in the corpus whose offset is zero; the next closest are 2 minutes (10
November) and 8 minutes (13 November), both before the current mix.

## 4. Four long-forms were made for a different slot

Four of the 40 went public **before** their own channel's slot: The Guided Path
at 00:11 (10 hours before its 10:14 slot), The Family Altar at 07:34 (6.7 hours
before its 14:14 slot), The Provision Table at 07:33 (2.7 hours before 10:14),
The Midday Watch at 05:16 (9 hours before 14:14). These are not late videos;
they are the two safety nets in `produce_plan.longform_due()`:

* **catch-up** — the newest long-form is older than `LONGFORM_CATCH_UP_HOURS`
  (26), so the slot that runs next makes one;
* **fallback** — the slot has no Short to show for itself and the newest
  long-form is older than `LONGFORM_FALLBACK_MIN_GAP_HOURS` (7), so the slot
  makes a long-form rather than come up empty.

A slot that has to be filled produces a video at whatever hour it is. That is
the right behaviour — a channel must not go dark because one Short failed — but
it is why "one long-form a day at its own slot" is a target and not a fact: the
network published 36 long-forms with a slot in four days, and four of them were
made by a net rather than by their own slot.

## 5. Shorts ride the same wave

241 published Shorts, measured the same way: **median 59 minutes** from the
nearest cron, **16% within 30 minutes**. Their hour histogram over the corpus
peaks after each cron (07:xx 26, 11:xx 30, 15:xx 27, 20:xx 30, 23:xx 26) and is
thin in between. Nothing about a Short is scheduled either; each appears when its
leg finishes.

## 6. The network publishes together

Two channels share each slot, and both legs run in the same workflow run, so they
finish within minutes of each other — sometimes seconds:

| Same-slot long-form pairs | |
|---|---|
| Pairs where both delivered | 21 |
| Median gap between the two channels | 40.6 min |
| Closest | **0.03 min — 2 seconds** (The Morning Altar 07:37:51, The Praise Garden 07:37:49, 17 November) |
| Within 1 min / 5 min / 15 min | 1 / 3 / 7 |
| Within 60 min | 11 of 21 |

Across the whole corpus, **243 of 373 receipts (65%) have another channel's
video published within ten minutes**, and 250 cross-channel pairs fall within
five minutes on five separate days. For a viewer this is invisible. For the
platform that decides whether ten channels are "a coordinated network of
channels" — the phrase in the spam policy this repository already measures itself
against (`scripts/channel_protection.py`) — it is the most literal form of the
signal: not similar videos, **simultaneous** ones.

## 7. The switch, and what turning it on would cost

`pipeline/publish_schedule.py` already does the whole job: finish early, upload
private with `publishAt`, let YouTube publish on the minute. It is off, and the
reason is arithmetic rather than doubt:

```
public time = production slot + PUBLISH_LEAD_MINUTES
```

- `PUBLISH_LEAD_MINUTES = 0` today. `publish_target()` also refuses any lead that
  reaches the next slot, and any target less than `PUBLISH_MARGIN_MINUTES` (15)
  away — in either case the upload publishes at once.
- Turning it on is **one change in two places** by design: set the lead, and move
  the five crons earlier by the same amount so the public times stay where they
  are. Because `LONGFORM_SLOT_UTC` is compared as the `HH:MM` of a cron (and a
  test holds the two together), the table's ten values and their comments move
  too, and so does every human-facing name of a slot in `README.md`, `STATE.md`
  and the workflow comments.
- **What a lead can absorb.** With the lead at L, a run that starts D minutes
  after its (moved) cron and renders in R minutes publishes on the minute only if
  `D + R + 15 ≤ L`. The shortest gap between slots is 4 hours, so L must stay
  under 240. At a three-hour lead (180 of those 240) and a render of about 76
  minutes — the p90 the repo measured for one channel's leg — a run may start
  **89 minutes late** and still land on the minute (180 − 76 − 15). At the 70
  minutes seen here it is 95. The one measurement of that lateness in this
  repository is 34–423 minutes, median 218 — so a three-hour lead would still miss
  on a substantial share of days, and would publish late rather than not at all,
  which is exactly what the module promises.
- **One trial has ever run.** The Healing Balm, above. No receipt currently
  carries `scheduled_publish: true`; the mechanism has been idle since 13
  November.

## Measured, changed, unproven, owner-only

**Measured.** 373 receipts with a full instant (132 long-forms, 241 Shorts); the
newest 40 long-forms a median **108 min** after their own slot with **0 of 36
within an hour**; a 70-minute floor; per-slot medians 89 / 144 / 108 / 101 / 169;
**65%** of receipts with another channel within ten minutes, the closest pair
**2 seconds** apart; one video ever on its slot minute, and that one scheduled.

**Changed (documentation and one measurement — no schedule change):**

| Change | Figure it moves | Where it is read |
|---|---|---|
| `scripts/automation_monitor.py` gains `publish_delays()` and a **`publish instant`** outcome | long-forms a median **108 min** after their slot; **0 of 36** within 30 min; the worst channel and minute; says plainly that scheduling is off | `python -m scripts.automation_monitor`, every daily health run |
| `README.md` line 18 | "release slots" with no time attached → says a slot is when work starts, with the measured 108 minutes | `README.md` |
| `README.md` line 42 | `produce.yml` "cron (06:14 & 14:14 UTC)" — **two** slots, stale since 14 November — → five crons, named | `README.md` |
| `STATE.md` §7 | the schedule table now says what a slot is and what the delay has measured | `STATE.md` |

Nothing about when a video is made or published changed. The monitor line reports
and never fails a run: it is `ok` severity, and a reporter that cannot read the
receipts says so instead of costing the monitor.

**Unproven.** That landing on the minute is worth anything: YouTube does not
publish per-video traffic by minute, and `content/analytics/` holds none. The
case for it is scheduling logic and the bedtime premise of the channel, not a
measured lift.

**Owner-only.** Setting `PUBLISH_LEAD_MINUTES` (with the crons, the slot table
and the docs moved by the same amount), and the idea underneath it — publishing
each channel at its own best hour — which needs the Analytics permission granted
on each channel and the slot accounting changed to date by upload, as
`docs/AUTOMATION_UPGRADES_2026-11-14.md` §9 sets out.

**One next step.** The smallest honest experiment is one slot, not the network:
set a lead on the 19:14 slot only, move that one cron to 17:14, and leave the
other four alone. Then the figure to read is the one the monitor now prints —
**long-forms public within one minute of their slot: 0 of 36 → 1, 2, 3** — and
if a late start eats it, the same line says so instead of the owner finding a
9:34pm "8:14pm" video.
